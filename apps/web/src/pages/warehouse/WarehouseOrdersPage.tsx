import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  ShoppingBag,
  Search,
  Filter,
  CheckCircle2,
  Clock,
  Package,
  Truck,
  Eye,
  X,
  AlertTriangle,
  Layers,
  MapPin,
  ChevronRight,
  XCircle,
} from 'lucide-react'
import { api } from '../../services/api'

interface OrderItem {
  id: number
  order_code: string
  customer_name: string
  customer_phone: string
  shipping_address: string
  total_amount: number
  payment_method: string
  payment_status: string
  order_status: string
  fulfillment_status: string
  items_count: number
  created_at: string | null
}

interface OrdersResponse {
  items: OrderItem[]
  total: number
  page: number
  page_size: number
  warehouse_code: string
}

interface PickDetailLine {
  order_item_id: number
  sku_id: number
  product_name: string
  unit: string
  quantity_required: number
  unit_price: number
  line_total: number
  suggested_batches: Array<{
    batch_id: number
    batch_number: string
    expiry_date: string
    quantity_available: number
  }>
}

interface PickDetailResponse {
  order_id: number
  order_code: string
  customer_name: string
  customer_phone: string
  shipping_address: string
  order_status?: string
  fulfillment_status: string
  lines: PickDetailLine[]
}

const STATUS_TABS = [
  { value: 'ALL', label: 'Tất cả' },
  { value: 'ALLOCATED', label: 'Chờ soạn' },
  { value: 'WAITING_PAYMENT', label: 'Chờ thanh toán' },
  { value: 'PICKING', label: 'Đang soạn' },
  { value: 'PACKED', label: 'Đã đóng gói' },
  { value: 'SHIPPED', label: 'Đang giao' },
  { value: 'DELIVERED', label: 'Hoàn tất' },
  { value: 'CANCELLED', label: 'Đã hủy' },
]

const FULFILLMENT_BADGES: Record<string, { label: string; bg: string; color: string }> = {
  WAITING_PAYMENT: { label: 'Chờ thanh toán', bg: '#fef3c7', color: '#92400e' },
  ALLOCATED: { label: 'Chờ soạn hàng', bg: '#f1f5f9', color: '#475569' },
  PICKING: { label: 'Đang soạn hàng', bg: '#fffbeb', color: '#b45309' },
  PACKED: { label: 'Đã đóng gói', bg: '#f0fdfa', color: '#0f766e' },
  SHIPPED: { label: 'Đang giao hàng', bg: '#eff6ff', color: '#1d4ed8' },
  DELIVERED: { label: 'Đã hoàn tất', bg: '#ecfdf5', color: '#047857' },
  CANCELLED: { label: 'Đã hủy đơn', bg: '#fef2f2', color: '#dc2626' },
}

export function WarehouseOrdersPage() {
  const [searchParams] = useSearchParams()
  const initialStatus = searchParams.get('status') || 'ALL'
  const [orders, setOrders] = useState<OrderItem[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [statusFilter, setStatusFilter] = useState(initialStatus)
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)

  // Pick Details Modal
  const [selectedOrder, setSelectedOrder] = useState<PickDetailResponse | null>(null)
  const [loadingDetailId, setLoadingDetailId] = useState<number | null>(null)
  const [updatingId, setUpdatingId] = useState<number | null>(null)

  const fetchOrders = () => {
    setLoading(true)
    const params = new URLSearchParams({
      page: String(page),
      page_size: '20',
    })
    if (statusFilter !== 'ALL') params.append('status', statusFilter)
    if (search.trim()) params.append('search', search.trim())

    api<OrdersResponse>(`/warehouse-portal/orders?${params.toString()}`)
      .then((res) => {
        setOrders(res.items || [])
        setTotal(res.total || 0)
      })
      .catch((err) => console.error(err))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    fetchOrders()
  }, [page, statusFilter])

  useEffect(() => {
    const qStatus = searchParams.get('status')
    if (qStatus && qStatus !== statusFilter) {
      setStatusFilter(qStatus)
    }
    const qOrderId = searchParams.get('order_id')
    if (qOrderId) {
      handleViewPickDetails(Number(qOrderId))
    }
  }, [searchParams])

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setPage(1)
    fetchOrders()
  }

  const handleUpdateStatus = async (orderId: number, newStatus: string) => {
    setUpdatingId(orderId)
    try {
      await api(`/warehouse-portal/orders/${orderId}/fulfillment`, {
        method: 'PATCH',
        body: JSON.stringify({ fulfillment_status: newStatus, status: newStatus }),
      })
      fetchOrders()
      if (selectedOrder && selectedOrder.order_id === orderId) {
        setSelectedOrder({ ...selectedOrder, fulfillment_status: newStatus })
      }
    } catch (err: any) {
      alert(err?.message || 'Không thể cập nhật trạng thái đơn')
    } finally {
      setUpdatingId(null)
    }
  }

  const handleViewPickDetails = async (orderId: number) => {
    setLoadingDetailId(orderId)
    try {
      const res = await api<PickDetailResponse>(`/warehouse-portal/orders/${orderId}/pick-details`)
      setSelectedOrder(res)
    } catch (err: any) {
      alert(err?.message || 'Không thể tải chi tiết đơn hàng')
    } finally {
      setLoadingDetailId(null)
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', maxWidth: '1400px', margin: '0 auto' }}>
      {/* Header */}
      <div
        style={{
          background: 'white',
          borderRadius: '16px',
          border: '1px solid #e2e8f0',
          padding: '20px 24px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '16px',
          boxShadow: '0 1px 3px rgba(0,0,0,0.03)',
        }}
      >
        <div>
          <div style={{ fontSize: '11px', fontWeight: 800, color: '#047857', textTransform: 'uppercase', letterSpacing: '0.8px' }}>
            QUY TRÌNH XUẤT KHO & SOẠN HÀNG FEFO
          </div>
          <h1 style={{ margin: '4px 0 0', fontSize: '22px', fontWeight: 900, color: '#0f172a' }}>
            Đơn Hàng Giao Cho Kho
          </h1>
          <p style={{ margin: '4px 0 0', fontSize: '13px', color: '#64748b' }}>
            Tiếp nhận đơn, trích xuất lô cận hạn nhất và đóng gói bàn giao vận chuyển
          </p>
        </div>

        <div
          style={{
            background: '#ecfdf5',
            border: '1px solid #a7f3d0',
            padding: '8px 16px',
            borderRadius: '12px',
            fontSize: '13px',
            fontWeight: 800,
            color: '#047857',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
          }}
        >
          <ShoppingBag size={16} />
          <span>Tổng số: {total} đơn hàng</span>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div
        style={{
          background: 'white',
          borderRadius: '16px',
          border: '1px solid #e2e8f0',
          padding: '16px 20px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '14px',
          boxShadow: '0 1px 3px rgba(0,0,0,0.03)',
        }}
      >
        <form onSubmit={handleSearchSubmit} style={{ display: 'flex', alignItems: 'center', gap: '8px', flex: '1', minWidth: '280px', maxWidth: '420px' }}>
          <div style={{ position: 'relative', width: '100%' }}>
            <input
              type="text"
              placeholder="Tìm mã đơn, tên khách, số điện thoại…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              style={{
                width: '100%',
                padding: '9px 14px 9px 36px',
                borderRadius: '10px',
                border: '1px solid #cbd5e1',
                fontSize: '13px',
                outline: 'none',
                boxSizing: 'border-box',
              }}
            />
            <Search size={16} style={{ position: 'absolute', left: '11px', top: '11px', color: '#94a3b8' }} />
          </div>
          <button
            type="submit"
            style={{
              padding: '9px 16px',
              borderRadius: '10px',
              border: 'none',
              background: '#047857',
              color: 'white',
              fontSize: '13px',
              fontWeight: 700,
              cursor: 'pointer',
              whiteSpace: 'nowrap',
            }}
          >
            Tìm
          </button>
        </form>

        {/* Status Tabs */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', overflowX: 'auto', paddingBottom: '2px' }}>
          {STATUS_TABS.map((tab) => {
            const isActive = statusFilter === tab.value
            return (
              <button
                key={tab.value}
                type="button"
                onClick={() => {
                  setStatusFilter(tab.value)
                  setPage(1)
                }}
                style={{
                  padding: '7px 14px',
                  borderRadius: '10px',
                  fontSize: '12px',
                  fontWeight: 800,
                  border: isActive ? '1px solid #0f172a' : '1px solid #e2e8f0',
                  background: isActive ? '#0f172a' : 'white',
                  color: isActive ? 'white' : '#64748b',
                  cursor: 'pointer',
                  whiteSpace: 'nowrap',
                  transition: 'all 0.15s ease',
                }}
              >
                {tab.label}
              </button>
            )
          })}
        </div>
      </div>

      {/* Orders Table */}
      <div
        style={{
          background: 'white',
          borderRadius: '16px',
          border: '1px solid #e2e8f0',
          overflow: 'hidden',
          boxShadow: '0 1px 3px rgba(0,0,0,0.03)',
        }}
      >
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '13px' }}>
            <thead>
              <tr style={{ background: '#f8fafc', borderBottom: '1px solid #e2e8f0', color: '#64748b', fontSize: '11px', fontWeight: 800, textTransform: 'uppercase' }}>
                <th style={{ padding: '14px 18px' }}>Mã Đơn Hàng</th>
                <th style={{ padding: '14px 18px' }}>Khách Hàng</th>
                <th style={{ padding: '14px 18px' }}>Tổng Tiền</th>
                <th style={{ padding: '14px 18px' }}>Trạng Thái Kho</th>
                <th style={{ padding: '14px 18px' }}>Thanh Toán</th>
                <th style={{ padding: '14px 18px' }}>Thời Gian</th>
                <th style={{ padding: '14px 18px', textAlign: 'right' }}>Thao Tác</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={7} style={{ padding: '40px', textAlign: 'center', color: '#94a3b8', fontWeight: 600 }}>
                    Đang tải danh sách đơn hàng kho…
                  </td>
                </tr>
              ) : orders.length === 0 ? (
                <tr>
                  <td colSpan={7} style={{ padding: '40px', textAlign: 'center', color: '#94a3b8', fontWeight: 600 }}>
                    Không có đơn hàng nào phù hợp với bộ lọc hiện tại.
                  </td>
                </tr>
              ) : (
                orders.map((o) => {
                  const isCancelled = o.order_status === 'CANCELLED' || o.fulfillment_status === 'CANCELLED'
                  const badge = isCancelled
                    ? FULFILLMENT_BADGES['CANCELLED']
                    : (FULFILLMENT_BADGES[o.fulfillment_status] || {
                        label: o.fulfillment_status,
                        bg: '#f1f5f9',
                        color: '#475569',
                      })
                  return (
                    <tr
                      key={o.id}
                      style={{
                        borderBottom: '1px solid #f1f5f9',
                        transition: 'background 0.15s ease',
                        background: isCancelled ? '#fffafa' : 'white',
                      }}
                      onMouseEnter={(e) => (e.currentTarget.style.background = isCancelled ? '#fff1f2' : '#f8fafc')}
                      onMouseLeave={(e) => (e.currentTarget.style.background = isCancelled ? '#fffafa' : 'white')}
                    >
                      <td style={{ padding: '14px 18px' }}>
                        <div style={{ fontFamily: 'monospace', fontWeight: 900, color: isCancelled ? '#e11d48' : '#047857', fontSize: '13.5px' }}>
                          {o.order_code}
                        </div>
                        <div style={{ fontSize: '11px', color: '#64748b', marginTop: '2px' }}>
                          {o.items_count} dòng sản phẩm
                        </div>
                      </td>

                      <td style={{ padding: '14px 18px' }}>
                        <div style={{ fontWeight: 800, color: '#0f172a' }}>{o.customer_name}</div>
                        <div style={{ fontSize: '11.5px', color: '#64748b' }}>{o.customer_phone}</div>
                      </td>

                      <td style={{ padding: '14px 18px', fontWeight: 800, color: '#0f172a' }}>
                        {(o.total_amount ?? 0).toLocaleString('vi-VN')} đ
                      </td>

                      <td style={{ padding: '14px 18px' }}>
                        <span
                          style={{
                            padding: '4px 10px',
                            borderRadius: '9999px',
                            fontSize: '11px',
                            fontWeight: 800,
                            background: badge.bg,
                            color: badge.color,
                            whiteSpace: 'nowrap',
                          }}
                        >
                          {badge.label}
                        </span>
                      </td>

                      <td style={{ padding: '14px 18px' }}>
                        <div style={{ fontSize: '12px', fontWeight: 600, color: '#334155' }}>
                          {o.payment_method}
                        </div>
                        <span
                          style={{
                            fontSize: '10.5px',
                            fontWeight: 700,
                            color: isCancelled
                              ? '#e11d48'
                              : o.payment_status === 'PAID'
                              ? '#047857'
                              : o.payment_method === 'COD'
                              ? '#d97706'
                              : '#ea580c',
                          }}
                        >
                          {isCancelled
                            ? 'Đã hủy đơn'
                            : o.payment_status === 'PAID'
                            ? 'Đã thanh toán'
                            : o.payment_method === 'COD'
                            ? 'Chờ thu tiền (COD)'
                            : 'Chờ thanh toán online'}
                        </span>
                      </td>

                      <td style={{ padding: '14px 18px', color: '#64748b', fontSize: '12px' }}>
                        {o.created_at ? new Date(o.created_at).toLocaleString('vi-VN') : '—'}
                      </td>

                      <td style={{ padding: '14px 18px', textAlign: 'right' }}>
                        <div style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
                          <button
                            type="button"
                            disabled={loadingDetailId === o.id}
                            onClick={() => handleViewPickDetails(o.id)}
                            style={{
                              padding: '6px 11px',
                              borderRadius: '8px',
                              border: '1px solid #cbd5e1',
                              background: loadingDetailId === o.id ? '#f1f5f9' : 'white',
                              color: isCancelled ? '#dc2626' : '#0284c7',
                              fontSize: '12px',
                              fontWeight: 700,
                              cursor: loadingDetailId === o.id ? 'not-allowed' : 'pointer',
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '4px',
                            }}
                          >
                            <Eye size={13} /> {loadingDetailId === o.id ? 'Đang mở…' : 'Phiếu Soạn'}
                          </button>

                          {isCancelled ? (
                            <span
                              style={{
                                padding: '5px 10px',
                                borderRadius: '8px',
                                fontSize: '11px',
                                fontWeight: 800,
                                background: '#fef2f2',
                                color: '#dc2626',
                                border: '1px solid #fecaca',
                              }}
                            >
                              Khách đã hủy
                            </span>
                          ) : (
                            <>
                              {o.fulfillment_status === 'WAITING_PAYMENT' && (
                                <span
                                  style={{
                                    padding: '5px 10px',
                                    borderRadius: '8px',
                                    fontSize: '11px',
                                    fontWeight: 700,
                                    background: '#fffbeb',
                                    color: '#b45309',
                                    border: '1px solid #fde68a',
                                  }}
                                >
                                  Chờ khách thanh toán
                                </span>
                              )}

                              {o.fulfillment_status === 'ALLOCATED' && (
                                <button
                                  type="button"
                                  disabled={updatingId === o.id}
                                  onClick={() => handleUpdateStatus(o.id, 'PICKING')}
                                  style={{
                                    padding: '6px 12px',
                                    borderRadius: '8px',
                                    border: 'none',
                                    background: '#f59e0b',
                                    color: 'white',
                                    fontSize: '12px',
                                    fontWeight: 800,
                                    cursor: 'pointer',
                                  }}
                                >
                                  Soạn hàng
                                </button>
                              )}

                              {o.fulfillment_status === 'PICKING' && (
                                <button
                                  type="button"
                                  disabled={updatingId === o.id}
                                  onClick={() => handleUpdateStatus(o.id, 'PACKED')}
                                  style={{
                                    padding: '6px 12px',
                                    borderRadius: '8px',
                                    border: 'none',
                                    background: '#0d9488',
                                    color: 'white',
                                    fontSize: '12px',
                                    fontWeight: 800,
                                    cursor: 'pointer',
                                  }}
                                >
                                  Đóng gói
                                </button>
                              )}

                              {o.fulfillment_status === 'PACKED' && (
                                <button
                                  type="button"
                                  disabled={updatingId === o.id}
                                  onClick={() => handleUpdateStatus(o.id, 'SHIPPED')}
                                  style={{
                                    padding: '6px 12px',
                                    borderRadius: '8px',
                                    border: 'none',
                                    background: '#2563eb',
                                    color: 'white',
                                    fontSize: '12px',
                                    fontWeight: 800,
                                    cursor: 'pointer',
                                  }}
                                >
                                  Bàn giao
                                </button>
                              )}

                              {o.fulfillment_status === 'SHIPPED' && (
                                <button
                                  type="button"
                                  disabled={updatingId === o.id}
                                  onClick={() => handleUpdateStatus(o.id, 'DELIVERED')}
                                  style={{
                                    padding: '6px 12px',
                                    borderRadius: '8px',
                                    border: 'none',
                                    background: '#059669',
                                    color: 'white',
                                    fontSize: '12px',
                                    fontWeight: 800,
                                    cursor: 'pointer',
                                  }}
                                >
                                  Giao thành công
                                </button>
                              )}
                            </>
                          )}

                          {o.fulfillment_status === 'DELIVERED' && !isCancelled && (
                            <span
                              style={{
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: '4px',
                                padding: '4px 8px',
                                borderRadius: '6px',
                                background: '#ecfdf5',
                                color: '#047857',
                                fontSize: '11px',
                                fontWeight: 800,
                              }}
                            >
                              <CheckCircle2 size={12} /> Đã giao khách
                            </span>
                          )}
                        </div>
                      </td>
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Picking Slip Modal */}
      {selectedOrder && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(15, 23, 42, 0.65)',
            backdropFilter: 'blur(4px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 60,
            padding: '20px',
          }}
        >
          <div
            style={{
              background: 'white',
              borderRadius: '20px',
              maxWidth: '680px',
              width: '100%',
              maxHeight: '90vh',
              overflowY: 'auto',
              padding: '24px',
              boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.25)',
              display: 'flex',
              flexDirection: 'column',
              gap: '16px',
            }}
          >
            {/* Modal Header */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid #e2e8f0', paddingBottom: '14px' }}>
              <div>
                <div style={{ fontSize: '11px', fontWeight: 800, color: (selectedOrder.fulfillment_status === 'CANCELLED' || selectedOrder.order_status === 'CANCELLED') ? '#dc2626' : '#047857', textTransform: 'uppercase' }}>
                  {(selectedOrder.fulfillment_status === 'CANCELLED' || selectedOrder.order_status === 'CANCELLED') ? 'ĐƠN HÀNG ĐÃ HỦY' : 'PHIẾU SOẠN HÀNG (PICKING SLIP)'}
                </div>
                <h3 style={{ margin: '2px 0 0', fontSize: '18px', fontWeight: 900, color: '#0f172a' }}>
                  {selectedOrder.order_code}
                </h3>
                <div style={{ fontSize: '12px', color: '#64748b', marginTop: '2px' }}>
                  Khách hàng: <b>{selectedOrder.customer_name}</b> ({selectedOrder.customer_phone})
                </div>
              </div>
              <button
                type="button"
                onClick={() => setSelectedOrder(null)}
                style={{ background: 'none', border: 'none', color: '#94a3b8', cursor: 'pointer', padding: '4px' }}
              >
                <X size={20} />
              </button>
            </div>

            {/* Cancelled Warning Banner */}
            {(selectedOrder.fulfillment_status === 'CANCELLED' || selectedOrder.order_status === 'CANCELLED') && (
              <div
                style={{
                  background: '#fef2f2',
                  borderRadius: '12px',
                  border: '1px solid #fecaca',
                  padding: '12px 16px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '10px',
                  fontSize: '12.5px',
                  color: '#dc2626',
                  fontWeight: 700,
                }}
              >
                <AlertTriangle size={18} style={{ color: '#dc2626', flexShrink: 0 }} />
                <div>
                  Đơn hàng này đã bị khách hàng hoặc hệ thống hủy. Toàn bộ thuốc giữ chỗ đã được giải phóng lại vào kho. Vui lòng dừng mọi thao tác soạn hoặc bàn giao.
                </div>
              </div>
            )}

            {/* Address Banner */}
            <div
              style={{
                background: '#f8fafc',
                borderRadius: '12px',
                border: '1px solid #e2e8f0',
                padding: '12px 16px',
                display: 'flex',
                alignItems: 'center',
                gap: '10px',
                fontSize: '12.5px',
                color: '#334155',
              }}
            >
              <MapPin size={16} style={{ color: '#059669', flexShrink: 0 }} />
              <div>
                <span style={{ fontWeight: 700, color: '#0f172a' }}>Địa chỉ giao hàng:</span> {selectedOrder.shipping_address}
              </div>
            </div>

            {/* Drug picking line items */}
            <div>
              <div style={{ fontSize: '12px', fontWeight: 800, color: '#475569', textTransform: 'uppercase', marginBottom: '8px' }}>
                Danh sách thuốc cần xuất kho (Quy tắc FEFO)
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                {selectedOrder.lines.map((line) => (
                  <div
                    key={line.order_item_id}
                    style={{
                      border: '1px solid #e2e8f0',
                      borderRadius: '12px',
                      padding: '14px',
                      background: 'white',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '8px',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <div>
                        <div style={{ fontWeight: 800, fontSize: '14px', color: '#0f172a' }}>
                          {line.product_name}
                        </div>
                        <div style={{ fontSize: '11.5px', color: '#64748b' }}>Đơn vị tính: {line.unit}</div>
                      </div>
                      <div style={{ fontSize: '15px', fontWeight: 900, color: '#047857' }}>
                        SL: {line.quantity_required}
                      </div>
                    </div>

                    {line.suggested_batches.length > 0 ? (
                      <div
                        style={{
                          background: '#ecfdf5',
                          border: '1px solid #a7f3d0',
                          borderRadius: '8px',
                          padding: '10px 12px',
                          fontSize: '12px',
                        }}
                      >
                        <div style={{ fontWeight: 800, color: '#047857', marginBottom: '4px', display: 'flex', alignItems: 'center', gap: '5px' }}>
                          <Layers size={13} /> Lô gợi ý xuất kho chuẩn FEFO:
                        </div>
                        {line.suggested_batches.map((b) => (
                          <div
                            key={b.batch_id}
                            style={{ display: 'flex', justifyContent: 'space-between', color: '#1e293b', paddingTop: '2px' }}
                          >
                            <span>
                              Mã lô: <b>{b.batch_number}</b> (HSD: {b.expiry_date})
                            </span>
                            <span style={{ fontWeight: 700, color: '#059669' }}>Khả dụng: {b.quantity_available}</span>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div
                        style={{
                          background: '#fffbeb',
                          border: '1px solid #fef3c7',
                          borderRadius: '8px',
                          padding: '8px 12px',
                          fontSize: '11.5px',
                          color: '#b45309',
                          fontWeight: 600,
                        }}
                      >
                        ⚠️ Không tìm thấy lô nào khả dụng đủ hạn dùng (&gt;= 180 ngày). Vui lòng kiểm kê!
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>

            {/* Modal Actions */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: '10px', paddingTop: '10px', borderTop: '1px solid #e2e8f0' }}>
              <button
                type="button"
                onClick={() => setSelectedOrder(null)}
                style={{
                  padding: '9px 18px',
                  borderRadius: '10px',
                  border: '1px solid #cbd5e1',
                  background: 'white',
                  color: '#64748b',
                  fontSize: '13px',
                  fontWeight: 700,
                  cursor: 'pointer',
                }}
              >
                Đóng
              </button>

              {selectedOrder.fulfillment_status === 'ALLOCATED' && (
                <button
                  type="button"
                  onClick={() => handleUpdateStatus(selectedOrder.order_id, 'PICKING')}
                  style={{
                    padding: '9px 20px',
                    borderRadius: '10px',
                    border: 'none',
                    background: '#f59e0b',
                    color: 'white',
                    fontSize: '13px',
                    fontWeight: 800,
                    cursor: 'pointer',
                  }}
                >
                  Bắt đầu soạn hàng (PICKING)
                </button>
              )}

              {selectedOrder.fulfillment_status === 'PICKING' && (
                <button
                  type="button"
                  onClick={() => handleUpdateStatus(selectedOrder.order_id, 'PACKED')}
                  style={{
                    padding: '9px 20px',
                    borderRadius: '10px',
                    border: 'none',
                    background: '#0d9488',
                    color: 'white',
                    fontSize: '13px',
                    fontWeight: 800,
                    cursor: 'pointer',
                  }}
                >
                  Xác nhận đã đóng gói (PACKED)
                </button>
              )}

              {selectedOrder.fulfillment_status === 'PACKED' && (
                <button
                  type="button"
                  onClick={() => handleUpdateStatus(selectedOrder.order_id, 'SHIPPED')}
                  style={{
                    padding: '9px 20px',
                    borderRadius: '10px',
                    border: 'none',
                    background: '#2563eb',
                    color: 'white',
                    fontSize: '13px',
                    fontWeight: 800,
                    cursor: 'pointer',
                  }}
                >
                  Bàn giao vận chuyển (SHIPPED)
                </button>
              )}

              {selectedOrder.fulfillment_status === 'SHIPPED' && (
                <button
                  type="button"
                  disabled={updatingId === selectedOrder.order_id}
                  onClick={() => handleUpdateStatus(selectedOrder.order_id, 'DELIVERED')}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '6px',
                    padding: '8px 16px',
                    borderRadius: '10px',
                    border: 'none',
                    background: '#059669',
                    color: 'white',
                    fontSize: '13px',
                    fontWeight: 800,
                    cursor: 'pointer',
                  }}
                >
                  <CheckCircle2 size={16} /> Xác nhận đã giao thành công (DELIVERED)
                </button>
              )}

              {selectedOrder.fulfillment_status === 'DELIVERED' && (
                <div
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '6px',
                    padding: '8px 16px',
                    borderRadius: '10px',
                    background: '#ecfdf5',
                    color: '#047857',
                    fontWeight: 800,
                    fontSize: '13px',
                  }}
                >
                  <CheckCircle2 size={16} /> Đơn hàng đã giao thành công
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
