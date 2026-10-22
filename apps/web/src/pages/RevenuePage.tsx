import React, { useEffect, useState, useCallback } from 'react'
import {
  Banknote,
  TrendingUp,
  RotateCcw,
  RefreshCw,
  Search,
  Building2,
  Calendar,
  AlertCircle,
  CreditCard,
  Truck,
  CheckCircle2,
  Clock,
  XCircle,
  FileSpreadsheet,
} from 'lucide-react'
import {
  ResponsiveContainer,
  ComposedChart,
  Line,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from 'recharts'
import { api } from '../services/api'

interface RevenueSummary {
  gross_gmv: number
  verified_collected_cash: number
  refund_amount: number
  refund_count: number
  net_cash: number
  recognized_revenue: number
  pending_cash: number
  total_orders: number
  paid_orders_count: number
  cancelled_orders_count: number
  pending_orders_count: number
  average_order_value: number
  time_range: {
    start_utc: string
    end_utc: string
  }
}

interface PaymentMethodBreakdown {
  payment_method: string
  total_orders: number
  gross_gmv: number
  collected_amount: number
  pending_amount: number
  paid_count: number
  failed_count: number
}

interface WarehouseBreakdown {
  warehouse_id: number
  warehouse_code: string
  warehouse_name: string
  total_orders: number
  gross_gmv: number
  collected_amount: number
  refund_amount: number
  net_cash: number
  paid_orders_count: number
}

interface TimeSeriesPoint {
  date: string
  order_count: number
  gross_gmv: number
  collected_cash: number
  refund_amount: number
  net_cash: number
}

interface FinancialTransaction {
  id: number
  order_code: string
  customer_name: string
  customer_phone: string
  payment_method: string
  payment_status: string
  order_status: string
  total_amount: number
  shipping_fee: number
  discount_amount: number
  warehouse_id: number
  warehouse_name: string
  is_cash_collected: boolean
  created_at: string | null
}

const formatVND = (val: number | null | undefined): string => {
  return `${(val ?? 0).toLocaleString('vi-VN')} đ`
}

const formatDate = (iso: string | null | undefined): string => {
  if (!iso) return '—'
  try {
    const d = new Date(iso)
    return d.toLocaleString('vi-VN', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return iso
  }
}

export function RevenuePage() {
  const [rangeType, setRangeType] = useState<string>('30d')
  const [selectedWarehouse, setSelectedWarehouse] = useState<string>('ALL')
  const [loading, setLoading] = useState<boolean>(true)
  const [error, setError] = useState<string | null>(null)

  // Data states
  const [summary, setSummary] = useState<RevenueSummary | null>(null)
  const [methods, setMethods] = useState<PaymentMethodBreakdown[]>([])
  const [warehouses, setWarehouses] = useState<WarehouseBreakdown[]>([])
  const [timeseries, setTimeseries] = useState<TimeSeriesPoint[]>([])

  // Transactions feed
  const [transactions, setTransactions] = useState<FinancialTransaction[]>([])
  const [txTotal, setTxTotal] = useState<number>(0)
  const [txPage, setTxPage] = useState<number>(1)
  const [txSearch, setTxSearch] = useState<string>('')
  const [txMethodFilter, setTxMethodFilter] = useState<string>('ALL')
  const [txStatusFilter, setTxStatusFilter] = useState<string>('ALL')

  const fetchData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const whParam = selectedWarehouse !== 'ALL' ? `&warehouse_id=${selectedWarehouse}` : ''

      const [summaryRes, methodRes, whRes, tsRes] = await Promise.all([
        api<RevenueSummary>(`/admin/analytics/revenue/summary?range_type=${rangeType}${whParam}`),
        api<PaymentMethodBreakdown[]>(`/admin/analytics/revenue/by-payment-method?range_type=${rangeType}${whParam}`),
        api<WarehouseBreakdown[]>(`/admin/analytics/revenue/by-warehouse?range_type=${rangeType}`),
        api<TimeSeriesPoint[]>(`/admin/analytics/revenue/timeseries?range_type=${rangeType}${whParam}`),
      ])

      setSummary(summaryRes)
      setMethods(methodRes || [])
      setWarehouses(whRes || [])
      setTimeseries(tsRes || [])
    } catch (err: any) {
      console.error('Lỗi nạp báo cáo doanh thu:', err)
      setError(err?.message || 'Không thể tải báo cáo doanh thu máy chủ')
    } finally {
      setLoading(false)
    }
  }, [rangeType, selectedWarehouse])

  const fetchTransactions = useCallback(async () => {
    try {
      const whParam = selectedWarehouse !== 'ALL' ? `&warehouse_id=${selectedWarehouse}` : ''
      const methodParam = txMethodFilter !== 'ALL' ? `&payment_method=${txMethodFilter}` : ''
      const statusParam = txStatusFilter !== 'ALL' ? `&payment_status=${txStatusFilter}` : ''
      const searchParam = txSearch.trim() ? `&search=${encodeURIComponent(txSearch.trim())}` : ''

      const res = await api<{ items: FinancialTransaction[]; total: number }>(
        `/admin/analytics/revenue/transactions?range_type=${rangeType}&page=${txPage}&page_size=15${whParam}${methodParam}${statusParam}${searchParam}`
      )
      setTransactions(res.items || [])
      setTxTotal(res.total || 0)
    } catch (err) {
      console.error('Lỗi tải danh sách giao dịch:', err)
    }
  }, [rangeType, selectedWarehouse, txPage, txMethodFilter, txStatusFilter, txSearch])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  useEffect(() => {
    fetchTransactions()
  }, [fetchTransactions])

  const rangeButtons = [
    { id: 'today', label: 'Hôm nay' },
    { id: 'yesterday', label: 'Hôm qua' },
    { id: '7d', label: '7 ngày' },
    { id: '30d', label: '30 ngày' },
    { id: 'this_month', label: 'Tháng này' },
    { id: 'last_month', label: 'Tháng trước' },
    { id: 'this_year', label: 'Năm nay' },
  ]

  return (
    <div className="space-y-6 pb-12">
      {/* 1. Header & Controls */}
      <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-blue-50 text-blue-600 border border-blue-100">
              <Banknote className="w-6 h-6" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-slate-800 tracking-tight">
                Báo Cáo Doanh Thu & Dòng Tiền
              </h1>
              <p className="text-sm text-slate-500 mt-0.5">
                Đối soát tài chính thực tế • COD chỉ tính khi giao hàng thành công • Không trùng lặp
              </p>
            </div>
          </div>
        </div>

        {/* Filter controls */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Warehouse Selector */}
          <div className="flex items-center gap-1.5 bg-slate-50 border border-slate-200 rounded-xl px-3 py-1.5 text-sm">
            <Building2 className="w-4 h-4 text-slate-400" />
            <select
              value={selectedWarehouse}
              onChange={(e) => setSelectedWarehouse(e.target.value)}
              className="bg-transparent border-none text-slate-700 font-medium focus:outline-none cursor-pointer"
            >
              <option value="ALL">Toàn hệ thống (Tất cả kho)</option>
              <option value="1">Kho HCM - Chi nhánh 1</option>
              <option value="2">Kho Hà Nội - Chi nhánh 2</option>
            </select>
          </div>

          {/* Refresh button */}
          <button
            onClick={() => {
              fetchData()
              fetchTransactions()
            }}
            disabled={loading}
            className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-white border border-slate-200 text-slate-700 hover:bg-slate-50 transition-colors shadow-2xs text-sm font-medium disabled:opacity-50"
            title="Làm mới số liệu"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin text-blue-600' : ''}`} />
            <span>Làm mới</span>
          </button>
        </div>
      </div>

      {/* Date Range Selector Pills */}
      <div className="flex items-center gap-1.5 overflow-x-auto pb-1">
        <span className="text-xs font-semibold uppercase tracking-wider text-slate-400 px-2 flex items-center gap-1">
          <Calendar className="w-3.5 h-3.5" /> Khoảng thời gian:
        </span>
        {rangeButtons.map((btn) => (
          <button
            key={btn.id}
            onClick={() => setRangeType(btn.id)}
            className={`px-3.5 py-1.5 rounded-full text-xs font-semibold transition-all ${
              rangeType === btn.id
                ? 'bg-blue-600 text-white shadow-sm'
                : 'bg-white border border-slate-200 text-slate-600 hover:bg-slate-50'
            }`}
          >
            {btn.label}
          </button>
        ))}
      </div>

      {/* Error alert */}
      {error && (
        <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 flex items-center justify-between text-rose-700">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-5 h-5 shrink-0" />
            <span className="text-sm font-medium">{error}</span>
          </div>
          <button
            onClick={() => fetchData()}
            className="px-3 py-1 bg-white border border-rose-300 rounded-lg text-xs font-bold hover:bg-rose-100"
          >
            Thử lại
          </button>
        </div>
      )}

      {/* 2. Master Financial KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Card 1: Gross GMV */}
        <div className="p-5 rounded-2xl bg-white border border-slate-200 shadow-xs hover:border-blue-200 transition-all">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-500">
              Tổng giá trị đơn hàng (GMV)
            </span>
            <span className="p-1.5 rounded-lg bg-blue-50 text-blue-600">
              <TrendingUp className="w-4 h-4" />
            </span>
          </div>
          <div className="mt-3">
            <div className="text-2xl font-black text-slate-900 tracking-tight">
              {formatVND(summary?.gross_gmv)}
            </div>
            <div className="text-xs text-slate-500 mt-1 flex items-center gap-2">
              <span>{summary?.total_orders ?? 0} đơn phát sinh</span>
              <span>•</span>
              <span>AOV: {formatVND(summary?.average_order_value)}</span>
            </div>
          </div>
        </div>

        {/* Card 2: Verified Collected Cash */}
        <div className="p-5 rounded-2xl bg-white border border-emerald-200 bg-gradient-to-br from-white to-emerald-50/20 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-emerald-700">
              Thực thu đã đối soát
            </span>
            <span className="p-1.5 rounded-lg bg-emerald-100 text-emerald-700">
              <CheckCircle2 className="w-4 h-4" />
            </span>
          </div>
          <div className="mt-3">
            <div className="text-2xl font-black text-emerald-800 tracking-tight">
              {formatVND(summary?.verified_collected_cash)}
            </div>
            <div className="text-xs text-emerald-600 mt-1">
              {summary?.paid_orders_count ?? 0} đơn đã thanh toán thành công
            </div>
          </div>
        </div>

        {/* Card 3: Refunds */}
        <div className="p-5 rounded-2xl bg-white border border-rose-200 bg-gradient-to-br from-white to-rose-50/20 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-rose-700">
              Hoàn tiền khách hàng
            </span>
            <span className="p-1.5 rounded-lg bg-rose-100 text-rose-700">
              <RotateCcw className="w-4 h-4" />
            </span>
          </div>
          <div className="mt-3">
            <div className="text-2xl font-black text-rose-700 tracking-tight">
              -{formatVND(summary?.refund_amount)}
            </div>
            <div className="text-xs text-rose-600 mt-1">
              {summary?.refund_count ?? 0} ca hoàn tiền thành công
            </div>
          </div>
        </div>

        {/* Card 4: Net Cash */}
        <div className="p-5 rounded-2xl bg-white border border-indigo-200 bg-gradient-to-br from-white to-indigo-50/20 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-indigo-700">
              Thực thu thuần (Net Cash)
            </span>
            <span className="p-1.5 rounded-lg bg-indigo-100 text-indigo-700">
              <Banknote className="w-4 h-4" />
            </span>
          </div>
          <div className="mt-3">
            <div className="text-2xl font-black text-indigo-900 tracking-tight">
              {formatVND(summary?.net_cash)}
            </div>
            <div className="text-xs text-indigo-600 mt-1">
              Thực thu sau khi trừ toàn bộ tiền hoàn
            </div>
          </div>
        </div>
      </div>

      {/* 3. Daily Time-Series Chart */}
      <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-base font-bold text-slate-800">
              Biểu Đồ Doanh Thu & Dòng Tiền Theo Ngày
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">
              So sánh Tổng giá trị phát sinh (GMV) và Dòng tiền thực thu thực tế
            </p>
          </div>
        </div>

        <div className="h-72 w-full">
          {timeseries.length === 0 ? (
            <div className="h-full flex items-center justify-center text-slate-400 text-sm">
              Chưa có dữ liệu trong khoảng thời gian đã chọn
            </div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={timeseries} margin={{ top: 10, right: 20, left: 20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                <XAxis
                  dataKey="date"
                  tickLine={false}
                  axisLine={{ stroke: '#e2e8f0' }}
                  tick={{ fontSize: 11, fill: '#64748b' }}
                  tickFormatter={(val) => {
                    const parts = val.split('-')
                    return parts.length === 3 ? `${parts[2]}/${parts[1]}` : val
                  }}
                />
                <YAxis
                  tickLine={false}
                  axisLine={{ stroke: '#e2e8f0' }}
                  tick={{ fontSize: 11, fill: '#64748b' }}
                  tickFormatter={(val) => `${(val / 1000).toLocaleString('vi-VN')}k`}
                />
                <Tooltip
                  formatter={(value: any) => [formatVND(Number(value)), '']}
                  labelFormatter={(lbl) => `Ngày ${lbl}`}
                  contentStyle={{
                    borderRadius: '12px',
                    border: '1px solid #e2e8f0',
                    boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)',
                  }}
                />
                <Legend
                  verticalAlign="top"
                  align="right"
                  wrapperStyle={{ paddingBottom: '12px', fontSize: '12px' }}
                />
                <Bar dataKey="gross_gmv" name="Giá trị phát sinh (GMV)" fill="#93c5fd" radius={[4, 4, 0, 0]} />
                <Line
                  type="monotone"
                  dataKey="collected_cash"
                  name="Thực thu đối soát"
                  stroke="#10b981"
                  strokeWidth={2.5}
                  dot={{ r: 3 }}
                />
                <Line
                  type="monotone"
                  dataKey="net_cash"
                  name="Thực thu thuần"
                  stroke="#6366f1"
                  strokeWidth={2}
                  strokeDasharray="4 4"
                />
              </ComposedChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* 4. Two-Column Breakdown: By Payment Method & By Warehouse */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* By Payment Method */}
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <CreditCard className="w-5 h-5 text-blue-600" />
              <h3 className="text-base font-bold text-slate-800">Cơ Cấu Phương Thức Thanh Toán</h3>
            </div>
            <span className="text-xs text-slate-400 font-medium">Chi tiết theo kênh</span>
          </div>

          <div className="space-y-3">
            {methods.map((m) => {
              const isCod = m.payment_method === 'COD'
              const isSepay = m.payment_method === 'SEPAY'
              const isPayos = m.payment_method === 'PAYOS'

              const label = isCod ? 'Tiền mặt khi nhận hàng (COD)' : isSepay ? 'Chuyển khoản SePay VietQR' : isPayos ? 'Cổng thanh toán payOS' : m.payment_method

              return (
                <div
                  key={m.payment_method}
                  className="p-4 rounded-xl border border-slate-100 bg-slate-50/60 hover:bg-slate-50 transition-colors"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2.5">
                      <span
                        className={`w-2.5 h-2.5 rounded-full ${
                          isCod ? 'bg-amber-500' : isSepay ? 'bg-blue-600' : 'bg-emerald-600'
                        }`}
                      />
                      <span className="text-sm font-bold text-slate-800">{label}</span>
                    </div>
                    <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-slate-200/80 text-slate-700">
                      {m.total_orders} đơn ({m.paid_count} đã thu)
                    </span>
                  </div>

                  <div className="mt-3 grid grid-cols-3 gap-2 text-xs">
                    <div>
                      <span className="text-slate-400 block">Tổng phát sinh:</span>
                      <span className="font-bold text-slate-700">{formatVND(m.gross_gmv)}</span>
                    </div>
                    <div>
                      <span className="text-emerald-600 block font-medium">Đã thực thu:</span>
                      <span className="font-bold text-emerald-700">{formatVND(m.collected_amount)}</span>
                    </div>
                    <div>
                      <span className="text-amber-600 block font-medium">Chờ thu:</span>
                      <span className="font-bold text-amber-700">{formatVND(m.pending_amount)}</span>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        {/* By Warehouse */}
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Building2 className="w-5 h-5 text-indigo-600" />
              <h3 className="text-base font-bold text-slate-800">Hiệu Suất Theo Chi Nhánh Kho</h3>
            </div>
            <span className="text-xs text-slate-400 font-medium">Phân bổ nguồn gốc xuất hàng</span>
          </div>

          <div className="space-y-3">
            {warehouses.map((w) => (
              <div
                key={w.warehouse_id}
                className="p-4 rounded-xl border border-slate-100 bg-slate-50/60 hover:bg-slate-50 transition-colors"
              >
                <div className="flex items-center justify-between">
                  <div>
                    <span className="text-sm font-bold text-slate-800">{w.warehouse_name}</span>
                    <span className="text-xs text-slate-400 block font-mono mt-0.5">{w.warehouse_code}</span>
                  </div>
                  <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-700 border border-indigo-100">
                    {w.total_orders} đơn
                  </span>
                </div>

                <div className="mt-3 grid grid-cols-3 gap-2 text-xs">
                  <div>
                    <span className="text-slate-400 block">Thực thu:</span>
                    <span className="font-bold text-emerald-700">{formatVND(w.collected_amount)}</span>
                  </div>
                  <div>
                    <span className="text-slate-400 block">Hoàn trả:</span>
                    <span className="font-bold text-rose-600">-{formatVND(w.refund_amount)}</span>
                  </div>
                  <div>
                    <span className="text-slate-400 block font-medium">Dòng tiền thuần:</span>
                    <span className="font-bold text-indigo-700">{formatVND(w.net_cash)}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* 5. Recent Financial Transactions Feed */}
      <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
          <div>
            <h3 className="text-base font-bold text-slate-800">Nhật Ký Đơn Hàng & Dòng Tiền</h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Danh sách chi tiết toàn bộ giao dịch trong kỳ đối soát ({txTotal} giao dịch)
            </p>
          </div>

          {/* Search & Status filter */}
          <div className="flex flex-wrap items-center gap-2">
            <div className="relative">
              <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                value={txSearch}
                onChange={(e) => {
                  setTxSearch(e.target.value)
                  setTxPage(1)
                }}
                placeholder="Tìm mã đơn, tên khách..."
                className="pl-9 pr-3 py-1.5 rounded-xl border border-slate-200 text-xs text-slate-700 placeholder:text-slate-400 focus:outline-none focus:border-blue-500"
              />
            </div>

            <select
              value={txMethodFilter}
              onChange={(e) => {
                setTxMethodFilter(e.target.value)
                setTxPage(1)
              }}
              className="px-2.5 py-1.5 rounded-xl border border-slate-200 text-xs text-slate-700 bg-white"
            >
              <option value="ALL">Tất cả phương thức</option>
              <option value="COD">COD</option>
              <option value="SEPAY">SePay</option>
              <option value="PAYOS">payOS</option>
            </select>

            <select
              value={txStatusFilter}
              onChange={(e) => {
                setTxStatusFilter(e.target.value)
                setTxPage(1)
              }}
              className="px-2.5 py-1.5 rounded-xl border border-slate-200 text-xs text-slate-700 bg-white"
            >
              <option value="ALL">Tất cả trạng thái tiền</option>
              <option value="PAID">Đã thanh toán (PAID)</option>
              <option value="PENDING">Chờ thanh toán (PENDING)</option>
              <option value="FAILED">Thất bại (FAILED)</option>
            </select>
          </div>
        </div>

        {/* Transactions Table */}
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50/70 text-slate-500 uppercase tracking-wider font-semibold">
                <th className="py-2.5 px-3">Mã đơn</th>
                <th className="py-2.5 px-3">Thời gian</th>
                <th className="py-2.5 px-3">Khách hàng</th>
                <th className="py-2.5 px-3">Chi nhánh</th>
                <th className="py-2.5 px-3">Phương thức</th>
                <th className="py-2.5 px-3">Trạng thái đơn</th>
                <th className="py-2.5 px-3">Thực thu</th>
                <th className="py-2.5 px-3 text-right">Tổng tiền</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {transactions.length === 0 ? (
                <tr>
                  <td colSpan={8} className="py-8 text-center text-slate-400">
                    Không tìm thấy giao dịch nào phù hợp
                  </td>
                </tr>
              ) : (
                transactions.map((tx) => (
                  <tr key={tx.id} className="hover:bg-slate-50/80 transition-colors">
                    <td className="py-2.5 px-3 font-mono font-bold text-blue-600">
                      {tx.order_code}
                    </td>
                    <td className="py-2.5 px-3 text-slate-500">{formatDate(tx.created_at)}</td>
                    <td className="py-2.5 px-3">
                      <div className="font-medium text-slate-800">{tx.customer_name}</div>
                      <div className="text-[10px] text-slate-400 font-mono">{tx.customer_phone}</div>
                    </td>
                    <td className="py-2.5 px-3 text-slate-600">{tx.warehouse_name}</td>
                    <td className="py-2.5 px-3">
                      <span className="font-semibold px-2 py-0.5 rounded-md bg-slate-100 text-slate-700">
                        {tx.payment_method}
                      </span>
                    </td>
                    <td className="py-2.5 px-3">
                      <span
                        className={`font-semibold px-2 py-0.5 rounded-full text-[10px] ${
                          tx.order_status === 'DELIVERED' || tx.order_status === 'COMPLETED'
                            ? 'bg-emerald-50 text-emerald-700 border border-emerald-100'
                            : tx.order_status === 'CANCELLED'
                            ? 'bg-rose-50 text-rose-700 border border-rose-100'
                            : 'bg-amber-50 text-amber-700 border border-amber-100'
                        }`}
                      >
                        {tx.order_status}
                      </span>
                    </td>
                    <td className="py-2.5 px-3">
                      {tx.is_cash_collected ? (
                        <span className="flex items-center gap-1 text-emerald-600 font-semibold text-[11px]">
                          <CheckCircle2 className="w-3.5 h-3.5" /> Đã thu
                        </span>
                      ) : (
                        <span className="flex items-center gap-1 text-amber-600 font-medium text-[11px]">
                          <Clock className="w-3.5 h-3.5" /> Chờ thu
                        </span>
                      )}
                    </td>
                    <td className="py-2.5 px-3 text-right font-bold text-slate-900">
                      {formatVND(tx.total_amount)}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        <div className="flex items-center justify-between mt-4 text-xs text-slate-500 pt-3 border-t border-slate-100">
          <span>
            Hiển thị {transactions.length} trên tổng số {txTotal} giao dịch
          </span>
          <div className="flex items-center gap-1">
            <button
              onClick={() => setTxPage((p) => Math.max(1, p - 1))}
              disabled={txPage <= 1}
              className="px-2.5 py-1 rounded-md border border-slate-200 disabled:opacity-40 hover:bg-slate-50"
            >
              Trang trước
            </button>
            <span className="px-2 font-bold text-slate-700">Trang {txPage}</span>
            <button
              onClick={() => setTxPage((p) => p + 1)}
              disabled={transactions.length < 15}
              className="px-2.5 py-1 rounded-md border border-slate-200 disabled:opacity-40 hover:bg-slate-50"
            >
              Trang sau
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
