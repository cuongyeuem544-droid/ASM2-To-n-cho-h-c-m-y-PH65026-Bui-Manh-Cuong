import {
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Filter,
  Layers,
  RefreshCw,
  Search,
  ShieldAlert,
  ShieldCheck,
  XCircle,
} from 'lucide-react'
import { useEffect, useState } from 'react'
import { AdminPageHeader } from '../components/AdminPageHeader'
import { api } from '../services/api'
import { useAuth } from '../services/auth'

interface ReviewItem {
  review_id: number
  product_id: number
  product_name: string
  registration_number: string | null
  manufacturer: string | null
  image_url: string | null
  suggested_product_type: string
  suggested_prescription_status: string
  suggested_category_id: number | null
  suggested_category_name: string | null
  suggested_category_slug: string | null
  confidence: number
  reasoning: string
  missing_fields: string[]
  conflicts: string[]
  status: string
  created_at: string | null
}

interface ReviewQueueResponse {
  items: ReviewItem[]
  total: number
  page: number
  page_size: number
}

interface CategoryOption {
  id: string
  dbId: number
  name: string
  code: string
  subCategories: Array<{
    id: string
    dbId: number
    name: string
    code: string
  }>
}

const PRODUCT_TYPES = [
  { value: 'MEDICINE', label: 'Thuốc (Dược phẩm)' },
  { value: 'SUPPLEMENT', label: 'Thực phẩm BVSK / Bổ sung' },
  { value: 'COSMETIC', label: 'Mỹ phẩm / Dược mỹ phẩm' },
  { value: 'MEDICAL_DEVICE', label: 'Trang thiết bị y tế' },
  { value: 'MOTHER_BABY', label: 'Sản phẩm Mẹ & Bé' },
  { value: 'PERSONAL_CARE', label: 'Chăm sóc cá nhân' },
  { value: 'OTHER', label: 'Khác / Chưa rõ' },
]

const RX_STATUSES = [
  { value: 'OTC', label: 'Không kê đơn (OTC)' },
  { value: 'RX', label: 'Thuốc kê đơn (Rx)' },
  { value: 'CONTROLLED', label: 'Thuốc kiểm soát đặc biệt' },
  { value: 'NOT_APPLICABLE', label: 'Không áp dụng (Không phải thuốc)' },
  { value: 'UNKNOWN', label: 'Chưa xác định' },
]

export function ClassificationQueuePage() {
  const { user } = useAuth()
  const canEdit = user?.role === 'ADMIN' || user?.role === 'DATA_REVIEWER'

  const [items, setItems] = useState<ReviewItem[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize] = useState(20)
  const [status, setStatus] = useState('PENDING')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [searchTerm, setSearchTerm] = useState('')

  // Categories list for modal
  const [categoriesTree, setCategoriesTree] = useState<CategoryOption[]>([])

  // Modal approve state
  const [approveTarget, setApproveTarget] = useState<ReviewItem | null>(null)
  const [approveType, setApproveType] = useState('MEDICINE')
  const [approveRx, setApproveRx] = useState('OTC')
  const [approveCatId, setApproveCatId] = useState<number | ''>('')
  const [approveNote, setApproveNote] = useState('')
  const [actionLoading, setActionLoading] = useState(false)

  // Modal reject state
  const [rejectTarget, setRejectTarget] = useState<ReviewItem | null>(null)
  const [rejectReason, setRejectReason] = useState('')

  // Bulk selection
  const [selectedIds, setSelectedIds] = useState<number[]>([])
  const [showBulkModal, setShowBulkModal] = useState(false)
  const [bulkType, setBulkType] = useState('MEDICINE')
  const [bulkRx, setBulkRx] = useState('OTC')
  const [bulkCatId, setBulkCatId] = useState<number | ''>('')

  const loadData = () => {
    setLoading(true)
    api<ReviewQueueResponse>(`/admin/classification/review-queue?page=${page}&page_size=${pageSize}&status=${status}`)
      .then(res => {
        setItems(res.items)
        setTotal(res.total)
        setError('')
      })
      .catch(err => setError(err.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    loadData()
  }, [page, status])

  useEffect(() => {
    api<CategoryOption[]>('/admin/categories/tree')
      .then(res => setCategoriesTree(res))
      .catch(() => {})
  }, [])

  const handleOpenApprove = (item: ReviewItem) => {
    setApproveTarget(item)
    setApproveType(item.suggested_product_type || 'MEDICINE')
    setApproveRx(item.suggested_prescription_status || 'OTC')
    setApproveCatId(item.suggested_category_id || '')
    setApproveNote(`Duyệt theo đề xuất: ${item.reasoning.substring(0, 100)}`)
  }

  const handleConfirmApprove = async () => {
    if (!approveTarget) return
    setActionLoading(true)
    setError('')
    try {
      await api(`/admin/classification/${approveTarget.product_id}/approve`, {
        method: 'POST',
        body: JSON.stringify({
          product_type: approveType,
          prescription_status: approveRx,
          category_ids: approveCatId ? [Number(approveCatId)] : undefined,
          primary_category_id: approveCatId ? Number(approveCatId) : undefined,
          note: approveNote,
        }),
      })
      setSuccess(`Đã duyệt phân loại thành công cho sản phẩm #${approveTarget.product_id}`)
      setApproveTarget(null)
      loadData()
    } catch (err: any) {
      setError(err.message || 'Lỗi phê duyệt')
    } finally {
      setActionLoading(false)
    }
  }

  const handleOpenReject = (item: ReviewItem) => {
    setRejectTarget(item)
    setRejectReason('Thiếu hồ sơ pháp lý / chưa đủ căn cứ chứng minh nhóm sản phẩm')
  }

  const handleConfirmReject = async () => {
    if (!rejectTarget || !rejectReason.trim()) return
    setActionLoading(true)
    setError('')
    try {
      await api(`/admin/classification/${rejectTarget.product_id}/reject`, {
        method: 'POST',
        body: JSON.stringify({ reason: rejectReason.trim() }),
      })
      setSuccess(`Đã từ chối phân loại cho sản phẩm #${rejectTarget.product_id}`)
      setRejectTarget(null)
      loadData()
    } catch (err: any) {
      setError(err.message || 'Lỗi từ chối')
    } finally {
      setActionLoading(false)
    }
  }

  const handleToggleSelect = (productId: number) => {
    setSelectedIds(prev =>
      prev.includes(productId) ? prev.filter(id => id !== productId) : [...prev, productId]
    )
  }

  const handleSelectAllOnPage = () => {
    if (selectedIds.length === items.length) {
      setSelectedIds([])
    } else {
      setSelectedIds(items.map(i => i.product_id))
    }
  }

  const handleConfirmBulkApprove = async () => {
    if (selectedIds.length === 0 || !bulkCatId) return
    setActionLoading(true)
    setError('')
    try {
      const res: any = await api('/admin/classification/bulk-approve', {
        method: 'POST',
        body: JSON.stringify({
          product_ids: selectedIds,
          product_type: bulkType,
          prescription_status: bulkRx,
          category_ids: [Number(bulkCatId)],
          primary_category_id: Number(bulkCatId),
          note: `Bulk approved by ${user?.full_name || 'Admin'}`,
        }),
      })
      setSuccess(res.message || `Đã duyệt hàng loạt ${selectedIds.length} sản phẩm!`)
      setSelectedIds([])
      setShowBulkModal(false)
      loadData()
    } catch (err: any) {
      setError(err.message || 'Lỗi duyệt hàng loạt')
    } finally {
      setActionLoading(false)
    }
  }

  const filteredItems = items.filter(i =>
    i.product_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    (i.registration_number && i.registration_number.toLowerCase().includes(searchTerm.toLowerCase()))
  )

  const totalPages = Math.ceil(total / pageSize)

  return (
    <div className="space-y-6">
      <AdminPageHeader
        title="Hàng Chờ Duyệt Phân Loại Y Tế"
        subtitle="Kiểm tra và phê duyệt phân loại Pháp lý (Thuốc, TPCN, Mỹ phẩm, TBYT) và Đơn thuốc (OTC/Rx) theo quy chuẩn Bộ Y Tế."
        actions={
          <div className="flex items-center gap-2">
            <button
              onClick={loadData}
              disabled={loading}
              className="inline-flex items-center gap-2 px-3 py-2 text-sm font-medium text-slate-700 bg-white border border-slate-300 rounded-lg hover:bg-slate-50 shadow-sm"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
              Làm mới
            </button>
            {canEdit && selectedIds.length > 0 && (
              <button
                onClick={() => setShowBulkModal(true)}
                className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 shadow-sm"
              >
                <CheckCircle2 className="w-4 h-4" />
                Duyệt hàng loạt ({selectedIds.length})
              </button>
            )}
          </div>
        }
      />

      {/* Notifications */}
      {error && (
        <div className="p-4 bg-rose-50 border border-rose-200 text-rose-700 rounded-lg flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-5 h-5 flex-shrink-0" />
            <span>{error}</span>
          </div>
          <button onClick={() => setError('')} className="text-rose-500 hover:text-rose-700">✕</button>
        </div>
      )}

      {success && (
        <div className="p-4 bg-emerald-50 border border-emerald-200 text-emerald-700 rounded-lg flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-5 h-5 flex-shrink-0" />
            <span>{success}</span>
          </div>
          <button onClick={() => setSuccess('')} className="text-emerald-500 hover:text-emerald-700">✕</button>
        </div>
      )}

      {/* Filter Bar */}
      <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex flex-col md:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-3 w-full md:w-auto">
          <div className="relative flex-1 md:w-80">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Tìm theo tên sản phẩm, số đăng ký..."
              value={searchTerm}
              onChange={e => setSearchTerm(e.target.value)}
              className="w-full pl-9 pr-4 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>
        </div>

        <div className="flex items-center gap-2 w-full md:w-auto justify-end">
          <span className="text-xs text-slate-500 font-medium flex items-center gap-1">
            <Filter className="w-3.5 h-3.5" /> Trạng thái:
          </span>
          <div className="inline-flex rounded-lg border border-slate-200 p-0.5 bg-slate-50">
            {(['PENDING', 'APPROVED', 'REJECTED'] as const).map(s => (
              <button
                key={s}
                onClick={() => { setStatus(s); setPage(1); }}
                className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                  status === s
                    ? 'bg-white text-indigo-700 shadow-sm'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                {s === 'PENDING' ? 'Chờ duyệt' : s === 'APPROVED' ? 'Đã duyệt' : 'Từ chối'}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Review Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-200 text-xs font-semibold text-slate-600 uppercase tracking-wider">
                {canEdit && (
                  <th className="py-3 px-4 w-10">
                    <input
                      type="checkbox"
                      checked={items.length > 0 && selectedIds.length === items.length}
                      onChange={handleSelectAllOnPage}
                      className="rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
                    />
                  </th>
                )}
                <th className="py-3 px-4">Sản phẩm & Số ĐK</th>
                <th className="py-3 px-4">Đề xuất Pháp lý</th>
                <th className="py-3 px-4">Đơn thuốc (Rx)</th>
                <th className="py-3 px-4">Danh mục gợi ý</th>
                <th className="py-3 px-4">Độ tin cậy</th>
                <th className="py-3 px-4">Căn cứ & Ghi chú</th>
                <th className="py-3 px-4 text-right">Thao tác</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-sm">
              {loading && items.length === 0 ? (
                <tr>
                  <td colSpan={canEdit ? 8 : 7} className="py-12 text-center text-slate-400">
                    <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2 text-indigo-600" />
                    Đang tải dữ liệu hàng chờ phân loại...
                  </td>
                </tr>
              ) : filteredItems.length === 0 ? (
                <tr>
                  <td colSpan={canEdit ? 8 : 7} className="py-12 text-center text-slate-400">
                    <ShieldCheck className="w-8 h-8 mx-auto mb-2 text-emerald-500" />
                    Không có sản phẩm nào trong trạng thái này.
                  </td>
                </tr>
              ) : (
                filteredItems.map(item => (
                  <tr key={item.review_id} className="hover:bg-slate-50/70 transition-colors">
                    {canEdit && (
                      <td className="py-3 px-4">
                        <input
                          type="checkbox"
                          checked={selectedIds.includes(item.product_id)}
                          onChange={() => handleToggleSelect(item.product_id)}
                          className="rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
                        />
                      </td>
                    )}
                    <td className="py-3 px-4">
                      <div className="font-medium text-slate-900 leading-snug">{item.product_name}</div>
                      <div className="flex items-center gap-2 mt-1">
                        {item.registration_number ? (
                          <span className="inline-block px-1.5 py-0.5 text-[11px] font-mono bg-blue-50 text-blue-700 rounded border border-blue-200">
                            SĐK: {item.registration_number}
                          </span>
                        ) : (
                          <span className="text-xs text-amber-600 font-medium">Chưa có SĐK</span>
                        )}
                        <span className="text-xs text-slate-400">ID: #{item.product_id}</span>
                      </div>
                    </td>
                    <td className="py-3 px-4">
                      <span className={`inline-block px-2.5 py-1 text-xs font-semibold rounded-full ${
                        item.suggested_product_type === 'MEDICINE'
                          ? 'bg-blue-100 text-blue-800'
                          : item.suggested_product_type === 'SUPPLEMENT'
                          ? 'bg-emerald-100 text-emerald-800'
                          : item.suggested_product_type === 'COSMETIC'
                          ? 'bg-pink-100 text-pink-800'
                          : item.suggested_product_type === 'MEDICAL_DEVICE'
                          ? 'bg-purple-100 text-purple-800'
                          : item.suggested_product_type === 'MOTHER_BABY'
                          ? 'bg-amber-100 text-amber-800'
                          : 'bg-slate-100 text-slate-800'
                      }`}>
                        {PRODUCT_TYPES.find(p => p.value === item.suggested_product_type)?.label.split(' (')[0] || item.suggested_product_type}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <span className={`inline-block px-2 py-0.5 text-xs font-medium rounded ${
                        item.suggested_prescription_status === 'RX'
                          ? 'bg-rose-100 text-rose-700 font-bold'
                          : item.suggested_prescription_status === 'OTC'
                          ? 'bg-emerald-50 text-emerald-700'
                          : item.suggested_prescription_status === 'CONTROLLED'
                          ? 'bg-amber-100 text-amber-800'
                          : 'bg-slate-100 text-slate-600'
                      }`}>
                        {item.suggested_prescription_status}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      {item.suggested_category_name ? (
                        <div className="text-xs text-slate-700 font-medium">
                          {item.suggested_category_name}
                          <div className="text-[11px] text-slate-400 font-mono">/{item.suggested_category_slug}</div>
                        </div>
                      ) : (
                        <span className="text-xs text-slate-400 italic">Chưa gán</span>
                      )}
                    </td>
                    <td className="py-3 px-4">
                      <div className="flex items-center gap-1.5">
                        <div className="w-14 bg-slate-200 rounded-full h-1.5 overflow-hidden">
                          <div
                            className={`h-full ${
                              item.confidence >= 0.95
                                ? 'bg-emerald-500'
                                : item.confidence >= 0.8
                                ? 'bg-blue-500'
                                : 'bg-amber-500'
                            }`}
                            style={{ width: `${Math.round(item.confidence * 100)}%` }}
                          />
                        </div>
                        <span className="text-xs font-mono font-medium text-slate-600">
                          {Math.round(item.confidence * 100)}%
                        </span>
                      </div>
                    </td>
                    <td className="py-3 px-4 max-w-xs">
                      <p className="text-xs text-slate-600 line-clamp-2" title={item.reasoning}>
                        {item.reasoning}
                      </p>
                      {item.conflicts && item.conflicts.length > 0 && (
                        <div className="flex items-center gap-1 mt-1 text-[11px] text-rose-600 font-medium">
                          <AlertTriangle className="w-3 h-3" />
                          <span>{item.conflicts.length} xung đột dữ liệu</span>
                        </div>
                      )}
                    </td>
                    <td className="py-3 px-4 text-right">
                      {canEdit ? (
                        <div className="flex items-center justify-end gap-1.5">
                          <button
                            onClick={() => handleOpenApprove(item)}
                            className="px-2.5 py-1 text-xs font-medium text-emerald-700 bg-emerald-50 hover:bg-emerald-100 border border-emerald-200 rounded-md transition-colors"
                          >
                            Duyệt
                          </button>
                          <button
                            onClick={() => handleOpenReject(item)}
                            className="px-2.5 py-1 text-xs font-medium text-rose-700 bg-rose-50 hover:bg-rose-100 border border-rose-200 rounded-md transition-colors"
                          >
                            Từ chối
                          </button>
                        </div>
                      ) : (
                        <span className="text-xs text-slate-400 italic">Chỉ xem</span>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination Footer */}
        <div className="px-4 py-3 bg-slate-50 border-t border-slate-200 flex items-center justify-between">
          <div className="text-xs text-slate-500">
            Hiển thị <span className="font-medium text-slate-700">{filteredItems.length}</span> / <span className="font-medium text-slate-700">{total}</span> sản phẩm
          </div>
          <div className="flex items-center gap-1">
            <button
              onClick={() => setPage(p => Math.max(1, p - 1))}
              disabled={page <= 1}
              className="p-1.5 text-slate-600 hover:bg-slate-200 rounded disabled:opacity-40 disabled:hover:bg-transparent"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <span className="text-xs font-medium text-slate-700 px-2">
              Trang {page} / {totalPages || 1}
            </span>
            <button
              onClick={() => setPage(p => Math.min(totalPages, p + 1))}
              disabled={page >= totalPages}
              className="p-1.5 text-slate-600 hover:bg-slate-200 rounded disabled:opacity-40 disabled:hover:bg-transparent"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Modal Approve */}
      {approveTarget && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-lg w-full p-6 space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-200">
              <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
                <CheckCircle2 className="w-5 h-5 text-emerald-600" />
                Phê duyệt phân loại sản phẩm
              </h3>
              <button onClick={() => setApproveTarget(null)} className="text-slate-400 hover:text-slate-600">✕</button>
            </div>

            <div className="text-sm bg-slate-50 p-3 rounded-lg border border-slate-200">
              <div className="font-semibold text-slate-900">{approveTarget.product_name}</div>
              <div className="text-xs text-slate-500 mt-1">SĐK: {approveTarget.registration_number || 'Chưa có'} | NSX: {approveTarget.manufacturer || 'Chưa rõ'}</div>
              <div className="text-xs text-slate-600 mt-2 italic bg-white p-2 rounded border border-slate-100">
                Lý do đề xuất: {approveTarget.reasoning}
              </div>
            </div>

            <div className="space-y-3">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Loại sản phẩm pháp lý *</label>
                <select
                  value={approveType}
                  onChange={e => {
                    setApproveType(e.target.value)
                    if (e.target.value !== 'MEDICINE') {
                      setApproveRx('NOT_APPLICABLE')
                    }
                  }}
                  className="w-full text-sm border border-slate-300 rounded-lg p-2 focus:ring-2 focus:ring-indigo-500"
                >
                  {PRODUCT_TYPES.map(pt => (
                    <option key={pt.value} value={pt.value}>{pt.label}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Trạng thái Kê đơn (Rx/OTC) *</label>
                <select
                  value={approveRx}
                  disabled={approveType !== 'MEDICINE'}
                  onChange={e => setApproveRx(e.target.value)}
                  className="w-full text-sm border border-slate-300 rounded-lg p-2 focus:ring-2 focus:ring-indigo-500 disabled:bg-slate-100"
                >
                  {RX_STATUSES.map(rx => (
                    <option key={rx.value} value={rx.value}>{rx.label}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Danh mục bán hàng chính</label>
                <select
                  value={approveCatId}
                  onChange={e => setApproveCatId(e.target.value ? Number(e.target.value) : '')}
                  className="w-full text-sm border border-slate-300 rounded-lg p-2 focus:ring-2 focus:ring-indigo-500"
                >
                  <option value="">-- Chọn danh mục --</option>
                  {categoriesTree.map(cat => (
                    <optgroup key={cat.dbId} label={cat.name}>
                      <option value={cat.dbId}>{cat.name} (Gốc)</option>
                      {cat.subCategories.map(sub => (
                        <option key={sub.dbId} value={sub.dbId}>-- {sub.name}</option>
                      ))}
                    </optgroup>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Ghi chú duyệt</label>
                <input
                  type="text"
                  value={approveNote}
                  onChange={e => setApproveNote(e.target.value)}
                  className="w-full text-sm border border-slate-300 rounded-lg p-2"
                />
              </div>
            </div>

            <div className="flex items-center justify-end gap-2 pt-3 border-t border-slate-200">
              <button
                onClick={() => setApproveTarget(null)}
                className="px-4 py-2 text-sm text-slate-700 hover:bg-slate-100 rounded-lg"
              >
                Hủy bỏ
              </button>
              <button
                onClick={handleConfirmApprove}
                disabled={actionLoading}
                className="px-4 py-2 text-sm text-white bg-emerald-600 hover:bg-emerald-700 rounded-lg font-medium shadow-sm disabled:opacity-50"
              >
                {actionLoading ? 'Đang xử lý...' : 'Xác nhận phê duyệt'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal Reject */}
      {rejectTarget && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-md w-full p-6 space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-200">
              <h3 className="text-base font-bold text-rose-700 flex items-center gap-2">
                <XCircle className="w-5 h-5" />
                Từ chối kết quả phân loại
              </h3>
              <button onClick={() => setRejectTarget(null)} className="text-slate-400 hover:text-slate-600">✕</button>
            </div>

            <div className="text-sm bg-slate-50 p-3 rounded-lg border border-slate-200">
              <div className="font-semibold text-slate-900">{rejectTarget.product_name}</div>
              <div className="text-xs text-slate-500 mt-1">ID: #{rejectTarget.product_id}</div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Lý do từ chối *</label>
              <textarea
                rows={3}
                value={rejectReason}
                onChange={e => setRejectReason(e.target.value)}
                placeholder="Nhập lý do từ chối (yêu cầu bổ sung hồ sơ, số ĐK sai...)"
                className="w-full text-sm border border-slate-300 rounded-lg p-2.5 focus:ring-2 focus:ring-rose-500"
              />
            </div>

            <div className="flex items-center justify-end gap-2 pt-3 border-t border-slate-200">
              <button
                onClick={() => setRejectTarget(null)}
                className="px-4 py-2 text-sm text-slate-700 hover:bg-slate-100 rounded-lg"
              >
                Hủy bỏ
              </button>
              <button
                onClick={handleConfirmReject}
                disabled={actionLoading || !rejectReason.trim()}
                className="px-4 py-2 text-sm text-white bg-rose-600 hover:bg-rose-700 rounded-lg font-medium shadow-sm disabled:opacity-50"
              >
                {actionLoading ? 'Đang xử lý...' : 'Xác nhận từ chối'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal Bulk Approve */}
      {showBulkModal && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl max-w-md w-full p-6 space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-200">
              <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
                <CheckCircle2 className="w-5 h-5 text-indigo-600" />
                Duyệt hàng loạt {selectedIds.length} sản phẩm
              </h3>
              <button onClick={() => setShowBulkModal(false)} className="text-slate-400 hover:text-slate-600">✕</button>
            </div>

            <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg text-xs text-amber-800">
              Tất cả các sản phẩm được chọn sẽ được gán cùng nhóm pháp lý và danh mục bên dưới.
            </div>

            <div className="space-y-3">
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Loại sản phẩm pháp lý *</label>
                <select
                  value={bulkType}
                  onChange={e => {
                    setBulkType(e.target.value)
                    if (e.target.value !== 'MEDICINE') setBulkRx('NOT_APPLICABLE')
                  }}
                  className="w-full text-sm border border-slate-300 rounded-lg p-2 focus:ring-2 focus:ring-indigo-500"
                >
                  {PRODUCT_TYPES.map(pt => (
                    <option key={pt.value} value={pt.value}>{pt.label}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Trạng thái Kê đơn (Rx/OTC) *</label>
                <select
                  value={bulkRx}
                  disabled={bulkType !== 'MEDICINE'}
                  onChange={e => setBulkRx(e.target.value)}
                  className="w-full text-sm border border-slate-300 rounded-lg p-2 focus:ring-2 focus:ring-indigo-500 disabled:bg-slate-100"
                >
                  {RX_STATUSES.map(rx => (
                    <option key={rx.value} value={rx.value}>{rx.label}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Danh mục bán hàng *</label>
                <select
                  value={bulkCatId}
                  onChange={e => setBulkCatId(e.target.value ? Number(e.target.value) : '')}
                  className="w-full text-sm border border-slate-300 rounded-lg p-2 focus:ring-2 focus:ring-indigo-500"
                >
                  <option value="">-- Chọn danh mục đích --</option>
                  {categoriesTree.map(cat => (
                    <optgroup key={cat.dbId} label={cat.name}>
                      <option value={cat.dbId}>{cat.name} (Gốc)</option>
                      {cat.subCategories.map(sub => (
                        <option key={sub.dbId} value={sub.dbId}>-- {sub.name}</option>
                      ))}
                    </optgroup>
                  ))}
                </select>
              </div>
            </div>

            <div className="flex items-center justify-end gap-2 pt-3 border-t border-slate-200">
              <button
                onClick={() => setShowBulkModal(false)}
                className="px-4 py-2 text-sm text-slate-700 hover:bg-slate-100 rounded-lg"
              >
                Hủy bỏ
              </button>
              <button
                onClick={handleConfirmBulkApprove}
                disabled={actionLoading || !bulkCatId}
                className="px-4 py-2 text-sm text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg font-medium shadow-sm disabled:opacity-50"
              >
                {actionLoading ? 'Đang xử lý...' : 'Xác nhận duyệt hàng loạt'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
