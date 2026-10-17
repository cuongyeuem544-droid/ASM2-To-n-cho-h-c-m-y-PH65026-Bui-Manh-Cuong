"use client";

import React, { useState, useRef, useEffect } from "react";
import { Send, Paperclip, X, Image as ImageIcon, Loader2, RefreshCw, AlertCircle } from "lucide-react";
import { ChatAttachment } from "@/lib/chatbot/types";

interface ChatInputProps {
  onSend: (message: string, attachments?: ChatAttachment[]) => void;
  disabled?: boolean;
  placeholder?: string;
}

const MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024; // 10 MB
const ALLOWED_EXTENSIONS = [".jpg", ".jpeg", ".png", ".webp"];

function formatFileSize(bytes: number): string {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}

export const ChatInput: React.FC<ChatInputProps> = ({
  onSend,
  disabled = false,
  placeholder = "Nhập tên thuốc, triệu chứng hoặc câu hỏi...",
}) => {
  const [text, setText] = useState("");
  const [attachment, setAttachment] = useState<ChatAttachment | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [pendingFile, setPendingFile] = useState<File | null>(null);

  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Auto-resize textarea theo nội dung nhập
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 120)}px`;
    }
  }, [text]);

  const uploadFile = async (file: File) => {
    // 1. Kiểm tra phần mở rộng
    const ext = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      setUploadError(`Định dạng '${ext}' không được hỗ trợ. Chỉ chấp nhận JPG, JPEG, PNG, WEBP.`);
      return;
    }

    // 2. Kiểm tra dung lượng
    if (file.size > MAX_FILE_SIZE_BYTES) {
      setUploadError(`Dung lượng tệp vượt quá 10 MB (${formatFileSize(file.size)}).`);
      return;
    }

    setPendingFile(file);
    setUploadError(null);
    setIsUploading(true);

    // Tạo preview URL cục bộ ngay lập tức
    const localUrl = URL.createObjectURL(file);
    setPreviewUrl(localUrl);

    try {
      const formData = new FormData();
      formData.append("file", file);

      const res = await fetch("/api/chat/upload", {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.error || `Lỗi tải lên HTTP ${res.status}`);
      }

      const data = await res.json();
      if (data.success && data.attachment) {
        setAttachment(data.attachment);
      } else {
        throw new Error("Phản hồi máy chủ không hợp lệ");
      }
    } catch (err: any) {
      console.error("[Upload file error]:", err);
      setUploadError(err.message || "Không thể tải ảnh lên. Vui lòng thử lại.");
    } finally {
      setIsUploading(false);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      uploadFile(file);
    }
    // Reset file input để có thể chọn lại cùng một file
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const handleRemoveAttachment = () => {
    setAttachment(null);
    setPreviewUrl(null);
    setPendingFile(null);
    setUploadError(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const handleRetryUpload = () => {
    if (pendingFile) {
      uploadFile(pendingFile);
    }
  };

  // Hỗ trợ dán ảnh từ clipboard (Ctrl+V)
  const handlePaste = (e: React.ClipboardEvent<HTMLTextAreaElement>) => {
    if (e.clipboardData.files && e.clipboardData.files.length > 0) {
      const file = e.clipboardData.files[0];
      if (file.type.startsWith("image/")) {
        e.preventDefault();
        uploadFile(file);
      }
    }
  };

  // Hỗ trợ kéo thả ảnh
  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const file = e.dataTransfer.files[0];
      if (file.type.startsWith("image/")) {
        uploadFile(file);
      } else {
        setUploadError("Chỉ chấp nhận tệp hình ảnh (JPG, JPEG, PNG, WEBP).");
      }
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleSubmit = () => {
    if (isUploading) return;
    const trimmed = text.trim();
    if (!trimmed && !attachment) return;
    if (disabled) return;

    onSend(trimmed, attachment ? [attachment] : undefined);
    setText("");
    handleRemoveAttachment();
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  };

  const canSubmit = !isUploading && (text.trim().length > 0 || attachment !== null);

  return (
    <div
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      className={`p-2.5 bg-white border-t border-slate-200/80 transition-colors ${
        isDragging ? "bg-brand-blue-50/50 border-brand-blue-400" : ""
      }`}
    >
      {/* Hidden File Input */}
      <input
        ref={fileInputRef}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        onChange={handleFileChange}
        className="hidden"
      />

      {/* Thanh xem trước ảnh trước khi gửi */}
      {(previewUrl || uploadError) && (
        <div className="mb-2 p-2 rounded-xl bg-slate-50 border border-slate-200 text-xs flex items-center justify-between gap-2 animate-in fade-in duration-150">
          <div className="flex items-center gap-2 min-w-0">
            {previewUrl ? (
              <div className="relative w-10 h-10 rounded-lg overflow-hidden border border-slate-200 bg-slate-100 shrink-0">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={previewUrl}
                  alt="Ảnh đính kèm"
                  className="w-full h-full object-cover"
                />
                {isUploading && (
                  <div className="absolute inset-0 bg-black/40 flex items-center justify-center">
                    <Loader2 className="w-4 h-4 text-white animate-spin" />
                  </div>
                )}
              </div>
            ) : (
              <div className="w-10 h-10 rounded-lg bg-rose-50 border border-rose-200 text-rose-600 flex items-center justify-center shrink-0">
                <AlertCircle className="w-5 h-5" />
              </div>
            )}

            <div className="min-w-0">
              <p className="font-semibold text-slate-700 truncate text-[11px]">
                {pendingFile?.name || "Tệp hình ảnh"}
              </p>
              {isUploading ? (
                <p className="text-[10px] text-brand-blue-600 flex items-center gap-1 font-medium">
                  <span>Đang tải lên và kiểm tra chữ ký...</span>
                </p>
              ) : uploadError ? (
                <p className="text-[10px] text-rose-600 truncate font-medium">
                  {uploadError}
                </p>
              ) : (
                <p className="text-[10px] text-emerald-600 font-medium flex items-center gap-1">
                  <span>Sẵn sàng gửi</span>
                  <span>• {formatFileSize(pendingFile?.size || 0)}</span>
                </p>
              )}
            </div>
          </div>

          <div className="flex items-center gap-1 shrink-0">
            {uploadError && (
              <button
                type="button"
                onClick={handleRetryUpload}
                className="p-1 rounded-md bg-white border border-slate-200 text-slate-600 hover:text-brand-blue-600 hover:bg-slate-50 transition-colors"
                title="Thử tải lại"
              >
                <RefreshCw className="w-3.5 h-3.5" />
              </button>
            )}
            <button
              type="button"
              onClick={handleRemoveAttachment}
              className="p-1 rounded-md bg-white border border-slate-200 text-slate-400 hover:text-rose-600 hover:bg-rose-50 transition-colors"
              title="Bỏ ảnh"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      )}

      {/* Khung nhập tin nhắn + nút đính kèm + nút gửi */}
      <div className="flex items-end gap-1.5 bg-slate-50 border border-slate-200 rounded-2xl px-2.5 py-1.5 focus-within:border-brand-blue-500 focus-within:bg-white focus-within:ring-2 focus-within:ring-brand-blue-100 transition-all">
        {/* Nút đính kèm ảnh (+) / kẹp giấy */}
        <button
          type="button"
          disabled={disabled || isUploading}
          onClick={() => fileInputRef.current?.click()}
          className="w-7 h-7 rounded-xl text-slate-500 hover:text-brand-blue-600 hover:bg-slate-200/60 disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center shrink-0 transition-colors mb-0.5"
          title="Đính kèm ảnh thuốc hoặc đơn thuốc (JPG, PNG, WEBP tối đa 10MB)"
        >
          <Paperclip className="w-4 h-4" />
        </button>

        <textarea
          ref={textareaRef}
          rows={1}
          value={text}
          disabled={disabled}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          onPaste={handlePaste}
          placeholder={attachment ? "Nhập câu hỏi về ảnh (không bắt buộc)..." : placeholder}
          maxLength={2000}
          className="flex-1 bg-transparent border-0 outline-none resize-none text-xs text-slate-800 placeholder:text-slate-400 py-1.5 leading-relaxed max-h-[120px]"
        />

        <button
          type="button"
          disabled={!canSubmit || disabled}
          onClick={handleSubmit}
          className="w-7 h-7 rounded-xl bg-brand-blue-600 text-white hover:bg-brand-blue-700 disabled:opacity-40 disabled:hover:bg-brand-blue-600 disabled:cursor-not-allowed flex items-center justify-center shrink-0 transition-all shadow-xs active:scale-95 mb-0.5"
          title="Gửi tin nhắn (Enter)"
        >
          {isUploading ? (
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
          ) : (
            <Send className="w-3.5 h-3.5" />
          )}
        </button>
      </div>

      <div className="mt-1 flex items-center justify-between text-[10px] text-slate-400 px-1">
        <span>Enter để gửi, dán ảnh Ctrl+V hoặc kéo thả</span>
        <span>H4CARE Chuẩn GPP</span>
      </div>
    </div>
  );
};
