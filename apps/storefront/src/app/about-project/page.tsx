"use client";

import React from "react";
import Link from "next/link";
import { Header } from "@/components/layout/Header";
import { Footer } from "@/components/layout/Footer";
import { FptPolyBadge } from "@/components/branding/FptPolyBadge";
import { AbstractSymbol } from "@/components/branding/AbstractSymbol";
import {
  ShieldCheck,
  CheckCircle2,
  Code2,
  Database,
  Layout,
  Stethoscope,
  Users,
  Award,
  ArrowLeft,
} from "lucide-react";

export default function AboutProjectPage() {
  return (
    <div className="min-h-screen flex flex-col bg-slate-50">
      <Header />

      <main className="flex-1 max-w-5xl mx-auto w-full px-4 sm:px-6 lg:px-8 py-10 sm:py-14">
        {/* Back navigation */}
        <Link
          href="/"
          className="inline-flex items-center gap-2 text-xs font-bold text-slate-500 hover:text-brand-blue-600 mb-6 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Quay lại Trang Chủ</span>
        </Link>

        {/* Header Hero Banner */}
        <div className="bg-white rounded-2xl p-6 sm:p-10 border border-slate-200 shadow-xs mb-8">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 pb-6 border-b border-slate-100">
            <div className="flex items-center gap-3.5">
              <div className="w-12 h-12 rounded-xl bg-brand-blue-50 text-brand-blue-600 flex items-center justify-center shrink-0 border border-brand-blue-100">
                <AbstractSymbol size={28} />
              </div>
              <div>
                <h1 className="text-xl sm:text-2xl font-black text-slate-900 tracking-tight">
                  Hồ Sơ Đồ Án H4CARE
                </h1>
                <p className="text-xs text-slate-500 mt-0.5">
                  Nền tảng Thương mại Điện tử Dược phẩm Trực tuyến Chuẩn Y Khoa
                </p>
              </div>
            </div>

            <FptPolyBadge variant="light" />
          </div>

          <div className="pt-6 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="p-4 rounded-xl bg-slate-50 border border-slate-200">
              <div className="flex items-center gap-2 text-brand-blue-600 mb-1">
                <Users className="w-4 h-4" />
                <span className="text-xs font-bold">Nhóm Tác Giả</span>
              </div>
              <p className="text-xs font-semibold text-slate-800">
                Hùng • Đức Anh • Hoàn • Cường
              </p>
              <p className="text-[11px] text-slate-400 mt-0.5">FPT Polytechnic</p>
            </div>

            <div className="p-4 rounded-xl bg-slate-50 border border-slate-200">
              <div className="flex items-center gap-2 text-emerald-600 mb-1">
                <Code2 className="w-4 h-4" />
                <span className="text-xs font-bold">Kiến Trúc Kỹ Thuật</span>
              </div>
              <p className="text-xs font-semibold text-slate-800">
                Next.js 14 App Router
              </p>
              <p className="text-[11px] text-slate-400 mt-0.5">TypeScript • Tailwind CSS</p>
            </div>

            <div className="p-4 rounded-xl bg-slate-50 border border-slate-200">
              <div className="flex items-center gap-2 text-cyan-600 mb-1">
                <Database className="w-4 h-4" />
                <span className="text-xs font-bold">Dữ Liệu Dược Khoa</span>
              </div>
              <p className="text-xs font-semibold text-slate-800">
                25 Sản Phẩm Dược Phẩm
              </p>
              <p className="text-[11px] text-slate-400 mt-0.5">Phân loại OTC & Rx</p>
            </div>

            <div className="p-4 rounded-xl bg-slate-50 border border-slate-200">
              <div className="flex items-center gap-2 text-amber-600 mb-1">
                <Award className="w-4 h-4" />
                <span className="text-xs font-bold">Tiêu Chuẩn Định Hướng</span>
              </div>
              <p className="text-xs font-semibold text-slate-800">
                Chuẩn GPP / GSP
              </p>
              <p className="text-[11px] text-slate-400 mt-0.5">An toàn đơn thuốc</p>
            </div>
          </div>
        </div>

        {/* Detailed Milestones Section */}
        <div className="bg-white rounded-2xl p-6 sm:p-10 border border-slate-200 shadow-xs space-y-6">
          <h2 className="text-lg font-bold text-slate-900 border-b border-slate-100 pb-3">
            Báo Cáo Tiến Độ Các Giai Đoạn Dự Án
          </h2>

          <div className="space-y-4">
            <div className="flex items-start gap-3.5 p-4 rounded-xl bg-emerald-50/50 border border-emerald-200/80">
              <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0 mt-0.5" />
              <div>
                <h3 className="text-sm font-bold text-slate-900">
                  Phase Medical Design System Redesign (10 Khu Vực Trải Nghiệm) - Hoàn Thành Xuất Sắc
                </h3>
                <p className="text-xs text-slate-600 mt-1 leading-relaxed">
                  Thiết lập chuẩn thiết kế y tế tinh giản và đáng tin cậy: Bảng màu Medical Blue `#0052cc` vững chãi, loại bỏ các dải gradient AI phi y tế, chuẩn hóa hệ thống bo góc (`rounded-2xl` cho card và modal, `rounded-xl` cho controls), hoàn thiện 100% trải nghiệm từ Header, MegaMenu, Footer, Trang chủ, Bộ lọc danh mục, Chi tiết thuốc, Giỏ hàng, Toa thuốc điện tử, Đơn hàng tài khoản cho đến Cổng Quản trị Admin.
                </p>
              </div>
            </div>

            <div className="flex items-start gap-3.5 p-4 rounded-xl bg-blue-50/50 border border-blue-200/80">
              <CheckCircle2 className="w-5 h-5 text-brand-blue-600 shrink-0 mt-0.5" />
              <div>
                <h3 className="text-sm font-bold text-slate-900">
                  Phase Core Functionality (CORE-0 đến CORE-4) - Hoàn Thành
                </h3>
                <p className="text-xs text-slate-600 mt-1 leading-relaxed">
                  Thiết lập kiến trúc dữ liệu 25 sản phẩm y khoa chi tiết, trang danh sách sản phẩm `/products` với bộ lọc đa chiều (dạng bào chế, giá, thương hiệu, loại đơn thuốc), dynamic routes `/category/[slug]`, trang chi tiết `/product/[slug]` với bảng dược lý chuyên sâu, modal xem nhanh và quy tắc kiểm duyệt đơn thuốc Rx bắt buộc.
                </p>
              </div>
            </div>

            <div className="flex items-start gap-3.5 p-4 rounded-xl bg-cyan-50/50 border border-cyan-200/80">
              <CheckCircle2 className="w-5 h-5 text-brand-cyan-600 shrink-0 mt-0.5" />
              <div>
                <h3 className="text-sm font-bold text-slate-900">
                  Phase Product Commerce & Healthcare Trust - Hoàn Thành
                </h3>
                <p className="text-xs text-slate-600 mt-1 leading-relaxed">
                  Nâng cấp toàn diện Product Card với cấu trúc phân tầng trực quan (Brand ➔ Tên thuốc ➔ Quy cách ➔ Đánh giá ➔ Giá nổi bật ➔ CTA), chuẩn hóa vùng ảnh ProductImageStage theo dạng bào chế, hệ thống badge tinh gọn tối đa 1-2 badge, bắt buộc CTA "Tư vấn Dược sĩ" đối với thuốc kê đơn Rx, và kiểm định an toàn tất cả claim dữ liệu demo.
                </p>
              </div>
            </div>
          </div>
        </div>
      </main>

      <Footer />
    </div>
  );
}
