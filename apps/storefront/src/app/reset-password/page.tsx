"use client";

import React, { useState, useEffect, Suspense, useCallback } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { motion, AnimatePresence, useReducedMotion } from "framer-motion";
import { H4CareLogo } from "@/components/branding/H4CareLogo";
import { SpatialLoginBackground } from "@/components/auth/SpatialLoginBackground";
import { LiquidMetalButton } from "@/components/auth/LiquidMetalButton";
import {
  ArrowLeft,
  Lock,
  Eye,
  EyeOff,
  ShieldCheck,
  AlertCircle,
  CheckCircle2,
  KeyRound,
} from "lucide-react";

/**
 * H4CARE Bespoke Reset Password Experience
 * Harmonized with the Oceanic Light Sea Blue Spatial Theme & Liquid Metal Motion
 */
function ResetPasswordContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const target = searchParams.get("target") || "";
  const resetToken = searchParams.get("token") || target;
  const shouldReduceMotion = useReducedMotion();

  const [password, setPassword] = useState<string>("");
  const [confirmPassword, setConfirmPassword] = useState<string>("");
  const [showPassword, setShowPassword] = useState<boolean>(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState<boolean>(false);
  const [focusedField, setFocusedField] = useState<string | null>(null);

  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [isSuccess, setIsSuccess] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Mouse Parallax (Desktop only)
  const [mouseParallax, setMouseParallax] = useState({ x: 0, y: 0 });
  const [isMobile, setIsMobile] = useState<boolean>(false);

  useEffect(() => {
    const checkMobile = () => {
      setIsMobile(window.innerWidth < 768 || window.matchMedia("(hover: none)").matches);
    };
    checkMobile();
    window.addEventListener("resize", checkMobile);
    return () => window.removeEventListener("resize", checkMobile);
  }, []);

  const handleMouseMove = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      if (isMobile || shouldReduceMotion) return;
      const { innerWidth, innerHeight } = window;
      const normX = (e.clientX / innerWidth - 0.5) * 2;
      const normY = (e.clientY / innerHeight - 0.5) * 2;
      setMouseParallax({ x: normX, y: normY });
    },
    [isMobile, shouldReduceMotion]
  );

  const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);

    if (!resetToken) {
      setErrorMessage("Thiếu mã đặt lại mật khẩu (Token). Vui lòng yêu cầu cấp lại mã OTP.");
      return;
    }
    if (password.length < 6) {
      setErrorMessage("Mật khẩu mới tối thiểu 6 ký tự.");
      return;
    }
    if (password !== confirmPassword) {
      setErrorMessage("Mật khẩu xác nhận không khớp.");
      return;
    }

    setIsSubmitting(true);
    try {
      const res = await fetch(`${API_BASE}/api/v1/auth/password-reset/confirm`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reset_token: resetToken, new_password: password }),
      });
      setIsSubmitting(false);

      if (res.ok) {
        setIsSuccess(true);
        setTimeout(() => {
          router.push("/login");
        }, 850);
      } else {
        const data = await res.json().catch(() => ({}));
        setErrorMessage(data.detail || "Không thể đặt lại mật khẩu. Token không hợp lệ hoặc đã hết hạn.");
      }
    } catch (e) {
      setIsSubmitting(false);
      setErrorMessage("Không thể kết nối đến máy chủ. Vui lòng kiểm tra lại dịch vụ backend.");
    }
  };

  const getStrength = (pass: string) => {
    if (!pass) return 0;
    let score = 0;
    if (pass.length >= 6) score++;
    if (pass.length >= 10) score++;
    if (/[A-Z]/.test(pass)) score++;
    if (/[0-9]/.test(pass)) score++;
    if (/[^A-Za-z0-9]/.test(pass)) score++;
    return Math.min(score, 4);
  };

  const strength = getStrength(password);
  const strengthLabels = ["Rất yếu", "Yếu", "Trung bình", "Khá mạnh", "Rất an toàn"];
  const strengthColors = [
    "bg-slate-300",
    "bg-rose-500",
    "bg-amber-500",
    "bg-sky-500",
    "bg-emerald-500",
  ];
  const strengthTextColors = [
    "text-slate-500",
    "text-rose-600",
    "text-amber-600",
    "text-sky-600",
    "text-emerald-600",
  ];

  const containerVariants = {
    hidden: { opacity: 0 },
    visible: {
      opacity: 1,
      transition: { staggerChildren: 0.08, delayChildren: 0.15 },
    },
  };

  const itemVariants = {
    hidden: { opacity: 0, y: 14 },
    visible: {
      opacity: 1,
      y: 0,
      transition: { type: "spring", stiffness: 280, damping: 24 },
    },
  };

  return (
    <div
      onMouseMove={handleMouseMove}
      className="min-h-screen relative flex flex-col justify-between overflow-x-hidden bg-[#ebf5fb] text-slate-800 selection:bg-sky-200 selection:text-sky-900"
    >
      <SpatialLoginBackground mouseParallax={mouseParallax} variant="light-sea" />

      {/* Top Header */}
      <header className="relative z-20 w-full max-w-6xl mx-auto px-4 sm:px-6 pt-5 sm:pt-7 flex items-center justify-between">
        <motion.div
          initial={{ opacity: 0, x: -16 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.7, ease: "easeOut" }}
          className="flex items-center gap-3"
        >
          <H4CareLogo variant="full" size="md" withTagline={false} />
          <div className="hidden sm:inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-white/80 border border-sky-300/60 text-[10px] font-mono text-sky-800 backdrop-blur-md shadow-xs">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
            <span>SECURITY KEY • ENCLAVE</span>
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, x: 16 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.7, ease: "easeOut" }}
          className="flex items-center gap-3"
        >
          <Link
            href="/login"
            className="group inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full text-xs font-semibold text-slate-700 bg-white/80 border border-sky-200/80 hover:border-sky-400 hover:text-sky-700 hover:bg-white transition-all shadow-xs backdrop-blur-md"
          >
            <ArrowLeft className="w-3.5 h-3.5 text-sky-600 group-hover:-translate-x-0.5 transition-transform" />
            <span>Về trang đăng nhập</span>
          </Link>
        </motion.div>
      </header>

      {/* Main Container */}
      <main className="relative z-10 w-full max-w-6xl mx-auto px-4 sm:px-6 py-6 sm:py-10 flex items-center justify-center flex-1">
        <motion.div
          variants={containerVariants}
          initial="hidden"
          animate="visible"
          className="w-full max-w-lg relative"
          style={{
            transform:
              !isMobile && !shouldReduceMotion
                ? `translate3d(${mouseParallax.x * 3}px, ${mouseParallax.y * 3}px, 0)`
                : undefined,
          }}
        >
          {/* Ambient Glow */}
          <div className="absolute -inset-1 rounded-[32px] bg-gradient-to-r from-sky-400/25 via-cyan-400/20 to-blue-400/20 blur-2xl pointer-events-none opacity-80" />

          {/* Frosted Crystalline Sea-Glass Card */}
          <div className="relative rounded-[28px] bg-white/85 backdrop-blur-2xl border border-white/90 p-6 sm:p-9 shadow-[0_25px_60px_-15px_rgba(2,132,199,0.16),0_0_40px_rgba(255,255,255,0.8)_inset] overflow-hidden">
            <div className="absolute top-0 inset-x-0 h-px bg-gradient-to-r from-transparent via-sky-400/60 to-transparent" />

            {/* Header info */}
            <motion.div variants={itemVariants} className="mb-6 text-center sm:text-left">
              <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-50 border border-emerald-200/80 text-emerald-700 text-[11px] font-semibold mb-3 tracking-wide">
                <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
                <span>Bảo mật tài khoản H4CARE</span>
              </div>
              <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight bg-gradient-to-r from-slate-900 via-sky-950 to-blue-900 bg-clip-text text-transparent">
                Tạo mật khẩu mới
              </h1>
              <p className="text-xs sm:text-sm text-slate-600 mt-1 leading-relaxed">
                {target ? `Thiết lập mật khẩu bảo mật mới cho tài khoản: ${target}` : "Vui lòng nhập mật khẩu mới để hoàn tất khôi phục tài khoản."}
              </p>
            </motion.div>

            {/* Alerts */}
            <AnimatePresence mode="wait">
              {errorMessage && (
                <motion.div
                  key="error-box"
                  initial={{ opacity: 0, y: -8, scale: 0.98 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, y: -8, scale: 0.98 }}
                  className="mb-5 p-3.5 rounded-2xl bg-red-50/95 border border-red-200 text-red-700 text-xs flex items-start gap-2.5 font-medium leading-relaxed backdrop-blur-md shadow-xs"
                >
                  <AlertCircle className="w-4 h-4 text-red-600 shrink-0 mt-0.5" />
                  <div className="flex-1">{errorMessage}</div>
                </motion.div>
              )}

              {isSuccess && (
                <motion.div
                  key="success-box"
                  initial={{ opacity: 0, y: -8, scale: 0.98 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, y: -8, scale: 0.98 }}
                  className="mb-5 p-3.5 rounded-2xl bg-emerald-50/95 border border-emerald-200 text-emerald-800 text-xs flex items-start gap-2.5 font-medium leading-relaxed backdrop-blur-md shadow-xs"
                >
                  <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                  <div className="flex-1">Mật khẩu đã được cập nhật thành công! Đang chuyển hướng về trang đăng nhập...</div>
                </motion.div>
              )}
            </AnimatePresence>

            <form onSubmit={handleSubmit} className="space-y-4">
              <motion.div variants={itemVariants}>
                <label className="block text-xs font-semibold text-slate-700 mb-1.5 flex items-center justify-between">
                  <span>Mật khẩu mới</span>
                  <span className="text-[10px] text-sky-600 font-mono">Tối thiểu 6 ký tự</span>
                </label>
                <div
                  className={`relative rounded-2xl bg-white/90 border transition-all duration-200 overflow-hidden ${
                    focusedField === "password"
                      ? "border-sky-500 ring-2 ring-sky-400/20 shadow-[0_0_20px_rgba(14,165,233,0.18)]"
                      : "border-sky-200/80 hover:border-sky-300"
                  }`}
                >
                  <input
                    type={showPassword ? "text" : "password"}
                    value={password}
                    onFocus={() => setFocusedField("password")}
                    onBlur={() => setFocusedField(null)}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Nhập mật khẩu mới..."
                    required
                    className="w-full px-4 py-3 pl-11 pr-11 bg-transparent text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none font-medium"
                  />
                  <div
                    className={`absolute left-3.5 top-1/2 -translate-y-1/2 transition-colors duration-200 pointer-events-none ${
                      focusedField === "password" ? "text-sky-600" : "text-slate-400"
                    }`}
                  >
                    <Lock className="w-4 h-4" />
                  </div>
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-sky-600 transition-colors p-1"
                    aria-label={showPassword ? "Ẩn mật khẩu" : "Hiện mật khẩu"}
                  >
                    {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>

                {/* Strength Bar */}
                {password && (
                  <div className="mt-2 flex items-center gap-2">
                    <div className="flex-1 grid grid-cols-4 gap-1 h-1.5 bg-slate-100 rounded-full overflow-hidden">
                      {[1, 2, 3, 4].map((lvl) => (
                        <div
                          key={lvl}
                          className={`h-full transition-colors ${
                            strength >= lvl ? strengthColors[strength] : "bg-transparent"
                          }`}
                        />
                      ))}
                    </div>
                    <span className={`text-[11px] font-bold ${strengthTextColors[strength]}`}>
                      {strengthLabels[strength]}
                    </span>
                  </div>
                )}
              </motion.div>

              <motion.div variants={itemVariants}>
                <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                  Xác nhận mật khẩu mới
                </label>
                <div
                  className={`relative rounded-2xl bg-white/90 border transition-all duration-200 overflow-hidden ${
                    focusedField === "confirmPassword"
                      ? "border-sky-500 ring-2 ring-sky-400/20 shadow-[0_0_20px_rgba(14,165,233,0.18)]"
                      : "border-sky-200/80 hover:border-sky-300"
                  }`}
                >
                  <input
                    type={showConfirmPassword ? "text" : "password"}
                    value={confirmPassword}
                    onFocus={() => setFocusedField("confirmPassword")}
                    onBlur={() => setFocusedField(null)}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    placeholder="Nhập lại mật khẩu mới..."
                    required
                    className="w-full px-4 py-3 pl-11 pr-11 bg-transparent text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none font-medium"
                  />
                  <div
                    className={`absolute left-3.5 top-1/2 -translate-y-1/2 transition-colors duration-200 pointer-events-none ${
                      focusedField === "confirmPassword" ? "text-sky-600" : "text-slate-400"
                    }`}
                  >
                    <Lock className="w-4 h-4" />
                  </div>
                  <button
                    type="button"
                    onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                    className="absolute right-3.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-sky-600 transition-colors p-1"
                    aria-label={showConfirmPassword ? "Ẩn mật khẩu" : "Hiện mật khẩu"}
                  >
                    {showConfirmPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </motion.div>

              <motion.div variants={itemVariants} className="pt-2">
                <LiquidMetalButton
                  type="submit"
                  variant="mercury"
                  isLoading={isSubmitting}
                  isSuccess={isSuccess}
                  disabled={isSubmitting || isSuccess}
                >
                  Cập nhật mật khẩu & Đăng nhập
                </LiquidMetalButton>
              </motion.div>
            </form>

            <motion.div variants={itemVariants} className="mt-6 text-center text-xs text-slate-600">
              <Link
                href="/login"
                className="font-bold text-sky-600 hover:text-sky-800 hover:underline transition-colors"
              >
                Quay lại đăng nhập
              </Link>
            </motion.div>

          </div>
        </motion.div>
      </main>

      <footer className="relative z-20 w-full text-center py-4 text-[11px] text-slate-500 select-none">
        <span>Hệ thống Quản lý Dữ liệu Thuốc & Bán lẻ Dược phẩm H4CARE • Đạt chuẩn GPP & GSP Bộ Y Tế</span>
      </footer>
    </div>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen bg-[#ebf5fb] flex items-center justify-center text-xs text-sky-700/60 font-mono">
          Đang tải H4CARE Security...
        </div>
      }
    >
      <ResetPasswordContent />
    </Suspense>
  );
}
