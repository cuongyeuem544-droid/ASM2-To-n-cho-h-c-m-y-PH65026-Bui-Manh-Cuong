"use client";

import React, { useState, useEffect } from "react";
import Image from "next/image";
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
} from "lucide-react";
import { CartItem } from "./CartItemsTable";

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
  sepayData?: any;
}

interface PendingOrderViewProps {
  order: PendingOrderData;
  onReopenPayment: () => void;
  onChangeMethodToCod: () => Promise<void>;
  onCancelOrder: () => Promise<void>;
  onPaymentSuccess: () => void;
}

export default function PendingOrderView({
  order,
  onReopenPayment,
  onChangeMethodToCod,
  onCancelOrder,
  onPaymentSuccess,
}: PendingOrderViewProps) {
  const [copiedCode, setCopiedCode] = useState(false);
  const [isChangingMethod, setIsChangingMethod] = useState(false);
  const [isCancelling, setIsCancelling] = useState(false);
  const [showCancelConfirm, setShowCancelConfirm] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [liveStatus, setLiveStatus] = useState<string>("PENDING");

  // Live polling kiểm tra trạng thái thanh toán từ backend
  useEffect(() => {
    let isMounted = true;
    const intervalId = setInterval(async () => {
      try {
        const token =
          typeof window !== "undefined"
            ? localStorage.getItem("h4care_auth_token") || localStorage.getItem("pharmatrust_token")
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
          setLiveStatus(data.payment_status || data.order_status || "PENDING");
          if (
            data.payment_status === "PAID" ||
            data.status === "PAID" ||
            data.order_status === "CONFIRMED"
          ) {
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

  const handleSwitchToCod = async () => {
    try {
      setIsChangingMethod(true);
      setErrorMessage(null);
      await onChangeMethodToCod();
    } catch (err: any) {
      setErrorMessage(err?.message || "Không thể chuyển đổi phương thức thanh toán. Vui lòng thử lại.");
    } finally {
      setIsChangingMethod(false);
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
          <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-ping" />
            Phương thức đã chọn:{" "}
            {order.paymentMethod === "SEPAY"
              ? "Chuyển khoản VietQR MBBank (SePay)"
              : order.paymentMethod === "PAYOS"
              ? "Cổng thanh toán payOS"
              : "Thanh toán khi nhận hàng (COD)"}
          </h2>

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
              <button
                type="button"
                onClick={onReopenPayment}
                className="w-full sm:w-auto px-5 py-3 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs sm:text-sm flex items-center justify-center gap-2 shadow-sm transition-all active:scale-98"
              >
                <QrCode className="w-4 h-4" />
                <span>Mở lại mã VietQR</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            )}
          </div>

          {/* Secondary Actions */}
          <div className="pt-3 border-t border-slate-100 flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-2.5">
            <button
              type="button"
              onClick={handleSwitchToCod}
              disabled={isChangingMethod}
              className="px-4 py-2.5 rounded-xl border border-brand-blue-300 bg-brand-blue-50/50 hover:bg-brand-blue-100/70 text-brand-blue-700 font-bold text-xs flex items-center justify-center gap-1.5 transition-colors disabled:opacity-50"
            >
              <Banknote className="w-4 h-4 text-brand-blue-600" />
              <span>
                {isChangingMethod ? "Đang chuyển đổi..." : "Đổi sang nhận hàng thanh toán (COD)"}
              </span>
            </button>

            <button
              type="button"
              onClick={() => setShowCancelConfirm(true)}
              disabled={isCancelling}
              className="px-4 py-2.5 rounded-xl text-slate-500 hover:text-rose-600 hover:bg-rose-50 text-xs font-semibold flex items-center justify-center gap-1.5 transition-colors"
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
            const itemImg = item.image || item.image_url;
            const itemName = item.name || item.product_name || "Thuốc";
            return (
            <div key={item.id || idx} className="p-3.5 flex items-center justify-between gap-3 bg-white">
              <div className="flex items-center gap-3">
                <div className="w-12 h-12 rounded-lg bg-slate-50 border border-slate-200 flex items-center justify-center overflow-hidden shrink-0">
                  {itemImg ? (
                    <Image
                      src={itemImg}
                      alt={itemName}
                      width={48}
                      height={48}
                      className="w-full h-full object-cover"
                      unoptimized
                    />
                  ) : (
                    <Package className="w-6 h-6 text-slate-400" />
                  )}
                </div>
                <div>
                  <h3 className="text-xs sm:text-sm font-bold text-slate-900 line-clamp-1">
                    {itemName}
                  </h3>
                  <div className="flex items-center gap-2 text-[11px] text-slate-500 mt-0.5">
                    <span>Số lượng: {item.quantity}</span>
                    <span>•</span>
                    <span>Đơn giá: {(item.price || 0).toLocaleString("vi-VN")} đ</span>
                  </div>
                </div>
              </div>

              <div className="text-right shrink-0">
                <span className="text-xs sm:text-sm font-bold text-slate-900">
                  {((item.price || 0) * (item.quantity || 1)).toLocaleString("vi-VN")} đ
                </span>
              </div>
            </div>
            );
          })}
        </div>
      </div>

      {/* Cancel Confirmation Modal */}
      {showCancelConfirm && (
        <div className="fixed inset-0 z-[1100] flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs animate-in fade-in">
          <div className="w-full max-w-md bg-white rounded-2xl p-5 sm:p-6 shadow-2xl border border-slate-200 space-y-4">
            <div className="flex items-center gap-3 text-rose-600">
              <div className="w-10 h-10 rounded-full bg-rose-100 flex items-center justify-center shrink-0">
                <AlertTriangle className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-sm sm:text-base font-bold text-slate-900">
                  Xác nhận hủy đơn hàng #{order.orderCode}
                </h3>
                <p className="text-xs text-slate-500">
                  Hành động này sẽ giải phóng tồn kho thuốc cho khách hàng khác.
                </p>
              </div>
            </div>

            <p className="text-xs text-slate-600 bg-slate-50 p-3 rounded-xl border border-slate-200 leading-relaxed">
              Bạn có chắc chắn muốn hủy đơn hàng này? Bạn có thể đổi sang phương thức <strong>COD (Thanh toán khi nhận hàng)</strong> thay vì hủy bỏ.
            </p>

            <div className="flex items-center justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setShowCancelConfirm(false)}
                disabled={isCancelling}
                className="px-4 py-2 rounded-xl border border-slate-300 text-slate-700 text-xs font-semibold hover:bg-slate-50 transition-colors"
              >
                Giữ đơn hàng
              </button>
              <button
                type="button"
                onClick={handleConfirmCancel}
                disabled={isCancelling}
                className="px-4 py-2 rounded-xl bg-rose-600 hover:bg-rose-700 text-white text-xs font-bold flex items-center gap-1.5 transition-colors shadow-xs disabled:opacity-50"
              >
                {isCancelling ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <XCircle className="w-3.5 h-3.5" />}
                <span>{isCancelling ? "Đang hủy..." : "Xác nhận hủy"}</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
