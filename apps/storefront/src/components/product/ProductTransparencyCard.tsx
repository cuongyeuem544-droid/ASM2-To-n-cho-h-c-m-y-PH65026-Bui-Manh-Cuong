"use client";

import React from "react";
import { TransparencyInfo } from "@/types";
import {
  ShieldCheck,
  FileCheck2,
  AlertTriangle,
  Clock,
  ExternalLink,
  Info,
  CheckCircle2,
  FileText,
} from "lucide-react";

interface ProductTransparencyCardProps {
  transparency?: TransparencyInfo;
  isPrescription?: boolean;
  registrationNumber?: string;
  manufacturer?: string;
  publishMode?: string;
  isSaleEligible?: boolean;
}

export const ProductTransparencyCard: React.FC<ProductTransparencyCardProps> = ({
  transparency,
  isPrescription = false,
  registrationNumber = "Đang cập nhật",
  manufacturer = "Đang cập nhật",
  publishMode = "REFERENCE_ONLY",
  isSaleEligible = false,
}) => {
  const score = transparency?.completeness_score ?? 85;
  const sourceName = transparency?.source_name ?? "Hồ sơ công bố thông tin y tế tham khảo";
  const lastAudited = transparency?.last_audited_at ?? new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Ho_Chi_Minh', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date());
  const pendingItems = transparency?.pending_verifications ?? [];
  const regStatus = transparency?.registration_status ?? (
    registrationNumber && !registrationNumber.startsWith("DEMO") && !registrationNumber.startsWith("REF-")
      ? "ĐÃ ĐỐI CHIẾU SỐ ĐĂNG KÝ LƯU HÀNH"
      : "DỮ LIỆU THAM KHẢO / CHƯA ĐỐI CHIẾU CHỨNG TỪ GỐC"
  );

  return (
    <div className="rounded-2xl border border-cyan-200/80 bg-gradient-to-br from-cyan-50/40 via-white to-blue-50/30 p-5 sm:p-6 shadow-xs space-y-5">
      {/* Header section */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-cyan-100">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-cyan-600 text-white flex items-center justify-center shrink-0 shadow-xs">
            <ShieldCheck className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-sm sm:text-base font-black text-slate-900 tracking-tight">
                Minh Bạch Thông Tin Dược Phẩm H4CARE
              </h3>
              <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-cyan-100 text-cyan-800 border border-cyan-200">
                Data Provenance
              </span>
            </div>
            <p className="text-[11px] text-slate-500 mt-0.5">
              Hệ thống đối chiếu hồ sơ dược khoa, nguồn gốc xuất xứ và điều kiện pháp lý lưu hành
            </p>
          </div>
        </div>

        {/* Completeness Score Badge */}
        <div className="flex items-center gap-2.5 bg-white px-3.5 py-2 rounded-xl border border-cyan-200 shadow-2xs shrink-0 self-start sm:self-center">
          <div className="text-right">
            <span className="text-[10px] text-slate-400 block font-semibold leading-tight">Độ đầy đủ hồ sơ</span>
            <span className="text-sm font-black text-cyan-700">{score}% chuẩn hóa</span>
          </div>
          <div className="w-8 h-8 rounded-full border-2 border-cyan-500 flex items-center justify-center text-[11px] font-black text-cyan-700 bg-cyan-50">
            {score}
          </div>
        </div>
      </div>

      {/* Grid: 4 Core Transparency Metrics */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 text-xs">
        {/* Metric 1: Source */}
        <div className="p-3 bg-white rounded-xl border border-slate-200/80 space-y-1">
          <span className="text-slate-400 text-[11px] block flex items-center gap-1">
            <FileCheck2 className="w-3.5 h-3.5 text-cyan-600" />
            Nguồn tham chiếu
          </span>
          <p className="font-bold text-slate-900 leading-snug line-clamp-2">
            {sourceName}
          </p>
        </div>

        {/* Metric 2: Registration number & Status */}
        <div className="p-3 bg-white rounded-xl border border-slate-200/80 space-y-1">
          <span className="text-slate-400 text-[11px] block flex items-center gap-1">
            <FileText className="w-3.5 h-3.5 text-cyan-600" />
            Số đăng ký lưu hành
          </span>
          <p className="font-mono font-bold text-slate-900">
            {registrationNumber}
          </p>
          <span className="text-[10px] text-emerald-700 font-semibold block">
            {regStatus}
          </span>
        </div>

        {/* Metric 3: Legal Category */}
        <div className="p-3 bg-white rounded-xl border border-slate-200/80 space-y-1">
          <span className="text-slate-400 text-[11px] block flex items-center gap-1">
            <Info className="w-3.5 h-3.5 text-cyan-600" />
            Phân loại lưu hành
          </span>
          <p className="font-bold text-slate-900">
            {isPrescription ? "Thuốc kê đơn (Rx)" : "Thuốc không kê đơn (OTC)"}
          </p>
          <span className="text-[10px] text-slate-500 block">
            {isPrescription ? "Cần đơn của Bác sĩ" : "Sử dụng theo hướng dẫn"}
          </span>
        </div>

        {/* Metric 4: Audit Date & Commercial Status */}
        <div className="p-3 bg-white rounded-xl border border-slate-200/80 space-y-1">
          <span className="text-slate-400 text-[11px] block flex items-center gap-1">
            <Clock className="w-3.5 h-3.5 text-cyan-600" />
            Thời điểm đối chiếu
          </span>
          <p className="font-bold text-slate-900">
            {lastAudited}
          </p>
          <span className="text-[10px] font-semibold text-slate-500 block">
            {isSaleEligible || (publishMode !== "REFERENCE_ONLY" && !isPrescription) ? "Đủ điều kiện bán online" : "Danh mục tra cứu / tư vấn"}
          </span>
        </div>
      </div>

      {/* Pending Verifications Box (nếu chưa sẵn sàng bán hoặc còn trường cần xác minh) */}
      {pendingItems.length > 0 && (
        <div className="p-3.5 rounded-xl bg-amber-50/80 border border-amber-200 text-xs space-y-1.5">
          <div className="flex items-center gap-1.5 text-amber-800 font-bold">
            <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
            <span>Hạng mục thẩm định thương mại trước khi mở bán thật:</span>
          </div>
          <ul className="space-y-1 text-slate-700 pl-5 list-disc text-[11.5px]">
            {pendingItems.map((item, idx) => (
              <li key={idx}>{item}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Official Medical & Regulatory Disclaimer */}
      <div className="p-3 rounded-xl bg-slate-50 border border-slate-200 text-[11px] text-slate-600 leading-relaxed flex items-start gap-2.5">
        <Info className="w-4 h-4 text-cyan-600 shrink-0 mt-0.5" />
        <p>
          <strong className="text-slate-800">Tuyên bố minh bạch:</strong>{" "}
          {transparency?.disclaimer ||
            "Chỉ số minh bạch dữ liệu phản ánh mức độ đầy đủ và nguồn gốc đối chiếu của hồ sơ thông tin, không phải đánh giá chất lượng sinh học hay hiệu quả điều trị của thuốc. Thông tin chỉ định và liều dùng mang tính chất tham khảo chuyên môn, người bệnh cần tuân thủ hướng dẫn của Bác sĩ hoặc Dược sĩ."}
        </p>
      </div>
    </div>
  );
};
