import {
  AlertCircle,
  ArrowRight,
  Boxes,
  CheckCircle2,
  Clock,
  Eye,
  Layers,
  Loader2,
  PackageCheck,
  RefreshCw,
  Repeat,
  Search,
  Truck,
  X,
  XCircle,
} from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { AdminPageHeader } from '../components/AdminPageHeader'
import { FilterBar } from '../components/FilterBar'
import { PaginationBar } from '../components/PaginationBar'
import { api } from '../services/api'

interface ExchangeSummary {
  id: number
  exchange_code: string
  return_code: string
  returned_items_value: number
  replacement_items_value: number
  price_difference: number
  status: string
  carrier_name: string | null
  tracking_code: string | null
  items_count: number
  created_at: string | null
  shipped_at: string | null
  delivered_at: string | null
}

interface ExchangeDetailItem {
  id: number
  product_id: number
  product_name: string
  quantity: number
  unit_price: number
  subtotal: number
}

interface ExchangeDetailData extends ExchangeSummary {
  shipping_address: string | null
  difference_payment_method: string | null
  difference_transaction_ref: string | null
  difference_payment_status: string | null
  customer_name?: string
  customer_phone?: string
  items: ExchangeDetailItem[]
}

const STATUS_CONFIG: Record<string, { label: string; color: string; bg: string }> = {
  PENDING_PRICE_DIFFERENCE: { label: 'Chờ bù tiền chênh lệch', color: '#c2410c', bg: '#ffedd5' },
  PREPARING_ITEMS: { label: 'Đang soạn hàng kho (FEFO)', color: '#4338ca', bg: '#e0e7ff' },
  DISPATCHED: { label: 'Đang vận chuyển giao khách', color: '#0369a1', bg: '#e0f2fe' },
  COMPLETED: { label: 'Đã hoàn tất', color: '#15803d', bg: '#dcfce7' },
  CANCELLED: { label: 'Đã hủy', color: '#475569', bg: '#f1f5f9' },
}

export function ExchangesPage() {
  const [exchanges, setExchanges] = useState<ExchangeSummary[]>([])
  const [totalCount, setTotalCount] = useState<number>(0)
  const [loading, setLoading] = useState<boolean>(true)
  const [search, setSearch] = useState<string>('')
  const [statusFilter, setStatusFilter] = useState<string>('')

  // Phân trang
  const [currentPage, setCurrentPage] = useState<number>(1)
  const [pageSize, setPageSize] = useState<number>(15)

  // Detail Modal
  const [selectedExchangeCode, setSelectedExchangeCode] = useState<string | null>(null)
  const [exchangeDetail, setExchangeDetail] = useState<ExchangeDetailData | null>(null)
  const [loadingDetail, setLoadingDetail] = useState<boolean>(false)
  const [actionLoading, setActionLoading] = useState<boolean>(false)
  const [actionError, setActionError] = useState<string>('')

  // Dispatch modal
  const [dispatchCode, setDispatchCode] = useState<string | null>(null)
  const [carrierName, setCarrierName] = useState<string>('VNPost Siêu Tốc')
  const [trackingCode, setTrackingCode] = useState<string>('')

  // Payment confirmation modal
  const [paymentCode, setPaymentCode] = useState<string | null>(null)
  const [paymentMethod, setPaymentMethod] = useState<string>('COD')
  const [transactionRef, setTransactionRef] = useState<string>('')

  const totalPages = Math.max(1, Math.ceil(totalCount / pageSize))

  const loadExchanges = async (page = currentPage, size = pageSize) => {
    setLoading(true)
    try {
      const params = new URLSearchParams()
      if (statusFilter) params.append('status', statusFilter)
      if (search.trim()) params.append('search', search.trim())
      params.append('page', String(page))
      params.append('page_size', String(size))

      const res = await api<{ total: number; items?: ExchangeSummary[]; exchanges?: ExchangeSummary[] }>(
        `/admin/exchanges?${params.toString()}`
      )
      const dataList = res.items || res.exchanges || []
      setExchanges(dataList)
      setTotalCount(res.total ?? dataList.length)
    } catch (err) {
      console.error('Failed to load exchanges', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    setCurrentPage(1)
    loadExchanges(1, pageSize)
  }, [statusFilter])

  useEffect(() => {
    const timer = setTimeout(() => {
      setCurrentPage(1)
      loadExchanges(1, pageSize)
    }, 350)
    return () => clearTimeout(timer)
  }, [search])

  const openDetail = async (code: string) => {
    setSelectedExchangeCode(code)
    setLoadingDetail(true)
    setActionError('')
    try {
      const detail = await api<ExchangeDetailData>(`/admin/exchanges/${code}`)
      setExchangeDetail(detail)
    } catch (err: any) {
      setActionError(err.message || 'Không thể tải chi tiết đơn đổi hàng')
    } finally {
      setLoadingDetail(false)
    }
  }

  const handleConfirmPayment = async () => {
    if (!paymentCode || !transactionRef.trim()) {
      setActionError('Vui lòng nhập mã tham chiếu thanh toán')
      return
    }
    setActionLoading(true)
    setActionError('')
    try {
      await api(`/admin/exchanges/${paymentCode}/confirm-payment`, {
        method: 'POST',
        body: JSON.stringify({
          payment_method: paymentMethod,
          transaction_ref: transactionRef.trim(),
        }),
      })
      setPaymentCode(null)
      loadExchanges()
      if (selectedExchangeCode === paymentCode) openDetail(paymentCode)
    } catch (err: any) {
      setActionError(err.message || 'Xác nhận thanh toán thất bại')
    } finally {
      setActionLoading(false)
    }
  }

  const handleDispatch = async () => {
    if (!dispatchCode || !trackingCode.trim()) {
      setActionError('Vui lòng nhập mã vận đơn phát hành')
      return
    }
    setActionLoading(true)
    setActionError('')
    try {
      await api(`/admin/exchanges/${dispatchCode}/dispatch`, {
        method: 'POST',
        body: JSON.stringify({
          carrier_name: carrierName.trim(),
          tracking_code: trackingCode.trim(),
        }),
      })
      setDispatchCode(null)
      loadExchanges()
      if (selectedExchangeCode === dispatchCode) openDetail(dispatchCode)
    } catch (err: any) {
      setActionError(err.message || 'Phát hành đơn đổi thất bại')
    } finally {
      setActionLoading(false)
    }
  }

  const handleComplete = async (code: string) => {
    if (!confirm(`Xác nhận khách hàng đã nhận thành công đơn đổi hàng #${code}?`)) return
    setActionLoading(true)
    setActionError('')
    try {
      await api(`/admin/exchanges/${code}/complete`, {
        method: 'POST',
      })
      loadExchanges()
      if (selectedExchangeCode === code) openDetail(code)
    } catch (err: any) {
      alert(`Thao tác thất bại: ${err.message}`)
    } finally {
      setActionLoading(false)
    }
  }

  return (
    <div className="admin-page-container" style={{ padding: '24px 32px' }}>
      <AdminPageHeader
        title="Quản Lý Đơn Đổi Hàng (Exchanges)"
        subtitle="Quản lý bù trừ giá chênh lệch, xuất kho theo nguyên tắc FEFO và phát hành vận đơn thay thế."
        breadcrumbs={[
          { label: 'Trang chủ', href: '/' },
          { label: 'Hậu Mãi', href: '/returns' },
          { label: 'Đơn đổi hàng' },
        ]}
      />

      {/* Filter and Search Bar */}
      <FilterBar
        searchValue={search}
        onSearchChange={setSearch}
        searchPlaceholder="Tìm theo mã đơn đổi, mã đổi trả, mã vận đơn..."
        onRefresh={loadExchanges}
        isRefreshing={loading}
        totalCount={totalCount}
        filteredCount={exchanges.length}
        unitLabel="đơn đổi"
      >
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            style={{
              padding: '6px 12px',
              borderRadius: 8,
              border: '1px solid #cbd5e1',
              background: '#fff',
              fontSize: 13,
              color: '#1e293b',
              fontWeight: 600,
            }}
          >
            <option value="">Tất cả trạng thái</option>
            <option value="PENDING_PRICE_DIFFERENCE">Chờ thanh toán chênh lệch</option>
            <option value="PREPARING_ITEMS">Đang soạn hàng kho</option>
            <option value="DISPATCHED">Đang giao hàng</option>
            <option value="COMPLETED">Đã hoàn tất</option>
          </select>
        </div>
      </FilterBar>

      {/* Main Table */}
      <div
        style={{
          background: '#ffffff',
          borderRadius: 14,
          border: '1px solid #e2e8f0',
          overflow: 'hidden',
          boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
          marginTop: 16,
        }}
      >
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: 13 }}>
            <thead>
              <tr style={{ background: '#f8fafc', borderBottom: '1px solid #e2e8f0', color: '#475569', fontWeight: 700 }}>
                <th style={{ padding: '14px 16px' }}>Mã Đổi Hàng</th>
                <th style={{ padding: '14px 16px' }}>Hồ Sơ Đổi Trả</th>
                <th style={{ padding: '14px 16px' }}>Giá Trị Hàng Cũ → Mới</th>
                <th style={{ padding: '14px 16px' }}>Chênh Lệch Giá</th>
                <th style={{ padding: '14px 16px' }}>Trạng Thái</th>
                <th style={{ padding: '14px 16px' }}>Vận Đơn Đổi</th>
                <th style={{ padding: '14px 16px', textAlign: 'right' }}>Thao Tác</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={7} style={{ padding: 40, textAlign: 'center', color: '#64748b' }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}>
                      <RefreshCw size={16} className="spin" />
                      <span>Đang tải danh sách đơn đổi...</span>
                    </div>
                  </td>
                </tr>
              ) : exchanges.length === 0 ? (
                <tr>
                  <td colSpan={7} style={{ padding: 50, textAlign: 'center', color: '#94a3b8' }}>
                    <Repeat size={32} style={{ margin: '0 auto 10px', opacity: 0.5 }} />
                    <p style={{ margin: 0, fontWeight: 600 }}>Không tìm thấy đơn đổi hàng nào</p>
                  </td>
                </tr>
              ) : (
                exchanges.map((ex) => {
                  const cfg = STATUS_CONFIG[ex.status] || { label: ex.status, color: '#334155', bg: '#f1f5f9' }
                  const diff = ex.price_difference

                  return (
                    <tr
                      key={ex.exchange_code}
                      style={{ borderBottom: '1px solid #f1f5f9', transition: 'background 0.15s' }}
                      onMouseEnter={(e) => (e.currentTarget.style.background = '#f8fafc')}
                      onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                    >
                      <td style={{ padding: '14px 16px', fontWeight: 800 }}>
                        <span style={{ fontFamily: 'monospace', color: '#4338ca' }}>{ex.exchange_code}</span>
                      </td>
                      <td style={{ padding: '14px 16px', fontWeight: 700, color: '#334155' }}>
                        #{ex.return_code}
                      </td>
                      <td style={{ padding: '14px 16px', fontSize: 12 }}>
                        <div>
                          Cũ: <strong>{(ex.returned_items_value ?? 0).toLocaleString('vi-VN')} đ</strong>
                        </div>
                        <div style={{ color: '#0369a1' }}>
                          Mới: <strong>{(ex.replacement_items_value ?? 0).toLocaleString('vi-VN')} đ</strong>
                        </div>
                      </td>
                      <td style={{ padding: '14px 16px', fontWeight: 800, fontSize: 13 }}>
                        {diff > 0 ? (
                          <span style={{ color: '#c2410c' }}>
                            Khách bù: +{(diff ?? 0).toLocaleString('vi-VN')} đ
                          </span>
                        ) : diff < 0 ? (
                          <span style={{ color: '#059669' }}>
                            Hoàn lại: {(diff ?? 0).toLocaleString('vi-VN')} đ
                          </span>
                        ) : (
                          <span style={{ color: '#64748b' }}>Ngang giá (0 đ)</span>
                        )}
                      </td>
                      <td style={{ padding: '14px 16px' }}>
                        <span
                          style={{
                            fontSize: 12,
                            fontWeight: 700,
                            padding: '4px 10px',
                            borderRadius: 12,
                            color: cfg.color,
                            background: cfg.bg,
                            display: 'inline-block',
                          }}
                        >
                          {cfg.label}
                        </span>
                      </td>
                      <td style={{ padding: '14px 16px', fontSize: 12 }}>
                        {ex.tracking_code ? (
                          <div>
                            <span style={{ fontWeight: 600 }}>{ex.carrier_name}</span>: {ex.tracking_code}
                          </div>
                        ) : (
                          <span style={{ color: '#94a3b8', fontStyle: 'italic' }}>Chưa phát hành</span>
                        )}
                      </td>
                      <td style={{ padding: '14px 16px', textAlign: 'right' }}>
                        <div style={{ display: 'flex', gap: 6, justifyContent: 'flex-end', alignItems: 'center' }}>
                          {ex.status === 'PENDING_PRICE_DIFFERENCE' && (
                            <button
                              type="button"
                              onClick={() => {
                                setPaymentCode(ex.exchange_code)
                                setTransactionRef('')
                              }}
                              style={{
                                padding: '5px 10px',
                                borderRadius: 6,
                                background: '#c2410c',
                                color: '#fff',
                                border: 'none',
                                fontWeight: 700,
                                fontSize: 11,
                                cursor: 'pointer',
                              }}
                            >
                              Xác nhận thu tiền
                            </button>
                          )}

                          {ex.status === 'PREPARING_ITEMS' && (
                            <button
                              type="button"
                              onClick={() => {
                                setDispatchCode(ex.exchange_code)
                                setTrackingCode('')
                              }}
                              style={{
                                padding: '5px 10px',
                                borderRadius: 6,
                                background: '#0284c7',
                                color: '#fff',
                                border: 'none',
                                fontWeight: 700,
                                fontSize: 11,
                                cursor: 'pointer',
                              }}
                            >
                              Xuất kho giao
                            </button>
                          )}

                          {ex.status === 'DISPATCHED' && (
                            <button
                              type="button"
                              onClick={() => handleComplete(ex.exchange_code)}
                              disabled={actionLoading}
                              style={{
                                padding: '5px 10px',
                                borderRadius: 6,
                                background: '#16a34a',
                                color: '#fff',
                                border: 'none',
                                fontWeight: 700,
                                fontSize: 11,
                                cursor: 'pointer',
                              }}
                            >
                              Đã giao xong
                            </button>
                          )}

                          <button
                            type="button"
                            onClick={() => openDetail(ex.exchange_code)}
                            style={{
                              padding: '5px 10px',
                              borderRadius: 6,
                              background: '#475569',
                              color: '#fff',
                              border: 'none',
                              fontWeight: 700,
                              fontSize: 11,
                              cursor: 'pointer',
                              display: 'flex',
                              alignItems: 'center',
                              gap: 4,
                            }}
                          >
                            <Eye size={12} />
                            <span>Chi tiết</span>
                          </button>
                        </div>
                      </td>
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </div>
        {!loading && exchanges.length > 0 && (
          <PaginationBar
            currentPage={currentPage}
            totalPages={totalPages}
            pageSize={pageSize}
            totalItems={totalCount}
            itemName="đơn đổi hàng"
            onPageChange={(p) => {
              setCurrentPage(p)
              loadExchanges(p, pageSize)
            }}
            onPageSizeChange={(sz) => {
              setPageSize(sz)
              setCurrentPage(1)
              loadExchanges(1, sz)
            }}
            pageSizeOptions={[10, 15, 25, 50]}
          />
        )}
      </div>

      {/* POPUP: Dispatch Order */}
      {dispatchCode && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(15, 23, 42, 0.65)',
            backdropFilter: 'blur(3px)',
            zIndex: 1000,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: 20,
          }}
          onClick={() => setDispatchCode(null)}
        >
          <div
            style={{
              background: '#fff',
              borderRadius: 16,
              maxWidth: 480,
              width: '100%',
              padding: 24,
              boxShadow: '0 25px 50px -12px rgba(0,0,0,0.25)',
              border: '1px solid #e2e8f0',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
              <h3 style={{ margin: 0, fontSize: 17, fontWeight: 800, color: '#0f172a' }}>
                Xuất Kho Đơn Đổi #{dispatchCode}
              </h3>
              <button
                type="button"
                onClick={() => setDispatchCode(null)}
                style={{ background: '#f1f5f9', border: 'none', borderRadius: 8, padding: 6, cursor: 'pointer' }}
              >
                <X size={16} />
              </button>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 12, fontSize: 13 }}>
              <div>
                <label style={{ display: 'block', fontWeight: 700, color: '#334155', marginBottom: 4 }}>
                  Đơn vị vận chuyển:
                </label>
                <input
                  type="text"
                  value={carrierName}
                  onChange={(e) => setCarrierName(e.target.value)}
                  style={{ width: '100%', padding: '8px 12px', borderRadius: 8, border: '1px solid #cbd5e1', fontSize: 13 }}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontWeight: 700, color: '#334155', marginBottom: 4 }}>
                  Mã vận đơn bưu phẩm (*):
                </label>
                <input
                  type="text"
                  value={trackingCode}
                  onChange={(e) => setTrackingCode(e.target.value)}
                  placeholder="Ví dụ: VNPOST-99988877..."
                  style={{ width: '100%', padding: '8px 12px', borderRadius: 8, border: '1px solid #cbd5e1', fontSize: 13 }}
                />
              </div>

              <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
                <button
                  type="button"
                  onClick={handleDispatch}
                  disabled={actionLoading}
                  style={{
                    flex: 1,
                    padding: '10px',
                    borderRadius: 8,
                    background: '#0284c7',
                    color: '#fff',
                    border: 'none',
                    fontWeight: 700,
                    cursor: 'pointer',
                  }}
                >
                  Xác Nhận Xuất Kho & Giao Hàng
                </button>
                <button
                  type="button"
                  onClick={() => setDispatchCode(null)}
                  style={{
                    padding: '10px 16px',
                    borderRadius: 8,
                    background: '#fff',
                    border: '1px solid #cbd5e1',
                    color: '#475569',
                    fontWeight: 600,
                    cursor: 'pointer',
                  }}
                >
                  Hủy
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* POPUP: Payment Difference Confirmation */}
      {paymentCode && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(15, 23, 42, 0.65)',
            backdropFilter: 'blur(3px)',
            zIndex: 1000,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: 20,
          }}
          onClick={() => setPaymentCode(null)}
        >
          <div
            style={{
              background: '#fff',
              borderRadius: 16,
              maxWidth: 480,
              width: '100%',
              padding: 24,
              boxShadow: '0 25px 50px -12px rgba(0,0,0,0.25)',
              border: '1px solid #e2e8f0',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
              <h3 style={{ margin: 0, fontSize: 17, fontWeight: 800, color: '#0f172a' }}>
                Xác Nhận Thu Chênh Lệch #{paymentCode}
              </h3>
              <button
                type="button"
                onClick={() => setPaymentCode(null)}
                style={{ background: '#f1f5f9', border: 'none', borderRadius: 8, padding: 6, cursor: 'pointer' }}
              >
                <X size={16} />
              </button>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 12, fontSize: 13 }}>
              <div>
                <label style={{ display: 'block', fontWeight: 700, color: '#334155', marginBottom: 4 }}>
                  Hình thức thanh toán:
                </label>
                <select
                  value={paymentMethod}
                  onChange={(e) => setPaymentMethod(e.target.value)}
                  style={{ width: '100%', padding: '8px 12px', borderRadius: 8, border: '1px solid #cbd5e1', fontWeight: 600 }}
                >
                  <option value="COD">Thu tiền khi bưu tá giao (COD)</option>
                  <option value="BANK_TRANSFER">Khách chuyển khoản ngân hàng</option>
                  <option value="MOMO">Thanh toán qua Ví MoMo</option>
                </select>
              </div>

              <div>
                <label style={{ display: 'block', fontWeight: 700, color: '#334155', marginBottom: 4 }}>
                  Mã tham chiếu / Mã biên nhận:
                </label>
                <input
                  type="text"
                  value={transactionRef}
                  onChange={(e) => setTransactionRef(e.target.value)}
                  placeholder="Ví dụ: COD-COLLECT, FT998877..."
                  style={{ width: '100%', padding: '8px 12px', borderRadius: 8, border: '1px solid #cbd5e1', fontSize: 13 }}
                />
              </div>

              <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
                <button
                  type="button"
                  onClick={handleConfirmPayment}
                  disabled={actionLoading}
                  style={{
                    flex: 1,
                    padding: '10px',
                    borderRadius: 8,
                    background: '#16a34a',
                    color: '#fff',
                    border: 'none',
                    fontWeight: 700,
                    cursor: 'pointer',
                  }}
                >
                  Xác Nhận Thanh Toán
                </button>
                <button
                  type="button"
                  onClick={() => setPaymentCode(null)}
                  style={{
                    padding: '10px 16px',
                    borderRadius: 8,
                    background: '#fff',
                    border: '1px solid #cbd5e1',
                    color: '#475569',
                    fontWeight: 600,
                    cursor: 'pointer',
                  }}
                >
                  Hủy
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* POPUP: Detail Modal */}
      {selectedExchangeCode && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(15, 23, 42, 0.65)',
            backdropFilter: 'blur(3px)',
            zIndex: 1000,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: 20,
          }}
          onClick={() => setSelectedExchangeCode(null)}
        >
          <div
            style={{
              background: '#fff',
              borderRadius: 16,
              maxWidth: 680,
              width: '100%',
              padding: 24,
              boxShadow: '0 25px 50px -12px rgba(0,0,0,0.25)',
              border: '1px solid #e2e8f0',
              maxHeight: '90vh',
              overflowY: 'auto',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16, borderBottom: '1px solid #f1f5f9', paddingBottom: 12 }}>
              <h3 style={{ margin: 0, fontSize: 18, fontWeight: 800, color: '#0f172a' }}>
                Chi Tiết Đơn Đổi Hàng #{selectedExchangeCode}
              </h3>
              <button
                type="button"
                onClick={() => setSelectedExchangeCode(null)}
                style={{ background: '#f1f5f9', border: 'none', borderRadius: 8, padding: 6, cursor: 'pointer' }}
              >
                <X size={16} />
              </button>
            </div>

            {loadingDetail ? (
              <div style={{ padding: 40, textAlign: 'center', color: '#64748b' }}>
                <RefreshCw size={20} className="spin" style={{ margin: '0 auto 8px' }} />
                <span>Đang tải đơn đổi hàng...</span>
              </div>
            ) : exchangeDetail ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 16, fontSize: 13 }}>
                <div style={{ background: '#f8fafc', padding: 14, borderRadius: 10, border: '1px solid #e2e8f0', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                  <div>
                    <span style={{ color: '#64748b', fontSize: 11 }}>Yêu cầu đổi/trả gốc:</span>
                    <div style={{ fontWeight: 700, color: '#0f172a' }}>#{exchangeDetail.return_code}</div>
                  </div>
                  <div>
                    <span style={{ color: '#64748b', fontSize: 11 }}>Trạng thái đơn đổi:</span>
                    <div>
                      <span
                        style={{
                          fontSize: 11,
                          fontWeight: 700,
                          padding: '2px 8px',
                          borderRadius: 6,
                          color: STATUS_CONFIG[exchangeDetail.status]?.color,
                          background: STATUS_CONFIG[exchangeDetail.status]?.bg,
                        }}
                      >
                        {STATUS_CONFIG[exchangeDetail.status]?.label || exchangeDetail.status}
                      </span>
                    </div>
                  </div>
                  <div>
                    <span style={{ color: '#64748b', fontSize: 11 }}>Địa chỉ nhận hàng đổi:</span>
                    <div style={{ fontWeight: 600, color: '#1e293b' }}>
                      {exchangeDetail.shipping_address || 'Địa chỉ ban đầu của đơn hàng'}
                    </div>
                  </div>
                  <div>
                    <span style={{ color: '#64748b', fontSize: 11 }}>Chênh lệch giá:</span>
                    <div style={{ fontWeight: 800, fontSize: 14, color: (exchangeDetail.price_difference ?? 0) > 0 ? '#c2410c' : '#059669' }}>
                      {(exchangeDetail.price_difference ?? 0).toLocaleString('vi-VN')} đ
                    </div>
                  </div>
                </div>

                {/* Items List */}
                <div style={{ border: '1px solid #e2e8f0', borderRadius: 10, overflow: 'hidden' }}>
                  <div style={{ background: '#f8fafc', padding: '10px 14px', fontWeight: 700, fontSize: 12, color: '#475569' }}>
                    SẢN PHẨM GIAO THAY THẾ ({exchangeDetail.items?.length || 0})
                  </div>
                  {exchangeDetail.items?.map((it) => (
                    <div
                      key={it.id}
                      style={{
                        padding: '10px 14px',
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        borderBottom: '1px solid #f1f5f9',
                      }}
                    >
                      <div>
                        <div style={{ fontWeight: 700, color: '#0f172a' }}>{it.product_name}</div>
                        <div style={{ fontSize: 11, color: '#64748b' }}>
                          Số lượng: x{it.quantity} • Đơn giá: {(it.unit_price ?? 0).toLocaleString('vi-VN')} đ
                        </div>
                      </div>
                      <div style={{ fontWeight: 800, color: '#0369a1' }}>
                        {((it.subtotal || (it.unit_price ?? 0) * (it.quantity ?? 1)) ?? 0).toLocaleString('vi-VN')} đ
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ) : null}
          </div>
        </div>
      )}
    </div>
  )
}
