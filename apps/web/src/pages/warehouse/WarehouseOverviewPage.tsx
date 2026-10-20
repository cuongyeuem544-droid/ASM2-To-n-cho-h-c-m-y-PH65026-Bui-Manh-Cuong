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
  Calendar,
  FileSpreadsheet,
  ShieldAlert,
  Bell,
  PackageCheck,
  XCircle,
  Truck,
  RotateCcw,
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
  time_range: string
  kpi: {
    total_assigned_orders: number
    total_skus: number
    total_batches: number
    total_available_quantity: number
    total_on_hand_quantity: number
    total_reserved_quantity: number
    low_stock_count: number
    near_expiry_batches: number
    expired_batches: number
    quarantined_batches: number
    pending_receipts_count: number
    pending_fulfillment_count: number
    staff_count: number
    inbound_transfers: number
    unread_alerts_count: number
    order_status_counts: Record<string, number>
    fulfillment_counts: Record<string, number>
  }
}

export function WarehouseOverviewPage() {
  const navigate = useNavigate()
  const [data, setData] = useState<OverviewData | null>(null)
  const [loading, setLoading] = useState(true)
  const [timeRange, setTimeRange] = useState<'today' | '7days' | '30days' | 'custom'>('30days')
  const [fromDate, setFromDate] = useState('')
  const [toDate, setToDate] = useState('')

  const fetchOverview = () => {
    setLoading(true)
    const params = new URLSearchParams({ time_range: timeRange })
    if (timeRange === 'custom') {
      if (fromDate) params.set('from_date', fromDate)
      if (toDate) params.set('to_date', toDate)
    }

    api<OverviewData>(`/warehouse-portal/me?${params.toString()}`)
      .then((res) => setData(res))
      .catch((err) => console.error(err))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    fetchOverview()
  }, [timeRange, fromDate, toDate])

  if (loading && !data) {
    return (
      <div style={{ padding: '40px', textAlign: 'center', color: '#64748b', fontWeight: 600, fontSize: '15px' }}>
        Đang tải dữ liệu tổng quan chi nhánh kho…
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

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
          <button
            onClick={() => navigate('/warehouse/products')}
            style={{
              background: 'white',
              color: '#065f46',
              border: 'none',
              padding: '10px 16px',
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
            <Boxes size={16} /> Thuốc trong kho ({kpi?.total_skus ?? 0})
          </button>

          <button
            onClick={() => navigate('/warehouse/imports')}
            style={{
              background: 'rgba(255, 255, 255, 0.2)',
              color: 'white',
              border: '1px solid rgba(255, 255, 255, 0.4)',
              padding: '10px 16px',
              borderRadius: '12px',
              fontWeight: 700,
              fontSize: '13px',
              cursor: 'pointer',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            <FileSpreadsheet size={16} /> Nhập File CSV/Excel
          </button>

          <button
            onClick={() => navigate('/warehouse/alerts')}
            style={{
              background: (kpi?.unread_alerts_count ?? 0) > 0 ? '#ef4444' : 'rgba(255, 255, 255, 0.2)',
              color: 'white',
              border: 'none',
              padding: '10px 16px',
              borderRadius: '12px',
              fontWeight: 800,
              fontSize: '13px',
              cursor: 'pointer',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            <Bell size={16} /> Cảnh báo ({kpi?.unread_alerts_count ?? 0})
          </button>
        </div>
      </div>

      {/* Time Range Selector Bar */}
      <div
        style={{
          background: 'white',
          borderRadius: '14px',
          border: '1px solid #e2e8f0',
          padding: '14px 20px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '12px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Calendar size={16} color="#059669" />
          <span style={{ fontSize: '13px', fontWeight: 800, color: '#0f172a' }}>Kỳ thống kê dữ liệu:</span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
          {[
            { id: 'today', label: 'Hôm nay' },
            { id: '7days', label: '7 ngày' },
            { id: '30days', label: '30 ngày' },
            { id: 'custom', label: 'Tùy chọn' },
          ].map((t) => (
            <button
              key={t.id}
              onClick={() => setTimeRange(t.id as any)}
              style={{
                padding: '6px 14px',
                borderRadius: '8px',
                fontSize: '12.5px',
                fontWeight: 700,
                border: 'none',
                cursor: 'pointer',
                background: timeRange === t.id ? '#059669' : '#f1f5f9',
                color: timeRange === t.id ? 'white' : '#475569',
                transition: 'all 0.15s ease',
              }}
            >
              {t.label}
            </button>
          ))}

          {timeRange === 'custom' && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginLeft: '8px' }}>
              <input
                type="date"
                value={fromDate}
                onChange={(e) => setFromDate(e.target.value)}
                style={{ padding: '5px 10px', borderRadius: '6px', border: '1px solid #cbd5e1', fontSize: '12px' }}
              />
              <span style={{ fontSize: '12px', color: '#64748b' }}>đến</span>
              <input
                type="date"
                value={toDate}
                onChange={(e) => setToDate(e.target.value)}
                style={{ padding: '5px 10px', borderRadius: '6px', border: '1px solid #cbd5e1', fontSize: '12px' }}
              />
            </div>
          )}
        </div>
      </div>

      {/* 4 Primary Hero KPI Cards */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
          gap: '16px',
        }}
      >
        {/* Card 1: Tổng đơn giao cho kho */}
        <div style={{ background: 'white', borderRadius: '14px', border: '1px solid #e2e8f0', padding: '20px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
            <span style={{ fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', color: '#64748b' }}>
              Đơn hàng giao cho kho
            </span>
            <div style={{ padding: '8px', borderRadius: '10px', background: '#eff6ff', color: '#2563eb' }}>
              <ShoppingBag size={20} />
            </div>
          </div>
          <div style={{ fontSize: '26px', fontWeight: 900, color: '#0f172a' }}>
            {(kpi?.total_assigned_orders ?? 0).toLocaleString()} <span style={{ fontSize: '12px', color: '#94a3b8' }}>đơn</span>
          </div>
          <div style={{ fontSize: '11px', color: '#64748b', marginTop: '4px' }}>
            Trong kỳ được chọn ({kpi?.pending_fulfillment_count ?? 0} đang chờ xử lý)
          </div>
        </div>

        {/* Card 2: Tổng loại thuốc trong kho */}
        <div style={{ background: 'white', borderRadius: '14px', border: '1px solid #e2e8f0', padding: '20px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
            <span style={{ fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', color: '#64748b' }}>
              Loại thuốc trong kho
            </span>
            <div style={{ padding: '8px', borderRadius: '10px', background: '#ecfdf5', color: '#059669' }}>
              <Boxes size={20} />
            </div>
          </div>
          <div style={{ fontSize: '26px', fontWeight: 900, color: '#0f172a' }}>
            {(kpi?.total_skus ?? 0).toLocaleString()} <span style={{ fontSize: '12px', color: '#94a3b8' }}>loại SKU</span>
          </div>
          <div style={{ fontSize: '11px', color: '#059669', marginTop: '4px' }}>
            Phân bổ trên {(kpi?.total_batches ?? 0).toLocaleString()} lô thuốc
          </div>
        </div>

        {/* Card 3: Tồn khả dụng & Tồn thực tế */}
        <div style={{ background: 'white', borderRadius: '14px', border: '1px solid #e2e8f0', padding: '20px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
            <span style={{ fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', color: '#64748b' }}>
              Tồn kho khả dụng (Bán)
            </span>
            <div style={{ padding: '8px', borderRadius: '10px', background: '#ecfdf5', color: '#059669' }}>
              <PackageCheck size={20} />
            </div>
          </div>
          <div style={{ fontSize: '26px', fontWeight: 900, color: '#059669' }}>
            {(kpi?.total_available_quantity ?? 0).toLocaleString()} <span style={{ fontSize: '12px', color: '#94a3b8' }}>đơn vị</span>
          </div>
          <div style={{ fontSize: '11px', color: '#64748b', marginTop: '4px' }}>
            Tồn vật lý: {(kpi?.total_on_hand_quantity ?? 0).toLocaleString()} • Giữ: {(kpi?.total_reserved_quantity ?? 0).toLocaleString()}
          </div>
        </div>

        {/* Card 4: Cảnh báo cận hạn & Hết hạn */}
        <div style={{ background: 'white', borderRadius: '14px', border: '1px solid #e2e8f0', padding: '20px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
            <span style={{ fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', color: '#64748b' }}>
              Lô cận hạn & Hết hạn
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
            <span style={{ fontSize: '12px', fontWeight: 600, color: '#94a3b8' }}>lô cận</span>
          </div>
          <div style={{ fontSize: '11px', color: '#64748b', marginTop: '4px' }}>
            Đã hết hạn: {kpi?.expired_batches ?? 0} • Cách ly: {kpi?.quarantined_batches ?? 0}
          </div>
        </div>
      </div>

      {/* Secondary Operational Metrics Grid */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: '14px',
        }}
      >
        <div style={{ background: 'white', borderRadius: '12px', border: '1px solid #e2e8f0', padding: '14px 18px' }}>
          <div style={{ fontSize: '11px', fontWeight: 700, color: '#64748b' }}>THUỐC SẮP HẾT HÀNG</div>
          <div style={{ fontSize: '20px', fontWeight: 900, color: (kpi?.low_stock_count ?? 0) > 0 ? '#ea580c' : '#0f172a', marginTop: '2px' }}>
            {kpi?.low_stock_count ?? 0} <span style={{ fontSize: '11px', color: '#94a3b8' }}>loại thuốc</span>
          </div>
        </div>

        <div style={{ background: 'white', borderRadius: '12px', border: '1px solid #e2e8f0', padding: '14px 18px' }}>
          <div style={{ fontSize: '11px', fontWeight: 700, color: '#64748b' }}>TỔNG SỐ LÔ THUỐC</div>
          <div style={{ fontSize: '20px', fontWeight: 900, color: '#0f172a', marginTop: '2px' }}>
            {kpi?.total_batches ?? 0} <span style={{ fontSize: '11px', color: '#94a3b8' }}>lô thuốc</span>
          </div>
        </div>

        <div style={{ background: 'white', borderRadius: '12px', border: '1px solid #e2e8f0', padding: '14px 18px' }}>
          <div style={{ fontSize: '11px', fontWeight: 700, color: '#64748b' }}>ĐƠN CHỜ SOẠN & ĐÓNG GÓI</div>
          <div style={{ fontSize: '20px', fontWeight: 900, color: '#0f172a', marginTop: '2px' }}>
            {kpi?.pending_fulfillment_count ?? 0} <span style={{ fontSize: '11px', color: '#94a3b8' }}>đơn hàng</span>
          </div>
        </div>

        <div style={{ background: 'white', borderRadius: '12px', border: '1px solid #e2e8f0', padding: '14px 18px' }}>
          <div style={{ fontSize: '11px', fontWeight: 700, color: '#64748b' }}>NHÂN SỰ THUỘC KHO</div>
          <div style={{ fontSize: '20px', fontWeight: 900, color: '#0f172a', marginTop: '2px' }}>
            {kpi?.staff_count ?? 0} <span style={{ fontSize: '11px', color: '#94a3b8' }}>nhân viên</span>
          </div>
        </div>
      </div>

      {/* Detailed Funnel & Shortcuts */}
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
            <TrendingUp size={18} style={{ color: '#059669' }} /> Quy trình thực hiện đơn tại kho ({data.time_range})
          </h2>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {[
              { key: 'ALLOCATED', label: 'Đã phân bổ kho (Chờ soạn)', count: kpi?.fulfillment_counts?.ALLOCATED ?? 0, bg: '#3b82f6' },
              { key: 'WAITING_INTERNAL_TRANSFER', label: 'Chờ điều chuyển gom hàng', count: kpi?.fulfillment_counts?.WAITING_INTERNAL_TRANSFER ?? 0, bg: '#8b5cf6' },
              { key: 'CONSOLIDATED', label: 'Đã gom đủ hàng tại kho', count: kpi?.fulfillment_counts?.CONSOLIDATED ?? 0, bg: '#6366f1' },
              { key: 'PICKING', label: 'Đang lấy hàng tại quầy / kệ', count: kpi?.fulfillment_counts?.PICKING ?? 0, bg: '#f59e0b' },
              { key: 'PACKED', label: 'Đã đóng gói xong (Chờ vận chuyển)', count: kpi?.fulfillment_counts?.PACKED ?? 0, bg: '#0d9488' },
              { key: 'SHIPPED', label: 'Đã bàn giao cho bưu tá', count: kpi?.fulfillment_counts?.SHIPPED ?? 0, bg: '#0284c7' },
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

          {/* Customer Order State Summary */}
          <div style={{ marginTop: '20px', paddingTop: '16px', borderTop: '1px solid #e2e8f0' }}>
            <div style={{ fontSize: '12px', fontWeight: 700, color: '#64748b', marginBottom: '8px' }}>
              Trạng thái đơn chung:
            </div>
            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
              <span style={{ fontSize: '12px', padding: '4px 10px', borderRadius: '6px', background: '#f1f5f9', color: '#475569' }}>
                Chờ duyệt: <strong>{kpi?.order_status_counts?.PENDING ?? 0}</strong>
              </span>
              <span style={{ fontSize: '12px', padding: '4px 10px', borderRadius: '6px', background: '#ecfdf5', color: '#065f46' }}>
                Hoàn thành: <strong>{kpi?.order_status_counts?.COMPLETED ?? 0}</strong>
              </span>
              <span style={{ fontSize: '12px', padding: '4px 10px', borderRadius: '6px', background: '#fee2e2', color: '#991b1b' }}>
                Hủy: <strong>{kpi?.order_status_counts?.CANCELLED ?? 0}</strong>
              </span>
              <span style={{ fontSize: '12px', padding: '4px 10px', borderRadius: '6px', background: '#fff7ed', color: '#c2410c' }}>
                Đổi/Trả: <strong>{kpi?.order_status_counts?.RETURNED ?? 0}</strong>
              </span>
            </div>
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
              <CheckCircle2 size={18} style={{ color: '#059669' }} /> Lối tắt vận hành chi nhánh kho
            </h2>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
              <div
                onClick={() => navigate('/warehouse/products')}
                style={{
                  padding: '16px',
                  borderRadius: '12px',
                  border: '1px solid #e2e8f0',
                  background: '#f8fafc',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                }}
              >
                <Boxes size={22} style={{ color: '#059669', marginBottom: '8px' }} />
                <div style={{ fontSize: '13px', fontWeight: 800, color: '#0f172a' }}>Thuốc trong kho</div>
                <div style={{ fontSize: '11px', color: '#64748b', marginTop: '2px' }}>Hồ sơ 5 mục & định mức</div>
              </div>

              <div
                onClick={() => navigate('/warehouse/imports')}
                style={{
                  padding: '16px',
                  borderRadius: '12px',
                  border: '1px solid #e2e8f0',
                  background: '#f8fafc',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                }}
              >
                <FileSpreadsheet size={22} style={{ color: '#2563eb', marginBottom: '8px' }} />
                <div style={{ fontSize: '13px', fontWeight: 800, color: '#0f172a' }}>Nhập file tồn kho</div>
                <div style={{ fontSize: '11px', color: '#64748b', marginTop: '2px' }}>File CSV / Excel chuẩn 14 cột</div>
              </div>

              <div
                onClick={() => navigate('/warehouse/alerts')}
                style={{
                  padding: '16px',
                  borderRadius: '12px',
                  border: '1px solid #e2e8f0',
                  background: '#f8fafc',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                }}
              >
                <AlertTriangle size={22} style={{ color: '#dc2626', marginBottom: '8px' }} />
                <div style={{ fontSize: '13px', fontWeight: 800, color: '#0f172a' }}>Cảnh báo bất thường</div>
                <div style={{ fontSize: '11px', color: '#64748b', marginTop: '2px' }}>Cận hạn & tồn kho bất thường</div>
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
                <div style={{ fontSize: '11px', color: '#64748b', marginTop: '2px' }}>Biến động lớn chờ Admin duyệt</div>
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
            🔒 <b>Bảo vệ dữ liệu chi nhánh kho (RBAC):</b> Bạn đang quản trị chi nhánh <b>{warehouse.name}</b>. Các truy vấn chỉ trích xuất dữ liệu gắn chặt với warehouse_id của bạn, không nhận warehouse_id tự do từ client.
          </div>
        </div>
      </div>
    </div>
  )
}
