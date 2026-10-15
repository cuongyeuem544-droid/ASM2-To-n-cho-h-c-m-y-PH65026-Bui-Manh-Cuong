import { useEffect, useRef, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Bell,
  X,
  CheckCheck,
  PackageCheck,
  RotateCcw,
  AlertTriangle,
  Boxes,
  ArrowLeftRight,
  Clock,
  ShieldAlert,
  ExternalLink,
  Camera,
  RefreshCw,
} from 'lucide-react'
import { api } from '../services/api'
import { WarehouseNotificationItem } from '../types'

interface NotificationBellProps {
  viewAllUrl?: string
  bellColor?: string
}

export function NotificationBell({ viewAllUrl, bellColor }: NotificationBellProps) {
  const navigate = useNavigate()
  const [isOpen, setIsOpen] = useState(false)
  const [unreadCount, setUnreadCount] = useState<number>(0)
  const [notifications, setNotifications] = useState<WarehouseNotificationItem[]>([])
  const [loading, setLoading] = useState(false)
  const [markingAll, setMarkingAll] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const dropdownRef = useRef<HTMLDivElement>(null)
  const bellButtonRef = useRef<HTMLButtonElement>(null)

  // 1. Tải số lượng chưa đọc (phục vụ badge & polling)
  const fetchUnreadCount = useCallback(async () => {
    try {
      const res = await api<{ unread_count: number }>('/warehouse-portal/notifications/unread-count')
      setUnreadCount(res.unread_count || 0)
    } catch {
      // Âm thầm bỏ qua khi mạng chập chờn
    }
  }, [])

  // 2. Tải danh sách 10 thông báo mới nhất khi mở dropdown
  const fetchNotifications = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await api<{
        items: WarehouseNotificationItem[]
        total: number
        unread_total: number
      }>('/warehouse-portal/notifications?page=1&page_size=10')
      setNotifications(res.items || [])
      setUnreadCount(res.unread_total || 0)
    } catch (err: any) {
      setError(err?.message || 'Không thể tải danh sách thông báo')
    } finally {
      setLoading(false)
    }
  }, [])

  // Polling 30 giây & Lắng nghe tab focus (visibilitychange)
  useEffect(() => {
    fetchUnreadCount()

    const intervalId = window.setInterval(() => {
      fetchUnreadCount()
    }, 30000)

    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        fetchUnreadCount()
        if (isOpen) {
          fetchNotifications()
        }
      }
    }

    document.addEventListener('visibilitychange', handleVisibilityChange)

    return () => {
      window.clearInterval(intervalId)
      document.removeEventListener('visibilitychange', handleVisibilityChange)
    }
  }, [fetchUnreadCount, isOpen, fetchNotifications])

  // Khi mở dropdown, tải dữ liệu thông báo
  const handleToggle = () => {
    if (!isOpen) {
      setIsOpen(true)
      fetchNotifications()
    } else {
      setIsOpen(false)
    }
  }

  // Đóng khi click ngoài hoặc ấn Escape
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        setIsOpen(false)
        bellButtonRef.current?.focus()
      }
    }

    const handleClickOutside = (e: MouseEvent) => {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(e.target as Node) &&
        bellButtonRef.current &&
        !bellButtonRef.current.contains(e.target as Node)
      ) {
        setIsOpen(false)
      }
    }

    if (isOpen) {
      document.addEventListener('keydown', handleKeyDown)
      document.addEventListener('mousedown', handleClickOutside)
    }

    return () => {
      document.removeEventListener('keydown', handleKeyDown)
      document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [isOpen])

  // Đánh dấu 1 thông báo đã đọc và mở link nghiệp vụ
  const handleItemClick = async (notif: WarehouseNotificationItem) => {
    if (!notif.is_read) {
      try {
        await api(`/warehouse-portal/notifications/${notif.id}/read`, { method: 'PATCH' })
        setNotifications((prev) =>
          prev.map((item) => (item.id === notif.id ? { ...item, is_read: true } : item))
        )
        setUnreadCount((c) => Math.max(0, c - 1))
      } catch {
        // Tiếp tục chuyển trang kể cả khi network read fail
      }
    }
    setIsOpen(false)
    if (notif.action_url) {
      navigate(notif.action_url)
    }
  }

  // Đánh dấu tất cả là đã đọc
  const handleMarkAllRead = async () => {
    if (markingAll || unreadCount === 0) return
    setMarkingAll(true)
    try {
      await api('/warehouse-portal/notifications/mark-all-read', { method: 'POST' })
      setNotifications((prev) => prev.map((item) => ({ ...item, is_read: true })))
      setUnreadCount(0)
    } catch (err: any) {
      alert(err?.message || 'Không thể đánh dấu tất cả đã đọc')
    } finally {
      setMarkingAll(false)
    }
  }

  // Lựa chọn Icon và Màu sắc đồng bộ theo quy tắc H4CARE
  const getBadgeStyle = (notif: WarehouseNotificationItem) => {
    const type = notif.notification_type
    const sev = notif.severity

    if (sev === 'CRITICAL' || sev === 'EXPIRED') {
      return {
        bg: '#fef2f2',
        color: '#dc2626',
        border: '#fecaca',
        icon: <ShieldAlert size={16} className="text-rose-600" />,
        label: sev === 'EXPIRED' ? 'Đã hết hạn' : 'Khẩn cấp',
      }
    }

    if (sev === 'HIGH' || sev === 'WARNING') {
      return {
        bg: '#fffbeb',
        color: '#d97706',
        border: '#fde68a',
        icon: <AlertTriangle size={16} className="text-amber-600" />,
        label: 'Cảnh báo',
      }
    }

    if (type.startsWith('RETURN_')) {
      return {
        bg: '#faf5ff',
        color: '#7e22ce',
        border: '#e9d5ff',
        icon: type.includes('EVIDENCE') ? <Camera size={16} className="text-purple-600" /> : <RotateCcw size={16} className="text-purple-600" />,
        label: 'Đổi trả',
      }
    }

    if (type === 'TRANSFER_ASSIGNED') {
      return {
        bg: '#eef2ff',
        color: '#4f46e5',
        border: '#c7d2fe',
        icon: <ArrowLeftRight size={16} className="text-indigo-600" />,
        label: 'Điều chuyển',
      }
    }

    if (type === 'STOCK_LOW' || type === 'STOCK_OUT') {
      return {
        bg: '#fff7ed',
        color: '#ea580c',
        border: '#fed7aa',
        icon: <Boxes size={16} className="text-orange-600" />,
        label: 'Tồn kho',
      }
    }

    // ORDER_NEW / ORDER_ASSIGNED / Default INFO
    return {
      bg: '#eff6ff',
      color: '#1d4ed8',
      border: '#bfdbfe',
      icon: <PackageCheck size={16} className="text-blue-600" />,
      label: 'Đơn hàng',
    }
  }

  // Định dạng ngày giờ thân thiện
  const formatTime = (isoString: string | null) => {
    if (!isoString) return ''
    try {
      const d = new Date(isoString)
      return d.toLocaleString('vi-VN', {
        hour: '2-digit',
        minute: '2-digit',
        day: '2-digit',
        month: '2-digit',
      })
    } catch {
      return ''
    }
  }

  return (
    <div style={{ position: 'relative', display: 'inline-block' }}>
      {/* Nút Chuông Thông Báo */}
      <button
        ref={bellButtonRef}
        type="button"
        onClick={handleToggle}
        aria-label="Thông báo"
        aria-expanded={isOpen}
        style={{
          position: 'relative',
          padding: '8px',
          borderRadius: '10px',
          background: isOpen ? (bellColor ? 'rgba(255,255,255,0.2)' : '#f1f5f9') : 'transparent',
          border: 'none',
          color: bellColor || '#475569',
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          transition: 'all 0.15s ease',
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.background = bellColor ? 'rgba(255,255,255,0.2)' : '#f1f5f9'
          if (!bellColor) e.currentTarget.style.color = '#0f172a'
        }}
        onMouseLeave={(e) => {
          if (!isOpen) {
            e.currentTarget.style.background = 'transparent'
            e.currentTarget.style.color = bellColor || '#475569'
          }
        }}
      >
        <Bell size={20} />

        {/* Badge đỏ hiển thị số lượng chưa đọc */}
        {unreadCount > 0 && (
          <span
            style={{
              position: 'absolute',
              top: '4px',
              right: '4px',
              minWidth: '18px',
              height: '18px',
              padding: '0 4px',
              background: '#ef4444',
              color: 'white',
              fontSize: '10px',
              fontWeight: 800,
              borderRadius: '9999px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              lineHeight: 1,
              boxShadow: '0 1px 3px rgba(239, 68, 68, 0.4)',
              border: '2px solid white',
            }}
          >
            {unreadCount > 99 ? '99+' : unreadCount}
          </span>
        )}
      </button>

      {/* Bảng Dropdown Thông Báo */}
      {isOpen && (
        <div
          ref={dropdownRef}
          style={{
            position: 'absolute',
            top: 'calc(100% + 8px)',
            right: 0,
            width: '380px',
            maxWidth: 'calc(100vw - 32px)',
            background: 'white',
            borderRadius: '16px',
            boxShadow: '0 12px 36px -4px rgba(15, 23, 42, 0.16), 0 4px 12px rgba(15, 23, 42, 0.08)',
            border: '1px solid #e2e8f0',
            zIndex: 100,
            overflow: 'hidden',
            display: 'flex',
            flexDirection: 'column',
          }}
        >
          {/* Header Dropdown */}
          <div
            style={{
              padding: '12px 16px',
              borderBottom: '1px solid #f1f5f9',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              background: '#ffffff',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontSize: '15px', fontWeight: 800, color: '#0f172a' }}>Thông báo</span>
              {unreadCount > 0 && (
                <span
                  style={{
                    padding: '2px 8px',
                    borderRadius: '9999px',
                    background: '#fee2e2',
                    color: '#dc2626',
                    fontSize: '11px',
                    fontWeight: 700,
                  }}
                >
                  {unreadCount} chưa đọc
                </span>
              )}
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              {unreadCount > 0 && (
                <button
                  type="button"
                  onClick={handleMarkAllRead}
                  disabled={markingAll}
                  style={{
                    background: 'none',
                    border: 'none',
                    fontSize: '11.5px',
                    fontWeight: 700,
                    color: '#059669',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px',
                    padding: '4px 6px',
                    borderRadius: '6px',
                  }}
                  title="Đánh dấu tất cả là đã đọc"
                >
                  <CheckCheck size={14} />
                  {markingAll ? 'Đang lưu…' : 'Đã đọc tất cả'}
                </button>
              )}

              <button
                type="button"
                onClick={() => setIsOpen(false)}
                style={{
                  background: 'none',
                  border: 'none',
                  color: '#94a3b8',
                  cursor: 'pointer',
                  padding: '4px',
                  borderRadius: '6px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
                title="Đóng"
              >
                <X size={16} />
              </button>
            </div>
          </div>

          {/* Body: Danh Sách Thông Báo */}
          <div
            style={{
              maxHeight: '420px',
              overflowY: 'auto',
            }}
          >
            {loading ? (
              <div style={{ padding: '36px 16px', textAlign: 'center', color: '#64748b', fontSize: '13px' }}>
                <RefreshCw size={20} className="animate-spin mx-auto mb-2 text-emerald-600" />
                Đang tải thông báo…
              </div>
            ) : error ? (
              <div style={{ padding: '24px 16px', textAlign: 'center', color: '#dc2626', fontSize: '13px' }}>
                <AlertTriangle size={20} className="mx-auto mb-1 text-rose-500" />
                <div>{error}</div>
                <button
                  type="button"
                  onClick={fetchNotifications}
                  style={{
                    marginTop: '8px',
                    padding: '4px 12px',
                    borderRadius: '6px',
                    background: '#f1f5f9',
                    border: 'none',
                    fontSize: '11.5px',
                    fontWeight: 700,
                    color: '#0f172a',
                    cursor: 'pointer',
                  }}
                >
                  Thử lại
                </button>
              </div>
            ) : notifications.length === 0 ? (
              <div style={{ padding: '36px 16px', textAlign: 'center', color: '#94a3b8', fontSize: '13px' }}>
                <Bell size={28} className="mx-auto mb-2 text-slate-300" />
                Hiện không có thông báo nào
              </div>
            ) : (
              notifications.map((item) => {
                const badge = getBadgeStyle(item)
                return (
                  <div
                    key={item.id}
                    onClick={() => handleItemClick(item)}
                    style={{
                      padding: '12px 16px',
                      display: 'flex',
                      alignItems: 'flex-start',
                      gap: '12px',
                      background: item.is_read ? '#ffffff' : '#f0fdf4',
                      borderBottom: '1px solid #f1f5f9',
                      cursor: 'pointer',
                      transition: 'background 0.15s ease',
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.background = item.is_read ? '#f8fafc' : '#dcfce7'
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.background = item.is_read ? '#ffffff' : '#f0fdf4'
                    }}
                  >
                    {/* Icon loại thông báo */}
                    <div
                      style={{
                        width: '32px',
                        height: '32px',
                        borderRadius: '10px',
                        background: badge.bg,
                        border: `1px solid ${badge.border}`,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        flexShrink: 0,
                        marginTop: '2px',
                      }}
                    >
                      {badge.icon}
                    </div>

                    {/* Nội dung thông báo */}
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '6px', marginBottom: '2px' }}>
                        <span
                          style={{
                            fontSize: '12.5px',
                            fontWeight: item.is_read ? 600 : 800,
                            color: item.is_read ? '#334155' : '#0f172a',
                            lineHeight: 1.3,
                          }}
                        >
                          {item.title}
                        </span>

                        {!item.is_read && (
                          <span
                            style={{
                              width: '7px',
                              height: '7px',
                              borderRadius: '9999px',
                              background: '#059669',
                              flexShrink: 0,
                            }}
                            title="Chưa đọc"
                          />
                        )}
                      </div>

                      <p
                        style={{
                          fontSize: '12px',
                          color: '#64748b',
                          margin: 0,
                          lineHeight: 1.4,
                          display: '-webkit-box',
                          WebkitLineClamp: 2,
                          WebkitBoxOrient: 'vertical',
                          overflow: 'hidden',
                        }}
                      >
                        {item.message}
                      </p>

                      <div
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '8px',
                          marginTop: '5px',
                          fontSize: '11px',
                          color: '#94a3b8',
                        }}
                      >
                        <span
                          style={{
                            padding: '1px 6px',
                            borderRadius: '4px',
                            background: badge.bg,
                            color: badge.color,
                            fontWeight: 700,
                            fontSize: '10px',
                          }}
                        >
                          {badge.label}
                        </span>
                        <span>{formatTime(item.created_at)}</span>
                      </div>
                    </div>
                  </div>
                )
              })
            )}
          </div>

          {/* Footer Dropdown */}
          <div
            style={{
              padding: '10px 16px',
              borderTop: '1px solid #f1f5f9',
              background: '#f8fafc',
              textAlign: 'center',
            }}
          >
            <button
              type="button"
              onClick={() => {
                setIsOpen(false)
                if (viewAllUrl) {
                  navigate(viewAllUrl)
                } else {
                  navigate('/warehouse/alerts')
                }
              }}
              style={{
                background: 'none',
                border: 'none',
                color: '#059669',
                fontSize: '12.5px',
                fontWeight: 700,
                cursor: 'pointer',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '4px',
              }}
            >
              Xem tất cả thông báo <ExternalLink size={13} />
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
