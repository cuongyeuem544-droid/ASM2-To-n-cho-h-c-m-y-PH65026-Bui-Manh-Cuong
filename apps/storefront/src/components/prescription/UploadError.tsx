"use client";

import React from "react";
import { AlertCircle, RefreshCw, XCircle } from "lucide-react";
import { ValidationErrorCode } from "@/types/prescription";

interface UploadErrorProps {
  message: string;
  code?: ValidationErrorCode | "INTERNAL_SERVER_ERROR" | "NETWORK_ERROR";
  onRetry?: () => void;
  onClear?: () => void;
}

export const UploadError: React.FC<UploadErrorProps> = ({
  message,
  code,
  onRetry,
  onClear,
}) => {
  // Gợi ý khắc phục thân thiện theo từng loại lỗi
  const getHelperText = () => {
    switch (code) {
      case "FILE_TOO_LARGE":
        return "Gợi ý: Bạn có thể dùng công cụ nén ảnh hoặc chụp lại ở độ phân giải tiêu chuẩn (dưới 10 MB).";
      case "UNSUPPORTED_TYPE":
      case "INVALID_SIGNATURE":
        return "Gợi ý: Hệ thống chỉ hỗ trợ định dạng JPG, JPEG, PNG hoặc tài liệu PDF chuẩn.";
      case "FILE_EMPTY":
        return "Gợi ý: Vui lòng mở thử file trên máy tính của bạn trước khi tải lên để đảm bảo dữ liệu không bị hỏng.";
      case "NETWORK_ERROR":
        return "Gợi ý: Vui lòng kiểm tra đường truyền Wi-Fi/4G và thử bấm nút tải lại.";
      default:
        return "Nếu sự cố tiếp tục xảy ra, vui lòng gửi email về duocsi@h4care.vn kèm ảnh toa thuốc để được hỗ trợ trực tiếp.";
    }
  };

  return (
    <div
      role="alert"
      className="p-4 sm:p-5 rounded-2xl bg-rose-50/90 border border-rose-200 text-rose-900 shadow-depth-1 animate-in fade-in duration-200"
    >
      <div className="flex items-start gap-3.5">
        <div className="p-2 rounded-xl bg-rose-100 text-rose-600 shrink-0">
          <AlertCircle className="w-5 h-5" />
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-2">
            <h4 className="text-sm font-bold text-rose-950">
              Không thể tiếp nhận đơn thuốc
            </h4>
            {code && (
              <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-rose-200/70 text-rose-800 font-semibold shrink-0">
                {code}
              </span>
            )}
          </div>

          <p className="text-xs text-rose-800 mt-1 leading-relaxed">{message}</p>
          <p className="text-[11px] text-rose-600/90 mt-1.5 font-medium">
            {getHelperText()}
          </p>

          <div className="flex items-center gap-3 mt-3.5 pt-2 border-t border-rose-200/60">
            {onRetry && (
              <button
                type="button"
                onClick={onRetry}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-700 text-white text-xs font-semibold shadow-xs transition-colors cursor-pointer"
              >
                <RefreshCw className="w-3.5 h-3.5" />
                <span>Thử tải lại</span>
              </button>
            )}

            {onClear && (
              <button
                type="button"
                onClick={onClear}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white hover:bg-rose-100/60 text-rose-700 border border-rose-300 text-xs font-medium transition-colors cursor-pointer"
              >
                <XCircle className="w-3.5 h-3.5 text-rose-500" />
                <span>Chọn file khác</span>
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
