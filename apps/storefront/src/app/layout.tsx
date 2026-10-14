import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { SmoothScroll } from "@/components/providers/SmoothScroll";
import { AuthProvider } from "@/lib/auth/auth-context";
import { ChatbotWidget } from "@/components/chatbot/ChatbotWidget";

const inter = Inter({
  subsets: ["latin", "vietnamese"],
  variable: "--font-sans",
  display: "swap",
});

export const metadata: Metadata = {
  title: "H4CARE | Hệ Thống Nhà Thuốc Trực Tuyến Chuẩn GPP 2026",
  description:
    "H4CARE - Đồ án sinh viên FPT Polytechnic. Hệ thống thương mại điện tử dược phẩm cao cấp, tra cứu và mua thuốc trực tuyến an toàn, tư vấn 24/7 cùng Dược sĩ.",
  keywords: [
    "H4CARE",
    "nhà thuốc trực tuyến",
    "thuốc chính hãng",
    "dược phẩm chuẩn GPP",
    "FPT Polytechnic",
  ],
  authors: [
    { name: "Hùng" },
    { name: "Đức Anh" },
    { name: "Hoàn" },
    { name: "Cường" },
  ],
  icons: {
    icon: "/favicon.svg",
  },
};

export const viewport: Viewport = {
  themeColor: "#0052cc",
  width: "device-width",
  initialScale: 1,
  maximumScale: 5,
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="vi" className={inter.variable}>
      <body className="font-sans min-h-screen flex flex-col bg-white text-slate-900 antialiased selection:bg-brand-cyan-100 selection:text-brand-blue-900">
        <AuthProvider>
          <SmoothScroll>
            {children}
            <ChatbotWidget />
          </SmoothScroll>
        </AuthProvider>
      </body>
    </html>
  );
}
