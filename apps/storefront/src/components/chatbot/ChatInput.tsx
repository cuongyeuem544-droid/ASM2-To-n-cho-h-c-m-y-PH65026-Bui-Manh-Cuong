"use client";

import React, { useState, useRef, useEffect, useCallback } from "react";
import {
  Send,
  Plus,
  X,
  Image as ImageIcon,
  FileText,
  FileUp,
  Camera,
  Mic,
  MicOff,
  Sparkles,
  Loader2,
  AlertCircle,
  Paperclip,
} from "lucide-react";
import { ChatAttachment } from "@/lib/chatbot/types";
import { SuggestedPromptsModal } from "./SuggestedPromptsModal";
import { CameraCaptureModal } from "./CameraCaptureModal";

interface ChatInputProps {
  onSend: (message: string, attachments?: ChatAttachment[]) => void;
  disabled?: boolean;
  placeholder?: string;
  onRequestLiveChat?: () => void;
}

const MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024; // 10 MB
const ALL_ALLOWED_EXTENSIONS = [".jpg", ".jpeg", ".png", ".webp", ".pdf", ".doc", ".docx", ".txt"];
const IMAGE_ALLOWED_EXTENSIONS = [".jpg", ".jpeg", ".png", ".webp"];

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
  placeholder = "Nhập câu hỏi, triệu chứng hoặc thông tin thuốc...",
  onRequestLiveChat,
}) => {
  const [text, setText] = useState("");
  const [attachment, setAttachment] = useState<ChatAttachment | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [isPromptsOpen, setIsPromptsOpen] = useState(false);
  const [isCameraOpen, setIsCameraOpen] = useState(false);

  // Speech to text state
  const [isListening, setIsListening] = useState(false);
  const [speechSupported, setSpeechSupported] = useState(true);
  const [speechNotice, setSpeechNotice] = useState<string | null>(null);

  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const galleryInputRef = useRef<HTMLInputElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const recognitionRef = useRef<any>(null);
  const baseTextRef = useRef<string>("");
  const finalTranscriptRef = useRef<string>("");

  // Dọn dẹp listener nhận diện giọng nói khi unmount
  useEffect(() => {
    return () => {
      if (recognitionRef.current) {
        recognitionRef.current.onstart = null;
        recognitionRef.current.onresult = null;
        recognitionRef.current.onerror = null;
        recognitionRef.current.onend = null;
        try {
          recognitionRef.current.abort();
        } catch {
          // ignore
        }
        recognitionRef.current = null;
      }
    };
  }, []);

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 120)}px`;
    }
  }, [text]);

  // Click outside to close plus menu
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setIsMenuOpen(false);
      }
    };
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setIsMenuOpen(false);
      }
    };
    if (isMenuOpen) {
      document.addEventListener("mousedown", handleClickOutside);
      document.addEventListener("keydown", handleEsc);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("keydown", handleEsc);
    };
  }, [isMenuOpen]);

  // Initialize Web Speech API
  useEffect(() => {
    if (typeof window !== "undefined") {
      const SpeechRecognition =
        (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
      if (!SpeechRecognition) {
        setSpeechSupported(false);
      }
    }
  }, []);

  const uploadFile = async (file: File) => {
    const ext = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
    if (!ALL_ALLOWED_EXTENSIONS.includes(ext)) {
      setUploadError(`Định dạng '${ext}' không được hỗ trợ. Chấp nhận JPG, PNG, WEBP, PDF, DOC, DOCX, TXT.`);
      return;
    }

    if (file.size > MAX_FILE_SIZE_BYTES) {
      setUploadError(`Dung lượng tệp vượt quá 10 MB (${formatFileSize(file.size)}).`);
      return;
    }

    setUploadError(null);
    setIsUploading(true);

    const isImg = IMAGE_ALLOWED_EXTENSIONS.includes(ext);
    if (isImg) {
      const localUrl = URL.createObjectURL(file);
      setPreviewUrl(localUrl);
    } else {
      setPreviewUrl(null);
    }

    try {
      const token = typeof window !== "undefined" ? localStorage.getItem("pharmatrust_access_token") : null;
      const formData = new FormData();
      formData.append("file", file);

      const headers: Record<string, string> = {};
      if (token) {
        headers["Authorization"] = `Bearer ${token}`;
      }

      const res = await fetch("/api/chat/upload", {
        method: "POST",
        headers,
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
      console.error("[Upload error]:", err);
      setUploadError(err.message || "Không thể tải tệp lên. Vui lòng thử lại.");
    } finally {
      setIsUploading(false);
    }
  };

  const handleClearAttachment = () => {
    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
    }
    setAttachment(null);
    setPreviewUrl(null);
    setUploadError(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
    if (galleryInputRef.current) galleryInputRef.current.value = "";
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleSubmit = () => {
    const trimmed = text.trim();
    if ((!trimmed && !attachment) || disabled || isUploading) return;

    onSend(trimmed, attachment ? [attachment] : undefined);
    setText("");
    handleClearAttachment();
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  };

  // Paste image handler (Ctrl+V)
  const handlePaste = (e: React.ClipboardEvent<HTMLTextAreaElement>) => {
    const items = e.clipboardData?.items;
    if (!items) return;
    for (let i = 0; i < items.length; i++) {
      if (items[i].type.startsWith("image/")) {
        const file = items[i].getAsFile();
        if (file) {
          uploadFile(file);
          e.preventDefault();
          break;
        }
      }
    }
  };

  // Drag and drop
  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    const files = e.dataTransfer.files;
    if (files && files.length > 0) {
      uploadFile(files[0]);
    }
  };

  // Speech recognition toggle
  const toggleSpeechRecognition = () => {
    if (!speechSupported) {
      setSpeechNotice("Trình duyệt của bạn chưa hỗ trợ nhận dạng giọng nói trực tiếp.");
      setTimeout(() => setSpeechNotice(null), 4000);
      return;
    }

    if (isListening) {
      if (recognitionRef.current) {
        recognitionRef.current.stop();
      }
      setIsListening(false);
      return;
    }

    try {
      const SpeechRecognition =
        (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
      const recognition = new SpeechRecognition();
      recognition.lang = "vi-VN";
      recognition.continuous = false;
      recognition.interimResults = true;

      recognition.onstart = () => {
        setIsListening(true);
        setSpeechNotice(null);
        baseTextRef.current = text.trim() ? `${text.trim()} ` : "";
        finalTranscriptRef.current = "";
      };

      recognition.onresult = (event: any) => {
        let interimTranscript = "";
        for (let i = event.resultIndex; i < event.results.length; i++) {
          const item = event.results[i];
          if (item.isFinal) {
            const finalChunk = item[0]?.transcript?.trim();
            if (finalChunk) {
              finalTranscriptRef.current = finalTranscriptRef.current
                ? `${finalTranscriptRef.current} ${finalChunk}`
                : finalChunk;
            }
          } else {
            interimTranscript += item[0]?.transcript || "";
          }
        }

        const committed = [baseTextRef.current, finalTranscriptRef.current]
          .filter(Boolean)
          .join("")
          .trim();

        const currentFull = interimTranscript.trim()
          ? (committed ? `${committed} ${interimTranscript.trim()}` : interimTranscript.trim())
          : committed;

        setText(currentFull);
      };

      recognition.onerror = (event: any) => {
        console.warn("[Speech Recognition Error]:", event.error);
        if (event.error === "not-allowed") {
          setSpeechNotice("Quyền truy cập micro đã bị từ chối. Vui lòng cấp quyền trong cài đặt trình duyệt.");
        } else if (event.error === "no-speech") {
          setSpeechNotice("Không nhận dạng được âm thanh. Vui lòng nói to và rõ hơn.");
        } else {
          setSpeechNotice(`Lỗi micro: ${event.error}`);
        }
        setIsListening(false);
        const finalCommitted = [baseTextRef.current, finalTranscriptRef.current]
          .filter(Boolean)
          .join("")
          .trim();
        if (finalCommitted) {
          setText(finalCommitted);
        }
        setTimeout(() => setSpeechNotice(null), 4000);
      };

      recognition.onend = () => {
        setIsListening(false);
        const finalCommitted = [baseTextRef.current, finalTranscriptRef.current]
          .filter(Boolean)
          .join("")
          .trim();
        if (finalCommitted) {
          setText(finalCommitted);
        }
      };

      recognitionRef.current = recognition;
      recognition.start();
    } catch (err: any) {
      console.warn("[Speech Error]:", err);
      setSpeechNotice("Không thể khởi động micro.");
      setIsListening(false);
      setTimeout(() => setSpeechNotice(null), 4000);
    }
  };

  const isSendActive = (text.trim().length > 0 || attachment !== null) && !isUploading && !disabled;

  return (
    <>
      <div
        onDragOver={(e) => e.preventDefault()}
        onDrop={handleDrop}
        className="p-3 bg-white border-t border-slate-200/80 relative"
      >
        {/* Hidden inputs */}
        <input
          ref={fileInputRef}
          type="file"
          accept=".jpg,.jpeg,.png,.webp,.pdf,.doc,.docx,.txt"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) uploadFile(f);
          }}
          className="hidden"
        />
        <input
          ref={galleryInputRef}
          type="file"
          accept="image/png,image/jpeg,image/webp,image/jpg"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) uploadFile(f);
          }}
          className="hidden"
        />

        {/* Thông báo lỗi upload hoặc micro */}
        {(uploadError || speechNotice) && (
          <div className="mb-2 p-2 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-xs flex items-center justify-between animate-in fade-in duration-150">
            <div className="flex items-center gap-1.5 flex-1 pr-2">
              <AlertCircle className="w-3.5 h-3.5 text-rose-500 shrink-0" />
              <span className="text-[11px] font-medium leading-tight">{uploadError || speechNotice}</span>
            </div>
            <button
              type="button"
              onClick={() => {
                setUploadError(null);
                setSpeechNotice(null);
              }}
              className="p-0.5 text-rose-400 hover:text-rose-600 rounded"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        )}

        {/* Preview file đính kèm */}
        {(attachment || previewUrl || isUploading) && (
          <div className="mb-2 p-2 rounded-2xl bg-slate-50 border border-slate-200/90 flex items-center justify-between">
            <div className="flex items-center gap-2 truncate">
              {previewUrl ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={previewUrl}
                  alt="Preview"
                  className="w-10 h-10 rounded-xl object-cover border border-slate-200 shrink-0"
                />
              ) : attachment?.type === "document" ? (
                <div className="w-10 h-10 rounded-xl bg-brand-blue-50 text-brand-blue-600 flex items-center justify-center border border-brand-blue-200 shrink-0">
                  <FileText className="w-5 h-5" />
                </div>
              ) : (
                <div className="w-10 h-10 rounded-xl bg-slate-100 text-slate-500 flex items-center justify-center shrink-0">
                  <Paperclip className="w-5 h-5" />
                </div>
              )}

              <div className="flex flex-col truncate">
                <span className="text-xs font-semibold text-slate-800 truncate">
                  {attachment?.fileName || "Đang xử lý tệp..."}
                </span>
                <span className="text-[10px] text-slate-400">
                  {isUploading ? (
                    <span className="inline-flex items-center gap-1 text-brand-blue-600 font-medium">
                      <Loader2 className="w-3 h-3 animate-spin" /> Đang tải lên an toàn...
                    </span>
                  ) : attachment ? (
                    formatFileSize(attachment.fileSize)
                  ) : null}
                </span>
              </div>
            </div>

            <button
              type="button"
              onClick={handleClearAttachment}
              className="p-1 rounded-full text-slate-400 hover:text-rose-600 hover:bg-rose-50 transition-colors ml-2 shrink-0"
              title="Xóa tệp đính kèm"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        )}

        {/* ChatGPT Style Input Container */}
        <div className="relative flex items-end gap-1.5 bg-slate-50 border border-slate-200 rounded-2xl px-2 py-1.5 focus-within:border-brand-blue-500 focus-within:bg-white focus-within:ring-2 focus-within:ring-brand-blue-100 transition-all">
          {/* Nút Dấu Cộng (+) */}
          <div className="relative shrink-0" ref={menuRef}>
            <button
              type="button"
              onClick={() => setIsMenuOpen(!isMenuOpen)}
              className={`w-8 h-8 rounded-xl flex items-center justify-center transition-all ${
                isMenuOpen
                  ? "bg-brand-blue-600 text-white rotate-45 shadow-2xs"
                  : "bg-white text-slate-600 border border-slate-200 hover:bg-slate-100 hover:text-slate-900"
              }`}
              title="Thêm tệp hoặc công cụ hỗ trợ (+)"
              aria-expanded={isMenuOpen}
            >
              <Plus className="w-4 h-4 transition-transform duration-200" />
            </button>

            {/* Menu Dấu Cộng 5 Chức Năng Chính */}
            {isMenuOpen && (
              <div className="absolute bottom-10 left-0 w-64 bg-white rounded-2xl shadow-xl border border-slate-100 p-1.5 z-50 animate-in fade-in zoom-in-95 duration-150">
                <div className="px-2.5 py-1 text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                  Công cụ hỗ trợ
                </div>

                {/* 1. Thêm ảnh và tệp */}
                <button
                  type="button"
                  onClick={() => {
                    setIsMenuOpen(false);
                    fileInputRef.current?.click();
                  }}
                  className="w-full text-left px-2.5 py-2 rounded-xl text-xs text-slate-700 hover:bg-brand-blue-50 hover:text-brand-blue-900 flex items-center gap-2.5 transition-colors group"
                >
                  <div className="w-7 h-7 rounded-lg bg-blue-100 text-brand-blue-700 flex items-center justify-center group-hover:bg-brand-blue-600 group-hover:text-white transition-colors">
                    <FileUp className="w-3.5 h-3.5" />
                  </div>
                  <div className="flex flex-col">
                    <span className="font-semibold text-xs leading-none">Thêm ảnh và tệp</span>
                    <span className="text-[10px] text-slate-400 mt-0.5">Ảnh, PDF, Word, TXT</span>
                  </div>
                </button>

                {/* 2. Thêm ảnh từ thư viện */}
                <button
                  type="button"
                  onClick={() => {
                    setIsMenuOpen(false);
                    galleryInputRef.current?.click();
                  }}
                  className="w-full text-left px-2.5 py-2 rounded-xl text-xs text-slate-700 hover:bg-brand-blue-50 hover:text-brand-blue-900 flex items-center gap-2.5 transition-colors group"
                >
                  <div className="w-7 h-7 rounded-lg bg-emerald-100 text-emerald-700 flex items-center justify-center group-hover:bg-emerald-600 group-hover:text-white transition-colors">
                    <ImageIcon className="w-3.5 h-3.5" />
                  </div>
                  <div className="flex flex-col">
                    <span className="font-semibold text-xs leading-none">Thêm ảnh từ thư viện</span>
                    <span className="text-[10px] text-slate-400 mt-0.5">Kho ảnh trên thiết bị</span>
                  </div>
                </button>

                {/* 3. Chụp ảnh trực tiếp */}
                <button
                  type="button"
                  onClick={() => {
                    setIsMenuOpen(false);
                    setIsCameraOpen(true);
                  }}
                  className="w-full text-left px-2.5 py-2 rounded-xl text-xs text-slate-700 hover:bg-brand-blue-50 hover:text-brand-blue-900 flex items-center gap-2.5 transition-colors group"
                >
                  <div className="w-7 h-7 rounded-lg bg-indigo-100 text-indigo-700 flex items-center justify-center group-hover:bg-indigo-600 group-hover:text-white transition-colors">
                    <Camera className="w-3.5 h-3.5" />
                  </div>
                  <div className="flex flex-col">
                    <span className="font-semibold text-xs leading-none">Chụp ảnh</span>
                    <span className="text-[10px] text-slate-400 mt-0.5">Chụp trực tiếp từ camera</span>
                  </div>
                </button>

                {/* 4. Ghi âm thành văn bản */}
                <button
                  type="button"
                  onClick={() => {
                    setIsMenuOpen(false);
                    toggleSpeechRecognition();
                  }}
                  className="w-full text-left px-2.5 py-2 rounded-xl text-xs text-slate-700 hover:bg-brand-blue-50 hover:text-brand-blue-900 flex items-center gap-2.5 transition-colors group"
                >
                  <div className="w-7 h-7 rounded-lg bg-amber-100 text-amber-700 flex items-center justify-center group-hover:bg-amber-600 group-hover:text-white transition-colors">
                    <Mic className="w-3.5 h-3.5" />
                  </div>
                  <div className="flex flex-col">
                    <span className="font-semibold text-xs leading-none">Ghi âm thành văn bản</span>
                    <span className="text-[10px] text-slate-400 mt-0.5">Nói để chuyển thành chữ</span>
                  </div>
                </button>

                {/* 5. Từ khóa & câu hỏi gợi ý */}
                <button
                  type="button"
                  onClick={() => {
                    setIsMenuOpen(false);
                    setIsPromptsOpen(true);
                  }}
                  className="w-full text-left px-2.5 py-2 rounded-xl text-xs text-slate-700 hover:bg-brand-blue-50 hover:text-brand-blue-900 flex items-center gap-2.5 transition-colors group border-t border-slate-100 mt-1 pt-2"
                >
                  <div className="w-7 h-7 rounded-lg bg-purple-100 text-purple-700 flex items-center justify-center group-hover:bg-purple-600 group-hover:text-white transition-colors">
                    <Sparkles className="w-3.5 h-3.5" />
                  </div>
                  <div className="flex flex-col">
                    <span className="font-semibold text-xs leading-none">Từ khóa & Câu hỏi gợi ý</span>
                    <span className="text-[10px] text-slate-400 mt-0.5">Mẫu câu hỏi thuốc & y tế</span>
                  </div>
                </button>
              </div>
            )}
          </div>

          {/* Textarea ở giữa */}
          <textarea
            ref={textareaRef}
            rows={1}
            value={text}
            disabled={disabled}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={handleKeyDown}
            onPaste={handlePaste}
            placeholder={isListening ? "Đang lắng nghe giọng nói của bạn..." : placeholder}
            maxLength={2000}
            className={`flex-1 bg-transparent border-0 outline-none resize-none text-xs text-slate-800 placeholder:text-slate-400 py-2 leading-relaxed max-h-[120px] ${
              isListening ? "placeholder:text-rose-500 placeholder:font-medium placeholder:animate-pulse" : ""
            }`}
          />

          {/* Nút Microphone */}
          <button
            type="button"
            onClick={toggleSpeechRecognition}
            className={`w-8 h-8 rounded-xl flex items-center justify-center shrink-0 transition-all ${
              isListening
                ? "bg-rose-500 text-white animate-pulse shadow-md"
                : "text-slate-400 hover:text-slate-700 hover:bg-slate-200/60"
            }`}
            title={isListening ? "Dừng ghi âm" : "Ghi âm giọng nói (Tiếng Việt)"}
          >
            {isListening ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
          </button>

          {/* Nút Gửi */}
          <button
            type="button"
            disabled={!isSendActive}
            onClick={handleSubmit}
            className={`w-8 h-8 rounded-xl flex items-center justify-center shrink-0 transition-all ${
              isSendActive
                ? "bg-brand-blue-600 text-white hover:bg-brand-blue-700 shadow-xs active:scale-95 cursor-pointer"
                : "bg-slate-200 text-slate-400 cursor-not-allowed opacity-60"
            }`}
            title="Gửi tin nhắn (Enter)"
          >
            <Send className="w-3.5 h-3.5" />
          </button>
        </div>

        {/* Footer tip */}
        <div className="mt-1.5 flex items-center justify-between text-[10px] text-slate-400 px-1">
          <span>Nhấn Enter để gửi • Shift+Enter xuống dòng</span>
          <span>Trợ lý AI H4CARE</span>
        </div>
      </div>

      {/* Modal Từ Khóa & Câu Hỏi Gợi Ý */}
      <SuggestedPromptsModal
        isOpen={isPromptsOpen}
        onClose={() => setIsPromptsOpen(false)}
        onSelectPrompt={(prompt) => {
          setText(prompt);
          if (textareaRef.current) {
            textareaRef.current.focus();
          }
        }}
        onRequestLiveChat={onRequestLiveChat}
      />

      {/* Modal Chụp Ảnh Trực Tiếp */}
      <CameraCaptureModal
        isOpen={isCameraOpen}
        onClose={() => setIsCameraOpen(false)}
        onCapture={(file) => {
          uploadFile(file);
        }}
        onFallbackToFile={() => {
          fileInputRef.current?.click();
        }}
      />
    </>
  );
};
