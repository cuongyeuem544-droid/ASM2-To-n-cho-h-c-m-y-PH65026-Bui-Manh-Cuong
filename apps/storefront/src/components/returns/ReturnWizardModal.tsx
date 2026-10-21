"use client";

import React, { useEffect, useState } from "react";
import {
  X,
  RotateCcw,
  RefreshCw,
  AlertCircle,
  CheckCircle2,
  Upload,
  Truck,
  ShieldCheck,
  ChevronRight,
  ArrowRight,
  CreditCard,
} from "lucide-react";

const POPULAR_BANKS = [
  { code: "VCB", name: "Vietcombank (Ngoại Thương Việt Nam)" },
  { code: "MB", name: "MB Bank (Quân Đội)" },
  { code: "TCB", name: "Techcombank (Kỹ Thương)" },
  { code: "BIDV", name: "BIDV (Đầu Tư & Phát Triển)" },
  { code: "CTG", name: "VietinBank (Công Thương)" },
  { code: "ACB", name: "ACB (Á Châu)" },
  { code: "VPB", name: "VPBank (Việt Nam Thịnh Vượng)" },
  { code: "TPB", name: "TPBank (Tiên Phong)" },
  { code: "STB", name: "Sacombank (Sài Gòn Thương Tín)" },
  { code: "VIB", name: "VIB (Quốc Tế)" },
  { code: "HDB", name: "HDBank (Phát Triển TP.HCM)" },
  { code: "AGR", name: "Agribank (Nông Nghiệp)" },
  { code: "OTHER", name: "Ngân hàng khác..." },
];

interface EligibilityItem {
  order_item_id: number;
  product_id: number;
  product_name: string;
  purchased_quantity: number;
  returned_quantity: number;
  returnable_quantity: number;
  is_rx: boolean;
  is_eligible: boolean;
  reason_code: string;
  message: string;
  net_unit_price: number;
}

interface EligibilityData {
  order_code: string;
  order_status: string;
  payment_status: string;
  total_amount: number;
  shipping_fee: number;
  can_request_return: boolean;
  can_request_exchange: boolean;
  rejection_reason?: string;
  items: EligibilityItem[];
  free_return_shipping_reasons: string[];
}

interface ReturnWizardModalProps {
  orderCode: string;
  customerPhone?: string;
  onClose: () => void;
  onSuccess: (returnCode: string) => void;
}

const REASONS = [
  { code: "WRONG_ITEM", text: "Giao sai sản phẩm / sai quy cách", isMerchantFault: true },
  { code: "DEFECTIVE", text: "Sản phẩm hỏng hóc, bể vỡ khi nhận", isMerchantFault: true },
  { code: "EXPIRED_DELIVERED", text: "Sản phẩm cận date / hết hạn sử dụng", isMerchantFault: true },
  { code: "ORDERED_WRONG", text: "Tôi đặt nhầm sản phẩm cần mua", isMerchantFault: false },
  { code: "CHANGED_MIND", text: "Đổi ý, không còn nhu cầu sử dụng (còn nguyên seal)", isMerchantFault: false },
  { code: "OTHER", text: "Lý do khác", isMerchantFault: false },
];

export function ReturnWizardModal({
  orderCode,
  customerPhone,
  onClose,
  onSuccess,
}: ReturnWizardModalProps) {
  const [eligibility, setEligibility] = useState<EligibilityData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Form states
  const [requestType, setRequestType] = useState<"RETURN" | "EXCHANGE">("RETURN");
  const [selectedItems, setSelectedItems] = useState<{ [itemId: number]: number }>({});
  const [itemConditions, setItemConditions] = useState<{ [itemId: number]: string }>({});
  const [reasonCode, setReasonCode] = useState<string>("WRONG_ITEM");
  const [customerNote, setCustomerNote] = useState<string>("");
  const [phoneVerify, setPhoneVerify] = useState<string>(customerPhone || "");
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [uploadedImages, setUploadedImages] = useState<string[]>([]);
  const [uploadingImage, setUploadingImage] = useState<boolean>(false);
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [createdReturnCode, setCreatedReturnCode] = useState<string | null>(null);
  const [uploadErrors, setUploadErrors] = useState<string[]>([]);
  const [failedFiles, setFailedFiles] = useState<File[]>([]);
  const [refundBankCode, setRefundBankCode] = useState<string>("VCB");
  const [refundBankName, setRefundBankName] = useState<string>("Vietcombank (Ngoại Thương Việt Nam)");
  const [refundAccountNumber, setRefundAccountNumber] = useState<string>("");
  const [refundAccountName, setRefundAccountName] = useState<string>("");
  const [bankError, setBankError] = useState<string>("");

  useEffect(() => {
    const token = typeof window !== "undefined" ? localStorage.getItem("pharmatrust_token") || localStorage.getItem("h4care_auth_token") : null;
    const guestToken = typeof window !== "undefined" ? localStorage.getItem(`h4care_order_token_${orderCode}`) || localStorage.getItem("h4care_latest_order_token") : null;
    const headers: Record<string, string> = {};
    if (token) headers["Authorization"] = `Bearer ${token}`;
    if (guestToken) headers["X-Order-Token"] = guestToken;

    setLoading(true);
    fetch(`/api/v1/returns/eligibility/${encodeURIComponent(orderCode)}`, { headers })
      .then(async (res) => {
        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          throw new Error(errData.detail || "Không thể kiểm tra điều kiện đổi trả.");
        }
        return res.json();
      })
      .then((data: EligibilityData) => {
        setEligibility(data);
        // Default select first eligible item
        const initialSelected: { [itemId: number]: number } = {};
        data.items.forEach((it) => {
          if (it.is_eligible && it.returnable_quantity > 0) {
            initialSelected[it.order_item_id] = 1;
          }
        });
        setSelectedItems(initialSelected);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [orderCode]);

  const handleImageUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files || e.target.files.length === 0) return;
    const file = e.target.files[0];
    if (file.size > 5 * 1024 * 1024) {
      alert("Dung lượng ảnh vượt quá 5MB. Vui lòng chọn ảnh nhỏ hơn.");
      return;
    }
    const previewUrl = URL.createObjectURL(file);
    setSelectedFiles((prev) => [...prev, file]);
    setUploadedImages((prev) => [...prev, previewUrl]);
  };

  const calculateEstimate = () => {
    if (!eligibility) return { itemsRefund: 0, shippingRefund: 0, totalRefund: 0 };
    let itemsRefund = 0;
    const selectedCount = Object.keys(selectedItems).length;

    eligibility.items.forEach((it) => {
      const qty = selectedItems[it.order_item_id] || 0;
      if (qty > 0) {
        itemsRefund += it.net_unit_price * qty;
      }
    });

    const isMerchantFault = REASONS.find((r) => r.code === reasonCode)?.isMerchantFault || false;
    const isFullReturn = selectedCount === eligibility.items.length;
    const shippingRefund = isMerchantFault && isFullReturn ? eligibility.shipping_fee : 0;
    const totalRefund = Math.min(itemsRefund + shippingRefund, eligibility.total_amount);

    return { itemsRefund, shippingRefund, totalRefund };
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (Object.values(selectedItems).every((qty) => qty <= 0)) {
      alert("Vui lòng chọn ít nhất một sản phẩm cần đổi/trả với số lượng lớn hơn 0.");
      return;
    }

    for (const [itemIdStr, qty] of Object.entries(selectedItems)) {
      if (qty > 0) {
        const cond = itemConditions[parseInt(itemIdStr, 10)];
        if (!cond) {
          alert("Vui lòng chọn tình trạng thực tế của từng sản phẩm cần đổi/trả.");
          return;
        }
      }
    }

    const itemsPayload = Object.entries(selectedItems)
      .filter(([_, qty]) => qty > 0)
      .map(([itemIdStr, qty]) => ({
        order_item_id: parseInt(itemIdStr, 10),
        requested_quantity: qty,
        customer_reason: customerNote,
        condition_reported: itemConditions[parseInt(itemIdStr, 10)] || "SEALED",
      }));

    const selectedReasonObj = REASONS.find((r) => r.code === reasonCode);

    const token = typeof window !== "undefined" ? localStorage.getItem("pharmatrust_token") || localStorage.getItem("h4care_auth_token") : null;
    const guestToken = typeof window !== "undefined" ? localStorage.getItem(`h4care_order_token_${orderCode}`) || localStorage.getItem("h4care_latest_order_token") : null;
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (token) headers["Authorization"] = `Bearer ${token}`;
    if (guestToken) headers["X-Order-Token"] = guestToken;

    if (requestType === "RETURN") {
      if (!refundBankName.trim()) {
        setBankError("Vui lòng chọn hoặc nhập tên ngân hàng nhận tiền hoàn.");
        return;
      }
      const cleanAcc = refundAccountNumber.trim();
      if (!cleanAcc || cleanAcc.length < 6 || cleanAcc.length > 20) {
        setBankError("Số tài khoản ngân hàng không hợp lệ (yêu cầu từ 6 đến 20 chữ số).");
        return;
      }
      if (!refundAccountName.trim()) {
        setBankError("Vui lòng nhập họ và tên chủ tài khoản thụ hưởng.");
        return;
      }
    }

    setSubmitting(true);
    setUploadErrors([]);
    try {
      let activeReturnCode = createdReturnCode;

      // 1. Tạo phiếu đổi trả nếu chưa từng tạo thành công trước đó (chống tạo trùng khi retry upload ảnh)
      if (!activeReturnCode) {
        const res = await fetch("/api/v1/returns", {
          method: "POST",
          headers,
          body: JSON.stringify({
            order_code: orderCode,
            request_type: requestType,
            reason_code: reasonCode,
            reason_text: selectedReasonObj?.text || "Yêu cầu đổi trả",
            customer_note: customerNote,
            return_method: "CUSTOMER_SHIP",
            items: itemsPayload,
            customer_phone_verify: phoneVerify.trim(),
            refund_bank_code: requestType === "RETURN" ? refundBankCode : undefined,
            refund_bank_name: requestType === "RETURN" ? refundBankName.trim() : undefined,
            refund_account_number: requestType === "RETURN" ? refundAccountNumber.trim() : undefined,
            refund_account_name: requestType === "RETURN" ? refundAccountName.trim() : undefined,
          }),
        });

        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          throw new Error(data.detail || "Không thể gửi yêu cầu.");
        }
        activeReturnCode = data.return_code;
        setCreatedReturnCode(activeReturnCode);
      }

      // 2. Tải lên danh sách ảnh bằng chứng (hoặc các ảnh retry còn lỗi)
      const filesToUpload = failedFiles.length > 0 ? failedFiles : selectedFiles;
      if (filesToUpload.length > 0 && activeReturnCode) {
        const currentFailed: File[] = [];
        const errMessages: string[] = [];

        for (const file of filesToUpload) {
          const formData = new FormData();
          formData.append("file", file);
          formData.append("return_code", activeReturnCode);
          const uploadHeaders: Record<string, string> = {};
          if (token) uploadHeaders["Authorization"] = `Bearer ${token}`;
          if (guestToken) uploadHeaders["X-Order-Token"] = guestToken;

          try {
            const upRes = await fetch("/api/v1/returns/upload-evidence", {
              method: "POST",
              headers: uploadHeaders,
              body: formData,
            });
            if (!upRes.ok) {
              const errData = await upRes.json().catch(() => ({}));
              currentFailed.push(file);
              errMessages.push(`Ảnh "${file.name}": ${errData.detail || `Lỗi tải lên (HTTP ${upRes.status})`}`);
            }
          } catch (netErr: any) {
            currentFailed.push(file);
            errMessages.push(`Ảnh "${file.name}": Lỗi kết nối mạng`);
          }
        }

        if (currentFailed.length > 0) {
          setFailedFiles(currentFailed);
          setUploadErrors(errMessages);
          return;
        }
      }

      if (activeReturnCode) {
        onSuccess(activeReturnCode);
      }
    } catch (err: any) {
      alert(err.message || "Gặp sự cố khi gửi yêu cầu.");
    } finally {
      setSubmitting(false);
    }
  };

  const estimate = calculateEstimate();

  return (
    <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4 overflow-y-auto animate-in fade-in duration-150">
      <div className="bg-white rounded-3xl max-w-2xl w-full p-6 sm:p-8 border border-slate-200 shadow-2xl relative my-8">
        <button
          onClick={onClose}
          className="absolute top-5 right-5 p-2 rounded-full hover:bg-slate-100 text-slate-400 hover:text-slate-700 transition-colors"
        >
          <X className="w-5 h-5" />
        </button>

        {/* Header */}
        <div className="flex items-center gap-3 mb-6 pb-4 border-b border-slate-100">
          <div className="w-12 h-12 rounded-2xl bg-brand-blue-50 text-brand-blue-600 flex items-center justify-center font-bold">
            <RotateCcw className="w-6 h-6" />
          </div>
          <div>
            <h2 className="text-lg font-black text-slate-900 tracking-tight">
              Tạo Yêu Cầu Đổi / Trả Hàng
            </h2>
            <p className="text-xs text-slate-500">
              Đơn hàng: <strong className="text-slate-800">#{orderCode}</strong> • Tuân thủ chính sách Dược GPP & Bảo vệ người tiêu dùng
            </p>
          </div>
        </div>

        {loading ? (
          <div className="py-12 text-center text-xs text-slate-500">
            Đang thẩm định điều kiện đổi trả của đơn thuốc...
          </div>
        ) : error ? (
          <div className="p-4 rounded-2xl bg-rose-50 border border-rose-200 text-rose-700 text-xs flex items-start gap-2.5">
            <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
            <div>
              <p className="font-bold">Không thể thực hiện yêu cầu</p>
              <p className="mt-0.5">{error}</p>
            </div>
          </div>
        ) : eligibility && !eligibility.can_request_return ? (
          <div className="p-5 rounded-2xl bg-amber-50 border border-amber-200 text-amber-900 text-xs space-y-2">
            <div className="flex items-center gap-2 font-bold text-amber-800">
              <AlertCircle className="w-4 h-4" />
              <span>Đơn hàng chưa đủ điều kiện đổi trả tự động</span>
            </div>
            <p>{eligibility.rejection_reason}</p>
            <div className="pt-2 border-t border-amber-200/60 text-[11px] text-amber-700">
              Cần hỗ trợ đặc biệt? Quý khách vui lòng liên hệ email: <strong>duocsi@h4care.vn</strong>
            </div>
          </div>
        ) : eligibility ? (
          <form onSubmit={handleSubmit} className="space-y-6">
            {/* Step 1: Chọn hình thức */}
            <div>
              <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-2">
                1. Chọn hình thức giải quyết
              </label>
              <div className="grid grid-cols-2 gap-3">
                <button
                  type="button"
                  onClick={() => setRequestType("RETURN")}
                  className={`p-3.5 rounded-2xl border text-left transition-all flex items-start gap-3 ${
                    requestType === "RETURN"
                      ? "border-brand-blue-600 bg-brand-blue-50/50 shadow-xs"
                      : "border-slate-200 hover:bg-slate-50"
                  }`}
                >
                  <div
                    className={`w-4 h-4 rounded-full mt-0.5 shrink-0 border flex items-center justify-center ${
                      requestType === "RETURN"
                        ? "border-brand-blue-600 bg-brand-blue-600"
                        : "border-slate-300"
                    }`}
                  >
                    {requestType === "RETURN" && <div className="w-1.5 h-1.5 rounded-full bg-white" />}
                  </div>
                  <div>
                    <span className="font-extrabold text-xs text-slate-900 block">Trả hàng & Hoàn tiền</span>
                    <span className="text-[11px] text-slate-500">Hoàn lại tiền vào tài khoản ngân hàng hoặc ví MoMo</span>
                  </div>
                </button>

                <button
                  type="button"
                  onClick={() => setRequestType("EXCHANGE")}
                  className={`p-3.5 rounded-2xl border text-left transition-all flex items-start gap-3 ${
                    requestType === "EXCHANGE"
                      ? "border-brand-blue-600 bg-brand-blue-50/50 shadow-xs"
                      : "border-slate-200 hover:bg-slate-50"
                  }`}
                >
                  <div
                    className={`w-4 h-4 rounded-full mt-0.5 shrink-0 border flex items-center justify-center ${
                      requestType === "EXCHANGE"
                        ? "border-brand-blue-600 bg-brand-blue-600"
                        : "border-slate-300"
                    }`}
                  >
                    {requestType === "EXCHANGE" && <div className="w-1.5 h-1.5 rounded-full bg-white" />}
                  </div>
                  <div>
                    <span className="font-extrabold text-xs text-slate-900 block">Đổi sang sản phẩm khác</span>
                    <span className="text-[11px] text-slate-500">Đổi quy cách hoặc thuốc tương đương (bù trừ chênh lệch)</span>
                  </div>
                </button>
              </div>
            </div>

            {/* Step 2: Chọn sản phẩm & số lượng */}
            <div>
              <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-2">
                2. Chọn sản phẩm cần đổi / trả
              </label>
              <div className="space-y-2.5 max-h-48 overflow-y-auto pr-1">
                {eligibility.items.map((it) => {
                  const qty = selectedItems[it.order_item_id] || 0;
                  return (
                    <div
                      key={it.order_item_id}
                      className={`p-3.5 rounded-2xl border transition-all flex items-center justify-between gap-3 ${
                        it.is_eligible
                          ? qty > 0
                            ? "border-brand-blue-300 bg-brand-blue-50/20"
                            : "border-slate-200 bg-white"
                          : "border-slate-200 bg-slate-50 opacity-60"
                      }`}
                    >
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <p className="font-bold text-xs text-slate-900 truncate">{it.product_name}</p>
                          {it.is_rx && (
                            <span className="px-1.5 py-0.5 rounded text-[9px] font-extrabold bg-rose-50 text-rose-700 border border-rose-200">
                              Thuốc Rx
                            </span>
                          )}
                        </div>
                        <p className="text-[11px] text-slate-500 mt-0.5">
                          Đã mua: {it.purchased_quantity} • Có thể trả: <strong>{it.returnable_quantity}</strong> • Đơn giá ròng:{" "}
                          <span className="text-brand-blue-600 font-bold">{it.net_unit_price.toLocaleString("vi-VN")} đ</span>
                        </p>
                        {!it.is_eligible && (
                          <p className="text-[10px] text-rose-600 mt-0.5">{it.message}</p>
                        )}
                      </div>

                      {it.is_eligible && (
                        <div className="flex flex-col sm:flex-row sm:items-center gap-2">
                          <div className="flex items-center gap-1.5">
                            <label className="text-xs text-slate-500 font-semibold">Số lượng:</label>
                            <select
                              value={qty}
                              onChange={(e) =>
                                setSelectedItems((prev) => ({
                                  ...prev,
                                  [it.order_item_id]: parseInt(e.target.value, 10),
                                }))
                              }
                              className="px-2.5 py-1 rounded-xl border border-slate-300 text-xs font-bold text-slate-800 bg-white focus:outline-brand-blue-600"
                            >
                              <option value={0}>0</option>
                              {Array.from({ length: it.returnable_quantity }, (_, i) => i + 1).map((n) => (
                                <option key={n} value={n}>
                                  {n}
                                </option>
                              ))}
                            </select>
                          </div>
                          {qty > 0 && (
                            <div className="flex items-center gap-1.5">
                              <label className="text-xs text-slate-500 font-semibold">Tình trạng:</label>
                              <select
                                value={itemConditions[it.order_item_id] || ""}
                                onChange={(e) =>
                                  setItemConditions((prev) => ({
                                    ...prev,
                                    [it.order_item_id]: e.target.value,
                                  }))
                                }
                                className="px-2.5 py-1 rounded-xl border border-slate-300 text-xs font-medium text-slate-800 bg-white focus:outline-brand-blue-600"
                              >
                                <option value="">-- Chọn tình trạng --</option>
                                <option value="SEALED">Nguyên bao bì (SEALED)</option>
                                <option value="OPENED">Đã mở bao bì (OPENED)</option>
                                <option value="DAMAGED">Hư hỏng / móp vỡ (DAMAGED)</option>
                                <option value="DEFECTIVE">Lỗi thuốc / biến chất (DEFECTIVE)</option>
                              </select>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Step 3: Lý do & Ghi chú */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5">
                  3. Lý do đổi / trả hàng
                </label>
                <select
                  value={reasonCode}
                  onChange={(e) => setReasonCode(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-xl border border-slate-300 text-xs font-bold text-slate-800 bg-white focus:outline-brand-blue-600"
                >
                  {REASONS.map((r) => (
                    <option key={r.code} value={r.code}>
                      {r.text} {r.isMerchantFault ? "(Miễn phí ship)" : ""}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5">
                  Số điện thoại xác thực
                </label>
                <input
                  type="tel"
                  value={phoneVerify}
                  onChange={(e) => setPhoneVerify(e.target.value)}
                  placeholder="Nhập SĐT đặt đơn hàng..."
                  className="w-full px-3.5 py-2.5 rounded-xl border border-slate-300 text-xs text-slate-800 focus:outline-brand-blue-600"
                  required
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5">
                Mô tả chi tiết tình trạng hàng
              </label>
              <textarea
                value={customerNote}
                onChange={(e) => setCustomerNote(e.target.value)}
                placeholder="Vui lòng mô tả chi tiết lỗi, tình trạng nguyên seal, bao bì..."
                rows={2}
                className="w-full px-3.5 py-2 rounded-xl border border-slate-300 text-xs text-slate-800 focus:outline-brand-blue-600"
              />
            </div>

            {/* Step 4: Tải lên hình ảnh bằng chứng */}
            <div>
              <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-2">
                4. Hình ảnh thực tế của sản phẩm
              </label>
              <div className="flex flex-wrap items-center gap-3">
                {uploadedImages.map((url, idx) => (
                  <div key={idx} className="w-16 h-16 rounded-xl border border-slate-200 overflow-hidden relative group">
                    <img src={url} alt="Bằng chứng" className="w-full h-full object-cover" />
                    <button
                      type="button"
                      onClick={() => {
                        setUploadedImages((prev) => prev.filter((_, i) => i !== idx));
                        setSelectedFiles((prev) => prev.filter((_, i) => i !== idx));
                        setFailedFiles((prev) => prev.filter((_, i) => i !== idx));
                      }}
                      className="absolute inset-0 bg-black/50 text-white flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                ))}

                <label className="w-16 h-16 rounded-xl border-2 border-dashed border-slate-300 hover:border-brand-blue-500 hover:bg-brand-blue-50/50 flex flex-col items-center justify-center cursor-pointer transition-colors text-slate-400 hover:text-brand-blue-600">
                  <Upload className="w-5 h-5" />
                  <span className="text-[9px] font-bold mt-1">Thêm ảnh</span>
                  <input
                    type="file"
                    accept="image/*"
                    onChange={handleImageUpload}
                    disabled={uploadingImage}
                    className="hidden"
                  />
                </label>
              </div>
              {uploadingImage && <p className="text-[11px] text-slate-400 mt-1">Đang tải ảnh lên...</p>}
            </div>

            {/* Step 5: Bảng tính toán hoàn tiền dự kiến */}
            <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200/80 space-y-2 text-xs">
              <div className="flex items-center justify-between text-slate-600">
                <span>Tiền hàng hoàn trả dự kiến:</span>
                <span className="font-bold text-slate-800">{estimate.itemsRefund.toLocaleString("vi-VN")} đ</span>
              </div>
              <div className="flex items-center justify-between text-slate-600">
                <span>Hoàn phí vận chuyển ban đầu:</span>
                <span className="font-bold text-slate-800">
                  {estimate.shippingRefund > 0
                    ? `+${estimate.shippingRefund.toLocaleString("vi-VN")} đ (Lỗi nhà thuốc)`
                    : "0 đ"}
                </span>
              </div>
              <div className="pt-2 border-t border-slate-200 flex items-center justify-between text-sm font-black">
                <span className="text-slate-900">Tổng tiền hoàn dự kiến:</span>
                <span className="text-brand-blue-600">{estimate.totalRefund.toLocaleString("vi-VN")} đ</span>
              </div>
            </div>

            {/* Step 6: Thông tin tài khoản nhận tiền hoàn */}
            {requestType === "RETURN" && (
              <div className="p-4 rounded-2xl bg-brand-blue-50/40 border border-brand-blue-200/80 space-y-3">
                <div className="flex items-center gap-2">
                  <CreditCard className="w-4 h-4 text-brand-blue-600 shrink-0" />
                  <label className="text-xs font-bold text-slate-800 uppercase tracking-wider">
                    Thông tin tài khoản nhận tiền hoàn
                  </label>
                </div>
                <p className="text-[11px] text-slate-500">
                  Số tiền hoàn sẽ được chuyển khoản trực tiếp về tài khoản ngân hàng của bạn sau khi Dược sĩ kiểm định đạt chuẩn.
                </p>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <label className="block text-[11px] font-bold text-slate-700 mb-1">
                      Ngân hàng thụ hưởng <span className="text-rose-500">*</span>
                    </label>
                    <select
                      value={refundBankCode}
                      onChange={(e) => {
                        const b = POPULAR_BANKS.find((x) => x.code === e.target.value);
                        setRefundBankCode(e.target.value);
                        if (b && b.code !== "OTHER") setRefundBankName(b.name);
                        setBankError("");
                      }}
                      className="w-full px-3 py-2 rounded-xl border border-slate-300 text-xs font-medium text-slate-800 bg-white focus:outline-brand-blue-600"
                    >
                      {POPULAR_BANKS.map((b) => (
                        <option key={b.code} value={b.code}>
                          {b.name}
                        </option>
                      ))}
                    </select>
                  </div>

                  {refundBankCode === "OTHER" && (
                    <div>
                      <label className="block text-[11px] font-bold text-slate-700 mb-1">
                        Tên ngân hàng khác <span className="text-rose-500">*</span>
                      </label>
                      <input
                        type="text"
                        value={refundBankName}
                        onChange={(e) => {
                          setRefundBankName(e.target.value);
                          setBankError("");
                        }}
                        placeholder="Nhập tên ngân hàng của bạn..."
                        className="w-full px-3 py-2 rounded-xl border border-slate-300 text-xs text-slate-800 bg-white focus:outline-brand-blue-600"
                      />
                    </div>
                  )}

                  <div>
                    <label className="block text-[11px] font-bold text-slate-700 mb-1">
                      Số tài khoản <span className="text-rose-500">*</span>
                    </label>
                    <input
                      type="text"
                      value={refundAccountNumber}
                      onChange={(e) => {
                        const val = e.target.value.replace(/\D/g, "");
                        setRefundAccountNumber(val);
                        setBankError("");
                      }}
                      placeholder="VD: 0123456789..."
                      className="w-full px-3 py-2 rounded-xl border border-slate-300 text-xs font-mono text-slate-800 bg-white focus:outline-brand-blue-600"
                    />
                  </div>

                  <div>
                    <label className="block text-[11px] font-bold text-slate-700 mb-1">
                      Tên chủ tài khoản (không dấu) <span className="text-rose-500">*</span>
                    </label>
                    <input
                      type="text"
                      value={refundAccountName}
                      onChange={(e) => {
                        setRefundAccountName(e.target.value.toUpperCase());
                        setBankError("");
                      }}
                      placeholder="VD: NGUYEN VAN A..."
                      className="w-full px-3 py-2 rounded-xl border border-slate-300 text-xs font-bold uppercase text-slate-800 bg-white focus:outline-brand-blue-600"
                    />
                  </div>
                </div>

                {bankError && (
                  <p className="text-[11px] text-rose-600 font-semibold">{bankError}</p>
                )}
              </div>
            )}

            {/* Upload Errors Alert & Retry */}
            {uploadErrors.length > 0 && (
              <div className="p-3.5 rounded-2xl bg-amber-50 border border-amber-200 text-amber-800 text-xs space-y-1.5">
                <div className="flex items-center gap-2 font-bold">
                  <AlertCircle className="w-4 h-4 text-amber-600 shrink-0" />
                  <span>
                    Phiếu #{createdReturnCode} đã được tạo thành công, nhưng một số ảnh chưa tải lên được:
                  </span>
                </div>
                <ul className="list-disc list-inside text-[11px] space-y-0.5 pl-2 text-amber-700">
                  {uploadErrors.map((msg, i) => (
                    <li key={i}>{msg}</li>
                  ))}
                </ul>
                <p className="text-[11px] text-amber-600">
                  Bạn có thể bấm &quot;Thử lại tải ảnh&quot; hoặc &quot;Hoàn tất không cần tải thêm&quot;.
                </p>
              </div>
            )}

            {/* Actions */}
            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2.5 rounded-xl border border-slate-200 text-slate-600 font-bold text-xs hover:bg-slate-50 transition-colors"
              >
                Hủy bỏ
              </button>
              {createdReturnCode && uploadErrors.length > 0 && (
                <button
                  type="button"
                  onClick={() => onSuccess(createdReturnCode)}
                  className="px-4 py-2.5 rounded-xl border border-slate-200 text-slate-700 font-bold text-xs hover:bg-slate-100 transition-colors"
                >
                  Hoàn tất không cần tải thêm
                </button>
              )}
              <button
                type="submit"
                disabled={submitting}
                className="px-6 py-2.5 rounded-xl bg-brand-blue-600 hover:bg-brand-blue-700 active:bg-brand-blue-800 text-white font-extrabold text-xs transition-colors shadow-xs disabled:opacity-50 flex items-center gap-1.5"
              >
                {submitting ? "Đang xử lý..." : createdReturnCode ? "Thử lại tải ảnh" : "Xác nhận gửi yêu cầu"}
                <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          </form>
        ) : null}
      </div>
    </div>
  );
}
