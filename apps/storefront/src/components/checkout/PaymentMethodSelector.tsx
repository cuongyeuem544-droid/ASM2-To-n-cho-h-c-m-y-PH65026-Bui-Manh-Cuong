"use client";

import React, { useState, useEffect } from "react";
import { Banknote, Check, AlertTriangle, ShieldCheck } from "lucide-react";

export type PaymentMethod = "COD" | "PAYOS" | "SEPAY";

interface PaymentMethodSelectorProps {
  paymentMethod: PaymentMethod;
  onChangePaymentMethod: (method: PaymentMethod) => void;
  availableMethods?: Record<string, boolean>;
  unavailabilityReasons?: Record<string, string>;
}

export default function PaymentMethodSelector({
  paymentMethod,
  onChangePaymentMethod,
  availableMethods: propAvailableMethods,
  unavailabilityReasons: propReasons,
}: PaymentMethodSelectorProps) {
  const [availableMethods, setAvailableMethods] = useState<Record<string, boolean>>(
    propAvailableMethods || { COD: true, SEPAY: true, PAYOS: false }
  );
  const [unavailabilityReasons, setUnavailabilityReasons] = useState<Record<string, string>>(
    propReasons || {}
  );
  const [infoMessage, setInfoMessage] = useState<string | null>(null);

  // Fetch live payment methods status from backend
  useEffect(() => {
    let isMounted = true;
    const fetchMethods = async () => {
      try {
        const res = await fetch("/api/v1/payments/methods");
        if (res.ok) {
          const data = await res.json();
          if (data && Array.isArray(data.methods) && isMounted) {
            const availMap: Record<string, boolean> = {};
            const reasonMap: Record<string, string> = {};
            data.methods.forEach((m: any) => {
              availMap[m.id] = Boolean(m.available);
              if (m.unavailability_reason) {
                reasonMap[m.id] = m.unavailability_reason;
              }
            });
            setAvailableMethods(availMap);
            setUnavailabilityReasons(reasonMap);

            // Nếu phương thức hiện tại không khả dụng, tự động chuyển về COD
            if (availMap[paymentMethod] === false) {
              onChangePaymentMethod("COD");
            }
          }
        }
      } catch (err) {
        // Fallback default
      }
    };
    fetchMethods();
    return () => {
      isMounted = false;
    };
  }, [paymentMethod, onChangePaymentMethod]);

  const methods = [
    {
      id: "COD" as PaymentMethod,
      title: "Thanh toán khi nhận hàng (COD)",
      desc: "Kiểm tra hàng trước khi thanh toán tiền mặt trực tiếp cho nhân viên giao hàng",
      icon: <Banknote className="w-5 h-5 text-emerald-600" />,
      tag: "Phổ biến",
      tagColor: "bg-emerald-50 text-emerald-700 border-emerald-200",
    },
    {
      id: "SEPAY" as PaymentMethod,
      title: "Chuyển khoản VietQR MBBank (SePay)",
      desc: "Quét mã QR Napas 247, xác nhận tự động tức thì 24/7 từ mọi ứng dụng ngân hàng",
      icon: (
        <span className="w-5 h-5 rounded-full bg-emerald-600 text-white flex items-center justify-center text-[10px] font-black shrink-0">
          MB
        </span>
      ),
      tag: "Tự động 24/7",
      tagColor: "bg-emerald-50 text-emerald-700 border-emerald-200",
    },
    {
      id: "PAYOS" as PaymentMethod,
      title: "Cổng thanh toán payOS (Napas 247)",
      desc: "Mở cổng payOS thanh toán bằng mã QR ngân hàng hoặc thẻ ATM nội địa",
      icon: (
        <span className="w-5 h-5 rounded-full bg-blue-600 text-white flex items-center justify-center text-[10px] font-black shrink-0">
          P
        </span>
      ),
      tag: availableMethods["PAYOS"] ? "Cổng trực tuyến" : "Đang bảo trì",
      tagColor: availableMethods["PAYOS"]
        ? "bg-blue-50 text-brand-blue-700 border-blue-200"
        : "bg-slate-100 text-slate-500 border-slate-200",
    },
  ];

  const handleSelect = (methodId: PaymentMethod) => {
    const isAvail = availableMethods[methodId] !== false;
    if (!isAvail) {
      const reason =
        unavailabilityReasons[methodId] ||
        `Phương thức ${methodId} đang tạm thời bảo trì cấu hình trên hệ thống. Vui lòng chọn COD hoặc Chuyển khoản VietQR MBBank.`;
      setInfoMessage(reason);
      return;
    }
    setInfoMessage(null);
    onChangePaymentMethod(methodId);
  };

  return (
    <div className="bg-white rounded-xl border border-slate-200 overflow-hidden shadow-xs p-4 sm:p-5">
      <div className="pb-3 border-b border-slate-100 flex items-center justify-between">
        <div>
          <h2 className="text-sm font-bold text-slate-900">
            Phương thức thanh toán
          </h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Chọn hình thức thanh toán thuận tiện và an toàn nhất
          </p>
        </div>
        <div className="flex items-center gap-1.5 text-[11px] text-emerald-700 font-semibold bg-emerald-50 px-2.5 py-1 rounded-full border border-emerald-200">
          <ShieldCheck className="w-3.5 h-3.5" />
          <span>Bảo mật 100%</span>
        </div>
      </div>

      {infoMessage && (
        <div className="mt-3 p-3 rounded-xl bg-amber-50 border border-amber-200 text-xs text-amber-800 flex items-start gap-2 animate-in fade-in">
          <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
          <span>{infoMessage}</span>
        </div>
      )}

      <div className="mt-3.5 grid grid-cols-1 sm:grid-cols-3 gap-3.5">
        {methods.map((m) => {
          const isSelected = paymentMethod === m.id;
          const isAvailable = availableMethods[m.id] !== false;

          return (
            <div
              key={m.id}
              onClick={() => handleSelect(m.id)}
              className={`p-4 rounded-xl border transition-all flex flex-col justify-between gap-3 ${
                !isAvailable
                  ? "opacity-60 bg-slate-50 border-slate-200 cursor-not-allowed"
                  : isSelected
                  ? "border-brand-blue-600 bg-brand-blue-50/40 shadow-xs ring-1 ring-brand-blue-600/30 cursor-pointer"
                  : "border-slate-200 hover:border-slate-300 hover:bg-slate-50/50 bg-white cursor-pointer"
              }`}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="w-9 h-9 rounded-lg bg-slate-50 border border-slate-200 flex items-center justify-center shrink-0">
                  {m.icon}
                </div>

                {/* Radio Indicator */}
                <div
                  className={`w-5 h-5 rounded-full flex items-center justify-center shrink-0 border transition-colors ${
                    !isAvailable
                      ? "border-slate-200 bg-slate-100"
                      : isSelected
                      ? "bg-brand-blue-600 border-brand-blue-600 text-white"
                      : "border-slate-300 bg-white"
                  }`}
                >
                  {isSelected && <Check className="w-3 h-3 stroke-[3]" />}
                </div>
              </div>

              <div className="space-y-1">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-xs sm:text-sm font-bold text-slate-900">
                    {m.title}
                  </span>
                  {m.tag && (
                    <span
                      className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border ${m.tagColor}`}
                    >
                      {m.tag}
                    </span>
                  )}
                </div>
                <p className="text-[11px] sm:text-xs text-slate-500 leading-normal">
                  {m.desc}
                </p>
                {!isAvailable && (
                  <p className="text-[10px] text-amber-700 font-medium">
                    (Tạm bảo trì cấu hình keys)
                  </p>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
