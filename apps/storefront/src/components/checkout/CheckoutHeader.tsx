"use client";

import React from "react";
import Link from "next/link";
import { ArrowLeft, ShieldCheck } from "lucide-react";
import { PHARMACY_CONTACT } from "@/lib/constants";

interface CheckoutHeaderProps {
  currentStep?: 1 | 2 | 3;
  totalItems?: number;
}

export default function CheckoutHeader({
  currentStep = 2,
  totalItems = 0,
}: CheckoutHeaderProps) {
  return (
    <div className="bg-white border-b border-slate-200">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3.5">
        <div className="flex flex-col sm:flex-row items-center justify-between gap-3 sm:gap-4">
          {/* Left: Back & Title */}
          <div className="flex items-center gap-3 w-full sm:w-auto justify-between sm:justify-start">
            <Link
              href="/products"
              className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-600 hover:text-brand-blue-700 transition-colors py-1 px-2 rounded-lg hover:bg-slate-100"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              <span>Tiếp tục mua hàng</span>
            </Link>

            <div className="h-4 w-px bg-slate-200 hidden sm:block" />

            <div className="flex items-center gap-2">
              <h1 className="text-base sm:text-lg font-bold text-slate-900">
                Thanh toán đơn hàng
              </h1>
              {totalItems > 0 && (
                <span className="text-xs font-medium text-slate-500 bg-slate-100 px-2 py-0.5 rounded-full">
                  {totalItems} sản phẩm
                </span>
              )}
            </div>
          </div>

          {/* Center / Right: Step Indicator (Long Châu style) */}
          <div className="flex items-center gap-2 text-xs font-semibold">
            <div
              className={`flex items-center gap-1.5 ${
                currentStep >= 1 ? "text-brand-blue-700 font-bold" : "text-slate-400"
              }`}
            >
              <span
                className={`w-5 h-5 rounded-full flex items-center justify-center text-[11px] font-bold ${
                  currentStep >= 1
                    ? "bg-brand-blue-600 text-white"
                    : "bg-slate-100 text-slate-500"
                }`}
              >
                1
              </span>
              <span>Giỏ hàng</span>
            </div>

            <div
              className={`w-6 h-0.5 ${
                currentStep >= 2 ? "bg-brand-blue-600" : "bg-slate-200"
              }`}
            />

            <div
              className={`flex items-center gap-1.5 ${
                currentStep >= 2 ? "text-brand-blue-700 font-bold" : "text-slate-400"
              }`}
            >
              <span
                className={`w-5 h-5 rounded-full flex items-center justify-center text-[11px] font-bold ${
                  currentStep >= 2
                    ? "bg-brand-blue-600 text-white"
                    : "bg-slate-100 text-slate-500"
                }`}
              >
                2
              </span>
              <span>Đặt hàng</span>
            </div>

            <div
              className={`w-6 h-0.5 ${
                currentStep >= 3 ? "bg-brand-blue-600" : "bg-slate-200"
              }`}
            />

            <div
              className={`flex items-center gap-1.5 ${
                currentStep >= 3 ? "text-brand-blue-700 font-bold" : "text-slate-400"
              }`}
            >
              <span
                className={`w-5 h-5 rounded-full flex items-center justify-center text-[11px] font-bold ${
                  currentStep >= 3
                    ? "bg-brand-blue-600 text-white"
                    : "bg-slate-100 text-slate-500"
                }`}
              >
                3
              </span>
              <span>Hoàn tất</span>
            </div>
          </div>

          {/* Right: Support Info */}
          <div className="hidden lg:flex items-center gap-2 text-xs text-slate-600">
            <span className="text-slate-400">Hỗ trợ đơn hàng:</span>
            <span className="font-semibold text-slate-700">{PHARMACY_CONTACT.supportEmail}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
