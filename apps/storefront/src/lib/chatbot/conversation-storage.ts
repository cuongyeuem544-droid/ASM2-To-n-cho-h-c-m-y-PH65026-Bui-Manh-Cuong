import { ChatAttachment, ChatConversation, ChatMessage, ExtractedMemory } from "./types";

const CONVERSATIONS_STORAGE_KEY = "h4care_conversations_v3";
const ACTIVE_CONVERSATION_KEY = "h4care_active_conv_id_v3";
const MAX_LOCAL_CONVERSATIONS = 30;

export const DEFAULT_WELCOME_MESSAGE_CONTENT = `Chào bạn! Mình là trợ lý AI của H4CARE. Mình có thể hỗ trợ bạn tìm hiểu thông tin thuốc, sản phẩm và giải đáp các thắc mắc về sức khỏe.\n\nBạn cần mình hỗ trợ điều gì hôm nay?`;
export const INITIAL_WELCOME_CONTENT = DEFAULT_WELCOME_MESSAGE_CONTENT;

export function getFormattedTime(): string {
  const now = new Date();
  return now.toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" });
}

export function createInitialWelcomeMessage(): ChatMessage {
  return {
    id: `welcome-${Date.now()}`,
    role: "assistant",
    content: DEFAULT_WELCOME_MESSAGE_CONTENT,
    timestamp: "Vừa xong",
    quickReplies: [],
  };
}

/**
 * Kiểm tra và chuyển đổi an toàn các tin nhắn chào cũ tự động sang lời chào chuẩn mực mới.
 * Không thay đổi bất kỳ tin nhắn thật nào của khách hàng hoặc câu trả lời nghiệp vụ của AI.
 */
export function migrateWelcomeMessage(msg: ChatMessage): ChatMessage {
  if (!msg || msg.role !== "assistant") return msg;
  const content = msg.content || "";
  const isOldWelcome =
    (msg.id && msg.id.startsWith("welcome")) ||
    content.includes("Tra cứu thuốc chính hãng") ||
    content.includes("Dạ xin chào quý khách") ||
    content.includes("Em là **Trợ lý AI H4CARE**") ||
    content.includes("Em là hệ thống tự động") ||
    content.includes("luôn sẵn sàng hỗ trợ bạn tìm hiểu thông tin thuốc, sản phẩm và giải đáp những thắc mắc") ||
    content.includes("Mình luôn sẵn sàng hỗ trợ bạn:\n- 💊") ||
    content.includes("Thông tin thuốc:** Công dụng, thành phần");

  if (isOldWelcome) {
    return {
      ...msg,
      content: DEFAULT_WELCOME_MESSAGE_CONTENT,
      quickReplies: [],
    };
  }
  return msg;
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
 * Tự động chuẩn hóa các lời chào cũ được khôi phục từ phiên trước.
 */
export function loadLocalConversations(): ChatConversation[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(CONVERSATIONS_STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed)) {
      let hasChanges = false;
      const migrated = parsed.map((conv: ChatConversation) => {
        if (conv.messages && Array.isArray(conv.messages) && conv.messages.length > 0) {
          const firstMsg = conv.messages[0];
          const updatedFirstMsg = migrateWelcomeMessage(firstMsg);
          if (
            updatedFirstMsg.content !== firstMsg.content ||
            (firstMsg.quickReplies && firstMsg.quickReplies.length > 0)
          ) {
            hasChanges = true;
            return {
              ...conv,
              messages: [updatedFirstMsg, ...conv.messages.slice(1)],
            };
          }
        }
        return conv;
      });

      if (hasChanges) {
        persistLocalConversations(migrated);
      }

      return migrated.sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime());
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
