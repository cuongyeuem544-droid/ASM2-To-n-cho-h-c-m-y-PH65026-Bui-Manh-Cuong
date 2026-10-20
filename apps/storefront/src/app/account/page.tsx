"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth/auth-context";
import { redirectToAdminPortal } from "@/lib/auth/admin-redirect";
import { Header } from "@/components/layout/Header";
import { Footer } from "@/components/layout/Footer";
import {
  User,
  Phone,
  Mail,
  ShieldCheck,
  FileText,
  Clock,
  Award,
  LogOut,
  ChevronRight,
  Package,
  HeartPulse,
  ExternalLink,
  ShoppingBag,
  Sparkles,
  X,
  MapPin,
  CheckCircle2,
  Edit3,
  Truck,
  PhoneCall,
  RotateCcw,
  RefreshCw,
  Banknote,
  QrCode,
  Stethoscope,
  AlertCircle,
  Search,
  ChevronLeft,
} from "lucide-react";
import { CustomerAddressBook } from "@/components/account/CustomerAddressBook";
import { CustomerReturnsSection } from "@/components/returns/CustomerReturnsSection";
import { ReturnWizardModal } from "@/components/returns/ReturnWizardModal";
import { formatDateTimeVN } from "@/lib/dateUtils";

interface CustomerOrder {
  id: number;
  order_code: string;
  customer_name: string;
  customer_phone: string;
  shipping_address: string;
  total_amount: number;
  order_status: string;
  payment_method: string;
  payment_status?: string;
  created_at: string | null;
  items_count: number;
  items: Array<{
    product_name: string;
    quantity: number;
    price: number;
    subtotal: number;
  }>;
}

export default function AccountPage() {
  const router = useRouter();
  const { user, isAuthenticated, isLoading, logout } = useAuth();
  const [orders, setOrders] = useState<CustomerOrder[]>([]);
  const [ordersStatus, setOrdersStatus] = useState<"loading" | "success" | "error">("loading");
  const [ordersError, setOrdersError] = useState<string>("");

  // Modal states
  const [selectedOrder, setSelectedOrder] = useState<CustomerOrder | null>(null);
  const [orderPaymentData, setOrderPaymentData] = useState<any | null>(null);
  const [loadingPaymentData, setLoadingPaymentData] = useState<boolean>(false);

  const [isSwitchingCod, setIsSwitchingCod] = useState<boolean>(false);
  const [isCancellingOrder, setIsCancellingOrder] = useState<boolean>(false);
  const [returnWizardOrderCode, setReturnWizardOrderCode] = useState<string | null>(null);
  const [isEditingProfile, setIsEditingProfile] = useState<boolean>(false);
  const [editName, setEditName] = useState<string>("");
  const [editEmail, setEditEmail] = useState<string>("");
  const [editAddress, setEditAddress] = useState<string>("123 Đường Nguyễn Huệ, Quận 1, TP. Hồ Chí Minh");
  const [saveSuccess, setSaveSuccess] = useState<boolean>(false);

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.push("/login?redirect=/account");
    }
  }, [isLoading, isAuthenticated, router]);

  useEffect(() => {
    if (user) {
      setEditName(user.fullName);
      setEditEmail(user.email || "");
    }
  }, [user]);

  const getAuthToken = () => {
    if (typeof window === "undefined") return null;
    return (
      localStorage.getItem("pharmatrust_access_token") ||
      localStorage.getItem("pharmatrust_token") ||
      localStorage.getItem("h4care_auth_token") ||
      localStorage.getItem("access_token")
    );
  };

  const getAuthHeaders = (): Record<string, string> => {
    const token = getAuthToken();
    const h: Record<string, string> = {};
    if (token) h["Authorization"] = `Bearer ${token}`;
    return h;
  };

  // Order list pagination & search state
  const [orderPage, setOrderPage] = useState<number>(1);
  const [orderPageSize] = useState<number>(5);
  const [orderTotal, setOrderTotal] = useState<number>(0);
  const [orderTotalPages, setOrderTotalPages] = useState<number>(1);
  const [orderSearchTerm, setOrderSearchTerm] = useState<string>("");
  const [orderStatusFilter, setOrderStatusFilter] = useState<string>("ALL");

  // Tab navigation state
  type AccountTab = "profile" | "addresses" | "prescriptions" | "orders" | "returns";
  const [activeTab, setActiveTab] = useState<AccountTab>("profile");

  useEffect(() => {
    const handleHashChange = () => {
      if (typeof window === "undefined") return;
      const rawHash = window.location.hash.replace("#", "").toLowerCase();
      if (
        rawHash === "addresses" ||
        rawHash === "prescriptions" ||
        rawHash === "orders" ||
        rawHash === "returns" ||
        rawHash === "profile"
      ) {
        setActiveTab(rawHash as AccountTab);
      }
    };

    handleHashChange();
    window.addEventListener("hashchange", handleHashChange);
    return () => window.removeEventListener("hashchange", handleHashChange);
  }, []);

  const handleTabClick = (tab: AccountTab) => {
    setActiveTab(tab);
    if (typeof window !== "undefined") {
      window.history.replaceState(null, "", `#${tab}`);
    }
  };

  // Load authenticated customer's orders strictly via JWT token with pagination & search
  const reloadOrders = async (
    targetPage: number = orderPage,
    status: string = orderStatusFilter,
    search: string = orderSearchTerm
  ) => {
    const token = getAuthToken();
    if (!token) {
      if (!isLoading && !isAuthenticated) {
        router.push("/login?redirect=/account");
      }
      return;
    }

    setOrdersStatus("loading");
    setOrdersError("");

    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL || "";
      const params = new URLSearchParams();
      params.append("page", String(targetPage));
      params.append("page_size", String(orderPageSize));
      if (status && status !== "ALL") params.append("status", status);
      if (search && search.trim()) params.append("search", search.trim());

      const res = await fetch(`${apiBase}/api/v1/store/orders/me?${params.toString()}`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (res.status === 401) {
        setOrdersStatus("error");
        setOrdersError("Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại để xem lịch sử đơn hàng.");
        router.push("/login?redirect=/account");
        return;
      }

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || "Không thể tải lịch sử đơn hàng từ máy chủ.");
      }

      const data = await res.json();
      const list = Array.isArray(data) ? data : (data.items || data.orders || []);
      setOrders(list);
      setOrderTotal(data.total ?? list.length);
      setOrderTotalPages(data.total_pages ?? Math.max(1, Math.ceil((data.total ?? list.length) / orderPageSize)));
      setOrderPage(data.page ?? targetPage);
      setOrdersStatus("success");
    } catch (err: any) {
      setOrdersStatus("error");
      setOrdersError(err.message || "Lỗi khi kết nối máy chủ để tải lịch sử đơn hàng.");
    }
  };

  const handleStatusFilterChange = (newStatus: string) => {
    setOrderStatusFilter(newStatus);
    setOrderPage(1);
    reloadOrders(1, newStatus, orderSearchTerm);
  };

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setOrderPage(1);
    reloadOrders(1, orderStatusFilter, orderSearchTerm);
  };

  const handleClearSearch = () => {
    setOrderSearchTerm("");
    setOrderPage(1);
    reloadOrders(1, orderStatusFilter, "");
  };

  const handlePageChange = (newPage: number) => {
    if (newPage < 1 || newPage > orderTotalPages) return;
    setOrderPage(newPage);
    reloadOrders(newPage, orderStatusFilter, orderSearchTerm);
  };

  useEffect(() => {
    if (isAuthenticated) {
      reloadOrders();
    }
  }, [isAuthenticated]);

  // Load live payment data when selectedOrder is opened
  useEffect(() => {
    if (selectedOrder?.order_code) {
      setLoadingPaymentData(true);
      fetch(`/api/v1/payments/orders/${selectedOrder.order_code}/status`, { headers: getAuthHeaders() })
        .then((res) => (res.ok ? res.json() : null))
        .then((data) => setOrderPaymentData(data))
        .catch(() => setOrderPaymentData(null))
        .finally(() => setLoadingPaymentData(false));
    } else {
      setOrderPaymentData(null);
    }
  }, [selectedOrder?.order_code]);

  const handleSwitchToCod = async (orderCode: string) => {
    setIsSwitchingCod(true);
    try {
      const res = await fetch("/api/v1/payments/retry", {
        method: "POST",
        headers: { "Content-Type": "application/json", ...getAuthHeaders() },
        body: JSON.stringify({
          order_code: orderCode,
          new_payment_method: "COD",
        }),
      });
      if (res.ok) {
        reloadOrders();
        const pRes = await fetch(`/api/v1/payments/orders/${orderCode}/status`, { headers: getAuthHeaders() });
        if (pRes.ok) {
          const freshPayment = await pRes.json();
          setOrderPaymentData(freshPayment);
          if (selectedOrder) {
            setSelectedOrder({
              ...selectedOrder,
              payment_method: "COD",
              payment_status: freshPayment.payment_status,
            });
          }
        }
      } else {
        const err = await res.json();
        alert(err.detail || "Không thể chuyển phương thức thanh toán.");
      }
    } catch (e: any) {
      alert("Lỗi khi kết nối: " + (e.message || "Unknown"));
    } finally {
      setIsSwitchingCod(false);
    }
  };

  const handleCancelOrder = async (orderCode: string) => {
    if (!confirm("Bạn có chắc chắn muốn hủy đơn hàng này không? Tồn kho thuốc sẽ được giải phóng ngay lập tức.")) return;
    setIsCancellingOrder(true);
    try {
      const res = await fetch(`/api/v1/payments/orders/${orderCode}/cancel`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...getAuthHeaders() },
        body: JSON.stringify({ reason: "Khách hàng yêu cầu hủy đơn qua trang Tài khoản" }),
      });
      if (res.ok) {
        reloadOrders();
        if (selectedOrder) {
          setSelectedOrder({ ...selectedOrder, order_status: "CANCELLED" });
        }
      } else {
        const err = await res.json();
        alert(err.detail || "Không thể hủy đơn hàng.");
      }
    } catch (e: any) {
      alert("Lỗi khi kết nối: " + (e.message || "Unknown"));
    } finally {
      setIsCancellingOrder(false);
    }
  };

  const handleOpenPayOS = async (orderCode: string) => {
    try {
      const returnUrl = typeof window !== "undefined" ? `${window.location.origin}/checkout/result?order_code=${encodeURIComponent(orderCode)}` : "";
      const res = await fetch("/api/v1/payments/payos/create", {
        method: "POST",
        headers: { "Content-Type": "application/json", ...getAuthHeaders() },
        body: JSON.stringify({
          order_code: orderCode,
          return_url: returnUrl,
        }),
      });
      const data = await res.json();
      if (res.ok && data?.checkout_url) {
        window.location.href = data.checkout_url;
      } else {
        alert(data?.detail || "Không thể tạo liên kết thanh toán payOS");
      }
    } catch (e: any) {
      alert("Lỗi kết nối cổng payOS: " + (e?.message || "Unknown error"));
    }
  };

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50 text-slate-600 text-sm">
        Đang tải thông tin thành viên H4CARE...
      </div>
    );
  }

  if (!user) {
    return null;
  }

  // Loyalty tier computation
  const points = user.points || 0;
  const tier = user.isAdmin
    ? {
        label: "Quản trị viên",
        badgeClass: "bg-indigo-50 text-indigo-700 border-indigo-200",
        nextTarget: 0,
        nextLabel: "",
      }
    : points >= 300
    ? {
        label: "Hội viên VIP",
        badgeClass: "bg-amber-100/80 text-amber-800 border-amber-300 font-extrabold shadow-xs shadow-amber-200",
        nextTarget: 500,
        nextLabel: "Kim Cương",
      }
    : points >= 100
    ? {
        label: "Hội viên Thân thiết",
        badgeClass: "bg-brand-blue-50 text-brand-blue-700 border-brand-blue-200 font-bold",
        nextTarget: 300,
        nextLabel: "Hội viên VIP",
      }
    : {
        label: "Tân hội viên",
        badgeClass: "bg-emerald-50 text-emerald-700 border-emerald-200 font-bold",
        nextTarget: 100,
        nextLabel: "Hội viên Thân thiết",
      };

  const handleSaveProfile = (e: React.FormEvent) => {
    e.preventDefault();
    if (user) {
      const updatedUser = {
        ...user,
        fullName: editName.trim() || user.fullName,
        email: editEmail.trim() || user.email,
      };
      try {
        localStorage.setItem("h4care_auth_session", JSON.stringify(updatedUser));
      } catch (err) {
        console.warn("Failed to persist updated profile", err);
      }
      setSaveSuccess(true);
      setTimeout(() => {
        setSaveSuccess(false);
        setIsEditingProfile(false);
        window.location.reload();
      }, 700);
    }
  };

  return (
    <div className="min-h-screen flex flex-col bg-[#f4f6f9]">
      <Header />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8 sm:py-10">
        
        {/* Admin Direct Banner for Admin Users */}
        {user.isAdmin && (
          <div className="bg-gradient-to-r from-slate-900 via-brand-blue-900 to-slate-900 text-white rounded-2xl p-6 border border-brand-blue-500/30 shadow-xs mb-6 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
            <div className="flex items-center gap-3.5">
              <div className="w-12 h-12 rounded-xl bg-white/10 text-white border border-white/20 flex items-center justify-center font-black">
                <ShieldCheck className="w-6 h-6 text-brand-cyan-400" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="text-base font-extrabold tracking-tight text-white">
                    Tài Khoản Quản Trị Viên (PharmaTrust Data Hub)
                  </h2>
                  <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-400/20 text-amber-300 border border-amber-400/30">
                    ADMIN
                  </span>
                </div>
                <p className="text-xs text-slate-300 mt-0.5">
                  Bạn có đầy đủ quyền quản trị dữ liệu thuốc, duyệt cào tự động và quản lý đơn hàng.
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2.5 w-full sm:w-auto">
              <button
                type="button"
                onClick={() => redirectToAdminPortal()}
                className="flex-1 sm:flex-initial px-4 py-2.5 rounded-xl bg-brand-blue-600 hover:bg-brand-blue-700 text-white font-bold text-xs flex items-center justify-center gap-1.5 transition-all shadow-xs"
              >
                <span>Vào Cổng Admin</span>
                <ExternalLink className="w-3.5 h-3.5" />
              </button>
              <Link
                href="/admin"
                className="px-3.5 py-2.5 rounded-xl bg-white/10 hover:bg-white/20 text-white font-semibold text-xs transition-colors border border-white/15"
              >
                Portal nội bộ
              </Link>
            </div>
          </div>
        )}

        {/* Top Member Card */}
        <div className="bg-white rounded-2xl p-6 sm:p-8 border border-slate-200 shadow-xs mb-6">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
            <div className="flex items-center gap-4">
              <div className="w-16 h-16 rounded-2xl bg-brand-blue-600 text-white flex items-center justify-center text-2xl font-black shadow-xs">
                {user.fullName ? user.fullName.charAt(0).toUpperCase() : "A"}
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h1 className="text-xl sm:text-2xl font-black text-slate-900 tracking-tight">
                    {user.fullName}
                  </h1>
                  <span className={`px-2.5 py-0.5 rounded-full text-xs border ${tier.badgeClass}`}>
                    {tier.label}
                  </span>
                </div>
                <p className="text-xs text-slate-500 mt-1 flex items-center gap-3">
                  {user.phone && (
                    <span className="flex items-center gap-1">
                      <Phone className="w-3.5 h-3.5 text-slate-400" />
                      <span>{user.phone}</span>
                    </span>
                  )}
                  {user.email && (
                    <span className="flex items-center gap-1">
                      <Mail className="w-3.5 h-3.5 text-slate-400" />
                      <span>{user.email}</span>
                    </span>
                  )}
                </p>
              </div>
            </div>

            {/* Points & Loyalty with Progress */}
            <div className="flex flex-col gap-2 bg-brand-blue-50/70 p-4 rounded-xl border border-brand-blue-100 sm:self-center w-full sm:w-72 shadow-xs">
              <div className="flex items-center justify-between">
                <div>
                  <span className="text-[11px] text-slate-500 block font-medium">Điểm tích lũy H4Care</span>
                  <span className="text-lg font-black text-brand-blue-700">{points} điểm</span>
                </div>
                <div className="w-9 h-9 rounded-xl bg-brand-blue-600 text-white flex items-center justify-center font-bold text-sm shadow-xs">
                  <Award className="w-5 h-5" />
                </div>
              </div>
              {tier.nextTarget > 0 && (
                <div className="space-y-1">
                  <div className="w-full bg-slate-200/80 h-1.5 rounded-full overflow-hidden">
                    <div
                      className="bg-brand-blue-600 h-full rounded-full transition-all"
                      style={{ width: `${Math.min(100, (points / tier.nextTarget) * 100)}%` }}
                    />
                  </div>
                  <p className="text-[10px] text-slate-500 flex justify-between">
                    <span>{points}/{tier.nextTarget} điểm</span>
                    <span>Lên {tier.nextLabel}</span>
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Dashboard Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6 items-start">
          
          {/* Left Navigation Sidebar */}
          <div className="lg:col-span-1 bg-white rounded-2xl p-4 border border-slate-200 shadow-xs h-fit space-y-1.5 sticky top-24">
            <button
              type="button"
              onClick={() => handleTabClick("profile")}
              className={`w-full flex items-center justify-between p-3 rounded-xl font-bold text-xs transition-all text-left ${
                activeTab === "profile"
                  ? "bg-brand-blue-50 text-brand-blue-700 border border-brand-blue-200/80 shadow-xs"
                  : "text-slate-700 hover:bg-slate-50 font-medium"
              }`}
            >
              <div className="flex items-center gap-2.5">
                <User className="w-4 h-4" />
                <span>Hồ sơ thành viên</span>
              </div>
              <ChevronRight className={`w-4 h-4 ${activeTab === "profile" ? "text-brand-blue-600" : "text-slate-400"}`} />
            </button>

            <button
              type="button"
              onClick={() => {
                handleTabClick("profile");
                setIsEditingProfile(true);
              }}
              className="w-full flex items-center justify-between p-3 rounded-xl text-slate-700 hover:bg-slate-50 font-medium text-xs transition-colors text-left"
            >
              <div className="flex items-center gap-2.5">
                <Edit3 className="w-4 h-4 text-slate-500" />
                <span>Chỉnh sửa thông tin cá nhân</span>
              </div>
              <ChevronRight className="w-4 h-4 text-slate-400" />
            </button>

            <button
              type="button"
              onClick={() => handleTabClick("addresses")}
              className={`w-full flex items-center justify-between p-3 rounded-xl font-bold text-xs transition-all text-left ${
                activeTab === "addresses"
                  ? "bg-brand-blue-50 text-brand-blue-700 border border-brand-blue-200/80 shadow-xs"
                  : "text-slate-700 hover:bg-slate-50 font-medium"
              }`}
            >
              <div className="flex items-center gap-2.5">
                <MapPin className="w-4 h-4 text-brand-blue-600" />
                <span>Sổ địa chỉ của tôi</span>
              </div>
              <ChevronRight className={`w-4 h-4 ${activeTab === "addresses" ? "text-brand-blue-600" : "text-slate-400"}`} />
            </button>

            {user.isAdmin && (
              <button
                type="button"
                onClick={() => redirectToAdminPortal()}
                className="w-full text-left flex items-center justify-between p-3 rounded-xl text-indigo-700 bg-indigo-50/70 hover:bg-indigo-100/70 font-bold text-xs transition-colors border border-indigo-200/60"
              >
                <div className="flex items-center gap-2.5">
                  <ShieldCheck className="w-4 h-4 text-indigo-600" />
                  <span>Cổng Quản Trị Hệ Thống</span>
                </div>
                <ExternalLink className="w-3.5 h-3.5 text-indigo-500" />
              </button>
            )}

            <button
              type="button"
              onClick={() => handleTabClick("prescriptions")}
              className={`w-full flex items-center justify-between p-3 rounded-xl font-bold text-xs transition-all text-left ${
                activeTab === "prescriptions"
                  ? "bg-brand-blue-50 text-brand-blue-700 border border-brand-blue-200/80 shadow-xs"
                  : "text-slate-700 hover:bg-slate-50 font-medium"
              }`}
            >
              <div className="flex items-center gap-2.5">
                <HeartPulse className="w-4 h-4 text-slate-500" />
                <span>Toa thuốc điện tử của tôi</span>
              </div>
              <ChevronRight className={`w-4 h-4 ${activeTab === "prescriptions" ? "text-brand-blue-600" : "text-slate-400"}`} />
            </button>

            <button
              type="button"
              onClick={() => handleTabClick("orders")}
              className={`w-full flex items-center justify-between p-3 rounded-xl font-bold text-xs transition-all text-left ${
                activeTab === "orders"
                  ? "bg-brand-blue-50 text-brand-blue-700 border border-brand-blue-200/80 shadow-xs"
                  : "text-slate-700 hover:bg-slate-50 font-medium"
              }`}
            >
              <div className="flex items-center gap-2.5">
                <Package className="w-4 h-4 text-slate-500" />
                <span>Lịch sử đơn hàng ({orderTotal || orders.length})</span>
              </div>
              <ChevronRight className={`w-4 h-4 ${activeTab === "orders" ? "text-brand-blue-600" : "text-slate-400"}`} />
            </button>

            <button
              type="button"
              onClick={() => handleTabClick("returns")}
              className={`w-full flex items-center justify-between p-3 rounded-xl font-bold text-xs transition-all text-left ${
                activeTab === "returns"
                  ? "bg-brand-blue-50 text-brand-blue-700 border border-brand-blue-200/80 shadow-xs"
                  : "text-slate-700 hover:bg-slate-50 font-medium"
              }`}
            >
              <div className="flex items-center gap-2.5">
                <RotateCcw className="w-4 h-4 text-brand-blue-600" />
                <span>Đổi trả & Hoàn tiền</span>
              </div>
              <ChevronRight className={`w-4 h-4 ${activeTab === "returns" ? "text-brand-blue-600" : "text-slate-400"}`} />
            </button>

            <div className="pt-3 mt-2 border-t border-slate-100">
              <button
                onClick={() => {
                  logout();
                  router.push("/login");
                }}
                className="w-full flex items-center gap-2.5 p-3 rounded-xl text-rose-600 hover:bg-rose-50 font-bold text-xs transition-colors text-left"
              >
                <LogOut className="w-4 h-4" />
                <span>Đăng xuất tài khoản</span>
              </button>
            </div>
          </div>

          {/* Right Main Content: Each tab displays ONLY its corresponding panel */}
          <div className="lg:col-span-3 min-w-0">
            
            {/* TAB 1: Hồ sơ thành viên */}
            {activeTab === "profile" && (
              <div id="profile" className="bg-white rounded-2xl p-6 sm:p-8 border border-slate-200 shadow-xs space-y-6">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-slate-100 gap-3">
                  <div>
                    <h2 className="font-extrabold text-lg text-slate-900 flex items-center gap-2">
                      <User className="w-5 h-5 text-brand-blue-600" />
                      <span>Hồ sơ thông tin thành viên</span>
                    </h2>
                    <p className="text-xs text-slate-500 mt-0.5">
                      Quản lý thông tin định danh cá nhân, tài khoản bảo mật và quyền lợi hội viên H4Care
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => setIsEditingProfile(true)}
                    className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-brand-blue-600 hover:bg-brand-blue-700 text-white text-xs font-bold transition-all shadow-xs shrink-0 self-start sm:self-auto"
                  >
                    <Edit3 className="w-4 h-4" />
                    <span>Chỉnh sửa thông tin</span>
                  </button>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="p-4 rounded-xl bg-slate-50 border border-slate-200/80 space-y-1">
                    <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">Họ và tên</span>
                    <p className="text-sm font-bold text-slate-900">{user.fullName || "Chưa cập nhật"}</p>
                  </div>
                  <div className="p-4 rounded-xl bg-slate-50 border border-slate-200/80 space-y-1">
                    <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">Số điện thoại</span>
                    <div className="flex items-center gap-2">
                      <p className="text-sm font-bold text-slate-900">{user.phone || "Chưa cập nhật"}</p>
                      <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
                        Đã xác thực
                      </span>
                    </div>
                  </div>
                  <div className="p-4 rounded-xl bg-slate-50 border border-slate-200/80 space-y-1">
                    <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">Email liên hệ</span>
                    <p className="text-sm font-bold text-slate-900">{user.email || "Chưa cập nhật"}</p>
                  </div>
                  <div className="p-4 rounded-xl bg-slate-50 border border-slate-200/80 space-y-1">
                    <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">Hạng hội viên</span>
                    <div className="flex items-center gap-2">
                      <span className={`px-2.5 py-0.5 rounded-full text-xs border ${tier.badgeClass}`}>
                        {tier.label}
                      </span>
                      <span className="text-xs font-bold text-brand-blue-700">({points} điểm)</span>
                    </div>
                  </div>
                </div>

                <div>
                  <h3 className="text-xs font-bold text-slate-700 uppercase tracking-wider mb-3">Truy cập nhanh danh mục</h3>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    <button
                      type="button"
                      onClick={() => handleTabClick("addresses")}
                      className="p-4 rounded-xl border border-slate-200 hover:border-brand-blue-300 hover:bg-brand-blue-50/40 transition-all text-left group"
                    >
                      <div className="flex items-center justify-between mb-1">
                        <MapPin className="w-5 h-5 text-brand-blue-600" />
                        <ChevronRight className="w-4 h-4 text-slate-400 group-hover:text-brand-blue-600" />
                      </div>
                      <p className="font-bold text-xs text-slate-900 group-hover:text-brand-blue-700">Sổ địa chỉ</p>
                      <p className="text-[11px] text-slate-500">Quản lý địa chỉ giao thuốc tận nơi</p>
                    </button>

                    <button
                      type="button"
                      onClick={() => handleTabClick("orders")}
                      className="p-4 rounded-xl border border-slate-200 hover:border-brand-blue-300 hover:bg-brand-blue-50/40 transition-all text-left group"
                    >
                      <div className="flex items-center justify-between mb-1">
                        <Package className="w-5 h-5 text-brand-blue-600" />
                        <ChevronRight className="w-4 h-4 text-slate-400 group-hover:text-brand-blue-600" />
                      </div>
                      <p className="font-bold text-xs text-slate-900 group-hover:text-brand-blue-700">Lịch sử đơn hàng</p>
                      <p className="text-[11px] text-slate-500">{orderTotal || orders.length} đơn hàng đã thực hiện</p>
                    </button>

                    <button
                      type="button"
                      onClick={() => handleTabClick("returns")}
                      className="p-4 rounded-xl border border-slate-200 hover:border-brand-blue-300 hover:bg-brand-blue-50/40 transition-all text-left group"
                    >
                      <div className="flex items-center justify-between mb-1">
                        <RotateCcw className="w-5 h-5 text-brand-blue-600" />
                        <ChevronRight className="w-4 h-4 text-slate-400 group-hover:text-brand-blue-600" />
                      </div>
                      <p className="font-bold text-xs text-slate-900 group-hover:text-brand-blue-700">Đổi trả & Hoàn tiền</p>
                      <p className="text-[11px] text-slate-500">Xem tiến độ hoàn hàng & hoàn tiền</p>
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* TAB 2: Customer Address Book V2 Section */}
            {activeTab === "addresses" && (
              <div id="addresses" className="bg-white rounded-2xl p-6 sm:p-8 border border-slate-200 shadow-xs">
                <CustomerAddressBook
                  userName={user.fullName}
                  userPhone={user.phone}
                />
              </div>
            )}

            {/* TAB 3: Health Records / Prescriptions Section */}
            {activeTab === "prescriptions" && (
              <div id="prescriptions" className="bg-white rounded-2xl p-6 sm:p-8 border border-slate-200 shadow-xs">
                <div className="flex items-center justify-between mb-4 pb-3 border-b border-slate-100">
                  <div>
                    <h2 className="font-extrabold text-base text-slate-900">Toa thuốc điện tử gần nhất</h2>
                    <p className="text-xs text-slate-500">Lưu trữ đơn thuốc của bạn và gia đình chuẩn GPP</p>
                  </div>
                  <span className="text-xs font-bold text-brand-blue-700 bg-brand-blue-50 px-2.5 py-1 rounded-lg border border-brand-blue-100">
                    1 Toa thuốc đang dùng
                  </span>
                </div>

                {/* Sample Prescription Card */}
                <div className="p-4 rounded-xl bg-slate-50 border border-slate-200/80 space-y-3">
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-bold text-slate-900">Đơn thuốc: Điều trị cảm cúm & tăng đề kháng</span>
                    <span className="text-slate-500">Kê ngày: 20/09/2026</span>
                  </div>
                  <div className="text-xs text-slate-600 space-y-1">
                    <p>• Paracetamol 500mg (Hộp 50 viên) - Uống sau ăn</p>
                    <p>• Vitamin C 1000mg Tuýp sủi - 1 viên/ngày</p>
                  </div>
                  <div className="pt-2 border-t border-slate-200/60 flex items-center justify-between text-[11px]">
                    <span className="text-emerald-700 font-bold flex items-center gap-1">
                      <ShieldCheck className="w-3.5 h-3.5" /> Dược sĩ tư vấn: DS. Nguyễn Minh Anh
                    </span>
                    <Link href="/prescription" className="text-brand-blue-600 font-bold hover:underline">
                      Tư vấn lại trực tuyến
                    </Link>
                  </div>
                </div>
              </div>
            )}

            {/* TAB 4: Orders Section - Authenticated Customer Orders */}
            {activeTab === "orders" && (
              <div id="orders" className="bg-white rounded-2xl p-6 sm:p-8 border border-slate-200 shadow-xs">
              <div className="flex items-center justify-between mb-4 pb-3 border-b border-slate-100">
                <div>
                  <h2 className="font-extrabold text-base text-slate-900">Đơn hàng gần đây</h2>
                  <p className="text-xs text-slate-500">
                    Lịch sử đơn hàng cá nhân gắn liền với tài khoản của bạn.
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  <button
                    type="button"
                    onClick={() => reloadOrders()}
                    className="p-1.5 rounded-lg text-slate-400 hover:text-brand-blue-600 hover:bg-slate-100 transition-colors"
                    title="Làm mới lịch sử đơn hàng"
                  >
                    <RefreshCw className={`w-3.5 h-3.5 ${ordersStatus === "loading" ? "animate-spin text-brand-blue-600" : ""}`} />
                  </button>
                  <Link href="/products" className="text-xs font-bold text-brand-blue-600 hover:underline">
                    Mua sắm tiếp →
                  </Link>
                </div>
              </div>

              {/* Search bar & Filter tabs */}
              <div className="space-y-3 mb-4">
                <form onSubmit={handleSearchSubmit} className="flex items-center gap-2">
                  <div className="relative flex-1">
                    <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                    <input
                      type="text"
                      value={orderSearchTerm}
                      onChange={(e) => setOrderSearchTerm(e.target.value)}
                      placeholder="Tìm theo mã đơn (ORD-...) hoặc tên thuốc..."
                      className="w-full pl-9 pr-8 py-2 rounded-xl bg-slate-50 border border-slate-200 text-xs text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-brand-blue-500/20 focus:border-brand-blue-500 transition-all"
                    />
                    {orderSearchTerm && (
                      <button
                        type="button"
                        onClick={handleClearSearch}
                        className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 p-0.5 rounded-full"
                        title="Xóa tìm kiếm"
                      >
                        <X className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>
                  <button
                    type="submit"
                    className="px-3.5 py-2 bg-brand-blue-600 hover:bg-brand-blue-700 text-white rounded-xl text-xs font-bold transition-colors shrink-0 shadow-xs"
                  >
                    Tìm kiếm
                  </button>
                </form>

                {/* Filter Tabs */}
                <div className="flex items-center gap-1.5 overflow-x-auto pb-1 text-xs scrollbar-none">
                  {[
                    { key: "ALL", label: "Tất cả" },
                    { key: "PENDING", label: "Chờ xử lý" },
                    { key: "CONFIRMED", label: "Đã xác nhận" },
                    { key: "SHIPPING", label: "Đang giao" },
                    { key: "COMPLETED", label: "Hoàn thành" },
                    { key: "CANCELLED", label: "Đã hủy" },
                  ].map((tab) => (
                    <button
                      key={tab.key}
                      type="button"
                      onClick={() => handleStatusFilterChange(tab.key)}
                      className={`px-3 py-1.5 rounded-lg font-bold transition-all whitespace-nowrap shrink-0 ${
                        orderStatusFilter === tab.key
                          ? "bg-brand-blue-600 text-white shadow-xs"
                          : "bg-slate-100 hover:bg-slate-200 text-slate-600"
                      }`}
                    >
                      {tab.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* 1. Trạng thái Đang tải (Loading) */}
              {ordersStatus === "loading" ? (
                <div className="p-8 text-center text-xs text-slate-500 flex flex-col items-center justify-center gap-2">
                  <RefreshCw className="w-5 h-5 animate-spin text-brand-blue-600" />
                  <span>Đang tải lịch sử đơn hàng của bạn...</span>
                </div>
              ) : ordersStatus === "error" ? (
                /* 2. Trạng thái Lỗi (Error with Retry) */
                <div className="p-6 rounded-xl bg-rose-50/80 border border-rose-200/80 text-center space-y-3">
                  <AlertCircle className="w-8 h-8 text-rose-500 mx-auto" />
                  <div>
                    <p className="text-xs font-bold text-rose-700">Không thể tải danh sách đơn hàng</p>
                    <p className="text-[11px] text-rose-600 mt-0.5">{ordersError || "Đã xảy ra sự cố khi kết nối tới máy chủ."}</p>
                  </div>
                  <button
                    type="button"
                    onClick={() => reloadOrders()}
                    className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-brand-blue-600 hover:bg-brand-blue-700 text-white text-xs font-bold transition-colors shadow-xs"
                  >
                    <RefreshCw className="w-3.5 h-3.5" />
                    <span>Thử lại</span>
                  </button>
                </div>
              ) : orders.length > 0 ? (
                /* 3. Trạng thái Có dữ liệu (Success - Data) */
                <div className="space-y-3">
                  <div className="space-y-3">
                    {orders.map((order) => (
                      <div
                        key={order.order_code}
                        onClick={() => setSelectedOrder(order)}
                        className="p-4 rounded-xl bg-slate-50 hover:bg-slate-100/80 border border-slate-200/80 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 cursor-pointer transition-colors group"
                        title="Bấm để xem chi tiết đơn hàng"
                      >
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="font-bold text-xs text-slate-900 group-hover:text-brand-blue-600 transition-colors">
                              Đơn hàng #{order.order_code}
                            </span>
                            <span className="text-[10px] text-slate-400">
                              {order.created_at ? formatDateTimeVN(order.created_at) : "—"}
                            </span>
                          </div>
                          <p className="text-[11px] text-slate-600 mt-0.5">
                            {order.items_count} sản phẩm • Tổng tiền:{" "}
                            <strong className="text-brand-blue-600">{order.total_amount.toLocaleString("vi-VN")} đ</strong>
                          </p>
                          {order.items && order.items.length > 0 && (
                            <p className="text-[10.5px] text-slate-500 mt-1 italic line-clamp-1">
                              {order.items.map((it) => `${it.product_name} (x${it.quantity})`).join(", ")}
                            </p>
                          )}
                        </div>
                        <div className="flex items-center gap-2 self-end sm:self-center">
                          <span className="px-2.5 py-1 rounded-full bg-emerald-50 text-emerald-800 text-xs font-bold border border-emerald-200">
                            {order.order_status === "PENDING"
                              ? "Chờ xử lý"
                              : order.order_status === "CONFIRMED"
                              ? "Đã xác nhận"
                              : order.order_status === "SHIPPING"
                              ? "Đang giao 2h"
                              : order.order_status === "COMPLETED"
                              ? "Đã hoàn thành"
                              : order.order_status === "CANCELLED"
                              ? "Đã hủy"
                              : order.order_status}
                          </span>
                          <ChevronRight className="w-4 h-4 text-slate-400 group-hover:text-slate-600" />
                        </div>
                      </div>
                    ))}
                  </div>

                  {/* Pagination Bar */}
                  {orderTotalPages > 1 && (
                    <div className="pt-3 mt-3 border-t border-slate-100 flex flex-col sm:flex-row items-center justify-between gap-2.5 text-xs text-slate-500">
                      <span>
                        Hiển thị trang <strong className="text-slate-800">{orderPage}</strong> / {orderTotalPages} ({orderTotal} đơn hàng)
                      </span>
                      <div className="flex items-center gap-1">
                        <button
                          type="button"
                          onClick={() => handlePageChange(orderPage - 1)}
                          disabled={orderPage <= 1}
                          className="px-2.5 py-1.5 rounded-lg border border-slate-200 hover:bg-slate-50 disabled:opacity-40 disabled:hover:bg-transparent font-medium flex items-center gap-1 transition-colors"
                        >
                          <ChevronLeft className="w-3.5 h-3.5" />
                          <span>Trước</span>
                        </button>
                        {Array.from({ length: orderTotalPages }, (_, i) => i + 1)
                          .filter((p) => p === 1 || p === orderTotalPages || Math.abs(p - orderPage) <= 1)
                          .map((p, idx, arr) => (
                            <React.Fragment key={p}>
                              {idx > 0 && arr[idx - 1] !== p - 1 && <span className="px-1 text-slate-300">...</span>}
                              <button
                                type="button"
                                onClick={() => handlePageChange(p)}
                                className={`w-7 h-7 rounded-lg font-bold text-xs transition-colors ${
                                  p === orderPage
                                    ? "bg-brand-blue-600 text-white shadow-xs"
                                    : "hover:bg-slate-100 text-slate-700"
                                }`}
                              >
                                {p}
                              </button>
                            </React.Fragment>
                          ))}
                        <button
                          type="button"
                          onClick={() => handlePageChange(orderPage + 1)}
                          disabled={orderPage >= orderTotalPages}
                          className="px-2.5 py-1.5 rounded-lg border border-slate-200 hover:bg-slate-50 disabled:opacity-40 disabled:hover:bg-transparent font-medium flex items-center gap-1 transition-colors"
                        >
                          <span>Sau</span>
                          <ChevronRight className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                /* 4. Trạng thái Rỗng (Success - Empty) */
                <div className="p-6 rounded-xl bg-slate-50 border border-slate-200/60 text-center space-y-2">
                  <ShoppingBag className="w-8 h-8 text-slate-300 mx-auto" />
                  <p className="text-xs font-semibold text-slate-600">
                    {orderSearchTerm || orderStatusFilter !== "ALL"
                      ? "Không tìm thấy đơn hàng nào phù hợp với bộ lọc."
                      : "Bạn chưa có đơn hàng nào."}
                  </p>
                  <p className="text-[11px] text-slate-400">
                    {orderSearchTerm || orderStatusFilter !== "ALL"
                      ? "Vui lòng thử tìm với từ khóa khác hoặc xóa bộ lọc."
                      : "Mỗi tài khoản lưu trữ lịch sử đơn hàng và điểm tích lũy hoàn toàn độc lập."}
                  </p>
                  {orderSearchTerm || orderStatusFilter !== "ALL" ? (
                    <button
                      type="button"
                      onClick={() => {
                        setOrderSearchTerm("");
                        setOrderStatusFilter("ALL");
                        setOrderPage(1);
                        reloadOrders(1, "ALL", "");
                      }}
                      className="inline-block mt-2 px-3.5 py-2 rounded-xl bg-slate-200 hover:bg-slate-300 text-slate-700 text-xs font-bold transition-colors shadow-xs"
                    >
                      Xóa bộ lọc tìm kiếm
                    </button>
                  ) : (
                    <Link
                      href="/products"
                      className="inline-block mt-2 px-3.5 py-2 rounded-xl bg-brand-blue-600 hover:bg-brand-blue-700 active:bg-brand-blue-800 text-white text-xs font-bold transition-colors shadow-xs"
                    >
                      Xem danh mục thuốc
                    </Link>
                  )}
                </div>
              )}
            </div>
            )}

            {/* TAB 5: Customer Returns & Refunds Section */}
            {activeTab === "returns" && (
              <div id="returns" className="bg-white rounded-2xl p-6 sm:p-8 border border-slate-200 shadow-xs">
                <CustomerReturnsSection
                  userPhone={user.phone}
                  userName={user.fullName}
                />
              </div>
            )}

          </div>

        </div>

      </main>

      {/* POPUP: Order Details Modal */}
      {selectedOrder && (
        <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-xs flex items-center justify-center p-4 animate-in fade-in duration-150">
          <div className="bg-white rounded-2xl max-w-lg w-full p-6 border border-slate-200 shadow-xl relative max-h-[90vh] overflow-y-auto">
            <button
              onClick={() => setSelectedOrder(null)}
              className="absolute top-5 right-5 p-1.5 rounded-full hover:bg-slate-100 text-slate-400 hover:text-slate-600 transition-colors"
            >
              <X className="w-5 h-5" />
            </button>

            <div className="flex items-center gap-2 mb-1">
              <span className="w-3 h-3 rounded-full bg-emerald-500 animate-pulse" />
              <h3 className="text-base font-black text-slate-900">Chi tiết đơn hàng #{selectedOrder.order_code}</h3>
            </div>
            <p className="text-xs text-slate-500 mb-3">
              Thời gian đặt đơn: <span className="font-semibold text-slate-700">{formatDateTimeVN(selectedOrder.created_at)}</span>
            </p>

            {/* Tracking Progress */}
            <div className="p-3.5 bg-brand-blue-50 border border-brand-blue-100 rounded-xl mb-4">
              <div className="flex items-center justify-between text-xs font-bold text-brand-blue-700 mb-2">
                <span className="flex items-center gap-1.5">
                  <Truck className="w-4 h-4" /> Vận chuyển Siêu Tốc 2H
                </span>
                <span>
                  {selectedOrder.order_status === "COMPLETED"
                    ? "Đã giao thành công"
                    : "Đang tiến hành"}
                </span>
              </div>
              <div className="w-full bg-brand-blue-100 h-2 rounded-full overflow-hidden flex gap-1">
                <div className="bg-brand-blue-600 h-full flex-1 rounded-full" />
                <div className="bg-brand-blue-600 h-full flex-1 rounded-full" />
                <div className={`h-full flex-1 rounded-full ${selectedOrder.order_status === "COMPLETED" ? "bg-brand-blue-600" : "bg-brand-blue-200"}`} />
              </div>
            </div>

            {/* Shipping address & buyer */}
            <div className="p-3.5 bg-slate-50 border border-slate-200/70 rounded-xl mb-4 text-xs space-y-1.5">
              <p className="text-slate-700">
                <strong>Người nhận:</strong> {selectedOrder.customer_name} ({selectedOrder.customer_phone})
              </p>
              <p className="text-slate-700 flex items-start gap-1">
                <MapPin className="w-3.5 h-3.5 text-slate-400 shrink-0 mt-0.5" />
                <span><strong>Địa chỉ giao:</strong> {selectedOrder.shipping_address}</span>
              </p>
              <div className="flex items-center justify-between pt-1 border-t border-slate-200/60">
                <span className="text-slate-500">
                  <strong>Thanh toán:</strong> {selectedOrder.payment_method === "COD" ? "Thanh toán khi nhận hàng (COD)" : selectedOrder.payment_method}
                </span>
                <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold border ${
                  selectedOrder.payment_status === "PAID"
                    ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                    : selectedOrder.payment_status === "FAILED"
                    ? "bg-rose-50 text-rose-700 border-rose-200"
                    : selectedOrder.payment_status === "REFUNDED"
                    ? "bg-purple-50 text-purple-700 border-purple-200"
                    : "bg-amber-50 text-amber-700 border-amber-200"
                }`}>
                  {selectedOrder.payment_status === "PAID"
                    ? "ĐÃ THANH TOÁN (PAID)"
                    : selectedOrder.payment_status === "FAILED"
                    ? "THANH TOÁN THẤT BẠI"
                    : selectedOrder.payment_status === "REFUNDED"
                    ? "ĐÃ HOÀN TIỀN"
                    : "CHỜ THANH TOÁN (PENDING)"}
                </span>
              </div>
            </div>

            {/* Payment Transactions & Retry Box */}
            <div className="p-3.5 bg-blue-50/50 border border-blue-200/70 rounded-xl mb-4 text-xs space-y-2">
              <div className="flex items-center justify-between text-blue-900 font-bold">
                <span className="flex items-center gap-1.5">
                  <ShieldCheck className="w-3.5 h-3.5 text-brand-blue-600" />
                  <span>Lịch sử giao dịch & Cổng thanh toán</span>
                </span>
                {loadingPaymentData && <RefreshCw className="w-3.5 h-3.5 animate-spin text-slate-400" />}
              </div>

              {orderPaymentData?.transactions && orderPaymentData.transactions.length > 0 ? (
                <div className="space-y-1.5 divide-y divide-blue-100 max-h-32 overflow-y-auto pr-1">
                  {orderPaymentData.transactions.map((t: any) => (
                    <div key={t.id} className="pt-1.5 flex items-center justify-between text-[11px]">
                      <div>
                        <span className="font-mono font-bold text-slate-800">{t.transaction_code}</span>
                        <span className="text-slate-400 block text-[10px]">
                          Cổng: {t.provider} • {t.created_at ? formatDateTimeVN(t.created_at) : "—"}
                        </span>
                      </div>
                      <div className="text-right">
                        <span className="font-bold text-slate-900">{Number(t.amount).toLocaleString("vi-VN")} đ</span>
                        <span className={`block text-[10px] font-bold ${
                          t.status === "SUCCESS"
                            ? "text-emerald-600"
                            : t.status === "FAILED"
                            ? "text-rose-600"
                            : t.status === "CANCELLED"
                            ? "text-slate-400"
                            : "text-amber-600"
                        }`}>
                          {t.status}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-[11px] text-slate-500">Chưa ghi nhận lịch sử giao dịch trực tuyến.</p>
              )}

              {/* Retry & Payment Options if Order is still PENDING */}
              {selectedOrder.payment_status !== "PAID" && selectedOrder.order_status !== "CANCELLED" && (
                <div className="pt-2 border-t border-blue-200/60 space-y-2">
                  <span className="text-[11px] font-bold text-slate-700 block">Thanh toán hoặc đổi phương thức:</span>
                  <div>
                    <button
                      type="button"
                      onClick={() => handleOpenPayOS(selectedOrder.order_code)}
                      className="w-full py-2.5 px-3 rounded-xl bg-brand-blue-600 hover:bg-brand-blue-700 text-white font-bold text-xs flex items-center justify-center gap-2 transition-colors shadow-xs cursor-pointer"
                    >
                      <span className="w-4 h-4 rounded-full bg-white text-brand-blue-600 flex items-center justify-center text-[9px] font-black shrink-0">P</span>
                      <span>Thanh toán Cổng payOS (QR Ngân hàng / Napas 247)</span>
                    </button>
                  </div>

                  <div className="flex items-center gap-2 pt-1">
                    <button
                      type="button"
                      disabled={isSwitchingCod}
                      onClick={() => handleSwitchToCod(selectedOrder.order_code)}
                      className="flex-1 py-1.5 px-2 rounded-lg bg-emerald-50 hover:bg-emerald-100 text-emerald-800 border border-emerald-200 text-[10.5px] font-bold flex items-center justify-center gap-1 transition-colors cursor-pointer"
                    >
                      <Banknote className="w-3 h-3 text-emerald-600" />
                      <span>{isSwitchingCod ? "Đang đổi..." : "Chuyển sang trả khi nhận (COD)"}</span>
                    </button>

                    <button
                      type="button"
                      disabled={isCancellingOrder}
                      onClick={() => handleCancelOrder(selectedOrder.order_code)}
                      className="py-1.5 px-2 rounded-lg bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 text-[10.5px] font-bold transition-colors cursor-pointer"
                    >
                      {isCancellingOrder ? "Đang hủy..." : "Hủy đơn & trả kho"}
                    </button>
                  </div>
                </div>
              )}
            </div>

            {/* Items Breakdown */}
            <div className="space-y-2 mb-4">
              <h4 className="text-xs font-bold text-slate-700 uppercase tracking-wider">Danh mục sản phẩm ({selectedOrder.items?.length || 0})</h4>
              <div className="divide-y divide-slate-100 max-h-48 overflow-y-auto pr-1">
                {selectedOrder.items && selectedOrder.items.map((it, idx) => (
                  <div key={idx} className="py-2 flex items-center justify-between text-xs">
                    <div>
                      <p className="font-bold text-slate-800">{it.product_name}</p>
                      <p className="text-slate-400 text-[11px]">Số lượng: x{it.quantity} • Đơn giá: {it.price.toLocaleString("vi-VN")} đ</p>
                    </div>
                    <span className="font-bold text-slate-900">{it.subtotal.toLocaleString("vi-VN")} đ</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Total and actions */}
            <div className="pt-3 border-t border-slate-100 flex items-center justify-between mb-4">
              <span className="text-xs text-slate-500 font-medium">Tổng thanh toán:</span>
              <span className="text-base font-black text-brand-blue-600">{selectedOrder.total_amount.toLocaleString("vi-VN")} đ</span>
            </div>

            {/* Return / Exchange Action */}
            {selectedOrder.order_status !== "CANCELLED" && (
              <button
                type="button"
                onClick={() => {
                  const code = selectedOrder.order_code;
                  setSelectedOrder(null);
                  setReturnWizardOrderCode(code);
                }}
                className="w-full mb-3 py-2.5 rounded-xl bg-amber-50 hover:bg-amber-100 text-amber-900 border border-amber-300 font-bold text-xs flex items-center justify-center gap-2 transition-colors shadow-xs"
              >
                <RotateCcw className="w-4 h-4 text-amber-700" />
                <span>Yêu cầu Đổi / Trả Hàng (Bảo hành 7 ngày)</span>
              </button>
            )}

            <div className="flex items-center gap-2">
              <Link
                href="/prescription"
                className="flex-1 py-2.5 rounded-xl bg-brand-blue-50 text-brand-blue-700 hover:bg-brand-blue-100 font-bold text-xs flex items-center justify-center gap-1.5 transition-colors"
              >
                <Stethoscope className="w-3.5 h-3.5" />
                <span>Tư vấn trực tuyến về đơn này</span>
              </Link>
              <button
                onClick={() => setSelectedOrder(null)}
                className="px-4 py-2.5 rounded-xl bg-slate-900 text-white font-bold text-xs hover:bg-slate-800 transition-colors"
              >
                Đóng
              </button>
            </div>
          </div>
        </div>
      )}

      {/* POPUP: Edit Profile Modal */}
      {isEditingProfile && (
        <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-xs flex items-center justify-center p-4 animate-in fade-in duration-150">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 border border-slate-200 shadow-xl relative">
            <button
              onClick={() => setIsEditingProfile(false)}
              className="absolute top-5 right-5 p-1.5 rounded-full hover:bg-slate-100 text-slate-400 hover:text-slate-600 transition-colors"
            >
              <X className="w-5 h-5" />
            </button>

            <h3 className="text-base font-black text-slate-900 mb-1">Cập nhật hồ sơ thành viên</h3>
            <p className="text-xs text-slate-500 mb-4">Thông tin lưu trữ riêng biệt theo tài khoản của bạn.</p>

            {saveSuccess && (
              <div className="p-3 bg-emerald-50 text-emerald-700 text-xs font-bold rounded-xl mb-3 flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                <span>Cập nhật hồ sơ thành công!</span>
              </div>
            )}

            <form onSubmit={handleSaveProfile} className="space-y-3.5 text-xs">
              <div>
                <label className="block font-semibold text-slate-700 mb-1">Họ và tên</label>
                <input
                  type="text"
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                  className="w-full h-10 px-3 border border-slate-200 rounded-xl focus:outline-none focus:border-brand-blue-500 focus:ring-1 focus:ring-brand-blue-500 font-semibold text-slate-900"
                  required
                />
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">Số điện thoại (Cố định theo tài khoản)</label>
                <input
                  type="text"
                  value={user.phone || ""}
                  disabled
                  className="w-full h-10 px-3 border border-slate-200 bg-slate-50 rounded-xl text-slate-400 cursor-not-allowed"
                />
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">Email nhận đơn thuốc & hóa đơn</label>
                <input
                  type="email"
                  value={editEmail}
                  onChange={(e) => setEditEmail(e.target.value)}
                  className="w-full h-10 px-3 border border-slate-200 rounded-xl focus:outline-none focus:border-brand-blue-500 focus:ring-1 focus:ring-brand-blue-500 font-semibold text-slate-900"
                />
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">Địa chỉ nhận thuốc mặc định</label>
                <textarea
                  value={editAddress}
                  onChange={(e) => setEditAddress(e.target.value)}
                  rows={2}
                  className="w-full p-2.5 border border-slate-200 rounded-xl focus:outline-none focus:border-brand-blue-500 focus:ring-1 focus:ring-brand-blue-500 font-semibold text-slate-900"
                />
              </div>

              <div className="pt-2 flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setIsEditingProfile(false)}
                  className="flex-1 py-2.5 rounded-xl border border-slate-200 text-slate-700 font-bold hover:bg-slate-50 transition-colors"
                >
                  Hủy
                </button>
                <button
                  type="submit"
                  className="flex-1 py-2.5 rounded-xl bg-brand-blue-600 hover:bg-brand-blue-700 active:bg-brand-blue-800 text-white font-bold transition-colors shadow-xs"
                >
                  Lưu thay đổi
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Return Wizard Modal */}
      {returnWizardOrderCode && (
        <ReturnWizardModal
          orderCode={returnWizardOrderCode}
          customerPhone={user.phone}
          onClose={() => setReturnWizardOrderCode(null)}
          onSuccess={() => {
            setReturnWizardOrderCode(null);
            // Auto reload to see new return in CustomerReturnsSection
            window.location.hash = "returns";
          }}
        />
      )}

      <Footer />
    </div>
  );
}
