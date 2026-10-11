"use client";

import React from "react";

interface SmoothScrollProps {
  children: React.ReactNode;
}

/**
 * SmoothScroll Provider
 * Đã vô hiệu hóa bộ hãm quán tính nhân tạo (Lenis) để trả lại tốc độ cuộn lướt nhạy tức thì 100%
 * theo chuẩn phần cứng chuột và màn hình của trình duyệt (Zero latency scroll).
 */
export const SmoothScroll: React.FC<SmoothScrollProps> = ({ children }) => {
  return <>{children}</>;
};

