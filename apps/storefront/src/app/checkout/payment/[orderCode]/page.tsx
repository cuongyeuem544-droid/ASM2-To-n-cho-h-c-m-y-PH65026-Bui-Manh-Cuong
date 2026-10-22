"use client";

import React, { useState, useEffect, useRef } from "react";
import Image from "next/image";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { Header } from "@/components/layout/Header";
import { Footer } from "@/components/layout/Footer";
import ChangePaymentMethodModal, {
  PaymentMethodType,
} from "@/components/checkout/ChangePaymentMethodModal";
import {
  QrCode,
  Copy,
  Check,
  Clock,
  ArrowRight,
  ShieldCheck,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  ShoppingBag,
  Phone,
  User,
  MapPin,
  CreditCard,
  Banknote,
  RefreshCw,
  Loader2,
  Download,
  ExternalLink,
  FileText,
  Package,
  HelpCircle,
} from "lucide-react";
import { PHARMACY_CONTACT } from "@/lib/constants";

interface PaymentItem {
  id: number;
  product_id?: number;
  product_name: string;
  product_sku?: string;
  price: number;
  quantity: number;
  subtotal: number;
  image_url?: string;
}

interface OrderPaymentSummary {
  order_code: string;
  payment_code?: string;
  payment_status: string;
  payment_method: string;
  order_status: string;
  fulfillment_status?: string;
  total_amount: number;
  customer_name: string;
  customer_phone?: string;
  shipping_address?: string;
  shipping_fee?: number;
  discount_amount?: number;
  items: PaymentItem[];
  sepay_details?: {
    payment_code: string;
    bank_name: string;
    account_number: string;
    account_holder: string;
    qr_code_url?: string;
    amount: number;
    expires_at?: string;
    is_expired?: boolean;
  };
  payos_details?: {
    checkout_url?: string;
    qr_code_url?: string;
    account_number?: string;
    account_name?: string;
    bin?: string;
    payos_order_code?: string;
    amount: number;
    expires_at?: string;
    is_expired?: boolean;
  };
  expires_at?: string;
  is_expired?: boolean;
  server_time?: string;
  can_retry?: boolean;
}

export default function DedicatedPaymentPage() {
  const params = useParams();
  const router = useRouter();
  const orderCode = typeof params?.orderCode === "string" ? params.orderCode : "";

  const [isLoading, setIsLoading] = useState(true);
  const [orderData, setOrderData] = useState<OrderPaymentSummary | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [copiedField, setCopiedField] = useState<string | null>(null);
  const [qrImgError, setQrImgError] = useState(false);
  const [qrReloadKey, setQrReloadKey] = useState(0);
  const isPollingBusyRef = React.useRef(false);

  // Modals & Action loading
  const [showChangeMethodModal, setShowChangeMethodModal] = useState(false);
  const [showCancelDialog, setShowCancelDialog] = useState(false);
  const [isCancelling, setIsCancelling] = useState(false);
  const [isRefreshingCode, setIsRefreshingCode] = useState(false);

  // Time remaining countdown in seconds
  const [timeLeft, setTimeLeft] = useState<number>(15 * 60);

  // Authentication & Session Headers
  const getAuthHeaders = () => {
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (typeof window !== "undefined") {
      const token =
        localStorage.getItem("pharmatrust_access_token") ||
        localStorage.getItem("h4care_auth_token") ||
        localStorage.getItem("pharmatrust_token");
      const orderToken =
        localStorage.getItem(`h4care_order_token_${orderCode}`) ||
        localStorage.getItem("h4care_latest_order_token") ||
        "";
      if (token) headers["Authorization"] = `Bearer ${token}`;
      if (orderToken) headers["X-Order-Token"] = orderToken;
    }
    return headers;
  };

  // 1. Fetch Order Payment Status
  const fetchOrderStatus = async (silent = false) => {
    if (!orderCode) return;
    if (!silent) setIsLoading(true);
    try {
      const phone =
        typeof window !== "undefined"
          ? localStorage.getItem("h4care_checkout_phone") || ""
          : "";
      const query = phone ? `?phone_verify=${encodeURIComponent(phone)}` : "";
      const res = await fetch(`/api/v1/payments/orders/${encodeURIComponent(orderCode)}/status${query}`, {
        headers: getAuthHeaders(),
      });

      if (!res.ok) {
        if (res.status === 404) {
          throw new Error(`Không tìm thấy đơn hàng "${orderCode}". Vui lòng kiểm tra lại mã đơn.`);
        }
        if (res.status === 403) {
          throw new Error("Bạn không có quyền truy cập thông tin đơn hàng này.");
        }
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || "Không thể tải thông tin thanh toán của đơn hàng.");
      }

      const data: OrderPaymentSummary = await res.json();
      setOrderData((prev) => {
        if (prev?.sepay_details?.qr_code_url && data.sepay_details && !data.sepay_details.qr_code_url) {
          data.sepay_details.qr_code_url = prev.sepay_details.qr_code_url;
        }
        return data;
      });
      setErrorMessage(null);

      // Compute initial remaining seconds from server expires_at
      const targetExp = data.expires_at || data.sepay_details?.expires_at || data.payos_details?.expires_at;
      if (targetExp) {
        const diff = Math.floor((new Date(targetExp).getTime() - Date.now()) / 1000);
        setTimeLeft(Math.max(0, diff));
      }
    } catch (err: any) {
      setErrorMessage(err.message || "Lỗi kết nối máy chủ");
    } finally {
      if (!silent) setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchOrderStatus();
  }, [orderCode]);

  // 2. Live Countdown Timer
  useEffect(() => {
    if (!orderData || orderData.payment_status === "PAID" || orderData.order_status === "CANCELLED") {
      return;
    }

    const timer = setInterval(() => {
      const targetExp = orderData.expires_at || orderData.sepay_details?.expires_at || orderData.payos_details?.expires_at;
      if (targetExp) {
        const diff = Math.floor((new Date(targetExp).getTime() - Date.now()) / 1000);
        setTimeLeft(Math.max(0, diff));
      } else {
        setTimeLeft((prev) => Math.max(0, prev - 1));
      }
    }, 1000);

    return () => clearInterval(timer);
  }, [orderData]);

  // 3. Robust Live Polling (Every 3s while PENDING & NOT EXPIRED, decoupled from 1s tick)
  useEffect(() => {
    const isOrderPaid = orderData?.payment_status === "PAID";
    const isOrderCancelled = orderData?.order_status === "CANCELLED";
    const isOrderExpired = orderData?.payment_method !== "COD" && timeLeft <= 0;

    if (!orderCode || isOrderPaid || isOrderCancelled || isOrderExpired) {
      return;
    }

    const safeFetch = async () => {
      if (isPollingBusyRef.current) return;
      isPollingBusyRef.current = true;
      try {
        await fetchOrderStatus(true);
      } finally {
        isPollingBusyRef.current = false;
      }
    };

    const poller = setInterval(safeFetch, 3000);

    // Bắt sự kiện khi khách hàng hoàn tất chuyển khoản trong App ngân hàng rồi quay lại trình duyệt
    const handleVisibility = () => {
      if (document.visibilityState === "visible") {
        safeFetch();
      }
    };
    const handleFocus = () => safeFetch();

    document.addEventListener("visibilitychange", handleVisibility);
    window.addEventListener("focus", handleFocus);

    return () => {
      clearInterval(poller);
      document.removeEventListener("visibilitychange", handleVisibility);
      window.removeEventListener("focus", handleFocus);
    };
  }, [orderCode, orderData?.payment_status, orderData?.order_status, orderData?.payment_method !== "COD" && timeLeft <= 0]);

  // Helper formatting
  const formatCountdown = (seconds: number) => {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
  };

  const handleCopy = (text: string, fieldName: string) => {
    if (!text) return;
    navigator.clipboard.writeText(text);
    setCopiedField(fieldName);
    setTimeout(() => setCopiedField(null), 2000);
  };

  // Action: Tạo lại mã thanh toán mới (15 phút mới)
  const handleRefreshCode = async () => {
    if (!orderData) return;
    try {
      setIsRefreshingCode(true);
      setErrorMessage(null);
      const phone = typeof window !== "undefined" ? localStorage.getItem("h4care_checkout_phone") || "" : "";
      const res = await fetch("/api/v1/payments/retry", {
        method: "POST",
        headers: getAuthHeaders(),
        body: JSON.stringify({
          order_code: orderData.order_code,
          new_payment_method: orderData.payment_method,
          phone_verify: phone || undefined,
        }),
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Không thể tạo mã thanh toán mới.");
      }

      await fetchOrderStatus(true);
    } catch (err: any) {
      setErrorMessage(err.message || "Lỗi khi tạo mã mới.");
    } finally {
      setIsRefreshingCode(false);
    }
  };

  // Action: Xác nhận đổi phương thức thanh toán
  const handleConfirmChangeMethod = async (newMethod: PaymentMethodType) => {
    if (!orderData) return;
    const phone = typeof window !== "undefined" ? localStorage.getItem("h4care_checkout_phone") || "" : "";
    const returnUrl = typeof window !== "undefined"
      ? `${window.location.origin}/checkout/result?order_code=${encodeURIComponent(orderData.order_code)}`
      : undefined;

    const res = await fetch("/api/v1/payments/retry", {
      method: "POST",
      headers: getAuthHeaders(),
      body: JSON.stringify({
        order_code: orderData.order_code,
        new_payment_method: newMethod,
        phone_verify: phone || undefined,
        return_url: returnUrl,
      }),
    });

    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || `Không thể chuyển sang phương thức ${newMethod}.`);
    }

    setShowChangeMethodModal(false);
    await fetchOrderStatus();

    if (newMethod === "PAYOS" && data.payment_intent?.pay_url) {
      window.location.href = data.payment_intent.pay_url;
    }
  };

  // Action: Hủy đơn hàng và giải phóng tồn kho
  const handleCancelOrder = async () => {
    if (!orderData) return;
    try {
      setIsCancelling(true);
      setErrorMessage(null);
      const phone = typeof window !== "undefined" ? localStorage.getItem("h4care_checkout_phone") || "" : "";
      const res = await fetch(`/api/v1/payments/orders/${encodeURIComponent(orderData.order_code)}/cancel`, {
        method: "POST",
        headers: getAuthHeaders(),
        body: JSON.stringify({
          reason: "Khách hàng hủy thanh toán trực tuyến",
          phone_verify: phone || undefined,
        }),
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Không thể hủy đơn hàng.");
      }

      setShowCancelDialog(false);
      await fetchOrderStatus();
    } catch (err: any) {
      setErrorMessage(err.message || "Lỗi khi hủy đơn hàng.");
    } finally {
      setIsCancelling(false);
    }
  };

  const isExpired = orderData?.payment_method !== "COD" && timeLeft <= 0;
  const isPaid = orderData?.payment_status === "PAID";
  const isCancelled = orderData?.order_status === "CANCELLED";

  // Data helpers
  const sepayInfo = orderData?.sepay_details;
  const payosInfo = orderData?.payos_details;
  const totalAmount = orderData?.total_amount || 0;

  return (
    <div className="min-h-screen flex flex-col bg-slate-50 text-slate-800">
      <Header />

      <main className="flex-1 py-6 sm:py-10">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 space-y-6">
          {/* Breadcrumb & Navigation */}
          <div className="flex items-center justify-between text-xs text-slate-500">
            <div className="flex items-center gap-1.5 flex-wrap">
              <Link href="/" className="hover:text-emerald-700 transition-colors">
                Trang chủ
              </Link>
              <span>/</span>
              <Link href="/cart" className="hover:text-emerald-700 transition-colors">
                Giỏ hàng
              </Link>
              <span>/</span>
              <span className="font-semibold text-slate-800">Thanh toán #{orderCode}</span>
            </div>

            <Link
              href="/products"
              className="hidden sm:inline-flex items-center gap-1 hover:text-emerald-700 transition-colors font-medium"
            >
              <ShoppingBag className="w-3.5 h-3.5" />
              <span>Tiếp tục mua thuốc</span>
            </Link>
          </div>

          {/* Loading Skeleton */}
          {isLoading ? (
            <div className="bg-white rounded-3xl p-12 border border-slate-200 text-center shadow-xs">
              <Loader2 className="w-10 h-10 animate-spin text-emerald-600 mx-auto mb-4" />
              <p className="text-sm font-bold text-slate-800">
                Đang đối soát thông tin đơn hàng #{orderCode}...
              </p>
              <p className="text-xs text-slate-500 mt-1">
                Hệ thống đang kết nối trực tiếp tới cổng thanh toán và kho lưu trữ.
              </p>
            </div>
          ) : errorMessage && !orderData ? (
            /* Error Card */
            <div className="bg-white rounded-3xl p-8 sm:p-12 border border-slate-200 text-center shadow-xs space-y-4 max-w-lg mx-auto">
              <div className="w-16 h-16 rounded-full bg-rose-50 text-rose-600 flex items-center justify-center mx-auto ring-8 ring-rose-50/50">
                <AlertTriangle className="w-8 h-8" />
              </div>
              <h1 className="text-xl font-black text-slate-900">Không thể tải đơn thanh toán</h1>
              <p className="text-xs sm:text-sm text-slate-600 leading-relaxed">{errorMessage}</p>
              <div className="pt-2 flex flex-col sm:flex-row items-center justify-center gap-2">
                <button
                  type="button"
                  onClick={() => fetchOrderStatus()}
                  className="w-full sm:w-auto px-5 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs transition-colors"
                >
                  Thử lại
                </button>
                <Link
                  href="/cart"
                  className="w-full sm:w-auto px-5 py-2.5 rounded-xl border border-slate-200 hover:bg-slate-50 text-slate-700 font-bold text-xs transition-colors"
                >
                  Quay về giỏ hàng
                </Link>
              </div>
            </div>
          ) : isPaid ? (
            /* 1. STATE: PAID SUCCESS VIEW */
            <div className="bg-white rounded-3xl p-8 sm:p-12 border border-slate-200 shadow-xs text-center max-w-2xl mx-auto space-y-6 animate-in zoom-in-95">
              <div className="w-20 h-20 rounded-full bg-emerald-50 text-emerald-600 flex items-center justify-center mx-auto ring-8 ring-emerald-50/50">
                <CheckCircle2 className="w-10 h-10" />
              </div>

              <div>
                <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-50 text-emerald-700 text-xs font-bold border border-emerald-200 mb-2">
                  <ShieldCheck className="w-3.5 h-3.5" />
                  Đã thanh toán thành công 100%
                </span>
                <h1 className="text-2xl sm:text-3xl font-black text-slate-900 tracking-tight">
                  Xác nhận thanh toán đơn #{orderCode}
                </h1>
                <p className="text-xs sm:text-sm text-slate-600 mt-2 max-w-md mx-auto leading-relaxed">
                  Giao dịch đã được hệ thống kế toán H4CARE tự động khớp lệnh. Đơn thuốc của bạn đã sẵn sàng và được chuyển cho Dược sĩ kho phụ trách soạn thuốc theo chuẩn FEFO.
                </p>
              </div>

              <div className="p-4 sm:p-5 bg-slate-50 rounded-2xl border border-slate-200 text-left text-xs space-y-2.5">
                <div className="flex justify-between items-center pb-2 border-b border-slate-200">
                  <span className="text-slate-500">Mã đơn hàng:</span>
                  <span className="font-mono font-bold text-slate-900 text-sm">{orderCode}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-slate-500">Người nhận thuốc:</span>
                  <span className="font-bold text-slate-900">{orderData?.customer_name}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-slate-500">Phương thức:</span>
                  <span className="font-semibold text-emerald-700">
                    {orderData?.payment_method === "SEPAY"
                      ? "Chuyển khoản VietQR MBBank (SePay)"
                      : orderData?.payment_method === "PAYOS"
                      ? "Cổng thanh toán payOS"
                      : "Thanh toán khi nhận hàng (COD)"}
                  </span>
                </div>
                <div className="flex justify-between items-center pt-2 border-t border-slate-200 text-sm">
                  <span className="font-bold text-slate-900">Tổng thanh toán:</span>
                  <span className="font-mono font-black text-rose-600 text-base">
                    {totalAmount.toLocaleString("vi-VN")} đ
                  </span>
                </div>
              </div>

              <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
                <Link
                  href={`/account#orders`}
                  className="w-full sm:w-auto px-6 py-3 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs flex items-center justify-center gap-2 shadow-sm transition-all"
                >
                  <FileText className="w-4 h-4" />
                  <span>Theo dõi tiến độ đơn thuốc</span>
                </Link>
                <Link
                  href="/products"
                  className="w-full sm:w-auto px-6 py-3 rounded-xl border border-slate-200 hover:bg-slate-50 text-slate-700 font-bold text-xs transition-colors"
                >
                  Tiếp tục mua hàng
                </Link>
              </div>
            </div>
          ) : isCancelled ? (
            /* 2. STATE: CANCELLED VIEW */
            <div className="bg-white rounded-3xl p-8 sm:p-12 border border-slate-200 shadow-xs text-center max-w-2xl mx-auto space-y-6">
              <div className="w-20 h-20 rounded-full bg-rose-50 text-rose-600 flex items-center justify-center mx-auto ring-8 ring-rose-50/50">
                <XCircle className="w-10 h-10" />
              </div>

              <div>
                <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-rose-50 text-rose-700 text-xs font-bold border border-rose-200 mb-2">
                  Đơn hàng đã hủy
                </span>
                <h1 className="text-2xl font-black text-slate-900">
                  Đơn hàng #{orderCode} đã được hủy bỏ
                </h1>
                <p className="text-xs sm:text-sm text-slate-600 mt-2 max-w-md mx-auto leading-relaxed">
                  Lượng thuốc giữ chỗ trong kho đã được giải phóng hoàn trả lại cho hệ thống. Bạn có thể chọn lại sản phẩm và đặt đơn mới bất kỳ lúc nào.
                </p>
              </div>

              <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
                <Link
                  href="/products"
                  className="w-full sm:w-auto px-6 py-3 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs flex items-center justify-center gap-2 shadow-sm transition-all"
                >
                  <ShoppingBag className="w-4 h-4" />
                  <span>Tiếp tục mua sắm</span>
                </Link>
              </div>
            </div>
          ) : (
            /* 3. STATE: ACTIVE PAYMENT VIEW (SePay / payOS / COD) */
            <div className="space-y-6">
              {/* Top Expiration Warning Banners */}
              {orderData?.payment_method !== "COD" && (
                <div>
                  {isExpired ? (
                    <div className="p-4 rounded-2xl bg-rose-50 border-2 border-rose-300 text-rose-900 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 shadow-xs">
                      <div className="flex items-start gap-3">
                        <AlertTriangle className="w-5 h-5 text-rose-600 shrink-0 mt-0.5" />
                        <div>
                          <p className="font-bold text-xs sm:text-sm text-rose-950">
                            Mã thanh toán 15 phút đã hết hạn
                          </p>
                          <p className="text-[11px] sm:text-xs text-rose-800 mt-0.5">
                            Vui lòng <strong>không chuyển tiền</strong> vào mã cũ. Đơn thuốc vẫn được giữ chỗ 30 phút. Bạn có thể tạo mã mới ngay lập tức.
                          </p>
                        </div>
                      </div>

                      <button
                        type="button"
                        onClick={handleRefreshCode}
                        disabled={isRefreshingCode}
                        className="w-full sm:w-auto px-4 py-2 rounded-xl bg-rose-600 hover:bg-rose-700 text-white font-bold text-xs flex items-center justify-center gap-1.5 shadow-xs transition-all shrink-0 cursor-pointer"
                      >
                        {isRefreshingCode ? (
                          <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        ) : (
                          <RefreshCw className="w-3.5 h-3.5" />
                        )}
                        <span>Tạo mã thanh toán mới</span>
                      </button>
                    </div>
                  ) : timeLeft <= 60 ? (
                    <div className="p-3.5 rounded-2xl bg-rose-50 border border-rose-300 text-rose-900 flex items-center justify-between gap-3 animate-pulse">
                      <div className="flex items-center gap-2 text-xs font-bold text-rose-800">
                        <Clock className="w-4 h-4 text-rose-600 shrink-0" />
                        <span>Mã thanh toán sắp hết hiệu lực! Vui lòng hoàn tất trong:</span>
                      </div>
                      <span className="font-mono font-black text-rose-700 text-sm bg-rose-100 px-2.5 py-1 rounded-lg border border-rose-300">
                        {formatCountdown(timeLeft)}
                      </span>
                    </div>
                  ) : timeLeft <= 300 ? (
                    <div className="p-3 rounded-2xl bg-amber-50 border border-amber-300 text-amber-900 flex items-center justify-between gap-3">
                      <div className="flex items-center gap-2 text-xs font-semibold text-amber-900">
                        <Clock className="w-4 h-4 text-amber-600 shrink-0" />
                        <span>Thời gian thanh toán còn lại:</span>
                      </div>
                      <span className="font-mono font-bold text-amber-900 text-xs bg-amber-100 px-2 py-0.5 rounded-md border border-amber-300">
                        {formatCountdown(timeLeft)}
                      </span>
                    </div>
                  ) : null}
                </div>
              )}

              {/* Main 2-Column Grid */}
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
                {/* Left Column: Payment Area */}
                <div className="lg:col-span-7 space-y-5">
                  <div className="p-5 sm:p-7 rounded-3xl bg-white border border-slate-200 shadow-xs space-y-5">
                    {/* Header: Method Selector Badge */}
                    <div className="flex items-center justify-between pb-4 border-b border-slate-100 flex-wrap gap-2">
                      <div>
                        <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                          Phương thức thanh toán
                        </span>
                        <h2 className="text-base sm:text-lg font-black text-slate-900 flex items-center gap-2">
                          {orderData?.payment_method === "SEPAY" ? (
                            <>
                              <QrCode className="w-5 h-5 text-emerald-600" />
                              <span>Chuyển khoản VietQR MBBank</span>
                            </>
                          ) : orderData?.payment_method === "PAYOS" ? (
                            <>
                              <CreditCard className="w-5 h-5 text-blue-600" />
                              <span>Cổng thanh toán trực tuyến payOS</span>
                            </>
                          ) : (
                            <>
                              <Banknote className="w-5 h-5 text-emerald-600" />
                              <span>Thanh toán khi nhận hàng (COD)</span>
                            </>
                          )}
                        </h2>
                      </div>

                      <button
                        type="button"
                        onClick={() => setShowChangeMethodModal(true)}
                        className="px-3 py-1.5 rounded-xl border border-slate-200 hover:bg-slate-50 text-slate-700 font-bold text-xs flex items-center gap-1.5 transition-colors cursor-pointer"
                      >
                        <RefreshCw className="w-3.5 h-3.5" />
                        <span>Đổi phương thức</span>
                      </button>
                    </div>

                    {/* METHOD SPECIFIC BODY: SEPAY */}
                    {orderData?.payment_method === "SEPAY" && (
                      <div className="space-y-5">
                        {/* QR Code Container */}
                        <div className="text-center p-4 bg-slate-50 rounded-2xl border border-slate-200/80 relative">
                          <div className="relative inline-block bg-white p-3 rounded-2xl shadow-sm border border-slate-100 overflow-hidden">
                            {qrImgError ? (
                              <div className="w-52 h-52 sm:w-60 sm:h-60 flex flex-col items-center justify-center p-4 text-center bg-slate-100 rounded-xl text-slate-700">
                                <AlertTriangle className="w-8 h-8 text-amber-500 mb-2" />
                                <span className="text-xs font-bold text-slate-800">Không tải được ảnh mã QR</span>
                                <span className="text-[10px] text-slate-500 mt-1 max-w-[180px] leading-relaxed">
                                  Bạn có thể chuyển khoản bằng thông tin số tài khoản bên dưới
                                </span>
                                <button
                                  type="button"
                                  onClick={() => {
                                    setQrImgError(false);
                                    setQrReloadKey((k) => k + 1);
                                  }}
                                  className="mt-3 px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs flex items-center gap-1.5 transition-all cursor-pointer"
                                >
                                  <RefreshCw className="w-3.5 h-3.5" />
                                  <span>Tải lại ảnh QR</span>
                                </button>
                              </div>
                            ) : sepayInfo?.qr_code_url ? (
                              <img
                                key={qrReloadKey}
                                src={sepayInfo.qr_code_url}
                                alt="VietQR MBBank SePay"
                                onError={() => setQrImgError(true)}
                                className={`w-52 h-52 sm:w-60 sm:h-60 object-contain mx-auto rounded-xl transition-all ${
                                  isExpired ? "opacity-20 blur-xs grayscale" : ""
                                }`}
                              />
                            ) : (
                              <div className="w-52 h-52 flex flex-col items-center justify-center text-slate-400 text-xs">
                                <QrCode className="w-8 h-8 mb-2" />
                                <span>Đang khởi tạo mã QR...</span>
                              </div>
                            )}

                            {/* Expired Overlay */}
                            {isExpired && (
                              <div className="absolute inset-0 bg-slate-900/65 backdrop-blur-2xs flex flex-col items-center justify-center p-4 text-white text-center">
                                <AlertTriangle className="w-10 h-10 text-rose-400 mb-2 animate-bounce" />
                                <p className="font-black text-xs uppercase tracking-wider text-rose-300">
                                  Mã Đã Quá Hạn 15 Phút
                                </p>
                                <p className="text-[10px] text-slate-200 mt-1 max-w-[190px] leading-relaxed">
                                  Vui lòng nhấn nút dưới để nhận mã QR mới 15 phút.
                                </p>
                                <button
                                  type="button"
                                  onClick={handleRefreshCode}
                                  disabled={isRefreshingCode}
                                  className="mt-3 px-3.5 py-1.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs flex items-center gap-1.5 shadow-md active:scale-95 transition-all cursor-pointer"
                                >
                                  {isRefreshingCode ? (
                                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                                  ) : (
                                    <RefreshCw className="w-3.5 h-3.5" />
                                  )}
                                  <span>Tạo mã QR mới</span>
                                </button>
                              </div>
                            )}
                          </div>

                          <div className="mt-3">
                            <span className="text-xs text-slate-500 font-medium">Số tiền cần thanh toán:</span>
                            <p className="text-xl sm:text-2xl font-black text-rose-600 font-mono">
                              {totalAmount.toLocaleString("vi-VN")} đ
                            </p>
                          </div>
                          <p className="text-[11px] text-slate-500 mt-1">
                            Sử dụng ứng dụng bất kỳ (MBBank, Vietcombank, Techcombank, BIDV, VPBank,...) để quét mã Napas 247
                          </p>

                          {/* Instant Check Button */}
                          <div className="mt-4 pt-3 border-t border-slate-200/70 flex flex-col items-center gap-1.5">
                            <button
                              type="button"
                              onClick={() => fetchOrderStatus(false)}
                              disabled={isLoading}
                              className="w-full sm:w-auto px-5 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs flex items-center justify-center gap-2 shadow-sm active:scale-98 transition-all cursor-pointer"
                            >
                              {isLoading ? (
                                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                              ) : (
                                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-200" />
                              )}
                              <span>Tôi đã chuyển khoản — Kiểm tra ngay</span>
                            </button>
                            <span className="text-[10px] text-slate-400">
                              Hệ thống tự động kiểm tra mỗi 3 giây hoặc khi bạn chuyển lại tab này
                            </span>
                          </div>
                        </div>

                        {/* Bank Details Table */}
                        <div className="space-y-2 text-xs">
                          <div className="flex items-center justify-between text-slate-500 font-bold uppercase tracking-wider text-[10px]">
                            <span>Thông tin người thụ hưởng</span>
                            <span className="text-emerald-700 font-normal">Chạm để sao chép nhanh</span>
                          </div>

                          <div className="p-3.5 bg-slate-50 rounded-2xl border border-slate-200 space-y-2.5">
                            <div className="flex justify-between items-center py-1 border-b border-slate-200/70">
                              <span className="text-slate-500">Ngân hàng:</span>
                              <span className="font-bold text-slate-900">
                                {sepayInfo?.bank_name || "Ngân hàng TMCP Quân Đội (MBBank)"}
                              </span>
                            </div>

                            <div className="flex justify-between items-center py-1 border-b border-slate-200/70">
                              <span className="text-slate-500">Số tài khoản:</span>
                              <div className="flex items-center gap-2">
                                <span className="font-mono font-bold text-emerald-800 text-sm">
                                  {sepayInfo?.account_number || "Đang tải..."}
                                </span>
                                {sepayInfo?.account_number && (
                                  <button
                                    type="button"
                                    onClick={() => handleCopy(sepayInfo.account_number, "acc")}
                                    className="p-1 rounded-md bg-white hover:bg-slate-200 text-slate-700 transition-colors border border-slate-200"
                                    title="Sao chép số tài khoản"
                                  >
                                    {copiedField === "acc" ? (
                                      <Check className="w-3.5 h-3.5 text-emerald-600" />
                                    ) : (
                                      <Copy className="w-3.5 h-3.5" />
                                    )}
                                  </button>
                                )}
                              </div>
                            </div>

                            <div className="flex justify-between items-center py-1 border-b border-slate-200/70">
                              <span className="text-slate-500">Chủ tài khoản:</span>
                              <span className="font-bold text-slate-900">{sepayInfo?.account_holder}</span>
                            </div>

                            {/* Transfer Content */}
                            <div className="p-2.5 bg-emerald-50 rounded-xl border border-emerald-200 flex items-center justify-between">
                              <div>
                                <span className="text-emerald-950 font-bold block text-[11px]">
                                  Nội dung chuyển khoản (bắt buộc giữ nguyên):
                                </span>
                                <span className="font-mono font-black text-emerald-800 text-sm tracking-wide">
                                  {sepayInfo?.payment_code || orderCode}
                                </span>
                              </div>
                              <button
                                type="button"
                                onClick={() => handleCopy(sepayInfo?.payment_code || orderCode, "memo")}
                                className="px-2.5 py-1 rounded-md bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-[10px] flex items-center gap-1 shadow-2xs transition-colors"
                              >
                                {copiedField === "memo" ? (
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

                        {/* Polling Indicator */}
                        <div className="p-3 rounded-2xl bg-amber-50/80 border border-amber-200 text-xs text-amber-900 flex items-center gap-3">
                          <RefreshCw className="w-4 h-4 text-amber-600 animate-spin shrink-0" />
                          <div className="leading-relaxed text-[11px]">
                            <strong>Đang chờ tín hiệu biến động số dư ngân hàng 24/7...</strong>
                            <p className="text-[10px] text-amber-800 mt-0.5">
                              Ngay khi bạn chuyển tiền thành công, SePay Webhook sẽ kích hoạt xác nhận đơn lập tức (không cần chụp biên lai).
                            </p>
                          </div>
                        </div>
                      </div>
                    )}

                    {/* METHOD SPECIFIC BODY: PAYOS */}
                    {orderData?.payment_method === "PAYOS" && (
                      <div className="space-y-4">
                        <div className="p-5 bg-blue-50/60 rounded-2xl border border-blue-200 text-center space-y-3">
                          <div className="w-12 h-12 rounded-full bg-blue-100 text-blue-600 flex items-center justify-center mx-auto">
                            <CreditCard className="w-6 h-6" />
                          </div>
                          <h3 className="font-black text-sm text-slate-900">
                            Cổng thanh toán payOS (Napas 247 / Thẻ ATM)
                          </h3>
                          <p className="text-xs text-slate-600 max-w-md mx-auto">
                            Nhấn nút bên dưới để chuyển tiếp sang giao diện thanh toán an toàn của cổng payOS. Sau khi thanh toán, hệ thống sẽ tự động cập nhật đơn của bạn.
                          </p>

                          {payosInfo?.checkout_url && (
                            <a
                              href={payosInfo.checkout_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="inline-flex items-center justify-center gap-2 px-6 py-3 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-bold text-xs shadow-sm transition-all"
                            >
                              <span>Mở cổng thanh toán payOS</span>
                              <ExternalLink className="w-3.5 h-3.5" />
                            </a>
                          )}
                        </div>

                        <div className="p-3.5 rounded-2xl bg-slate-50 border border-slate-200 text-xs space-y-2">
                          <div className="flex justify-between">
                            <span className="text-slate-500">Mã đơn payOS:</span>
                            <span className="font-mono font-bold text-slate-900">
                              {payosInfo?.payos_order_code || "N/A"}
                            </span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-slate-500">Số tiền:</span>
                            <span className="font-mono font-black text-rose-600">
                              {totalAmount.toLocaleString("vi-VN")} đ
                            </span>
                          </div>
                        </div>
                      </div>
                    )}

                    {/* METHOD SPECIFIC BODY: COD */}
                    {orderData?.payment_method === "COD" && (
                      <div className="p-5 bg-emerald-50/70 rounded-2xl border border-emerald-200 text-center space-y-3">
                        <div className="w-12 h-12 rounded-full bg-emerald-100 text-emerald-600 flex items-center justify-center mx-auto">
                          <Banknote className="w-6 h-6" />
                        </div>
                        <h3 className="font-black text-sm text-slate-900">
                          Thanh toán khi nhận hàng (COD)
                        </h3>
                        <p className="text-xs text-emerald-800 max-w-md mx-auto leading-relaxed">
                          Đơn thuốc đã được tiếp nhận và giữ chỗ trong kho. Quý khách vui lòng chuẩn bị số tiền{" "}
                          <strong>{totalAmount.toLocaleString("vi-VN")} đ</strong> để thanh toán cho nhân viên giao hàng sau khi kiểm tra niêm phong.
                        </p>
                      </div>
                    )}

                    {/* Action Buttons Hierarchy */}
                    <div className="pt-3 border-t border-slate-100 flex flex-col sm:flex-row items-center justify-between gap-2.5">
                      {orderData?.payment_method === "SEPAY" && sepayInfo?.qr_code_url && !isExpired && (
                        <a
                          href={sepayInfo.qr_code_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          download={`VietQR_MBBank_${orderCode}.png`}
                          className="w-full sm:w-auto px-4 py-2.5 rounded-xl border border-slate-200 hover:bg-slate-100 text-slate-700 font-bold text-xs flex items-center justify-center gap-1.5 transition-colors"
                        >
                          <Download className="w-4 h-4" />
                          <span>Tải ảnh QR</span>
                        </a>
                      )}

                      <div className="w-full sm:w-auto flex items-center gap-2 flex-1 justify-end">
                        <button
                          type="button"
                          onClick={() => setShowCancelDialog(true)}
                          className="w-full sm:w-auto px-4 py-2.5 rounded-xl text-slate-500 hover:text-rose-600 hover:bg-rose-50 text-xs font-semibold transition-colors cursor-pointer"
                        >
                          Hủy đơn hàng
                        </button>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Right Column: Order Summary (Sticky Sidebar) */}
                <div className="lg:col-span-5 space-y-4">
                  {/* Order Details Card */}
                  <div className="p-5 sm:p-6 rounded-3xl bg-white border border-slate-200 shadow-xs space-y-4">
                    <div className="flex items-center justify-between pb-3 border-b border-slate-100">
                      <h3 className="font-black text-sm text-slate-900 flex items-center gap-2">
                        <Package className="w-4 h-4 text-emerald-600" />
                        <span>Sản phẩm trong đơn ({orderData?.items?.length || 0})</span>
                      </h3>
                      <span className="font-mono text-xs font-bold text-slate-600">#{orderCode}</span>
                    </div>

                    {/* Medication list */}
                    <div className="divide-y divide-slate-100 max-h-56 overflow-y-auto pr-1">
                      {orderData?.items?.map((item, idx) => (
                        <div key={item.id || idx} className="py-2.5 flex items-center justify-between gap-3 text-xs">
                          <div className="flex items-center gap-2.5 min-w-0">
                            <div className="relative w-9 h-9 rounded-lg bg-slate-100 border border-slate-200 overflow-hidden shrink-0">
                              {item.image_url ? (
                                <Image
                                  src={item.image_url}
                                  alt={item.product_name}
                                  fill
                                  className="object-cover"
                                  sizes="36px"
                                />
                              ) : (
                                <div className="w-full h-full flex items-center justify-center text-slate-400">
                                  <Package className="w-4 h-4" />
                                </div>
                              )}
                            </div>
                            <div className="min-w-0">
                              <p className="font-bold text-slate-900 line-clamp-1">{item.product_name}</p>
                              <p className="text-[10px] text-slate-500">Số lượng: {item.quantity}</p>
                            </div>
                          </div>
                          <span className="font-mono font-bold text-slate-900 shrink-0">
                            {item.subtotal.toLocaleString("vi-VN")} đ
                          </span>
                        </div>
                      ))}
                    </div>

                    {/* Pricing Breakdown */}
                    <div className="pt-3 border-t border-slate-100 space-y-2 text-xs">
                      <div className="flex justify-between text-slate-600">
                        <span>Tạm tính thuốc:</span>
                        <span className="font-mono">
                          {((orderData?.total_amount || 0) - (orderData?.shipping_fee || 0) + (orderData?.discount_amount || 0)).toLocaleString("vi-VN")} đ
                        </span>
                      </div>
                      <div className="flex justify-between text-slate-600">
                        <span>Phí vận chuyển:</span>
                        <span className="font-mono">
                          {(orderData?.shipping_fee || 0) === 0 ? "Miễn phí" : `${orderData?.shipping_fee?.toLocaleString("vi-VN")} đ`}
                        </span>
                      </div>
                      {(orderData?.discount_amount || 0) > 0 && (
                        <div className="flex justify-between text-emerald-700 font-semibold">
                          <span>Giảm giá voucher:</span>
                          <span className="font-mono">-{orderData?.discount_amount?.toLocaleString("vi-VN")} đ</span>
                        </div>
                      )}
                      <div className="flex justify-between pt-2 border-t border-slate-200 text-sm font-bold text-slate-900">
                        <span>Tổng thanh toán:</span>
                        <span className="font-mono font-black text-rose-600 text-base">
                          {totalAmount.toLocaleString("vi-VN")} đ
                        </span>
                      </div>
                    </div>

                    {/* Delivery Address Details */}
                    {orderData?.shipping_address && (
                      <div className="pt-3 border-t border-slate-100 text-xs text-slate-600 space-y-1.5">
                        <div className="flex items-center gap-1.5 font-bold text-slate-900">
                          <User className="w-3.5 h-3.5 text-slate-400" />
                          <span>{orderData.customer_name}</span>
                          {orderData.customer_phone && <span className="font-normal text-slate-500">• {orderData.customer_phone}</span>}
                        </div>
                        <div className="flex items-start gap-1.5 text-[11px] leading-relaxed">
                          <MapPin className="w-3.5 h-3.5 text-slate-400 shrink-0 mt-0.5" />
                          <span>{orderData.shipping_address}</span>
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Pharmacist Hotline Widget */}
                  <div className="p-4 rounded-3xl bg-emerald-50/70 border border-emerald-200 text-xs text-emerald-950 space-y-2">
                    <div className="flex items-center gap-2 font-bold">
                      <HelpCircle className="w-4 h-4 text-emerald-600" />
                      <span>Cần hỗ trợ thanh toán hoặc toa thuốc?</span>
                    </div>
                    <p className="text-[11px] text-emerald-800 leading-relaxed">
                      Dược sĩ chuyên môn luôn túc trực hỗ trợ tư vấn 24/7. Mọi thắc mắc về đơn hàng, vui lòng liên hệ:
                    </p>
                    <div className="pt-1 flex items-center justify-between">
                      <span className="font-bold text-emerald-900">{PHARMACY_CONTACT.supportEmail}</span>
                      <span className="text-[10px] text-emerald-700 bg-white px-2 py-0.5 rounded-full border border-emerald-200">
                        {PHARMACY_CONTACT.operatingHours}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </main>

      {/* MODAL 1: CHANGE PAYMENT METHOD */}
      {showChangeMethodModal && orderData && (
        <ChangePaymentMethodModal
          isOpen={showChangeMethodModal}
          currentMethod={orderData.payment_method as PaymentMethodType}
          totalAmount={totalAmount}
          orderCode={orderData.order_code}
          onClose={() => setShowChangeMethodModal(false)}
          onConfirmChange={handleConfirmChangeMethod}
        />
      )}

      {/* MODAL 2: CANCEL ORDER DIALOG */}
      {showCancelDialog && (
        <div className="fixed inset-0 z-[1200] flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-2xs animate-in fade-in">
          <div className="bg-white rounded-2xl max-w-sm w-full p-5 shadow-2xl border border-slate-200 space-y-4">
            <div className="w-11 h-11 rounded-full bg-rose-100 text-rose-600 flex items-center justify-center mx-auto">
              <AlertTriangle className="w-6 h-6" />
            </div>

            <div className="text-center space-y-1">
              <h3 className="text-base font-black text-slate-900">Xác nhận hủy đơn hàng</h3>
              <p className="text-xs text-slate-600 leading-relaxed">
                Đơn hàng #{orderCode} sẽ bị hủy bỏ và lượng thuốc đang giữ chỗ sẽ được giải phóng hoàn trả lại kho. Bạn có thể tiếp tục mua sắm lại bất kỳ lúc nào.
              </p>
            </div>

            <div className="flex items-center gap-2 pt-2">
              <button
                type="button"
                onClick={() => setShowCancelDialog(false)}
                disabled={isCancelling}
                className="flex-1 py-2 px-3 rounded-xl border border-slate-200 text-slate-700 font-bold text-xs hover:bg-slate-50 transition-colors"
              >
                Quay lại
              </button>
              <button
                type="button"
                onClick={handleCancelOrder}
                disabled={isCancelling}
                className="flex-1 py-2 px-3 rounded-xl bg-rose-600 hover:bg-rose-700 text-white font-bold text-xs flex items-center justify-center gap-1.5 transition-colors cursor-pointer"
              >
                {isCancelling ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
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

      <Footer />
    </div>
  );
}
