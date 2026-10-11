import {
  AlertCircle,
  AlertTriangle,
  ArrowRight,
  Ban,
  Boxes,
  CheckCircle2,
  Clock,
  Eye,
  FileCheck,
  FileText,
  Filter,
  Image as ImageIcon,
  Loader2,
  Package,
  RefreshCw,
  RotateCcw,
  Search,
  ShieldAlert,
  ShieldCheck,
  Truck,
  X,
  XCircle,
} from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { AdminPageHeader } from '../components/AdminPageHeader'
import { FilterBar } from '../components/FilterBar'
import { PaginationBar } from '../components/PaginationBar'
import { api } from '../services/api'

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
}

const STATUS_CONFIG: Record<string, { label: string; color: string; bg: string }> = {
  REQUESTED: { label: 'Chờ duyệt', color: '#b45309', bg: '#fef3c7' },
  REVIEWING: { label: 'Đang xem xét', color: '#1d4ed8', bg: '#dbeafe' },
  NEEDS_CUSTOMER_INFO: { label: 'Cần bổ sung TT', color: '#7c3aed', bg: '#ede9fe' },
  APPROVED: { label: 'Đã phê duyệt', color: '#15803d', bg: '#dcfce7' },
  WAITING_CUSTOMER_RETURN: { label: 'Chờ gửi hàng', color: '#c2410c', bg: '#ffedd5' },
  RETURN_IN_TRANSIT: { label: 'Đang chuyển về kho', color: '#0369a1', bg: '#e0f2fe' },
  RECEIVED_AT_WAREHOUSE: { label: 'Đã tới kho', color: '#4338ca', bg: '#e0e7ff' },
  INSPECTING: { label: 'DS đang thẩm định', color: '#6d28d9', bg: '#f3e8ff' },
  REFUND_PENDING: { label: 'Chờ hoàn tiền', color: '#0e7490', bg: '#cffafe' },
  REFUNDED: { label: 'Đã hoàn tiền', color: '#166534', bg: '#bbf7d0' },
  REPLACING: { label: 'Đang chuẩn bị đổi', color: '#3730a3', bg: '#e0e7ff' },
  REPLACEMENT_SHIPPED: { label: 'Đã giao đơn đổi', color: '#1e40af', bg: '#dbeafe' },
  COMPLETED: { label: 'Hoàn tất', color: '#15803d', bg: '#dcfce7' },
  REJECTED: { label: 'Từ chối', color: '#b91c1c', bg: '#fee2e2' },
  CANCELLED: { label: 'Đã hủy', color: '#475569', bg: '#f1f5f9' },
}

export function ReturnsPage() {
  const [returns, setReturns] = useState<ReturnSummary[]>([])
  const [totalCount, setTotalCount] = useState<number>(0)
  const [loading, setLoading] = useState<boolean>(true)
  const [search, setSearch] = useState<string>('')
  const [statusFilter, setStatusFilter] = useState<string>('')
  const [typeFilter, setTypeFilter] = useState<string>('')

  // Phân trang
  const [currentPage, setCurrentPage] = useState<number>(1)
  const [pageSize, setPageSize] = useState<number>(15)

  // Detail Modal State
  const [selectedReturnCode, setSelectedReturnCode] = useState<string | null>(null)
  const [returnDetail, setReturnDetail] = useState<ReturnDetailData | null>(null)
  const [loadingDetail, setLoadingDetail] = useState<boolean>(false)
  const [actionLoading, setActionLoading] = useState<boolean>(false)
  const [actionError, setActionError] = useState<string>('')

  // Review / Approve / Reject sub-modals
  const [rejectReason, setRejectReason] = useState<string>('')
  const [showRejectBox, setShowRejectBox] = useState<boolean>(false)
  const [approveNote, setApproveNote] = useState<string>('Vui lòng đóng gói thuốc cẩn thận và gửi về kho H4Care.')
  const [showApproveBox, setShowApproveBox] = useState<boolean>(false)

  // Inspection state
  const [showInspectionBox, setShowInspectionBox] = useState<boolean>(false)
  const [inspectionItems, setInspectionItems] = useState<
    Array<{
      return_item_id: number
      product_name: string
      condition: string
      restock_destination: string
      accepted_quantity: number
      rejected_quantity: number
      notes: string
    }>
  >([])
  const [generalInspectNote, setGeneralInspectNote] = useState<string>('Dược sĩ đã kiểm tra ngoại quan và tem seal GPP.')

  const totalPages = Math.max(1, Math.ceil(totalCount / pageSize))

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
    setCurrentPage(1)
    loadReturns(1, pageSize)
  }, [statusFilter, typeFilter])

  useEffect(() => {
    const timer = setTimeout(() => {
      setCurrentPage(1)
      loadReturns(1, pageSize)
    }, 350)
    return () => clearTimeout(timer)
  }, [search])

  const openDetail = async (code: string) => {
    setSelectedReturnCode(code)
    setLoadingDetail(true)
    setActionError('')
    setShowRejectBox(false)
    setShowApproveBox(false)
    setShowInspectionBox(false)
    try {
      const detail = await api<ReturnDetailData>(`/admin/returns/${code}`)
      setReturnDetail(detail)
      // Prepare inspection items
      if (detail.items) {
        setInspectionItems(
          detail.items.map((it) => ({
            return_item_id: it.id,
            product_name: it.product_name,
            condition: it.inspected_condition || 'GOOD_CONDITION',
            restock_destination: it.restock_destination || 'SELLABLE_STOCK',
            accepted_quantity: it.accepted_quantity > 0 ? it.accepted_quantity : it.requested_quantity,
            rejected_quantity: it.rejected_quantity || 0,
            notes: '',
          }))
        )
      }
    } catch (err: any) {
      setActionError(err.message || 'Không thể tải chi tiết yêu cầu')
    } finally {
      setLoadingDetail(false)
    }
  }

  const handleReviewStatus = async (newStatus: 'REVIEWING' | 'NEEDS_CUSTOMER_INFO') => {
    if (!selectedReturnCode) return
    setActionLoading(true)
    setActionError('')
    try {
      await api(`/admin/returns/${selectedReturnCode}/review`, {
        method: 'POST',
        body: JSON.stringify({
          status: newStatus,
          admin_note: `Cập nhật trạng thái sang ${newStatus}`,
          customer_visible_note: newStatus === 'NEEDS_CUSTOMER_INFO' ? 'Vui lòng cung cấp thêm hình ảnh sản phẩm' : undefined,
        }),
      })
      await openDetail(selectedReturnCode)
      loadReturns()
    } catch (err: any) {
      setActionError(err.message || 'Thao tác thất bại')
    } finally {
      setActionLoading(false)
    }
  }

  const handleApprove = async () => {
    if (!selectedReturnCode) return
    setActionLoading(true)
    setActionError('')
    try {
      await api(`/admin/returns/${selectedReturnCode}/approve`, {
        method: 'POST',
        body: JSON.stringify({
          customer_visible_note: approveNote,
        }),
      })
      setShowApproveBox(false)
      await openDetail(selectedReturnCode)
      loadReturns()
    } catch (err: any) {
      setActionError(err.message || 'Phê duyệt thất bại')
    } finally {
      setActionLoading(false)
    }
  }

  const handleReject = async () => {
    if (!selectedReturnCode || !rejectReason.trim()) {
      setActionError('Vui lòng nhập lý do từ chối')
      return
    }
    setActionLoading(true)
    setActionError('')
    try {
      await api(`/admin/returns/${selectedReturnCode}/reject`, {
        method: 'POST',
        body: JSON.stringify({
          rejection_reason: rejectReason.trim(),
        }),
      })
      setShowRejectBox(false)
      await openDetail(selectedReturnCode)
      loadReturns()
    } catch (err: any) {
      setActionError(err.message || 'Từ chối thất bại')
    } finally {
      setActionLoading(false)
    }
  }

  const handleReceiveAtWarehouse = async () => {
    if (!selectedReturnCode) return
    if (!confirm('Xác nhận kho H4Care đã tiếp nhận kiện hàng đổi trả từ bưu tá?')) return
    setActionLoading(true)
    setActionError('')
    try {
      await api(`/admin/returns/${selectedReturnCode}/receive`, {
        method: 'POST',
        body: JSON.stringify({
          note: 'Kho dược H4Care đã nhận kiện hàng nguyên vẹn.',
        }),
      })
      await openDetail(selectedReturnCode)
      loadReturns()
    } catch (err: any) {
      setActionError(err.message || 'Thao tác thất bại')
    } finally {
      setActionLoading(false)
    }
  }

  const handleInspectSubmit = async () => {
    if (!selectedReturnCode) return
    setActionLoading(true)
    setActionError('')
    try {
      await api(`/admin/returns/${selectedReturnCode}/inspect`, {
        method: 'POST',
        body: JSON.stringify({
          general_inspection_note: generalInspectNote,
          items: inspectionItems.map((it) => ({
            return_item_id: it.return_item_id,
            condition: it.condition,
            restock_destination: it.restock_destination,
            accepted_quantity: Number(it.accepted_quantity),
            rejected_quantity: Number(it.rejected_quantity),
            notes: it.notes,
          })),
        }),
      })
      setShowInspectionBox(false)
      await openDetail(selectedReturnCode)
      loadReturns()
    } catch (err: any) {
      setActionError(err.message || 'Lỗi thẩm định dược phẩm')
    } finally {
      setActionLoading(false)
    }
  }

  return (
    <div className="admin-page-container" style={{ padding: '24px 32px' }}>
      <AdminPageHeader
        title="Quản Lý Đổi & Trả Hàng (Returns)"
        subtitle="Tiếp nhận, kiểm tra hồ sơ thuốc GPP, thẩm định thực tế tại kho và phân luồng nhập lại kho bán."
        breadcrumbs={[
          { label: 'Trang chủ', href: '/' },
          { label: 'Hậu Mãi', href: '/returns' },
          { label: 'Yêu cầu đổi/trả' },
        ]}
      />

      {/* Filter and Search Bar */}
      <FilterBar
        searchValue={search}
        onSearchChange={setSearch}
        searchPlaceholder="Tìm kiếm theo mã đổi/trả, mã đơn, tên hoặc SĐT khách..."
        onRefresh={loadReturns}
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
            <option value="REVIEWING">Đang xem xét hồ sơ</option>
            <option value="NEEDS_CUSTOMER_INFO">Cần bổ sung thông tin</option>
            <option value="APPROVED">Đã phê duyệt</option>
            <option value="WAITING_CUSTOMER_RETURN">Chờ khách gửi hàng</option>
            <option value="RETURN_IN_TRANSIT">Đang chuyển về kho</option>
            <option value="RECEIVED_AT_WAREHOUSE">Đã tới kho H4Care</option>
            <option value="INSPECTING">Dược sĩ đang thẩm định</option>
            <option value="REFUND_PENDING">Chờ hoàn tiền</option>
            <option value="REFUNDED">Đã hoàn tiền</option>
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

      {/* Main Table */}
      <div
        style={{
          background: '#ffffff',
          borderRadius: 14,
          border: '1px solid #e2e8f0',
          overflow: 'hidden',
          boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
          marginTop: 16,
        }}
      >
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: 13 }}>
            <thead>
              <tr style={{ background: '#f8fafc', borderBottom: '1px solid #e2e8f0', color: '#475569', fontWeight: 700 }}>
                <th style={{ padding: '14px 16px' }}>Mã Đổi Trả</th>
                <th style={{ padding: '14px 16px' }}>Mã Đơn Hàng</th>
                <th style={{ padding: '14px 16px' }}>Khách Hàng</th>
                <th style={{ padding: '14px 16px' }}>Phân Loại</th>
                <th style={{ padding: '14px 16px' }}>Lý Do Trả</th>
                <th style={{ padding: '14px 16px' }}>Trạng Thái</th>
                <th style={{ padding: '14px 16px' }}>Vận Chuyển Kho</th>
                <th style={{ padding: '14px 16px', textAlign: 'right' }}>Thao Tác</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={8} style={{ padding: 40, textAlign: 'center', color: '#64748b' }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}>
                      <RefreshCw size={16} className="spin" />
                      <span>Đang tải danh sách đổi trả...</span>
                    </div>
                  </td>
                </tr>
              ) : returns.length === 0 ? (
                <tr>
                  <td colSpan={8} style={{ padding: 50, textAlign: 'center', color: '#94a3b8' }}>
                    <RotateCcw size={32} style={{ margin: '0 auto 10px', opacity: 0.5 }} />
                    <p style={{ margin: 0, fontWeight: 600 }}>Không tìm thấy yêu cầu đổi/trả nào phù hợp</p>
                  </td>
                </tr>
              ) : (
                returns.map((r) => {
                  const cfg = STATUS_CONFIG[r.status] || { label: r.status, color: '#334155', bg: '#f1f5f9' }
                  const isExchange = r.request_type === 'EXCHANGE'

                  return (
                    <tr
                      key={r.return_code}
                      style={{ borderBottom: '1px solid #f1f5f9', transition: 'background 0.15s' }}
                      onMouseEnter={(e) => (e.currentTarget.style.background = '#f8fafc')}
                      onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                    >
                      <td style={{ padding: '14px 16px', fontWeight: 800, color: '#0f172a' }}>
                        <span style={{ fontFamily: 'monospace', color: '#1e40af' }}>{r.return_code}</span>
                      </td>
                      <td style={{ padding: '14px 16px', fontWeight: 700, color: '#334155' }}>
                        #{r.order_code}
                      </td>
                      <td style={{ padding: '14px 16px' }}>
                        <div style={{ fontWeight: 700, color: '#0f172a' }}>{r.customer_name}</div>
                        <div style={{ fontSize: 11, color: '#64748b' }}>{r.customer_phone}</div>
                      </td>
                      <td style={{ padding: '14px 16px' }}>
                        <span
                          style={{
                            fontSize: 11,
                            fontWeight: 700,
                            padding: '3px 8px',
                            borderRadius: 6,
                            color: isExchange ? '#4338ca' : '#047857',
                            background: isExchange ? '#e0e7ff' : '#d1fae5',
                          }}
                        >
                          {isExchange ? 'ĐỔI HÀNG' : 'TRẢ HÀNG'}
                        </span>
                      </td>
                      <td style={{ padding: '14px 16px', color: '#475569', maxWidth: 220 }}>
                        <div style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                          {r.reason_text}
                        </div>
                        <span style={{ fontSize: 11, color: '#94a3b8' }}>{r.items_count} mặt hàng</span>
                      </td>
                      <td style={{ padding: '14px 16px' }}>
                        <span
                          style={{
                            fontSize: 12,
                            fontWeight: 700,
                            padding: '4px 10px',
                            borderRadius: 12,
                            color: cfg.color,
                            background: cfg.bg,
                            display: 'inline-block',
                          }}
                        >
                          {cfg.label}
                        </span>
                      </td>
                      <td style={{ padding: '14px 16px', fontSize: 12, color: '#475569' }}>
                        {r.tracking_code ? (
                          <div>
                            <span style={{ fontWeight: 600, color: '#0f172a' }}>{r.carrier_name}</span>: {r.tracking_code}
                          </div>
                        ) : (
                          <span style={{ color: '#94a3b8', fontStyle: 'italic' }}>Chưa có mã vận đơn</span>
                        )}
                      </td>
                      <td style={{ padding: '14px 16px', textAlign: 'right' }}>
                        <button
                          type="button"
                          onClick={() => openDetail(r.return_code)}
                          style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: 6,
                            padding: '6px 12px',
                            borderRadius: 8,
                            background: '#0284c7',
                            color: '#fff',
                            border: 'none',
                            fontWeight: 700,
                            fontSize: 12,
                            cursor: 'pointer',
                          }}
                        >
                          <Eye size={13} />
                          <span>Chi tiết</span>
                        </button>
                      </td>
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </div>
        {!loading && returns.length > 0 && (
          <PaginationBar
            currentPage={currentPage}
            totalPages={totalPages}
            pageSize={pageSize}
            totalItems={totalCount}
            itemName="yêu cầu đổi trả"
            onPageChange={(p) => {
              setCurrentPage(p)
              loadReturns(p, pageSize)
            }}
            onPageSizeChange={(sz) => {
              setPageSize(sz)
              setCurrentPage(1)
              loadReturns(1, sz)
            }}
            pageSizeOptions={[10, 15, 25, 50]}
          />
        )}
      </div>

      {/* DETAIL & ACTION MODAL */}
      {selectedReturnCode && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(15, 23, 42, 0.65)',
            backdropFilter: 'blur(3px)',
            zIndex: 1000,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: 20,
          }}
          onClick={() => setSelectedReturnCode(null)}
        >
          <div
            style={{
              background: '#fff',
              borderRadius: 16,
              maxWidth: 860,
              width: '100%',
              maxHeight: '90vh',
              overflowY: 'auto',
              padding: 28,
              boxShadow: '0 25px 50px -12px rgba(0,0,0,0.25)',
              border: '1px solid #e2e8f0',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'flex-start',
                borderBottom: '1px solid #f1f5f9',
                paddingBottom: 16,
                marginBottom: 20,
              }}
            >
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <h2 style={{ margin: 0, fontSize: 20, fontWeight: 800, color: '#0f172a' }}>
                    Yêu cầu #{selectedReturnCode}
                  </h2>
                  {returnDetail && (
                    <span
                      style={{
                        fontSize: 12,
                        fontWeight: 700,
                        padding: '4px 10px',
                        borderRadius: 12,
                        color: STATUS_CONFIG[returnDetail.status]?.color || '#334155',
                        background: STATUS_CONFIG[returnDetail.status]?.bg || '#f1f5f9',
                      }}
                    >
                      {STATUS_CONFIG[returnDetail.status]?.label || returnDetail.status}
                    </span>
                  )}
                </div>
                {returnDetail && (
                  <p style={{ margin: '4px 0 0', fontSize: 12, color: '#64748b' }}>
                    Đơn hàng gốc: <strong>#{returnDetail.order_code}</strong> • Khách: <strong>{returnDetail.customer_name}</strong> ({returnDetail.customer_phone})
                  </p>
                )}
              </div>

              <button
                type="button"
                onClick={() => setSelectedReturnCode(null)}
                style={{
                  background: '#f1f5f9',
                  border: 'none',
                  borderRadius: 8,
                  padding: 6,
                  cursor: 'pointer',
                  color: '#64748b',
                }}
              >
                <X size={18} />
              </button>
            </div>

            {loadingDetail ? (
              <div style={{ padding: 60, textAlign: 'center', color: '#64748b' }}>
                <RefreshCw size={24} className="spin" style={{ margin: '0 auto 12px' }} />
                <span>Đang tải hồ sơ đổi trả...</span>
              </div>
            ) : returnDetail ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
                {actionError && (
                  <div
                    style={{
                      background: '#fef2f2',
                      border: '1px solid #fecaca',
                      padding: '10px 14px',
                      borderRadius: 8,
                      color: '#b91c1c',
                      fontSize: 13,
                      display: 'flex',
                      alignItems: 'center',
                      gap: 8,
                    }}
                  >
                    <AlertCircle size={16} />
                    <span>{actionError}</span>
                  </div>
                )}

                {/* Workflow Action Bar */}
                <div
                  style={{
                    background: '#f8fafc',
                    border: '1px solid #e2e8f0',
                    borderRadius: 12,
                    padding: 16,
                  }}
                >
                  <div style={{ fontSize: 12, fontWeight: 700, color: '#475569', textTransform: 'uppercase', marginBottom: 10 }}>
                    Thao tác xử lý hồ sơ (Workflow Actions)
                  </div>
                  <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                    {returnDetail.status === 'REQUESTED' && (
                      <>
                        <button
                          type="button"
                          onClick={() => handleReviewStatus('REVIEWING')}
                          disabled={actionLoading}
                          style={{
                            padding: '8px 14px',
                            borderRadius: 8,
                            background: '#1d4ed8',
                            color: '#fff',
                            border: 'none',
                            fontWeight: 700,
                            fontSize: 12,
                            cursor: 'pointer',
                          }}
                        >
                          Tiếp nhận xem xét (Reviewing)
                        </button>
                        <button
                          type="button"
                          onClick={() => handleReviewStatus('NEEDS_CUSTOMER_INFO')}
                          disabled={actionLoading}
                          style={{
                            padding: '8px 14px',
                            borderRadius: 8,
                            background: '#7c3aed',
                            color: '#fff',
                            border: 'none',
                            fontWeight: 700,
                            fontSize: 12,
                            cursor: 'pointer',
                          }}
                        >
                          Yêu cầu thêm bằng chứng
                        </button>
                        <button
                          type="button"
                          onClick={() => setShowApproveBox(true)}
                          disabled={actionLoading}
                          style={{
                            padding: '8px 14px',
                            borderRadius: 8,
                            background: '#16a34a',
                            color: '#fff',
                            border: 'none',
                            fontWeight: 700,
                            fontSize: 12,
                            cursor: 'pointer',
                          }}
                        >
                          Phê duyệt đổi trả
                        </button>
                        <button
                          type="button"
                          onClick={() => setShowRejectBox(true)}
                          disabled={actionLoading}
                          style={{
                            padding: '8px 14px',
                            borderRadius: 8,
                            background: '#dc2626',
                            color: '#fff',
                            border: 'none',
                            fontWeight: 700,
                            fontSize: 12,
                            cursor: 'pointer',
                          }}
                        >
                          Từ chối yêu cầu
                        </button>
                      </>
                    )}

                    {returnDetail.status === 'REVIEWING' && (
                      <>
                        <button
                          type="button"
                          onClick={() => setShowApproveBox(true)}
                          disabled={actionLoading}
                          style={{
                            padding: '8px 14px',
                            borderRadius: 8,
                            background: '#16a34a',
                            color: '#fff',
                            border: 'none',
                            fontWeight: 700,
                            fontSize: 12,
                            cursor: 'pointer',
                          }}
                        >
                          Phê duyệt đổi trả
                        </button>
                        <button
                          type="button"
                          onClick={() => setShowRejectBox(true)}
                          disabled={actionLoading}
                          style={{
                            padding: '8px 14px',
                            borderRadius: 8,
                            background: '#dc2626',
                            color: '#fff',
                            border: 'none',
                            fontWeight: 700,
                            fontSize: 12,
                            cursor: 'pointer',
                          }}
                        >
                          Từ chối yêu cầu
                        </button>
                      </>
                    )}

                    {['APPROVED', 'WAITING_CUSTOMER_RETURN', 'RETURN_IN_TRANSIT'].includes(returnDetail.status) && (
                      <button
                        type="button"
                        onClick={handleReceiveAtWarehouse}
                        disabled={actionLoading}
                        style={{
                          padding: '8px 14px',
                          borderRadius: 8,
                          background: '#0284c7',
                          color: '#fff',
                          border: 'none',
                          fontWeight: 700,
                          fontSize: 12,
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          gap: 6,
                        }}
                      >
                        <Truck size={14} />
                        <span>Kho H4Care xác nhận đã nhận hàng</span>
                      </button>
                    )}

                    {['RECEIVED_AT_WAREHOUSE', 'INSPECTING'].includes(returnDetail.status) && (
                      <button
                        type="button"
                        onClick={() => setShowInspectionBox(true)}
                        disabled={actionLoading}
                        style={{
                          padding: '8px 14px',
                          borderRadius: 8,
                          background: '#6d28d9',
                          color: '#fff',
                          border: 'none',
                          fontWeight: 700,
                          fontSize: 12,
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          gap: 6,
                        }}
                      >
                        <ShieldCheck size={14} />
                        <span>Dược sĩ Thẩm định chất lượng & Nhập kho</span>
                      </button>
                    )}
                  </div>
                </div>

                {/* Sub-box: Approve form */}
                {showApproveBox && (
                  <div style={{ background: '#ecfdf5', border: '1px solid #a7f3d0', padding: 16, borderRadius: 12 }}>
                    <div style={{ fontWeight: 800, color: '#065f46', marginBottom: 8, fontSize: 13 }}>
                      Xác nhận Phê duyệt yêu cầu đổi/trả:
                    </div>
                    <textarea
                      value={approveNote}
                      onChange={(e) => setApproveNote(e.target.value)}
                      placeholder="Hướng dẫn gửi hàng cho khách..."
                      style={{
                        width: '100%',
                        padding: 10,
                        borderRadius: 8,
                        border: '1px solid #cbd5e1',
                        fontSize: 12,
                        marginBottom: 10,
                      }}
                      rows={2}
                    />
                    <div style={{ display: 'flex', gap: 8 }}>
                      <button
                        type="button"
                        onClick={handleApprove}
                        disabled={actionLoading}
                        style={{
                          padding: '6px 14px',
                          borderRadius: 6,
                          background: '#059669',
                          color: '#fff',
                          border: 'none',
                          fontWeight: 700,
                          fontSize: 12,
                          cursor: 'pointer',
                        }}
                      >
                        Xác nhận Duyệt
                      </button>
                      <button
                        type="button"
                        onClick={() => setShowApproveBox(false)}
                        style={{
                          padding: '6px 14px',
                          borderRadius: 6,
                          background: '#fff',
                          border: '1px solid #cbd5e1',
                          color: '#475569',
                          fontWeight: 600,
                          fontSize: 12,
                          cursor: 'pointer',
                        }}
                      >
                        Hủy
                      </button>
                    </div>
                  </div>
                )}

                {/* Sub-box: Reject form */}
                {showRejectBox && (
                  <div style={{ background: '#fef2f2', border: '1px solid #fecaca', padding: 16, borderRadius: 12 }}>
                    <div style={{ fontWeight: 800, color: '#991b1b', marginBottom: 8, fontSize: 13 }}>
                      Từ chối yêu cầu đổi/trả (Lý do bắt buộc):
                    </div>
                    <textarea
                      value={rejectReason}
                      onChange={(e) => setRejectReason(e.target.value)}
                      placeholder="Ghi rõ lý do theo quy chế dược (ví dụ: Thuốc kê đơn, đã mở seal niêm phong...)"
                      style={{
                        width: '100%',
                        padding: 10,
                        borderRadius: 8,
                        border: '1px solid #cbd5e1',
                        fontSize: 12,
                        marginBottom: 10,
                      }}
                      rows={2}
                    />
                    <div style={{ display: 'flex', gap: 8 }}>
                      <button
                        type="button"
                        onClick={handleReject}
                        disabled={actionLoading}
                        style={{
                          padding: '6px 14px',
                          borderRadius: 6,
                          background: '#dc2626',
                          color: '#fff',
                          border: 'none',
                          fontWeight: 700,
                          fontSize: 12,
                          cursor: 'pointer',
                        }}
                      >
                        Xác nhận Từ chối
                      </button>
                      <button
                        type="button"
                        onClick={() => setShowRejectBox(false)}
                        style={{
                          padding: '6px 14px',
                          borderRadius: 6,
                          background: '#fff',
                          border: '1px solid #cbd5e1',
                          color: '#475569',
                          fontWeight: 600,
                          fontSize: 12,
                          cursor: 'pointer',
                        }}
                      >
                        Hủy
                      </button>
                    </div>
                  </div>
                )}

                {/* Sub-box: Inspection Form */}
                {showInspectionBox && (
                  <div style={{ background: '#f5f3ff', border: '1px solid #ddd6fe', padding: 18, borderRadius: 12 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
                      <ShieldCheck size={18} style={{ color: '#6d28d9' }} />
                      <div style={{ fontWeight: 800, color: '#5b21b6', fontSize: 14 }}>
                        Biên Bản Thẩm Định Chất Lượng Dược Phẩm (GPP Inspection)
                      </div>
                    </div>

                    <div style={{ display: 'flex', flexDirection: 'column', gap: 14, marginBottom: 14 }}>
                      {inspectionItems.map((it, idx) => (
                        <div
                          key={it.return_item_id}
                          style={{
                            background: '#fff',
                            border: '1px solid #e2e8f0',
                            borderRadius: 8,
                            padding: 12,
                            fontSize: 12,
                          }}
                        >
                          <div style={{ fontWeight: 700, color: '#0f172a', marginBottom: 6 }}>
                            {idx + 1}. {it.product_name}
                          </div>

                          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 10 }}>
                            <div>
                              <label style={{ display: 'block', color: '#64748b', fontSize: 11, marginBottom: 3 }}>
                                Tình trạng thẩm định:
                              </label>
                              <select
                                value={it.condition}
                                onChange={(e) => {
                                  const updated = [...inspectionItems]
                                  updated[idx].condition = e.target.value
                                  setInspectionItems(updated)
                                }}
                                style={{ width: '100%', padding: '4px 8px', borderRadius: 6, border: '1px solid #cbd5e1' }}
                              >
                                <option value="GOOD_CONDITION">Nguyên seal, đạt GPP</option>
                                <option value="DAMAGED_TRANSIT">Hỏng do vận chuyển</option>
                                <option value="DEFECTIVE_MANUFACTURER">Lỗi do nhà sản xuất</option>
                                <option value="OPENED_UNSEALED">Đã bóc seal</option>
                                <option value="EXPIRED">Cận/Hết hạn dùng</option>
                                <option value="CUSTOMER_DAMAGED">Khách hàng làm hỏng</option>
                              </select>
                            </div>

                            <div>
                              <label style={{ display: 'block', color: '#64748b', fontSize: 11, marginBottom: 3 }}>
                                Phân luồng tồn kho:
                              </label>
                              <select
                                value={it.restock_destination}
                                onChange={(e) => {
                                  const updated = [...inspectionItems]
                                  updated[idx].restock_destination = e.target.value
                                  setInspectionItems(updated)
                                }}
                                style={{ width: '100%', padding: '4px 8px', borderRadius: 6, border: '1px solid #cbd5e1' }}
                              >
                                <option value="SELLABLE_STOCK">Nhập lại kho bán lẻ</option>
                                <option value="QUARANTINE_AREA">Khu cách ly chờ xử lý</option>
                                <option value="DISPOSAL">Tiêu hủy y tế</option>
                              </select>
                            </div>

                            <div>
                              <label style={{ display: 'block', color: '#64748b', fontSize: 11, marginBottom: 3 }}>
                                Số lượng chấp nhận / Từ chối:
                              </label>
                              <div style={{ display: 'flex', gap: 6 }}>
                                <input
                                  type="number"
                                  min={0}
                                  value={it.accepted_quantity}
                                  onChange={(e) => {
                                    const updated = [...inspectionItems]
                                    updated[idx].accepted_quantity = Number(e.target.value)
                                    setInspectionItems(updated)
                                  }}
                                  style={{ width: 60, padding: '4px 6px', borderRadius: 6, border: '1px solid #cbd5e1' }}
                                  title="Số lượng chấp thuận nhận lại"
                                />
                                <span style={{ alignSelf: 'center', color: '#94a3b8' }}>/</span>
                                <input
                                  type="number"
                                  min={0}
                                  value={it.rejected_quantity}
                                  onChange={(e) => {
                                    const updated = [...inspectionItems]
                                    updated[idx].rejected_quantity = Number(e.target.value)
                                    setInspectionItems(updated)
                                  }}
                                  style={{ width: 60, padding: '4px 6px', borderRadius: 6, border: '1px solid #cbd5e1' }}
                                  title="Số lượng từ chối"
                                />
                              </div>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>

                    <div style={{ marginBottom: 12 }}>
                      <label style={{ display: 'block', color: '#475569', fontSize: 12, fontWeight: 700, marginBottom: 4 }}>
                        Ghi chú tổng thể của Dược sĩ phụ trách chuyên môn:
                      </label>
                      <input
                        type="text"
                        value={generalInspectNote}
                        onChange={(e) => setGeneralInspectNote(e.target.value)}
                        style={{ width: '100%', padding: 8, borderRadius: 6, border: '1px solid #cbd5e1', fontSize: 12 }}
                      />
                    </div>

                    <div style={{ display: 'flex', gap: 8 }}>
                      <button
                        type="button"
                        onClick={handleInspectSubmit}
                        disabled={actionLoading}
                        style={{
                          padding: '8px 18px',
                          borderRadius: 6,
                          background: '#6d28d9',
                          color: '#fff',
                          border: 'none',
                          fontWeight: 700,
                          fontSize: 12,
                          cursor: 'pointer',
                        }}
                      >
                        Lưu Thẩm Định & Nhập Kho
                      </button>
                      <button
                        type="button"
                        onClick={() => setShowInspectionBox(false)}
                        style={{
                          padding: '8px 14px',
                          borderRadius: 6,
                          background: '#fff',
                          border: '1px solid #cbd5e1',
                          color: '#475569',
                          fontWeight: 600,
                          fontSize: 12,
                          cursor: 'pointer',
                        }}
                      >
                        Đóng
                      </button>
                    </div>
                  </div>
                )}

                {/* Items List */}
                <div style={{ border: '1px solid #e2e8f0', borderRadius: 12, overflow: 'hidden' }}>
                  <div style={{ background: '#f8fafc', padding: '10px 14px', fontWeight: 700, fontSize: 12, color: '#475569' }}>
                    SẢN PHẨM TRẢ ({returnDetail.items?.length || 0})
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column' }}>
                    {returnDetail.items?.map((it) => (
                      <div
                        key={it.id}
                        style={{
                          padding: '12px 14px',
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center',
                          borderBottom: '1px solid #f1f5f9',
                          fontSize: 13,
                        }}
                      >
                        <div>
                          <div style={{ fontWeight: 700, color: '#0f172a' }}>{it.product_name}</div>
                          <div style={{ fontSize: 11, color: '#64748b', marginTop: 2 }}>
                            Số lượng yêu cầu: <strong>x{it.requested_quantity}</strong> • Đơn giá: {it.unit_price?.toLocaleString('vi-VN')} đ
                          </div>
                          {it.inspected_condition && (
                            <div style={{ fontSize: 11, color: '#059669', marginTop: 2 }}>
                              ✓ Đã thẩm định: <strong>{it.inspected_condition}</strong> → Phân luồng: <strong>{it.restock_destination}</strong> (Nhận: {it.accepted_quantity})
                            </div>
                          )}
                        </div>
                        <div style={{ fontWeight: 800, color: '#1e40af' }}>
                          {(it.subtotal || it.unit_price * it.requested_quantity).toLocaleString('vi-VN')} đ
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Evidences */}
                {returnDetail.evidences && returnDetail.evidences.length > 0 && (
                  <div>
                    <div style={{ fontSize: 12, fontWeight: 700, color: '#475569', textTransform: 'uppercase', marginBottom: 8 }}>
                      Hình ảnh / Bằng chứng khách tải lên ({returnDetail.evidences.length})
                    </div>
                    <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                      {returnDetail.evidences.map((ev) => (
                        <a
                          key={ev.id}
                          href={ev.file_url}
                          target="_blank"
                          rel="noreferrer"
                          style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: 6,
                            padding: '6px 12px',
                            background: '#f8fafc',
                            border: '1px solid #e2e8f0',
                            borderRadius: 8,
                            fontSize: 12,
                            color: '#0284c7',
                            textDecoration: 'none',
                            fontWeight: 600,
                          }}
                        >
                          <ImageIcon size={14} />
                          <span>{ev.file_name}</span>
                        </a>
                      ))}
                    </div>
                  </div>
                )}

                {/* Timeline */}
                <div>
                  <div style={{ fontSize: 12, fontWeight: 700, color: '#475569', textTransform: 'uppercase', marginBottom: 8 }}>
                    Lịch sử thay đổi trạng thái (Timeline)
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    {returnDetail.timeline?.map((tl) => (
                      <div
                        key={tl.id}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: 10,
                          fontSize: 12,
                          background: '#f8fafc',
                          padding: '6px 12px',
                          borderRadius: 6,
                        }}
                      >
                        <Clock size={13} style={{ color: '#94a3b8' }} />
                        <span style={{ fontWeight: 700, color: '#1e293b' }}>{tl.to_status}</span>
                        <span style={{ color: '#64748b' }}>bởi {tl.actor_name} ({tl.actor_role})</span>
                        {tl.note && <span style={{ color: '#475569', fontStyle: 'italic' }}>— "{tl.note}"</span>}
                        <span style={{ marginLeft: 'auto', fontSize: 11, color: '#94a3b8' }}>
                          {new Date(tl.created_at).toLocaleString('vi-VN')}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            ) : null}
          </div>
        </div>
      )}
    </div>
  )
}
