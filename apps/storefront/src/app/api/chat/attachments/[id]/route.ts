import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";

/**
 * Proxy tải tệp đính kèm Live Chat an toàn:
 * - Dùng FastAPI làm nguồn dữ liệu và quyền duy nhất.
 * - Tuyệt đối không đọc file trên đĩa cục bộ hay tìm theo tiền tố.
 * - Chuyển tiếp Authorization và X-Chat-Guest-Token.
 * - Giữ nguyên security headers và mã lỗi 401, 403, 404, 503 (fail-closed).
 */
export async function GET(
  req: NextRequest,
  { params }: { params: { id: string } }
) {
  const attachmentId = params.id;
  // 1. Mã attachment phải khớp chính xác định dạng att-...
  if (!attachmentId || !/^att-[a-zA-Z0-9_-]+$/.test(attachmentId)) {
    return NextResponse.json({ error: "Mã tệp không hợp lệ" }, { status: 400 });
  }

  // 2. Thu thập thông tin xác thực (Bearer header hoặc X-Chat-Guest-Token header)
  const authHeader = req.headers.get("authorization");
  const guestHeader = req.headers.get("x-chat-guest-token");

  if (!authHeader && !guestHeader) {
    return NextResponse.json(
      { error: "Vui lòng cung cấp thông tin xác thực để xem tệp đính kèm." },
      { status: 401 }
    );
  }

  // 3. Forward tới FastAPI backend - nguồn thẩm quyền duy nhất
  const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  const backendUrl = `${apiBase}/api/v1/live-chat/attachments/${encodeURIComponent(attachmentId)}`;

  const forwardHeaders: Record<string, string> = {};
  if (authHeader) {
    forwardHeaders["Authorization"] = authHeader;
  }
  if (guestHeader) {
    forwardHeaders["X-Chat-Guest-Token"] = guestHeader;
  }

  let backendRes: Response;
  try {
    backendRes = await fetch(backendUrl, {
      method: "GET",
      headers: forwardHeaders,
      cache: "no-store",
    });
  } catch {
    // 4. Nếu backend không phản hồi, trả 503; tuyệt đối không đọc file cục bộ để dự phòng
    return NextResponse.json(
      { error: "Không thể kết nối đến máy chủ xác thực và lưu trữ tệp đính kèm." },
      { status: 503 }
    );
  }

  // 5. Nếu backend trả 401, 403 hoặc 404, giữ đúng trạng thái tương ứng (fail-closed)
  if (!backendRes.ok) {
    let errorDetail = "Không thể tải tệp đính kèm";
    try {
      const errJson = await backendRes.json();
      if (errJson && errJson.detail) {
        errorDetail = errJson.detail;
      }
    } catch {
      // Giữ errorDetail mặc định
    }

    return NextResponse.json(
      { error: errorDetail },
      { status: backendRes.status }
    );
  }

  const contentType = backendRes.headers.get("content-type") || "application/octet-stream";
  const fileBuffer = await backendRes.arrayBuffer();

  return new NextResponse(Buffer.from(fileBuffer), {
    status: 200,
    headers: {
      "Content-Type": contentType,
      "X-Content-Type-Options": "nosniff",
      "Content-Security-Policy": "default-src 'none'",
      "Cache-Control": "private, max-age=86400",
    },
  });
}
