"use client";

import React from "react";
import { ChatMessage } from "@/lib/chatbot/types";
import { MarkdownContent } from "./MarkdownContent";
import { ChatProductCard } from "./ChatProductCard";
import { AlertTriangle, Bot, User, PhoneCall, ShieldCheck } from "lucide-react";

interface ChatMessageItemProps {
  message: ChatMessage;
}

export const ChatMessageItem: React.FC<ChatMessageItemProps> = ({ message }) => {
  const isUser = message.role === "user";

  return (
    <div className={`flex gap-2.5 ${isUser ? "justify-end" : "justify-start"} group`}>
      {/* Avatar cho Bot */}
      {!isUser && (
        <div className="w-7 h-7 rounded-full bg-brand-blue-600 text-white flex items-center justify-center shrink-0 mt-0.5 shadow-xs border border-brand-blue-400">
          <Bot className="w-4 h-4" />
        </div>
      )}

      {/* Bubble tin nhắn */}
      <div
        className={`max-w-[85%] sm:max-w-[80%] flex flex-col ${
          isUser ? "items-end" : "items-start"
        }`}
      >
        <div
          className={`relative px-3.5 py-2.5 rounded-2xl text-xs ${
            isUser
              ? "bg-brand-blue-600 text-white rounded-tr-xs shadow-xs"
              : message.isError
              ? "bg-rose-50 border border-rose-200 text-rose-800 rounded-tl-xs shadow-2xs"
              : "bg-white border border-slate-200/90 text-slate-800 rounded-tl-xs shadow-2xs"
          }`}
        >
          {/* Header nhỏ cho Bot: Tên & Badge chuẩn GPP */}
          {!isUser && (
            <div className="flex items-center gap-1.5 mb-1.5 pb-1 border-b border-slate-100 text-[10px] text-slate-400">
              <span className="font-bold text-brand-blue-700">Dược sĩ AI H4CARE</span>
              <span className="inline-flex items-center gap-0.5 text-emerald-600 font-semibold">
                <ShieldCheck className="w-2.5 h-2.5" />
                Chuẩn GPP
              </span>
            </div>
          )}

          {/* Banner Cảnh Báo Khẩn Cấp (Red Flag Alert) */}
          {message.safetyAlert && (
            <div className="mb-2.5 p-2.5 rounded-xl bg-rose-50 border-2 border-rose-400/80 text-rose-900 shadow-2xs">
              <div className="flex items-center gap-1.5 font-black text-rose-700 text-xs uppercase tracking-wide">
                <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0 animate-pulse" />
                <span>{message.safetyAlert.title}</span>
              </div>
              <p className="mt-1 text-[11px] text-rose-800 leading-relaxed font-medium">
                {message.safetyAlert.message}
              </p>
              {message.safetyAlert.actionRequired && (
                <div className="mt-2 p-1.5 rounded-lg bg-white border border-rose-200 flex items-center justify-between text-xs font-bold text-rose-700">
                  <span className="text-[11px]">{message.safetyAlert.actionRequired}</span>
                  {message.safetyAlert.emergencyNumber && (
                    <a
                      href={`tel:${message.safetyAlert.emergencyNumber}`}
                      className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-rose-600 text-white hover:bg-rose-700 transition-colors shrink-0"
                    >
                      <PhoneCall className="w-3 h-3" />
                      115
                    </a>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Nội dung tin nhắn Markdown */}
          <MarkdownContent
            content={message.content}
            className={isUser ? "!text-white *:!text-white" : ""}
          />

          {/* Danh sách thẻ sản phẩm gợi ý (nếu có) */}
          {message.recommendedProducts && message.recommendedProducts.length > 0 && (
            <div className="mt-3 pt-2.5 border-t border-slate-100 w-full">
              <div className="flex items-center gap-1.5 text-[11px] font-bold text-slate-700 mb-2">
                <span>💊 Thuốc & sản phẩm liên quan từ H4CARE:</span>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {message.recommendedProducts.map((p) => (
                  <ChatProductCard key={p.id} product={p} />
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Timestamp */}
        <div
          className={`text-[10px] text-slate-400 mt-1 px-1 flex items-center gap-1 ${
            isUser ? "flex-row-reverse" : "flex-row"
          }`}
        >
          <span>{message.timestamp}</span>
        </div>
      </div>

      {/* Avatar cho User */}
      {isUser && (
        <div className="w-7 h-7 rounded-full bg-slate-100 text-slate-600 flex items-center justify-center shrink-0 mt-0.5 border border-slate-200">
          <User className="w-4 h-4" />
        </div>
      )}
    </div>
  );
};
