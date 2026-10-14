"use client";

import React, { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  MessageSquare,
  X,
  Minus,
  RotateCcw,
  Bot,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { ChatMessage, ChatResponse } from "@/lib/chatbot/types";
import { ChatMessageList } from "./ChatMessageList";
import { QuickReplyChips } from "./QuickReplyChips";
import { ChatInput } from "./ChatInput";

const STORAGE_KEY = "h4care_chat_messages_v1";

const INITIAL_WELCOME_MESSAGE: ChatMessage = {
  id: "welcome-1",
  role: "assistant",
  content: `Dạ xin chào quý khách! Em là **Trợ lý Dược sĩ AI của H4CARE** 🩺\n\nEm có thể hỗ trợ quý khách:\n- 🔍 **Tra cứu thuốc chính hãng:** Công dụng, hoạt chất, cách dùng và giá niêm yết chuẩn GPP.\n- 📋 **Tư vấn hướng dẫn:** Phân biệt thuốc kê đơn (Rx) / OTC, quy trình thẩm định đơn thuốc.\n- 📦 **Chính sách & Vận chuyển:** Đổi trả trong 7 ngày, giải thích trạng thái đơn hàng.\n\n*⚠️ Lưu ý y tế: Mọi thông tin do Trợ lý AI cung cấp mang tính chất tham khảo khoa học, không thay thế chẩn đoán và chỉ định điều trị của Bác sĩ.*`,
  timestamp: "Vừa xong",
  quickReplies: [
    "🔍 Tra cứu Panadol Extra",
    "🤒 Tôi bị sốt và đau đầu",
    "📦 Chính sách đổi trả thuốc thế nào?",
    "💊 Hướng dẫn đặt thuốc kê đơn (Rx)",
  ],
};

function getFormattedTime(): string {
  const now = new Date();
  return now.toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" });
}

export const ChatbotWidget: React.FC = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [isMinimized, setIsMinimized] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([INITIAL_WELCOME_MESSAGE]);
  const [isLoading, setIsLoading] = useState(false);
  const [hasUnread, setHasUnread] = useState(false);
  const [isMounted, setIsMounted] = useState(false);

  // Khôi phục lịch sử chat từ sessionStorage khi component mount
  useEffect(() => {
    setIsMounted(true);
    try {
      const saved = sessionStorage.getItem(STORAGE_KEY);
      if (saved) {
        const parsed = JSON.parse(saved);
        if (Array.isArray(parsed) && parsed.length > 0) {
          setMessages(parsed);
        }
      }
    } catch (e) {
      console.warn("Could not load chat history from sessionStorage:", e);
    }
  }, []);

  // Lưu lịch sử chat vào sessionStorage khi có thay đổi
  useEffect(() => {
    if (!isMounted) return;
    try {
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(messages));
    } catch (e) {
      console.warn("Could not save chat history to sessionStorage:", e);
    }
  }, [messages, isMounted]);

  const handleSendMessage = async (text: string) => {
    if (!text.trim() || isLoading) return;

    const userMessage: ChatMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      content: text,
      timestamp: getFormattedTime(),
    };

    const updatedMessages = [...messages, userMessage];
    setMessages(updatedMessages);
    setIsLoading(true);

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
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: text,
          conversationHistory: historyForApi,
        }),
      });

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

      setMessages((prev) => [...prev, botMessage]);

      if (!isOpen) {
        setHasUnread(true);
      }
    } catch (err: any) {
      console.error("[Chatbot Error]:", err);
      const errorMessage: ChatMessage = {
        id: `err-${Date.now()}`,
        role: "assistant",
        content: `Dạ hệ thống gặp gián đoạn tạm thời: ${err.message || "Không thể kết nối máy chủ"}.\n\nQuý khách vui lòng thử lại sau giây lát hoặc gửi câu hỏi trực tiếp đến hòm thư Dược sĩ: **duocsi@h4care.vn** nhé ạ!`,
        timestamp: getFormattedTime(),
        isError: true,
        quickReplies: ["🔄 Thử lại câu hỏi vừa rồi", "📞 Kênh tư vấn Dược sĩ"],
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleResetChat = () => {
    if (window.confirm("Bắt đầu cuộc trò chuyện mới? Lịch sử tư vấn hiện tại sẽ được làm mới.")) {
      setMessages([INITIAL_WELCOME_MESSAGE]);
      try {
        sessionStorage.removeItem(STORAGE_KEY);
      } catch {}
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
      {/* Cửa sổ Chatbot chính */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, y: 20, scale: 0.95 }}
            animate={{
              opacity: 1,
              y: 0,
              scale: 1,
              height: isMinimized ? "auto" : "620px",
            }}
            exit={{ opacity: 0, y: 20, scale: 0.95 }}
            transition={{ duration: 0.24, ease: "easeOut" }}
            className={`w-[calc(100vw-32px)] sm:w-[410px] max-h-[85vh] bg-white rounded-3xl border border-slate-200/90 shadow-depth-4 flex flex-col overflow-hidden mb-3 ${
              isMinimized ? "h-auto" : "h-[620px]"
            }`}
          >
            {/* Header Chatbot */}
            <div className="px-4 py-3 bg-gradient-to-r from-brand-blue-700 via-brand-blue-600 to-brand-blue-700 text-white flex items-center justify-between shrink-0 shadow-xs">
              <div className="flex items-center gap-2.5">
                <div className="relative">
                  <div className="w-9 h-9 rounded-2xl bg-white/10 backdrop-blur-md flex items-center justify-center border border-white/20 shadow-xs">
                    <Bot className="w-5 h-5 text-white" />
                  </div>
                  {/* Chấm xanh báo online */}
                  <span className="absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 rounded-full bg-emerald-400 border-2 border-brand-blue-700" />
                </div>

                <div>
                  <div className="flex items-center gap-1.5">
                    <h3 className="font-extrabold text-sm leading-none tracking-tight">
                      Dược Sĩ AI H4CARE
                    </h3>
                    <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded-full bg-white/20 text-[9px] font-bold tracking-wider uppercase">
                      <ShieldCheck className="w-2.5 h-2.5 text-emerald-300" />
                      GPP
                    </span>
                  </div>
                  <p className="text-[11px] text-brand-blue-100 mt-1 flex items-center gap-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                    Trực tuyến 24/7 • Tra cứu thuốc chính hãng
                  </p>
                </div>
              </div>

              {/* Nút điều khiển: Reset, Minimize, Close */}
              <div className="flex items-center gap-1 text-white/80">
                <button
                  type="button"
                  onClick={handleResetChat}
                  className="p-1.5 rounded-lg hover:bg-white/10 hover:text-white transition-colors"
                  title="Cuộc trò chuyện mới"
                >
                  <RotateCcw className="w-4 h-4" />
                </button>

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

            {/* Nội dung khi không bị thu nhỏ */}
            {!isMinimized && (
              <>
                {/* Danh sách tin nhắn */}
                <ChatMessageList messages={messages} isLoading={isLoading} />

                {/* Thanh gợi ý câu hỏi nhanh (Quick Replies) */}
                {currentQuickReplies.length > 0 && !isLoading && (
                  <div className="px-4 py-1.5 bg-slate-50/80 border-t border-slate-100/90 overflow-x-auto scrollbar-none">
                    <div className="text-[10px] font-bold text-slate-400 mb-1 flex items-center gap-1">
                      <Sparkles className="w-2.5 h-2.5 text-brand-blue-500" />
                      <span>Gợi ý câu hỏi:</span>
                    </div>
                    <QuickReplyChips
                      chips={currentQuickReplies}
                      onSelect={(chip) => handleSendMessage(chip)}
                      disabled={isLoading}
                    />
                  </div>
                )}

                {/* Ô nhập tin nhắn */}
                <ChatInput
                  onSend={handleSendMessage}
                  disabled={isLoading}
                  placeholder="Nhập tên thuốc hoặc triệu chứng sức khỏe..."
                />

                {/* Footer disclaimer */}
                <div className="px-3 py-1 bg-slate-50 border-t border-slate-100 text-[9px] text-slate-400 text-center leading-tight">
                  Thông tin tham khảo y khoa • Tham vấn bác sĩ khi có dấu hiệu bệnh nặng
                </div>
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
            <span>Tư vấn Dược sĩ AI 24/7</span>
          </motion.div>
        )}

        {/* Nút tròn chính */}
        <motion.button
          type="button"
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          onClick={handleToggleOpen}
          aria-label="Mở trợ lý Dược sĩ H4CARE"
          className="relative w-14 h-14 rounded-2xl bg-gradient-to-tr from-brand-blue-700 via-brand-blue-600 to-brand-cyan-500 text-white shadow-medical-lg flex items-center justify-center border-2 border-white/60 transition-shadow hover:shadow-medical-glow focus:outline-none focus:ring-4 focus:ring-brand-blue-200"
        >
          {isOpen ? (
            <X className="w-6 h-6 transition-transform rotate-0" />
          ) : (
            <>
              <MessageSquare className="w-6 h-6" />
              {/* Badge tin nhắn chưa đọc hoặc online */}
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
