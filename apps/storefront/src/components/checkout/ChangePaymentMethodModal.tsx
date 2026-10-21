"use client";

import React, { useState, useEffect } from "react";
import {
  Banknote,
  QrCode,
  CreditCard,
  X,
  Check,
  AlertTriangle,
  Loader2,
  ShieldCheck,
  ArrowRight,
} from "lucide-react";

export type PaymentMethodType = "COD" | "SEPAY" | "PAYOS";

interface ChangePaymentMethodModalProps {
  isOpen: boolean;
  currentMethod: PaymentMethodType;
  totalAmount: number;
  orderCode: string;
  onClose: () => void;
  onConfirmChange: (newMethod: PaymentMethodType) => Promise<void>;
  isSubmitting?: boolean;
}

export default function ChangePaymentMethodModal({
  isOpen,
  currentMethod,
  totalAmount,
  orderCode,
  onClose,
  onConfirmChange,
  isSubmitting = false,
}: ChangePaymentMethodModalProps) {
  const [selectedMethod, setSelectedMethod] = useState<PaymentMethodType>(currentMethod);
  const [availableMethods, setAvailableMethods] = useState<Record<string, boolean>>({
    COD: true,
    SEPAY: true,
    PAYOS: false,
  });
  const [unavailabilityReasons, setUnavailabilityReasons] = useState<Record<string, string>>({});
  const [actionLoading, setActionLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Sync selectedMethod with currentMethod when modal opens
  useEffect(() => {
    if (isOpen) {
      setSelectedMethod(currentMethod);
      setErrorMsg(null);
    }
  }, [isOpen, currentMethod]);

  // Fetch live payment methods availability from backend
  useEffect(() => {
    if (!isOpen) return;
    let isMounted = true;
    const fetchMethods = async () => {
      try {
        const res = await fetch("/api/v1/payments/methods");
        if (res.ok) {
          const data = await res.json();
          if (data && Array.isArray(data.methods) && isMounted) {
            const availMap: Record<string, boolean> = {};
            const reasonMap: Record<string, string> = {};
            data.methods.forEach((m: any) => {
              availMap[m.id] = Boolean(m.available);
              if (m.unavailability_reason) {
                reasonMap[m.id] = m.unavailability_reason;
              }
            });
            setAvailableMethods(availMap);
            setUnavailabilityReasons(reasonMap);
          }
        }
      } catch (err) {
        // Fallback default
      }
    };
    fetchMethods();
    return () => {
      isMounted = false;
    };
  }, [isOpen]);

  if (!isOpen) return null;

  const handleConfirm = async () => {
    try {
      setActionLoading(true);
      setErrorMsg(null);
      await onConfirmChange(selectedMethod);
    } catch (err: any) {
      setErrorMsg(err?.message || "Không thể chuyển đổi phương thức thanh toán. Vui lòng thử lại.");
    } finally {
      setActionLoading(false);
    }
  };

  const methods = [
    {
      id: "COD" as PaymentMethodType,
      title: "Thanh toán khi nhận hàng (COD)",
      desc: "Kiểm tra hàng trước khi thanh toán bằng tiền mặt trực tiếp cho bưu tá khi nhận thuốc tận nơi.",
      icon: <Banknote className="w-5 h-5 text-emerald-600" />,
      tag: "Phổ biến",
      tagColor: "bg-emerald-50 text-emerald-700 border-emerald-200",
      available: availableMethods["COD"] !== false,
      reason: unavailabilityReasons["COD"],
    },
    {
      id: "SEPAY" as PaymentMethodType,
      title: "Chuyển khoản VietQR MBBank (SePay)",
      desc: "Quét mã VietQR Napas 247 trên ứng dụng ngân hàng bất kỳ. Hệ thống xác thực và kích hoạt đơn 24/7.",
      icon: <QrCode className="w-5 h-5 text-emerald-600" />,
      tag: "Tự động 24/7",
      tagColor: "bg-emerald-50 text-emerald-700 border-emerald-200",
      available: availableMethods["SEPAY"] !== false,
      reason: unavailabilityReasons["SEPAY"],
    },
    {
      id: "PAYOS" as PaymentMethodType,
      title: "Cổng thanh toán trực tuyến payOS",
      desc: "Thanh toán trực tuyến qua cổng payOS bằng mã QR hoặc thẻ ATM / tài khoản ngân hàng nội địa.",
      icon: <CreditCard className="w-5 h-5 text-blue-600" />,
      tag: availableMethods["PAYOS"] ? "Cổng trực tuyến" : "Đang bảo trì",
      tagColor: availableMethods["PAYOS"]
        ? "bg-blue-50 text-blue-700 border-blue-200"
        : "bg-slate-100 text-slate-500 border-slate-200",
      available: Boolean(availableMethods["PAYOS"]),
      reason: unavailabilityReasons["PAYOS"] || "Cổng thanh toán payOS hiện chưa được cấu hình sẵn sàng trên máy chủ.",
    },
  ];

  const getMethodName = (m: PaymentMethodType) => {
    if (m === "COD") return "Thanh toán khi nhận hàng (COD)";
    if (m === "SEPAY") return "Chuyển khoản VietQR MBBank";
    return "Cổng thanh toán payOS";
  };

  return (
    <div className="fixed inset-0 z-[1100] flex items-center justify-center p-3 sm:p-4 bg-slate-900/75 backdrop-blur-xs animate-in fade-in duration-200">
      <div className="relative w-full max-w-lg bg-white rounded-3xl shadow-2xl border border-slate-200 overflow-hidden flex flex-col max-h-[92vh]">
        {/* Header */}
        <div className="bg-gradient-to-r from-slate-900 via-slate-800 to-emerald-950 p-4 sm:p-5 text-white flex items-center justify-between shrink-0">
          <div>
            <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full bg-emerald-400/20 text-emerald-200 border border-emerald-300/30">
              Đơn hàng #{orderCode}
            </span>
            <h2 className="text-base sm:text-lg font-black tracking-tight mt-1">
              Đổi Phương Thức Thanh Toán
            </h2>
          </div>

          <button
            type="button"
            onClick={onClose}
            disabled={actionLoading || isSubmitting}
            className="p-1.5 rounded-xl bg-white/10 hover:bg-white/20 text-white/80 hover:text-white transition-colors disabled:opacity-50"
            title="Đóng cửa sổ"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Scrollable Body */}
        <div className="overflow-y-auto p-4 sm:p-6 space-y-4">
          {/* Order Snapshot Notice */}
          <div className="p-3.5 rounded-2xl bg-slate-50 border border-slate-200 text-xs flex items-center justify-between">
            <div>
              <span className="text-slate-500 font-medium">Số tiền đơn hàng:</span>
              <p className="text-base font-black text-rose-600 font-mono">
                {totalAmount.toLocaleString("vi-VN")} đ
              </p>
            </div>
            <div className="text-right">
              <span className="text-slate-500 font-medium">Hiện tại đang chọn:</span>
              <p className="font-bold text-slate-800">
                {getMethodName(currentMethod)}
              </p>
            </div>
          </div>

          {errorMsg && (
            <div className="p-3.5 rounded-xl bg-rose-50 border border-rose-200 text-xs text-rose-800 flex items-start gap-2">
              <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
              <span>{errorMsg}</span>
            </div>
          )}

          {/* Options Selection */}
          <div className="space-y-2.5">
            <label className="text-xs font-bold text-slate-700 block">
              Chọn phương thức thanh toán mới bạn muốn sử dụng:
            </label>

            {methods.map((method) => {
              const isSelected = selectedMethod === method.id;
              const isCurrent = currentMethod === method.id;
              const isDisabled = !method.available;

              return (
                <div
                  key={method.id}
                  onClick={() => {
                    if (!isDisabled && !actionLoading && !isSubmitting) {
                      setSelectedMethod(method.id);
                    }
                  }}
                  className={`relative p-3.5 rounded-2xl border-2 transition-all cursor-pointer ${
                    isDisabled
                      ? "opacity-55 cursor-not-allowed bg-slate-50 border-slate-200"
                      : isSelected
                      ? "bg-emerald-50/70 border-emerald-600 shadow-xs"
                      : "bg-white border-slate-200 hover:border-slate-300 hover:bg-slate-50/60"
                  }`}
                >
                  <div className="flex items-start gap-3">
                    {/* Radio circle */}
                    <div className="pt-0.5">
                      <div
                        className={`w-4 h-4 rounded-full border-2 flex items-center justify-center transition-colors ${
                          isSelected
                            ? "border-emerald-600 bg-emerald-600"
                            : "border-slate-300 bg-white"
                        }`}
                      >
                        {isSelected && <div className="w-1.5 h-1.5 rounded-full bg-white" />}
                      </div>
                    </div>

                    {/* Method Content */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-xs font-bold text-slate-900">
                          {method.title}
                        </span>
                        <span
                          className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${method.tagColor}`}
                        >
                          {method.tag}
                        </span>
                        {isCurrent && (
                          <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 border border-slate-200">
                            Đang dùng
                          </span>
                        )}
                      </div>

                      <p className="text-[11px] text-slate-600 mt-1 leading-relaxed">
                        {method.desc}
                      </p>

                      {isDisabled && method.reason && (
                        <div className="mt-1.5 flex items-center gap-1.5 text-[10px] text-amber-700 bg-amber-50 px-2 py-1 rounded-md border border-amber-200">
                          <AlertTriangle className="w-3 h-3 text-amber-600 shrink-0" />
                          <span>{method.reason}</span>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Guarantee Note */}
          <div className="p-3 rounded-xl bg-slate-50 border border-slate-200 text-slate-600 text-[11px] flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-emerald-600 shrink-0" />
            <span>
              Đổi phương thức sẽ giữ nguyên mã đơn #{orderCode}, sản phẩm và voucher. Không tạo đơn trùng lặp.
            </span>
          </div>
        </div>

        {/* Footer Actions */}
        <div className="p-4 bg-slate-50 border-t border-slate-200 flex flex-col sm:flex-row items-center justify-between gap-2 shrink-0">
          <button
            type="button"
            onClick={onClose}
            disabled={actionLoading || isSubmitting}
            className="w-full sm:w-auto px-4 py-2.5 rounded-xl border border-slate-300 hover:bg-slate-100 text-slate-700 font-bold text-xs transition-colors disabled:opacity-50"
          >
            Hủy / Giữ nguyên
          </button>

          <button
            type="button"
            onClick={handleConfirm}
            disabled={
              actionLoading ||
              isSubmitting ||
              (selectedMethod === currentMethod)
            }
            className="w-full sm:flex-1 py-2.5 px-4 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs flex items-center justify-center gap-2 shadow-sm transition-all disabled:opacity-50 cursor-pointer"
          >
            {actionLoading || isSubmitting ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Đang xử lý đổi phương thức...</span>
              </>
            ) : (
              <>
                <span>Xác nhận đổi sang {getMethodName(selectedMethod)}</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
