"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { IntroAnimation } from "@/components/intro/IntroAnimation";
import { Header } from "@/components/layout/Header";
import { HeroSection } from "@/components/hero/HeroSection";
import { Footer } from "@/components/layout/Footer";
import { Product } from "@/types";
import { ProductCard } from "@/components/product/ProductCard";
import { ProductQuickViewModal } from "@/components/product/ProductQuickViewModal";
import { RxConsultModal } from "@/components/product/RxConsultModal";
import {
  ArrowRight,
  Flame,
  Award,
  Sparkles,
  ShieldCheck,
  Stethoscope,
  HeartPulse,
  Pill,
  Droplets,
  PackageCheck,
  CheckCircle2,
  FileText,
  Clock,
  Building2,
  MessageSquare,
  ChevronRight,
  BookOpen,
} from "lucide-react";
import { Button } from "@/components/ui/Button";

interface CuratedHomeData {
  bestsellers: Product[];
  otc_medicines: Product[];
  supplements: Product[];
  medical_devices: Product[];
  campaigns: Array<{
    id: string;
    title: string;
    tag: string;
    description: string;
    gradient: string;
    cta: string;
    link: string;
  }>;
  verified_brands: Array<{
    name: string;
    country: string;
    badge: string;
    logoText: string;
  }>;
  health_articles: Array<{
    id: string;
    title: string;
    category: string;
    readTime: string;
    author: string;
    date: string;
    summary: string;
    link: string;
  }>;
  total_active_products: number;
}

export default function HomePage() {
  const [data, setData] = useState<CuratedHomeData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [showIntro, setShowIntro] = useState(false);
  const [introKey, setIntroKey] = useState(0);

  // Modals state for product interaction on Home Page
  const [quickViewProduct, setQuickViewProduct] = useState<Product | null>(null);
  const [rxConsultProduct, setRxConsultProduct] = useState<Product | null>(null);

  useEffect(() => {
    setIsLoading(true);
    fetch("/api/v1/store/home/curated")
      .then((res) => {
        if (!res.ok) throw new Error("API error");
        return res.json();
      })
      .then((json: CuratedHomeData) => {
        setData(json);
      })
      .catch((err) => {
        console.warn("Could not fetch curated home data:", err);
      })
      .finally(() => {
        setIsLoading(false);
      });
  }, []);

  const handleReplayIntro = () => {
    setIntroKey((prev) => prev + 1);
    setShowIntro(true);
  };

  const handleOpenPharmacistChat = (contextMsg?: string, product?: Product) => {
    if (typeof window !== "undefined") {
      window.dispatchEvent(
        new CustomEvent("h4care_open_chat", {
          detail: {
            message:
              contextMsg ||
              "Xin chào dược sĩ, tôi cần tư vấn dùng thuốc và hướng dẫn liều dùng.",
            contextProduct: product,
          },
        })
      );
    }
  };

  const quickCategories = [
    {
      title: "Thuốc Không Kê Đơn",
      subtitle: "Hạ sốt, tiêu hóa, cảm ho",
      icon: Pill,
      href: "/category/thuoc-khong-ke-don",
      color: "text-blue-600 bg-blue-50 border-blue-100",
    },
    {
      title: "Thuốc Kê Đơn (Rx)",
      subtitle: "Tư vấn & thẩm định đơn",
      icon: Stethoscope,
      href: "/category/thuoc-ke-don",
      color: "text-indigo-600 bg-indigo-50 border-indigo-100",
    },
    {
      title: "Vitamin & Thực Phẩm CN",
      subtitle: "Tăng đề kháng, xương khớp",
      icon: Sparkles,
      href: "/category/thuc-pham-chuc-nang",
      color: "text-amber-600 bg-amber-50 border-amber-100",
    },
    {
      title: "Thiết Bị Y Tế",
      subtitle: "Huyết áp, nhiệt kế, đo đường",
      icon: HeartPulse,
      href: "/category/thiet-bi-y-te",
      color: "text-emerald-600 bg-emerald-50 border-emerald-100",
    },
    {
      title: "Dược Mỹ Phẩm",
      subtitle: "Phục hồi da, chống nắng",
      icon: Droplets,
      href: "/category/duoc-my-pham",
      color: "text-teal-600 bg-teal-50 border-teal-100",
    },
    {
      title: "Mẹ & Bé",
      subtitle: "Sữa, men vi sinh, dinh dưỡng",
      icon: Award,
      href: "/category/me-va-be",
      color: "text-rose-600 bg-rose-50 border-rose-100",
    },
  ];

  return (
    <main className="min-h-screen flex flex-col bg-white">
      {/* 1. Cinematic Intro Sequence */}
      <IntroAnimation
        key={introKey}
        forceShow={showIntro}
        onComplete={() => setShowIntro(false)}
      />

      {/* 2. Global Sticky Header */}
      <Header onReplayIntro={handleReplayIntro} />

      {/* 3. Hero Section */}
      <HeroSection />

      {/* 4. QUICK CATEGORY PILLS */}
      <section className="py-8 bg-slate-50/70 border-y border-slate-100">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
            {quickCategories.map((c, i) => {
              const Icon = c.icon;
              return (
                <Link
                  key={i}
                  href={c.href}
                  className="group p-3.5 rounded-2xl bg-white border border-slate-200/80 hover:border-brand-blue-300 hover:shadow-depth-1 transition-all flex flex-col items-center text-center select-none"
                >
                  <div
                    className={`w-11 h-11 rounded-xl flex items-center justify-center mb-2.5 transition-transform group-hover:scale-110 ${c.color}`}
                  >
                    <Icon className="w-5 h-5" />
                  </div>
                  <span className="text-xs font-bold text-slate-800 line-clamp-1 group-hover:text-brand-blue-600 transition-colors">
                    {c.title}
                  </span>
                  <span className="text-[10px] text-slate-400 mt-0.5 line-clamp-1">
                    {c.subtitle}
                  </span>
                </Link>
              );
            })}
          </div>
        </div>
      </section>

      {/* 5. BESTSELLERS: SẢN PHẨM BÁN CHẠY & VERIFIED PACKSHOTS */}
      <section className="py-12 sm:py-16 bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 mb-8">
            <div>
              <div className="flex items-center gap-1.5 text-xs font-bold text-rose-600 uppercase tracking-wider mb-1.5">
                <Flame className="w-3.5 h-3.5 fill-current text-rose-500" />
                <span>Bán Chạy Nhất Tại Nhà Thuốc</span>
              </div>
              <h2 className="text-2xl sm:text-3xl font-black text-slate-900 tracking-tight">
                Sản Phẩm Y Tế Được Tin Dùng
              </h2>
              <p className="text-xs sm:text-sm text-slate-500 mt-1 max-w-2xl">
                Bao bì chuẩn xác, số lô hạn dùng minh bạch, kiểm soát chất lượng theo nguyên tắc FEFO.
              </p>
            </div>

            <Link href="/products" className="shrink-0">
              <Button
                variant="outline"
                size="sm"
                className="group border-slate-200 hover:border-brand-blue-300 text-xs sm:text-sm"
                rightIcon={<ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-1 transition-transform" />}
              >
                Xem tất cả {data?.total_active_products || 194} sản phẩm
              </Button>
            </Link>
          </div>

          {/* Grid Cards */}
          {isLoading ? (
            <div className="grid grid-cols-2 sm:grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-5">
              {[...Array(4)].map((_, idx) => (
                <div key={idx} className="h-72 rounded-2xl bg-slate-100 animate-pulse" />
              ))}
            </div>
          ) : (
            <div className="grid grid-cols-2 sm:grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-5 items-stretch">
              {(data?.bestsellers || []).slice(0, 8).map((product) => (
                <ProductCard
                  key={product.id}
                  product={product}
                  onQuickView={(p) => setQuickViewProduct(p)}
                  onOpenRxConsult={(p) => setRxConsultProduct(p)}
                />
              ))}
            </div>
          )}
        </div>
      </section>

      {/* 6. SEASONAL HEALTH CAMPAIGNS */}
      <section className="py-10 bg-slate-50 border-y border-slate-200/80">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 sm:gap-6">
            {(data?.campaigns || []).map((camp) => (
              <div
                key={camp.id}
                className={`p-6 sm:p-8 rounded-3xl bg-gradient-to-br ${camp.gradient} text-white shadow-depth-2 flex flex-col justify-between relative overflow-hidden group`}
              >
                <div className="absolute top-0 right-0 w-64 h-64 bg-white/10 rounded-full blur-2xl pointer-events-none group-hover:scale-110 transition-transform duration-500" />
                <div>
                  <span className="inline-flex items-center px-3 py-1 rounded-full bg-white/20 backdrop-blur-md text-xs font-bold uppercase tracking-wider mb-3">
                    {camp.tag}
                  </span>
                  <h3 className="text-xl sm:text-2xl font-black tracking-tight leading-tight mb-2">
                    {camp.title}
                  </h3>
                  <p className="text-xs sm:text-sm text-white/90 leading-relaxed max-w-md">
                    {camp.description}
                  </p>
                </div>
                <div className="mt-6 flex items-center gap-3">
                  <Link href={camp.link}>
                    <Button
                      variant="primary"
                      size="sm"
                      className="bg-white text-slate-900 hover:bg-slate-100 font-bold border-none"
                      rightIcon={<ArrowRight className="w-3.5 h-3.5" />}
                    >
                      {camp.cta}
                    </Button>
                  </Link>
                  <button
                    onClick={() => handleOpenPharmacistChat(`Tôi muốn tìm hiểu thêm về: ${camp.title}`)}
                    className="px-3 py-2 rounded-xl bg-white/15 hover:bg-white/25 text-xs font-bold transition-colors flex items-center gap-1.5"
                  >
                    <MessageSquare className="w-3.5 h-3.5" />
                    Tư vấn dược sĩ
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* 7. ESSENTIAL OTC MEDICINES */}
      <section className="py-12 sm:py-16 bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 mb-8">
            <div>
              <div className="flex items-center gap-1.5 text-xs font-bold text-brand-blue-600 uppercase tracking-wider mb-1.5">
                <Pill className="w-3.5 h-3.5" />
                <span>Thuốc Không Kê Đơn Thiết Yếu</span>
              </div>
              <h2 className="text-2xl sm:text-3xl font-black text-slate-900 tracking-tight">
                Tủ Thuốc Gia Đình An Toàn
              </h2>
              <p className="text-xs sm:text-sm text-slate-500 mt-1 max-w-2xl">
                Giảm đau hạ sốt, đau họng, tiêu hóa, dị ứng và cảm cúm từ các thương hiệu dược phẩm uy tín.
              </p>
            </div>

            <Link href="/category/thuoc-khong-ke-don" className="shrink-0">
              <Button
                variant="outline"
                size="sm"
                className="border-slate-200 hover:border-brand-blue-300 text-xs sm:text-sm"
                rightIcon={<ArrowRight className="w-3.5 h-3.5" />}
              >
                Xem danh mục OTC
              </Button>
            </Link>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-5 items-stretch">
            {(data?.otc_medicines || []).map((product) => (
              <ProductCard
                key={product.id}
                product={product}
                onQuickView={(p) => setQuickViewProduct(p)}
                onOpenRxConsult={(p) => setRxConsultProduct(p)}
              />
            ))}
          </div>
        </div>
      </section>

      {/* 8. VITAMINS & WELLNESS SUPPLEMENTS */}
      <section className="py-12 sm:py-16 bg-[#f8fafc] border-t border-slate-200/80">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 mb-8">
            <div>
              <div className="flex items-center gap-1.5 text-xs font-bold text-amber-600 uppercase tracking-wider mb-1.5">
                <Sparkles className="w-3.5 h-3.5" />
                <span>Tăng Cường Đề Kháng & Sức Khỏe</span>
              </div>
              <h2 className="text-2xl sm:text-3xl font-black text-slate-900 tracking-tight">
                Vitamin & Thực Phẩm Chức Năng
              </h2>
              <p className="text-xs sm:text-sm text-slate-500 mt-1 max-w-2xl">
                Sản phẩm bổ sung vi chất, khoáng chất, sụn khớp và men vi sinh nhập khẩu chính ngạch.
              </p>
            </div>

            <Link href="/category/thuc-pham-chuc-nang" className="shrink-0">
              <Button
                variant="outline"
                size="sm"
                className="border-slate-200 hover:border-brand-blue-300 text-xs sm:text-sm"
                rightIcon={<ArrowRight className="w-3.5 h-3.5" />}
              >
                Xem tất cả TPCN
              </Button>
            </Link>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-5 items-stretch">
            {(data?.supplements || []).map((product) => (
              <ProductCard
                key={product.id}
                product={product}
                onQuickView={(p) => setQuickViewProduct(p)}
                onOpenRxConsult={(p) => setRxConsultProduct(p)}
              />
            ))}
          </div>
        </div>
      </section>

      {/* 9. PRESCRIPTION WORKFLOW & COUNSELING GUARANTEE */}
      <section className="py-14 sm:py-20 bg-gradient-to-b from-brand-blue-900 to-slate-900 text-white relative overflow-hidden">
        <div className="absolute inset-0 bg-radial from-brand-blue-600/10 via-transparent to-transparent pointer-events-none" />
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10">
          <div className="text-center max-w-3xl mx-auto mb-12">
            <span className="inline-flex items-center gap-1.5 px-3.5 py-1 rounded-full bg-white/10 backdrop-blur-md text-xs font-bold uppercase tracking-wider text-brand-cyan-400 mb-3 border border-white/15">
              <ShieldCheck className="w-4 h-4" />
              Tuân Thủ Luật Dược 2016 & Chuẩn GPP
            </span>
            <h2 className="text-2xl sm:text-4xl font-black tracking-tight leading-tight">
              Quy Trình Cung Ứng Thuốc Kê Đơn (Rx) Chuẩn Y Khoa
            </h2>
            <p className="text-xs sm:text-sm text-slate-300 mt-3 leading-relaxed">
              H4CARE nghiêm cấm mua bán thuốc kê đơn trực tuyến tự do. Mọi yêu cầu thuốc kê đơn đều trải qua quy trình 4 bước thẩm định nghiêm ngặt từ Dược sĩ Chuyên khoa.
            </p>
          </div>

          {/* 4 Steps Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-6">
            <div className="p-6 rounded-2xl bg-white/5 border border-white/10 backdrop-blur-xs flex flex-col justify-between">
              <div>
                <div className="w-10 h-10 rounded-xl bg-brand-cyan-500/20 text-brand-cyan-400 flex items-center justify-center font-black text-lg mb-4">
                  1
                </div>
                <h3 className="text-base font-bold text-white mb-1.5">Tải Đơn Thuốc</h3>
                <p className="text-xs text-slate-300 leading-relaxed">
                  Khách hàng chụp hoặc gửi đơn thuốc hợp lệ có chữ ký bác sĩ và chẩn đoán điều trị.
                </p>
              </div>
              <div className="mt-4 pt-3 border-t border-white/10 flex items-center gap-1.5 text-[11px] text-slate-400">
                <FileText className="w-3.5 h-3.5 text-brand-cyan-400" /> Đơn chụp rõ nét
              </div>
            </div>

            <div className="p-6 rounded-2xl bg-white/5 border border-white/10 backdrop-blur-xs flex flex-col justify-between">
              <div>
                <div className="w-10 h-10 rounded-xl bg-blue-500/20 text-blue-400 flex items-center justify-center font-black text-lg mb-4">
                  2
                </div>
                <h3 className="text-base font-bold text-white mb-1.5">Dược Sĩ Thẩm Định</h3>
                <p className="text-xs text-slate-300 leading-relaxed">
                  Dược sĩ đại học đối soát hàm lượng, tương tác thuốc và tư vấn cách dùng thuốc an toàn.
                </p>
              </div>
              <div className="mt-4 pt-3 border-t border-white/10 flex items-center gap-1.5 text-[11px] text-slate-400">
                <Stethoscope className="w-3.5 h-3.5 text-blue-400" /> Dược sĩ CKI tư vấn
              </div>
            </div>

            <div className="p-6 rounded-2xl bg-white/5 border border-white/10 backdrop-blur-xs flex flex-col justify-between">
              <div>
                <div className="w-10 h-10 rounded-xl bg-emerald-500/20 text-emerald-400 flex items-center justify-center font-black text-lg mb-4">
                  3
                </div>
                <h3 className="text-base font-bold text-white mb-1.5">Phân Bổ Kho Chi Nhánh</h3>
                <p className="text-xs text-slate-300 leading-relaxed">
                  Đơn hàng được phân bổ về chi nhánh kho gần nhất, bảo quản điều kiện chuẩn nhiệt độ GSP.
                </p>
              </div>
              <div className="mt-4 pt-3 border-t border-white/10 flex items-center gap-1.5 text-[11px] text-slate-400">
                <Building2 className="w-3.5 h-3.5 text-emerald-400" /> Kho Hà Nội & TP.HCM
              </div>
            </div>

            <div className="p-6 rounded-2xl bg-white/5 border border-white/10 backdrop-blur-xs flex flex-col justify-between">
              <div>
                <div className="w-10 h-10 rounded-xl bg-amber-500/20 text-amber-400 flex items-center justify-center font-black text-lg mb-4">
                  4
                </div>
                <h3 className="text-base font-bold text-white mb-1.5">Giao Tận Tay</h3>
                <p className="text-xs text-slate-300 leading-relaxed">
                  Đóng gói niêm phong bảo mật, giao nhanh tận tay kèm cẩm nang chỉ dẫn dùng thuốc.
                </p>
              </div>
              <div className="mt-4 pt-3 border-t border-white/10 flex items-center gap-1.5 text-[11px] text-slate-400">
                <PackageCheck className="w-3.5 h-3.5 text-amber-400" /> Niêm phong GSP
              </div>
            </div>
          </div>

          {/* Action CTAs */}
          <div className="mt-10 flex flex-wrap items-center justify-center gap-3">
            <button
              onClick={() => handleOpenPharmacistChat("Xin chào dược sĩ, tôi muốn tư vấn về đơn thuốc bệnh viện.")}
              className="px-6 py-3 rounded-xl bg-brand-cyan-500 hover:bg-brand-cyan-400 text-slate-900 font-bold text-sm transition-colors flex items-center gap-2 shadow-lg"
            >
              <MessageSquare className="w-4 h-4" />
              Tư Vấn Ngay Với Dược Sĩ
            </button>
            <Link href="/category/thuoc-ke-don">
              <button className="px-6 py-3 rounded-xl bg-white/10 hover:bg-white/20 text-white font-bold text-sm transition-colors border border-white/20">
                Tra Cứu Danh Mục Kê Đơn (Rx)
              </button>
            </Link>
          </div>
        </div>
      </section>

      {/* 10. VERIFIED PHARMACEUTICAL BRANDS */}
      <section className="py-12 bg-white border-b border-slate-100">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center max-w-2xl mx-auto mb-8">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-400">
              Đối Tác Dược Phẩm Chiến Lược
            </span>
            <h2 className="text-xl sm:text-2xl font-black text-slate-900 tracking-tight mt-1">
              Thương Hiệu Được Phê Duyệt Phân Phối
            </h2>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-3">
            {(data?.verified_brands || []).map((brand, i) => (
              <Link
                key={i}
                href={`/products?brand=${encodeURIComponent(brand.name)}`}
                className="p-3 rounded-2xl border border-slate-100 bg-slate-50/50 hover:bg-white hover:border-brand-blue-300 hover:shadow-xs transition-all flex flex-col items-center justify-center text-center group"
              >
                <div className="w-12 h-12 rounded-xl bg-white border border-slate-200 flex items-center justify-center font-black text-xs text-brand-blue-700 tracking-wider shadow-2xs mb-2 group-hover:scale-105 transition-transform">
                  {brand.logoText}
                </div>
                <span className="text-xs font-bold text-slate-800 line-clamp-1 group-hover:text-brand-blue-600 transition-colors">
                  {brand.name}
                </span>
                <span className="text-[10px] text-slate-400 font-medium">
                  {brand.country}
                </span>
              </Link>
            ))}
          </div>
        </div>
      </section>

      {/* 11. CLINICAL HEALTH ARTICLES & ADVICE */}
      <section className="py-12 sm:py-16 bg-slate-50/80">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 mb-8">
            <div>
              <div className="flex items-center gap-1.5 text-xs font-bold text-teal-600 uppercase tracking-wider mb-1.5">
                <BookOpen className="w-3.5 h-3.5" />
                <span>Góc Dược Lâm Sàng & Cẩm Nang Sức Khỏe</span>
              </div>
              <h2 className="text-2xl sm:text-3xl font-black text-slate-900 tracking-tight">
                Kiến Thức Y Khoa Đáng Tin Cậy
              </h2>
              <p className="text-xs sm:text-sm text-slate-500 mt-1 max-w-2xl">
                Thông tin được thẩm định và biên soạn bởi đội ngũ Dược sĩ Chuyên khoa H4CARE.
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
            {(data?.health_articles || []).map((art) => (
              <Link
                key={art.id}
                href={art.link}
                className="group p-6 rounded-3xl bg-white border border-slate-200 shadow-xs hover:border-brand-blue-300 hover:shadow-depth-1 transition-all flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-center justify-between text-xs text-slate-400 mb-3">
                    <span className="font-semibold text-brand-blue-600 px-2 py-0.5 rounded-full bg-blue-50 border border-blue-100">
                      {art.category}
                    </span>
                    <span className="flex items-center gap-1">
                      <Clock className="w-3 h-3" /> {art.readTime}
                    </span>
                  </div>
                  <h3 className="text-base font-bold text-slate-900 leading-snug group-hover:text-brand-blue-600 transition-colors">
                    {art.title}
                  </h3>
                  <p className="text-xs text-slate-500 leading-relaxed mt-2.5 line-clamp-3">
                    {art.summary}
                  </p>
                </div>

                <div className="mt-5 pt-3 border-t border-slate-100 flex items-center justify-between text-xs text-slate-400">
                  <span className="font-medium text-slate-600">{art.author}</span>
                  <span className="flex items-center gap-1 text-brand-blue-600 font-bold group-hover:translate-x-1 transition-transform">
                    Chi tiết <ChevronRight className="w-3 h-3" />
                  </span>
                </div>
              </Link>
            ))}
          </div>
        </div>
      </section>

      {/* Quick View Modal */}
      <ProductQuickViewModal
        product={quickViewProduct}
        isOpen={!!quickViewProduct}
        onClose={() => setQuickViewProduct(null)}
        onOpenRxConsult={(p) => setRxConsultProduct(p)}
      />

      {/* Rx Consultation Modal */}
      <RxConsultModal
        product={rxConsultProduct}
        isOpen={!!rxConsultProduct}
        onClose={() => setRxConsultProduct(null)}
      />

      {/* 12. Customer-facing Shared Footer */}
      <Footer />
    </main>
  );
}
