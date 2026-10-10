"use client";

import React from "react";
import Link from "next/link";
import { H4CareLogo } from "../branding/H4CareLogo";
import { FptPolyBadge } from "../branding/FptPolyBadge";
import { PhoneCall, ShieldCheck, Heart, MapPin, Mail, ExternalLink } from "lucide-react";
import { PHARMACY_CONTACT } from "@/lib/constants";

export const Footer: React.FC = () => {
  return (
    <footer className="mt-auto bg-[#0b1329] border-t border-slate-800 text-slate-300 text-xs select-none">
      {/* Upper Main Footer Grid */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-8 lg:gap-8">
          {/* Col 1 & 2: Brand Identity, Vision & Trust */}
          <div className="lg:col-span-2 space-y-4">
            <H4CareLogo variant="white" size="md" withTagline={true} />
            <p className="text-slate-300/90 text-xs leading-relaxed max-w-sm mt-3">
              Nền tảng tra cứu và tiếp cận dược phẩm số hóa hiện đại. Hỗ trợ tư vấn chuyên môn Dược khoa, cung cấp thông tin minh bạch theo định hướng tiêu chuẩn Thực hành Tốt (GPP & GSP).
            </p>

            {/* Academic Credential & Medical Standards Badge */}
            <div className="pt-1 flex flex-wrap items-center gap-2">
              <FptPolyBadge variant="dark" />
              <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-slate-900/80 border border-slate-800 text-[10px] text-slate-300 font-medium">
                <ShieldCheck className="w-3 h-3 text-brand-emerald-400" />
                <span>Định hướng chuẩn GPP / GSP</span>
              </div>
            </div>

            {/* Hotline consultation card */}
            <div className="pt-2">
              <a
                href={`tel:${PHARMACY_CONTACT.consultationPhone}`}
                className="inline-flex items-center gap-3 px-4 py-2.5 rounded-xl bg-slate-900/90 border border-slate-800 hover:border-cyan-400/50 hover:bg-slate-900 text-slate-200 transition-all duration-150 group shadow-xs"
              >
                <div className="w-8 h-8 rounded-lg bg-cyan-500/10 border border-cyan-500/20 text-cyan-400 flex items-center justify-center group-hover:scale-105 transition-transform">
                  <PhoneCall className="w-4 h-4" />
                </div>
                <div>
                  <span className="text-[10.5px] text-slate-400 block font-medium">{PHARMACY_CONTACT.fullLabel}</span>
                  <span className="text-xs font-bold text-cyan-300 tracking-wide group-hover:text-white transition-colors">{PHARMACY_CONTACT.consultationPhoneDisplay}</span>
                </div>
              </a>
            </div>
          </div>

          {/* Col 3: Danh Mục Dược Phẩm */}
          <div className="space-y-3.5">
            <h4 className="text-white font-bold text-xs uppercase tracking-wider flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-brand-blue-500" />
              Danh Mục Sản Phẩm
            </h4>
            <ul className="space-y-2 text-slate-300 text-xs">
              <li>
                <Link href="/category/thuoc-khong-ke-don" className="hover:text-cyan-300 transition-colors inline-block hover:translate-x-0.5 transform duration-150">
                  Thuốc Không Kê Đơn (OTC)
                </Link>
              </li>
              <li>
                <Link href="/category/thuoc-ke-don" className="hover:text-cyan-300 transition-colors inline-block hover:translate-x-0.5 transform duration-150">
                  Thuốc Kê Đơn (Rx)
                </Link>
              </li>
              <li>
                <Link href="/category/thuc-pham-chuc-nang" className="hover:text-cyan-300 transition-colors inline-block hover:translate-x-0.5 transform duration-150">
                  Vitamin & Thực Phẩm Chức Năng
                </Link>
              </li>
              <li>
                <Link href="/category/thiet-bi-y-te" className="hover:text-cyan-300 transition-colors inline-block hover:translate-x-0.5 transform duration-150">
                  Thiết Bị Y Tế & Chăm Sóc
                </Link>
              </li>
              <li className="pt-1">
                <Link href="/products" className="text-cyan-400 hover:text-cyan-300 font-semibold transition-colors inline-flex items-center gap-1">
                  <span>Tất cả sản phẩm</span>
                  <span>→</span>
                </Link>
              </li>
            </ul>
          </div>

          {/* Col 4: Dịch Vụ Khách Hàng & Tiêu Chuẩn */}
          <div className="space-y-3.5">
            <h4 className="text-white font-bold text-xs uppercase tracking-wider flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-cyan-400" />
              Dịch Vụ Khách Hàng
            </h4>
            <ul className="space-y-2 text-slate-300 text-xs">
              <li>
                <Link href="/category/thuoc-ke-don" className="hover:text-cyan-300 transition-colors inline-block hover:translate-x-0.5 transform duration-150">
                  Gửi đơn thuốc Bác sĩ
                </Link>
              </li>
              <li>
                <span className="text-slate-400 hover:text-slate-300 transition-colors cursor-default">
                  Tra cứu đơn thuốc điện tử
                </span>
              </li>
              <li>
                <span className="text-slate-400 hover:text-slate-300 transition-colors cursor-default">
                  Chính sách giao nhận chuẩn GSP
                </span>
              </li>
              <li>
                <Link href="/chinh-sach-doi-tra" className="hover:text-cyan-300 transition-colors inline-block hover:translate-x-0.5 transform duration-150">
                  Chính sách đổi trả & hoàn tiền
                </Link>
              </li>
              <li>
                <span className="text-slate-400 hover:text-slate-300 transition-colors cursor-default">
                  Bảo mật thông tin bệnh án
                </span>
              </li>
            </ul>
          </div>

          {/* Col 5: Về Dự Án & Học Thuật */}
          <div className="space-y-3.5">
            <h4 className="text-white font-bold text-xs uppercase tracking-wider flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
              Thông Tin Đồ Án
            </h4>
            <ul className="space-y-2.5 text-slate-300 text-xs">
              <li>
                <span className="text-white font-semibold block">
                  FPT Polytechnic
                </span>
                <span className="text-slate-400 text-[11px] block mt-0.5">
                  Khoa Công Nghệ Thông Tin
                </span>
              </li>
              <li className="pt-1 border-t border-slate-800/80">
                <span className="text-slate-400 block text-[11px] mb-1">
                  Nhóm sinh viên thực hiện:
                </span>
                <span className="text-cyan-300 font-medium text-[11.5px] bg-slate-900/90 px-2 py-1 rounded-md border border-slate-800 inline-block">
                  Hùng • Đức Anh • Hoàn • Cường
                </span>
              </li>
              <li className="pt-1.5">
                <Link
                  href="/about-project"
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 text-cyan-400 hover:text-white text-[11px] font-semibold border border-slate-800 hover:border-slate-700 transition-colors shadow-xs"
                >
                  <span>Hồ sơ & Báo cáo kỹ thuật</span>
                  <ExternalLink className="w-3 h-3 text-cyan-400" />
                </Link>
              </li>
            </ul>
          </div>
        </div>
      </div>

      {/* Bottom Legal & Ethical Standards Ribbon */}
      <div className="border-t border-slate-800/90 bg-[#060a16] py-4">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-3 text-[11px] text-slate-400">
          <div className="flex items-center gap-2 text-center sm:text-left">
            <ShieldCheck className="w-4 h-4 text-brand-emerald-400 shrink-0" />
            <span>
              © 2026 H4CARE. Dự án mô phỏng E-Commerce Dược Phẩm Cao Cấp • Tuân thủ chuẩn thông tin y tế.
            </span>
          </div>

          <div className="text-slate-400 text-[11px] font-medium">
            Đồ án tốt nghiệp • FPT Polytechnic
          </div>
        </div>
      </div>
    </footer>
  );
};
