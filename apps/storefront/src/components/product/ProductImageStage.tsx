"use client";

import React, { useState } from "react";
import { Product } from "@/types";
import {
  Pill,
  Droplets,
  Package,
  Activity,
  HeartPulse,
  Sparkles,
  Layers,
  Thermometer,
} from "lucide-react";

interface ProductImageStageProps {
  product: Product;
  className?: string;
  isHoverable?: boolean;
}

export const ProductImageStage: React.FC<ProductImageStageProps> = ({
  product,
  className = "",
  isHoverable = true,
}) => {
  const [imgError, setImgError] = useState(false);
  const [isLoaded, setIsLoaded] = useState(false);

  // Helper to render dosage form icon & styling for clean pharmaceutical presentation
  const renderDosageVisual = () => {
    const dosage = (product.dosageForm || "").toLowerCase();
    const category = (product.category || "").toLowerCase();

    if (category.includes("thiet-bi") || category.includes("thiết bị")) {
      return (
        <div className="flex flex-col items-center justify-center text-center p-3">
          <div className="w-14 h-14 rounded-2xl bg-cyan-50 border border-cyan-100 flex items-center justify-center text-cyan-600 shadow-sm mb-2">
            <HeartPulse className="w-7 h-7" />
          </div>
          <span className="text-[10px] font-bold text-slate-700 block leading-tight">
            {product.brand}
          </span>
          <span className="text-[9px] text-slate-400 font-medium mt-0.5">
            Thiết Bị Y Tế
          </span>
        </div>
      );
    }

    if (dosage.includes("hỗn dịch") || dosage.includes("gói") || dosage.includes("cốm")) {
      return (
        <div className="flex flex-col items-center justify-center text-center p-3">
          <div className="w-12 h-16 rounded-xl bg-gradient-to-b from-blue-50 via-cyan-50 to-slate-100 border border-brand-blue-100 flex flex-col items-center justify-between p-1.5 shadow-sm mb-2">
            <Droplets className="w-4 h-4 text-brand-cyan-600 mt-1" />
            <span className="text-[7.5px] font-bold text-brand-blue-800 tracking-wider uppercase">
              Gói Uống
            </span>
            <span className="text-[7px] text-slate-400 font-mono">10ml</span>
          </div>
          <span className="text-[10px] font-bold text-slate-700 block leading-tight">
            {product.brand}
          </span>
          <span className="text-[9px] text-slate-400 font-medium mt-0.5">
            {product.dosageForm}
          </span>
        </div>
      );
    }

    if (dosage.includes("nang") || dosage.includes("capsule")) {
      return (
        <div className="flex flex-col items-center justify-center text-center p-3">
          <div className="w-14 h-14 rounded-2xl bg-emerald-50 border border-emerald-100 flex items-center justify-center text-emerald-600 shadow-sm mb-2">
            <Pill className="w-7 h-7 rotate-45" />
          </div>
          <span className="text-[10px] font-bold text-slate-700 block leading-tight">
            {product.brand}
          </span>
          <span className="text-[9px] text-slate-400 font-medium mt-0.5">
            Viên Nang
          </span>
        </div>
      );
    }

    // Default pharmaceutical blister/tablet packaging presentation
    return (
      <div className="flex flex-col items-center justify-center text-center p-3">
        <div className="w-14 h-14 rounded-2xl bg-brand-blue-50 border border-brand-blue-100 flex items-center justify-center text-brand-blue-600 shadow-sm mb-2">
          <Layers className="w-7 h-7" />
        </div>
        <span className="text-[10px] font-bold text-slate-700 block leading-tight">
          {product.brand}
        </span>
        <span className="text-[9px] text-slate-400 font-medium mt-0.5">
          {product.dosageForm || "Quy cách đóng gói"}
        </span>
      </div>
    );
  };

  const primaryImage = product.images?.[0];
  const hasValidImage = primaryImage && !imgError;

  return (
    <div
      className={`relative w-full aspect-square rounded-2xl bg-gradient-to-b from-[#f8fafc] to-[#f1f5f9]/70 overflow-hidden flex items-center justify-center p-3 border border-slate-100/90 select-none group-hover:border-brand-blue-100 transition-colors ${className}`}
    >
      {/* Subtle radial ambient background glow */}
      <div className="absolute inset-0 bg-radial from-white via-transparent to-transparent opacity-80 pointer-events-none" />

      {hasValidImage ? (
        <img
          src={primaryImage}
          alt={product.name}
          onLoad={() => setIsLoaded(true)}
          onError={() => setImgError(true)}
          className={`relative z-0 w-full h-full object-contain mix-blend-multiply transition-all duration-300 ${
            isHoverable ? "group-hover:scale-[1.03]" : ""
          } ${isLoaded ? "opacity-100" : "opacity-0"}`}
          loading="lazy"
        />
      ) : (
        <div
          className={`relative z-0 w-full h-full flex items-center justify-center transition-transform duration-300 ${
            isHoverable ? "group-hover:scale-[1.02]" : ""
          }`}
        >
          {renderDosageVisual()}
        </div>
      )}

      {/* Subtle soft grounding shadow under product */}
      <div className="absolute bottom-2 left-1/2 -translate-x-1/2 w-24 h-2 bg-slate-900/5 rounded-full blur-xs pointer-events-none" />
    </div>
  );
};
