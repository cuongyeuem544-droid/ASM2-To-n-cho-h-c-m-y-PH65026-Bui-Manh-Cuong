"use client";

import React, { useEffect, useState } from "react";
import {
  X,
  Truck,
  RotateCcw,
  CheckCircle2,
  Clock,
  AlertCircle,
  FileText,
  MapPin,
  Building2,
  ShieldCheck,
  Send,
  Ban,
  Camera,
  Upload,
  Trash2,
  RefreshCw,
  Image as ImageIcon,
  AlertTriangle,
  Eye,
} from "lucide-react";

interface CustomerEvidenceRequest {
  id: number;
  request_code: string;
  return_code?: string;
  return_item_id?: number | null;
  product_name?: string | null;
  reason: string;
  instructions: string;
  required_image_count: number;
  status: string;
  requested_at?: string;
  expires_at?: string;
  remaining_seconds?: number;
  is_expired?: boolean;
  submitted_at?: string;
  customer_note?: string;
  evidences?: Array<{
    id: number;
    file_url: string;
    file_name: string;
    created_at?: string;
  }>;
}

interface ReturnDetail {
  id: number;
  return_code: string;
  order_code: string;
  request_type: string;
  status: string;
  reason_code: string;
  reason_text: string;
  customer_note?: string;
  customer_name: string;
  customer_phone: string;
  carrier_name?: string;
  tracking_code?: string;
  customer_visible_note?: string;
  rejection_reason?: string;
  requested_at?: string;
  approved_at?: string;
  received_at?: string;
  inspected_at?: string;
  active_evidence_request?: CustomerEvidenceRequest | null;
  items: Array<{
    id: number;
    product_name: string;
    requested_quantity: number;
    accepted_quantity: number;
    inspected_condition: string;
    restock_destination?: string;
  }>;
  timeline: Array<{
    id: number;
    from_status?: string;
    to_status: string;
    actor_name: string;
    actor_role: string;
    note?: string;
    created_at?: string;
  }>;
  evidences: Array<{
    id: number;
    file_url: string;
    file_name: string;
  }>;
  refunds: Array<{
    refund_code: string;
    refund_amount: number;
    refund_method: string;
    status: string;
    bank_transfer_ref?: string;
    gateway_trans_id?: string;
  }>;
  exchanges: Array<{
    exchange_code: string;
    price_difference: number;
    status: string;
    carrier_name?: string;
    tracking_code?: string;
  }>;
}

interface ReturnDetailModalProps {
  returnCode: string;
  phoneVerify?: string;
  onClose: () => void;
  onRefreshNeeded: () => void;
}

const STATUS_LABELS: Record<string, { label: string; badge: string }> = {
  REQUESTED: { label: "Chờ xem xét", badge: "bg-amber-50 text-amber-800 border-amber-200" },
  REVIEWING: { label: "Đang xem xét", badge: "bg-blue-50 text-blue-800 border-blue-200" },
  NEEDS_CUSTOMER_INFO: { label: "Cần bổ sung thông tin", badge: "bg-purple-50 text-purple-800 border-purple-200" },
  APPROVED: { label: "Đã duyệt", badge: "bg-emerald-50 text-emerald-800 border-emerald-200" },
  WAITING_CUSTOMER_EVIDENCE: { label: "Yêu cầu bổ sung hình ảnh", badge: "bg-amber-100 text-amber-900 border-amber-300 font-bold" },
  WAITING_MANAGER_REVIEW: { label: "Đã nộp ảnh - Chờ kho duyệt", badge: "bg-sky-100 text-sky-900 border-sky-300 font-bold" },
  CANCELLED_EVIDENCE_TIMEOUT: { label: "Hết hạn bổ sung ảnh", badge: "bg-rose-50 text-rose-800 border-rose-200" },
  WAITING_CUSTOMER_RETURN: { label: "Chờ bạn gửi hàng về kho", badge: "bg-amber-100 text-amber-900 border-amber-300 font-bold" },
  RETURN_IN_TRANSIT: { label: "Hàng đang trên đường về kho", badge: "bg-sky-50 text-sky-800 border-sky-200" },
  RECEIVED: { label: "Kho đã nhận hàng", badge: "bg-indigo-50 text-indigo-800 border-indigo-200" },
  INSPECTING: { label: "Dược sĩ đang kiểm định", badge: "bg-purple-50 text-purple-800 border-purple-200" },
  INSPECTION_COMPLETED: { label: "Đã kiểm định chất lượng", badge: "bg-teal-50 text-teal-800 border-teal-200" },
  REFUND_PENDING: { label: "Chờ hoàn tiền", badge: "bg-amber-50 text-amber-800 border-amber-200" },
  EXCHANGE_PENDING: { label: "Chờ xuất đơn đổi hàng", badge: "bg-blue-50 text-blue-800 border-blue-200" },
  REFUNDED: { label: "Đã hoàn tiền", badge: "bg-emerald-100 text-emerald-900 border-emerald-300 font-extrabold" },
  EXCHANGED: { label: "Đã xuất hàng đổi", badge: "bg-emerald-100 text-emerald-900 border-emerald-300 font-extrabold" },
  REJECTED: { label: "Từ chối yêu cầu", badge: "bg-rose-50 text-rose-800 border-rose-200" },
  CANCELLED: { label: "Đã hủy", badge: "bg-slate-100 text-slate-700 border-slate-200" },
  CLOSED: { label: "Đã hoàn tất & Đóng", badge: "bg-slate-100 text-slate-800 border-slate-300" },
};

function formatCountdown(totalSeconds: number): string {
  if (totalSeconds <= 0) return "00:00:00 (Đã hết hạn)";
  const days = Math.floor(totalSeconds / 86400);
  const hours = Math.floor((totalSeconds % 86400) / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;

  if (days > 0) {
    return `${days} ngày ${hours.toString().padStart(2, "0")} giờ ${minutes.toString().padStart(2, "0")} phút`;
  }
  return `${hours.toString().padStart(2, "0")} giờ ${minutes.toString().padStart(2, "0")} phút ${seconds.toString().padStart(2, "0")} giây`;
}

function getAuthToken(): string | null {
  if (typeof window === "undefined") return null;
  return (
    localStorage.getItem("pharmatrust_access_token") ||
    localStorage.getItem("pharmatrust_token") ||
    localStorage.getItem("h4care_auth_token") ||
    localStorage.getItem("access_token")
  );
}

function getGuestToken(orderCode?: string): string | null {
  if (typeof window === "undefined") return null;
  if (orderCode) {
    const specific = localStorage.getItem(`h4care_order_token_${orderCode}`);
    if (specific) return specific;
  }
  return localStorage.getItem("h4care_latest_order_token");
}

export function ReturnDetailModal({
  returnCode,
  phoneVerify,
  onClose,
  onRefreshNeeded,
}: ReturnDetailModalProps) {
  const [detail, setDetail] = useState<ReturnDetail | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Shipping form
  const [carrierName, setCarrierName] = useState<string>("Giao Hàng Tiết Kiệm (GHTK)");
  const [trackingCode, setTrackingCode] = useState<string>("");
  const [submittingShip, setSubmittingShip] = useState<boolean>(false);

  // Cancel action
  const [cancelling, setCancelling] = useState<boolean>(false);

  // Customer Evidence Request State
  const [evidenceSlots, setEvidenceSlots] = useState<Array<{ file_url: string; file_name: string; file_size?: number } | null>>([]);
  const [customerEvidenceNote, setCustomerEvidenceNote] = useState<string>("");
  const [uploadingSlotIndex, setUploadingSlotIndex] = useState<number | null>(null);
  const [submittingEvidence, setSubmittingEvidence] = useState<boolean>(false);
  const [evidenceActionError, setEvidenceActionError] = useState<string | null>(null);
  const [evidenceActionSuccess, setEvidenceActionSuccess] = useState<string | null>(null);
  const [countdownSeconds, setCountdownSeconds] = useState<number>(0);

  useEffect(() => {
    const activeReq = detail?.active_evidence_request;
    if (activeReq && activeReq.status === "OPEN") {
      setEvidenceSlots(Array.from({ length: activeReq.required_image_count }, () => null));
      setCountdownSeconds(activeReq.remaining_seconds ?? 0);
    }
  }, [detail?.active_evidence_request]);

  useEffect(() => {
    if (countdownSeconds <= 0) return;
    const interval = setInterval(() => {
      setCountdownSeconds((prev) => {
        if (prev <= 1) {
          clearInterval(interval);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(interval);
  }, [countdownSeconds > 0]);

  const handleUploadSlot = async (slotIndex: number, e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    e.target.value = "";
    setEvidenceActionError(null);
    setEvidenceActionSuccess(null);

    // Max 10MB
    if (file.size > 10 * 1024 * 1024) {
      setEvidenceActionError("Dung lượng file vượt quá giới hạn cho phép (tối đa 10MB).");
      return;
    }

    // Allowed image types
    const allowed = [".jpg", ".jpeg", ".png", ".webp"];
    const ext = file.name.substring(file.name.lastIndexOf(".")).toLowerCase();
    if (!allowed.includes(ext)) {
      setEvidenceActionError(`Định dạng file '${ext || file.name}' không được hỗ trợ. Chỉ chấp nhận JPG, PNG, WEBP.`);
      return;
    }

    setUploadingSlotIndex(slotIndex);
    try {
      const formData = new FormData();
      formData.append("file", file);

      const token = getAuthToken();
      const headers: Record<string, string> = {};
      if (token) headers["Authorization"] = `Bearer ${token}`;

      const res = await fetch("/api/v1/returns/upload-evidence", {
        method: "POST",
        headers,
        body: formData,
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Không thể tải ảnh lên máy chủ.");
      }

      setEvidenceSlots((prev) => {
        const next = [...prev];
        next[slotIndex] = {
          file_url: data.file_url,
          file_name: data.file_name || file.name,
          file_size: data.file_size || file.size,
        };
        return next;
      });
    } catch (err: any) {
      setEvidenceActionError(err.message || "Lỗi khi tải ảnh lên.");
    } finally {
      setUploadingSlotIndex(null);
    }
  };

  const handleRemoveSlot = (slotIndex: number) => {
    setEvidenceSlots((prev) => {
      const next = [...prev];
      next[slotIndex] = null;
      return next;
    });
  };

  const handleSubmitEvidence = async () => {
    const activeReq = detail?.active_evidence_request;
    if (!activeReq) return;

    const validImages = evidenceSlots.filter((s): s is { file_url: string; file_name: string; file_size?: number } => s !== null);
    if (validImages.length !== activeReq.required_image_count) {
      setEvidenceActionError(`Bạn bắt buộc phải tải lên đủ ${activeReq.required_image_count} hình ảnh theo yêu cầu.`);
      return;
    }

    if (countdownSeconds <= 0) {
      setEvidenceActionError("Yêu cầu đã hết thời hạn 3 ngày. Không thể gửi hình ảnh.");
      return;
    }

    setSubmittingEvidence(true);
    setEvidenceActionError(null);
    setEvidenceActionSuccess(null);

    try {
      const token = getAuthToken();
      const headers: Record<string, string> = { "Content-Type": "application/json" };
      if (token) headers["Authorization"] = `Bearer ${token}`;

      const res = await fetch(`/api/v1/returns/${encodeURIComponent(returnCode)}/evidence/submit`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          images: validImages,
          customer_note: customerEvidenceNote.trim() || undefined,
          phone_verify: phoneVerify || detail?.customer_phone || undefined,
        }),
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Gửi bằng chứng thất bại.");
      }

      setEvidenceActionSuccess("Đã gửi hình ảnh bằng chứng thành công! Quản lý kho sẽ xem xét hồ sơ của bạn.");
      fetchDetail();
      onRefreshNeeded();
    } catch (err: any) {
      setEvidenceActionError(err.message || "Lỗi khi gửi bằng chứng.");
    } finally {
      setSubmittingEvidence(false);
    }
  };

  const fetchDetail = () => {
    setLoading(true);
    const token = getAuthToken();
    const guestToken = getGuestToken();
    const headers: Record<string, string> = {};
    if (token) headers["Authorization"] = `Bearer ${token}`;
    if (guestToken) headers["X-Order-Token"] = guestToken;

    const query = phoneVerify ? `?phone_verify=${encodeURIComponent(phoneVerify)}` : "";
    fetch(`/api/v1/returns/${encodeURIComponent(returnCode)}${query}`, { headers })
      .then((res) => {
        if (!res.ok) throw new Error("Không thể tải chi tiết yêu cầu đổi/trả.");
        return res.json();
      })
      .then((data: ReturnDetail) => setDetail(data))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchDetail();
  }, [returnCode, phoneVerify]);

  const handleUpdateShipping = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!trackingCode.trim()) return;

    const token = getAuthToken();
    const guestToken = getGuestToken();
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (token) headers["Authorization"] = `Bearer ${token}`;
    if (guestToken) headers["X-Order-Token"] = guestToken;

    setSubmittingShip(true);
    try {
      const res = await fetch(`/api/v1/returns/${encodeURIComponent(returnCode)}/shipping`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          carrier_name: carrierName.trim(),
          tracking_code: trackingCode.trim(),
        }),
      });
      if (!res.ok) throw new Error("Cập nhật vận đơn thất bại.");
      alert("Cập nhật mã vận đơn thành công. Kho H4CARE sẽ đón kiện hàng của bạn.");
      fetchDetail();
      onRefreshNeeded();
    } catch (err: any) {
      alert(err.message || "Lỗi khi cập nhật");
    } finally {
      setSubmittingShip(false);
    }
  };

  const handleCancelRequest = async () => {
    if (!confirm("Bạn có chắc chắn muốn hủy yêu cầu đổi trả này?")) return;

    const token = getAuthToken();
    const guestToken = getGuestToken();
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (token) headers["Authorization"] = `Bearer ${token}`;
    if (guestToken) headers["X-Order-Token"] = guestToken;

    setCancelling(true);
    try {
      const res = await fetch(`/api/v1/returns/${encodeURIComponent(returnCode)}/cancel`, {
        method: "POST",
        headers,
        body: JSON.stringify({ reason: "Khách hàng hủy trên giao diện" }),
      });
      if (!res.ok) throw new Error("Hủy yêu cầu thất bại.");
      alert("Đã hủy yêu cầu đổi trả.");
      fetchDetail();
      onRefreshNeeded();
    } catch (err: any) {
      alert(err.message || "Lỗi khi hủy");
    } finally {
      setCancelling(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4 overflow-y-auto animate-in fade-in duration-150">
      <div className="bg-white rounded-3xl max-w-2xl w-full p-6 sm:p-8 border border-slate-200 shadow-2xl relative my-8 max-h-[90vh] overflow-y-auto">
        <button
          onClick={onClose}
          className="absolute top-5 right-5 p-2 rounded-full hover:bg-slate-100 text-slate-400 hover:text-slate-700 transition-colors"
        >
          <X className="w-5 h-5" />
        </button>

        {loading ? (
          <div className="py-12 text-center text-xs text-slate-500">Đang tải chi tiết hồ sơ đổi trả...</div>
        ) : error ? (
          <div className="p-4 rounded-2xl bg-rose-50 border border-rose-200 text-rose-700 text-xs flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        ) : detail ? (
          <div className="space-y-6">
            {/* Header info */}
            <div>
              <div className="flex flex-wrap items-center gap-2 mb-1.5">
                <span className="text-base font-black text-slate-900 tracking-tight">
                  Phiếu {detail.request_type === "EXCHANGE" ? "Đổi hàng" : "Trả hàng"} #{detail.return_code}
                </span>
                <span
                  className={`px-2.5 py-0.5 rounded-full text-[11px] font-bold border ${
                    STATUS_LABELS[detail.status]?.badge || "bg-slate-100 text-slate-800 border-slate-200"
                  }`}
                >
                  {STATUS_LABELS[detail.status]?.label || detail.status}
                </span>
              </div>
              <p className="text-xs text-slate-500">
                Đơn hàng gốc: <strong className="text-slate-800">#{detail.order_code}</strong> • Người yêu cầu:{" "}
                <strong>{detail.customer_name}</strong> ({detail.customer_phone})
              </p>
            </div>

            {/* Note from pharmacy or rejection reason */}
            {detail.status === "REJECTED" && detail.rejection_reason && (
              <div className="p-4 rounded-2xl bg-rose-50 border border-rose-200 text-rose-800 text-xs space-y-1">
                <div className="flex items-center gap-1.5 font-bold">
                  <Ban className="w-4 h-4 text-rose-600" />
                  <span>Lý do từ chối yêu cầu</span>
                </div>
                <p className="text-rose-700 leading-relaxed">{detail.rejection_reason}</p>
              </div>
            )}

            {detail.customer_visible_note && detail.status !== "REJECTED" && (
              <div className="p-4 rounded-2xl bg-blue-50/70 border border-blue-200 text-blue-900 text-xs space-y-1">
                <div className="flex items-center gap-1.5 font-bold text-blue-800">
                  <ShieldCheck className="w-4 h-4 text-brand-blue-600" />
                  <span>Hướng dẫn từ Nhà thuốc H4CARE</span>
                </div>
                <p className="text-blue-800 whitespace-pre-line leading-relaxed">{detail.customer_visible_note}</p>
              </div>
            )}

            {/* CARD 1: YÊU CẦU BỔ SUNG ẢNH ĐANG MỞ (OPEN) */}
            {detail.active_evidence_request && detail.active_evidence_request.status === "OPEN" && (
              <div className="p-5 rounded-2xl bg-amber-50/90 border-2 border-amber-300 shadow-xs space-y-4">
                {/* Header & Countdown */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-amber-200/80 pb-3">
                  <div className="flex items-center gap-2">
                    <div className="p-2 rounded-xl bg-amber-500 text-white shadow-xs">
                      <Camera className="w-4 h-4" />
                    </div>
                    <div>
                      <h4 className="text-xs font-black text-amber-950 uppercase tracking-wide">
                        Quản Lý Kho Yêu Cầu Bổ Sung Hình Ảnh
                      </h4>
                      <p className="text-[11px] text-amber-800">
                        Vui lòng tải lên đúng <strong>{detail.active_evidence_request.required_image_count} hình ảnh</strong> theo hướng dẫn bên dưới
                      </p>
                    </div>
                  </div>

                  {/* Countdown timer */}
                  <div
                    className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-bold shrink-0 ${
                      countdownSeconds <= 3600 * 12
                        ? "bg-rose-100 text-rose-900 border border-rose-300 animate-pulse"
                        : "bg-white text-amber-900 border border-amber-300 shadow-2xs"
                    }`}
                  >
                    <Clock className="w-3.5 h-3.5 text-amber-700" />
                    <span>Hạn: {formatCountdown(countdownSeconds)}</span>
                  </div>
                </div>

                {/* Details */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs bg-white/80 p-3.5 rounded-xl border border-amber-200">
                  <div>
                    <span className="font-bold text-amber-950">Lý do yêu cầu:</span>
                    <p className="text-amber-900 mt-0.5">{detail.active_evidence_request.reason}</p>
                  </div>
                  <div>
                    <span className="font-bold text-amber-950">Hướng dẫn chụp ảnh:</span>
                    <p className="text-amber-900 mt-0.5">{detail.active_evidence_request.instructions}</p>
                  </div>
                  {detail.active_evidence_request.product_name && (
                    <div className="sm:col-span-2 pt-2 border-t border-amber-100">
                      <span className="font-bold text-amber-950">Sản phẩm cần chụp:</span>{" "}
                      <span className="text-slate-800 font-semibold">{detail.active_evidence_request.product_name}</span>
                    </div>
                  )}
                </div>

                {countdownSeconds <= 0 ? (
                  <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl text-xs text-rose-800 font-medium">
                    ⚠️ Thời hạn 3 ngày bổ sung hình ảnh đã kết thúc. Yêu cầu đổi trả đã tự động hủy theo quy định.
                  </div>
                ) : (
                  <>
                    {/* Upload Slots */}
                    <div>
                      <label className="block text-[11px] font-bold text-amber-950 mb-2">
                        Tải lên đủ {detail.active_evidence_request.required_image_count} hình ảnh:
                      </label>
                      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                        {Array.from({ length: detail.active_evidence_request.required_image_count }).map((_, idx) => {
                          const uploaded = evidenceSlots[idx];
                          const isUploading = uploadingSlotIndex === idx;

                          return (
                            <div
                              key={idx}
                              className={`relative p-3 rounded-xl border-2 border-dashed flex flex-col items-center justify-center text-center transition-all min-h-[140px] bg-white ${
                                uploaded
                                  ? "border-emerald-400 bg-emerald-50/20"
                                  : "border-amber-300 hover:border-amber-400"
                              }`}
                            >
                              {uploaded ? (
                                <div className="w-full h-full flex flex-col items-center justify-between space-y-2">
                                  <div className="relative w-full h-24 rounded-lg overflow-hidden border border-slate-200 bg-slate-100">
                                    <img
                                      src={uploaded.file_url}
                                      alt={`Slot ${idx + 1}`}
                                      className="w-full h-full object-cover"
                                    />
                                    <span className="absolute top-1 left-1 px-1.5 py-0.5 rounded text-[10px] font-bold bg-black/60 text-white">
                                      Ảnh {idx + 1}
                                    </span>
                                  </div>
                                  <div className="flex items-center gap-1.5 w-full">
                                    <label className="flex-1 py-1 px-2 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 text-[11px] font-bold cursor-pointer transition-colors text-center">
                                      <input
                                        type="file"
                                        accept="image/jpeg,image/png,image/webp"
                                        onChange={(e) => handleUploadSlot(idx, e)}
                                        className="hidden"
                                      />
                                      Thay thế
                                    </label>
                                    <button
                                      type="button"
                                      onClick={() => handleRemoveSlot(idx)}
                                      className="p-1 rounded-lg bg-rose-50 hover:bg-rose-100 text-rose-600 transition-colors"
                                      title="Xóa ảnh này"
                                    >
                                      <Trash2 className="w-3.5 h-3.5" />
                                    </button>
                                  </div>
                                </div>
                              ) : (
                                <label className="w-full h-full flex flex-col items-center justify-center cursor-pointer py-3">
                                  <input
                                    type="file"
                                    accept="image/jpeg,image/png,image/webp"
                                    onChange={(e) => handleUploadSlot(idx, e)}
                                    disabled={isUploading}
                                    className="hidden"
                                  />
                                  {isUploading ? (
                                    <div className="flex flex-col items-center gap-1.5 text-amber-700">
                                      <RefreshCw className="w-5 h-5 animate-spin" />
                                      <span className="text-[11px] font-bold">Đang tải ảnh {idx + 1}...</span>
                                    </div>
                                  ) : (
                                    <div className="flex flex-col items-center gap-1.5 text-amber-800">
                                      <div className="p-2 rounded-full bg-amber-100 text-amber-700">
                                        <Upload className="w-4 h-4" />
                                      </div>
                                      <span className="text-xs font-bold">Chọn Ảnh {idx + 1}</span>
                                      <span className="text-[10px] text-slate-400">JPG, PNG, WEBP &lt; 10MB</span>
                                    </div>
                                  )}
                                </label>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    </div>

                    {/* Customer Note */}
                    <div>
                      <label className="block text-[11px] font-bold text-amber-950 mb-1">
                        Ghi chú phản hồi cho Quản lý kho (Tùy chọn):
                      </label>
                      <textarea
                        rows={2}
                        value={customerEvidenceNote}
                        onChange={(e) => setCustomerEvidenceNote(e.target.value)}
                        placeholder="VD: Tôi đã chụp rõ vết rách bao bì và số lô in trên đáy hộp..."
                        className="w-full px-3 py-2 rounded-xl border border-amber-300 text-xs bg-white focus:outline-amber-500"
                      />
                    </div>

                    {evidenceActionError && (
                      <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-center gap-2">
                        <AlertCircle className="w-4 h-4 shrink-0 text-rose-600" />
                        <span>{evidenceActionError}</span>
                      </div>
                    )}

                    {evidenceActionSuccess && (
                      <div className="p-3 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs flex items-center gap-2">
                        <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-600" />
                        <span>{evidenceActionSuccess}</span>
                      </div>
                    )}

                    {/* Submit button */}
                    <button
                      type="button"
                      onClick={handleSubmitEvidence}
                      disabled={
                        submittingEvidence ||
                        evidenceSlots.filter(Boolean).length !== detail.active_evidence_request.required_image_count
                      }
                      className="w-full py-2.5 rounded-xl bg-amber-600 hover:bg-amber-700 text-white font-bold text-xs flex items-center justify-center gap-2 transition-colors shadow-sm disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      <Send className="w-3.5 h-3.5" />
                      <span>
                        {submittingEvidence
                          ? "Đang gửi hình ảnh..."
                          : `Gửi bổ sung hình ảnh (${evidenceSlots.filter(Boolean).length}/${detail.active_evidence_request.required_image_count} ảnh)`}
                      </span>
                    </button>
                  </>
                )}
              </div>
            )}

            {/* CARD 2: ĐÃ NỘP ẢNH - CHỜ KHO DUYỆT (SUBMITTED / WAITING_MANAGER_REVIEW) */}
            {detail.active_evidence_request &&
              (detail.active_evidence_request.status === "SUBMITTED" || detail.status === "WAITING_MANAGER_REVIEW") && (
                <div className="p-4 rounded-2xl bg-sky-50 border border-sky-200 text-sky-950 space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 font-bold text-xs text-sky-900">
                      <CheckCircle2 className="w-4 h-4 text-sky-600" />
                      <span>Bạn đã gửi bổ sung hình ảnh thành công</span>
                    </div>
                    <span className="text-[10px] text-sky-700 font-medium">
                      {detail.active_evidence_request.submitted_at
                        ? new Date(detail.active_evidence_request.submitted_at).toLocaleString("vi-VN")
                        : "Đang chờ kho xem xét"}
                    </span>
                  </div>
                  <p className="text-xs text-sky-800">
                    Hồ sơ đang ở trạng thái <strong>Chờ Quản lý kho xem xét bằng chứng</strong>. Nhà thuốc H4CARE sẽ kiểm tra và phản hồi trong thời gian sớm nhất.
                  </p>
                  {detail.active_evidence_request.customer_note && (
                    <div className="text-[11px] text-sky-800 bg-white/70 p-2.5 rounded-xl border border-sky-100">
                      <strong>Ghi chú của bạn:</strong> &ldquo;{detail.active_evidence_request.customer_note}&rdquo;
                    </div>
                  )}
                  {detail.active_evidence_request.evidences && detail.active_evidence_request.evidences.length > 0 && (
                    <div>
                      <span className="block text-[11px] font-bold text-sky-900 mb-1.5">Ảnh bằng chứng đã nộp:</span>
                      <div className="flex gap-2 flex-wrap">
                        {detail.active_evidence_request.evidences.map((ev) => (
                          <a
                            key={ev.id}
                            href={ev.file_url}
                            target="_blank"
                            rel="noreferrer"
                            className="block w-20 h-20 rounded-xl overflow-hidden border border-sky-200 shadow-2xs hover:opacity-90"
                          >
                            <img src={ev.file_url} alt={ev.file_name} className="w-full h-full object-cover" />
                          </a>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}

            {/* CARD 3: QUÁ HẠN 3 NGÀY (CANCELLED_EVIDENCE_TIMEOUT) */}
            {(detail.status === "CANCELLED_EVIDENCE_TIMEOUT" || detail.active_evidence_request?.status === "EXPIRED") && (
              <div className="p-4 rounded-2xl bg-rose-50 border border-rose-200 text-rose-900 space-y-1">
                <div className="flex items-center gap-2 font-bold text-xs text-rose-800">
                  <AlertTriangle className="w-4 h-4 text-rose-600" />
                  <span>Hết hạn bổ sung hình ảnh (Quá thời hạn 3 ngày)</span>
                </div>
                <p className="text-xs text-rose-700 leading-relaxed">
                  Yêu cầu đổi trả này đã bị hủy tự động do quá thời hạn 3 ngày bạn chưa cung cấp đủ hình ảnh bằng chứng theo yêu cầu của Quản lý kho.
                </p>
                <p className="text-[11px] text-rose-600 font-medium">
                  Lưu ý: Đơn mua hàng gốc <strong>#{detail.order_code}</strong> của bạn vẫn được bảo toàn nguyên vẹn.
                </p>
              </div>
            )}

            {/* Gửi hàng về kho (Nếu trạng thái WAITING_CUSTOMER_RETURN) */}
            {(detail.status === "WAITING_CUSTOMER_RETURN" || detail.status === "APPROVED") && (
              <div className="p-5 rounded-2xl bg-amber-50/80 border border-amber-200 space-y-4">
                <div className="flex items-center gap-2 text-xs font-bold text-amber-900">
                  <Truck className="w-4 h-4 text-amber-700" />
                  <span>Cập nhật mã vận đơn gửi hàng về kho</span>
                </div>

                <div className="p-3.5 bg-white rounded-xl border border-amber-200/80 text-xs text-slate-700 space-y-1">
                  <p className="font-bold text-slate-900 flex items-center gap-1">
                    <Building2 className="w-3.5 h-3.5 text-brand-blue-600" /> Địa chỉ kho tiếp nhận:
                  </p>
                  <p className="text-slate-600">Trung tâm Dược phẩm H4CARE - Kho Tổng GSP</p>
                  <p className="text-slate-600">Số 123 Đường Nguyễn Trãi, Thanh Xuân, Hà Nội</p>
                  <p className="text-slate-500 text-[11px]">Người nhận: Tiếp nhận Đổi trả H4CARE (ĐT: 0988.123.456)</p>
                </div>

                <form onSubmit={handleUpdateShipping} className="space-y-3">
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div>
                      <label className="block text-[11px] font-bold text-slate-700 mb-1">Đơn vị vận chuyển</label>
                      <input
                        type="text"
                        value={carrierName}
                        onChange={(e) => setCarrierName(e.target.value)}
                        placeholder="VD: GHTK, ViettelPost, J&T..."
                        className="w-full px-3 py-2 rounded-xl border border-slate-300 text-xs bg-white focus:outline-brand-blue-600"
                        required
                      />
                    </div>
                    <div>
                      <label className="block text-[11px] font-bold text-slate-700 mb-1">Mã vận đơn theo dõi</label>
                      <input
                        type="text"
                        value={trackingCode}
                        onChange={(e) => setTrackingCode(e.target.value)}
                        placeholder="VD: GHTK123456789"
                        className="w-full px-3 py-2 rounded-xl border border-slate-300 text-xs bg-white font-mono uppercase focus:outline-brand-blue-600"
                        required
                      />
                    </div>
                  </div>
                  <button
                    type="submit"
                    disabled={submittingShip}
                    className="w-full py-2.5 rounded-xl bg-amber-600 hover:bg-amber-700 text-white font-bold text-xs flex items-center justify-center gap-1.5 transition-colors shadow-xs disabled:opacity-50"
                  >
                    <Send className="w-3.5 h-3.5" />
                    <span>{submittingShip ? "Đang cập nhật..." : "Xác nhận đã gửi hàng cho bưu tá"}</span>
                  </button>
                </form>
              </div>
            )}

            {/* Vận đơn hiện tại */}
            {detail.tracking_code && (
              <div className="p-3.5 bg-slate-50 border border-slate-200/80 rounded-xl flex items-center justify-between text-xs">
                <div>
                  <span className="text-slate-500">Đơn vị vận chuyển:</span>{" "}
                  <strong className="text-slate-800">{detail.carrier_name || "Giao hàng"}</strong>
                </div>
                <div>
                  <span className="text-slate-500">Mã vận đơn:</span>{" "}
                  <code className="font-bold text-brand-blue-600 bg-brand-blue-50 px-2 py-0.5 rounded border border-brand-blue-100">
                    {detail.tracking_code}
                  </code>
                </div>
              </div>
            )}

            {/* Danh sách sản phẩm */}
            <div>
              <h3 className="text-xs font-bold text-slate-700 uppercase tracking-wider mb-2.5">
                Danh sách sản phẩm trong yêu cầu
              </h3>
              <div className="divide-y divide-slate-100 rounded-2xl border border-slate-200 overflow-hidden">
                {detail.items.map((it) => (
                  <div key={it.id} className="p-3.5 bg-white flex items-center justify-between gap-3 text-xs">
                    <div>
                      <p className="font-bold text-slate-900">{it.product_name}</p>
                      <p className="text-slate-500 text-[11px] mt-0.5">
                        Yêu cầu: x{it.requested_quantity} • Tình trạng kiểm định:{" "}
                        <strong className="text-slate-700">{it.inspected_condition || "Chờ kiểm"}</strong>
                      </p>
                    </div>
                    {it.accepted_quantity > 0 && (
                      <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-50 text-emerald-800 border border-emerald-200">
                        Chấp nhận x{it.accepted_quantity}
                      </span>
                    )}
                  </div>
                ))}
              </div>
            </div>

            {/* Hoàn tiền (Refunds) */}
            {detail.refunds && detail.refunds.length > 0 && (
              <div>
                <h3 className="text-xs font-bold text-slate-700 uppercase tracking-wider mb-2">
                  Thông tin hoàn tiền
                </h3>
                <div className="space-y-2">
                  {detail.refunds.map((ref) => (
                    <div
                      key={ref.refund_code}
                      className="p-3.5 rounded-2xl bg-emerald-50/60 border border-emerald-200/80 flex items-center justify-between text-xs"
                    >
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-emerald-900">Mã hoàn: {ref.refund_code}</span>
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-800 font-bold">
                            {ref.status === "SUCCEEDED" ? "Hoàn tất" : ref.status}
                          </span>
                        </div>
                        {ref.bank_transfer_ref && (
                          <p className="text-[11px] text-emerald-700 mt-0.5">
                            Mã UNC ngân hàng: <code>{ref.bank_transfer_ref}</code>
                          </p>
                        )}
                      </div>
                      <span className="font-black text-sm text-emerald-800">
                        {ref.refund_amount.toLocaleString("vi-VN")} đ
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Lịch sử dòng thời gian (Timeline) */}
            <div>
              <h3 className="text-xs font-bold text-slate-700 uppercase tracking-wider mb-2.5">
                Dòng thời gian xử lý
              </h3>
              <div className="space-y-3 pl-2 border-l-2 border-slate-200">
                {detail.timeline.map((h) => (
                  <div key={h.id} className="relative pl-4 text-xs space-y-0.5">
                    <div className="absolute -left-[21px] top-1 w-2.5 h-2.5 rounded-full bg-brand-blue-500 border-2 border-white" />
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-slate-800">
                        {STATUS_LABELS[h.to_status]?.label || h.to_status}
                      </span>
                      <span className="text-[10px] text-slate-400">
                        {h.created_at ? new Date(h.created_at).toLocaleString("vi-VN") : ""}
                      </span>
                    </div>
                    {h.note && <p className="text-slate-600 text-[11px] italic">{h.note}</p>}
                    <p className="text-[10px] text-slate-400">Người cập nhật: {h.actor_name}</p>
                  </div>
                ))}
              </div>
            </div>

            {/* Actions */}
            <div className="flex items-center justify-between pt-4 border-t border-slate-100">
              {detail.status === "REQUESTED" ? (
                <button
                  type="button"
                  onClick={handleCancelRequest}
                  disabled={cancelling}
                  className="px-3.5 py-2 rounded-xl border border-rose-200 text-rose-600 font-bold text-xs hover:bg-rose-50 transition-colors disabled:opacity-50"
                >
                  {cancelling ? "Đang hủy..." : "Hủy yêu cầu này"}
                </button>
              ) : (
                <div />
              )}
              <button
                type="button"
                onClick={onClose}
                className="px-5 py-2 rounded-xl bg-slate-900 text-white font-bold text-xs hover:bg-slate-800 transition-colors"
              >
                Đóng
              </button>
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}
