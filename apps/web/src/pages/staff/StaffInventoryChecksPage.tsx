import { useEffect, useState } from 'react'
import { ClipboardList, Plus, AlertCircle, CheckCircle2, History, X } from 'lucide-react'
import { api } from '../../services/api'

interface AdjustmentItem {
  id: number
  adjustment_code: string
  reason: string
  status: string
  created_at: string | null
  items_count: number
}

interface BatchOption {
  batch_id: number
  batch_number: string
  product_name: string
  sku_code: string
  unit_name: string
  expiry_date: string | null
  quantity_on_hand: number
}

export function StaffInventoryChecksPage() {
  const [adjustments, setAdjustments] = useState<AdjustmentItem[]>([])
  const [loading, setLoading] = useState(true)

  // Batch list for shelf check selection
  const [batches, setBatches] = useState<BatchOption[]>([])
  const [loadingBatches, setLoadingBatches] = useState(false)

  // Quick count modal
  const [showModal, setShowModal] = useState(false)
  const [batchId, setBatchId] = useState(1)
  const [actualQty, setActualQty] = useState(0)
  const [reason, setReason] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)

  const fetchChecks = () => {
    setLoading(true)
    api<{ items: AdjustmentItem[] }>('/warehouse-portal/adjustments?page_size=50')
      .then((res) => setAdjustments(res.items || []))
      .catch((err) => console.error(err))
      .finally(() => setLoading(false))
  }

  const fetchBatches = () => {
    setLoadingBatches(true)
    api<{ items: BatchOption[] }>('/warehouse-portal/batches?page_size=100')
      .then((res) => {
        const list = res.items || []
        setBatches(list)
        if (list.length > 0 && (!batchId || batchId === 1)) {
          setBatchId(list[0].batch_id)
          setActualQty(list[0].quantity_on_hand ?? 0)
        }
      })
      .catch((err) => console.error(err))
      .finally(() => setLoadingBatches(false))
  }

  useEffect(() => {
    fetchChecks()
    fetchBatches()
  }, [])

  const selectedBatch = batches.find((b) => b.batch_id === batchId)

  const handleOpenModal = () => {
    setFormError(null)
    if (batches.length > 0) {
      const defaultB = batches[0]
      setBatchId(defaultB.batch_id)
      setActualQty(defaultB.quantity_on_hand ?? 0)
    }
    setShowModal(true)
  }

  const handleSubmitCheck = async (e: React.FormEvent) => {
    e.preventDefault()
    setFormError(null)

    if (!reason.trim() || reason.trim().length < 5) {
      setFormError('Bắt buộc phải ghi rõ lý do kiểm kê / chênh lệch (tối thiểu 5 ký tự)')
      return
    }

    setSubmitting(true)
    try {
      await api('/warehouse-portal/adjustments', {
        method: 'POST',
        body: JSON.stringify({
          reason: reason.trim(),
          items: [
            {
              batch_id: batchId,
              actual_quantity: actualQty,
              reason: reason.trim(),
            },
          ],
        }),
      })
      setShowModal(false)
      setReason('')
      fetchChecks()
      alert('Đã gửi kết quả kiểm kê số lượng thực tế thành công!')
    } catch (err: any) {
      setFormError(err?.message || 'Không thể lưu biên bản kiểm kê')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 bg-white p-5 rounded-2xl border border-slate-200">
        <div>
          <div className="text-xs font-black uppercase text-emerald-700 tracking-wider">
            4. KIỂM ĐẾM & ĐỐI SOÁT TỒN THỰC TẾ
          </div>
          <h1 className="text-xl font-black text-slate-800">Kiểm Kê Được Giao</h1>
          <p className="text-xs text-slate-500">Đếm số lượng thực tế trên kệ để đối chiếu với phần mềm quản lý kho</p>
        </div>

        <button
          onClick={handleOpenModal}
          className="bg-emerald-700 hover:bg-emerald-800 text-white px-5 py-2.5 rounded-xl font-bold text-xs shadow flex items-center gap-2 transition"
        >
          <Plus size={16} /> Nhập Kết Quả Đếm Kệ
        </button>
      </div>

      {/* Adjustments & Check Logs */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="p-4 border-b bg-slate-50 flex items-center justify-between">
          <span className="text-xs font-black uppercase text-slate-600">Lịch sử các đợt kiểm kê gần đây</span>
          <span className="text-xs font-bold text-slate-500">{adjustments.length} đợt</span>
        </div>

        <div className="divide-y divide-slate-100">
          {loading ? (
            <div className="p-10 text-center text-slate-400 font-bold">Đang tải biên bản kiểm kê…</div>
          ) : adjustments.length === 0 ? (
            <div className="p-10 text-center text-slate-400 font-bold">Chưa có biên bản kiểm kê nào.</div>
          ) : (
            adjustments.map((a) => (
              <div key={a.id} className="p-4 hover:bg-slate-50/80 transition flex items-center justify-between gap-4">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="font-mono font-black text-sm text-emerald-900">{a.adjustment_code}</span>
                    <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-800">
                      {a.status}
                    </span>
                  </div>
                  <div className="text-xs font-bold text-slate-700">{a.reason}</div>
                  <div className="text-[11px] text-slate-400">
                    Số lô kiểm đếm: <b>{a.items_count}</b> • {a.created_at ? new Date(a.created_at).toLocaleString('vi-VN') : '—'}
                  </div>
                </div>
                <div className="text-emerald-600">
                  <CheckCircle2 size={20} />
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Quick Count Modal */}
      {showModal && (
        <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 space-y-4 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between border-b pb-3">
              <div className="flex items-center gap-2">
                <ClipboardList className="text-emerald-700" size={20} />
                <h3 className="text-base font-black text-slate-800">Nhập Kết Quả Đếm Kệ Thực Tế</h3>
              </div>
              <button onClick={() => setShowModal(false)} className="text-slate-400 hover:text-slate-600">
                <X size={20} />
              </button>
            </div>

            {formError && (
              <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 text-rose-700 text-xs font-semibold flex items-center gap-2">
                <AlertCircle size={16} /> {formError}
              </div>
            )}

            <form onSubmit={handleSubmitCheck} className="space-y-4">
              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="block text-xs font-bold text-slate-700 uppercase">Chọn Lô Thuốc Cần Kiểm Kê</label>
                  {loadingBatches && <span className="text-[11px] text-emerald-600 font-semibold">Đang tải lô...</span>}
                </div>
                {batches.length > 0 ? (
                  <select
                    value={batchId}
                    onChange={(e) => {
                      const newId = Number(e.target.value)
                      setBatchId(newId)
                      const found = batches.find((b) => b.batch_id === newId)
                      if (found) {
                        setActualQty(found.quantity_on_hand ?? 0)
                      }
                    }}
                    className="w-full px-3 py-2 border rounded-xl text-xs font-semibold bg-white focus:ring-2 focus:ring-emerald-500 focus:outline-none"
                    required
                  >
                    {batches.map((b) => (
                      <option key={b.batch_id} value={b.batch_id}>
                        {b.batch_number} - {b.product_name} ({b.unit_name || 'ĐV'}) - HSD: {b.expiry_date || 'N/A'} [Tồn: {b.quantity_on_hand}]
                      </option>
                    ))}
                  </select>
                ) : (
                  <div className="space-y-1">
                    <input
                      type="number"
                      min={1}
                      value={batchId}
                      onChange={(e) => setBatchId(Number(e.target.value))}
                      placeholder="Nhập mã Batch ID..."
                      className="w-full px-3 py-2 border rounded-xl text-sm"
                      required
                    />
                    <p className="text-[11px] text-slate-400">Chưa có danh mục lô tự động, vui lòng nhập mã Batch ID trực tiếp.</p>
                  </div>
                )}

                {selectedBatch && (
                  <div className="mt-2.5 p-3 bg-slate-50 border border-slate-200 rounded-xl text-xs space-y-1.5">
                    <div className="flex justify-between items-center text-slate-700">
                      <span className="text-slate-500">Tên thuốc:</span>
                      <span className="font-bold text-slate-900 text-right max-w-[240px] truncate">{selectedBatch.product_name}</span>
                    </div>
                    <div className="flex justify-between text-slate-700">
                      <span className="text-slate-500">Mã lô & HSD:</span>
                      <span className="font-semibold text-emerald-800">{selectedBatch.batch_number} • HSD: {selectedBatch.expiry_date || 'N/A'}</span>
                    </div>
                    <div className="flex justify-between text-slate-700">
                      <span className="text-slate-500">Tồn hệ thống máy:</span>
                      <span className="font-bold text-slate-900">{(selectedBatch.quantity_on_hand ?? 0).toLocaleString()} {selectedBatch.unit_name || 'đơn vị'}</span>
                    </div>
                    {actualQty !== undefined && actualQty >= 0 && (
                      <div className="flex justify-between pt-1.5 border-t border-slate-200">
                        <span className="text-slate-600 font-semibold">Chênh lệch đối soát:</span>
                        {actualQty === selectedBatch.quantity_on_hand ? (
                          <span className="font-bold text-emerald-700">Khớp chuẩn 100% (0)</span>
                        ) : actualQty > selectedBatch.quantity_on_hand ? (
                          <span className="font-bold text-amber-700">Thừa thực tế +{actualQty - selectedBatch.quantity_on_hand} {selectedBatch.unit_name || 'đơn vị'}</span>
                        ) : (
                          <span className="font-bold text-rose-700">Thiếu thực tế -{selectedBatch.quantity_on_hand - actualQty} {selectedBatch.unit_name || 'đơn vị'}</span>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 uppercase mb-1">Số Lượng Thực Đếm Tại Kệ (Hộp / Lọ)</label>
                <input
                  type="number"
                  min={0}
                  value={actualQty}
                  onChange={(e) => setActualQty(Number(e.target.value))}
                  className="w-full px-3 py-2 border rounded-xl text-sm font-bold text-emerald-800 focus:ring-2 focus:ring-emerald-500 focus:outline-none"
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 uppercase mb-1">
                  Ghi Chú Kiểm Kê <span className="text-rose-500">* Bắt buộc</span>
                </label>
                <textarea
                  rows={3}
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  placeholder="VD: Kiểm đếm định kỳ kệ A2, số lượng khớp; hoặc phát hiện bao bì rách…"
                  className="w-full px-3 py-2 border rounded-xl text-sm"
                  required
                />
              </div>

              <div className="flex justify-end gap-3 pt-3 border-t">
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="px-4 py-2 border rounded-xl text-sm font-semibold text-slate-600 hover:bg-slate-50"
                >
                  Hủy
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-5 py-2 bg-emerald-700 hover:bg-emerald-800 text-white rounded-xl text-sm font-bold shadow"
                >
                  {submitting ? 'Đang lưu…' : 'Xác nhận kiểm kê'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
