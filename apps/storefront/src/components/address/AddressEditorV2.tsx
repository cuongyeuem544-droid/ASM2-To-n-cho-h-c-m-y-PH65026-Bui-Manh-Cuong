"use client";

import React, { useState, useEffect, useRef, useMemo } from "react";
import dynamic from "next/dynamic";
import {
  MapPin,
  Search,
  Crosshair,
  Compass,
  CheckCircle2,
  AlertCircle,
  Building,
  GraduationCap,
  Hospital,
  ChevronDown,
  Check,
  User,
  Phone,
  BookmarkCheck,
  Clock,
  Layers,
  Sparkles,
  Info,
  Loader2,
  Navigation,
} from "lucide-react";
import {
  administrativeService,
  ProvinceUnit,
  CommuneUnit,
  removeVietnameseAccents,
} from "@/services/administrativeService";
import {
  placesService,
  PlaceSuggestionItem,
  ReverseGeocodeResult,
  ProviderStatus,
} from "@/services/placesService";
import { CustomerAddressItem, CustomerAddressInput } from "@/services/customerAddressService";

const DeliveryRealMap = dynamic(
  () => import("@/components/checkout/DeliveryRealMap"),
  {
    ssr: false,
    loading: () => (
      <div className="w-full h-56 rounded-xl bg-slate-100 border border-slate-200 flex flex-col items-center justify-center text-slate-400 gap-2">
        <Loader2 className="w-6 h-6 animate-spin text-brand-blue-600" />
        <span className="text-xs font-medium">Đang tải bản đồ định vị H4CARE...</span>
      </div>
    ),
  }
);

export interface AddressEditorV2Data {
  recipient_name: string;
  phone: string;
  address_line: string;
  province_code: string;
  province_name: string;
  commune_code: string;
  commune_name: string;
  formatted_address: string;
  lat: number;
  lng: number;
  place_id?: string;
  delivery_note?: string;
  is_default?: boolean;
  is_verified: boolean;
}

export interface AddressEditorV2Props {
  initialData?: Partial<CustomerAddressItem> | null;
  onSave: (data: AddressEditorV2Data) => Promise<void> | void;
  onCancel?: () => void;
  showRecipientFields?: boolean;
  prefillName?: string;
  prefillPhone?: string;
  submitButtonText?: string;
  nearestWarehouse?: any;
  onRegisterSubmit?: (fn: () => Promise<AddressEditorV2Data | null>) => void;
}

export default function AddressEditorV2({
  initialData,
  onSave,
  onCancel,
  showRecipientFields = true,
  prefillName = "",
  prefillPhone = "",
  submitButtonText = "Xác nhận địa chỉ này",
  nearestWarehouse,
  onRegisterSubmit,
}: AddressEditorV2Props) {
  // Form fields
  const [recipientName, setRecipientName] = useState(
    initialData?.recipient_name || prefillName || ""
  );
  const [phone, setPhone] = useState(initialData?.phone || prefillPhone || "");
  const [deliveryNote, setDeliveryNote] = useState(initialData?.delivery_note || "");
  const [isDefault, setIsDefault] = useState(initialData?.is_default || false);

  // Address components
  const [selectedProvince, setSelectedProvince] = useState<ProvinceUnit | null>(null);
  const [selectedCommune, setSelectedCommune] = useState<CommuneUnit | null>(null);
  const [streetAddress, setStreetAddress] = useState(initialData?.address_line || "");
  const [formattedAddress, setFormattedAddress] = useState(
    initialData?.formatted_address || ""
  );

  // Coordinates
  const [lat, setLat] = useState<number>(initialData?.lat || 10.7769);
  const [lng, setLng] = useState<number>(initialData?.lng || 106.7009);
  const [hasRealCoordinates, setHasRealCoordinates] = useState<boolean>(
    Boolean(initialData?.lat && initialData?.lng && !(Math.abs(initialData.lat - 10.7769) < 0.0001 && Math.abs(initialData.lng - 106.7009) < 0.0001))
  );

  // Verification state (Chỉ true khi tọa độ thực tế được xác minh từ Google Maps, GPS hoặc Ghim bản đồ)
  const [isVerified, setIsVerified] = useState<boolean>(
    Boolean(initialData?.is_verified && initialData?.lat && initialData?.lng && !(Math.abs(initialData.lat - 10.7769) < 0.0001 && Math.abs(initialData.lng - 106.7009) < 0.0001))
  );

  // Session Token Google Places để tối ưu chi phí API
  const sessionTokenRef = useRef<string>("");
  useEffect(() => {
    sessionTokenRef.current = typeof crypto !== "undefined" && crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).substring(2);
  }, []);

  // Place Autocomplete search
  const [searchQuery, setSearchQuery] = useState("");
  const [suggestions, setSuggestions] = useState<PlaceSuggestionItem[]>([]);
  const [isLoadingSuggestions, setIsLoadingSuggestions] = useState(false);
  const [isSuggestionsOpen, setIsSuggestionsOpen] = useState(false);
  const [activeSuggestionIndex, setActiveSuggestionIndex] = useState<number>(-1);
  const [searchError, setSearchError] = useState<string | null>(null);

  // 2-tier dropdown states
  const [provinceSearch, setProvinceSearch] = useState("");
  const [communeSearch, setCommuneSearch] = useState("");
  const [isProvinceOpen, setIsProvinceOpen] = useState(false);
  const [isCommuneOpen, setIsCommuneOpen] = useState(false);

  // Geolocation & UI notifications
  const [isLocatingGps, setIsLocatingGps] = useState(false);
  const [gpsAccuracyNotice, setGpsAccuracyNotice] = useState<string | null>(null);
  const [locationNotice, setLocationNotice] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [providerStatus, setProviderStatus] = useState<ProviderStatus | null>(null);

  const searchBoxRef = useRef<HTMLDivElement>(null);
  const provinceRef = useRef<HTMLDivElement>(null);
  const communeRef = useRef<HTMLDivElement>(null);

  // Load provider status
  useEffect(() => {
    placesService.getProviderStatus().then(setProviderStatus).catch(() => {});
  }, []);

  // Initialize province and commune from initialData
  useEffect(() => {
    if (initialData?.province_code && !selectedProvince) {
      const p = administrativeService.getProvinceByCode(initialData.province_code);
      if (p) setSelectedProvince(p);
    }
    if (initialData?.commune_code && !selectedCommune) {
      const c = administrativeService.getCommuneByCode(initialData.commune_code);
      if (c) setSelectedCommune(c);
    }
    if (initialData?.lat && initialData?.lng) {
      setLat(initialData.lat);
      setLng(initialData.lng);
    }
  }, [initialData]);

  // Click outside to close dropdowns
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (searchBoxRef.current && !searchBoxRef.current.contains(e.target as Node)) {
        setIsSuggestionsOpen(false);
      }
      if (provinceRef.current && !provinceRef.current.contains(e.target as Node)) {
        setIsProvinceOpen(false);
      }
      if (communeRef.current && !communeRef.current.contains(e.target as Node)) {
        setIsCommuneOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Filtered 63 Provinces
  const filteredProvinces = useMemo(() => {
    return administrativeService.getProvinces(provinceSearch);
  }, [provinceSearch]);

  // Filtered Communes for selected province
  const filteredCommunes = useMemo(() => {
    if (!selectedProvince) return [];
    return administrativeService.getCommunes(selectedProvince.code, undefined, communeSearch);
  }, [selectedProvince, communeSearch]);

  // Debounced Place Search (Requirement 1, 2, 8, 11)
  useEffect(() => {
    const clean = searchQuery.trim();
    if (clean.length < 2) {
      setSuggestions([]);
      setIsSuggestionsOpen(false);
      setSearchError(null);
      setActiveSuggestionIndex(-1);
      return;
    }

    const timer = setTimeout(async () => {
      setIsLoadingSuggestions(true);
      setSearchError(null);
      setActiveSuggestionIndex(-1);
      try {
        const results = await placesService.searchPlaces(clean, {
          limit: 8,
          sessionToken: sessionTokenRef.current,
        });
        setSuggestions(results);
        setIsSuggestionsOpen(true);
      } catch (e) {
        setSuggestions([]);
        setSearchError("Không thể tải gợi ý địa chỉ lúc này. Vui lòng thử lại.");
        setIsSuggestionsOpen(true);
      } finally {
        setIsLoadingSuggestions(false);
      }
    }, 350);

    return () => clearTimeout(timer);
  }, [searchQuery]);

  // Keyboard navigation for suggestions
  const handleKeyDownSearch = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (!isSuggestionsOpen) {
      if (e.key === "ArrowDown" && suggestions.length > 0) {
        setIsSuggestionsOpen(true);
        e.preventDefault();
      }
      return;
    }

    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveSuggestionIndex((prev) => (prev < suggestions.length - 1 ? prev + 1 : 0));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveSuggestionIndex((prev) => (prev > 0 ? prev - 1 : suggestions.length - 1));
    } else if (e.key === "Enter") {
      if (activeSuggestionIndex >= 0 && activeSuggestionIndex < suggestions.length) {
        e.preventDefault();
        handleSelectSuggestion(suggestions[activeSuggestionIndex]);
      }
    } else if (e.key === "Escape") {
      e.preventDefault();
      setIsSuggestionsOpen(false);
    }
  };

  // Handle Suggestion Click (Requirement 3 & 4)
  const handleSelectSuggestion = (item: PlaceSuggestionItem) => {
    setIsSuggestionsOpen(false);
    setActiveSuggestionIndex(-1);
    setSearchQuery(item.name);
    setErrorMessage(null);
    setIsVerified(false); // Invalidate per Requirement 18

    // 1. Coordinates & Google Place Details
    if (item.lat && item.lng && (Math.abs(item.lat) > 0.0001 || Math.abs(item.lng) > 0.0001)) {
      setLat(item.lat);
      setLng(item.lng);
      setHasRealCoordinates(true);
      setIsVerified(true);
    } else if (item.place_id) {
      // Gọi chi tiết Place Details để lấy tọa độ hình học (geometry)
      placesService.getPlaceDetails(item.place_id, sessionTokenRef.current).then((detail) => {
        if (detail && detail.lat && detail.lng && (Math.abs(detail.lat) > 0.0001 || Math.abs(detail.lng) > 0.0001)) {
          setLat(detail.lat);
          setLng(detail.lng);
          setHasRealCoordinates(true);
          setIsVerified(true);
          if (detail.formatted_address) setFormattedAddress(detail.formatted_address);
          if (detail.street_address) setStreetAddress(detail.street_address);
          if (detail.province_code) {
            const p = administrativeService.getProvinceByCode(detail.province_code);
            if (p) setSelectedProvince(p);
          }
          if (detail.commune_code) {
            const c = administrativeService.getCommuneByCode(detail.commune_code);
            if (c) setSelectedCommune(c);
          }
        } else {
          setHasRealCoordinates(false);
          setIsVerified(false);
          setLocationNotice("Không tìm thấy tọa độ chi tiết cho địa điểm này. Vui lòng kéo ghim trên bản đồ để xác minh.");
        }
      });
      // Tạo session token mới cho lượt tìm kiếm tiếp theo
      sessionTokenRef.current = typeof crypto !== "undefined" && crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).substring(2);
    }

    // 2. Map administrative components
    if (item.province_code) {
      const p = administrativeService.getProvinceByCode(item.province_code);
      if (p) setSelectedProvince(p);
    }
    if (item.commune_code) {
      const c = administrativeService.getCommuneByCode(item.commune_code);
      if (c) setSelectedCommune(c);
    }

    // 3. Address fields
    const street = item.street_address || item.name;
    setStreetAddress(street);
    setFormattedAddress(item.formatted_address || `${street}, Việt Nam`);

    setLocationNotice(`Đã chọn địa điểm: ${item.name} (${item.short_address})`);
    setTimeout(() => setLocationNotice(null), 4000);
  };

  // Handle Map Click or Marker Drag End (Requirement 5, 6, 7)
  const handleMapLocationChange = async (newLat: number, newLng: number) => {
    setLat(newLat);
    setLng(newLng);
    setHasRealCoordinates(true);
    setIsVerified(true); // Người dùng trực tiếp kéo ghim định vị thật trên bản đồ
    setLocationNotice("Vị trí giao hàng đã được điều chỉnh trên bản đồ. Đang cập nhật địa chỉ...");

    try {
      const rev = await placesService.reverseGeocode(newLat, newLng);
      if (rev) {
        let currentProv: ProvinceUnit | null = null;
        if (rev.province_code) {
          const p = administrativeService.getProvinceByCode(rev.province_code);
          if (p) {
            setSelectedProvince(p);
            currentProv = p;
          }
        } else if (rev.province_name) {
          const provs = administrativeService.getProvinces(rev.province_name);
          if (provs.length > 0) {
            setSelectedProvince(provs[0]);
            currentProv = provs[0];
          }
        }

        if (rev.commune_code) {
          const c = administrativeService.getCommuneByCode(rev.commune_code);
          if (c) setSelectedCommune(c);
        } else if (currentProv) {
          const candidateNames = [rev.commune_name, rev.district_name, rev.street_address].filter(Boolean);
          let matched: CommuneUnit | null = null;
          for (const name of candidateNames) {
            const comms = administrativeService.getCommunes(currentProv.code, undefined, name as string);
            if (comms.length > 0) {
              matched = comms[0];
              break;
            }
          }
          if (matched) {
            setSelectedCommune(matched);
          }
        }

        if (rev.street_address) {
          setStreetAddress(rev.street_address);
        }
        setFormattedAddress(rev.formatted_address);
        setLocationNotice(`Vị trí giao hàng đã được điều chỉnh: ${rev.formatted_address}`);
        setTimeout(() => setLocationNotice(null), 4000);
      }
    } catch {
      setLocationNotice("Đã định vị lại vị trí trên bản đồ.");
      setTimeout(() => setLocationNotice(null), 3000);
    }
  };

  // Handle "Vị trí hiện tại của tôi" (Requirement 8 & 9)
  const handleGetCurrentLocation = async () => {
    setIsLocatingGps(true);
    setErrorMessage(null);
    setGpsAccuracyNotice(null);

    try {
      const loc = await placesService.getCurrentLocation();
      setLat(loc.lat);
      setLng(loc.lng);
      setIsVerified(false); // Invalidate per Requirement 18

      if (loc.isLowAccuracy) {
        setGpsAccuracyNotice(
          `Vị trí hiện tại chưa đủ chính xác (sai số ±${Math.round(loc.accuracy)}m). Bạn có thể điều chỉnh ghim trên bản đồ.`
        );
      }

      const rev = await placesService.reverseGeocode(loc.lat, loc.lng);
      if (rev) {
        let currentProv: ProvinceUnit | null = null;
        if (rev.province_code) {
          const p = administrativeService.getProvinceByCode(rev.province_code);
          if (p) {
            setSelectedProvince(p);
            currentProv = p;
          }
        } else if (rev.province_name) {
          const provs = administrativeService.getProvinces(rev.province_name);
          if (provs.length > 0) {
            setSelectedProvince(provs[0]);
            currentProv = provs[0];
          }
        }

        if (rev.commune_code) {
          const c = administrativeService.getCommuneByCode(rev.commune_code);
          if (c) setSelectedCommune(c);
        } else if (currentProv) {
          const candidateNames = [rev.commune_name, rev.district_name, rev.street_address].filter(Boolean);
          let matched: CommuneUnit | null = null;
          for (const name of candidateNames) {
            const comms = administrativeService.getCommunes(currentProv.code, undefined, name as string);
            if (comms.length > 0) {
              matched = comms[0];
              break;
            }
          }
          if (matched) {
            setSelectedCommune(matched);
          }
        }
        if (rev.street_address) {
          setStreetAddress(rev.street_address);
        }
        setFormattedAddress(rev.formatted_address);
        setLocationNotice(`Đã lấy vị trí GPS hiện tại: ${rev.formatted_address}`);
        setTimeout(() => setLocationNotice(null), 4000);
      }
    } catch (err: any) {
      setErrorMessage(err.message || "Không thể truy cập cảm biến GPS của thiết bị.");
    } finally {
      setIsLocatingGps(false);
    }
  };

  // Handle Province Select
  const handleSelectProvince = (p: ProvinceUnit) => {
    setSelectedProvince(p);
    setSelectedCommune(null);
    setIsProvinceOpen(false);
    setProvinceSearch("");
    setIsVerified(false); // Invalidate per Requirement 18

    // Center map on province bounding box
    if (p.boundingBox) {
      const midLat = (p.boundingBox.minLat + p.boundingBox.maxLat) / 2;
      const midLng = (p.boundingBox.minLng + p.boundingBox.maxLng) / 2;
      setLat(midLat);
      setLng(midLng);
    }
  };

  // Handle Commune Select
  const handleSelectCommune = (c: CommuneUnit) => {
    setSelectedCommune(c);
    setIsCommuneOpen(false);
    setCommuneSearch("");
    setIsVerified(false); // Invalidate per Requirement 18
  };

  // Handle Submit / Confirm
  const handleSubmit = async (e?: React.FormEvent): Promise<AddressEditorV2Data | null> => {
    if (e) e.preventDefault();
    setErrorMessage(null);

    if (showRecipientFields) {
      if (!recipientName.trim()) {
        setErrorMessage("Vui lòng nhập Họ và tên người nhận thuốc.");
        return null;
      }
      const cleanPhone = phone.replace(/\D/g, "");
      if (cleanPhone.length < 9 || cleanPhone.length > 11) {
        setErrorMessage("Vui lòng nhập số điện thoại nhận hàng hợp lệ (10 chữ số).");
        return null;
      }
    }

    if (!selectedProvince) {
      setErrorMessage("Vui lòng chọn Tỉnh / Thành phố nhận hàng.");
      return null;
    }
    if (!selectedCommune) {
      setErrorMessage("Vui lòng chọn Xã / Phường / Đặc khu nhận hàng.");
      return null;
    }
    if (!streetAddress.trim() || streetAddress.trim().length < 3) {
      setErrorMessage("Vui lòng nhập số nhà, tên đường hoặc địa chỉ cụ thể (tối thiểu 3 ký tự).");
      return null;
    }

    const fullAddr =
      formattedAddress ||
      `${streetAddress.trim()}, ${selectedCommune.fullName}, ${selectedProvince.fullName}`;

    const payloadData: AddressEditorV2Data = {
      recipient_name: recipientName.trim(),
      phone: phone.trim(),
      address_line: streetAddress.trim(),
      province_code: selectedProvince.code,
      province_name: selectedProvince.fullName,
      commune_code: selectedCommune.code,
      commune_name: selectedCommune.fullName,
      formatted_address: fullAddr,
      lat,
      lng,
      place_id: `geo_${selectedProvince.code}_${selectedCommune.code}`,
      delivery_note: deliveryNote.trim() || undefined,
      is_default: isDefault,
      is_verified: Boolean(hasRealCoordinates && isVerified),
    };

    setIsSubmitting(true);
    try {
      await onSave(payloadData);
      return payloadData;
    } catch (err: any) {
      setErrorMessage(err.message || "Lỗi khi lưu địa chỉ giao hàng.");
      setIsVerified(false);
      return null;
    } finally {
      setIsSubmitting(false);
    }
  };

  useEffect(() => {
    if (onRegisterSubmit) {
      onRegisterSubmit(async () => {
        return await handleSubmit();
      });
    }
  });

  const getCategoryIcon = (cat?: string) => {
    switch (cat) {
      case "education":
        return <GraduationCap className="w-4 h-4 text-brand-blue-600" />;
      case "hospital":
        return <Hospital className="w-4 h-4 text-rose-600" />;
      case "commercial":
        return <Building className="w-4 h-4 text-emerald-600" />;
      default:
        return <MapPin className="w-4 h-4 text-brand-blue-600" />;
    }
  };

  return (
    <div className="space-y-4 text-slate-800">
      {/* 1. GOOGLE-LIKE UNIFIED PLACE SEARCH BAR (Requirement 1 & 2) */}
      <div className="relative" ref={searchBoxRef}>
        <label className="block text-xs font-semibold text-slate-700 mb-1.5 flex items-center justify-between">
          <span className="flex items-center gap-1.5">
            <Search className="w-3.5 h-3.5 text-brand-blue-600" />
            Tìm địa chỉ hoặc địa điểm
          </span>
          <span className="text-[11px] text-slate-400">
            Trường học, bệnh viện, tòa nhà, đường phố...
          </span>
        </label>

        <div className="relative">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value);
              setIsVerified(false);
            }}
            onKeyDown={handleKeyDownSearch}
            onFocus={() => {
              if (suggestions.length > 0 || searchError) setIsSuggestionsOpen(true);
            }}
            placeholder="Nhập địa chỉ, số nhà, tòa nhà, trường học, bệnh viện, khu dân cư..."
            className="w-full pl-9 pr-24 py-2.5 rounded-xl border border-slate-300 bg-white text-sm focus:outline-hidden focus:ring-2 focus:ring-brand-blue-500/20 focus:border-brand-blue-600 transition-all text-slate-900 placeholder:text-slate-400 font-medium"
          />
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-3 pointer-events-none" />

          {/* Current Location Quick Button on right of search box */}
          <button
            type="button"
            onClick={handleGetCurrentLocation}
            disabled={isLocatingGps}
            title="Định vị GPS vị trí hiện tại của tôi"
            className="absolute right-1.5 top-1.5 px-2.5 py-1 rounded-lg bg-slate-100 hover:bg-brand-blue-50 text-slate-700 hover:text-brand-blue-600 text-xs font-semibold flex items-center gap-1 transition-colors border border-slate-200"
          >
            {isLocatingGps ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin text-brand-blue-600" />
            ) : (
              <Crosshair className="w-3.5 h-3.5 text-brand-blue-600" />
            )}
            <span className="hidden sm:inline">Vị trí tôi</span>
          </button>
        </div>

        {/* Suggestions Dropdown (Google Maps style - Requirement 10, 11, 21, 22) */}
        {isSuggestionsOpen && (
          <div className="absolute z-40 left-0 right-0 top-full mt-1.5 bg-white rounded-xl border border-slate-200 shadow-xl overflow-hidden divide-y divide-slate-100 max-h-80 overflow-y-auto">
            {/* Loading indicator */}
            {isLoadingSuggestions && (
              <div className="p-3 text-center text-xs text-slate-500 flex items-center justify-center gap-2 bg-slate-50/50">
                <Loader2 className="w-4 h-4 animate-spin text-brand-blue-600" />
                <span>Đang tìm kiếm địa điểm trên toàn Việt Nam...</span>
              </div>
            )}

            {/* Error state (Requirement 22) */}
            {!isLoadingSuggestions && searchError && (
              <div className="p-3.5 text-center text-xs text-rose-600 bg-rose-50/50 flex items-center justify-center gap-2">
                <AlertCircle className="w-4 h-4 text-rose-500 shrink-0" />
                <span>{searchError}</span>
              </div>
            )}

            {/* Empty state (Requirement 21) */}
            {!isLoadingSuggestions && !searchError && suggestions.length === 0 && searchQuery.trim().length >= 2 && (
              <div className="p-4 text-center text-xs text-slate-500 bg-white">
                <MapPin className="w-5 h-5 text-slate-300 mx-auto mb-1.5" />
                <p className="font-semibold text-slate-700">Không tìm thấy địa điểm phù hợp.</p>
                <p className="text-[11px] text-slate-400 mt-0.5">
                  Hãy thử nhập tên đường, số nhà hoặc địa danh khác.
                </p>
              </div>
            )}

            {/* Suggestions list (Requirement 1, 2, 3, 10, 11) */}
            {!isLoadingSuggestions && suggestions.map((item, idx) => {
              const isSelected = idx === activeSuggestionIndex;
              return (
                <button
                  key={`${item.place_id}_${idx}`}
                  type="button"
                  onClick={() => handleSelectSuggestion(item)}
                  className={`w-full px-3.5 py-2.5 text-left text-xs flex items-start gap-2.5 transition-colors group ${
                    isSelected ? "bg-brand-blue-50/80 text-brand-blue-900" : "hover:bg-slate-50 text-slate-700"
                  }`}
                >
                  <div
                    className={`p-1.5 rounded-lg shrink-0 mt-0.5 transition-colors ${
                      isSelected ? "bg-brand-blue-100 text-brand-blue-700" : "bg-slate-100 text-slate-600 group-hover:bg-brand-blue-50"
                    }`}
                  >
                    {getCategoryIcon(item.category)}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-slate-900 truncate">
                        {item.name}
                      </span>
                      {item.provider && (
                        <span className="text-[9px] px-1.5 py-0.2 rounded-sm bg-slate-100 text-slate-500 font-mono">
                          {item.provider}
                        </span>
                      )}
                    </div>
                    <p className="text-[11px] text-slate-500 line-clamp-1 mt-0.5">
                      {item.short_address || item.formatted_address}
                    </p>
                  </div>
                </button>
              );
            })}
          </div>
        )}
      </div>

      {/* GPS Accuracy Notice (Requirement 9) */}
      {gpsAccuracyNotice && (
        <div className="p-2.5 rounded-lg bg-amber-50 border border-amber-200 text-amber-800 text-xs flex items-start gap-2">
          <AlertCircle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
          <span>{gpsAccuracyNotice}</span>
        </div>
      )}

      {/* Location Adjusted Notice (Requirement 6) */}
      {locationNotice && (
        <div className="p-2.5 rounded-lg bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs flex items-start gap-2 animate-in fade-in">
          <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
          <span>{locationNotice}</span>
        </div>
      )}

      {/* 2. INTERACTIVE LEAFLET MAP WITH DRAGGABLE PIN (Requirement 5 & 6) */}
      <div className="space-y-1.5">
        <div className="flex items-center justify-between text-xs">
          <span className="font-semibold text-slate-700 flex items-center gap-1.5">
            <Compass className="w-3.5 h-3.5 text-brand-blue-600" />
            Bản đồ định vị giao hàng (Kéo ghim hoặc click để chỉnh chính xác)
          </span>
          <span className="text-[11px] text-slate-500 font-mono">
            GPS: ({lat.toFixed(4)}, {lng.toFixed(4)})
          </span>
        </div>

        <div className="rounded-xl overflow-hidden border border-slate-200 shadow-xs">
          <DeliveryRealMap
            customerCoords={{ lat, lng }}
            nearestWarehouse={nearestWarehouse}
            onLocationSelect={handleMapLocationChange}
            isLocating={isLocatingGps}
            onGetGps={handleGetCurrentLocation}
          />
        </div>
      </div>

      {/* 3. ADMINISTRATIVE 2-TIER SELECTORS (63 Provinces & Cities 2026) */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5 pt-1">
        {/* CẤP 1: TỈNH / THÀNH PHỐ */}
        <div className="relative" ref={provinceRef}>
          <label className="block text-xs font-semibold text-slate-700 mb-1.5">
            Tỉnh / Thành phố <span className="text-rose-500">*</span>
          </label>
          <button
            type="button"
            onClick={() => setIsProvinceOpen(!isProvinceOpen)}
            className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 bg-white text-left text-sm flex items-center justify-between hover:border-slate-300"
          >
            <span className={selectedProvince ? "text-slate-900 font-medium" : "text-slate-400"}>
              {selectedProvince ? selectedProvince.fullName : "Chọn Tỉnh / Thành phố (63 tỉnh thành)"}
            </span>
            <ChevronDown className="w-4 h-4 text-slate-400" />
          </button>

          {isProvinceOpen && (
            <div className="absolute z-30 left-0 right-0 top-full mt-1 bg-white rounded-xl border border-slate-200 shadow-xl overflow-hidden max-h-60 flex flex-col">
              <div className="p-2 border-b border-slate-100 bg-slate-50 flex items-center gap-2">
                <Search className="w-3.5 h-3.5 text-slate-400 shrink-0 ml-1" />
                <input
                  type="text"
                  value={provinceSearch}
                  onChange={(e) => setProvinceSearch(e.target.value)}
                  placeholder="Tìm nhanh: Hà Nội, TP.HCM, Đà Nẵng..."
                  className="w-full bg-transparent text-xs text-slate-800 outline-hidden placeholder:text-slate-400"
                  autoFocus
                />
              </div>
              <div className="overflow-y-auto divide-y divide-slate-50">
                {filteredProvinces.map((p) => {
                  const isSelected = selectedProvince?.code === p.code;
                  return (
                    <button
                      key={p.code}
                      type="button"
                      onClick={() => handleSelectProvince(p)}
                      className={`w-full px-3.5 py-2.5 text-left text-xs flex items-center justify-between hover:bg-brand-blue-50 ${
                        isSelected ? "bg-brand-blue-50/70 text-brand-blue-700 font-semibold" : "text-slate-700"
                      }`}
                    >
                      <span>{p.fullName}</span>
                      {isSelected && <Check className="w-3.5 h-3.5 text-brand-blue-600" />}
                    </button>
                  );
                })}
              </div>
            </div>
          )}
        </div>

        {/* CẤP 2: XÃ / PHƯỜNG / ĐẶC KHU */}
        <div className="relative" ref={communeRef}>
          <label className="block text-xs font-semibold text-slate-700 mb-1.5 flex items-center justify-between">
            <span>
              Xã / Phường / Đặc khu <span className="text-rose-500">*</span>
            </span>
            {selectedProvince && (
              <span className="text-[11px] text-brand-blue-600">
                {filteredCommunes.length} đơn vị
              </span>
            )}
          </label>
          <button
            type="button"
            disabled={!selectedProvince}
            onClick={() => setIsCommuneOpen(!isCommuneOpen)}
            className={`w-full px-3.5 py-2.5 rounded-xl border text-left text-sm flex items-center justify-between ${
              !selectedProvince
                ? "bg-slate-100 border-slate-200 text-slate-400 cursor-not-allowed"
                : "bg-white border-slate-200 hover:border-slate-300 text-slate-900"
            }`}
          >
            <span className={selectedCommune ? "text-slate-900 font-medium" : "text-slate-400"}>
              {selectedCommune
                ? selectedCommune.fullName
                : selectedProvince
                ? "Chọn Xã, Phường hoặc Đặc khu"
                : "Vui lòng chọn Tỉnh/Thành trước"}
            </span>
            <ChevronDown className="w-4 h-4 text-slate-400" />
          </button>

          {isCommuneOpen && selectedProvince && (
            <div className="absolute z-30 left-0 right-0 top-full mt-1 bg-white rounded-xl border border-slate-200 shadow-xl overflow-hidden max-h-60 flex flex-col">
              <div className="p-2 border-b border-slate-100 bg-slate-50 flex items-center gap-2">
                <Search className="w-3.5 h-3.5 text-slate-400 shrink-0 ml-1" />
                <input
                  type="text"
                  value={communeSearch}
                  onChange={(e) => setCommuneSearch(e.target.value)}
                  placeholder="Tìm kiếm theo tên phường, xã hoặc quận cũ..."
                  className="w-full bg-transparent text-xs text-slate-800 outline-hidden placeholder:text-slate-400"
                  autoFocus
                />
              </div>
              <div className="overflow-y-auto divide-y divide-slate-50">
                {filteredCommunes.map((c) => {
                  const isSelected = selectedCommune?.code === c.code;
                  return (
                    <button
                      key={c.code}
                      type="button"
                      onClick={() => handleSelectCommune(c)}
                      className={`w-full px-3.5 py-2 text-left text-xs flex items-center justify-between hover:bg-brand-blue-50 ${
                        isSelected ? "bg-brand-blue-50/70 text-brand-blue-700 font-semibold" : "text-slate-700"
                      }`}
                    >
                      <div>
                        <span className="font-medium">{c.fullName}</span>
                        {c.legacyDistrictName && (
                          <span className="text-[10px] text-slate-400 block">
                            (Thuộc {c.legacyDistrictName})
                          </span>
                        )}
                        {(() => {
                          if (!communeSearch.trim()) return null;
                          const cleanQ = removeVietnameseAccents(communeSearch);
                          const matchedAlias = c.aliases?.find(
                            (a) =>
                              removeVietnameseAccents(a).includes(cleanQ) &&
                              removeVietnameseAccents(a) !== removeVietnameseAccents(c.name) &&
                              removeVietnameseAccents(a) !== removeVietnameseAccents(c.fullName) &&
                              !removeVietnameseAccents(c.name).includes(removeVietnameseAccents(a))
                          );
                          if (matchedAlias) {
                            return (
                              <span className="text-[10px] text-emerald-600 font-medium block">
                                (Địa danh cũ: {matchedAlias} - Hiện thuộc {c.fullName})
                              </span>
                            );
                          }
                          return null;
                        })()}
                      </div>
                      {isSelected && <Check className="w-3.5 h-3.5 text-brand-blue-600" />}
                    </button>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* 4. STREET / HOUSE NUMBER INPUT */}
      <div>
        <label className="block text-xs font-semibold text-slate-700 mb-1.5">
          Số nhà, tên đường, thôn / ngõ cụ thể <span className="text-rose-500">*</span>
        </label>
        <div className="relative">
          <input
            type="text"
            value={streetAddress}
            onChange={(e) => {
              setStreetAddress(e.target.value);
              setIsVerified(false); // Invalidate per Requirement 18
            }}
            placeholder="Ví dụ: Số 25 Lê Duẩn, Số 72 Trần Duy Hưng hoặc Tòa nhà Landmark..."
            className="w-full pl-9 pr-3.5 py-2.5 rounded-xl border border-slate-200 text-sm focus:outline-hidden focus:ring-2 focus:ring-brand-blue-500/20 focus:border-brand-blue-600 transition-all text-slate-800 placeholder:text-slate-400"
          />
          <Building className="w-4 h-4 text-slate-400 absolute left-3 top-3 pointer-events-none" />
        </div>
      </div>

      {/* 5. RECIPIENT INFORMATION (If enabled) */}
      {showRecipientFields && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5 pt-1">
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1.5">
              Họ và tên người nhận <span className="text-rose-500">*</span>
            </label>
            <div className="relative">
              <input
                type="text"
                value={recipientName}
                onChange={(e) => setRecipientName(e.target.value)}
                placeholder="Ví dụ: Nguyễn Văn A"
                className="w-full pl-9 pr-3.5 py-2.5 rounded-xl border border-slate-200 text-sm focus:outline-hidden focus:ring-2 focus:ring-brand-blue-500/20 focus:border-brand-blue-600 transition-all text-slate-800 placeholder:text-slate-400"
              />
              <User className="w-4 h-4 text-slate-400 absolute left-3 top-3 pointer-events-none" />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1.5">
              Số điện thoại nhận hàng <span className="text-rose-500">*</span>
            </label>
            <div className="relative">
              <input
                type="tel"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                placeholder="Ví dụ: 0912 345 678"
                className="w-full pl-9 pr-3.5 py-2.5 rounded-xl border border-slate-200 text-sm focus:outline-hidden focus:ring-2 focus:ring-brand-blue-500/20 focus:border-brand-blue-600 transition-all text-slate-800 placeholder:text-slate-400"
              />
              <Phone className="w-4 h-4 text-slate-400 absolute left-3 top-3 pointer-events-none" />
            </div>
          </div>
        </div>
      )}

      {/* 6. DELIVERY NOTE (Optional) */}
      <div>
        <label className="block text-xs font-semibold text-slate-700 mb-1.5">
          Ghi chú giao hàng{" "}
          <span className="text-slate-400 font-normal">(Ví dụ: Nhà cổng xanh, gọi trước khi đến...)</span>
        </label>
        <input
          type="text"
          value={deliveryNote}
          onChange={(e) => setDeliveryNote(e.target.value)}
          placeholder="Ghi chú thêm cho Dược sĩ hoặc Shipper..."
          className="w-full px-3.5 py-2 rounded-xl border border-slate-200 text-xs focus:outline-hidden focus:ring-2 focus:ring-brand-blue-500/20 focus:border-brand-blue-600 transition-all text-slate-800 placeholder:text-slate-400"
        />
      </div>

      {/* Default Address Checkbox */}
      <div className="flex items-center gap-2 pt-1">
        <input
          type="checkbox"
          id="is-default-checkbox"
          checked={isDefault}
          onChange={(e) => setIsDefault(e.target.checked)}
          className="w-4 h-4 rounded text-brand-blue-600 focus:ring-brand-blue-500 border-slate-300 cursor-pointer"
        />
        <label
          htmlFor="is-default-checkbox"
          className="text-xs text-slate-700 cursor-pointer select-none flex items-center gap-1"
        >
          <BookmarkCheck className="w-3.5 h-3.5 text-brand-blue-600" />
          Đặt làm địa chỉ nhận hàng mặc định
        </label>
      </div>

      {/* Error alert */}
      {errorMessage && (
        <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-start gap-2">
          <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* 7. ADDRESS PREVIEW & CONFIRMATION (Requirement 10) */}
      {formattedAddress && (
        <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200 text-xs space-y-1">
          <span className="font-bold text-slate-900 block flex items-center gap-1.5">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
            Địa chỉ đầy đủ đã chuẩn hóa:
          </span>
          <p className="text-slate-700 font-medium">{formattedAddress}</p>
        </div>
      )}

      {/* CTA Buttons */}
      <div className="pt-2 flex items-center justify-between gap-3 border-t border-slate-100">
        {onCancel ? (
          <button
            type="button"
            onClick={onCancel}
            disabled={isSubmitting}
            className="px-4 py-2.5 rounded-xl border border-slate-300 text-slate-700 hover:bg-slate-50 text-xs font-semibold transition-colors"
          >
            Hủy
          </button>
        ) : (
          <div className="text-[11px] text-slate-400">
            {providerStatus?.report.includes("NOT CONFIGURED")
              ? "OpenStreetMap & Photon Engine"
              : "Google Places Platform"}
          </div>
        )}

        <button
          type="button"
          onClick={() => handleSubmit()}
          disabled={isSubmitting}
          className="px-6 py-2.5 rounded-xl bg-brand-blue-600 hover:bg-brand-blue-700 text-white text-xs font-bold transition-all shadow-xs flex items-center gap-1.5 disabled:bg-slate-300 disabled:cursor-not-allowed ml-auto"
        >
          {isSubmitting ? (
            <>
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
              Đang xác minh...
            </>
          ) : (
            <>
              <Check className="w-4 h-4" />
              {submitButtonText}
            </>
          )}
        </button>
      </div>
    </div>
  );
}
