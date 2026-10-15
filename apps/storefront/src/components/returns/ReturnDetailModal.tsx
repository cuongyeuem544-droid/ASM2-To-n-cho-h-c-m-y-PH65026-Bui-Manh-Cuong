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
} from "lucide-react";

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

  const fetchDetail = () => {
    setLoading(true);
    const token = typeof window !== "undefined" ? localStorage.getItem("pharmatrust_token") || localStorage.getItem("h4care_auth_token") : null;
    const guestToken = typeof window !== "undefined" ? localStorage.getItem("h4care_latest_order_token") : null;
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

    const token = typeof window !== "undefined" ? localStorage.getItem("pharmatrust_token") || localStorage.getItem("h4care_auth_token") : null;
    const guestToken = typeof window !== "undefined" ? localStorage.getItem("h4care_latest_order_token") : null;
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

    const token = typeof window !== "undefined" ? localStorage.getItem("pharmatrust_token") || localStorage.getItem("h4care_auth_token") : null;
    const guestToken = typeof window !== "undefined" ? localStorage.getItem("h4care_latest_order_token") : null;
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
