"use client";

import React, { useState, useMemo, useEffect, Suspense } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Header } from "@/components/layout/Header";
import { PRODUCTS_DATA } from "@/data/products";
import { Product, ProductFilterState, ProductSortOption } from "@/types";
import { ProductCard } from "@/components/product/ProductCard";
import { ProductFilterSidebar } from "@/components/product/ProductFilterSidebar";
import { ProductSortBar } from "@/components/product/ProductSortBar";
import { ProductQuickViewModal } from "@/components/product/ProductQuickViewModal";
import { RxConsultModal } from "@/components/product/RxConsultModal";
import { Footer } from "@/components/layout/Footer";
import {
  ChevronRight,
  Home,
  PackageOpen,
  RotateCcw,
  X,
  ChevronLeft,
  Search,
  Sparkles,
  Stethoscope,
  AlertCircle,
  Loader2,
} from "lucide-react";
import { Button } from "@/components/ui/Button";

const INITIAL_FILTERS: ProductFilterState = {
  category: "",
  subCategory: "",
  brand: [],
  priceRange: "",
  origin: [],
  dosageForm: [],
  prescriptionType: "all",
};

const ITEMS_PER_PAGE = 8;

function ProductsContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const searchParamQuery = searchParams.get("search") || "";
  const categoryParam = searchParams.get("category") || "";

  const [products, setProducts] = useState<Product[]>(PRODUCTS_DATA);
  const [filters, setFilters] = useState<ProductFilterState>(() => ({
    ...INITIAL_FILTERS,
    category: categoryParam,
  }));
  const [sortOption, setSortOption] = useState<ProductSortOption>("popular");
  const [gridCols, setGridCols] = useState<3 | 4>(3);
  const [currentPage, setCurrentPage] = useState(1);
  const [mobileFilterOpen, setMobileFilterOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  // Modals state
  const [quickViewProduct, setQuickViewProduct] = useState<Product | null>(null);
  const [rxConsultProduct, setRxConsultProduct] = useState<Product | null>(null);

  // Sync category param if changed
  useEffect(() => {
    if (categoryParam) {
      setFilters((prev) => ({ ...prev, category: categoryParam }));
    }
  }, [categoryParam]);

  // Dynamically sync products from FastAPI backend based on searchParamQuery and prescriptionType
  useEffect(() => {
    let isMounted = true;
    setIsLoading(true);

    const queryParts = ["limit=300"];
    if (searchParamQuery.trim()) {
      queryParts.push(`search=${encodeURIComponent(searchParamQuery.trim())}`);
    }
    if (filters.prescriptionType && filters.prescriptionType !== "all") {
      queryParts.push(`prescriptionType=${filters.prescriptionType}`);
    } else {
      queryParts.push("prescriptionType=all");
    }

    const url = `/api/v1/store/products?${queryParts.join("&")}`;

    fetch(url)
      .then((res) => {
        if (!res.ok) throw new Error("API error");
        return res.json();
      })
      .then((data) => {
        if (!isMounted) return;
        if (data?.items && Array.isArray(data.items)) {
          setProducts(data.items);
        }
      })
      .catch((err) => {
        if (!isMounted) return;
        console.warn("FastAPI Storefront offline, using fallback catalog:", err);
        // Fallback filter
        if (searchParamQuery.trim()) {
          const q = searchParamQuery.trim().toLowerCase();
          const fallbackMatches = PRODUCTS_DATA.filter((p) => {
            return (
              p.name.toLowerCase().includes(q) ||
              p.brand.toLowerCase().includes(q) ||
              p.activeIngredient.toLowerCase().includes(q) ||
              p.usage.toLowerCase().includes(q) ||
              p.indications.toLowerCase().includes(q)
            );
          });
          setProducts(fallbackMatches);
        } else {
          setProducts(PRODUCTS_DATA);
        }
      })
      .finally(() => {
        if (isMounted) setIsLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [searchParamQuery, filters.prescriptionType]);

  // Filter products locally (brand, origin, priceRange, dosageForm, category)
  const filteredProducts = useMemo(() => {
    return products.filter((product) => {
      // Category filter
      if (filters.category && product.category !== filters.category) {
        return false;
      }
      // Prescription type filter
      if (filters.prescriptionType === "rx" && !product.isPrescription) {
        return false;
      }
      if (filters.prescriptionType === "otc" && product.isPrescription) {
        return false;
      }
      // Brand filter
      if (filters.brand.length > 0 && !filters.brand.includes(product.brand)) {
        return false;
      }
      // Origin filter
      if (filters.origin.length > 0 && !filters.origin.includes(product.origin)) {
        return false;
      }
      // Dosage form filter
      if (
        filters.dosageForm.length > 0 &&
        !filters.dosageForm.includes(product.dosageForm)
      ) {
        return false;
      }
      // Price range filter
      const effectivePrice = product.salePrice || product.price;
      if (filters.priceRange === "under-100" && effectivePrice >= 100000) {
        return false;
      }
      if (
        filters.priceRange === "100-300" &&
        (effectivePrice < 100000 || effectivePrice > 300000)
      ) {
        return false;
      }
      if (
        filters.priceRange === "300-500" &&
        (effectivePrice < 300000 || effectivePrice > 500000)
      ) {
        return false;
      }
      if (filters.priceRange === "above-500" && effectivePrice <= 500000) {
        return false;
      }

      return true;
    });
  }, [products, filters]);

  // Sort products
  const sortedProducts = useMemo(() => {
    const list = [...filteredProducts];
    switch (sortOption) {
      case "newest":
        return list.sort(
          (a, b) =>
            new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
        );
      case "price-asc":
        return list.sort(
          (a, b) => (a.salePrice || a.price) - (b.salePrice || b.price)
        );
      case "price-desc":
        return list.sort(
          (a, b) => (b.salePrice || b.price) - (a.salePrice || a.price)
        );
      case "rating":
        return list.sort((a, b) => b.rating - a.rating);
      case "popular":
      default:
        return list.sort((a, b) => b.reviewCount - a.reviewCount);
    }
  }, [filteredProducts, sortOption]);

  // Pagination logic
  const totalPages = Math.ceil(sortedProducts.length / ITEMS_PER_PAGE) || 1;
  const paginatedProducts = useMemo(() => {
    const start = (currentPage - 1) * ITEMS_PER_PAGE;
    return sortedProducts.slice(start, start + ITEMS_PER_PAGE);
  }, [sortedProducts, currentPage]);

  const handleFilterChange = (newFilters: ProductFilterState) => {
    setFilters(newFilters);
    setCurrentPage(1);
  };

  const handleResetFilters = () => {
    setFilters(INITIAL_FILTERS);
    setCurrentPage(1);
  };

  const handleClearSearch = () => {
    router.push("/products");
  };

  return (
    <div className="min-h-screen flex flex-col bg-slate-50/50">
      {/* 1. Header */}
      <Header />

      {/* 2. Breadcrumb & Page Banner */}
      <div className="bg-white border-b border-slate-200/80 py-4 px-4 sm:px-6 lg:px-8">
        <div className="max-w-7xl mx-auto">
          {/* Breadcrumb */}
          <nav className="flex items-center gap-1.5 text-xs text-slate-500 mb-2 flex-wrap">
            <Link
              href="/"
              className="flex items-center gap-1 hover:text-brand-blue-600 transition-colors"
            >
              <Home className="w-3.5 h-3.5" />
              <span>Trang chủ</span>
            </Link>
            <ChevronRight className="w-3 h-3 text-slate-300" />
            <Link
              href="/products"
              className="hover:text-brand-blue-600 transition-colors"
            >
              Tất cả sản phẩm
            </Link>
            {searchParamQuery && (
              <>
                <ChevronRight className="w-3 h-3 text-slate-300" />
                <span className="font-semibold text-brand-blue-700 bg-brand-blue-50 px-2 py-0.5 rounded-full border border-brand-blue-100 truncate max-w-xs">
                  Tìm kiếm: &ldquo;{searchParamQuery}&rdquo;
                </span>
              </>
            )}
          </nav>

          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
            <div>
              {searchParamQuery ? (
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <Search className="w-5 h-5 text-brand-blue-600" />
                    <h1 className="text-xl sm:text-2xl font-black text-slate-900 tracking-tight">
                      Kết quả tìm kiếm cho: &ldquo;{searchParamQuery}&rdquo;
                    </h1>
                  </div>
                  <p className="text-xs text-slate-500">
                    Tìm thấy <span className="font-bold text-slate-800">{filteredProducts.length}</span> sản phẩm phù hợp trong hệ thống nhà thuốc H4CARE.
                  </p>
                  <div className="mt-2 flex items-start gap-1.5 p-2 rounded-lg bg-amber-50/80 border border-amber-200/60 text-[11px] text-amber-900 max-w-2xl">
                    <AlertCircle className="w-3.5 h-3.5 text-amber-600 shrink-0 mt-0.5" />
                    <span>
                      <strong>Lưu ý y tế:</strong> Kết quả tra cứu chỉ mang tính tham khảo thông tin sản phẩm, không thay thế chẩn đoán hay chỉ định của bác sĩ. Đối với thuốc kê đơn (Rx), khách hàng cần có đơn thuốc hợp lệ từ bác sĩ trước khi sử dụng.
                    </span>
                  </div>
                </div>
              ) : (
                <div>
                  <h1 className="text-2xl font-black text-slate-900 tracking-tight">
                    Danh Mục Thuốc & Sản Phẩm Y Tế
                  </h1>
                  <p className="text-xs text-slate-500 mt-0.5">
                    Cung cấp đầy đủ thuốc kê đơn, không kê đơn, thực phẩm chức năng và thiết bị y tế chuẩn GPP.
                  </p>
                </div>
              )}
            </div>

            {searchParamQuery && (
              <Button
                variant="outline"
                size="sm"
                onClick={handleClearSearch}
                className="self-start sm:self-center gap-1.5 text-xs text-slate-600 border-slate-300 hover:text-rose-600 hover:border-rose-200 hover:bg-rose-50"
              >
                <X className="w-3.5 h-3.5" />
                <span>Xóa tìm kiếm (Xem tất cả)</span>
              </Button>
            )}
          </div>
        </div>
      </div>

      {/* 3. Main Product Listing Content Area */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 w-full flex-1">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
          {/* ================= LEFT SIDEBAR (Desktop) ================= */}
          <aside className="hidden lg:block lg:col-span-3 sticky top-24">
            <ProductFilterSidebar
              filters={filters}
              onFilterChange={handleFilterChange}
              onResetFilters={handleResetFilters}
              totalProducts={filteredProducts.length}
            />
          </aside>

          {/* ================= RIGHT MAIN PRODUCT GRID ================= */}
          <main className="col-span-12 lg:col-span-9 space-y-6">
            {/* Sort and View Options Bar */}
            <ProductSortBar
              total={filteredProducts.length}
              currentSort={sortOption}
              onSortChange={setSortOption}
              gridCols={gridCols}
              onGridColsChange={setGridCols}
              onOpenMobileFilter={() => setMobileFilterOpen(true)}
            />

            {/* Active Filters Badges */}
            {(searchParamQuery ||
              filters.category ||
              filters.brand.length > 0 ||
              filters.priceRange ||
              filters.origin.length > 0 ||
              filters.dosageForm.length > 0 ||
              filters.prescriptionType !== "all") && (
              <div className="flex flex-wrap items-center gap-2 p-3 bg-white rounded-xl border border-slate-200 shadow-xs">
                <span className="text-xs font-bold text-slate-500">Đang lọc theo:</span>

                {searchParamQuery && (
                  <span className="inline-flex items-center gap-1 text-xs px-2.5 py-1 rounded-full bg-brand-blue-50 text-brand-blue-700 font-bold border border-brand-blue-200">
                    Từ khóa: &ldquo;{searchParamQuery}&rdquo;
                    <X
                      className="w-3 h-3 cursor-pointer hover:text-rose-600"
                      onClick={handleClearSearch}
                    />
                  </span>
                )}

                {filters.prescriptionType !== "all" && (
                  <span className="inline-flex items-center gap-1 text-xs px-2.5 py-1 rounded-full bg-indigo-50 text-indigo-700 font-semibold border border-indigo-200">
                    {filters.prescriptionType === "rx" ? "Thuốc kê đơn (Rx)" : "Không kê đơn"}
                    <X
                      className="w-3 h-3 cursor-pointer hover:text-rose-600"
                      onClick={() => setFilters({ ...filters, prescriptionType: "all" })}
                    />
                  </span>
                )}

                {filters.category && (
                  <span className="inline-flex items-center gap-1 text-xs px-2.5 py-1 rounded-full bg-cyan-50 text-cyan-800 font-semibold border border-cyan-200">
                    Danh mục: {filters.category}
                    <X
                      className="w-3 h-3 cursor-pointer hover:text-rose-600"
                      onClick={() => setFilters({ ...filters, category: "" })}
                    />
                  </span>
                )}

                {filters.brand.map((b) => (
                  <span
                    key={b}
                    className="inline-flex items-center gap-1 text-xs px-2.5 py-1 rounded-full bg-slate-100 text-slate-700 font-medium"
                  >
                    {b}
                    <X
                      className="w-3 h-3 cursor-pointer hover:text-rose-600"
                      onClick={() =>
                        setFilters({
                          ...filters,
                          brand: filters.brand.filter((item) => item !== b),
                        })
                      }
                    />
                  </span>
                ))}

                <button
                  onClick={handleResetFilters}
                  className="text-xs text-rose-600 font-bold hover:underline ml-auto"
                >
                  Xóa bộ lọc
                </button>
              </div>
            )}

            {/* Loading state indicator */}
            {isLoading && (
              <div className="py-12 flex flex-col items-center justify-center gap-3 text-slate-500 bg-white rounded-2xl border border-slate-200/80 p-8 shadow-xs">
                <Loader2 className="w-8 h-8 animate-spin text-brand-blue-600" />
                <p className="text-sm font-semibold text-slate-700">Đang tra cứu cơ sở dữ liệu thuốc H4CARE...</p>
              </div>
            )}

            {/* Product Cards Grid */}
            {!isLoading && paginatedProducts.length > 0 ? (
              <div
                className={`grid grid-cols-2 sm:grid-cols-2 ${
                  gridCols === 4
                    ? "lg:grid-cols-4 gap-3 sm:gap-4"
                    : "lg:grid-cols-3 gap-3 sm:gap-5"
                } items-stretch`}
              >
                {paginatedProducts.map((product) => (
                  <ProductCard
                    key={product.id}
                    product={product}
                    onQuickView={(p) => setQuickViewProduct(p)}
                    onOpenRxConsult={(p) => setRxConsultProduct(p)}
                  />
                ))}
              </div>
            ) : !isLoading && (
              <div className="bg-white rounded-2xl border border-slate-200 p-8 sm:p-12 text-center space-y-4 shadow-xs">
                <div className="w-16 h-16 rounded-2xl bg-brand-blue-50 text-brand-blue-600 flex items-center justify-center mx-auto border border-brand-blue-100 shadow-xs">
                  {searchParamQuery ? (
                    <Search className="w-8 h-8 text-brand-blue-500" />
                  ) : (
                    <PackageOpen className="w-8 h-8 text-slate-400" />
                  )}
                </div>
                <div>
                  <h3 className="text-base sm:text-lg font-bold text-slate-900">
                    {searchParamQuery
                      ? `Không tìm thấy thuốc khớp với "${searchParamQuery}"`
                      : "Không tìm thấy sản phẩm phù hợp với bộ lọc"}
                  </h3>
                  <p className="text-xs sm:text-sm text-slate-500 mt-1 max-w-md mx-auto">
                    {searchParamQuery
                      ? "Vui lòng kiểm tra lại chính tả, thử tìm theo tên hoạt chất chính (ví dụ: Paracetamol, Amoxicillin) hoặc liên hệ Dược sĩ H4CARE để được tư vấn thuốc tương đương."
                      : "Hãy thử nới lỏng khoảng giá, bỏ chọn các thương hiệu hoặc xóa các tiêu chí đang lọc để hiển thị nhiều sản phẩm hơn."}
                  </p>
                </div>

                <div className="flex flex-wrap items-center justify-center gap-3 pt-2">
                  {searchParamQuery ? (
                    <>
                      <Button
                        variant="primary"
                        size="sm"
                        onClick={handleClearSearch}
                        className="gap-2"
                      >
                        <RotateCcw className="w-4 h-4" />
                        <span>Xem toàn bộ danh mục thuốc</span>
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => router.push("/category/thuoc-ke-don")}
                        className="gap-2 border-brand-blue-200 text-brand-blue-700 hover:bg-brand-blue-50"
                      >
                        <Stethoscope className="w-4 h-4" />
                        <span>Gửi đơn thuốc cho Dược sĩ</span>
                      </Button>
                    </>
                  ) : (
                    <Button
                      variant="primary"
                      size="sm"
                      onClick={handleResetFilters}
                      className="gap-2"
                    >
                      <RotateCcw className="w-4 h-4" />
                      <span>Xóa tất cả bộ lọc</span>
                    </Button>
                  )}
                </div>
              </div>
            )}

            {/* Pagination Controls */}
            {!isLoading && totalPages > 1 && (
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

      {/* ================= MOBILE FILTER MODAL ================= */}
      {mobileFilterOpen && (
        <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-sm lg:hidden flex justify-end">
          <div className="w-[85%] max-w-sm bg-white h-full overflow-y-auto p-5 space-y-4 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between pb-3 border-b border-slate-100">
                <h3 className="text-base font-bold text-slate-900">Bộ Lọc Tìm Kiếm</h3>
                <button
                  onClick={() => setMobileFilterOpen(false)}
                  className="p-1 rounded-lg text-slate-400 hover:text-slate-700"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              <div className="pt-4">
                <ProductFilterSidebar
                  filters={filters}
                  onFilterChange={handleFilterChange}
                  onResetFilters={handleResetFilters}
                  totalProducts={filteredProducts.length}
                />
              </div>
            </div>

            <div className="pt-4 border-t border-slate-100 sticky bottom-0 bg-white">
              <Button
                variant="primary"
                size="md"
                className="w-full"
                onClick={() => setMobileFilterOpen(false)}
              >
                Áp dụng bộ lọc ({filteredProducts.length})
              </Button>
            </div>
          </div>
        </div>
      )}

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

      {/* Customer-Facing Shared Footer */}
      <Footer />
    </div>
  );
}

export default function ProductsPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen flex items-center justify-center bg-slate-50">
          <div className="flex flex-col items-center gap-3">
            <Loader2 className="w-8 h-8 animate-spin text-brand-blue-600" />
            <p className="text-sm font-semibold text-slate-600">Đang tải danh mục dược phẩm H4CARE...</p>
          </div>
        </div>
      }
    >
      <ProductsContent />
    </Suspense>
  );
}
