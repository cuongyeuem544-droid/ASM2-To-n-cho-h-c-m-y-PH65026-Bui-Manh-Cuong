"use client";

import React, { useState } from "react";
import Link from "next/link";
import { H4CareLogo } from "../branding/H4CareLogo";
import { FptPolyBadge } from "../branding/FptPolyBadge";
import { CATEGORIES_DATA } from "@/data/mockData";
import {
  X,
  PhoneCall,
  ChevronDown,
  User,
  Heart,
  FileText,
  HelpCircle,
  Stethoscope,
  ArrowRight,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { PHARMACY_CONTACT } from "@/lib/constants";

interface MobileDrawerProps {
  isOpen: boolean;
  onClose: () => void;
}

export const MobileDrawer: React.FC<MobileDrawerProps> = ({ isOpen, onClose }) => {
  const [expandedCat, setExpandedCat] = useState<string | null>(null);

  const toggleCat = (id: string) => {
    setExpandedCat(expandedCat === id ? null : id);
  };

  if (!isOpen) return null;

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-50 lg:hidden">
        {/* Backdrop */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={onClose}
          transition={{ duration: 0.2 }}
          className="absolute inset-0 bg-slate-900/50 backdrop-blur-sm"
        />

        {/* Drawer panel */}
        <motion.div
          initial={{ x: "-100%" }}
          animate={{ x: 0 }}
          exit={{ x: "-100%" }}
          transition={{ duration: 0.28, ease: [0.16, 1, 0.3, 1] }}
          className="absolute top-0 bottom-0 left-0 w-[85%] max-w-sm bg-white shadow-depth-4 flex flex-col justify-between overflow-y-auto"
        >
          {/* Header */}
          <div className="p-4 border-b border-slate-100 flex items-center justify-between sticky top-0 bg-white/95 backdrop-blur-md z-10">
            <H4CareLogo size="sm" withTagline={true} />
            <button
              onClick={onClose}
              className="p-2 rounded-xl text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors"
              aria-label="Đóng menu"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Body */}
          <div className="p-4 space-y-5 flex-1">
            {/* Pharmacist Quick Call Bar */}
            <div className="p-3.5 rounded-2xl bg-brand-blue-50/80 border border-brand-blue-200/80 shadow-xs">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-brand-blue-600 text-white flex items-center justify-center shadow-xs">
                  <Stethoscope className="w-5 h-5" />
                </div>
                <div>
                  <p className="text-xs font-bold text-brand-blue-950">Tư vấn Dược sĩ chuyên môn</p>
                  <a
                    href={`tel:${PHARMACY_CONTACT.consultationPhone}`}
                    className="text-sm font-extrabold text-brand-blue-600 flex items-center gap-1 hover:underline"
                  >
                    <PhoneCall className="w-3.5 h-3.5" />
                    <span>{PHARMACY_CONTACT.consultationPhoneDisplay}</span>
                  </a>
                </div>
              </div>
            </div>

            {/* Category Accordion */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <p className="text-xs font-bold text-slate-500 uppercase tracking-wider">
                  Danh mục y tế & dược phẩm
                </p>
                <Link
                  href="/products"
                  onClick={onClose}
                  className="text-[11px] font-bold text-brand-blue-600 hover:underline"
                >
                  Tất cả
                </Link>
              </div>

              <div className="divide-y divide-slate-100 border border-slate-200 rounded-2xl overflow-hidden shadow-xs">
                {CATEGORIES_DATA.map((cat) => {
                  const isExpanded = expandedCat === cat.id;
                  return (
                    <div key={cat.id}>
                      <button
                        onClick={() => toggleCat(cat.id)}
                        className="w-full flex items-center justify-between p-3.5 text-left text-xs sm:text-sm font-semibold text-slate-800 hover:bg-slate-50 transition-colors"
                      >
                        <div className="flex items-center gap-2">
                          <span>{cat.name}</span>
                          {cat.badge && (
                            <span className="text-[9px] bg-brand-blue-50 text-brand-blue-600 px-1.5 py-0.2 rounded font-bold border border-brand-blue-100">
                              {cat.badge}
                            </span>
                          )}
                        </div>
                        <ChevronDown
                          className={`w-4 h-4 text-slate-400 transition-transform duration-200 ${
                            isExpanded ? "rotate-180 text-brand-blue-600" : ""
                          }`}
                        />
                      </button>

                      {isExpanded && (
                        <div className="bg-slate-50/80 px-4 py-2 space-y-1">
                          <Link
                            href={`/category/${cat.slug}`}
                            onClick={onClose}
                            className="flex items-center justify-between py-1.5 text-xs font-bold text-brand-blue-700 pl-3 border-l-2 border-brand-blue-600"
                          >
                            <span>Xem toàn bộ {cat.name}</span>
                            <ArrowRight className="w-3 h-3" />
                          </Link>
                          {cat.subCategories.map((sub) => (
                            <Link
                              key={sub.id}
                              href={`/category/${cat.slug}`}
                              onClick={onClose}
                              className="block py-1.5 text-xs text-slate-600 hover:text-brand-blue-600 pl-3 border-l-2 border-slate-200 hover:border-brand-blue-600 transition-colors"
                            >
                              {sub.name}
                            </Link>
                          ))}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Quick links */}
            <div className="space-y-1">
              <p className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">
                Tiện ích thành viên
              </p>
              <Link
                href="/products"
                onClick={onClose}
                className="flex items-center gap-3 p-2.5 text-xs sm:text-sm font-medium text-slate-700 hover:bg-slate-50 rounded-xl transition-colors"
              >
                <FileText className="w-4 h-4 text-slate-400" />
                <span>Khám phá toàn bộ thuốc</span>
              </Link>
              <Link
                href="/category/thuoc-ke-don"
                onClick={onClose}
                className="flex items-center gap-3 p-2.5 text-xs sm:text-sm font-medium text-slate-700 hover:bg-slate-50 rounded-xl transition-colors"
              >
                <Stethoscope className="w-4 h-4 text-slate-400" />
                <span>Gửi đơn thuốc theo toa Bác sĩ</span>
              </Link>
              <Link
                href="/login"
                onClick={onClose}
                className="flex items-center gap-3 p-2.5 text-xs sm:text-sm font-medium text-slate-700 hover:bg-slate-50 rounded-xl transition-colors"
              >
                <User className="w-4 h-4 text-slate-400" />
                <span>Đăng nhập / Tài khoản</span>
              </Link>
              <Link
                href="/about-project"
                onClick={onClose}
                className="flex items-center gap-3 p-2.5 text-xs sm:text-sm font-medium text-slate-700 hover:bg-slate-50 rounded-xl transition-colors"
              >
                <HelpCircle className="w-4 h-4 text-slate-400" />
                <span>Trung tâm hỗ trợ y khoa</span>
              </Link>
            </div>
          </div>

          {/* Footer of Drawer */}
          <div className="p-4 border-t border-slate-100 bg-slate-50/70">
            <FptPolyBadge variant="light" className="w-full justify-center mb-2" />
            <p className="text-[10px] text-center text-slate-400">
              H4CARE Healthcare • Student Project 2026
            </p>
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
};
