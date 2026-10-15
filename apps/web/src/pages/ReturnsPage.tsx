import {
  AlertCircle,
  AlertTriangle,
  ArrowRight,
  Ban,
  Boxes,
  Building2,
  CheckCircle2,
  Clock,
  DollarSign,
  Eye,
  FileCheck,
  FileText,
  Filter,
  Image as ImageIcon,
  Loader2,
  Lock,
  Package,
  RefreshCw,
  RotateCcw,
  Search,
  ShieldAlert,
  ShieldCheck,
  Truck,
  Users,
  X,
  XCircle,
} from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { AdminPageHeader } from '../components/AdminPageHeader'
import { FilterBar } from '../components/FilterBar'
import { PaginationBar } from '../components/PaginationBar'
import { api } from '../services/api'
import { formatDateTimeVN } from '../utils/dateUtils'

// --- Interfaces ---
interface ReturnSummary {
  id: number
  return_code: string
  order_code: string
  request_type: string
  status: string
  reason_text: string
  customer_name: string
  customer_phone: string
  items_count: number
  carrier_name?: string
  tracking_code?: string
  requested_at: string | null
}

interface ReturnDetailItem {
  id: number
  order_item_id: number
  product_name: string
  requested_quantity: number
  accepted_quantity: number
  rejected_quantity: number
  unit_price: number
  subtotal: number
  condition_reported: string
  inspected_condition: string
  restock_destination: string
  customer_reason?: string
}

interface ReturnTimelineItem {
  id: number
  from_status?: string
  to_status: string
  actor_name: string
  actor_role: string
  note?: string
  created_at: string
}

interface ReturnEvidenceItem {
  id: number
  file_url: string
  file_name: string
  evidence_type: string
}

interface ChildWarehouseCase {
  id: number
  case_code: string
  warehouse_id: number
  warehouse_code?: string
  warehouse_name?: string
  status: string
  assigned_staff_name?: string
  inspected_at?: string
  approved_at?: string
  items_count: number
}

interface ReturnDetailData {
  id: number
  return_code: string
  order_code: string
  order_id: number
  request_type: string
  status: string
  reason_code: string
  reason_text: string
  customer_name: string
  customer_phone: string
  customer_note?: string
  customer_visible_note?: string
  admin_internal_note?: string
  carrier_name?: string
  tracking_code?: string
  rejection_reason?: string
  requested_at?: string
  approved_at?: string
  received_at?: string
  inspected_at?: string
  items: ReturnDetailItem[]
  timeline: ReturnTimelineItem[]
  evidences: ReturnEvidenceItem[]
  warehouse_cases?: ChildWarehouseCase[]
}

interface ReturnsOverviewKPI {
  total_returns: number
  waiting_warehouse_receive: number
  in_transit: number
  inspecting: number
  waiting_manager_approval: number
  approved: number
  rejected: number
  refund_pending: number
  refund_processing: number
  refund_succeeded: number
  refund_failed: number
  overdue: number
  total_refunded_amount: number
  total_pending_refund_amount: number
}

interface WarehouseReturnStatItem {
  warehouse_id: number
  warehouse_code: string
  warehouse_name: string
  manager_name: string
  total_cases: number
  inspecting: number
  waiting_approval: number
  approved: number
  rejected: number
  completed: number
  failed: number
  overdue_sla: number
  total_refunded_amount: number
  avg_processing_time_hours: number
}

interface SimpleWarehouse {
  id: number
  code: string
  name: string
}

const STATUS_CONFIG: Record<string, { label: string; color: string; bg: string }> = {
  REQUESTED: { label: 'Chờ duyệt', color: '#b45309', bg: '#fef3c7' },
  ASSIGNED_TO_WAREHOUSE: { label: 'Chờ nhận tại kho', color: '#0369a1', bg: '#e0f2fe' },
  WAITING_CUSTOMER_SHIPMENT: { label: 'Chờ khách gửi', color: '#c2410c', bg: '#ffedd5' },
  IN_TRANSIT: { label: 'Đang chuyển về kho', color: '#0284c7', bg: '#e0f2fe' },
  RECEIVED: { label: 'Đã nhận tại kho', color: '#1d4ed8', bg: '#dbeafe' },
  INSPECTING: { label: 'Đang kiểm hàng', color: '#7c3aed', bg: '#f3e8ff' },
  WAITING_MANAGER_APPROVAL: { label: 'Chờ QL duyệt', color: '#ea580c', bg: '#fff7ed' },
  APPROVED: { label: 'Đã phê duyệt', color: '#15803d', bg: '#dcfce7' },
  REFUND_PENDING: { label: 'Chờ hoàn tiền', color: '#0e7490', bg: '#cffafe' },
  REFUND_PROCESSING: { label: 'Đang hoàn tiền', color: '#6d28d9', bg: '#ede9fe' },
  REFUNDED: { label: 'Đã hoàn tiền', color: '#166534', bg: '#bbf7d0' },
  RESTOCKED: { label: 'Đã nhập lại kho', color: '#16a34a', bg: '#dcfce7' },
  QUARANTINED: { label: 'Đã cách ly', color: '#a16207', bg: '#fef9c3' },
  DISPOSED: { label: 'Đã hủy thuốc', color: '#64748b', bg: '#f1f5f9' },
  COMPLETED: { label: 'Hoàn tất', color: '#15803d', bg: '#dcfce7' },
  REJECTED: { label: 'Từ chối', color: '#b91c1c', bg: '#fee2e2' },
  CANCELLED: { label: 'Đã hủy', color: '#475569', bg: '#f1f5f9' },
}

export function ReturnsPage() {
  const [activeTab, setActiveTab] = useState<'OVERVIEW' | 'REQUESTS'>('OVERVIEW')

  // Overview states
  const [kpi, setKpi] = useState<ReturnsOverviewKPI | null>(null)
  const [whStats, setWhStats] = useState<WarehouseReturnStatItem[]>([])
  const [loadingOverview, setLoadingOverview] = useState(false)

  // Requests list states
  const [returns, setReturns] = useState<ReturnSummary[]>([])
  const [totalCount, setTotalCount] = useState<number>(0)
  const [loading, setLoading] = useState<boolean>(true)
  const [search, setSearch] = useState<string>('')
  const [statusFilter, setStatusFilter] = useState<string>('')
  const [typeFilter, setTypeFilter] = useState<string>('')
  const [currentPage, setCurrentPage] = useState<number>(1)
  const [pageSize, setPageSize] = useState<number>(15)

  // Detail Modal states
  const [selectedReturnCode, setSelectedReturnCode] = useState<string | null>(null)
  const [returnDetail, setReturnDetail] = useState<ReturnDetailData | null>(null)
  const [loadingDetail, setLoadingDetail] = useState<boolean>(false)
  const [actionLoading, setActionLoading] = useState<boolean>(false)
  const [actionError, setActionError] = useState<string>('')
  const [actionSuccess, setActionSuccess] = useState<string>('')

  // Warehouses list for reassignment
  const [warehouses, setWarehouses] = useState<SimpleWarehouse[]>([])

  // Reassign Modal
  const [showReassignModal, setShowReassignModal] = useState(false)
  const [reassignWhId, setReassignWhId] = useState<number | ''>('')
  const [reassignReason, setReassignReason] = useState('')

  // Admin Override Modal
  const [showOverrideModal, setShowOverrideModal] = useState(false)
  const [overrideStatus, setOverrideStatus] = useState('APPROVED')
  const [overrideReason, setOverrideReason] = useState('')
  const [overrideNotes, setOverrideNotes] = useState('')

  const loadOverview = async () => {
    setLoadingOverview(true)
    try {
      const [kpiRes, statsRes] = await Promise.all([
        api<ReturnsOverviewKPI>('/admin/returns/overview'),
        api<WarehouseReturnStatItem[]>('/admin/returns/by-warehouse'),
      ])
      setKpi(kpiRes)
      setWhStats(statsRes || [])
    } catch (err: any) {
      console.error('Lỗi nạp KPI đổi trả toàn hệ thống:', err)
    } finally {
      setLoadingOverview(false)
    }
  }

  const loadWarehouses = async () => {
    try {
      const res = await api<SimpleWarehouse[]>('/warehouses')
      setWarehouses(res || [])
    } catch {
      // Ignore
    }
  }

  const loadReturns = async (page = currentPage, size = pageSize) => {
    setLoading(true)
    try {
      const params = new URLSearchParams()
      if (statusFilter) params.append('status', statusFilter)
      if (typeFilter) params.append('request_type', typeFilter)
      if (search.trim()) params.append('search', search.trim())
      params.append('page', String(page))
      params.append('page_size', String(size))

      const res = await api<{ total: number; items?: ReturnSummary[]; returns?: ReturnSummary[] }>(
        `/admin/returns?${params.toString()}`
      )
      const dataList = res.items || res.returns || []
      setReturns(dataList)
      setTotalCount(res.total ?? dataList.length)
    } catch (err) {
      console.error('Failed to load admin returns', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (activeTab === 'OVERVIEW') {
      loadOverview()
    } else {
      loadReturns(1, pageSize)
    }
    loadWarehouses()
  }, [activeTab, statusFilter, typeFilter])

  const totalPages = Math.max(1, Math.ceil(totalCount / pageSize))

  const openDetail = async (code: string) => {
    setSelectedReturnCode(code)
    setLoadingDetail(true)
    setActionError('')
    setActionSuccess('')
    try {
      const detail = await api<ReturnDetailData>(`/admin/returns/${code}`)
      setReturnDetail(detail)
    } catch (err: any) {
      setActionError(err.message || 'Không thể tải chi tiết yêu cầu')
    } finally {
      setLoadingDetail(false)
    }
  }

  // Handle Admin Reassign Warehouse
  const handleReassignWarehouse = async () => {
    if (!selectedReturnCode || !reassignWhId || !reassignReason.trim()) return
    setActionLoading(true)
    setActionError('')
    try {
      await api(`/admin/returns/${selectedReturnCode}/reassign`, {
        method: 'POST',
        body: JSON.stringify({
          new_warehouse_id: Number(reassignWhId),
          reason: reassignReason.trim(),
        }),
      })
      setActionSuccess('Đã điều chuyển ca hoàn sang kho mới thành công!')
      setShowReassignModal(false)
      setReassignReason('')
      await openDetail(selectedReturnCode)
      await loadReturns()
    } catch (err: any) {
      setActionError(err?.message || 'Lỗi khi điều chuyển kho.')
    } finally {
      setActionLoading(false)
    }
  }

  // Handle Admin Override
  const handleAdminOverride = async () => {
    if (!selectedReturnCode || !overrideReason.trim()) return
    setActionLoading(true)
    setActionError('')
    try {
      await api(`/admin/returns/${selectedReturnCode}/override`, {
        method: 'POST',
        body: JSON.stringify({
          new_status: overrideStatus,
          override_reason: overrideReason.trim(),
          notes: overrideNotes.trim() || undefined,
        }),
      })
      setActionSuccess('Đã thực hiện can thiệp khẩn cấp (Admin Override) thành công!')
      setShowOverrideModal(false)
      setOverrideReason('')
      await openDetail(selectedReturnCode)
      await loadReturns()
    } catch (err: any) {
      setActionError(err?.message || 'Lỗi khi can thiệp Admin Override.')
    } finally {
      setActionLoading(false)
    }
  }

  return (
    <div className="admin-page-container" style={{ padding: '24px 32px' }}>
      <AdminPageHeader
        title="Quản Lý Đổi Trả & Hoàn Tiền Toàn Hệ Thống"
        subtitle="Giám sát ca đổi trả thuốc GPP, đối soát bưu phẩm hoàn tại từng chi nhánh kho, điều phối kho và kiểm soát hoàn tiền bảo mật."
        actions={
          <button
            type="button"
            onClick={activeTab === 'OVERVIEW' ? loadOverview : () => loadReturns()}
            disabled={loadingOverview || loading}
            className="admin-button button-secondary"
            style={{ display: 'flex', alignItems: 'center', gap: 6 }}
          >
            <RefreshCw size={14} className={loadingOverview || loading ? 'spinner' : ''} />
            <span>Làm mới dữ liệu</span>
          </button>
        }
      />

      {/* Main Tab Bar */}
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
          <span>Tổng quan ca hoàn chi nhánh & SLA</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('REQUESTS')}
          style={{
            padding: '10px 20px',
            fontSize: 14,
            fontWeight: 700,
            background: 'none',
            border: 'none',
            borderBottom: activeTab === 'REQUESTS' ? '3px solid #047857' : '3px solid transparent',
            color: activeTab === 'REQUESTS' ? '#047857' : '#64748b',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: 8,
          }}
        >
          <RotateCcw size={16} />
          <span>Danh sách yêu cầu đổi/trả ({totalCount})</span>
        </button>
      </div>

      {/* ======================================================== */}
      {/* TAB 1: TỔNG QUAN CA HOÀN & SLA TỪNG KHO                  */}
      {/* ======================================================== */}
      {activeTab === 'OVERVIEW' && (
        <div>
          {/* 12 KPI CARDS */}
          {kpi && (
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
                gap: 14,
                marginBottom: 24,
              }}
            >
              {[
                { label: 'Tổng số yêu cầu hoàn', val: kpi.total_returns, icon: RotateCcw, color: '#0284c7', bg: '#f0f9ff' },
                { label: 'Chờ kho tiếp nhận', val: kpi.waiting_warehouse_receive, icon: Clock, color: '#b45309', bg: '#fef3c7' },
                { label: 'Đang chuyển về kho', val: kpi.in_transit, icon: Truck, color: '#0284c7', bg: '#eff6ff' },
                { label: 'Đang kiểm tra tại kho', val: kpi.inspecting, icon: FileText, color: '#7c3aed', bg: '#f3e8ff' },
                { label: 'Chờ Quản lý kho duyệt', val: kpi.waiting_manager_approval, icon: AlertTriangle, color: '#ea580c', bg: '#fff7ed' },
                { label: 'Đã duyệt chờ hoàn tiền', val: kpi.approved, icon: CheckCircle2, color: '#16a34a', bg: '#f0fdf4' },
                { label: 'Đã hoàn tiền thành công', val: kpi.refund_succeeded, icon: DollarSign, color: '#15803d', bg: '#dcfce7' },
                { label: 'Hoàn tiền thất bại', val: kpi.refund_failed, icon: AlertCircle, color: '#dc2626', bg: '#fef2f2' },
                { label: 'Đã từ chối', val: kpi.rejected, icon: XCircle, color: '#b91c1c', bg: '#fee2e2' },
                { label: 'Quá hạn xử lý (SLA)', val: kpi.overdue, icon: AlertTriangle, color: '#b91c1c', bg: '#fee2e2' },
                {
                  label: 'Tổng tiền đã hoàn',
                  val: `${(kpi.total_refunded_amount ?? 0).toLocaleString('vi-VN')} ₫`,
                  icon: DollarSign,
                  color: '#15803d',
                  bg: '#dcfce7',
                },
                {
                  label: 'Tiền đang chờ hoàn',
                  val: `${(kpi.total_pending_refund_amount ?? 0).toLocaleString('vi-VN')} ₫`,
                  icon: DollarSign,
                  color: '#0e7490',
                  bg: '#cffafe',
                },
              ].map((item, idx) => {
                const IconComp = item.icon
                return (
                  <div
                    key={idx}
                    style={{
                      background: '#fff',
                      borderRadius: 12,
                      padding: 14,
                      boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
                      border: '1px solid #e2e8f0',
                      display: 'flex',
                      alignItems: 'center',
                      gap: 10,
                    }}
                  >
                    <div
                      style={{
                        width: 40,
                        height: 40,
                        borderRadius: 10,
                        background: item.bg,
                        color: item.color,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        flexShrink: 0,
                      }}
                    >
                      <IconComp size={20} />
                    </div>
                    <div>
                      <div style={{ fontSize: 11, fontWeight: 600, color: '#64748b' }}>{item.label}</div>
                      <div style={{ fontSize: 17, fontWeight: 800, color: '#0f172a', marginTop: 2 }}>{item.val}</div>
                    </div>
                  </div>
                )
              })}
            </div>
          )}

          {/* BẢNG THEO DÕI CA HOÀN THEO TỪNG KHO */}
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
                Bảng Phân Bổ Ca Hoàn & Chỉ Số SLA Từng Chi Nhánh Kho
              </h3>
              <span style={{ fontSize: 12, color: '#64748b' }}>
                Hàng hoàn trả về kho đã xuất • Quản lý kho trực tiếp tiếp nhận & phê duyệt
              </span>
            </div>

            {loadingOverview ? (
              <div style={{ padding: 48, textAlign: 'center', color: '#64748b' }}>
                <Loader2 size={24} className="spinner" style={{ margin: '0 auto 8px' }} />
                Đang tải dữ liệu ca hoàn từng kho...
              </div>
            ) : whStats.length === 0 ? (
              <div style={{ padding: 48, textAlign: 'center', color: '#64748b' }}>
                Không có dữ liệu ca hoàn nào.
              </div>
            ) : (
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12, textAlign: 'left' }}>
                  <thead>
                    <tr style={{ background: '#f8fafc', borderBottom: '1px solid #e2e8f0', color: '#475569' }}>
                      <th style={{ padding: '10px 14px' }}>Mã & Tên Kho</th>
                      <th style={{ padding: '10px 14px' }}>Quản Lý Kho</th>
                      <th style={{ padding: '10px 14px', textAlign: 'center' }}>Tổng Ca Hoàn</th>
                      <th style={{ padding: '10px 14px', textAlign: 'center' }}>Đang Kiểm Tra</th>
                      <th style={{ padding: '10px 14px', textAlign: 'center' }}>Chờ QL Duyệt</th>
                      <th style={{ padding: '10px 14px', textAlign: 'center' }}>Đã Duyệt</th>
                      <th style={{ padding: '10px 14px', textAlign: 'center' }}>Đã Từ Chối</th>
                      <th style={{ padding: '10px 14px', textAlign: 'center' }}>Hoàn Tất</th>
                      <th style={{ padding: '10px 14px', textAlign: 'center' }}>Thất Bại</th>
                      <th style={{ padding: '10px 14px', textAlign: 'right' }}>Tiền Đã Hoàn</th>
                      <th style={{ padding: '10px 14px', textAlign: 'center' }}>Quá SLA</th>
                    </tr>
                  </thead>
                  <tbody>
                    {whStats.map((wh) => (
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
                        <td style={{ padding: '10px 14px', color: '#047857', fontWeight: 600 }}>{wh.manager_name}</td>
                        <td style={{ padding: '10px 14px', textAlign: 'center', fontWeight: 700 }}>{wh.total_cases}</td>
                        <td style={{ padding: '10px 14px', textAlign: 'center', color: '#7c3aed' }}>{wh.inspecting}</td>
                        <td style={{ padding: '10px 14px', textAlign: 'center', color: '#ea580c', fontWeight: 600 }}>
                          {wh.waiting_approval}
                        </td>
                        <td style={{ padding: '10px 14px', textAlign: 'center', color: '#16a34a' }}>{wh.approved}</td>
                        <td style={{ padding: '10px 14px', textAlign: 'center', color: '#dc2626' }}>{wh.rejected}</td>
                        <td style={{ padding: '10px 14px', textAlign: 'center', color: '#15803d', fontWeight: 600 }}>
                          {wh.completed}
                        </td>
                        <td style={{ padding: '10px 14px', textAlign: 'center', color: '#b91c1c' }}>{wh.failed}</td>
                        <td style={{ padding: '10px 14px', textAlign: 'right', fontWeight: 700, color: '#15803d' }}>
                          {(wh.total_refunded_amount ?? 0).toLocaleString('vi-VN')} ₫
                        </td>
                        <td style={{ padding: '10px 14px', textAlign: 'center' }}>
                          {wh.overdue_sla > 0 ? (
                            <span style={{ color: '#b91c1c', fontWeight: 700 }}>⚠️ {wh.overdue_sla}</span>
                          ) : (
                            <span style={{ color: '#64748b' }}>0</span>
                          )}
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
      {/* TAB 2: DANH SÁCH YÊU CẦU ĐỔI/TRẢ (REQUESTS LIST)         */}
      {/* ======================================================== */}
      {activeTab === 'REQUESTS' && (
        <div>
          <FilterBar
            searchValue={search}
            onSearchChange={setSearch}
            searchPlaceholder="Tìm kiếm theo mã đổi/trả, mã đơn, tên hoặc SĐT khách..."
            onRefresh={() => loadReturns()}
            isRefreshing={loading}
            totalCount={totalCount}
            filteredCount={returns.length}
            unitLabel="yêu cầu"
          >
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                style={{
                  padding: '6px 12px',
                  borderRadius: 8,
                  border: '1px solid #cbd5e1',
                  background: '#fff',
                  fontSize: 13,
                  color: '#1e293b',
                  fontWeight: 600,
                }}
              >
                <option value="">Tất cả trạng thái</option>
                <option value="REQUESTED">Chờ duyệt ban đầu</option>
                <option value="ASSIGNED_TO_WAREHOUSE">Đã phân về kho</option>
                <option value="IN_TRANSIT">Đang chuyển về kho</option>
                <option value="RECEIVED">Đã tới kho</option>
                <option value="INSPECTING">Đang kiểm hàng</option>
                <option value="WAITING_MANAGER_APPROVAL">Chờ QL duyệt</option>
                <option value="APPROVED">Đã phê duyệt</option>
                <option value="REFUND_PENDING">Chờ hoàn tiền</option>
                <option value="REFUNDED">Đã hoàn tiền</option>
                <option value="RESTOCKED">Đã nhập kho</option>
                <option value="COMPLETED">Hoàn tất</option>
                <option value="REJECTED">Đã từ chối</option>
              </select>

              <select
                value={typeFilter}
                onChange={(e) => setTypeFilter(e.target.value)}
                style={{
                  padding: '6px 12px',
                  borderRadius: 8,
                  border: '1px solid #cbd5e1',
                  background: '#fff',
                  fontSize: 13,
                  color: '#1e293b',
                  fontWeight: 600,
                }}
              >
                <option value="">Tất cả phân loại</option>
                <option value="RETURN">Trả hàng hoàn tiền (RETURN)</option>
                <option value="EXCHANGE">Đổi sản phẩm (EXCHANGE)</option>
              </select>
            </div>
          </FilterBar>

          {/* Table List */}
          <div className="panel" style={{ padding: 0, overflow: 'hidden' }}>
            {loading ? (
              <div style={{ padding: 48, textAlign: 'center', color: '#64748b' }}>
                <Loader2 size={24} className="spinner" style={{ margin: '0 auto 8px' }} />
                Đang nạp danh sách yêu cầu...
              </div>
            ) : returns.length === 0 ? (
              <div style={{ padding: 48, textAlign: 'center', color: '#64748b' }}>
                Không có yêu cầu đổi/trả nào phù hợp.
              </div>
            ) : (
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13, textAlign: 'left' }}>
                  <thead>
                    <tr style={{ background: '#f8fafc', borderBottom: '1px solid #e2e8f0', color: '#475569' }}>
                      <th style={{ padding: '12px 16px' }}>Mã Yêu Cầu</th>
                      <th style={{ padding: '12px 16px' }}>Mã Đơn Hàng</th>
                      <th style={{ padding: '12px 16px' }}>Khách Hàng</th>
                      <th style={{ padding: '12px 16px' }}>Phân Loại</th>
                      <th style={{ padding: '12px 16px' }}>Trạng Thái</th>
                      <th style={{ padding: '12px 16px' }}>Ngày Yêu Cầu</th>
                      <th style={{ padding: '12px 16px', textAlign: 'right' }}>Thao Tác</th>
                    </tr>
                  </thead>
                  <tbody>
                    {returns.map((r) => {
                      const badge = STATUS_CONFIG[r.status] || { label: r.status, color: '#475569', bg: '#f1f5f9' }
                      return (
                        <tr
                          key={r.id}
                          style={{ borderBottom: '1px solid #f1f5f9', transition: 'background 0.15s' }}
                          onMouseEnter={(e) => (e.currentTarget.style.background = '#f8fafc')}
                          onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                        >
                          <td style={{ padding: '12px 16px', fontWeight: 700, color: '#0f172a' }}>{r.return_code}</td>
                          <td style={{ padding: '12px 16px', fontWeight: 600, color: '#0284c7' }}>{r.order_code}</td>
                          <td style={{ padding: '12px 16px' }}>
                            <div style={{ fontWeight: 600 }}>{r.customer_name}</div>
                            <div style={{ fontSize: 11, color: '#64748b' }}>{r.customer_phone}</div>
                          </td>
                          <td style={{ padding: '12px 16px' }}>
                            <span style={{ fontSize: 11, padding: '3px 8px', borderRadius: 4, background: '#f1f5f9', fontWeight: 600 }}>
                              {r.request_type}
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
                                background: badge.bg,
                                color: badge.color,
                              }}
                            >
                              {badge.label}
                            </span>
                          </td>
                          <td style={{ padding: '12px 16px', color: '#64748b', fontSize: 12 }}>
                            {r.requested_at ? formatDateTimeVN(r.requested_at) : '—'}
                          </td>
                          <td style={{ padding: '12px 16px', textAlign: 'right' }}>
                            <button
                              type="button"
                              onClick={() => openDetail(r.return_code)}
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
                              <span>Chi tiết</span>
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
              totalItems={totalCount}
              itemName="yêu cầu"
              onPageChange={setCurrentPage}
              onPageSizeChange={setPageSize}
            />
          </div>
        </div>
      )}

      {/* ======================================================== */}
      {/* MODAL CHI TIẾT YÊU CẦU ĐỔI/TRẢ (DETAIL MODAL)            */}
      {/* ======================================================== */}
      {selectedReturnCode && returnDetail && (
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
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <h2 style={{ margin: 0, fontSize: 18, fontWeight: 700 }}>
                    Chi Tiết Yêu Cầu Đổi/Trả: {returnDetail.return_code}
                  </h2>
                  <span
                    style={{
                      padding: '3px 10px',
                      borderRadius: 12,
                      fontSize: 11,
                      fontWeight: 700,
                      background: STATUS_CONFIG[returnDetail.status]?.bg || '#fff',
                      color: STATUS_CONFIG[returnDetail.status]?.color || '#000',
                    }}
                  >
                    {STATUS_CONFIG[returnDetail.status]?.label || returnDetail.status}
                  </span>
                </div>
                <div style={{ fontSize: 12, color: '#94a3b8', marginTop: 4 }}>
                  Mã đơn gốc: {returnDetail.order_code} • Khách: {returnDetail.customer_name} ({returnDetail.customer_phone})
                </div>
              </div>
              <button
                type="button"
                onClick={() => setSelectedReturnCode(null)}
                style={{ background: 'none', border: 'none', color: '#94a3b8', cursor: 'pointer' }}
              >
                <X size={20} />
              </button>
            </div>

            {/* Body */}
            <div style={{ padding: '20px 24px', overflowY: 'auto', flex: 1 }}>
              {actionError && (
                <div
                  style={{
                    padding: '12px 16px',
                    borderRadius: 8,
                    background: '#fef2f2',
                    border: '1px solid #fecaca',
                    color: '#991b1b',
                    fontSize: 13,
                    marginBottom: 16,
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                  }}
                >
                  <AlertCircle size={16} />
                  <span>{actionError}</span>
                </div>
              )}

              {actionSuccess && (
                <div
                  style={{
                    padding: '12px 16px',
                    borderRadius: 8,
                    background: '#f0fdf4',
                    border: '1px solid #bbf7d0',
                    color: '#166534',
                    fontSize: 13,
                    marginBottom: 16,
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                  }}
                >
                  <CheckCircle2 size={16} />
                  <span>{actionSuccess}</span>
                </div>
              )}

              {/* Thông tin lý do */}
              <div style={{ background: '#f8fafc', padding: 14, borderRadius: 8, border: '1px solid #e2e8f0', marginBottom: 20 }}>
                <div><strong>Lý do gửi trả:</strong> {returnDetail.reason_text}</div>
                {returnDetail.customer_note && <div style={{ marginTop: 4 }}><strong>Ghi chú của khách:</strong> {returnDetail.customer_note}</div>}
              </div>

              {/* CA HOÀN CON THEO CHI NHÁNH KHO (WarehouseReturnCases) */}
              {returnDetail.warehouse_cases && returnDetail.warehouse_cases.length > 0 && (
                <div style={{ marginBottom: 20 }}>
                  <h3 style={{ fontSize: 14, fontWeight: 700, color: '#0f172a', marginBottom: 8 }}>
                    Các Ca Hoàn Chi Nhánh Phụ Trách (Child Warehouse Cases)
                  </h3>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    {returnDetail.warehouse_cases.map((wc) => (
                      <div
                        key={wc.id}
                        style={{
                          background: '#f8fafc',
                          padding: 12,
                          borderRadius: 8,
                          border: '1px solid #e2e8f0',
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center',
                        }}
                      >
                        <div>
                          <div style={{ fontWeight: 700, color: '#0f172a' }}>
                            {wc.case_code} — Kho: {wc.warehouse_name || wc.warehouse_code}
                          </div>
                          <div style={{ fontSize: 11, color: '#64748b', marginTop: 2 }}>
                            Nhân viên kiểm hàng: <strong>{wc.assigned_staff_name || 'Chưa gán'}</strong> • Số mặt hàng: {wc.items_count}
                          </div>
                        </div>
                        <span
                          style={{
                            padding: '3px 10px',
                            borderRadius: 12,
                            fontSize: 11,
                            fontWeight: 700,
                            background: STATUS_CONFIG[wc.status]?.bg || '#f1f5f9',
                            color: STATUS_CONFIG[wc.status]?.color || '#475569',
                          }}
                        >
                          {STATUS_CONFIG[wc.status]?.label || wc.status}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Danh sách mặt hàng */}
              <div style={{ marginBottom: 20 }}>
                <h3 style={{ fontSize: 14, fontWeight: 700, color: '#0f172a', marginBottom: 8 }}>
                  Sản Phẩm Trong Yêu Cầu Đổi/Trả
                </h3>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12, border: '1px solid #e2e8f0' }}>
                  <thead>
                    <tr style={{ background: '#f1f5f9', color: '#475569', textAlign: 'left' }}>
                      <th style={{ padding: '8px 12px' }}>Tên Sản Phẩm</th>
                      <th style={{ padding: '8px 12px', textAlign: 'center' }}>SL Khách Yêu Cầu</th>
                      <th style={{ padding: '8px 12px', textAlign: 'right' }}>Đơn Giá Ròng</th>
                      <th style={{ padding: '8px 12px', textAlign: 'right' }}>Thành Tiền</th>
                    </tr>
                  </thead>
                  <tbody>
                    {returnDetail.items.map((it) => (
                      <tr key={it.id} style={{ borderBottom: '1px solid #f1f5f9' }}>
                        <td style={{ padding: '8px 12px', fontWeight: 600 }}>{it.product_name}</td>
                        <td style={{ padding: '8px 12px', textAlign: 'center', fontWeight: 700, color: '#0284c7' }}>
                          {it.requested_quantity}
                        </td>
                        <td style={{ padding: '8px 12px', textAlign: 'right' }}>
                          {(it.unit_price ?? 0).toLocaleString('vi-VN')} ₫
                        </td>
                        <td style={{ padding: '8px 12px', textAlign: 'right', fontWeight: 600 }}>
                          {((it.subtotal || (it.unit_price ?? 0) * (it.requested_quantity ?? 0)) ?? 0).toLocaleString('vi-VN')} ₫
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Bằng chứng ảnh */}
              {returnDetail.evidences.length > 0 && (
                <div style={{ marginBottom: 20 }}>
                  <h3 style={{ fontSize: 14, fontWeight: 700, color: '#0f172a', marginBottom: 8 }}>
                    Ảnh / Bằng Chứng Do Khách Tải Lên
                  </h3>
                  <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                    {returnDetail.evidences.map((ev) => (
                      <a
                        key={ev.id}
                        href={ev.file_url}
                        target="_blank"
                        rel="noreferrer"
                        style={{
                          width: 80,
                          height: 80,
                          borderRadius: 8,
                          border: '1px solid #cbd5e1',
                          overflow: 'hidden',
                          display: 'block',
                        }}
                      >
                        <img src={ev.file_url} alt={ev.file_name} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                      </a>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Footer Admin Controls */}
            <div
              style={{
                padding: '14px 24px',
                background: '#f8fafc',
                borderTop: '1px solid #e2e8f0',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
              }}
            >
              <div style={{ display: 'flex', gap: 10 }}>
                {/* Nút Điều chuyển kho */}
                <button
                  type="button"
                  onClick={() => setShowReassignModal(true)}
                  style={{
                    padding: '8px 14px',
                    borderRadius: 6,
                    background: '#fff',
                    border: '1px solid #cbd5e1',
                    fontSize: 12,
                    fontWeight: 600,
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 6,
                  }}
                >
                  <Building2 size={14} />
                  <span>Điều chuyển kho</span>
                </button>

                {/* Nút Can thiệp khẩn cấp (Override) */}
                <button
                  type="button"
                  onClick={() => setShowOverrideModal(true)}
                  style={{
                    padding: '8px 14px',
                    borderRadius: 6,
                    background: '#fee2e2',
                    border: '1px solid #fecaca',
                    color: '#991b1b',
                    fontSize: 12,
                    fontWeight: 700,
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 6,
                  }}
                >
                  <ShieldAlert size={14} />
                  <span>Can thiệp khẩn cấp (Override)</span>
                </button>
              </div>

              <button
                type="button"
                onClick={() => setSelectedReturnCode(null)}
                className="admin-button button-secondary"
              >
                Đóng
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL ĐIỀU CHUYỂN KHO */}
      {showReassignModal && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,0.5)',
            zIndex: 1100,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: 20,
          }}
        >
          <div style={{ background: '#fff', borderRadius: 12, width: '100%', maxWidth: 440, padding: 24 }}>
            <h3 style={{ fontSize: 16, fontWeight: 700, margin: '0 0 12px 0' }}>Điều Chuyển Ca Hoàn Sang Kho Mới</h3>
            <p style={{ fontSize: 13, color: '#64748b', margin: '0 0 16px 0' }}>
              Chọn chi nhánh kho mới sẽ tiếp nhận gói hàng và thẩm định dược phẩm:
            </p>
            <div style={{ marginBottom: 14 }}>
              <select
                value={reassignWhId}
                onChange={(e) => setReassignWhId(e.target.value ? Number(e.target.value) : '')}
                style={{ width: '100%', padding: '10px 12px', borderRadius: 8, border: '1px solid #cbd5e1', fontSize: 14 }}
              >
                <option value="">-- Chọn kho mới --</option>
                {warehouses.map((w) => (
                  <option key={w.id} value={w.id}>
                    {w.name} ({w.code})
                  </option>
                ))}
              </select>
            </div>
            <div style={{ marginBottom: 20 }}>
              <textarea
                rows={3}
                value={reassignReason}
                onChange={(e) => setReassignReason(e.target.value)}
                placeholder="Nhập lý do điều chuyển kho bắt buộc (tối thiểu 5 ký tự)..."
                style={{ width: '100%', padding: '10px 12px', borderRadius: 8, border: '1px solid #cbd5e1', fontSize: 13 }}
              />
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
              <button
                type="button"
                onClick={() => setShowReassignModal(false)}
                className="admin-button button-secondary"
              >
                Hủy
              </button>
              <button
                type="button"
                onClick={handleReassignWarehouse}
                disabled={!reassignWhId || reassignReason.trim().length < 5 || actionLoading}
                style={{
                  padding: '8px 18px',
                  background: '#047857',
                  color: '#fff',
                  border: 'none',
                  borderRadius: 8,
                  fontWeight: 600,
                  cursor: 'pointer',
                }}
              >
                Xác nhận chuyển kho
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL CAN THIỆP KHẨN CẤP (ADMIN OVERRIDE) */}
      {showOverrideModal && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,0.5)',
            zIndex: 1100,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: 20,
          }}
        >
          <div style={{ background: '#fff', borderRadius: 12, width: '100%', maxWidth: 460, padding: 24 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: '#b91c1c', marginBottom: 12 }}>
              <ShieldAlert size={20} />
              <h3 style={{ fontSize: 16, fontWeight: 700, margin: 0 }}>Can Thiệp Khẩn Cấp (Admin Override)</h3>
            </div>
            <p style={{ fontSize: 13, color: '#64748b', margin: '0 0 16px 0' }}>
              Quyền hạn tối cao của Admin Tổng để ép chuyển trạng thái ca hoàn khi phát hiện sai phạm hoặc kho bị nghẽn:
            </p>
            <div style={{ marginBottom: 14 }}>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: '#334155', marginBottom: 6 }}>
                Chọn trạng thái mới:
              </label>
              <select
                value={overrideStatus}
                onChange={(e) => setOverrideStatus(e.target.value)}
                style={{ width: '100%', padding: '9px 12px', borderRadius: 8, border: '1px solid #cbd5e1', fontSize: 13 }}
              >
                <option value="APPROVED">Phê duyệt bắt buộc (APPROVED)</option>
                <option value="REJECTED">Từ chối bắt buộc (REJECTED)</option>
                <option value="CLOSED">Đóng hồ sơ khẩn cấp (CLOSED)</option>
              </select>
            </div>
            <div style={{ marginBottom: 20 }}>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 700, color: '#991b1b', marginBottom: 6 }}>
                Lý do can thiệp khẩn cấp (Bắt buộc ghi nhận kiểm toán):
              </label>
              <textarea
                rows={3}
                value={overrideReason}
                onChange={(e) => setOverrideReason(e.target.value)}
                placeholder="Nhập lý do can thiệp (tối thiểu 5 ký tự)..."
                style={{ width: '100%', padding: '10px 12px', borderRadius: 8, border: '1px solid #f87171', fontSize: 13 }}
              />
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
              <button
                type="button"
                onClick={() => setShowOverrideModal(false)}
                className="admin-button button-secondary"
              >
                Hủy
              </button>
              <button
                type="button"
                onClick={handleAdminOverride}
                disabled={overrideReason.trim().length < 5 || actionLoading}
                style={{
                  padding: '9px 20px',
                  background: '#b91c1c',
                  color: '#fff',
                  border: 'none',
                  borderRadius: 8,
                  fontWeight: 700,
                  cursor: 'pointer',
                }}
              >
                Xác nhận Override
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
