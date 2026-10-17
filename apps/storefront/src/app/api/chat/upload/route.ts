import { NextRequest, NextResponse } from "next/server";
import fs from "fs/promises";
import path from "path";
import crypto from "crypto";

export const dynamic = "force-dynamic";

const MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024; // 10 MB
const ALLOWED_EXTENSIONS = [".jpg", ".jpeg", ".png", ".webp"];

function sanitizeFileName(fileName: string): string {
  if (!fileName) return "image.jpg";
  const baseName = fileName.replace(/[\x00-\x1f\x80-\x9f]/g, "").trim();
  const cleanName = baseName.split(/[/\\]/).pop() || "image.jpg";
  return cleanName;
}

function verifyImageSignature(buffer: Buffer, ext: string): boolean {
  if (buffer.length < 12) return false;
  if (ext === ".jpg" || ext === ".jpeg") {
    return buffer[0] === 0xff && buffer[1] === 0xd8 && buffer[2] === 0xff;
  }
  if (ext === ".png") {
    return (
      buffer[0] === 0x89 &&
      buffer[1] === 0x50 &&
      buffer[2] === 0x4e &&
      buffer[3] === 0x47 &&
      buffer[4] === 0x0d &&
      buffer[5] === 0x0a &&
      buffer[6] === 0x1a &&
      buffer[7] === 0x0a
    );
  }
  if (ext === ".webp") {
    const isRiff = buffer.toString("ascii", 0, 4) === "RIFF";
    const isWebp = buffer.toString("ascii", 8, 12) === "WEBP";
    return isRiff && isWebp;
  }
  return false;
}

export async function POST(req: NextRequest) {
  try {
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
        { error: "Vui lòng chọn một tệp hình ảnh để tải lên." },
        { status: 400 }
      );
    }

    const cleanName = sanitizeFileName(file.name);
    const ext = cleanName.slice(cleanName.lastIndexOf(".")).toLowerCase();

    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      return NextResponse.json(
        { error: `Định dạng tệp '${ext}' không được hỗ trợ. Chỉ chấp nhận JPG, JPEG, PNG, WEBP.` },
        { status: 400 }
      );
    }

    if (file.size === 0) {
      return NextResponse.json(
        { error: "Tệp ảnh tải lên có dung lượng rỗng (0 bytes). Vui lòng thử lại." },
        { status: 400 }
      );
    }

    if (file.size > MAX_FILE_SIZE_BYTES) {
      return NextResponse.json(
        { error: `Dung lượng tệp vượt quá giới hạn 10 MB (tệp hiện tại: ${(file.size / (1024 * 1024)).toFixed(2)} MB).` },
        { status: 413 }
      );
    }

    const arrayBuffer = await file.arrayBuffer();
    const buffer = Buffer.from(arrayBuffer);

    if (!verifyImageSignature(buffer, ext)) {
      return NextResponse.json(
        { error: "Chữ ký nhị phân của tệp không khớp với định dạng hình ảnh hợp lệ hoặc tệp đã bị sửa đổi." },
        { status: 422 }
      );
    }

    // Lưu vào Private Storage (ngoài /public)
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
    const mimeType = ext === ".jpg" || ext === ".jpeg" ? "image/jpeg" : `image/${ext.replace(".", "")}`;
    const base64Data = buffer.toString("base64");

    return NextResponse.json({
      success: true,
      attachment: {
        id: attachmentId,
        fileName: cleanName,
        storedFileName,
        fileSize: file.size,
        mimeType,
        url: `/api/chat/attachments/${attachmentId}`,
        base64Data,
        uploadedAt: now.toISOString(),
      },
    });
  } catch (err: any) {
    console.error("[Upload Error]:", err);
    return NextResponse.json(
      { error: "Đã xảy ra lỗi khi lưu tệp ảnh lên máy chủ. Vui lòng thử lại." },
      { status: 500 }
    );
  }
}
