import { useEffect, useState } from 'react'
import {
  RotateCcw,
  Search,
  CheckCircle2,
  Package,
  Eye,
  X,
  AlertTriangle,
  Upload,
  Image as ImageIcon,
  AlertCircle,
  Truck,
  CheckSquare,
  ShieldCheck,
  Send,
  Save,
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
  condition_reported: string
  customer_reason?: string
}

interface ReturnEvidenceItem {
  id: number
  file_url: string
  file_name: string
  evidence_type: string
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
}

interface StaffReturnCase {
  id: number
  case_code: string
  return_code: string
  order_code: string
  status: string
  customer_name: string
  customer_phone: string
  customer_reason: string
  items_count: number
  created_at: string | null
  items: ReturnCaseItem[]
  inspections: InspectionRecord[]
  evidences: ReturnEvidenceItem[]
}

const STATUS_CONFIG: Record<string, { label: string; bg: string; color: string }> = {
  ASSIGNED_TO_WAREHOUSE: { label: 'Chờ nhận hàng từ bưu tá', bg: '#e0f2fe', color: '#0369a1' },
  IN_TRANSIT: { label: 'Bưu tá đang giao tới kho', bg: '#e0f2fe', color: '#0284c7' },
  RECEIVED: { label: 'Đã nhận tại kho (Cần kiểm)', bg: '#dbeafe', color: '#1d4ed8' },
  INSPECTING: { label: 'Đang kiểm hàng & đối chiếu', bg: '#f3e8ff', color: '#7c3aed' },
  WAITING_MANAGER_APPROVAL: { label: 'Đã nộp biên bản (Chờ QL duyệt)', bg: '#fff7ed', color: '#ea580c' },
  APPROVED: { label: 'Quản lý đã duyệt', bg: '#dcfce7', color: '#166534' },
  REJECTED: { label: 'Quản lý đã từ chối', bg: '#fee2e2', color: '#b91c1c' },
  REFUND_PENDING: { label: 'Chờ hoàn tiền', bg: '#cffafe', color: '#0e7490' },
  REFUNDED: { label: 'Đã hoàn tiền', bg: '#bbf7d0', color: '#15803d' },
  RESTOCKED: { label: 'Đã nhập kho', bg: '#dcfce7', color: '#16a34a' },
  CLOSED: { label: 'Hồ sơ đã đóng', bg: '#f8fafc', color: '#334155' },
}

export function StaffReturnsPage() {
  const [cases, setCases] = useState<StaffReturnCase[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')

  // Detail Modal
  const [selectedCase, setSelectedCase] = useState<StaffReturnCase | null>(null)
  const [loadingDetail, setLoadingDetail] = useState(false)
  const [actionLoading, setActionLoading] = useState(false)
  const [actionError, setActionError] = useState('')
  const [actionSuccess, setActionSuccess] = useState('')

  // Step 1: Receive Form
  const [carrierName, setCarrierName] = useState('Viettel Post')
  const [trackingCode, setTrackingCode] = useState('')
  const [receivePackageCond, setReceivePackageCond] = useState('SEALED')
  const [receiveNote, setReceiveNote] = useState('')

  // Step 2: Evidence Upload Mock
  const [uploadUrl, setUploadUrl] = useState('')

  // Step 3: Inspections Form
  const [inspectionDrafts, setInspectionDrafts] = useState<
    Record<
      number,
      {
        received_quantity: number
        accepted_quantity: number
        rejected_quantity: number
        package_condition: string
        seal_intact: boolean
        batch_matched: boolean
        expiry_matched: boolean
        damage_description: string
        suggested_action: string
        inspection_note: string
      }
    >
  >({})

  const fetchCases = async () => {
    setLoading(true)
    try {
      const res = await api<{ items: StaffReturnCase[] }>('/warehouse/staff/me/returns')
      setCases(res.items || [])
    } catch (err: any) {
      console.error('Lỗi tải danh sách ca hoàn phân công cho nhân viên:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchCases()
  }, [])

  const openCaseDetail = async (caseCode: string) => {
    setLoadingDetail(true)
    setActionError('')
    setActionSuccess('')
    try {
      const res = await api<StaffReturnCase>(`/warehouse/staff/me/returns/${caseCode}`)
      setSelectedCase(res)

      // Khởi tạo draft kiểm hàng từ danh sách items
      const initialDrafts: Record<number, any> = {}
      res.items.forEach((item) => {
        const existingInsp = res.inspections.find((i) => i.return_item_id === item.id)
        if (existingInsp) {
          initialDrafts[item.id] = {
            received_quantity: existingInsp.received_quantity,
            accepted_quantity: existingInsp.accepted_quantity,
            rejected_quantity: existingInsp.rejected_quantity,
            package_condition: existingInsp.package_condition,
            seal_intact: existingInsp.seal_intact,
            batch_matched: existingInsp.batch_matched,
            expiry_matched: existingInsp.expiry_matched,
            damage_description: existingInsp.damage_description || '',
            suggested_action: existingInsp.suggested_action,
            inspection_note: existingInsp.inspection_note || '',
          }
        } else {
          initialDrafts[item.id] = {
            received_quantity: item.requested_quantity,
            accepted_quantity: item.requested_quantity,
            rejected_quantity: 0,
            package_condition: 'SEALED',
            seal_intact: true,
            batch_matched: true,
            expiry_matched: true,
            damage_description: '',
            suggested_action: 'RESTOCK',
            inspection_note: '',
          }
        }
      })
      setInspectionDrafts(initialDrafts)
    } catch (err: any) {
      alert('Không thể mở chi tiết ca hoàn: ' + (err?.message || 'Lỗi mạng'))
    } finally {
      setLoadingDetail(false)
    }
  }

  // 1. Xác nhận nhận hàng từ bưu tá
  const handleReceiveGoods = async () => {
    if (!selectedCase) return
    setActionLoading(true)
    setActionError('')
    try {
      await api(`/warehouse/staff/me/returns/${selectedCase.case_code}/receive`, {
        method: 'POST',
        body: JSON.stringify({
          carrier_name: carrierName,
          tracking_code: trackingCode,
          package_condition: receivePackageCond,
          note: receiveNote,
        }),
      })
      setActionSuccess('Đã xác nhận nhận gói hàng từ bưu tá! Ca hoàn đã chuyển sang trạng thái "Đang kiểm hàng".')
      await openCaseDetail(selectedCase.case_code)
      await fetchCases()
    } catch (err: any) {
      setActionError(err?.message || 'Lỗi khi tiếp nhận gói hàng.')
    } finally {
      setActionLoading(false)
    }
  }

  // 2. Tải ảnh bằng chứng
  const handleAddEvidence = async () => {
    if (!selectedCase || !uploadUrl.trim()) return
    setActionLoading(true)
    setActionError('')
    try {
      await api(`/warehouse/staff/me/returns/${selectedCase.case_code}/evidence`, {
        method: 'POST',
        body: JSON.stringify({
          file_url: uploadUrl.trim(),
          file_name: `evidence_${Date.now()}.jpg`,
          file_category: 'INSPECTION_PHOTO',
        }),
      })
      setActionSuccess('Đã đính kèm ảnh bằng chứng thành công!')
      setUploadUrl('')
      await openCaseDetail(selectedCase.case_code)
    } catch (err: any) {
      setActionError(err?.message || 'Lỗi khi tải ảnh bằng chứng.')
    } finally {
      setActionLoading(false)
    }
  }

  // 3. Lưu biên bản kiểm đếm
  const handleSaveInspection = async () => {
    if (!selectedCase) return
    setActionLoading(true)
    setActionError('')
    try {
      const payloadItems = Object.entries(inspectionDrafts).map(([itemIdStr, draft]) => ({
        return_item_id: Number(itemIdStr),
        received_quantity: draft.received_quantity,
        accepted_quantity: draft.accepted_quantity,
        rejected_quantity: draft.rejected_quantity,
        package_condition: draft.package_condition,
        seal_intact: draft.seal_intact,
        batch_matched: draft.batch_matched,
        expiry_matched: draft.expiry_matched,
        damage_description: draft.damage_description,
        suggested_action: draft.suggested_action,
        inspection_note: draft.inspection_note,
      }))

      await api(`/warehouse/staff/me/returns/${selectedCase.case_code}/inspect`, {
        method: 'POST',
        body: JSON.stringify({ inspections: payloadItems }),
      })
      setActionSuccess('Đã lưu kết quả kiểm đếm và đối chiếu số lô thành công!')
      await openCaseDetail(selectedCase.case_code)
      await fetchCases()
    } catch (err: any) {
      setActionError(err?.message || 'Lỗi khi lưu biên bản kiểm đếm.')
    } finally {
      setActionLoading(false)
    }
  }

  // 4. Nộp biên bản lên Quản lý kho
  const handleSubmitToManager = async () => {
    if (!selectedCase) return
    if (
      !confirm(
        'Bạn có chắc chắn đã kiểm đếm, đối chiếu số lô và chụp đầy đủ ảnh bằng chứng để nộp lên Quản lý kho duyệt?'
      )
    )
      return
    setActionLoading(true)
    setActionError('')
    try {
      await api(`/warehouse/staff/me/returns/${selectedCase.case_code}/submit`, {
        method: 'POST',
        body: JSON.stringify({ note: 'Nhân viên đã kiểm tra hoàn tất và nộp biên bản.' }),
      })
      setActionSuccess('Đã nộp biên bản kiểm hàng lên Quản lý kho thành công!')
      await openCaseDetail(selectedCase.case_code)
      await fetchCases()
    } catch (err: any) {
      setActionError(err?.message || 'Lỗi khi nộp biên bản.')
    } finally {
      setActionLoading(false)
    }
  }

  return (
    <div style={{ padding: '20px', maxWidth: '1300px', margin: '0 auto' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 800, color: '#0f172a', margin: '0 0 6px 0' }}>
            8. Hàng Đổi Trả Được Phân Công (Bàn Tiếp Nhận & Kiểm Định)
          </h1>
          <p style={{ margin: 0, fontSize: 13, color: '#64748b' }}>
            Tiếp nhận kiện hàng từ bưu tá, kiểm tra tem niêm phong, đối chiếu số lô/HSD với đơn xuất và nộp biên bản cho Quản lý.
          </p>
        </div>
        <button
          type="button"
          onClick={() => fetchCases()}
          className="admin-button button-secondary"
          style={{ display: 'flex', alignItems: 'center', gap: 6 }}
        >
          <RotateCcw size={14} />
          <span>Làm mới danh sách</span>
        </button>
      </div>

      {/* Table of Assigned Cases */}
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
            <div>Đang tải danh sách ca hoàn được phân công...</div>
          </div>
        ) : cases.length === 0 ? (
          <div style={{ padding: 60, textAlign: 'center', color: '#64748b' }}>
            <Package size={40} style={{ margin: '0 auto 12px', opacity: 0.3 }} />
            <div style={{ fontSize: 16, fontWeight: 600, color: '#334155' }}>
              Hiện chưa có ca hoàn nào được phân công cho bạn
            </div>
            <p style={{ margin: '4px 0 0', fontSize: 13 }}>
              Khi Quản lý kho phân công ca hoàn, bạn sẽ nhận được thông báo và xem chi tiết tại đây.
            </p>
          </div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: 13 }}>
            <thead>
              <tr style={{ background: '#f8fafc', borderBottom: '1px solid #e2e8f0', color: '#475569' }}>
                <th style={{ padding: '12px 16px', fontWeight: 600 }}>Mã Ca Hoàn</th>
                <th style={{ padding: '12px 16px', fontWeight: 600 }}>Đơn Hàng & YC Gốc</th>
                <th style={{ padding: '12px 16px', fontWeight: 600 }}>Khách Hàng</th>
                <th style={{ padding: '12px 16px', fontWeight: 600 }}>Trạng Thái</th>
                <th style={{ padding: '12px 16px', fontWeight: 600 }}>Số Loại Thuốc</th>
                <th style={{ padding: '12px 16px', fontWeight: 600 }}>Thời Gian Nhận Việc</th>
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
                      <div style={{ fontWeight: 600, color: '#0284c7' }}>{c.order_code}</div>
                      <div style={{ fontSize: 11, color: '#64748b' }}>{c.return_code}</div>
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
                          background: '#047857',
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
                        <CheckSquare size={13} />
                        <span>Mở bàn kiểm hàng</span>
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </div>

      {/* MODAL CHI TIẾT KIỂM HÀNG CỦA NHÂN VIÊN */}
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
              maxWidth: 980,
              maxHeight: '94vh',
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
                padding: '16px 24px',
                background: '#047857',
                color: '#fff',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
              }}
            >
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <h2 style={{ fontSize: 18, fontWeight: 800, margin: 0 }}>
                    Bàn Thẩm Định & Kiểm Đếm Ca Hoàn: {selectedCase.case_code}
                  </h2>
                  <span
                    style={{
                      padding: '3px 10px',
                      borderRadius: 12,
                      fontSize: 11,
                      fontWeight: 700,
                      background: '#fff',
                      color: '#047857',
                    }}
                  >
                    {STATUS_CONFIG[selectedCase.status]?.label || selectedCase.status}
                  </span>
                </div>
                <div style={{ fontSize: 12, opacity: 0.9, marginTop: 4 }}>
                  Đơn: {selectedCase.order_code} • Khách hàng: {selectedCase.customer_name} ({selectedCase.customer_phone})
                </div>
              </div>
              <button
                type="button"
                onClick={() => setSelectedCase(null)}
                style={{ background: 'none', border: 'none', color: '#fff', cursor: 'pointer' }}
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

              {/* BƯỚC 1: TIẾP NHẬN HÀNG TỪ BƯU TÁ (Nếu chưa nhận) */}
              {['ASSIGNED_TO_WAREHOUSE', 'IN_TRANSIT', 'WAITING_CUSTOMER_SHIPMENT'].includes(selectedCase.status) && (
                <div
                  style={{
                    padding: 16,
                    background: '#f0fdf4',
                    borderRadius: 10,
                    border: '1px solid #bbf7d0',
                    marginBottom: 20,
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10, color: '#166534' }}>
                    <Truck size={18} />
                    <h3 style={{ margin: 0, fontSize: 15, fontWeight: 700 }}>
                      Bước 1: Tiếp Nhận Kiện Hàng Từ Đơn Vị Vận Chuyển
                    </h3>
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginBottom: 12 }}>
                    <div>
                      <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: '#334155', marginBottom: 4 }}>
                        Đơn vị vận chuyển:
                      </label>
                      <input
                        type="text"
                        value={carrierName}
                        onChange={(e) => setCarrierName(e.target.value)}
                        style={{ width: '100%', padding: '8px 10px', borderRadius: 6, border: '1px solid #cbd5e1', fontSize: 13 }}
                      />
                    </div>
                    <div>
                      <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: '#334155', marginBottom: 4 }}>
                        Mã vận đơn giao hàng:
                      </label>
                      <input
                        type="text"
                        value={trackingCode}
                        onChange={(e) => setTrackingCode(e.target.value)}
                        placeholder="VD: VT123456789"
                        style={{ width: '100%', padding: '8px 10px', borderRadius: 6, border: '1px solid #cbd5e1', fontSize: 13 }}
                      />
                    </div>
                    <div>
                      <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: '#334155', marginBottom: 4 }}>
                        Tình trạng gói bưu phẩm:
                      </label>
                      <select
                        value={receivePackageCond}
                        onChange={(e) => setReceivePackageCond(e.target.value)}
                        style={{ width: '100%', padding: '8px 10px', borderRadius: 6, border: '1px solid #cbd5e1', fontSize: 13 }}
                      >
                        <option value="SEALED">Nguyên vẹn hộp niêm phong</option>
                        <option value="DAMAGED">Bẹp méo / Rách bao bì bên ngoài</option>
                        <option value="OPENED">Có dấu hiệu đã bị xé / bóc mở</option>
                      </select>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={handleReceiveGoods}
                    disabled={actionLoading}
                    style={{
                      padding: '8px 16px',
                      background: '#047857',
                      color: '#fff',
                      border: 'none',
                      borderRadius: 6,
                      fontWeight: 600,
                      cursor: 'pointer',
                    }}
                  >
                    Xác nhận nhận kiện hàng
                  </button>
                </div>
              )}

              {/* BƯỚC 2: BẰNG CHỨNG HÌNH ẢNH */}
              <div
                style={{
                  padding: 16,
                  background: '#f8fafc',
                  borderRadius: 10,
                  border: '1px solid #e2e8f0',
                  marginBottom: 20,
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
                  <ImageIcon size={18} style={{ color: '#0284c7' }} />
                  <h3 style={{ margin: 0, fontSize: 15, fontWeight: 700, color: '#0f172a' }}>
                    Bước 2: Hình Ảnh & Bằng Chứng Thẩm Định Thực Tế
                  </h3>
                </div>
                <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 12 }}>
                  {selectedCase.evidences.map((ev) => (
                    <div
                      key={ev.id}
                      style={{
                        width: 80,
                        height: 80,
                        borderRadius: 6,
                        border: '1px solid #cbd5e1',
                        overflow: 'hidden',
                        position: 'relative',
                      }}
                    >
                      <img src={ev.file_url} alt={ev.file_name} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                    </div>
                  ))}
                  {selectedCase.evidences.length === 0 && (
                    <div style={{ fontSize: 12, color: '#94a3b8', fontStyle: 'italic' }}>
                      Chưa có ảnh bằng chứng nào được tải lên.
                    </div>
                  )}
                </div>

                <div style={{ display: 'flex', gap: 10 }}>
                  <input
                    type="text"
                    value={uploadUrl}
                    onChange={(e) => setUploadUrl(e.target.value)}
                    placeholder="Dán link ảnh chụp số lô / tem niêm phong / vỏ hộp thuốc..."
                    style={{
                      flex: 1,
                      padding: '8px 12px',
                      borderRadius: 6,
                      border: '1px solid #cbd5e1',
                      fontSize: 13,
                    }}
                  />
                  <button
                    type="button"
                    onClick={handleAddEvidence}
                    disabled={!uploadUrl.trim() || actionLoading}
                    style={{
                      padding: '8px 16px',
                      background: '#0284c7',
                      color: '#fff',
                      border: 'none',
                      borderRadius: 6,
                      fontWeight: 600,
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: 6,
                    }}
                  >
                    <Upload size={14} />
                    <span>Đính kèm ảnh</span>
                  </button>
                </div>
              </div>

              {/* BƯỚC 3: BIÊN BẢN KIỂM ĐẾM & ĐỐI CHIẾU SỐ LÔ / HSD */}
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                  <h3 style={{ margin: 0, fontSize: 15, fontWeight: 700, color: '#0f172a' }}>
                    Bước 3: Biên Bản Kiểm Đếm, Tình Trạng Tem & Đối Chiếu Lô/HSD
                  </h3>
                  <button
                    type="button"
                    onClick={handleSaveInspection}
                    disabled={actionLoading}
                    style={{
                      padding: '6px 14px',
                      background: '#475569',
                      color: '#fff',
                      border: 'none',
                      borderRadius: 6,
                      fontSize: 12,
                      fontWeight: 600,
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: 4,
                    }}
                  >
                    <Save size={13} />
                    <span>Lưu tạm biên bản</span>
                  </button>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                  {selectedCase.items.map((item) => {
                    const draft = inspectionDrafts[item.id] || {
                      received_quantity: item.requested_quantity,
                      accepted_quantity: item.requested_quantity,
                      rejected_quantity: 0,
                      package_condition: 'SEALED',
                      seal_intact: true,
                      batch_matched: true,
                      expiry_matched: true,
                      damage_description: '',
                      suggested_action: 'RESTOCK',
                      inspection_note: '',
                    }

                    const updateField = (field: string, value: any) => {
                      setInspectionDrafts({
                        ...inspectionDrafts,
                        [item.id]: {
                          ...draft,
                          [field]: value,
                        },
                      })
                    }

                    return (
                      <div
                        key={item.id}
                        style={{
                          background: '#fff',
                          borderRadius: 10,
                          border: '1px solid #cbd5e1',
                          padding: 16,
                          boxShadow: '0 1px 2px rgba(0,0,0,0.03)',
                        }}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 12 }}>
                          <div>
                            <span style={{ fontSize: 14, fontWeight: 700, color: '#0f172a' }}>{item.product_name}</span>
                            <span style={{ fontSize: 12, color: '#64748b', marginLeft: 8 }}>SKU: {item.product_sku || '—'}</span>
                          </div>
                          <div style={{ fontSize: 12, color: '#0284c7', fontWeight: 600 }}>
                            Khách yêu cầu: {item.requested_quantity} sp
                          </div>
                        </div>

                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginBottom: 12 }}>
                          <div>
                            <label style={{ display: 'block', fontSize: 11, fontWeight: 600, color: '#475569', marginBottom: 4 }}>
                              Số lượng thực nhận:
                            </label>
                            <input
                              type="number"
                              min={0}
                              value={draft.received_quantity}
                              onChange={(e) => updateField('received_quantity', Number(e.target.value))}
                              style={{ width: '100%', padding: '6px 10px', borderRadius: 6, border: '1px solid #cbd5e1', fontSize: 13 }}
                            />
                          </div>
                          <div>
                            <label style={{ display: 'block', fontSize: 11, fontWeight: 600, color: '#166534', marginBottom: 4 }}>
                              Đề xuất chấp nhận:
                            </label>
                            <input
                              type="number"
                              min={0}
                              value={draft.accepted_quantity}
                              onChange={(e) => updateField('accepted_quantity', Number(e.target.value))}
                              style={{ width: '100%', padding: '6px 10px', borderRadius: 6, border: '1px solid #cbd5e1', fontSize: 13 }}
                            />
                          </div>
                          <div>
                            <label style={{ display: 'block', fontSize: 11, fontWeight: 600, color: '#991b1b', marginBottom: 4 }}>
                              Đề xuất từ chối:
                            </label>
                            <input
                              type="number"
                              min={0}
                              value={draft.rejected_quantity}
                              onChange={(e) => updateField('rejected_quantity', Number(e.target.value))}
                              style={{ width: '100%', padding: '6px 10px', borderRadius: 6, border: '1px solid #cbd5e1', fontSize: 13 }}
                            />
                          </div>
                        </div>

                        {/* Checklist */}
                        <div
                          style={{
                            display: 'grid',
                            gridTemplateColumns: 'repeat(3, 1fr)',
                            gap: 12,
                            padding: '10px 12px',
                            background: '#f8fafc',
                            borderRadius: 8,
                            marginBottom: 12,
                          }}
                        >
                          <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, cursor: 'pointer' }}>
                            <input
                              type="checkbox"
                              checked={draft.seal_intact}
                              onChange={(e) => updateField('seal_intact', e.target.checked)}
                            />
                            <span>Tem niêm phong nguyên vẹn</span>
                          </label>

                          <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, cursor: 'pointer' }}>
                            <input
                              type="checkbox"
                              checked={draft.batch_matched}
                              onChange={(e) => updateField('batch_matched', e.target.checked)}
                            />
                            <span>Khớp số lô đã xuất từ kho</span>
                          </label>

                          <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, cursor: 'pointer' }}>
                            <input
                              type="checkbox"
                              checked={draft.expiry_matched}
                              onChange={(e) => updateField('expiry_matched', e.target.checked)}
                            />
                            <span>Khớp hạn sử dụng đã xuất</span>
                          </label>
                        </div>

                        {/* Đề xuất hướng xử lý */}
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: 12 }}>
                          <div>
                            <label style={{ display: 'block', fontSize: 11, fontWeight: 600, color: '#475569', marginBottom: 4 }}>
                              Đề xuất xử lý thuốc:
                            </label>
                            <select
                              value={draft.suggested_action}
                              onChange={(e) => updateField('suggested_action', e.target.value)}
                              style={{ width: '100%', padding: '7px 10px', borderRadius: 6, border: '1px solid #cbd5e1', fontSize: 12 }}
                            >
                              <option value="RESTOCK">Nhập lại kho bán (Đạt GSP)</option>
                              <option value="QUARANTINE">Cách ly theo dõi</option>
                              <option value="DISPOSE">Xuất hủy theo biên bản</option>
                              <option value="REJECT">Từ chối nhận hàng hoàn</option>
                            </select>
                          </div>
                          <div>
                            <label style={{ display: 'block', fontSize: 11, fontWeight: 600, color: '#475569', marginBottom: 4 }}>
                              Mô tả hư hỏng / Ghi chú thẩm định:
                            </label>
                            <input
                              type="text"
                              value={draft.damage_description}
                              onChange={(e) => updateField('damage_description', e.target.value)}
                              placeholder="Ghi chú cụ thể nếu có khiếm khuyết..."
                              style={{ width: '100%', padding: '7px 10px', borderRadius: 6, border: '1px solid #cbd5e1', fontSize: 12 }}
                            />
                          </div>
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>
            </div>

            {/* Modal Footer Controls */}
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
              <div style={{ fontSize: 12, color: '#64748b', fontStyle: 'italic' }}>
                * Nhân viên kho thẩm định số lô thực tế và nộp biên bản. Quyết định duyệt và hoàn tiền do Quản lý kho thực hiện.
              </div>

              <div style={{ display: 'flex', gap: 10 }}>
                <button
                  type="button"
                  onClick={() => setSelectedCase(null)}
                  className="admin-button button-secondary"
                >
                  Đóng
                </button>

                {['RECEIVED', 'INSPECTING'].includes(selectedCase.status) && (
                  <button
                    type="button"
                    onClick={handleSubmitToManager}
                    disabled={actionLoading}
                    style={{
                      padding: '9px 20px',
                      background: '#047857',
                      color: '#fff',
                      border: 'none',
                      borderRadius: 8,
                      fontWeight: 700,
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: 6,
                    }}
                  >
                    <Send size={14} />
                    <span>Nộp biên bản lên Quản lý duyệt</span>
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
