/**
 * apps/storefront/src/services/customerAddressService.ts
 *
 * Client API kết nối hệ thống Địa chỉ giao nhận H4CARE Production V2.
 * Hỗ trợ xác thực token, CRUD sổ địa chỉ, tính cước vận chuyển và đồng bộ địa giới.
 */

import { API_BASE } from "@/lib/api-config";

export interface CustomerAddressItem {
  id: number;
  user_id?: number | null;
  recipient_name: string;
  phone: string;
  address_line: string;
  province_code?: string;
  province_name?: string;
  commune_code?: string;
  commune_name?: string;
  formatted_address?: string;
  district_code?: string;
  ward_code?: string;
  lat?: number | null;
  lng?: number | null;
  place_id?: string | null;
  delivery_note?: string | null;
  is_verified: boolean;
  verified_at?: string | null;
  is_default: boolean;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface CustomerAddressInput {
  recipient_name: string;
  phone: string;
  address_line: string;
  province_code: string;
  province_name?: string;
  commune_code?: string;
  commune_name?: string;
  district_code?: string;
  ward_code?: string;
  lat?: number | null;
  lng?: number | null;
  place_id?: string | null;
  delivery_note?: string | null;
  is_default?: boolean;
}

export interface ShippingCalculationResult {
  warehouse_id: number | null;
  warehouse_code: string | null;
  warehouse_name: string;
  warehouse_address: string;
  distance_km: number;
  base_fee: number;
  shipping_fee: number;
  is_free_shipping: boolean;
  free_shipping_threshold: number;
  estimated_delivery: string;
  calculation_basis: string;
}

function getAuthHeader(): Record<string, string> {
  if (typeof window === "undefined") return {};
  const token = localStorage.getItem("pharmatrust_access_token");
  if (token) {
    return { Authorization: `Bearer ${token}` };
  }
  return {};
}

const LOCAL_FALLBACK_KEY = "h4care_saved_addresses_v2";

function getLocalFallbackAddresses(): CustomerAddressItem[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(LOCAL_FALLBACK_KEY);
    if (raw) return JSON.parse(raw);
  } catch (e) {
    console.warn("Failed to load local fallback addresses", e);
  }
  return [];
}

function saveLocalFallbackAddresses(list: CustomerAddressItem[]) {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(LOCAL_FALLBACK_KEY, JSON.stringify(list));
  } catch (e) {
    console.warn("Failed to persist local fallback addresses", e);
  }
}

export const customerAddressService = {
  /**
   * Lấy danh sách địa chỉ nhận hàng của người dùng đang đăng nhập
   */
  async listAddresses(): Promise<CustomerAddressItem[]> {
    const headers = getAuthHeader();
    try {
      const res = await fetch(`${API_BASE}/api/v1/customer/addresses`, {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
          ...headers,
        },
      });

      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data)) {
          saveLocalFallbackAddresses(data);
          return data;
        }
      }
    } catch (e) {
      console.warn("Failed to fetch customer addresses from API, using fallback", e);
    }
    return getLocalFallbackAddresses();
  },

  /**
   * Lấy chi tiết một địa chỉ theo ID
   */
  async getAddressById(id: number): Promise<CustomerAddressItem | null> {
    const headers = getAuthHeader();
    try {
      const res = await fetch(`${API_BASE}/api/v1/customer/addresses/${id}`, {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
          ...headers,
        },
      });
      if (res.ok) {
        return await res.json();
      }
    } catch (e) {
      console.warn(`Failed to fetch address #${id} from API`, e);
    }
    const local = getLocalFallbackAddresses();
    return local.find((a) => a.id === id) || null;
  },

  /**
   * Thêm địa chỉ mới vào sổ địa chỉ
   */
  async createAddress(payload: CustomerAddressInput): Promise<CustomerAddressItem> {
    const headers = getAuthHeader();
    try {
      const res = await fetch(`${API_BASE}/api/v1/customer/addresses`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...headers,
        },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        const detail = errJson.detail || "Không thể tạo địa chỉ giao hàng. Vui lòng kiểm tra lại thông tin.";
        throw new Error(detail);
      }

      const resData = await res.json();
      const item: CustomerAddressItem = resData.data || resData;

      // Cập nhật bộ nhớ cục bộ
      const current = getLocalFallbackAddresses();
      if (item.is_default) {
        current.forEach((a) => (a.is_default = false));
      }
      const updated = [item, ...current.filter((a) => a.id !== item.id)];
      saveLocalFallbackAddresses(updated);

      return item;
    } catch (e: any) {
      if (e.message && e.message !== "Failed to fetch") {
        throw e;
      }
      // Offline fallback
      const current = getLocalFallbackAddresses();
      const newId = Date.now();
      const newItem: CustomerAddressItem = {
        id: newId,
        recipient_name: payload.recipient_name,
        phone: payload.phone,
        address_line: payload.address_line,
        province_code: payload.province_code,
        province_name: payload.province_name,
        commune_code: payload.commune_code,
        commune_name: payload.commune_name,
        formatted_address: `${payload.address_line}, ${payload.commune_name || ""}, ${payload.province_name || ""}`.trim(),
        district_code: payload.district_code,
        ward_code: payload.ward_code || payload.commune_code,
        lat: payload.lat,
        lng: payload.lng,
        place_id: payload.place_id,
        delivery_note: payload.delivery_note,
        is_verified: !!(payload.lat && payload.lng),
        verified_at: payload.lat && payload.lng ? new Date().toISOString() : null,
        is_default: !!payload.is_default || current.length === 0,
        created_at: new Date().toISOString(),
      };
      if (newItem.is_default) {
        current.forEach((a) => (a.is_default = false));
      }
      saveLocalFallbackAddresses([newItem, ...current]);
      return newItem;
    }
  },

  /**
   * Lưu địa chỉ mới (alias cho createAddress)
   */
  async saveAddress(payload: CustomerAddressInput): Promise<CustomerAddressItem> {
    return this.createAddress(payload);
  },

  /**
   * Cập nhật thông tin địa chỉ đã lưu
   */
  async updateAddress(id: number, payload: Partial<CustomerAddressInput>): Promise<CustomerAddressItem> {
    const headers = getAuthHeader();
    try {
      const res = await fetch(`${API_BASE}/api/v1/customer/addresses/${id}`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          ...headers,
        },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        const detail = errJson.detail || "Không thể cập nhật địa chỉ.";
        throw new Error(detail);
      }

      const resData = await res.json();
      const item: CustomerAddressItem = resData.data || resData;

      const current = getLocalFallbackAddresses();
      if (item.is_default) {
        current.forEach((a) => {
          if (a.id !== item.id) a.is_default = false;
        });
      }
      const updated = current.map((a) => (a.id === id ? item : a));
      saveLocalFallbackAddresses(updated);

      return item;
    } catch (e: any) {
      if (e.message && e.message !== "Failed to fetch") {
        throw e;
      }
      const current = getLocalFallbackAddresses();
      const index = current.findIndex((a) => a.id === id);
      if (index >= 0) {
        current[index] = { ...current[index], ...payload } as CustomerAddressItem;
        if (payload.is_default) {
          current.forEach((a, idx) => {
            if (idx !== index) a.is_default = false;
          });
        }
        saveLocalFallbackAddresses(current);
        return current[index];
      }
      throw e;
    }
  },

  /**
   * Xóa địa chỉ khỏi sổ địa chỉ
   */
  async deleteAddress(id: number): Promise<boolean> {
    const headers = getAuthHeader();
    try {
      const res = await fetch(`${API_BASE}/api/v1/customer/addresses/${id}`, {
        method: "DELETE",
        headers: {
          "Content-Type": "application/json",
          ...headers,
        },
      });
      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || "Không thể xóa địa chỉ này.");
      }
    } catch (e: any) {
      if (e.message && e.message !== "Failed to fetch") {
        throw e;
      }
    }

    const current = getLocalFallbackAddresses();
    const remaining = current.filter((a) => a.id !== id);
    if (remaining.length > 0 && !remaining.some((a) => a.is_default)) {
      remaining[0].is_default = true;
    }
    saveLocalFallbackAddresses(remaining);
    return true;
  },

  /**
   * Đặt địa chỉ làm mặc định
   */
  async setDefaultAddress(id: number): Promise<CustomerAddressItem> {
    const headers = getAuthHeader();
    try {
      const res = await fetch(`${API_BASE}/api/v1/customer/addresses/${id}/default`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          ...headers,
        },
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || "Không thể đặt làm địa chỉ mặc định.");
      }

      const resData = await res.json();
      const item: CustomerAddressItem = resData.data || resData;

      const current = getLocalFallbackAddresses();
      current.forEach((a) => {
        a.is_default = a.id === id;
      });
      saveLocalFallbackAddresses(current);

      return item;
    } catch (e: any) {
      if (e.message && e.message !== "Failed to fetch") {
        throw e;
      }
      const current = getLocalFallbackAddresses();
      current.forEach((a) => {
        a.is_default = a.id === id;
      });
      saveLocalFallbackAddresses(current);
      const target = current.find((a) => a.id === id);
      if (target) return target;
      throw e;
    }
  },

  /**
   * Tính toán cước phí giao hàng và ước tính thời gian dựa trên vị trí GPS và giá trị đơn hàng
   */
  async calculateShipping(params: {
    lat?: number | null;
    lng?: number | null;
    province_code?: string;
    district_code?: string;
    order_total?: number;
  }): Promise<ShippingCalculationResult> {
    try {
      const res = await fetch(`${API_BASE}/api/v1/addresses/calculate-shipping`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          lat: params.lat,
          lng: params.lng,
          province_code: params.province_code,
          district_code: params.district_code,
          order_total: params.order_total || 0,
        }),
      });
      if (res.ok) {
        return await res.json();
      }
    } catch (e) {
      console.warn("Failed to calculate shipping via API, using local estimation", e);
    }

    // Default offline estimation
    const isFree = (params.order_total || 0) >= 300000;
    return {
      warehouse_id: 1,
      warehouse_code: "KHO-HCM-01",
      warehouse_name: "Kho Dược Trung Tâm H4CARE",
      warehouse_address: "123 Lê Lợi, Quận 1, TP. Hồ Chí Minh",
      distance_km: 4.5,
      base_fee: 15000,
      shipping_fee: isFree ? 0 : 15000,
      is_free_shipping: isFree,
      free_shipping_threshold: 300000,
      estimated_delivery: "Dự kiến giao siêu tốc 1 - 2 giờ",
      calculation_basis: "Khoảng cách ước tính bán kính nội thành",
    };
  },
};
