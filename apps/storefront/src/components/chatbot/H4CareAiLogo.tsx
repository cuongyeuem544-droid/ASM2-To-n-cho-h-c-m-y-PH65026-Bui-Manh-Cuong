import React from "react";

interface H4CareAiLogoProps {
  size?: "xs" | "sm" | "md" | "lg" | "xl";
  showBadge?: boolean;
  className?: string;
}

const SIZE_MAP = {
  xs: "w-4 h-4",
  sm: "w-6 h-6",
  md: "w-8 h-8",
  lg: "w-10 h-10",
  xl: "w-14 h-14",
};

/**
 * Logo chính thức của Trợ Lý Trí Tuệ Nhân Tạo H4CARE (H4CARE AI Assistant).
 * Thiết kế độc quyền:
 * - Khiên bảo vệ y khoa (Medical Shield) cách điệu hình giọt ngọc / viên nang.
 * - Chữ thập y tế chuẩn GPP phát sáng ở tâm điểm.
 * - Mạch nơ-ron AI (Neural Network Nodes & Synapses) tượng trưng cho khả năng tra cứu dược lý học sâu.
 * - Gradient màu sắc nhận diện H4CARE: Brand Blue (xanh dương y tế), Cyan (công nghệ hiện đại), Emerald (dược thảo an toàn).
 */
export const H4CareAiLogo: React.FC<H4CareAiLogoProps> = ({
  size = "md",
  showBadge = false,
  className = "",
}) => {
  const dimensionClass = SIZE_MAP[size];

  return (
    <div className={`relative inline-flex items-center justify-center select-none ${className}`}>
      <svg
        className={`${dimensionClass} shrink-0 drop-shadow-xs transition-transform duration-200`}
        viewBox="0 0 64 64"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        aria-label="Logo Trợ lý AI H4CARE"
      >
        <defs>
          {/* Nền gradient chính của biểu tượng */}
          <linearGradient id="h4ai_bg_grad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#0284c7" />   {/* Sky Blue 600 */}
            <stop offset="50%" stopColor="#0369a1" />  {/* Sky Blue 700 */}
            <stop offset="100%" stopColor="#0f766e" /> {/* Teal 700 */}
          </linearGradient>

          {/* Gradient sáng nổi cho chi tiết công nghệ */}
          <linearGradient id="h4ai_cyan_glow" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#38bdf8" />   {/* Light Cyan */}
            <stop offset="100%" stopColor="#34d399" />  {/* Light Emerald */}
          </linearGradient>

          {/* Vầng hào quang bảo vệ */}
          <radialGradient id="h4ai_core_glow" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="#38bdf8" stopOpacity="0.8" />
            <stop offset="100%" stopColor="#0284c7" stopOpacity="0" />
          </radialGradient>
        </defs>

        {/* Khung khiên / Hexagon bo tròn cách điệu */}
        <rect
          x="3"
          y="3"
          width="58"
          height="58"
          rx="18"
          fill="url(#h4ai_bg_grad)"
          stroke="#e0f2fe"
          strokeWidth="2.5"
        />

        {/* Vầng hào quang trung tâm */}
        <circle cx="32" cy="32" r="22" fill="url(#h4ai_core_glow)" />

        {/* Mạch nơ-ron AI (Neural Network Grid & Nodes) */}
        <path
          d="M16 22 L26 32 M16 42 L26 32 M48 22 L38 32 M48 42 L38 32 M32 14 L32 24 M32 50 L32 40"
          stroke="url(#h4ai_cyan_glow)"
          strokeWidth="1.8"
          strokeLinecap="round"
          strokeDasharray="2 3"
        />

        {/* Các nốt mạng AI phát sáng */}
        <circle cx="16" cy="22" r="2.8" fill="#38bdf8" stroke="#ffffff" strokeWidth="1" />
        <circle cx="16" cy="42" r="2.8" fill="#34d399" stroke="#ffffff" strokeWidth="1" />
        <circle cx="48" cy="22" r="2.8" fill="#38bdf8" stroke="#ffffff" strokeWidth="1" />
        <circle cx="48" cy="42" r="2.8" fill="#34d399" stroke="#ffffff" strokeWidth="1" />
        <circle cx="32" cy="14" r="2.8" fill="#38bdf8" stroke="#ffffff" strokeWidth="1" />
        <circle cx="32" cy="50" r="2.8" fill="#34d399" stroke="#ffffff" strokeWidth="1" />

        {/* Chữ Thập Y Tế Tâm Điểm (Pharma Cross Core) */}
        {/* Nhánh dọc */}
        <rect
          x="28.5"
          y="23"
          width="7"
          height="18"
          rx="3.5"
          fill="#ffffff"
        />
        {/* Nhánh ngang */}
        <rect
          x="23"
          y="28.5"
          width="18"
          height="7"
          rx="3.5"
          fill="#ffffff"
        />

        {/* Điểm sáng AI Sparkle ở trung tâm chữ thập */}
        <circle cx="32" cy="32" r="2" fill="#0284c7" />
        <path
          d="M32 29.5 L32.6 31.4 L34.5 32 L32.6 32.6 L32 34.5 L31.4 32.6 L29.5 32 L31.4 31.4 Z"
          fill="#38bdf8"
        />
      </svg>

      {/* Huy hiệu AI nhận diện nhanh */}
      {showBadge && (
        <span className="absolute -bottom-1 -right-1.5 px-1 py-0.2 bg-gradient-to-r from-sky-500 to-teal-500 text-white text-[9px] font-black tracking-wider rounded-md border border-white shadow-xs">
          AI
        </span>
      )}
    </div>
  );
};
