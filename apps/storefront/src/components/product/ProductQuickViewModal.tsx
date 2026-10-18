"use client";

import React, { useState } from "react";
import { Product } from "@/types";
import { motion, AnimatePresence } from "framer-motion";
import {
  X,
  Star,
  ShieldCheck,
  Stethoscope,
  ShoppingBag,
  CheckCircle2,
  ArrowRight,
  AlertCircle,
  Info,
} from "lucide-react";
import { formatVND } from "@/lib/utils";
import { Button } from "../ui/Button";
import Link from "next/link";

interface ProductQuickViewModalProps {
  product: Product | null;
  isOpen: boolean;
  onClose: () => void;
  onOpenRxConsult: (product: Product) => void;
  onAddToCart?: (product: Product) => void;
}

export const ProductQuickViewModal: React.FC<ProductQuickViewModalProps> = ({
  product,
  isOpen,
  onClose,
  onOpenRxConsult,
  onAddToCart,
}) => {
  const [selectedImageIdx, setSelectedImageIdx] = useState(0);

  if (!isOpen || !product) return null;

  const discountPercent =
    product.salePrice && product.salePrice < product.price
      ? Math.round(((product.price - product.salePrice) / product.price) * 100)
      : 0;

  const currentPrice = product.salePrice || product.price;

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
        {/* Backdrop */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={onClose}
          className="absolute inset-0 bg-black/50 backdrop-blur-xs"
        />

        {/* Modal Window */}
        <motion.div
          initial={{ opacity: 0, scale: 0.95, y: 15 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: 15 }}
          transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
          className="relative w-full max-w-3xl bg-white rounded-2xl shadow-xl border border-slate-200 overflow-hidden z-10 max-h-[90vh] flex flex-col"
        >
          {/* Close button */}
          <button
            onClick={onClose}
            className="absolute top-4 right-4 z-20 p-2 rounded-full bg-slate-100 hover:bg-slate-200 text-slate-500 hover:text-slate-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>

          <div className="overflow-y-auto p-6 md:p-8">
            <div className="grid grid-cols-1 md:grid-cols-12 gap-6">
              {/* Left Column: Image Gallery */}
              <div className="md:col-span-5 flex flex-col items-center">
                <div className="relative w-full aspect-square rounded-xl bg-slate-50 border border-slate-200 overflow-hidden flex items-center justify-center p-4 group">
                  <img
                    src={product.images[selectedImageIdx] || product.images[0]}
                    alt={product.name}
                    className="w-full h-full object-contain mix-blend-multiply group-hover:scale-105 transition-transform duration-300"
                  />
                  {discountPercent > 0 && (
                    <span className="absolute top-3 left-3 bg-rose-500 text-white text-xs font-black px-2 py-0.5 rounded-full shadow-xs">
                      -{discountPercent}%
                    </span>
                  )}
                  {product.isPrescription && (
                    <span className="absolute bottom-3 left-3 bg-rose-50 text-rose-700 border border-rose-200 text-[10px] font-bold px-2 py-0.5 rounded-full">
                      Thuốc kê đơn (Rx)
                    </span>
                  )}
                </div>

                {/* Thumbnails if multiple */}
                {product.images.length > 1 && (
                  <div className="flex gap-2 mt-3 overflow-x-auto w-full pb-1">
                    {product.images.map((img, i) => (
                      <button
                        key={i}
                        onClick={() => setSelectedImageIdx(i)}
                        className={`w-14 h-14 rounded-xl border-2 p-1 bg-slate-50 shrink-0 overflow-hidden transition-all ${
                          selectedImageIdx === i
                            ? "border-brand-blue-600 shadow-xs"
                            : "border-slate-200 opacity-70 hover:opacity-100"
                        }`}
                      >
                        <img src={img} alt="" className="w-full h-full object-contain" />
                      </button>
                    ))}
                  </div>
                )}
              </div>

              {/* Right Column: Product details */}
              <div className="md:col-span-7 flex flex-col justify-between">
                <div>
                  <div className="flex items-center gap-2 mb-1.5">
                    <span className="text-xs font-bold text-slate-400 uppercase tracking-wider">
                      {product.brand}
                    </span>
                    <span className="text-slate-300">•</span>
                    <span className="text-xs text-slate-400">SKU: {product.sku}</span>
                  </div>

                  <h3 className="text-lg font-bold text-slate-900 leading-snug mb-2">
                    {product.name}
                  </h3>

                  {/* Rating and Reviews */}
                  <div className="flex items-center gap-2 mb-3 text-xs">
                    <div className="flex text-amber-400">
                      {[...Array(5)].map((_, i) => (
                        <Star
                          key={i}
                          className={`w-3.5 h-3.5 ${
                            (product.reviewCount ?? 0) > 0 && i < Math.floor(product.rating ?? 0)
                              ? "fill-current"
                              : "text-slate-200"
                          }`}
                        />
                      ))}
                    </div>
                    <span className="font-bold text-slate-800">
                      {(product.reviewCount ?? 0) > 0 ? (product.rating ?? 0).toFixed(1) : "0.0"}
                    </span>
                    <span className="text-slate-400">({product.reviewCount ?? 0} đánh giá)</span>
                    <span className="text-slate-300">|</span>
                    {product.isPrescription ? (
                      <span className="text-rose-600 font-semibold flex items-center gap-1">
                        <AlertCircle className="w-3.5 h-3.5" />
                        Cần đơn Bác sĩ
                      </span>
                    ) : product.catalogTier === "REFERENCE_ONLY" || product.isSaleEligible === false ? (
                      <span className="text-amber-700 font-semibold flex items-center gap-1">
                        <Info className="w-3.5 h-3.5" />
                        Tra cứu y tế
                      </span>
                    ) : (
                      <span className="text-emerald-600 font-semibold flex items-center gap-1">
                        <CheckCircle2 className="w-3.5 h-3.5" />
                        Còn hàng
                      </span>
                    )}
                  </div>

                  {/* Pricing */}
                  <div className="p-3 rounded-xl bg-slate-50 border border-slate-200 mb-4 flex flex-col gap-1">
                    {product.catalogTier === "REFERENCE_ONLY" || product.isSaleEligible === false ? (
                      <div>
                        <div className="flex items-baseline gap-2">
                          <span className="text-xl font-bold text-slate-700">
                            {currentPrice > 0 ? `~${formatVND(currentPrice)}` : "Liên hệ tra cứu"}
                          </span>
                          <span className="text-xs text-slate-500 font-medium">/ {product.packaging}</span>
                        </div>
                        <span className="text-[11px] text-amber-700 bg-amber-100/70 px-2 py-0.5 rounded font-medium inline-block mt-1">
                          Giá tham khảo phục vụ tra cứu thông tin y tế (Chưa mở bán thương mại)
                        </span>
                      </div>
                    ) : (
                      <div className="flex items-baseline gap-3">
                        <span className="text-2xl font-black text-brand-blue-700">
                          {formatVND(currentPrice)}
                        </span>
                        {product.salePrice && (
                          <span className="text-sm text-slate-400 line-through">
                            {formatVND(product.price)}
                          </span>
                        )}
                        <span className="text-xs text-slate-500 font-medium">
                          / {product.packaging}
                        </span>
                        <span className="text-[10px] text-emerald-600 font-semibold ml-auto">
                          Đã có VAT
                        </span>
                      </div>
                    )}
                  </div>

                  {/* Medical Specs bullet points */}
                  <div className="space-y-1.5 text-xs text-slate-600 mb-4">
                    <p>
                      <span className="font-semibold text-slate-800">Hoạt chất: </span>
                      {product.activeIngredient}
                    </p>
                    <p>
                      <span className="font-semibold text-slate-800">Dạng bào chế: </span>
                      {product.dosageForm}
                    </p>
                    <p>
                      <span className="font-semibold text-slate-800">Xuất xứ: </span>
                      {product.origin} ({product.manufacturer})
                    </p>
                  </div>

                  <p className="text-xs text-slate-500 line-clamp-2 mb-4 leading-relaxed">
                    {product.shortDescription}
                  </p>
                </div>

                {/* Actions */}
                <div className="space-y-2.5 pt-2 border-t border-slate-100">
                  {product.isPrescription ? (
                    <div>
                      <div className="p-2.5 rounded-xl bg-rose-50 border border-rose-200/80 mb-2 flex items-center gap-2 text-xs text-rose-800">
                        <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
                        <span>Thuốc kê đơn (Rx) - Cần tư vấn và kiểm duyệt đơn thuốc.</span>
                      </div>
                      <Button
                        variant="primary"
                        size="md"
                        className="w-full bg-brand-blue-600 hover:bg-brand-blue-700 active:bg-brand-blue-800 shadow-xs"
                        leftIcon={<Stethoscope className="w-4 h-4" />}
                        onClick={() => {
                          onClose();
                          onOpenRxConsult(product);
                        }}
                      >
                        Tư Vấn Dược Sĩ & Gửi Đơn Thuốc
                      </Button>
                    </div>
                  ) : product.catalogTier === "REFERENCE_ONLY" ? (
                    <div>
                      <div className="p-2.5 rounded-xl bg-amber-50 border border-amber-200/80 mb-2 flex items-center gap-2 text-xs text-amber-800">
                        <Info className="w-4 h-4 text-amber-600 shrink-0" />
                        <span>Danh mục tra cứu thông tin y tế (Chưa mở bán online).</span>
                      </div>
                      <Link href={`/product/${product.slug}`} onClick={onClose} className="block w-full">
                        <Button
                          variant="primary"
                          size="md"
                          className="w-full bg-slate-800 hover:bg-slate-900 shadow-xs text-white"
                          leftIcon={<Info className="w-4 h-4" />}
                        >
                          Tra Cứu Thông Tin Dược Lý
                        </Button>
                      </Link>
                    </div>
                  ) : (
                    <div className="flex items-center gap-3">
                      <Button
                        variant="primary"
                        size="md"
                        className="flex-1 shadow-xs"
                        leftIcon={<ShoppingBag className="w-4 h-4" />}
                        onClick={() => {
                          if (onAddToCart) {
                            onAddToCart(product);
                          } else {
                            try {
                              let cart: any[] = [];
                              const raw = localStorage.getItem("pharmatrust_cart");
                              if (raw) {
                                const parsed = JSON.parse(raw);
                                if (Array.isArray(parsed)) cart = parsed;
                              }
                              const dbId =
                                product.dbId ||
                                (product.id && product.id.startsWith("pt-")
                                  ? parseInt(product.id.replace("pt-", ""), 10)
                                  : 1);
                              const existing = cart.findIndex((i: any) => i.id === product.id);
                              if (existing > -1) {
                                cart[existing].quantity += 1;
                              } else {
                                cart.push({
                                  id: product.id,
                                  dbId: dbId,
                                  name: product.name,
                                  price: product.salePrice || product.price,
                                  salePrice: product.salePrice,
                                  quantity: 1,
                                  image: (product.images && product.images[0]) || "/images/medicines/panadol.jpg",
                                  unit: product.packaging || "Hộp",
                                  isPrescription: false,
                                });
                              }
                              localStorage.setItem("pharmatrust_cart", JSON.stringify(cart));
                              window.dispatchEvent(new Event("cart_updated"));
                            } catch (err) {}
                          }
                          onClose();
                        }}
                      >
                        Chọn Mua Ngay
                      </Button>
                    </div>
                  )}

                  <div className="text-center pt-1">
                    <Link
                      href={`/product/${product.slug}`}
                      onClick={onClose}
                      className="text-xs font-semibold text-brand-blue-600 hover:text-brand-blue-800 inline-flex items-center gap-1 group"
                    >
                      <span>Xem toàn bộ thông tin chi tiết & dược lý</span>
                      <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-1 transition-transform" />
                    </Link>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
};
