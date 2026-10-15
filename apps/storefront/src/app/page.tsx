"use client";

import React, { useState } from "react";
import Link from "next/link";
import { IntroAnimation } from "@/components/intro/IntroAnimation";
import { Header } from "@/components/layout/Header";
import { HeroSection } from "@/components/hero/HeroSection";
import { Footer } from "@/components/layout/Footer";
import { Product } from "@/types";
import { ProductCard } from "@/components/product/ProductCard";
import { ProductQuickViewModal } from "@/components/product/ProductQuickViewModal";
import { RxConsultModal } from "@/components/product/RxConsultModal";
import { SeasonalCampaignsSection } from "@/components/home/SeasonalCampaignsSection";
import {
  ArrowRight,
  Flame,
  Award,
  Loader2,
} from "lucide-react";
import { Button } from "@/components/ui/Button";

export default function HomePage() {
  const [products, setProducts] = useState<Product[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [showIntro, setShowIntro] = useState(false);
  const [introKey, setIntroKey] = useState(0);

  // Modals state for product interaction on Home Page
  const [quickViewProduct, setQuickViewProduct] = useState<Product | null>(null);
  const [rxConsultProduct, setRxConsultProduct] = useState<Product | null>(null);

  React.useEffect(() => {
    setIsLoading(true);
    fetch("/api/v1/store/products?limit=300")
      .then((res) => {
        if (!res.ok) throw new Error("API error");
        return res.json();
      })
      .then((data) => {
        if (data?.items && Array.isArray(data.items)) {
          setProducts(data.items);
        }
      })
      .catch((err) => {
        console.warn("Could not fetch store products on Home:", err);
        setProducts([]);
      })
      .finally(() => {
        setIsLoading(false);
      });
  }, []);

  const handleReplayIntro = () => {
    setIntroKey((prev) => prev + 1);
    setShowIntro(true);
  };

  // Best seller products (4 items)
  const bestSellers = products.filter((p) => p.isBestSeller).slice(0, 4);

  // Featured prescription & OTC items (4 items)
  const featuredProducts = products.filter((p) => p.isFeatured).slice(0, 4);


  return (
    <main className="min-h-screen flex flex-col bg-white">
      {/* 1. Cinematic Intro Sequence (Auto-runs on first visit, replayable) */}
      <IntroAnimation
        key={introKey}
        forceShow={showIntro}
        onComplete={() => setShowIntro(false)}
      />

      {/* 2. Global Sticky Header */}
      <Header onReplayIntro={handleReplayIntro} />

      {/* 3. Hero Section (Phase UI-1 Benchmark) */}
      <HeroSection />

      {/* 4. REAL PRODUCTS SHOWCASE: SẢN PHẨM BÁN CHẠY NHẤT */}
      <section className="py-12 sm:py-16 bg-white border-t border-slate-100">
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
                Danh mục sản phẩm chọn lọc, hạn dùng mới, quy trình kiểm soát chất lượng định hướng chuẩn GPP.
              </p>
            </div>

            <Link href="/products" className="shrink-0">
              <Button
                variant="outline"
                size="sm"
                className="group border-slate-200 hover:border-brand-blue-300 text-xs sm:text-sm"
                rightIcon={<ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-1 transition-transform" />}
              >
                Xem tất cả {products.length} sản phẩm
              </Button>
            </Link>
          </div>

          {/* Product Cards Grid: 2 cols on mobile, 4 cols on desktop */}
          <div className="grid grid-cols-2 sm:grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-5 items-stretch">
            {bestSellers.map((product) => (
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

      {/* 4.5. CHUYÊN ĐỀ DỊCH BỆNH THEO MÙA & PHÁC ĐỒ PHÒNG NGỪA GPP */}
      <SeasonalCampaignsSection />

      {/* 5. NỔI BẬT & THUỐC KÊ ĐƠN TƯ VẤN (Rx Showcase) */}
      <section className="py-12 sm:py-16 bg-[#f8fafc] border-t border-slate-200/80">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 mb-8">
            <div>
              <div className="flex items-center gap-1.5 text-xs font-bold text-brand-blue-600 uppercase tracking-wider mb-1.5">
                <Award className="w-3.5 h-3.5" />
                <span>Chuyên Khoa & Thuốc Kê Đơn</span>
              </div>
              <h2 className="text-2xl sm:text-3xl font-black text-slate-900 tracking-tight">
                Chuyên Khoa & Hỗ Trợ Đơn Thuốc
              </h2>
              <p className="text-xs sm:text-sm text-slate-500 mt-1 max-w-2xl">
                Thuốc điều trị theo phác đồ và sản phẩm chăm sóc đặc thù cần có tư vấn & hướng dẫn của Dược sĩ chuyên môn.
              </p>
            </div>

            <Link href="/category/thuoc-ke-don" className="shrink-0">
              <Button
                variant="primary"
                size="sm"
                className="bg-brand-blue-700 hover:bg-brand-blue-800 text-xs sm:text-sm"
                rightIcon={<ArrowRight className="w-3.5 h-3.5" />}
              >
                Tư vấn đơn thuốc
              </Button>
            </Link>
          </div>

          {/* Featured Cards Grid: 2 cols on mobile, 4 cols on desktop */}
          <div className="grid grid-cols-2 sm:grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-5 items-stretch">
            {featuredProducts.map((product) => (
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

      {/* 6. Customer-facing Shared Footer */}
      <Footer />
    </main>
  );
}
