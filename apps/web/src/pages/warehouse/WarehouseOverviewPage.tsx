import { useEffect, useState } from 'react'
import {
  Boxes,
  Layers,
  ShoppingBag,
  Users,
  AlertTriangle,
  ArrowDownToLine,
  ArrowLeftRight,
  ClipboardCheck,
  TrendingUp,
  Clock,
  CheckCircle2,
} from 'lucide-react'
import { api } from '../../services/api'
import { useNavigate } from 'react-router-dom'

interface OverviewData {
  warehouse: {
    id: number
    code: string
    name: string
    address: string
    province: string
  }
  kpi: {
    total_batches: number
    total_available_quantity: number
    total_on_hand_quantity: number
    near_expiry_batches: number
    pending_fulfillment_count: number
    staff_count: number
    inbound_transfers: number
    order_status_counts: Record<string, number>
    fulfillment_counts: Record<string, number>
  }
}

export function WarehouseOverviewPage() {
  const navigate = useNavigate()
  const [data, setData] = useState<OverviewData | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api<OverviewData>('/warehouse-portal/me')
      .then((res) => setData(res))
      .catch((err) => console.error(err))
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div style={{ padding: '40px', textAlign: 'center', color: '#64748b', fontWeight: 600, fontSize: '15px' }}>
        Đang tải dữ liệu tổng quan kho…
      </div>
    )
  }

  if (!data) {
    return (
      <div style={{ padding: '40px', textAlign: 'center', color: '#e11d48', fontWeight: 700 }}>
        Không thể tải dữ liệu kho. Vui lòng kiểm tra kết nối và thử lại.
      </div>
    )
  }

  const { warehouse, kpi } = data

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', maxWidth: '1400px', margin: '0 auto' }}>
      {/* Top Banner */}
      <div
        style={{
          background: 'linear-gradient(135deg, #065f46 0%, #047857 50%, #059669 100%)',
          color: 'white',
          borderRadius: '16px',
          padding: '24px 28px',
          boxShadow: '0 4px 16px rgba(6, 95, 70, 0.25)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '16px',
        }}
      >
        <div>
          <div
            style={{
              fontSize: '11px',
              textTransform: 'uppercase',
              fontWeight: 800,
              letterSpacing: '1px',
              color: '#a7f3d0',
              marginBottom: '4px',
            }}
          >
            CHI NHÁNH KHO GSP TRỰC THUỘC • {warehouse.code}
          </div>
          <h1 style={{ margin: 0, fontSize: '24px', fontWeight: 900, letterSpacing: '-0.3px' }}>
            {warehouse.name}
          </h1>
          <p style={{ margin: '6px 0 0', fontSize: '13px', color: '#d1fae5', opacity: 0.9 }}>
            📍 {warehouse.address}, {warehouse.province}
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <button
            onClick={() => navigate('/warehouse/orders')}
            style={{
              background: 'white',
              color: '#065f46',
              border: 'none',
              padding: '10px 18px',
              borderRadius: '12px',
              fontWeight: 800,
              fontSize: '13px',
              boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
              cursor: 'pointer',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            <ShoppingBag size={16} /> Xử lý đơn ({kpi?.pending_fulfillment_count ?? 0})
          </button>

          <button
            onClick={() => navigate('/warehouse/receipts')}
            style={{
              background: 'rgba(255, 255, 255, 0.15)',
              color: 'white',
              border: '1px solid rgba(255, 255, 255, 0.3)',
              padding: '10px 18px',
              borderRadius: '12px',
              fontWeight: 700,
              fontSize: '13px',
              cursor: 'pointer',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            <ArrowDownToLine size={16} /> + Nhập kho mới
          </button>
        </div>
      </div>

      {/* KPI Cards Grid */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
          gap: '16px',
        }}
      >
        {/* Card 1: Tồn khả dụng */}
        <div
          style={{
            background: 'white',
            borderRadius: '14px',
            border: '1px solid #e2e8f0',
            padding: '20px',
            boxShadow: '0 1px 3px rgba(0,0,0,0.03)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
            <span style={{ fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', color: '#64748b' }}>
              Tồn khả dụng
            </span>
            <div style={{ padding: '8px', borderRadius: '10px', background: '#ecfdf5', color: '#059669' }}>
              <Boxes size={20} />
            </div>
          </div>
          <div style={{ fontSize: '26px', fontWeight: 900, color: '#0f172a' }}>
            {(kpi?.total_available_quantity ?? 0).toLocaleString()}{' '}
            <span style={{ fontSize: '12px', fontWeight: 600, color: '#94a3b8' }}>đơn vị</span>
          </div>
          <div style={{ fontSize: '11px', color: '#64748b', marginTop: '4px' }}>
            Tổng tồn vật lý: {(kpi?.total_on_hand_quantity ?? kpi?.total_available_quantity ?? 0).toLocaleString()}
          </div>
        </div>

        {/* Card 2: Đơn cần soạn */}
        <div
          style={{
            background: 'white',
            borderRadius: '14px',
            border: '1px solid #e2e8f0',
            padding: '20px',
            boxShadow: '0 1px 3px rgba(0,0,0,0.03)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
            <span style={{ fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', color: '#64748b' }}>
              Đơn cần soạn gấp
            </span>
            <div style={{ padding: '8px', borderRadius: '10px', background: '#fffbeb', color: '#d97706' }}>
              <Clock size={20} />
            </div>
          </div>
          <div style={{ fontSize: '26px', fontWeight: 900, color: '#d97706' }}>
            {kpi?.pending_fulfillment_count ?? 0}{' '}
            <span style={{ fontSize: '12px', fontWeight: 600, color: '#94a3b8' }}>đơn</span>
          </div>
          <div style={{ fontSize: '11px', color: '#64748b', marginTop: '4px' }}>
            Chờ soạn, gom hàng hoặc đóng gói
          </div>
        </div>

        {/* Card 3: Cận hạn */}
        <div
          style={{
            background: 'white',
            borderRadius: '14px',
            border: '1px solid #e2e8f0',
            padding: '20px',
            boxShadow: '0 1px 3px rgba(0,0,0,0.03)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
            <span style={{ fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', color: '#64748b' }}>
              Cảnh báo cận hạn
            </span>
            <div
              style={{
                padding: '8px',
                borderRadius: '10px',
                background: (kpi?.near_expiry_batches ?? 0) > 0 ? '#fef2f2' : '#f8fafc',
                color: (kpi?.near_expiry_batches ?? 0) > 0 ? '#dc2626' : '#94a3b8',
              }}
            >
              <AlertTriangle size={20} />
            </div>
          </div>
          <div
            style={{
              fontSize: '26px',
              fontWeight: 900,
              color: (kpi?.near_expiry_batches ?? 0) > 0 ? '#dc2626' : '#0f172a',
            }}
          >
            {kpi?.near_expiry_batches ?? 0}{' '}
            <span style={{ fontSize: '12px', fontWeight: 600, color: '#94a3b8' }}>lô</span>
          </div>
          <div style={{ fontSize: '11px', color: '#64748b', marginTop: '4px' }}>
            Hạn dùng &lt; 180 ngày (chặn xuất FEFO)
          </div>
        </div>

        {/* Card 4: Nhân viên */}
        <div
          style={{
            background: 'white',
            borderRadius: '14px',
            border: '1px solid #e2e8f0',
            padding: '20px',
            boxShadow: '0 1px 3px rgba(0,0,0,0.03)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
            <span style={{ fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', color: '#64748b' }}>
              Nhân viên kho
            </span>
            <div style={{ padding: '8px', borderRadius: '10px', background: '#eff6ff', color: '#2563eb' }}>
              <Users size={20} />
            </div>
          </div>
          <div style={{ fontSize: '26px', fontWeight: 900, color: '#0f172a' }}>
            {kpi?.staff_count ?? 0}{' '}
            <span style={{ fontSize: '12px', fontWeight: 600, color: '#94a3b8' }}>nhân sự</span>
          </div>
          <div style={{ fontSize: '11px', color: '#64748b', marginTop: '4px' }}>
            Thuộc quyền quản lý của bạn
          </div>
        </div>
      </div>

      {/* Breakdown Grids */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))',
          gap: '20px',
        }}
      >
        {/* Fulfillment Pipeline Breakdown */}
        <div
          style={{
            background: 'white',
            borderRadius: '16px',
            border: '1px solid #e2e8f0',
            padding: '24px',
            boxShadow: '0 1px 3px rgba(0,0,0,0.03)',
          }}
        >
          <h2
            style={{
              fontSize: '15px',
              fontWeight: 800,
              color: '#0f172a',
              margin: '0 0 16px',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
            }}
          >
            <TrendingUp size={18} style={{ color: '#059669' }} /> Tiến độ xử lý đơn hàng tại kho
          </h2>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {[
              { key: 'ALLOCATED', label: 'Đã phân bổ kho (Chờ soạn)', count: kpi?.fulfillment_counts?.ALLOCATED ?? 0, bg: '#3b82f6' },
              { key: 'WAITING_INTERNAL_TRANSFER', label: 'Chờ điều chuyển gom hàng', count: kpi?.fulfillment_counts?.WAITING_INTERNAL_TRANSFER ?? 0, bg: '#8b5cf6' },
              { key: 'CONSOLIDATED', label: 'Đã gom đủ hàng tại kho', count: kpi?.fulfillment_counts?.CONSOLIDATED ?? 0, bg: '#6366f1' },
              { key: 'PICKING', label: 'Đang soạn hàng tại quầy', count: kpi?.fulfillment_counts?.PICKING ?? 0, bg: '#f59e0b' },
              { key: 'PACKED', label: 'Đã đóng gói xong (Chờ gửi)', count: kpi?.fulfillment_counts?.PACKED ?? 0, bg: '#0d9488' },
              { key: 'SHIPPED', label: 'Đã bàn giao bưu tá vận chuyển', count: kpi?.fulfillment_counts?.SHIPPED ?? 0, bg: '#0284c7' },
              { key: 'DELIVERED', label: 'Đã giao thành công cho khách', count: kpi?.fulfillment_counts?.DELIVERED ?? 0, bg: '#10b981' },
            ].map((st) => (
              <div
                key={st.key}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '10px 14px',
                  borderRadius: '10px',
                  background: '#f8fafc',
                  border: '1px solid #f1f5f9',
                }}
              >
                <span style={{ fontSize: '13px', fontWeight: 600, color: '#334155' }}>{st.label}</span>
                <span
                  style={{
                    padding: '3px 10px',
                    borderRadius: '9999px',
                    fontSize: '11px',
                    fontWeight: 800,
                    color: 'white',
                    background: st.bg,
                  }}
                >
                  {st.count} đơn
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Quick Operational Shortcuts */}
        <div
          style={{
            background: 'white',
            borderRadius: '16px',
            border: '1px solid #e2e8f0',
            padding: '24px',
            boxShadow: '0 1px 3px rgba(0,0,0,0.03)',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'space-between',
          }}
        >
          <div>
            <h2
              style={{
                fontSize: '15px',
                fontWeight: 800,
                color: '#0f172a',
                margin: '0 0 16px',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
              }}
            >
              <CheckCircle2 size={18} style={{ color: '#059669' }} /> Lối tắt thao tác nhanh
            </h2>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
              <div
                onClick={() => navigate('/warehouse/receipts')}
                style={{
                  padding: '16px',
                  borderRadius: '12px',
                  border: '1px solid #e2e8f0',
                  background: '#f8fafc',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                }}
              >
                <ArrowDownToLine size={22} style={{ color: '#059669', marginBottom: '8px' }} />
                <div style={{ fontSize: '13px', fontWeight: 800, color: '#0f172a' }}>Nhập kho GSP</div>
                <div style={{ fontSize: '11px', color: '#64748b', marginTop: '2px' }}>Nhập thuốc theo lô & HSD</div>
              </div>

              <div
                onClick={() => navigate('/warehouse/transfers')}
                style={{
                  padding: '16px',
                  borderRadius: '12px',
                  border: '1px solid #e2e8f0',
                  background: '#f8fafc',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                }}
              >
                <ArrowLeftRight size={22} style={{ color: '#0284c7', marginBottom: '8px' }} />
                <div style={{ fontSize: '13px', fontWeight: 800, color: '#0f172a' }}>Điều chuyển kho</div>
                <div style={{ fontSize: '11px', color: '#64748b', marginTop: '2px' }}>Yêu cầu luân chuyển hàng</div>
              </div>

              <div
                onClick={() => navigate('/warehouse/inventory-check')}
                style={{
                  padding: '16px',
                  borderRadius: '12px',
                  border: '1px solid #e2e8f0',
                  background: '#f8fafc',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                }}
              >
                <ClipboardCheck size={22} style={{ color: '#d97706', marginBottom: '8px' }} />
                <div style={{ fontSize: '13px', fontWeight: 800, color: '#0f172a' }}>Kiểm kê & Điều chỉnh</div>
                <div style={{ fontSize: '11px', color: '#64748b', marginTop: '2px' }}>Cân đối tồn kho có lý do</div>
              </div>

              <div
                onClick={() => navigate('/warehouse/staff')}
                style={{
                  padding: '16px',
                  borderRadius: '12px',
                  border: '1px solid #e2e8f0',
                  background: '#f8fafc',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                }}
              >
                <Users size={22} style={{ color: '#7c3aed', marginBottom: '8px' }} />
                <div style={{ fontSize: '13px', fontWeight: 800, color: '#0f172a' }}>Tạo tài khoản NV</div>
                <div style={{ fontSize: '11px', color: '#64748b', marginTop: '2px' }}>Thêm nhân viên kho mới</div>
              </div>
            </div>
          </div>

          <div
            style={{
              marginTop: '20px',
              padding: '14px 16px',
              borderRadius: '10px',
              background: '#f1f5f9',
              border: '1px solid #e2e8f0',
              fontSize: '11.5px',
              color: '#475569',
              lineHeight: 1.5,
            }}
          >
            🔒 <b>Phân quyền GSP/GDP:</b> Bạn đang đăng nhập với vai trò Quản lý kho trực thuộc{' '}
            <b>{warehouse.name}</b>. Dữ liệu các kho khác hoàn toàn được bảo vệ và cô lập theo chính sách Anti-IDOR.
          </div>
        </div>
      </div>
    </div>
  )
}
