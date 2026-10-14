import { NextRequest, NextResponse } from "next/server";
import { getAiChatResponse } from "@/lib/chatbot/ai-service";
import { ChatRequest, ChatResponse } from "@/lib/chatbot/types";

// Bộ nhớ đệm rate limiting đơn giản theo IP (in-memory sliding window)
const rateLimitMap = new Map<string, { count: number; resetAt: number }>();
const MAX_REQUESTS_PER_WINDOW = 30; // 30 requests
const WINDOW_DURATION_MS = 60 * 1000; // 1 phút

function checkRateLimit(ip: string): boolean {
  const now = Date.now();
  const entry = rateLimitMap.get(ip);

  if (!entry || now > entry.resetAt) {
    rateLimitMap.set(ip, { count: 1, resetAt: now + WINDOW_DURATION_MS });
    return true;
  }

  if (entry.count >= MAX_REQUESTS_PER_WINDOW) {
    return false;
  }

  entry.count += 1;
  return true;
}

// Dọn dẹp rate limit map định kỳ
setInterval(() => {
  const now = Date.now();
  rateLimitMap.forEach((value, key) => {
    if (now > value.resetAt) {
      rateLimitMap.delete(key);
    }
  });
}, 5 * 60 * 1000);

export async function POST(req: NextRequest) {
  try {
    // 1. Kiểm tra Rate Limiting theo IP
    const clientIp =
      req.headers.get("x-forwarded-for")?.split(",")[0]?.trim() ||
      req.headers.get("x-real-ip") ||
      "127.0.0.1";

    if (!checkRateLimit(clientIp)) {
      return NextResponse.json(
        {
          error: "Bạn đã gửi quá nhiều yêu cầu trong thời gian ngắn. Vui lòng đợi 1 phút trước khi tiếp tục.",
        },
        { status: 429 }
      );
    }

    // 2. Parse & Validate body
    let body: ChatRequest;
    try {
      body = await req.json();
    } catch {
      return NextResponse.json(
        { error: "Dữ liệu yêu cầu không hợp lệ (JSON không đúng định dạng)." },
        { status: 400 }
      );
    }

    const { message, conversationHistory = [] } = body;

    if (!message || typeof message !== "string" || message.trim().length === 0) {
      return NextResponse.json(
        { error: "Vui lòng nhập nội dung câu hỏi." },
        { status: 400 }
      );
    }

    if (message.length > 2000) {
      return NextResponse.json(
        { error: "Nội dung câu hỏi quá dài (tối đa 2.000 ký tự)." },
        { status: 400 }
      );
    }

    // 3. Chuẩn hóa lịch sử hội thoại an toàn
    const cleanHistory = Array.isArray(conversationHistory)
      ? conversationHistory
          .filter(
            (item) =>
              item &&
              (item.role === "user" || item.role === "assistant") &&
              typeof item.content === "string"
          )
          .slice(-10)
      : [];

    // 4. Gọi bộ máy AI điều phối
    const response: ChatResponse = await getAiChatResponse(
      message.trim(),
      cleanHistory
    );

    return NextResponse.json(response, { status: 200 });
  } catch (err: any) {
    console.error("[API /api/chat Error]:", err);
    return NextResponse.json(
      {
        error: "Đã xảy ra lỗi trong quá trình xử lý câu trả lời. Quý khách vui lòng thử lại sau.",
        detail: process.env.NODE_ENV === "development" ? err.message : undefined,
      },
      { status: 500 }
    );
  }
}

export async function GET() {
  const provider = process.env.AI_PROVIDER || (process.env.GEMINI_API_KEY ? "gemini" : "fallback");
  const model = process.env.AI_MODEL || (provider === "gemini" ? "gemini-1.5-flash" : "gpp-medical-v1");

  return NextResponse.json({
    status: "online",
    service: "H4CARE AI Pharmacist Chatbot",
    activeProvider: provider,
    model,
    catalog: "H4CARE Certified GPP Medicines",
    timestamp: new Date().toISOString(),
  });
}
