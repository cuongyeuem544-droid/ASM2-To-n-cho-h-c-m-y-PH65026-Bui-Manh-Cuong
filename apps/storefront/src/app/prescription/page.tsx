"use client";

import React from "react";
import Link from "next/link";
import { Header } from "@/components/layout/Header";
import { Footer } from "@/components/layout/Footer";
import { PrescriptionUploader } from "@/components/prescription/PrescriptionUploader";
import {
  FileText,
  ShieldCheck,
  PhoneCall,
  CheckCircle2,
  Clock,
  ArrowLeft,
  AlertTriangle,
  FileCheck,
  Stethoscope,
  Lock,
  Mail,
} from "lucide-react";
import { PHARMACY_CONTACT } from "@/lib/constants";

export default function PrescriptionPage() {
  return (
    <div className="min-h-screen flex flex-col bg-slate-50">
      <Header />

      <main className="flex-1 max-w-5xl mx-auto w-full px-4 sm:px-6 lg:px-8 py-8 sm:py-12">
        {/* Navigation Breadcrumb */}
        <Link
          href="/"
          className="inline-flex items-center gap-2 text-xs font-bold text-slate-500 hover:text-brand-blue-600 mb-6 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Quay lại Trang Chủ</span>
        </Link>

        {/* Hero Introduction Section */}
        <div className="bg-white rounded-3xl p-6 sm:p-10 border border-slate-200/90 shadow-depth-1 mb-8">
          <div className="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-6 pb-6 border-b border-slate-100">
            <div className="space-y-2">
              <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-brand-blue-50 text-brand-blue-700 text-xs font-bold border border-brand-blue-100">
                <Stethoscope className="w-3.5 h-3.5" />
                <span>Tiếp Nhận Đơn Thuốc Trực Tuyến Chuẩn GPP</span>
              </div>
              <h1 className="text-2xl sm:text-3xl font-black text-slate-900 tracking-tight">
                Gửi Đơn Thuốc - Dược Sĩ Tư Vấn Miễn Phí
              </h1>
              <p className="text-xs sm:text-sm text-slate-500 max-w-2xl leading-relaxed">
                Tải lên ảnh chụp hoặc tài liệu PDF đơn thuốc của bác sĩ. Đội ngũ
                Dược sĩ chuyên môn H4CARE sẽ kiểm tra, đối chiếu liều lượng và hỗ
                trợ bạn lấy đúng phác đồ điều trị.
              </p>
            </div>

            {/* Quick Contact Pill */}
            <div className="p-4 rounded-2xl bg-brand-blue-50/70 border border-brand-blue-100 shrink-0 flex items-center gap-3.5 w-full lg:w-auto">
              <div className="w-10 h-10 rounded-xl bg-brand-blue-600 text-white flex items-center justify-center shrink-0 shadow-xs">
                <Mail className="w-5 h-5" />
              </div>
              <div>
                <span className="text-[11px] text-slate-500 font-medium block">
                  Kênh tiếp nhận trực tuyến
                </span>
                <span className="text-sm sm:text-base font-bold text-brand-blue-800">
                  {PHARMACY_CONTACT.supportEmail}
                </span>
                <span className="text-[10px] text-slate-400 block">
                  (Tiếp nhận thẩm định chuyên môn nội bộ)
                </span>
              </div>
            </div>
          </div>

          {/* 3 Step Workflow */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-6">
            <div className="p-4 rounded-2xl bg-slate-50 border border-slate-100 flex items-start gap-3">
              <div className="w-7 h-7 rounded-lg bg-brand-blue-100 text-brand-blue-700 flex items-center justify-center font-bold text-xs shrink-0">
                1
              </div>
              <div>
                <h4 className="text-xs font-bold text-slate-900">
                  Tải lên đơn thuốc
                </h4>
                <p className="text-[11px] text-slate-500 mt-0.5 leading-relaxed">
                  Chụp rõ nét đơn thuốc (JPG, PNG) hoặc tải file PDF từ bệnh viện.
                </p>
              </div>
            </div>

            <div className="p-4 rounded-2xl bg-slate-50 border border-slate-100 flex items-start gap-3">
              <div className="w-7 h-7 rounded-lg bg-brand-cyan-100 text-brand-cyan-700 flex items-center justify-center font-bold text-xs shrink-0">
                2
              </div>
              <div>
                <h4 className="text-xs font-bold text-slate-900">
                  Kiểm định & Mã hóa
                </h4>
                <p className="text-[11px] text-slate-500 mt-0.5 leading-relaxed">
                  Hệ thống kiểm tra tính toàn vẹn và bảo mật dữ liệu y tế 256-bit.
                </p>
              </div>
            </div>

            <div className="p-4 rounded-2xl bg-slate-50 border border-slate-100 flex items-start gap-3">
              <div className="w-7 h-7 rounded-lg bg-emerald-100 text-emerald-700 flex items-center justify-center font-bold text-xs shrink-0">
                3
              </div>
              <div>
                <h4 className="text-xs font-bold text-slate-900">
                  Dược sĩ tư vấn
                </h4>
                <p className="text-[11px] text-slate-500 mt-0.5 leading-relaxed">
                  Dược sĩ liên hệ xác nhận danh mục thuốc và hướng dẫn liều dùng.
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Main Upload Box */}
        <div className="mb-10">
          <PrescriptionUploader />
        </div>

        {/* Medical Instructions & Trust Guarantee */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Chụp đơn thuốc đúng cách */}
          <div className="bg-white rounded-3xl p-6 sm:p-7 border border-slate-200/90 shadow-depth-1">
            <div className="flex items-center gap-2.5 mb-4 text-slate-900">
              <FileCheck className="w-5 h-5 text-brand-blue-600" />
              <h3 className="text-sm font-bold">Lưu ý khi chụp đơn thuốc</h3>
            </div>

            <ul className="space-y-3 text-xs text-slate-600">
              <li className="flex items-start gap-2.5">
                <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                <span>
                  Hình ảnh cần đủ ánh sáng, góc chụp thẳng, không bị rung mờ hoặc
                  lóa đèn flash.
                </span>
              </li>
              <li className="flex items-start gap-2.5">
                <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                <span>
                  Hiển thị đầy đủ thông tin: Tiêu đề cơ sở y tế, tên bệnh nhân,
                  chẩn đoán và chữ ký của bác sĩ.
                </span>
              </li>
              <li className="flex items-start gap-2.5">
                <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                <span>
                  Đơn thuốc phải còn hạn sử dụng theo quy định của Bộ Y tế (trong
                  vòng 05 ngày kể từ ngày kê đơn).
                </span>
              </li>
            </ul>
          </div>

          {/* Cam kết bảo mật y tế */}
          <div className="bg-white rounded-3xl p-6 sm:p-7 border border-slate-200/90 shadow-depth-1">
            <div className="flex items-center gap-2.5 mb-4 text-slate-900">
              <Lock className="w-5 h-5 text-brand-emerald-600" />
              <h3 className="text-sm font-bold">Cam kết bảo mật thông tin</h3>
            </div>

            <ul className="space-y-3 text-xs text-slate-600">
              <li className="flex items-start gap-2.5">
                <ShieldCheck className="w-4 h-4 text-brand-emerald-600 shrink-0 mt-0.5" />
                <span>
                  Mọi thông tin đơn thuốc và bệnh án được mã hóa bảo mật theo tiêu
                  chuẩn bảo vệ dữ liệu y tế.
                </span>
              </li>
              <li className="flex items-start gap-2.5">
                <ShieldCheck className="w-4 h-4 text-brand-emerald-600 shrink-0 mt-0.5" />
                <span>
                  Chỉ Dược sĩ có chứng chỉ hành nghề phụ trách mới được quyền truy
                  cập để tư vấn cho bạn.
                </span>
              </li>
              <li className="flex items-start gap-2.5">
                <ShieldCheck className="w-4 h-4 text-brand-emerald-600 shrink-0 mt-0.5" />
                <span>
                  Tuyệt đối không chia sẻ dữ liệu y khoa cá nhân cho bất kỳ bên
                  thứ ba nào khác.
                </span>
              </li>
            </ul>
          </div>
        </div>
      </main>

      <Footer />
    </div>
  );
}
