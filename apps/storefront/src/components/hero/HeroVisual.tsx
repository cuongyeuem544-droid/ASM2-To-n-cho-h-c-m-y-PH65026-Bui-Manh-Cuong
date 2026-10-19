"use client";

import React, { useState, useRef, useEffect } from "react";
import { motion, useMotionValue, useSpring, useTransform } from "framer-motion";
import {
  ShieldCheck,
  Star,
  CheckCircle2,
  Stethoscope,
  Sparkles,
  ThermometerSnowflake,
  Clock,
  Pill,
} from "lucide-react";
import { AbstractSymbol } from "../branding/AbstractSymbol";

export const HeroVisual: React.FC = () => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [isHovered, setIsHovered] = useState(false);
  const [isTouchOrReduced, setIsTouchOrReduced] = useState(false);

  useEffect(() => {
    const checkCapabilities = () => {
      const isTouch =
        "ontouchstart" in window ||
        navigator.maxTouchPoints > 0 ||
        window.innerWidth < 1024;
      const prefersReduced = window.matchMedia(
        "(prefers-reduced-motion: reduce)"
      ).matches;
      setIsTouchOrReduced(isTouch || prefersReduced);
    };
    checkCapabilities();
    window.addEventListener("resize", checkCapabilities);
    return () => window.removeEventListener("resize", checkCapabilities);
  }, []);

  // Smooth mouse tilt physics for desktop
  const x = useMotionValue(0);
  const y = useMotionValue(0);

  const mouseXSpring = useSpring(x, { stiffness: 150, damping: 20 });
  const mouseYSpring = useSpring(y, { stiffness: 150, damping: 20 });

  const rotateX = useTransform(mouseYSpring, [-0.5, 0.5], ["6deg", "-6deg"]);
  const rotateY = useTransform(mouseXSpring, [-0.5, 0.5], ["-6deg", "6deg"]);

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (isTouchOrReduced || !containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    const width = rect.width;
    const height = rect.height;
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;

    const xPct = mouseX / width - 0.5;
    const yPct = mouseY / height - 0.5;

    x.set(xPct);
    y.set(yPct);
  };

  const handleMouseLeave = () => {
    x.set(0);
    y.set(0);
    setIsHovered(false);
  };

  return (
    <div
      ref={containerRef}
      onMouseMove={handleMouseMove}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={handleMouseLeave}
      className="relative w-full max-w-[340px] xs:max-w-[380px] sm:max-w-[480px] lg:max-w-[520px] aspect-square flex items-center justify-center select-none perspective-[1200px]"
    >
      {/* Background Layer 1: Ambient Studio Glow Atmosphere */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[340px] h-[340px] bg-gradient-to-tr from-brand-blue-400/20 via-brand-cyan-300/25 to-brand-emerald-300/20 rounded-full blur-[80px] pointer-events-none" />
      <div className="absolute -top-6 -right-6 w-48 h-48 bg-cyan-200/25 rounded-full blur-[60px] pointer-events-none" />
      <div className="absolute -bottom-6 -left-6 w-48 h-48 bg-blue-300/20 rounded-full blur-[60px] pointer-events-none" />

      {/* Main 3D Art-Directed Stage */}
      <motion.div
        style={{
          rotateX: isTouchOrReduced ? 0 : rotateX,
          rotateY: isTouchOrReduced ? 0 : rotateY,
          transformStyle: "preserve-3d",
        }}
        className="relative w-full h-full rounded-[28px] p-5 sm:p-7 bg-white border border-slate-200 shadow-depth-3 transition-shadow duration-300 hover:shadow-depth-4 flex flex-col justify-between overflow-hidden"
      >
        {/* Subtle Decorative Ambient Lighting Sheen inside Card */}
        <div className="absolute -top-32 -left-32 w-64 h-64 bg-slate-50 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute bottom-0 right-0 w-48 h-48 bg-blue-50/50 rounded-full blur-2xl pointer-events-none" />

        {/* Top Product Header Row */}
        <div className="relative z-10 flex items-center justify-between pb-3 border-b border-slate-100">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-xl bg-brand-blue-600 text-white flex items-center justify-center shadow-xs">
              <AbstractSymbol size={18} />
            </div>
            <div>
              <span className="text-[11px] font-black text-slate-900 tracking-wider block leading-none">
                H4CARE PHARMACY
              </span>
              <span className="text-[10px] text-slate-400 font-medium">
                Hệ Thống Dược Trực Tuyến
              </span>
            </div>
          </div>

          <div className="flex items-center gap-1.5 bg-emerald-50/90 border border-emerald-200/70 px-2.5 py-1 rounded-full">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
            <span className="text-[10px] font-bold text-emerald-700">
              Mô hình chuẩn GPP
            </span>
          </div>
        </div>

        {/* Central Visual Showcase: Realistic Pharmaceutical Packaging Composition */}
        <div className="relative z-10 my-auto py-2 flex flex-col items-center justify-center">
          {/* Studio Podium Base Shadow */}
          <div className="absolute w-72 sm:w-80 h-32 bg-gradient-to-b from-blue-100/40 via-slate-100/30 to-transparent rounded-[100%] blur-md -bottom-2 pointer-events-none" />

          {/* Composition Container */}
          <div className="relative flex items-end justify-center gap-3 sm:gap-5 pt-3 pb-2">
            {/* Primary Product: Realistic Medicine Bottle Packaging */}
            <motion.div
              animate={isTouchOrReduced ? {} : { y: [0, -3, 0] }}
              transition={{ duration: 5, repeat: Infinity, ease: "easeInOut" }}
              className="relative w-36 sm:w-44 h-56 sm:h-64 rounded-[26px] bg-gradient-to-r from-slate-950 via-[#0a2240] to-slate-950 p-3 sm:p-3.5 shadow-2xl border border-white/20 flex flex-col justify-between text-white overflow-hidden group shrink-0"
              style={{ transform: "translateZ(35px)" }}
            >
              {/* Glass Specular Reflection Highlight Strip */}
              <div className="absolute top-0 left-2.5 w-1 h-full bg-gradient-to-b from-white/35 via-white/10 to-transparent rounded-full opacity-60 pointer-events-none" />
              <div className="absolute -top-10 -right-10 w-24 h-24 bg-brand-cyan-400/15 rounded-full blur-lg pointer-events-none" />

              {/* Realistic Ribbed Medicine Safety Cap */}
              <div className="relative mx-auto -mt-1 flex flex-col items-center z-10">
                <div
                  className="w-14 sm:w-16 h-4 rounded-t-md shadow-md border-b border-slate-700/80"
                  style={{
                    background:
                      "repeating-linear-gradient(90deg, #334155 0px, #334155 2px, #64748b 2px, #64748b 4px)",
                  }}
                />
                <div className="w-16 sm:w-18 h-1.5 bg-slate-300 rounded-sm shadow-sm" />
              </div>

              {/* Medicine Packaging Center Prescription Label */}
              <div className="my-auto bg-white/98 backdrop-blur-md rounded-xl p-2.5 sm:p-3 text-slate-900 shadow-md border border-slate-100 z-10">
                {/* Brand & Micro-badge */}
                <div className="flex items-center justify-between pb-1 mb-1 border-b border-slate-100">
                  <span className="text-[8.5px] font-black tracking-wider text-brand-blue-700 uppercase">
                    H4CARE Pharmacy
                  </span>
                  <Pill className="w-2.5 h-2.5 text-brand-emerald-500" />
                </div>

                {/* Formula Name */}
                <p className="text-xs sm:text-[13px] font-black text-slate-900 leading-tight">
                  Formula No. 04
                </p>
                <p className="text-[8.5px] text-slate-500 font-medium mt-0.5 leading-snug">
                  Phức hợp vi chất tự nhiên
                </p>

                {/* Packaging Count & Specs */}
                <div className="mt-2 pt-1 border-t border-dashed border-slate-200 flex items-center justify-between">
                  <span className="text-[8px] font-semibold text-slate-700 bg-slate-100 px-1.5 py-0.5 rounded">
                    60 Viên nang
                  </span>
                  <span className="text-[8px] font-bold text-emerald-600">
                    Định hướng GPP
                  </span>
                </div>

                {/* Barcode Strip & LOT */}
                <div className="mt-1.5 pt-1 border-t border-slate-100 flex items-center justify-between text-[7.5px] font-mono text-slate-400">
                  <div className="flex items-center gap-0.5 h-2.5 opacity-60">
                    <span className="w-0.5 h-full bg-slate-800" />
                    <span className="w-1 h-full bg-slate-800" />
                    <span className="w-0.5 h-full bg-slate-800" />
                    <span className="w-1.5 h-full bg-slate-800" />
                    <span className="w-0.5 h-full bg-slate-800" />
                    <span className="w-1 h-full bg-slate-800" />
                  </div>
                  <span>LOT: 2026-H4</span>
                </div>
              </div>

              {/* Bottle Bottom Security Seal */}
              <div className="flex items-center justify-between text-[8.5px] text-slate-400 px-1 font-mono z-10">
                <span>SEALED</span>
                <span className="text-cyan-300 font-semibold">GSP 25°C</span>
              </div>
            </motion.div>

            {/* Secondary Product: Realistic Clinical Blister Card */}
            <motion.div
              animate={isTouchOrReduced ? {} : { y: [0, 3, 0] }}
              transition={{
                duration: 5.5,
                repeat: Infinity,
                ease: "easeInOut",
                delay: 0.5,
              }}
              className="relative w-28 sm:w-34 h-44 sm:h-50 rounded-2xl bg-gradient-to-br from-slate-50 via-white to-slate-100 p-2.5 shadow-xl border border-slate-200/90 flex flex-col justify-between shrink-0"
              style={{ transform: "translateZ(45px)" }}
            >
              {/* Blister Card Header */}
              <div className="flex items-center justify-between pb-1 border-b border-slate-100">
                <div className="flex items-center gap-1">
                  <ShieldCheck className="w-3 h-3 text-brand-blue-600" />
                  <span className="text-[8.5px] font-extrabold text-slate-800">
                    Toa Hỗ Trợ
                  </span>
                </div>
                <span className="text-[8px] font-mono text-slate-400">10 Viên</span>
              </div>

              {/* Realistic Blister Pockets (4 Capsules) */}
              <div className="grid grid-cols-2 gap-1.5 my-1">
                {[...Array(4)].map((_, i) => (
                  <div
                    key={i}
                    className="h-8 rounded-xl bg-gradient-to-br from-slate-100 to-blue-50/70 border border-slate-200 flex items-center justify-center shadow-inner relative overflow-hidden"
                  >
                    {/* Embedded Dual-Tone Capsule */}
                    <div className="w-6 h-2.5 rounded-full bg-gradient-to-r from-brand-blue-600 to-brand-cyan-400 shadow-sm flex items-center justify-between p-0.5">
                      <div className="w-1/2 h-full bg-brand-blue-700 rounded-l-full" />
                      <div className="w-1/2 h-full bg-brand-cyan-400 rounded-r-full" />
                    </div>
                    {/* Blister Dome Specular Highlight */}
                    <div className="absolute top-1 left-2 w-2 h-1 rounded-full bg-white/70" />
                  </div>
                ))}
              </div>

              {/* Blister Bottom Verification Stamp */}
              <div className="bg-slate-100/80 rounded-lg p-1 text-center border border-slate-200/60">
                <span className="text-[8px] font-bold text-slate-700 block leading-tight">
                  Kiểm tra tương tác
                </span>
                <span className="text-[7.5px] text-emerald-600 font-semibold">
                  Đã xác nhận
                </span>
              </div>
            </motion.div>
          </div>

          {/* Contact Ground Shadow directly under products */}
          <div className="w-48 sm:w-56 h-3 bg-slate-900/10 rounded-full blur-sm mx-auto -mt-1" />
        </div>

        {/* Floating Badge 1: Pharmacist Consultation (Positioned at Top-Right perimeter, unobstructed) */}
        <motion.div
          animate={isTouchOrReduced ? {} : { y: [0, -4, 0] }}
          transition={{ duration: 4, repeat: Infinity, ease: "easeInOut" }}
          style={{ transform: "translateZ(55px)" }}
          className="absolute top-2 -right-1 sm:-right-3 bg-white rounded-xl p-2 sm:p-2.5 shadow-depth-2 border border-slate-200 flex items-center gap-2 sm:gap-2.5 z-20"
        >
          <div className="relative">
            <div className="w-7 h-7 sm:w-8 sm:h-8 rounded-lg bg-brand-blue-50 text-brand-blue-600 flex items-center justify-center shrink-0 border border-brand-blue-100">
              <Stethoscope className="w-3.5 h-3.5" />
            </div>
            <span className="absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full bg-emerald-500 ring-2 ring-white animate-pulse" />
          </div>
          <div>
            <p className="text-[10px] sm:text-[10.5px] font-bold text-slate-800 leading-tight">
              Tư vấn Dược sĩ
            </p>
            <p className="text-[9px] sm:text-[9.5px] text-brand-blue-600 font-semibold">
              Hướng dẫn dùng thuốc 1-1
            </p>
          </div>
        </motion.div>

        {/* Floating Badge 2: Certified Cold Storage (Positioned at Bottom-Left perimeter, unobstructed) */}
        <motion.div
          animate={isTouchOrReduced ? {} : { y: [0, 4, 0] }}
          transition={{
            duration: 4.5,
            repeat: Infinity,
            ease: "easeInOut",
            delay: 0.8,
          }}
          style={{ transform: "translateZ(65px)" }}
          className="absolute bottom-9 -left-1 sm:-left-3 bg-white rounded-xl p-2 sm:p-2.5 shadow-depth-2 border border-slate-200 flex items-center gap-2 sm:gap-2.5 z-20"
        >
          <div className="w-7 h-7 sm:w-8 sm:h-8 rounded-lg bg-cyan-50 text-cyan-700 flex items-center justify-center shrink-0 border border-cyan-100">
            <ThermometerSnowflake className="w-3.5 h-3.5" />
          </div>
          <div>
            <p className="text-[10px] sm:text-[10.5px] font-bold text-slate-800 leading-tight">
              Quy trình GSP
            </p>
            <p className="text-[9px] sm:text-[9.5px] text-slate-500 font-medium">
              Bảo quản tiêu chuẩn an toàn
            </p>
          </div>
        </motion.div>

        {/* Bottom Social Proof & Purity Assurance */}
        <div className="relative z-10 pt-3 border-t border-slate-100/80 flex items-center justify-between text-xs text-slate-600">
          <div className="flex items-center gap-1.5">
            <div className="flex text-amber-400">
              {[...Array(5)].map((_, i) => (
                <Star key={i} className="w-3 h-3 fill-current" />
              ))}
            </div>
            <span className="font-bold text-slate-800 text-[11px]">4.9/5</span>
            <span className="text-slate-400 text-[10px]">
              (Đánh giá trải nghiệm)
            </span>
          </div>

          <div className="flex items-center gap-1 text-[11px] font-semibold text-brand-blue-600">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
            <span>Nguồn gốc rõ ràng</span>
          </div>
        </div>
      </motion.div>
    </div>
  );
};
