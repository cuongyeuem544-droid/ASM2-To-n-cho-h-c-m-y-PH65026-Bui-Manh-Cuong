"use client";

import React from "react";
import { ChatMessage, ChatAttachment } from "@/lib/chatbot/types";
import { MarkdownContent } from "./MarkdownContent";
import { ChatProductCard } from "./ChatProductCard";
import { H4CareAiLogo } from "./H4CareAiLogo";
import { AlertTriangle, User, PhoneCall, Headphones, Sparkles, ZoomIn } from "lucide-react";

interface ChatMessageItemProps {
  message: ChatMessage;
  onHandoffToHuman?: (context: string) => void;
  onViewImage?: (attachment: ChatAttachment) => void;
}

export const ChatMessageItem: React.FC<ChatMessageItemProps> = ({
  message,
  onHandoffToHuman,
  onViewImage,
}) => {
  const isUser = message.role === "user";

  // Kiểm tra xem tin nhắn bot có gợi ý kết nối người thật hay không
  const isHumanSupportSuggestion =
    !isUser &&
    (message.content.includes("1800 6828") ||
      message.content.includes("duocsi@h4care.vn") ||
      message.content.includes("Dược sĩ chuyên môn H4CARE") ||
      message.content.includes("chuyển máy") ||
      message.content.includes("không thể chuyển máy") ||
      message.content.includes("chưa tìm thấy thông tin sản phẩm"));

  return (
    <div className={`flex gap-2.5 ${isUser ? "justify-end" : "justify-start"} group`}>
      {/* Avatar AI nhận diện riêng biệt H4CareAiLogo */}
      {!isUser && (
        <div className="shrink-0 mt-0.5">
          <H4CareAiLogo size="sm" showBadge={true} />
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
          {/* Header nhận diện rõ là Trợ lý AI tự động */}
          {!isUser && (
            <div className="flex items-center justify-between gap-1.5 mb-1.5 pb-1 border-b border-slate-100 text-[10px] text-slate-400">
              <div className="flex items-center gap-1.5 flex-wrap">
                <span className="font-extrabold text-brand-blue-800">Trợ Lý AI H4CARE</span>
                {message.apiStatus === "real_llm_success" ? (
                  <span className="inline-flex items-center gap-0.5 px-1 py-0.2 rounded bg-emerald-50 text-emerald-700 font-bold text-[9px] border border-emerald-200" title={`Mô hình: ${message.modelUsed || "LLM"} | Độ trễ: ${message.latencyMs || "?"}ms`}>
                    <Sparkles className="w-2.5 h-2.5 text-emerald-500" />
                    LLM Thực tế ({message.modelUsed || "Gemini"}){message.latencyMs ? ` • ${message.latencyMs}ms` : ""}
                  </span>
                ) : message.apiStatus === "quota_exceeded" ? (
                  <span className="inline-flex items-center gap-0.5 px-1 py-0.2 rounded bg-amber-50 text-amber-700 font-bold text-[9px] border border-amber-200">
                    ⚠️ Hết Quota LLM • Dự phòng H4CARE
                  </span>
                ) : message.apiStatus === "api_error" ? (
                  <span className="inline-flex items-center gap-0.5 px-1 py-0.2 rounded bg-rose-50 text-rose-700 font-bold text-[9px] border border-rose-200">
                    ⚠️ Lỗi API LLM • Dự phòng H4CARE
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-0.5 px-1 py-0.2 rounded bg-sky-50 text-sky-700 font-bold text-[9px] border border-sky-200">
                    <Sparkles className="w-2.5 h-2.5 text-sky-500" />
                    H4CARE Expert
                  </span>
                )}
              </div>
              <span className="text-[9px] text-slate-400 shrink-0">Tham khảo y khoa</span>
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

          {/* Tệp đính kèm / Hình ảnh */}
          {message.attachments && message.attachments.length > 0 && (
            <div className="mb-2 space-y-1.5">
              {message.attachments.map((att) => {
                const mime = att.mimeType || att.mime_type || "";
                const isImg = att.type === "image" || mime.startsWith("image/");
                const displayName = att.fileName || att.name || "Hình ảnh";
                return (
                  <div
                    key={att.id}
                    className="relative group/att overflow-hidden rounded-xl border border-slate-200/90 bg-slate-900/5 max-w-xs"
                  >
                    {isImg ? (
                      <div
                        onClick={() => onViewImage?.(att)}
                        className="cursor-pointer overflow-hidden relative group/img"
                        title="Bấm để xem ảnh kích thước lớn"
                      >
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img
                          src={att.url}
                          alt={displayName}
                          className="max-h-56 w-auto object-cover rounded-xl transition-transform duration-200 group-hover/img:scale-[1.02]"
                        />
                        <div className="absolute inset-0 bg-black/0 group-hover/img:bg-black/30 transition-all flex items-center justify-center opacity-0 group-hover/img:opacity-100">
                          <span className="px-2 py-1 rounded-md bg-black/75 text-white text-[10px] font-bold shadow-xs flex items-center gap-1">
                            <ZoomIn className="w-3 h-3" /> Phóng to
                          </span>
                        </div>
                      </div>
                    ) : (
                      <div className="p-2 flex items-center gap-2 text-xs">
                        <span className="font-medium truncate">{displayName}</span>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}

          {/* Nội dung tin nhắn Markdown */}
          {message.content && (
            <MarkdownContent
              content={message.content}
              className={isUser ? "!text-white *:!text-white" : ""}
            />
          )}

          {/* Nút Handoff chuyển sang nhân viên người thật khi AI đề xuất */}
          {isHumanSupportSuggestion && onHandoffToHuman && (
            <div className="mt-2.5 pt-2 border-t border-slate-100 flex items-center justify-between bg-brand-blue-50/60 p-2 rounded-xl">
              <div className="text-[11px] font-medium text-slate-700">
                Cần chuyên viên giải đáp trực tiếp?
              </div>
              <button
                type="button"
                onClick={() => onHandoffToHuman(message.content)}
                className="px-2.5 py-1 rounded-lg bg-brand-blue-600 hover:bg-brand-blue-700 text-white text-[11px] font-bold flex items-center gap-1 transition-colors shadow-2xs"
              >
                <Headphones className="w-3 h-3" />
                <span>Tư vấn trực tiếp</span>
              </button>
            </div>
          )}

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
