"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence, useReducedMotion } from "framer-motion";
import { useAuth } from "@/lib/auth/auth-context";
import { H4CareLogo } from "@/components/branding/H4CareLogo";
import { SpatialLoginBackground } from "@/components/auth/SpatialLoginBackground";
import { LiquidMetalButton } from "@/components/auth/LiquidMetalButton";
import {
  ArrowLeft,
  Smartphone,
  Mail,
  ShieldCheck,
  AlertCircle,
  CheckCircle2,
  KeyRound,
  Sparkles,
} from "lucide-react";

/**
 * H4CARE Bespoke Forgot Password Experience
 * Harmonized with the Oceanic Light Sea Blue Spatial Theme & Liquid Metal Motion
 */
export default function ForgotPasswordPage() {
  const router = useRouter();
  const { sendPhoneOtp } = useAuth();
  const shouldReduceMotion = useReducedMotion();

  const [identifier, setIdentifier] = useState<string>("");
  const [step, setStep] = useState<"input" | "otp">("input");
  const [otpValues, setOtpValues] = useState<string[]>(["", "", "", "", "", ""]);
  const [countdown, setCountdown] = useState<number>(60);
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

  // Timer countdown
  useEffect(() => {
    let timer: NodeJS.Timeout;
    if (step === "otp" && countdown > 0) {
      timer = setInterval(() => setCountdown((c) => c - 1), 1000);
    }
    return () => clearInterval(timer);
  }, [step, countdown]);

  const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  const handleSendOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);

    const cleanId = identifier.trim();
    if (!cleanId) {
      setErrorMessage("Vui lòng nhập số điện thoại hoặc email đã đăng ký.");
      return;
    }

    setIsSubmitting(true);
    try {
      const res = await fetch(`${API_BASE}/api/v1/auth/password-reset/request`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ identifier: cleanId }),
      });
      setIsSubmitting(false);

      if (res.ok) {
        setStep("otp");
        setCountdown(60);
      } else {
        const data = await res.json().catch(() => ({}));
        setErrorMessage(data.detail || "Không thể gửi mã xác thực. Vui lòng kiểm tra lại thông tin.");
      }
    } catch (e) {
      setIsSubmitting(false);
      setErrorMessage("Không thể kết nối đến máy chủ. Vui lòng kiểm tra lại dịch vụ backend.");
    }
  };

  const handleVerifyOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);

    const otpCode = otpValues.join("");
    if (otpCode.length < 6) {
      setErrorMessage("Vui lòng nhập đủ 6 chữ số mã OTP.");
      return;
    }

    setIsSubmitting(true);
    try {
      const res = await fetch(`${API_BASE}/api/v1/auth/password-reset/verify`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ identifier: identifier.trim(), otp: otpCode }),
      });
      setIsSubmitting(false);

      if (res.ok) {
        const data = await res.json();
        setIsSuccess(true);
        setTimeout(() => {
          router.push(`/reset-password?token=${encodeURIComponent(data.reset_token)}`);
        }, 750);
      } else {
        const data = await res.json().catch(() => ({}));
        setErrorMessage(data.detail || "Mã OTP không chính xác hoặc đã hết hạn.");
      }
    } catch (e) {
      setIsSubmitting(false);
      setErrorMessage("Không thể kết nối đến máy chủ. Vui lòng kiểm tra lại dịch vụ backend.");
    }
  };

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
            <span className="w-1.5 h-1.5 rounded-full bg-sky-500 animate-pulse" />
            <span>RECOVERY v2.6 • ENCLAVE</span>
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
              <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-sky-50 border border-sky-200/80 text-sky-700 text-[11px] font-semibold mb-3 tracking-wide">
                <KeyRound className="w-3.5 h-3.5 text-sky-600" />
                <span>Khôi phục tài khoản bảo mật</span>
              </div>
              <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight bg-gradient-to-r from-slate-900 via-sky-950 to-blue-900 bg-clip-text text-transparent">
                Quên mật khẩu?
              </h1>
              <p className="text-xs sm:text-sm text-slate-600 mt-1 leading-relaxed">
                Nhập số điện thoại hoặc email đã đăng ký. Hệ thống sẽ gửi mã xác thực OTP bảo mật để đặt lại mật khẩu.
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
                  <div className="flex-1">Mã xác thực chính xác! Đang chuyển hướng sang trang đặt lại mật khẩu...</div>
                </motion.div>
              )}
            </AnimatePresence>

            {step === "input" ? (
              <form onSubmit={handleSendOtp} className="space-y-4">
                <motion.div variants={itemVariants}>
                  <label className="block text-xs font-semibold text-slate-700 mb-1.5 flex items-center justify-between">
                    <span>Số điện thoại hoặc Email</span>
                    <span className="text-[10px] text-sky-600 font-mono">Xác thực OTP</span>
                  </label>
                  <div
                    className={`relative rounded-2xl bg-white/90 border transition-all duration-200 overflow-hidden ${
                      focusedField === "identifier"
                        ? "border-sky-500 ring-2 ring-sky-400/20 shadow-[0_0_20px_rgba(14,165,233,0.18)]"
                        : "border-sky-200/80 hover:border-sky-300"
                    }`}
                  >
                    <input
                      type="text"
                      value={identifier}
                      onFocus={() => setFocusedField("identifier")}
                      onBlur={() => setFocusedField(null)}
                      onChange={(e) => setIdentifier(e.target.value)}
                      placeholder="Ví dụ: 0901234567 hoặc email..."
                      required
                      className="w-full px-4 py-3 pl-11 bg-transparent text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none font-medium"
                    />
                    <div
                      className={`absolute left-3.5 top-1/2 -translate-y-1/2 transition-colors duration-200 pointer-events-none ${
                        focusedField === "identifier" ? "text-sky-600" : "text-slate-400"
                      }`}
                    >
                      {identifier.includes("@") ? (
                        <Mail className="w-4 h-4" />
                      ) : (
                        <Smartphone className="w-4 h-4" />
                      )}
                    </div>
                  </div>
                </motion.div>

                <motion.div variants={itemVariants} className="pt-2">
                  <LiquidMetalButton
                    type="submit"
                    variant="mercury"
                    isLoading={isSubmitting}
                    disabled={isSubmitting}
                  >
                    Tiếp tục nhận mã OTP
                  </LiquidMetalButton>
                </motion.div>
              </form>
            ) : (
              <form onSubmit={handleVerifyOtp} className="space-y-4">
                <motion.div variants={itemVariants} className="text-center mb-3">
                  <span className="text-xs text-slate-500">Mã OTP 6 số đã gửi tới</span>
                  <p className="text-sm font-bold text-sky-700">{identifier}</p>
                </motion.div>

                {/* 6-Cell OTP Input */}
                <motion.div variants={itemVariants} className="flex justify-center gap-2">
                  {otpValues.map((val, idx) => (
                    <input
                      key={idx}
                      id={`forgot-otp-${idx}`}
                      type="text"
                      maxLength={1}
                      value={val}
                      onChange={(e) => {
                        const newVals = [...otpValues];
                        newVals[idx] = e.target.value.slice(-1);
                        setOtpValues(newVals);
                        if (e.target.value && idx < 5) {
                          document.getElementById(`forgot-otp-${idx + 1}`)?.focus();
                        }
                      }}
                      className="w-10 sm:w-12 h-12 text-center text-lg font-bold rounded-xl border border-sky-200/80 bg-white/95 text-slate-900 focus:outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-400/20 focus:shadow-[0_0_15px_rgba(14,165,233,0.25)] transition-all font-mono"
                    />
                  ))}
                </motion.div>

                <motion.div variants={itemVariants} className="flex items-center justify-between text-xs text-slate-500 pt-2">
                  <button
                    type="button"
                    onClick={() => setStep("input")}
                    className="text-slate-600 hover:text-sky-700 font-medium transition-colors"
                  >
                    ← Đổi số / email
                  </button>
                  <span>
                    {countdown > 0 ? (
                      `Gửi lại sau ${countdown}s`
                    ) : (
                      <button
                        type="button"
                        onClick={() => {
                          setCountdown(60);
                          sendPhoneOtp(identifier);
                        }}
                        className="text-sky-600 font-bold hover:underline"
                      >
                        Gửi lại mã
                      </button>
                    )}
                  </span>
                </motion.div>

                <motion.div variants={itemVariants} className="pt-2">
                  <LiquidMetalButton
                    type="submit"
                    variant="mercury"
                    isLoading={isSubmitting}
                    isSuccess={isSuccess}
                    disabled={isSubmitting || isSuccess}
                  >
                    Xác nhận & Đặt lại mật khẩu
                  </LiquidMetalButton>
                </motion.div>
              </form>
            )}

            <motion.div variants={itemVariants} className="mt-6 text-center text-xs text-slate-600">
              Nhớ mật khẩu tài khoản?{" "}
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
