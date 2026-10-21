"use client";

import React, { useState, useEffect, useMemo } from "react";
import {
  User,
  Phone,
  Mail,
  MapPin,
  Clock,
  CheckCircle2,
  AlertCircle,
  Edit3,
  Check,
  Building,
  Plus,
  BookOpen,
  X,
  Compass,
} from "lucide-react";
import { FulfillmentType } from "./FulfillmentSelector";
import {
  customerAddressService,
  CustomerAddressItem,
  ShippingCalculationResult,
} from "@/services/customerAddressService";
import { CustomerAddressModal } from "@/components/account/CustomerAddressModal";
import AddressEditorV2 from "@/components/address/AddressEditorV2";
import { useAuth } from "@/lib/auth/auth-context";

export interface NearestWarehouseInfo {
  warehouse_id: number;
  warehouse_code: string;
  warehouse_name: string;
  warehouse_address: string;
  distance_km: number;
  estimated_delivery_time: string;
  navigation_url: string;
  lat?: number;
  lng?: number;
}

export interface StructuredAddress {
  provinceCode: string;
  provinceName: string;
  communeCode: string;
  communeName: string;
  communeType: "ward" | "commune" | "special_zone";
  streetAddress: string;
  fullAddress: string;
  lat: number;
  lng: number;
  isVerified: boolean;
  placeId?: string;
  deliveryNote?: string;
  recipientName?: string;
  phone?: string;
  // Legacy aliases
  districtCode?: string;
  districtName?: string;
  wardCode?: string;
  wardName?: string;
}

export type AdminProvince = any;
export type AdminDistrict = any;
export type AdminWard = any;

export interface ShippingAddressFormProps {
  fulfillmentType: FulfillmentType;
  customerName: string;
  setCustomerName: (v: string) => void;
  customerPhone: string;
  setCustomerPhone: (v: string) => void;
  customerEmail: string;
  setCustomerEmail: (v: string) => void;
  shippingAddress?: string;
  setShippingAddress?: (v: string) => void;
  orderNote: string;
  setOrderNote: (v: string) => void;
  selectedStoreId?: number | string;
  setSelectedStoreId?: (v: number | string) => void;
  isAddressVerified?: boolean;
  setIsAddressVerified?: (v: boolean) => void;
  isVerified?: boolean;
  setIsVerified?: (v: boolean) => void;
  verifiedAddress: StructuredAddress | null;
  setVerifiedAddress: (addr: StructuredAddress | null) => void;
  nearestWarehouse: NearestWarehouseInfo | null;
  setNearestWarehouse?: (wh: NearestWarehouseInfo | null) => void;
  subtotal?: number;
  onShippingFeeCalculated?: (fee: number) => void;
  confirmAddressRef?: React.MutableRefObject<(() => Promise<StructuredAddress | null>) | null>;

  // Compatibility props with cart/page.tsx
  selectedProvinceCode?: string;
  setSelectedProvinceCode?: (v: string) => void;
  selectedDistrictCode?: string;
  setSelectedDistrictCode?: (v: string) => void;
  selectedWardCode?: string;
  setSelectedWardCode?: (v: string) => void;
  wardName?: string;
  setWardName?: (v: string) => void;
  streetAddress?: string;
  setStreetAddress?: (v: string) => void;
  needInvoice?: boolean;
  setNeedInvoice?: (v: boolean) => void;
  taxCode?: string;
  setTaxCode?: (v: string) => void;
  companyName?: string;
  setCompanyName?: (v: string) => void;
  adminTree?: any[];
  coords?: { lat: number; lng: number } | null;
  setCoords?: (c: { lat: number; lng: number } | null) => void;
  isLocating?: boolean;
  onGetLocation?: () => void;
}

export default function ShippingAddressForm({
  fulfillmentType,
  customerName,
  setCustomerName,
  customerPhone,
  setCustomerPhone,
  customerEmail,
  setCustomerEmail,
  shippingAddress,
  setShippingAddress,
  orderNote,
  setOrderNote,
  isAddressVerified: propIsAddressVerified,
  setIsAddressVerified: propSetIsAddressVerified,
  isVerified: propIsVerified,
  setIsVerified: propSetIsVerified,
  verifiedAddress,
  setVerifiedAddress,
  nearestWarehouse,
  setNearestWarehouse,
  subtotal = 0,
  onShippingFeeCalculated,
  confirmAddressRef,
}: ShippingAddressFormProps) {
  const { user, isAuthenticated } = useAuth();

  const isAddressVerified =
    propIsVerified !== undefined ? propIsVerified : propIsAddressVerified || false;
  const setIsAddressVerified = (v: boolean) => {
    if (propSetIsVerified) propSetIsVerified(v);
    if (propSetIsAddressVerified) propSetIsAddressVerified(v);
  };

  const editorSubmitRef = React.useRef<(() => Promise<any | null>) | null>(null);

  React.useEffect(() => {
    if (confirmAddressRef) {
      confirmAddressRef.current = async () => {
        if (editorSubmitRef.current) {
          const data = await editorSubmitRef.current();
          if (!data) return null;
          return {
            provinceCode: data.province_code,
            provinceName: data.province_name,
            communeCode: data.commune_code,
            communeName: data.commune_name,
            communeType: "ward",
            streetAddress: data.address_line,
            fullAddress: data.formatted_address,
            lat: data.lat,
            lng: data.lng,
            isVerified: true,
            placeId: data.place_id,
            deliveryNote: data.delivery_note,
            recipientName: data.recipient_name,
            phone: data.phone,
            wardCode: data.commune_code,
            wardName: data.commune_name,
          };
        }
        return null;
      };
    }
  }, [confirmAddressRef]);

  // Saved addresses state
  const [savedAddresses, setSavedAddresses] = useState<CustomerAddressItem[]>([]);
  const [selectedAddressId, setSelectedAddressId] = useState<number | null>(null);
  const [isPickerModalOpen, setIsPickerModalOpen] = useState(false);
  const [isAddressModalOpen, setIsAddressModalOpen] = useState(false);
  const [addressToEdit, setAddressToEdit] = useState<CustomerAddressItem | null>(null);
  const [isEditingAddress, setIsEditingAddress] = useState(false);

  // Helper: Calculate shipping fee and nearest warehouse
  const calculateShippingForLocation = async (
    lat: number,
    lng: number,
    provCode?: string,
    distCode?: string
  ) => {
    try {
      const calcResult = await customerAddressService.calculateShipping({
        lat,
        lng,
        province_code: provCode,
        district_code: distCode,
        order_total: subtotal,
      });

      if (calcResult && setNearestWarehouse) {
        setNearestWarehouse({
          warehouse_id: calcResult.warehouse_id || 1,
          warehouse_code: calcResult.warehouse_code || "KHO-HCM-01",
          warehouse_name: calcResult.warehouse_name,
          warehouse_address: calcResult.warehouse_address,
          distance_km: calcResult.distance_km,
          estimated_delivery_time: calcResult.estimated_delivery,
          navigation_url: "",
          lat,
          lng,
        });
      }

      if (onShippingFeeCalculated && calcResult) {
        onShippingFeeCalculated(calcResult.shipping_fee);
      }
    } catch (e) {
      console.warn("Error calculating shipping fee:", e);
    }
  };

  // Helper: Apply a saved address item
  const applySavedAddress = (addr: CustomerAddressItem) => {
    setSelectedAddressId(addr.id);
    setIsEditingAddress(false);

    if (addr.recipient_name) setCustomerName(addr.recipient_name);
    if (addr.phone) setCustomerPhone(addr.phone);
    if (addr.delivery_note && !orderNote) setOrderNote(addr.delivery_note);

    const lat = addr.lat || 10.7769;
    const lng = addr.lng || 106.7009;
    // FIX: Không tự gán verified = true nếu tọa độ chỉ là mặc định TP.HCM hoặc thiếu GPS
    const isActuallyVerified = Boolean(
      addr.is_verified &&
      addr.lat &&
      addr.lng &&
      !(Math.abs(addr.lat - 10.7769) < 0.0001 && Math.abs(addr.lng - 106.7009) < 0.0001)
    );

    const fullAddr =
      addr.formatted_address ||
      `${addr.address_line}, ${addr.commune_name || ""}, ${addr.province_name || ""}`;

    const structured: StructuredAddress = {
      provinceCode: addr.province_code || "",
      provinceName: addr.province_name || "",
      communeCode: addr.commune_code || "",
      communeName: addr.commune_name || "",
      communeType: "ward",
      streetAddress: addr.address_line,
      fullAddress: fullAddr,
      lat,
      lng,
      isVerified: isActuallyVerified,
      placeId: addr.place_id || undefined,
      deliveryNote: addr.delivery_note || undefined,
      districtName: addr.district_code || undefined,
      wardCode: addr.commune_code || addr.ward_code || undefined,
      wardName: addr.commune_name || undefined,
    };

    setVerifiedAddress(structured);
    if (setShippingAddress) {
      setShippingAddress(fullAddr);
    }
    setIsAddressVerified(isActuallyVerified);

    calculateShippingForLocation(lat, lng, addr.province_code, addr.district_code);
  };

  // Load saved addresses on mount or auth change
  useEffect(() => {
    async function loadAddresses() {
      try {
        const list = await customerAddressService.listAddresses();
        setSavedAddresses(list);

        if (list.length > 0 && !verifiedAddress) {
          const defaultAddr = list.find((a) => a.is_default) || list[0];
          applySavedAddress(defaultAddr);
        }
      } catch (err) {
        console.warn("Could not fetch saved addresses", err);
      }
    }

    if (fulfillmentType === "DELIVERY") {
      loadAddresses();
    }
  }, [fulfillmentType, isAuthenticated]);

  // Handle Save from AddressEditorV2 (Single Source of Truth)
  const handleEditorSave = async (data: any) => {
    setIsEditingAddress(false);
    setCustomerName(data.recipient_name);
    setCustomerPhone(data.phone);
    if (data.delivery_note) setOrderNote(data.delivery_note);

    const structured: StructuredAddress = {
      provinceCode: data.province_code,
      provinceName: data.province_name,
      communeCode: data.commune_code,
      communeName: data.commune_name,
      communeType: "ward",
      streetAddress: data.address_line,
      fullAddress: data.formatted_address,
      lat: data.lat,
      lng: data.lng,
      isVerified: true,
      placeId: data.place_id,
      deliveryNote: data.delivery_note,
      wardCode: data.commune_code,
      wardName: data.commune_name,
    };

    setVerifiedAddress(structured);
    if (setShippingAddress) {
      setShippingAddress(data.formatted_address);
    }
    setIsAddressVerified(true);

    // Save to address book if authenticated
    if (isAuthenticated) {
      try {
        const saved = await customerAddressService.saveAddress({
          recipient_name: data.recipient_name,
          phone: data.phone,
          address_line: data.address_line,
          province_code: data.province_code,
          province_name: data.province_name,
          commune_code: data.commune_code,
          commune_name: data.commune_name,
          lat: data.lat,
          lng: data.lng,
          place_id: data.place_id,
          delivery_note: data.delivery_note,
          is_default: data.is_default || savedAddresses.length === 0,
        });
        if (saved) {
          setSavedAddresses((prev) => [saved, ...prev]);
          setSelectedAddressId(saved.id);
        }
      } catch (e) {
        console.warn("Could not save address to address book", e);
      }
    }

    // Calculate shipping
    calculateShippingForLocation(data.lat, data.lng, data.province_code);
  };

  const selectedSavedItem = useMemo(() => {
    if (!selectedAddressId) return null;
    return savedAddresses.find((a) => a.id === selectedAddressId) || null;
  }, [selectedAddressId, savedAddresses]);

  return (
    <div id="shipping-address-section" className="bg-white rounded-2xl border border-slate-200/90 shadow-xs overflow-hidden scroll-mt-24">
      {/* Header */}
      <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/60">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-brand-blue-50 text-brand-blue-600 flex items-center justify-center font-bold text-sm">
            1
          </div>
          <div>
            <h3 className="font-bold text-slate-800 text-sm sm:text-base">
              Thông tin nhận hàng
            </h3>
            <p className="text-[11.5px] text-slate-500">
              {fulfillmentType === "DELIVERY"
                ? "Mô hình 2 cấp: Tỉnh/Thành phố → Xã/Phường/Đặc khu → Xác thực vị trí Google-like"
                : "Nhận thuốc trực tiếp tại chi nhánh H4CARE"}
            </p>
          </div>
        </div>

        {fulfillmentType === "DELIVERY" && isAddressVerified && !isEditingAddress && (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200/80">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
            Đã xác thực vị trí
          </span>
        )}
      </div>

      <div className="p-5 sm:p-6 space-y-5">
        {/* STORE_PICKUP Receiver Fields */}
        {fulfillmentType === "STORE_PICKUP" && (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pb-2 border-b border-slate-100">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                Họ và tên người nhận thuốc <span className="text-rose-500">*</span>
              </label>
              <div className="relative">
                <input
                  type="text"
                  value={customerName}
                  onChange={(e) => setCustomerName(e.target.value)}
                  placeholder="Ví dụ: Nguyễn Văn A"
                  className="w-full pl-9 pr-3.5 py-2.5 rounded-xl border border-slate-200 text-sm focus:outline-hidden focus:ring-2 focus:ring-brand-blue-500/20 focus:border-brand-blue-600 transition-all text-slate-800 placeholder:text-slate-400"
                />
                <User className="w-4 h-4 text-slate-400 absolute left-3 top-3 pointer-events-none" />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                Số điện thoại liên hệ <span className="text-rose-500">*</span>
              </label>
              <div className="relative">
                <input
                  type="tel"
                  value={customerPhone}
                  onChange={(e) => setCustomerPhone(e.target.value)}
                  placeholder="Ví dụ: 0912 345 678"
                  className="w-full pl-9 pr-3.5 py-2.5 rounded-xl border border-slate-200 text-sm focus:outline-hidden focus:ring-2 focus:ring-brand-blue-500/20 focus:border-brand-blue-600 transition-all text-slate-800 placeholder:text-slate-400"
                />
                <Phone className="w-4 h-4 text-slate-400 absolute left-3 top-3 pointer-events-none" />
              </div>
            </div>
          </div>
        )}

        {/* Email receipt field */}
        <div>
          <label className="block text-xs font-semibold text-slate-700 mb-1.5">
            Email nhận thông báo đơn hàng{" "}
            <span className="text-slate-400 font-normal">(Không bắt buộc)</span>
          </label>
          <div className="relative">
            <input
              type="email"
              value={customerEmail}
              onChange={(e) => setCustomerEmail(e.target.value)}
              placeholder="ví dụ: email@gmail.com để nhận hóa đơn"
              className="w-full pl-9 pr-3.5 py-2.5 rounded-xl border border-slate-200 text-sm focus:outline-hidden focus:ring-2 focus:ring-brand-blue-500/20 focus:border-brand-blue-600 transition-all text-slate-800 placeholder:text-slate-400"
            />
            <Mail className="w-4 h-4 text-slate-400 absolute left-3 top-3 pointer-events-none" />
          </div>
        </div>

        {/* DELIVERY FLOW */}
        {fulfillmentType === "DELIVERY" && (
          <div className="space-y-4 pt-1">
            {/* SAVED ADDRESS SELECTOR BANNER */}
            {savedAddresses.length > 0 && (
              <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200/90 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  <div className="w-7 h-7 rounded-lg bg-brand-blue-100/70 text-brand-blue-700 flex items-center justify-center shrink-0">
                    <BookOpen className="w-4 h-4" />
                  </div>
                  <div>
                    <span className="text-xs font-bold text-slate-800">
                      Sổ địa chỉ của bạn ({savedAddresses.length} địa chỉ)
                    </span>
                    <p className="text-[11px] text-slate-500">
                      {selectedSavedItem
                        ? `Đang chọn: ${selectedSavedItem.recipient_name} - ${selectedSavedItem.address_line}`
                        : "Chọn địa chỉ sẵn có để thanh toán ngay"}
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-2 w-full sm:w-auto">
                  <button
                    type="button"
                    onClick={() => setIsPickerModalOpen(true)}
                    className="flex-1 sm:flex-initial px-3 py-1.5 rounded-lg border border-brand-blue-600 text-brand-blue-600 hover:bg-brand-blue-50 text-xs font-bold transition-colors shadow-2xs"
                  >
                    Đổi địa chỉ ({savedAddresses.length})
                  </button>

                  <button
                    type="button"
                    onClick={() => {
                      setAddressToEdit(null);
                      setIsAddressModalOpen(true);
                    }}
                    className="flex-1 sm:flex-initial inline-flex items-center justify-center gap-1 px-3 py-1.5 rounded-lg bg-brand-blue-600 hover:bg-brand-blue-700 text-white text-xs font-bold transition-colors shadow-2xs"
                  >
                    <Plus className="w-3.5 h-3.5" />
                    Thêm mới
                  </button>
                </div>
              </div>
            )}

            {/* STATE B: VERIFIED SUMMARY CARD (Requirement 10 & 12) */}
            {isAddressVerified && verifiedAddress && !isEditingAddress ? (
              <div className="p-4 rounded-xl border-2 border-emerald-500/40 bg-emerald-50/30 space-y-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-start gap-2.5">
                    <div className="w-7 h-7 rounded-lg bg-emerald-100 text-emerald-700 flex items-center justify-center shrink-0 mt-0.5">
                      <CheckCircle2 className="w-4 h-4" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-xs font-bold text-emerald-800 uppercase tracking-wider">
                          Địa chỉ giao hàng đã xác thực
                        </span>
                        {selectedSavedItem?.is_default && (
                          <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-100 text-amber-800 border border-amber-200">
                            Mặc định
                          </span>
                        )}
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-800 border border-emerald-200">
                          Đã xác minh vị trí
                        </span>
                      </div>

                      <div className="mt-1 flex items-center gap-2">
                        <span className="font-bold text-slate-900 text-sm">
                          {customerName}
                        </span>
                        <span className="text-slate-300">•</span>
                        <span className="text-xs text-slate-600 font-mono">
                          {customerPhone}
                        </span>
                      </div>

                      <p className="text-sm font-medium text-slate-800 mt-0.5">
                        {verifiedAddress.fullAddress}
                      </p>

                      <p className="text-xs text-slate-500 mt-1 flex items-center gap-2 flex-wrap font-mono">
                        <span>
                          GPS: ({verifiedAddress.lat.toFixed(4)}, {verifiedAddress.lng.toFixed(4)})
                        </span>
                        {verifiedAddress.districtName && (
                          <span className="text-slate-400 text-[11px] font-sans">
                            • Khu vực: {verifiedAddress.districtName}
                          </span>
                        )}
                      </p>

                      {orderNote && (
                        <p className="text-xs text-slate-600 mt-1 italic">
                          Ghi chú: {orderNote}
                        </p>
                      )}
                    </div>
                  </div>

                  <button
                    type="button"
                    onClick={() => setIsEditingAddress(true)}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-300 hover:border-brand-blue-500 text-xs font-semibold text-slate-700 hover:text-brand-blue-600 bg-white transition-colors shadow-2xs shrink-0"
                  >
                    <Edit3 className="w-3.5 h-3.5" />
                    Chỉnh sửa
                  </button>
                </div>

                {/* Nearest warehouse banner */}
                {nearestWarehouse && (
                  <div className="pt-2.5 border-t border-emerald-200/60 flex items-center justify-between text-xs text-emerald-800 flex-wrap gap-2">
                    <span className="flex items-center gap-1.5 font-medium">
                      <Clock className="w-3.5 h-3.5 text-emerald-600" />
                      Điều phối từ: <strong>{nearestWarehouse.warehouse_name}</strong> (cách {nearestWarehouse.distance_km} km)
                    </span>
                    <span className="text-emerald-700 font-semibold bg-emerald-100/70 px-2 py-0.5 rounded-md">
                      {nearestWarehouse.estimated_delivery_time}
                    </span>
                  </div>
                )}
              </div>
            ) : (
              /* STATE A: UNIFIED ADDRESS EDITOR (Single Source of Truth, Requirement 13) */
              <div className="p-4 rounded-xl border border-slate-200 bg-slate-50/40">
                <AddressEditorV2
                  initialData={
                    verifiedAddress
                      ? {
                          recipient_name: customerName,
                          phone: customerPhone,
                          address_line: verifiedAddress.streetAddress,
                          province_code: verifiedAddress.provinceCode,
                          province_name: verifiedAddress.provinceName,
                          commune_code: verifiedAddress.communeCode,
                          commune_name: verifiedAddress.communeName,
                          formatted_address: verifiedAddress.fullAddress,
                          lat: verifiedAddress.lat,
                          lng: verifiedAddress.lng,
                          delivery_note: orderNote,
                          is_verified: isAddressVerified,
                        }
                      : null
                  }
                  prefillName={customerName || user?.fullName}
                  prefillPhone={customerPhone || user?.phone}
                  showRecipientFields={true}
                  submitButtonText="Xác nhận địa chỉ này"
                  nearestWarehouse={nearestWarehouse}
                  onRegisterSubmit={(fn) => {
                    editorSubmitRef.current = fn;
                  }}
                  onSave={handleEditorSave}
                  onCancel={verifiedAddress ? () => setIsEditingAddress(false) : undefined}
                />
              </div>
            )}
          </div>
        )}
      </div>

      {/* MODAL 1: SAVED ADDRESS PICKER MODAL */}
      {isPickerModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs animate-in fade-in duration-150">
          <div className="bg-white rounded-2xl max-w-lg w-full overflow-hidden shadow-2xl border border-slate-200 flex flex-col max-h-[85vh]">
            <div className="p-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/80">
              <div className="flex items-center gap-2">
                <BookOpen className="w-4 h-4 text-brand-blue-600" />
                <h3 className="font-bold text-slate-900 text-sm">
                  Chọn địa chỉ nhận hàng từ Sổ địa chỉ
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setIsPickerModalOpen(false)}
                className="p-1 rounded-lg hover:bg-slate-200/60 text-slate-400 hover:text-slate-600 transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="p-4 overflow-y-auto space-y-3 flex-1">
              {savedAddresses.map((addr) => {
                const isSelected = selectedAddressId === addr.id;
                return (
                  <div
                    key={addr.id}
                    onClick={() => {
                      applySavedAddress(addr);
                      setIsPickerModalOpen(false);
                    }}
                    className={`p-3.5 rounded-xl border cursor-pointer transition-all ${
                      isSelected
                        ? "border-brand-blue-600 bg-brand-blue-50/40 ring-2 ring-brand-blue-500/10 shadow-xs"
                        : "border-slate-200 hover:border-slate-300 hover:bg-slate-50"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-slate-900 text-xs sm:text-sm">
                          {addr.recipient_name}
                        </span>
                        <span className="text-slate-300">•</span>
                        <span className="text-xs text-slate-600 font-mono">
                          {addr.phone}
                        </span>
                      </div>

                      <div className="flex items-center gap-1.5 shrink-0">
                        {addr.is_default && (
                          <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-100 text-amber-800 border border-amber-200">
                            Mặc định
                          </span>
                        )}
                        {addr.is_verified && (
                          <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-800 border border-emerald-200">
                            Đã xác thực
                          </span>
                        )}
                      </div>
                    </div>

                    <p className="text-xs text-slate-700 mt-1 font-medium">
                      {addr.formatted_address || addr.address_line}
                    </p>

                    {addr.delivery_note && (
                      <p className="text-[11px] text-slate-500 mt-1 italic">
                        Ghi chú: {addr.delivery_note}
                      </p>
                    )}
                  </div>
                );
              })}
            </div>

            <div className="p-4 border-t border-slate-100 bg-slate-50 flex items-center justify-between gap-3">
              <button
                type="button"
                onClick={() => {
                  setIsPickerModalOpen(false);
                  setAddressToEdit(null);
                  setIsAddressModalOpen(true);
                }}
                className="inline-flex items-center gap-1.5 text-xs font-bold text-brand-blue-600 hover:text-brand-blue-700"
              >
                <Plus className="w-3.5 h-3.5" />
                Thêm địa chỉ mới vào sổ
              </button>

              <button
                type="button"
                onClick={() => setIsPickerModalOpen(false)}
                className="px-4 py-2 rounded-xl bg-slate-900 hover:bg-slate-800 text-white text-xs font-bold transition-colors"
              >
                Đóng
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL 2: ADD/EDIT ADDRESS MODAL */}
      <CustomerAddressModal
        isOpen={isAddressModalOpen}
        onClose={() => {
          setIsAddressModalOpen(false);
          setAddressToEdit(null);
        }}
        addressToEdit={addressToEdit}
        prefillName={customerName}
        prefillPhone={customerPhone}
        onSaved={(savedAddr) => {
          setSavedAddresses((prev) => {
            const exists = prev.some((a) => a.id === savedAddr.id);
            if (exists) {
              return prev.map((a) => (a.id === savedAddr.id ? savedAddr : a));
            }
            return [savedAddr, ...prev];
          });
          applySavedAddress(savedAddr);
          setIsAddressModalOpen(false);
          setAddressToEdit(null);
        }}
      />
    </div>
  );
}
