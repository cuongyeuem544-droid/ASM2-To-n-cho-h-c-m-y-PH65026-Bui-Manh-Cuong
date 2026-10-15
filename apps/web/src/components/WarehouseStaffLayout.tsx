import {
  ArrowDownToLine,
  ArrowLeftRight,
  Boxes,
  CheckSquare,
  ClipboardList,
  History,
  LogOut,
  PackageCheck,
  Search,
  ExternalLink,
  Barcode,
  RotateCcw,
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
  }
}

const staffNavItems = [
  { to: '/staff/today', label: '1. Việc hôm nay', icon: CheckSquare },
  { to: '/staff/picking-packing', label: '2. Soạn & Đóng gói', icon: PackageCheck },
  { to: '/staff/receipts', label: '3. Nhập kho được giao', icon: ArrowDownToLine },
  { to: '/staff/inventory-checks', label: '4. Kiểm kê được giao', icon: ClipboardList },
  { to: '/staff/transfers', label: '5. Điều chuyển nhận', icon: ArrowLeftRight },
  { to: '/staff/stock', label: '6. Tra cứu tồn kho (Xem)', icon: Boxes },
  { to: '/staff/history', label: '7. Lịch sử của tôi', icon: History },
  { to: '/staff/returns', label: '8. Hàng đổi trả (Kiểm hàng)', icon: RotateCcw },
]

export function WarehouseStaffLayout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [warehouseInfo, setWarehouseInfo] = useState<WarehouseInfo | null>(null)
  const [barcodeInput, setBarcodeInput] = useState('')

  useEffect(() => {
    api<WarehouseInfo>('/warehouse-portal/me')
      .then((data) => setWarehouseInfo(data))
      .catch((err) => console.error('Failed to load warehouse info:', err))
  }, [])

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  const handleBarcodeSearch = (e: React.FormEvent) => {
    e.preventDefault()
    if (!barcodeInput.trim()) return
    // Điều hướng nhanh đến trang tìm kiếm hoặc soạn đơn
    navigate(`/staff/picking-packing?search=${encodeURIComponent(barcodeInput.trim())}`)
  }

  return (
    <div style={{ background: '#f1f5f9', minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      {/* High-visibility Top Action Header */}
      <header
        style={{
          background: '#047857',
          color: 'white',
          padding: '12px 20px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '12px',
          boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
        }}
      >
        {/* Left: Brand & Warehouse Station */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
          <div
            style={{
              padding: '6px 12px',
              background: 'white',
              color: '#047857',
              borderRadius: '8px',
              fontWeight: 900,
              fontSize: '16px',
              letterSpacing: '1px',
            }}
          >
            H4CARE
          </div>
          <div>
            <div style={{ fontSize: '13px', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
              BÀN SOẠN HÀNG & ĐÓNG GÓI
            </div>
            <div style={{ fontSize: '11px', opacity: 0.9 }}>
              {warehouseInfo?.warehouse.name} ({warehouseInfo?.warehouse.code})
            </div>
          </div>
        </div>

        {/* Center: Barcode / Quick Search */}
        <form
          onSubmit={handleBarcodeSearch}
          style={{
            flex: '1',
            maxWidth: '480px',
            display: 'flex',
            alignItems: 'center',
            background: 'white',
            borderRadius: '9999px',
            padding: '4px 12px',
            boxShadow: 'inset 0 1px 3px rgba(0,0,0,0.1)',
          }}
        >
          <Barcode size={20} color="#059669" style={{ marginRight: '8px' }} />
          <input
            type="text"
            placeholder="Quét Barcode hoặc Nhập mã đơn / mã thuốc / mã lô..."
            value={barcodeInput}
            onChange={(e) => setBarcodeInput(e.target.value)}
            style={{
              border: 'none',
              outline: 'none',
              width: '100%',
              fontSize: '13px',
              fontWeight: 600,
              color: '#0f172a',
            }}
          />
          <button
            type="submit"
            style={{
              background: '#047857',
              color: 'white',
              border: 'none',
              borderRadius: '9999px',
              padding: '6px 14px',
              fontSize: '12px',
              fontWeight: 700,
              cursor: 'pointer',
            }}
          >
            Tìm
          </button>
        </form>

        {/* Right: User Station & Logout */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: '12px', fontWeight: 800 }}>{user?.full_name}</div>
            <div style={{ fontSize: '10px', opacity: 0.85 }}>Nhân viên đóng gói</div>
          </div>
          <button
            onClick={handleLogout}
            style={{
              background: 'rgba(255,255,255,0.2)',
              border: 'none',
              color: 'white',
              padding: '8px 12px',
              borderRadius: '8px',
              cursor: 'pointer',
              fontWeight: 700,
              fontSize: '12px',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            <LogOut size={14} /> Thoát
          </button>
        </div>
      </header>

      {/* Large Touch-friendly Navigation Bar */}
      <nav
        style={{
          background: 'white',
          borderBottom: '2px solid #e2e8f0',
          padding: '8px 16px',
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          overflowX: 'auto',
        }}
      >
        {staffNavItems.map((item) => {
          const Icon = item.icon
          return (
            <NavLink
              key={item.to}
              to={item.to}
              style={({ isActive }) => ({
                display: 'inline-flex',
                alignItems: 'center',
                gap: '8px',
                padding: '10px 18px',
                borderRadius: '12px',
                fontSize: '13px',
                fontWeight: 750,
                whiteSpace: 'nowrap',
                textDecoration: 'none',
                color: isActive ? 'white' : '#334155',
                background: isActive ? '#047857' : '#f1f5f9',
                boxShadow: isActive ? '0 2px 8px rgba(4, 120, 87, 0.3)' : 'none',
                transition: 'all 0.15s ease',
              })}
            >
              <Icon size={17} />
              <span>{item.label}</span>
            </NavLink>
          )
        })}
      </nav>

      {/* Main Touch Workspace */}
      <main style={{ flex: 1, padding: '20px', overflowY: 'auto' }}>
        <Outlet />
      </main>
    </div>
  )
}
