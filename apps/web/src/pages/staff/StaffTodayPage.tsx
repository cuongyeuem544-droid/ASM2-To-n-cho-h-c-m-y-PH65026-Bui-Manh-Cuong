import { useEffect, useState } from 'react'
import {
  CheckSquare,
  PackageCheck,
  ArrowRight,
  Clock,
  CheckCircle2,
  AlertTriangle,
} from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { api } from '../../services/api'

interface TaskData {
  warehouse: { id: number; code: string; name: string }
  picking_tasks: Array<{
    order_id: number
    order_code: string
    customer_name: string
    customer_phone: string
    items_count: number
    fulfillment_status: string
    created_at: string | null
  }>
  packing_tasks: Array<{
    order_id: number
    order_code: string
    customer_name: string
    items_count: number
    created_at: string | null
  }>
  inbound_transfers: Array<{
    transfer_id: number
    transfer_code: string
    from_warehouse_name: string
    items_count: number
    status: string
  }>
}

export function StaffTodayPage() {
  const navigate = useNavigate()
  const [data, setData] = useState<TaskData | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api<TaskData>('/warehouse-portal/staff/today-tasks')
      .then((res) => setData(res))
      .catch((err) => console.error(err))
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return <div className="p-8 text-center text-slate-500 font-bold text-lg">Đang tải công việc hôm nay…</div>
  }

  if (!data) {
    return <div className="p-8 text-center text-rose-500 font-bold">Không thể tải nhiệm vụ. Vui lòng thử lại.</div>
  }

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      {/* Top Banner */}
      <div className="bg-emerald-800 text-white rounded-2xl p-6 shadow-md flex flex-col sm:flex-row items-center justify-between gap-4">
        <div>
          <div className="text-xs uppercase font-bold text-emerald-200">BÀN SOẠN HÀNG & ĐÓNG GÓI CHI NHÁNH</div>
          <h1 className="text-2xl font-black">{data.warehouse.name} ({data.warehouse.code})</h1>
          <p className="text-xs text-emerald-100 mt-1">Nhiệm vụ trực ban đóng gói và soạn thuốc hôm nay</p>
        </div>
        <button
          onClick={() => navigate('/staff/picking-packing')}
          className="bg-white text-emerald-900 px-6 py-3 rounded-xl font-black text-sm shadow hover:bg-emerald-50 transition flex items-center gap-2"
        >
          <PackageCheck size={18} /> MỞ BÀN SOẠN ĐƠN NGAY
        </button>
      </div>

      {/* Task Summary Touch Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        {/* Card 1: Don can soan */}
        <div
          onClick={() => navigate('/staff/picking-packing')}
          className="bg-white p-6 rounded-2xl border-2 border-amber-200 hover:border-amber-400 cursor-pointer shadow-sm transition hover:shadow-md space-y-4"
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-black uppercase text-amber-800 bg-amber-100 px-3 py-1 rounded-full">
              1. CẦN LẤY HÀNG
            </span>
            <CheckSquare className="text-amber-600" size={26} />
          </div>
          <div>
            <div className="text-4xl font-black text-amber-600">
              {data.picking_tasks.length}
            </div>
            <div className="text-xs font-bold text-slate-500 mt-1">Đơn hàng cần lấy thuốc theo lô FEFO</div>
          </div>
          <div className="text-xs font-bold text-amber-700 flex items-center gap-1 pt-2 border-t">
            Bắt đầu soạn hàng <ArrowRight size={14} />
          </div>
        </div>

        {/* Card 2: Don can dong goi */}
        <div
          onClick={() => navigate('/staff/picking-packing')}
          className="bg-white p-6 rounded-2xl border-2 border-teal-200 hover:border-teal-400 cursor-pointer shadow-sm transition hover:shadow-md space-y-4"
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-black uppercase text-teal-800 bg-teal-100 px-3 py-1 rounded-full">
              2. CẦN ĐÓNG GÓI
            </span>
            <PackageCheck className="text-teal-600" size={26} />
          </div>
          <div>
            <div className="text-4xl font-black text-teal-600">
              {data.packing_tasks.length}
            </div>
            <div className="text-xs font-bold text-slate-500 mt-1">Đơn đã lấy đủ thuốc, chờ dán tem & đóng hộp</div>
          </div>
          <div className="text-xs font-bold text-teal-700 flex items-center gap-1 pt-2 border-t">
            Đóng gói & In phiếu <ArrowRight size={14} />
          </div>
        </div>

              </div>

      {/* Immediate Pick Task List */}
      <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm space-y-4">
        <h2 className="text-base font-black text-slate-800 flex items-center gap-2">
          <Clock size={18} className="text-amber-500" /> Danh Sách Đơn Cần Soạn Ngay
        </h2>
        {data.picking_tasks.length === 0 ? (
          <div className="py-8 text-center text-slate-400 font-medium">Hiện không có đơn nào đang chờ soạn. Tuyệt vời!</div>
        ) : (
          <div className="divide-y divide-slate-100">
            {data.picking_tasks.map((task) => (
              <div key={task.order_id} className="py-3 flex items-center justify-between gap-4">
                <div>
                  <div className="font-mono font-bold text-emerald-800 text-sm">{task.order_code}</div>
                  <div className="text-xs text-slate-600">
                    Khách: <b>{task.customer_name}</b> • {task.items_count} dòng sản phẩm
                  </div>
                </div>
                <button
                  onClick={() => navigate(`/staff/picking-packing?order_id=${task.order_id}`)}
                  className="px-4 py-2 bg-emerald-700 hover:bg-emerald-800 text-white rounded-xl text-xs font-bold shadow flex items-center gap-1 transition"
                >
                  Lấy thuốc ngay
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
