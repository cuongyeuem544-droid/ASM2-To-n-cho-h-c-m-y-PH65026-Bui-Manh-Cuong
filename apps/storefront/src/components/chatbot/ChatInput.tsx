"use client";

import React, { useState, useRef, useEffect } from "react";
import { Send } from "lucide-react";

interface ChatInputProps {
  onSend: (message: string) => void;
  disabled?: boolean;
  placeholder?: string;
}

export const ChatInput: React.FC<ChatInputProps> = ({
  onSend,
  disabled = false,
  placeholder = "Nhập tên thuốc, triệu chứng hoặc câu hỏi...",
}) => {
  const [text, setText] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-resize textarea theo nội dung nhập
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 120)}px`;
    }
  }, [text]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleSubmit = () => {
    const trimmed = text.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setText("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  };

  return (
    <div className="p-3 bg-white border-t border-slate-200/80">
      <div className="flex items-end gap-2 bg-slate-50 border border-slate-200 rounded-2xl px-3 py-1.5 focus-within:border-brand-blue-500 focus-within:bg-white focus-within:ring-2 focus-within:ring-brand-blue-100 transition-all">
        <textarea
          ref={textareaRef}
          rows={1}
          value={text}
          disabled={disabled}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          maxLength={2000}
          className="flex-1 bg-transparent border-0 outline-none resize-none text-xs text-slate-800 placeholder:text-slate-400 py-1.5 leading-relaxed max-h-[120px]"
        />

        <button
          type="button"
          disabled={!text.trim() || disabled}
          onClick={handleSubmit}
          className="w-8 h-8 rounded-xl bg-brand-blue-600 text-white hover:bg-brand-blue-700 disabled:opacity-40 disabled:hover:bg-brand-blue-600 disabled:cursor-not-allowed flex items-center justify-center shrink-0 transition-all shadow-xs active:scale-95"
          title="Gửi tin nhắn (Enter)"
        >
          <Send className="w-3.5 h-3.5" />
        </button>
      </div>

      <div className="mt-1.5 flex items-center justify-between text-[10px] text-slate-400 px-1">
        <span>Nhấn Enter để gửi, Shift+Enter xuống dòng</span>
        <span>H4CARE Chuẩn GPP</span>
      </div>
    </div>
  );
};
