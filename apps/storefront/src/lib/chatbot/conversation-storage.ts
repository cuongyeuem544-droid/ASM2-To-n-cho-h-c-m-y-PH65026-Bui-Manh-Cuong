import { ChatAttachment, ChatConversation, ChatMessage, ExtractedMemory } from "./types";

const CONVERSATIONS_STORAGE_KEY = "h4care_conversations_v3";
const ACTIVE_CONVERSATION_KEY = "h4care_active_conv_id_v3";
const MAX_LOCAL_CONVERSATIONS = 30;

export const INITIAL_WELCOME_CONTENT = `Dạ xin chào quý khách! Em là **Trợ lý AI H4CARE** 🩺\n\nEm là hệ thống tự động, có thể hỗ trợ quý khách:\n- 🔍 **Tra cứu thuốc chính hãng:** Công dụng, hoạt chất, cách dùng và giá niêm yết chuẩn GPP.\n- 📋 **Tư vấn hướng dẫn:** Phân biệt thuốc kê đơn (Rx) / OTC, quy trình thẩm định đơn thuốc.\n- 📷 **Nhận diện ảnh thuốc / đơn thuốc:** Hỗ trợ tải ảnh để xem thành phần và nhãn thuốc.\n- 📦 **Chính sách & Vận chuyển:** Đổi trả trong 7 ngày, giải thích trạng thái đơn hàng.\n\n*⚠️ Lưu ý: Em là Trợ lý AI tự động. Thông tin mang tính tham khảo y khoa. Quý khách có thể chuyển sang tab **"Tư vấn trực tiếp"** để gặp nhân viên thật bất kỳ lúc nào!*`;

export function getFormattedTime(): string {
  const now = new Date();
  return now.toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" });
}

export function createInitialWelcomeMessage(): ChatMessage {
  return {
    id: `welcome-${Date.now()}`,
    role: "assistant",
    content: INITIAL_WELCOME_CONTENT,
    timestamp: "Vừa xong",
    quickReplies: [
      "🔍 Tra cứu Panadol Extra",
      "🤒 Tôi bị sốt và đau đầu",
      "📦 Chính sách đổi trả thuốc thế nào?",
      "🎧 Tôi muốn gặp nhân viên tư vấn",
    ],
  };
}

/**
 * Tự động trích xuất tiêu đề ngắn gọn súc tích từ tin nhắn đầu tiên của người dùng
 */
export function generateTitleFromMessage(message: string): string {
  if (!message || typeof message !== "string") return "Cuộc trò chuyện mới";
  const clean = message.replace(/[\r\n\t]+/g, " ").trim();
  if (!clean) return "Cuộc trò chuyện mới";

  // Cắt bỏ các từ chào hỏi dư thừa ở đầu
  const stripped = clean
    .replace(/^(?:xin chào|chào bot|chào bạn|alo|hi|hello|cho mình hỏi|cho tôi hỏi|tôi muốn hỏi|bạn ơi)\s*[,.:;!-]?\s*/i, "")
    .trim();

  const titleCandidate = stripped || clean;
  if (titleCandidate.length <= 40) {
    return titleCandidate;
  }
  return titleCandidate.slice(0, 38).trim() + "...";
}

/**
 * Đọc toàn bộ danh sách cuộc trò chuyện từ LocalStorage (SSR Safe)
 */
export function loadLocalConversations(): ChatConversation[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(CONVERSATIONS_STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed)) {
      return parsed.sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime());
    }
    return [];
  } catch (err) {
    console.warn("[ConversationStorage] Lỗi đọc conversations từ localStorage:", err);
    return [];
  }
}

/**
 * Lưu danh sách cuộc trò chuyện vào LocalStorage (giới hạn tối đa MAX_LOCAL_CONVERSATIONS)
 */
export function persistLocalConversations(convs: ChatConversation[]): void {
  if (typeof window === "undefined") return;
  try {
    const trimmed = convs.slice(0, MAX_LOCAL_CONVERSATIONS);
    localStorage.setItem(CONVERSATIONS_STORAGE_KEY, JSON.stringify(trimmed));
  } catch (err) {
    console.warn("[ConversationStorage] Lỗi lưu conversations vào localStorage:", err);
  }
}

/**
 * Lấy ID cuộc trò chuyện đang được kích hoạt
 */
export function getActiveConversationId(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return localStorage.getItem(ACTIVE_CONVERSATION_KEY);
  } catch {
    return null;
  }
}

/**
 * Ghi nhận ID cuộc trò chuyện đang được kích hoạt
 */
export function setActiveConversationId(id: string): void {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(ACTIVE_CONVERSATION_KEY, id);
  } catch {}
}

/**
 * Tạo một cuộc trò chuyện mới tinh hoàn toàn (Memory mới, Session mới)
 */
export function createNewConversation(
  initialUserMessage?: string,
  userId?: string | number | null
): ChatConversation {
  const nowIso = new Date().toISOString();
  const convId = `conv-${Date.now()}-${Math.random().toString(36).substring(2, 7)}`;
  const sessionId = `sess-${Date.now()}-${Math.random().toString(36).substring(2, 7)}`;

  const title = initialUserMessage ? generateTitleFromMessage(initialUserMessage) : "Cuộc trò chuyện mới";

  const newConv: ChatConversation = {
    id: convId,
    title,
    createdAt: nowIso,
    updatedAt: nowIso,
    messages: [createInitialWelcomeMessage()],
    extractedMemory: {},
    userId: userId || null,
    sessionId,
    isPinned: false,
  };

  const existing = loadLocalConversations();
  const updated = [newConv, ...existing];
  persistLocalConversations(updated);
  setActiveConversationId(convId);

  return newConv;
}

/**
 * Cập nhật hoặc lưu một cuộc trò chuyện
 */
export function saveConversation(conv: ChatConversation): void {
  const existing = loadLocalConversations();
  const idx = existing.findIndex((c) => c.id === conv.id);

  conv.updatedAt = new Date().toISOString();

  let updated: ChatConversation[];
  if (idx >= 0) {
    updated = [...existing];
    updated[idx] = conv;
  } else {
    updated = [conv, ...existing];
  }

  persistLocalConversations(updated);
}

/**
 * Đổi tên một cuộc trò chuyện
 */
export function renameConversation(id: string, newTitle: string): void {
  const clean = newTitle.trim();
  if (!clean) return;
  const existing = loadLocalConversations();
  const target = existing.find((c) => c.id === id);
  if (target) {
    target.title = clean;
    target.updatedAt = new Date().toISOString();
    persistLocalConversations(existing);
  }
}

/**
 * Xóa một cuộc trò chuyện khỏi danh sách
 */
export function deleteConversation(id: string): void {
  const existing = loadLocalConversations();
  const filtered = existing.filter((c) => c.id !== id);
  persistLocalConversations(filtered);

  if (getActiveConversationId() === id) {
    const nextActive = filtered.length > 0 ? filtered[0].id : "";
    if (nextActive) {
      setActiveConversationId(nextActive);
    } else {
      if (typeof window !== "undefined") {
        localStorage.removeItem(ACTIVE_CONVERSATION_KEY);
      }
    }
  }
}

/**
 * Xóa toàn bộ lịch sử cuộc trò chuyện
 */
export function clearAllConversations(): void {
  if (typeof window === "undefined") return;
  try {
    localStorage.removeItem(CONVERSATIONS_STORAGE_KEY);
    localStorage.removeItem(ACTIVE_CONVERSATION_KEY);
  } catch {}
}

/**
 * Phân nhóm cuộc trò chuyện theo mốc thời gian: Hôm nay, Hôm qua, 7 ngày trước, Cũ hơn
 */
export function groupConversationsByDate(convs: ChatConversation[]): Record<string, ChatConversation[]> {
  const groups: Record<string, ChatConversation[]> = {
    "Hôm nay": [],
    "Hôm qua": [],
    "7 ngày trước": [],
    "Cũ hơn": [],
  };

  const now = new Date();
  const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const yesterdayStart = todayStart - 24 * 60 * 60 * 1000;
  const sevenDaysAgoStart = todayStart - 7 * 24 * 60 * 60 * 1000;

  for (const c of convs) {
    const time = new Date(c.updatedAt).getTime();
    if (time >= todayStart) {
      groups["Hôm nay"].push(c);
    } else if (time >= yesterdayStart) {
      groups["Hôm qua"].push(c);
    } else if (time >= sevenDaysAgoStart) {
      groups["7 ngày trước"].push(c);
    } else {
      groups["Cũ hơn"].push(c);
    }
  }

  // Loại bỏ các nhóm rỗng
  const result: Record<string, ChatConversation[]> = {};
  for (const [key, list] of Object.entries(groups)) {
    if (list.length > 0) {
      result[key] = list;
    }
  }
  return result;
}

/**
 * Tìm kiếm cuộc trò chuyện theo từ khóa trong Tiêu đề hoặc Nội dung tin nhắn
 */
export function searchConversations(convs: ChatConversation[], query: string): ChatConversation[] {
  if (!query || !query.trim()) return convs;
  const q = query.toLowerCase().trim();

  return convs.filter((c) => {
    if (c.title.toLowerCase().includes(q)) return true;
    return c.messages.some((m) => m.content && m.content.toLowerCase().includes(q));
  });
}

/**
 * Đồng bộ cuộc trò chuyện với FastAPI backend nếu người dùng đã đăng nhập
 */
export async function syncConversationWithBackend(conv: ChatConversation): Promise<void> {
  if (typeof window === "undefined") return;
  try {
    const token =
      localStorage.getItem("pharmatrust_access_token") ||
      localStorage.getItem("pharmatrust_token") ||
      localStorage.getItem("h4care_auth_token");

    if (!token) return;

    await fetch("/api/v1/chat/conversations", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        id: conv.id,
        title: conv.title,
        session_id: conv.sessionId,
        messages: conv.messages.map((m) => ({
          id: m.id,
          role: m.role,
          content: m.content,
          timestamp: m.timestamp,
          attachments: m.attachments,
          safety_alert: m.safetyAlert,
          quick_replies: m.quickReplies,
          api_status: m.apiStatus,
          model_used: m.modelUsed,
          latency_ms: m.latencyMs,
          is_error: m.isError,
        })),
        extracted_memory: conv.extractedMemory,
      }),
    });
  } catch (err) {
    console.debug("[ConversationStorage] Background sync skipped:", err);
  }
}

/**
 * Xóa cuộc trò chuyện trên FastAPI backend nếu người dùng đã đăng nhập
 */
export async function deleteConversationOnBackend(id: string): Promise<void> {
  if (typeof window === "undefined") return;
  try {
    const token =
      localStorage.getItem("pharmatrust_access_token") ||
      localStorage.getItem("pharmatrust_token") ||
      localStorage.getItem("h4care_auth_token");

    if (!token) return;

    await fetch(`/api/v1/chat/conversations/${id}`, {
      method: "DELETE",
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });
  } catch (err) {
    console.debug("[ConversationStorage] Delete on backend skipped:", err);
  }
}

