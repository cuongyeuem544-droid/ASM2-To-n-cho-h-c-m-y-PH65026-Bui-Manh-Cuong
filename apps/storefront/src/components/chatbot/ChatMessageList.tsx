"use client";

import React, { useEffect, useRef } from "react";
import { ChatAttachment, ChatMessage } from "@/lib/chatbot/types";
import { ChatMessageItem } from "./ChatMessageItem";
import { Bot, ShieldCheck } from "lucide-react";

interface ChatMessageListProps {
  messages: ChatMessage[];
  isLoading: boolean;
  onViewImage?: (attachment: ChatAttachment) => void;
}

export const ChatMessageList: React.FC<ChatMessageListProps> = ({
  messages,
  isLoading,
  onViewImage,
}) => {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-4 scroll-smooth">
      {messages.map((msg) => (
        <ChatMessageItem key={msg.id} message={msg} onViewImage={onViewImage} />
      ))}

      {/* Typing Indicator */}
      {isLoading && (
        <div className="flex gap-2.5 justify-start">
          <div className="w-7 h-7 rounded-full bg-brand-blue-600 text-white flex items-center justify-center shrink-0 mt-0.5 shadow-xs border border-brand-blue-400">
            <Bot className="w-4 h-4" />
          </div>

          <div className="bg-white border border-slate-200/90 rounded-2xl rounded-tl-xs px-4 py-3 shadow-2xs flex flex-col gap-1.5">
            <div className="flex items-center gap-1.5 text-[10px] text-slate-400">
              <span className="font-bold text-brand-blue-700">Trợ lý AI H4CARE</span>
              <span className="inline-flex items-center gap-0.5 text-emerald-600 font-semibold">
                <ShieldCheck className="w-2.5 h-2.5" />
                Đang tra cứu dữ liệu...
              </span>
            </div>

            <div className="flex items-center gap-1.5 py-1">
              <span className="w-2 h-2 rounded-full bg-brand-blue-600 animate-bounce [animation-delay:-0.3s]" />
              <span className="w-2 h-2 rounded-full bg-brand-blue-600 animate-bounce [animation-delay:-0.15s]" />
              <span className="w-2 h-2 rounded-full bg-brand-blue-600 animate-bounce" />
            </div>
          </div>
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  );
};
