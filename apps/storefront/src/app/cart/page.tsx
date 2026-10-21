"use client";

import React, { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { Header } from "@/components/layout/Header";
import { Footer } from "@/components/layout/Footer";
import { useAuth } from "@/lib/auth/auth-context";
import { AlertCircle, X } from "lucide-react";

import CheckoutHeader from "@/components/checkout/CheckoutHeader";
import CartItemsTable, { CartItem } from "@/components/checkout/CartItemsTable";
import FulfillmentSelector, {
  FulfillmentType,
  PHARMACY_STORES,
} from "@/components/checkout/FulfillmentSelector";
import ShippingAddressForm, {
  AdminProvince,
  NearestWarehouseInfo,
  StructuredAddress,
} from "@/components/checkout/ShippingAddressForm";
import PaymentMethodSelector, {
  PaymentMethod,
} from "@/components/checkout/PaymentMethodSelector";
import OrderSummaryCard from "@/components/checkout/OrderSummaryCard";
import EmptyCartState from "@/components/checkout/EmptyCartState";
import OrderSuccessView, {
  OrderSuccessData,
} from "@/components/checkout/OrderSuccessView";
import MobileStickyCheckoutBar from "@/components/checkout/MobileStickyCheckoutBar";
import SepayVietQrModal from "@/components/checkout/SepayVietQrModal";
import PendingOrderView, { PendingOrderData } from "@/components/checkout/PendingOrderView";
import ChangePaymentMethodModal, {
  PaymentMethodType,
} from "@/components/checkout/ChangePaymentMethodModal";
import { placesService } from "@/services/placesService";


export default function CartPage() {
  const router = useRouter();
  const { user, isAuthenticated } = useAuth();
  const summaryRef = useRef<HTMLDivElement>(null);
  const confirmAddressRef = useRef<(() => Promise<StructuredAddress | null>) | null>(null);

  // Cart state
  const [items, setItems] = useState<CartItem[]>([]);
  const [isLoaded, setIsLoaded] = useState(false);

  // Fulfillment & Store Pickup state
  const [fulfillmentType, setFulfillmentType] = useState<FulfillmentType>("DELIVERY");
  const [selectedStoreId, setSelectedStoreId] = useState<string>("h4care-tb");

  // Customer & Shipping state
  const [customerName, setCustomerName] = useState("");
  const [customerPhone, setCustomerPhone] = useState("");
  const [customerEmail, setCustomerEmail] = useState("");
  const [selectedWardCode, setSelectedWardCode] = useState("");
  const [wardName, setWardName] = useState("");
  const [streetAddress, setStreetAddress] = useState("");
  const [orderNote, setOrderNote] = useState("");
  const [isAddressVerified, setIsAddressVerified] = useState(false);
  const [verifiedAddress, setVerifiedAddress] = useState<StructuredAddress | null>(null);

  // Invoice state
  const [needInvoice, setNeedInvoice] = useState(false);
  const [taxCode, setTaxCode] = useState("");
  const [companyName, setCompanyName] = useState("");

  // Payment method
  const [paymentMethod, setPaymentMethod] = useState<PaymentMethod>("COD");
  const [sepayModalData, setSepayModalData] = useState<{
    isOpen: boolean;
    orderCode: string;
    paymentCode: string;
    amount: number;
    bankName?: string;
    accountNumber?: string;
    accountHolder?: string;
    qrCodeUrl?: string;
    expiresAt?: string;
  } | null>(null);
  const [showChangeMethodModal, setShowChangeMethodModal] = useState(false);

  // Vouchers state
  const [voucherCode, setVoucherCode] = useState("");
  const [appliedVoucher, setAppliedVoucher] = useState<string | null>(null);
  const [discount, setDiscount] = useState<number>(0);
  const [voucherError, setVoucherError] = useState("");

  // Administrative Units & Geolocation
  const [adminTree, setAdminTree] = useState<AdminProvince[]>([]);
  const [selectedProvinceCode, setSelectedProvinceCode] = useState<string>("79");
  const [selectedDistrictCode, setSelectedDistrictCode] = useState<string>("760");
  const [coords, setCoords] = useState<{ lat: number; lng: number } | null>(null);
  const [nearestWarehouse, setNearestWarehouse] = useState<NearestWarehouseInfo | null>(null);
  const [isLocating, setIsLocating] = useState<boolean>(false);

  // Form submission & feedback
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [orderSuccess, setOrderSuccess] = useState<OrderSuccessData | null>(null);
  const [pendingOrder, setPendingOrder] = useState<PendingOrderData | null>(null);


  // Idempotency key to prevent duplicate order placement
  const idempotencyKeyRef = useRef<string>("");
  const [validationAlert, setValidationAlert] = useState<{
    type: "warning" | "error";
    message: string;
  } | null>(null);

  // Tự động đồng bộ tọa độ và mã tỉnh vào state tính cước khi địa chỉ được xác nhận
  useEffect(() => {
    if (verifiedAddress) {
      if (verifiedAddress.provinceCode && verifiedAddress.provinceCode !== selectedProvinceCode) {
        setSelectedProvinceCode(verifiedAddress.provinceCode);
      }
      if (verifiedAddress.communeCode && verifiedAddress.communeCode !== selectedDistrictCode) {
        setSelectedDistrictCode(verifiedAddress.communeCode);
      }
      if (verifiedAddress.lat && verifiedAddress.lng) {
        setCoords({ lat: verifiedAddress.lat, lng: verifiedAddress.lng });
      }
    }
  }, [verifiedAddress]);

  useEffect(() => {
    if (!idempotencyKeyRef.current) {
      idempotencyKeyRef.current =
        typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
          ? crypto.randomUUID()
          : `IDEM-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
    }
  }, []);

  const validateCartWithServer = async (cartItems: CartItem[]) => {
    if (!cartItems || cartItems.length === 0) {
      setValidationAlert(null);
      return;
    }
    try {
      const payload = {
        items: cartItems.map((it) => {
          let dbId = it.dbId;
          if (!dbId && it.id.startsWith("pt-")) dbId = parseInt(it.id.replace("pt-", ""), 10);
          else if (!dbId && /^\d+$/.test(it.id)) dbId = parseInt(it.id, 10);
          return {
            product_id: dbId || 0,
            sku_id: it.skuId,
            quantity: it.quantity,
            client_price: it.salePrice || it.price,
          };
        }),
      };
      const res = await fetch("/api/v1/store/orders/cart/validate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (res.ok) {
        const data = await res.json();
        if (data && Array.isArray(data.items)) {
          const stockIssues = data.items.filter((resIt: any) => !resIt.can_checkout);
          const priceChanges = data.items.filter((resIt: any) => resIt.price_changed);
          if (stockIssues.length > 0) {
            setValidationAlert({
              type: "error",
              message: `Một số sản phẩm không đủ điều kiện đặt hàng: ${stockIssues.map((s: any) => `${s.product_name} (${s.rejection_reason})`).join("; ")}`,
            });
          } else if (priceChanges.length > 0) {
            setValidationAlert({
              type: "warning",
              message: "Đơn giá niêm yết của một số sản phẩm đã được máy chủ cập nhật. Tổng tiền sẽ tính chính xác theo giá mới.",
            });
          } else {
            setValidationAlert(null);
          }
        }
      }
    } catch (e) {
      console.warn("Lỗi kiểm tra giỏ hàng với máy chủ:", e);
    }
  };

  // Khôi phục và đối soát đơn hàng chờ thanh toán từ localStorage & backend
  useEffect(() => {
    if (typeof window === "undefined") return;
    const rawPending = localStorage.getItem("h4care_pending_order");
    if (!rawPending) return;

    try {
      const parsed: PendingOrderData = JSON.parse(rawPending);
      if (!parsed?.orderCode) return;

      const orderToken =
        parsed.orderToken ||
        localStorage.getItem(`h4care_order_token_${parsed.orderCode}`) ||
        localStorage.getItem("h4care_latest_order_token") ||
        "";

      const token =
        localStorage.getItem("pharmatrust_access_token") ||
        localStorage.getItem("pharmatrust_token") ||
        localStorage.getItem("h4care_auth_token") ||
        localStorage.getItem("access_token") ||
        null;

      const headers: Record<string, string> = {};
      if (token) headers["Authorization"] = `Bearer ${token}`;
      if (orderToken) headers["X-Order-Token"] = orderToken;

      fetch(`/api/v1/payments/orders/${encodeURIComponent(parsed.orderCode)}/status`, { headers })
        .then((r) => r.json())
        .then((statusData) => {
          if (statusData?.payment_status === "PAID" || statusData?.status === "PAID") {
            localStorage.removeItem("h4care_pending_order");
            router.push(`/checkout/result?order_code=${encodeURIComponent(parsed.orderCode)}`);
          } else if (statusData?.order_status === "CANCELLED") {
            localStorage.removeItem("h4care_pending_order");
          } else {
            // Làm giàu dữ liệu đơn từ server nếu có
            if (statusData?.sepay_details) {
              parsed.sepayData = {
                isOpen: false,
                orderCode: parsed.orderCode,
                ...statusData.sepay_details,
              };
            }
            if (Array.isArray(statusData?.items) && statusData.items.length > 0) {
              parsed.items = statusData.items.map((it: any) => ({
                id: String(it.product_id),
                dbId: it.product_id,
                name: it.product_name,
                sku: it.product_sku || "",
                price: it.price,
                quantity: it.quantity,
                image_url: it.image_url,
              }));
            }
            setPendingOrder(parsed);
          }
        })
        .catch(() => {
          setPendingOrder(parsed);
        });
    } catch (e) {
      localStorage.removeItem("h4care_pending_order");
    }
  }, [router]);

  // Initialize cart from localStorage
  useEffect(() => {
    try {
      const stored = localStorage.getItem("pharmatrust_cart");
      if (stored) {
        const parsed = JSON.parse(stored);
        if (Array.isArray(parsed) && parsed.length > 0) {
          setItems(parsed);
          setIsLoaded(true);
          validateCartWithServer(parsed);
          return;
        }
      }
    } catch (e) {
      console.warn("Could not read cart from localStorage:", e);
    }
    setItems([]);
    setIsLoaded(true);
  }, []);

  // Sync cart to localStorage
  useEffect(() => {
    if (isLoaded) {
      localStorage.setItem("pharmatrust_cart", JSON.stringify(items));
    }
  }, [items, isLoaded]);

  // Autofill user details if logged in
  useEffect(() => {
    if (user) {
      if (user.fullName && !customerName) setCustomerName(user.fullName);
      if (user.phone && !customerPhone) setCustomerPhone(user.phone);
      if (user.email && !customerEmail) setCustomerEmail(user.email);
    }
  }, [user]);

  // Load 2-tier administrative units
  useEffect(() => {
    async function loadAdminTree() {
      try {
        const res = await fetch("/api/v1/addresses/administrative-units?tree=true");
        if (res.ok) {
          const data: AdminProvince[] = await res.json();
          if (Array.isArray(data) && data.length > 0) {
            setAdminTree(data);
            const defaultProv = data.find((p) => p.code === "79") || data[0];
            setSelectedProvinceCode(defaultProv.code);
            if (defaultProv.districts && defaultProv.districts.length > 0) {
              setSelectedDistrictCode(defaultProv.districts[0].code);
            }
          }
        }
      } catch (e) {
        console.warn("Could not load administrative tree:", e);
      }
    }
    loadAdminTree();
  }, []);

  // Fetch nearest warehouse based on province/district and optional GPS
  useEffect(() => {
    async function fetchNearestWarehouse() {
      try {
        const bodyPayload: any = {
          province_code: selectedProvinceCode,
          district_code: selectedDistrictCode,
        };
        if (coords) {
          bodyPayload.lat = coords.lat;
          bodyPayload.lng = coords.lng;
        }
        const res = await fetch("/api/v1/addresses/nearest-warehouse", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(bodyPayload),
        });
        if (res.ok) {
          const data = await res.json();
          if (data.nearest_warehouse) {
            setNearestWarehouse(data.nearest_warehouse);
          }
        }
      } catch (e) {
        console.warn("Could not compute nearest warehouse:", e);
      }
    }
    if (fulfillmentType === "DELIVERY") {
      fetchNearestWarehouse();
    }
  }, [selectedProvinceCode, selectedDistrictCode, coords, fulfillmentType]);

  // Cart actions
  const updateQuantity = (id: string, delta: number) => {
    setItems((prev) =>
      prev
        .map((item) => {
          if (item.id === id) {
            const newQty = item.quantity + delta;
            return newQty > 0 ? { ...item, quantity: newQty } : null;
          }
          return item;
        })
        .filter(Boolean) as CartItem[]
    );
  };

  const removeItem = (id: string) => {
    setItems((prev) => prev.filter((item) => item.id !== id));
  };

  const clearCart = () => {
    setItems([]);
    localStorage.removeItem("pharmatrust_cart");
  };

  // Mở lại modal QR SePay cho đơn đang chờ
  const handleReopenSepay = () => {
    if (!pendingOrder) return;
    if (pendingOrder.sepayData) {
      setSepayModalData({
        ...pendingOrder.sepayData,
        isOpen: true,
      });
    } else {
      handleRefreshSepayQr();
    }
  };

  // Tạo mã QR SePay mới (15 phút) cho đơn hàng đang chờ
  const handleRefreshSepayQr = async () => {
    if (!pendingOrder) return;
    const token = typeof window !== "undefined"
      ? localStorage.getItem("pharmatrust_access_token") ||
        localStorage.getItem("pharmatrust_token") ||
        localStorage.getItem("h4care_auth_token") ||
        localStorage.getItem("access_token")
      : null;
    const orderToken =
      pendingOrder.orderToken ||
      (typeof window !== "undefined"
        ? localStorage.getItem(`h4care_order_token_${pendingOrder.orderCode}`) ||
          localStorage.getItem("h4care_latest_order_token") ||
          ""
        : "");

    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (token) headers["Authorization"] = `Bearer ${token}`;
    if (orderToken) headers["X-Order-Token"] = orderToken;

    const res = await fetch("/api/v1/payments/retry", {
      method: "POST",
      headers,
      body: JSON.stringify({
        order_code: pendingOrder.orderCode,
        new_payment_method: "SEPAY",
        phone_verify: pendingOrder.customerPhone,
        order_token: orderToken,
      }),
    });

    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || "Không thể tạo mã thanh toán mới. Vui lòng thử lại.");
    }

    const intent = data.payment_intent || {};
    const bankDetails = intent.bank_details || {};
    const modalInfo = {
      isOpen: true,
      orderCode: pendingOrder.orderCode,
      paymentCode: bankDetails.payment_code || intent.payment_code || pendingOrder.orderCode,
      amount: intent.amount || pendingOrder.totalAmount,
      bankName: bankDetails.bank_name || intent.bank_name,
      accountNumber: bankDetails.account_number || intent.account_number,
      accountHolder: bankDetails.account_holder || intent.account_holder,
      qrCodeUrl: intent.qr_code_url,
      expiresAt: intent.expires_at,
    };

    const updatedOrder: PendingOrderData = {
      ...pendingOrder,
      paymentMethod: "SEPAY",
      expiresAt: intent.expires_at,
      sepayData: modalInfo,
    };

    setPendingOrder(updatedOrder);
    if (typeof window !== "undefined") {
      localStorage.setItem("h4care_pending_order", JSON.stringify(updatedOrder));
    }
    setSepayModalData(modalInfo);
  };

  // Xác nhận đổi phương thức thanh toán có chủ đích từ modal lựa chọn
  const handleConfirmChangePaymentMethod = async (newMethod: PaymentMethodType) => {
    if (!pendingOrder) return;
    const token = typeof window !== "undefined"
      ? localStorage.getItem("pharmatrust_access_token") ||
        localStorage.getItem("pharmatrust_token") ||
        localStorage.getItem("h4care_auth_token") ||
        localStorage.getItem("access_token")
      : null;
    const orderToken =
      pendingOrder.orderToken ||
      (typeof window !== "undefined"
        ? localStorage.getItem(`h4care_order_token_${pendingOrder.orderCode}`) ||
          localStorage.getItem("h4care_latest_order_token") ||
          ""
        : "");

    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (token) headers["Authorization"] = `Bearer ${token}`;
    if (orderToken) headers["X-Order-Token"] = orderToken;

    const returnUrl = typeof window !== "undefined"
      ? `${window.location.origin}/checkout/result?order_code=${encodeURIComponent(pendingOrder.orderCode)}`
      : undefined;

    const res = await fetch("/api/v1/payments/retry", {
      method: "POST",
      headers,
      body: JSON.stringify({
        order_code: pendingOrder.orderCode,
        new_payment_method: newMethod,
        phone_verify: pendingOrder.customerPhone,
        order_token: orderToken,
        return_url: returnUrl,
      }),
    });

    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || `Không thể chuyển sang phương thức ${newMethod}. Vui lòng thử lại.`);
    }

    if (newMethod === "COD") {
      const storeObj = PHARMACY_STORES.find((s) => s.id === selectedStoreId);
      setOrderSuccess({
        order_code: pendingOrder.orderCode,
        total: pendingOrder.totalAmount,
        customer_name: pendingOrder.customerName,
        customer_phone: pendingOrder.customerPhone,
        shipping_address: pendingOrder.shippingAddress,
        payment_method: "COD",
        fulfillment_type: fulfillmentType,
        store_name: storeObj?.name,
      });
      setPendingOrder(null);
      setSepayModalData(null);
      setShowChangeMethodModal(false);
      if (typeof window !== "undefined") {
        localStorage.removeItem("h4care_pending_order");
        localStorage.removeItem("pharmatrust_cart");
        window.dispatchEvent(new Event("cart_updated"));
      }
      return;
    }

    if (newMethod === "SEPAY") {
      const intent = data.payment_intent || {};
      const bankDetails = intent.bank_details || {};
      const modalInfo = {
        isOpen: true,
        orderCode: pendingOrder.orderCode,
        paymentCode: bankDetails.payment_code || intent.payment_code || pendingOrder.orderCode,
        amount: intent.amount || pendingOrder.totalAmount,
        bankName: bankDetails.bank_name || intent.bank_name,
        accountNumber: bankDetails.account_number || intent.account_number,
        accountHolder: bankDetails.account_holder || intent.account_holder,
        qrCodeUrl: intent.qr_code_url,
        expiresAt: intent.expires_at,
      };

      const updatedOrder: PendingOrderData = {
        ...pendingOrder,
        paymentMethod: "SEPAY",
        expiresAt: intent.expires_at,
        sepayData: modalInfo,
      };

      setPendingOrder(updatedOrder);
      if (typeof window !== "undefined") {
        localStorage.setItem("h4care_pending_order", JSON.stringify(updatedOrder));
      }
      setSepayModalData(modalInfo);
      setShowChangeMethodModal(false);
      return;
    }

    if (newMethod === "PAYOS") {
      const payUrl = data.payment_intent?.pay_url || data.pay_url;
      if (payUrl) {
        window.location.href = payUrl;
      } else {
        setShowChangeMethodModal(false);
      }
    }
  };

  // Hủy đơn hàng đang chờ thanh toán an toàn và giải phóng kho
  const handleCancelPendingOrder = async () => {
    if (!pendingOrder) return;
    const token = typeof window !== "undefined"
      ? localStorage.getItem("pharmatrust_access_token") ||
        localStorage.getItem("pharmatrust_token") ||
        localStorage.getItem("h4care_auth_token") ||
        localStorage.getItem("access_token")
      : null;
    const orderToken =
      pendingOrder.orderToken ||
      (typeof window !== "undefined"
        ? localStorage.getItem(`h4care_order_token_${pendingOrder.orderCode}`) ||
          localStorage.getItem("h4care_latest_order_token") ||
          ""
        : "");

    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (token) headers["Authorization"] = `Bearer ${token}`;
    if (orderToken) headers["X-Order-Token"] = orderToken;

    const res = await fetch(`/api/v1/payments/orders/${encodeURIComponent(pendingOrder.orderCode)}/cancel`, {
      method: "POST",
      headers,
      body: JSON.stringify({
        reason: "Khách hàng hủy đơn trên website",
        phone_verify: pendingOrder.customerPhone,
        order_token: orderToken,
      }),
    });

    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || "Không thể hủy đơn hàng.");
    }

    // Khôi phục lại sản phẩm vào giỏ hàng để khách không phải chọn lại từ đầu
    if (pendingOrder.items && pendingOrder.items.length > 0) {
      setItems(pendingOrder.items);
      if (typeof window !== "undefined") {
        localStorage.setItem("pharmatrust_cart", JSON.stringify(pendingOrder.items));
        window.dispatchEvent(new Event("cart_updated"));
      }
    }

    setPendingOrder(null);
    if (typeof window !== "undefined") {
      localStorage.removeItem("h4care_pending_order");
    }
  };

  const handlePendingOrderPaymentSuccess = () => {
    if (!pendingOrder) return;
    const code = pendingOrder.orderCode;
    setPendingOrder(null);
    if (typeof window !== "undefined") {
      localStorage.removeItem("h4care_pending_order");
      localStorage.removeItem("pharmatrust_cart");
      window.dispatchEvent(new Event("cart_updated"));
    }
    router.push(`/checkout/result?order_code=${encodeURIComponent(code)}`);
  };

  // GPS locator & VIETMAP Auto-fill
  const handleGetLocation = async () => {
    setIsLocating(true);
    try {
      const loc = await placesService.getCurrentLocation();
      setCoords({
        lat: loc.lat,
        lng: loc.lng,
      });

      const rev = await placesService.reverseGeocode(loc.lat, loc.lng);
      if (rev) {
        if (rev.province_code) setSelectedProvinceCode(rev.province_code);
        if (rev.commune_code) setSelectedDistrictCode(rev.commune_code);
        if (rev.street_address) setStreetAddress(rev.street_address);

        // Tự động thiết lập địa chỉ xác minh
        const autoStructured: StructuredAddress = {
          provinceCode: rev.province_code || "",
          provinceName: rev.province_name || "",
          communeCode: rev.commune_code || "",
          communeName: rev.commune_name || "",
          communeType: "ward",
          streetAddress: rev.street_address || "",
          fullAddress: rev.formatted_address,
          lat: loc.lat,
          lng: loc.lng,
          isVerified: true,
          placeId: rev.place_id,
          wardCode: rev.commune_code || undefined,
          wardName: rev.commune_name || undefined,
        };
        setVerifiedAddress(autoStructured);
        setIsAddressVerified(true);
      }
    } catch (e: any) {
      console.warn("Geolocation warning:", e);
      alert(e.message || "Không thể truy cập cảm biến GPS của thiết bị.");
    } finally {
      setIsLocating(false);
    }
  };

  const [dynamicShippingFee, setDynamicShippingFee] = useState<number>(25000);
  const [serverQuote, setServerQuote] = useState<{
    subtotal: number;
    shipping_fee: number;
    discount_amount: number;
    grand_total: number;
  } | null>(null);

  // Server quote calculation
  const fetchQuote = async (
    cartItems: CartItem[],
    voucherToTry?: string | null,
    overrideFulfill?: FulfillmentType
  ) => {
    if (!cartItems || cartItems.length === 0) {
      setServerQuote(null);
      return;
    }
    try {
      const itemsPayload = cartItems.map((it) => {
        let dbId = it.dbId;
        if (!dbId && it.id.startsWith("pt-")) dbId = parseInt(it.id.replace("pt-", ""), 10);
        else if (!dbId && /^\d+$/.test(it.id)) dbId = parseInt(it.id, 10);
        if (!dbId || isNaN(dbId)) {
          throw new Error(`Sản phẩm '${it.name}' không có mã định danh hợp lệ trên hệ thống.`);
        }
        return {
          product_id: dbId,
          sku_id: it.skuId,
          quantity: it.quantity,
        };
      });

      const effectiveVoucher = voucherToTry !== undefined ? voucherToTry : appliedVoucher;
      const effectiveType = overrideFulfill || fulfillmentType;

      const calcPayload: any = {
        items: itemsPayload,
        voucher_code: effectiveVoucher || undefined,
        fulfillment_type: effectiveType,
        province_code: selectedProvinceCode,
        district_code: selectedDistrictCode,
      };
      if (coords) {
        calcPayload.lat = coords.lat;
        calcPayload.lng = coords.lng;
      }

      const res = await fetch("/api/v1/store/orders/cart/calculate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(calcPayload),
      });

      if (res.ok) {
        const data = await res.json();
        setServerQuote({
          subtotal: data.subtotal,
          shipping_fee: data.shipping_fee,
          discount_amount: data.discount_amount,
          grand_total: data.grand_total,
        });

        if (voucherToTry !== undefined) {
          if (data.voucher && data.voucher.is_valid) {
            setAppliedVoucher(data.voucher.code);
            setDiscount(data.discount_amount);
            setVoucherError("");
          } else if (voucherToTry) {
            setAppliedVoucher(null);
            setDiscount(0);
            setVoucherError(data.voucher?.message || "Mã giảm giá không hợp lệ.");
          } else {
            setAppliedVoucher(null);
            setDiscount(0);
            setVoucherError("");
          }
        } else if (data.voucher && data.voucher.is_valid) {
          setDiscount(data.discount_amount);
        }
      }
    } catch (e) {
      console.warn("Could not calculate cart quote from server:", e);
    }
  };

  useEffect(() => {
    if (items.length > 0) {
      fetchQuote(items);
    }
  }, [items, fulfillmentType, selectedProvinceCode, coords]);

  // Pricing calculations
  const clientSubtotal = items.reduce(
    (sum, item) => sum + (item.salePrice || item.price) * item.quantity,
    0
  );
  const subtotal = serverQuote ? serverQuote.subtotal : clientSubtotal;
  const isFreeShip = subtotal >= 300000;
  const baseShippingFee = isFreeShip || subtotal === 0 ? 0 : (serverQuote ? serverQuote.shipping_fee : dynamicShippingFee);
  const effectiveShippingFee =
    fulfillmentType === "STORE_PICKUP" ? 0 : baseShippingFee;
  const grandTotal = serverQuote
    ? serverQuote.grand_total
    : Math.max(0, subtotal + effectiveShippingFee - discount);
  const totalCount = items.reduce((sum, item) => sum + item.quantity, 0);

  // Voucher application via server validation
  const handleApplyVoucher = (code: string) => {
    setVoucherError("");
    const clean = code.trim().toUpperCase();
    if (!clean) return;
    fetchQuote(items, clean);
  };

  const handleRemoveVoucher = () => {
    setAppliedVoucher(null);
    setDiscount(0);
    setVoucherCode("");
    setVoucherError("");
    fetchQuote(items, null);
  };

  // Checkout submission handler
  const handleCheckout = async (e?: React.FormEvent) => {
    if (e && typeof e.preventDefault === "function") {
      e.preventDefault();
    }
    setErrorMessage("");

    if (items.length === 0) {
      setErrorMessage("Giỏ hàng của bạn đang trống.");
      return;
    }

    const hasRxItem = items.some((it) => it.isPrescription);
    if (hasRxItem) {
      setErrorMessage(
        "Giỏ hàng của bạn chứa thuốc kê đơn (Rx). Theo quy định của Bộ Y Tế, thuốc kê đơn không được phép bán trực tuyến. Vui lòng xóa thuốc kê đơn khỏi giỏ hàng hoặc gửi đơn thuốc qua chuyên mục Tư Vấn Dược Sĩ."
      );
      return;
    }

    // Kiểm tra tính sẵn sàng của cổng thanh toán payOS trước khi tạo đơn
    if (paymentMethod === "PAYOS") {
      try {
        const mRes = await fetch("/api/v1/payments/methods");
        if (mRes.ok) {
          const mData = await mRes.json();
          const isPayosReady = mData?.methods?.find((m: any) => m.id === "PAYOS")?.available;
          if (!isPayosReady) {
            setErrorMessage("Cổng thanh toán payOS hiện đang trong quá trình bảo trì cấu hình keys trên máy chủ. Vui lòng chọn Thanh toán khi nhận hàng (COD) hoặc Chuyển khoản VietQR MBBank (SePay).");
            return;
          }
        }
      } catch (e) {}
    }

    let currentVerified = verifiedAddress;
    let finalCustomerName = customerName.trim();
    let finalCustomerPhone = customerPhone.trim();

    if (fulfillmentType === "DELIVERY") {
      if (!isAddressVerified || !currentVerified) {
        if (confirmAddressRef.current) {
          const addr = await confirmAddressRef.current();
          if (!addr) {
            const el = document.getElementById("shipping-address-section");
            if (el) el.scrollIntoView({ behavior: "smooth", block: "center" });
            return;
          }
          currentVerified = addr;
          if (addr.recipientName && !finalCustomerName) {
            finalCustomerName = addr.recipientName;
            setCustomerName(addr.recipientName);
          }
          if (addr.phone && !finalCustomerPhone) {
            finalCustomerPhone = addr.phone;
            setCustomerPhone(addr.phone);
          }
        } else {
          setErrorMessage("Vui lòng hoàn thành xác nhận địa chỉ giao thuốc và vị trí trên bản đồ trước khi đặt hàng.");
          const el = document.getElementById("shipping-address-section");
          if (el) el.scrollIntoView({ behavior: "smooth", block: "center" });
          return;
        }
      }

      if (!currentVerified?.lat || !currentVerified?.lng) {
        setErrorMessage("Vui lòng chọn vị trí tọa độ hợp lệ trên bản đồ.");
        const el = document.getElementById("shipping-address-section");
        if (el) el.scrollIntoView({ behavior: "smooth", block: "center" });
        return;
      }
    }

    if (!finalCustomerName) {
      if (currentVerified?.recipientName) {
        finalCustomerName = currentVerified.recipientName;
        setCustomerName(finalCustomerName);
      } else {
        setErrorMessage("Vui lòng nhập Họ và tên người nhận thuốc.");
        const el = document.getElementById("shipping-address-section");
        if (el) el.scrollIntoView({ behavior: "smooth", block: "center" });
        return;
      }
    }

    const cleanPhone = finalCustomerPhone.replace(/\D/g, "");
    if (cleanPhone.length < 9 || cleanPhone.length > 11) {
      if (currentVerified?.phone && currentVerified.phone.replace(/\D/g, "").length >= 9) {
        finalCustomerPhone = currentVerified.phone;
        setCustomerPhone(finalCustomerPhone);
      } else {
        setErrorMessage("Vui lòng nhập số điện thoại hợp lệ để Dược sĩ liên hệ xác nhận đơn.");
        const el = document.getElementById("shipping-address-section");
        if (el) el.scrollIntoView({ behavior: "smooth", block: "center" });
        return;
      }
    }

    let fullShippingAddress = "";
    let cityName = "Toàn quốc";
    let selectedStoreObj = null;

    if (fulfillmentType === "STORE_PICKUP") {
      selectedStoreObj = PHARMACY_STORES.find((s) => s.id === selectedStoreId) || PHARMACY_STORES[0];
      fullShippingAddress = `Nhận tại: ${selectedStoreObj.name} (${selectedStoreObj.address})`;
      cityName = selectedStoreObj.city === "79" ? "TP. Hồ Chí Minh" : "Hà Nội";
    } else {
      fullShippingAddress = currentVerified!.fullAddress;
      cityName = currentVerified!.provinceName;
    }

    setIsSubmitting(true);
    try {
      const checkoutItems = items.map((it) => {
        let dbId = it.dbId;
        if (!dbId && it.id.startsWith("pt-")) {
          dbId = parseInt(it.id.replace("pt-", ""), 10);
        } else if (!dbId && /^\d+$/.test(it.id)) {
          dbId = parseInt(it.id, 10);
        }
        if (!dbId || isNaN(dbId)) {
          throw new Error(`Sản phẩm '${it.name}' không có mã định danh hợp lệ trên hệ thống. Vui lòng chọn lại.`);
        }
        return {
          product_id: dbId,
          quantity: it.quantity,
          sku_id: it.skuId,
          client_unit_price: it.salePrice || it.price,
        };
      });

      const orderPayload = {
        customer_name: finalCustomerName,
        customer_phone: finalCustomerPhone,
        customer_email: customerEmail.trim() || undefined,
        shipping_address: fullShippingAddress,
        shipping_city: cityName,
        payment_method: paymentMethod,
        note: orderNote.trim() || undefined,
        items: checkoutItems,
        idempotency_key: idempotencyKeyRef.current || undefined,
        voucher_code: appliedVoucher || undefined,
        fulfillment_type: fulfillmentType,
        province_code: fulfillmentType === "DELIVERY" ? currentVerified?.provinceCode : undefined,
        commune_code: fulfillmentType === "DELIVERY" ? currentVerified?.communeCode : undefined,
        commune_type: fulfillmentType === "DELIVERY" ? currentVerified?.communeType : undefined,
        address_line: fulfillmentType === "DELIVERY" ? currentVerified?.streetAddress : undefined,
        formatted_address: fullShippingAddress,
        place_id: fulfillmentType === "DELIVERY" ? currentVerified?.placeId : undefined,
        lat: fulfillmentType === "DELIVERY" ? currentVerified?.lat : undefined,
        lng: fulfillmentType === "DELIVERY" ? currentVerified?.lng : undefined,
        is_verified: fulfillmentType === "DELIVERY" ? true : true,
        district_code: fulfillmentType === "DELIVERY" ? (currentVerified?.districtName || currentVerified?.districtCode) : undefined,
        ward_code: fulfillmentType === "DELIVERY" ? (currentVerified?.communeCode || currentVerified?.wardCode) : undefined,
        shipping_fee: effectiveShippingFee,
      };

      const token = typeof window !== "undefined"
        ? localStorage.getItem("pharmatrust_access_token") ||
          localStorage.getItem("pharmatrust_token") ||
          localStorage.getItem("h4care_auth_token") ||
          localStorage.getItem("access_token")
        : null;
      const headers: Record<string, string> = { "Content-Type": "application/json" };
      if (token) {
        headers["Authorization"] = `Bearer ${token}`;
      }

      const res = await fetch("/api/v1/store/orders/checkout", {
        method: "POST",
        headers,
        body: JSON.stringify(orderPayload),
      });

      const data = await res.json();
      if (!res.ok) {
        if (res.status === 401) {
          throw new Error("Phiên đăng nhập đã hết hạn hoặc không hợp lệ. Vui lòng đăng nhập lại để tích điểm và lưu lịch sử đơn hàng, hoặc đăng xuất để đặt hàng với tư cách khách vãng lai.");
        }
        let msg = "Không thể khởi tạo đơn hàng. Vui lòng thử lại.";
        if (typeof data.detail === "string") {
          msg = data.detail;
        } else if (Array.isArray(data.detail)) {
          msg = data.detail
            .map((d: any) => {
              if (typeof d === "string") return d;
              const field = d.loc ? d.loc[d.loc.length - 1] : "";
              const m = d.msg || "dữ liệu không hợp lệ";
              return field ? `${field}: ${m}` : m;
            })
            .join("; ");
        } else if (data.message && typeof data.message === "string") {
          msg = data.message;
        }
        throw new Error(msg);
      }

      // Lưu trữ token bảo mật đơn hàng của khách vãng lai
      const guestOrderToken = data.guest_access_token || data.order_token || "";
      if (typeof window !== "undefined" && guestOrderToken) {
        localStorage.setItem(`h4care_order_token_${data.order_code}`, guestOrderToken);
        localStorage.setItem("h4care_latest_order_token", guestOrderToken);
      }

      // Handle SePay MBBank VietQR payment
      if (paymentMethod === "SEPAY") {
        if (typeof window !== "undefined" && finalCustomerPhone) {
          localStorage.setItem("h4care_checkout_phone", finalCustomerPhone);
        }
        try {
          const payHeaders: Record<string, string> = { "Content-Type": "application/json" };
          if (token) payHeaders["Authorization"] = `Bearer ${token}`;
          if (guestOrderToken) payHeaders["X-Order-Token"] = guestOrderToken;

          const sepayRes = await fetch("/api/v1/payments/sepay/create", {
            method: "POST",
            headers: payHeaders,
            body: JSON.stringify({
              order_code: data.order_code,
              phone_verify: finalCustomerPhone,
              order_token: guestOrderToken,
            }),
          });
          const sepayData = await sepayRes.json();
          if (sepayRes.ok && sepayData?.payment_code) {
            const modalInfo = {
              isOpen: true,
              orderCode: data.order_code,
              paymentCode: sepayData.payment_code,
              amount: sepayData.amount || data.total_amount || grandTotal,
              bankName: sepayData.bank_name,
              accountNumber: sepayData.account_number,
              accountHolder: sepayData.account_holder,
              qrCodeUrl: sepayData.qr_code_url,
              expiresAt: sepayData.expires_at,
            };

            const pendingData: PendingOrderData = {
              orderCode: data.order_code,
              orderToken: guestOrderToken,
              customerName: customerName.trim(),
              customerPhone: customerPhone.trim(),
              shippingAddress: fullShippingAddress,
              totalAmount: data.total_amount || grandTotal,
              paymentMethod: "SEPAY",
              items: [...items],
              shippingFee: effectiveShippingFee,
              discountAmount: discount,
              createdAt: new Date().toISOString(),
              expiresAt: sepayData.expires_at,
              sepayData: modalInfo,
            };

            // Lưu pendingOrder vào state và localStorage trước khi xóa giỏ hàng
            setPendingOrder(pendingData);
            if (typeof window !== "undefined") {
              localStorage.setItem("h4care_pending_order", JSON.stringify(pendingData));
              localStorage.removeItem("pharmatrust_cart");
              window.dispatchEvent(new Event("cart_updated"));
            }
            setItems([]);
            setSepayModalData(modalInfo);
            return;
          } else {
            throw new Error(sepayData?.detail || "Không thể khởi tạo mã chuyển khoản SePay MBBank");
          }
        } catch (sErr: any) {
          console.warn("Lỗi khi kết nối cổng SePay:", sErr);
          setErrorMessage(sErr?.message || "Lỗi khi kết nối cổng thanh toán SePay MBBank");
          return;
        }
      }

      // Handle payOS Gateway payment
      if (paymentMethod === "PAYOS") {
        const returnUrl = typeof window !== "undefined"
          ? `${window.location.origin}/checkout/result?order_code=${encodeURIComponent(data.order_code)}`
          : "";
        if (typeof window !== "undefined" && finalCustomerPhone) {
          localStorage.setItem("h4care_checkout_phone", finalCustomerPhone);
        }
        try {
          const payHeaders: Record<string, string> = { "Content-Type": "application/json" };
          if (token) payHeaders["Authorization"] = `Bearer ${token}`;
          if (guestOrderToken) payHeaders["X-Order-Token"] = guestOrderToken;

          const payosRes = await fetch("/api/v1/payments/payos/create", {
            method: "POST",
            headers: payHeaders,
            body: JSON.stringify({
              order_code: data.order_code,
              return_url: returnUrl,
              phone_verify: finalCustomerPhone,
              order_token: guestOrderToken,
            }),
          });
          const payosData = await payosRes.json();
          if (payosRes.ok && payosData?.checkout_url) {
            setItems([]);
            localStorage.removeItem("pharmatrust_cart");
            window.location.href = payosData.checkout_url;
            return;
          } else {
            throw new Error(payosData?.detail || "Không thể tạo liên kết thanh toán payOS");
          }
        } catch (pErr: any) {
          console.warn("Lỗi khi kết nối cổng payOS:", pErr);
          setErrorMessage(pErr?.message || "Lỗi khi kết nối cổng thanh toán payOS");
          return;
        }
      }

      // COD: Chỉ duy nhất phương thức COD (Thanh toán khi nhận hàng) mới được phép hiển thị màn hình đặt hàng thành công trực tiếp
      if (paymentMethod === "COD") {
        setOrderSuccess({
          order_code: data.order_code,
          total: data.total_amount || grandTotal,
          customer_name: customerName.trim(),
          customer_phone: customerPhone.trim(),
          shipping_address: fullShippingAddress,
          payment_method: "COD",
          fulfillment_type: fulfillmentType,
          store_name: selectedStoreObj?.name,
        });

        // Clear local cart
        setItems([]);
        localStorage.removeItem("pharmatrust_cart");
        return;
      }

      // Mọi phương thức trực tuyến khác ngoài COD: Tuyệt đối không tự ý hiển thị thành công, chuyển hướng sang trang kết quả thanh toán
      setItems([]);
      localStorage.removeItem("pharmatrust_cart");
      router.push(`/checkout/result?order_code=${encodeURIComponent(data.order_code)}`);
      return;
    } catch (err: any) {
      setErrorMessage(err.message || "Lỗi khi xử lý đơn hàng");
    } finally {
      setIsSubmitting(false);
    }
  };


  return (
    <div className="min-h-screen flex flex-col bg-slate-50">
      <Header />

      {/* Checkout Header with Step Indicator */}
      <CheckoutHeader
        currentStep={orderSuccess ? 3 : 2}
        totalItems={totalCount}
      />

      <main className="flex-1 max-w-7xl mx-auto w-full px-4 sm:px-6 lg:px-8 py-6 sm:py-8">
        {/* 1. ORDER SUCCESS VIEW */}
        {orderSuccess ? (
          <OrderSuccessView
            order={orderSuccess}
            isAuthenticated={isAuthenticated}
          />
        ) : pendingOrder ? (
          /* 2. PENDING ORDER VIEW (Đơn đang chờ thanh toán) */
          <PendingOrderView
            order={pendingOrder}
            onReopenPayment={handleReopenSepay}
            onChangePaymentMethod={() => setShowChangeMethodModal(true)}
            onRefreshPaymentCode={handleRefreshSepayQr}
            onCancelOrder={handleCancelPendingOrder}
            onPaymentSuccess={handlePendingOrderPaymentSuccess}
          />
        ) : items.length === 0 && isLoaded ? (
          /* 3. EMPTY CART VIEW */
          <EmptyCartState />
        ) : (
          /* 3. TWO-COLUMN PHARMACY CHECKOUT (Long Châu style) */
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 sm:gap-8 items-start">
            {/* Left Column: Form & Products */}
            <div className="lg:col-span-7 xl:col-span-8 space-y-4">
              {/* Error Alert */}
              {errorMessage && (
                <div className="p-3.5 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs sm:text-sm flex items-start gap-2.5">
                  <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
                  <div className="flex-1">{errorMessage}</div>
                  <button
                    type="button"
                    onClick={() => setErrorMessage("")}
                    className="text-rose-500 hover:text-rose-700 p-0.5"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                </div>
              )}

              {/* Server-side Cart Validation Alert */}
              {validationAlert && (
                <div
                  className={`p-3.5 rounded-xl border text-xs sm:text-sm flex items-start gap-2.5 ${
                    validationAlert.type === "error"
                      ? "bg-rose-50 border-rose-200 text-rose-800"
                      : "bg-amber-50 border-amber-200 text-amber-800"
                  }`}
                >
                  <AlertCircle
                    className={`w-4 h-4 shrink-0 mt-0.5 ${
                      validationAlert.type === "error" ? "text-rose-600" : "text-amber-600"
                    }`}
                  />
                  <div className="flex-1 font-medium">{validationAlert.message}</div>
                  <button
                    type="button"
                    onClick={() => setValidationAlert(null)}
                    className="opacity-70 hover:opacity-100 p-0.5"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                </div>
              )}

              {/* 1. Cart Items List */}
              <CartItemsTable
                items={items}
                onUpdateQuantity={updateQuantity}
                onRemoveItem={removeItem}
                onClearCart={clearCart}
              />

              {/* 2. Fulfillment Selector (Giao tận nơi vs Nhận tại quầy) */}
              <FulfillmentSelector
                fulfillmentType={fulfillmentType}
                onChangeFulfillmentType={setFulfillmentType}
                selectedStoreId={selectedStoreId}
                onSelectStore={setSelectedStoreId}
              />

              {/* 3. Receiver Information & Shipping Form */}
              <ShippingAddressForm
                fulfillmentType={fulfillmentType}
                customerName={customerName}
                setCustomerName={setCustomerName}
                customerPhone={customerPhone}
                setCustomerPhone={setCustomerPhone}
                customerEmail={customerEmail}
                setCustomerEmail={setCustomerEmail}
                selectedProvinceCode={selectedProvinceCode}
                setSelectedProvinceCode={setSelectedProvinceCode}
                selectedDistrictCode={selectedDistrictCode}
                setSelectedDistrictCode={setSelectedDistrictCode}
                selectedWardCode={selectedWardCode}
                setSelectedWardCode={setSelectedWardCode}
                wardName={wardName}
                setWardName={setWardName}
                streetAddress={streetAddress}
                setStreetAddress={setStreetAddress}
                orderNote={orderNote}
                setOrderNote={setOrderNote}
                needInvoice={needInvoice}
                setNeedInvoice={setNeedInvoice}
                taxCode={taxCode}
                setTaxCode={setTaxCode}
                companyName={companyName}
                setCompanyName={setCompanyName}
                adminTree={adminTree}
                coords={coords}
                setCoords={setCoords}
                nearestWarehouse={nearestWarehouse}
                setNearestWarehouse={setNearestWarehouse}
                isLocating={isLocating}
                onGetLocation={handleGetLocation}
                isVerified={isAddressVerified}
                setIsVerified={setIsAddressVerified}
                verifiedAddress={verifiedAddress}
                setVerifiedAddress={setVerifiedAddress}
                subtotal={subtotal}
                onShippingFeeCalculated={setDynamicShippingFee}
                confirmAddressRef={confirmAddressRef}
              />

              {/* 4. Payment Method Selector */}
              <PaymentMethodSelector
                paymentMethod={paymentMethod}
                onChangePaymentMethod={setPaymentMethod}
              />
            </div>

            {/* Right Column: Order Summary (Sticky Sidebar) */}
            <div
              ref={summaryRef}
              className="lg:col-span-5 xl:col-span-4 space-y-4"
            >
              <OrderSummaryCard
                subtotal={subtotal}
                shippingFee={baseShippingFee}
                discount={discount}
                grandTotal={grandTotal}
                totalItems={totalCount}
                fulfillmentType={fulfillmentType}
                voucherCode={voucherCode}
                setVoucherCode={setVoucherCode}
                appliedVoucher={appliedVoucher}
                onApplyVoucher={handleApplyVoucher}
                onRemoveVoucher={handleRemoveVoucher}
                voucherError={voucherError}
                isSubmitting={isSubmitting}
                isAddressVerified={fulfillmentType === "STORE_PICKUP" || isAddressVerified}
                onSubmitOrder={handleCheckout}
              />
            </div>
          </div>
        )}
      </main>

      {/* Mobile Sticky Checkout Bar */}
      {!orderSuccess && items.length > 0 && (
        <MobileStickyCheckoutBar
          totalAmount={grandTotal}
          totalItems={totalCount}
          isSubmitting={isSubmitting}
          isAddressVerified={fulfillmentType === "STORE_PICKUP" || isAddressVerified}
          onSubmit={handleCheckout}
          onScrollToSummary={() => {
            summaryRef.current?.scrollIntoView({ behavior: "smooth" });
          }}
        />
      )}

      {sepayModalData && (
        <SepayVietQrModal
          isOpen={sepayModalData.isOpen}
          orderCode={sepayModalData.orderCode}
          paymentCode={sepayModalData.paymentCode}
          amount={sepayModalData.amount}
          bankName={sepayModalData.bankName}
          accountNumber={sepayModalData.accountNumber}
          accountHolder={sepayModalData.accountHolder}
          qrCodeUrl={sepayModalData.qrCodeUrl}
          expiresAt={sepayModalData.expiresAt}
          onClose={() => setSepayModalData(null)}
          onChangeMethod={() => setShowChangeMethodModal(true)}
          onRefreshQr={handleRefreshSepayQr}
          onCancelOrder={handleCancelPendingOrder}
          onSuccess={() => {
            const code = sepayModalData.orderCode;
            setSepayModalData(null);
            setPendingOrder(null);
            if (typeof window !== "undefined") {
              localStorage.removeItem("h4care_pending_order");
              localStorage.removeItem("pharmatrust_cart");
              window.dispatchEvent(new Event("cart_updated"));
            }
            router.push(`/checkout/result?order_code=${encodeURIComponent(code)}`);
          }}
        />
      )}

      {showChangeMethodModal && pendingOrder && (
        <ChangePaymentMethodModal
          isOpen={showChangeMethodModal}
          currentMethod={pendingOrder.paymentMethod}
          totalAmount={pendingOrder.totalAmount}
          orderCode={pendingOrder.orderCode}
          onClose={() => setShowChangeMethodModal(false)}
          onConfirmChange={handleConfirmChangePaymentMethod}
        />
      )}

      <Footer />
    </div>
  );
}
