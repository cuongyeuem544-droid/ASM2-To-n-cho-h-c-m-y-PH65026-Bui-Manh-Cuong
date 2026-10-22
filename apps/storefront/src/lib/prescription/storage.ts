import fs from "fs/promises";
import path from "path";
import crypto from "crypto";
import { StorageError } from "./errors";

export interface StorageSaveResult {
  storageKey: string;
  storedFileName: string;
  filePath: string;
}

export interface StorageKeyInfo {
  storageKey: string;
  storedFileName: string;
  subDir: string;
}

export interface PrescriptionStorageService {
  saveFile(fileBuffer: Buffer | Uint8Array, extension: string): Promise<StorageSaveResult>;
  getFile(storageKey: string): Promise<Buffer | null>;
  deleteFile(storageKey: string): Promise<boolean>;
  generateStorageKey(extension: string): StorageKeyInfo;
}

let hasWarnedServerless = false;

/**
 * LocalPrescriptionStorage
 * Bộ điều hợp lưu trữ tệp tin cục bộ với khả năng nhận diện môi trường Serverless (Vercel).
 * - Trong môi trường Vercel/Serverless: Tự động chuyển hướng về /tmp/prescriptions kèm cảnh báo vòng đời.
 * - Trong môi trường Local Dev: Lưu vào process.cwd()/storage/prescriptions (đã được .gitignore bảo vệ).
 */
export class LocalPrescriptionStorage implements PrescriptionStorageService {
  private baseStorageDir: string;
  private isServerless: boolean;

  constructor(customBaseDir?: string) {
    this.isServerless = Boolean(
      process.env.VERCEL ||
      process.env.AWS_LAMBDA_FUNCTION_NAME ||
      process.env.NEXT_RUNTIME === "edge"
    );

    if (customBaseDir) {
      this.baseStorageDir = customBaseDir;
    } else if (this.isServerless) {
      this.baseStorageDir = path.join("/tmp", "prescriptions");
      if (!hasWarnedServerless) {
        console.warn(
          "[PrescriptionStorage Warning] Hệ thống đang chạy trên môi trường Serverless (Vercel) mà chưa cấu hình S3_BUCKET / R2_BUCKET. " +
          "Tệp đơn thuốc được lưu tạm thời tại /tmp/prescriptions và sẽ bị xóa khi container serverless giải phóng hoặc redeploy. " +
          "Để bảo toàn dữ liệu bệnh án bền vững, hãy cấu hình S3_BUCKET, S3_REGION, S3_ACCESS_KEY_ID, S3_SECRET_ACCESS_KEY."
        );
        hasWarnedServerless = true;
      }
    } else {
      this.baseStorageDir = path.join(process.cwd(), "storage", "prescriptions");
    }
  }

  public generateStorageKey(extension: string): StorageKeyInfo {
    const cleanExt = extension.startsWith(".") ? extension : `.${extension}`;
    const fileId = crypto.randomUUID();
    const storedFileName = `${fileId}${cleanExt}`;

    const now = new Date();
    const year = now.getFullYear().toString();
    const month = (now.getMonth() + 1).toString().padStart(2, "0");
    const subDir = path.join(year, month);
    const storageKey = `prescriptions/${year}/${month}/${storedFileName}`;

    return {
      storageKey,
      storedFileName,
      subDir,
    };
  }

  public async saveFile(
    fileBuffer: Buffer | Uint8Array,
    extension: string
  ): Promise<StorageSaveResult> {
    try {
      const { storageKey, storedFileName, subDir } = this.generateStorageKey(extension);
      const targetDir = path.join(this.baseStorageDir, subDir);

      await fs.mkdir(targetDir, { recursive: true });

      const targetPath = path.join(targetDir, storedFileName);
      const buffer = Buffer.isBuffer(fileBuffer) ? fileBuffer : Buffer.from(fileBuffer);

      await fs.writeFile(targetPath, buffer);

      return {
        storageKey,
        storedFileName,
        filePath: targetPath,
      };
    } catch (error) {
      console.error("[LocalPrescriptionStorage Error] Không thể lưu file:", error);
      throw new StorageError("Không thể ghi tệp đơn thuốc vào hệ thống lưu trữ an toàn.");
    }
  }

  public async getFile(storageKey: string): Promise<Buffer | null> {
    try {
      if (storageKey.includes("..") || path.isAbsolute(storageKey)) {
        throw new Error("Phát hiện đường dẫn storageKey không an toàn.");
      }

      const relativePart = storageKey.startsWith("prescriptions/")
        ? storageKey.replace("prescriptions/", "")
        : storageKey;

      const fullPath = path.join(this.baseStorageDir, relativePart);
      return await fs.readFile(fullPath);
    } catch {
      return null;
    }
  }

  public async deleteFile(storageKey: string): Promise<boolean> {
    try {
      if (storageKey.includes("..") || path.isAbsolute(storageKey)) {
        return false;
      }

      const relativePart = storageKey.startsWith("prescriptions/")
        ? storageKey.replace("prescriptions/", "")
        : storageKey;

      const fullPath = path.join(this.baseStorageDir, relativePart);
      await fs.unlink(fullPath);
      return true;
    } catch (error) {
      console.error(`[LocalPrescriptionStorage Error] Không thể xóa file ${storageKey}:`, error);
      return false;
    }
  }
}

/**
 * Helper ký AWS Signature V4 cho các dịch vụ S3 / Cloudflare R2 chuẩn
 */
function hmacSha256(key: string | Buffer, data: string): Buffer {
  return crypto.createHmac("sha256", key).update(data, "utf8").digest();
}

function sha256Hex(data: string | Buffer): string {
  return crypto.createHash("sha256").update(data).digest("hex");
}

function getSignatureKey(key: string, dateStamp: string, regionName: string, serviceName: string): Buffer {
  const kDate = hmacSha256("AWS4" + key, dateStamp);
  const kRegion = hmacSha256(kDate, regionName);
  const kService = hmacSha256(kRegion, serviceName);
  return hmacSha256(kService, "aws4_request");
}

/**
 * S3CompatiblePrescriptionStorage
 * Bộ điều hợp lưu trữ đám mây chuẩn S3 / Cloudflare R2 / MinIO.
 * Không phụ thuộc gói ngoài (sử dụng native Node.js crypto + fetch với SigV4).
 * Dữ liệu được lưu trữ ở chế độ PRIVATE (chống truy cập trái phép qua URL tĩnh).
 */
export class S3CompatiblePrescriptionStorage implements PrescriptionStorageService {
  private bucket: string;
  private region: string;
  private endpoint: string;
  private accessKeyId: string;
  private secretAccessKey: string;

  constructor(config?: {
    bucket?: string;
    region?: string;
    endpoint?: string;
    accessKeyId?: string;
    secretAccessKey?: string;
  }) {
    this.bucket = config?.bucket || process.env.S3_BUCKET || process.env.R2_BUCKET || "";
    this.region = config?.region || process.env.S3_REGION || "auto";
    this.endpoint = (config?.endpoint || process.env.S3_ENDPOINT || `https://s3.${this.region}.amazonaws.com`).replace(/\/+$/, "");
    this.accessKeyId = config?.accessKeyId || process.env.S3_ACCESS_KEY_ID || "";
    this.secretAccessKey = config?.secretAccessKey || process.env.S3_SECRET_ACCESS_KEY || "";

    if (!this.bucket || !this.accessKeyId || !this.secretAccessKey) {
      throw new StorageError("Thiếu cấu hình S3/R2 bắt buộc (bucket, accessKeyId, secretAccessKey).");
    }
  }

  public generateStorageKey(extension: string): StorageKeyInfo {
    const cleanExt = extension.startsWith(".") ? extension : `.${extension}`;
    const fileId = crypto.randomUUID();
    const storedFileName = `${fileId}${cleanExt}`;

    const now = new Date();
    const year = now.getFullYear().toString();
    const month = (now.getMonth() + 1).toString().padStart(2, "0");
    const subDir = `${year}/${month}`;
    const storageKey = `prescriptions/${year}/${month}/${storedFileName}`;

    return {
      storageKey,
      storedFileName,
      subDir,
    };
  }

  private signRequest(
    method: string,
    canonicalUri: string,
    payloadHash: string,
    now: Date
  ): { headers: Record<string, string>; url: string } {
    const amzDate = now.toISOString().replace(/[:-]|\.\d{3}/g, "");
    const dateStamp = amzDate.substring(0, 8);

    const host = new URL(this.endpoint).host;
    const url = `${this.endpoint}/${this.bucket}${canonicalUri}`;

    const canonicalHeaders = `host:${host}\nx-amz-content-sha256:${payloadHash}\nx-amz-date:${amzDate}\n`;
    const signedHeaders = "host;x-amz-content-sha256;x-amz-date";

    const canonicalRequest = [
      method,
      `/${this.bucket}${canonicalUri}`,
      "", // canonical query string
      canonicalHeaders,
      signedHeaders,
      payloadHash,
    ].join("\n");

    const credentialScope = `${dateStamp}/${this.region}/s3/aws4_request`;
    const stringToSign = [
      "AWS4-HMAC-SHA256",
      amzDate,
      credentialScope,
      sha256Hex(canonicalRequest),
    ].join("\n");

    const signingKey = getSignatureKey(this.secretAccessKey, dateStamp, this.region, "s3");
    const signature = crypto.createHmac("sha256", signingKey).update(stringToSign, "utf8").digest("hex");

    const authHeader = `AWS4-HMAC-SHA256 Credential=${this.accessKeyId}/${credentialScope}, SignedHeaders=${signedHeaders}, Signature=${signature}`;

    return {
      url,
      headers: {
        host,
        "x-amz-date": amzDate,
        "x-amz-content-sha256": payloadHash,
        Authorization: authHeader,
      },
    };
  }

  public async saveFile(
    fileBuffer: Buffer | Uint8Array,
    extension: string
  ): Promise<StorageSaveResult> {
    try {
      const { storageKey, storedFileName } = this.generateStorageKey(extension);
      const canonicalUri = `/${storageKey}`;
      const buffer = Buffer.isBuffer(fileBuffer) ? fileBuffer : Buffer.from(fileBuffer);
      const payloadHash = sha256Hex(buffer);

      const now = new Date();
      const { url, headers } = this.signRequest("PUT", canonicalUri, payloadHash, now);

      const mimeType = extension.toLowerCase() === ".pdf" ? "application/pdf" : "image/jpeg";
      headers["Content-Type"] = mimeType;
      // Private ACL đảm bảo đơn thuốc không bị xem tự do
      headers["x-amz-acl"] = "private";

      const res = await fetch(url, {
        method: "PUT",
        headers,
        body: new Uint8Array(buffer),
      });

      if (!res.ok) {
        const errText = await res.text().catch(() => "");
        throw new Error(`S3 PUT failed with status ${res.status}: ${errText}`);
      }

      return {
        storageKey,
        storedFileName,
        filePath: `${this.endpoint}/${this.bucket}/${storageKey}`,
      };
    } catch (err) {
      console.error("[S3Storage Error] Không thể lưu file lên S3/R2:", err);
      throw new StorageError("Không thể tải tệp đơn thuốc lên hệ thống lưu trữ đám mây.");
    }
  }

  public async getFile(storageKey: string): Promise<Buffer | null> {
    try {
      const canonicalUri = `/${storageKey}`;
      const payloadHash = sha256Hex("");
      const now = new Date();
      const { url, headers } = this.signRequest("GET", canonicalUri, payloadHash, now);

      const res = await fetch(url, { method: "GET", headers });
      if (!res.ok) return null;

      const arrayBuf = await res.arrayBuffer();
      return Buffer.from(arrayBuf);
    } catch {
      return null;
    }
  }

  public async deleteFile(storageKey: string): Promise<boolean> {
    try {
      const canonicalUri = `/${storageKey}`;
      const payloadHash = sha256Hex("");
      const now = new Date();
      const { url, headers } = this.signRequest("DELETE", canonicalUri, payloadHash, now);

      const res = await fetch(url, { method: "DELETE", headers });
      return res.ok;
    } catch (err) {
      console.error(`[S3Storage Error] Không thể xóa file ${storageKey}:`, err);
      return false;
    }
  }
}

/**
 * Factory tạo adapter lưu trữ phù hợp dựa trên cấu hình môi trường
 */
export function createPrescriptionStorage(): PrescriptionStorageService {
  const hasS3Config = Boolean(
    (process.env.S3_BUCKET || process.env.R2_BUCKET) &&
    process.env.S3_ACCESS_KEY_ID &&
    process.env.S3_SECRET_ACCESS_KEY
  );

  if (hasS3Config) {
    try {
      return new S3CompatiblePrescriptionStorage();
    } catch (err) {
      console.warn("[Storage Factory] Lỗi khởi tạo S3Storage, chuyển về LocalStorage fallback:", err);
    }
  }

  return new LocalPrescriptionStorage();
}

// Singleton storage service instance
export const prescriptionStorage = createPrescriptionStorage();
