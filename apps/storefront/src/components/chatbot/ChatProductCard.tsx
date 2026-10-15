"use client";

import React, { useState } from "react";
import Link from "next/link";
import { ChatProductItem } from "@/lib/chatbot/types";
import { ArrowRight, Pill, ShieldCheck, AlertCircle } from "lucide-react";

interface ChatProductCardProps {
  product: ChatProductItem;
}

export const ChatProductCard: React.FC<ChatProductCardProps> = ({ product }) => {
  const [imgSrc, setImgSrc] = useState<string>(
    product.image || "https://images.unsplash.com/photo-1584308666744-24d5c474f2ae?w=800"
  );

  const formattedPrice = (product.salePrice || product.price).toLocaleString("vi-VN");
  const originalPrice = product.salePrice ? product.price.toLocaleString("vi-VN") : null;

  return (
    <div className="group bg-white rounded-xl border border-slate-200/90 shadow-2xs hover:shadow-xs hover:border-brand-blue-300 transition-all duration-200 overflow-hidden flex flex-col">
      {/* Phần trên: Ảnh & Tag */}
      <div className="relative h-28 bg-slate-50 flex items-center justify-center p-2 border-b border-slate-100 overflow-hidden">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={imgSrc}
          alt={product.name}
          onError={() =>
            setImgSrc("https://images.unsplash.com/photo-1584308666744-24d5c474f2ae?w=800")
          }
          className="max-h-full max-w-full object-contain group-hover:scale-105 transition-transform duration-300"
        />

        {/* Badge Phân Loại Rx / OTC */}
        <div className="absolute top-1.5 left-1.5 flex gap-1">
          {product.isPrescription ? (
            <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-md bg-amber-500/90 text-white text-[10px] font-bold shadow-xs backdrop-blur-xs">
              <AlertCircle className="w-2.5 h-2.5" />
              Rx Kê Đơn
            </span>
          ) : (
            <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-md bg-emerald-600/90 text-white text-[10px] font-bold shadow-xs backdrop-blur-xs">
              <ShieldCheck className="w-2.5 h-2.5" />
              OTC
            </span>
          )}
        </div>

        {/* Tồn kho */}
        <div className="absolute top-1.5 right-1.5">
          {product.stock > 0 ? (
            <span className="px-1.5 py-0.5 rounded-md bg-white/95 text-emerald-700 text-[10px] font-semibold border border-emerald-200 shadow-2xs">
              Còn hàng
            </span>
          ) : (
            <span className="px-1.5 py-0.5 rounded-md bg-white/95 text-slate-500 text-[10px] font-semibold border border-slate-200 shadow-2xs">
              Hết hàng
            </span>
          )}
        </div>
      </div>

      {/* Phần dưới: Thông tin chi tiết */}
      <div className="p-2.5 flex-1 flex flex-col justify-between">
        <div>
          <div className="text-[10px] font-medium text-slate-400 uppercase tracking-wider line-clamp-1">
            {product.brand}
          </div>
          <Link
            href={`/product/${product.slug}`}
            className="text-xs font-bold text-slate-800 hover:text-brand-blue-600 transition-colors line-clamp-2 mt-0.5 leading-snug"
            title={product.name}
          >
            {product.name}
          </Link>

          {product.activeIngredient && (
            <div className="flex items-center gap-1 mt-1 text-[11px] text-slate-500">
              <Pill className="w-3 h-3 text-brand-blue-500 shrink-0" />
              <span className="truncate italic">{product.activeIngredient}</span>
            </div>
          )}
        </div>

        {/* Giá & Nút hành động */}
        <div className="mt-2 pt-2 border-t border-slate-100 flex items-center justify-between">
          <div>
            <div className="text-xs font-black text-brand-blue-700">
              {formattedPrice} <span className="text-[10px] font-bold">đ</span>
            </div>
            {originalPrice && (
              <div className="text-[10px] text-slate-400 line-through">
                {originalPrice} đ
              </div>
            )}
          </div>

          <Link
            href={`/product/${product.slug}`}
            className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-brand-blue-50 text-brand-blue-700 hover:bg-brand-blue-600 hover:text-white text-[11px] font-bold transition-all"
          >
            Chi tiết
            <ArrowRight className="w-3 h-3" />
          </Link>
        </div>
      </div>
    </div>
  );
};
