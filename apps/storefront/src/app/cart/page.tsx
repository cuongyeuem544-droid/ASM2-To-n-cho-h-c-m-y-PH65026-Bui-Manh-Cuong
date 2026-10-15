"use client";

import React, { useState, useEffect, useRef } from "react";
import { Header } from "@/components/layout/Header";
import { Footer } from "@/components/layout/Footer";
import { useAuth } from "@/lib/auth/auth-context";
import { AlertCircle, X, RefreshCw, ExternalLink, CheckCircle2 } from "lucide-react";

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
import VietQrPaymentModal from "@/components/checkout/VietQrPaymentModal";

export default function CartPage() {
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

  // Modals: VietQR & MoMo Sandbox
  const [vietQrModal, setVietQrModal] = useState<{
    isOpen: boolean;
    orderCode: string;
    amount: number;
    customerName: string;
    shippingAddress: string;
  } | null>(null);

  const [isSimulatingPayment, setIsSimulatingPayment] = useState(false);
  const [momoModal, setMomoModal] = useState<{
    isOpen: boolean;
    orderCode: string;
    amount: number;
    payUrl?: string;
    qrCodeUrl?: string;
    deeplink?: string;
    status: "PENDING" | "PAID" | "FAILED";
    message?: string;
  } | null>(null);

  // Idempotency key to prevent duplicate order placement
  const idempotencyKeyRef = useRef<string>("");
  const [validationAlert, setValidationAlert] = useState<{
    type: "warning" | "error";
    message: string;
  } | null>(null);

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

  // GPS locator
  const handleGetLocation = () => {
    if (typeof window === "undefined" || !navigator.geolocation) {
      alert("Trình duyệt không hỗ trợ định vị GPS.");
      return;
    }
    setIsLocating(true);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setIsLocating(false);
        setCoords({
          lat: pos.coords.latitude,
          lng: pos.coords.longitude,
        });
      },
      (err) => {
        setIsLocating(false);
        console.warn("Geolocation warning:", err);
      },
      { timeout: 8000 }
    );
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

      // Handle MoMo Sandbox payment
      if (paymentMethod === "MOMO") {
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

          const momoRes = await fetch("/api/v1/payments/momo/create", {
            method: "POST",
            headers: payHeaders,
            body: JSON.stringify({
              order_code: data.order_code,
              return_url: returnUrl,
              phone_verify: finalCustomerPhone,
              order_token: guestOrderToken,
            }),
          });
          const momoData = await momoRes.json();
          if (momoRes.ok && momoData) {
            setItems([]);
            localStorage.removeItem("pharmatrust_cart");
            setMomoModal({
              isOpen: true,
              orderCode: data.order_code,
              amount: data.total_amount || grandTotal,
              payUrl: momoData.pay_url,
              qrCodeUrl: momoData.qr_code_url,
              deeplink: momoData.deeplink,
              status: "PENDING",
            });
            return;
          }
        } catch (mErr) {
          console.warn("Lỗi khi kết nối cổng MoMo, chuyển về trang đơn hàng:", mErr);
        }
      }

      // Handle VietQR Bank Transfer Modal
      if (paymentMethod === "BANK_TRANSFER") {
        setItems([]);
        localStorage.removeItem("pharmatrust_cart");
        setVietQrModal({
          isOpen: true,
          orderCode: data.order_code,
          amount: data.total_amount || grandTotal,
          customerName: customerName.trim(),
          shippingAddress: fullShippingAddress,
        });
        return;
      }

      // COD or standard order placed successfully
      setOrderSuccess({
        order_code: data.order_code,
        total: data.total_amount || grandTotal,
        customer_name: customerName.trim(),
        customer_phone: customerPhone.trim(),
        shipping_address: fullShippingAddress,
        payment_method: paymentMethod,
        fulfillment_type: fulfillmentType,
        store_name: selectedStoreObj?.name,
      });

      // Clear local cart
      setItems([]);
      localStorage.removeItem("pharmatrust_cart");
    } catch (err: any) {
      setErrorMessage(err.message || "Lỗi khi xử lý đơn hàng");
    } finally {
      setIsSubmitting(false);
    }
  };

  // Polling MoMo payment status
  useEffect(() => {
    if (!momoModal?.isOpen || momoModal.status !== "PENDING" || !momoModal.orderCode) {
      return;
    }
    const intervalId = setInterval(async () => {
      try {
        const token = typeof window !== "undefined" ? localStorage.getItem("pharmatrust_token") : null;
        const savedPhone = typeof window !== "undefined" ? localStorage.getItem("h4care_checkout_phone") || customerPhone : customerPhone;
        const orderToken = typeof window !== "undefined" ? localStorage.getItem(`h4care_order_token_${momoModal.orderCode}`) || localStorage.getItem("h4care_latest_order_token") || "" : "";
        const payHeaders: Record<string, string> = {};
        if (token) payHeaders["Authorization"] = `Bearer ${token}`;
        if (orderToken) payHeaders["X-Order-Token"] = orderToken;
        const queryParams = [];
        if (savedPhone) queryParams.push(`phone_verify=${encodeURIComponent(savedPhone)}`);
        if (orderToken) queryParams.push(`token=${encodeURIComponent(orderToken)}`);
        const queryStr = queryParams.length ? `?${queryParams.join("&")}` : "";
        const res = await fetch(`/api/v1/payments/orders/${momoModal.orderCode}/status${queryStr}`, { headers: payHeaders });
        if (res.ok) {
          const data = await res.json();
          if (data.payment_status === "PAID") {
            setMomoModal((prev) =>
              prev
                ? {
                    ...prev,
                    status: "PAID",
                    message: "Giao dịch MoMo đã được xác nhận thành công!",
                  }
                : null
            );
            clearInterval(intervalId);
          }
        }
      } catch (e) {
        // silent error during background polling
      }
    }, 2500);

    return () => clearInterval(intervalId);
  }, [momoModal?.isOpen, momoModal?.status, momoModal?.orderCode]);

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
        ) : items.length === 0 && isLoaded ? (
          /* 2. EMPTY CART VIEW */
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

      {/* VietQR Payment Modal */}
      {vietQrModal && (
        <VietQrPaymentModal
          isOpen={vietQrModal.isOpen}
          orderCode={vietQrModal.orderCode}
          amount={vietQrModal.amount}
          customerName={vietQrModal.customerName}
          onClose={() => {
            setVietQrModal(null);
            setOrderSuccess({
              order_code: vietQrModal.orderCode,
              total: vietQrModal.amount,
              customer_name: vietQrModal.customerName,
              customer_phone: customerPhone,
              shipping_address: vietQrModal.shippingAddress,
              payment_method: "BANK_TRANSFER",
              fulfillment_type: fulfillmentType,
            });
          }}
          onConfirmPaid={() => {
            setVietQrModal(null);
            setOrderSuccess({
              order_code: vietQrModal.orderCode,
              total: vietQrModal.amount,
              customer_name: vietQrModal.customerName,
              customer_phone: customerPhone,
              shipping_address: vietQrModal.shippingAddress,
              payment_method: "BANK_TRANSFER",
              fulfillment_type: fulfillmentType,
            });
          }}
        />
      )}

      {/* MoMo Sandbox Payment Modal */}
      {momoModal?.isOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-xs animate-in fade-in duration-200">
          <div className="bg-white rounded-3xl max-w-md w-full overflow-hidden shadow-2xl border border-slate-200">
            {/* Modal Header */}
            <div className="bg-gradient-to-r from-[#a50064] to-[#d82d8b] text-white p-5 flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-full bg-white text-[#a50064] flex items-center justify-center font-black text-sm">
                  M
                </div>
                <div>
                  <h3 className="font-bold text-base leading-tight">Cổng thanh toán MoMo Sandbox</h3>
                  <p className="text-[11px] text-pink-100 font-mono">Đơn hàng: {momoModal.orderCode}</p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => {
                  setMomoModal(null);
                  setOrderSuccess({
                    order_code: momoModal.orderCode,
                    total: momoModal.amount,
                    customer_name: customerName,
                    customer_phone: customerPhone,
                    shipping_address: streetAddress,
                    payment_method: "MOMO",
                    fulfillment_type: fulfillmentType,
                  });
                }}
                className="text-white/80 hover:text-white p-1 rounded-lg hover:bg-white/10 transition-colors cursor-pointer"
                title="Đóng popup"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-6 text-center space-y-4">
              <div className="space-y-1">
                <span className="text-xs text-slate-500">Số tiền cần thanh toán</span>
                <p className="text-2xl font-black text-slate-900 font-mono">
                  {momoModal.amount.toLocaleString("vi-VN")} đ
                </p>
              </div>

              {momoModal.status === "PAID" ? (
                <div className="p-4 bg-emerald-50 rounded-2xl border border-emerald-200 text-emerald-800 space-y-2">
                  <div className="w-12 h-12 rounded-full bg-emerald-100 text-emerald-600 flex items-center justify-center mx-auto">
                    <CheckCircle2 className="w-7 h-7" />
                  </div>
                  <p className="font-bold text-sm">Thanh toán MoMo thành công!</p>
                  <p className="text-xs text-emerald-600">
                    Cổng MoMo Sandbox đã ghi nhận giao dịch. Đơn hàng của bạn đã chuyển sang trạng thái ĐÃ THANH TOÁN (PAID).
                  </p>
                </div>
              ) : (
                <div className="space-y-3">
                  <div className="w-48 h-48 mx-auto p-2 bg-white rounded-2xl border-2 border-dashed border-pink-300 flex items-center justify-center shadow-xs">
                    {momoModal.qrCodeUrl ? (
                      <img
                        src={momoModal.qrCodeUrl}
                        alt="Mã QR MoMo"
                        className="w-full h-full object-contain"
                      />
                    ) : (
                      <div className="text-center p-3 text-slate-400 text-xs">
                        Đang tạo mã QR MoMo Sandbox...
                      </div>
                    )}
                  </div>
                  <p className="text-xs text-slate-500">
                    Mở ứng dụng MoMo và quét mã QR để thử nghiệm thanh toán Sandbox
                  </p>
                </div>
              )}

              <div className="pt-2 flex flex-col gap-2">
                {momoModal.payUrl && momoModal.status === "PENDING" && (
                  <a
                    href={momoModal.payUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="w-full py-2.5 px-4 rounded-xl bg-[#a50064] hover:bg-[#850050] text-white font-bold text-xs shadow-xs transition-colors flex items-center justify-center gap-1.5"
                  >
                    <ExternalLink className="w-4 h-4" />
                    <span>Mở cổng thanh toán MoMo Sandbox Web</span>
                  </a>
                )}

                {/* Sandbox payment simulator button for 1-click test */}
                {momoModal.status === "PENDING" && (
                  <button
                    type="button"
                    disabled={isSimulatingPayment}
                    onClick={async () => {
                      if (!momoModal.orderCode) return;
                      setIsSimulatingPayment(true);
                      try {
                        const res = await fetch("/api/v1/payments/momo/simulate", {
                          method: "POST",
                          headers: { "Content-Type": "application/json" },
                          body: JSON.stringify({
                            order_code: momoModal.orderCode,
                            success: true,
                          }),
                        });
                        if (res.ok) {
                          setMomoModal((prev) =>
                            prev
                              ? {
                                  ...prev,
                                  status: "PAID",
                                  message: "Đã mô phỏng thanh toán MoMo thành công!",
                                }
                              : null
                          );
                        }
                      } catch (simErr) {
                        console.error("Simulation error:", simErr);
                      } finally {
                        setIsSimulatingPayment(false);
                      }
                    }}
                    className="w-full py-2.5 px-4 rounded-xl border-2 border-emerald-500 bg-emerald-50 hover:bg-emerald-100 text-emerald-800 font-bold text-xs flex items-center justify-center gap-1.5 transition-all cursor-pointer"
                  >
                    {isSimulatingPayment ? (
                      <>
                        <RefreshCw className="w-4 h-4 animate-spin text-emerald-600" />
                        <span>Đang kích hoạt giả lập MoMo...</span>
                      </>
                    ) : (
                      <>
                        <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                        <span>[TEST] Mô phỏng Khách đã quét MoMo thành công</span>
                      </>
                    )}
                  </button>
                )}

                <button
                  type="button"
                  onClick={() => {
                    setMomoModal(null);
                    setOrderSuccess({
                      order_code: momoModal.orderCode,
                      total: momoModal.amount,
                      customer_name: customerName,
                      customer_phone: customerPhone,
                      shipping_address: streetAddress,
                      payment_method: "MOMO",
                      fulfillment_type: fulfillmentType,
                    });
                  }}
                  className="w-full py-2.5 px-4 rounded-xl border border-slate-200 text-slate-700 font-semibold text-xs hover:bg-slate-50 transition-colors cursor-pointer"
                >
                  Hoàn tất và xem đơn hàng
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      <Footer />
    </div>
  );
}
