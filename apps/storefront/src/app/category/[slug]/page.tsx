"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { Header } from "@/components/layout/Header";
import { CATEGORIES_DATA } from "@/data/mockData";
import { getStoreCategoriesTree, getStoreProducts } from "@/lib/api/products";
import { Category, Product, ProductFilterState, ProductSortOption } from "@/types";
import { ProductCard } from "@/components/product/ProductCard";
import { ProductSortBar } from "@/components/product/ProductSortBar";
import { ProductFilterSidebar } from "@/components/product/ProductFilterSidebar";
import { ProductQuickViewModal } from "@/components/product/ProductQuickViewModal";
import { RxConsultModal } from "@/components/product/RxConsultModal";
import { FptPolyBadge } from "@/components/branding/FptPolyBadge";
import {
  ChevronRight,
  ChevronLeft,
  Home,
  PackageOpen,
  RotateCcw,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { Button } from "@/components/ui/Button";

const ITEMS_PER_PAGE = 12;

export default function CategoryPage() {
  const params = useParams();
  const slug = params?.slug as string;

  const [categories, setCategories] = useState<Category[]>(CATEGORIES_DATA);
  const [products, setProducts] = useState<Product[]>([]);
  const [totalProducts, setTotalProducts] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [isLoadingProducts, setIsLoadingProducts] = useState(true);

  // Facet data from backend
  const [availableBrands, setAvailableBrands] = useState<string[]>([]);
  const [availableOrigins, setAvailableOrigins] = useState<string[]>([]);
  const [availableDosageForms, setAvailableDosageForms] = useState<string[]>([]);

  const [activeSubCategory, setActiveSubCategory] = useState<string>("");
  const [sortOption, setSortOption] = useState<ProductSortOption>("popular");
  const [gridCols, setGridCols] = useState<3 | 4>(3);
  const [currentPage, setCurrentPage] = useState(1);
  const [mobileFilterOpen, setMobileFilterOpen] = useState(false);

  // Modals state
  const [quickViewProduct, setQuickViewProduct] = useState<Product | null>(null);
  const [rxConsultProduct, setRxConsultProduct] = useState<Product | null>(null);

  // Filter state for sidebar
  const [filters, setFilters] = useState<ProductFilterState>({
    category: slug,
    subCategory: "",
    brand: [],
    priceRange: "",
    origin: [],
    dosageForm: [],
    prescriptionType: "all",
  });

  // Load category tree once
  useEffect(() => {
    let mounted = true;
    getStoreCategoriesTree().then((cats) => {
      if (mounted && cats?.length) setCategories(cats);
    });
    return () => {
      mounted = false;
    };
  }, []);

  // Sync category changes
  useEffect(() => {
    setFilters((prev) => ({
      ...prev,
      category: slug,
      subCategory: "",
    }));
    setActiveSubCategory("");
    setCurrentPage(1);
  }, [slug]);

  // Server-side fetching: pagination, sort, facet filtering
  useEffect(() => {
    let mounted = true;
    setIsLoadingProducts(true);

    getStoreProducts({
      page: currentPage,
      pageSize: ITEMS_PER_PAGE,
      category: slug,
      subCategory: activeSubCategory || undefined,
      prescriptionType: filters.prescriptionType,
      brand: filters.brand.length > 0 ? filters.brand : undefined,
      origin: filters.origin.length > 0 ? filters.origin : undefined,
      dosageForm: filters.dosageForm.length > 0 ? filters.dosageForm : undefined,
      priceRange: filters.priceRange || undefined,
      sort: sortOption,
    })
      .then((res) => {
        if (!mounted) return;
        setProducts(res?.items || []);
        setTotalProducts(res?.total || 0);
        setTotalPages(res?.totalPages || 1);
        if (res?.availableBrands?.length) setAvailableBrands(res.availableBrands);
        if (res?.availableOrigins?.length) setAvailableOrigins(res.availableOrigins);
        if (res?.availableDosageForms?.length) setAvailableDosageForms(res.availableDosageForms);
      })
      .catch((err) => {
        console.warn("Error fetching category products:", err);
        if (mounted) {
          setProducts([]);
          setTotalProducts(0);
          setTotalPages(1);
        }
      })
      .finally(() => {
        if (mounted) setIsLoadingProducts(false);
      });

    return () => {
      mounted = false;
    };
  }, [slug, activeSubCategory, filters, sortOption, currentPage]);

  const currentCategory =
    categories.find((c) => c.slug === slug) ||
    CATEGORIES_DATA.find((c) => c.slug === slug);

  const handleSubCategorySelect = (subSlug: string) => {
    setActiveSubCategory(activeSubCategory === subSlug ? "" : subSlug);
    setCurrentPage(1);
  };

  const handleResetFilters = () => {
    setActiveSubCategory("");
    setFilters({
      category: slug,
      subCategory: "",
      brand: [],
      priceRange: "",
      origin: [],
      dosageForm: [],
      prescriptionType: "all",
    });
    setCurrentPage(1);
  };

  if (!currentCategory) {
    return (
      <div className="min-h-screen flex flex-col bg-slate-50">
        <Header />
        <div className="max-w-xl mx-auto my-auto text-center p-8 bg-white rounded-3xl border border-slate-200 shadow-sm space-y-4">
          <h2 className="text-xl font-bold text-slate-800">Danh Mục Không Tồn Tại</h2>
          <p className="text-xs text-slate-500">
            Danh mục bạn đang tìm kiếm không tồn tại hoặc đã được cập nhật lại.
          </p>
          <Link href="/products">
            <Button variant="primary" size="md">
              Xem Tất Cả Sản Phẩm
            </Button>
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col bg-slate-50/50">
      <Header />

      {/* Category Banner */}
      <div className="bg-gradient-to-r from-brand-blue-900 via-brand-blue-800 to-slate-900 text-white py-8 px-4 sm:px-6 lg:px-8">
        <div className="max-w-7xl mx-auto">
          {/* Breadcrumb */}
          <nav className="flex items-center gap-1.5 text-xs text-slate-300 mb-4">
            <Link href="/" className="hover:text-cyan-300 flex items-center gap-1">
              <Home className="w-3.5 h-3.5" />
              <span>Trang chủ</span>
            </Link>
            <ChevronRight className="w-3 h-3 text-slate-400" />
            <Link href="/products" className="hover:text-cyan-300">
              Sản phẩm
            </Link>
            <ChevronRight className="w-3 h-3 text-slate-400" />
            <span className="font-semibold text-white">{currentCategory.name}</span>
          </nav>

          <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
            <div className="max-w-2xl">
              <div className="flex items-center gap-2 mb-2">
                <span className="text-xs font-bold px-2.5 py-0.5 rounded-full bg-cyan-400/20 text-cyan-200 border border-cyan-400/30">
                  {currentCategory.badge || "Chính Hãng"}
                </span>
                <span className="text-xs text-slate-300 flex items-center gap-1">
                  <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
                  Chuẩn bảo quản GSP
                </span>
              </div>
              <h1 className="text-3xl sm:text-4xl font-black tracking-tight mb-2">
                {currentCategory.name}
              </h1>
              <p className="text-xs sm:text-sm text-slate-300 leading-relaxed">
                {currentCategory.description || currentCategory.featuredSubtitle}
              </p>
            </div>

            {/* Quick Consultation Badge */}
            <div className="p-3.5 rounded-xl bg-slate-900/90 border border-slate-700/80 text-xs shrink-0 flex items-center gap-3 shadow-xs">
              <div className="w-9 h-9 rounded-lg bg-cyan-500/20 text-cyan-300 flex items-center justify-center font-bold border border-cyan-400/30">
                <Sparkles className="w-5 h-5" />
              </div>
              <div>
                <p className="font-bold text-white">Tư Vấn Đúng Bệnh, Đúng Thuốc</p>
                <p className="text-[11px] text-cyan-300">Dược sĩ chuyên môn tận tâm tư vấn (8h00 - 21h30)</p>
              </div>
            </div>
          </div>

          {/* Subcategory Pills Carousel */}
          {currentCategory.subCategories.length > 0 && (
            <div className="flex items-center gap-2 mt-6 overflow-x-auto pb-1 custom-scrollbar">
              <button
                onClick={() => handleSubCategorySelect("")}
                className={`px-3.5 py-1.5 rounded-full text-xs font-semibold shrink-0 transition-all ${
                  activeSubCategory === ""
                    ? "bg-white text-brand-blue-900 shadow-sm"
                    : "bg-white/15 text-slate-200 hover:bg-white/25"
                }`}
              >
                Tất cả nhóm
              </button>
              {currentCategory.subCategories.map((sub) => {
                const isActive = activeSubCategory === sub.slug;
                return (
                  <button
                    key={sub.id}
                    onClick={() => handleSubCategorySelect(sub.slug)}
                    className={`px-3.5 py-1.5 rounded-full text-xs font-semibold shrink-0 transition-all ${
                      isActive
                        ? "bg-cyan-400 text-slate-950 font-bold shadow-sm"
                        : "bg-white/15 text-slate-200 hover:bg-white/25"
                    }`}
                  >
                    {sub.name}
                  </button>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* Main Grid Area */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 w-full flex-1">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
          {/* Filter Sidebar */}
          <aside className="hidden lg:block lg:col-span-3 sticky top-24">
            <ProductFilterSidebar
              filters={filters}
              onFilterChange={(f) => {
                setFilters(f);
                setCurrentPage(1);
              }}
              onResetFilters={handleResetFilters}
              totalProducts={totalProducts}
              availableBrands={availableBrands}
              availableOrigins={availableOrigins}
              availableDosageForms={availableDosageForms}
            />
          </aside>

          {/* Main Cards List */}
          <main className="col-span-12 lg:col-span-9 space-y-6">
            <ProductSortBar
              total={totalProducts}
              currentSort={sortOption}
              onSortChange={(s) => {
                setSortOption(s);
                setCurrentPage(1);
              }}
              gridCols={gridCols}
              onGridColsChange={setGridCols}
              onOpenMobileFilter={() => setMobileFilterOpen(true)}
            />

            {isLoadingProducts ? (
              <div
                className={`grid grid-cols-1 sm:grid-cols-2 ${
                  gridCols === 4 ? "lg:grid-cols-4 gap-4" : "lg:grid-cols-3 gap-5"
                }`}
              >
                {[...Array(6)].map((_, i) => (
                  <div
                    key={i}
                    className="bg-white rounded-2xl p-5 border border-slate-200 animate-pulse space-y-4 shadow-xs"
                  >
                    <div className="w-full aspect-square bg-slate-100 rounded-xl" />
                    <div className="h-4 bg-slate-100 rounded w-3/4" />
                    <div className="h-3 bg-slate-100 rounded w-1/2" />
                    <div className="h-6 bg-slate-100 rounded w-1/3" />
                  </div>
                ))}
              </div>
            ) : products.length > 0 ? (
              <div
                className={`grid grid-cols-1 sm:grid-cols-2 ${
                  gridCols === 4 ? "lg:grid-cols-4 gap-4" : "lg:grid-cols-3 gap-5"
                }`}
              >
                {products.map((product) => (
                  <ProductCard
                    key={product.id}
                    product={product}
                    onQuickView={(p) => setQuickViewProduct(p)}
                    onOpenRxConsult={(p) => setRxConsultProduct(p)}
                  />
                ))}
              </div>
            ) : (
              <div className="bg-white rounded-2xl p-10 sm:p-12 text-center border border-slate-200 shadow-xs space-y-4">
                <div className="w-16 h-16 rounded-full bg-slate-100 text-slate-400 flex items-center justify-center mx-auto border border-slate-200">
                  <PackageOpen className="w-8 h-8" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-slate-800">
                    Chưa có sản phẩm trong nhóm lọc này
                  </h3>
                  <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
                    Vui lòng chọn nhóm phân loại khác hoặc xóa các tiêu chí bộ lọc.
                  </p>
                </div>
                <Button
                  variant="primary"
                  size="sm"
                  onClick={handleResetFilters}
                  leftIcon={<RotateCcw className="w-4 h-4" />}
                >
                  Xóa bộ lọc
                </Button>
              </div>
            )}

            {/* Pagination Controls */}
            {!isLoadingProducts && totalPages > 1 && (
              <div className="flex items-center justify-center gap-2 pt-6">
                <button
                  onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                  disabled={currentPage === 1}
                  className="p-2 rounded-xl border border-slate-200 bg-white text-slate-600 disabled:opacity-40 disabled:cursor-not-allowed hover:bg-slate-50 transition-colors shadow-xs"
                >
                  <ChevronLeft className="w-4 h-4" />
                </button>
                {Array.from({ length: totalPages }, (_, i) => i + 1).map((page) => (
                  <button
                    key={page}
                    onClick={() => setCurrentPage(page)}
                    className={`w-9 h-9 rounded-xl text-xs font-bold transition-all shadow-xs ${
                      currentPage === page
                        ? "bg-brand-blue-600 text-white shadow-brand-blue-500/20 shadow-md"
                        : "bg-white border border-slate-200 text-slate-700 hover:bg-slate-50"
                    }`}
                  >
                    {page}
                  </button>
                ))}
                <button
                  onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                  disabled={currentPage === totalPages}
                  className="p-2 rounded-xl border border-slate-200 bg-white text-slate-600 disabled:opacity-40 disabled:cursor-not-allowed hover:bg-slate-50 transition-colors shadow-xs"
                >
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            )}
          </main>
        </div>
      </div>

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

      {/* Academic Project Footer */}
      <footer className="border-t border-slate-200 bg-slate-900 text-slate-400 text-xs py-8 mt-12">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-4">
          <FptPolyBadge variant="dark" />
          <p className="text-[11px] text-slate-400">
            H4CARE Pharmacy • Đồ án sinh viên FPT Polytechnic • Hùng - Đức Anh - Hoàn - Cường
          </p>
        </div>
      </footer>
    </div>
  );
}
