"use client";

import React, { useEffect, useState, useCallback } from "react";
import {
  RotateCcw,
  RefreshCw,
  Package,
  Truck,
  CheckCircle2,
  Clock,
  AlertCircle,
  ExternalLink,
  ChevronRight,
  ShieldCheck,
  Search,
  ArrowRight,
  PlusCircle,
} from "lucide-react";
import { ReturnDetailModal } from "./ReturnDetailModal";
import { ReturnWizardModal } from "./ReturnWizardModal";

interface ReturnItemSummary {
  id: number;
  return_code: string;
  order_code: string;
  request_type: string;
  status: string;
  reason_text: string;
  items_count: number;
  carrier_name?: string;
  tracking_code?: string;
  requested_at?: string;
  updated_at?: string;
}

interface CustomerReturnsSectionProps {
  userPhone?: string;
  userName?: string;
}

const STATUS_MAP: Record<string, { label: string; badge: string; step: number }> = {
  REQUESTED: { label: "Chờ xem xét", badge: "bg-amber-50 text-amber-800 border-amber-200", step: 1 },
  REVIEWING: { label: "Dược sĩ đang xem xét", badge: "bg-blue-50 text-blue-800 border-blue-200", step: 1 },
  NEEDS_CUSTOMER_INFO: { label: "Cần bổ sung thông tin", badge: "bg-purple-50 text-purple-800 border-purple-200", step: 1 },
  APPROVED: { label: "Đã phê duyệt", badge: "bg-emerald-50 text-emerald-800 border-emerald-200", step: 2 },
  WAITING_CUSTOMER_RETURN: { label: "Cần gửi hàng về kho", badge: "bg-orange-100 text-orange-900 border-orange-300 font-bold", step: 2 },
  RETURN_IN_TRANSIT: { label: "Đang chuyển về kho", badge: "bg-sky-50 text-sky-800 border-sky-200", step: 3 },
  RECEIVED_AT_WAREHOUSE: { label: "Đã tới kho H4Care", badge: "bg-indigo-50 text-indigo-800 border-indigo-200", step: 3 },
  INSPECTING: { label: "Dược sĩ đang thẩm định", badge: "bg-purple-50 text-purple-800 border-purple-200", step: 3 },
  REFUND_PENDING: { label: "Đang thực hiện hoàn tiền", badge: "bg-cyan-50 text-cyan-800 border-cyan-200", step: 4 },
  REFUNDED: { label: "Đã hoàn tiền", badge: "bg-emerald-100 text-emerald-900 border-emerald-300 font-bold", step: 4 },
  REPLACING: { label: "Đang đóng gói hàng đổi", badge: "bg-indigo-50 text-indigo-800 border-indigo-200", step: 4 },
  REPLACEMENT_SHIPPED: { label: "Đơn đổi đang giao", badge: "bg-blue-50 text-blue-800 border-blue-200", step: 4 },
  COMPLETED: { label: "Hoàn tất thành công", badge: "bg-emerald-100 text-emerald-900 border-emerald-300 font-bold", step: 4 },
  REJECTED: { label: "Đã từ chối", badge: "bg-rose-50 text-rose-800 border-rose-200", step: 0 },
  CANCELLED: { label: "Đã hủy", badge: "bg-slate-100 text-slate-700 border-slate-200", step: 0 },
};

export function CustomerReturnsSection({ userPhone, userName }: CustomerReturnsSectionProps) {
  const [returnsList, setReturnsList] = useState<ReturnItemSummary[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [filterTab, setFilterTab] = useState<"ALL" | "ACTIVE" | "WAITING_SHIP" | "DONE">("ALL");
  const [selectedReturnCode, setSelectedReturnCode] = useState<string | null>(null);
  const [wizardOrderCode, setWizardOrderCode] = useState<string | null>(null);
  const [manualOrderInput, setManualOrderInput] = useState<string>("");
  const [errorMsg, setErrorMsg] = useState<string>("");

  const fetchReturns = useCallback(async () => {
    if (!userPhone) {
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const token = typeof window !== "undefined"
        ? (localStorage.getItem("pharmatrust_access_token") || localStorage.getItem("pharmatrust_token") || localStorage.getItem("access_token"))
        : null;
      const headers: Record<string, string> = {};
      if (token) headers["Authorization"] = `Bearer ${token}`;

      const res = await fetch(`/api/v1/returns/my-requests?customer_phone=${encodeURIComponent(userPhone)}`, { headers });
      if (res.ok) {
        const data = await res.json();
        setReturnsList(data.returns || []);
      } else {
        setReturnsList([]);
      }
    } catch {
      setReturnsList([]);
    } finally {
      setLoading(false);
    }
  }, [userPhone]);

  useEffect(() => {
    fetchReturns();
  }, [fetchReturns]);

  const filteredReturns = returnsList.filter((item) => {
    if (filterTab === "ALL") return true;
    if (filterTab === "WAITING_SHIP") return item.status === "WAITING_CUSTOMER_RETURN";
    if (filterTab === "ACTIVE") {
      return !["COMPLETED", "REFUNDED", "REJECTED", "CANCELLED"].includes(item.status);
    }
    if (filterTab === "DONE") {
      return ["COMPLETED", "REFUNDED", "REJECTED", "CANCELLED"].includes(item.status);
    }
    return true;
  });

  const handleStartReturnFromInput = (e: React.FormEvent) => {
    e.preventDefault();
    const code = manualOrderInput.trim().toUpperCase().replace("#", "");
    if (!code) {
      setErrorMsg("Vui lòng nhập mã đơn hàng (Ví dụ: ORD-123456)");
      return;
    }
    setErrorMsg("");
    setWizardOrderCode(code);
  };

  return (
    <div className="space-y-6">
      {/* Section Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-slate-100 gap-3">
        <div>
          <div className="flex items-center gap-2">
            <RotateCcw className="w-5 h-5 text-brand-blue-600" />
            <h2 className="font-extrabold text-base sm:text-lg text-slate-900">
              Yêu Cầu Đổi Trả & Hoàn Tiền H4Care
            </h2>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Chính sách đổi trả trong 7 ngày đối với thuốc không kê đơn còn nguyên tem niêm phong GPP.
          </p>
        </div>

        <button
          onClick={() => {
            const promptCode = prompt("Nhập mã đơn hàng bạn muốn đổi / trả (ví dụ: ORD-xxxxxx):");
            if (promptCode && promptCode.trim()) {
              setWizardOrderCode(promptCode.trim().toUpperCase().replace("#", ""));
            }
          }}
          className="inline-flex items-center justify-center gap-1.5 px-3.5 py-2 rounded-xl bg-brand-blue-600 hover:bg-brand-blue-700 text-white text-xs font-bold transition-all shadow-xs shrink-0"
        >
          <PlusCircle className="w-4 h-4" />
          <span>Tạo yêu cầu đổi trả mới</span>
        </button>
      </div>

      {/* Quick Lookup Bar */}
      <form onSubmit={handleStartReturnFromInput} className="bg-slate-50 border border-slate-200/80 rounded-xl p-3 sm:p-4 flex flex-col sm:flex-row items-stretch sm:items-center gap-2.5">
        <div className="relative flex-1">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={manualOrderInput}
            onChange={(e) => {
              setManualOrderInput(e.target.value);
              setErrorMsg("");
            }}
            placeholder="Nhập mã đơn hàng để yêu cầu đổi/trả (ví dụ: ORD-888999)..."
            className="w-full pl-9 pr-3 py-2 text-xs rounded-lg border border-slate-200 bg-white focus:outline-none focus:border-brand-blue-500 font-medium"
          />
        </div>
        <button
          type="submit"
          className="px-4 py-2 bg-slate-900 hover:bg-slate-800 text-white font-bold text-xs rounded-lg transition-colors flex items-center justify-center gap-1.5 shrink-0"
        >
          <span>Kiểm tra đổi trả</span>
          <ArrowRight className="w-3.5 h-3.5" />
        </button>
      </form>
      {errorMsg && <p className="text-xs text-rose-600 font-semibold -mt-3">{errorMsg}</p>}

      {/* Tabs */}
      <div className="flex items-center gap-1.5 border-b border-slate-200 overflow-x-auto pb-1 text-xs">
        <button
          onClick={() => setFilterTab("ALL")}
          className={`px-3 py-2 rounded-lg font-bold transition-colors whitespace-nowrap ${
            filterTab === "ALL"
              ? "bg-brand-blue-50 text-brand-blue-700"
              : "text-slate-600 hover:bg-slate-100"
          }`}
        >
          Tất cả ({returnsList.length})
        </button>
        <button
          onClick={() => setFilterTab("WAITING_SHIP")}
          className={`px-3 py-2 rounded-lg font-bold transition-colors whitespace-nowrap ${
            filterTab === "WAITING_SHIP"
              ? "bg-orange-50 text-orange-700"
              : "text-slate-600 hover:bg-slate-100"
          }`}
        >
          Cần gửi hàng ({returnsList.filter((r) => r.status === "WAITING_CUSTOMER_RETURN").length})
        </button>
        <button
          onClick={() => setFilterTab("ACTIVE")}
          className={`px-3 py-2 rounded-lg font-bold transition-colors whitespace-nowrap ${
            filterTab === "ACTIVE"
              ? "bg-blue-50 text-blue-700"
              : "text-slate-600 hover:bg-slate-100"
          }`}
        >
          Đang xử lý ({returnsList.filter((r) => !["COMPLETED", "REFUNDED", "REJECTED", "CANCELLED"].includes(r.status)).length})
        </button>
        <button
          onClick={() => setFilterTab("DONE")}
          className={`px-3 py-2 rounded-lg font-bold transition-colors whitespace-nowrap ${
            filterTab === "DONE"
              ? "bg-slate-200 text-slate-800"
              : "text-slate-600 hover:bg-slate-100"
          }`}
        >
          Đã xong ({returnsList.filter((r) => ["COMPLETED", "REFUNDED", "REJECTED", "CANCELLED"].includes(r.status)).length})
        </button>
      </div>

      {/* List Content */}
      {loading ? (
        <div className="p-8 text-center text-xs text-slate-500">
          <RefreshCw className="w-5 h-5 text-brand-blue-600 animate-spin mx-auto mb-2" />
          Đang tải danh sách đổi trả...
        </div>
      ) : filteredReturns.length > 0 ? (
        <div className="space-y-3">
          {filteredReturns.map((ret) => {
            const statusConfig = STATUS_MAP[ret.status] || {
              label: ret.status,
              badge: "bg-slate-100 text-slate-700 border-slate-200",
              step: 1,
            };

            const isExchange = ret.request_type === "EXCHANGE";

            return (
              <div
                key={ret.return_code}
                onClick={() => setSelectedReturnCode(ret.return_code)}
                className="p-4 rounded-xl bg-white border border-slate-200 hover:border-brand-blue-300 hover:shadow-xs transition-all cursor-pointer group"
              >
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2.5 pb-2.5 border-b border-slate-100">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-black text-sm text-slate-900 group-hover:text-brand-blue-600 transition-colors">
                      #{ret.return_code}
                    </span>
                    <span
                      className={`px-2 py-0.5 rounded text-[10.5px] font-bold border ${
                        isExchange
                          ? "bg-indigo-50 text-indigo-700 border-indigo-200"
                          : "bg-emerald-50 text-emerald-700 border-emerald-200"
                      }`}
                    >
                      {isExchange ? "ĐỔI SẢN PHẨM" : "TRẢ HÀNG & HOÀN TIỀN"}
                    </span>
                    <span className="text-[11px] text-slate-400">
                      Đơn #{ret.order_code}
                    </span>
                  </div>

                  <span className={`px-2.5 py-1 rounded-full text-xs font-bold border self-start sm:self-auto ${statusConfig.badge}`}>
                    {statusConfig.label}
                  </span>
                </div>

                <div className="pt-2.5 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs text-slate-600">
                  <div>
                    <p className="font-semibold text-slate-800">
                      Lý do: <span className="font-normal text-slate-600">{ret.reason_text}</span>
                    </p>
                    <p className="text-[11px] text-slate-500 mt-0.5">
                      Số lượng mặt hàng: {ret.items_count} • Tạo lúc:{" "}
                      {ret.requested_at ? new Date(ret.requested_at).toLocaleDateString("vi-VN") : "--"}
                    </p>

                    {/* Shipping action prompt */}
                    {ret.status === "WAITING_CUSTOMER_RETURN" && (
                      <div className="mt-2 inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-amber-50 text-amber-900 border border-amber-200 text-[11px] font-bold">
                        <Truck className="w-3.5 h-3.5 text-amber-600" />
                        <span>Vui lòng gửi bưu phẩm về kho H4Care và cập nhật mã bưu tá</span>
                      </div>
                    )}

                    {ret.tracking_code && (
                      <div className="mt-1 text-[11px] text-slate-500 flex items-center gap-1.5">
                        <Truck className="w-3.5 h-3.5 text-slate-400" />
                        <span>Mã vận đơn: <strong>{ret.carrier_name}</strong> - <strong>{ret.tracking_code}</strong></span>
                      </div>
                    )}
                  </div>

                  <div className="flex items-center gap-1.5 text-brand-blue-600 font-bold text-xs group-hover:translate-x-0.5 transition-transform shrink-0">
                    <span>Xem tiến trình & bằng chứng</span>
                    <ChevronRight className="w-4 h-4" />
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="p-8 rounded-xl bg-slate-50 border border-slate-200/70 text-center space-y-3">
          <RotateCcw className="w-10 h-10 text-slate-300 mx-auto" />
          <div className="max-w-md mx-auto">
            <h4 className="text-xs font-bold text-slate-700">Chưa có yêu cầu đổi/trả nào</h4>
            <p className="text-[11px] text-slate-500 mt-1">
              Bạn có thể tạo yêu cầu đổi/trả thuốc trong vòng 7 ngày kể từ lúc nhận hàng trực tiếp từ danh sách đơn hàng đã mua hoặc nhập mã đơn phía trên.
            </p>
          </div>
        </div>
      )}

      {/* Return Policy Reminder Card */}
      <div className="p-4 rounded-xl bg-gradient-to-r from-brand-blue-50/60 to-slate-50 border border-brand-blue-100 flex items-start gap-3">
        <ShieldCheck className="w-5 h-5 text-brand-blue-600 shrink-0 mt-0.5" />
        <div className="text-xs space-y-1">
          <p className="font-bold text-slate-800">Quy định thẩm định dược phẩm GPP:</p>
          <p className="text-slate-600">
            • <strong>Thuốc kê đơn (Rx) & Vaccine:</strong> Không áp dụng đổi trả theo Luật Dược nhằm bảo đảm an toàn chuỗi cung ứng lạnh và truy xuất nguồn gốc.
          </p>
          <p className="text-slate-600">
            • <strong>Sản phẩm lỗi/hư hỏng do vận chuyển hoặc nhà thuốc:</strong> H4Care chịu 100% phí hoàn hàng và bồi hoàn/đổi mới trong 24h.
          </p>
        </div>
      </div>

      {/* MODAL: Return Detail */}
      {selectedReturnCode && (
        <ReturnDetailModal
          returnCode={selectedReturnCode}
          phoneVerify={userPhone}
          onClose={() => setSelectedReturnCode(null)}
          onRefreshNeeded={() => {
            fetchReturns();
          }}
        />
      )}

      {/* MODAL: Wizard */}
      {wizardOrderCode && (
        <ReturnWizardModal
          orderCode={wizardOrderCode}
          customerPhone={userPhone}
          onClose={() => setWizardOrderCode(null)}
          onSuccess={(newReturnCode) => {
            setWizardOrderCode(null);
            fetchReturns();
            setSelectedReturnCode(newReturnCode);
          }}
        />
      )}
    </div>
  );
}
