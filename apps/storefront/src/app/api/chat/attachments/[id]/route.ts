import { NextRequest, NextResponse } from "next/server";
import fs from "fs/promises";
import path from "path";

export const dynamic = "force-dynamic";

/**
 * Trả về tệp ảnh an toàn với security headers
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

    const filePrefix = attachmentId.replace("att-", "");
    const baseDir = path.join(process.cwd(), "storage", "chat-attachments");

    // Tìm file trong storage/chat-attachments
    let foundPath: string | null = null;
    let foundExt = ".jpg";

    const searchDir = async (dir: string): Promise<void> => {
      try {
        const entries = await fs.readdir(dir, { withFileTypes: true });
        for (const entry of entries) {
          const full = path.join(dir, entry.name);
          if (entry.isDirectory()) {
            await searchDir(full);
            if (foundPath) return;
          } else if (entry.isFile() && entry.name.startsWith(filePrefix)) {
            foundPath = full;
            foundExt = path.extname(entry.name).toLowerCase();
            return;
          }
        }
      } catch {}
    };

    await searchDir(baseDir);

    if (!foundPath) {
      return NextResponse.json({ error: "Không tìm thấy tệp đính kèm" }, { status: 404 });
    }

    const fileBuffer = await fs.readFile(foundPath);
    const mimeType =
      foundExt === ".png"
        ? "image/png"
        : foundExt === ".webp"
        ? "image/webp"
        : "image/jpeg";

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
