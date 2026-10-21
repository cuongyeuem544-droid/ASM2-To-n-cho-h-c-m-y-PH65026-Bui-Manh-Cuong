"use client";

import React, { createContext, useContext, useState, useEffect } from "react";
import { AuthUser, AuthContextType, RegisterFormState } from "@/types/auth";

const AuthContext = createContext<AuthContextType | undefined>(undefined);

const STORAGE_KEY = "h4care_auth_session";
import { API_BASE } from "@/lib/api-config";

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  // Initialize session from localStorage on mount (SSR safe)
  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        setUser(JSON.parse(stored));
      }
    } catch (e) {
      console.warn("Failed to read auth session from storage", e);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const saveSession = (userData: AuthUser) => {
    setUser(userData);
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(userData));
    } catch (e) {
      console.warn("Failed to persist auth session", e);
    }
  };

  const sendPhoneOtp = async (phone: string): Promise<{ success: boolean; error?: string }> => {
    const cleanPhone = phone.trim().replace(/\s+/g, "").replace(/-/g, "");
    if (!cleanPhone || cleanPhone.length < 9) {
      return { success: false, error: "Số điện thoại chưa hợp lệ (tối thiểu 9-10 chữ số)." };
    }
    try {
      const res = await fetch(`${API_BASE}/api/v1/auth/otp/request`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ identifier: cleanPhone, purpose: "LOGIN" }),
      });
      if (res.ok) {
        return { success: true };
      }
      const data = await res.json().catch(() => ({}));
      return { success: false, error: data.detail || "Không thể gửi mã xác thực OTP. Vui lòng thử lại sau." };
    } catch (e) {
      return {
        success: false,
        error: "Không thể kết nối đến máy chủ H4CARE. Vui lòng kiểm tra kết nối mạng và thử lại.",
      };
    }
  };

  const loginWithPhone = async (
    phone: string,
    otp: string
  ): Promise<{ success: boolean; error?: string; user?: AuthUser }> => {
    const cleanPhone = phone.trim().replace(/\s+/g, "").replace(/-/g, "");
    const cleanOtp = otp.trim();

    if (!cleanOtp || cleanOtp.length < 6) {
      return { success: false, error: "Vui lòng nhập đầy đủ 6 chữ số mã xác thực OTP." };
    }

    try {
      const res = await fetch(`${API_BASE}/api/v1/auth/otp/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ phone: cleanPhone, otp: cleanOtp }),
      });

      if (res.ok) {
        const data = await res.json();
        const rawRole = String(data.user?.role || "CUSTOMER").toUpperCase();
        const isAdmin = rawRole === "ADMIN";
        const isWarehouseManager = rawRole === "WAREHOUSE_MANAGER";
        const isWarehouseStaff = rawRole === "WAREHOUSE_STAFF";
        const authUser: AuthUser = {
          id: data.user?.id || `usr_${cleanPhone}`,
          fullName: data.user?.full_name || `Khách hàng ${cleanPhone.slice(-4)}`,
          phone: data.user?.phone || cleanPhone,
          email: data.user?.email || `${cleanPhone}@customer.pharmatrust.vn`,
          role: isAdmin
            ? "Quản trị viên"
            : isWarehouseManager
            ? "Quản lý kho"
            : isWarehouseStaff
            ? "Nhân viên kho"
            : "Hội viên Thân thiết",
          roleCode: rawRole,
          isAdmin,
          isWarehouseManager,
          isWarehouseStaff,
          points: data.user?.loyalty_points ?? (isAdmin ? 9999 : 50),
          createdAt: data.user?.created_at?.split("T")[0] || new Date().toISOString().split("T")[0],
        };
        if (data.access_token) {
          localStorage.setItem("pharmatrust_access_token", data.access_token);
          if (data.refresh_token) localStorage.setItem("pharmatrust_refresh_token", data.refresh_token);
        }
        saveSession(authUser);
        return { success: true, user: authUser };
      } else {
        const errData = await res.json().catch(() => ({}));
        return {
          success: false,
          error: errData.detail || "Mã OTP không chính xác hoặc đã hết hạn.",
        };
      }
    } catch (e) {
      return {
        success: false,
        error: "Không thể kết nối đến máy chủ xác thực. Vui lòng kiểm tra lại backend.",
      };
    }
  };

  const loginWithPassword = async (
    identifier: string,
    password: string
  ): Promise<{ success: boolean; error?: string; user?: AuthUser }> => {
    const cleanId = identifier.trim();
    if (!cleanId) {
      return { success: false, error: "Vui lòng nhập Email hoặc Số điện thoại." };
    }
    if (!password || password.length < 6) {
      return { success: false, error: "Mật khẩu tối thiểu 6 ký tự." };
    }

    try {
      const res = await fetch(`${API_BASE}/api/v1/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ identifier: cleanId, password }),
      });

      if (res.ok) {
        const data = await res.json();
        const rawRole = String(data.user?.role || "CUSTOMER").toUpperCase();
        const isAdmin = rawRole === "ADMIN";
        const isWarehouseManager = rawRole === "WAREHOUSE_MANAGER";
        const isWarehouseStaff = rawRole === "WAREHOUSE_STAFF";
        const authUser: AuthUser = {
          id: data.user?.id || Date.now(),
          fullName: data.user?.full_name || (isAdmin ? "Quản trị viên" : isWarehouseManager ? "Quản lý kho" : isWarehouseStaff ? "Nhân viên kho" : cleanId),
          phone: data.user?.phone || (cleanId.includes("@") ? "" : cleanId),
          email: data.user?.email || (cleanId.includes("@") ? cleanId : ""),
          role: isAdmin
            ? "Quản trị viên"
            : isWarehouseManager
            ? "Quản lý kho"
            : isWarehouseStaff
            ? "Nhân viên kho"
            : "Hội viên Thân thiết",
          roleCode: rawRole,
          isAdmin,
          isWarehouseManager,
          isWarehouseStaff,
          points: data.user?.loyalty_points ?? (isAdmin ? 9999 : 50),
          createdAt: data.user?.created_at?.split("T")[0] || new Date().toISOString().split("T")[0],
        };

        if (data.access_token) {
          localStorage.setItem("pharmatrust_access_token", data.access_token);
          if (data.refresh_token) localStorage.setItem("pharmatrust_refresh_token", data.refresh_token);
        }

        saveSession(authUser);
        return { success: true, user: authUser };
      } else {
        const errData = await res.json().catch(() => ({}));
        return {
          success: false,
          error: errData.detail || "Thông tin đăng nhập không chính xác. Vui lòng thử lại.",
        };
      }
    } catch (e) {
      return {
        success: false,
        error: "Không thể kết nối đến máy chủ xác thực. Vui lòng đảm bảo backend đang hoạt động.",
      };
    }
  };

  const register = async (
    data: Partial<RegisterFormState>
  ): Promise<{ success: boolean; error?: string; user?: AuthUser }> => {
    if (!data.phone || data.phone.trim().length < 9) {
      return { success: false, error: "Số điện thoại không hợp lệ." };
    }
    if (!data.password || data.password.length < 6) {
      return { success: false, error: "Mật khẩu tối thiểu 6 ký tự." };
    }

    const cleanPhone = data.phone.trim().replace(/\s+/g, "").replace(/-/g, "");

    try {
      const res = await fetch(`${API_BASE}/api/v1/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          full_name: data.fullName?.trim() || `Khách hàng ${cleanPhone.slice(-4)}`,
          phone: cleanPhone,
          email: data.email?.trim() || undefined,
          password: data.password,
        }),
      });

      if (res.ok) {
        const resData = await res.json();
        const authUser: AuthUser = {
          id: resData.user?.id || Date.now(),
          fullName: resData.user?.full_name || data.fullName?.trim() || "Thành viên Mới",
          phone: cleanPhone,
          email: resData.user?.email || data.email?.trim() || `${cleanPhone}@customer.pharmatrust.vn`,
          role: "Hội viên",
          isAdmin: false,
          points: resData.user?.loyalty_points ?? 50,
          createdAt: new Date().toISOString().split("T")[0],
        };

        if (resData.access_token) {
          localStorage.setItem("pharmatrust_access_token", resData.access_token);
          if (resData.refresh_token) localStorage.setItem("pharmatrust_refresh_token", resData.refresh_token);
        }

        saveSession(authUser);
        return { success: true, user: authUser };
      } else {
        const errData = await res.json().catch(() => ({}));
        return {
          success: false,
          error: errData.detail || "Đăng ký không thành công. Thông tin có thể đã tồn tại.",
        };
      }
    } catch (e) {
      return {
        success: false,
        error: "Không thể kết nối đến máy chủ đăng ký. Vui lòng kiểm tra lại kết nối mạng.",
      };
    }
  };

  const logout = () => {
    setUser(null);
    try {
      localStorage.removeItem(STORAGE_KEY);
      localStorage.removeItem("pharmatrust_access_token");
      localStorage.removeItem("pharmatrust_refresh_token");
    } catch (e) {
      console.warn("Failed to clear auth session", e);
    }
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: !!user,
        isAdmin: !!user?.isAdmin,
        isWarehouseManager: !!user?.isWarehouseManager,
        isWarehouseStaff: !!user?.isWarehouseStaff,
        isLoading,
        loginWithPhone,
        loginWithPassword,
        sendPhoneOtp,
        register,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
};
