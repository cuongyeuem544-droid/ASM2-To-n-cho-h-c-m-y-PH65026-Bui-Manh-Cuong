import { useEffect, useState } from 'react'
import { Boxes, Search, AlertCircle, ShieldAlert, Package } from 'lucide-react'
import { api } from '../../services/api'

interface StockItem {
  product_id: number
  product_name: string
  registration_number: string
  product_type: string
  sku_id: number
  sku_code: string
  unit_name: string
  total_on_hand: number
  total_available: number
  total_reserved: number
  batches_count: number
}

export function StaffStockPage() {
  const [items, setItems] = useState<StockItem[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')

  const fetchStock = (searchTerm = '') => {
    setLoading(true)
    const url = searchTerm
      ? `/warehouse-portal/stock?search=${encodeURIComponent(searchTerm)}&page_size=50`
      : '/warehouse-portal/stock?page_size=50'

    api<{ items: StockItem[]; total: number }>(url)
      .then((res) => {
        setItems(res.items || [])
        setTotal(res.total || 0)
      })
      .catch((err) => console.error(err))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    fetchStock()
  }, [])

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    fetchStock(search.trim())
  }

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 bg-white p-5 rounded-2xl border border-slate-200">
        <div>
          <div className="text-xs font-black uppercase text-emerald-700 tracking-wider">
            6. TRA CỨU TỒN KHO & VỊ TRÍ THUỐC (CHỈ XEM)
          </div>
          <h1 className="text-xl font-black text-slate-800">Danh Mục Thuốc Hiện Có Trong Kho</h1>
          <p className="text-xs text-slate-500">Tra cứu nhanh số lượng thuốc khả dụng và đơn vị đóng gói để soạn hàng</p>
        </div>

        <form onSubmit={handleSearch} className="flex items-center gap-2">
          <div className="relative">
            <input
              type="text"
              placeholder="Tên thuốc / SKU / Số ĐK…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-8 pr-3 py-2 border rounded-xl text-xs font-semibold w-48 sm:w-64"
            />
            <Search size={14} className="absolute left-2.5 top-2.5 text-slate-400" />
          </div>
          <button
            type="submit"
            className="px-4 py-2 bg-emerald-700 hover:bg-emerald-800 text-white rounded-xl text-xs font-bold shadow"
          >
            Tìm
          </button>
        </form>
      </div>

      {/* Stock Cards Grid */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="p-4 border-b bg-slate-50 flex items-center justify-between">
          <span className="text-xs font-black uppercase text-slate-600">Tổng cộng {total} mặt hàng có tại kho</span>
          <span className="text-[11px] font-bold text-slate-400 bg-slate-200 px-2 py-0.5 rounded">
            🔒 Chế độ nhân viên: Không hiển thị giá tài chính
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 text-slate-500 text-xs font-bold uppercase border-b border-slate-200">
              <tr>
                <th className="px-5 py-3.5">Tên Thuốc & Quy Cách</th>
                <th className="px-5 py-3.5">Mã SKU / Số ĐK</th>
                <th className="px-5 py-3.5">Đơn Vị</th>
                <th className="px-5 py-3.5 text-center">Số Lô</th>
                <th className="px-5 py-3.5 text-right">Tồn Thực Tế</th>
                <th className="px-5 py-3.5 text-right">Khả Dụng Để Bán</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading ? (
                <tr>
                  <td colSpan={6} className="px-5 py-10 text-center text-slate-400 font-bold">
                    Đang tra cứu danh mục thuốc…
                  </td>
                </tr>
              ) : items.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-5 py-10 text-center text-slate-400 font-bold">
                    Không tìm thấy thuốc nào khớp với từ khóa.
                  </td>
                </tr>
              ) : (
                items.map((it) => (
                  <tr key={it.sku_id} className="hover:bg-slate-50/70 transition">
                    <td className="px-5 py-3.5">
                      <div className="font-black text-slate-900 text-sm">{it.product_name}</div>
                      <div className="text-[11px] text-slate-400 font-semibold uppercase">{it.product_type}</div>
                    </td>
                    <td className="px-5 py-3.5 font-mono text-xs text-slate-600">
                      <div>{it.sku_code}</div>
                      <div className="text-[11px] text-slate-400">{it.registration_number || '—'}</div>
                    </td>
                    <td className="px-5 py-3.5">
                      <span className="px-2 py-0.5 rounded-lg bg-slate-100 text-slate-700 text-xs font-bold">
                        {it.unit_name}
                      </span>
                    </td>
                    <td className="px-5 py-3.5 text-center font-bold text-slate-700">
                      {it.batches_count} lô
                    </td>
                    <td className="px-5 py-3.5 text-right font-black text-slate-800 text-base">
                      {(it.total_on_hand ?? 0).toLocaleString()}
                    </td>
                    <td className="px-5 py-3.5 text-right font-black text-emerald-700 text-base">
                      {(it.total_available ?? 0).toLocaleString()}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
