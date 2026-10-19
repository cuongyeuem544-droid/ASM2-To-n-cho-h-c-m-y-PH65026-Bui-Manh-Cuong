"use client";

import React, { useState } from "react";
import { ProductFilterState } from "@/types";
import { CATEGORIES_DATA } from "@/data/mockData";
import {
  Filter,
  RotateCcw,
  ChevronDown,
  Check,
  ShieldCheck,
  Pill,
} from "lucide-react";

interface ProductFilterSidebarProps {
  filters: ProductFilterState;
  onFilterChange: (newFilters: ProductFilterState) => void;
  onResetFilters: () => void;
  totalProducts: number;
}

const BRANDS_LIST = [
  "GSK GlaxoSmithKline",
  "Pfizer",
  "Sanofi Aventis",
  "DHC Japan",
  "Blackmores Australia",
  "Omron Healthcare",
  "La Roche-Posay",
  "CeraVe",
  "Merck KGaA",
  "Dược Hậu Giang (DHG)",
  "Reckitt Benckiser",
  "Bayer",
  "Orihiro",
  "Microlife",
  "BioAmicus",
];

const ORIGINS_LIST = [
  "Việt Nam",
  "Pháp",
  "Nhật Bản",
  "Đức",
  "Anh (UK)",
  "Úc (Australia)",
  "Thụy Sĩ",
  "Mỹ",
  "Canada",
];

const DOSAGE_FORMS = [
  "Viên nén",
  "Viên nén bao phim",
  "Viên sủi bọt",
  "Viên nang mềm",
  "Viên nang cứng",
  "Hỗn dịch uống",
  "Siro uống",
  "Dung dịch rửa ngoài",
  "Kem bôi ngoài da (Cream)",
  "Thiết bị y tế gia đình",
];

export const ProductFilterSidebar: React.FC<ProductFilterSidebarProps> = ({
  filters,
  onFilterChange,
  onResetFilters,
  totalProducts,
}) => {
  const [openSections, setOpenSections] = useState({
    category: true,
    prescription: true,
    price: true,
    brand: true,
    dosageForm: false,
    origin: false,
  });

  const toggleSection = (section: keyof typeof openSections) => {
    setOpenSections((prev) => ({ ...prev, [section]: !prev[section] }));
  };

  const handleCategorySelect = (slug: string) => {
    onFilterChange({
      ...filters,
      category: filters.category === slug ? "" : slug,
      subCategory: "",
    });
  };

  const handlePrescriptionSelect = (type: "all" | "otc" | "rx") => {
    onFilterChange({ ...filters, prescriptionType: type });
  };

  const handlePriceSelect = (range: string) => {
    onFilterChange({
      ...filters,
      priceRange: filters.priceRange === range ? "" : range,
    });
  };

  const handleBrandToggle = (brand: string) => {
    const exists = filters.brand.includes(brand);
    const updated = exists
      ? filters.brand.filter((b) => b !== brand)
      : [...filters.brand, brand];
    onFilterChange({ ...filters, brand: updated });
  };

  const handleOriginToggle = (origin: string) => {
    const exists = filters.origin.includes(origin);
    const updated = exists
      ? filters.origin.filter((o) => o !== origin)
      : [...filters.origin, origin];
    onFilterChange({ ...filters, origin: updated });
  };

  const handleDosageToggle = (form: string) => {
    const exists = filters.dosageForm.includes(form);
    const updated = exists
      ? filters.dosageForm.filter((f) => f !== form)
      : [...filters.dosageForm, form];
    onFilterChange({ ...filters, dosageForm: updated });
  };

  const hasActiveFilters =
    filters.category !== "" ||
    filters.subCategory !== "" ||
    filters.brand.length > 0 ||
    filters.priceRange !== "" ||
    filters.origin.length > 0 ||
    filters.dosageForm.length > 0 ||
    filters.prescriptionType !== "all";

  return (
    <div className="w-full bg-white rounded-2xl border border-slate-200 p-5 shadow-xs space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between pb-4 border-b border-slate-100">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-xl bg-brand-blue-50 border border-brand-blue-100 text-brand-blue-600 flex items-center justify-center shadow-xs">
            <Filter className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-slate-900">Bộ Lọc Tìm Kiếm</h3>
            <p className="text-[11px] text-slate-400">{totalProducts} sản phẩm phù hợp</p>
          </div>
        </div>

        {hasActiveFilters && (
          <button
            onClick={onResetFilters}
            className="flex items-center gap-1 text-xs text-rose-600 hover:text-rose-700 font-semibold transition-colors"
          >
            <RotateCcw className="w-3 h-3" />
            <span>Xóa lọc</span>
          </button>
        )}
      </div>

      {/* 1. Loại thuốc: Kê đơn (Rx) vs Không kê đơn (OTC) */}
      <div className="space-y-2">
        <button
          onClick={() => toggleSection("prescription")}
          className="w-full flex items-center justify-between text-xs font-bold text-slate-800 uppercase tracking-wider"
        >
          <span>Phân Loại Dược Phẩm</span>
          <ChevronDown
            className={`w-4 h-4 text-slate-400 transition-transform ${
              openSections.prescription ? "rotate-180" : ""
            }`}
          />
        </button>

        {openSections.prescription && (
          <div className="grid grid-cols-3 gap-1.5 pt-1">
            <button
              onClick={() => handlePrescriptionSelect("all")}
              className={`py-2 px-2 rounded-xl text-xs font-semibold text-center border transition-all ${
                filters.prescriptionType === "all"
                  ? "bg-brand-blue-600 text-white border-brand-blue-600 shadow-sm"
                  : "bg-slate-50 text-slate-600 border-slate-200/70 hover:bg-slate-100"
              }`}
            >
              Tất cả
            </button>
            <button
              onClick={() => handlePrescriptionSelect("otc")}
              className={`py-2 px-2 rounded-xl text-xs font-semibold text-center border transition-all ${
                filters.prescriptionType === "otc"
                  ? "bg-emerald-600 text-white border-emerald-600 shadow-sm"
                  : "bg-slate-50 text-slate-600 border-slate-200/70 hover:bg-slate-100"
              }`}
            >
              Không kê đơn
            </button>
            <button
              onClick={() => handlePrescriptionSelect("rx")}
              className={`py-2 px-2 rounded-xl text-xs font-semibold text-center border transition-all ${
                filters.prescriptionType === "rx"
                  ? "bg-rose-600 text-white border-rose-600 shadow-sm"
                  : "bg-slate-50 text-slate-600 border-slate-200/70 hover:bg-slate-100"
              }`}
            >
              Thuốc kê đơn
            </button>
          </div>
        )}
      </div>

      {/* 2. Danh mục ngành hàng */}
      <div className="pt-2 border-t border-slate-100 space-y-2">
        <button
          onClick={() => toggleSection("category")}
          className="w-full flex items-center justify-between text-xs font-bold text-slate-800 uppercase tracking-wider"
        >
          <span>Danh Mục Ngành Hàng</span>
          <ChevronDown
            className={`w-4 h-4 text-slate-400 transition-transform ${
              openSections.category ? "rotate-180" : ""
            }`}
          />
        </button>

        {openSections.category && (
          <div className="space-y-1 pt-1">
            {CATEGORIES_DATA.map((cat) => {
              const isSelected = filters.category === cat.slug;
              return (
                <div
                  key={cat.id}
                  onClick={() => handleCategorySelect(cat.slug)}
                  className={`flex items-center justify-between px-3 py-2 rounded-xl text-xs cursor-pointer transition-all ${
                    isSelected
                      ? "bg-brand-blue-50 font-bold text-brand-blue-700 border border-brand-blue-200"
                      : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
                  }`}
                >
                  <span>{cat.name}</span>
                  {isSelected && <Check className="w-3.5 h-3.5 text-brand-blue-600" />}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* 3. Khoảng giá */}
      <div className="pt-2 border-t border-slate-100 space-y-2">
        <button
          onClick={() => toggleSection("price")}
          className="w-full flex items-center justify-between text-xs font-bold text-slate-800 uppercase tracking-wider"
        >
          <span>Khoảng Giá (VND)</span>
          <ChevronDown
            className={`w-4 h-4 text-slate-400 transition-transform ${
              openSections.price ? "rotate-180" : ""
            }`}
          />
        </button>

        {openSections.price && (
          <div className="space-y-1.5 pt-1">
            {[
              { id: "under-100", label: "Dưới 100.000đ" },
              { id: "100-300", label: "100.000đ - 300.000đ" },
              { id: "300-500", label: "300.000đ - 500.000đ" },
              { id: "above-500", label: "Trên 500.000đ" },
            ].map((p) => {
              const isSelected = filters.priceRange === p.id;
              return (
                <label
                  key={p.id}
                  onClick={() => handlePriceSelect(p.id)}
                  className="flex items-center gap-2.5 text-xs text-slate-600 hover:text-slate-900 cursor-pointer py-1 select-none"
                >
                  <input
                    type="radio"
                    name="priceRange"
                    checked={isSelected}
                    onChange={() => {}}
                    className="w-4 h-4 text-brand-blue-600 focus:ring-brand-blue-500 rounded border-slate-300"
                  />
                  <span>{p.label}</span>
                </label>
              );
            })}
          </div>
        )}
      </div>

      {/* 4. Thương hiệu hàng đầu */}
      <div className="pt-2 border-t border-slate-100 space-y-2">
        <button
          onClick={() => toggleSection("brand")}
          className="w-full flex items-center justify-between text-xs font-bold text-slate-800 uppercase tracking-wider"
        >
          <span>Thương Hiệu ({filters.brand.length})</span>
          <ChevronDown
            className={`w-4 h-4 text-slate-400 transition-transform ${
              openSections.brand ? "rotate-180" : ""
            }`}
          />
        </button>

        {openSections.brand && (
          <div className="max-h-48 overflow-y-auto space-y-1.5 pt-1 pr-1 custom-scrollbar">
            {BRANDS_LIST.map((brand) => {
              const isChecked = filters.brand.includes(brand);
              return (
                <label
                  key={brand}
                  onClick={() => handleBrandToggle(brand)}
                  className="flex items-center gap-2.5 text-xs text-slate-600 hover:text-slate-900 cursor-pointer py-1 select-none"
                >
                  <input
                    type="checkbox"
                    checked={isChecked}
                    onChange={() => {}}
                    className="w-4 h-4 text-brand-blue-600 focus:ring-brand-blue-500 rounded border-slate-300"
                  />
                  <span className="truncate">{brand}</span>
                </label>
              );
            })}
          </div>
        )}
      </div>

      {/* 5. Dạng bào chế */}
      <div className="pt-2 border-t border-slate-100 space-y-2">
        <button
          onClick={() => toggleSection("dosageForm")}
          className="w-full flex items-center justify-between text-xs font-bold text-slate-800 uppercase tracking-wider"
        >
          <span>Dạng Bào Chế</span>
          <ChevronDown
            className={`w-4 h-4 text-slate-400 transition-transform ${
              openSections.dosageForm ? "rotate-180" : ""
            }`}
          />
        </button>

        {openSections.dosageForm && (
          <div className="max-h-40 overflow-y-auto space-y-1.5 pt-1 pr-1 custom-scrollbar">
            {DOSAGE_FORMS.map((form) => {
              const isChecked = filters.dosageForm.includes(form);
              return (
                <label
                  key={form}
                  onClick={() => handleDosageToggle(form)}
                  className="flex items-center gap-2.5 text-xs text-slate-600 hover:text-slate-900 cursor-pointer py-1 select-none"
                >
                  <input
                    type="checkbox"
                    checked={isChecked}
                    onChange={() => {}}
                    className="w-4 h-4 text-brand-blue-600 focus:ring-brand-blue-500 rounded border-slate-300"
                  />
                  <span className="truncate">{form}</span>
                </label>
              );
            })}
          </div>
        )}
      </div>

      {/* 6. Xuất xứ */}
      <div className="pt-2 border-t border-slate-100 space-y-2">
        <button
          onClick={() => toggleSection("origin")}
          className="w-full flex items-center justify-between text-xs font-bold text-slate-800 uppercase tracking-wider"
        >
          <span>Xuất Xứ</span>
          <ChevronDown
            className={`w-4 h-4 text-slate-400 transition-transform ${
              openSections.origin ? "rotate-180" : ""
            }`}
          />
        </button>

        {openSections.origin && (
          <div className="max-h-40 overflow-y-auto space-y-1.5 pt-1 pr-1 custom-scrollbar">
            {ORIGINS_LIST.map((origin) => {
              const isChecked = filters.origin.includes(origin);
              return (
                <label
                  key={origin}
                  onClick={() => handleOriginToggle(origin)}
                  className="flex items-center gap-2.5 text-xs text-slate-600 hover:text-slate-900 cursor-pointer py-1 select-none"
                >
                  <input
                    type="checkbox"
                    checked={isChecked}
                    onChange={() => {}}
                    className="w-4 h-4 text-brand-blue-600 focus:ring-brand-blue-500 rounded border-slate-300"
                  />
                  <span className="truncate">{origin}</span>
                </label>
              );
            })}
          </div>
        )}
      </div>

      {/* Footer Notice */}
      <div className="p-3 rounded-xl bg-brand-blue-50/80 border border-brand-blue-100 flex items-center gap-2.5 text-[11px] text-brand-blue-950 font-medium shadow-xs">
        <ShieldCheck className="w-4 h-4 text-brand-blue-600 shrink-0" />
        <span>100% Sản phẩm chính hãng có nguồn gốc xuất xứ rõ ràng.</span>
      </div>
    </div>
  );
};
