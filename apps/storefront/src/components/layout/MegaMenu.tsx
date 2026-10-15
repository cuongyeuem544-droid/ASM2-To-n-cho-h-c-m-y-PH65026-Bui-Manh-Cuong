"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { CATEGORIES_DATA } from "@/data/mockData";
import { getStoreCategoriesTree } from "@/lib/api/products";
import { Category } from "@/types";
import {
  Pill,
  FileCheck,
  Sparkles,
  ShieldAlert,
  Activity,
  HeartPulse,
  ChevronRight,
  ArrowRight,
  Stethoscope,
  ShieldCheck,
  CheckCircle2,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

interface MegaMenuProps {
  isOpen: boolean;
  onClose: () => void;
  topClassName?: string;
}

// Icon mapping helper
const CategoryIcon: React.FC<{ iconName: string; className?: string }> = ({
  iconName,
  className = "w-5 h-5",
}) => {
  switch (iconName) {
    case "Pill":
      return <Pill className={className} />;
    case "FileCheck":
      return <FileCheck className={className} />;
    case "Sparkles":
      return <Sparkles className={className} />;
    case "ShieldAlert":
      return <ShieldAlert className={className} />;
    case "Activity":
      return <Activity className={className} />;
    case "HeartPulse":
      return <HeartPulse className={className} />;
    default:
      return <Pill className={className} />;
  }
};

export const MegaMenu: React.FC<MegaMenuProps> = ({ isOpen, onClose, topClassName }) => {
  const router = useRouter();
  const [categories, setCategories] = useState<Category[]>(CATEGORIES_DATA);
  const [activeCategoryId, setActiveCategoryId] = useState<string>(CATEGORIES_DATA[0].id);

  React.useEffect(() => {
    let isMounted = true;
    getStoreCategoriesTree().then((data) => {
      if (isMounted && data && data.length > 0) {
        setCategories(data);
      }
    });
    return () => {
      isMounted = false;
    };
  }, []);

  const activeCategory: Category =
    categories.find((c) => c.id === activeCategoryId || c.slug === activeCategoryId) || categories[0];

  if (!isOpen) return null;

  return (
    <AnimatePresence>
      <div className={`fixed inset-0 z-40 ${topClassName || "top-[104px]"}`} onClick={onClose}>
        {/* Backdrop */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.2 }}
          className="absolute inset-0 bg-slate-900/30 backdrop-blur-sm"
        />

        {/* Mega Menu Window */}
        <div
          className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-2"
          onClick={(e) => e.stopPropagation()}
        >
          <motion.div
            initial={{ opacity: 0, y: -8, scale: 0.99 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -8, scale: 0.99 }}
            transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
            className="bg-white rounded-3xl border border-slate-200 shadow-2xl overflow-hidden"
          >
            <div className="grid grid-cols-12 min-h-[440px]">
              {/* CỘT 1: Danh sách Danh mục chính (Width: 4/12) */}
              <div className="col-span-12 md:col-span-4 bg-slate-50/90 border-r border-slate-200/80 p-3.5 space-y-1">
                <div className="px-3 py-2 text-[11px] font-bold tracking-wider uppercase text-slate-500">
                  Danh mục dược phẩm chuẩn GPP
                </div>
                {categories.map((cat) => {
                  const isActive = cat.id === activeCategoryId || cat.slug === activeCategoryId;
                  return (
                    <div
                      key={cat.id}
                      onMouseEnter={() => setActiveCategoryId(cat.id)}
                      onClick={() => setActiveCategoryId(cat.id)}
                      className={`group flex items-center justify-between p-3 rounded-2xl cursor-pointer transition-all duration-150 ${
                        isActive
                          ? "bg-white text-brand-blue-700 shadow-depth-1 border border-brand-blue-200 font-bold"
                          : "text-slate-700 hover:bg-white hover:text-brand-blue-600"
                      }`}
                    >
                      <div className="flex items-center gap-3">
                        <div
                          className={`w-9 h-9 rounded-xl flex items-center justify-center transition-colors ${
                            isActive
                              ? "bg-brand-blue-600 text-white shadow-xs"
                              : "bg-slate-200/80 text-slate-600 group-hover:bg-brand-blue-50 group-hover:text-brand-blue-600"
                          }`}
                        >
                          <CategoryIcon iconName={cat.iconName} className="w-4 h-4" />
                        </div>
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="text-xs sm:text-sm">{cat.name}</span>
                            {cat.badge && (
                              <span className="px-1.5 py-0.2 text-[9px] font-bold rounded-full bg-cyan-100 text-cyan-800 border border-cyan-200">
                                {cat.badge}
                              </span>
                            )}
                          </div>
                          <p className="text-[11px] text-slate-400 font-normal line-clamp-1 max-w-[210px]">
                            {cat.description}
                          </p>
                        </div>
                      </div>
                      <ChevronRight
                        className={`w-4 h-4 transition-transform ${
                          isActive ? "text-brand-blue-600 translate-x-1" : "text-slate-300"
                        }`}
                      />
                    </div>
                  );
                })}
              </div>

              {/* CỘT 2: Chi tiết Nhóm sản phẩm con & Phổ biến (Width: 5/12) */}
              <div className="col-span-12 md:col-span-5 p-6 flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between pb-3 mb-4 border-b border-slate-100">
                    <div>
                      <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
                        <span>{activeCategory.name}</span>
                      </h3>
                      <p className="text-xs text-slate-500 mt-0.5">
                        {activeCategory.description}
                      </p>
                    </div>
                    <Link
                      href={`/category/${activeCategory.slug}`}
                      onClick={onClose}
                      className="text-xs font-semibold text-brand-blue-600 hover:text-brand-blue-700 inline-flex items-center gap-1 group"
                    >
                      <span>Xem toàn bộ</span>
                      <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-1 transition-transform" />
                    </Link>
                  </div>

                  {/* Danh sách nhóm con */}
                  <div className="grid grid-cols-2 gap-2.5">
                    {activeCategory.subCategories.map((sub) => (
                      <Link
                        key={sub.id}
                        href={`/category/${activeCategory.slug}`}
                        onClick={onClose}
                        className="group flex items-center justify-between p-3 rounded-xl border border-slate-200/80 hover:border-brand-blue-300 hover:bg-brand-blue-50/40 transition-all duration-150"
                      >
                        <div className="flex items-center gap-2">
                          <span className="w-1.5 h-1.5 rounded-full bg-brand-cyan-500 group-hover:scale-125 transition-transform" />
                          <span className="text-xs font-medium text-slate-800 group-hover:text-brand-blue-600">
                            {sub.name}
                          </span>
                        </div>
                        {sub.isPopular && (
                          <span className="text-[9px] font-bold text-emerald-700 bg-emerald-50 px-1.5 py-0.5 rounded border border-emerald-200">
                            Hot
                          </span>
                        )}
                      </Link>
                    ))}
                  </div>
                </div>

                {/* Hộp cam kết y tế chuẩn GPP */}
                <div className="mt-6 p-3.5 rounded-2xl bg-brand-blue-50/70 border border-brand-blue-100 flex items-center gap-3">
                  <div className="w-8 h-8 rounded-xl bg-brand-blue-600 text-white flex items-center justify-center shrink-0 shadow-xs">
                    <ShieldCheck className="w-4 h-4" />
                  </div>
                  <div className="text-xs">
                    <p className="font-bold text-brand-blue-900">Chuẩn Thực hành tốt Nhà thuốc (GPP)</p>
                    <p className="text-slate-500 text-[11px]">100% Thuốc nguồn gốc rõ ràng, bảo quản nhiệt độ chuẩn &lt; 25°C.</p>
                  </div>
                </div>
              </div>

              {/* CỘT 3: Banner Chuyên Môn & Tư Vấn Dược Sĩ (Width: 3/12) */}
              <div className="col-span-12 md:col-span-3 bg-slate-50/80 p-6 border-l border-slate-200/80 flex flex-col justify-between">
                <div>
                  <div className="relative rounded-2xl overflow-hidden border border-slate-200 shadow-sm aspect-video mb-4 group">
                    <img
                      src={activeCategory.featuredImage || "https://images.unsplash.com/photo-1576091160550-2173dba999ef?w=600&auto=format&fit=crop&q=80"}
                      alt={activeCategory.name}
                      className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
                    />
                    <div className="absolute inset-0 bg-gradient-to-t from-slate-900/80 via-slate-900/20 to-transparent flex items-end p-3">
                      <span className="text-white text-xs font-semibold">
                        {activeCategory.featuredTitle || "Tư vấn sức khỏe cùng chuyên gia"}
                      </span>
                    </div>
                  </div>

                  <div className="space-y-2 text-xs text-slate-600 mb-4">
                    <div className="flex items-center gap-2">
                      <CheckCircle2 className="w-3.5 h-3.5 text-brand-emerald-500 shrink-0" />
                      <span>Kiểm duyệt bởi Hội đồng Dược sĩ</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <CheckCircle2 className="w-3.5 h-3.5 text-brand-emerald-500 shrink-0" />
                      <span>Hỗ trợ đọc đơn thuốc viết tay</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <CheckCircle2 className="w-3.5 h-3.5 text-brand-emerald-500 shrink-0" />
                      <span>Giao hàng kín đáo & an toàn</span>
                    </div>
                  </div>
                </div>

                {/* Live Pharmacist Consultation Card */}
                <div className="p-3.5 rounded-2xl bg-white border border-slate-200 shadow-xs">
                  <div className="flex items-center gap-2.5 mb-2.5">
                    <div className="relative">
                      <div className="w-8 h-8 rounded-full bg-brand-cyan-50 text-brand-cyan-700 flex items-center justify-center font-bold text-xs border border-brand-cyan-100">
                        <Stethoscope className="w-4 h-4 text-brand-blue-600" />
                      </div>
                      <span className="absolute bottom-0 right-0 w-2.5 h-2.5 rounded-full bg-emerald-500 border-2 border-white" />
                    </div>
                    <div>
                      <p className="text-xs font-bold text-slate-800">Dược Sĩ Trực Tuyến</p>
                      <p className="text-[10px] text-emerald-600 font-semibold">Sẵn sàng phản hồi</p>
                    </div>
                  </div>
                  <button
                    onClick={() => {
                      onClose();
                      router.push("/category/thuoc-ke-don");
                    }}
                    className="w-full py-2.5 px-3 rounded-xl bg-brand-blue-600 hover:bg-brand-blue-700 active:scale-95 text-white font-bold text-xs shadow-xs transition-all duration-150"
                  >
                    Gửi đơn thuốc hoặc Hỏi ngay
                  </button>
                </div>
              </div>
            </div>
          </motion.div>
        </div>
      </div>
    </AnimatePresence>
  );
};
