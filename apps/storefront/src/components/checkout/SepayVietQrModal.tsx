"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
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
  AlertTriangle,
  Clock,
  Loader2,
  ExternalLink,
  XCircle,
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
  expiresAt?: string;
  onClose: () => void;
  onChangeMethod?: () => void;
  onRefreshQr?: () => Promise<void>;
  onCancelOrder?: () => Promise<void>;
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
  expiresAt,
  onClose,
  onChangeMethod,
  onRefreshQr,
  onCancelOrder,
  onSuccess,
}: SepayVietQrModalProps) {
  const [copiedField, setCopiedField] = useState<string | null>(null);
  const [isPaid, setIsPaid] = useState(false);
  const [pollingCount, setPollingCount] = useState(0);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [showCancelConfirm, setShowCancelConfirm] = useState(false);
  const [isCancelling, setIsCancelling] = useState(false);
  const [cancelError, setCancelError] = useState<string | null>(null);
  const [qrImgError, setQrImgError] = useState(false);
  const [qrReloadKey, setQrReloadKey] = useState(0);

  const bankName = propBankName || "Ngân hàng TMCP Quân Đội (MBBank)";
  const accountNumber = propAccountNumber || "";
  const accountHolder = propAccountHolder || "PHARMATRUST / H4CARE";
  const transferContent = paymentCode || orderCode;

  // Real 15-Minute Expiry Countdown
  const calculateSecondsLeft = () => {
    if (!expiresAt) return 15 * 60;
    const diff = Math.floor((new Date(expiresAt).getTime() - Date.now()) / 1000);
    return Math.max(0, diff);
  };

  const [timeLeft, setTimeLeft] = useState<number>(calculateSecondsLeft);

  useEffect(() => {
    if (isOpen) {
      setTimeLeft(calculateSecondsLeft());
    }
  }, [isOpen, expiresAt]);

  useEffect(() => {
    if (!isOpen || isPaid) return;

    const timer = setInterval(() => {
      if (expiresAt) {
        const diff = Math.floor((new Date(expiresAt).getTime() - Date.now()) / 1000);
        setTimeLeft(Math.max(0, diff));
      } else {
        setTimeLeft((prev) => Math.max(0, prev - 1));
      }
    }, 1000);

    return () => clearInterval(timer);
  }, [isOpen, isPaid, expiresAt]);

  const isExpired = timeLeft <= 0;

  const formatCountdown = (seconds: number) => {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
  };

  // URL VietQR chuẩn Napas 247
  const vietQrUrl =
    propQrCodeUrl ||
    (accountNumber
      ? `https://img.vietqr.io/image/MB-${accountNumber}-compact2.png?amount=${amount}&addInfo=${encodeURIComponent(
          transferContent
        )}&accountName=${encodeURIComponent(accountHolder)}`
      : "");

  // Polling tự động kiểm tra trạng thái từ Backend
  useEffect(() => {
    if (!isOpen || isPaid || !orderCode || isExpired) return;

    let isMounted = true;
    const intervalId = setInterval(async () => {
      try {
        const token =
          typeof window !== "undefined"
            ? localStorage.getItem("pharmatrust_access_token") ||
              localStorage.getItem("h4care_auth_token") ||
              localStorage.getItem("pharmatrust_token")
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
          // CHỈ ĐÁNH DẤU LÀ ĐÃ THANH TOÁN KHI PAYMENT_STATUS == 'PAID' (KHÔNG DÙNG CONFIRMED!)
          if (data.payment_status === "PAID" || data.status === "PAID") {
            setIsPaid(true);
            clearInterval(intervalId);
          }
        }
      } catch (e) {
        // Lỗi mạng tạm thời, tiếp tục kiểm tra
      }
    }, 2500);

    return () => {
      isMounted = false;
      clearInterval(intervalId);
    };
  }, [isOpen, isPaid, orderCode, isExpired]);

  if (!isOpen) return null;

  const handleCopy = (text: string, fieldName: string) => {
    if (!text) return;
    navigator.clipboard.writeText(text);
    setCopiedField(fieldName);
    setTimeout(() => setCopiedField(null), 2000);
  };

  const handleRefresh = async () => {
    if (onRefreshQr) {
      try {
        setIsRefreshing(true);
        await onRefreshQr();
      } finally {
        setIsRefreshing(false);
      }
    } else if (onChangeMethod) {
      onChangeMethod();
    }
  };

  const handleCancelOrderAction = async () => {
    if (!onCancelOrder) return;
    try {
      setIsCancelling(true);
      setCancelError(null);
      await onCancelOrder();
      setShowCancelConfirm(false);
      onClose();
    } catch (err: any) {
      setCancelError(err?.message || "Không thể hủy đơn hàng.");
    } finally {
      setIsCancelling(false);
    }
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

          <div className="flex items-center gap-1.5">
            <Link
              href={`/checkout/payment/${encodeURIComponent(orderCode)}`}
              target="_blank"
              className="p-1.5 rounded-xl bg-white/10 hover:bg-white/20 text-white/80 hover:text-white transition-colors"
              title="Mở toàn màn hình trang thanh toán"
            >
              <ExternalLink className="w-4 h-4" />
            </Link>

            <button
              type="button"
              onClick={onClose}
              className="p-1.5 rounded-xl bg-white/10 hover:bg-white/20 text-white/80 hover:text-white transition-colors"
              title="Đóng cửa sổ"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Scrollable Body */}
        <div className="overflow-y-auto p-4 sm:p-6 space-y-4">
          {/* Live Countdown & Expiry Banners */}
          {!isPaid && (
            <div>
              {isExpired ? (
                <div className="p-3.5 rounded-2xl bg-rose-50 border-2 border-rose-300 text-rose-900 space-y-1.5">
                  <div className="flex items-center gap-2 font-bold text-xs text-rose-800">
                    <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0" />
                    <span>Mã thanh toán này đã hết hạn sau 15 phút</span>
                  </div>
                  <p className="text-[11px] text-rose-700 leading-relaxed">
                    Vui lòng <strong>không chuyển tiền</strong> vào mã này để tránh giao dịch bị giữ lại đối soát kế toán. Bạn có thể tạo mã mới ngay lập tức hoặc chọn phương thức khác.
                  </p>
                </div>
              ) : timeLeft <= 60 ? (
                <div className="p-3 rounded-2xl bg-rose-50 border border-rose-300 text-rose-900 flex items-center justify-between gap-2 animate-pulse">
                  <div className="flex items-center gap-2 text-xs font-bold text-rose-800">
                    <Clock className="w-4 h-4 text-rose-600 shrink-0" />
                    <span>Mã sắp hết hạn! Vui lòng hoàn tất trong:</span>
                  </div>
                  <span className="font-mono font-black text-rose-700 text-sm bg-rose-100 px-2 py-0.5 rounded-lg border border-rose-300">
                    {formatCountdown(timeLeft)}
                  </span>
                </div>
              ) : timeLeft <= 300 ? (
                <div className="p-2.5 rounded-2xl bg-amber-50 border border-amber-200 text-amber-900 flex items-center justify-between gap-2">
                  <div className="flex items-center gap-1.5 text-[11px] font-semibold text-amber-800">
                    <Clock className="w-3.5 h-3.5 text-amber-600 shrink-0" />
                    <span>Thời gian quét mã còn lại:</span>
                  </div>
                  <span className="font-mono font-bold text-amber-800 text-xs bg-amber-100 px-2 py-0.5 rounded-md border border-amber-300">
                    {formatCountdown(timeLeft)}
                  </span>
                </div>
              ) : (
                <div className="flex items-center justify-between text-[11px] text-slate-500 bg-slate-50 px-3 py-1.5 rounded-xl border border-slate-200">
                  <span className="flex items-center gap-1.5">
                    <Clock className="w-3.5 h-3.5 text-slate-400" />
                    <span>Mã có hiệu lực trong 15 phút:</span>
                  </span>
                  <span className="font-mono font-bold text-slate-700">
                    {formatCountdown(timeLeft)}
                  </span>
                </div>
              )}
            </div>
          )}

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
            <div className="text-center bg-slate-50 p-4 rounded-2xl border border-slate-200/80 relative">
              <div className="relative inline-block bg-white p-2.5 rounded-2xl shadow-md border border-slate-100 overflow-hidden">
                {qrImgError ? (
                  <div className="w-52 h-52 sm:w-56 sm:h-56 flex flex-col items-center justify-center p-3 text-center bg-slate-100 rounded-xl text-slate-700">
                    <AlertTriangle className="w-7 h-7 text-amber-500 mb-2" />
                    <span className="text-xs font-bold text-slate-800">Không tải được ảnh VietQR</span>
                    <span className="text-[10px] text-slate-500 mt-1 max-w-[170px] leading-relaxed">
                      Bạn có thể chuyển khoản bằng thông tin số tài khoản bên dưới
                    </span>
                    <button
                      type="button"
                      onClick={() => {
                        setQrImgError(false);
                        setQrReloadKey((k) => k + 1);
                      }}
                      className="mt-2.5 px-3 py-1 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-[11px] flex items-center gap-1.5 transition-all cursor-pointer"
                    >
                      <RefreshCw className="w-3 h-3" />
                      <span>Thử tải lại ảnh QR</span>
                    </button>
                  </div>
                ) : (
                  <img
                    key={qrReloadKey}
                    src={vietQrUrl}
                    alt="VietQR MBBank SePay"
                    onError={() => setQrImgError(true)}
                    className={`w-52 h-52 sm:w-56 sm:h-56 object-contain mx-auto rounded-xl transition-all ${
                      isExpired ? "opacity-20 blur-xs grayscale" : ""
                    }`}
                  />
                )}

                {/* Expired Overlay */}
                {isExpired && (
                  <div className="absolute inset-0 bg-slate-900/60 backdrop-blur-2xs flex flex-col items-center justify-center p-4 text-white text-center">
                    <AlertTriangle className="w-10 h-10 text-rose-400 mb-2 animate-bounce" />
                    <p className="font-black text-xs uppercase tracking-wider text-rose-300">
                      Mã Đã Hết Hạn
                    </p>
                    <p className="text-[10px] text-slate-200 mt-1 max-w-[180px] leading-relaxed">
                      Nhấn nút bên dưới để tạo mã thanh toán mới 15 phút.
                    </p>
                    <button
                      type="button"
                      onClick={handleRefresh}
                      disabled={isRefreshing}
                      className="mt-3 px-3 py-1.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-[11px] flex items-center gap-1.5 shadow-md active:scale-95 transition-all cursor-pointer"
                    >
                      {isRefreshing ? (
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      ) : (
                        <RefreshCw className="w-3.5 h-3.5" />
                      )}
                      <span>Tạo mã QR mới</span>
                    </button>
                  </div>
                )}
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
                  <span className="font-mono font-bold text-emerald-800 text-sm">
                    {accountNumber || "Đang tải số tài khoản..."}
                  </span>
                  {accountNumber && (
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
                  )}
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
                  {isExpired
                    ? "Mã đã quá hạn 15 phút. Vui lòng tạo mã mới để tiếp tục."
                    : "Đang chờ hệ thống ngân hàng xác nhận tiền về..."}
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
          <div className="flex items-center gap-2 w-full sm:w-auto">
            {!isExpired && vietQrUrl && (
              <a
                href={vietQrUrl}
                target="_blank"
                rel="noopener noreferrer"
                download={`VietQR_MBBank_${orderCode}.png`}
                className="w-full sm:w-auto px-3.5 py-2.5 rounded-xl border border-slate-200 hover:bg-slate-100 text-slate-700 font-bold text-xs flex items-center justify-center gap-1.5 transition-colors"
              >
                <Download className="w-4 h-4" />
                <span>Tải QR</span>
              </a>
            )}

            {!isPaid && onCancelOrder && (
              <button
                type="button"
                onClick={() => setShowCancelConfirm(true)}
                className="w-full sm:w-auto px-3 py-2.5 rounded-xl text-slate-500 hover:text-rose-600 hover:bg-rose-50 text-xs font-semibold flex items-center justify-center gap-1 transition-colors cursor-pointer"
              >
                <XCircle className="w-3.5 h-3.5" />
                <span>Hủy đơn</span>
              </button>
            )}
          </div>

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
            <div className="w-full sm:w-auto flex items-center gap-2 flex-1 justify-end">
              {isExpired && (
                <button
                  type="button"
                  onClick={handleRefresh}
                  disabled={isRefreshing}
                  className="w-full sm:w-auto px-4 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs flex items-center justify-center gap-1.5 transition-colors shadow-xs"
                >
                  {isRefreshing ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <RefreshCw className="w-4 h-4" />
                  )}
                  <span>Tạo mã thanh toán mới</span>
                </button>
              )}
              <button
                type="button"
                onClick={onChangeMethod || onClose}
                className="w-full sm:w-auto px-4 py-2.5 rounded-xl border border-slate-300 hover:bg-slate-100 text-slate-700 font-bold text-xs transition-colors hover:border-slate-400 cursor-pointer"
              >
                Đổi phương thức khác
              </button>
            </div>
          )}
        </div>

        {/* Cancel Confirmation Dialog */}
        {showCancelConfirm && (
          <div className="absolute inset-0 z-50 bg-slate-900/80 backdrop-blur-xs flex items-center justify-center p-4 animate-in fade-in duration-150">
            <div className="bg-white rounded-2xl max-w-sm w-full p-5 shadow-2xl border border-slate-200 space-y-4">
              <div className="w-11 h-11 rounded-full bg-rose-100 text-rose-600 flex items-center justify-center mx-auto">
                <AlertTriangle className="w-6 h-6" />
              </div>

              <div className="text-center space-y-1">
                <h3 className="text-base font-black text-slate-900">Xác nhận hủy đơn hàng</h3>
                <p className="text-xs text-slate-600 leading-relaxed">
                  Bạn có chắc chắn muốn hủy đơn hàng <strong>#{orderCode}</strong> không? Các mặt hàng thuốc giữ chỗ tại kho sẽ được giải phóng ngay lập tức cho khách hàng khác.
                </p>
              </div>

              {cancelError && (
                <p className="text-xs text-rose-600 font-medium text-center bg-rose-50 p-2 rounded-lg border border-rose-200">
                  {cancelError}
                </p>
              )}

              <div className="flex items-center gap-2 pt-1">
                <button
                  type="button"
                  onClick={() => {
                    setShowCancelConfirm(false);
                    setCancelError(null);
                  }}
                  disabled={isCancelling}
                  className="flex-1 py-2 px-3 rounded-xl border border-slate-200 text-slate-700 font-bold text-xs hover:bg-slate-50 transition-colors"
                >
                  Không, quay lại
                </button>
                <button
                  type="button"
                  onClick={handleCancelOrderAction}
                  disabled={isCancelling}
                  className="flex-1 py-2 px-3 rounded-xl bg-rose-600 hover:bg-rose-700 text-white font-bold text-xs flex items-center justify-center gap-1.5 transition-colors cursor-pointer"
                >
                  {isCancelling ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      <span>Đang hủy...</span>
                    </>
                  ) : (
                    <span>Xác nhận hủy</span>
                  )}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
