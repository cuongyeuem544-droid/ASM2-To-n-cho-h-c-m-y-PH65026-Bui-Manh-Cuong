"use client";

import React, { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  MessageSquare,
  X,
  Minus,
  RotateCcw,
  Sparkles,
  Pill,
  Headphones,
  Bot,
  ShieldCheck,
  PhoneCall,
  Clock,
  ExternalLink,
} from "lucide-react";
import {
  ChatMessage,
  ChatResponse,
  ExtractedMemory,
  ChatAttachment,
  ChatConversation,
} from "@/lib/chatbot/types";
import { ChatMessageList } from "./ChatMessageList";
import { QuickReplyChips } from "./QuickReplyChips";
import { ChatInput } from "./ChatInput";
import { H4CareAiLogo } from "./H4CareAiLogo";
import { LiveChatPanel } from "./LiveChatPanel";
import { ChatHistoryDrawer } from "./ChatHistoryDrawer";
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
  syncConversationWithBackend,
  deleteConversationOnBackend,
  createInitialWelcomeMessage,
  getFormattedTime,
} from "@/lib/chatbot/conversation-storage";

export const ChatbotWidget: React.FC = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [isMinimized, setIsMinimized] = useState(false);
  const [activeTab, setActiveTab] = useState<"ai" | "human">("ai");
  const [isHistoryOpen, setIsHistoryOpen] = useState(false);
  const [conversations, setConversations] = useState<ChatConversation[]>([]);
  const [activeConversationId, setActiveConversationIdState] = useState<string>("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [hasUnread, setHasUnread] = useState(false);
  const [isMounted, setIsMounted] = useState(false);
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [handoffContext, setHandoffContext] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string>("sess-init");
  const [extractedMemory, setExtractedMemory] = useState<ExtractedMemory>({});
  const [lightboxAttachment, setLightboxAttachment] = useState<ChatAttachment | null>(null);

  const extractedMemoryRef = React.useRef<ExtractedMemory>({});
  const sessionIdRef = React.useRef<string>("sess-init");

  // Đồng bộ ref với state
  useEffect(() => {
    extractedMemoryRef.current = extractedMemory;
  }, [extractedMemory]);

  useEffect(() => {
    sessionIdRef.current = sessionId;
  }, [sessionId]);

  const [contextProduct, setContextProduct] = useState<{
    id: string;
    name: string;
    slug: string;
    brand?: string;
    activeIngredient?: string;
    price?: number;
    isPrescription?: boolean;
  } | null>(null);

  // Khôi phục danh sách cuộc trò chuyện và memory từ LocalStorage khi component mount
  useEffect(() => {
    setIsMounted(true);
    try {
      const token =
        localStorage.getItem("pharmatrust_access_token") ||
        localStorage.getItem("pharmatrust_token") ||
        localStorage.getItem("h4care_auth_token");
      setIsLoggedIn(!!token);

      const localConvs = loadLocalConversations();
      let activeId = getActiveConversationId();
      let activeConv: ChatConversation | undefined;

      if (localConvs.length > 0) {
        if (activeId) {
          activeConv = localConvs.find((c) => c.id === activeId);
        }
        if (!activeConv) {
          activeConv = localConvs[0];
          activeId = activeConv.id;
          setActiveConversationId(activeId);
        }
        setConversations(localConvs);
        setActiveConversationIdState(activeId || activeConv.id);
        setMessages(
          activeConv.messages.length > 0 ? activeConv.messages : [createInitialWelcomeMessage()]
        );
        setExtractedMemory(activeConv.extractedMemory || {});
        extractedMemoryRef.current = activeConv.extractedMemory || {};
        const sess = activeConv.sessionId || `sess-${activeConv.id}`;
        setSessionId(sess);
        sessionIdRef.current = sess;
      } else {
        const newConv = createNewConversation();
        setConversations([newConv]);
        setActiveConversationIdState(newConv.id);
        setActiveConversationId(newConv.id);
        setMessages(newConv.messages);
        setExtractedMemory({});
        extractedMemoryRef.current = {};
        const sess = newConv.sessionId || `sess-${newConv.id}`;
        setSessionId(sess);
        sessionIdRef.current = sess;
      }
    } catch (e) {
      console.warn("Could not load chat conversations on mount:", e);
    }
  }, []);

  // Lắng nghe phím Escape để đóng Lightbox hoặc History Drawer
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        if (lightboxAttachment) {
          setLightboxAttachment(null);
        } else if (isHistoryOpen) {
          setIsHistoryOpen(false);
        }
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [lightboxAttachment, isHistoryOpen]);

  // Lắng nghe sự kiện mở chat từ trang sản phẩm (PDP)
  useEffect(() => {
    const handleOpenChat = (event: Event) => {
      const customEvent = event as CustomEvent<{
        message?: string;
        contextProduct?: any;
        mode?: "ai" | "human";
      }>;
      setIsOpen(true);
      setIsMinimized(false);
      if (customEvent.detail?.mode) {
        setActiveTab(customEvent.detail.mode);
      }
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
  }, [messages, isLoading, contextProduct, conversations, activeConversationId]);

  // Chuyển đổi cuộc trò chuyện (Đảm bảo cô lập Memory & Ngữ cảnh hoàn toàn)
  const handleSelectConversation = (id: string) => {
    const target = conversations.find((c) => c.id === id);
    if (!target) return;

    setActiveConversationId(id);
    setActiveConversationIdState(id);
    setMessages(target.messages.length > 0 ? target.messages : [createInitialWelcomeMessage()]);
    setExtractedMemory(target.extractedMemory || {});
    extractedMemoryRef.current = target.extractedMemory || {};
    const sess = target.sessionId || `sess-${target.id}`;
    setSessionId(sess);
    sessionIdRef.current = sess;
    setIsHistoryOpen(false);
  };

  // Tạo cuộc trò chuyện mới hoàn toàn
  const handleNewConversation = () => {
    const newConv = createNewConversation();
    setConversations((prev) => [newConv, ...prev.filter((c) => c.id !== newConv.id)]);
    setActiveConversationIdState(newConv.id);
    setActiveConversationId(newConv.id);
    setMessages(newConv.messages);
    setExtractedMemory({});
    extractedMemoryRef.current = {};
    const sess = newConv.sessionId || `sess-${newConv.id}`;
    setSessionId(sess);
    sessionIdRef.current = sess;
    setIsHistoryOpen(false);
  };

  // Đổi tên cuộc trò chuyện
  const handleRenameConversation = (id: string, newTitle: string) => {
    renameConversation(id, newTitle);
    setConversations((prev) =>
      prev.map((c) => (c.id === id ? { ...c, title: newTitle, updatedAt: new Date().toISOString() } : c))
    );
  };

  // Xóa một cuộc trò chuyện
  const handleDeleteConversation = (id: string) => {
    deleteConversation(id);
    deleteConversationOnBackend(id);
    setConversations((prev) => {
      const remaining = prev.filter((c) => c.id !== id);
      if (activeConversationId === id) {
        if (remaining.length > 0) {
          const next = remaining[0];
          setActiveConversationIdState(next.id);
          setActiveConversationId(next.id);
          setMessages(next.messages);
          setExtractedMemory(next.extractedMemory || {});
          extractedMemoryRef.current = next.extractedMemory || {};
          const sess = next.sessionId || `sess-${next.id}`;
          setSessionId(sess);
          sessionIdRef.current = sess;
        } else {
          const newConv = createNewConversation();
          setActiveConversationIdState(newConv.id);
          setActiveConversationId(newConv.id);
          setMessages(newConv.messages);
          setExtractedMemory({});
          extractedMemoryRef.current = {};
          return [newConv];
        }
      }
      return remaining;
    });
  };

  // Xóa toàn bộ lịch sử
  const handleClearAllConversations = () => {
    clearAllConversations();
    const newConv = createNewConversation();
    setConversations([newConv]);
    setActiveConversationIdState(newConv.id);
    setActiveConversationId(newConv.id);
    setMessages(newConv.messages);
    setExtractedMemory({});
    extractedMemoryRef.current = {};
    const sess = newConv.sessionId || `sess-${newConv.id}`;
    setSessionId(sess);
    sessionIdRef.current = sess;
  };

  // Luồng Handoff chuyển từ AI sang Live Chat người thật
  const handleHandoffToHuman = (contextSummary?: string) => {
    const lastUserQuery = [...messages].reverse().find((m) => m.role === "user")?.content || "";
    const summary = contextSummary || `Khách hàng yêu cầu: "${lastUserQuery}"`;
    setHandoffContext(summary);
    setActiveTab("human");
    setIsMinimized(false);
  };

  const handleSendMessage = async (
    text: string,
    attachmentsOrProduct?: ChatAttachment[] | any,
    overrideProduct?: any
  ) => {
    let attachments: ChatAttachment[] | undefined;
    let currentOverrideProduct = overrideProduct;

    if (Array.isArray(attachmentsOrProduct)) {
      attachments = attachmentsOrProduct;
    } else if (
      attachmentsOrProduct &&
      typeof attachmentsOrProduct === "object" &&
      !("url" in attachmentsOrProduct)
    ) {
      currentOverrideProduct = attachmentsOrProduct;
    }

    const hasText = Boolean(text && text.trim());
    const hasAttachments = Boolean(attachments && attachments.length > 0);

    if ((!hasText && !hasAttachments) || isLoading) return;

    // Nếu người dùng gõ từ khóa muốn gặp người thật
    const lower = text.toLowerCase();
    if (
      lower.includes("gặp người thật") ||
      lower.includes("gap nguoi that") ||
      lower.includes("gặp dược sĩ") ||
      lower.includes("gap duoc si") ||
      lower.includes("gặp nhân viên") ||
      lower.includes("gap nhan vien") ||
      lower.includes("tư vấn trực tiếp") ||
      lower.includes("tu van truc tiep")
    ) {
      handleHandoffToHuman(`Khách hàng yêu cầu: "${text}"`);
      return;
    }

    const currentProduct = currentOverrideProduct || contextProduct;

    const userMessage: ChatMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      content: text,
      attachments: attachments && attachments.length > 0 ? attachments : undefined,
      timestamp: getFormattedTime(),
    };

    const updatedMessages = [...messages, userMessage];
    setMessages(updatedMessages);
    setIsLoading(true);

    // Tự động sinh tiêu đề nếu cuộc trò chuyện hiện tại đang để tiêu đề mặc định
    let currentConv = conversations.find((c) => c.id === activeConversationId);
    let updatedTitle = currentConv?.title || "Cuộc trò chuyện mới";
    if (
      (!currentConv ||
        currentConv.title === "Cuộc trò chuyện mới" ||
        currentConv.title === "Đoạn chat mới") &&
      (hasText || hasAttachments)
    ) {
      updatedTitle = generateTitleFromMessage(
        text.trim() || attachments?.[0]?.fileName || attachments?.[0]?.name || "Hình ảnh thuốc"
      );
    }

    try {
      const historyForApi = updatedMessages
        .filter((m) => m.role === "user" || m.role === "assistant")
        .slice(-8)
        .map((m) => ({
          role: m.role as "user" | "assistant",
          content: m.content,
        }));

      let currentMemory = extractedMemoryRef.current;
      const currentSessionId = sessionIdRef.current || sessionId;

      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: text,
          conversationHistory: historyForApi,
          contextProduct: currentProduct || undefined,
          sessionId: currentSessionId,
          conversationId: activeConversationId,
          extractedMemory: currentMemory,
          attachments: attachments && attachments.length > 0 ? attachments : undefined,
        }),
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.error || `HTTP ${res.status}`);
      }

      const data: ChatResponse = await res.json();

      let nextMemory = currentMemory;
      if (data.extractedMemory) {
        nextMemory = data.extractedMemory;
        extractedMemoryRef.current = data.extractedMemory;
        setExtractedMemory(data.extractedMemory);
      }
      if (data.sessionId) {
        sessionIdRef.current = data.sessionId;
        setSessionId(data.sessionId);
      }

      const botMessage: ChatMessage = {
        id: `bot-${Date.now()}`,
        role: "assistant",
        content: data.reply,
        timestamp: getFormattedTime(),
        recommendedProducts: data.recommendedProducts,
        safetyAlert: data.safetyAlert,
        quickReplies: data.quickReplies,
        apiStatus: data.apiStatus,
        modelUsed: data.modelUsed,
        latencyMs: data.latencyMs,
      };

      const finalMessages = [...updatedMessages, botMessage];
      setMessages(finalMessages);

      // Cập nhật và lưu cuộc trò chuyện vào Storage
      const updatedConv: ChatConversation = {
        id: activeConversationId || `conv-${Date.now()}`,
        title: updatedTitle,
        createdAt: currentConv?.createdAt || new Date().toISOString(),
        updatedAt: new Date().toISOString(),
        messages: finalMessages,
        extractedMemory: nextMemory,
        sessionId: currentSessionId,
      };

      saveConversation(updatedConv);
      setConversations((prev) => {
        const idx = prev.findIndex((c) => c.id === updatedConv.id);
        if (idx >= 0) {
          const cp = [...prev];
          cp[idx] = updatedConv;
          return cp;
        }
        return [updatedConv, ...prev];
      });

      // Đồng bộ ngầm với Backend cho người dùng đăng nhập
      syncConversationWithBackend(updatedConv);

      if (data.handoffRequested) {
        handleHandoffToHuman(data.contextSummary || `Khách hàng cần hỗ trợ: "${text}"`);
      }

      if (!isOpen) {
        setHasUnread(true);
      }
    } catch (err: any) {
      console.error("[Chatbot Error]:", err);
      const errorMessage: ChatMessage = {
        id: `err-${Date.now()}`,
        role: "assistant",
        content: `Dạ hệ thống gặp gián đoạn tạm thời: ${
          err.message || "Không thể kết nối máy chủ"
        }.\n\nQuý khách có thể chuyển sang tab **"Tư vấn trực tiếp"** để nhắn tin với nhân viên hỗ trợ ngay nhé!`,
        timestamp: getFormattedTime(),
        isError: true,
        quickReplies: ["🔄 Thử lại câu hỏi", "🎧 Chuyển sang tư vấn trực tiếp"],
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleToggleOpen = () => {
    if (!isOpen) {
      setIsOpen(true);
      setIsMinimized(false);
      setHasUnread(false);
    } else {
      setIsOpen(false);
    }
  };

  // Lấy quick replies từ tin nhắn bot cuối cùng
  const lastBotMessage = [...messages].reverse().find((m) => m.role === "assistant");
  const currentQuickReplies = lastBotMessage?.quickReplies || [];

  if (!isMounted) return null;

  return (
    <div className="fixed bottom-20 right-4 lg:bottom-6 lg:right-6 z-50 select-none">
      {/* Lightbox Modal phóng to ảnh */}
      {lightboxAttachment && (
        <div
          className="fixed inset-0 z-[100] bg-black/85 backdrop-blur-sm flex flex-col items-center justify-center p-4 animate-in fade-in duration-150"
          onClick={() => setLightboxAttachment(null)}
        >
          <div
            className="relative max-w-3xl max-h-[90vh] flex flex-col items-center"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="w-full flex items-center justify-between text-white/90 mb-2 px-1">
              <span className="text-xs font-semibold truncate max-w-xs sm:max-w-md">
                {lightboxAttachment.fileName || lightboxAttachment.name || "Hình ảnh đính kèm"}
              </span>
              <div className="flex items-center gap-2">
                <a
                  href={lightboxAttachment.url}
                  download={lightboxAttachment.fileName || lightboxAttachment.name || "h4care-image"}
                  target="_blank"
                  rel="noreferrer"
                  className="p-1.5 rounded-lg bg-white/10 hover:bg-white/20 text-white transition-colors"
                  title="Mở tab mới / Tải xuống"
                >
                  <ExternalLink className="w-4 h-4" />
                </a>
                <button
                  type="button"
                  onClick={() => setLightboxAttachment(null)}
                  className="p-1.5 rounded-lg bg-white/10 hover:bg-white/20 text-white transition-colors"
                  title="Đóng (Esc)"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
            </div>

            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={lightboxAttachment.url}
              alt={lightboxAttachment.fileName || lightboxAttachment.name || "Hình ảnh đính kèm"}
              className="max-h-[80vh] w-auto max-w-full rounded-2xl object-contain shadow-2xl border border-white/20"
            />
          </div>
        </div>
      )}

      {/* Cửa sổ Chatbot chính */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, y: 20, scale: 0.95 }}
            animate={{
              opacity: 1,
              y: 0,
              scale: 1,
              height: isMinimized ? "auto" : "630px",
            }}
            exit={{ opacity: 0, y: 20, scale: 0.95 }}
            transition={{ duration: 0.24, ease: "easeOut" }}
            className={`w-[calc(100vw-32px)] sm:w-[420px] max-h-[88vh] bg-white rounded-3xl border border-slate-200/90 shadow-depth-4 flex flex-col relative overflow-hidden mb-3 ${
              isMinimized ? "h-auto" : "h-[630px]"
            }`}
          >
            {/* Header Chatbot: Logo AI H4CARE + Điều Khiển */}
            <div className="px-4 py-3 bg-gradient-to-r from-brand-blue-800 via-brand-blue-700 to-teal-800 text-white flex items-center justify-between shrink-0 shadow-xs z-10">
              <div className="flex items-center gap-2.5">
                {/* Logo Trợ lý AI H4CARE độc quyền */}
                <div className="relative shrink-0">
                  <H4CareAiLogo size="md" showBadge={false} />
                  <span className="absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 rounded-full bg-emerald-400 border-2 border-brand-blue-800" />
                </div>

                <div>
                  <div className="flex items-center gap-1.5">
                    <h3 className="font-extrabold text-sm leading-none tracking-tight">
                      H4CARE Support
                    </h3>
                    <span className="inline-flex items-center gap-0.5 px-1.5 py-0.2 rounded-full bg-white/20 text-[9px] font-bold tracking-wider uppercase">
                      <ShieldCheck className="w-2.5 h-2.5 text-emerald-300" />
                      GPP
                    </span>
                  </div>
                  <p className="text-[11px] text-brand-blue-100 mt-1 flex items-center gap-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                    Hệ thống Dược thư & Tư vấn chuyên môn
                  </p>
                </div>
              </div>

              {/* Nút điều khiển: Lịch sử, New Chat, Minimize, Close */}
              <div className="flex items-center gap-1 text-white/80">
                {activeTab === "ai" && (
                  <>
                    <button
                      type="button"
                      onClick={() => setIsHistoryOpen(!isHistoryOpen)}
                      className={`p-1.5 rounded-lg transition-colors ${
                        isHistoryOpen
                          ? "bg-white/25 text-white"
                          : "hover:bg-white/10 hover:text-white"
                      }`}
                      title="Lịch sử đoạn chat"
                    >
                      <Clock className="w-4 h-4" />
                    </button>

                    <button
                      type="button"
                      onClick={handleNewConversation}
                      className="p-1.5 rounded-lg hover:bg-white/10 hover:text-white transition-colors"
                      title="Đoạn chat mới"
                    >
                      <RotateCcw className="w-4 h-4" />
                    </button>
                  </>
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

            {/* Thanh Tabs Chuyển Đổi: Trợ Lý AI 24/7 <-> Tư Vấn Trực Tiếp (Người Thật) */}
            {!isMinimized && (
              <div className="bg-slate-100 p-1 flex items-center border-b border-slate-200/90 text-xs font-bold shrink-0 z-10">
                <button
                  type="button"
                  onClick={() => {
                    setActiveTab("ai");
                    setIsHistoryOpen(false);
                  }}
                  className={`flex-1 py-1.5 px-2 rounded-xl flex items-center justify-center gap-1.5 transition-all ${
                    activeTab === "ai"
                      ? "bg-white text-brand-blue-700 shadow-2xs"
                      : "text-slate-600 hover:text-slate-900"
                  }`}
                >
                  <Sparkles className="w-3.5 h-3.5 text-brand-blue-600" />
                  <span>Trợ lý AI 24/7</span>
                  <span className="text-[9px] px-1 py-0.2 rounded bg-sky-100 text-sky-700">Tự động</span>
                </button>

                <button
                  type="button"
                  onClick={() => {
                    setActiveTab("human");
                    setIsHistoryOpen(false);
                  }}
                  className={`flex-1 py-1.5 px-2 rounded-xl flex items-center justify-center gap-1.5 transition-all ${
                    activeTab === "human"
                      ? "bg-white text-brand-blue-700 shadow-2xs"
                      : "text-slate-600 hover:text-slate-900"
                  }`}
                >
                  <Headphones className="w-3.5 h-3.5 text-teal-600" />
                  <span>Tư vấn trực tiếp</span>
                  <span className="text-[9px] px-1 py-0.2 rounded bg-teal-100 text-teal-800">Người thật</span>
                </button>
              </div>
            )}

            {/* Drawer Lịch sử trò chuyện */}
            <ChatHistoryDrawer
              isOpen={isHistoryOpen && !isMinimized && activeTab === "ai"}
              onClose={() => setIsHistoryOpen(false)}
              conversations={conversations}
              activeConversationId={activeConversationId}
              onSelectConversation={handleSelectConversation}
              onNewConversation={handleNewConversation}
              onRenameConversation={handleRenameConversation}
              onDeleteConversation={handleDeleteConversation}
              onClearAll={handleClearAllConversations}
              isLoggedIn={isLoggedIn}
            />

            {/* Nội dung khi không bị thu nhỏ */}
            {!isMinimized && (
              <>
                {/* TAB 1: CHATBOT AI RIÊNG BIỆT */}
                {activeTab === "ai" ? (
                  <div className="flex-1 flex flex-col overflow-hidden">
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

                    {/* Danh sách tin nhắn AI */}
                    <ChatMessageList
                      messages={messages}
                      isLoading={isLoading}
                      onHandoffToHuman={handleHandoffToHuman}
                      onViewImage={(att) => setLightboxAttachment(att)}
                    />

                    {/* Thanh gợi ý câu hỏi nhanh (Quick Replies) */}
                    {currentQuickReplies.length > 0 && !isLoading && (
                      <div className="px-4 py-1.5 bg-slate-50/80 border-t border-slate-100/90 overflow-x-auto scrollbar-none">
                        <div className="text-[10px] font-bold text-slate-400 mb-1 flex items-center gap-1">
                          <Sparkles className="w-2.5 h-2.5 text-brand-blue-500" />
                          <span>Gợi ý câu hỏi:</span>
                        </div>
                        <QuickReplyChips
                          chips={currentQuickReplies}
                          onSelect={(chip) => {
                            if (chip.includes("gặp nhân viên") || chip.includes("tư vấn trực tiếp")) {
                              handleHandoffToHuman();
                            } else {
                              handleSendMessage(chip);
                            }
                          }}
                          disabled={isLoading}
                        />
                      </div>
                    )}

                    {/* Ô nhập tin nhắn AI (hỗ trợ đính kèm ảnh, kéo thả, Ctrl+V) */}
                    <ChatInput
                      onSend={(msg, atts) => handleSendMessage(msg, atts)}
                      disabled={isLoading}
                      placeholder="Nhập tên thuốc, triệu chứng hoặc gửi ảnh nhãn thuốc..."
                    />

                    {/* Footer disclaimer và nút chuyển người thật */}
                    <div className="px-3 py-1.5 bg-slate-50 border-t border-slate-100 flex items-center justify-between text-[10px] text-slate-400">
                      <span>Trợ lý AI tự động • Không thay thế bác sĩ</span>
                      <button
                        type="button"
                        onClick={() => handleHandoffToHuman()}
                        className="text-brand-blue-700 font-bold hover:underline flex items-center gap-1"
                      >
                        <Headphones className="w-3 h-3" /> Gặp nhân viên
                      </button>
                    </div>
                  </div>
                ) : (
                  /* TAB 2: LIVE CHAT VỚI NHÂN VIÊN THẬT */
                  <LiveChatPanel
                    handoffContext={handoffContext}
                    onClearHandoff={() => setHandoffContext(null)}
                    onBackToAi={() => setActiveTab("ai")}
                    onNewMessageNotify={() => {
                      if (!isOpen) setHasUnread(true);
                    }}
                  />
                )}
              </>
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
            <span>Tư vấn AI & Dược sĩ 24/7</span>
          </motion.div>
        )}

        {/* Nút tròn chính hiển thị Logo AI H4CARE */}
        <motion.button
          type="button"
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          onClick={handleToggleOpen}
          aria-label="Mở trợ lý H4CARE"
          className="relative w-14 h-14 rounded-2xl bg-gradient-to-tr from-brand-blue-800 via-brand-blue-700 to-teal-700 text-white shadow-medical-lg flex items-center justify-center border-2 border-white/80 transition-shadow hover:shadow-medical-glow focus:outline-none focus:ring-4 focus:ring-brand-blue-200"
        >
          {isOpen ? (
            <X className="w-6 h-6 transition-transform rotate-0" />
          ) : (
            <>
              {/* Logo AI H4CARE ở vị trí nút mở */}
              <H4CareAiLogo size="md" showBadge={false} />

              {/* Badge tin nhắn chưa đọc */}
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
  );
};
