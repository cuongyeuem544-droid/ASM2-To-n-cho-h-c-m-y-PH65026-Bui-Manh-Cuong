"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { Header } from "@/components/layout/Header";
import { Product, ProductSkuItem } from "@/types";
import { ProductCard } from "@/components/product/ProductCard";
import { RxConsultModal } from "@/components/product/RxConsultModal";
import { ProductQuickViewModal } from "@/components/product/ProductQuickViewModal";
import { ProductReviewsSection } from "@/components/product/ProductReviewsSection";
import { ProductTransparencyCard } from "@/components/product/ProductTransparencyCard";
import { FptPolyBadge } from "@/components/branding/FptPolyBadge";
import { Button } from "@/components/ui/Button";
import { formatVND } from "@/lib/utils";
import { useAuth } from "@/lib/auth/auth-context";
import { PHARMACY_CONTACT } from "@/lib/constants";
import {
  ChevronRight,
  Home,
  Star,
  ShieldCheck,
  Stethoscope,
  ShoppingBag,
  Heart,
  Share2,
  CheckCircle2,
  AlertTriangle,
  AlertCircle,
  Minus,
  Plus,
  Pill,
  FileText,
  Clock,
  Check,
  X,
  MapPin,
  QrCode,
  Info,
  Layers,
  Sparkles,
  ArrowRight,
  Bot,
  MessageSquare,
} from "lucide-react";

const FALLBACK_MEDICINE_IMAGE = "/images/placeholder-medicine.svg";

export default function ProductDetailPage() {
  const params = useParams();
  const slug = params?.slug as string;
  const router = useRouter();

  // Dữ liệu sản phẩm thực tế từ Neon PostgreSQL Core API (không dùng mock offline)
  const [product, setProduct] = useState<Product | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [relatedProducts, setRelatedProducts] = useState<Product[]>([]);
  const [selectedSku, setSelectedSku] = useState<ProductSkuItem | null>(null);
  const [selectedImgIdx, setSelectedImgIdx] = useState(0);
  const [imgErrorMap, setImgErrorMap] = useState<Record<number, boolean>>({});
  const [quantity, setQuantity] = useState(1);
  const [activeTab, setActiveTab] = useState<
    "overview" | "ingredients" | "indications" | "usage" | "precautions" | "storage"
  >("overview");
  const [isWishlisted, setIsWishlisted] = useState(false);
  const [copiedLink, setCopiedLink] = useState(false);

  // Modals & feedback
  const [isRxModalOpen, setIsRxModalOpen] = useState(false);
  const [quickViewProduct, setQuickViewProduct] = useState<Product | null>(null);
  const [showAddedToast, setShowAddedToast] = useState(false);
  const [warningToast, setWarningToast] = useState<string | null>(null);

  // 1. Fetch official product details from Core Backend API
  useEffect(() => {
    if (!slug) return;
    setIsLoading(true);

    fetch(`/api/v1/store/products/${encodeURIComponent(slug)}`)
      .then((res) => {
        if (!res.ok) throw new Error("Not found in API");
        return res.json();
      })
      .then((data) => {
        if (data && data.name) {
          setProduct(data);
          if (data.skus && data.skus.length > 0) {
            setSelectedSku(data.selectedSku || data.skus[0]);
          }
          // Tải sản phẩm liên quan thực tế từ Neon DB theo danh mục
          if (data.category) {
            fetch(`/api/v1/store/products?category=${encodeURIComponent(data.category)}&limit=5`)
              .then((r) => (r.ok ? r.json() : null))
              .then((catData) => {
                const items = catData?.items || (Array.isArray(catData) ? catData : []);
                setRelatedProducts(
                  items
                    .filter((p: Product) => p.id !== data.id && p.catalogTier !== "INTERNAL_TEST")
                    .slice(0, 4)
                );
              })
              .catch(() => {});
          }
        } else {
          setProduct(null);
        }
      })
      .catch((err) => {
        console.error("Lỗi khi tải thông tin sản phẩm từ máy chủ:", err);
        setProduct(null);
      })
      .finally(() => {
        setIsLoading(false);
      });
  }, [slug]);

  // 2. Switch SKU Packaging unit dynamically
  const handleSelectSku = async (sku: ProductSkuItem) => {
    setSelectedSku(sku);
    setQuantity(1);

    // Call Backend Eligibility API to get verified stock and price for the selected SKU
    try {
      const res = await fetch(
        `/api/v1/store/products/${encodeURIComponent(slug)}/eligibility?skuId=${sku.id}`
      );
      if (res.ok) {
        const elig = await res.json();
        setProduct((prev) => {
          if (!prev) return null;
          return {
            ...prev,
            price: sku.base_price,
            stock: elig.available_stock,
            isSaleEligible: elig.is_eligible_for_sale,
            canAddToCart: elig.can_add_to_cart,
            ctaType: elig.cta_type,
            ctaLabel: elig.cta_label,
            primaryReason: elig.primary_reason,
            reasons: elig.reasons,
            selectedSku: sku,
          };
        });
      }
    } catch (e) {
      // Local state fallback
      setProduct((prev) => (prev ? { ...prev, price: sku.base_price, selectedSku: sku } : null));
    }
  };

  // Image fallback handler
  const handleImageError = (index: number) => {
    setImgErrorMap((prev) => ({ ...prev, [index]: true }));
  };

  // Copy shareable link
  const handleCopyLink = () => {
    if (typeof window !== "undefined") {
      navigator.clipboard.writeText(window.location.href);
      setCopiedLink(true);
      setTimeout(() => setCopiedLink(false), 2500);
    }
  };

  // Hỏi Trợ lý AI H4CARE về sản phẩm này
  const handleAskAssistant = () => {
    if (!product || typeof window === "undefined") return;
    window.dispatchEvent(
      new CustomEvent("h4care_open_chat", {
        detail: {
          message: `Cho tôi hỏi thêm thông tin về sản phẩm ${product.name}`,
          contextProduct: {
            id: String(product.id || product.dbId || ""),
            name: product.name,
            slug: product.slug,
            brand: product.brand,
            activeIngredient: product.activeIngredient,
            price: product.price,
            isPrescription: product.isPrescription,
          },
        },
      })
    );
  };

  // 3. Shopping cart action handler
  const handleAddToCart = (redirectAfter = false) => {
    if (!product) return;

    // A. Kiểm tra Thuốc kê đơn Rx
    if (product.isPrescription) {
      setWarningToast(
        "Theo quy định của Bộ Y Tế, thuốc kê đơn (Rx) không được phép bán trực tuyến. Vui lòng gửi toa thuốc để Dược sĩ Đại học xác thực."
      );
      setTimeout(() => setWarningToast(null), 5000);
      setIsRxModalOpen(true);
      return;
    }

    // B. Kiểm tra danh mục tham khảo
    if (product.catalogTier === "REFERENCE_ONLY") {
      setWarningToast(
        product.primaryReason ||
          "Sản phẩm thuộc danh mục tra cứu thông tin y tế. Vui lòng liên hệ Dược sĩ để được tư vấn."
      );
      setTimeout(() => setWarningToast(null), 5000);
      return;
    }

    // C. Kiểm tra tồn kho & quá hạn
    const effectiveStock = selectedSku ? selectedSku.available_stock : product.stock;
    if (effectiveStock <= 0 || product.canAddToCart === false || product.catalogTier === "OUT_OF_STOCK" || product.isSaleEligible === false) {
      setWarningToast("Sản phẩm hiện đang tạm hết hàng hoặc lô thuốc đã hết hạn sử dụng. Không thể đặt hàng.");
      setTimeout(() => setWarningToast(null), 5000);
      return;
    }

    const currentPrice = selectedSku ? selectedSku.base_price : product.salePrice || product.price || 0;
    const dbId =
      product.dbId ||
      (product.id && product.id.startsWith("pt-")
        ? parseInt(product.id.replace("pt-", ""), 10)
        : 1);

    try {
      let cart: any[] = [];
      const raw = localStorage.getItem("pharmatrust_cart");
      if (raw) {
        const parsed = JSON.parse(raw);
        if (Array.isArray(parsed)) cart = parsed;
      }

      const cartItemKey = `${product.id}-${selectedSku ? selectedSku.id : "default"}`;
      const existingIndex = cart.findIndex((i: any) => i.cartKey === cartItemKey || i.id === product.id);

      if (existingIndex > -1) {
        cart[existingIndex].quantity += quantity;
      } else {
        cart.push({
          cartKey: cartItemKey,
          id: product.id,
          dbId: dbId,
          skuId: selectedSku?.id,
          name: product.name,
          price: currentPrice,
          salePrice: product.salePrice,
          quantity: quantity,
          image: (product.images && product.images[0]) || FALLBACK_MEDICINE_IMAGE,
          unit: selectedSku?.uom || product.packaging || "Hộp",
          isPrescription: product.isPrescription || false,
        });
      }

      localStorage.setItem("pharmatrust_cart", JSON.stringify(cart));
      window.dispatchEvent(new Event("cart_updated"));

      if (redirectAfter) {
        router.push("/cart");
      } else {
        setShowAddedToast(true);
        setTimeout(() => setShowAddedToast(false), 4500);
      }
    } catch (e) {
      console.error("Lỗi cập nhật giỏ hàng:", e);
      if (redirectAfter) router.push("/cart");
    }
  };

  // Product not found state
  if (!product && !isLoading) {
    return (
      <div className="min-h-screen flex flex-col bg-slate-50">
        <Header />
        <div className="max-w-lg mx-auto my-auto text-center p-8 bg-white rounded-3xl border border-slate-200 shadow-sm space-y-4">
          <div className="w-16 h-16 rounded-full bg-rose-50 text-rose-500 flex items-center justify-center mx-auto">
            <AlertTriangle className="w-8 h-8" />
          </div>
          <h2 className="text-xl font-bold text-slate-900">Không Tìm Thấy Sản Phẩm</h2>
          <p className="text-xs text-slate-500">
            Sản phẩm này có thể đã ngừng lưu hành hoặc đường dẫn không chính xác.
          </p>
          <Link href="/products">
            <Button variant="primary" size="md">
              Khám Phá Danh Mục Thuốc
            </Button>
          </Link>
        </div>
      </div>
    );
  }

  if (!product) {
    return (
      <div className="min-h-screen flex flex-col bg-slate-50">
        <Header />
        <div className="max-w-7xl mx-auto px-4 py-16 text-center text-slate-500 text-xs">
          Đang tải thông tin dược phẩm...
        </div>
      </div>
    );
  }

  // Images setup
  const galleryImages = product.images && product.images.length > 0
    ? product.images
    : [product.thumbnail || FALLBACK_MEDICINE_IMAGE];
  const activeImage = imgErrorMap[selectedImgIdx]
    ? FALLBACK_MEDICINE_IMAGE
    : galleryImages[selectedImgIdx] || FALLBACK_MEDICINE_IMAGE;

  // Active pricing & packaging
  const currentPrice = selectedSku ? selectedSku.base_price : product.salePrice || product.price || 0;
  const currentUnit = selectedSku ? selectedSku.uom : product.packaging || "Hộp";
  const availableStock = selectedSku ? selectedSku.available_stock : product.stock || 0;
  const availableSkus = product.skus || [];

  return (
    <div className="min-h-screen flex flex-col bg-slate-50 text-slate-800">
      <Header />

      {/* ================= BREADCRUMB NAVIGATION ================= */}
      <nav
        aria-label="Breadcrumb"
        className="bg-white border-b border-slate-200/80 sticky top-16 z-30 shadow-2xs"
      >
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-2.5">
          <ol className="flex items-center flex-wrap gap-1.5 text-xs text-slate-500">
            <li className="flex items-center gap-1.5">
              <Link href="/" className="hover:text-brand-blue-700 flex items-center gap-1">
                <Home className="w-3.5 h-3.5" />
                <span className="hidden sm:inline">Trang chủ</span>
              </Link>
              <ChevronRight className="w-3 h-3 text-slate-300" />
            </li>
            <li className="flex items-center gap-1.5">
              <Link href="/products" className="hover:text-brand-blue-700">
                Sản phẩm
              </Link>
              <ChevronRight className="w-3 h-3 text-slate-300" />
            </li>
            <li className="flex items-center gap-1.5">
              <Link
                href={`/category/${product.category}`}
                className="hover:text-brand-blue-700 max-w-[140px] sm:max-w-xs truncate"
              >
                {product.categoryName}
              </Link>
              <ChevronRight className="w-3 h-3 text-slate-300" />
            </li>
            <li className="font-semibold text-slate-900 truncate max-w-[180px] sm:max-w-md">
              {product.name}
            </li>
          </ol>
        </div>
      </nav>

      {/* ================= MAIN PRODUCT DETAIL CONTAINER ================= */}
      <main className="flex-1 max-w-7xl mx-auto w-full px-4 sm:px-6 lg:px-8 py-6 space-y-8">
        <div className="bg-white rounded-3xl border border-slate-200/90 p-5 sm:p-8 shadow-xs">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 lg:gap-10">
            {/* ================= CỘT TRÁI: GALLERY ẢNH (5 CỘT) ================= */}
            <div className="lg:col-span-5 space-y-4">
              {/* Ảnh chính lớn */}
              <div className="relative aspect-square w-full rounded-2xl border border-slate-200 bg-white p-4 flex items-center justify-center overflow-hidden group shadow-2xs">
                <img
                  src={activeImage}
                  alt={product.name}
                  onError={() => handleImageError(selectedImgIdx)}
                  className="max-h-full max-w-full object-contain transition-transform duration-300 group-hover:scale-105"
                />

                {/* Badge trạng thái trên ảnh */}
                <div className="absolute top-3 left-3 flex flex-col gap-1.5">
                  {product.isPrescription ? (
                    <span className="px-2.5 py-1 text-[11px] font-black uppercase rounded-lg bg-rose-600 text-white shadow-xs">
                      Thuốc kê đơn (Rx)
                    </span>
                  ) : product.catalogTier === "REFERENCE_ONLY" ? (
                    <span className="px-2.5 py-1 text-[11px] font-bold uppercase rounded-lg bg-amber-500 text-white shadow-xs">
                      Tra cứu thông tin
                    </span>
                  ) : (
                    <span className="px-2.5 py-1 text-[11px] font-bold uppercase rounded-lg bg-brand-blue-600 text-white shadow-xs">
                      {product.categoryName}
                    </span>
                  )}
                </div>
              </div>

              {/* Thumbnails Strip */}
              {galleryImages.length > 1 && (
                <div className="flex items-center gap-2.5 overflow-x-auto pb-1.5 scrollbar-thin">
                  {galleryImages.map((img, idx) => (
                    <button
                      key={idx}
                      onClick={() => setSelectedImgIdx(idx)}
                      className={`relative w-16 h-16 rounded-xl border-2 p-1 bg-white shrink-0 overflow-hidden transition-all ${
                        selectedImgIdx === idx
                          ? "border-brand-blue-600 shadow-xs ring-2 ring-brand-blue-100"
                          : "border-slate-200 opacity-70 hover:opacity-100"
                      }`}
                    >
                      <img
                        src={imgErrorMap[idx] ? FALLBACK_MEDICINE_IMAGE : img}
                        alt=""
                        onError={() => handleImageError(idx)}
                        className="w-full h-full object-contain"
                      />
                    </button>
                  ))}
                </div>
              )}

              {/* Assurance Trust Badges (Inspired by Long Châu) */}
              <div className="grid grid-cols-2 gap-2.5 pt-2 text-xs text-slate-600">
                <div className="p-2.5 rounded-xl bg-slate-50 border border-slate-200/80 flex items-center gap-2">
                  <ShieldCheck className="w-4 h-4 text-emerald-600 shrink-0" />
                  <span className="text-[11.5px] font-medium">Đối chiếu hồ sơ Cục QLD</span>
                </div>
                <div className="p-2.5 rounded-xl bg-slate-50 border border-slate-200/80 flex items-center gap-2">
                  <Stethoscope className="w-4 h-4 text-brand-blue-600 shrink-0" />
                  <span className="text-[11.5px] font-medium">Dược sĩ Đại học tư vấn</span>
                </div>
              </div>
            </div>

            {/* ================= CỘT PHẢI: CHI TIẾT SẢN PHẨM & MỞ BÁN (7 CỘT) ================= */}
            <div className="lg:col-span-7 flex flex-col justify-between space-y-6">
              <div>
                {/* Header: Thương hiệu, SKU & Social Share */}
                <div className="flex items-center justify-between pb-3 mb-3 border-b border-slate-100">
                  <div className="flex flex-wrap items-center gap-2 text-xs">
                    <span className="font-black text-brand-blue-700 uppercase tracking-wider">
                      {product.brand}
                    </span>
                    <span className="text-slate-300">•</span>
                    <span className="text-slate-500 font-medium">
                      Mã SKU: <span className="font-mono text-slate-700">{selectedSku?.sku_code || product.sku}</span>
                    </span>
                    <span className="text-slate-300">•</span>
                    <span className="text-slate-500 font-medium">
                      Số ĐK: <span className="font-mono font-semibold text-slate-800">{product.sku}</span>
                    </span>
                  </div>

                  <div className="flex items-center gap-2 shrink-0">
                    <button
                      onClick={() => setIsWishlisted(!isWishlisted)}
                      className={`p-2 rounded-full border transition-colors ${
                        isWishlisted
                          ? "bg-rose-50 text-rose-500 border-rose-200"
                          : "text-slate-400 hover:text-slate-700 border-slate-200 hover:bg-slate-100"
                      }`}
                      title="Lưu vào danh sách quan tâm"
                    >
                      <Heart className={`w-4 h-4 ${isWishlisted ? "fill-current" : ""}`} />
                    </button>
                    <button
                      onClick={handleCopyLink}
                      className="p-2 rounded-full border border-slate-200 text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors"
                      title="Sao chép đường dẫn sản phẩm"
                    >
                      {copiedLink ? (
                        <Check className="w-4 h-4 text-emerald-600" />
                      ) : (
                        <Share2 className="w-4 h-4" />
                      )}
                    </button>
                  </div>
                </div>

                {/* Tên sản phẩm chính thức */}
                <h1 className="text-xl sm:text-2xl font-black text-slate-900 leading-snug tracking-tight mb-3">
                  {product.name}
                </h1>

                {/* Rating & Stock Status */}
                <div className="flex flex-wrap items-center gap-4 text-xs mb-5">
                  <div className="flex items-center gap-1.5">
                    <div className="flex text-amber-400">
                      {[...Array(5)].map((_, i) => (
                        <Star
                          key={i}
                          className={`w-3.5 h-3.5 ${
                            (product.reviewCount ?? 0) > 0 && i < Math.floor(product.rating ?? 0)
                              ? "fill-current"
                              : "text-slate-200"
                          }`}
                        />
                      ))}
                    </div>
                    <span className="font-bold text-slate-800">
                      {(product.reviewCount ?? 0) > 0 ? (product.rating ?? 0).toFixed(1) : "0.0"}
                    </span>
                    <span className="text-slate-400">({product.reviewCount ?? 0} đánh giá)</span>
                  </div>

                  <span className="text-slate-300">|</span>

                  {product.isPrescription ? (
                    <span className="text-rose-600 font-semibold flex items-center gap-1">
                      <AlertCircle className="w-3.5 h-3.5" />
                      Cần đơn thuốc của Bác sĩ
                    </span>
                  ) : product.catalogTier === "REFERENCE_ONLY" ? (
                    <span className="text-amber-700 font-semibold flex items-center gap-1">
                      <Info className="w-3.5 h-3.5 text-amber-600" />
                      Danh mục tra cứu y tế tham khảo
                    </span>
                  ) : availableStock > 0 ? (
                    <span className="text-emerald-600 font-semibold flex items-center gap-1">
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      Còn hàng ({availableStock} {currentUnit})
                    </span>
                  ) : (
                    <span className="text-rose-600 font-semibold flex items-center gap-1">
                      <AlertTriangle className="w-3.5 h-3.5" />
                      Tạm hết hàng tại kho
                    </span>
                  )}
                </div>

                {/* ================= CHỌN QUY CÁCH / ĐƠN VỊ ĐÓNG GÓI (MULTI-SKU) ================= */}
                {availableSkus.length > 1 && (
                  <div className="mb-5 p-3.5 rounded-2xl bg-slate-50 border border-slate-200/80 space-y-2">
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-bold text-slate-700 uppercase tracking-wider flex items-center gap-1.5">
                        <Layers className="w-3.5 h-3.5 text-brand-blue-600" />
                        Chọn quy cách đóng gói:
                      </span>
                      <span className="text-slate-500 text-[11px]">
                        Giá tự động cập nhật theo đơn vị
                      </span>
                    </div>

                    <div className="flex flex-wrap items-center gap-2.5">
                      {availableSkus.map((sku) => {
                        const isSelected = selectedSku?.id === sku.id;
                        return (
                          <button
                            key={sku.id}
                            type="button"
                            onClick={() => handleSelectSku(sku)}
                            className={`px-3.5 py-2 rounded-xl text-xs font-bold transition-all border flex items-center gap-2 ${
                              isSelected
                                ? "bg-brand-blue-600 text-white border-brand-blue-600 shadow-xs"
                                : "bg-white text-slate-700 border-slate-200 hover:border-brand-blue-300 hover:bg-brand-blue-50/50"
                            }`}
                          >
                            <span>{sku.uom}</span>
                            <span
                              className={`text-[11px] px-1.5 py-0.5 rounded-md ${
                                isSelected
                                  ? "bg-brand-blue-700 text-white"
                                  : "bg-slate-100 text-slate-600 font-mono"
                              }`}
                            >
                              {formatVND(sku.base_price)}
                            </span>
                          </button>
                        );
                      })}
                    </div>
                  </div>
                )}

                {/* ================= BẢNG GIÁ NIÊM YẾT XÁC MINH ================= */}
                <div className="p-4 sm:p-5 rounded-2xl bg-brand-blue-50/60 border border-brand-blue-100 mb-6 flex flex-wrap items-baseline justify-between gap-3 shadow-2xs">
                  <div className="flex items-baseline gap-3">
                    <span className="text-3xl font-black text-brand-blue-700">
                      {formatVND(currentPrice)}
                    </span>
                    {product.salePrice && currentPrice === product.salePrice && (
                      <span className="text-base text-slate-400 line-through">
                        {formatVND(product.price)}
                      </span>
                    )}
                    <span className="text-xs font-semibold text-slate-600">
                      / {currentUnit}
                    </span>
                  </div>

                  <span className="text-xs text-slate-500 font-medium bg-white px-2.5 py-1 rounded-full border border-slate-200/80">
                    {product.catalogTier === "REFERENCE_ONLY"
                      ? "Giá tham khảo (Tra cứu y tế)"
                      : "Giá niêm yết (Đã gồm VAT)"}
                  </span>
                </div>

                {/* ================= THÔNG SỐ DƯỢC KHOA NHANH ================= */}
                <div className="grid grid-cols-2 gap-3 text-xs bg-slate-50 rounded-2xl p-4 border border-slate-200/80 mb-6">
                  <div>
                    <span className="text-slate-400 block font-normal mb-0.5">Hoạt chất chính:</span>
                    <span className="font-bold text-slate-800">{product.activeIngredient}</span>
                  </div>
                  <div>
                    <span className="text-slate-400 block font-normal mb-0.5">Dạng bào chế:</span>
                    <span className="font-bold text-slate-800">{product.dosageForm}</span>
                  </div>
                  <div>
                    <span className="text-slate-400 block font-normal mb-0.5">Xuất xứ / Nước SX:</span>
                    <span className="font-bold text-slate-800">{product.origin}</span>
                  </div>
                  <div>
                    <span className="text-slate-400 block font-normal mb-0.5">Nhà sản xuất:</span>
                    <span className="font-bold text-slate-800 line-clamp-1">{product.manufacturer}</span>
                  </div>
                </div>

                {/* ================= CTA HÀNH ĐỘNG DỰA TRÊN ELIGIBILITY ENGINE ================= */}
                {product.isPrescription ? (
                  /* 1. THUỐC KÊ ĐƠN (Rx) */
                  <div className="space-y-4 pt-1">
                    <div className="p-4 rounded-2xl bg-rose-50 border border-rose-200 text-xs text-rose-900 flex items-start gap-3">
                      <AlertTriangle className="w-5 h-5 text-rose-600 shrink-0 mt-0.5" />
                      <div className="leading-relaxed">
                        <p className="font-bold text-rose-800 uppercase tracking-wide mb-1">
                          Cảnh Báo Thuốc Kê Đơn (Rx)
                        </p>
                        <p>
                          Thuốc này chỉ được bán khi có đơn chỉ định hợp lệ của Bác sĩ. Vui lòng gửi toa thuốc để Dược sĩ Đại học xác thực liều lượng và hỗ trợ cấp phát đúng quy chế Dược.
                        </p>
                      </div>
                    </div>

                    <div className="flex items-center">
                      <Button
                        variant="primary"
                        size="lg"
                        className="w-full shadow-xs bg-brand-blue-600 hover:bg-brand-blue-700 text-white"
                        leftIcon={<Stethoscope className="w-5 h-5" />}
                        onClick={() => setIsRxModalOpen(true)}
                      >
                        Gửi Đơn Thuốc & Tư Vấn Dược Sĩ Trực Tuyến
                      </Button>
                    </div>

                    <button
                      type="button"
                      onClick={handleAskAssistant}
                      className="w-full py-2.5 px-4 rounded-xl border border-brand-blue-200 bg-brand-blue-50 hover:bg-brand-blue-100 text-brand-blue-700 font-bold text-xs flex items-center justify-center gap-2 transition-all shadow-2xs"
                    >
                      <Bot className="w-4 h-4 text-brand-blue-600" />
                      <span>Hỏi Trợ Lý AI Về Sản Phẩm Này</span>
                    </button>
                  </div>
                ) : product.catalogTier === "REFERENCE_ONLY" ? (
                  /* 2. SẢN PHẨM DANH MỤC THAM KHẢO / CHƯA MỞ BÁN THẬT */
                  <div className="space-y-4 pt-1">
                    <div className="p-4 rounded-2xl bg-amber-50 border border-amber-200 text-xs text-amber-900 flex items-start gap-3">
                      <Info className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
                      <div className="leading-relaxed">
                        <p className="font-bold text-amber-800 uppercase tracking-wide mb-1">
                          Danh mục tra cứu thông tin y tế tham khảo
                        </p>
                        <p>
                          {product.primaryReason ||
                            "Sản phẩm này hiện đang phục vụ mục đích tra cứu dữ liệu dược lý học. Quý khách vui lòng liên hệ Dược sĩ H4CARE để nhận tư vấn chuyên môn trước khi mua tại quầy thuốc."}
                        </p>
                      </div>
                    </div>

                    <div className="flex items-center">
                      <Button
                        variant="primary"
                        size="lg"
                        className="w-full shadow-xs bg-brand-blue-600 hover:bg-brand-blue-700 text-white"
                        leftIcon={<Stethoscope className="w-5 h-5" />}
                        onClick={() => setIsRxModalOpen(true)}
                      >
                        Gửi Câu Hỏi Cho Dược Sĩ Trực Tuyến
                      </Button>
                    </div>

                    <button
                      type="button"
                      onClick={handleAskAssistant}
                      className="w-full py-2.5 px-4 rounded-xl border border-brand-blue-200 bg-brand-blue-50 hover:bg-brand-blue-100 text-brand-blue-700 font-bold text-xs flex items-center justify-center gap-2 transition-all shadow-2xs"
                    >
                      <Bot className="w-4 h-4 text-brand-blue-600" />
                      <span>Hỏi Trợ Lý AI Về Sản Phẩm Này</span>
                    </button>
                  </div>
                ) : (availableStock <= 0 || product.canAddToCart === false || product.catalogTier === "OUT_OF_STOCK" || product.isSaleEligible === false) ? (
                  /* 3. SẢN PHẨM HẾT HÀNG HOẶC QUÁ HẠN SỬ DỤNG */
                  <div className="space-y-4 pt-1">
                    <div className="p-4 rounded-2xl bg-amber-50 border border-amber-200 text-xs text-amber-900 flex items-start gap-3">
                      <AlertCircle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
                      <div className="leading-relaxed">
                        <p className="font-bold text-amber-800 uppercase tracking-wide mb-1">
                          Sản phẩm tạm hết hàng hoặc các lô thuốc đã quá hạn
                        </p>
                        <p>
                          Hiện tại sản phẩm này đã tạm hết hàng hoặc các lô hàng trong kho đã hết hạn sử dụng theo nguyên tắc FEFO. PharmaTrust tạm ngừng tiếp nhận đặt hàng trực tuyến cho sản phẩm này để bảo đảm an toàn dược phẩm cho người sử dụng.
                        </p>
                      </div>
                    </div>

                    <div className="flex items-center">
                      <Button
                        variant="secondary"
                        size="lg"
                        disabled
                        className="w-full bg-slate-100 text-slate-400 border-slate-200 cursor-not-allowed shadow-none"
                        leftIcon={<AlertCircle className="w-5 h-5 text-slate-400" />}
                      >
                        Tạm Hết Hàng / Quá Hạn Sử Dụng
                      </Button>
                    </div>

                    {/* Nút Hỏi Trợ Lý AI Về Sản Phẩm Này */}
                    <button
                      type="button"
                      onClick={handleAskAssistant}
                      className="w-full py-2.5 px-4 rounded-xl border border-brand-blue-200 bg-brand-blue-50 hover:bg-brand-blue-100 text-brand-blue-700 font-bold text-xs flex items-center justify-center gap-2 transition-all shadow-2xs"
                    >
                      <Bot className="w-4 h-4 text-brand-blue-600" />
                      <span>Hỏi Trợ Lý AI Về Sản Phẩm Thay Thế</span>
                    </button>
                  </div>
                ) : (
                  /* 4. SẢN PHẨM ĐỦ ĐIỀU KIỆN MỞ BÁN THƯƠNG MẠI (SALE_ELIGIBLE) */
                  <div className="space-y-5 pt-1">
                    {/* Quantity Selector */}
                    <div className="flex items-center gap-4">
                      <span className="text-xs font-bold text-slate-700 uppercase tracking-wider">
                        Số lượng:
                      </span>
                      <div className="flex items-center border border-slate-200 rounded-xl bg-white shadow-2xs">
                        <button
                          onClick={() => setQuantity((q) => Math.max(1, q - 1))}
                          className="p-2 text-slate-500 hover:text-slate-800 hover:bg-slate-50 rounded-l-xl transition-colors"
                        >
                          <Minus className="w-4 h-4" />
                        </button>
                        <span className="w-12 text-center text-sm font-bold text-slate-900">
                          {quantity}
                        </span>
                        <button
                          onClick={() => setQuantity((q) => Math.min(availableStock || 99, q + 1))}
                          className="p-2 text-slate-500 hover:text-slate-800 hover:bg-slate-50 rounded-r-xl transition-colors"
                        >
                          <Plus className="w-4 h-4" />
                        </button>
                      </div>
                      <span className="text-xs text-slate-400">
                        (Còn {availableStock} {currentUnit})
                      </span>
                    </div>

                    {/* Action Buttons: Add to Cart & Buy Now */}
                    <div className="flex flex-col sm:flex-row items-center gap-3">
                      <Button
                        variant="secondary"
                        size="lg"
                        className="w-full sm:flex-1 font-bold text-brand-blue-700 bg-brand-blue-50 hover:bg-brand-blue-100 border-brand-blue-200"
                        leftIcon={<ShoppingBag className="w-5 h-5" />}
                        onClick={() => handleAddToCart(false)}
                      >
                        Thêm Vào Giỏ Hàng
                      </Button>

                      <Button
                        variant="primary"
                        size="lg"
                        className="w-full sm:flex-1 font-bold shadow-md hover:shadow-lg bg-brand-blue-600 hover:bg-brand-blue-700 text-white transition-all"
                        onClick={() => handleAddToCart(true)}
                      >
                        Mua Ngay
                      </Button>
                    </div>

                    {/* Nút Hỏi Trợ Lý AI Về Sản Phẩm Này */}
                    <button
                      type="button"
                      onClick={handleAskAssistant}
                      className="w-full py-2.5 px-4 rounded-xl border border-brand-blue-200 bg-brand-blue-50 hover:bg-brand-blue-100 text-brand-blue-700 font-bold text-xs flex items-center justify-center gap-2 transition-all shadow-2xs"
                    >
                      <Bot className="w-4 h-4 text-brand-blue-600" />
                      <span>Hỏi Trợ Lý AI Về Sản Phẩm Này</span>
                    </button>

                    {/* Delivery & Payment Assurance Badge */}
                    <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200/80 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2.5 text-xs text-slate-600">
                      <div className="flex items-center gap-2">
                        <MapPin className="w-4 h-4 text-emerald-600 shrink-0" />
                        <span>Bản đồ định vị GPS & Tìm kho GPP gần nhất</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <QrCode className="w-4 h-4 text-brand-blue-600 shrink-0" />
                        <span>Cổng thanh toán payOS (VietQR 24/7) & COD</span>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* ================= KHU VỰC RIÊNG: MINH BẠCH THÔNG TIN SẢN PHẨM H4CARE ================= */}
        <section aria-label="Minh bạch thông tin dược phẩm">
          <ProductTransparencyCard
            transparency={product.transparency}
            isPrescription={product.isPrescription}
            registrationNumber={product.sku}
            manufacturer={product.manufacturer}
            publishMode={product.catalogTier}
            isSaleEligible={product.isSaleEligible}
          />
        </section>

        {/* ================= TABS THÔNG TIN DƯỢC KHOA CHUYÊN SÂU ================= */}
        <section className="bg-white rounded-3xl border border-slate-200/90 p-6 md:p-8 shadow-xs space-y-6">
          <div className="border-b border-slate-200 pb-3 flex flex-wrap gap-2 sm:gap-3">
            {[
              { id: "overview", label: "Tổng quan & Chỉ định", icon: Pill },
              { id: "ingredients", label: "Thành phần & Hoạt chất", icon: FileText },
              { id: "usage", label: "Cách dùng & Liều lượng", icon: Clock },
              { id: "precautions", label: "Chống chỉ định & Thận trọng", icon: AlertCircle },
              { id: "storage", label: "Bảo quản & Xuất xứ", icon: ShieldCheck },
            ].map((tab) => {
              const Icon = tab.icon;
              const isActive = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id as any)}
                  className={`px-4 py-2.5 rounded-xl text-xs font-bold transition-all flex items-center gap-2 ${
                    isActive
                      ? "bg-brand-blue-600 text-white shadow-xs"
                      : "text-slate-600 hover:text-slate-900 hover:bg-slate-100"
                  }`}
                >
                  <Icon className="w-4 h-4" />
                  <span>{tab.label}</span>
                </button>
              );
            })}
          </div>

          {/* Tab 1: Tổng quan */}
          {activeTab === "overview" && (
            <div className="space-y-4 text-xs sm:text-sm text-slate-700 leading-relaxed animate-in fade-in duration-150">
              <h3 className="text-base font-bold text-slate-900">Mô Tả Sản Phẩm</h3>
              <p>{product.description}</p>

              <h4 className="text-sm font-bold text-slate-900 pt-2">Chỉ Định Điều Trị</h4>
              <p>{product.indications}</p>
            </div>
          )}

          {/* Tab 2: Thành phần */}
          {activeTab === "ingredients" && (
            <div className="space-y-4 text-xs sm:text-sm text-slate-700 leading-relaxed animate-in fade-in duration-150">
              <h3 className="text-base font-bold text-slate-900">Thành Phần Hoạt Chất</h3>
              <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200 space-y-2">
                <p className="font-semibold text-slate-900">{product.activeIngredient}</p>
                <p className="text-slate-500 text-xs">
                  Dạng bào chế: <span className="font-medium text-slate-700">{product.dosageForm}</span>
                </p>
                <p className="text-slate-500 text-xs">
                  Quy cách đóng gói: <span className="font-medium text-slate-700">{product.packaging}</span>
                </p>
              </div>
            </div>
          )}

          {/* Tab 3: Cách dùng */}
          {activeTab === "usage" && (
            <div className="space-y-4 text-xs sm:text-sm text-slate-700 leading-relaxed animate-in fade-in duration-150">
              <h3 className="text-base font-bold text-slate-900">Hướng Dẫn Sử Dụng & Liều Lượng</h3>
              <p>{product.usage}</p>
              <div className="p-3.5 rounded-xl bg-blue-50 border border-blue-200 text-xs text-blue-900">
                Lưu ý: Đọc kỹ hướng dẫn sử dụng trong hộp thuốc. Không tự ý tăng liều khi chưa có chỉ định của Bác sĩ hoặc Dược sĩ.
              </div>
            </div>
          )}

          {/* Tab 4: Chống chỉ định & Thận trọng */}
          {activeTab === "precautions" && (
            <div className="space-y-4 text-xs sm:text-sm text-slate-700 leading-relaxed animate-in fade-in duration-150">
              <h3 className="text-base font-bold text-slate-900">Chống Chỉ Định</h3>
              <p>{product.contraindications}</p>

              <h4 className="text-sm font-bold text-slate-900 pt-2">Tác Dụng Không Mong Muốn</h4>
              <p>{product.sideEffects}</p>

              <h4 className="text-sm font-bold text-slate-900 pt-2">Thận Trọng Khi Sử Dụng</h4>
              <p>{product.precautions}</p>
            </div>
          )}

          {/* Tab 5: Bảo quản */}
          {activeTab === "storage" && (
            <div className="space-y-4 text-xs sm:text-sm text-slate-700 leading-relaxed animate-in fade-in duration-150">
              <h3 className="text-base font-bold text-slate-900">Điều Kiện Bảo Quản</h3>
              <p>{product.storage}</p>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2 text-xs">
                <div className="p-3 bg-slate-50 rounded-xl border border-slate-200">
                  <span className="text-slate-400 block mb-0.5">Xuất xứ:</span>
                  <span className="font-bold text-slate-900">{product.origin}</span>
                </div>
                <div className="p-3 bg-slate-50 rounded-xl border border-slate-200">
                  <span className="text-slate-400 block mb-0.5">Nhà sản xuất:</span>
                  <span className="font-bold text-slate-900">{product.manufacturer}</span>
                </div>
              </div>
            </div>
          )}
        </section>

        {/* ================= ĐÁNH GIÁ CÓ DỮ LIỆU THẬT ================= */}
        <section aria-label="Đánh giá khách hàng">
          <ProductReviewsSection
            productId={product.dbId || 1}
            productName={product.name}
            defaultRating={product.rating ?? 0}
            defaultReviewCount={product.reviewCount ?? 0}
          />
        </section>

        {/* ================= SẢN PHẨM CÙNG DANH MỤC HỢP LỆ ================= */}
        {relatedProducts.length > 0 && (
          <section className="space-y-5" aria-label="Sản phẩm liên quan">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-lg font-bold text-slate-900">Sản Phẩm Cùng Danh Mục</h3>
                <p className="text-xs text-slate-500">
                  Các sản phẩm thuộc nhóm {product.categoryName} được người dùng tin chọn
                </p>
              </div>

              <Link
                href={`/category/${product.category}`}
                className="text-xs font-bold text-brand-blue-600 hover:underline flex items-center gap-1"
              >
                <span>Xem tất cả</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </Link>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              {relatedProducts.map((relProduct) => (
                <ProductCard
                  key={relProduct.id}
                  product={relProduct}
                  onQuickView={(p) => setQuickViewProduct(p)}
                  onOpenRxConsult={() => setIsRxModalOpen(true)}
                />
              ))}
            </div>
          </section>
        )}
      </main>

      {/* ================= TOAST NOTIFICATIONS ================= */}
      {showAddedToast && (
        <div className="fixed bottom-6 right-6 z-50 max-w-md w-[calc(100vw-3rem)] bg-white border border-emerald-300 rounded-2xl shadow-2xl p-4 flex items-center justify-between gap-3 animate-in fade-in slide-in-from-bottom-5 duration-200">
          <div className="flex items-center gap-3 min-w-0">
            <div className="w-10 h-10 rounded-xl bg-emerald-100 text-emerald-700 flex items-center justify-center shrink-0">
              <CheckCircle2 className="w-5 h-5" />
            </div>
            <div className="min-w-0">
              <p className="text-xs font-bold text-slate-900 truncate">
                Đã thêm vào giỏ hàng thành công!
              </p>
              <p className="text-[11px] text-slate-500 truncate">
                {product.name} ({currentUnit} x{quantity})
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <Button
              variant="primary"
              size="sm"
              onClick={() => router.push("/cart")}
              className="text-xs font-bold bg-brand-blue-600 hover:bg-brand-blue-700 text-white shadow-xs"
            >
              Xem Giỏ Hàng
            </Button>
            <button
              onClick={() => setShowAddedToast(false)}
              className="p-1 rounded-lg hover:bg-slate-100 text-slate-400 hover:text-slate-600 transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      {warningToast && (
        <div className="fixed bottom-6 right-6 z-50 max-w-md w-[calc(100vw-3rem)] bg-white border border-amber-300 rounded-2xl shadow-2xl p-4 flex items-center justify-between gap-3 animate-in fade-in slide-in-from-bottom-5 duration-200">
          <div className="flex items-center gap-3 min-w-0">
            <div className="w-10 h-10 rounded-xl bg-amber-100 text-amber-800 flex items-center justify-center shrink-0">
              <AlertCircle className="w-5 h-5" />
            </div>
            <div className="min-w-0">
              <p className="text-xs font-bold text-slate-900">Thông Báo Điều Kiện Mở Bán</p>
              <p className="text-[11px] text-slate-600 leading-snug">{warningToast}</p>
            </div>
          </div>
          <button
            onClick={() => setWarningToast(null)}
            className="p-1 rounded-lg hover:bg-slate-100 text-slate-400 hover:text-slate-600 transition-colors shrink-0"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* ================= MODALS ================= */}
      <RxConsultModal
        product={product}
        isOpen={isRxModalOpen}
        onClose={() => setIsRxModalOpen(false)}
      />

      <ProductQuickViewModal
        product={quickViewProduct}
        isOpen={!!quickViewProduct}
        onClose={() => setQuickViewProduct(null)}
        onOpenRxConsult={() => setIsRxModalOpen(true)}
      />

      {/* Footer */}
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
