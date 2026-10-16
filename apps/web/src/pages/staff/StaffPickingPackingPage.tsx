import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  PackageCheck,
  CheckCircle2,
  Clock,
  Printer,
  Truck,
  AlertTriangle,
  Search,
  X,
  Layers,
} from 'lucide-react'
import { api } from '../../services/api'

interface OrderItem {
  id: number
  order_code: string
  customer_name: string
  customer_phone: string
  shipping_address: string
  order_status?: string
  fulfillment_status: string
  items_count: number
  created_at: string | null
}

interface PickDetailLine {
  order_item_id: number
  sku_id: number
  product_name: string
  unit: string
  quantity_required: number
  suggested_batches: Array<{
    batch_id: number
    batch_number: string
    expiry_date: string
    quantity_available: number
  }>
}

interface PickDetailResponse {
  order_id: number
  order_code: string
  customer_name: string
  customer_phone: string
  shipping_address: string
  order_status?: string
  fulfillment_status: string
  lines: PickDetailLine[]
}

export function StaffPickingPackingPage() {
  const [searchParams] = useSearchParams()
  const [orders, setOrders] = useState<OrderItem[]>([])
  const [selectedOrderId, setSelectedOrderId] = useState<number | null>(null)
  const [detail, setDetail] = useState<PickDetailResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [loadingDetail, setLoadingDetail] = useState(false)
  const [checkedItems, setCheckedItems] = useState<Record<number, boolean>>({})

  // Issue reporting modal
  const [showIssueModal, setShowIssueModal] = useState(false)
  const [issueType, setIssueType] = useState('OUT_OF_STOCK')
  const [issueReason, setIssueReason] = useState('')
  const [reporting, setReporting] = useState(false)

  const fetchOrders = () => {
    setLoading(true)
    api<{ items: OrderItem[] }>('/warehouse-portal/orders?page_size=50')
      .then((res) => {
        setOrders(res.items || [])
        const queryOrderId = searchParams.get('order_id')
        if (queryOrderId) {
          loadOrderDetail(Number(queryOrderId))
        } else if (res.items && res.items.length > 0) {
          loadOrderDetail(res.items[0].id)
        }
      })
      .catch((err) => console.error(err))
      .finally(() => setLoading(false))
  }

  const loadOrderDetail = async (orderId: number) => {
    setSelectedOrderId(orderId)
    setLoadingDetail(true)
    setCheckedItems({})
    try {
      const res = await api<PickDetailResponse>(`/warehouse-portal/orders/${orderId}/pick-details`)
      setDetail(res)
    } catch (err: any) {
      alert(err?.message || 'Không thể tải chi tiết đơn hàng')
    } finally {
      setLoadingDetail(false)
    }
  }

  useEffect(() => {
    fetchOrders()
  }, [])

  const handleToggleCheck = (itemId: number) => {
    setCheckedItems((prev) => ({ ...prev, [itemId]: !prev[itemId] }))
  }

  const handleUpdateStatus = async (newStatus: string) => {
    if (!selectedOrderId) return
    try {
      await api(`/warehouse-portal/orders/${selectedOrderId}/fulfillment`, {
        method: 'PATCH',
        body: JSON.stringify({ fulfillment_status: newStatus }),
      })
      alert(`Đã cập nhật đơn sang trạng thái: ${newStatus}`)
      loadOrderDetail(selectedOrderId)
      fetchOrders()
    } catch (err: any) {
      alert(err?.message || 'Không thể cập nhật tiến trình đơn')
    }
  }

  const handleReportIssue = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!selectedOrderId || !issueReason.trim()) return

    setReporting(true)
    try {
      await api(`/warehouse-portal/orders/${selectedOrderId}/report-issue`, {
        method: 'POST',
        body: JSON.stringify({ issue_type: issueType, reason: issueReason.trim() }),
      })
      setShowIssueModal(false)
      setIssueReason('')
      alert('Đã báo sự cố cho quản lý kho!')
    } catch (err: any) {
      alert(err?.message || 'Không thể gửi báo cáo sự cố')
    } finally {
      setReporting(false)
    }
  }

  const handlePrintSlip = () => {
    window.print()
  }

  const allItemsChecked = detail?.lines && detail.lines.length > 0 && detail.lines.every((l) => checkedItems[l.order_item_id])

  return (
    <div className="space-y-4 max-w-7xl mx-auto">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 bg-white p-4 rounded-xl border border-slate-200">
        <div>
          <h1 className="text-xl font-black text-slate-800">Bàn Soạn Hàng & Đóng Gói (Touch Station)</h1>
          <p className="text-xs text-slate-500">Quy trình: Lấy thuốc theo lô FEFO &gt; Đóng gói &gt; In phiếu &gt; Bàn giao bưu tá</p>
        </div>
        {detail && (
          <div className="flex items-center gap-2">
            <button
              onClick={handlePrintSlip}
              className="px-4 py-2.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl text-xs font-bold flex items-center gap-2 transition"
            >
              <Printer size={16} /> In Phiếu Giao
            </button>
            <button
              onClick={() => setShowIssueModal(true)}
              className="px-4 py-2.5 bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 rounded-xl text-xs font-bold flex items-center gap-2 transition"
            >
              <AlertTriangle size={16} /> Báo Hàng Thiếu / Hỏng
            </button>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Orders Queue */}
        <div className="bg-white rounded-2xl border border-slate-200 p-4 shadow-sm space-y-3 h-[750px] flex flex-col">
          <div className="flex items-center justify-between border-b pb-3">
            <span className="text-xs font-black uppercase text-slate-700">Hàng đợi đơn hàng</span>
            <span className="text-xs font-bold text-emerald-800 bg-emerald-100 px-2.5 py-0.5 rounded-full">
              {orders.length} đơn
            </span>
          </div>

          <div className="overflow-y-auto flex-1 space-y-2 pr-1">
            {loading ? (
              <div className="py-8 text-center text-slate-400">Đang tải…</div>
            ) : orders.map((o) => (
              <div
                key={o.id}
                onClick={() => loadOrderDetail(o.id)}
                className={`p-3.5 rounded-xl border-2 cursor-pointer transition text-left space-y-1 ${
                  selectedOrderId === o.id
                    ? 'border-emerald-600 bg-emerald-50/60 shadow-sm'
                    : 'border-slate-100 hover:border-slate-200 bg-slate-50/50'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="font-mono font-black text-sm text-emerald-900">{o.order_code}</span>
                  <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                    (o.fulfillment_status === 'CANCELLED' || o.order_status === 'CANCELLED') ? 'bg-rose-100 text-rose-800' :
                    o.fulfillment_status === 'PICKING' ? 'bg-amber-100 text-amber-800' :
                    o.fulfillment_status === 'PACKED' ? 'bg-teal-100 text-teal-800' :
                    o.fulfillment_status === 'SHIPPED' ? 'bg-blue-100 text-blue-800' :
                    o.fulfillment_status === 'DELIVERED' ? 'bg-emerald-100 text-emerald-800' :
                    'bg-slate-200 text-slate-700'
                  }`}>
                    {(o.fulfillment_status === 'CANCELLED' || o.order_status === 'CANCELLED') ? 'ĐÃ HỦY' : o.fulfillment_status}
                  </span>
                </div>
                <div className="text-xs font-bold text-slate-800 truncate">{o.customer_name}</div>
                <div className="text-[11px] text-slate-500">{o.items_count} mặt hàng • {o.customer_phone}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Right Column: Active Order Picking Checklist */}
        <div className="lg:col-span-2 bg-white rounded-2xl border border-slate-200 p-6 shadow-sm space-y-5 flex flex-col justify-between">
          {loadingDetail ? (
            <div className="py-20 text-center text-slate-400 font-bold">Đang tải dữ liệu soạn hàng…</div>
          ) : !detail ? (
            <div className="py-20 text-center text-slate-400 font-bold">Chọn một đơn hàng ở cột bên trái để soạn thuốc.</div>
          ) : (
            <>
              <div className="space-y-4">
                {/* Cancelled Alert Banner */}
                {(detail.fulfillment_status === 'CANCELLED' || detail.order_status === 'CANCELLED') && (
                  <div className="bg-rose-50 border-2 border-rose-300 rounded-2xl p-4 text-rose-800 flex items-start gap-3">
                    <AlertTriangle size={24} className="text-rose-600 flex-shrink-0 mt-0.5" />
                    <div>
                      <div className="font-black text-sm uppercase tracking-wide">Đơn hàng này đã bị hủy</div>
                      <div className="text-xs text-rose-700 mt-1 font-semibold">
                        Khách hàng hoặc quản trị viên đã hủy đơn này. Toàn bộ thuốc đã được hoàn trả tồn kho. Vui lòng không thực hiện lấy thuốc, đóng gói hay giao hàng.
                      </div>
                    </div>
                  </div>
                )}

                {/* Order Summary Card */}
                <div className="bg-slate-50 p-4 rounded-xl border border-slate-200 flex flex-col sm:flex-row justify-between gap-4">
                  <div>
                    <div className="font-mono font-black text-lg text-emerald-900">{detail.order_code}</div>
                    <div className="text-xs text-slate-600 font-bold mt-0.5">Khách: {detail.customer_name} ({detail.customer_phone})</div>
                    <div className="text-xs text-slate-500 mt-1">📍 {detail.shipping_address}</div>
                  </div>
                  <div className="text-right">
                    <span className={`px-3 py-1 rounded-full text-xs font-black uppercase tracking-wider ${
                      (detail.fulfillment_status === 'CANCELLED' || detail.order_status === 'CANCELLED')
                        ? 'bg-rose-100 text-rose-800'
                        : 'bg-emerald-100 text-emerald-800'
                    }`}>
                      {(detail.fulfillment_status === 'CANCELLED' || detail.order_status === 'CANCELLED') ? 'ĐÃ HỦY' : detail.fulfillment_status}
                    </span>
                  </div>
                </div>

                {/* Items Checklist */}
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <h3 className="text-xs font-black uppercase text-slate-500 tracking-wider">
                      Danh sách thuốc cần lấy (Tích chọn khi đã lấy đủ)
                    </h3>
                    <span className="text-xs font-bold text-emerald-700">
                      Đã lấy: {Object.values(checkedItems).filter(Boolean).length} / {detail.lines.length}
                    </span>
                  </div>

                  <div className="space-y-2.5 max-h-[360px] overflow-y-auto pr-1">
                    {detail.lines.map((line) => {
                      const isChecked = !!checkedItems[line.order_item_id]
                      return (
                        <div
                          key={line.order_item_id}
                          onClick={() => handleToggleCheck(line.order_item_id)}
                          className={`p-4 rounded-xl border-2 cursor-pointer transition flex items-center justify-between gap-4 ${
                            isChecked
                              ? 'border-emerald-500 bg-emerald-50/70'
                              : 'border-slate-200 bg-white hover:border-slate-300'
                          }`}
                        >
                          <div className="flex items-center gap-3.5">
                            <input
                              type="checkbox"
                              checked={isChecked}
                              onChange={() => {}}
                              className="w-6 h-6 rounded text-emerald-600 focus:ring-emerald-500"
                            />
                            <div>
                              <div className={`font-black text-sm ${isChecked ? 'line-through text-slate-500' : 'text-slate-800'}`}>
                                {line.product_name}
                              </div>
                              <div className="text-xs text-slate-500">
                                Đơn vị: <b>{line.unit}</b>
                              </div>
                              {line.suggested_batches.length > 0 && (
                                <div className="text-[11px] text-emerald-700 font-mono mt-0.5">
                                  Lô FEFO: <b>{line.suggested_batches[0].batch_number}</b> (HSD: {line.suggested_batches[0].expiry_date})
                                </div>
                              )}
                            </div>
                          </div>

                          <div className="text-right">
                            <span className="text-xl font-black text-emerald-800">x{line.quantity_required}</span>
                          </div>
                        </div>
                      )
                    })}
                  </div>
                </div>
              </div>

              {/* Big Stage Progression Buttons */}
              <div className="pt-4 border-t space-y-3">
                {(detail.fulfillment_status === 'CANCELLED' || detail.order_status === 'CANCELLED') ? (
                  <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-center text-rose-700 font-bold text-sm">
                    ⚠️ Đơn hàng đã bị hủy. Mọi thao tác soạn hàng và chuyển trạng thái đã bị khóa.
                  </div>
                ) : (
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
                    <button
                      onClick={() => handleUpdateStatus('PICKING')}
                      className={`py-4 rounded-xl font-black text-sm uppercase transition flex items-center justify-center gap-2 ${
                        detail.fulfillment_status === 'PICKING'
                          ? 'bg-amber-600 text-white shadow-md'
                          : 'bg-amber-50 text-amber-800 border border-amber-200 hover:bg-amber-100'
                      }`}
                    >
                      <Clock size={18} /> 1. Đang Soạn (PICKING)
                    </button>

                    <button
                      onClick={() => handleUpdateStatus('PACKED')}
                      className={`py-4 rounded-xl font-black text-sm uppercase transition flex items-center justify-center gap-2 ${
                        detail.fulfillment_status === 'PACKED'
                          ? 'bg-teal-700 text-white shadow-md'
                          : 'bg-teal-50 text-teal-800 border border-teal-200 hover:bg-teal-100'
                      }`}
                    >
                      <PackageCheck size={18} /> 2. Đã Đóng Gói (PACKED)
                    </button>

                    <button
                      onClick={() => handleUpdateStatus('SHIPPED')}
                      className={`py-4 rounded-xl font-black text-sm uppercase transition flex items-center justify-center gap-2 ${
                        detail.fulfillment_status === 'SHIPPED'
                          ? 'bg-blue-700 text-white shadow-md'
                          : 'bg-blue-50 text-blue-800 border border-blue-200 hover:bg-blue-100'
                      }`}
                    >
                      <Truck size={18} /> 3. Bàn Giao Xe (SHIPPED)
                    </button>

                    <button
                      onClick={() => handleUpdateStatus('DELIVERED')}
                      className={`py-4 rounded-xl font-black text-sm uppercase transition flex items-center justify-center gap-2 ${
                        detail.fulfillment_status === 'DELIVERED'
                          ? 'bg-emerald-700 text-white shadow-md'
                          : 'bg-emerald-50 text-emerald-800 border border-emerald-200 hover:bg-emerald-100'
                      }`}
                    >
                      <CheckCircle2 size={18} /> 4. Đã Giao (DELIVERED)
                    </button>
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      </div>

      {/* Report Issue Modal */}
      {showIssueModal && (
        <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 space-y-4">
            <div className="flex items-center justify-between border-b pb-3">
              <div className="flex items-center gap-2 text-rose-600">
                <AlertTriangle size={20} />
                <h3 className="text-base font-black text-slate-800">Báo Sự Cố Soạn Hàng</h3>
              </div>
              <button onClick={() => setShowIssueModal(false)} className="text-slate-400 hover:text-slate-600">
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleReportIssue} className="space-y-4">
              <div>
                <label className="block text-xs font-bold text-slate-700 uppercase mb-1">Loại sự cố</label>
                <select
                  value={issueType}
                  onChange={(e) => setIssueType(e.target.value)}
                  className="w-full px-3 py-2 border rounded-lg text-sm bg-white"
                >
                  <option value="OUT_OF_STOCK">Hết hàng / Không đủ tồn thực tế</option>
                  <option value="DAMAGED_PRODUCT">Thuốc bị móp méo / vỡ hỏng</option>
                  <option value="EXPIRED_BATCH">Lô thuốc cận hạn / quá hạn dùng</option>
                  <option value="OTHER">Lý do khác</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 uppercase mb-1">Mô tả chi tiết</label>
                <textarea
                  rows={3}
                  value={issueReason}
                  onChange={(e) => setIssueReason(e.target.value)}
                  placeholder="Ghi rõ mặt hàng thiếu, số lượng hoặc tình trạng hư hỏng…"
                  className="w-full px-3 py-2 border rounded-lg text-sm"
                  required
                />
              </div>

              <div className="flex justify-end gap-3 pt-3 border-t">
                <button
                  type="button"
                  onClick={() => setShowIssueModal(false)}
                  className="px-4 py-2 border rounded-xl text-sm font-semibold text-slate-600 hover:bg-slate-50"
                >
                  Hủy
                </button>
                <button
                  type="submit"
                  disabled={reporting}
                  className="px-5 py-2 bg-rose-600 hover:bg-rose-700 text-white rounded-xl text-sm font-bold shadow"
                >
                  {reporting ? 'Đang gửi…' : 'Gửi báo cáo sự cố'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
