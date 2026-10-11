"use client";

import React from "react";
import Link from "next/link";
import { Plus, Minus, Trash2, AlertTriangle, PlusCircle } from "lucide-react";

export interface CartItem {
  id: string;
  name: string;
  price: number;
  salePrice?: number | null;
  quantity: number;
  image: string;
  unit: string;
  isPrescription: boolean;
  dbId?: number;
  skuId?: number;
  cartKey?: string;
  catalogTier?: string;
  isSaleEligible?: boolean;
}

interface CartItemsTableProps {
  items: CartItem[];
  onUpdateQuantity: (id: string, delta: number) => void;
  onRemoveItem: (id: string) => void;
  onClearCart?: () => void;
}

export default function CartItemsTable({
  items,
  onUpdateQuantity,
  onRemoveItem,
  onClearCart,
}: CartItemsTableProps) {
  const hasPrescriptionItem = items.some((it) => it.isPrescription);
  const totalCount = items.reduce((sum, it) => sum + it.quantity, 0);

  return (
    <div className="bg-white rounded-xl border border-slate-200 overflow-hidden shadow-xs">
      {/* Header Bar */}
      <div className="px-4 py-3 bg-slate-50/80 border-b border-slate-200 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h2 className="text-sm font-bold text-slate-900">
            Sản phẩm trong giỏ ({totalCount})
          </h2>
        </div>

        {onClearCart && items.length > 0 && (
          <button
            type="button"
            onClick={onClearCart}
            className="text-xs text-slate-500 hover:text-rose-600 transition-colors flex items-center gap-1 font-medium"
          >
            <Trash2 className="w-3.5 h-3.5" />
            <span>Xóa tất cả</span>
          </button>
        )}
      </div>

      {/* Prescription Warning Notice (if applicable) */}
      {hasPrescriptionItem && (
        <div className="mx-4 mt-3 p-3 bg-rose-50 border border-rose-200 rounded-xl flex items-start gap-2.5 text-xs text-rose-900">
          <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
          <div className="leading-relaxed flex-1">
            <span className="font-bold">Lưu ý thuốc kê đơn (Rx): </span>
            Theo quy định của Bộ Y Tế, thuốc kê đơn không được phép bán trực tuyến. Quý khách vui lòng gửi đơn thuốc qua chuyên mục{" "}
            <Link href="/prescription" className="text-brand-blue-700 underline font-semibold">
              Tư Vấn Dược Sĩ & Gửi Đơn Thuốc
            </Link>{" "}
            hoặc xóa thuốc kê đơn khỏi giỏ hàng để tiếp tục thanh toán các sản phẩm OTC.
          </div>
        </div>
      )}

      {/* Product List */}
      <div className="divide-y divide-slate-100">
        {items.map((item) => {
          const itemTotal = (item.salePrice || item.price) * item.quantity;
          return (
            <div
              key={item.id}
              className="p-4 flex flex-col sm:flex-row sm:items-center gap-3 sm:gap-4 hover:bg-slate-50/50 transition-colors"
            >
              {/* Product Thumbnail */}
              <div className="w-16 h-16 sm:w-18 sm:h-18 rounded-lg bg-slate-50 border border-slate-200 p-1 shrink-0 overflow-hidden flex items-center justify-center">
                <img
                  src={item.image}
                  alt={item.name}
                  className="w-full h-full object-contain"
                  onError={(e) => {
                    (e.target as HTMLImageElement).src =
                      "https://images.unsplash.com/photo-1584308666744-24d5c474f2ae?w=300&auto=format&fit=crop&q=80";
                  }}
                />
              </div>

              {/* Product Info */}
              <div className="flex-1 min-w-0">
                <div className="flex items-start gap-2">
                  <h3 className="text-xs sm:text-sm font-semibold text-slate-900 line-clamp-2 leading-snug">
                    {item.name}
                  </h3>
                </div>

                <div className="flex flex-wrap items-center gap-2 mt-1">
                  <span className="text-xs font-bold text-slate-900">
                    {(item.salePrice || item.price).toLocaleString("vi-VN")} đ
                  </span>
                  <span className="text-[11px] text-slate-500">/{item.unit || "Hộp"}</span>

                  {item.salePrice && item.salePrice < item.price && (
                    <span className="text-[11px] text-slate-400 line-through">
                      {item.price.toLocaleString("vi-VN")} đ
                    </span>
                  )}

                  {item.isPrescription && (
                    <span className="text-[10px] font-bold text-amber-700 bg-amber-50 px-1.5 py-0.5 rounded border border-amber-200">
                      Thuốc kê đơn (Rx)
                    </span>
                  )}
                </div>
              </div>

              {/* Quantity Controls & Line Total */}
              <div className="flex items-center justify-between sm:justify-end gap-4 shrink-0 pt-2 sm:pt-0 border-t sm:border-t-0 border-slate-100">
                {/* Quantity adjuster */}
                <div className="inline-flex items-center border border-slate-200 rounded-lg bg-white overflow-hidden shadow-2xs">
                  <button
                    type="button"
                    onClick={() => onUpdateQuantity(item.id, -1)}
                    className="w-7 h-7 flex items-center justify-center text-slate-600 hover:bg-slate-100 hover:text-slate-900 transition-colors"
                    aria-label="Giảm số lượng"
                  >
                    <Minus className="w-3 h-3" />
                  </button>
                  <span className="w-9 text-center text-xs font-bold text-slate-900 select-none">
                    {item.quantity}
                  </span>
                  <button
                    type="button"
                    onClick={() => onUpdateQuantity(item.id, 1)}
                    className="w-7 h-7 flex items-center justify-center text-slate-600 hover:bg-slate-100 hover:text-slate-900 transition-colors"
                    aria-label="Tăng số lượng"
                  >
                    <Plus className="w-3 h-3" />
                  </button>
                </div>

                {/* Subtotal */}
                <div className="text-right min-w-[90px]">
                  <span className="text-xs sm:text-sm font-bold text-brand-blue-700">
                    {itemTotal.toLocaleString("vi-VN")} đ
                  </span>
                </div>

                {/* Delete button */}
                <button
                  type="button"
                  onClick={() => onRemoveItem(item.id)}
                  className="p-1.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-md transition-colors"
                  title="Xóa khỏi đơn"
                  aria-label="Xóa sản phẩm"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {/* Footer link to continue shopping */}
      <div className="p-3 bg-slate-50/50 border-t border-slate-100 flex items-center justify-between">
        <Link
          href="/products"
          className="inline-flex items-center gap-1.5 text-xs font-medium text-brand-blue-700 hover:text-brand-blue-800 hover:underline"
        >
          <PlusCircle className="w-3.5 h-3.5" />
          <span>Chọn thêm sản phẩm khác</span>
        </Link>
      </div>
    </div>
  );
}
