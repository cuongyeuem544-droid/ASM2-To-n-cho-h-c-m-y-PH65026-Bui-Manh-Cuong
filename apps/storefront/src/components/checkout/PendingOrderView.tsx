"use client";

import React, { useState, useEffect } from "react";
import Image from "next/image";
import Link from "next/link";
import {
  Clock,
  QrCode,
  Banknote,
  AlertTriangle,
  XCircle,
  Copy,
  Check,
  Package,
  MapPin,
  Phone,
  User,
  ShieldCheck,
  RefreshCw,
  ArrowRight,
  CreditCard,
  Loader2,
} from "lucide-react";

export interface PendingOrderData {
  orderCode: string;
  orderToken?: string;
  customerName: string;
  customerPhone: string;
  shippingAddress: string;
  totalAmount: number;
  paymentMethod: "COD" | "PAYOS" | "SEPAY";
  items: any[];
  shippingFee?: number;
  discountAmount?: number;
  createdAt?: string;
  expiresAt?: string;
  sepayData?: any;
}

interface PendingOrderViewProps {
  order: PendingOrderData;
  onReopenPayment: () => void;
  onChangePaymentMethod: () => void;
  onRefreshPaymentCode?: () => Promise<void>;
  onCancelOrder: () => Promise<void>;
  onPaymentSuccess: () => void;
}

export default function PendingOrderView({
  order,
  onReopenPayment,
  onChangePaymentMethod,
  onRefreshPaymentCode,
  onCancelOrder,
  onPaymentSuccess,
}: PendingOrderViewProps) {
  const [copiedCode, setCopiedCode] = useState(false);
  const [isRefreshingCode, setIsRefreshingCode] = useState(false);
  const [isCancelling, setIsCancelling] = useState(false);
  const [showCancelConfirm, setShowCancelConfirm] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [liveStatus, setLiveStatus] = useState<string>("PENDING");

  // Calculate remaining seconds for 15-minute payment expiry
  const effectiveExpiresAt = order.expiresAt || order.sepayData?.expiresAt;
  const calculateSecondsLeft = () => {
    if (!effectiveExpiresAt) return 15 * 60;
    const diff = Math.floor((new Date(effectiveExpiresAt).getTime() - Date.now()) / 1000);
    return Math.max(0, diff);
  };

  const [timeLeft, setTimeLeft] = useState<number>(calculateSecondsLeft);

  useEffect(() => {
    setTimeLeft(calculateSecondsLeft());
  }, [effectiveExpiresAt]);

  useEffect(() => {
    if (order.paymentMethod === "COD") return;

    const timer = setInterval(() => {
      if (effectiveExpiresAt) {
        const diff = Math.floor((new Date(effectiveExpiresAt).getTime() - Date.now()) / 1000);
        setTimeLeft(Math.max(0, diff));
      } else {
        setTimeLeft((prev) => Math.max(0, prev - 1));
      }
    }, 1000);

    return () => clearInterval(timer);
  }, [order.paymentMethod, effectiveExpiresAt]);

  const isExpired = order.paymentMethod !== "COD" && timeLeft <= 0;

  const formatCountdown = (seconds: number) => {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
  };

  // Live polling kiểm tra trạng thái thanh toán từ backend
  useEffect(() => {
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
          order.orderToken ||
          (typeof window !== "undefined"
            ? localStorage.getItem(`h4care_order_token_${order.orderCode}`) ||
              localStorage.getItem("h4care_latest_order_token") ||
              ""
            : "");

        const headers: Record<string, string> = {};
        if (token) headers["Authorization"] = `Bearer ${token}`;
        if (orderToken) headers["X-Order-Token"] = orderToken;

        const res = await fetch(`/api/v1/payments/orders/${encodeURIComponent(order.orderCode)}/status`, {
          headers,
        });

        if (res.ok && isMounted) {
          const data = await res.json();
          setLiveStatus(data.payment_status || "PENDING");
          // CHỈ COI LÀ THÀNH CÔNG KHI PAYMENT_STATUS == 'PAID' (KHÔNG DÙNG CONFIRMED!)
          if (data.payment_status === "PAID" || data.status === "PAID") {
            onPaymentSuccess();
          }
        }
      } catch (err) {
        // Polling im lặng
      }
    }, 3500);

    return () => {
      isMounted = false;
      clearInterval(intervalId);
    };
  }, [order.orderCode, order.orderToken, onPaymentSuccess]);

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedCode(true);
    setTimeout(() => setCopiedCode(false), 2000);
  };

  const handleRefreshCode = async () => {
    if (!onRefreshPaymentCode) {
      onChangePaymentMethod();
      return;
    }
    try {
      setIsRefreshingCode(true);
      setErrorMessage(null);
      await onRefreshPaymentCode();
    } catch (err: any) {
      setErrorMessage(err?.message || "Không thể tạo mã mới. Vui lòng thử lại.");
    } finally {
      setIsRefreshingCode(false);
    }
  };

  const handleConfirmCancel = async () => {
    try {
      setIsCancelling(true);
      setErrorMessage(null);
      await onCancelOrder();
    } catch (err: any) {
      setErrorMessage(err?.message || "Không thể hủy đơn hàng. Vui lòng thử lại.");
      setIsCancelling(false);
      setShowCancelConfirm(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6 animate-in fade-in duration-300">
      {/* Alert Header Banner */}
      <div className="p-4 sm:p-5 rounded-2xl bg-amber-50 border-2 border-amber-300 text-amber-900 shadow-xs flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div className="flex items-start gap-3">
          <div className="w-10 h-10 rounded-xl bg-amber-200/80 flex items-center justify-center shrink-0 text-amber-800">
            <Clock className="w-5 h-5 animate-pulse" />
          </div>
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-xs font-bold uppercase tracking-wider text-amber-700 bg-amber-200/60 px-2 py-0.5 rounded-full">
                Đơn hàng đang chờ thanh toán
              </span>
              <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-emerald-800 bg-emerald-100 px-2 py-0.5 rounded-full">
                <ShieldCheck className="w-3 h-3 text-emerald-600" />
                Đã giữ hàng trong kho
              </span>
            </div>
            <h1 className="text-base sm:text-lg font-black text-slate-900 mt-1">
              Đơn hàng #{order.orderCode}
            </h1>
            <p className="text-xs text-amber-800/90 mt-0.5">
              Hệ thống đã ghi nhận đơn và đang chờ xác nhận thanh toán trực tuyến từ bạn.
            </p>
          </div>
        </div>

        {/* Copy Order Code */}
        <button
          type="button"
          onClick={() => handleCopy(order.orderCode)}
          className="px-3 py-1.5 rounded-lg bg-white border border-amber-300 text-amber-900 text-xs font-bold flex items-center gap-1.5 hover:bg-amber-100/50 transition-colors shrink-0"
        >
          {copiedCode ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
          <span>{copiedCode ? "Đã sao chép mã" : "Sao chép mã đơn"}</span>
        </button>
      </div>

      {errorMessage && (
        <div className="p-3.5 rounded-xl bg-rose-50 border border-rose-200 text-xs text-rose-800 flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0" />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* Main Action Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Primary Action Card */}
        <div className="md:col-span-2 p-5 rounded-2xl bg-white border border-slate-200 shadow-xs space-y-4">
          <div className="flex items-center justify-between gap-2 flex-wrap">
            <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-ping" />
              Phương thức đã chọn:{" "}
              {order.paymentMethod === "SEPAY"
                ? "Chuyển khoản VietQR MBBank (SePay)"
                : order.paymentMethod === "PAYOS"
                ? "Cổng thanh toán payOS"
                : "Thanh toán khi nhận hàng (COD)"}
            </h2>

            {/* Live Countdown Badge */}
            {order.paymentMethod !== "COD" && (
              <div
                className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-mono font-bold border ${
                  isExpired
                    ? "bg-rose-50 text-rose-700 border-rose-300"
                    : timeLeft <= 60
                    ? "bg-rose-50 text-rose-700 border-rose-300 animate-pulse"
                    : timeLeft <= 300
                    ? "bg-amber-50 text-amber-800 border-amber-300"
                    : "bg-slate-100 text-slate-700 border-slate-200"
                }`}
              >
                <Clock className="w-3.5 h-3.5" />
                <span>
                  {isExpired ? "Hết hạn thanh toán" : `Còn lại: ${formatCountdown(timeLeft)}`}
                </span>
              </div>
            )}
          </div>

          {/* Expired Warning Notice */}
          {isExpired && (
            <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs space-y-1">
              <div className="flex items-center gap-1.5 font-bold">
                <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0" />
                <span>Mã thanh toán 15 phút đã hết hạn</span>
              </div>
              <p className="text-[11px] text-rose-700 leading-relaxed">
                Đơn hàng và tồn kho vẫn được bảo lưu trong thời gian gia hạn 30 phút. Vui lòng bấm &quot;Tạo mã thanh toán mới&quot; hoặc &quot;Đổi phương thức thanh toán&quot; để tiếp tục hoàn tất.
              </p>
            </div>
          )}

          <div className="p-4 rounded-xl bg-emerald-50/70 border border-emerald-200 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
            <div>
              <span className="text-[11px] text-emerald-800 font-semibold">Tổng tiền thanh toán:</span>
              <p className="text-xl sm:text-2xl font-black text-emerald-700">
                {(order.totalAmount || 0).toLocaleString("vi-VN")} đ
              </p>
              <p className="text-[11px] text-slate-500 mt-0.5">
                Chuyển khoản chính xác số tiền này để hệ thống tự động hoàn tất đơn 24/7.
              </p>
            </div>

            {order.paymentMethod === "SEPAY" && (
              <div className="flex items-center gap-2 w-full sm:w-auto">
                {isExpired ? (
                  <button
                    type="button"
                    onClick={handleRefreshCode}
                    disabled={isRefreshingCode}
                    className="w-full sm:w-auto px-5 py-3 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs sm:text-sm flex items-center justify-center gap-2 shadow-sm transition-all cursor-pointer"
                  >
                    {isRefreshingCode ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <RefreshCw className="w-4 h-4" />
                    )}
                    <span>Tạo mã thanh toán mới</span>
                  </button>
                ) : (
                  <div className="flex flex-col sm:flex-row items-center gap-2">
                    <button
                      type="button"
                      onClick={onReopenPayment}
                      className="w-full sm:w-auto px-5 py-3 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs sm:text-sm flex items-center justify-center gap-2 shadow-sm transition-all active:scale-98 cursor-pointer"
                    >
                      <QrCode className="w-4 h-4" />
                      <span>Mở lại mã VietQR</span>
                      <ArrowRight className="w-3.5 h-3.5" />
                    </button>

                    <Link
                      href={`/checkout/payment/${encodeURIComponent(order.orderCode)}`}
                      className="w-full sm:w-auto px-4 py-3 rounded-xl border border-slate-200 hover:bg-slate-100 text-slate-700 font-bold text-xs flex items-center justify-center gap-1.5 transition-colors"
                    >
                      <span>Trang thanh toán riêng</span>
                    </Link>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Secondary Actions */}
          <div className="pt-3 border-t border-slate-100 flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-2.5">
            <button
              type="button"
              onClick={onChangePaymentMethod}
              className="px-4 py-2.5 rounded-xl border border-brand-blue-300 bg-brand-blue-50/50 hover:bg-brand-blue-100/70 text-brand-blue-700 font-bold text-xs flex items-center justify-center gap-1.5 transition-colors cursor-pointer"
            >
              <CreditCard className="w-4 h-4 text-brand-blue-600" />
              <span>Đổi phương thức thanh toán</span>
            </button>

            <button
              type="button"
              onClick={() => setShowCancelConfirm(true)}
              disabled={isCancelling}
              className="px-4 py-2.5 rounded-xl text-slate-500 hover:text-rose-600 hover:bg-rose-50 text-xs font-semibold flex items-center justify-center gap-1.5 transition-colors cursor-pointer"
            >
              <XCircle className="w-4 h-4" />
              <span>Hủy đơn hàng</span>
            </button>
          </div>
        </div>

        {/* Shipping Info Card */}
        <div className="p-5 rounded-2xl bg-white border border-slate-200 shadow-xs space-y-3">
          <h2 className="text-sm font-bold text-slate-900 flex items-center gap-1.5">
            <Package className="w-4 h-4 text-brand-blue-600" />
            <span>Thông tin giao hàng</span>
          </h2>

          <div className="space-y-2 text-xs text-slate-600">
            <div className="flex items-center gap-2">
              <User className="w-3.5 h-3.5 text-slate-400 shrink-0" />
              <span className="font-semibold text-slate-900">{order.customerName}</span>
            </div>
            <div className="flex items-center gap-2">
              <Phone className="w-3.5 h-3.5 text-slate-400 shrink-0" />
              <span>{order.customerPhone}</span>
            </div>
            <div className="flex items-start gap-2 pt-1 border-t border-slate-100">
              <MapPin className="w-3.5 h-3.5 text-slate-400 shrink-0 mt-0.5" />
              <span className="leading-relaxed">{order.shippingAddress}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Product List Breakdown */}
      <div className="p-5 rounded-2xl bg-white border border-slate-200 shadow-xs space-y-4">
        <h2 className="text-sm font-bold text-slate-900 flex items-center justify-between">
          <span>Sản phẩm trong đơn ({order.items?.length || 0})</span>
          <span className="text-xs font-normal text-slate-500">
            Giữ nguyên giá và số lượng đã đặt
          </span>
        </h2>

        <div className="divide-y divide-slate-100 border border-slate-100 rounded-xl overflow-hidden">
          {order.items?.map((item: any, idx: number) => {
            const price = item.salePrice || item.price || 0;
            const subtotal = price * item.quantity;
            return (
              <div key={item.id || idx} className="p-3.5 flex items-center justify-between gap-3 bg-white">
                <div className="flex items-center gap-3">
                  <div className="relative w-12 h-12 rounded-lg bg-slate-50 border border-slate-200 overflow-hidden shrink-0">
                    {item.image ? (
                      <Image
                        src={item.image}
                        alt={item.name}
                        fill
                        className="object-cover"
                        sizes="48px"
                      />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center text-slate-400">
                        <Package className="w-5 h-5" />
                      </div>
                    )}
                  </div>
                  <div>
                    <h3 className="font-bold text-xs text-slate-900 line-clamp-1">{item.name}</h3>
                    <p className="text-[11px] text-slate-500">
                      {item.unit || item.packaging} • SL: <span className="font-bold text-slate-800">{item.quantity}</span>
                    </p>
                  </div>
                </div>

                <div className="text-right">
                  <span className="font-bold text-xs text-slate-900">
                    {subtotal.toLocaleString("vi-VN")} đ
                  </span>
                  <p className="text-[10px] text-slate-500">
                    {price.toLocaleString("vi-VN")} đ / {item.unit || item.packaging}
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Cancel Order Confirmation Modal */}
      {showCancelConfirm && (
        <div className="fixed inset-0 z-[1200] flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-2xs animate-in fade-in">
          <div className="bg-white rounded-2xl max-w-sm w-full p-5 shadow-2xl border border-slate-200 space-y-4">
            <div className="w-11 h-11 rounded-full bg-rose-100 text-rose-600 flex items-center justify-center mx-auto">
              <AlertTriangle className="w-6 h-6" />
            </div>

            <div className="text-center space-y-1">
              <h3 className="text-base font-black text-slate-900">Xác nhận hủy đơn hàng</h3>
              <p className="text-xs text-slate-600">
                Toàn bộ sản phẩm sẽ được hoàn về giỏ hàng để bạn có thể tiếp tục mua sắm mà không bị mất lựa chọn. Tồn kho giữ chỗ sẽ được giải phóng cho khách hàng khác.
              </p>
            </div>

            <div className="flex items-center gap-2 pt-2">
              <button
                type="button"
                onClick={() => setShowCancelConfirm(false)}
                disabled={isCancelling}
                className="flex-1 py-2 px-3 rounded-xl border border-slate-200 text-slate-700 font-bold text-xs hover:bg-slate-50 transition-colors"
              >
                Quay lại
              </button>
              <button
                type="button"
                onClick={handleConfirmCancel}
                disabled={isCancelling}
                className="flex-1 py-2 px-3 rounded-xl bg-rose-600 hover:bg-rose-700 text-white font-bold text-xs flex items-center justify-center gap-1.5 transition-colors cursor-pointer"
              >
                {isCancelling ? (
                  <>
                    <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                    <span>Đang hủy...</span>
                  </>
                ) : (
                  <span>Đồng ý hủy</span>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
