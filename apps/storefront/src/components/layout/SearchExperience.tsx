"use client";

import React, { useState, useRef, useEffect, useMemo } from "react";
import { useRouter } from "next/navigation";
import {
  Search,
  X,
  Clock,
  TrendingUp,
  Sparkles,
  ArrowRight,
  ShieldCheck,
  AlertCircle,
  Loader2,
  CheckCircle2,
  Pill,
} from "lucide-react";
import { TRENDING_KEYWORDS } from "@/data/mockData";
import { Product } from "@/types";
import { formatVND } from "@/lib/utils";
import { motion, AnimatePresence } from "framer-motion";

interface SearchExperienceProps {
  onSearchSubmit?: (query: string) => void;
  className?: string;
  isMobileModal?: boolean;
  onCloseMobileModal?: () => void;
}

const RECENT_KEY = "h4care_recent_searches";

export const SearchExperience: React.FC<SearchExperienceProps> = ({
  onSearchSubmit,
  className = "",
  isMobileModal = false,
  onCloseMobileModal,
}) => {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [isOpen, setIsOpen] = useState(false);
  const [recentSearches, setRecentSearches] = useState<string[]>([]);
  const [liveResults, setLiveResults] = useState<Product[]>([]);
  const [popularProducts, setPopularProducts] = useState<Product[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [totalFound, setTotalFound] = useState(0);

  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Load recent searches from localStorage on mount & fetch real popular products
  useEffect(() => {
    try {
      const saved = localStorage.getItem(RECENT_KEY);
      if (saved) {
        const parsed = JSON.parse(saved);
        if (Array.isArray(parsed) && parsed.length > 0) {
          setRecentSearches(parsed.slice(0, 6));
          return;
        }
      }
    } catch {}
    setRecentSearches(["Panadol Extra", "Efferalgan 500mg", "Berocca", "Vitamin C DHG"]);

    fetch("/api/v1/store/products?limit=4")
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data?.items && Array.isArray(data.items)) {
          setPopularProducts(data.items);
        }
      })
      .catch(() => {});
  }, []);

  const saveRecentSearch = (kw: string) => {
    const trimmed = kw.trim();
    if (!trimmed) return;
    setRecentSearches((prev) => {
      const updated = [trimmed, ...prev.filter((item) => item.toLowerCase() !== trimmed.toLowerCase())].slice(0, 6);
      try {
        localStorage.setItem(RECENT_KEY, JSON.stringify(updated));
      } catch {}
      return updated;
    });
  };

  // Debounced search query
  const [debouncedQuery, setDebouncedQuery] = useState("");
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedQuery(query.trim());
    }, 220);
    return () => clearTimeout(timer);
  }, [query]);

  // Live fetch from FastAPI /api/v1/store/products with fallback to local catalog
  useEffect(() => {
    if (!debouncedQuery || debouncedQuery.length < 2) {
      setLiveResults([]);
      setTotalFound(0);
      setIsLoading(false);
      setSearchError(null);
      return;
    }

    let isMounted = true;
    setIsLoading(true);
    setSearchError(null);

    fetch(`/api/v1/store/products?search=${encodeURIComponent(debouncedQuery)}&limit=6&prescriptionType=all`)
      .then((res) => {
        if (!res.ok) throw new Error("Search API error");
        return res.json();
      })
      .then((data) => {
        if (!isMounted) return;
        if (data && Array.isArray(data.items)) {
          setLiveResults(data.items);
          setTotalFound(data.total || data.items.length);
        } else {
          setLiveResults([]);
          setTotalFound(0);
        }
      })
      .catch((err) => {
        if (!isMounted) return;
        setSearchError("Không thể kết nối đến máy chủ tra cứu thuốc. Vui lòng thử lại sau.");
        setLiveResults([]);
        setTotalFound(0);
      })
      .finally(() => {
        if (isMounted) setIsLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [debouncedQuery]);

  // Close when clicking outside or pressing Escape
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (
        containerRef.current &&
        !containerRef.current.contains(event.target as Node) &&
        !isMobileModal
      ) {
        setIsOpen(false);
      }
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setIsOpen(false);
        if (onCloseMobileModal) onCloseMobileModal();
      }
    }

    document.addEventListener("mousedown", handleClickOutside);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [isMobileModal, onCloseMobileModal]);

  const handleSelectKeyword = (kw: string) => {
    saveRecentSearch(kw);
    setQuery(kw);
    if (onSearchSubmit) onSearchSubmit(kw);
    setIsOpen(false);
    if (onCloseMobileModal) onCloseMobileModal();
    router.push(`/products?search=${encodeURIComponent(kw.trim())}`);
  };

  const handleKeyDownInput = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && query.trim()) {
      e.preventDefault();
      handleSelectKeyword(query.trim());
    }
  };

  const handleSelectProduct = (product: Product) => {
    saveRecentSearch(product.name);
    setIsOpen(false);
    if (onCloseMobileModal) onCloseMobileModal();
    router.push(`/product/${product.slug}`);
  };

  const removeRecent = (e: React.MouseEvent, index: number) => {
    e.stopPropagation();
    setRecentSearches((prev) => {
      const updated = prev.filter((_, i) => i !== index);
      try {
        localStorage.setItem(RECENT_KEY, JSON.stringify(updated));
      } catch {}
      return updated;
    });
  };

  const clearAllRecent = (e: React.MouseEvent) => {
    e.stopPropagation();
    setRecentSearches([]);
    try {
      localStorage.removeItem(RECENT_KEY);
    } catch {}
  };

  return (
    <div ref={containerRef} className={`relative w-full ${className}`}>
      {/* Search Input Bar - Long Châu style prominent pill bar */}
      <div
        className={`relative flex items-center w-full min-h-[48px] sm:min-h-[52px] transition-all duration-200 rounded-full px-1.5 ${
          isOpen
            ? "ring-2 ring-brand-blue-500 shadow-depth-2 bg-white border border-brand-blue-500"
            : "bg-slate-50 hover:bg-slate-100/90 border border-slate-200/90 hover:border-slate-300 shadow-xs"
        }`}
      >
        <div className="pl-3.5 pr-2 text-slate-400 shrink-0">
          {isLoading ? (
            <Loader2 className="w-5 h-5 text-brand-blue-600 animate-spin" />
          ) : (
            <Search
              className={`w-5 h-5 transition-colors duration-150 ${
                isOpen ? "text-brand-blue-600" : "text-slate-400"
              }`}
            />
          )}
        </div>

        <input
          ref={inputRef}
          type="text"
          value={query}
          onFocus={() => setIsOpen(true)}
          onChange={(e) => {
            setQuery(e.target.value);
            if (!isOpen) setIsOpen(true);
          }}
          onKeyDown={handleKeyDownInput}
          placeholder="Tìm tên thuốc, hoạt chất, triệu chứng, vitamin..."
          className="w-full py-2.5 pr-2 text-sm sm:text-[15px] bg-transparent outline-none text-slate-800 placeholder:text-slate-400 font-medium"
        />

        <div className="flex items-center gap-1.5 mr-1 shrink-0">
          {query && (
            <button
              type="button"
              onClick={() => {
                setQuery("");
                inputRef.current?.focus();
              }}
              className="p-1.5 text-slate-400 hover:text-slate-600 rounded-full hover:bg-slate-200/60 transition-colors"
              title="Xóa từ khóa"
            >
              <X className="w-4 h-4" />
            </button>
          )}
          <button
            type="button"
            onClick={() => handleSelectKeyword(query.trim())}
            className="h-8 sm:h-9 px-4 sm:px-5 bg-gradient-to-r from-brand-blue-600 to-brand-blue-700 hover:from-brand-blue-700 hover:to-brand-blue-800 text-white rounded-full text-xs sm:text-sm font-bold transition-all shadow-sm flex items-center gap-1.5 active:scale-95 shrink-0"
            aria-label="Tìm kiếm thuốc"
          >
            <Search className="w-3.5 h-3.5 sm:w-4 sm:h-4" />
            <span className="hidden sm:inline">Tìm kiếm</span>
          </button>
        </div>
      </div>

      {/* Suggestion Dropdown Popover */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, y: 6, scale: 0.99 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 4, scale: 0.99 }}
            transition={{ duration: 0.15, ease: [0.16, 1, 0.3, 1] }}
            style={{ backgroundColor: "#ffffff" }}
            className={`absolute left-0 right-0 mt-2 z-[100] rounded-2xl bg-white border border-slate-200 shadow-2xl overflow-hidden ${
              isMobileModal ? "static mt-4 shadow-none border-0" : "max-h-[560px] overflow-y-auto"
            }`}
          >
            <div className="p-4 divide-y divide-slate-100 bg-white">
              {/* 1. Live Search Results if typing */}
              {debouncedQuery.length >= 2 ? (
                <div className="pb-3 bg-white">
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-1.5 text-xs font-bold text-slate-700 uppercase tracking-wider">
                      <Search className="w-3.5 h-3.5 text-brand-blue-600" />
                      <span>Kết quả tìm kiếm cho &ldquo;{debouncedQuery}&rdquo;</span>
                    </div>
                    {isLoading ? (
                      <span className="text-[11px] font-semibold text-slate-400 flex items-center gap-1">
                        <Loader2 className="w-3 h-3 animate-spin" />
                        Đang tra cứu từ Dược thư Quốc gia...
                      </span>
                    ) : (
                      <span className="text-[11px] font-bold text-brand-blue-700 bg-brand-blue-50 px-2 py-0.5 rounded-full border border-brand-blue-100">
                        {totalFound} sản phẩm
                      </span>
                    )}
                  </div>

                  {searchError ? (
                    <div className="py-6 text-center text-rose-500 space-y-2">
                      <AlertCircle className="w-6 h-6 mx-auto text-rose-500" />
                      <p className="text-xs font-bold text-rose-700">{searchError}</p>
                    </div>
                  ) : liveResults.length > 0 ? (
                    <div className="space-y-2">
                      {liveResults.map((prod) => {
                        const safeBrand =
                          !prod.brand || prod.brand.includes("{") || prod.brand.includes('"') || prod.brand.length > 40
                            ? "Dược Phẩm Chính Hãng"
                            : prod.brand;
                        return (
                          <div
                            key={prod.id}
                            onClick={() => handleSelectProduct(prod)}
                            className="flex items-center gap-3 p-3 rounded-xl border border-slate-200/90 bg-white hover:border-brand-blue-400 hover:bg-brand-blue-50/40 cursor-pointer transition-all duration-150 group shadow-xs"
                          >
                            <div className="w-12 h-12 rounded-lg bg-slate-50 border border-slate-200 overflow-hidden shrink-0 flex items-center justify-center p-1">
                              <img
                                src={prod.images?.[0] || prod.thumbnail || "/images/medicines/panadol.jpg"}
                                alt={prod.name}
                                className="w-full h-full object-contain mix-blend-multiply group-hover:scale-105 transition-transform duration-200"
                              />
                            </div>
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-1.5 mb-1 flex-wrap">
                                <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider truncate max-w-[140px] inline-block">
                                  {safeBrand}
                                </span>
                                {prod.isPrescription ? (
                                  <span className="text-[9px] font-bold text-rose-700 bg-rose-50 px-1.5 py-0.5 rounded border border-rose-200">
                                    Thuốc kê đơn (Rx)
                                  </span>
                                ) : (
                                  <span className="text-[9px] font-semibold text-brand-blue-700 bg-brand-blue-50 px-1.5 py-0.5 rounded border border-brand-blue-100">
                                    {prod.categoryName || "Không kê đơn"}
                                  </span>
                                )}
                              </div>
                              <h4 className="text-xs font-bold text-slate-900 line-clamp-1 group-hover:text-brand-blue-600 transition-colors">
                                {prod.name}
                              </h4>
                              {prod.activeIngredient && (
                                <p className="text-[11px] text-slate-500 truncate mt-0.5">
                                  <span className="text-slate-400 font-medium">Hoạt chất:</span> {prod.activeIngredient}
                                </p>
                              )}
                              <div className="flex items-baseline gap-2 mt-1">
                                <span className="text-xs font-black text-brand-blue-700">
                                  {formatVND(prod.salePrice || prod.price)}
                                </span>
                                {prod.salePrice && (
                                  <span className="text-[10px] text-slate-400 line-through">
                                    {formatVND(prod.price)}
                                  </span>
                                )}
                              </div>
                            </div>
                            <ArrowRight className="w-4 h-4 text-slate-300 group-hover:text-brand-blue-600 group-hover:translate-x-1 transition-all shrink-0" />
                          </div>
                        );
                      })}

                      {/* View all search results button */}
                      <button
                        type="button"
                        onClick={() => handleSelectKeyword(debouncedQuery)}
                        className="w-full mt-2 py-2.5 px-3 bg-slate-50 hover:bg-brand-blue-50 border border-slate-200 hover:border-brand-blue-200 rounded-xl text-xs font-bold text-brand-blue-700 flex items-center justify-center gap-1.5 transition-colors"
                      >
                        <span>Xem tất cả {totalFound} sản phẩm cho &ldquo;{debouncedQuery}&rdquo;</span>
                        <ArrowRight className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  ) : !isLoading ? (
                    <div className="py-6 text-center text-slate-500 space-y-2">
                      <AlertCircle className="w-6 h-6 mx-auto text-slate-400" />
                      <p className="text-xs font-bold text-slate-700">
                        Không tìm thấy thuốc khớp với &ldquo;{debouncedQuery}&rdquo;
                      </p>
                      <p className="text-[11px] text-slate-500 max-w-sm mx-auto">
                        Thử tìm theo hoạt chất (ví dụ: <span className="font-semibold text-brand-blue-600">Paracetamol, Amoxicillin</span>) hoặc triệu chứng (<span className="font-semibold text-brand-blue-600">Hạ sốt, Đau đầu, Dạ dày</span>).
                      </p>
                    </div>
                  ) : null}
                </div>
              ) : (
                <>
                  {/* 2. Lịch sử tìm kiếm gần đây */}
                  {recentSearches.length > 0 && (
                    <div className="pb-3">
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-1.5 text-xs font-bold text-slate-600 uppercase tracking-wider">
                          <Clock className="w-3.5 h-3.5 text-brand-blue-500" />
                          <span>Tìm kiếm gần đây</span>
                        </div>
                        <button
                          onClick={clearAllRecent}
                          className="text-[11px] text-slate-400 hover:text-rose-500 font-medium transition-colors"
                        >
                          Xóa tất cả
                        </button>
                      </div>
                      <div className="flex flex-wrap gap-1.5">
                        {recentSearches.map((item, idx) => (
                          <span
                            key={idx}
                            onClick={() => handleSelectKeyword(item)}
                            className="group inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs bg-slate-100 hover:bg-brand-blue-50 text-slate-700 hover:text-brand-blue-700 border border-slate-200/60 hover:border-brand-blue-200 cursor-pointer transition-all duration-150"
                          >
                            <span>{item}</span>
                            <X
                              onClick={(e) => removeRecent(e, idx)}
                              className="w-3 h-3 text-slate-400 group-hover:text-slate-600 hover:text-rose-500"
                            />
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* 3. Từ khóa thịnh hành */}
                  <div className="py-3">
                    <div className="flex items-center gap-1.5 mb-2 text-xs font-bold text-slate-600 uppercase tracking-wider">
                      <TrendingUp className="w-3.5 h-3.5 text-brand-cyan-500" />
                      <span>Xu hướng tìm kiếm hôm nay</span>
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                      {TRENDING_KEYWORDS.map((keyword, idx) => (
                        <button
                          key={idx}
                          onClick={() => handleSelectKeyword(keyword)}
                          className="inline-flex items-center gap-1 px-3 py-1 rounded-xl text-xs font-medium bg-slate-50 hover:bg-cyan-50 text-slate-700 hover:text-cyan-800 border border-slate-200/70 hover:border-cyan-200 transition-all duration-150 active:scale-95"
                        >
                          <Sparkles className="w-3 h-3 text-cyan-500" />
                          <span>{keyword}</span>
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* 4. Dược phẩm tiêu biểu */}
                  <div className="pt-3">
                    <div className="flex items-center justify-between mb-2.5 text-xs font-bold text-slate-600 uppercase tracking-wider">
                      <div className="flex items-center gap-1.5">
                        <ShieldCheck className="w-3.5 h-3.5 text-brand-emerald-500" />
                        <span>Dược phẩm thiết yếu chuẩn GPP</span>
                      </div>
                      <span
                        onClick={() => {
                          setIsOpen(false);
                          router.push("/products");
                        }}
                        className="text-[11px] text-brand-blue-600 font-semibold cursor-pointer hover:underline"
                      >
                        Xem tất cả
                      </span>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                      {popularProducts.map((prod) => (
                        <div
                          key={prod.id}
                          onClick={() => handleSelectProduct(prod)}
                          className="flex items-center gap-2.5 p-2 rounded-xl border border-slate-100 hover:border-brand-blue-200 hover:bg-brand-blue-50/40 cursor-pointer transition-all duration-150 group"
                        >
                          <div className="w-10 h-10 rounded-lg bg-slate-50 border border-slate-200/70 overflow-hidden shrink-0 flex items-center justify-center p-0.5">
                            <img
                              src={prod.images?.[0] || "/images/medicines/panadol.jpg"}
                              alt={prod.name}
                              className="w-full h-full object-contain mix-blend-multiply group-hover:scale-105 transition-transform"
                            />
                          </div>
                          <div className="flex-1 min-w-0">
                            <h4 className="text-xs font-semibold text-slate-800 line-clamp-1 group-hover:text-brand-blue-600 transition-colors">
                              {prod.name}
                            </h4>
                            <span className="text-xs font-bold text-brand-blue-700">
                              {formatVND(prod.salePrice || prod.price)}
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </>
              )}

              {/* Bottom fast consultation hint */}
              <div className="pt-3 mt-3 flex items-center justify-between text-xs text-slate-500 bg-gradient-to-r from-blue-50/70 to-cyan-50/70 -mx-4 -mb-4 p-3 border-t border-slate-100">
                <span className="flex items-center gap-1.5 text-[11px]">
                  <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                  Dược sĩ H4CARE đang trực tuyến
                </span>
                <span
                  onClick={() => {
                    setIsOpen(false);
                    router.push("/category/thuoc-ke-don");
                  }}
                  className="inline-flex items-center gap-1 font-bold text-brand-blue-600 hover:underline cursor-pointer text-[11px]"
                >
                  <span>Gửi đơn thuốc theo toa</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </span>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};
