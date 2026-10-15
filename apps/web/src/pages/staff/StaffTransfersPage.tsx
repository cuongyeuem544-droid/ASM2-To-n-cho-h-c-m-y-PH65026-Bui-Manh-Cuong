import { useEffect, useState } from 'react'
import { ArrowLeftRight, CheckCircle2, Clock, Truck, AlertTriangle } from 'lucide-react'
import { api } from '../../services/api'

interface TransferItem {
  id: number
  transfer_code: string
  order_id: number | null
  from_warehouse: { id: number; name: string; code: string }
  to_warehouse: { id: number; name: string; code: string }
  status: string
  note: string | null
  shipped_at: string | null
  received_at: string | null
  created_at: string | null
  items_count: number
}

export function StaffTransfersPage() {
  const [transfers, setTransfers] = useState<TransferItem[]>([])
  const [loading, setLoading] = useState(true)
  const [processingId, setProcessingId] = useState<number | null>(null)

  const fetchTransfers = () => {
    setLoading(true)
    api<TransferItem[]>('/warehouse-portal/transfers?direction=inbound')
      .then((res) => setTransfers(res || []))
      .catch((err) => console.error(err))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    fetchTransfers()
  }, [])

  const handleReceive = async (transferId: number) => {
    if (!confirm('Xác nhận bạn đã kiểm đếm đầy đủ thuốc và muốn nhập vào kho chi nhánh?')) return

    setProcessingId(transferId)
    try {
      const res = await api<{ success: boolean; message: string }>(
        `/warehouse-portal/transfers/${transferId}/receive`,
        { method: 'POST' }
      )
      alert(res.message || 'Đã tiếp nhận kiện hàng điều chuyển thành công!')
      fetchTransfers()
    } catch (err: any) {
      alert(err?.message || 'Không thể tiếp nhận hàng')
    } finally {
      setProcessingId(null)
    }
  }

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 bg-white p-5 rounded-2xl border border-slate-200">
        <div>
          <div className="text-xs font-black uppercase text-emerald-700 tracking-wider">
            5. TIẾP NHẬN HÀNG ĐIỀU CHUYỂN NỘI BỘ
          </div>
          <h1 className="text-xl font-black text-slate-800">Kiện Hàng Luân Chuyển Đến</h1>
          <p className="text-xs text-slate-500">
            Hàng được gửi từ chi nhánh kho khác đến kho này để giao cho khách hàng hoặc bổ sung tồn
          </p>
        </div>

        <button
          onClick={fetchTransfers}
          className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl text-xs font-bold transition"
        >
          Làm mới danh sách
        </button>
      </div>

      {/* Transfers List */}
      <div className="space-y-3">
        {loading ? (
          <div className="p-12 text-center text-slate-400 font-bold bg-white rounded-2xl border">
            Đang tải danh sách điều chuyển…
          </div>
        ) : transfers.length === 0 ? (
          <div className="p-12 text-center text-slate-400 font-bold bg-white rounded-2xl border">
            Hiện không có kiện hàng điều chuyển nào đang chuyển đến kho này.
          </div>
        ) : (
          transfers.map((t) => {
            const canReceive = t.status === 'IN_TRANSIT' || t.status === 'DRAFT'
            return (
              <div
                key={t.id}
                className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm hover:border-emerald-300 transition flex flex-col sm:flex-row sm:items-center justify-between gap-4"
              >
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="font-mono font-black text-base text-emerald-800">{t.transfer_code}</span>
                    <span
                      className={`px-2.5 py-0.5 rounded-full text-[10px] font-black uppercase ${
                        t.status === 'RECEIVED'
                          ? 'bg-emerald-100 text-emerald-800'
                          : t.status === 'IN_TRANSIT'
                          ? 'bg-blue-100 text-blue-800'
                          : 'bg-amber-100 text-amber-800'
                      }`}
                    >
                      {t.status === 'RECEIVED' ? 'Đã tiếp nhận' : t.status === 'IN_TRANSIT' ? 'Đang giao tới' : t.status}
                    </span>
                  </div>

                  <div className="text-xs font-bold text-slate-700 flex items-center gap-2">
                    <span>Từ kho:</span>
                    <span className="px-2 py-0.5 bg-slate-100 text-slate-800 rounded font-semibold">
                      {t.from_warehouse.name} ({t.from_warehouse.code})
                    </span>
                    <span>→ Kho nhận:</span>
                    <span className="px-2 py-0.5 bg-emerald-50 text-emerald-800 rounded font-bold">
                      {t.to_warehouse.name}
                    </span>
                  </div>

                  <div className="text-[11px] text-slate-500 flex items-center gap-4">
                    <span>📦 {t.items_count} mặt hàng</span>
                    {t.order_id && <span>🛒 Đơn hàng: #{t.order_id}</span>}
                    {t.shipped_at && (
                      <span>🚚 Xuất kho: {new Date(t.shipped_at).toLocaleString('vi-VN')}</span>
                    )}
                    {t.note && <span>💬 {t.note}</span>}
                  </div>
                </div>

                <div>
                  {canReceive ? (
                    <button
                      onClick={() => handleReceive(t.id)}
                      disabled={processingId === t.id}
                      className="px-5 py-2.5 bg-emerald-700 hover:bg-emerald-800 text-white rounded-xl text-xs font-bold shadow flex items-center gap-2 transition"
                    >
                      <CheckCircle2 size={16} />
                      {processingId === t.id ? 'Đang tiếp nhận…' : 'Xác Nhận Nhận Hàng'}
                    </button>
                  ) : (
                    <div className="flex items-center gap-1.5 text-xs font-bold text-emerald-700 bg-emerald-50 px-3 py-1.5 rounded-xl border border-emerald-200">
                      <CheckCircle2 size={15} /> Đã vào kho ({t.received_at ? new Date(t.received_at).toLocaleDateString('vi-VN') : 'Xong'})
                    </div>
                  )}
                </div>
              </div>
            )
          })
        )}
      </div>
    </div>
  )
}
