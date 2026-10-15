"use client";

import React, { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Header } from "@/components/layout/Header";
import { Footer } from "@/components/layout/Footer";
import {
  CheckCircle2,
  XCircle,
  Clock,
  ArrowRight,
  ShoppingBag,
  RotateCcw,
  ShieldCheck,
  FileText,
  CreditCard,
  Banknote,
  QrCode,
  RefreshCw,
} from "lucide-react";

interface PaymentStatusResponse {
  order_code: string;
  order_status: string;
  payment_status: string;
  payment_method: string;
  total_amount: number;
  customer_name: string;
  created_at: string;
  can_retry?: boolean;
  transactions?: Array<{
    id: number;
    transaction_code: string;
    provider: string;
    amount: number;
    status: string;
    provider_trans_id?: string;
  }>;
}

function CheckoutResultContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const orderId = searchParams.get("orderId") || searchParams.get("order_code") || "";
  const resultCode = searchParams.get("resultCode");
  const message = searchParams.get("message") || "";
  const transId = searchParams.get("transId") || "";
  const amountStr = searchParams.get("amount") || "";

  // Extract clean order_code if orderId has format "ORDERCODE_momo_..."
  const cleanOrderCode = orderId.includes("_momo_")
    ? orderId.split("_momo_")[0]
    : orderId;

  const [isLoading, setIsLoading] = useState(true);
  const [orderData, setOrderData] = useState<PaymentStatusResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isRetrying, setIsRetrying] = useState(false);
  const [retryMessage, setRetryMessage] = useState<string | null>(null);

  const isSuccess = resultCode === "0" || orderData?.payment_status === "PAID";

  useEffect(() => {
    if (!cleanOrderCode) {
      setIsLoading(false);
      return;
    }

    async function fetchStatus() {
      try {
        const phone = searchParams.get("phone") || (typeof window !== "undefined" ? localStorage.getItem("h4care_checkout_phone") || "" : "");
        const token = typeof window !== "undefined" ? localStorage.getItem("h4care_auth_token") || localStorage.getItem("pharmatrust_token") : null;
        const orderToken = searchParams.get("token") || (typeof window !== "undefined" ? localStorage.getItem(`h4care_order_token_${cleanOrderCode}`) || localStorage.getItem("h4care_latest_order_token") || "" : "");

        const headers: Record<string, string> = {};
        if (token) headers["Authorization"] = `Bearer ${token}`;
        if (orderToken) headers["X-Order-Token"] = orderToken;

        const queryParts = [];
        if (phone) queryParts.push(`phone_verify=${encodeURIComponent(phone)}`);
        if (orderToken) queryParts.push(`token=${encodeURIComponent(orderToken)}`);
        const queryParam = queryParts.length ? `?${queryParts.join("&")}` : "";

        const res = await fetch(`/api/v1/payments/orders/${cleanOrderCode}/status${queryParam}`, { headers });
        if (res.ok) {
          const data = await res.json();
          setOrderData(data);
        } else {
          setError("Không thể tra cứu thông tin thanh toán từ hệ thống.");
        }
      } catch (err: any) {
        setError(err.message || "Lỗi kết nối");
      } finally {
        setIsLoading(false);
      }
    }

    fetchStatus();
  }, [cleanOrderCode, searchParams]);

  // Switch to COD with 1-click retry
  const handleSwitchToCod = async () => {
    if (!cleanOrderCode) return;
    setIsRetrying(true);
    setRetryMessage(null);
    try {
      const phone = searchParams.get("phone") || (typeof window !== "undefined" ? localStorage.getItem("h4care_checkout_phone") || "" : "");
      const token = typeof window !== "undefined" ? localStorage.getItem("h4care_auth_token") || localStorage.getItem("pharmatrust_token") : null;
      const orderToken = searchParams.get("token") || (typeof window !== "undefined" ? localStorage.getItem(`h4care_order_token_${cleanOrderCode}`) || localStorage.getItem("h4care_latest_order_token") || "" : "");

      const headers: Record<string, string> = { "Content-Type": "application/json" };
      if (token) headers["Authorization"] = `Bearer ${token}`;
      if (orderToken) headers["X-Order-Token"] = orderToken;

      const res = await fetch("/api/v1/payments/retry", {
        method: "POST",
        headers,
        body: JSON.stringify({
          order_code: cleanOrderCode,
          new_payment_method: "COD",
          phone_verify: phone || undefined,
          order_token: orderToken || undefined,
        }),
      });
      if (res.ok) {
        setRetryMessage("Đã chuyển thành công sang Thanh toán khi nhận hàng (COD)!");
        // Refresh status
        const queryParts = [];
        if (phone) queryParts.push(`phone_verify=${encodeURIComponent(phone)}`);
        if (orderToken) queryParts.push(`token=${encodeURIComponent(orderToken)}`);
        const queryParam = queryParts.length ? `?${queryParts.join("&")}` : "";
        const statusRes = await fetch(`/api/v1/payments/orders/${cleanOrderCode}/status${queryParam}`, { headers });
        if (statusRes.ok) {
          const fresh = await statusRes.json();
          setOrderData(fresh);
        }
      } else {
        const err = await res.json();
        alert(err.detail || "Không thể chuyển phương thức thanh toán");
      }
    } catch (e: any) {
      alert("Lỗi khi xử lý: " + (e.message || "Unknown"));
    } finally {
      setIsRetrying(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto px-4 sm:px-6 py-12">
      {isLoading ? (
        <div className="bg-white rounded-3xl p-12 border border-slate-200 text-center shadow-xs">
          <div className="w-12 h-12 border-4 border-brand-blue-200 border-t-brand-blue-600 rounded-full animate-spin mx-auto mb-4" />
          <p className="text-sm font-semibold text-slate-700">Đang đối soát kết quả giao dịch thanh toán...</p>
        </div>
      ) : isSuccess ? (
        <div className="bg-white rounded-3xl p-8 sm:p-12 border border-slate-200 shadow-xs text-center">
          <div className="w-20 h-20 rounded-full bg-emerald-50 text-emerald-600 flex items-center justify-center mx-auto mb-6 ring-8 ring-emerald-50/50">
            <CheckCircle2 className="w-10 h-10" />
          </div>

          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-50 text-emerald-700 text-xs font-bold border border-emerald-200 mb-3">
            <ShieldCheck className="w-3.5 h-3.5" />
            Thanh toán thành công & Đã xác nhận
          </span>

          <h1 className="text-2xl sm:text-3xl font-black text-slate-900 tracking-tight">
            Giao dịch thanh toán được xác nhận!
          </h1>

          <p className="text-sm text-slate-600 mt-2 max-w-md mx-auto">
            Hệ thống nhà thuốc H4CARE đã nhận đủ số tiền thanh toán. Đơn thuốc của quý khách đã chuyển sang trạng thái sẵn sàng xuất kho theo tiêu chuẩn FEFO.
          </p>

          {/* Details Card */}
          <div className="mt-8 p-6 bg-slate-50 rounded-2xl border border-slate-200/80 text-left space-y-3.5">
            <div className="flex items-center justify-between pb-3 border-b border-slate-200 text-sm">
              <span className="text-slate-500">Mã đơn hàng:</span>
              <span className="font-mono font-bold text-brand-blue-700 text-base">
                {orderData?.order_code || cleanOrderCode}
              </span>
            </div>

            <div className="flex items-center justify-between text-sm">
              <span className="text-slate-500">Phương thức thanh toán:</span>
              <span className="inline-flex items-center gap-1.5 font-bold text-slate-800 bg-white px-2.5 py-0.5 rounded-full border border-slate-200 text-xs">
                {orderData?.payment_method === "MOMO"
                  ? "Ví điện tử MoMo"
                  : orderData?.payment_method === "BANK_TRANSFER" || orderData?.payment_method === "VIETQR"
                  ? "Chuyển khoản VietQR Napas 247"
                  : "Thanh toán khi nhận hàng (COD)"}
              </span>
            </div>

            {(transId || orderData?.transactions?.[0]?.provider_trans_id) && (
              <div className="flex items-center justify-between text-sm">
                <span className="text-slate-500">Mã giao dịch đối soát:</span>
                <span className="font-mono text-xs text-slate-800 font-semibold">
                  {transId || orderData?.transactions?.[0]?.provider_trans_id}
                </span>
              </div>
            )}

            <div className="flex items-center justify-between text-sm">
              <span className="text-slate-500">Trạng thái thanh toán:</span>
              <span className="inline-flex items-center gap-1 font-bold text-emerald-700 text-xs">
                <CheckCircle2 className="w-3.5 h-3.5" />
                ĐÃ THANH TOÁN (PAID)
              </span>
            </div>

            <div className="flex items-center justify-between pt-3 border-t border-slate-200 text-base">
              <span className="font-bold text-slate-900">Số tiền quyết toán:</span>
              <span className="font-black text-rose-600 text-lg">
                {(orderData?.total_amount || (amountStr ? Number(amountStr) : 0)).toLocaleString("vi-VN")} đ
              </span>
            </div>
          </div>

          <div className="mt-8 flex flex-col sm:flex-row items-center justify-center gap-3">
            <Link
              href={`/account?order=${encodeURIComponent(cleanOrderCode)}`}
              className="w-full sm:w-auto px-6 py-3 rounded-xl bg-brand-blue-600 hover:bg-brand-blue-700 text-white font-bold text-sm shadow-xs transition-all flex items-center justify-center gap-2 cursor-pointer"
            >
              <span>Xem tiến độ đơn thuốc</span>
              <ArrowRight className="w-4 h-4" />
            </Link>

            <Link
              href="/products"
              className="w-full sm:w-auto px-6 py-3 rounded-xl border border-slate-200 hover:bg-slate-50 text-slate-700 font-bold text-sm transition-all flex items-center justify-center gap-2 cursor-pointer"
            >
              <ShoppingBag className="w-4 h-4" />
              <span>Tiếp tục mua sắm</span>
            </Link>
          </div>
        </div>
      ) : (
        /* FAILED OR PENDING SCREEN */
        <div className="bg-white rounded-3xl p-8 sm:p-12 border border-slate-200 shadow-xs text-center">
          <div className="w-20 h-20 rounded-full bg-amber-50 text-amber-600 flex items-center justify-center mx-auto mb-6 ring-8 ring-amber-50/50">
            <Clock className="w-10 h-10" />
          </div>

          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-amber-50 text-amber-800 text-xs font-bold border border-amber-200 mb-3">
            Chờ thanh toán / Chưa quyết toán
          </span>

          <h1 className="text-2xl sm:text-3xl font-black text-slate-900 tracking-tight">
            Giao dịch đang chờ xác nhận
          </h1>

          <p className="text-sm text-slate-600 mt-2 max-w-md mx-auto">
            {message || "Giao dịch trực tuyến chưa ghi nhận hoàn tất. Thuốc trong đơn của quý khách vẫn đang được giữ chỗ trong kho."}
          </p>

          {retryMessage && (
            <div className="mt-4 p-3 bg-emerald-50 text-emerald-800 rounded-xl border border-emerald-200 text-xs font-bold flex items-center justify-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-600" />
              <span>{retryMessage}</span>
            </div>
          )}

          <div className="mt-8 p-6 bg-slate-50 rounded-2xl border border-slate-200/80 text-left space-y-3 text-sm">
            <div className="flex justify-between">
              <span className="text-slate-500">Mã đơn hàng:</span>
              <span className="font-mono font-bold text-slate-800">{cleanOrderCode || "N/A"}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Phương thức đã chọn:</span>
              <span className="font-semibold text-slate-800">
                {orderData?.payment_method || "Trực tuyến"}
              </span>
            </div>
            {orderData?.total_amount && (
              <div className="flex justify-between pt-2 border-t border-slate-200">
                <span className="text-slate-500">Tổng tiền cần thanh toán:</span>
                <span className="font-black text-rose-600">{orderData.total_amount.toLocaleString("vi-VN")} đ</span>
              </div>
            )}
          </div>

          {/* Action buttons including 1-click switch to COD */}
          <div className="mt-8 flex flex-col sm:flex-row items-center justify-center gap-3">
            <button
              type="button"
              disabled={isRetrying}
              onClick={handleSwitchToCod}
              className="w-full sm:w-auto px-5 py-3 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs shadow-xs transition-all flex items-center justify-center gap-2 cursor-pointer"
            >
              {isRetrying ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" />
                  <span>Đang cập nhật...</span>
                </>
              ) : (
                <>
                  <Banknote className="w-4 h-4" />
                  <span>Chuyển sang trả khi nhận hàng (COD)</span>
                </>
              )}
            </button>

            <Link
              href={`/account?order=${encodeURIComponent(cleanOrderCode)}`}
              className="w-full sm:w-auto px-5 py-3 rounded-xl bg-brand-blue-600 hover:bg-brand-blue-700 text-white font-bold text-xs shadow-xs transition-all flex items-center justify-center gap-2 cursor-pointer"
            >
              <RotateCcw className="w-4 h-4" />
              <span>Mở chi tiết & Thanh toán lại</span>
            </Link>

            <Link
              href="/products"
              className="w-full sm:w-auto px-5 py-3 rounded-xl border border-slate-200 hover:bg-slate-50 text-slate-700 font-bold text-xs transition-all"
            >
              Tiếp tục mua hàng
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}

export default function CheckoutResultPage() {
  return (
    <div className="min-h-screen flex flex-col bg-slate-50">
      <Header />
      <main className="flex-1">
        <Suspense
          fallback={
            <div className="max-w-md mx-auto py-24 text-center text-slate-500 text-sm">
              Đang tải kết quả thanh toán...
            </div>
          }
        >
          <CheckoutResultContent />
        </Suspense>
      </main>
      <Footer />
    </div>
  );
}
