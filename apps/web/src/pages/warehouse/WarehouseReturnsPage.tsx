import { useEffect, useState } from 'react'
import {
  RotateCcw,
  Search,
  Filter,
  CheckCircle2,
  Clock,
  Package,
  Eye,
  X,
  AlertTriangle,
  Layers,
  MapPin,
  ChevronRight,
  ShieldCheck,
  ShieldAlert,
  UserCheck,
  DollarSign,
  Boxes,
  Lock,
  ArrowRight,
  AlertCircle,
  FileText,
  Truck,
  Image as ImageIcon,
} from 'lucide-react'
import { api } from '../../services/api'
import { formatDateTimeVN } from '../../utils/dateUtils'

interface ReturnCaseItem {
  id: number
  order_item_id: number
  product_name: string
  product_sku: string | null
  requested_quantity: number
  accepted_quantity: number
  rejected_quantity: number
  condition_reported?: string
  customer_reason?: string
  unit_price?: number
  net_unit_price?: number
  subtotal?: number
  approved_refund_amount?: number
}

interface ReturnEvidenceItem {
  id: number
  file_url: string
  file_name: string
  evidence_type: string
  video_url?: string
}

interface InspectionRecord {
  id: number
  return_item_id: number
  product_name?: string
  received_quantity: number
  accepted_quantity: number
  rejected_quantity: number
  package_condition: string
  seal_intact: boolean
  batch_matched: boolean
  expiry_matched: boolean
  damage_description?: string
  suggested_action: string
  inspection_note?: string
  inspected_at?: string
  inspected_by_name?: string
}

interface WarehouseReturnCaseDetail {
  id: number
  case_code: string
  return_code: string
  order_code: string
  status: string
  warehouse_name: string
  assigned_staff_id?: number
  assigned_staff_name?: string
  customer_name: string
  customer_phone: string
  customer_reason?: string
  items_count?: number
  created_at: string | null
  manager_note?: string
  rejection_reason?: string
  disposition?: string
  items: ReturnCaseItem[]
  inspections: InspectionRecord[]
  evidences: ReturnEvidenceItem[]
  active_evidence_request?: ActiveEvidenceRequest
  refund_info?: {
    estimated_refund_amount?: number
    already_refunded?: boolean
    refund_status?: string
    beneficiary_bank?: string
    beneficiary_account_name?: string
    beneficiary_account_number_masked?: string
  }
  proposed_refund?: {
    items_refund_amount?: number
    max_possible_refund?: number
    already_refunded?: number
    final_proposed_refund?: number
  }
}

interface ActiveEvidenceRequest {
  id: number
  request_code: string
  return_item_id?: number
  product_name?: string
  reason: string
  instructions: string
  required_image_count: number
  status: string
  requested_at?: string
  expires_at?: string
  submitted_at?: string
  customer_note?: string
  evidences?: Array<{
    id: number
    file_url: string
    file_name: string
    created_at?: string
  }>
}

interface WarehouseStaffOption {
  id: number
  full_name: string
  phone: string
}

const STATUS_TABS = [
  { value: 'ALL', label: 'Tất cả' },
  { value: 'ASSIGNED_TO_WAREHOUSE', label: 'Chờ nhận hàng' },
  { value: 'WAITING_CUSTOMER_EVIDENCE', label: 'Chờ khách nộp ảnh' },
  { value: 'WAITING_MANAGER_REVIEW', label: 'Khách đã nộp ảnh' },
  { value: 'INSPECTING', label: 'Đang kiểm hàng' },
  { value: 'WAITING_MANAGER_APPROVAL', label: 'Chờ duyệt' },
  { value: 'APPROVED', label: 'Đã duyệt' },
  { value: 'REFUND_PENDING', label: 'Chờ hoàn tiền' },
  { value: 'REFUNDED', label: 'Đã hoàn tiền' },
  { value: 'RESTOCKED', label: 'Đã nhập kho' },
  { value: 'REJECTED', label: 'Từ chối' },
]

const STATUS_CONFIG: Record<string, { label: string; bg: string; color: string }> = {
  REQUESTED: { label: 'Yêu cầu mới', bg: '#fef3c7', color: '#b45309' },
  ASSIGNED_TO_WAREHOUSE: { label: 'Chờ bưu tá giao tới', bg: '#e0f2fe', color: '#0369a1' },
  WAITING_CUSTOMER_SHIPMENT: { label: 'Chờ khách gửi', bg: '#f1f5f9', color: '#475569' },
  IN_TRANSIT: { label: 'Đang giao tới kho', bg: '#e0f2fe', color: '#0284c7' },
  RECEIVED: { label: 'Đã nhận tại kho', bg: '#dbeafe', color: '#1d4ed8' },
  WAITING_CUSTOMER_EVIDENCE: { label: 'Chờ khách gửi ảnh', bg: '#fff7ed', color: '#c2410c' },
  WAITING_MANAGER_REVIEW: { label: 'Khách đã gửi ảnh', bg: '#fef3c7', color: '#b45309' },
  INSPECTING: { label: 'NV đang kiểm hàng', bg: '#f3e8ff', color: '#7c3aed' },
  WAITING_MANAGER_APPROVAL: { label: 'Chờ Quản lý duyệt', bg: '#fff7ed', color: '#ea580c' },
  APPROVED: { label: 'Quản lý đã duyệt', bg: '#dcfce7', color: '#166534' },
  REJECTED: { label: 'Đã từ chối', bg: '#fee2e2', color: '#b91c1c' },
  CANCELLED_EVIDENCE_TIMEOUT: { label: 'Hết hạn bổ sung ảnh', bg: '#fee2e2', color: '#991b1b' },
  REFUND_PENDING: { label: 'Chờ hoàn tiền', bg: '#cffafe', color: '#0e7490' },
  REFUND_PROCESSING: { label: 'Đang xử lý hoàn tiền', bg: '#ede9fe', color: '#6d28d9' },
  REFUNDED: { label: 'Đã hoàn tiền', bg: '#bbf7d0', color: '#15803d' },
  RESTOCKED: { label: 'Đã nhập lại kho', bg: '#dcfce7', color: '#16a34a' },
  QUARANTINED: { label: 'Đã cách ly', bg: '#fef9c3', color: '#a16207' },
  DISPOSED: { label: 'Đã tiêu hủy', bg: '#f1f5f9', color: '#64748b' },
  CLOSED: { label: 'Hồ sơ đã đóng', bg: '#f8fafc', color: '#334155' },
}

export function WarehouseReturnsPage() {
  const [cases, setCases] = useState<WarehouseReturnCaseDetail[]>([])
  const [loading, setLoading] = useState(true)
  const [statusFilter, setStatusFilter] = useState('ALL')
  const [search, setSearch] = useState('')

  // Staff options in this warehouse
  const [staffList, setStaffList] = useState<WarehouseStaffOption[]>([])

  // Detail Modal
  const [selectedCase, setSelectedCase] = useState<WarehouseReturnCaseDetail | null>(null)
  const [loadingDetail, setLoadingDetail] = useState(false)

  // Actions states
  const [actionLoading, setActionLoading] = useState(false)
  const [actionError, setActionError] = useState('')
  const [actionSuccess, setActionSuccess] = useState('')

  // Assign Modal
  const [showAssignModal, setShowAssignModal] = useState(false)
  const [assignStaffId, setAssignStaffId] = useState<number | ''>('')

  // Re-inspection prompt Modal
  const [showReinspectModal, setShowReinspectModal] = useState(false)
  const [reinspectReason, setReinspectReason] = useState('')

  // Reject Modal
  const [showRejectModal, setShowRejectModal] = useState(false)
  const [rejectReason, setRejectReason] = useState('')

  // Refund Modal (Password Verified)
  const [showRefundModal, setShowRefundModal] = useState(false)
  const [managerPassword, setManagerPassword] = useState('')
  const [refundMethod, setRefundMethod] = useState('BANK_TRANSFER')
  const [manualRefNo, setManualRefNo] = useState('')

  // Stock Disposition Modal
  const [showDispositionModal, setShowDispositionModal] = useState(false)
  const [dispositionChoice, setDispositionChoice] = useState<'RESTOCK' | 'QUARANTINE' | 'DISPOSE'>('RESTOCK')
  const [dispositionNote, setDispositionNote] = useState('')

  // Request Evidence Modal
  const [showRequestEvidenceModal, setShowRequestEvidenceModal] = useState(false)
  const [evidenceRequiredCount, setEvidenceRequiredCount] = useState<number>(1)
  const [evidenceReason, setEvidenceReason] = useState('')
  const [evidenceInstructions, setEvidenceInstructions] = useState('')
  const [evidenceItemId, setEvidenceItemId] = useState<number | ''>('')

  const handleRequestEvidence = async () => {
    if (!selectedCase) return
    if (!evidenceReason.trim() || !evidenceInstructions.trim()) {
      setActionError('Vui lòng nhập đầy đủ lý do và hướng dẫn chụp ảnh.')
      return
    }
    setActionLoading(true)
    setActionError('')
    try {
      await api(`/warehouse/me/returns/${selectedCase.case_code}/request-evidence`, {
        method: 'POST',
        body: JSON.stringify({
          required_image_count: Number(evidenceRequiredCount),
          reason: evidenceReason.trim(),
          instructions: evidenceInstructions.trim(),
          return_item_id: evidenceItemId ? Number(evidenceItemId) : null,
        }),
      })
      setActionSuccess('Đã gửi yêu cầu bổ sung hình ảnh tới khách hàng thành công!')
      setShowRequestEvidenceModal(false)
      setEvidenceReason('')
      setEvidenceInstructions('')
      setEvidenceRequiredCount(1)
      setEvidenceItemId('')
      await openCaseDetail(selectedCase.case_code)
      await fetchCases()
    } catch (err: any) {
      setActionError(err?.message || 'Lỗi khi gửi yêu cầu bổ sung hình ảnh.')
    } finally {
      setActionLoading(false)
    }
  }

  const handleAcceptEvidence = async () => {
    if (!selectedCase) return
    setActionLoading(true)
    setActionError('')
    try {
      await api(`/warehouse/me/returns/${selectedCase.case_code}/accept-evidence`, {
        method: 'POST',
        body: JSON.stringify({
          manager_note: 'Quản lý kho đã kiểm tra và chấp nhận bằng chứng hình ảnh của khách hàng.',
        }),
      })
      setActionSuccess('Đã chấp nhận bằng chứng ảnh! Ca hoàn chuyển sang Chờ Quản lý duyệt hoàn.')
      await openCaseDetail(selectedCase.case_code)
      await fetchCases()
    } catch (err: any) {
      setActionError(err?.message || 'Lỗi khi chấp nhận bằng chứng ảnh.')
    } finally {
      setActionLoading(false)
    }
  }

  const fetchCases = async () => {
    setLoading(true)
    try {
      const params = new URLSearchParams()
      if (statusFilter !== 'ALL') params.set('status', statusFilter)
      if (search.trim()) params.set('search', search.trim())

      const res = await api<{ items: WarehouseReturnCaseDetail[] }>(`/warehouse/me/returns?${params.toString()}`)
      setCases(res.items || [])
    } catch (err: any) {
      console.error('Lỗi tải danh sách ca hoàn kho:', err)
    } finally {
      setLoading(false)
    }
  }

  const fetchStaffList = async () => {
    try {
      const res = await api<{ staff: WarehouseStaffOption[] }>('/warehouse-portal/staff')
      setStaffList(res.staff || [])
    } catch {
      // Fallback
    }
  }

  useEffect(() => {
    fetchCases()
    fetchStaffList()
  }, [statusFilter])

  const openCaseDetail = async (caseCode: string) => {
    setLoadingDetail(true)
    setActionError('')
    setActionSuccess('')
    try {
      const res = await api<WarehouseReturnCaseDetail>(`/warehouse/me/returns/${caseCode}`)
      setSelectedCase(res)
    } catch (err: any) {
      alert('Không thể mở chi tiết ca hoàn: ' + (err?.message || 'Lỗi mạng'))
    } finally {
      setLoadingDetail(false)
    }
  }

  // 1. Phân công nhân viên
  const handleAssignStaff = async () => {
    if (!selectedCase || !assignStaffId) return
    setActionLoading(true)
    setActionError('')
    try {
      await api(`/warehouse/me/returns/${selectedCase.case_code}/assign`, {
        method: 'POST',
        body: JSON.stringify({ staff_id: Number(assignStaffId) }),
      })
      setActionSuccess('Đã phân công nhân viên kiểm hàng thành công!')
      setShowAssignModal(false)
      await openCaseDetail(selectedCase.case_code)
      await fetchCases()
    } catch (err: any) {
      setActionError(err?.message || 'Lỗi khi phân công nhân viên.')
    } finally {
      setActionLoading(false)
    }
  }

  // 2. Yêu cầu kiểm tra lại
  const handleRequestReinspection = async () => {
    if (!selectedCase || !reinspectReason.trim()) return
    setActionLoading(true)
    setActionError('')
    try {
      await api(`/warehouse/me/returns/${selectedCase.case_code}/request-reinspection`, {
        method: 'POST',
        body: JSON.stringify({ reason: reinspectReason }),
      })
      setActionSuccess('Đã gửi yêu cầu kiểm tra lại cho nhân viên kho!')
      setShowReinspectModal(false)
      setReinspectReason('')
      await openCaseDetail(selectedCase.case_code)
      await fetchCases()
    } catch (err: any) {
      setActionError(err?.message || 'Lỗi khi gửi yêu cầu kiểm tra lại.')
    } finally {
      setActionLoading(false)
    }
  }

  // 3. Phê duyệt ca hoàn
  const handleApproveCase = async () => {
    if (!selectedCase) return
    if (!confirm(`Bạn có chắc chắn muốn phê duyệt ca hoàn ${selectedCase.case_code}?`)) return
    setActionLoading(true)
    setActionError('')
    try {
      const itemsPayload = (selectedCase.items || []).map((item) => {
        const insp = selectedCase.inspections?.find((i) => i.return_item_id === item.id)
        const recQty = insp ? insp.received_quantity : ((item as any).received_quantity ?? item.requested_quantity ?? 0)
        const accQty = insp ? insp.accepted_quantity : (item.accepted_quantity ?? recQty)
        const rejQty = insp ? insp.rejected_quantity : (item.rejected_quantity ?? Math.max(0, recQty - accQty))
        const rejReason = rejQty > 0 ? (insp?.damage_description || insp?.inspection_note || 'Không đạt điều kiện hoàn tiền') : undefined
        return {
          return_item_id: item.id,
          approved_quantity: accQty,
          rejected_quantity: rejQty,
          rejection_reason: rejReason,
        }
      })

      await api(`/warehouse/me/returns/${selectedCase.case_code}/approve`, {
        method: 'POST',
        body: JSON.stringify({
          items: itemsPayload,
          manager_note: 'Quản lý kho phê duyệt ca hoàn sau khi đối chiếu biên bản kiểm tra.',
        }),
      })
      setActionSuccess('Đã phê duyệt ca hoàn thành công! Ca hoàn đã chuyển sang trạng thái chờ hoàn tiền.')
      await openCaseDetail(selectedCase.case_code)
      await fetchCases()
    } catch (err: any) {
      setActionError(err?.message || 'Lỗi khi phê duyệt ca hoàn.')
    } finally {
      setActionLoading(false)
    }
  }

  // 4. Từ chối ca hoàn
  const handleRejectCase = async () => {
    if (!selectedCase || !rejectReason.trim()) return
    setActionLoading(true)
    setActionError('')
    try {
      await api(`/warehouse/me/returns/${selectedCase.case_code}/reject`, {
        method: 'POST',
        body: JSON.stringify({ rejection_reason: rejectReason }),
      })
      setActionSuccess('Đã từ chối ca hoàn thành công.')
      setShowRejectModal(false)
      setRejectReason('')
      await openCaseDetail(selectedCase.case_code)
      await fetchCases()
    } catch (err: any) {
      setActionError(err?.message || 'Lỗi khi từ chối ca hoàn.')
    } finally {
      setActionLoading(false)
    }
  }

  // 5. Hoàn tiền bảo mật (Mật khẩu Quản lý)
  const handleProcessRefund = async () => {
    if (!selectedCase || !managerPassword) return
    setActionLoading(true)
    setActionError('')
    try {
      await api(`/warehouse/me/returns/${selectedCase.case_code}/refund`, {
        method: 'POST',
        body: JSON.stringify({
          password: managerPassword,
          refund_method: refundMethod,
          manual_reference_number: manualRefNo.trim() || undefined,
        }),
      })
      setActionSuccess('Giao dịch hoàn tiền cho khách hàng đã được thực hiện thành công!')
      setShowRefundModal(false)
      setManagerPassword('')
      await openCaseDetail(selectedCase.case_code)
      await fetchCases()
    } catch (err: any) {
      setActionError(err?.message || 'Mật khẩu không chính xác hoặc lỗi khi xử lý hoàn tiền.')
    } finally {
      setActionLoading(false)
    }
  }

  // 6. Xử lý tồn kho (Restock / Quarantine / Dispose)
  const handleStockDisposition = async () => {
    if (!selectedCase) return
    setActionLoading(true)
    setActionError('')
    try {
      await api(`/warehouse/me/returns/${selectedCase.case_code}/stock-disposition`, {
        method: 'POST',
        body: JSON.stringify({
          disposition: dispositionChoice,
          note: dispositionNote.trim() || undefined,
        }),
      })
      setActionSuccess(
        dispositionChoice === 'RESTOCK'
          ? 'Đã nhập lại thuốc vào kho thành công (Số lượng khả dụng đã tăng)!'
          : dispositionChoice === 'QUARANTINE'
          ? 'Đã chuyển thuốc vào khu vực cách ly thành công!'
          : 'Đã hoàn tất thủ tục hủy thuốc theo biên bản!'
      )
      setShowDispositionModal(false)
      await openCaseDetail(selectedCase.case_code)
      await fetchCases()
    } catch (err: any) {
      setActionError(err?.message || 'Lỗi khi phân luồng kho.')
    } finally {
      setActionLoading(false)
    }
  }

  return (
    <div className="warehouse-returns-page" style={{ padding: '24px', maxWidth: '1400px', margin: '0 auto' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <div>
          <h1 style={{ fontSize: 24, fontWeight: 700, color: '#0f172a', margin: '0 0 6px 0' }}>
            Quản Lý Ca Đổi Trả & Hoàn Tiền Chi Nhánh
          </h1>
          <p style={{ margin: 0, fontSize: 14, color: '#64748b' }}>
            Tiếp nhận, phân công nhân viên kiểm định số lô HSD, phê duyệt đề xuất và thực hiện hoàn tiền bảo mật cho khách hàng.
          </p>
        </div>
        <button
          type="button"
          onClick={() => fetchCases()}
          className="admin-button button-secondary"
          style={{ display: 'flex', alignItems: 'center', gap: 6 }}
        >
          <RotateCcw size={15} />
          <span>Làm mới danh sách</span>
        </button>
      </div>

      {/* Filter Tabs & Search */}
      <div
        style={{
          background: '#fff',
          borderRadius: 12,
          padding: '16px',
          boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
          marginBottom: 20,
        }}
      >
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 14 }}>
          {STATUS_TABS.map((tab) => (
            <button
              key={tab.value}
              type="button"
              onClick={() => setStatusFilter(tab.value)}
              style={{
                padding: '6px 14px',
                borderRadius: 20,
                fontSize: 13,
                fontWeight: 600,
                border: 'none',
                cursor: 'pointer',
                background: statusFilter === tab.value ? '#0f172a' : '#f1f5f9',
                color: statusFilter === tab.value ? '#fff' : '#475569',
                transition: 'all 0.15s ease',
              }}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <div style={{ display: 'flex', gap: 12 }}>
          <div style={{ position: 'relative', flex: 1 }}>
            <Search size={16} style={{ position: 'absolute', left: 12, top: 12, color: '#94a3b8' }} />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && fetchCases()}
              placeholder="Tìm theo mã ca hoàn (WRC-...), mã yêu cầu (RET-...), mã đơn, tên khách..."
              style={{
                width: '100%',
                padding: '10px 12px 10px 38px',
                borderRadius: 8,
                border: '1px solid #cbd5e1',
                fontSize: 14,
                outline: 'none',
              }}
            />
          </div>
          <button
            type="button"
            onClick={() => fetchCases()}
            style={{
              padding: '0 20px',
              background: '#047857',
              color: '#fff',
              border: 'none',
              borderRadius: 8,
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            Tìm kiếm
          </button>
        </div>
      </div>

      {/* Table List */}
      <div
        style={{
          background: '#fff',
          borderRadius: 12,
          overflow: 'hidden',
          boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
        }}
      >
        {loading ? (
          <div style={{ padding: 48, textAlign: 'center', color: '#64748b' }}>
            <RotateCcw size={24} className="spinner" style={{ margin: '0 auto 8px' }} />
            <div>Đang nạp dữ liệu ca đổi trả thuộc kho...</div>
          </div>
        ) : cases.length === 0 ? (
          <div style={{ padding: 60, textAlign: 'center', color: '#64748b' }}>
            <RotateCcw size={40} style={{ margin: '0 auto 12px', opacity: 0.3 }} />
            <div style={{ fontSize: 16, fontWeight: 600, color: '#334155' }}>Không có ca hoàn nào phù hợp</div>
            <p style={{ margin: '4px 0 0', fontSize: 13 }}>
              Mọi yêu cầu đổi trả các mặt hàng xuất từ kho bạn sẽ hiển thị tại đây.
            </p>
          </div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: 13 }}>
            <thead>
              <tr style={{ background: '#f8fafc', borderBottom: '1px solid #e2e8f0', color: '#475569' }}>
                <th style={{ padding: '12px 16px', fontWeight: 600 }}>Mã Ca Hoàn Chi Nhánh</th>
                <th style={{ padding: '12px 16px', fontWeight: 600 }}>Yêu Cầu Gốc</th>
                <th style={{ padding: '12px 16px', fontWeight: 600 }}>Khách Hàng</th>
                <th style={{ padding: '12px 16px', fontWeight: 600 }}>Trạng Thái</th>
                <th style={{ padding: '12px 16px', fontWeight: 600 }}>Nhân Viên Kiểm Hàng</th>
                <th style={{ padding: '12px 16px', fontWeight: 600 }}>Số Mặt Hàng</th>
                <th style={{ padding: '12px 16px', fontWeight: 600 }}>Ngày Tạo</th>
                <th style={{ padding: '12px 16px', fontWeight: 600, textAlign: 'right' }}>Thao Tác</th>
              </tr>
            </thead>
            <tbody>
              {cases.map((c) => {
                const badge = STATUS_CONFIG[c.status] || { label: c.status, bg: '#f1f5f9', color: '#475569' }
                return (
                  <tr
                    key={c.id}
                    style={{ borderBottom: '1px solid #f1f5f9', transition: 'background 0.15s' }}
                    onMouseEnter={(e) => (e.currentTarget.style.background = '#f8fafc')}
                    onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                  >
                    <td style={{ padding: '12px 16px', fontWeight: 700, color: '#0f172a' }}>{c.case_code}</td>
                    <td style={{ padding: '12px 16px' }}>
                      <div style={{ fontWeight: 600, color: '#0284c7' }}>{c.return_code}</div>
                      <div style={{ fontSize: 11, color: '#64748b' }}>Đơn: {c.order_code}</div>
                    </td>
                    <td style={{ padding: '12px 16px' }}>
                      <div style={{ fontWeight: 600, color: '#1e293b' }}>{c.customer_name}</div>
                      <div style={{ fontSize: 11, color: '#64748b' }}>{c.customer_phone}</div>
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
                    <td style={{ padding: '12px 16px' }}>
                      {c.assigned_staff_name ? (
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: '#047857' }}>
                          <UserCheck size={14} />
                          <span style={{ fontWeight: 600 }}>{c.assigned_staff_name}</span>
                        </div>
                      ) : (
                        <span style={{ color: '#94a3b8', fontStyle: 'italic' }}>Chưa phân công</span>
                      )}
                    </td>
                    <td style={{ padding: '12px 16px', fontWeight: 600 }}>{c.items_count} sp</td>
                    <td style={{ padding: '12px 16px', color: '#64748b', fontSize: 12 }}>
                      {c.created_at ? formatDateTimeVN(c.created_at) : '—'}
                    </td>
                    <td style={{ padding: '12px 16px', textAlign: 'right' }}>
                      <button
                        type="button"
                        onClick={() => openCaseDetail(c.case_code)}
                        style={{
                          padding: '6px 14px',
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
                        <Eye size={13} />
                        <span>Xử lý ca</span>
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </div>

      {/* MODAL CHI TIẾT CA HOÀN */}
      {selectedCase && (
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
            {/* Modal Header */}
            <div
              style={{
                padding: '18px 24px',
                background: '#0f172a',
                color: '#fff',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
              }}
            >
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <h2 style={{ fontSize: 18, fontWeight: 700, margin: 0 }}>
                    Hồ Sơ Ca Hoàn: {selectedCase.case_code}
                  </h2>
                  <span
                    style={{
                      padding: '3px 10px',
                      borderRadius: 12,
                      fontSize: 11,
                      fontWeight: 700,
                      background: STATUS_CONFIG[selectedCase.status]?.bg || '#fff',
                      color: STATUS_CONFIG[selectedCase.status]?.color || '#000',
                    }}
                  >
                    {STATUS_CONFIG[selectedCase.status]?.label || selectedCase.status}
                  </span>
                </div>
                <div style={{ fontSize: 12, color: '#94a3b8', marginTop: 4 }}>
                  Mã YC cha: {selectedCase.return_code} • Đơn hàng: {selectedCase.order_code} • Kho: {selectedCase.warehouse_name}
                </div>
              </div>
              <button
                type="button"
                onClick={() => setSelectedCase(null)}
                style={{ background: 'none', border: 'none', color: '#94a3b8', cursor: 'pointer' }}
              >
                <X size={20} />
              </button>
            </div>

            {/* Modal Body */}
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

              {/* Thông báo khách đã nộp ảnh bằng chứng */}
              {selectedCase.active_evidence_request && selectedCase.status === 'WAITING_MANAGER_REVIEW' && (
                <div
                  style={{
                    padding: 16,
                    background: '#fef3c7',
                    border: '1px solid #fde68a',
                    borderRadius: 12,
                    marginBottom: 16,
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontWeight: 700, color: '#92400e', fontSize: 14 }}>
                      <ImageIcon size={18} />
                      <span>Khách hàng đã nộp hình ảnh bằng chứng</span>
                    </div>
                    <span style={{ fontSize: 11, color: '#78350f' }}>
                      Thời gian nộp: {selectedCase.active_evidence_request.submitted_at ? formatDateTimeVN(selectedCase.active_evidence_request.submitted_at) : 'Vừa xong'}
                    </span>
                  </div>
                  <div style={{ fontSize: 13, color: '#78350f', marginBottom: 6 }}>
                    <strong>Yêu cầu gốc:</strong> {selectedCase.active_evidence_request.reason} ({selectedCase.active_evidence_request.required_image_count} ảnh)
                  </div>
                  {selectedCase.active_evidence_request.customer_note && (
                    <div style={{ fontSize: 13, color: '#78350f', marginBottom: 10 }}>
                      <strong>Ghi chú của khách:</strong> &ldquo;{selectedCase.active_evidence_request.customer_note}&rdquo;
                    </div>
                  )}
                  {/* Grid hình ảnh khách nộp */}
                  <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginTop: 10 }}>
                    {selectedCase.active_evidence_request.evidences && selectedCase.active_evidence_request.evidences.length > 0 ? (
                      selectedCase.active_evidence_request.evidences.map((ev) => (
                        <a
                          key={ev.id}
                          href={ev.file_url}
                          target="_blank"
                          rel="noreferrer"
                          style={{
                            display: 'block',
                            border: '2px solid #f59e0b',
                            borderRadius: 8,
                            overflow: 'hidden',
                            width: 120,
                            height: 120,
                            position: 'relative',
                            boxShadow: '0 2px 4px rgba(0,0,0,0.05)',
                          }}
                        >
                          <img
                            src={ev.file_url}
                            alt={ev.file_name}
                            style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                          />
                        </a>
                      ))
                    ) : (
                      <div style={{ fontSize: 12, color: '#92400e', fontStyle: 'italic' }}>
                        Đã ghi nhận nộp bằng chứng.
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Thông báo đang chờ khách gửi ảnh */}
              {selectedCase.active_evidence_request && selectedCase.status === 'WAITING_CUSTOMER_EVIDENCE' && (
                <div
                  style={{
                    padding: 14,
                    background: '#fff7ed',
                    border: '1px solid #fed7aa',
                    borderRadius: 10,
                    marginBottom: 16,
                    fontSize: 13,
                    color: '#9a3412',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontWeight: 700, marginBottom: 4 }}>
                    <Clock size={16} />
                    <span>Đang chờ khách hàng bổ sung {selectedCase.active_evidence_request.required_image_count} hình ảnh</span>
                  </div>
                  <div>
                    Lý do yêu cầu: {selectedCase.active_evidence_request.reason} • Hạn chót:{' '}
                    {selectedCase.active_evidence_request.expires_at ? formatDateTimeVN(selectedCase.active_evidence_request.expires_at) : '3 ngày'}
                  </div>
                </div>
              )}

              {/* Thông báo quá hạn bổ sung ảnh */}
              {selectedCase.status === 'CANCELLED_EVIDENCE_TIMEOUT' && (
                <div
                  style={{
                    padding: 14,
                    background: '#fef2f2',
                    border: '1px solid #fecaca',
                    borderRadius: 10,
                    marginBottom: 16,
                    fontSize: 13,
                    color: '#991b1b',
                    fontWeight: 600,
                  }}
                >
                  ⚠️ Ca hoàn đã tự động hủy do quá thời hạn 3 ngày khách hàng không bổ sung hình ảnh theo yêu cầu.
                </div>
              )}

              {/* Grid 2 cột thông tin */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 20 }}>
                {/* Thông tin khách hàng & lý do */}
                <div style={{ background: '#f8fafc', padding: 16, borderRadius: 10, border: '1px solid #e2e8f0' }}>
                  <div style={{ fontSize: 12, fontWeight: 700, color: '#475569', marginBottom: 8, textTransform: 'uppercase' }}>
                    Thông tin khách hàng & Yêu cầu
                  </div>
                  <div style={{ fontSize: 13, color: '#1e293b', marginBottom: 4 }}>
                    <strong>Khách hàng:</strong> {selectedCase.customer_name} ({selectedCase.customer_phone})
                  </div>
                  <div style={{ fontSize: 13, color: '#1e293b', marginBottom: 4 }}>
                    <strong>Lý do gửi trả:</strong> {selectedCase.customer_reason}
                  </div>
                  {selectedCase.rejection_reason && (
                    <div style={{ fontSize: 13, color: '#b91c1c', marginTop: 8, fontWeight: 600 }}>
                      ⚠️ Lý do từ chối: {selectedCase.rejection_reason}
                    </div>
                  )}
                </div>

                {/* Thông tin phân công & hoàn tiền */}
                <div style={{ background: '#f8fafc', padding: 16, borderRadius: 10, border: '1px solid #e2e8f0' }}>
                  <div style={{ fontSize: 12, fontWeight: 700, color: '#475569', marginBottom: 8, textTransform: 'uppercase' }}>
                    Nhân sự & Tài chính ca hoàn
                  </div>
                  <div style={{ fontSize: 13, color: '#1e293b', marginBottom: 4 }}>
                    <strong>Nhân viên kiểm hàng:</strong>{' '}
                    {selectedCase.assigned_staff_name ? (
                      <span style={{ color: '#047857', fontWeight: 600 }}>{selectedCase.assigned_staff_name}</span>
                    ) : (
                      <span style={{ color: '#94a3b8' }}>Chưa phân công</span>
                    )}
                  </div>
                  {(selectedCase.refund_info || selectedCase.proposed_refund) && (
                    <div style={{ marginTop: 8, paddingTop: 8, borderTop: '1px dashed #cbd5e1' }}>
                      <div style={{ fontSize: 13, color: '#0f766e', fontWeight: 700 }}>
                        Số tiền hoàn tính toán bởi hệ thống:{' '}
                        {(selectedCase.refund_info?.estimated_refund_amount ?? selectedCase.proposed_refund?.final_proposed_refund ?? 0).toLocaleString('vi-VN')} ₫
                      </div>
                      <div style={{ fontSize: 11, color: '#64748b', marginTop: 2 }}>
                        TK thụ hưởng: {selectedCase.refund_info?.beneficiary_bank || 'Mặc định'} • {selectedCase.refund_info?.beneficiary_account_name || 'Khách hàng'} (
                        {selectedCase.refund_info?.beneficiary_account_number_masked || '—'})
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {/* Danh sách mặt hàng khách yêu cầu trả */}
              <div style={{ marginBottom: 20 }}>
                <h3 style={{ fontSize: 14, fontWeight: 700, color: '#0f172a', marginBottom: 10 }}>
                  1. Danh Sách Thuốc / Dược Phẩm Khách Yêu Cầu Trả Thuộc Kho
                </h3>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12, border: '1px solid #e2e8f0' }}>
                  <thead>
                    <tr style={{ background: '#f1f5f9', color: '#475569', textAlign: 'left' }}>
                      <th style={{ padding: '8px 12px' }}>Tên Sản Phẩm</th>
                      <th style={{ padding: '8px 12px' }}>Mã SKU</th>
                      <th style={{ padding: '8px 12px', textAlign: 'center' }}>SL Khách Yêu Cầu</th>
                      <th style={{ padding: '8px 12px', textAlign: 'right' }}>Đơn Giá Ròng</th>
                      <th style={{ padding: '8px 12px', textAlign: 'right' }}>Thành Tiền</th>
                    </tr>
                  </thead>
                  <tbody>
                    {selectedCase.items.map((it) => (
                      <tr key={it.id} style={{ borderBottom: '1px solid #f1f5f9' }}>
                        <td style={{ padding: '8px 12px', fontWeight: 600 }}>{it.product_name}</td>
                        <td style={{ padding: '8px 12px', color: '#64748b' }}>{it.product_sku || '—'}</td>
                        <td style={{ padding: '8px 12px', textAlign: 'center', fontWeight: 700, color: '#0284c7' }}>
                          {it.requested_quantity}
                        </td>
                        <td style={{ padding: '8px 12px', textAlign: 'right' }}>
                          {(it.unit_price ?? it.net_unit_price ?? 0).toLocaleString('vi-VN')} ₫
                        </td>
                        <td style={{ padding: '8px 12px', textAlign: 'right', fontWeight: 600 }}>
                          {(it.subtotal ?? (it.approved_refund_amount && it.approved_refund_amount > 0 ? it.approved_refund_amount : (it.unit_price ?? it.net_unit_price ?? 0) * (it.requested_quantity ?? 0)) ?? 0).toLocaleString('vi-VN')} ₫
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Biên bản kiểm tra của nhân viên */}
              <div style={{ marginBottom: 20 }}>
                <h3 style={{ fontSize: 14, fontWeight: 700, color: '#0f172a', marginBottom: 10 }}>
                  2. Kết Quả Kiểm Đếm & Đối Chiếu Lô/HSD Của Nhân Viên Kho
                </h3>
                {selectedCase.inspections.length === 0 ? (
                  <div style={{ padding: 16, background: '#f8fafc', borderRadius: 8, color: '#64748b', fontSize: 13 }}>
                    Chưa có biên bản kiểm tra từ nhân viên kho.
                  </div>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                    {selectedCase.inspections.map((insp) => (
                      <div
                        key={insp.id}
                        style={{
                          background: '#f8fafc',
                          padding: 12,
                          borderRadius: 8,
                          border: '1px solid #e2e8f0',
                          fontSize: 12,
                        }}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                          <span style={{ fontWeight: 700, color: '#0f172a' }}>{insp.product_name}</span>
                          <span style={{ color: '#047857', fontWeight: 600 }}>
                            Đề xuất: {insp.suggested_action}
                          </span>
                        </div>
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8, marginBottom: 6 }}>
                          <div>Thực nhận: <strong>{insp.received_quantity}</strong></div>
                          <div>Đề xuất nhận: <strong style={{ color: '#16a34a' }}>{insp.accepted_quantity}</strong></div>
                          <div>Từ chối: <strong style={{ color: '#dc2626' }}>{insp.rejected_quantity}</strong></div>
                          <div>Bao bì: <strong>{insp.package_condition}</strong></div>
                        </div>
                        <div style={{ display: 'flex', gap: 12, fontSize: 11, color: '#475569' }}>
                          <span>Tem niêm phong: {insp.seal_intact ? '✅ Còn nguyên' : '❌ Rách/Mất'}</span>
                          <span>Khớp số lô đã xuất: {insp.batch_matched ? '✅ Khớp lô' : '❌ Sai lô'}</span>
                          <span>Khớp HSD đã xuất: {insp.expiry_matched ? '✅ Khớp HSD' : '❌ Sai HSD'}</span>
                        </div>
                        {insp.damage_description && (
                          <div style={{ marginTop: 4, color: '#b91c1c' }}>Mô tả lỗi: {insp.damage_description}</div>
                        )}
                        {insp.inspection_note && (
                          <div style={{ marginTop: 4, color: '#475569' }}>Ghi chú: {insp.inspection_note}</div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Bằng chứng ảnh/video */}
              {selectedCase.evidences.length > 0 && (
                <div style={{ marginBottom: 20 }}>
                  <h3 style={{ fontSize: 14, fontWeight: 700, color: '#0f172a', marginBottom: 10 }}>
                    3. Hình Ảnh & Video Bằng Chứng Thẩm Định
                  </h3>
                  <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                    {selectedCase.evidences.map((ev) => (
                      <a
                        key={ev.id}
                        href={ev.file_url}
                        target="_blank"
                        rel="noreferrer"
                        style={{
                          display: 'block',
                          border: '1px solid #cbd5e1',
                          borderRadius: 8,
                          overflow: 'hidden',
                          width: 100,
                          height: 100,
                          position: 'relative',
                        }}
                      >
                        <img
                          src={ev.file_url}
                          alt={ev.file_name}
                          style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                        />
                      </a>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Modal Footer Controls for Manager */}
            <div
              style={{
                padding: '14px 24px',
                background: '#f8fafc',
                borderTop: '1px solid #e2e8f0',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                flexWrap: 'wrap',
                gap: 10,
              }}
            >
              <div style={{ display: 'flex', gap: 8 }}>
                {/* 1. Nút Phân công */}
                <button
                  type="button"
                  onClick={() => setShowAssignModal(true)}
                  disabled={actionLoading}
                  style={{
                    padding: '8px 14px',
                    borderRadius: 8,
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
                  <UserCheck size={14} />
                  <span>Phân công NV</span>
                </button>

                {/* Nút Yêu cầu bổ sung hình ảnh */}
                {['ASSIGNED_TO_WAREHOUSE', 'INSPECTING', 'WAITING_MANAGER_APPROVAL'].includes(selectedCase.status) && (
                  <button
                    type="button"
                    onClick={() => setShowRequestEvidenceModal(true)}
                    disabled={actionLoading}
                    style={{
                      padding: '8px 14px',
                      borderRadius: 8,
                      background: '#fff',
                      border: '1px solid #0284c7',
                      color: '#0284c7',
                      fontSize: 12,
                      fontWeight: 600,
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: 6,
                    }}
                  >
                    <ImageIcon size={14} />
                    <span>Yêu cầu khách bổ sung ảnh</span>
                  </button>
                )}

                {/* 2. Nút Yêu cầu kiểm tra lại */}
                {selectedCase.status === 'WAITING_MANAGER_APPROVAL' && (
                  <button
                    type="button"
                    onClick={() => setShowReinspectModal(true)}
                    disabled={actionLoading}
                    style={{
                      padding: '8px 14px',
                      borderRadius: 8,
                      background: '#fff',
                      border: '1px solid #f59e0b',
                      color: '#b45309',
                      fontSize: 12,
                      fontWeight: 600,
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: 6,
                    }}
                  >
                    <RotateCcw size={14} />
                    <span>Yêu cầu kiểm tra lại</span>
                  </button>
                )}
              </div>

              <div style={{ display: 'flex', gap: 8 }}>
                {/* Chấp nhận bằng chứng ảnh khi khách đã nộp */}
                {selectedCase.status === 'WAITING_MANAGER_REVIEW' && (
                  <button
                    type="button"
                    onClick={handleAcceptEvidence}
                    disabled={actionLoading}
                    style={{
                      padding: '8px 18px',
                      borderRadius: 8,
                      background: '#047857',
                      color: '#fff',
                      border: 'none',
                      fontSize: 12,
                      fontWeight: 700,
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: 6,
                    }}
                  >
                    <CheckCircle2 size={14} />
                    <span>Chấp nhận bằng chứng</span>
                  </button>
                )}

                {/* 3. Từ chối hoàn hàng */}
                {['WAITING_MANAGER_APPROVAL', 'INSPECTING'].includes(selectedCase.status) && (
                  <button
                    type="button"
                    onClick={() => setShowRejectModal(true)}
                    disabled={actionLoading}
                    style={{
                      padding: '8px 16px',
                      borderRadius: 8,
                      background: '#fee2e2',
                      border: '1px solid #fecaca',
                      color: '#b91c1c',
                      fontSize: 12,
                      fontWeight: 700,
                      cursor: 'pointer',
                    }}
                  >
                    Từ chối ca hoàn
                  </button>
                )}

                {/* 4. Phê duyệt ca hoàn */}
                {selectedCase.status === 'WAITING_MANAGER_APPROVAL' && (
                  <button
                    type="button"
                    onClick={handleApproveCase}
                    disabled={actionLoading}
                    style={{
                      padding: '8px 18px',
                      borderRadius: 8,
                      background: '#047857',
                      color: '#fff',
                      border: 'none',
                      fontSize: 12,
                      fontWeight: 700,
                      cursor: 'pointer',
                    }}
                  >
                    Phê duyệt ca hoàn
                  </button>
                )}

                {/* 5. Hoàn tiền cho khách */}
                {['APPROVED', 'REFUND_PENDING', 'REFUND_FAILED'].includes(selectedCase.status) && (
                  <button
                    type="button"
                    onClick={() => setShowRefundModal(true)}
                    disabled={actionLoading}
                    style={{
                      padding: '8px 18px',
                      borderRadius: 8,
                      background: '#0284c7',
                      color: '#fff',
                      border: 'none',
                      fontSize: 12,
                      fontWeight: 700,
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: 6,
                    }}
                  >
                    <DollarSign size={14} />
                    <span>Thực hiện hoàn tiền</span>
                  </button>
                )}

                {/* 6. Phân luồng kho (Restock / Quarantine / Dispose) */}
                {['REFUNDED', 'APPROVED'].includes(selectedCase.status) && (
                  <button
                    type="button"
                    onClick={() => setShowDispositionModal(true)}
                    disabled={actionLoading}
                    style={{
                      padding: '8px 18px',
                      borderRadius: 8,
                      background: '#4338ca',
                      color: '#fff',
                      border: 'none',
                      fontSize: 12,
                      fontWeight: 700,
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: 6,
                    }}
                  >
                    <Boxes size={14} />
                    <span>Xử lý nhập kho / Phân luồng</span>
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* MODAL PHÂN CÔNG NHÂN VIÊN */}
      {showAssignModal && (
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
          <div style={{ background: '#fff', borderRadius: 12, width: '100%', maxWidth: 420, padding: 24 }}>
            <h3 style={{ fontSize: 16, fontWeight: 700, margin: '0 0 12px 0' }}>Phân Công Nhân Viên Kiểm Hàng</h3>
            <p style={{ fontSize: 13, color: '#64748b', margin: '0 0 16px 0' }}>
              Chọn nhân viên kho chịu trách nhiệm tiếp nhận gói hàng và thẩm định số lô, HSD thực tế:
            </p>
            <select
              value={assignStaffId}
              onChange={(e) => setAssignStaffId(e.target.value ? Number(e.target.value) : '')}
              style={{
                width: '100%',
                padding: '10px 12px',
                borderRadius: 8,
                border: '1px solid #cbd5e1',
                fontSize: 14,
                marginBottom: 20,
              }}
            >
              <option value="">-- Chọn nhân viên thuộc kho --</option>
              {staffList.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.full_name} ({s.phone})
                </option>
              ))}
            </select>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
              <button
                type="button"
                onClick={() => setShowAssignModal(false)}
                className="admin-button button-secondary"
              >
                Hủy
              </button>
              <button
                type="button"
                onClick={handleAssignStaff}
                disabled={!assignStaffId || actionLoading}
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
                Xác nhận
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL YÊU CẦU KIỂM TRA LẠI */}
      {showReinspectModal && (
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
            <h3 style={{ fontSize: 16, fontWeight: 700, margin: '0 0 12px 0' }}>Yêu Cầu Nhân Viên Kiểm Tra Lại</h3>
            <p style={{ fontSize: 13, color: '#64748b', margin: '0 0 16px 0' }}>
              Nhập lý do hoặc chỉ dẫn chi tiết để nhân viên kho đối chiếu lại số lô, tem mác hoặc chụp lại ảnh:
            </p>
            <textarea
              rows={4}
              value={reinspectReason}
              onChange={(e) => setReinspectReason(e.target.value)}
              placeholder="Nhập lý do bắt buộc (tối thiểu 5 ký tự)..."
              style={{
                width: '100%',
                padding: '10px 12px',
                borderRadius: 8,
                border: '1px solid #cbd5e1',
                fontSize: 14,
                marginBottom: 20,
              }}
            />
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
              <button
                type="button"
                onClick={() => setShowReinspectModal(false)}
                className="admin-button button-secondary"
              >
                Hủy
              </button>
              <button
                type="button"
                onClick={handleRequestReinspection}
                disabled={reinspectReason.trim().length < 5 || actionLoading}
                style={{
                  padding: '8px 18px',
                  background: '#b45309',
                  color: '#fff',
                  border: 'none',
                  borderRadius: 8,
                  fontWeight: 600,
                  cursor: 'pointer',
                }}
              >
                Gửi yêu cầu
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL TỪ CHỐI CA HOÀN */}
      {showRejectModal && (
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
            <h3 style={{ fontSize: 16, fontWeight: 700, margin: '0 0 12px 0', color: '#b91c1c' }}>
              Từ Chối Ca Hoàn Hàng
            </h3>
            <p style={{ fontSize: 13, color: '#64748b', margin: '0 0 16px 0' }}>
              Lý do từ chối là bắt buộc và sẽ được lưu vào biên bản kiểm toán đồng thời thông báo cho khách hàng:
            </p>
            <textarea
              rows={4}
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
              placeholder="Nhập lý do từ chối (tối thiểu 5 ký tự)..."
              style={{
                width: '100%',
                padding: '10px 12px',
                borderRadius: 8,
                border: '1px solid #cbd5e1',
                fontSize: 14,
                marginBottom: 20,
              }}
            />
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
              <button
                type="button"
                onClick={() => setShowRejectModal(false)}
                className="admin-button button-secondary"
              >
                Hủy
              </button>
              <button
                type="button"
                onClick={handleRejectCase}
                disabled={rejectReason.trim().length < 5 || actionLoading}
                style={{
                  padding: '8px 18px',
                  background: '#b91c1c',
                  color: '#fff',
                  border: 'none',
                  borderRadius: 8,
                  fontWeight: 600,
                  cursor: 'pointer',
                }}
              >
                Xác nhận từ chối
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL HOÀN TIỀN BẢO MẬT (Xác thực Mật khẩu) */}
      {showRefundModal && (
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
          <div style={{ background: '#fff', borderRadius: 12, width: '100%', maxWidth: 480, padding: 24 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
              <Lock size={20} style={{ color: '#0284c7' }} />
              <h3 style={{ fontSize: 16, fontWeight: 700, margin: 0 }}>Xác Nhận Hoàn Tiền Cho Khách Hàng</h3>
            </div>

            <div style={{ padding: 12, background: '#f0fdfa', borderRadius: 8, border: '1px solid #ccfbf1', marginBottom: 16 }}>
              <div style={{ fontSize: 12, color: '#0f766e', fontWeight: 600 }}>SỐ TIỀN HOÀN TÍNH BỞI HỆ THỐNG:</div>
              <div style={{ fontSize: 20, fontWeight: 800, color: '#047857', marginTop: 2 }}>
                {(selectedCase?.refund_info?.estimated_refund_amount ?? selectedCase?.proposed_refund?.final_proposed_refund ?? 0).toLocaleString('vi-VN')} ₫
              </div>
              <div style={{ fontSize: 11, color: '#64748b', marginTop: 4 }}>
                * Số tiền được tính toán tự động dựa trên đơn giá ròng sau chiết khấu của các mặt hàng được duyệt. Quản lý kho không được tự ý sửa số tiền này.
              </div>
            </div>

            <div style={{ marginBottom: 14 }}>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: '#334155', marginBottom: 6 }}>
                Phương thức hoàn tiền:
              </label>
              <select
                value={refundMethod}
                onChange={(e) => setRefundMethod(e.target.value)}
                style={{
                  width: '100%',
                  padding: '9px 12px',
                  borderRadius: 8,
                  border: '1px solid #cbd5e1',
                  fontSize: 13,
                }}
              >
                <option value="BANK_TRANSFER">Chuyển khoản ngân hàng</option>
                <option value="WALLET">Ví điện tử / Cổng thanh toán gốc</option>
                <option value="CASH">Tiền mặt tại quầy kho</option>
              </select>
            </div>

            <div style={{ marginBottom: 14 }}>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: '#334155', marginBottom: 6 }}>
                Mã tham chiếu chuyển khoản (Nếu có):
              </label>
              <input
                type="text"
                value={manualRefNo}
                onChange={(e) => setManualRefNo(e.target.value)}
                placeholder="VD: FT241013892..."
                style={{
                  width: '100%',
                  padding: '9px 12px',
                  borderRadius: 8,
                  border: '1px solid #cbd5e1',
                  fontSize: 13,
                }}
              />
            </div>

            <div style={{ marginBottom: 20 }}>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 700, color: '#991b1b', marginBottom: 6 }}>
                Nhập mật khẩu tài khoản Quản lý để xác thực giao dịch tài chính:
              </label>
              <input
                type="password"
                value={managerPassword}
                onChange={(e) => setManagerPassword(e.target.value)}
                placeholder="Nhập mật khẩu đăng nhập của bạn..."
                style={{
                  width: '100%',
                  padding: '10px 12px',
                  borderRadius: 8,
                  border: '1px solid #f87171',
                  fontSize: 14,
                }}
              />
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
              <button
                type="button"
                onClick={() => {
                  setShowRefundModal(false)
                  setManagerPassword('')
                }}
                className="admin-button button-secondary"
              >
                Hủy
              </button>
              <button
                type="button"
                onClick={handleProcessRefund}
                disabled={!managerPassword || actionLoading}
                style={{
                  padding: '9px 20px',
                  background: '#0284c7',
                  color: '#fff',
                  border: 'none',
                  borderRadius: 8,
                  fontWeight: 700,
                  cursor: 'pointer',
                }}
              >
                Xác nhận hoàn tiền
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL PHÂN LUỒNG KHO (RESTOCK / QUARANTINE / DISPOSE) */}
      {showDispositionModal && (
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
          <div style={{ background: '#fff', borderRadius: 12, width: '100%', maxWidth: 480, padding: 24 }}>
            <h3 style={{ fontSize: 16, fontWeight: 700, margin: '0 0 12px 0' }}>Xử Lý Phân Luồng Tồn Kho Thuốc</h3>
            <p style={{ fontSize: 13, color: '#64748b', margin: '0 0 16px 0' }}>
              Quyết định trạng thái lưu kho sau khi hoàn tất kiểm tra và hoàn tiền:
            </p>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginBottom: 16 }}>
              {[
                {
                  id: 'RESTOCK',
                  label: 'Nhập lại kho khả dụng (RESTOCK)',
                  desc: 'Thuốc còn nguyên tem mác, đạt chuẩn GSP, tăng tồn kho khả dụng để bán tiếp.',
                },
                {
                  id: 'QUARANTINE',
                  label: 'Chuyển vào khu cách ly (QUARANTINE)',
                  desc: 'Thuốc cần theo dõi thêm hoặc chờ nhà sản xuất thẩm định.',
                },
                {
                  id: 'DISPOSE',
                  label: 'Tiêu hủy thuốc (DISPOSE)',
                  desc: 'Thuốc bị rách niêm phong, nhiễm bẩn hoặc cận hạn, xuất hủy theo biên bản.',
                },
              ].map((opt) => (
                <label
                  key={opt.id}
                  style={{
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: 10,
                    padding: 12,
                    borderRadius: 8,
                    border: dispositionChoice === opt.id ? '2px solid #4338ca' : '1px solid #e2e8f0',
                    background: dispositionChoice === opt.id ? '#eef2ff' : '#fff',
                    cursor: 'pointer',
                  }}
                >
                  <input
                    type="radio"
                    name="disposition"
                    checked={dispositionChoice === opt.id}
                    onChange={() => setDispositionChoice(opt.id as any)}
                    style={{ marginTop: 3 }}
                  />
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 700, color: '#1e293b' }}>{opt.label}</div>
                    <div style={{ fontSize: 11, color: '#64748b' }}>{opt.desc}</div>
                  </div>
                </label>
              ))}
            </div>

            <div style={{ marginBottom: 20 }}>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: '#334155', marginBottom: 6 }}>
                Ghi chú phân luồng (Tùy chọn):
              </label>
              <textarea
                rows={3}
                value={dispositionNote}
                onChange={(e) => setDispositionNote(e.target.value)}
                placeholder="Ghi chú vị trí kệ hoặc biên bản hủy..."
                style={{
                  width: '100%',
                  padding: '9px 12px',
                  borderRadius: 8,
                  border: '1px solid #cbd5e1',
                  fontSize: 13,
                }}
              />
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
              <button
                type="button"
                onClick={() => setShowDispositionModal(false)}
                className="admin-button button-secondary"
              >
                Hủy
              </button>
              <button
                type="button"
                onClick={handleStockDisposition}
                disabled={actionLoading}
                style={{
                  padding: '9px 20px',
                  background: '#4338ca',
                  color: '#fff',
                  border: 'none',
                  borderRadius: 8,
                  fontWeight: 700,
                  cursor: 'pointer',
                }}
              >
                Xác nhận phân luồng
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL YÊU CẦU KHÁCH BỔ SUNG HÌNH ẢNH */}
      {showRequestEvidenceModal && selectedCase && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(15, 23, 42, 0.65)',
            backdropFilter: 'blur(3px)',
            zIndex: 1100,
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
              maxWidth: 540,
              borderRadius: 16,
              overflow: 'hidden',
              boxShadow: '0 25px 50px -12px rgba(0,0,0,0.25)',
            }}
          >
            <div
              style={{
                padding: '16px 20px',
                background: '#0f172a',
                color: '#fff',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
              }}
            >
              <h3 style={{ fontSize: 16, fontWeight: 700, margin: 0, display: 'flex', alignItems: 'center', gap: 8 }}>
                <ImageIcon size={18} />
                <span>Yêu Cầu Khách Bổ Sung Hình Ảnh</span>
              </h3>
              <button
                type="button"
                onClick={() => setShowRequestEvidenceModal(false)}
                style={{ background: 'none', border: 'none', color: '#94a3b8', cursor: 'pointer' }}
              >
                <X size={18} />
              </button>
            </div>

            <div style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 14 }}>
              <div>
                <label style={{ fontSize: 12, fontWeight: 700, color: '#334155', display: 'block', marginBottom: 6 }}>
                  Số lượng ảnh bắt buộc khách phải nộp (1 - 3 ảnh):
                </label>
                <div style={{ display: 'flex', gap: 12 }}>
                  {[1, 2, 3].map((count) => (
                    <label
                      key={count}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 6,
                        fontSize: 13,
                        cursor: 'pointer',
                        padding: '6px 14px',
                        borderRadius: 8,
                        border: evidenceRequiredCount === count ? '2px solid #0284c7' : '1px solid #cbd5e1',
                        background: evidenceRequiredCount === count ? '#f0f9ff' : '#fff',
                        fontWeight: evidenceRequiredCount === count ? 700 : 500,
                      }}
                    >
                      <input
                        type="radio"
                        name="evidenceCount"
                        checked={evidenceRequiredCount === count}
                        onChange={() => setEvidenceRequiredCount(count)}
                      />
                      <span>{count} ảnh</span>
                    </label>
                  ))}
                </div>
              </div>

              {selectedCase.items.length > 1 && (
                <div>
                  <label style={{ fontSize: 12, fontWeight: 700, color: '#334155', display: 'block', marginBottom: 6 }}>
                    Chỉ định sản phẩm cần bằng chứng (tùy chọn):
                  </label>
                  <select
                    value={evidenceItemId}
                    onChange={(e) => setEvidenceItemId(e.target.value ? Number(e.target.value) : '')}
                    style={{ width: '100%', padding: '8px 12px', borderRadius: 8, border: '1px solid #cbd5e1', fontSize: 13 }}
                  >
                    <option value="">Tất cả / Toàn bộ đơn hoàn</option>
                    {selectedCase.items.map((it) => (
                      <option key={it.id} value={it.id}>
                        {it.product_name} (SL: {it.requested_quantity})
                      </option>
                    ))}
                  </select>
                </div>
              )}

              <div>
                <label style={{ fontSize: 12, fontWeight: 700, color: '#334155', display: 'block', marginBottom: 6 }}>
                  Lý do yêu cầu bổ sung ảnh <span style={{ color: '#dc2626' }}>*</span>:
                </label>
                <input
                  type="text"
                  placeholder="VD: Tem niêm phong mờ, bao bì hộp bị móp rách..."
                  value={evidenceReason}
                  onChange={(e) => setEvidenceReason(e.target.value)}
                  style={{ width: '100%', padding: '8px 12px', borderRadius: 8, border: '1px solid #cbd5e1', fontSize: 13 }}
                />
              </div>

              <div>
                <label style={{ fontSize: 12, fontWeight: 700, color: '#334155', display: 'block', marginBottom: 6 }}>
                  Hướng dẫn khách chụp ảnh chi tiết <span style={{ color: '#dc2626' }}>*</span>:
                </label>
                <textarea
                  rows={3}
                  placeholder="VD: Chụp rõ 2 góc cạnh của tem niêm phong và đáy hộp có in rõ số lô, hạn sử dụng..."
                  value={evidenceInstructions}
                  onChange={(e) => setEvidenceInstructions(e.target.value)}
                  style={{ width: '100%', padding: '8px 12px', borderRadius: 8, border: '1px solid #cbd5e1', fontSize: 13, resize: 'vertical' }}
                />
              </div>

              <div style={{ padding: '10px 14px', background: '#f8fafc', borderRadius: 8, fontSize: 12, color: '#64748b' }}>
                ⏱️ Khách hàng sẽ có thời hạn <strong>3 ngày</strong> kể từ lúc gửi để nộp đủ số ảnh. Nếu quá 3 ngày khách không gửi, đơn hoàn sẽ tự động bị hủy theo quy định.
              </div>
            </div>

            <div style={{ padding: '14px 20px', background: '#f8fafc', borderTop: '1px solid #e2e8f0', display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
              <button
                type="button"
                onClick={() => setShowRequestEvidenceModal(false)}
                disabled={actionLoading}
                style={{ padding: '8px 16px', borderRadius: 8, background: '#fff', border: '1px solid #cbd5e1', fontSize: 12, fontWeight: 600, cursor: 'pointer' }}
              >
                Hủy bỏ
              </button>
              <button
                type="button"
                onClick={handleRequestEvidence}
                disabled={actionLoading || !evidenceReason.trim() || !evidenceInstructions.trim()}
                style={{
                  padding: '8px 18px',
                  borderRadius: 8,
                  background: '#0284c7',
                  color: '#fff',
                  border: 'none',
                  fontSize: 12,
                  fontWeight: 700,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 6,
                }}
              >
                {actionLoading ? 'Đang gửi...' : 'Gửi yêu cầu tới khách'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
