import {
  Activity,
  AlertTriangle,
  ArrowDownToLine,
  ArrowLeftRight,
  Boxes,
  Building2,
  Database,
  ExternalLink,
  FileInput,
  FlaskConical,
  Globe,
  History,
  Layers,
  LayoutDashboard,
  LogOut,
  Mail,
  Menu,
  MessageSquare,
  RefreshCw,
  Repeat,
  RotateCcw,
  ShieldCheck,
  ShoppingBag,
  ThermometerSnowflake,
  Users,
  X,
  Banknote,
  Bell,
  ChevronRight,
  CheckCircle2,
  FileSpreadsheet,
} from 'lucide-react'
import { useState, useEffect, useRef, type ReactNode } from 'react'
import { NavLink } from 'react-router-dom'
import { useAuth } from '../services/auth'
import { useServerHealth } from '../services/useServerHealth'
import { api } from '../services/api'

const ROLE_NAMES: Record<string, string> = {
  ADMIN: 'Quản trị viên',
  DATA_REVIEWER: 'Kiểm duyệt viên',
  VIEWER: 'Nhân viên tra cứu',
  CUSTOMER: 'Khách hàng',
}

interface NavItem {
  to: string
  label: string
  icon: typeof LayoutDashboard
  adminOnly?: boolean
}

interface NavGroup {
  groupLabel: string
  items: NavItem[]
}

const navGroups: NavGroup[] = [
  {
    groupLabel: 'HỒ SƠ & BÁN HÀNG',
    items: [
      { to: '/', label: 'Tổng quan hệ thống', icon: LayoutDashboard },
      { to: '/products', label: 'Hồ sơ thuốc & Duyệt bán', icon: Boxes },
      { to: '/orders', label: 'Quản lý đơn hàng', icon: ShoppingBag },
      { to: '/reviews', label: 'Đánh giá & Nhận xét', icon: MessageSquare },
      { to: '/campaigns', label: 'Chiến dịch mùa bệnh', icon: ThermometerSnowflake },
      { to: '/candidates', label: 'Thuốc mới chờ duyệt', icon: FlaskConical },
      { to: '/conflicts', label: 'Mâu thuẫn dữ liệu', icon: AlertTriangle },
    ],
  },
  {
    groupLabel: 'HẬU MÃI & ĐỔI TRẢ',
    items: [
      { to: '/returns', label: 'Quản lý Đổi/Trả hàng', icon: RotateCcw },
      { to: '/refunds', label: 'Hoàn tiền & Đối soát', icon: Banknote },
      { to: '/exchanges', label: 'Đơn đổi hàng (Exchanges)', icon: Repeat },
    ],
  },
  {
    groupLabel: 'KHO VẬN & LÔ HẠN DÙNG',
    items: [
      { to: '/warehouses', label: 'Kho & Chi nhánh', icon: Building2 },
      { to: '/inventory/batches', label: 'Lô thuốc & Hạn dùng', icon: Layers },
      { to: '/inventory/receipts', label: 'Nhập kho (GSP)', icon: ArrowDownToLine },
      { to: '/inventory/transfers', label: 'Điều chuyển kho', icon: ArrowLeftRight },
    ],
  },
  {
    groupLabel: 'NHẬP LIỆU & ĐƠN THUỐC',
    items: [
      { to: '/imports', label: 'Nhập file Excel đơn thuốc', icon: FileSpreadsheet },
    ],
  },
  {
    groupLabel: 'QUẢN TRỊ HỆ THỐNG',
    items: [
      { to: '/emails', label: 'Hộp thư & Outbox', icon: Mail, adminOnly: true },
      { to: '/users', label: 'Quản lý người dùng', icon: Users, adminOnly: true },
      { to: '/audit', label: 'Nhật ký thao tác', icon: History, adminOnly: true },
    ],
  },
]

interface ReturnNotifData {
  pending_count: number
  reviewing_count: number
  inspecting_count: number
  total_action_needed: number
  recent_pending: Array<{
    id: number
    return_code: string
    customer_name: string
    customer_phone: string
    reason_text: string
    request_type: string
    requested_at: string | null
  }>
}

export function Layout({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth()
  const { status: healthStatus, latencyMs, lastChecked, checkHealth } = useServerHealth()
  const [open, setOpen] = useState(false)
  const [checking, setChecking] = useState(false)
  const [returnStats, setReturnStats] = useState<ReturnNotifData | null>(null)
  const [showNotifMenu, setShowNotifMenu] = useState(false)
  const [newReturnToast, setNewReturnToast] = useState<string | null>(null)
  const prevCountRef = useRef<number>(0)

  useEffect(() => {
    if (!user || (user.role !== 'ADMIN' && user.role !== 'DATA_REVIEWER')) return

    const fetchStats = async () => {
      try {
        const data = await api<ReturnNotifData>('/admin/returns/notifications/stats')
        if (data) {
          if (data.pending_count > prevCountRef.current && prevCountRef.current > 0) {
            const latest = data.recent_pending?.[0]
            const toastMsg = latest
              ? `Có đơn đổi/trả mới cần duyệt: ${latest.return_code} (${latest.customer_name})`
              : 'Có yêu cầu đổi/trả thuốc mới cần duyệt!'
            setNewReturnToast(toastMsg)
            setTimeout(() => setNewReturnToast(null), 8000)
          }
          prevCountRef.current = data.pending_count
          setReturnStats(data)
        }
      } catch {
        // Ignore background polling errors
      }
    }

    fetchStats()
    const timer = setInterval(fetchStats, 8000)
    return () => clearInterval(timer)
  }, [user])

  const handleManualHealthCheck = async () => {
    setChecking(true)
    await checkHealth()
    setTimeout(() => setChecking(false), 400)
  }

  const renderHealthIndicator = () => {
    switch (healthStatus) {
      case 'ONLINE':
        return (
          <div
            className="system-health-pill health-online"
            title={`API & Cơ sở dữ liệu: Hoạt động bình thường\nĐộ trễ: ${latencyMs ?? 0}ms\nLần kiểm tra cuối: ${
              lastChecked ? lastChecked.toLocaleTimeString('vi-VN') : 'vừa xong'
            }`}
            onClick={handleManualHealthCheck}
          >
            <span className="health-dot dot-online" />
            <span className="health-label">Hệ thống Online</span>
            {latencyMs !== null && <span className="health-latency">{latencyMs}ms</span>}
            <RefreshCw size={11} className={`health-refresh-icon ${checking ? 'spin' : ''}`} />
          </div>
        )
      case 'DEGRADED':
        return (
          <div
            className="system-health-pill health-degraded"
            title={`API phản hồi chậm: ${latencyMs ?? 0}ms (ngưỡng bình thường < 1000ms)\nLần kiểm tra cuối: ${
              lastChecked ? lastChecked.toLocaleTimeString('vi-VN') : 'vừa xong'
            }`}
            onClick={handleManualHealthCheck}
          >
            <span className="health-dot dot-degraded" />
            <span className="health-label">Phản hồi chậm</span>
            {latencyMs !== null && <span className="health-latency">{latencyMs}ms</span>}
            <RefreshCw size={11} className={`health-refresh-icon ${checking ? 'spin' : ''}`} />
          </div>
        )
      case 'OFFLINE':
        return (
          <div
            className="system-health-pill health-offline"
            title="Mất kết nối tới API máy chủ backend (:8000). Vui lòng kiểm tra lại dịch vụ."
            onClick={handleManualHealthCheck}
          >
            <span className="health-dot dot-offline" />
            <span className="health-label">Mất kết nối API</span>
            <RefreshCw size={11} className={`health-refresh-icon ${checking ? 'spin' : ''}`} />
          </div>
        )
      case 'CHECKING':
      default:
        return (
          <div className="system-health-pill health-checking">
            <span className="health-dot dot-checking" />
            <span className="health-label">Đang kiểm tra...</span>
          </div>
        )
    }
  }

  return (
    <div className="app-shell">
      <aside className={`sidebar ${open ? 'sidebar-open' : ''}`}>
        <div className="brand">
          <div className="brand-mark">
            <ShieldCheck size={22} />
          </div>
          <div className="brand-text">
            <strong>PharmaTrust Data Hub</strong>
            <span>Backoffice for H4CARE</span>
          </div>
          <button
            type="button"
            className="icon-button mobile-only"
            onClick={() => setOpen(false)}
            aria-label="Đóng menu"
          >
            <X size={18} />
          </button>
        </div>

        <div className="sidebar-nav-container">
          {navGroups.map((group) => {
            const visibleItems = group.items.filter(
              (item) => !item.adminOnly || user?.role === 'ADMIN'
            )
            if (visibleItems.length === 0) return null

            return (
              <div key={group.groupLabel} className="sidebar-section">
                <div className="sidebar-label">{group.groupLabel}</div>
                <nav>
                  {visibleItems.map((item) => (
                    <NavLink
                      key={item.to}
                      to={item.to}
                      end={item.to === '/'}
                      onClick={() => setOpen(false)}
                      className={({ isActive }) =>
                        `sidebar-nav-item ${isActive ? 'active' : ''}`
                      }
                    >
                      <item.icon size={16} className="nav-item-icon" />
                      <span className="nav-item-text">{item.label}</span>
                      {item.to === '/returns' && (returnStats?.pending_count || 0) > 0 && (
                        <span className="nav-return-badge" title={`${returnStats?.pending_count} đơn chờ duyệt`}>
                          {returnStats?.pending_count}
                        </span>
                      )}
                    </NavLink>
                  ))}
                </nav>
              </div>
            )
          })}
        </div>

        <div className="user-card">
          <div className="avatar">{user?.full_name?.charAt(0) || 'A'}</div>
          <div className="user-info">
            <strong title={user?.full_name}>{user?.full_name}</strong>
            <span>{ROLE_NAMES[user?.role || ''] || user?.role}</span>
          </div>
          <button
            type="button"
            className="icon-button logout-action-btn"
            onClick={logout}
            title="Đăng xuất khỏi hệ thống"
          >
            <LogOut size={16} />
          </button>
        </div>
      </aside>

      <main className="main-content">
        <header className="admin-desktop-header">
          <div className="header-left">
            <button
              type="button"
              className="icon-button mobile-only"
              onClick={() => setOpen(true)}
              aria-label="Mở menu"
            >
              <Menu size={20} />
            </button>
            <div className="hub-identity">
              <span className="hub-name">PharmaTrust Data Hub</span>
              <span className="hub-divider">/</span>
              <span className="hub-sub">H4CARE Operations</span>
            </div>
            {renderHealthIndicator()}
          </div>

          <div className="header-right">
            {/* Notification Bell for Returns / Alerts */}
            {(user?.role === 'ADMIN' || user?.role === 'DATA_REVIEWER') && (
              <div className="admin-notif-container">
                <button
                  type="button"
                  className={`admin-notif-btn ${(returnStats?.pending_count || 0) > 0 ? 'has-unread' : ''}`}
                  onClick={() => setShowNotifMenu(!showNotifMenu)}
                  title="Thông báo đơn đổi/trả hàng cần duyệt"
                  aria-label="Thông báo"
                >
                  <Bell size={18} />
                  {(returnStats?.pending_count || 0) > 0 && (
                    <span className="notif-count-pill">
                      {returnStats?.pending_count}
                    </span>
                  )}
                </button>

                {showNotifMenu && (
                  <div className="admin-notif-dropdown">
                    <div className="notif-dropdown-header">
                      <div className="notif-header-title">
                        <strong>Yêu cầu Đổi / Trả Thuốc</strong>
                        <span className="notif-header-tag">
                          {returnStats?.pending_count || 0} chờ duyệt
                        </span>
                      </div>
                      <button
                        type="button"
                        className="notif-close-btn"
                        onClick={() => setShowNotifMenu(false)}
                      >
                        <X size={14} />
                      </button>
                    </div>

                    <div className="notif-dropdown-body">
                      {(returnStats?.recent_pending && returnStats.recent_pending.length > 0) ? (
                        <div className="notif-list">
                          {returnStats.recent_pending.map((item) => (
                            <NavLink
                              key={item.id}
                              to="/returns"
                              onClick={() => setShowNotifMenu(false)}
                              className="notif-item"
                            >
                              <div className="notif-item-top">
                                <span className="notif-item-code">{item.return_code}</span>
                                <span className="notif-item-type">
                                  {item.request_type === 'EXCHANGE' ? 'Đổi hàng' : 'Trả hàng'}
                                </span>
                              </div>
                              <div className="notif-item-customer">
                                {item.customer_name} - {item.customer_phone}
                              </div>
                              <div className="notif-item-reason" title={item.reason_text}>
                                {item.reason_text}
                              </div>
                            </NavLink>
                          ))}
                        </div>
                      ) : (
                        <div className="notif-empty">
                          <CheckCircle2 size={24} className="notif-empty-icon" />
                          <p>Hiện không có yêu cầu đổi/trả nào chờ duyệt</p>
                        </div>
                      )}
                    </div>

                    <div className="notif-dropdown-footer">
                      <NavLink
                        to="/returns"
                        className="notif-view-all-btn"
                        onClick={() => setShowNotifMenu(false)}
                      >
                        <span>Quản lý tất cả đơn đổi/trả</span>
                        <ChevronRight size={14} />
                      </NavLink>
                    </div>
                  </div>
                )}
              </div>
            )}

            <a
              href="http://localhost:3000"
              target="_blank"
              rel="noreferrer"
              className="storefront-link"
              title="Mở Website Khách Hàng (Storefront :3000)"
            >
              <span className="storefront-text">🌐 Web Khách Hàng (:3000)</span>
              <ExternalLink size={13} />
            </a>

            <div className="admin-profile-pill">
              <div className="avatar-tag">{user?.full_name?.charAt(0) || 'A'}</div>
              <div className="profile-texts">
                <strong>{user?.full_name}</strong>
                <span className="role-tag">{ROLE_NAMES[user?.role || ''] || user?.role}</span>
              </div>
              <button
                type="button"
                className="logout-btn"
                onClick={logout}
                title="Đăng xuất khỏi hệ thống"
              >
                <LogOut size={15} />
              </button>
            </div>
          </div>
        </header>

        {newReturnToast && (
          <div className="admin-realtime-toast" role="alert">
            <div className="toast-content">
              <span className="toast-icon">🔔</span>
              <div className="toast-text">
                <strong>Thông báo mới từ Khách Hàng:</strong>
                <p>{newReturnToast}</p>
              </div>
            </div>
            <div className="toast-actions">
              <NavLink
                to="/returns"
                className="toast-btn-action"
                onClick={() => setNewReturnToast(null)}
              >
                Xem ngay
              </NavLink>
              <button
                type="button"
                className="toast-btn-close"
                onClick={() => setNewReturnToast(null)}
              >
                <X size={14} />
              </button>
            </div>
          </div>
        )}

        <div className="content-inner">{children}</div>
      </main>

      {open && <div className="overlay" onClick={() => setOpen(false)} />}
    </div>
  )
}
