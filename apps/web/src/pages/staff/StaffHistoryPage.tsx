import { useEffect, useState } from 'react'
import { History, Clock, FileText, CheckCircle2 } from 'lucide-react'
import { api } from '../../services/api'

interface StaffLog {
  id: number
  action: string
  entity_type: string
  entity_id: number
  created_at: string | null
  details: string | null
}

export function StaffHistoryPage() {
  const [logs, setLogs] = useState<StaffLog[]>([])
  const [loading, setLoading] = useState(true)

  const fetchHistory = () => {
    setLoading(true)
    api<StaffLog[]>('/warehouse-portal/staff/my-history')
      .then((res) => setLogs(res || []))
      .catch((err) => console.error(err))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    fetchHistory()
  }, [])

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 bg-white p-5 rounded-2xl border border-slate-200">
        <div>
          <div className="text-xs font-black uppercase text-emerald-700 tracking-wider">
            7. LỊCH SỬ THAO TÁC CÁ NHÂN
          </div>
          <h1 className="text-xl font-black text-slate-800">Nhật Ký Công Việc Đã Thực Hiện</h1>
          <p className="text-xs text-slate-500">Ghi nhận minh bạch các đơn hàng đã đóng gói, kiểm kê và tiếp nhận</p>
        </div>

        <button
          onClick={fetchHistory}
          className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl text-xs font-bold transition"
        >
          Làm mới lịch sử
        </button>
      </div>

      {/* History Timeline List */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="p-4 border-b bg-slate-50 flex items-center justify-between">
          <span className="text-xs font-black uppercase text-slate-600">50 thao tác gần nhất của bạn</span>
          <span className="text-xs font-bold text-slate-500">{logs.length} bản ghi</span>
        </div>

        <div className="divide-y divide-slate-100">
          {loading ? (
            <div className="p-10 text-center text-slate-400 font-bold">Đang tải lịch sử công việc…</div>
          ) : logs.length === 0 ? (
            <div className="p-10 text-center text-slate-400 font-bold">Chưa có thao tác nào được ghi nhận hôm nay.</div>
          ) : (
            logs.map((log) => (
              <div key={log.id} className="p-4 hover:bg-slate-50/80 transition flex items-center justify-between gap-4">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="px-2.5 py-0.5 rounded-full text-[10px] font-black uppercase tracking-wider bg-emerald-100 text-emerald-800">
                      {log.action}
                    </span>
                    <span className="text-xs font-bold text-slate-700">
                      {log.entity_type} #{log.entity_id}
                    </span>
                  </div>

                  {log.details && (
                    <div className="text-xs text-slate-600 font-mono bg-slate-50 px-2.5 py-1 rounded border inline-block max-w-2xl truncate">
                      {typeof log.details === 'string' ? log.details : JSON.stringify(log.details)}
                    </div>
                  )}

                  <div className="text-[11px] text-slate-400 flex items-center gap-1">
                    <Clock size={12} />
                    {log.created_at ? new Date(log.created_at).toLocaleString('vi-VN') : '—'}
                  </div>
                </div>

                <div className="text-emerald-600">
                  <CheckCircle2 size={18} />
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  )
}
