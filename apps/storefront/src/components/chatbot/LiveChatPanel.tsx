"use client";

import React, { useState, useEffect, useRef } from "react";
import {
  Send,
  Image as ImageIcon,
  Loader2,
  Clock,
  CheckCircle2,
  AlertCircle,
  RotateCcw,
  Star,
  User,
  ShieldCheck,
  Headphones,
  X,
  PhoneCall,
  Info,
} from "lucide-react";

interface LiveChatMessageItem {
  id?: number | string;
  sender_type: "CUSTOMER" | "STAFF" | "SYSTEM";
  sender_name: string;
  sender_role_title?: string;
  content: string;
  attachment_url?: string;
  attachment_type?: string;
  client_msg_id?: string;
  created_at?: string;
  isPending?: boolean;
  isError?: boolean;
}

interface LiveChatSessionData {
  id: number;
  session_code: string;
  customer_name: string;
  customer_phone?: string;
  customer_email?: string;
  guest_session_token?: string;
  assigned_staff_id?: number;
  assigned_staff_name?: string;
  assigned_staff_title?: string;
  status: "WAITING" | "ACTIVE" | "CLOSED";
  subject?: string;
  initial_context?: string;
  rating?: number;
  feedback?: string;
  created_at: string;
  messages: LiveChatMessageItem[];
}

interface LiveChatPanelProps {
  handoffContext?: string | null;
  onClearHandoff?: () => void;
  onBackToAi?: () => void;
  onNewMessageNotify?: () => void;
}

const STORAGE_SESSION_KEY = "h4care_live_chat_session_code";
const STORAGE_GUEST_TOKEN_KEY = "h4care_live_chat_guest_token";

const API_BASE = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");
const WS_BASE = API_BASE.replace(/^http/, "ws");

/**
 * Phát âm thanh thông báo nhẹ nhàng bằng Web Audio API
 */
function playNotificationChime() {
  try {
    const AudioContextClass = window.AudioContext || (window as any).webkitAudioContext;
    if (!AudioContextClass) return;
    const ctx = new AudioContextClass();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();

    osc.type = "sine";
    osc.frequency.setValueAtTime(587.33, ctx.currentTime); // D5
    osc.frequency.setValueAtTime(880, ctx.currentTime + 0.08); // A5

    gain.gain.setValueAtTime(0.08, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.35);

    osc.connect(gain);
    gain.connect(ctx.destination);

    osc.start();
    osc.stop(ctx.currentTime + 0.35);
  } catch {
    // Ignored in environments where audio is restricted
  }
}

/**
 * Component hiển thị hình ảnh đính kèm bảo mật:
 * - Tải ảnh qua fetch() với Bearer token và guest token.
 * - Chuyển dữ liệu nhị phân thành Blob URL.
 * - Thu hồi URL bằng URL.revokeObjectURL() khi unmount để chống rò rỉ bộ nhớ.
 * - Tuyệt đối không truyền JWT qua URL query string.
 */
function SecureChatImage({
  url,
  onClick,
}: {
  url: string;
  onClick: (blobUrl: string) => void;
}) {
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    let active = true;
    let createdUrl: string | null = null;

    const fetchImage = async () => {
      try {
        setLoading(true);
        setError(false);

        const headers: Record<string, string> = {};
        const authToken = localStorage.getItem("pharmatrust_access_token") || localStorage.getItem("token");
        if (authToken) headers["Authorization"] = `Bearer ${authToken}`;

        const guestToken = localStorage.getItem(STORAGE_GUEST_TOKEN_KEY);
        if (guestToken) headers["X-Chat-Guest-Token"] = guestToken;

        const targetUrl = url.startsWith("http")
          ? url
          : url.startsWith("/api/chat/attachments/")
          ? url
          : `${API_BASE}${url.startsWith("/") ? "" : "/"}${url}`;

        const res = await fetch(targetUrl, { headers });
        if (!res.ok) {
          if (active) setError(true);
          return;
        }

        const blob = await res.blob();
        if (!active) return;

        createdUrl = URL.createObjectURL(blob);
        setBlobUrl(createdUrl);
      } catch {
        if (active) setError(true);
      } finally {
        if (active) setLoading(false);
      }
    };

    fetchImage();

    return () => {
      active = false;
      if (createdUrl) {
        URL.revokeObjectURL(createdUrl);
      }
    };
  }, [url]);

  if (loading) {
    return (
      <div className="h-28 w-44 bg-slate-100/80 animate-pulse rounded-xl flex items-center justify-center text-slate-400 text-[10px]">
        Đang tải ảnh an toàn...
      </div>
    );
  }

  if (error || !blobUrl) {
    return (
      <div className="p-2 bg-red-50/90 border border-red-200 text-red-600 rounded-xl text-[10px] flex items-center gap-1.5">
        <span>Không thể tải ảnh đính kèm (yêu cầu quyền xem).</span>
      </div>
    );
  }

  return (
    <img
      src={blobUrl}
      alt="Đính kèm"
      onClick={() => onClick(blobUrl)}
      className="max-h-48 w-auto object-cover hover:opacity-95 transition-opacity"
    />
  );
}

export const LiveChatPanel: React.FC<LiveChatPanelProps> = ({
  handoffContext,
  onClearHandoff,
  onBackToAi,
  onNewMessageNotify,
}) => {
  const [session, setSession] = useState<LiveChatSessionData | null>(null);
  const [messages, setMessages] = useState<LiveChatMessageItem[]>([]);
  const [inputText, setInputText] = useState("");
  const [isInitializing, setIsInitializing] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [isSending, setIsSending] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [previewImage, setPreviewImage] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [staffOnlineInfo, setStaffOnlineInfo] = useState<{ is_online: boolean; online_count: number } | null>(null);
  const [wsConnected, setWsConnected] = useState(false);
  const [authFailed, setAuthFailed] = useState(false);

  // Form đăng ký thông tin cho khách vãng lai
  const [customerName, setCustomerName] = useState("");
  const [customerPhone, setCustomerPhone] = useState("");
  const [includeAiContext, setIncludeAiContext] = useState(true);

  // Rating modal state
  const [ratingVal, setRatingVal] = useState<number>(5);
  const [feedbackText, setFeedbackText] = useState("");
  const [hasRated, setHasRated] = useState(false);

  // Phóng to ảnh đính kèm
  const [zoomImage, setZoomImage] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // 1. Kiểm tra trạng thái trực tuyến của nhân viên
  useEffect(() => {
    const fetchStaffStatus = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/v1/live-chat/staff-status`);
        if (res.ok) {
          const data = await res.json();
          setStaffOnlineInfo(data);
        }
      } catch {
        // Fallback
      }
    };

    fetchStaffStatus();
    const interval = setInterval(fetchStaffStatus, 30000); // Check every 30s
    return () => clearInterval(interval);
  }, []);

  // 2. Khôi phục phiên chat từ localStorage khi component mount
  useEffect(() => {
    const savedCode = localStorage.getItem(STORAGE_SESSION_KEY);
    const guestToken = localStorage.getItem(STORAGE_GUEST_TOKEN_KEY);

    if (savedCode) {
      loadSessionDetail(savedCode, guestToken);
    }
  }, []);

  const loadSessionDetail = async (code: string, token: string | null) => {
    try {
      const headers: Record<string, string> = {};
      if (token) headers["X-Chat-Guest-Token"] = token;

      // Đọc JWT token nếu khách đã đăng nhập
      const authToken = localStorage.getItem("pharmatrust_access_token") || localStorage.getItem("token");
      if (authToken) headers["Authorization"] = `Bearer ${authToken}`;

      const res = await fetch(`${API_BASE}/api/v1/live-chat/sessions/${code}`, { headers });
      if (res.ok) {
        const data: LiveChatSessionData = await res.json();
        setSession(data);
        setMessages(data.messages || []);
      } else if (res.status === 404 || res.status === 403) {
        localStorage.removeItem(STORAGE_SESSION_KEY);
        setSession(null);
      }
    } catch (err) {
      console.warn("Could not load live chat session:", err);
    }
  };

  // 3. Quản lý WebSocket kết nối Realtime
  useEffect(() => {
    if (!session || session.status === "CLOSED" || authFailed) {
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
      return;
    }

    const sessionCode = session.session_code;
    const authToken = typeof window !== "undefined" ? (localStorage.getItem("pharmatrust_access_token") || localStorage.getItem("token") || "") : "";
    const guestToken = session.guest_session_token || (typeof window !== "undefined" ? (localStorage.getItem(STORAGE_GUEST_TOKEN_KEY) || "") : "");
    const activeToken = authToken || guestToken;
    const wsUrl = `${WS_BASE}/api/v1/live-chat/ws/client/${sessionCode}?token=${encodeURIComponent(activeToken)}`;

    let socket: WebSocket;
    let pingTimer: any;

    try {
      socket = new WebSocket(wsUrl);
      wsRef.current = socket;

      socket.onopen = () => {
        setWsConnected(true);
        // Heartbeat PING định kỳ
        pingTimer = setInterval(() => {
          if (socket.readyState === WebSocket.OPEN) {
            socket.send(JSON.stringify({ type: "PING" }));
          }
        }, 25000);
      };

      socket.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);

          if (payload.type === "NEW_MESSAGE") {
            const incoming: LiveChatMessageItem = payload.message;
            setMessages((prev) => {
              // Chống trùng nếu tin nhắn đã có
              if (incoming.client_msg_id && prev.some((m) => m.client_msg_id === incoming.client_msg_id)) {
                return prev.map((m) => (m.client_msg_id === incoming.client_msg_id ? incoming : m));
              }
              if (prev.some((m) => m.id === incoming.id)) {
                return prev;
              }
              return [...prev, incoming];
            });

            // Nếu tin nhắn từ nhân viên hoặc hệ thống, báo âm thanh và notify
            if (incoming.sender_type !== "CUSTOMER") {
              playNotificationChime();
              onNewMessageNotify?.();
            }
          } else if (payload.type === "SESSION_CLAIMED" || payload.type === "SESSION_ASSIGNED") {
            setSession((prev) =>
              prev
                ? {
                    ...prev,
                    status: "ACTIVE",
                    assigned_staff_id: payload.assigned_staff_id,
                    assigned_staff_name: payload.assigned_staff_name,
                    assigned_staff_title: payload.assigned_staff_title,
                  }
                : null
            );
            playNotificationChime();
          } else if (payload.type === "SESSION_CLOSED") {
            setSession((prev) => (prev ? { ...prev, status: "CLOSED" } : null));
          } else if (payload.type === "STAFF_STATUS") {
            setStaffOnlineInfo({
              is_online: payload.is_online,
              online_count: payload.online_count,
            });
          }
        } catch (e) {
          console.warn("WebSocket parse error:", e);
        }
      };

      socket.onclose = (event) => {
        setWsConnected(false);
        clearInterval(pingTimer);
        if (event.code === 4401 || event.code === 4403) {
          console.warn("LiveChat WebSocket authentication rejected:", event.code);
          setAuthFailed(true);
        }
      };

      socket.onerror = () => {
        setWsConnected(false);
      };
    } catch {
      setWsConnected(false);
    }

    // Fallback polling mỗi 5 giây khi WebSocket không kết nối (dừng nếu lỗi xác thực)
    const pollInterval = setInterval(() => {
      if (!wsConnected && sessionCode && !authFailed) {
        loadSessionDetail(sessionCode, session.guest_session_token || null);
      }
    }, 5000);

    return () => {
      clearInterval(pingTimer);
      clearInterval(pollInterval);
      if (socket && socket.readyState === WebSocket.OPEN) {
        socket.close();
      }
    };
  }, [session?.session_code, session?.status, authFailed]);

  // 4. Bắt đầu phiên Live Chat
  const handleStartSession = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    setFormError(null);
    setIsInitializing(true);

    try {
      const headers: Record<string, string> = { "Content-Type": "application/json" };
      const authToken = localStorage.getItem("pharmatrust_access_token") || localStorage.getItem("token");
      if (authToken) headers["Authorization"] = `Bearer ${authToken}`;

      const existingGuestToken = localStorage.getItem(STORAGE_GUEST_TOKEN_KEY);
      if (existingGuestToken) headers["X-Chat-Guest-Token"] = existingGuestToken;

      let userLat: number | undefined = undefined;
      let userLng: number | undefined = undefined;
      let userCity: string | undefined = undefined;

      try {
        const savedLoc = localStorage.getItem("pharmatrust_user_location");
        if (savedLoc) {
          const parsed = JSON.parse(savedLoc);
          if (parsed.lat && parsed.lng) {
            userLat = Number(parsed.lat);
            userLng = Number(parsed.lng);
          }
          if (parsed.city) userCity = parsed.city;
        }
      } catch {}

      const bodyPayload = {
        customer_name: customerName.trim() || undefined,
        customer_phone: customerPhone.trim() || undefined,
        subject: handoffContext ? "Tư vấn triệu chứng từ Trợ lý AI" : "Tư vấn trực tiếp với nhân viên",
        initial_context: includeAiContext && handoffContext ? handoffContext : undefined,
        shared_ai_history: includeAiContext && !!handoffContext,
        lat: userLat,
        lng: userLng,
        city: userCity,
      };

      const res = await fetch(`${API_BASE}/api/v1/live-chat/sessions`, {
        method: "POST",
        headers,
        body: JSON.stringify(bodyPayload),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Không thể khởi tạo phiên trò chuyện");
      }

      const data: LiveChatSessionData = await res.json();
      setSession(data);
      setMessages(data.messages || []);

      localStorage.setItem(STORAGE_SESSION_KEY, data.session_code);
      if (data.guest_session_token) {
        localStorage.setItem(STORAGE_GUEST_TOKEN_KEY, data.guest_session_token);
      }

      if (onClearHandoff) onClearHandoff();
    } catch (err: any) {
      console.error("[LiveChat Init Error]:", err);
      const msg =
        err.message === "Failed to fetch"
          ? "Không thể kết nối đến máy chủ hỗ trợ trực tiếp. Vui lòng kiểm tra lại kết nối mạng hoặc thử lại sau."
          : (err.detail || err.message || "Đã xảy ra sự cố khi kết nối tới nhân viên tư vấn.");
      setFormError(msg);
    } finally {
      setIsInitializing(false);
    }
  };

  // 5. Gửi tin nhắn
  const handleSendMessage = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    const text = inputText.trim();
    if ((!text && !selectedFile) || isSending || !session) return;

    setIsSending(true);
    let uploadedUrl: string | undefined = undefined;
    let uploadedType: string | undefined = undefined;

    // Nếu có chọn ảnh -> Upload ảnh trước
    if (selectedFile) {
      setIsUploading(true);
      try {
        const formData = new FormData();
        formData.append("file", selectedFile);

        const uploadRes = await fetch(`${API_BASE}/api/v1/live-chat/upload`, {
          method: "POST",
          body: formData,
        });

        if (!uploadRes.ok) {
          const err = await uploadRes.json().catch(() => ({}));
          throw new Error(err.detail || "Tải ảnh lên thất bại");
        }

        const uploadData = await uploadRes.json();
        uploadedUrl = `${API_BASE}${uploadData.url}`;
        uploadedType = uploadData.content_type;
      } catch (err: any) {
        alert(err.message || "Lỗi tải ảnh");
        setIsSending(false);
        setIsUploading(false);
        return;
      } finally {
        setIsUploading(false);
      }
    }

    const clientMsgId = `client-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;

    // Optimistic UI message
    const tempMsg: LiveChatMessageItem = {
      id: clientMsgId,
      sender_type: "CUSTOMER",
      sender_name: session.customer_name || "Bạn",
      content: text || "(Hình ảnh đính kèm)",
      attachment_url: uploadedUrl,
      attachment_type: uploadedType,
      client_msg_id: clientMsgId,
      created_at: new Date().toISOString(),
      isPending: true,
    };

    setMessages((prev) => [...prev, tempMsg]);
    setInputText("");
    setSelectedFile(null);
    setPreviewImage(null);

    try {
      const headers: Record<string, string> = { "Content-Type": "application/json" };
      if (session.guest_session_token) headers["X-Chat-Guest-Token"] = session.guest_session_token;
      const authToken = localStorage.getItem("pharmatrust_access_token") || localStorage.getItem("token");
      if (authToken) headers["Authorization"] = `Bearer ${authToken}`;

      const res = await fetch(`${API_BASE}/api/v1/live-chat/sessions/${session.session_code}/messages`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          content: tempMsg.content,
          attachment_url: uploadedUrl,
          attachment_type: uploadedType,
          client_msg_id: clientMsgId,
        }),
      });

      if (!res.ok) {
        throw new Error("Lỗi gửi tin nhắn");
      }

      const savedMsg: LiveChatMessageItem = await res.json();
      setMessages((prev) => prev.map((m) => (m.client_msg_id === clientMsgId ? savedMsg : m)));
    } catch {
      setMessages((prev) =>
        prev.map((m) => (m.client_msg_id === clientMsgId ? { ...m, isPending: false, isError: true } : m))
      );
    } finally {
      setIsSending(false);
    }
  };

  // 6. Xử lý chọn tệp ảnh
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (!file.type.startsWith("image/")) {
      alert("Vui lòng chọn tệp định dạng hình ảnh (JPG, PNG, WEBP).");
      return;
    }

    if (file.size > 5 * 1024 * 1024) {
      alert("Dung lượng ảnh vượt quá 5MB. Vui lòng chọn ảnh nhỏ hơn.");
      return;
    }

    setSelectedFile(file);
    const reader = new FileReader();
    reader.onload = () => {
      setPreviewImage(reader.result as string);
    };
    reader.readAsDataURL(file);
  };

  // 7. Đóng cuộc trò chuyện
  const handleCloseSession = async () => {
    if (!session || !window.confirm("Bạn có chắc chắn muốn kết thúc cuộc trò chuyện với nhân viên tư vấn không?")) return;

    try {
      const headers: Record<string, string> = { "Content-Type": "application/json" };
      if (session.guest_session_token) headers["X-Chat-Guest-Token"] = session.guest_session_token;
      const authToken = localStorage.getItem("pharmatrust_access_token") || localStorage.getItem("token");
      if (authToken) headers["Authorization"] = `Bearer ${authToken}`;

      await fetch(`${API_BASE}/api/v1/live-chat/sessions/${session.session_code}/close`, {
        method: "POST",
        headers,
        body: JSON.stringify({ rating: ratingVal, feedback: feedbackText }),
      });

      setSession((prev) => (prev ? { ...prev, status: "CLOSED" } : null));
    } catch (e) {
      console.error(e);
    }
  };

  // 8. Bắt đầu phiên mới
  const handleStartNewSession = () => {
    localStorage.removeItem(STORAGE_SESSION_KEY);
    setSession(null);
    setMessages([]);
    setHasRated(false);
  };

  // 9. Gửi đánh giá sau khi đóng
  const handleSubmitRating = async () => {
    if (!session) return;
    try {
      const headers: Record<string, string> = { "Content-Type": "application/json" };
      if (session.guest_session_token) headers["X-Chat-Guest-Token"] = session.guest_session_token;
      const authToken = localStorage.getItem("pharmatrust_access_token") || localStorage.getItem("token");
      if (authToken) headers["Authorization"] = `Bearer ${authToken}`;

      await fetch(`${API_BASE}/api/v1/live-chat/sessions/${session.session_code}/close`, {
        method: "POST",
        headers,
        body: JSON.stringify({ rating: ratingVal, feedback: feedbackText }),
      });

      setHasRated(true);
    } catch {
      setHasRated(true);
    }
  };

  // GIAO DIỆN 1: KHI CHƯA CÓ PHIÊN CHAT (HOẶC VỪA TỪ AI SANG)
  if (!session) {
    return (
      <div className="flex-1 flex flex-col p-4 bg-slate-50 overflow-y-auto">
        {/* Banner giới thiệu kênh Live Chat */}
        <div className="bg-white p-4 rounded-2xl border border-slate-200/90 shadow-xs mb-4">
          <div className="flex items-start gap-3">
            <div className="w-10 h-10 rounded-xl bg-brand-blue-50 text-brand-blue-600 flex items-center justify-center shrink-0">
              <Headphones className="w-5 h-5" />
            </div>
            <div>
              <h4 className="text-sm font-extrabold text-slate-800">
                Tư Vấn Trực Tiếp Cùng Nhân Viên H4CARE
              </h4>
              <p className="text-xs text-slate-500 mt-1 leading-relaxed">
                Kết nối với đội ngũ tư vấn viên và dược sĩ chuyên môn để được hỗ trợ cụ thể về đơn thuốc, cách dùng và bảo hành đổi trả.
              </p>
            </div>
          </div>

          {/* Trạng thái nhân viên trực tuyến thực tế */}
          <div className="mt-3 pt-3 border-t border-slate-100 flex items-center justify-between text-xs">
            <span className="text-slate-500 flex items-center gap-1.5">
              <span
                className={`w-2 h-2 rounded-full ${
                  staffOnlineInfo?.is_online ? "bg-emerald-500 animate-pulse" : "bg-amber-500"
                }`}
              />
              {staffOnlineInfo?.is_online
                ? `Nhân viên đang trực tuyến (${staffOnlineInfo.online_count} trực tiếp)`
                : "Ngoài giờ hỗ trợ trực tiếp (08:00 - 21:00)"}
            </span>
            <span className="text-[11px] text-brand-blue-600 font-semibold flex items-center gap-1">
              <PhoneCall className="w-3 h-3" /> Hotline 1800 6828
            </span>
          </div>
        </div>

        {/* Khối Handoff từ AI (nếu chuyển từ AI sang) */}
        {handoffContext && (
          <div className="bg-amber-50 border border-amber-200 p-3.5 rounded-2xl mb-4 text-xs">
            <div className="flex items-center gap-1.5 font-bold text-amber-900 mb-1.5">
              <Info className="w-4 h-4 text-amber-600 shrink-0" />
              <span>Tóm tắt từ Trợ lý AI sẵn sàng chuyển tiếp:</span>
            </div>
            <p className="text-amber-800 line-clamp-3 bg-white/70 p-2 rounded-lg border border-amber-100 font-mono text-[11px]">
              {handoffContext}
            </p>
            <label className="flex items-center gap-2 mt-2.5 cursor-pointer text-amber-950 font-medium">
              <input
                type="checkbox"
                checked={includeAiContext}
                onChange={(e) => setIncludeAiContext(e.target.checked)}
                className="rounded border-amber-300 text-brand-blue-600 focus:ring-brand-blue-500"
              />
              <span>Đồng ý chia sẻ đoạn tóm tắt này để nhân viên nắm bắt nhanh</span>
            </label>
          </div>
        )}

        {/* Form nhập thông tin kết nối */}
        <form onSubmit={handleStartSession} className="bg-white p-4 rounded-2xl border border-slate-200/90 shadow-xs flex-1 flex flex-col justify-between">
          <div className="space-y-3">
            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1">
                Họ và tên của bạn
              </label>
              <input
                type="text"
                placeholder="VD: Nguyễn Văn A (hoặc để trống)"
                value={customerName}
                onChange={(e) => setCustomerName(e.target.value)}
                className="w-full px-3 py-2 text-xs border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-brand-blue-500"
              />
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-700 mb-1">
                Số điện thoại liên hệ
              </label>
              <input
                type="tel"
                placeholder="VD: 0912 345 678 (để nhận liên hệ khi ngoài giờ)"
                value={customerPhone}
                onChange={(e) => setCustomerPhone(e.target.value)}
                className="w-full px-3 py-2 text-xs border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-brand-blue-500"
              />
            </div>
          </div>

          {formError && (
            <div className="mt-3 p-3 rounded-xl bg-red-50 border border-red-200 text-red-700 text-xs flex items-start gap-2">
              <AlertCircle className="w-4 h-4 text-red-600 shrink-0 mt-0.5" />
              <span className="leading-relaxed">{formError}</span>
            </div>
          )}

          <div className="pt-4 space-y-2">
            <button
              type="submit"
              disabled={isInitializing}
              className="w-full py-2.5 px-4 rounded-xl bg-gradient-to-r from-brand-blue-700 to-brand-blue-600 hover:from-brand-blue-800 hover:to-brand-blue-700 text-white font-bold text-xs flex items-center justify-center gap-2 shadow-xs transition-all disabled:opacity-50"
            >
              {isInitializing ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Đang kết nối hệ thống...</span>
                </>
              ) : (
                <>
                  <Headphones className="w-4 h-4" />
                  <span>Bắt đầu trò chuyện với nhân viên</span>
                </>
              )}
            </button>

            {onBackToAi && (
              <button
                type="button"
                onClick={onBackToAi}
                className="w-full py-2 px-3 rounded-xl border border-slate-200 text-slate-600 hover:bg-slate-50 text-xs font-semibold transition-colors"
              >
                Quay lại Trợ lý AI H4CARE
              </button>
            )}
          </div>
        </form>
      </div>
    );
  }

  // GIAO DIỆN 2: TRONG CUỘC TRÒ CHUYỆN (WAITING / ACTIVE / CLOSED)
  return (
    <div className="flex-1 flex flex-col h-full bg-slate-50 overflow-hidden relative">
      {/* Cảnh báo lỗi xác thực WebSocket */}
      {authFailed && (
        <div className="bg-rose-50 border-b border-rose-200 px-3.5 py-2.5 flex items-center justify-between text-xs text-rose-800 shrink-0">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
            <span>Phiên kết nối đã hết hạn hoặc xác thực không hợp lệ.</span>
          </div>
          <button
            onClick={() => {
              if (typeof window !== "undefined") {
                localStorage.removeItem(STORAGE_SESSION_KEY);
                localStorage.removeItem(STORAGE_GUEST_TOKEN_KEY);
              }
              setSession(null);
              setAuthFailed(false);
            }}
            className="px-2.5 py-1 bg-rose-600 text-white rounded-lg text-[11px] font-semibold hover:bg-rose-700 transition-colors shrink-0"
          >
            Bắt đầu phiên mới
          </button>
        </div>
      )}

      {/* Thanh trạng thái phiên Live Chat */}
      <div className="px-3.5 py-2 bg-white border-b border-slate-200/80 flex items-center justify-between text-xs shrink-0 shadow-2xs">
        <div className="flex items-center gap-2 truncate">
          <div className="relative">
            <div className="w-7 h-7 rounded-lg bg-brand-blue-50 text-brand-blue-600 flex items-center justify-center font-bold text-xs">
              <Headphones className="w-4 h-4" />
            </div>
            <span
              className={`absolute -bottom-0.5 -right-0.5 w-2 h-2 rounded-full border border-white ${
                session.status === "ACTIVE"
                  ? "bg-emerald-500"
                  : session.status === "WAITING"
                  ? "bg-amber-400 animate-pulse"
                  : "bg-slate-400"
              }`}
            />
          </div>

          <div className="truncate">
            <div className="flex items-center gap-1.5 truncate">
              <span className="font-bold text-slate-800 truncate">
                {session.status === "ACTIVE"
                  ? session.assigned_staff_name || "Nhân viên tư vấn"
                  : session.status === "WAITING"
                  ? "Đang chờ nhân viên tiếp nhận..."
                  : "Cuộc trò chuyện đã kết thúc"}
              </span>
              {session.status === "ACTIVE" && session.assigned_staff_title && (
                <span className="px-1.5 py-0.2 bg-brand-blue-50 text-brand-blue-700 text-[10px] font-bold rounded-md shrink-0 border border-brand-blue-100">
                  {session.assigned_staff_title}
                </span>
              )}
            </div>
            <p className="text-[10px] text-slate-400">
              Mã phiên: <span className="font-mono text-slate-600">{session.session_code}</span>
            </p>
          </div>
        </div>

        {/* Nút hành động trên header phiên */}
        <div className="flex items-center gap-1 shrink-0">
          {session.status !== "CLOSED" ? (
            <button
              type="button"
              onClick={handleCloseSession}
              className="px-2 py-1 rounded-lg border border-rose-200 text-rose-600 hover:bg-rose-50 text-[11px] font-semibold transition-colors"
              title="Kết thúc tư vấn"
            >
              Kết thúc
            </button>
          ) : (
            <button
              type="button"
              onClick={handleStartNewSession}
              className="px-2 py-1 rounded-lg bg-brand-blue-50 text-brand-blue-600 hover:bg-brand-blue-100 text-[11px] font-bold transition-colors flex items-center gap-1"
            >
              <RotateCcw className="w-3 h-3" /> Mới
            </button>
          )}

          {onBackToAi && (
            <button
              type="button"
              onClick={onBackToAi}
              className="p-1 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors"
              title="Mở Trợ lý AI"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>

      {/* Thông báo nếu phiên đang WAITING */}
      {session.status === "WAITING" && (
        <div className="px-3 py-1.5 bg-amber-50 border-b border-amber-200/70 text-[11px] text-amber-900 flex items-center gap-1.5 shrink-0">
          <Clock className="w-3.5 h-3.5 text-amber-600 shrink-0 animate-spin" />
          <span>Hệ thống đang điều phối nhân viên tiếp nhận ca tư vấn của bạn...</span>
        </div>
      )}

      {/* Danh sách tin nhắn */}
      <div className="flex-1 p-3.5 overflow-y-auto space-y-3">
        {messages.map((msg, idx) => {
          const isMe = msg.sender_type === "CUSTOMER";
          const isSystem = msg.sender_type === "SYSTEM";

          if (isSystem) {
            return (
              <div key={msg.id || idx} className="flex justify-center my-2">
                <div className="max-w-[85%] px-3 py-1.5 rounded-xl bg-slate-200/70 text-slate-600 text-[11px] text-center leading-relaxed">
                  {msg.content}
                </div>
              </div>
            );
          }

          return (
            <div
              key={msg.id || idx}
              className={`flex items-end gap-1.5 ${isMe ? "justify-end" : "justify-start"}`}
            >
              {/* Avatar người gửi phía nhân viên */}
              {!isMe && (
                <div className="w-7 h-7 rounded-full bg-gradient-to-tr from-brand-blue-600 to-teal-500 text-white flex items-center justify-center text-xs font-bold shrink-0 shadow-xs">
                  {msg.sender_name.slice(0, 1).toUpperCase()}
                </div>
              )}

              <div
                className={`max-w-[78%] flex flex-col ${isMe ? "items-end" : "items-start"}`}
              >
                {/* Tên và chức danh người gửi */}
                {!isMe && (
                  <div className="flex items-center gap-1 mb-0.5 px-1">
                    <span className="text-[10px] font-bold text-slate-700">{msg.sender_name}</span>
                    {msg.sender_role_title && (
                      <span className="text-[9px] text-brand-blue-600 bg-brand-blue-50 px-1 rounded font-semibold">
                        {msg.sender_role_title}
                      </span>
                    )}
                  </div>
                )}

                {/* Bong bóng tin nhắn */}
                <div
                  className={`px-3 py-2 rounded-2xl text-xs leading-relaxed shadow-2xs break-words ${
                    isMe
                      ? "bg-brand-blue-600 text-white rounded-br-xs"
                      : "bg-white text-slate-800 border border-slate-200/90 rounded-bl-xs"
                  }`}
                >
                  {/* Hình ảnh đính kèm (nếu có) */}
                  {msg.attachment_url && (
                    <div className="mb-2 overflow-hidden rounded-xl cursor-pointer">
                      <SecureChatImage
                        url={msg.attachment_url}
                        onClick={(blobUrl) => setZoomImage(blobUrl)}
                      />
                    </div>
                  )}

                  <p className="whitespace-pre-wrap">{msg.content}</p>

                  {/* Thời gian & Trạng thái gửi */}
                  <div
                    className={`mt-1 flex items-center justify-end gap-1 text-[9px] ${
                      isMe ? "text-brand-blue-100" : "text-slate-400"
                    }`}
                  >
                    <span>
                      {msg.created_at
                        ? new Date(msg.created_at).toLocaleTimeString("vi-VN", {
                            hour: "2-digit",
                            minute: "2-digit",
                          })
                        : "Vừa xong"}
                    </span>
                    {msg.isPending && <Clock className="w-2.5 h-2.5 animate-spin" />}
                    {msg.isError && (
                      <span className="text-rose-300 font-bold flex items-center gap-0.5">
                        <AlertCircle className="w-2.5 h-2.5" /> Lỗi
                      </span>
                    )}
                  </div>
                </div>
              </div>
            </div>
          );
        })}
        <div ref={messagesEndRef} />
      </div>

      {/* Khung đánh giá khi phiên đã đóng */}
      {session.status === "CLOSED" && !hasRated && (
        <div className="m-3 p-3 bg-white rounded-2xl border border-slate-200 shadow-xs text-xs">
          <h5 className="font-bold text-slate-800 text-center mb-1">
            Đánh giá chất lượng hỗ trợ
          </h5>
          <p className="text-[11px] text-slate-500 text-center mb-2.5">
            Ý kiến của quý khách giúp H4CARE ngày càng hoàn thiện dịch vụ!
          </p>
          <div className="flex justify-center gap-1.5 mb-2.5">
            {[1, 2, 3, 4, 5].map((star) => (
              <button
                key={star}
                type="button"
                onClick={() => setRatingVal(star)}
                className="p-1 text-slate-300 hover:text-amber-400 transition-colors"
              >
                <Star
                  className={`w-5 h-5 ${
                    star <= ratingVal ? "text-amber-400 fill-amber-400" : "text-slate-300"
                  }`}
                />
              </button>
            ))}
          </div>
          <input
            type="text"
            placeholder="Để lại lời nhắn đóng góp (tùy chọn)..."
            value={feedbackText}
            onChange={(e) => setFeedbackText(e.target.value)}
            className="w-full px-2.5 py-1.5 text-xs border border-slate-200 rounded-xl mb-2 focus:outline-none focus:ring-1 focus:ring-brand-blue-500"
          />
          <button
            type="button"
            onClick={handleSubmitRating}
            className="w-full py-1.5 rounded-xl bg-brand-blue-600 text-white font-bold text-xs hover:bg-brand-blue-700 transition-colors"
          >
            Gửi đánh giá
          </button>
        </div>
      )}

      {/* Preview hình ảnh đang chuẩn bị gửi */}
      {previewImage && (
        <div className="px-3.5 py-2 bg-slate-100 border-t border-slate-200 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-2">
            <img src={previewImage} alt="Preview" className="w-10 h-10 object-cover rounded-lg border border-white" />
            <span className="text-[11px] text-slate-600 truncate max-w-[200px]">
              {selectedFile?.name}
            </span>
          </div>
          <button
            type="button"
            onClick={() => {
              setSelectedFile(null);
              setPreviewImage(null);
            }}
            className="p-1 text-slate-400 hover:text-slate-700 rounded transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Ô nhập tin nhắn Live Chat */}
      {session.status !== "CLOSED" ? (
        <form
          onSubmit={handleSendMessage}
          className="p-2.5 bg-white border-t border-slate-200 flex items-center gap-1.5 shrink-0"
        >
          {/* Nút chọn ảnh đính kèm */}
          <input
            ref={fileInputRef}
            type="file"
            accept="image/jpeg,image/png,image/webp"
            className="hidden"
            onChange={handleFileChange}
          />
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={isSending || isUploading}
            className="p-2 rounded-xl text-slate-500 hover:text-brand-blue-600 hover:bg-slate-100 transition-colors disabled:opacity-50"
            title="Gửi ảnh đơn thuốc / sản phẩm"
          >
            <ImageIcon className="w-5 h-5" />
          </button>

          {/* Ô gõ tin nhắn */}
          <input
            type="text"
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            disabled={isSending}
            placeholder="Nhập tin nhắn gửi nhân viên tư vấn..."
            className="flex-1 px-3 py-2 text-xs border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-brand-blue-500 disabled:bg-slate-50"
          />

          {/* Nút gửi */}
          <button
            type="submit"
            disabled={(!inputText.trim() && !selectedFile) || isSending}
            className="p-2 rounded-xl bg-brand-blue-600 hover:bg-brand-blue-700 text-white transition-colors disabled:opacity-40 disabled:hover:bg-brand-blue-600"
            title="Gửi"
          >
            {isSending ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Send className="w-4 h-4" />
            )}
          </button>
        </form>
      ) : (
        <div className="p-3 bg-slate-100 border-t border-slate-200 text-center text-xs text-slate-500">
          Cuộc trò chuyện đã kết thúc. Nhấn nút <strong>"Mới"</strong> ở góc trên để tạo yêu cầu mới.
        </div>
      )}

      {/* Modal phóng to ảnh xem chi tiết */}
      {zoomImage && (
        <div
          className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4 cursor-pointer"
          onClick={() => setZoomImage(null)}
        >
          <div className="relative max-w-full max-h-full">
            <img src={zoomImage} alt="Zoom" className="max-h-[85vh] max-w-[90vw] object-contain rounded-2xl" />
            <button
              type="button"
              className="absolute -top-3 -right-3 w-8 h-8 rounded-full bg-white text-slate-800 flex items-center justify-center shadow-lg"
              onClick={() => setZoomImage(null)}
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
