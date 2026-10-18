"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import Image from "next/image";
import {
  ThermometerSnowflake,
  ShieldCheck,
  AlertTriangle,
  Pill,
  ArrowRight,
  Sparkles,
  HeartPulse,
  Info,
} from "lucide-react";
import { Button } from "@/components/ui/Button";
import { formatVND } from "@/lib/utils";

interface RecommendedProduct {
  id: number;
  dbId: number;
  name: string;
  registration_number?: string | null;
  price: number;
  image_url?: string | null;
  dosage_form?: string | null;
  indications?: string | null;
  is_rx: boolean;
}

interface Campaign {
  id: number;
  slug: string;
  title: string;
  disease_name: string;
  season: string;
  symptoms: string;
  prevention: string;
  status: string;
  banner_image_url?: string | null;
  recommended_products: RecommendedProduct[];
  created_at: string;
}

const SEASON_LABELS: Record<string, { label: string; bg: string; text: string }> = {
  MUA_MUA: { label: "Mùa Mưa & Ẩm Thấp", bg: "bg-cyan-50 border-cyan-200", text: "text-cyan-800" },
  DONG: { label: "Mùa Đông - Xuân Lạnh", bg: "bg-blue-50 border-blue-200", text: "text-blue-800" },
  HA: { label: "Mùa Hè Nắng Nóng", bg: "bg-amber-50 border-amber-200", text: "text-amber-800" },
  THU: { label: "Mùa Thu Giao Mùa", bg: "bg-orange-50 border-orange-200", text: "text-orange-800" },
  XUAN: { label: "Mùa Xuân", bg: "bg-emerald-50 border-emerald-200", text: "text-emerald-800" },
  QUANH_NAM: { label: "Chăm Sóc Quanh Năm", bg: "bg-purple-50 border-purple-200", text: "text-purple-800" },
};

export function SeasonalCampaignsSection() {
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/v1/store/campaigns")
      .then((res) => {
        if (!res.ok) throw new Error("API error");
        return res.json();
      })
      .then((data) => {
        if (Array.isArray(data) && data.length > 0) {
          setCampaigns(data);
        }
      })
      .catch((err) => {
        console.warn("Could not fetch seasonal campaigns:", err);
      })
      .finally(() => setLoading(false));
  }, []);

  if (loading && campaigns.length === 0) {
    return null;
  }

  if (campaigns.length === 0) {
    return null;
  }

  const activeCamp = campaigns[selectedIndex] || campaigns[0];
  const seasonInfo = SEASON_LABELS[activeCamp.season] || {
    label: activeCamp.season,
    bg: "bg-slate-50 border-slate-200",
    text: "text-slate-800",
  };

  return (
    <section className="font-sans py-12 sm:py-16 bg-linear-to-b from-sky-50/60 to-white border-t border-slate-200/80">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 mb-8">
          <div>
            <div className="flex items-center gap-1.5 text-xs font-bold text-teal-700 uppercase tracking-wider mb-1.5">
              <HeartPulse className="w-4 h-4 text-teal-600 animate-pulse" />
              <span>Cẩm Nang Y Tế & Phác Đồ GPP</span>
            </div>
            <h2 className="text-2xl sm:text-3xl font-black text-slate-900 tracking-tight">
              Chuyên Đề Dịch Bệnh Theo Mùa
            </h2>
            <p className="text-xs sm:text-sm text-slate-500 mt-1 max-w-2xl">
              Hướng dẫn phòng ngừa và danh mục thuốc điều trị được chỉ định bởi Dược sĩ chuyên môn theo đặc điểm dịch tễ từng mùa.
            </p>
          </div>

          {/* Topic Switcher Tabs */}
          <div className="flex items-center gap-2 overflow-x-auto pb-2 sm:pb-0 scrollbar-none">
            {campaigns.map((c, idx) => (
              <button
                key={c.id}
                onClick={() => setSelectedIndex(idx)}
                className={`px-3.5 py-2 rounded-xl text-xs font-bold shrink-0 transition-all ${
                  selectedIndex === idx
                    ? "bg-brand-blue-700 text-white shadow-sm scale-102"
                    : "bg-white text-slate-600 hover:text-slate-900 hover:bg-slate-100 border border-slate-200"
                }`}
              >
                {c.disease_name}
              </button>
            ))}
          </div>
        </div>

        {/* Featured Campaign Container */}
        <div className="bg-white rounded-3xl border border-slate-200/80 shadow-xs overflow-hidden">
          <div className="grid grid-cols-1 lg:grid-cols-12">
            {/* Left 7 cols: Medical Guidance & Symptoms */}
            <div className="lg:col-span-7 p-6 sm:p-8 flex flex-col justify-between space-y-6">
              <div>
                <div className="flex flex-wrap items-center gap-2 mb-3">
                  <span
                    className={`inline-flex items-center gap-1.5 text-xs font-bold px-3 py-1 rounded-full border ${seasonInfo.bg} ${seasonInfo.text}`}
                  >
                    <ThermometerSnowflake className="w-3.5 h-3.5" />
                    <span>{seasonInfo.label}</span>
                  </span>
                  <span className="text-xs text-slate-400">• Cập nhật chuẩn GPP</span>
                </div>

                <h3 className="text-xl sm:text-2xl font-black text-slate-900 leading-snug break-words">
                  {activeCamp.title}
                </h3>

                {/* Symptoms block */}
                <div className="mt-5 p-4 rounded-2xl bg-amber-50/70 border border-amber-200/80">
                  <div className="flex items-center gap-2 text-xs font-bold text-amber-900 mb-1.5">
                    <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
                    <span>Dấu hiệu & Triệu chứng nhận biết sớm:</span>
                  </div>
                  <p className="text-xs sm:text-sm text-amber-950 leading-relaxed break-words">
                    {activeCamp.symptoms}
                  </p>
                </div>

                {/* Prevention block */}
                <div className="mt-4 p-4 rounded-2xl bg-emerald-50/70 border border-emerald-200/80">
                  <div className="flex items-center gap-2 text-xs font-bold text-emerald-900 mb-1.5">
                    <ShieldCheck className="w-4 h-4 text-emerald-600 shrink-0" />
                    <span>Lời khuyên phòng bệnh từ Dược sĩ:</span>
                  </div>
                  <p className="text-xs sm:text-sm text-emerald-950 leading-relaxed break-words">
                    {activeCamp.prevention}
                  </p>
                </div>
              </div>

              {/* Disclaimer */}
              <div className="flex items-start gap-2 text-[11px] text-slate-400 bg-slate-50 p-3 rounded-xl border border-slate-100">
                <Info className="w-4 h-4 text-slate-400 shrink-0 mt-0.5" />
                <span>
                  Lưu ý: Các biện pháp và thuốc chỉ mang tính chất hướng dẫn tham khảo. Khi người bệnh có triệu chứng sốt cao không hạ hoặc co giật, cần lập tức đến cơ sở y tế gần nhất.
                </span>
              </div>
            </div>

            {/* Right 5 cols: Recommended Products Grid */}
            <div className="lg:col-span-5 bg-slate-50/70 p-6 sm:p-8 border-t lg:border-t-0 lg:border-l border-slate-200/80 flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between mb-4">
                  <h4 className="text-xs sm:text-sm font-bold text-slate-900 uppercase tracking-wider flex items-center gap-1.5">
                    <Pill className="w-4 h-4 text-brand-blue-600" />
                    <span>Thuốc & Sản Phẩm Chỉ Định</span>
                  </h4>
                  <span className="text-[11px] font-semibold text-slate-500">
                    {activeCamp.recommended_products.length} sản phẩm
                  </span>
                </div>

                {activeCamp.recommended_products.length > 0 ? (
                  <div className="space-y-3">
                    {activeCamp.recommended_products.map((p) => (
                      <div
                        key={p.id}
                        className="p-3.5 rounded-2xl bg-white border border-slate-200 hover:border-brand-blue-300 shadow-xs transition-all flex items-center justify-between gap-3 group"
                      >
                        <div className="flex items-center gap-3 min-w-0">
                          <div className="w-12 h-12 rounded-xl bg-slate-100 overflow-hidden shrink-0 relative flex items-center justify-center">
                            {p.image_url ? (
                              <img
                                src={p.image_url}
                                alt={p.name}
                                className="w-full h-full object-contain p-1"
                              />
                            ) : (
                              <Pill className="w-6 h-6 text-slate-300" />
                            )}
                          </div>
                          <div className="min-w-0">
                            <h5 className="text-xs font-bold text-slate-900 truncate group-hover:text-brand-blue-700 transition-colors">
                              {p.name}
                            </h5>
                            <div className="flex items-center gap-2 mt-0.5 text-[11px] text-slate-500">
                              <span>{p.dosage_form || "Viên nén"}</span>
                              {p.registration_number && (
                                <span className="font-mono text-[10px] text-slate-400">
                                  • {p.registration_number}
                                </span>
                              )}
                            </div>
                            <div className="text-xs font-black text-rose-600 mt-1">
                              {formatVND(p.price)}
                            </div>
                          </div>
                        </div>

                        <Link
                          href={`/product/${p.dbId || p.id}`}
                          className="shrink-0"
                        >
                          <Button
                            variant="outline"
                            size="sm"
                            className="text-xs px-2.5 py-1.5 border-slate-200 hover:border-brand-blue-400 hover:bg-brand-blue-50 text-brand-blue-700"
                          >
                            Xem chi tiết
                          </Button>
                        </Link>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-12 text-xs text-slate-400">
                    Chưa gắn sản phẩm chỉ định cụ thể.
                  </div>
                )}
              </div>

              <div className="pt-4 mt-4 border-t border-slate-200/60 flex items-center justify-between text-xs">
                <span className="text-slate-500 font-medium">Cần Dược sĩ hỗ trợ thêm?</span>
                <Link
                  href="/prescription"
                  className="font-bold text-brand-blue-700 hover:underline"
                >
                  Tư vấn Dược sĩ trực tuyến &rarr;
                </Link>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
