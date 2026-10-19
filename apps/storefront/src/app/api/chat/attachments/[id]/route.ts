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

    interface FileCandidate {
      metaPath?: string;
      dataPath?: string;
      ext?: string;
    }

    const candidates: FileCandidate[] = [];

    const scanDir = async (dir: string) => {
      try {
        const entries = await fs.readdir(dir, { withFileTypes: true });
        for (const entry of entries) {
          const fullPath = path.join(dir, entry.name);
          if (entry.isDirectory()) {
            await scanDir(fullPath);
          } else if (entry.isFile() && entry.name.startsWith(filePrefix)) {
            if (entry.name.endsWith(".meta.json")) {
              const stem = entry.name.slice(0, -10);
              let cand = candidates.find(
                (c) =>
                  c.metaPath === fullPath ||
                  (c.dataPath && path.basename(c.dataPath, c.ext || path.extname(c.dataPath)) === stem)
              );
              if (!cand) {
                cand = {};
                candidates.push(cand);
              }
              cand.metaPath = fullPath;
            } else {
              const ext = path.extname(entry.name).toLowerCase();
              const stem = path.basename(entry.name, ext);
              let cand = candidates.find(
                (c) =>
                  c.dataPath === fullPath ||
                  (c.metaPath && path.basename(c.metaPath, ".meta.json") === stem)
              );
              if (!cand) {
                cand = {};
                candidates.push(cand);
              }
              cand.dataPath = fullPath;
              cand.ext = ext;
            }
          }
        }
      } catch {
        // Base dir or sub dir might not exist yet
      }
    };

    await scanDir(baseDir);

    if (candidates.length === 0) {
      return NextResponse.json({ error: "Không tìm thấy tệp đính kèm" }, { status: 404 });
    }

    // Kiểm tra từng candidate tìm attachment khớp chính xác attachmentId
    let matchingCandidate: FileCandidate | null = null;
    let hasCorruptedMeta = false;
    let hasMismatchedId = false;
    let hasMissingUser = false;
    let hasMissingMeta = false;

    for (const cand of candidates) {
      if (!cand.metaPath) {
        hasMissingMeta = true;
        continue;
      }

      let metaContent = "";
      try {
        metaContent = await fs.readFile(cand.metaPath, "utf-8");
      } catch {
        hasCorruptedMeta = true;
        continue;
      }

      let meta: any = null;
      try {
        meta = JSON.parse(metaContent);
      } catch {
        hasCorruptedMeta = true;
        continue;
      }

      if (!meta || typeof meta !== "object") {
        hasCorruptedMeta = true;
        continue;
      }

      if (meta.attachmentId !== attachmentId) {
        hasMismatchedId = true;
        continue;
      }

      if (meta.userId === undefined || meta.userId === null || String(meta.userId).trim() === "") {
        hasMissingUser = true;
        continue;
      }

      // Khớp chính xác attachmentId và metadata hợp lệ
      matchingCandidate = cand;
      (matchingCandidate as any)._meta = meta;
      break;
    }

    if (!matchingCandidate) {
      if (hasCorruptedMeta) {
        return NextResponse.json(
          { error: "Metadata của tệp đính kèm bị hỏng hoặc không đúng định dạng." },
          { status: 403 }
        );
      }
      if (hasMissingUser) {
        return NextResponse.json(
          { error: "Metadata của tệp đính kèm thiếu thông tin người sở hữu." },
          { status: 403 }
        );
      }
      if (hasMismatchedId) {
        return NextResponse.json(
          { error: "Mã định danh trong metadata không khớp với tệp yêu cầu." },
          { status: 403 }
        );
      }
      if (hasMissingMeta) {
        return NextResponse.json(
          { error: "Tệp đính kèm thiếu tệp metadata chứng thực quyền sở hữu." },
          { status: 403 }
        );
      }
      return NextResponse.json({ error: "Không tìm thấy tệp đính kèm hợp lệ" }, { status: 404 });
    }

    const validMeta = (matchingCandidate as any)._meta;

    // Xác thực quyền sở hữu: người dùng phải là người upload hoặc có vai trò ADMIN
    const isOwner = String(verifiedUser.id) === String(validMeta.userId);
    const userRole = (verifiedUser.role || "").toUpperCase();
    const isAdmin = userRole === "ADMIN";

    if (!isOwner && !isAdmin) {
      return NextResponse.json(
        { error: "Bạn không có quyền truy cập vào tệp đính kèm này." },
        { status: 403 }
      );
    }

    if (!matchingCandidate.dataPath) {
      return NextResponse.json(
        { error: "Không tìm thấy nội dung tệp đính kèm trên máy chủ." },
        { status: 404 }
      );
    }

    const fileBuffer = await fs.readFile(matchingCandidate.dataPath);
    const mimeType = resolveMimeType(matchingCandidate.ext || path.extname(matchingCandidate.dataPath).toLowerCase());

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
