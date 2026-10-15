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
  User,
  Smartphone,
  Mail,
  Lock,
  Eye,
  EyeOff,
  ShieldCheck,
  CheckCircle2,
  AlertCircle,
  Sparkles,
  ArrowRight,
} from "lucide-react";

/**
 * H4CARE Bespoke Registration Experience
 * Harmonized with the Oceanic Light Sea Blue Spatial Theme & Liquid Metal Motion
 */
export default function RegisterPage() {
  const router = useRouter();
  const { isAuthenticated, register } = useAuth();
  const shouldReduceMotion = useReducedMotion();

  useEffect(() => {
    if (isAuthenticated) {
      router.push("/account");
    }
  }, [isAuthenticated, router]);

  // Form Fields
  const [fullName, setFullName] = useState<string>("");
  const [phone, setPhone] = useState<string>("");
  const [formattedPhone, setFormattedPhone] = useState<string>("");
  const [carrier, setCarrier] = useState<string>("Việt Nam (+84)");
  const [email, setEmail] = useState<string>("");
  const [password, setPassword] = useState<string>("");
  const [confirmPassword, setConfirmPassword] = useState<string>("");

  const [showPassword, setShowPassword] = useState<boolean>(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState<boolean>(false);
  const [agreeTerms, setAgreeTerms] = useState<boolean>(true);
  const [focusedField, setFocusedField] = useState<string | null>(null);

  // Status feedback
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

  // Password strength calculator
  const getPasswordStrength = (pwd: string) => {
    if (!pwd) return { score: 0, text: "", color: "" };
    let score = 0;
    if (pwd.length >= 6) score += 1;
    if (pwd.length >= 8) score += 1;
    if (/[A-Z]/.test(pwd) && /[a-z]/.test(pwd)) score += 1;
    if (/[0-9]/.test(pwd) || /[^A-Za-z0-9]/.test(pwd)) score += 1;
    if (score <= 1) return { score: 1, text: "Yếu", color: "bg-rose-500", textCol: "text-rose-600" };
    if (score === 2) return { score: 2, text: "Trung bình", color: "bg-amber-500", textCol: "text-amber-600" };
    if (score === 3) return { score: 3, text: "Khá mạnh", color: "bg-sky-500", textCol: "text-sky-600" };
    return { score: 4, text: "Rất an toàn", color: "bg-emerald-500", textCol: "text-emerald-600" };
  };

  // Phone Formatter Utility
  const formatPhoneString = (inputVal: string) => {
    let val = inputVal.replace(/\D/g, "");
    if (val.length > 10) val = val.substring(0, 10);

    let formatted = "";
    if (val.length > 0) formatted += val.substring(0, 4);
    if (val.length > 4) formatted += " " + val.substring(4, 7);
    if (val.length > 7) formatted += " " + val.substring(7, 10);

    let detectedCarrier = "Việt Nam (+84)";
    if (val.startsWith("090") || val.startsWith("093") || val.startsWith("070") || val.startsWith("079")) {
      detectedCarrier = "MobiFone";
    } else if (val.startsWith("098") || val.startsWith("097") || val.startsWith("086") || val.startsWith("03")) {
      detectedCarrier = "Viettel";
    } else if (val.startsWith("091") || val.startsWith("094") || val.startsWith("088") || val.startsWith("08")) {
      detectedCarrier = "VinaPhone";
    }

    return { raw: val, formatted, carrier: detectedCarrier };
  };

  const handlePhoneChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { raw, formatted, carrier: detectedCarrier } = formatPhoneString(e.target.value);
    setPhone(raw);
    setFormattedPhone(formatted);
    setCarrier(detectedCarrier);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);

    if (!fullName.trim() || fullName.trim().length < 2) {
      setErrorMessage("Vui lòng nhập họ và tên của bạn.");
      return;
    }
    if (!phone || phone.length < 9) {
      setErrorMessage("Số điện thoại chưa đúng định dạng (tối thiểu 9-10 số).");
      return;
    }
    if (password.length < 6) {
      setErrorMessage("Mật khẩu tối thiểu 6 ký tự.");
      return;
    }
    if (password !== confirmPassword) {
      setErrorMessage("Mật khẩu xác nhận không khớp.");
      return;
    }
    if (!agreeTerms) {
      setErrorMessage("Vui lòng đồng ý với Điều khoản dịch vụ & Chính sách y tế.");
      return;
    }

    setIsSubmitting(true);
    const res = await register({
      fullName: fullName.trim(),
      phone,
      email: email.trim() || undefined,
      password,
    });
    setIsSubmitting(false);

    if (res.success) {
      setIsSuccess(true);
      setTimeout(() => {
        router.push("/account");
      }, 750);
    } else {
      setErrorMessage(res.error || "Đăng ký không thành công. Vui lòng kiểm tra lại thông tin.");
    }
  };

  const pwdStrength = getPasswordStrength(password);

  const containerVariants = {
    hidden: { opacity: 0 },
    visible: {
      opacity: 1,
      transition: { staggerChildren: 0.07, delayChildren: 0.12 },
    },
  };

  const itemVariants = {
    hidden: { opacity: 0, y: 12 },
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
            <span>MEMBER REGISTRATION • ENCLAVE</span>
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
              <div className="flex items-center justify-between gap-2 mb-3">
                <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-sky-50 border border-sky-200/80 text-sky-700 text-[11px] font-semibold tracking-wide">
                  <ShieldCheck className="w-3.5 h-3.5 text-sky-600" />
                  <span>Hội viên H4CARE</span>
                </div>
              </div>

              <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight bg-gradient-to-r from-slate-900 via-sky-950 to-blue-900 bg-clip-text text-transparent">
                Tạo tài khoản thành viên
              </h1>
              <p className="text-xs sm:text-sm text-slate-600 mt-1 leading-relaxed">
                Đăng ký tài khoản để theo dõi đơn thuốc, tích điểm và nhận tư vấn chuyên môn từ Dược sĩ.
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
                  <div className="flex-1">Đăng ký thành công! Đang chuyển hướng vào hồ sơ thành viên...</div>
                </motion.div>
              )}
            </AnimatePresence>

            <form onSubmit={handleSubmit} className="space-y-4">
              {/* Full name */}
              <motion.div variants={itemVariants}>
                <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                  Họ và tên của bạn
                </label>
                <div
                  className={`relative rounded-2xl bg-white/90 border transition-all duration-200 overflow-hidden ${
                    focusedField === "fullName"
                      ? "border-sky-500 ring-2 ring-sky-400/20 shadow-[0_0_20px_rgba(14,165,233,0.18)]"
                      : "border-sky-200/80 hover:border-sky-300"
                  }`}
                >
                  <input
                    type="text"
                    value={fullName}
                    onFocus={() => setFocusedField("fullName")}
                    onBlur={() => setFocusedField(null)}
                    onChange={(e) => setFullName(e.target.value)}
                    placeholder="Ví dụ: Nguyễn Văn An"
                    required
                    className="w-full px-4 py-3 pl-11 bg-transparent text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none font-medium"
                  />
                  <div
                    className={`absolute left-3.5 top-1/2 -translate-y-1/2 transition-colors duration-200 pointer-events-none ${
                      focusedField === "fullName" ? "text-sky-600" : "text-slate-400"
                    }`}
                  >
                    <User className="w-4 h-4" />
                  </div>
                </div>
              </motion.div>

              {/* Phone number */}
              <motion.div variants={itemVariants}>
                <div className="flex items-center justify-between mb-1.5">
                  <label className="text-xs font-semibold text-slate-700">Số điện thoại</label>
                  <span className="text-[10px] font-semibold text-sky-700 bg-sky-100/80 px-2 py-0.5 rounded-full border border-sky-200/60 font-mono">
                    {carrier}
                  </span>
                </div>
                <div
                  className={`relative rounded-2xl bg-white/90 border transition-all duration-200 overflow-hidden ${
                    focusedField === "phone"
                      ? "border-sky-500 ring-2 ring-sky-400/20 shadow-[0_0_20px_rgba(14,165,233,0.18)]"
                      : "border-sky-200/80 hover:border-sky-300"
                  }`}
                >
                  <input
                    type="tel"
                    value={formattedPhone}
                    onFocus={() => setFocusedField("phone")}
                    onBlur={() => setFocusedField(null)}
                    onChange={handlePhoneChange}
                    placeholder="0901 234 567"
                    required
                    className="w-full px-4 py-3 pl-11 bg-transparent text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none font-medium"
                  />
                  <div
                    className={`absolute left-3.5 top-1/2 -translate-y-1/2 transition-colors duration-200 pointer-events-none ${
                      focusedField === "phone" ? "text-sky-600" : "text-slate-400"
                    }`}
                  >
                    <Smartphone className="w-4 h-4" />
                  </div>
                </div>
              </motion.div>

              {/* Email */}
              <motion.div variants={itemVariants}>
                <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                  Email <span className="text-slate-400 font-normal">(không bắt buộc)</span>
                </label>
                <div
                  className={`relative rounded-2xl bg-white/90 border transition-all duration-200 overflow-hidden ${
                    focusedField === "email"
                      ? "border-sky-500 ring-2 ring-sky-400/20 shadow-[0_0_20px_rgba(14,165,233,0.18)]"
                      : "border-sky-200/80 hover:border-sky-300"
                  }`}
                >
                  <input
                    type="email"
                    value={email}
                    onFocus={() => setFocusedField("email")}
                    onBlur={() => setFocusedField(null)}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="nguyenvanan@example.com"
                    className="w-full px-4 py-3 pl-11 bg-transparent text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none font-medium"
                  />
                  <div
                    className={`absolute left-3.5 top-1/2 -translate-y-1/2 transition-colors duration-200 pointer-events-none ${
                      focusedField === "email" ? "text-sky-600" : "text-slate-400"
                    }`}
                  >
                    <Mail className="w-4 h-4" />
                  </div>
                </div>
              </motion.div>

              {/* Password */}
              <motion.div variants={itemVariants}>
                <label className="block text-xs font-semibold text-slate-700 mb-1.5 flex items-center justify-between">
                  <span>Mật khẩu</span>
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
                    placeholder="Tối thiểu 6 ký tự..."
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

                {/* Password strength */}
                {password && (
                  <div className="mt-2 flex items-center gap-2">
                    <div className="flex-1 grid grid-cols-4 gap-1 h-1.5 bg-slate-100 rounded-full overflow-hidden">
                      {[1, 2, 3, 4].map((step) => (
                        <div
                          key={step}
                          className={`h-full transition-colors ${
                            pwdStrength.score >= step ? pwdStrength.color : "bg-transparent"
                          }`}
                        />
                      ))}
                    </div>
                    <span className={`text-[11px] font-bold ${pwdStrength.textCol}`}>
                      {pwdStrength.text}
                    </span>
                  </div>
                )}
              </motion.div>

              {/* Confirm Password */}
              <motion.div variants={itemVariants}>
                <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                  Xác nhận mật khẩu
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
                    placeholder="Nhập lại mật khẩu..."
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

              {/* Terms checkbox */}
              <motion.div variants={itemVariants} className="pt-1">
                <label className="flex items-start gap-2.5 cursor-pointer select-none text-xs text-slate-600 leading-snug group">
                  <input
                    type="checkbox"
                    checked={agreeTerms}
                    onChange={(e) => setAgreeTerms(e.target.checked)}
                    className="w-4 h-4 mt-0.5 rounded border-sky-300 bg-white text-sky-600 focus:ring-sky-400/20"
                  />
                  <span className="group-hover:text-slate-800 transition-colors">
                    Tôi đồng ý với{" "}
                    <span className="text-sky-600 font-semibold">Điều khoản dịch vụ</span> &{" "}
                    <span className="text-sky-600 font-semibold">Chính sách bảo mật y tế</span>{" "}
                    của H4CARE.
                  </span>
                </label>
              </motion.div>

              <motion.div variants={itemVariants} className="pt-2">
                <LiquidMetalButton
                  type="submit"
                  variant="mercury"
                  isLoading={isSubmitting}
                  isSuccess={isSuccess}
                  disabled={isSubmitting || isSuccess}
                >
                  Đăng ký tài khoản
                </LiquidMetalButton>
              </motion.div>
            </form>

            <motion.div variants={itemVariants} className="mt-6 text-center text-xs text-slate-600">
              Đã có tài khoản thành viên?{" "}
              <Link
                href="/login"
                className="font-bold text-sky-600 hover:text-sky-800 hover:underline transition-colors"
              >
                Đăng nhập tại đây
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
