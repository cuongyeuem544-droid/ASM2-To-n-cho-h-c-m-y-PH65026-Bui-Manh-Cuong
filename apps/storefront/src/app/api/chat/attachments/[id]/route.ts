import { NextRequest, NextResponse } from "next/server";
import fs from "fs/promises";
import path from "path";

export const dynamic = "force-dynamic";

function resolveMimeType(ext: string): string {
  switch (ext) {
    case ".png":
      return "image/png";
    case ".webp":
      return "image/webp";
    case ".jpg":
    case ".jpeg":
      return "image/jpeg";
    case ".pdf":
      return "application/pdf";
    case ".doc":
      return "application/msword";
    case ".docx":
      return "application/vnd.openxmlformats-officedocument.wordprocessingml.document";
    case ".txt":
      return "text/plain; charset=utf-8";
    default:
      return "application/octet-stream";
  }
}

/**
 * Trả về tệp đính kèm an toàn với xác thực và security headers
 */
export async function GET(
  req: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const attachmentId = params.id;
    if (!attachmentId || !attachmentId.startsWith("att-")) {
      return NextResponse.json({ error: "Mã tệp không hợp lệ" }, { status: 400 });
    }

    // 1. Kiểm tra xác thực Bearer token hoặc query token
    const authHeader = req.headers.get("authorization");
    let token = "";
    if (authHeader && authHeader.toLowerCase().startsWith("bearer ")) {
      token = authHeader.slice(7).trim();
    }
    if (!token) {
      token = req.nextUrl.searchParams.get("token") || "";
    }

    if (!token) {
      return NextResponse.json(
        { error: "Vui lòng đăng nhập để xem tệp đính kèm." },
        { status: 401 }
      );
    }

    // Xác thực token với FastAPI Backend
    const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    let verifiedUser: { id: string | number; role?: string } | null = null;
    try {
      const authRes = await fetch(`${apiBase}/api/v1/auth/me`, {
        method: "GET",
        headers: { Authorization: `Bearer ${token}` },
        cache: "no-store",
      });
      if (!authRes.ok) {
        return NextResponse.json(
          { error: "Phiên đăng nhập không hợp lệ hoặc đã hết hạn." },
          { status: 401 }
        );
      }
      const userJson = await authRes.json();
      verifiedUser = { id: userJson.id, role: userJson.role };
    } catch {
      return NextResponse.json(
        { error: "Không thể xác thực danh tính người dùng." },
        { status: 503 }
      );
    }

    const filePrefix = attachmentId.replace("att-", "");
    const baseDir = path.join(process.cwd(), "storage", "chat-attachments");

    // Tìm file trong storage/chat-attachments
    const findFile = async (dir: string): Promise<{ path: string; ext: string } | null> => {
      try {
        const entries = await fs.readdir(dir, { withFileTypes: true });
        for (const entry of entries) {
          const full = path.join(dir, entry.name);
          if (entry.isDirectory()) {
            const nested = await findFile(full);
            if (nested) return nested;
          } else if (entry.isFile() && entry.name.startsWith(filePrefix) && !entry.name.endsWith(".meta.json")) {
            return { path: full, ext: path.extname(entry.name).toLowerCase() };
          }
        }
      } catch {}
      return null;
    };

    const found = await findFile(baseDir);
    if (!found) {
      return NextResponse.json({ error: "Không tìm thấy tệp đính kèm" }, { status: 404 });
    }

    const { path: foundPath, ext: foundExt } = found;
    // Kiểm tra quyền sở hữu nếu có file metadata
    const metaPath = foundPath.replace(path.extname(foundPath), ".meta.json");
    try {
      const metaContent = await fs.readFile(metaPath, "utf-8");
      const meta = JSON.parse(metaContent);
      if (
        meta &&
        meta.userId &&
        verifiedUser &&
        verifiedUser.id !== meta.userId &&
        verifiedUser.role !== "ADMIN"
      ) {
        return NextResponse.json(
          { error: "Bạn không có quyền truy cập vào tệp đính kèm này." },
          { status: 403 }
        );
      }
    } catch {}

    const fileBuffer = await fs.readFile(foundPath);
    const mimeType = resolveMimeType(foundExt);

    return new NextResponse(fileBuffer, {
      status: 200,
      headers: {
        "Content-Type": mimeType,
        "X-Content-Type-Options": "nosniff",
        "Content-Security-Policy": "default-src 'none'",
        "Cache-Control": "private, max-age=86400",
      },
    });
  } catch (err) {
    return NextResponse.json({ error: "Lỗi máy chủ khi đọc tệp" }, { status: 500 });
  }
}
