"use client";

import React from "react";
import { Banknote, QrCode, Check } from "lucide-react";

export type PaymentMethod = "COD" | "BANK_TRANSFER" | "MOMO" | "PAYOS";

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
      desc: "Kiểm tra hàng trước khi thanh toán tiền mặt cho shipper",
      icon: <Banknote className="w-5 h-5 text-brand-blue-600" />,
      tag: "Phổ biến nhất",
      tagColor: "bg-emerald-50 text-emerald-700 border-emerald-200",
    },
    {
      id: "PAYOS" as PaymentMethod,
      title: "Cổng thanh toán payOS (QR Ngân hàng / Napas 247)",
      desc: "Thanh toán quét mã VietQR tự động khớp tiền tức thì 24/7 qua cổng payOS",
      icon: (
        <span className="w-5 h-5 rounded-full bg-blue-600 text-white flex items-center justify-center text-[10px] font-black shrink-0">
          P
        </span>
      ),
      tag: "Tự động 24/7",
      tagColor: "bg-blue-50 text-brand-blue-700 border-blue-200",
    },
    {
      id: "BANK_TRANSFER" as PaymentMethod,
      title: "Chuyển khoản thủ công (VietQR Napas 247)",
      desc: "Quét mã QR chuyển khoản tới tài khoản nhà thuốc H4CARE",
      icon: <QrCode className="w-5 h-5 text-brand-blue-600" />,
      tag: "Thủ công",
      tagColor: "bg-slate-50 text-slate-700 border-slate-200",
    },
    {
      id: "MOMO" as PaymentMethod,
      title: "Ví điện tử MoMo",
      desc: "Thanh toán qua ví MoMo hoặc quét mã QR MoMo Sandbox",
      icon: (
        <span className="w-5 h-5 rounded-full bg-[#a50064] text-white flex items-center justify-center text-[10px] font-black shrink-0">
          M
        </span>
      ),
      tag: "Ví điện tử",
      tagColor: "bg-pink-50 text-pink-700 border-pink-200",
    },
  ];

  return (
    <div className="bg-white rounded-xl border border-slate-200 overflow-hidden shadow-xs p-4 sm:p-5">
      <div className="pb-3 border-b border-slate-100">
        <h2 className="text-sm font-bold text-slate-900">
          Phương thức thanh toán
        </h2>
        <p className="text-xs text-slate-500 mt-0.5">
          Chọn hình thức thanh toán thuận tiện nhất với bạn
        </p>
      </div>

      <div className="mt-3.5 space-y-2.5">
        {methods.map((m) => {
          const isSelected = paymentMethod === m.id;
          return (
            <div
              key={m.id}
              onClick={() => onChangePaymentMethod(m.id)}
              className={`p-3.5 rounded-xl border cursor-pointer transition-all flex items-start justify-between gap-3 ${
                isSelected
                  ? "border-brand-blue-600 bg-brand-blue-50/40 shadow-2xs"
                  : "border-slate-200 hover:border-slate-300 bg-white"
              }`}
            >
              <div className="flex items-start gap-3">
                <div className="w-9 h-9 rounded-lg bg-slate-50 border border-slate-200 flex items-center justify-center shrink-0 mt-0.5">
                  {m.icon}
                </div>

                <div className="space-y-0.5">
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

              {/* Radio Indicator */}
              <div
                className={`w-5 h-5 rounded-full flex items-center justify-center shrink-0 border mt-1 ${
                  isSelected
                    ? "bg-brand-blue-600 border-brand-blue-600 text-white"
                    : "border-slate-300 bg-white"
                }`}
              >
                {isSelected && <Check className="w-3 h-3 stroke-[3]" />}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
