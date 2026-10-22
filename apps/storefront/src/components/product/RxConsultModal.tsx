"use client";

import React, { useState, useRef } from "react";
import { Product } from "@/types";
import { motion, AnimatePresence } from "framer-motion";
import {
  X,
  Stethoscope,
  UploadCloud,
  CheckCircle2,
  ShieldCheck,
  AlertCircle,
  Clock,
  Loader2,
  FileText,
} from "lucide-react";
import { Button } from "../ui/Button";
import { PHARMACY_CONTACT } from "@/lib/constants";

interface RxConsultModalProps {
  product: Product | null;
  isOpen: boolean;
  onClose: () => void;
}

const ALLOWED_MIME_TYPES = [
  "image/jpeg",
  "image/png",
  "image/webp",
  "application/pdf",
];
const MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024; // 10MB

export const RxConsultModal: React.FC<RxConsultModalProps> = ({
  product,
  isOpen,
  onClose,
}) => {
  const [phoneNumber, setPhoneNumber] = useState("");
  const [patientName, setPatientName] = useState("");
  const [notes, setNotes] = useState("");
  const [prescriptionFile, setPrescriptionFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSubmitted, setIsSubmitted] = useState(false);
  const [consultRequestId, setConsultRequestId] = useState<number | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  if (!isOpen || !product) return null;

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFileError(null);
    const file = e.target.files?.[0];
    if (!file) return;

    if (!ALLOWED_MIME_TYPES.includes(file.type)) {
      setFileError("Định dạng tệp không được hỗ trợ. Vui lòng tải file ảnh (JPG, PNG, WEBP) hoặc tài liệu PDF.");
      return;
    }

    if (file.size > MAX_FILE_SIZE_BYTES) {
      setFileError("Dung lượng tệp vượt quá giới hạn 10MB. Vui lòng giảm kích thước tệp.");
      return;
    }

    setPrescriptionFile(file);
  };

  const handleRemoveFile = (e: React.MouseEvent) => {
    e.stopPropagation();
    setPrescriptionFile(null);
    setFileError(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);

    const cleanPhone = phoneNumber.trim().replace(/\s+/g, "");
    if (!/^(0|\+84)(3|5|7|8|9)[0-9]{8}$/.test(cleanPhone)) {
      setErrorMessage("Số điện thoại không đúng định dạng di động Việt Nam (10 số).");
      return;
    }

    const cleanName = patientName.trim();
    if (!cleanName || cleanName.length < 2) {
      setErrorMessage("Vui lòng nhập họ và tên người bệnh (tối thiểu 2 ký tự).");
      return;
    }

    setIsSubmitting(true);

    let uploadedStorageKey: string | undefined = undefined;
    let uploadedFileName: string | undefined = undefined;

    try {
      // 1. Tải lên tệp đơn thuốc thật nếu có
      if (prescriptionFile) {
        const formData = new FormData();
        formData.append("file", prescriptionFile);

        const uploadRes = await fetch("/api/prescription/upload", {
          method: "POST",
          body: formData,
        });

        const uploadData = await uploadRes.json().catch(() => null);

        if (!uploadRes.ok || !uploadData?.success) {
          throw new Error(
            uploadData?.message ||
              "Không thể tải lên tệp đơn thuốc. Vui lòng kiểm tra lại tệp hoặc thử lại."
          );
        }

        uploadedStorageKey = uploadData?.prescriptionId || uploadData?.file?.name;
        uploadedFileName = prescriptionFile.name;
      }

      // 2. Gửi yêu cầu tư vấn chính thức tới backend
      const consultRes = await fetch("/api/prescription/consult", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          productId: product.dbId || parseInt(product.id.replace("pt-", ""), 10) || 0,
          patientName: cleanName,
          phoneNumber: cleanPhone,
          prescriptionFileName: uploadedFileName,
          storageKey: uploadedStorageKey,
          notes: notes.trim() || undefined,
        }),
      });

      const consultData = await consultRes.json().catch(() => null);

      if (!consultRes.ok || !consultData?.success) {
        throw new Error(
          consultData?.message ||
            "Máy chủ chưa thể tiếp nhận yêu cầu tư vấn. Vui lòng thử lại sau giây lát."
        );
      }

      // 3. Chỉ đánh dấu thành công khi máy chủ phản hồi 200 OK
      setConsultRequestId(consultData.requestId || null);
      setIsSubmitted(true);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Đã xảy ra sự cố kết nối. Vui lòng thử lại.";
      setErrorMessage(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleReset = () => {
    setIsSubmitted(false);
    setIsSubmitting(false);
    setPhoneNumber("");
    setPatientName("");
    setNotes("");
    setPrescriptionFile(null);
    setFileError(null);
    setErrorMessage(null);
    setConsultRequestId(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
    onClose();
  };

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
        {/* Backdrop */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={handleReset}
          className="absolute inset-0 bg-black/50 backdrop-blur-xs"
        />

        {/* Modal Window */}
        <motion.div
          initial={{ opacity: 0, scale: 0.95, y: 12 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: 12 }}
          transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
          className="relative w-full max-w-lg bg-white rounded-2xl shadow-xl border border-slate-200 overflow-hidden z-10 max-h-[92vh] flex flex-col"
        >
          {/* Header */}
          <div className="bg-brand-blue-600 text-white p-5 flex items-start justify-between border-b border-brand-blue-700 shrink-0">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-white/15 flex items-center justify-center text-white shrink-0 border border-white/20">
                <Stethoscope className="w-5 h-5" />
              </div>
              <div>
                <span className="text-[10px] font-bold tracking-wider uppercase text-brand-blue-100 bg-white/10 px-2.5 py-0.5 rounded-full inline-block mb-1">
                  Chuẩn Y Khoa • Tư Vấn Theo Toa
                </span>
                <h3 className="text-base font-bold leading-snug">
                  Tư Vấn Thuốc Kê Đơn Cùng Dược Sĩ
                </h3>
              </div>
            </div>
            <button
              onClick={handleReset}
              className="p-1.5 rounded-xl text-white/80 hover:text-white hover:bg-white/10 transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          <div className="p-6 overflow-y-auto">
            {!isSubmitted ? (
              <form onSubmit={handleSubmit} className="space-y-4">
                {/* Warning notice */}
                <div className="p-3.5 rounded-xl bg-amber-50 border border-amber-200 flex items-start gap-2.5">
                  <AlertCircle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                  <div className="text-xs text-amber-900 leading-relaxed">
                    <span className="font-bold">Quy định của Bộ Y Tế: </span>
                    Sản phẩm <span className="font-semibold">{product.name}</span> là thuốc kê đơn (Rx). Thuốc chỉ được cấp phát khi có đơn chỉ định hợp lệ của Bác sĩ. Dược sĩ Đại học H4CARE sẽ liên hệ xác nhận đơn thuốc của bạn.
                  </div>
                </div>

                {errorMessage && (
                  <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-start gap-2">
                    <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
                    <div className="flex-1">{errorMessage}</div>
                  </div>
                )}

                {/* Patient Information Inputs */}
                <div>
                  <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5">
                    Họ và tên người bệnh <span className="text-rose-500">*</span>
                  </label>
                  <input
                    type="text"
                    required
                    value={patientName}
                    onChange={(e) => setPatientName(e.target.value)}
                    placeholder="Ví dụ: Nguyễn Văn A"
                    disabled={isSubmitting}
                    className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 text-sm text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-1 focus:ring-brand-blue-500 focus:border-brand-blue-500 disabled:bg-slate-100"
                  />
                </div>

                <div>
                  <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5">
                    Số điện thoại nhận tư vấn <span className="text-rose-500">*</span>
                  </label>
                  <input
                    type="tel"
                    required
                    value={phoneNumber}
                    onChange={(e) => setPhoneNumber(e.target.value)}
                    placeholder="Ví dụ: 0912 345 678"
                    disabled={isSubmitting}
                    className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 text-sm text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-1 focus:ring-brand-blue-500 focus:border-brand-blue-500 disabled:bg-slate-100"
                  />
                </div>

                {/* Upload prescription box */}
                <div>
                  <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5">
                    Ảnh chụp đơn thuốc hoặc file PDF (nếu có)
                  </label>
                  <input
                    type="file"
                    ref={fileInputRef}
                    onChange={handleFileChange}
                    accept="image/jpeg,image/png,image/webp,application/pdf"
                    className="hidden"
                    disabled={isSubmitting}
                  />
                  <div
                    onClick={() => !isSubmitting && fileInputRef.current?.click()}
                    className="border-2 border-dashed border-slate-200 hover:border-brand-blue-400 rounded-xl p-4 text-center cursor-pointer transition-colors bg-slate-50 hover:bg-brand-blue-50/40"
                  >
                    <UploadCloud className="w-7 h-7 text-slate-400 mx-auto mb-1.5" />
                    {prescriptionFile ? (
                      <div className="space-y-1.5">
                        <p className="text-xs font-semibold text-emerald-600 flex items-center justify-center gap-1">
                          <CheckCircle2 className="w-3.5 h-3.5" />
                          Đã chọn tệp: {prescriptionFile.name}
                        </p>
                        <p className="text-[10px] text-slate-400">
                          Dung lượng: {(prescriptionFile.size / 1024).toFixed(1)} KB
                        </p>
                        <button
                          type="button"
                          onClick={handleRemoveFile}
                          className="text-[11px] text-rose-600 hover:underline inline-block mt-1 font-medium"
                        >
                          Xóa tệp và chọn lại
                        </button>
                      </div>
                    ) : (
                      <>
                        <p className="text-xs font-medium text-slate-700">
                          Bấm để tải lên ảnh chụp đơn thuốc hoặc file PDF
                        </p>
                        <p className="text-[10px] text-slate-400 mt-0.5">
                          Hỗ trợ định dạng JPG, PNG, WEBP, PDF (Tối đa 10MB)
                        </p>
                      </>
                    )}
                  </div>
                  {fileError && (
                    <p className="text-[11px] text-rose-600 mt-1">{fileError}</p>
                  )}
                </div>

                {/* Additional notes */}
                <div>
                  <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5">
                    Ghi chú thêm cho Dược sĩ (nếu có)
                  </label>
                  <textarea
                    rows={2}
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                    placeholder="Mô tả triệu chứng, tiền sử dị ứng hoặc yêu cầu đặc biệt..."
                    disabled={isSubmitting}
                    className="w-full px-3.5 py-2 rounded-xl border border-slate-200 text-xs text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-1 focus:ring-brand-blue-500 focus:border-brand-blue-500 disabled:bg-slate-100"
                  />
                </div>

                {/* Commitments */}
                <div className="pt-1 flex items-center justify-between text-[11px] text-slate-500">
                  <span className="flex items-center gap-1">
                    <ShieldCheck className="w-3.5 h-3.5 text-brand-emerald-500" />
                    Bảo mật dữ liệu bệnh án 100%
                  </span>
                  <span className="flex items-center gap-1">
                    <Clock className="w-3.5 h-3.5 text-brand-blue-500" />
                    Tư vấn trong giờ làm việc (8h00 - 21h30)
                  </span>
                </div>

                {/* Submit button */}
                <div className="pt-2">
                  <Button
                    type="submit"
                    variant="primary"
                    size="lg"
                    disabled={isSubmitting}
                    className="w-full shadow-xs"
                  >
                    {isSubmitting ? (
                      <span className="flex items-center justify-center gap-2">
                        <Loader2 className="w-4 h-4 animate-spin" />
                        Đang xử lý yêu cầu...
                      </span>
                    ) : (
                      "Gửi Yêu Cầu Cho Dược Sĩ Ngay"
                    )}
                  </Button>
                </div>
              </form>
            ) : (
              <div className="py-6 text-center space-y-4">
                <div className="w-16 h-16 rounded-full bg-emerald-100 text-emerald-600 flex items-center justify-center mx-auto shadow-xs">
                  <CheckCircle2 className="w-9 h-9" />
                </div>
                <div>
                  <h4 className="text-lg font-bold text-slate-900">
                    Đã Tiếp Nhận Yêu Cầu Tư Vấn!
                  </h4>
                  <p className="text-xs text-slate-600 mt-1.5 max-w-sm mx-auto leading-relaxed">
                    Dược sĩ chuyên môn của H4CARE đã nhận thông tin và sẽ liên hệ tới số{" "}
                    <span className="font-bold text-brand-blue-700">{phoneNumber}</span>{" "}
                    trong khung giờ làm việc của nhà thuốc (8h00 - 21h30 hàng ngày).
                  </p>
                </div>

                <div className="p-3.5 rounded-xl bg-brand-blue-50 border border-brand-blue-100 text-left text-xs space-y-1">
                  <p className="font-bold text-brand-blue-900">Chi tiết phiếu tư vấn:</p>
                  {consultRequestId && (
                    <p className="text-slate-600">• Mã phiếu: <span className="font-semibold text-brand-blue-700">#{consultRequestId}</span></p>
                  )}
                  <p className="text-slate-600">• Người bệnh: <span className="font-semibold">{patientName}</span></p>
                  <p className="text-slate-600">• Thuốc quan tâm: <span className="font-semibold">{product.name}</span></p>
                  {prescriptionFile && (
                    <p className="text-slate-600 flex items-center gap-1">• File đơn thuốc: <FileText className="w-3.5 h-3.5 text-emerald-600 inline" /> <span className="font-semibold text-emerald-700">{prescriptionFile.name}</span></p>
                  )}
                  <p className="text-slate-600">• Kênh hỗ trợ: <span className="font-semibold text-brand-blue-700">{PHARMACY_CONTACT.consultationPhoneDisplay}</span> ({PHARMACY_CONTACT.supportEmail})</p>
                </div>

                <Button variant="outline" size="md" onClick={handleReset} className="w-full">
                  Đóng cửa sổ
                </Button>
              </div>
            )}
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
};
