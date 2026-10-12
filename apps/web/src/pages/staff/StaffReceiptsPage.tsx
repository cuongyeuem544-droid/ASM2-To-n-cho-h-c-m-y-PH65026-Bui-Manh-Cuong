import { useEffect, useState } from 'react'
import { ArrowDownToLine, CheckCircle2, Clock, FileText, Search } from 'lucide-react'
import { api } from '../../services/api'

interface ReceiptItem {
  id: number
  receipt_code: string
  supplier_name: string
  status: string
  total_amount: number
  received_date: string | null
  note: string | null
  items_count: number
  created_at: string | null
}

export function StaffReceiptsPage() {
  const [receipts, setReceipts] = useState<ReceiptItem[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')

  const fetchReceipts = () => {
    setLoading(true)
    api<{ items: ReceiptItem[] }>('/warehouse-portal/receipts?page_size=50')
      .then((res) => setReceipts(res.items || []))
      .catch((err) => console.error(err))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    fetchReceipts()
  }, [])

  const filteredReceipts = receipts.filter(
    (r) =>
      r.receipt_code.toLowerCase().includes(search.toLowerCase()) ||
      r.supplier_name.toLowerCase().includes(search.toLowerCase())
  )

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 bg-white p-5 rounded-2xl border border-slate-200">
        <div>
          <div className="text-xs font-black uppercase text-emerald-700 tracking-wider">
            3. TIẾP NHẬN & KIỂM ĐẾM NHẬP KHO
          </div>
          <h1 className="text-xl font-black text-slate-800">Phiếu Nhập Thuốc Được Giao</h1>
          <p className="text-xs text-slate-500">Đối chiếu danh sách thuốc và số lượng theo biên bản giao nhận từ nhà cung cấp</p>
        </div>

        <div className="flex items-center gap-2">
          <div className="relative">
            <input
              type="text"
              placeholder="Tìm mã phiếu / NCC…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-8 pr-3 py-2 border rounded-xl text-xs font-semibold w-48 sm:w-60"
            />
            <Search size={14} className="absolute left-2.5 top-2.5 text-slate-400" />
          </div>
        </div>
      </div>

      {/* Receipts List */}
      <div className="space-y-3">
        {loading ? (
          <div className="p-12 text-center text-slate-400 font-bold bg-white rounded-2xl border">
            Đang tải danh sách phiếu nhập…
          </div>
        ) : filteredReceipts.length === 0 ? (
          <div className="p-12 text-center text-slate-400 font-bold bg-white rounded-2xl border">
            Không tìm thấy phiếu nhập nào phù hợp.
          </div>
        ) : (
          filteredReceipts.map((r) => (
            <div
              key={r.id}
              className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm hover:border-emerald-300 transition flex flex-col sm:flex-row sm:items-center justify-between gap-4"
            >
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <span className="font-mono font-black text-base text-emerald-800">{r.receipt_code}</span>
                  <span
                    className={`px-2.5 py-0.5 rounded-full text-[10px] font-black uppercase ${
                      r.status === 'CONFIRMED'
                        ? 'bg-emerald-100 text-emerald-800'
                        : 'bg-amber-100 text-amber-800'
                    }`}
                  >
                    {r.status === 'CONFIRMED' ? 'Đã nhập kho' : r.status}
                  </span>
                </div>
                <div className="text-xs font-bold text-slate-700">
                  Nhà cung cấp: <span className="text-slate-900">{r.supplier_name}</span>
                </div>
                <div className="text-[11px] text-slate-500 flex items-center gap-4">
                  <span>📦 {r.items_count} mặt hàng</span>
                  {r.received_date && (
                    <span>📅 Ngày nhận: {new Date(r.received_date).toLocaleDateString('vi-VN')}</span>
                  )}
                  {r.note && <span>💬 {r.note}</span>}
                </div>
              </div>

              <div className="flex items-center gap-3">
                <div className="text-right hidden sm:block">
                  <div className="text-[11px] text-slate-400">Thời gian tạo</div>
                  <div className="text-xs font-bold text-slate-600">
                    {r.created_at ? new Date(r.created_at).toLocaleString('vi-VN') : '—'}
                  </div>
                </div>
                <div className="p-2.5 rounded-xl bg-emerald-50 text-emerald-700">
                  <CheckCircle2 size={22} />
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
