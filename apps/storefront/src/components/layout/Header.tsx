"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { H4CareLogo } from "../branding/H4CareLogo";
import { FptPolyBadge } from "../branding/FptPolyBadge";
import { MegaMenu } from "./MegaMenu";
import { SearchExperience } from "./SearchExperience";
import { MobileDrawer } from "./MobileDrawer";
import { MobileBottomNav } from "./MobileBottomNav";
import {
  LayoutGrid,
  Stethoscope,
  ShoppingBag,
  User,
  ChevronDown,
  Menu,
  ShieldCheck,
  RotateCcw,
  Search,
  LogOut,
  FileText,
  UserCheck,
} from "lucide-react";
import { useAuth } from "@/lib/auth/auth-context";
import { LiveClock } from "../common/LiveClock";
import { redirectToAdminPortal } from "@/lib/auth/admin-redirect";
import { PHARMACY_CONTACT } from "@/lib/constants";

interface HeaderProps {
  onReplayIntro?: () => void;
}

export const Header: React.FC<HeaderProps> = ({ onReplayIntro }) => {
  const { user, isAuthenticated, logout } = useAuth();
  const [isScrolled, setIsScrolled] = useState(false);
  const [isMegaMenuOpen, setIsMegaMenuOpen] = useState(false);
  const [isMobileDrawerOpen, setIsMobileDrawerOpen] = useState(false);
  const [isMobileSearchOpen, setIsMobileSearchOpen] = useState(false);
  const [isAccountDropdownOpen, setIsAccountDropdownOpen] = useState(false);
  const [cartCount, setCartCount] = useState(0);


  useEffect(() => {
    const updateCartCount = () => {
      try {
        const raw = localStorage.getItem("pharmatrust_cart");
        if (raw) {
          const parsed = JSON.parse(raw);
          if (Array.isArray(parsed)) {
            const count = parsed.reduce((sum: number, item: any) => sum + (item.quantity || 1), 0);
            setCartCount(count);
            return;
          }
        }
      } catch (e) {}
      setCartCount(0);
    };

    updateCartCount();
    window.addEventListener("cart_updated", updateCartCount);
    window.addEventListener("storage", updateCartCount);

    const handleScroll = () => {
      if (window.scrollY > 15) {
        setIsScrolled(true);
      } else {
        setIsScrolled(false);
      }
    };

    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => {
      window.removeEventListener("scroll", handleScroll);
      window.removeEventListener("cart_updated", updateCartCount);
      window.removeEventListener("storage", updateCartCount);
    };
  }, []);

  return (
    <>
      {/* Top Academic & Medical Trust Bar - Sleek & Secondary */}
      <div className="bg-slate-900 text-slate-300 text-[11px] py-1.5 px-4 hidden md:block border-b border-slate-800 select-none">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <FptPolyBadge variant="dark" />
            <span className="text-slate-700">/</span>
            <div className="flex items-center gap-1.5 text-slate-300">
              <ShieldCheck className="w-3.5 h-3.5 text-brand-emerald-400" />
              <span>Hệ thống Dược phẩm H4CARE • Định hướng chuẩn GPP & GSP</span>
            </div>
          </div>

          <div className="flex items-center gap-4">
            <LiveClock />
            <Link
              href="/prescription"
              className="flex items-center gap-1.5 text-cyan-300 hover:text-white font-semibold transition-colors cursor-pointer"
              title="Tư vấn Dược sĩ chuyên môn trực tuyến"
            >
              <Stethoscope className="w-3.5 h-3.5 text-cyan-400" />
              <span>{PHARMACY_CONTACT.consultationPhoneDisplay}</span>
            </Link>

            {onReplayIntro && (
              <button
                onClick={onReplayIntro}
                className="flex items-center gap-1 text-slate-400 hover:text-white transition-colors cursor-pointer text-[10.5px]"
                title="Xem lại hiệu ứng mở đầu"
              >
                <RotateCcw className="w-2.5 h-2.5" />
                <span>Xem Intro</span>
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Main Sticky Header with Balanced Depth */}
      <header
        className={`sticky top-0 z-40 transition-all duration-200 bg-white/98 backdrop-blur-md ${
          isScrolled
            ? "shadow-depth-2 py-2 border-b border-slate-200"
            : "py-2.5 sm:py-3 border-b border-slate-200/80"
        }`}
      >
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between gap-3 md:gap-5">
            {/* Mobile Menu Button */}
            <button
              onClick={() => setIsMobileDrawerOpen(true)}
              className="p-2 -ml-2 rounded-xl text-slate-700 hover:bg-slate-100 lg:hidden focus:outline-none transition-colors"
              aria-label="Mở menu di động"
            >
              <Menu className="w-5 h-5" />
            </button>

            {/* H4CARE Primary Brand Identity */}
            <div className="shrink-0 flex items-center">
              <H4CareLogo size={isScrolled ? "sm" : "md"} withTagline={!isScrolled} />
            </div>

            {/* Mega Menu Button (Desktop) */}
            <div className="hidden lg:block relative shrink-0">
              <button
                onClick={() => setIsMegaMenuOpen(!isMegaMenuOpen)}
                aria-expanded={isMegaMenuOpen}
                className={`flex items-center gap-2 px-3.5 py-2.5 rounded-xl font-bold text-xs sm:text-[13px] transition-all duration-150 active:scale-95 ${
                  isMegaMenuOpen
                    ? "bg-brand-blue-600 text-white shadow-depth-1 border border-brand-blue-600"
                    : "bg-slate-50 hover:bg-slate-100 text-slate-800 border border-slate-200"
                }`}
              >
                <LayoutGrid className={`w-4 h-4 ${isMegaMenuOpen ? "text-white" : "text-brand-blue-600"}`} />
                <span>Danh mục thuốc</span>
                <ChevronDown
                  className={`w-3.5 h-3.5 text-slate-400 transition-transform duration-200 ${
                    isMegaMenuOpen ? "rotate-180 text-white" : ""
                  }`}
                />
              </button>
            </div>

            {/* Central Interactive Search (Desktop & Tablet) - Long Châu prominent bar (680px - 900px) */}
            <div className="flex-1 max-w-3xl xl:max-w-4xl hidden md:block mx-2 lg:mx-4">
              <SearchExperience />
            </div>

            {/* Right Action Navigation */}
            <div className="flex items-center gap-2 sm:gap-2.5 shrink-0">

              {/* Consultation Hotline Pill - Minimalist on xl */}
              <Link
                href="/prescription"
                className="hidden xl:flex items-center gap-2 px-3 py-2 rounded-xl border border-cyan-200 bg-cyan-50/50 hover:bg-cyan-100/60 text-slate-800 transition-all duration-150 cursor-pointer"
                title="Gửi yêu cầu tư vấn Dược sĩ chuyên môn"
              >
                <div className="w-6 h-6 rounded-lg bg-cyan-100 text-cyan-700 flex items-center justify-center shrink-0">
                  <Stethoscope className="w-3.5 h-3.5" />
                </div>
                <div className="text-left leading-none">
                  <span className="text-[10px] text-slate-500 block font-normal">Dược sĩ chuyên môn</span>
                  <span className="text-xs font-bold text-slate-900">
                    Tư vấn trực tuyến
                  </span>
                </div>
              </Link>

              {/* Admin & Crawler Portal Quick Access Button */}
              {user?.isAdmin ? (
                <button
                  type="button"
                  onClick={() => redirectToAdminPortal()}
                  className="hidden lg:flex items-center gap-1.5 px-3 py-2 rounded-xl border border-brand-blue-600 bg-brand-blue-600 hover:bg-brand-blue-700 text-white text-xs font-bold transition-all shadow-sm"
                  title="Mở Cổng Quản Trị Hệ Thống"
                >
                  <ShieldCheck className="w-3.5 h-3.5 text-white" />
                  <span>Cổng Admin</span>
                </button>
              ) : (
                <Link
                  href="/admin"
                  className="hidden lg:flex items-center gap-1.5 px-3 py-2 rounded-xl border border-brand-blue-200 bg-brand-blue-50/80 hover:bg-brand-blue-100 text-brand-blue-700 text-xs font-bold transition-all"
                  title="Vào khu vực Quản trị & Cào dữ liệu thuốc (Admin Portal)"
                >
                  <ShieldCheck className="w-3.5 h-3.5 text-brand-blue-600" />
                  <span>Quản Trị / Cào Thuốc</span>
                </Link>
              )}

              {/* Account Trigger: User profile or Login */}
              {isAuthenticated && user ? (
                <div className="relative">
                  <button
                    onClick={() => setIsAccountDropdownOpen(!isAccountDropdownOpen)}
                    className="hidden sm:flex items-center gap-2 p-1.5 sm:px-2.5 sm:py-1.5 rounded-xl hover:bg-slate-100 text-slate-800 transition-colors border border-slate-200 bg-white"
                  >
                    <div className="w-7 h-7 rounded-lg bg-brand-blue-600 text-white flex items-center justify-center font-bold text-xs shadow-xs">
                      {user.fullName ? user.fullName.charAt(0).toUpperCase() : "U"}
                    </div>
                    <div className="hidden xl:block text-left leading-tight">
                      <span className="text-[10px] text-slate-400 block font-normal">{user.role || "Hội viên"}</span>
                      <span className="text-xs font-bold text-slate-900 line-clamp-1 max-w-[120px]">{user.fullName}</span>
                    </div>
                    <ChevronDown className="w-3.5 h-3.5 text-slate-400" />
                  </button>

                  {/* Dropdown Menu */}
                  {isAccountDropdownOpen && (
                    <div
                      className="absolute right-0 mt-2 w-64 bg-white rounded-2xl shadow-xl border border-slate-200 py-2 z-50 animate-in fade-in zoom-in-95 duration-150"
                      onMouseLeave={() => setIsAccountDropdownOpen(false)}
                    >
                      <div className="px-4 py-2.5 border-b border-slate-100">
                        <p className="text-xs font-bold text-slate-900">{user.fullName}</p>
                        <p className="text-[11px] text-slate-500">{user.phone || user.email}</p>
                        <span className="inline-block mt-1 px-2 py-0.5 rounded bg-blue-50 text-brand-blue-700 text-[10px] font-bold border border-blue-100">
                          {user.role} • {user.points || 0} điểm
                        </span>
                      </div>

                      {user.isAdmin && (
                        <div className="py-1 border-b border-slate-100 bg-blue-50/50">
                          <button
                            type="button"
                            onClick={() => {
                              setIsAccountDropdownOpen(false);
                              redirectToAdminPortal("", true);
                            }}
                            className="w-full text-left flex items-center gap-2 px-4 py-2 text-brand-blue-700 hover:bg-blue-100/70 font-bold text-xs"
                          >
                            <ShieldCheck className="w-4 h-4 text-brand-blue-600" />
                            <span>Cổng Quản Trị Hệ Thống (Tab Mới)</span>
                          </button>
                          <Link
                            href="/admin"
                            onClick={() => setIsAccountDropdownOpen(false)}
                            className="flex items-center gap-2 px-4 py-1.5 text-slate-600 hover:bg-slate-100 font-medium text-[11px]"
                          >
                            <span className="w-4" />
                            <span>Admin Portal nội bộ</span>
                          </Link>
                        </div>
                      )}

                      <div className="py-1 text-xs text-slate-700">
                        <Link
                          href="/account"
                          onClick={() => setIsAccountDropdownOpen(false)}
                          className="flex items-center gap-2 px-4 py-2 hover:bg-slate-50 font-medium"
                        >
                          <UserCheck className="w-4 h-4 text-slate-500" />
                          <span>Hồ sơ thành viên</span>
                        </Link>
                        <Link
                          href="/account#orders"
                          onClick={() => setIsAccountDropdownOpen(false)}
                          className="flex items-center gap-2 px-4 py-2 hover:bg-slate-50 font-medium"
                        >
                          <FileText className="w-4 h-4 text-slate-500" />
                          <span>Đơn thuốc & Lịch sử mua hàng</span>
                        </Link>
                      </div>

                      <div className="pt-1 border-t border-slate-100">
                        <button
                          onClick={() => {
                            logout();
                            setIsAccountDropdownOpen(false);
                          }}
                          className="w-full flex items-center gap-2 px-4 py-2 text-xs text-rose-600 hover:bg-rose-50 font-bold transition-colors"
                        >
                          <LogOut className="w-4 h-4" />
                          <span>Đăng xuất tài khoản</span>
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <Link
                  href="/login"
                  className="hidden sm:flex items-center gap-2 p-2 rounded-xl text-slate-700 hover:bg-slate-100 transition-colors"
                  title="Đăng nhập / Đăng ký"
                >
                  <div className="w-8 h-8 rounded-xl bg-slate-100 flex items-center justify-center border border-slate-200/80 text-slate-600 hover:text-brand-blue-600">
                    <User className="w-4 h-4" />
                  </div>
                  <div className="hidden 2xl:block text-left leading-none">
                    <span className="text-[10px] text-slate-400 block font-normal">Thành viên</span>
                    <span className="text-xs font-bold text-slate-800">Tài khoản</span>
                  </div>
                </Link>
              )}

              {/* Cart Button with Count Badge */}
              <Link
                href="/cart"
                aria-label="Giỏ hàng"
                title="Giỏ hàng H4CARE"
                className="relative flex items-center gap-2 px-2.5 sm:px-3.5 py-2 rounded-xl bg-brand-blue-50/80 hover:bg-brand-blue-100/90 text-brand-blue-700 border border-brand-blue-200/80 transition-all duration-150 group active:scale-95 shadow-2xs"
              >
                <div className="relative flex items-center justify-center">
                  <ShoppingBag className="w-4.5 h-4.5 text-brand-blue-600 group-hover:scale-105 transition-transform duration-150 shrink-0" />
                  {cartCount > 0 && (
                    <span className="sm:hidden absolute -top-2 -right-2 min-w-[16px] h-4 px-1 rounded-full bg-rose-500 text-white text-[9px] font-bold flex items-center justify-center ring-2 ring-white">
                      {cartCount > 99 ? "99+" : cartCount}
                    </span>
                  )}
                </div>
                <span className="hidden sm:inline font-semibold text-slate-800 text-xs">
                  Giỏ hàng
                </span>
                {cartCount > 0 && (
                  <span className="hidden sm:inline-flex min-w-[18px] h-[18px] px-1.5 rounded-full bg-brand-blue-600 text-white text-[10px] font-bold items-center justify-center shadow-xs">
                    {cartCount > 99 ? "99+" : cartCount}
                  </span>
                )}
              </Link>
            </div>
          </div>

          {/* Dedicated Mobile Search Bar Row (Clean, prominent, Long Châu style on mobile) */}
          <div className="pt-2 pb-0.5 md:hidden">
            <SearchExperience />
          </div>
        </div>

        {/* Mega Menu Popover */}
        <MegaMenu isOpen={isMegaMenuOpen} onClose={() => setIsMegaMenuOpen(false)} />
      </header>

      {/* Mobile Drawer Menu */}
      <MobileDrawer
        isOpen={isMobileDrawerOpen}
        onClose={() => setIsMobileDrawerOpen(false)}
      />

      {/* Mobile Search Modal Popover */}
      {isMobileSearchOpen && (
        <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-sm p-4 pt-16 md:hidden">
          <div className="bg-white rounded-3xl p-4 shadow-depth-4">
            <div className="flex items-center justify-between pb-3 mb-2 border-b border-slate-100">
              <span className="text-sm font-bold text-slate-900">Tìm kiếm thuốc & thiết bị y tế</span>
              <button
                onClick={() => setIsMobileSearchOpen(false)}
                className="p-1 rounded-lg text-slate-400 hover:text-slate-700"
              >
                Đóng
              </button>
            </div>
            <SearchExperience
              isMobileModal={true}
              onCloseMobileModal={() => setIsMobileSearchOpen(false)}
            />
          </div>
        </div>
      )}

      {/* Mobile Bottom Navigation */}
      <MobileBottomNav
        onOpenCategories={() => setIsMobileDrawerOpen(true)}
        onOpenSearch={() => setIsMobileSearchOpen(true)}
      />
    </>
  );
};
