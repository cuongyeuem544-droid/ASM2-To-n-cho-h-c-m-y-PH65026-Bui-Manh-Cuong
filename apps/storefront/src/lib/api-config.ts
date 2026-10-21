/**
 * H4CARE Storefront API Configuration
 *
 * Chuẩn hóa URL gọi API thống nhất cho toàn bộ Storefront:
 * 1. Trên trình duyệt (Client-side):
 *    - Sử dụng đường dẫn tương đối rỗng "" (Same-Origin).
 *    - Mọi request `/api/v1/...` sẽ được gửi về chính domain Storefront Vercel.
 *    - Next.js Rewrites trong next.config.mjs đóng vai trò reverse proxy chuyển tiếp
 *      sang Render Backend. Điều này LOẠI BỎ TRIỆT ĐỂ lỗi CORS và không bắt trình duyệt
 *      người dùng phải biết URL Backend thật hoặc bị phụ thuộc vào localhost:8000.
 *
 * 2. Trên máy chủ (Server-side / Route Handlers):
 *    - Sử dụng INTERNAL_API_URL hoặc NEXT_PUBLIC_API_URL.
 *    - Nếu thiếu trên môi trường Production/Staging, tự động fallback an toàn về
 *      https://h4care-api-staging.onrender.com thay vì localhost.
 */

export const getClientApiBase = (): string => {
  if (typeof window !== "undefined") {
    // Trình duyệt người dùng: Sử dụng đường dẫn tương đối "" để Next.js rewrite proxy,
    // trừ khi có NEXT_PUBLIC_API_URL được cấu hình tường minh
    return process.env.NEXT_PUBLIC_API_URL ? process.env.NEXT_PUBLIC_API_URL.replace(/\/+$/, "") : "";
  }
  return getServerApiBase();
};

export const getServerApiBase = (): string => {
  const isProduction =
    process.env.NODE_ENV === "production" ||
    process.env.VERCEL === "1" ||
    Boolean(process.env.VERCEL_ENV);

  const url =
    process.env.INTERNAL_API_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    (isProduction ? "https://h4care-api-staging.onrender.com" : "http://localhost:8000");

  return url.replace(/\/+$/, "");
};

export const API_BASE = getClientApiBase();
