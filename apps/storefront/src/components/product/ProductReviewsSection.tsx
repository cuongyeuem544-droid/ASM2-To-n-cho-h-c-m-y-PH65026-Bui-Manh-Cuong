"use client";

import React, { useState, useEffect } from "react";
import { Star, ShieldCheck, CheckCircle2, MessageSquare, AlertCircle, Send, Check } from "lucide-react";
import { Button } from "@/components/ui/Button";

interface ReviewItem {
  id: number;
  canonical_product_id: number;
  customer_name: string;
  rating: number;
  comment: string;
  is_verified_purchase: boolean;
  is_approved: boolean;
  created_at: string;
  order_code?: string | null;
}

interface ReviewSummary {
  average_rating: number;
  total_reviews: number;
  verified_reviews_count: number;
  rating_distribution: Record<number, number>;
  reviews: ReviewItem[];
}

interface ProductReviewsSectionProps {
  productId: number;
  productName: string;
  defaultRating?: number;
  defaultReviewCount?: number;
}

export function ProductReviewsSection({
  productId,
  productName,
  defaultRating = 0,
  defaultReviewCount = 0,
}: ProductReviewsSectionProps) {
  const [data, setData] = useState<ReviewSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);

  // Form states
  const [rating, setRating] = useState(5);
  const [customerName, setCustomerName] = useState("");
  const [orderCode, setOrderCode] = useState("");
  const [comment, setComment] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitSuccess, setSubmitSuccess] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  const fetchReviews = async () => {
    try {
      setLoading(true);
      const res = await fetch(`/api/v1/store/products/${productId}/reviews`);
      if (res.ok) {
        const json = await res.json();
        setData(json);
      }
    } catch (err) {
      console.warn("Could not fetch reviews:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (productId) {
      fetchReviews();
    }
  }, [productId]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage("");

    if (!customerName.trim()) {
      setErrorMessage("Vui lòng nhập họ và tên của bạn");
      return;
    }
    if (comment.trim().length < 5) {
      setErrorMessage("Nội dung đánh giá cần ít nhất 5 ký tự");
      return;
    }

    try {
      setSubmitting(true);
      const res = await fetch(`/api/v1/store/products/${productId}/reviews`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          rating,
          customer_name: customerName.trim(),
          comment: comment.trim(),
          order_code: orderCode.trim() || undefined,
        }),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Không thể gửi đánh giá");
      }

      setSubmitSuccess(true);
      setComment("");
      setOrderCode("");
      await fetchReviews();
      setTimeout(() => {
        setSubmitSuccess(false);
        setShowForm(false);
      }, 2500);
    } catch (err: any) {
      setErrorMessage(err.message || "Đã xảy ra lỗi khi gửi đánh giá");
    } finally {
      setSubmitting(false);
    }
  };

  const avgRating = data ? (data.total_reviews > 0 ? data.average_rating : 0.0) : (defaultRating ?? 0);
  const totalReviews = data?.total_reviews ?? (defaultReviewCount ?? 0);
  const verifiedCount = data?.verified_reviews_count ?? 0;
  const distribution = data?.rating_distribution || { 5: 0, 4: 0, 3: 0, 2: 0, 1: 0 };

  return (
    <div className="bg-white rounded-3xl p-6 sm:p-8 border border-slate-200/80 shadow-sm mt-8">
      {/* Section Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-6 border-b border-slate-100 gap-4">
        <div>
          <div className="flex items-center gap-2 text-xs font-bold text-brand-blue-700 uppercase tracking-wider mb-1">
            <ShieldCheck className="w-4 h-4 text-emerald-600" />
            <span>Phản Hồi & Trải Nghiệm Khách Hàng</span>
          </div>
          <h3 className="text-xl sm:text-2xl font-black text-slate-900 tracking-tight">
            Đánh Giá Sản Phẩm Xác Thực
          </h3>
          <p className="text-xs sm:text-sm text-slate-500 mt-0.5">
            100% nhận xét từ người mua thực tế, có kiểm tra mã đơn hàng và chứng từ xuất kho.
          </p>
        </div>

        <Button
          variant="primary"
          size="sm"
          onClick={() => setShowForm(!showForm)}
          leftIcon={<MessageSquare className="w-4 h-4" />}
          className="bg-brand-blue-600 hover:bg-brand-blue-700 text-white shrink-0 self-start sm:self-auto"
        >
          {showForm ? "Đóng biểu mẫu" : "Viết đánh giá của bạn"}
        </Button>
      </div>

      {/* Review Submission Form Modal / Box */}
      {showForm && (
        <form
          onSubmit={handleSubmit}
          className="my-6 p-6 rounded-2xl bg-brand-blue-50/50 border border-brand-blue-100/80 animate-in fade-in slide-in-from-top-4 duration-200"
        >
          <h4 className="text-sm font-bold text-brand-blue-950 mb-3 flex items-center gap-2">
            <span>Chia sẻ trải nghiệm sử dụng {productName}</span>
          </h4>

          {errorMessage && (
            <div className="mb-4 p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-xs flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{errorMessage}</span>
            </div>
          )}

          {submitSuccess && (
            <div className="mb-4 p-3 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-700 text-xs flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-600" />
              <span>Cảm ơn bạn! Đánh giá đã được ghi nhận và xác thực thành công.</span>
            </div>
          )}

          {/* Rating stars picker */}
          <div className="mb-4">
            <label className="block text-xs font-bold text-slate-700 mb-1.5">
              Đánh giá mức độ hài lòng:
            </label>
            <div className="flex items-center gap-1.5">
              {[1, 2, 3, 4, 5].map((star) => (
                <button
                  type="button"
                  key={star}
                  onClick={() => setRating(star)}
                  className="p-1 text-amber-400 hover:scale-110 transition-transform"
                >
                  <Star
                    className={`w-6 h-6 ${
                      star <= rating ? "fill-amber-400 text-amber-400" : "text-slate-300"
                    }`}
                  />
                </button>
              ))}
              <span className="text-xs font-bold text-amber-700 ml-2">
                {rating === 5 && "Cực kỳ hài lòng"}
                {rating === 4 && "Hài lòng"}
                {rating === 3 && "Bình thường"}
                {rating === 2 && "Chưa hài lòng"}
                {rating === 1 && "Rất thất vọng"}
              </span>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4">
            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1">
                Họ và tên <span className="text-rose-500">*</span>
              </label>
              <input
                type="text"
                value={customerName}
                onChange={(e) => setCustomerName(e.target.value)}
                placeholder="VD: Nguyễn Văn An"
                className="w-full text-xs px-3.5 py-2.5 rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-brand-blue-500 bg-white"
                required
              />
            </div>
            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1">
                Mã đơn hàng (tùy chọn)
              </label>
              <input
                type="text"
                value={orderCode}
                onChange={(e) => setOrderCode(e.target.value)}
                placeholder="VD: PT-260930-XXXX"
                className="w-full text-xs px-3.5 py-2.5 rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-brand-blue-500 bg-white"
              />
              <span className="text-[11px] text-slate-500 mt-1 block">
                Nhập mã đơn để nhận huy hiệu <strong>"Đã Mua Hàng Chính Hãng"</strong>.
              </span>
            </div>
          </div>

          <div className="mb-4">
            <label className="block text-xs font-bold text-slate-700 mb-1">
              Nhận xét chi tiết <span className="text-rose-500">*</span>
            </label>
            <textarea
              rows={3}
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              placeholder="Chia sẻ về hiệu quả thuốc, hạn dùng, thời gian giao hàng hoặc đóng gói chuẩn GPP..."
              className="w-full text-xs p-3.5 rounded-xl border border-slate-300 focus:outline-none focus:ring-2 focus:ring-brand-blue-500 bg-white"
              required
            />
          </div>

          <div className="flex justify-end gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setShowForm(false)}
            >
              Hủy
            </Button>
            <Button
              type="submit"
              variant="primary"
              size="sm"
              disabled={submitting}
              leftIcon={<Send className="w-3.5 h-3.5" />}
              className="bg-brand-blue-600 hover:bg-brand-blue-700 text-white"
            >
              {submitting ? "Đang gửi..." : "Gửi Đánh Giá"}
            </Button>
          </div>
        </form>
      )}

      {/* Summary Score & Distribution Breakdown */}
      <div className="grid grid-cols-1 md:grid-cols-12 gap-6 my-6 p-6 rounded-2xl bg-slate-50/70 border border-slate-100">
        {/* Left: Overall Score */}
        <div className="md:col-span-4 flex flex-col items-center justify-center text-center p-4 border-b md:border-b-0 md:border-r border-slate-200/80">
          <div className="text-4xl sm:text-5xl font-black text-slate-900 tracking-tight flex items-baseline gap-1">
            <span>{avgRating.toFixed(1)}</span>
            <span className="text-base text-slate-400 font-normal">/ 5</span>
          </div>
          <div className="flex items-center gap-1 my-2">
            {[1, 2, 3, 4, 5].map((star) => (
              <Star
                key={star}
                className={`w-5 h-5 ${
                  totalReviews > 0 && star <= Math.round(avgRating)
                    ? "fill-amber-400 text-amber-400"
                    : "text-slate-200"
                }`}
              />
            ))}
          </div>
          <p className="text-xs text-slate-500 font-medium">
            Dựa trên {totalReviews} lượt đánh giá thực tế
          </p>
          {verifiedCount > 0 && (
            <div className="mt-2.5 inline-flex items-center gap-1 text-[11px] font-bold text-emerald-800 bg-emerald-50 px-2.5 py-1 rounded-full border border-emerald-200">
              <Check className="w-3 h-3 text-emerald-600" />
              <span>{verifiedCount} người mua đã xác thực đơn</span>
            </div>
          )}
        </div>

        {/* Right: Star Distribution Bars */}
        <div className="md:col-span-8 flex flex-col justify-center gap-2">
          {[5, 4, 3, 2, 1].map((star) => {
            const count = distribution[star] || 0;
            const pct = totalReviews > 0 ? Math.round((count / totalReviews) * 100) : 0;
            return (
              <div key={star} className="flex items-center gap-3 text-xs">
                <div className="flex items-center gap-1 w-14 shrink-0 font-semibold text-slate-700">
                  <span>{star}</span>
                  <Star className="w-3.5 h-3.5 fill-amber-400 text-amber-400" />
                </div>
                <div className="flex-1 h-2 rounded-full bg-slate-200 overflow-hidden">
                  <div
                    className="h-full bg-amber-400 rounded-full transition-all duration-500"
                    style={{ width: `${pct}%` }}
                  />
                </div>
                <span className="w-12 text-right text-[11px] font-bold text-slate-500">
                  {count} ({pct}%)
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Reviews List */}
      <div className="space-y-4">
        {data && data.reviews.length > 0 ? (
          data.reviews.map((rev) => (
            <div
              key={rev.id}
              className="p-5 rounded-2xl bg-white border border-slate-100 hover:border-slate-200 shadow-xs transition-all space-y-2.5"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-3">
                  <div className="w-9 h-9 rounded-full bg-brand-blue-100 text-brand-blue-800 font-bold flex items-center justify-center text-sm">
                    {rev.customer_name ? rev.customer_name[0].toUpperCase() : "K"}
                  </div>
                  <div>
                    <h5 className="text-xs sm:text-sm font-bold text-slate-900 flex items-center gap-2">
                      <span>{rev.customer_name}</span>
                      {rev.is_verified_purchase && (
                        <span className="inline-flex items-center gap-1 text-[10px] font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full border border-emerald-200">
                          <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                          <span>Đã mua chính hãng</span>
                        </span>
                      )}
                    </h5>
                    <div className="flex items-center gap-2 mt-0.5">
                      <div className="flex items-center gap-0.5">
                        {[1, 2, 3, 4, 5].map((s) => (
                          <Star
                            key={s}
                            className={`w-3.5 h-3.5 ${
                              s <= rev.rating
                                ? "fill-amber-400 text-amber-400"
                                : "text-slate-200"
                            }`}
                          />
                        ))}
                      </div>
                      <span className="text-[11px] text-slate-400">• {rev.created_at}</span>
                      {rev.order_code && (
                        <span className="text-[10px] text-slate-400">
                          (Đơn #{rev.order_code})
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              </div>

              <p className="text-xs sm:text-sm text-slate-700 leading-relaxed pl-12">
                {rev.comment}
              </p>
            </div>
          ))
        ) : (
          <div className="text-center py-10 bg-slate-50/50 rounded-2xl border border-dashed border-slate-200">
            <MessageSquare className="w-8 h-8 text-slate-300 mx-auto mb-2" />
            <p className="text-xs sm:text-sm font-bold text-slate-600">
              Chưa có đánh giá nào cho sản phẩm này
            </p>
            <p className="text-xs text-slate-400 mt-1">
              Hãy là người đầu tiên chia sẻ cảm nhận sau khi sử dụng thuốc.
            </p>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowForm(true)}
              className="mt-3 text-xs"
            >
              Viết đánh giá ngay
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
