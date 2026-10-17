"use client";

import React, { useEffect, useRef } from "react";
import { ChatMessage, ChatAttachment } from "@/lib/chatbot/types";
import { ChatMessageItem } from "./ChatMessageItem";
import { H4CareAiLogo } from "./H4CareAiLogo";
import { Sparkles } from "lucide-react";

interface ChatMessageListProps {
  messages: ChatMessage[];
  isLoading: boolean;
  onHandoffToHuman?: (context: string) => void;
  onViewImage?: (attachment: ChatAttachment) => void;
}

export const ChatMessageList: React.FC<ChatMessageListProps> = ({
  messages,
  isLoading,
  onHandoffToHuman,
  onViewImage,
}) => {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-4 scroll-smooth">
      {messages.map((msg) => (
        <ChatMessageItem
          key={msg.id}
          message={msg}
          onHandoffToHuman={onHandoffToHuman}
          onViewImage={onViewImage}
        />
      ))}

      {/* Typing Indicator với Logo AI H4CARE */}
      {isLoading && (
        <div className="flex gap-2.5 justify-start">
          <div className="shrink-0 mt-0.5">
            <H4CareAiLogo size="sm" showBadge={false} />
          </div>

          <div className="bg-white border border-slate-200/90 rounded-2xl rounded-tl-xs px-4 py-3 shadow-2xs flex flex-col gap-1.5">
            <div className="flex items-center gap-1.5 text-[10px] text-slate-400">
              <span className="font-extrabold text-brand-blue-800">Trợ Lý AI H4CARE</span>
              <span className="inline-flex items-center gap-0.5 text-sky-600 font-semibold">
                <Sparkles className="w-2.5 h-2.5 text-sky-500 animate-spin" />
                Đang đối chiếu dữ liệu Dược thư...
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
