/**
 * apps/storefront/src/services/placesService.ts
 *
 * Client Service kết nối hệ thống tìm kiếm địa điểm đa năng và Geocoding chuẩn Google Maps.
 * Hỗ trợ Autocomplete POI, Reverse Geocoding, Browser Geolocation và Provider Status.
 */

import { API_BASE } from "@/lib/api-config";

export interface PlaceSuggestionItem {
  place_id: string;
  name: string;
  short_address: string;
  formatted_address: string;
  street_address?: string;
  lat: number;
  lng: number;
  province_code?: string | null;
  province_name?: string | null;
  commune_code?: string | null;
  commune_name?: string | null;
  district_name?: string | null;
  provider?: string;
  category?: string;
  verified?: boolean;
}

export interface ReverseGeocodeResult {
  place_id: string;
  formatted_address: string;
  street_address: string;
  lat: number;
  lng: number;
  province_code?: string | null;
  province_name?: string | null;
  commune_code?: string | null;
  commune_name?: string | null;
  district_name?: string | null;
  provider: string;
  is_verified: boolean;
}

export interface ProviderStatus {
  google_configured: boolean;
  active_provider: string;
  fallback_provider: string;
  report: string;
}

export interface CurrentLocationResult {
  lat: number;
  lng: number;
  accuracy: number;
  isLowAccuracy: boolean;
}

export const placesService = {
  /**
   * Tìm kiếm gợi ý địa điểm / địa chỉ theo thời gian thực (Google-like Place Autocomplete có Session Token)
   */
  async searchPlaces(
    query: string,
    options?: { limit?: number; lat?: number; lng?: number; sessionToken?: string }
  ): Promise<PlaceSuggestionItem[]> {
    const q = query.trim();
    if (q.length < 2) return [];

    try {
      const params = new URLSearchParams({
        q,
        limit: String(options?.limit || 8),
      });
      if (options?.lat !== undefined && options?.lng !== undefined) {
        params.append("lat", String(options.lat));
        params.append("lng", String(options.lng));
      }
      if (options?.sessionToken) {
        params.append("session_token", options.sessionToken);
      }

      const res = await fetch(`${API_BASE}/api/v1/addresses/places/autocomplete?${params.toString()}`);
      if (res.ok) {
        return await res.json();
      }
    } catch (e) {
      console.warn("Places autocomplete API failed, using fallback:", e);
    }

    return [];
  },

  /**
   * Lấy chi tiết địa điểm theo Place ID (Tọa độ chính xác và thành phần hành chính)
   */
  async getPlaceDetails(placeId: string, sessionToken?: string): Promise<PlaceSuggestionItem | null> {
    if (!placeId) return null;
    try {
      const params = new URLSearchParams({ place_id: placeId });
      if (sessionToken) {
        params.append("session_token", sessionToken);
      }
      const res = await fetch(`${API_BASE}/api/v1/addresses/places/details?${params.toString()}`);
      if (res.ok) {
        return await res.json();
      }
    } catch (e) {
      console.warn("Place details API error:", e);
    }
    return null;
  },

  /**
   * Reverse Geocoding: Tọa độ GPS -> Địa chỉ & Thành phần hành chính 2 cấp
   */
  async reverseGeocode(lat: number, lng: number): Promise<ReverseGeocodeResult> {
    try {
      const res = await fetch(
        `${API_BASE}/api/v1/addresses/reverse-geocode?lat=${encodeURIComponent(lat)}&lng=${encodeURIComponent(lng)}`
      );
      if (res.ok) {
        return await res.json();
      }
    } catch (e) {
      console.warn("Reverse geocode API failed, using local estimate:", e);
    }

    return {
      place_id: `local_rev_${lat.toFixed(4)}_${lng.toFixed(4)}`,
      formatted_address: `Vị trí ghim tọa độ (${lat.toFixed(4)}, ${lng.toFixed(4)})`,
      street_address: `Tọa độ (${lat.toFixed(4)}, ${lng.toFixed(4)})`,
      lat,
      lng,
      provider: "fallback_client",
      is_verified: false, // TUYỆT ĐỐI không gán true cho client fallback
    };
  },

  /**
   * Kiểm tra trạng thái nhà cung cấp Geocoding (Mục 16)
   */
  async getProviderStatus(): Promise<ProviderStatus> {
    try {
      const res = await fetch(`${API_BASE}/api/v1/addresses/provider-status`);
      if (res.ok) {
        return await res.json();
      }
    } catch (e) {
      // offline fallback
    }

    return {
      google_configured: false,
      active_provider: "photon_osm_composite",
      fallback_provider: "photon_osm_internal",
      report: "GOOGLE PLACES: NOT CONFIGURED | FALLBACK: OpenStreetMap / Nominatim + Photon + Internal 2-Tier GeoService",
    };
  },

  /**
   * Lấy vị trí GPS hiện tại của thiết bị (Mục 8 & Mục 9)
   * Chỉ kích hoạt khi người dùng bấm nút "Vị trí hiện tại của tôi".
   */
  getCurrentLocation(): Promise<CurrentLocationResult> {
    return new Promise((resolve, reject) => {
      if (typeof window === "undefined" || !navigator.geolocation) {
        reject(new Error("Trình duyệt của bạn không hỗ trợ định vị GPS toàn cầu."));
        return;
      }

      navigator.geolocation.getCurrentPosition(
        (pos) => {
          const acc = pos.coords.accuracy || 0;
          resolve({
            lat: pos.coords.latitude,
            lng: pos.coords.longitude,
            accuracy: acc,
            isLowAccuracy: acc > 100, // Cảnh báo nếu độ lệch lớn hơn 100m
          });
        },
        (err) => {
          let msg = "Không thể lấy vị trí hiện tại.";
          if (err.code === err.PERMISSION_DENIED) {
            msg = "Bạn đã từ chối quyền truy cập vị trí GPS. Vui lòng cho phép quyền định vị trong cài đặt trình duyệt.";
          } else if (err.code === err.TIMEOUT) {
            msg = "Quá thời gian chờ phản hồi từ cảm biến GPS. Vui lòng thử lại.";
          } else if (err.code === err.POSITION_UNAVAILABLE) {
            msg = "Tín hiệu định vị hiện tại không khả dụng. Bạn có thể kéo ghim trên bản đồ để chọn vị trí.";
          }
          reject(new Error(msg));
        },
        {
          enableHighAccuracy: true,
          timeout: 10000,
          maximumAge: 30000,
        }
      );
    });
  },
};
