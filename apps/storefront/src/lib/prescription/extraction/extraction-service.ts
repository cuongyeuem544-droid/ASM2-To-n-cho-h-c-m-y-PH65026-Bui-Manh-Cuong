import prisma from "@/lib/prisma";
import {
  ExtractionStatus,
  DrugMatchStatus,
  ExtractionApiResponseData,
  ExtractedMedicationData,
  DrugCandidate,
  MAX_EXTRACTION_RETRY_ATTEMPTS,
  RawAiExtractionOutput,
} from "./extraction-types";
import {
  OcrNotCompletedError,
  ExtractionAlreadyProcessingError,
  MedicationNotFoundError,
  ExtractionError,
} from "./extraction-errors";
import { NotFoundError, ValidationError } from "../errors";
import { PrescriptionExtractionProvider } from "./ai-provider";
import { NativeRestAiProvider } from "./native-rest-provider";
import { mockExtractionProvider, MockExtractionProvider } from "./mock-provider";
import { DrugRepository, drugRepository } from "./drug-repository";
import { DrugNormalizer } from "./drug-normalizer";

export class ExtractionService {
  private aiProvider: PrescriptionExtractionProvider;
  private drugRepo: DrugRepository;
  private db: typeof prisma;

  constructor(
    aiProvider?: PrescriptionExtractionProvider,
    drugRepo: DrugRepository = drugRepository,
    dbClient: typeof prisma = prisma
  ) {
    if (aiProvider) {
      this.aiProvider = aiProvider;
    } else {
      // Tự động chọn provider dựa trên biến môi trường AI_PROVIDER
      const providerType = process.env.AI_PROVIDER || "mock";
      if (providerType === "openai" || providerType === "gemini") {
        this.aiProvider = new NativeRestAiProvider();
      } else {
        this.aiProvider = mockExtractionProvider;
      }
    }
    this.drugRepo = drugRepo;
    this.db = dbClient;
  }

  /**
   * Khởi chạy bóc tách dữ liệu đơn thuốc có cấu trúc bằng AI (Phase 4)
   */
  public async runExtraction(
    prescriptionId: string,
    options?: {
      forceRetry?: boolean;
    }
  ): Promise<ExtractionApiResponseData> {
    if (!prescriptionId || typeof prescriptionId !== "string") {
      throw new ValidationError("Mã định danh đơn thuốc không hợp lệ.", 400, "INVALID_ID");
    }

    const startTime = Date.now();

    // 1. Kiểm tra sự tồn tại của đơn thuốc và kết quả OCR Phase 3
    const prescription = await this.db.prescription.findUnique({
      where: { id: prescriptionId },
      include: {
        ocrResult: {
          include: {
            pages: { orderBy: { pageNumber: "asc" } },
          },
        },
        extraction: {
          include: {
            medications: true,
          },
        },
      },
    });

    if (!prescription) {
      throw new NotFoundError(`Không tìm thấy đơn thuốc với mã ID: ${prescriptionId}`);
    }

    // 2. Bắt buộc Phase 3 OCR phải hoàn thành thành công
    const ocrResult = prescription.ocrResult;
    if (!ocrResult || ocrResult.status !== "COMPLETED") {
      throw new OcrNotCompletedError(
        "Đơn thuốc chưa hoàn tất nhận diện ký tự OCR (Phase 3). Vui lòng hoàn thành OCR trước khi chạy trích xuất cấu trúc AI."
      );
    }

    // 3. Kiểm soát tính Idempotent và chống race-condition
    const existingExtraction = prescription.extraction;

    if (existingExtraction) {
      if (existingExtraction.status === "PROCESSING") {
        throw new ExtractionAlreadyProcessingError(
          "Tiến trình phân tích AI đang được thực hiện. Vui lòng chờ kết quả hoàn tất."
        );
      }

      if (
        (existingExtraction.status === "COMPLETED" ||
          existingExtraction.status === "NEEDS_REVIEW") &&
        !options?.forceRetry
      ) {
        // Trả về kết quả hiện tại ngay lập tức
        return this.formatExtractionData(prescriptionId, existingExtraction);
      }

      if (existingExtraction.status === "FAILED" && !options?.forceRetry) {
        if (existingExtraction.attemptCount >= MAX_EXTRACTION_RETRY_ATTEMPTS) {
          throw new ExtractionError(
            `Đơn thuốc đã thử phân tích AI tối đa ${MAX_EXTRACTION_RETRY_ATTEMPTS} lần nhưng không thành công.`,
            422,
            "MAX_RETRY_EXCEEDED"
          );
        }
      }
    }

    const currentAttempt = (existingExtraction?.attemptCount || 0) + 1;

    // 4. Cập nhật trạng thái sang PROCESSING
    await this.db.$transaction([
      this.db.prescription.update({
        where: { id: prescriptionId },
        data: { status: "EXTRACTION_PROCESSING" },
      }),
      this.db.prescriptionExtraction.upsert({
        where: { prescriptionId },
        create: {
          prescriptionId,
          ocrResultId: ocrResult.id,
          provider: this.aiProvider.name,
          model: (this.aiProvider as any).model || "default",
          status: "PROCESSING",
          rawOcrText: ocrResult.fullText,
          attemptCount: currentAttempt,
        },
        update: {
          provider: this.aiProvider.name,
          model: (this.aiProvider as any).model || "default",
          status: "PROCESSING",
          rawOcrText: ocrResult.fullText,
          attemptCount: currentAttempt,
          errorMessage: null,
          errorCode: null,
        },
      }),
    ]);

    try {
      // 5. Chuẩn bị dữ liệu đầu vào cho AI Provider
      const pagesInput = (ocrResult.pages || []).map((p) => ({
        pageNumber: p.pageNumber,
        text: p.text,
      }));

      // 6. Thực thi trích xuất cấu trúc AI
      const extractionResult = await this.aiProvider.extract({
        prescriptionId,
        rawOcrText: ocrResult.fullText,
        pages: pagesInput,
      });

      const aiData: RawAiExtractionOutput = extractionResult.data;

      // 7. Quy trình Chuẩn hóa tên thuốc & Đối soát danh mục (Drug Normalization & Matching)
      const processedMedications: any[] = [];
      let matchedCount = 0;
      let needsReviewCount = 0;
      let unmatchedCount = 0;

      for (const med of aiData.medications) {
        const rawName = med.rawName.trim();
        const normalizedName = DrugNormalizer.getSearchKey(rawName);

        // Đối chiếu với DrugRepository xác định
        const matchResult = await this.drugRepo.findCandidates(rawName, med.strength, 3);

        let matchStatus: DrugMatchStatus = matchResult.matchStatus;
        let matchedDrugId: string | null = null;
        let matchedDrugName: string | null = null;
        let matchScore: number | null = null;

        if (matchStatus === "MATCHED" && matchResult.bestMatch) {
          matchedDrugId = matchResult.bestMatch.drugId;
          matchedDrugName = matchResult.bestMatch.brandName;
          matchScore = matchResult.bestMatch.score;
          matchedCount++;
        } else if (matchStatus === "NEEDS_REVIEW") {
          matchedDrugId = matchResult.bestMatch?.drugId || null;
          matchedDrugName = matchResult.bestMatch?.brandName || null;
          matchScore = matchResult.bestMatch?.score || null;
          needsReviewCount++;
        } else {
          matchStatus = "UNMATCHED";
          unmatchedCount++;
        }

        processedMedications.push({
          rawName,
          normalizedName,
          strength: med.strength ? DrugNormalizer.normalizeStrengthSpacing(med.strength) : null,
          dosage: med.dosage || null,
          frequency: med.frequency || null,
          duration: med.duration || null,
          quantity: med.quantity != null ? String(med.quantity) : null,
          route: med.route || null,
          instructions: med.instructions || null,
          sourcePage: med.sourcePage || 1,
          sourceText: med.sourceText || null,
          matchStatus,
          matchedDrugId,
          matchedDrugName,
          matchScore,
          candidatesJson: JSON.stringify(matchResult.candidates),
          reviewStatus: "PENDING_REVIEW",
        });
      }

      // Xác định trạng thái tổng thể của quá trình bóc tách
      let overallStatus: ExtractionStatus = "COMPLETED";
      if (needsReviewCount > 0 || unmatchedCount > 0 || processedMedications.length === 0) {
        overallStatus = "NEEDS_REVIEW";
      }

      const processingDuration = Date.now() - startTime;

      let savedExtractionId = "";

      // 8. Lưu kết quả cấu trúc vào CSDL thông qua Database Transaction
      await this.db.$transaction(async (tx) => {
        const savedExtraction = await tx.prescriptionExtraction.update({
          where: { prescriptionId },
          data: {
            status: overallStatus,
            provider: extractionResult.provider,
            model: extractionResult.model,
            patientName: aiData.patientName || null,
            patientAge: aiData.patientAge != null ? String(aiData.patientAge) : null,
            patientGender: aiData.patientGender || null,
            doctorName: aiData.doctorName || null,
            diagnosis: aiData.diagnosis || null,
            medicationCount: processedMedications.length,
            matchedCount,
            needsReviewCount,
            unmatchedCount,
            processingTimeMs: processingDuration,
            errorMessage: null,
            errorCode: null,
          },
        });

        savedExtractionId = savedExtraction.id;

        // Xóa các dòng thuốc cũ nếu là lượt retry
        await tx.prescriptionMedication.deleteMany({
          where: { extractionId: savedExtraction.id },
        });

        // Tạo các dòng thuốc mới
        if (processedMedications.length > 0) {
          await tx.prescriptionMedication.createMany({
            data: processedMedications.map((m) => ({
              ...m,
              extractionId: savedExtraction.id,
            })),
          });
        }

        // Cập nhật trạng thái Prescription
        const prescriptionNextStatus =
          overallStatus === "COMPLETED" ? "EXTRACTION_COMPLETED" : "EXTRACTION_NEEDS_REVIEW";

        await tx.prescription.update({
          where: { id: prescriptionId },
          data: { status: prescriptionNextStatus },
        });
      });

      console.info(
        `[AI Extraction Completed] Đơn thuốc ${prescriptionId} hoàn tất phân tích (${processedMedications.length} thuốc, Trạng thái: ${overallStatus}).`
      );

      // 9. Nạp lại bản ghi hoàn chỉnh kèm danh sách thuốc để trả về
      return await this.getExtractionResult(prescriptionId);
    } catch (error: any) {
      console.error(`[AI Extraction Failed] Đơn thuốc ${prescriptionId} thất bại:`, error);

      const errMessage = error?.message || "Quá trình phân tích đơn thuốc bằng AI thất bại.";
      const errCode = error?.code || "EXTRACTION_FAILED";

      // Cập nhật trạng thái FAILED trong CSDL để phục vụ kiểm soát lỗi và audit
      try {
        await this.db.$transaction([
          this.db.prescription.update({
            where: { id: prescriptionId },
            data: { status: "EXTRACTION_FAILED" },
          }),
          this.db.prescriptionExtraction.update({
            where: { prescriptionId },
            data: {
              status: "FAILED",
              errorMessage: errMessage,
              errorCode: errCode,
              processingTimeMs: Date.now() - startTime,
            },
          }),
        ]);
      } catch (dbErr) {
        console.error("Không thể cập nhật lỗi Extraction vào CSDL:", dbErr);
      }

      throw error;
    }
  }

  /**
   * Lấy kết quả phân tích có cấu trúc của đơn thuốc
   */
  public async getExtractionResult(prescriptionId: string): Promise<ExtractionApiResponseData> {
    if (!prescriptionId) {
      throw new ValidationError("Mã định danh đơn thuốc không hợp lệ.", 400, "INVALID_ID");
    }

    const prescription = await this.db.prescription.findUnique({
      where: { id: prescriptionId },
      include: {
        extraction: {
          include: {
            medications: {
              orderBy: { createdAt: "asc" },
            },
          },
        },
      },
    });

    if (!prescription) {
      throw new NotFoundError(`Không tìm thấy đơn thuốc với mã ID: ${prescriptionId}`);
    }

    if (!prescription.extraction) {
      return {
        id: "",
        prescriptionId,
        status: "PENDING",
        provider: "",
        model: "",
        patientName: null,
        patientAge: null,
        patientGender: null,
        doctorName: null,
        diagnosis: null,
        medications: [],
        medicationCount: 0,
        matchedCount: 0,
        needsReviewCount: 0,
        unmatchedCount: 0,
        attemptCount: 0,
        processingTimeMs: null,
      };
    }

    return this.formatExtractionData(prescriptionId, prescription.extraction);
  }

  /**
   * Xác nhận hoặc chọn ứng viên thuốc từ phía người dùng/dược sĩ (Human Review)
   */
  public async confirmMedicationCandidate(
    prescriptionId: string,
    medicationId: string,
    payload: {
      action: "CONFIRM" | "CHOOSE_CANDIDATE" | "REJECT_UNKNOWN";
      candidateDrugId?: string;
    }
  ): Promise<ExtractedMedicationData> {
    const med = await this.db.prescriptionMedication.findUnique({
      where: { id: medicationId },
      include: { extraction: true },
    });

    if (!med || med.extraction.prescriptionId !== prescriptionId) {
      throw new MedicationNotFoundError("Không tìm thấy thông tin dòng thuốc yêu cầu xác nhận.");
    }

    let reviewStatus = med.reviewStatus;
    let userConfirmedDrugId = med.userConfirmedDrugId;
    let userConfirmedName = med.userConfirmedName;

    if (payload.action === "CONFIRM") {
      reviewStatus = "CONFIRMED";
      userConfirmedDrugId = med.matchedDrugId;
      userConfirmedName = med.matchedDrugName;
    } else if (payload.action === "CHOOSE_CANDIDATE") {
      if (!payload.candidateDrugId) {
        throw new ValidationError("Thiếu candidateDrugId khi chọn ứng viên thay thế.", 400, "INVALID_CANDIDATE");
      }
      const chosenDrug = await this.drugRepo.getById(payload.candidateDrugId);
      if (!chosenDrug) {
        throw new ValidationError("Không tìm thấy ứng viên thuốc chỉ định trong danh mục.", 400, "CANDIDATE_NOT_FOUND");
      }
      reviewStatus = "CONFIRMED";
      userConfirmedDrugId = chosenDrug.id;
      userConfirmedName = chosenDrug.brandName;
    } else if (payload.action === "REJECT_UNKNOWN") {
      reviewStatus = "REJECTED_UNKNOWN";
      userConfirmedDrugId = null;
      userConfirmedName = null;
    }

    const updatedMed = await this.db.prescriptionMedication.update({
      where: { id: medicationId },
      data: {
        reviewStatus,
        userConfirmedDrugId,
        userConfirmedName,
      },
    });

    // Kiểm tra xem tất cả các thuốc trong đơn đã được review xong chưa
    const allMeds = await this.db.prescriptionMedication.findMany({
      where: { extractionId: med.extractionId },
    });

    const isAllReviewed = allMeds.every((m) => m.reviewStatus !== "PENDING_REVIEW");
    if (isAllReviewed) {
      await this.db.prescriptionExtraction.update({
        where: { id: med.extractionId },
        data: { status: "COMPLETED" },
      });
      await this.db.prescription.update({
        where: { id: prescriptionId },
        data: { status: "EXTRACTION_COMPLETED" },
      });
    }

    let parsedCandidates: DrugCandidate[] = [];
    try {
      if (updatedMed.candidatesJson) {
        parsedCandidates = JSON.parse(updatedMed.candidatesJson);
      }
    } catch {
      // ignore
    }

    return {
      id: updatedMed.id,
      rawName: updatedMed.rawName,
      normalizedName: updatedMed.normalizedName,
      strength: updatedMed.strength,
      dosage: updatedMed.dosage,
      frequency: updatedMed.frequency,
      duration: updatedMed.duration,
      quantity: updatedMed.quantity,
      route: updatedMed.route,
      instructions: updatedMed.instructions,
      sourcePage: updatedMed.sourcePage,
      sourceText: updatedMed.sourceText,
      matchStatus: updatedMed.matchStatus as DrugMatchStatus,
      matchedDrugId: updatedMed.matchedDrugId,
      matchedDrugName: updatedMed.matchedDrugName,
      matchScore: updatedMed.matchScore,
      candidates: parsedCandidates,
      userConfirmedDrugId: updatedMed.userConfirmedDrugId,
      userConfirmedName: updatedMed.userConfirmedName,
      reviewStatus: updatedMed.reviewStatus as any,
    };
  }

  /**
   * Định dạng dữ liệu Extraction an toàn trả về cho Client
   */
  private formatExtractionData(
    prescriptionId: string,
    extraction: any
  ): ExtractionApiResponseData {
    const medications: ExtractedMedicationData[] = (extraction.medications || []).map(
      (m: any) => {
        let candidates: DrugCandidate[] = [];
        try {
          if (m.candidatesJson) {
            candidates = JSON.parse(m.candidatesJson);
          }
        } catch {
          // ignore
        }

        return {
          id: m.id,
          rawName: m.rawName,
          normalizedName: m.normalizedName,
          strength: m.strength,
          dosage: m.dosage,
          frequency: m.frequency,
          duration: m.duration,
          quantity: m.quantity,
          route: m.route,
          instructions: m.instructions,
          sourcePage: m.sourcePage,
          sourceText: m.sourceText,
          matchStatus: m.matchStatus,
          matchedDrugId: m.matchedDrugId,
          matchedDrugName: m.matchedDrugName,
          matchScore: m.matchScore,
          candidates,
          userConfirmedDrugId: m.userConfirmedDrugId,
          userConfirmedName: m.userConfirmedName,
          reviewStatus: m.reviewStatus,
        };
      }
    );

    return {
      id: extraction.id,
      prescriptionId,
      status: extraction.status,
      provider: extraction.provider,
      model: extraction.model,
      patientName: extraction.patientName,
      patientAge: extraction.patientAge,
      patientGender: extraction.patientGender,
      doctorName: extraction.doctorName,
      diagnosis: extraction.diagnosis,
      medications,
      medicationCount: extraction.medicationCount,
      matchedCount: extraction.matchedCount,
      needsReviewCount: extraction.needsReviewCount,
      unmatchedCount: extraction.unmatchedCount,
      attemptCount: extraction.attemptCount,
      processingTimeMs: extraction.processingTimeMs,
      errorMessage: extraction.errorMessage || undefined,
      errorCode: extraction.errorCode || undefined,
      completedAt: extraction.updatedAt ? extraction.updatedAt.toISOString() : undefined,
    };
  }
}

export const extractionService = new ExtractionService();
