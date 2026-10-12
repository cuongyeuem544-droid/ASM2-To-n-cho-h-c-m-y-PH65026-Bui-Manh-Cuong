"use client";

import React, { useState, useEffect, Suspense, useCallback } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { motion, AnimatePresence, useReducedMotion } from "framer-motion";
import { useAuth } from "@/lib/auth/auth-context";
import { redirectToAdminPortal } from "@/lib/auth/admin-redirect";
import { H4CareLogo } from "@/components/branding/H4CareLogo";
import { SpatialLoginBackground } from "@/components/auth/SpatialLoginBackground";
import { LiquidMetalButton } from "@/components/auth/LiquidMetalButton";
import {
  ArrowLeft,
  Mail,
  Lock,
  Eye,
  EyeOff,
  CheckCircle2,
  AlertCircle,
  Smartphone,
  ShieldCheck,
  ArrowRight,
  Sparkles,
} from "lucide-react";

/**
 * H4CARE Bespoke Liquid Metal Login Experience
 * Oceanic Light Sea Blue Theme ("Xanh nước biển nhạt"):
 * - Pristine sea blue spatial background with gentle oceanic ambient blooms (#ebf5fb -> #e0f2fe)
 * - Crystalline frosted sea-glass enclave card with Settigation spring physics { k: 55, d: 11 }
 * - Liquid metal mercury capsule button with morphing emerald checkmark on success
 * - Full responsive 60 FPS performance, desktop cursor parallax, mobile optimized
 */
function LoginContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const redirectUrl = searchParams.get("redirect") || "/account";
  const shouldReduceMotion = useReducedMotion();

  const { user, isAuthenticated, loginWithPassword, loginWithPhone, sendPhoneOtp } = useAuth();

  // Redirect if already authenticated
  useEffect(() => {
    if (isAuthenticated) {
      if (user?.isAdmin) {
        router.push("/admin");
      } else {
        router.push(redirectUrl);
      }
    }
  }, [isAuthenticated, user, router, redirectUrl]);

  // ================= FORM STATE =================
  const [identifier, setIdentifier] = useState<string>("");
  const [password, setPassword] = useState<string>("");
  const [showPassword, setShowPassword] = useState<boolean>(false);
  const [rememberMe, setRememberMe] = useState<boolean>(true);

  // OTP mode toggle
  const [useOtpMode, setUseOtpMode] = useState<boolean>(false);
  const [otpStep, setOtpStep] = useState<"phone" | "verify">("phone");
  const [otpValues, setOtpValues] = useState<string[]>(["", "", "", "", "", ""]);
  const [countdown, setCountdown] = useState<number>(60);

  // Focus tracking for dynamic input glows
  const [focusedField, setFocusedField] = useState<string | null>(null);

  // Status feedback
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [isSuccess, setIsSuccess] = useState<boolean>(false);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Mouse Parallax State (Desktop only, 2-6px)
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
      const normX = (e.clientX / innerWidth - 0.5) * 2; // -1 to 1
      const normY = (e.clientY / innerHeight - 0.5) * 2; // -1 to 1
      setMouseParallax({ x: normX, y: normY });
    },
    [isMobile, shouldReduceMotion]
  );

  // Recent accounts list
  const [recentAccounts, setRecentAccounts] = useState<Array<{ fullName: string; identifier: string; role: string }>>([]);

  useEffect(() => {
    try {
      const stored = localStorage.getItem("h4care_recent_accounts");
      if (stored) {
        setRecentAccounts(JSON.parse(stored));
      }
    } catch (e) {
      console.warn("Failed to load recent accounts", e);
    }
  }, []);

  const saveRecentAccount = (name: string, id: string, role: string) => {
    try {
      const updated = [
        { fullName: name, identifier: id, role },
        ...recentAccounts.filter((a) => a.identifier !== id),
      ].slice(0, 4);
      setRecentAccounts(updated);
      localStorage.setItem("h4care_recent_accounts", JSON.stringify(updated));
    } catch (e) {
      console.warn("Failed to save recent account", e);
    }
  };

  // OTP Countdown timer
  useEffect(() => {
    let timer: NodeJS.Timeout;
    if (useOtpMode && otpStep === "verify" && countdown > 0) {
      timer = setInterval(() => setCountdown((c) => c - 1), 1000);
    }
    return () => clearInterval(timer);
  }, [useOtpMode, otpStep, countdown]);

  // ================= SUBMIT HANDLERS =================
  const handlePasswordSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);

    if (!identifier.trim()) {
      setErrorMessage("Vui lòng nhập Email hoặc Số điện thoại.");
      return;
    }
    if (!password) {
      setErrorMessage("Vui lòng nhập mật khẩu tài khoản.");
      return;
    }

    setIsSubmitting(true);
    const result = await loginWithPassword(identifier.trim(), password);
    setIsSubmitting(false);

    if (result.success) {
      setIsSuccess(true);
      if (result.user) {
        saveRecentAccount(result.user.fullName, identifier.trim(), result.user.role);
      }
      const isTargetAdmin = result.user?.isAdmin;
      if (isTargetAdmin) {
        setSuccessMessage("Đăng nhập Quản trị viên thành công! Đang mở Cổng Quản Trị...");
        redirectToAdminPortal("", true);
        setTimeout(() => {
          router.push("/");
        }, 850);
      } else {
        setSuccessMessage(`Chào mừng trở lại, ${result.user?.fullName}!`);
        setTimeout(() => {
          router.push(redirectUrl);
        }, 800);
      }
    } else {
      setErrorMessage(result.error || "Thông tin đăng nhập không chính xác. Vui lòng kiểm tra lại.");
    }
  };

  const handleOtpRequest = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);

    const cleanPhone = identifier.replace(/\D/g, "");
    if (cleanPhone.length < 9) {
      setErrorMessage("Vui lòng nhập số điện thoại hợp lệ (9 - 10 chữ số).");
      return;
    }

    setIsSubmitting(true);
    const res = await sendPhoneOtp(cleanPhone);
    setIsSubmitting(false);

    if (res.success) {
      setOtpStep("verify");
      setCountdown(60);
    } else {
      setErrorMessage(res.error || "Gửi OTP không thành công.");
    }
  };

  const handleOtpVerify = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);

    const otpCode = otpValues.join("");
    if (otpCode.length < 6) {
      setErrorMessage("Vui lòng nhập đầy đủ 6 chữ số mã xác thực OTP.");
      return;
    }

    setIsSubmitting(true);
    const cleanPhone = identifier.replace(/\D/g, "");
    const res = await loginWithPhone(cleanPhone, otpCode);
    setIsSubmitting(false);

    if (res.success) {
      setIsSuccess(true);
      const isTargetAdmin = res.user?.isAdmin;
      if (isTargetAdmin) {
        setSuccessMessage("Đăng nhập Quản trị viên thành công! Đang chuyển tới Cổng Quản Trị...");
        redirectToAdminPortal("", true);
        setTimeout(() => {
          router.push("/");
        }, 850);
      } else {
        setSuccessMessage(`Chào mừng trở lại, ${res.user?.fullName}!`);
        setTimeout(() => {
          router.push(redirectUrl);
        }, 800);
      }
    } else {
      setErrorMessage(res.error || "Mã OTP không chính xác.");
    }
  };

  // Motion variants for opening sequence (0.8s - 1.2s total choreo)
  const containerVariants = {
    hidden: { opacity: 0 },
    visible: {
      opacity: 1,
      transition: {
        staggerChildren: 0.08,
        delayChildren: 0.15,
      },
    },
  };

  const itemVariants = {
    hidden: { opacity: 0, y: 14 },
    visible: {
      opacity: 1,
      y: 0,
      transition: {
        type: "spring",
        stiffness: 280,
        damping: 24,
      },
    },
  };

  return (
    <div
      onMouseMove={handleMouseMove}
      className="min-h-screen relative flex flex-col justify-between overflow-x-hidden bg-[#ebf5fb] text-slate-800 selection:bg-sky-200 selection:text-sky-900"
    >
      {/* Oceanic Light Sea Blue Spatial Background with Settigation Parallax */}
      <SpatialLoginBackground mouseParallax={mouseParallax} variant="light-sea" />

      {/* Top Floating Glass Navigation Header */}
      <header className="relative z-20 w-full max-w-6xl mx-auto px-4 sm:px-6 pt-5 sm:pt-7 flex items-center justify-between">
        <motion.div
          initial={{ opacity: 0, x: -16 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.7, ease: "easeOut" }}
          className="flex items-center gap-3"
        >
          <H4CareLogo variant="full" size="md" withTagline={false} />
          {/* Settigation Telemetry Tag */}
          <div className="hidden sm:inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-white/80 border border-sky-300/60 text-[10px] font-mono text-sky-800 backdrop-blur-md shadow-xs">
            <span className="w-1.5 h-1.5 rounded-full bg-sky-500 animate-pulse" />
            <span>ENCLAVE v2.6 • {`{ k: 55, d: 11 }`}</span>
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, x: 16 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.7, ease: "easeOut" }}
          className="flex items-center gap-3"
        >
          <Link
            href="/"
            className="group inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full text-xs font-semibold text-slate-700 bg-white/80 border border-sky-200/80 hover:border-sky-400 hover:text-sky-700 hover:bg-white transition-all shadow-xs backdrop-blur-md"
          >
            <ArrowLeft className="w-3.5 h-3.5 text-sky-600 group-hover:-translate-x-0.5 transition-transform" />
            <span>Về trang chủ</span>
          </Link>
        </motion.div>
      </header>

      {/* Main Bespoke Spatial Centerpiece */}
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
          {/* Ambient Glow Halo behind the glass card (Oceanic cyan/sky blue) */}
          <div className="absolute -inset-1 rounded-[32px] bg-gradient-to-r from-sky-400/25 via-cyan-400/20 to-blue-400/20 blur-2xl pointer-events-none opacity-80" />

          {/* Frosted Crystalline Sea-Glass Enclave Container */}
          <div className="relative rounded-[28px] bg-white/85 backdrop-blur-2xl border border-white/90 p-6 sm:p-9 shadow-[0_25px_60px_-15px_rgba(2,132,199,0.16),0_0_40px_rgba(255,255,255,0.8)_inset] overflow-hidden">
            
            {/* Top Specular Sheen Edge */}
            <div className="absolute top-0 inset-x-0 h-px bg-gradient-to-r from-transparent via-sky-400/60 to-transparent" />

            {/* 1. Header & Brand Title */}
            <motion.div variants={itemVariants} className="mb-6 text-center sm:text-left">
              <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-sky-50 border border-sky-200/80 text-sky-700 text-[11px] font-semibold mb-3 tracking-wide">
                <ShieldCheck className="w-3.5 h-3.5 text-sky-600" />
                <span>Nền tảng Y tế & Dược phẩm H4CARE</span>
              </div>
              <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight bg-gradient-to-r from-slate-900 via-sky-950 to-blue-900 bg-clip-text text-transparent">
                Chào mừng trở lại.
              </h1>
              <p className="text-xs sm:text-sm text-slate-600 mt-1 leading-relaxed">
                Chăm sóc sức khỏe, bắt đầu từ sự thấu hiểu.
              </p>
            </motion.div>

            {/* 2. Notification Alerts */}
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

              {isSuccess && successMessage && (
                <motion.div
                  key="success-box"
                  initial={{ opacity: 0, y: -8, scale: 0.98 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, y: -8, scale: 0.98 }}
                  className="mb-5 p-3.5 rounded-2xl bg-emerald-50/95 border border-emerald-200 text-emerald-800 text-xs flex items-start gap-2.5 font-medium leading-relaxed backdrop-blur-md shadow-xs"
                >
                  <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                  <div className="flex-1">{successMessage}</div>
                </motion.div>
              )}
            </AnimatePresence>

            {/* 3. Mode Toggle: Password vs Phone OTP Capsule */}
            <motion.div variants={itemVariants} className="relative p-1 bg-sky-100/70 rounded-2xl mb-6 border border-sky-200/60 text-xs font-semibold grid grid-cols-2">
              <button
                type="button"
                onClick={() => {
                  setUseOtpMode(false);
                  setErrorMessage(null);
                }}
                className={`relative py-2.5 rounded-xl transition-all duration-200 flex items-center justify-center gap-2 z-10 ${
                  !useOtpMode
                    ? "text-white font-bold"
                    : "text-slate-600 hover:text-slate-900"
                }`}
              >
                {!useOtpMode && (
                  <motion.div
                    layoutId="activeModeIndicator"
                    className="absolute inset-0 rounded-xl bg-gradient-to-r from-sky-500 to-blue-600 border border-sky-400/40 shadow-[0_2px_10px_rgba(14,165,233,0.3)] -z-10"
                    transition={{ type: "spring", stiffness: 350, damping: 28 }}
                  />
                )}
                <Lock className={`w-3.5 h-3.5 ${!useOtpMode ? "text-white" : "text-slate-500"}`} />
                <span>Dùng Mật khẩu</span>
              </button>

              <button
                type="button"
                onClick={() => {
                  setUseOtpMode(true);
                  setOtpStep("phone");
                  setErrorMessage(null);
                }}
                className={`relative py-2.5 rounded-xl transition-all duration-200 flex items-center justify-center gap-2 z-10 ${
                  useOtpMode
                    ? "text-white font-bold"
                    : "text-slate-600 hover:text-slate-900"
                }`}
              >
                {useOtpMode && (
                  <motion.div
                    layoutId="activeModeIndicator"
                    className="absolute inset-0 rounded-xl bg-gradient-to-r from-sky-500 to-blue-600 border border-sky-400/40 shadow-[0_2px_10px_rgba(14,165,233,0.3)] -z-10"
                    transition={{ type: "spring", stiffness: 350, damping: 28 }}
                  />
                )}
                <Smartphone className={`w-3.5 h-3.5 ${useOtpMode ? "text-white" : "text-slate-500"}`} />
                <span>Mã OTP di động</span>
              </button>
            </motion.div>

            {/* 4. MODE 1: Standard Password Authentication */}
            {!useOtpMode && (
              <form onSubmit={handlePasswordSubmit} className="space-y-4">
                {/* Identifier field */}
                <motion.div variants={itemVariants}>
                  <label className="block text-xs font-semibold text-slate-700 mb-1.5 flex items-center justify-between">
                    <span>Email hoặc Số điện thoại</span>
                    <span className="text-[10px] text-sky-600 font-mono">Bảo mật SSL 256</span>
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
                      placeholder="Nhập email hoặc số điện thoại..."
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

                {/* Password field */}
                <motion.div variants={itemVariants}>
                  <div className="flex items-center justify-between mb-1.5">
                    <label className="text-xs font-semibold text-slate-700">Mật khẩu</label>
                    <Link
                      href="/forgot-password"
                      className="text-xs text-sky-600 hover:text-sky-800 font-semibold transition-colors focus:outline-none"
                    >
                      Quên mật khẩu?
                    </Link>
                  </div>
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
                      placeholder="Nhập mật khẩu của bạn..."
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
                </motion.div>

                {/* Remember Me Checkbox */}
                <motion.div variants={itemVariants} className="flex items-center justify-between pt-1">
                  <label className="flex items-center gap-2.5 cursor-pointer select-none text-xs text-slate-700 group">
                    <input
                      type="checkbox"
                      checked={rememberMe}
                      onChange={(e) => setRememberMe(e.target.checked)}
                      className="w-4 h-4 rounded border-sky-300 bg-white text-sky-600 focus:ring-sky-400/20 focus:ring-offset-0 transition-colors"
                    />
                    <span className="group-hover:text-slate-900 transition-colors">
                      Ghi nhớ đăng nhập trên thiết bị này
                    </span>
                  </label>
                </motion.div>

                {/* Settigation Liquid Metal Capsule Button */}
                <motion.div variants={itemVariants} className="pt-2">
                  <LiquidMetalButton
                    type="submit"
                    variant="mercury"
                    isLoading={isSubmitting}
                    isSuccess={isSuccess}
                    disabled={isSubmitting || isSuccess}
                  >
                    Đăng nhập H4CARE
                  </LiquidMetalButton>
                </motion.div>
              </form>
            )}

            {/* 5. MODE 2: OTP Fast Verification */}
            {useOtpMode && (
              <div className="space-y-4">
                {otpStep === "phone" ? (
                  <form onSubmit={handleOtpRequest} className="space-y-4">
                    <motion.div variants={itemVariants}>
                      <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                        Số điện thoại nhận mã OTP
                      </label>
                      <div
                        className={`relative rounded-2xl bg-white/90 border transition-all duration-200 overflow-hidden ${
                          focusedField === "otpPhone"
                            ? "border-sky-500 ring-2 ring-sky-400/20 shadow-[0_0_20px_rgba(14,165,233,0.18)]"
                            : "border-sky-200/80 hover:border-sky-300"
                        }`}
                      >
                        <input
                          type="tel"
                          value={identifier}
                          onFocus={() => setFocusedField("otpPhone")}
                          onBlur={() => setFocusedField(null)}
                          onChange={(e) => setIdentifier(e.target.value)}
                          placeholder="Ví dụ: 0901234567"
                          required
                          className="w-full px-4 py-3 pl-11 bg-transparent text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none font-medium"
                        />
                        <div
                          className={`absolute left-3.5 top-1/2 -translate-y-1/2 transition-colors duration-200 pointer-events-none ${
                            focusedField === "otpPhone" ? "text-sky-600" : "text-slate-400"
                          }`}
                        >
                          <Smartphone className="w-4 h-4" />
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
                        Gửi mã xác thực OTP
                      </LiquidMetalButton>
                    </motion.div>
                  </form>
                ) : (
                  <form onSubmit={handleOtpVerify} className="space-y-4">
                    <motion.div variants={itemVariants} className="text-center mb-3">
                      <span className="text-xs text-slate-500">Mã xác thực 6 số đã gửi tới</span>
                      <p className="text-sm font-bold text-sky-700">{identifier}</p>
                    </motion.div>

                    {/* 6-Cell OTP Input */}
                    <motion.div variants={itemVariants} className="flex justify-center gap-2">
                      {otpValues.map((val, idx) => (
                        <input
                          key={idx}
                          id={`otp-input-${idx}`}
                          type="text"
                          maxLength={1}
                          value={val}
                          onChange={(e) => {
                            const newVals = [...otpValues];
                            newVals[idx] = e.target.value.slice(-1);
                            setOtpValues(newVals);
                            if (e.target.value && idx < 5) {
                              document.getElementById(`otp-input-${idx + 1}`)?.focus();
                            }
                          }}
                          className="w-10 sm:w-12 h-12 text-center text-lg font-bold rounded-xl border border-sky-200/80 bg-white/95 text-slate-900 focus:outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-400/20 focus:shadow-[0_0_15px_rgba(14,165,233,0.25)] transition-all font-mono"
                        />
                      ))}
                    </motion.div>

                    <motion.div variants={itemVariants} className="flex items-center justify-between text-xs text-slate-500 pt-2">
                      <button
                        type="button"
                        onClick={() => setOtpStep("phone")}
                        className="text-slate-600 hover:text-sky-700 font-medium transition-colors"
                      >
                        ← Đổi số điện thoại
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
                        Xác nhận & Đăng nhập
                      </LiquidMetalButton>
                    </motion.div>
                  </form>
                )}
              </div>
            )}

            {/* 6. Quick Test Role Switcher (Chỉ hiển thị khi DEMO_MODE = true) */}
            {process.env.NEXT_PUBLIC_DEMO_MODE === "true" && (
              <motion.div variants={itemVariants} className="mt-7 pt-5 border-t border-sky-100">
                <div className="flex items-center justify-between mb-2.5">
                  <span className="text-[11px] font-bold text-slate-600 uppercase tracking-wider flex items-center gap-1.5">
                    <Sparkles className="w-3 h-3 text-sky-600" />
                    <span>Thử nghiệm vai trò Demo</span>
                  </span>
                  <span className="text-[10px] text-sky-600 font-mono">DEMO MODE</span>
                </div>
                <div className="grid grid-cols-3 gap-2">
                  <button
                    type="button"
                    onClick={() => {
                      setIdentifier("admin@pharmatrust.vn");
                      setPassword("Admin@123456");
                      setUseOtpMode(false);
                      setErrorMessage(null);
                    }}
                    className="p-2.5 rounded-xl border border-indigo-200/80 bg-indigo-50/80 hover:bg-indigo-100/90 hover:border-indigo-300 text-indigo-700 text-[11px] font-semibold transition-all text-center group cursor-pointer shadow-xs"
                    title="Đăng nhập tài khoản Quản trị viên (Chuyển tới Admin Portal)"
                  >
                    <span className="block group-hover:scale-105 transition-transform">🛡️ Admin</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setIdentifier("reviewer@pharmatrust.vn");
                      setPassword("Reviewer@123456");
                      setUseOtpMode(false);
                      setErrorMessage(null);
                    }}
                    className="p-2.5 rounded-xl border border-amber-200/80 bg-amber-50/80 hover:bg-amber-100/90 hover:border-amber-300 text-amber-700 text-[11px] font-semibold transition-all text-center group cursor-pointer shadow-xs"
                    title="Dược sĩ Kiểm duyệt Dữ liệu"
                  >
                    <span className="block group-hover:scale-105 transition-transform">🔬 Dược sĩ</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setIdentifier("buyer@pharmatrust.vn");
                      setPassword("Buyer@123456");
                      setUseOtpMode(false);
                      setErrorMessage(null);
                    }}
                    className="p-2.5 rounded-xl border border-sky-200/80 bg-sky-50/80 hover:bg-sky-100/90 hover:border-sky-300 text-sky-700 text-[11px] font-semibold transition-all text-center group cursor-pointer shadow-xs"
                    title="Khách mua thuốc"
                  >
                    <span className="block group-hover:scale-105 transition-transform">👤 Người mua</span>
                  </button>
                </div>
                <p className="text-[10px] text-slate-500 mt-2 leading-relaxed">
                  * Dữ liệu tài khoản demo được sinh tự động bởi script seed.
                </p>
              </motion.div>
            )}

            {/* 7. Bottom Registration Link */}
            <motion.div variants={itemVariants} className="mt-6 text-center text-xs text-slate-600">
              Chưa có tài khoản thành viên?{" "}
              <Link
                href="/register"
                className="font-bold text-sky-600 hover:text-sky-800 hover:underline transition-colors"
              >
                Đăng ký ngay
              </Link>
            </motion.div>

          </div>
        </motion.div>
      </main>

      {/* Global Academic & Healthcare Trust Subtext */}
      <footer className="relative z-20 w-full text-center py-4 text-[11px] text-slate-500 select-none">
        <span>Hệ thống Quản lý Dữ liệu Thuốc & Bán lẻ Dược phẩm H4CARE • Đạt chuẩn GPP & GSP Bộ Y Tế</span>
      </footer>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen bg-[#ebf5fb] flex items-center justify-center text-xs text-sky-700/60 font-mono">
          Đang khởi tạo H4CARE Liquid Space...
        </div>
      }
    >
      <LoginContent />
    </Suspense>
  );
}
