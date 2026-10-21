import { NextRequest, NextResponse } from "next/server";
import fs from "fs/promises";
import path from "path";
import crypto from "crypto";

export const dynamic = "force-dynamic";

const MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024; // 10 MB
const ALLOWED_EXTENSIONS = [".jpg", ".jpeg", ".png", ".webp", ".pdf", ".doc", ".docx", ".txt"];

function sanitizeFileName(fileName: string): string {
  if (!fileName) return "file.bin";
  const baseName = fileName.replace(/[\x00-\x1f\x80-\x9f]/g, "").trim();
  const cleanName = baseName.split(/[/\\]/).pop() || "file.bin";
  return cleanName;
}

function verifyBinarySignature(buffer: Buffer, ext: string): boolean {
  if (buffer.length < 4) return false;

  // Ảnh JPG/JPEG
  if (ext === ".jpg" || ext === ".jpeg") {
    return buffer[0] === 0xff && buffer[1] === 0xd8 && buffer[2] === 0xff;
  }
  // Ảnh PNG
  if (ext === ".png") {
    return (
      buffer[0] === 0x89 &&
      buffer[1] === 0x50 &&
      buffer[2] === 0x4e &&
      buffer[3] === 0x47
    );
  }
  // Ảnh WEBP
  if (ext === ".webp") {
    if (buffer.length < 12) return false;
    const isRiff = buffer.toString("ascii", 0, 4) === "RIFF";
    const isWebp = buffer.toString("ascii", 8, 12) === "WEBP";
    return isRiff && isWebp;
  }
  // Tài liệu PDF (%PDF-)
  if (ext === ".pdf") {
    return buffer.toString("ascii", 0, 4) === "%PDF";
  }
  // Microsoft Word DOCX (ZIP archive: PK\x03\x04)
  if (ext === ".docx") {
    return buffer[0] === 0x50 && buffer[1] === 0x4b && buffer[2] === 0x03 && buffer[3] === 0x04;
  }
  // Microsoft Word DOC (OLE Compound File: D0 CF 11 E0)
  if (ext === ".doc") {
    return buffer[0] === 0xd0 && buffer[1] === 0xcf && buffer[2] === 0x11 && buffer[3] === 0xe0;
  }
  // File văn bản thuần TXT: không chứa byte null nhị phân trong 100 byte đầu
  if (ext === ".txt") {
    const sample = buffer.slice(0, Math.min(buffer.length, 512));
    for (let i = 0; i < sample.length; i++) {
      if (sample[i] === 0x00) return false;
    }
    return true;
  }

  return false;
}

function resolveMimeType(ext: string): string {
  switch (ext) {
    case ".jpg":
    case ".jpeg":
      return "image/jpeg";
    case ".png":
      return "image/png";
    case ".webp":
      return "image/webp";
    case ".pdf":
      return "application/pdf";
    case ".docx":
      return "application/vnd.openxmlformats-officedocument.wordprocessingml.document";
    case ".doc":
      return "application/msword";
    case ".txt":
      return "text/plain; charset=utf-8";
    default:
      return "application/octet-stream";
  }
}

export async function POST(req: NextRequest) {
  try {
    // 1. Kiểm tra và xác thực Token Bearer với Backend API
    const authHeader = req.headers.get("authorization");
    if (!authHeader || !authHeader.toLowerCase().startsWith("bearer ")) {
      return NextResponse.json(
        { error: "Vui lòng đăng nhập để tải lên tệp đính kèm." },
        { status: 401 }
      );
    }

    const token = authHeader.slice(7).trim();
    if (!token) {
      return NextResponse.json(
        { error: "Vui lòng đăng nhập để tải lên tệp đính kèm." },
        { status: 401 }
      );
    }

    // Xác thực token qua FastAPI backend
    const apiBase = (process.env.INTERNAL_API_URL || process.env.NEXT_PUBLIC_API_URL || "https://h4care-api-staging.onrender.com").replace(/\/+$/, "");
    let verifiedUser: { id: string | number; role?: string } | null = null;

    try {
      const authRes = await fetch(`${apiBase}/api/v1/auth/me`, {
        method: "GET",
        headers: {
          Authorization: `Bearer ${token}`,
        },
        cache: "no-store",
      });

      if (authRes.status === 401 || authRes.status === 403) {
        return NextResponse.json(
          { error: "Phiên đăng nhập đã hết hạn hoặc không hợp lệ. Vui lòng đăng nhập lại." },
          { status: 401 }
        );
      }

      if (!authRes.ok) {
        return NextResponse.json(
          { error: "Không thể xác thực danh tính người dùng. Vui lòng thử lại sau." },
          { status: authRes.status }
        );
      }

      const userJson = await authRes.json();
      verifiedUser = {
        id: userJson.id,
        role: userJson.role,
      };
    } catch (authErr) {
      console.warn("[Upload Auth Error]: Lỗi kết nối FastAPI backend:", authErr);
      return NextResponse.json(
        { error: "Máy chủ xác thực không phản hồi. Vui lòng thử lại sau." },
        { status: 503 }
      );
    }

    // 2. Parse Multipart form data
    let formData: FormData;
    try {
      formData = await req.formData();
    } catch {
      return NextResponse.json(
        { error: "Dữ liệu yêu cầu không hợp lệ (cần multipart/form-data)." },
        { status: 400 }
      );
    }

    const file = formData.get("file");
    if (!file || !(file instanceof File)) {
      return NextResponse.json(
        { error: "Vui lòng chọn một tệp hình ảnh hoặc tài liệu để tải lên." },
        { status: 400 }
      );
    }

    const cleanName = sanitizeFileName(file.name);
    const ext = cleanName.slice(cleanName.lastIndexOf(".")).toLowerCase();

    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      return NextResponse.json(
        {
          error: `Định dạng tệp '${ext}' không được hỗ trợ. Chấp nhận JPG, JPEG, PNG, WEBP, PDF, DOC, DOCX, TXT.`,
        },
        { status: 400 }
      );
    }

    if (file.size === 0) {
      return NextResponse.json(
        { error: "Tệp tải lên có dung lượng rỗng (0 bytes). Vui lòng thử lại." },
        { status: 400 }
      );
    }

    if (file.size > MAX_FILE_SIZE_BYTES) {
      return NextResponse.json(
        {
          error: `Dung lượng tệp vượt quá giới hạn 10 MB (tệp hiện tại: ${(file.size / (1024 * 1024)).toFixed(2)} MB).`,
        },
        { status: 413 }
      );
    }

    const arrayBuffer = await file.arrayBuffer();
    const buffer = Buffer.from(arrayBuffer);

    if (!verifyBinarySignature(buffer, ext)) {
      return NextResponse.json(
        {
          error: "Chữ ký nhị phân của tệp không khớp với định dạng tệp hợp lệ hoặc tệp đã bị sửa đổi.",
        },
        { status: 422 }
      );
    }

    // Lưu vào Private Storage (ngoài thư mục /public)
    const now = new Date();
    const year = now.getFullYear().toString();
    const month = (now.getMonth() + 1).toString().padStart(2, "0");
    const subDir = path.join(year, month);

    const baseStorageDir = path.join(process.cwd(), "storage", "chat-attachments", subDir);
    await fs.mkdir(baseStorageDir, { recursive: true });

    const fileId = crypto.randomUUID();
    const storedFileName = `${fileId}${ext}`;
    const targetPath = path.join(baseStorageDir, storedFileName);

    await fs.writeFile(targetPath, buffer);

    const attachmentId = `att-${fileId.substring(0, 12)}`;
    const metaPath = path.join(baseStorageDir, `${fileId}.meta.json`);
    try {
      await fs.writeFile(
        metaPath,
        JSON.stringify({
          userId: verifiedUser?.id,
          attachmentId,
          fileName: cleanName,
          fileSize: file.size,
          uploadedAt: now.toISOString(),
        })
      );
    } catch {}
    const mimeType = resolveMimeType(ext);
    const isImage = [".jpg", ".jpeg", ".png", ".webp"].includes(ext);
    const base64Data = isImage ? buffer.toString("base64") : undefined;

    return NextResponse.json({
      success: true,
      attachment: {
        id: attachmentId,
        fileName: cleanName,
        storedFileName,
        fileSize: file.size,
        mimeType,
        type: isImage ? "image" : "document",
        url: `/api/chat/attachments/${attachmentId}`,
        base64Data,
        uploadedAt: now.toISOString(),
      },
    });
  } catch (err: any) {
    console.error("[Upload Error]:", err);
    return NextResponse.json(
      { error: "Đã xảy ra lỗi khi lưu tệp lên máy chủ. Vui lòng thử lại." },
      { status: 500 }
    );
  }
}
