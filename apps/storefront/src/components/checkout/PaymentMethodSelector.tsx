"use client";

import React from "react";
import { Banknote, Check } from "lucide-react";

export type PaymentMethod = "COD" | "PAYOS" | "SEPAY";

interface PaymentMethodSelectorProps {
  paymentMethod: PaymentMethod;
  onChangePaymentMethod: (method: PaymentMethod) => void;
}

export default function PaymentMethodSelector({
  paymentMethod,
  onChangePaymentMethod,
}: PaymentMethodSelectorProps) {
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
      tag: "Cổng trực tuyến",
      tagColor: "bg-blue-50 text-brand-blue-700 border-blue-200",
    },
  ];

  return (
    <div className="bg-white rounded-xl border border-slate-200 overflow-hidden shadow-xs p-4 sm:p-5">
      <div className="pb-3 border-b border-slate-100">
        <h2 className="text-sm font-bold text-slate-900">
          Phương thức thanh toán
        </h2>
        <p className="text-xs text-slate-500 mt-0.5">
          Chọn hình thức thanh toán thuận tiện và an toàn nhất
        </p>
      </div>

      <div className="mt-3.5 grid grid-cols-1 sm:grid-cols-3 gap-3.5">
        {methods.map((m) => {
          const isSelected = paymentMethod === m.id;
          return (
            <div
              key={m.id}
              onClick={() => onChangePaymentMethod(m.id)}
              className={`p-4 rounded-xl border cursor-pointer transition-all flex flex-col justify-between gap-3 ${
                isSelected
                  ? "border-brand-blue-600 bg-brand-blue-50/40 shadow-xs ring-1 ring-brand-blue-600/30"
                  : "border-slate-200 hover:border-slate-300 hover:bg-slate-50/50 bg-white"
              }`}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="w-9 h-9 rounded-lg bg-slate-50 border border-slate-200 flex items-center justify-center shrink-0">
                  {m.icon}
                </div>

                {/* Radio Indicator */}
                <div
                  className={`w-5 h-5 rounded-full flex items-center justify-center shrink-0 border transition-colors ${
                    isSelected
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
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
