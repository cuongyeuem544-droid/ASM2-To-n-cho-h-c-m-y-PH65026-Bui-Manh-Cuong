import {
  AlertCircle,
  AlertTriangle,
  Building2,
  CheckCircle2,
  ChevronRight,
  Clock,
  DollarSign,
  Eye,
  Filter,
  History,
  Layers,
  Loader2,
  Lock,
  MapPin,
  Package,
  RefreshCw,
  RotateCcw,
  Search,
  ShieldAlert,
  ShoppingBag,
  TrendingUp,
  Truck,
  Users,
  X,
  XCircle,
} from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { AdminPageHeader } from '../components/AdminPageHeader'
import { FilterBar } from '../components/FilterBar'
import { PaginationBar } from '../components/PaginationBar'
import { StatusBadge } from '../components/StatusBadge'
import { OrderStatusActions, type OrderStatusAction } from '../components/OrderStatusActions'
import { api, ApiError } from '../services/api'
import { formatDateTimeVN } from '../utils/dateUtils'

// --- Interfaces for Orders List ---
interface OrderSummary {
  id: number
  order_code: string
  customer_name: string
  customer_phone: string
  shipping_address: string
  payment_method: string
  payment_status: string
  order_status: string
  total_amount: number
  items_count: number
  created_at: string | null
}

interface OrderDetailItem {
  id: number
  product_id: number | null
  product_name: string
  product_sku: string | null
  price: number
  quantity: number
  subtotal: number
}

interface BatchAllocationInfo {
  batch_id: number
  batch_number: string
  expiry_date: string
  allocated_quantity: number
}

interface FulfillmentItemInfo {
  fulfillment_item_id: number
  order_item_id: number
  product_name: string
  quantity: number
  batches: BatchAllocationInfo[]
}

interface OrderFulfillmentInfo {
  id: number
  fulfillment_code: string
  warehouse_id: number
  warehouse_code: string
  warehouse_name: string
  status: string
  carrier_name: string | null
  tracking_code: string | null
  shipping_fee: number
  shipped_at: string | null
  delivered_at: string | null
  items: FulfillmentItemInfo[]
}

interface OrderDetailData {
  id: number
  order_code: string
  customer_name: string
  customer_phone: string
  customer_email: string | null
  shipping_address: string
  shipping_city: string | null
  payment_method: string
  payment_status: string
  order_status: string
  total_amount: number
  note: string | null
  created_at: string | null
  items: OrderDetailItem[]
  fulfillments?: OrderFulfillmentInfo[]
  status_actions?: OrderStatusAction[]
}

// --- Interfaces for Warehouse Overview & Detail ---
interface OrdersOverviewKPI {
  total_orders_today: number
  orders_processing: number
  orders_shipping: number
  orders_delivered: number
  orders_cancelled: number
  orders_returned: number
  pending_refund_amount: number
  refunded_amount: number
  overdue_orders: number
  active_warehouses: number
  distinct_orders_count: number
  total_fulfillments_count: number
}

interface WarehouseOverviewItem {
  warehouse_id: number
  warehouse_code: string
  warehouse_name: string
  province: string
  manager_name: string
  total_fulfillments: number
  orders_new: number
  orders_confirming: number
  orders_picking: number
  orders_picked: number
  orders_packing: number
  orders_ready_to_ship: number
  orders_shipping: number
  orders_delivered: number
  orders_cancelled: number
  returns_processing: number
  returns_overdue: number
  items_to_pick: number
  stockout_orders: number
  avg_processing_time_hours: number
  is_active: boolean
}

interface WarehouseDetailData {
  warehouse: {
    id: number
    code: string
    name: string
    address: string
    province: string
    phone?: string
    is_active: boolean
    total_skus: number
    total_units: number
  }
  fulfillments: Array<{
    id: number
    fulfillment_code: string
    order_id: number
    status: string
    carrier_name?: string
    tracking_code?: string
    assigned_staff?: string
    items_count: number
    created_at?: string
  }>
  returns: Array<{
    id: number
    case_code: string
    return_code?: string
    status: string
    assigned_staff?: string
    items_count: number
    created_at?: string
  }>
  refunds: Array<{
    id: number
    refund_code: string
    amount: number
    refund_method: string
    status: string
    created_at?: string
  }>
  staff_performance: Array<{
    user_id: number
    full_name: string
    phone: string
    role: string
    is_active: boolean
    orders_processed: number
    returns_inspected: number
  }>
  audit_logs: Array<{
    id: number
    action: string
    entity_type: string
    entity_id: string
    actor_name: string
    details: string
    timestamp?: string
  }>
}

const STATUS_LABELS: Record<string, { label: string; color: string; bg: string }> = {
  PENDING: { label: 'Chờ xác nhận', color: '#b45309', bg: '#fef3c7' },
  CONFIRMED: { label: 'Đã xác nhận', color: '#1d4ed8', bg: '#dbeafe' },
  PROCESSING: { label: 'Đang đóng gói', color: '#4338ca', bg: '#e0e7ff' },
  SHIPPING: { label: 'Đang giao hàng', color: '#0369a1', bg: '#e0f2fe' },
  COMPLETED: { label: 'Đã hoàn thành', color: '#15803d', bg: '#dcfce7' },
  CANCELLED: { label: 'Đã hủy', color: '#b91c1c', bg: '#fee2e2' },
}

const FULFILLMENT_STATUS_LABELS: Record<string, { label: string; color: string; bg: string }> = {
  PENDING: { label: 'Chờ lấy hàng', color: '#b45309', bg: '#fef3c7' },
  PICKED: { label: 'Đã lấy hàng', color: '#1d4ed8', bg: '#dbeafe' },
  PACKED: { label: 'Đã đóng gói', color: '#4338ca', bg: '#e0e7ff' },
  SHIPPED: { label: 'Đã xuất kho giao', color: '#0284c7', bg: '#e0f2fe' },
  DELIVERED: { label: 'Đã giao thành công', color: '#15803d', bg: '#dcfce7' },
  CANCELLED: { label: 'Đã hủy kiện', color: '#b91c1c', bg: '#fee2e2' },
}

export function OrdersPage() {
  const [searchParams] = useSearchParams()
  const [activeTab, setActiveTab] = useState<'OVERVIEW' | 'ORDERS'>('OVERVIEW')

  // --- OVERVIEW TAB STATES ---
  const [kpi, setKpi] = useState<OrdersOverviewKPI | null>(null)
  const [warehouseTable, setWarehouseTable] = useState<WarehouseOverviewItem[]>([])
  const [loadingOverview, setLoadingOverview] = useState(false)
  const [timeRange, setTimeRange] = useState<string>('today')
  const [selectedProvince, setSelectedProvince] = useState<string>('')

  // Warehouse Detail Modal
  const [selectedWarehouseId, setSelectedWarehouseId] = useState<number | null>(null)
  const [warehouseDetail, setWarehouseDetail] = useState<WarehouseDetailData | null>(null)
  const [loadingWarehouseDetail, setLoadingWarehouseDetail] = useState(false)
  const [detailSubTab, setDetailSubTab] = useState<'FULFILLMENTS' | 'RETURNS' | 'REFUNDS' | 'STAFF' | 'AUDIT'>('FULFILLMENTS')

  // --- ORDERS TAB STATES ---
  const [orders, setOrders] = useState<OrderSummary[]>([])
  const [loadingOrders, setLoadingOrders] = useState(false)
  const [selectedStatus, setSelectedStatus] = useState<string>('ALL')
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedOrder, setSelectedOrder] = useState<OrderDetailData | null>(null)
  const [loadingOrderDetail, setLoadingOrderDetail] = useState(false)
  const [updatingId, setUpdatingId] = useState<number | null>(null)
  const [updatingFulfillmentId, setUpdatingFulfillmentId] = useState<number | null>(null)
  const [notification, setNotification] = useState<{ type: 'success' | 'error'; message: string } | null>(null)
  const actionInFlight = useRef(false)

  // Orders Pagination
  const [currentPage, setCurrentPage] = useState<number>(1)
  const [pageSize, setPageSize] = useState<number>(15)

  // Load Overview Data
  const loadOverview = async () => {
    setLoadingOverview(true)
    try {
      const q = new URLSearchParams({ time_range: timeRange })
      if (selectedProvince.trim()) q.set('province', selectedProvince.trim())

      const [kpiRes, tableRes] = await Promise.all([
        api<OrdersOverviewKPI>(`/admin/orders/overview?${q.toString()}`),
        api<WarehouseOverviewItem[]>(`/admin/orders/by-warehouse?${q.toString()}`),
      ])
      setKpi(kpiRes)
      setWarehouseTable(tableRes || [])
    } catch (err: any) {
      console.error('Lỗi nạp tổng quan chi nhánh:', err)
    } finally {
      setLoadingOverview(false)
    }
  }

  // Load Warehouse Detail
  const openWarehouseDetail = async (whId: number) => {
    setSelectedWarehouseId(whId)
    setLoadingWarehouseDetail(true)
    try {
      const res = await api<WarehouseDetailData>(`/admin/orders/warehouses/${whId}`)
      setWarehouseDetail(res)
    } catch (err: any) {
      alert('Không thể tải chi tiết kho: ' + (err?.message || 'Lỗi mạng'))
    } finally {
      setLoadingWarehouseDetail(false)
    }
  }

  // Load Orders Data
  const loadOrders = async () => {
    setLoadingOrders(true)
    try {
      const q = new URLSearchParams()
      if (selectedStatus !== 'ALL') q.set('status', selectedStatus)
      if (searchQuery.trim()) q.set('search', searchQuery.trim())

      const res = await api<{ items: OrderSummary[] }>(`/admin/orders?${q.toString()}`)
      setOrders(res.items || [])
    } catch (err: any) {
      console.error('Không tải được danh sách đơn hàng:', err)
    } finally {
      setLoadingOrders(false)
    }
  }

  useEffect(() => {
    if (activeTab === 'OVERVIEW') {
      loadOverview()
    } else {
      loadOrders()
    }
  }, [activeTab, timeRange, selectedProvince, selectedStatus])

  useEffect(() => {
    const qOrderId = searchParams.get('order_id')
    if (qOrderId) {
      setActiveTab('ORDERS')
      openOrderDetail(Number(qOrderId))
    }
  }, [searchParams])

  const totalPages = Math.max(1, Math.ceil(orders.length / pageSize))
  const displayedOrders = useMemo(() => {
    const start = (currentPage - 1) * pageSize
    return orders.slice(start, start + pageSize)
  }, [orders, currentPage, pageSize])

  async function openOrderDetail(orderId: number) {
    setNotification(null)
    setLoadingOrderDetail(true)
    try {
      const res = await api<OrderDetailData>(`/admin/orders/${orderId}`)
      setSelectedOrder(res)
    } catch (err: any) {
      alert('Không tải được chi tiết đơn hàng: ' + (err?.message || 'Lỗi mạng'))
    } finally {
      setLoadingOrderDetail(false)
    }
  }

  async function handleUpdateStatus(orderId: number, newStatus: string) {
    if (actionInFlight.current) return
    actionInFlight.current = true
    setUpdatingId(orderId)
    setNotification(null)
    try {
      const result = await api<{ order_status: string; payment_status: string; message: string }>(`/admin/orders/${orderId}/status`, {
        method: 'PATCH',
        body: JSON.stringify({ order_status: newStatus }),
      })
      setSelectedOrder(current => current?.id === orderId
        ? { ...current, order_status: result.order_status, payment_status: result.payment_status, status_actions: undefined }
        : current)
      try {
        const detail = await api<OrderDetailData>(`/admin/orders/${orderId}`)
        setSelectedOrder(current => current?.id === orderId ? detail : current)
        setNotification({ type: 'success', message: result.message })
      } catch {
        setNotification({ type: 'error', message: 'Đã lưu trạng thái đơn, nhưng chưa tải lại được chi tiết. Bấm “Làm mới trạng thái” để kiểm tra; không cần gửi lại thao tác.' })
      }
      await loadOrders()
    } catch (err: any) {
      const prefix = err instanceof ApiError && [401, 403].includes(err.status)
        ? `Lỗi xác thực/quyền truy cập (${err.status}): ` : ''
      setNotification({ type: 'error', message: prefix + (err?.message || 'Không thể cập nhật trạng thái đơn hàng.') })
    } finally {
      actionInFlight.current = false
      setUpdatingId(null)
    }
  }

  async function handleUpdateFulfillmentStatus(fulfillmentId: number, newStatus: string) {
    if (actionInFlight.current) return
    actionInFlight.current = true
    setUpdatingFulfillmentId(fulfillmentId)
    setNotification(null)
    try {
      await api(`/admin/orders/fulfillments/${fulfillmentId}/status`, {
        method: 'PATCH',
        body: JSON.stringify({ status: newStatus }),
      })
      if (selectedOrder) {
        try {
          const detail = await api<OrderDetailData>(`/admin/orders/${selectedOrder.id}`)
          setSelectedOrder(current => current?.id === selectedOrder.id ? detail : current)
        } catch {
          setSelectedOrder(current => current?.id === selectedOrder.id ? { ...current, status_actions: undefined } : current)
          setNotification({ type: 'error', message: 'Đã lưu trạng thái kiện hàng, nhưng chưa tải lại được chi tiết. Bấm “Làm mới trạng thái” để kiểm tra; không cần gửi lại thao tác.' })
          return
        }
      }
      setNotification({
        type: 'success',
        message: `Đã chuyển trạng thái kiện hàng sang "${FULFILLMENT_STATUS_LABELS[newStatus]?.label || newStatus}"!`,
      })
      await loadOrders()
    } catch (err: any) {
      setNotification({
        type: 'error',
        message: err?.message || 'Không thể cập nhật trạng thái kiện hàng.',
      })
    } finally {
      actionInFlight.current = false
      setUpdatingFulfillmentId(null)
    }
  }

  async function refreshOrderActions(orderId: number) {
    if (actionInFlight.current) return
    actionInFlight.current = true
    setUpdatingId(orderId)
    setNotification(null)
    try {
      const detail = await api<OrderDetailData>(`/admin/orders/${orderId}`)
      setSelectedOrder(current => current?.id === orderId ? detail : current)
    } catch (err: any) {
      setNotification({ type: 'error', message: err?.message || 'Không tải được trạng thái mới nhất. Vui lòng thử lại.' })
    } finally {
      actionInFlight.current = false
      setUpdatingId(null)
    }
  }

  return (
    <div className="page orders-page">
      <AdminPageHeader
        title="Quản Lý Đơn Hàng & Vận Hành Đa Kho Toàn Quốc"
        eyebrow="HỒ SƠ & BÁN HÀNG • Điều Phối Kho Dược Toàn Hệ Thống"
        subtitle="Giám sát tập trung số đơn khách hàng, tiến độ xử lý fulfillment tại từng chi nhánh kho, phân tích hiệu suất SLA và điều phối đơn hàng."
        actions={
          <div style={{ display: 'flex', gap: 10 }}>
            <button
              type="button"
              onClick={activeTab === 'OVERVIEW' ? loadOverview : loadOrders}
              disabled={loadingOverview || loadingOrders}
              className="admin-button button-secondary"
            >
              <RefreshCw size={14} className={loadingOverview || loadingOrders ? 'spinner' : ''} />
              <span>Làm mới dữ liệu</span>
            </button>
          </div>
        }
      />

      {/* Main Tab Navigation */}
      <div style={{ display: 'flex', gap: 12, borderBottom: '2px solid #e2e8f0', marginBottom: 20 }}>
        <button
          type="button"
          onClick={() => setActiveTab('OVERVIEW')}
          style={{
            padding: '10px 20px',
            fontSize: 14,
            fontWeight: 700,
            background: 'none',
            border: 'none',
            borderBottom: activeTab === 'OVERVIEW' ? '3px solid #047857' : '3px solid transparent',
            color: activeTab === 'OVERVIEW' ? '#047857' : '#64748b',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: 8,
          }}
        >
          <Building2 size={16} />
          <span>Tổng quan các chi nhánh kho</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('ORDERS')}
          style={{
            padding: '10px 20px',
            fontSize: 14,
            fontWeight: 700,
            background: 'none',
            border: 'none',
            borderBottom: activeTab === 'ORDERS' ? '3px solid #047857' : '3px solid transparent',
            color: activeTab === 'ORDERS' ? '#047857' : '#64748b',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: 8,
          }}
        >
          <ShoppingBag size={16} />
          <span>Danh sách đơn hàng toàn quốc ({orders.length})</span>
        </button>
      </div>

      {notification && !selectedOrder && (
        <div
          className={`alert ${notification.type === 'success' ? 'alert-success' : 'alert-error'}`}
          style={{ marginBottom: 20 }}
        >
          {notification.type === 'success' ? <CheckCircle2 size={18} /> : <AlertCircle size={18} />}
          <div style={{ flex: 1 }}>{notification.message}</div>
          <button type="button" onClick={() => setNotification(null)} className="btn-close-icon">
            <X size={16} />
          </button>
        </div>
      )}

      {/* ======================================================== */}
      {/* TAB 1: TỔNG QUAN CÁC CHI NHÁNH KHO                       */}
      {/* ======================================================== */}
      {activeTab === 'OVERVIEW' && (
        <div>
          {/* Controls Filter: Time range & Province */}
          <div
            style={{
              background: '#fff',
              borderRadius: 12,
              padding: '14px 18px',
              boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
              marginBottom: 20,
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              flexWrap: 'wrap',
              gap: 12,
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <span style={{ fontSize: 13, fontWeight: 700, color: '#334155' }}>Khoảng thời gian:</span>
              {[
                { id: 'today', label: 'Hôm nay' },
                { id: '7d', label: '7 ngày qua' },
                { id: '30d', label: '30 ngày qua' },
                { id: 'all', label: 'Tất cả' },
              ].map((t) => (
                <button
                  key={t.id}
                  type="button"
                  onClick={() => setTimeRange(t.id)}
                  style={{
                    padding: '6px 14px',
                    borderRadius: 20,
                    fontSize: 12,
                    fontWeight: 600,
                    border: 'none',
                    cursor: 'pointer',
                    background: timeRange === t.id ? '#0f172a' : '#f1f5f9',
                    color: timeRange === t.id ? '#fff' : '#475569',
                  }}
                >
                  {t.label}
                </button>
              ))}
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <span style={{ fontSize: 13, fontWeight: 700, color: '#334155' }}>Lọc Tỉnh/Thành:</span>
              <input
                type="text"
                value={selectedProvince}
                onChange={(e) => setSelectedProvince(e.target.value)}
                placeholder="VD: Hà Nội, TP. Hồ Chí Minh..."
                style={{
                  padding: '7px 12px',
                  borderRadius: 8,
                  border: '1px solid #cbd5e1',
                  fontSize: 13,
                  outline: 'none',
                }}
              />
            </div>
          </div>

          {/* 10 KPI CARDS */}
          {kpi && (
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))',
                gap: 14,
                marginBottom: 24,
              }}
            >
              {[
                { label: 'Tổng số đơn hôm nay', val: kpi.total_orders_today, icon: ShoppingBag, color: '#0284c7', bg: '#f0f9ff' },
                { label: 'Tổng số đơn đang xử lý', val: kpi.orders_processing, icon: Clock, color: '#4338ca', bg: '#e0e7ff' },
                { label: 'Tổng số đơn đang giao', val: kpi.orders_shipping, icon: Truck, color: '#0284c7', bg: '#eff6ff' },
                { label: 'Tổng số đơn đã giao', val: kpi.orders_delivered, icon: CheckCircle2, color: '#16a34a', bg: '#f0fdf4' },
                { label: 'Tổng số đơn bị hủy', val: kpi.orders_cancelled, icon: XCircle, color: '#dc2626', bg: '#fef2f2' },
                { label: 'Tổng số đơn hoàn', val: kpi.orders_returned, icon: RotateCcw, color: '#ea580c', bg: '#fff7ed' },
                {
                  label: 'Tiền đang chờ hoàn',
                  val: `${(kpi.pending_refund_amount ?? 0).toLocaleString('vi-VN')} ₫`,
                  icon: DollarSign,
                  color: '#0e7490',
                  bg: '#cffafe',
                },
                {
                  label: 'Tiền đã hoàn',
                  val: `${(kpi.refunded_amount ?? 0).toLocaleString('vi-VN')} ₫`,
                  icon: DollarSign,
                  color: '#15803d',
                  bg: '#dcfce7',
                },
                { label: 'Số đơn quá hạn SLA', val: kpi.overdue_orders, icon: AlertTriangle, color: '#b91c1c', bg: '#fee2e2' },
                { label: 'Số kho đang hoạt động', val: kpi.active_warehouses, icon: Building2, color: '#047857', bg: '#ecfdf5' },
              ].map((item, idx) => {
                const IconComponent = item.icon
                return (
                  <div
                    key={idx}
                    style={{
                      background: '#fff',
                      borderRadius: 12,
                      padding: 16,
                      boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
                      border: '1px solid #e2e8f0',
                      display: 'flex',
                      alignItems: 'center',
                      gap: 12,
                    }}
                  >
                    <div
                      style={{
                        width: 44,
                        height: 44,
                        borderRadius: 10,
                        background: item.bg,
                        color: item.color,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        flexShrink: 0,
                      }}
                    >
                      <IconComponent size={22} />
                    </div>
                    <div>
                      <div style={{ fontSize: 11, fontWeight: 600, color: '#64748b' }}>{item.label}</div>
                      <div style={{ fontSize: 18, fontWeight: 800, color: '#0f172a', marginTop: 2 }}>{item.val}</div>
                    </div>
                  </div>
                )
              })}
            </div>
          )}

          {/* BẢNG TỔNG QUAN THEO TỪNG KHO */}
          <div
            style={{
              background: '#fff',
              borderRadius: 12,
              overflow: 'hidden',
              boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
              marginBottom: 30,
            }}
          >
            <div
              style={{
                padding: '16px 20px',
                borderBottom: '1px solid #e2e8f0',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
              }}
            >
              <h3 style={{ margin: 0, fontSize: 16, fontWeight: 700, color: '#0f172a' }}>
                Bảng Tiến Độ & Hiệu Suất Từng Chi Nhánh Kho
              </h3>
              <span style={{ fontSize: 12, color: '#64748b' }}>
                Đếm theo lượt Fulfillment thực tế tại kho • Không đếm trùng đơn khách
              </span>
            </div>

            {loadingOverview ? (
              <div style={{ padding: 48, textAlign: 'center', color: '#64748b' }}>
                <Loader2 size={24} className="spinner" style={{ margin: '0 auto 8px' }} />
                Đang tải dữ liệu vận hành từng kho...
              </div>
            ) : warehouseTable.length === 0 ? (
              <div style={{ padding: 48, textAlign: 'center', color: '#64748b' }}>
                Không có dữ liệu kho nào phù hợp bộ lọc.
              </div>
            ) : (
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12, textAlign: 'left' }}>
                  <thead>
                    <tr style={{ background: '#f8fafc', borderBottom: '1px solid #e2e8f0', color: '#475569' }}>
                      <th style={{ padding: '10px 14px' }}>Mã & Tên Kho</th>
                      <th style={{ padding: '10px 14px' }}>Tỉnh/Thành</th>
                      <th style={{ padding: '10px 14px' }}>Quản Lý Kho</th>
                      <th style={{ padding: '10px 14px', textAlign: 'center' }}>Tổng Kiện</th>
                      <th style={{ padding: '10px 14px', textAlign: 'center' }}>Mới</th>
                      <th style={{ padding: '10px 14px', textAlign: 'center' }}>Lấy Hàng</th>
                      <th style={{ padding: '10px 14px', textAlign: 'center' }}>Đóng Gói</th>
                      <th style={{ padding: '10px 14px', textAlign: 'center' }}>Đang Giao</th>
                      <th style={{ padding: '10px 14px', textAlign: 'center' }}>Đã Giao</th>
                      <th style={{ padding: '10px 14px', textAlign: 'center' }}>Hủy</th>
                      <th style={{ padding: '10px 14px', textAlign: 'center' }}>Đơn Hoàn</th>
                      <th style={{ padding: '10px 14px', textAlign: 'center' }}>Quá SLA</th>
                      <th style={{ padding: '10px 14px', textAlign: 'center' }}>TG TB (Giờ)</th>
                      <th style={{ padding: '10px 14px', textAlign: 'right' }}>Thao Tác</th>
                    </tr>
                  </thead>
                  <tbody>
                    {warehouseTable.map((wh) => (
                      <tr
                        key={wh.warehouse_id}
                        style={{ borderBottom: '1px solid #f1f5f9', transition: 'background 0.15s' }}
                        onMouseEnter={(e) => (e.currentTarget.style.background = '#f8fafc')}
                        onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                      >
                        <td style={{ padding: '10px 14px' }}>
                          <div style={{ fontWeight: 700, color: '#0f172a' }}>{wh.warehouse_name}</div>
                          <div style={{ fontSize: 11, color: '#64748b' }}>{wh.warehouse_code}</div>
                        </td>
                        <td style={{ padding: '10px 14px', color: '#334155' }}>{wh.province}</td>
                        <td style={{ padding: '10px 14px', color: '#047857', fontWeight: 600 }}>{wh.manager_name}</td>
                        <td style={{ padding: '10px 14px', textAlign: 'center', fontWeight: 700 }}>{wh.total_fulfillments}</td>
                        <td style={{ padding: '10px 14px', textAlign: 'center', color: '#b45309' }}>{wh.orders_new}</td>
                        <td style={{ padding: '10px 14px', textAlign: 'center', color: '#4338ca' }}>
                          {wh.orders_picking + wh.orders_picked}
                        </td>
                        <td style={{ padding: '10px 14px', textAlign: 'center', color: '#0f766e' }}>{wh.orders_packing}</td>
                        <td style={{ padding: '10px 14px', textAlign: 'center', color: '#0284c7' }}>{wh.orders_shipping}</td>
                        <td style={{ padding: '10px 14px', textAlign: 'center', color: '#16a34a', fontWeight: 600 }}>
                          {wh.orders_delivered}
                        </td>
                        <td style={{ padding: '10px 14px', textAlign: 'center', color: '#dc2626' }}>{wh.orders_cancelled}</td>
                        <td style={{ padding: '10px 14px', textAlign: 'center', color: '#ea580c', fontWeight: 600 }}>
                          {wh.returns_processing}
                        </td>
                        <td style={{ padding: '10px 14px', textAlign: 'center' }}>
                          {wh.returns_overdue > 0 ? (
                            <span style={{ color: '#b91c1c', fontWeight: 700 }}>⚠️ {wh.returns_overdue}</span>
                          ) : (
                            <span style={{ color: '#64748b' }}>0</span>
                          )}
                        </td>
                        <td style={{ padding: '10px 14px', textAlign: 'center', fontWeight: 600 }}>
                          {wh.avg_processing_time_hours}h
                        </td>
                        <td style={{ padding: '10px 14px', textAlign: 'right' }}>
                          <button
                            type="button"
                            onClick={() => openWarehouseDetail(wh.warehouse_id)}
                            style={{
                              padding: '5px 12px',
                              background: '#0f172a',
                              color: '#fff',
                              border: 'none',
                              borderRadius: 6,
                              fontSize: 11,
                              fontWeight: 600,
                              cursor: 'pointer',
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: 4,
                            }}
                          >
                            <Eye size={12} />
                            <span>Chi tiết kho</span>
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ======================================================== */}
      {/* TAB 2: DANH SÁCH ĐƠN HÀNG TOÀN QUỐC                     */}
      {/* ======================================================== */}
      {activeTab === 'ORDERS' && (
        <div>
          {/* Standardized FilterBar */}
          <FilterBar
            searchValue={searchQuery}
            onSearchChange={(val) => setSearchQuery(val)}
            searchPlaceholder="Tìm theo mã đơn, tên khách, SĐT..."
            totalCount={orders.length}
            unitLabel="đơn hàng"
            onRefresh={loadOrders}
            isRefreshing={loadingOrders}
          >
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {['ALL', 'PENDING', 'CONFIRMED', 'SHIPPING', 'COMPLETED', 'CANCELLED'].map((st) => (
                <button
                  key={st}
                  type="button"
                  className={`admin-button ${selectedStatus === st ? 'button-primary' : 'button-secondary'}`}
                  onClick={() => setSelectedStatus(st)}
                  style={{ fontSize: 12, padding: '5px 10px' }}
                >
                  {st === 'ALL' ? 'Tất cả trạng thái' : STATUS_LABELS[st]?.label || st}
                </button>
              ))}
            </div>
          </FilterBar>

          {/* Table List */}
          <div className="panel" style={{ padding: 0, overflow: 'hidden' }}>
            {loadingOrders ? (
              <div style={{ padding: 40, textAlign: 'center', color: '#64748b' }}>
                <Loader2 size={24} className="spinner" style={{ margin: '0 auto 8px' }} />
                Đang tải danh sách đơn hàng...
              </div>
            ) : orders.length === 0 ? (
              <div style={{ padding: 50, textAlign: 'center', color: '#64748b' }}>
                <ShoppingBag size={36} style={{ margin: '0 auto 12px', opacity: 0.4 }} />
                <h4 style={{ margin: 0, fontSize: 16, color: '#334155' }}>Chưa có đơn hàng nào</h4>
                <p style={{ margin: '4px 0 0', fontSize: 13 }}>
                  Đơn hàng khách đặt từ Web Bán Hàng sẽ hiển thị tập trung tại đây.
                </p>
              </div>
            ) : (
              <div style={{ overflowX: 'auto' }}>
                <table className="data-table" style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                  <thead>
                    <tr style={{ background: '#f8fafc', borderBottom: '1px solid #e2e8f0', textAlign: 'left' }}>
                      <th style={{ padding: '12px 16px' }}>Mã Đơn Hàng</th>
                      <th style={{ padding: '12px 16px' }}>Khách Hàng</th>
                      <th style={{ padding: '12px 16px' }}>Địa Chỉ Giao Hàng</th>
                      <th style={{ padding: '12px 16px' }}>Tổng Tiền</th>
                      <th style={{ padding: '12px 16px' }}>Thanh Toán</th>
                      <th style={{ padding: '12px 16px' }}>Trạng Thái</th>
                      <th style={{ padding: '12px 16px', textAlign: 'right' }}>Thao Tác</th>
                    </tr>
                  </thead>
                  <tbody>
                    {displayedOrders.map((o) => {
                      const st = STATUS_LABELS[o.order_status] || {
                        label: o.order_status,
                        color: '#475569',
                        bg: '#f1f5f9',
                      }
                      return (
                        <tr
                          key={o.id}
                          style={{ borderBottom: '1px solid #f1f5f9', transition: 'background 0.15s' }}
                          onMouseEnter={(e) => (e.currentTarget.style.background = '#f8fafc')}
                          onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                        >
                          <td style={{ padding: '12px 16px', fontWeight: 700, color: '#0f172a' }}>{o.order_code}</td>
                          <td style={{ padding: '12px 16px' }}>
                            <div style={{ fontWeight: 600 }}>{o.customer_name}</div>
                            <div style={{ fontSize: 11, color: '#64748b' }}>{o.customer_phone}</div>
                          </td>
                          <td style={{ padding: '12px 16px', maxWidth: 260, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                            {o.shipping_address}
                          </td>
                          <td style={{ padding: '12px 16px', fontWeight: 700, color: '#16a34a' }}>
                            {(o.total_amount ?? 0).toLocaleString('vi-VN')} đ
                          </td>
                          <td style={{ padding: '12px 16px' }}>
                            <span style={{ fontSize: 11, padding: '3px 8px', borderRadius: 4, background: '#f1f5f9' }}>
                              {o.payment_method}
                            </span>
                          </td>
                          <td style={{ padding: '12px 16px' }}>
                            <span
                              style={{
                                display: 'inline-block',
                                padding: '4px 10px',
                                borderRadius: 12,
                                fontSize: 11,
                                fontWeight: 700,
                                background: st.bg,
                                color: st.color,
                              }}
                            >
                              {st.label}
                            </span>
                          </td>
                          <td style={{ padding: '12px 16px', textAlign: 'right' }}>
                            <button
                              type="button"
                              onClick={() => openOrderDetail(o.id)}
                              style={{
                                padding: '6px 12px',
                                background: '#0f172a',
                                color: '#fff',
                                border: 'none',
                                borderRadius: 6,
                                fontSize: 12,
                                fontWeight: 600,
                                cursor: 'pointer',
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: 4,
                              }}
                            >
                              <Eye size={12} />
                              <span>Xem đơn</span>
                            </button>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            )}
            <PaginationBar
              currentPage={currentPage}
              totalPages={totalPages}
              pageSize={pageSize}
              totalItems={orders.length}
              itemName="đơn"
              onPageChange={setCurrentPage}
              onPageSizeChange={setPageSize}
            />
          </div>
        </div>
      )}

      {/* ======================================================== */}
      {/* MODAL CHI TIẾT KHO CHI NHÁNH                            */}
      {/* ======================================================== */}
      {selectedWarehouseId && warehouseDetail && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(15, 23, 42, 0.65)',
            backdropFilter: 'blur(3px)',
            zIndex: 1000,
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            padding: 20,
          }}
        >
          <div
            style={{
              background: '#fff',
              width: '100%',
              maxWidth: 960,
              maxHeight: '92vh',
              borderRadius: 16,
              overflow: 'hidden',
              display: 'flex',
              flexDirection: 'column',
              boxShadow: '0 25px 50px -12px rgba(0,0,0,0.25)',
            }}
          >
            {/* Header */}
            <div
              style={{
                padding: '16px 24px',
                background: '#0f172a',
                color: '#fff',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
              }}
            >
              <div>
                <h2 style={{ margin: 0, fontSize: 18, fontWeight: 700 }}>
                  Chi Tiết Chi Nhánh Kho: {warehouseDetail.warehouse.name} ({warehouseDetail.warehouse.code})
                </h2>
                <div style={{ fontSize: 12, color: '#94a3b8', marginTop: 4 }}>
                  Địa chỉ: {warehouseDetail.warehouse.address} • Tỉnh: {warehouseDetail.warehouse.province} • SĐT:{' '}
                  {warehouseDetail.warehouse.phone || '—'}
                </div>
              </div>
              <button
                type="button"
                onClick={() => {
                  setSelectedWarehouseId(null)
                  setWarehouseDetail(null)
                }}
                style={{ background: 'none', border: 'none', color: '#94a3b8', cursor: 'pointer' }}
              >
                <X size={20} />
              </button>
            </div>

            {/* SubTab Navigation */}
            <div
              style={{
                display: 'flex',
                background: '#f8fafc',
                borderBottom: '1px solid #e2e8f0',
                padding: '0 16px',
                gap: 8,
              }}
            >
              {[
                { id: 'FULFILLMENTS', label: `Đơn/Kiện xử lý (${warehouseDetail.fulfillments.length})`, icon: Package },
                { id: 'RETURNS', label: `Ca hoàn kho (${warehouseDetail.returns.length})`, icon: RotateCcw },
                { id: 'REFUNDS', label: `Hoàn tiền (${warehouseDetail.refunds.length})`, icon: DollarSign },
                { id: 'STAFF', label: `Nhân viên & Hiệu suất (${warehouseDetail.staff_performance.length})`, icon: Users },
                { id: 'AUDIT', label: `Nhật ký kho (${warehouseDetail.audit_logs.length})`, icon: History },
              ].map((st) => {
                const IconComp = st.icon
                return (
                  <button
                    key={st.id}
                    type="button"
                    onClick={() => setDetailSubTab(st.id as any)}
                    style={{
                      padding: '10px 14px',
                      fontSize: 12,
                      fontWeight: 600,
                      background: 'none',
                      border: 'none',
                      borderBottom: detailSubTab === st.id ? '2px solid #047857' : '2px solid transparent',
                      color: detailSubTab === st.id ? '#047857' : '#64748b',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: 6,
                    }}
                  >
                    <IconComp size={14} />
                    <span>{st.label}</span>
                  </button>
                )
              })}
            </div>

            {/* Content Area */}
            <div style={{ padding: '20px 24px', overflowY: 'auto', flex: 1 }}>
              {detailSubTab === 'FULFILLMENTS' && (
                <div>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12, textAlign: 'left' }}>
                    <thead>
                      <tr style={{ background: '#f1f5f9', color: '#475569' }}>
                        <th style={{ padding: '8px 12px' }}>Mã Kiện</th>
                        <th style={{ padding: '8px 12px' }}>Đơn Hàng ID</th>
                        <th style={{ padding: '8px 12px' }}>Trạng Thái</th>
                        <th style={{ padding: '8px 12px' }}>Nhân Viên Soạn</th>
                        <th style={{ padding: '8px 12px' }}>Vận Chuyển</th>
                        <th style={{ padding: '8px 12px' }}>Thời Gian</th>
                      </tr>
                    </thead>
                    <tbody>
                      {warehouseDetail.fulfillments.map((f) => (
                        <tr key={f.id} style={{ borderBottom: '1px solid #f1f5f9' }}>
                          <td style={{ padding: '8px 12px', fontWeight: 700 }}>{f.fulfillment_code}</td>
                          <td style={{ padding: '8px 12px' }}>#{f.order_id}</td>
                          <td style={{ padding: '8px 12px' }}>
                            <span style={{ padding: '2px 8px', borderRadius: 10, background: '#e0f2fe', color: '#0369a1', fontWeight: 600 }}>
                              {f.status}
                            </span>
                          </td>
                          <td style={{ padding: '8px 12px' }}>{f.assigned_staff || '—'}</td>
                          <td style={{ padding: '8px 12px' }}>
                            {f.carrier_name ? `${f.carrier_name} (${f.tracking_code || '—'})` : '—'}
                          </td>
                          <td style={{ padding: '8px 12px', color: '#64748b' }}>
                            {f.created_at ? formatDateTimeVN(f.created_at) : '—'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {detailSubTab === 'RETURNS' && (
                <div>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12, textAlign: 'left' }}>
                    <thead>
                      <tr style={{ background: '#f1f5f9', color: '#475569' }}>
                        <th style={{ padding: '8px 12px' }}>Mã Ca Hoàn</th>
                        <th style={{ padding: '8px 12px' }}>Yêu Cầu Gốc</th>
                        <th style={{ padding: '8px 12px' }}>Trạng Thái</th>
                        <th style={{ padding: '8px 12px' }}>NV Kiểm Hàng</th>
                        <th style={{ padding: '8px 12px' }}>Số SP</th>
                        <th style={{ padding: '8px 12px' }}>Ngày Tạo</th>
                      </tr>
                    </thead>
                    <tbody>
                      {warehouseDetail.returns.map((r) => (
                        <tr key={r.id} style={{ borderBottom: '1px solid #f1f5f9' }}>
                          <td style={{ padding: '8px 12px', fontWeight: 700 }}>{r.case_code}</td>
                          <td style={{ padding: '8px 12px' }}>{r.return_code || '—'}</td>
                          <td style={{ padding: '8px 12px' }}>
                            <span style={{ padding: '2px 8px', borderRadius: 10, background: '#fef3c7', color: '#b45309', fontWeight: 600 }}>
                              {r.status}
                            </span>
                          </td>
                          <td style={{ padding: '8px 12px' }}>{r.assigned_staff || 'Chưa gán'}</td>
                          <td style={{ padding: '8px 12px' }}>{r.items_count} sp</td>
                          <td style={{ padding: '8px 12px', color: '#64748b' }}>
                            {r.created_at ? formatDateTimeVN(r.created_at) : '—'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {detailSubTab === 'REFUNDS' && (
                <div>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12, textAlign: 'left' }}>
                    <thead>
                      <tr style={{ background: '#f1f5f9', color: '#475569' }}>
                        <th style={{ padding: '8px 12px' }}>Mã Hoàn Tiền</th>
                        <th style={{ padding: '8px 12px' }}>Số Tiền</th>
                        <th style={{ padding: '8px 12px' }}>Phương Thức</th>
                        <th style={{ padding: '8px 12px' }}>Trạng Thái</th>
                        <th style={{ padding: '8px 12px' }}>Ngày Thực Hiện</th>
                      </tr>
                    </thead>
                    <tbody>
                      {warehouseDetail.refunds.map((rf) => (
                        <tr key={rf.id} style={{ borderBottom: '1px solid #f1f5f9' }}>
                          <td style={{ padding: '8px 12px', fontWeight: 700 }}>{rf.refund_code}</td>
                          <td style={{ padding: '8px 12px', fontWeight: 700, color: '#16a34a' }}>
                            {(rf.amount ?? 0).toLocaleString('vi-VN')} ₫
                          </td>
                          <td style={{ padding: '8px 12px' }}>{rf.refund_method}</td>
                          <td style={{ padding: '8px 12px' }}>{rf.status}</td>
                          <td style={{ padding: '8px 12px', color: '#64748b' }}>
                            {rf.created_at ? formatDateTimeVN(rf.created_at) : '—'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {detailSubTab === 'STAFF' && (
                <div>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12, textAlign: 'left' }}>
                    <thead>
                      <tr style={{ background: '#f1f5f9', color: '#475569' }}>
                        <th style={{ padding: '8px 12px' }}>Họ Và Tên</th>
                        <th style={{ padding: '8px 12px' }}>Số Điện Thoại</th>
                        <th style={{ padding: '8px 12px' }}>Vai Trò</th>
                        <th style={{ padding: '8px 12px', textAlign: 'center' }}>Đơn Đã Soạn/Đóng</th>
                        <th style={{ padding: '8px 12px', textAlign: 'center' }}>Ca Hoàn Đã Kiểm</th>
                        <th style={{ padding: '8px 12px' }}>Trạng Thái</th>
                      </tr>
                    </thead>
                    <tbody>
                      {warehouseDetail.staff_performance.map((s) => (
                        <tr key={s.user_id} style={{ borderBottom: '1px solid #f1f5f9' }}>
                          <td style={{ padding: '8px 12px', fontWeight: 700 }}>{s.full_name}</td>
                          <td style={{ padding: '8px 12px' }}>{s.phone}</td>
                          <td style={{ padding: '8px 12px' }}>{s.role}</td>
                          <td style={{ padding: '8px 12px', textAlign: 'center', fontWeight: 700, color: '#047857' }}>
                            {s.orders_processed}
                          </td>
                          <td style={{ padding: '8px 12px', textAlign: 'center', fontWeight: 700, color: '#0284c7' }}>
                            {s.returns_inspected}
                          </td>
                          <td style={{ padding: '8px 12px' }}>
                            {s.is_active ? (
                              <span style={{ color: '#16a34a', fontWeight: 600 }}>Đang làm việc</span>
                            ) : (
                              <span style={{ color: '#94a3b8' }}>Nghỉ việc</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {detailSubTab === 'AUDIT' && (
                <div>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12, textAlign: 'left' }}>
                    <thead>
                      <tr style={{ background: '#f1f5f9', color: '#475569' }}>
                        <th style={{ padding: '8px 12px' }}>Thời Gian</th>
                        <th style={{ padding: '8px 12px' }}>Người Thực Hiện</th>
                        <th style={{ padding: '8px 12px' }}>Hành Động</th>
                        <th style={{ padding: '8px 12px' }}>Chi Tiết Thao Tác</th>
                      </tr>
                    </thead>
                    <tbody>
                      {warehouseDetail.audit_logs.map((a) => (
                        <tr key={a.id} style={{ borderBottom: '1px solid #f1f5f9' }}>
                          <td style={{ padding: '8px 12px', color: '#64748b' }}>
                            {a.timestamp ? formatDateTimeVN(a.timestamp) : '—'}
                          </td>
                          <td style={{ padding: '8px 12px', fontWeight: 600 }}>{a.actor_name}</td>
                          <td style={{ padding: '8px 12px', fontWeight: 700, color: '#0f172a' }}>{a.action}</td>
                          <td style={{ padding: '8px 12px', color: '#475569' }}>{a.details}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            {/* Footer */}
            <div
              style={{
                padding: '12px 24px',
                background: '#f8fafc',
                borderTop: '1px solid #e2e8f0',
                display: 'flex',
                justifyContent: 'flex-end',
              }}
            >
              <button
                type="button"
                onClick={() => {
                  setSelectedWarehouseId(null)
                  setWarehouseDetail(null)
                }}
                className="admin-button button-secondary"
              >
                Đóng
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ======================================================== */}
      {/* MODAL CHI TIẾT ĐƠN HÀNG KHÁCH (ORDER DETAIL MODAL)       */}
      {/* ======================================================== */}
      {selectedOrder && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label={`Chi tiết đơn hàng ${selectedOrder.order_code}`}
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(15, 23, 42, 0.65)',
            backdropFilter: 'blur(3px)',
            zIndex: 1000,
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            padding: 20,
          }}
        >
          <div
            style={{
              background: '#fff',
              width: '100%',
              maxWidth: 900,
              maxHeight: '92vh',
              borderRadius: 16,
              overflow: 'hidden',
              display: 'flex',
              flexDirection: 'column',
              boxShadow: '0 25px 50px -12px rgba(0,0,0,0.25)',
            }}
          >
            {/* Header */}
            <div
              style={{
                padding: '16px 24px',
                background: '#0f172a',
                color: '#fff',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
              }}
            >
              <div>
                <h2 style={{ margin: 0, fontSize: 18, fontWeight: 700 }}>
                  Chi Tiết Đơn Hàng: {selectedOrder.order_code}
                </h2>
                <div style={{ fontSize: 12, color: '#94a3b8', marginTop: 4 }}>
                  Ngày đặt: {selectedOrder.created_at ? formatDateTimeVN(selectedOrder.created_at) : '—'}
                </div>
              </div>
              <button
                type="button"
                onClick={() => setSelectedOrder(null)}
                style={{ background: 'none', border: 'none', color: '#94a3b8', cursor: 'pointer' }}
                disabled={updatingId !== null || updatingFulfillmentId !== null}
                aria-label="Đóng chi tiết đơn hàng"
              >
                <X size={20} />
              </button>
            </div>

            {/* Body */}
            <div style={{ padding: '20px 24px', overflowY: 'auto', flex: 1 }}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 20 }}>
                <div style={{ background: '#f8fafc', padding: 14, borderRadius: 8, border: '1px solid #e2e8f0' }}>
                  <div style={{ fontSize: 11, fontWeight: 700, color: '#475569', marginBottom: 6 }}>
                    THÔNG TIN KHÁCH HÀNG & GIAO HÀNG
                  </div>
                  <div><strong>Họ tên:</strong> {selectedOrder.customer_name}</div>
                  <div><strong>SĐT:</strong> {selectedOrder.customer_phone}</div>
                  <div><strong>Địa chỉ:</strong> {selectedOrder.shipping_address}</div>
                </div>

                <div style={{ background: '#f8fafc', padding: 14, borderRadius: 8, border: '1px solid #e2e8f0' }}>
                  <div style={{ fontSize: 11, fontWeight: 700, color: '#475569', marginBottom: 6 }}>
                    THANH TOÁN & TRẠNG THÁI
                  </div>
                  <div><strong>Phương thức:</strong> {selectedOrder.payment_method}</div>
                  <div><strong>Thanh toán:</strong> {selectedOrder.payment_status}</div>
                  <div>
                    <strong>Trạng thái:</strong>{' '}
                    <span style={{ fontWeight: 700, color: STATUS_LABELS[selectedOrder.order_status]?.color }}>
                      {STATUS_LABELS[selectedOrder.order_status]?.label || selectedOrder.order_status}
                    </span>
                  </div>
                </div>
              </div>

              {/* Items Table */}
              <div style={{ marginBottom: 20 }}>
                <h3 style={{ fontSize: 14, fontWeight: 700, marginBottom: 8 }}>Sản Phẩm Trong Đơn</h3>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                  <thead>
                    <tr style={{ background: '#f1f5f9', textAlign: 'left' }}>
                      <th style={{ padding: '8px 12px' }}>Tên Sản Phẩm</th>
                      <th style={{ padding: '8px 12px' }}>SKU</th>
                      <th style={{ padding: '8px 12px', textAlign: 'center' }}>SL</th>
                      <th style={{ padding: '8px 12px', textAlign: 'right' }}>Đơn Giá</th>
                      <th style={{ padding: '8px 12px', textAlign: 'right' }}>Thành Tiền</th>
                    </tr>
                  </thead>
                  <tbody>
                    {selectedOrder.items.map((it) => (
                      <tr key={it.id} style={{ borderBottom: '1px solid #f1f5f9' }}>
                        <td style={{ padding: '8px 12px', fontWeight: 600 }}>{it.product_name}</td>
                        <td style={{ padding: '8px 12px', color: '#64748b' }}>{it.product_sku || '—'}</td>
                        <td style={{ padding: '8px 12px', textAlign: 'center', fontWeight: 700 }}>{it.quantity}</td>
                        <td style={{ padding: '8px 12px', textAlign: 'right' }}>{(it.price ?? 0).toLocaleString('vi-VN')} đ</td>
                        <td style={{ padding: '8px 12px', textAlign: 'right', fontWeight: 600 }}>
                          {(it.subtotal ?? 0).toLocaleString('vi-VN')} đ
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Fulfillments Breakdown */}
              {selectedOrder.fulfillments && selectedOrder.fulfillments.length > 0 && (
                <div style={{ marginBottom: 20 }}>
                  <h3 style={{ fontSize: 14, fontWeight: 700, marginBottom: 8 }}>
                    Chi Nhánh Kho Xuất Thuốc (Fulfillments)
                  </h3>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                    {selectedOrder.fulfillments.map((ff) => (
                      <div
                        key={ff.id}
                        style={{
                          background: '#f8fafc',
                          padding: 12,
                          borderRadius: 8,
                          border: '1px solid #e2e8f0',
                        }}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                          <span style={{ fontWeight: 700, color: '#0f172a' }}>
                            Kiện: {ff.fulfillment_code} ({ff.warehouse_name})
                          </span>
                          <span
                            style={{
                              padding: '2px 8px',
                              borderRadius: 10,
                              fontSize: 11,
                              fontWeight: 700,
                              background: FULFILLMENT_STATUS_LABELS[ff.status]?.bg || '#f1f5f9',
                              color: FULFILLMENT_STATUS_LABELS[ff.status]?.color || '#475569',
                            }}
                          >
                            {FULFILLMENT_STATUS_LABELS[ff.status]?.label || ff.status}
                          </span>
                        </div>
                        <div style={{ fontSize: 12, color: '#475569', marginBottom: 8 }}>
                          Vận chuyển: {ff.carrier_name || 'Nội bộ'} • Mã vận đơn: {ff.tracking_code || '—'}
                        </div>

                        {/* Batch allocations */}
                        <div style={{ background: '#fff', padding: 8, borderRadius: 6, border: '1px solid #cbd5e1' }}>
                          <div style={{ fontSize: 11, fontWeight: 700, color: '#334155', marginBottom: 4 }}>
                            Lô thuốc FEFO chỉ định xuất kho:
                          </div>
                          {ff.items.map((fit) => (
                            <div key={fit.fulfillment_item_id} style={{ fontSize: 12, marginBottom: 4 }}>
                              <strong>{fit.product_name}</strong>: {fit.quantity} sp
                              {fit.batches.length > 0 && (
                                <span style={{ color: '#047857', marginLeft: 8 }}>
                                  [Lô: {fit.batches.map((b) => `${b.batch_number} (HSD: ${b.expiry_date}) x${b.allocated_quantity}`).join(', ')}]
                                </span>
                              )}
                            </div>
                          ))}
                        </div>

                        {/* Action buttons on fulfillment */}
                        <div style={{ display: 'flex', gap: 6, marginTop: 8, justifyContent: 'flex-end' }}>
                          {ff.status === 'PICKED' && (
                            <button
                              type="button"
                              onClick={() => handleUpdateFulfillmentStatus(ff.id, 'PACKED')}
                              disabled={updatingFulfillmentId !== null || updatingId !== null}
                              style={{ padding: '4px 10px', fontSize: 11, background: '#4338ca', color: '#fff', border: 'none', borderRadius: 4, cursor: 'pointer', fontWeight: 600 }}
                            >
                              Đã đóng gói (PACKED)
                            </button>
                          )}
                          {ff.status === 'PACKED' && (
                            <button
                              type="button"
                              onClick={() => handleUpdateFulfillmentStatus(ff.id, 'SHIPPED')}
                              disabled={updatingFulfillmentId !== null || updatingId !== null}
                              style={{ padding: '4px 10px', fontSize: 11, background: '#0284c7', color: '#fff', border: 'none', borderRadius: 4, cursor: 'pointer', fontWeight: 600 }}
                            >
                              Xuất kho giao (SHIPPED)
                            </button>
                          )}
                          {ff.status === 'SHIPPED' && (
                            <button
                              type="button"
                              onClick={() => handleUpdateFulfillmentStatus(ff.id, 'DELIVERED')}
                              disabled={updatingFulfillmentId !== null || updatingId !== null}
                              style={{ padding: '4px 10px', fontSize: 11, background: '#16a34a', color: '#fff', border: 'none', borderRadius: 4, cursor: 'pointer', fontWeight: 600 }}
                            >
                              Giao thành công (DELIVERED)
                            </button>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Total & Status buttons */}
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '14px 18px',
                  background: '#f0fdf4',
                  borderRadius: 10,
                  border: '1px solid #bbf7d0',
                  marginBottom: 16,
                }}
              >
                <span style={{ fontSize: 14, fontWeight: 700, color: '#166534' }}>Tổng tiền thanh toán đơn:</span>
                <span style={{ fontSize: 22, fontWeight: 900, color: '#15803d' }}>
                  {(selectedOrder.total_amount ?? 0).toLocaleString('vi-VN')} đ
                </span>
              </div>
            </div>

            {/* Footer */}
            <div
              style={{
                padding: '14px 24px',
                background: '#f8fafc',
                borderTop: '1px solid #e2e8f0',
                display: 'flex',
                flexDirection: 'column',
                gap: 12,
                flexShrink: 0,
                maxHeight: '40vh',
                overflowY: 'auto',
                justifyContent: 'space-between',
                alignItems: 'stretch',
              }}
            >
              <button
                type="button"
                onClick={() => setSelectedOrder(null)}
                className="admin-button button-secondary"
                style={{ alignSelf: 'flex-start' }}
                disabled={updatingId !== null || updatingFulfillmentId !== null}
              >
                Đóng
              </button>

              <OrderStatusActions
                actions={selectedOrder.status_actions}
                busy={updatingId !== null || updatingFulfillmentId !== null}
                notification={notification}
                onUpdate={status => handleUpdateStatus(selectedOrder.id, status)}
                onRefresh={() => refreshOrderActions(selectedOrder.id)}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
