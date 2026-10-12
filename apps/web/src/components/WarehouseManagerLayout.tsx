import {
  Boxes,
  Building2,
  ChevronRight,
  ClipboardCheck,
  History,
  Layers,
  LayoutDashboard,
  LogOut,
  Menu,
  MessageSquare,
  PackageCheck,
  RefreshCw,
  ShoppingBag,
  ArrowDownToLine,
  ArrowLeftRight,
  Users,
  X,
  ExternalLink,
} from 'lucide-react'
import { useState, useEffect } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { LiveClock } from './LiveClock'
import { useAuth } from '../services/auth'
import { api } from '../services/api'

interface WarehouseInfo {
  warehouse: {
    id: number
    code: string
    name: string
    address: string
    district: string
    province: string
    phone?: string
  }
  user_role: string
  kpi: {
    total_batches: number
    total_available_quantity: number
    pending_fulfillment_count: number
    staff_count: number
  }
}

const navItems = [
  { to: '/warehouse/overview', label: 'Tổng quan kho', icon: LayoutDashboard },
  { to: '/warehouse/orders', label: 'Đơn hàng kho', icon: ShoppingBag },
  { to: '/warehouse/receipts', label: 'Nhập kho (GSP)', icon: ArrowDownToLine },
  { to: '/warehouse/batches', label: 'Lô thuốc & HSD', icon: Layers },
  { to: '/warehouse/stock', label: 'Tồn kho thuốc', icon: Boxes },
  { to: '/warehouse/inventory-check', label: 'Kiểm kê kho', icon: ClipboardCheck },
  { to: '/warehouse/transfers', label: 'Điều chuyển kho', icon: ArrowLeftRight },
  { to: '/warehouse/staff', label: 'Quản lý nhân viên', icon: Users },
  { to: '/warehouse/audit', label: 'Nhật ký kho', icon: History },
  { to: '/warehouse/reviews', label: 'Đánh giá & Phản hồi', icon: MessageSquare },
]

export function WarehouseManagerLayout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const [warehouseInfo, setWarehouseInfo] = useState<WarehouseInfo | null>(null)

  useEffect(() => {
    api<WarehouseInfo>('/warehouse-portal/me')
      .then((data) => setWarehouseInfo(data))
      .catch((err) => console.error('Failed to load warehouse info:', err))
  }, [])

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <div className="app-shell" style={{ background: '#f8fafc', minHeight: '100vh', display: 'flex' }}>
      {/* Mobile Backdrop */}
      {open && (
        <div
          onClick={() => setOpen(false)}
          style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', zIndex: 40 }}
        />
      )}

      {/* Fixed Left Sidebar */}
      <aside
        className={`sidebar ${open ? 'open' : ''}`}
        style={{
          width: '258px',
          background: '#0f172a',
          color: '#e2e8f0',
          display: 'flex',
          flexDirection: 'column',
          zIndex: 50,
          borderRight: '1px solid #1e293b',
          position: 'fixed',
          top: 0,
          bottom: 0,
          left: 0,
        }}
      >
        {/* Brand Header */}
        <div style={{ padding: '20px 20px', borderBottom: '1px solid #1e293b' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <div
                style={{
                  width: '36px',
                  height: '36px',
                  borderRadius: '10px',
                  background: 'linear-gradient(135deg, #059669, #0d9488)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: 'white',
                  fontWeight: 800,
                  fontSize: '18px',
                  boxShadow: '0 2px 8px rgba(5, 150, 105, 0.4)',
                }}
              >
                📦
              </div>
              <div>
                <div style={{ fontWeight: 800, fontSize: '15px', color: '#f8fafc', letterSpacing: '0.3px' }}>
                  H4CARE KHO
                </div>
                <div style={{ fontSize: '10px', color: '#10b981', fontWeight: 700, letterSpacing: '0.5px' }}>
                  CỔNG QUẢN LÝ KHO
                </div>
              </div>
            </div>
            <button
              type="button"
              onClick={() => setOpen(false)}
              className="md:hidden"
              style={{ background: 'none', border: 'none', color: '#94a3b8', cursor: 'pointer' }}
            >
              <X size={20} />
            </button>
          </div>

          {/* Warehouse badge */}
          {warehouseInfo?.warehouse && (
            <div
              style={{
                marginTop: '12px',
                padding: '8px 12px',
                background: 'rgba(16, 185, 129, 0.1)',
                border: '1px solid rgba(16, 185, 129, 0.25)',
                borderRadius: '8px',
              }}
            >
              <div style={{ fontSize: '10px', fontWeight: 800, color: '#34d399', textTransform: 'uppercase' }}>
                {warehouseInfo.warehouse.code || 'KHO'}
              </div>
              <div
                style={{
                  fontSize: '12px',
                  color: '#e2e8f0',
                  fontWeight: 600,
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  marginTop: '1px',
                }}
              >
                {warehouseInfo.warehouse.name || 'Chi Nhánh Kho'}
              </div>
            </div>
          )}
        </div>

        {/* Navigation Menus */}
        <nav style={{ flex: 1, padding: '14px 10px', overflowY: 'auto' }}>
          <div
            style={{
              fontSize: '10px',
              fontWeight: 700,
              color: '#64748b',
              textTransform: 'uppercase',
              letterSpacing: '0.8px',
              padding: '0 10px 8px',
            }}
          >
            DANH MỤC VẬN HÀNH
          </div>
          {navItems.map((item) => {
            const Icon = item.icon
            return (
              <NavLink
                key={item.to}
                to={item.to}
                onClick={() => setOpen(false)}
                style={({ isActive }) => ({
                  display: 'flex',
                  alignItems: 'center',
                  gap: '10px',
                  padding: '9px 12px',
                  borderRadius: '10px',
                  fontSize: '13px',
                  fontWeight: isActive ? 700 : 500,
                  color: isActive ? '#ffffff' : '#94a3b8',
                  background: isActive ? 'linear-gradient(135deg, #059669, #047857)' : 'transparent',
                  boxShadow: isActive ? '0 2px 8px rgba(5, 150, 105, 0.3)' : 'none',
                  textDecoration: 'none',
                  marginBottom: '3px',
                  transition: 'all 0.15s ease',
                })}
              >
                <Icon size={17} />
                <span>{item.label}</span>
              </NavLink>
            )
          })}
        </nav>

        {/* Footer User Info */}
        <div style={{ padding: '14px 16px', borderTop: '1px solid #1e293b', background: '#0b1120' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', overflow: 'hidden' }}>
              <div
                style={{
                  width: '32px',
                  height: '32px',
                  borderRadius: '9999px',
                  background: '#047857',
                  color: 'white',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '12px',
                  fontWeight: 700,
                  flexShrink: 0,
                }}
              >
                {user?.full_name?.charAt(0) || 'Q'}
              </div>
              <div style={{ overflow: 'hidden' }}>
                <div
                  style={{
                    fontSize: '12px',
                    fontWeight: 700,
                    color: '#f8fafc',
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                  }}
                >
                  {user?.full_name}
                </div>
                <div style={{ fontSize: '10px', color: '#10b981', fontWeight: 600 }}>Quản lý chi nhánh</div>
              </div>
            </div>
            <button
              onClick={handleLogout}
              style={{
                background: 'rgba(239, 68, 68, 0.1)',
                border: '1px solid rgba(239, 68, 68, 0.2)',
                color: '#f87171',
                padding: '6px',
                borderRadius: '6px',
                cursor: 'pointer',
                flexShrink: 0,
              }}
              title="Đăng xuất"
            >
              <LogOut size={15} />
            </button>
          </div>
        </div>
      </aside>

      {/* Main Content Area - Shifted Right by Sidebar Width */}
      <div
        className="main-content"
        style={{
          marginLeft: '258px',
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          minWidth: 0,
          minHeight: '100vh',
          background: '#f8fafc',
        }}
      >
        {/* Top Navbar */}
        <header
          style={{
            height: '60px',
            background: 'white',
            borderBottom: '1px solid #e2e8f0',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '0 28px',
            zIndex: 10,
            position: 'sticky',
            top: 0,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <button
              type="button"
              onClick={() => setOpen(true)}
              className="md:hidden"
              style={{ background: 'none', border: 'none', color: '#64748b', cursor: 'pointer' }}
            >
              <Menu size={20} />
            </button>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontSize: '14px', fontWeight: 800, color: '#0f172a' }}>
                {warehouseInfo?.warehouse.name || 'Chi Nhánh Kho'}
              </span>
              <span
                style={{
                  fontSize: '10px',
                  padding: '2px 8px',
                  borderRadius: '9999px',
                  background: '#dcfce7',
                  color: '#15803d',
                  fontWeight: 700,
                }}
              >
                GSP Active
              </span>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            <LiveClock />
            <a
              href="http://localhost:3000"
              target="_blank"
              rel="noreferrer"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '5px',
                fontSize: '12px',
                fontWeight: 700,
                color: '#0284c7',
                textDecoration: 'none',
                padding: '6px 12px',
                borderRadius: '8px',
                background: '#f0f9ff',
                border: '1px solid #bae6fd',
              }}
            >
              Storefront <ExternalLink size={12} />
            </a>
          </div>
        </header>

        {/* Page Content Body */}
        <main style={{ flex: 1, padding: '24px 28px', overflowY: 'auto' }}>
          <Outlet />
        </main>
      </div>
    </div>
  )
}
