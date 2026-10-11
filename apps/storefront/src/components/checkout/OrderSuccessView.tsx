"use client";

import React, { useState } from "react";
import Link from "next/link";
import {
  CheckCircle2,
  Copy,
  Check,
  ShoppingBag,
  FileText,
  PhoneCall,
  Clock,
  ArrowRight,
  ShieldCheck,
} from "lucide-react";
import { PHARMACY_CONTACT } from "@/lib/constants";

export interface OrderSuccessData {
  order_code: string;
  total: number;
  customer_name: string;
  customer_phone?: string;
  shipping_address: string;
  payment_method: string;
  fulfillment_type?: "DELIVERY" | "STORE_PICKUP";
  store_name?: string;
}

interface OrderSuccessViewProps {
  order: OrderSuccessData;
  isAuthenticated?: boolean;
}

export default function OrderSuccessView({
  order,
  isAuthenticated = false,
}: OrderSuccessViewProps) {
  const [copied, setCopied] = useState(false);

  const handleCopyCode = () => {
    navigator.clipboard.writeText(order.order_code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="max-w-2xl mx-auto my-8 bg-white rounded-2xl border border-slate-200 overflow-hidden shadow-xs">
      {/* Top Banner */}
      <div className="p-6 sm:p-8 text-center bg-gradient-to-b from-emerald-50/70 to-white border-b border-slate-100">
        <div className="w-16 h-16 rounded-full bg-emerald-100 text-emerald-600 flex items-center justify-center mx-auto mb-3.5 ring-8 ring-emerald-50">
          <CheckCircle2 className="w-8 h-8" />
        </div>

        <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-100/80 text-emerald-800 text-xs font-bold mb-2">
          Đặt đơn thuốc thành công
        </span>

        <h1 className="text-xl sm:text-2xl font-black text-slate-900 tracking-tight">
          Cảm ơn bạn đã tin chọn Nhà thuốc H4CARE!
        </h1>

        <p className="text-xs sm:text-sm text-slate-600 mt-2 max-w-md mx-auto leading-relaxed">
          Đơn thuốc của bạn đã được chuyển tới Dược sĩ chuyên môn. Chúng tôi sẽ liên hệ số điện thoại{" "}
          <strong className="text-slate-900 font-bold">{order.customer_phone || "của bạn"}</strong> trong vòng 15 phút để tư vấn và xác nhận giao thuốc.
        </p>
      </div>

      {/* Order Details Receipt */}
      <div className="p-6 space-y-4">
        <div className="bg-slate-50 rounded-xl p-4 sm:p-5 border border-slate-200/80 space-y-3 text-xs sm:text-sm">
          {/* Order Code */}
          <div className="flex items-center justify-between pb-3 border-b border-slate-200">
            <span className="text-slate-500">Mã đơn hàng:</span>
            <div className="flex items-center gap-2">
              <span className="font-mono font-bold text-brand-blue-700 text-base">
                {order.order_code}
              </span>
              <button
                type="button"
                onClick={handleCopyCode}
                className="p-1 text-slate-400 hover:text-slate-700 rounded transition-colors cursor-pointer"
                title="Sao chép mã đơn"
              >
                {copied ? (
                  <Check className="w-4 h-4 text-emerald-600" />
                ) : (
                  <Copy className="w-4 h-4" />
                )}
              </button>
            </div>
          </div>

          {/* Receiver */}
          <div className="flex items-center justify-between">
            <span className="text-slate-500">Người nhận thuốc:</span>
            <span className="font-bold text-slate-900">{order.customer_name}</span>
          </div>

          {/* Fulfillment & Address */}
          <div className="flex items-start justify-between gap-4">
            <span className="text-slate-500 shrink-0">
              {order.fulfillment_type === "STORE_PICKUP"
                ? "Nhận tại nhà thuốc:"
                : "Địa chỉ giao hàng:"}
            </span>
            <span className="font-medium text-slate-900 text-right leading-relaxed">
              {order.store_name || order.shipping_address}
            </span>
          </div>

          {/* Payment Method */}
          <div className="flex items-center justify-between">
            <span className="text-slate-500">Hình thức thanh toán:</span>
            <span className="font-semibold text-slate-900">
              {order.payment_method === "MOMO" ? (
                <span className="inline-flex items-center gap-1 font-bold text-pink-700 bg-pink-50 px-2 py-0.5 rounded border border-pink-200 text-xs">
                  Ví điện tử MoMo
                </span>
              ) : order.payment_method === "BANK_TRANSFER" ? (
                "Chuyển khoản VietQR"
              ) : (
                "Tiền mặt khi nhận hàng (COD)"
              )}
            </span>
          </div>

          {/* Total Amount */}
          <div className="flex items-center justify-between pt-3 border-t border-slate-200 text-base">
            <span className="font-bold text-slate-900">Tổng thanh toán:</span>
            <span className="font-black text-rose-600 text-lg sm:text-xl font-mono">
              {order.total.toLocaleString("vi-VN")} đ
            </span>
          </div>
        </div>

        {/* Guidance Notice */}
        <div className="p-3.5 bg-blue-50/60 border border-blue-100 rounded-xl flex items-start gap-2.5 text-xs text-slate-700">
          <Clock className="w-4 h-4 text-brand-blue-600 shrink-0 mt-0.5" />
          <div className="leading-relaxed">
            <p className="font-bold text-brand-blue-900">Thời gian giao hàng dự kiến:</p>
            <p className="text-slate-600 mt-0.5">
              Nội thành: Giao siêu tốc trong 1-2 giờ. Các khu vực khác: 1-2 ngày làm việc.
            </p>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="pt-2 flex flex-col sm:flex-row items-center justify-center gap-3">
          {isAuthenticated ? (
            <Link
              href="/account#orders"
              className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-6 py-3 rounded-xl bg-brand-blue-600 hover:bg-brand-blue-700 text-white font-bold text-sm shadow-xs transition-all cursor-pointer"
            >
              <FileText className="w-4 h-4" />
              <span>Theo dõi đơn hàng của tôi</span>
            </Link>
          ) : (
            <Link
              href={`/account?phone=${encodeURIComponent(order.customer_phone || "")}`}
              className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-6 py-3 rounded-xl bg-brand-blue-600 hover:bg-brand-blue-700 text-white font-bold text-sm shadow-xs transition-all cursor-pointer"
            >
              <FileText className="w-4 h-4" />
              <span>Tra cứu tiến độ đơn thuốc</span>
            </Link>
          )}

          <Link
            href="/products"
            className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-6 py-3 rounded-xl border border-slate-200 hover:bg-slate-50 text-slate-700 font-semibold text-sm transition-all cursor-pointer"
          >
            <ShoppingBag className="w-4 h-4 text-slate-500" />
            <span>Tiếp tục mua sắm</span>
          </Link>
        </div>

        {/* Pharmacy Support Hotline */}
        <div className="pt-4 text-center text-xs text-slate-500">
          Cần hỗ trợ về đơn hàng hoặc toa thuốc? Vui lòng gửi email tới{" "}
          <span className="font-bold text-brand-blue-700">{PHARMACY_CONTACT.supportEmail}</span>{" "}
          hoặc gửi yêu cầu qua trang{" "}
          <Link href="/prescription" className="text-brand-blue-600 underline font-semibold">
            Tư vấn Dược sĩ trực tuyến
          </Link>
          . ({PHARMACY_CONTACT.operatingHours})
        </div>
      </div>
    </div>
  );
}
