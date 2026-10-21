"use client";

import React, { useState, useEffect } from "react";
import {
  QrCode,
  Copy,
  Check,
  Download,
  CheckCircle2,
  X,
  ShieldCheck,
  RefreshCw,
  ArrowRight,
  AlertCircle,
} from "lucide-react";

interface SepayVietQrModalProps {
  isOpen: boolean;
  orderCode: string;
  paymentCode: string;
  amount: number;
  bankName?: string;
  accountNumber?: string;
  accountHolder?: string;
  qrCodeUrl?: string;
  onClose: () => void;
  onChangeMethod?: () => void;
  onSuccess: () => void;
}

export default function SepayVietQrModal({
  isOpen,
  orderCode,
  paymentCode,
  amount,
  bankName: propBankName,
  accountNumber: propAccountNumber,
  accountHolder: propAccountHolder,
  qrCodeUrl: propQrCodeUrl,
  onClose,
  onChangeMethod,
  onSuccess,
}: SepayVietQrModalProps) {
  const [copiedField, setCopiedField] = useState<string | null>(null);
  const [isPaid, setIsPaid] = useState(false);
  const [pollingCount, setPollingCount] = useState(0);

  const bankName = propBankName || "Ngân hàng TMCP Quân Đội (MBBank)";
  const accountNumber = propAccountNumber || "0901234567";
  const accountHolder = propAccountHolder || "PHARMATRUST / H4CARE";
  const transferContent = paymentCode || orderCode;

  // URL VietQR chuẩn Napas 247
  const vietQrUrl =
    propQrCodeUrl ||
    `https://img.vietqr.io/image/MB-${accountNumber}-compact2.png?amount=${amount}&addInfo=${encodeURIComponent(
      transferContent
    )}&accountName=${encodeURIComponent(accountHolder)}`;

  // Polling tự động kiểm tra trạng thái từ Backend (render & neon staging)
  useEffect(() => {
    if (!isOpen || isPaid || !orderCode) return;

    let isMounted = true;
    const intervalId = setInterval(async () => {
      try {
        const token =
          typeof window !== "undefined"
            ? localStorage.getItem("h4care_auth_token") || localStorage.getItem("pharmatrust_token")
            : null;
        const orderToken =
          typeof window !== "undefined"
            ? localStorage.getItem(`h4care_order_token_${orderCode}`) ||
              localStorage.getItem("h4care_latest_order_token") ||
              ""
            : "";

        const headers: Record<string, string> = {};
        if (token) headers["Authorization"] = `Bearer ${token}`;
        if (orderToken) headers["X-Order-Token"] = orderToken;

        const endpoint = `/api/v1/payments/orders/${encodeURIComponent(orderCode)}/status`;
        const res = await fetch(endpoint, { headers });
        if (res.ok && isMounted) {
          const data = await res.json();
          setPollingCount((prev) => prev + 1);
          if (
            data.payment_status === "PAID" ||
            data.status === "PAID" ||
            data.order_status === "CONFIRMED"
          ) {
            setIsPaid(true);
            clearInterval(intervalId);
          }
        }
      } catch (e) {
        // Lỗi mạng hoặc polling tạm thời, tiếp tục kiểm tra
      }
    }, 2500);

    return () => {
      isMounted = false;
      clearInterval(intervalId);
    };
  }, [isOpen, isPaid, orderCode]);

  if (!isOpen) return null;

  const handleCopy = (text: string, fieldName: string) => {
    navigator.clipboard.writeText(text);
    setCopiedField(fieldName);
    setTimeout(() => setCopiedField(null), 2000);
  };

  return (
    <div className="fixed inset-0 z-[1000] flex items-center justify-center p-3 sm:p-4 bg-slate-900/70 backdrop-blur-xs animate-in fade-in duration-200">
      <div className="relative w-full max-w-lg bg-white rounded-3xl shadow-2xl border border-slate-200 overflow-hidden flex flex-col max-h-[92vh]">
        {/* Header */}
        <div className="bg-gradient-to-r from-emerald-700 via-teal-800 to-slate-900 p-4 sm:p-5 text-white flex items-center justify-between shrink-0">
          <div className="flex items-center gap-2.5">
            <div className="w-10 h-10 rounded-xl bg-white/10 flex items-center justify-center border border-white/20">
              <QrCode className="w-5 h-5 text-emerald-300" />
            </div>
            <div>
              <div className="flex items-center gap-1.5">
                <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-400/20 text-emerald-200 border border-emerald-300/30">
                  Napas 247 • MBBank SePay Tự Động
                </span>
              </div>
              <h2 className="text-base sm:text-lg font-black tracking-tight">
                Quét Mã VietQR Chuyển Khoản MBBank
              </h2>
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-xl bg-white/10 hover:bg-white/20 text-white/80 hover:text-white transition-colors"
            title="Đóng cửa sổ"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Scrollable Body */}
        <div className="overflow-y-auto p-4 sm:p-6 space-y-4">
          {/* PAID Banner nếu đã nhận tiền thành công */}
          {isPaid ? (
            <div className="p-4 bg-emerald-50 rounded-2xl border border-emerald-200 text-emerald-800 space-y-2 text-center animate-in zoom-in-95">
              <div className="w-12 h-12 rounded-full bg-emerald-100 text-emerald-600 flex items-center justify-center mx-auto">
                <CheckCircle2 className="w-7 h-7" />
              </div>
              <p className="font-bold text-sm">Thanh toán chuyển khoản thành công!</p>
              <p className="text-xs text-emerald-700">
                Hệ thống kế toán H4CARE đã khớp giao dịch SePay MBBank. Đơn hàng đã được xác nhận và chuyển kho xuất thuốc.
              </p>
            </div>
          ) : (
            /* QR Box */
            <div className="text-center bg-slate-50 p-4 rounded-2xl border border-slate-200/80">
              <div className="inline-block bg-white p-2.5 rounded-2xl shadow-md border border-slate-100">
                <img
                  src={vietQrUrl}
                  alt="VietQR MBBank SePay"
                  className="w-52 h-52 sm:w-56 sm:h-56 object-contain mx-auto rounded-xl"
                />
              </div>

              <div className="mt-2.5 flex items-center justify-center gap-2">
                <span className="text-xs text-slate-500 font-medium">Số tiền thanh toán:</span>
                <span className="text-lg sm:text-xl font-black text-rose-600 font-mono">
                  {amount.toLocaleString("vi-VN")} đ
                </span>
              </div>

              <p className="text-[11px] text-slate-500 mt-1">
                Mở ứng dụng ngân hàng bất kỳ (MB, Vietcombank, Techcombank, VPBank,...) để quét mã
              </p>
            </div>
          )}

          {/* Chi tiết chuyển khoản có nút 1-click copy */}
          <div className="space-y-2 text-xs">
            <div className="flex items-center justify-between text-slate-500 font-bold uppercase tracking-wider text-[10px]">
              <span>Thông tin chuyển khoản</span>
              <span className="text-emerald-700 font-normal">Chạm để sao chép</span>
            </div>

            <div className="p-3 bg-white rounded-xl border border-slate-200 space-y-2 shadow-2xs">
              {/* Ngân hàng */}
              <div className="flex items-center justify-between py-1 border-b border-slate-100">
                <span className="text-slate-500">Ngân hàng thụ hưởng:</span>
                <span className="font-bold text-slate-900">{bankName}</span>
              </div>

              {/* Số tài khoản */}
              <div className="flex items-center justify-between py-1 border-b border-slate-100">
                <span className="text-slate-500">Số tài khoản nhận:</span>
                <div className="flex items-center gap-2">
                  <span className="font-mono font-bold text-emerald-800 text-sm">{accountNumber}</span>
                  <button
                    type="button"
                    onClick={() => handleCopy(accountNumber, "accountNumber")}
                    className="p-1 rounded-md bg-slate-100 hover:bg-slate-200 text-slate-700 transition-colors"
                    title="Sao chép số tài khoản"
                  >
                    {copiedField === "accountNumber" ? (
                      <Check className="w-3.5 h-3.5 text-emerald-600" />
                    ) : (
                      <Copy className="w-3.5 h-3.5" />
                    )}
                  </button>
                </div>
              </div>

              {/* Chủ tài khoản */}
              <div className="flex items-center justify-between py-1 border-b border-slate-100">
                <span className="text-slate-500">Chủ tài khoản:</span>
                <span className="font-bold text-slate-900">{accountHolder}</span>
              </div>

              {/* Nội dung chuyển khoản */}
              <div className="flex items-center justify-between py-1.5 bg-emerald-50/80 p-2.5 rounded-lg border border-emerald-200">
                <div>
                  <span className="text-emerald-900 font-bold block text-[11px]">
                    Nội dung chuyển khoản (bắt buộc giữ nguyên):
                  </span>
                  <span className="font-mono font-black text-emerald-800 text-sm tracking-wide">
                    {transferContent}
                  </span>
                </div>
                <button
                  type="button"
                  onClick={() => handleCopy(transferContent, "transferContent")}
                  className="px-2.5 py-1 rounded-md bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-[10px] transition-colors flex items-center gap-1 shadow-2xs"
                >
                  {copiedField === "transferContent" ? (
                    <>
                      <Check className="w-3 h-3" />
                      <span>Đã chép</span>
                    </>
                  ) : (
                    <>
                      <Copy className="w-3 h-3" />
                      <span>Sao chép</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>

          {/* Trạng thái xác nhận tự động */}
          {!isPaid ? (
            <div className="p-3.5 rounded-xl bg-amber-50/90 border border-amber-200 text-xs text-amber-900 flex items-center gap-3">
              <RefreshCw className="w-5 h-5 text-amber-600 animate-spin shrink-0" />
              <div>
                <p className="font-bold text-[11px] text-amber-950">
                  Đang chờ hệ thống ngân hàng xác nhận tiền về...
                </p>
                <p className="text-[10px] text-amber-800 mt-0.5 leading-relaxed">
                  Ngay khi bạn hoàn tất chuyển khoản từ ứng dụng ngân hàng, SePay sẽ gửi thông báo và hệ thống tự động hoàn tất đơn (không cần chụp biên lai).
                </p>
              </div>
            </div>
          ) : (
            <div className="p-3 rounded-xl bg-emerald-50 border border-emerald-200 text-xs text-emerald-900 flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-emerald-600 shrink-0" />
              <span>Giao dịch an toàn đã được xác thực 100% qua SePay Webhook.</span>
            </div>
          )}
        </div>

        {/* Footer Actions */}
        <div className="p-4 bg-slate-50 border-t border-slate-200 flex flex-col sm:flex-row items-center justify-between gap-2 shrink-0">
          <a
            href={vietQrUrl}
            target="_blank"
            rel="noopener noreferrer"
            download={`VietQR_MBBank_${orderCode}.png`}
            className="w-full sm:w-auto px-4 py-2.5 rounded-xl border border-slate-200 hover:bg-slate-100 text-slate-700 font-bold text-xs flex items-center justify-center gap-1.5 transition-colors"
          >
            <Download className="w-4 h-4" />
            <span>Tải ảnh QR</span>
          </a>

          {isPaid ? (
            <button
              type="button"
              onClick={onSuccess}
              className="w-full sm:flex-1 py-2.5 px-4 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs flex items-center justify-center gap-1.5 shadow-sm transition-all cursor-pointer"
            >
              <CheckCircle2 className="w-4 h-4" />
              <span>Xem đơn hàng đã thanh toán</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          ) : (
            <button
              type="button"
              onClick={onChangeMethod || onClose}
              className="w-full sm:w-auto px-4 py-2.5 rounded-xl border border-slate-300 hover:bg-slate-100 text-slate-700 font-bold text-xs transition-colors hover:border-slate-400"
            >
              Đổi phương thức khác
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
