"use client";

import React, { useState, useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import {
  MessageSquare,
  X,
  Minus,
  RotateCcw,
  Bot,
  ShieldCheck,
  Sparkles,
  Pill,
  LogIn,
  Headphones,
  Clock,
  Download,
  ZoomIn,
} from "lucide-react";
import { useAuth } from "@/lib/auth/auth-context";
import {
  ChatAttachment,
  ChatConversation,
  ChatMessage,
  ChatResponse,
} from "@/lib/chatbot/types";
import {
  loadLocalConversations,
  persistLocalConversations,
  getActiveConversationId,
  setActiveConversationId,
  createNewConversation,
  saveConversation,
  renameConversation,
  deleteConversation,
  clearAllConversations,
  generateTitleFromMessage,
  createInitialWelcomeMessage,
  migrateWelcomeMessage,
} from "@/lib/chatbot/conversation-storage";
import { ChatMessageList } from "./ChatMessageList";
import { ChatInput } from "./ChatInput";
import { LiveChatPanel } from "./LiveChatPanel";
import { ChatHistoryDrawer } from "./ChatHistoryDrawer";
import { H4CareAiLogo } from "./H4CareAiLogo";

const AUTH_ROUTES = [
  "/login",
  "/register",
  "/forgot-password",
  "/reset-password",
  "/verify-otp",
];

const isAuthRoute = (path: string | null): boolean => {
  if (!path) return false;
  return AUTH_ROUTES.some((route) => path === route || path.startsWith(`${route}/`));
};

function getFormattedTime(): string {
  const now = new Date();
  return now.toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" });
}

export const ChatbotWidget: React.FC = () => {
  const router = useRouter();
  const pathname = usePathname();
  const { user, isAuthenticated } = useAuth();

  // Trạng thái mở / thu nhỏ / unread
  const [isOpen, setIsOpen] = useState(false);
  const [isMinimized, setIsMinimized] = useState(false);
  const [hasUnread, setHasUnread] = useState(false);
  const [isMounted, setIsMounted] = useState(false);
  const [showLoginModal, setShowLoginModal] = useState(false);

  // Tab điều hướng: "ai" (Trợ lý AI) hoặc "human" (Tư vấn trực tiếp - Người thật)
  const [activeTab, setActiveTab] = useState<"ai" | "human">("ai");

  // Ngữ cảnh chuyển giao cho tư vấn trực tiếp (handoff)
  const [handoffContext, setHandoffContext] = useState<string | null>(null);

  // Quản lý đa cuộc trò chuyện AI & Lịch sử
  const [conversations, setConversations] = useState<ChatConversation[]>([]);
  const [activeConvId, setActiveConvId] = useState<string>("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isHistoryOpen, setIsHistoryOpen] = useState(false);

  // Xem ảnh phóng to (Lightbox)
  const [selectedImagePreview, setSelectedImagePreview] = useState<ChatAttachment | null>(null);

  // Ngữ cảnh sản phẩm khi mở từ trang PDP
  const [contextProduct, setContextProduct] = useState<{
    id: string;
    name: string;
    slug: string;
    brand?: string;
    activeIngredient?: string;
    price?: number;
    isPrescription?: boolean;
  } | null>(null);

  // 1. Khởi tạo danh sách cuộc trò chuyện từ LocalStorage khi mount
  useEffect(() => {
    setIsMounted(true);
    try {
      // Dọn dẹp cache cũ nếu có trong sessionStorage
      if (typeof window !== "undefined") {
        try {
          const legacySession = sessionStorage.getItem("h4care_chat_messages_v1");
          if (
            legacySession &&
            (legacySession.includes("Tra cứu thuốc chính hãng") ||
              legacySession.includes("Dạ xin chào quý khách") ||
              legacySession.includes("Em là **Trợ lý AI H4CARE**"))
          ) {
            sessionStorage.removeItem("h4care_chat_messages_v1");
          }
        } catch {}
      }

      const localConvs = loadLocalConversations();
      if (localConvs && localConvs.length > 0) {
        setConversations(localConvs);
        const storedActiveId = getActiveConversationId();
        const active = localConvs.find((c) => c.id === storedActiveId) || localConvs[0];
        setActiveConvId(active.id);
        setActiveConversationId(active.id);
        if (active.messages && active.messages.length > 0) {
          const migratedMessages = active.messages.map((m, idx) =>
            idx === 0 ? migrateWelcomeMessage(m) : m
          );
          setMessages(migratedMessages);
        } else {
          setMessages([createInitialWelcomeMessage()]);
        }
      } else {
        const initialConv = createNewConversation(undefined, user?.id);
        setConversations([initialConv]);
        setActiveConvId(initialConv.id);
        setMessages(initialConv.messages);
      }
    } catch (e) {
      console.warn("Could not load conversations from storage:", e);
      setMessages([createInitialWelcomeMessage()]);
    }
  }, [user?.id]);

  // 2. Khi người dùng đăng xuất: Đóng chat, dọn dẹp phiên và đưa về trạng thái sạch
  useEffect(() => {
    if (!isAuthenticated) {
      setIsOpen(false);
      setIsMinimized(false);
      setContextProduct(null);
      setHasUnread(false);
      setActiveTab("ai");
      setIsHistoryOpen(false);
      setSelectedImagePreview(null);
    }
  }, [isAuthenticated]);

  // 3. Phím tắt Esc đóng Lightbox ảnh
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && selectedImagePreview) {
        setSelectedImagePreview(null);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [selectedImagePreview]);

  // 4. Lắng nghe sự kiện mở chat từ trang sản phẩm (PDP)
  useEffect(() => {
    const handleOpenChat = (event: Event) => {
      if (!isAuthenticated) {
        setShowLoginModal(true);
        return;
      }
      const customEvent = event as CustomEvent<{
        message?: string;
        contextProduct?: any;
      }>;
      setIsOpen(true);
      setIsMinimized(false);
      setActiveTab("ai");
      if (customEvent.detail?.contextProduct) {
        setContextProduct(customEvent.detail.contextProduct);
      }
      if (customEvent.detail?.message) {
        handleSendMessage(customEvent.detail.message, undefined, customEvent.detail.contextProduct);
      }
    };

    window.addEventListener("h4care_open_chat", handleOpenChat);
    return () => {
      window.removeEventListener("h4care_open_chat", handleOpenChat);
    };
  }, [isAuthenticated, messages, isLoading, contextProduct, activeConvId, conversations]);

  // 5. Gửi tin nhắn đến AI Assistant
  const handleSendMessage = async (
    text: string,
    attachments?: ChatAttachment[],
    overrideProduct?: any
  ) => {
    if ((!text.trim() && (!attachments || attachments.length === 0)) || isLoading) return;

    // Kiểm tra đăng nhập bắt buộc
    if (!isAuthenticated) {
      setShowLoginModal(true);
      return;
    }

    const token = typeof window !== "undefined" ? localStorage.getItem("pharmatrust_access_token") : null;
    if (!token) {
      setShowLoginModal(true);
      return;
    }

    const currentProduct = overrideProduct || contextProduct;

    const userMessage: ChatMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      content: text,
      timestamp: getFormattedTime(),
      attachments: attachments && attachments.length > 0 ? attachments : undefined,
    };

    const updatedMessages = [...messages, userMessage];
    setMessages(updatedMessages);
    setIsLoading(true);

    // Cập nhật tiêu đề cuộc trò chuyện nếu là tin nhắn đầu tiên của user
    const currentConv = conversations.find((c) => c.id === activeConvId);
    let updatedTitle = currentConv?.title;
    const isFirstUserMsg = !messages.some((m) => m.role === "user");
    if (isFirstUserMsg && text.trim()) {
      updatedTitle = generateTitleFromMessage(text.trim());
    }

    try {
      const historyForApi = updatedMessages
        .filter((m) => m.role === "user" || m.role === "assistant")
        .slice(-8)
        .map((m) => ({
          role: m.role as "user" | "assistant",
          content: m.content,
        }));

      const res = await fetch("/api/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          message: text,
          conversationHistory: historyForApi,
          contextProduct: currentProduct || undefined,
          attachments: attachments && attachments.length > 0 ? attachments : undefined,
          conversationId: activeConvId || undefined,
        }),
      });

      if (res.status === 401) {
        setShowLoginModal(true);
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.error || "Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.");
      }

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.error || `HTTP ${res.status}`);
      }

      const data: ChatResponse = await res.json();

      const botMessage: ChatMessage = {
        id: `bot-${Date.now()}`,
        role: "assistant",
        content: data.reply,
        timestamp: getFormattedTime(),
        recommendedProducts: data.recommendedProducts,
        safetyAlert: data.safetyAlert,
        quickReplies: data.quickReplies,
      };

      const finalMessages = [...updatedMessages, botMessage];
      setMessages(finalMessages);

      // Nếu AI đề xuất gặp nhân viên thật hoặc người dùng yêu cầu:
      if (data.isHumanSupport || data.handoffRequested) {
        setHandoffContext(data.contextSummary || `Khách hàng cần tư vấn: ${text}`);
      }

      // Lưu trữ cuộc trò chuyện hiện tại
      if (activeConvId) {
        const updatedConv: ChatConversation = {
          id: activeConvId,
          title: updatedTitle || currentConv?.title || "Cuộc trò chuyện",
          createdAt: currentConv?.createdAt || new Date().toISOString(),
          updatedAt: new Date().toISOString(),
          messages: finalMessages,
          extractedMemory: data.extractedMemory || currentConv?.extractedMemory || {},
          userId: user?.id || null,
          sessionId: currentConv?.sessionId || `sess-${Date.now()}`,
          isPinned: currentConv?.isPinned || false,
        };
        saveConversation(updatedConv);
        setConversations((prev) =>
          prev.map((c) => (c.id === activeConvId ? updatedConv : c))
        );
      }

      if (!isOpen) {
        setHasUnread(true);
      }
    } catch (err: any) {
      console.error("[Chatbot Error]:", err);
      const errorMessage: ChatMessage = {
        id: `err-${Date.now()}`,
        role: "assistant",
        content: `Dạ hệ thống gặp gián đoạn tạm thời: ${err.message || "Không thể kết nối máy chủ"}.\n\nQuý khách vui lòng thử lại sau giây lát hoặc gửi câu hỏi trực tiếp đến hòm thư hỗ trợ: **duocsi@h4care.vn** nhé ạ!`,
        timestamp: getFormattedTime(),
        isError: true,
        quickReplies: ["🔄 Thử lại câu hỏi vừa rồi", "🎧 Tư vấn trực tiếp"],
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  // 6. Quản lý chuyển đổi cuộc trò chuyện (Conversation Switcher)
  const handleSelectConversation = (id: string) => {
    const target = conversations.find((c) => c.id === id);
    if (target) {
      setActiveConvId(target.id);
      setActiveConversationId(target.id);
      const migrated =
        target.messages && target.messages.length > 0
          ? target.messages.map((m, idx) => (idx === 0 ? migrateWelcomeMessage(m) : m))
          : [createInitialWelcomeMessage()];
      setMessages(migrated);
      setIsHistoryOpen(false);
    }
  };

  const handleNewConversation = () => {
    const newConv = createNewConversation(undefined, user?.id);
    setConversations((prev) => [newConv, ...prev.filter((c) => c.id !== newConv.id)]);
    setActiveConvId(newConv.id);
    setActiveConversationId(newConv.id);
    setMessages(newConv.messages);
    setIsHistoryOpen(false);
  };

  const handleRenameConversation = (id: string, newTitle: string) => {
    renameConversation(id, newTitle);
    setConversations((prev) =>
      prev.map((c) => (c.id === id ? { ...c, title: newTitle, updatedAt: new Date().toISOString() } : c))
    );
  };

  const handleDeleteConversation = (id: string) => {
    deleteConversation(id);
    const remaining = conversations.filter((c) => c.id !== id);
    setConversations(remaining);
    if (activeConvId === id) {
      if (remaining.length > 0) {
        setActiveConvId(remaining[0].id);
        setActiveConversationId(remaining[0].id);
        setMessages(remaining[0].messages);
      } else {
        const newConv = createNewConversation(undefined, user?.id);
        setConversations([newConv]);
        setActiveConvId(newConv.id);
        setActiveConversationId(newConv.id);
        setMessages(newConv.messages);
      }
    }
  };

  const handleClearAllConversations = () => {
    clearAllConversations();
    const newConv = createNewConversation(undefined, user?.id);
    setConversations([newConv]);
    setActiveConvId(newConv.id);
    setActiveConversationId(newConv.id);
    setMessages(newConv.messages);
    setIsHistoryOpen(false);
  };

  const handleResetChat = () => {
    if (window.confirm("Bắt đầu cuộc trò chuyện mới? Đoạn chat hiện tại đã được lưu vào lịch sử.")) {
      handleNewConversation();
    }
  };

  const handleToggleOpen = () => {
    if (!isAuthenticated) {
      setShowLoginModal(true);
      return;
    }
    if (!isOpen) {
      setIsOpen(true);
      setIsMinimized(false);
      setHasUnread(false);
    } else {
      setIsOpen(false);
    }
  };

  // Ẩn hoàn toàn trên các trang xác thực (Zero Flash)
  if (isAuthRoute(pathname)) {
    return null;
  }

  if (!isMounted) return null;

  return (
    <>
      {/* Modal Yêu Cầu Đăng Nhập (Auth Gating Modal) */}
      <AnimatePresence>
        {showLoginModal && (
          <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-xs">
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 10 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 10 }}
              transition={{ duration: 0.2 }}
              className="relative w-full max-w-md bg-white rounded-3xl p-6 sm:p-7 shadow-2xl border border-slate-100 flex flex-col items-center text-center"
            >
              <button
                type="button"
                onClick={() => setShowLoginModal(false)}
                className="absolute top-4 right-4 p-1.5 rounded-full text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
                aria-label="Đóng"
              >
                <X className="w-5 h-5" />
              </button>

              <div className="w-14 h-14 rounded-2xl bg-gradient-to-tr from-brand-blue-600 to-brand-cyan-500 text-white flex items-center justify-center shadow-medical mb-4">
                <H4CareAiLogo size="md" />
              </div>

              <h3 className="text-lg font-bold text-slate-900 mb-2">
                Đăng nhập để sử dụng H4CARE Support
              </h3>
              <p className="text-xs sm:text-sm text-slate-600 leading-relaxed mb-6">
                Vui lòng đăng nhập để sử dụng Trợ lý AI, tư vấn trực tiếp và lưu lịch sử trò chuyện của bạn.
              </p>

              <div className="flex flex-col sm:flex-row items-center gap-3 w-full">
                <button
                  type="button"
                  onClick={() => {
                    setShowLoginModal(false);
                    const targetPath =
                      pathname && !isAuthRoute(pathname) ? pathname : "/";
                    router.push(`/login?redirect=${encodeURIComponent(targetPath)}`);
                  }}
                  className="w-full sm:w-auto sm:flex-1 py-2.5 px-4 rounded-xl bg-brand-blue-600 hover:bg-brand-blue-700 active:scale-98 text-white font-semibold text-sm shadow-md transition-all flex items-center justify-center gap-2"
                >
                  <LogIn className="w-4 h-4" />
                  <span>Đăng nhập ngay</span>
                </button>

                <button
                  type="button"
                  onClick={() => setShowLoginModal(false)}
                  className="w-full sm:w-auto py-2.5 px-4 rounded-xl bg-slate-100 hover:bg-slate-200 active:scale-98 text-slate-700 font-semibold text-sm transition-all"
                >
                  Để sau
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* Lightbox Modal Xem Ảnh Lớn */}
      <AnimatePresence>
        {selectedImagePreview && (
          <div
            className="fixed inset-0 z-[120] flex items-center justify-center p-4 bg-black/85 backdrop-blur-sm animate-in fade-in duration-200"
            onClick={() => setSelectedImagePreview(null)}
          >
            <div
              className="relative max-w-4xl max-h-[90vh] flex flex-col items-center"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="w-full flex items-center justify-between text-white/90 mb-2 px-1 text-xs">
                <span className="font-semibold truncate max-w-xs sm:max-w-md">
                  {selectedImagePreview.fileName || "Ảnh đính kèm"}
                </span>
                <div className="flex items-center gap-2">
                  {selectedImagePreview.url && (
                    <a
                      href={selectedImagePreview.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      download={selectedImagePreview.fileName || "download"}
                      className="p-1.5 rounded-lg bg-white/20 hover:bg-white/30 text-white transition-colors flex items-center gap-1 text-[11px]"
                      title="Tải ảnh về máy"
                    >
                      <Download className="w-3.5 h-3.5" />
                      <span className="hidden sm:inline">Tải về</span>
                    </a>
                  )}
                  <button
                    type="button"
                    onClick={() => setSelectedImagePreview(null)}
                    className="p-1.5 rounded-lg bg-white/20 hover:bg-white/30 text-white transition-colors"
                    title="Đóng (Esc)"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
              </div>
              <img
                src={
                  selectedImagePreview.url ||
                  (selectedImagePreview.base64Data
                    ? `data:${selectedImagePreview.mimeType};base64,${selectedImagePreview.base64Data}`
                    : "")
                }
                alt={selectedImagePreview.fileName || "Xem ảnh phóng to"}
                className="max-h-[80vh] max-w-[90vw] object-contain rounded-2xl shadow-2xl border border-white/20"
              />
            </div>
          </div>
        )}
      </AnimatePresence>

      {/* Cửa sổ chat nổi góc dưới */}
      <div className="fixed bottom-20 right-4 lg:bottom-6 lg:right-6 z-50 select-none">
        <AnimatePresence>
          {isOpen && (
            <motion.div
              initial={{ opacity: 0, y: 20, scale: 0.95 }}
              animate={{
                opacity: 1,
                y: 0,
                scale: 1,
                height: isMinimized ? "auto" : "640px",
              }}
              exit={{ opacity: 0, y: 20, scale: 0.95 }}
              transition={{ duration: 0.24, ease: "easeOut" }}
              className={`w-[calc(100vw-32px)] sm:w-[420px] max-h-[88vh] bg-white rounded-3xl border border-slate-200/90 shadow-depth-4 flex flex-col overflow-hidden mb-3 ${
                isMinimized ? "h-auto" : "h-[640px]"
              }`}
            >
              {/* Header Widget */}
              <div className="px-4 py-3 bg-gradient-to-r from-brand-blue-700 via-brand-blue-600 to-brand-blue-700 text-white flex items-center justify-between shrink-0 shadow-xs">
                <div className="flex items-center gap-2.5">
                  <div className="relative">
                    <div className="w-9 h-9 rounded-2xl bg-white/10 backdrop-blur-md flex items-center justify-center border border-white/20 shadow-xs">
                      {activeTab === "ai" ? (
                        <H4CareAiLogo size="xs" />
                      ) : (
                        <Headphones className="w-5 h-5 text-emerald-200" />
                      )}
                    </div>
                    {/* Chấm xanh online */}
                    <span className="absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 rounded-full bg-emerald-400 border-2 border-brand-blue-700" />
                  </div>

                  <div>
                    <div className="flex items-center gap-1.5">
                      <h3 className="font-extrabold text-sm leading-none tracking-tight">
                        {activeTab === "ai" ? "Trợ Lý AI H4CARE" : "Tư Vấn Trực Tiếp"}
                      </h3>
                      <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded-full bg-white/20 text-[9px] font-bold tracking-wider uppercase">
                        <ShieldCheck className="w-2.5 h-2.5 text-emerald-300" />
                        {activeTab === "ai" ? "AI 24/7" : "Người thật"}
                      </span>
                    </div>
                    <p className="text-[11px] text-brand-blue-100 mt-1 flex items-center gap-1">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                      {activeTab === "ai"
                        ? "Hỗ trợ y tế & giải đáp sức khỏe 24/7"
                        : "Kết nối Dược sĩ / Nhân viên trực tuyến"}
                    </p>
                  </div>
                </div>

                {/* Các nút điều khiển góc phải Header */}
                <div className="flex items-center gap-1 text-white/80">
                  {/* Nút Lịch sử đoạn chat (Chỉ hiện ở Tab AI) */}
                  {activeTab === "ai" && (
                    <button
                      type="button"
                      onClick={() => setIsHistoryOpen(true)}
                      className="p-1.5 rounded-lg hover:bg-white/10 hover:text-white transition-colors"
                      title="Lịch sử đoạn chat"
                    >
                      <Clock className="w-4 h-4" />
                    </button>
                  )}

                  {/* Nút Đoạn chat mới (Chỉ hiện ở Tab AI) */}
                  {activeTab === "ai" && (
                    <button
                      type="button"
                      onClick={handleResetChat}
                      className="p-1.5 rounded-lg hover:bg-white/10 hover:text-white transition-colors"
                      title="Cuộc trò chuyện mới"
                    >
                      <RotateCcw className="w-4 h-4" />
                    </button>
                  )}

                  <button
                    type="button"
                    onClick={() => setIsMinimized(!isMinimized)}
                    className="p-1.5 rounded-lg hover:bg-white/10 hover:text-white transition-colors"
                    title={isMinimized ? "Mở rộng" : "Thu nhỏ"}
                  >
                    <Minus className="w-4 h-4" />
                  </button>

                  <button
                    type="button"
                    onClick={() => setIsOpen(false)}
                    className="p-1.5 rounded-lg hover:bg-white/10 hover:text-white transition-colors"
                    title="Đóng cửa sổ chat"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
              </div>

              {/* Sub-header: Thanh chuyển 2 Tab (Dual-Tab Navigation) */}
              <div className="flex border-b border-slate-200/90 bg-slate-50/90 p-1 gap-1 text-xs font-semibold shrink-0">
                <button
                  type="button"
                  onClick={() => setActiveTab("ai")}
                  className={`flex-1 py-1.5 px-3 rounded-xl flex items-center justify-center gap-1.5 transition-all ${
                    activeTab === "ai"
                      ? "bg-white text-brand-blue-700 shadow-2xs font-bold border border-slate-200/80"
                      : "text-slate-600 hover:text-slate-900 hover:bg-slate-100"
                  }`}
                >
                  <Bot className="w-4 h-4 text-brand-blue-600 shrink-0" />
                  <span>Trợ lý AI 24/7</span>
                </button>

                <button
                  type="button"
                  onClick={() => setActiveTab("human")}
                  className={`flex-1 py-1.5 px-3 rounded-xl flex items-center justify-center gap-1.5 transition-all ${
                    activeTab === "human"
                      ? "bg-white text-emerald-700 shadow-2xs font-bold border border-slate-200/80"
                      : "text-slate-600 hover:text-slate-900 hover:bg-slate-100"
                  }`}
                >
                  <Headphones className="w-4 h-4 text-emerald-600 shrink-0" />
                  <span>Tư vấn trực tiếp</span>
                  <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse ml-0.5" />
                </button>
              </div>

              {/* Thân cửa sổ chat khi không bị thu nhỏ */}
              {!isMinimized && (
                <div className="flex-1 overflow-hidden flex flex-col relative">
                  {/* TAB 1: TRỢ LÝ AI */}
                  {activeTab === "ai" && (
                    <>
                      {/* Banner Ngữ Cảnh Sản Phẩm (nếu mở từ PDP) */}
                      {contextProduct && (
                        <div className="px-3 py-1.5 bg-brand-blue-50/90 border-b border-brand-blue-100 flex items-center justify-between text-xs text-brand-blue-900 shrink-0">
                          <div className="flex items-center gap-1.5 truncate">
                            <Pill className="w-3.5 h-3.5 text-brand-blue-600 shrink-0" />
                            <span className="text-[11px] font-bold truncate">
                              Đang tư vấn: {contextProduct.name}
                            </span>
                          </div>
                          <button
                            type="button"
                            onClick={() => setContextProduct(null)}
                            className="p-1 text-slate-400 hover:text-slate-700 ml-2 rounded transition-colors"
                            title="Bỏ ngữ cảnh sản phẩm"
                          >
                            <X className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      )}

                      {/* Danh sách tin nhắn */}
                      <ChatMessageList
                        messages={messages}
                        isLoading={isLoading}
                        onViewImage={(att) => setSelectedImagePreview(att)}
                      />

                      {/* Khung nhập tin nhắn phong cách ChatGPT */}
                      <ChatInput
                        onSend={(msg, atts) => handleSendMessage(msg, atts)}
                        disabled={isLoading}
                        placeholder="Nhập tên thuốc hoặc triệu chứng sức khỏe..."
                        onRequestLiveChat={() => setActiveTab("human")}
                      />

                      {/* Footer disclaimer y khoa */}
                      <div className="px-3 py-1 bg-slate-50 border-t border-slate-100 text-[9px] text-slate-400 text-center leading-tight shrink-0">
                        Thông tin tham khảo y khoa • Tham vấn bác sĩ khi có dấu hiệu bệnh nặng
                      </div>

                      {/* Drawer Lịch Sử Cuộc Trò Chuyện AI */}
                      <ChatHistoryDrawer
                        isOpen={isHistoryOpen}
                        onClose={() => setIsHistoryOpen(false)}
                        conversations={conversations}
                        activeConversationId={activeConvId}
                        onSelectConversation={handleSelectConversation}
                        onNewConversation={handleNewConversation}
                        onRenameConversation={handleRenameConversation}
                        onDeleteConversation={handleDeleteConversation}
                        onClearAll={handleClearAllConversations}
                        isLoggedIn={isAuthenticated}
                      />
                    </>
                  )}

                  {/* TAB 2: TƯ VẤN TRỰC TIẾP (NGƯỜI THẬT) */}
                  {activeTab === "human" && (
                    <LiveChatPanel
                      handoffContext={handoffContext}
                      onClearHandoff={() => setHandoffContext(null)}
                      onBackToAi={() => setActiveTab("ai")}
                      onNewMessageNotify={() => {
                        if (!isOpen) setHasUnread(true);
                      }}
                    />
                  )}
                </div>
              )}
            </motion.div>
          )}
        </AnimatePresence>

        {/* Nút bấm nổi bật mở Chatbot */}
        <div className="flex items-center justify-end gap-2.5">
          {/* Tooltip khi chưa mở */}
          {!isOpen && (
            <motion.div
              initial={{ opacity: 0, x: 10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.8 }}
              onClick={handleToggleOpen}
              className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-2xl bg-white border border-brand-blue-200/90 shadow-medical text-xs font-bold text-brand-blue-900 cursor-pointer hover:border-brand-blue-400 hover:shadow-card-hover transition-all"
            >
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-ping" />
              <span>Tư vấn Trợ lý AI & Trực tiếp</span>
            </motion.div>
          )}

          {/* Nút tròn chính */}
          <motion.button
            type="button"
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            onClick={handleToggleOpen}
            aria-label="Mở H4CARE Support"
            className="relative w-14 h-14 rounded-2xl bg-gradient-to-tr from-brand-blue-700 via-brand-blue-600 to-brand-cyan-500 text-white shadow-medical-lg flex items-center justify-center border-2 border-white/60 transition-shadow hover:shadow-medical-glow focus:outline-none focus:ring-4 focus:ring-brand-blue-200"
          >
            {isOpen ? (
              <X className="w-6 h-6 transition-transform rotate-0" />
            ) : (
              <>
                <MessageSquare className="w-6 h-6" />
                {hasUnread ? (
                  <span className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-rose-500 text-white text-[10px] font-black flex items-center justify-center border-2 border-white shadow-xs">
                    1
                  </span>
                ) : (
                  <span className="absolute -top-0.5 -right-0.5 w-3.5 h-3.5 rounded-full bg-emerald-400 border-2 border-white" />
                )}
              </>
            )}
          </motion.button>
        </div>
      </div>
    </>
  );
};
