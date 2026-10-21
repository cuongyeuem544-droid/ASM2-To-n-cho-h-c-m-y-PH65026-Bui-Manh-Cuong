/** @type {import('next').NextConfig} */
const isProduction =
  process.env.NODE_ENV === "production" ||
  process.env.VERCEL === "1" ||
  Boolean(process.env.VERCEL_ENV);

let rawBackendUrl =
  process.env.INTERNAL_API_URL ||
  process.env.NEXT_PUBLIC_API_URL;

if (!rawBackendUrl) {
  if (isProduction) {
    console.warn(
      "[H4CARE] CẢNH BÁO CẤU HÌNH: Thiếu biến môi trường INTERNAL_API_URL trên Vercel. " +
      "Tự động trỏ destination của /api/v1/:path* về Backend Render Staging: https://h4care-api-staging.onrender.com. " +
      "Vui lòng cấu hình INTERNAL_API_URL=https://h4care-api-staging.onrender.com trên Vercel Dashboard!"
    );
    rawBackendUrl = "https://h4care-api-staging.onrender.com";
  } else {
    rawBackendUrl = "http://localhost:8000";
  }
}

const backendUrl = rawBackendUrl.replace(/\/+$/, "");

const nextConfig = {
  reactStrictMode: true,
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "**" },
      { protocol: "http", hostname: "**" },
    ],
  },
  async rewrites() {
    return [
      {
        source: "/api/v1/:path*",
        destination: `${backendUrl}/api/v1/:path*`,
      },
      {
        source: "/storage/:path*",
        destination: `${backendUrl}/storage/:path*`,
      },
    ];
  },
};

export default nextConfig;
