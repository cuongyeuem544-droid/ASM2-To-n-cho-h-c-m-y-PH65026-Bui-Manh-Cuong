import { useEffect, useState } from 'react'
import {
  ArrowLeftRight,
  Plus,
  CheckCircle2,
  AlertTriangle,
  Truck,
  Building2,
  X,
  Package,
} from 'lucide-react'
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

const STATUS_BADGES: Record<string, { label: string; bg: string; color: string }> = {
  IN_TRANSIT: { label: 'Đang vận chuyển', bg: '#eff6ff', color: '#1d4ed8' },
  COMPLETED: { label: 'Đã hoàn tất', bg: '#ecfdf5', color: '#047857' },
  FAILED: { label: 'Sự cố / Đã hủy', bg: '#fef2f2', color: '#b91c1c' },
  CANCELLED: { label: 'Đã hủy', bg: '#f1f5f9', color: '#475569' },
}

export function WarehouseTransfersPage() {
  const [transfers, setTransfers] = useState<TransferItem[]>([])
  const [loading, setLoading] = useState(true)
  const [direction, setDirection] = useState('all')

  // Failure / Refund Modal
  const [failTransferId, setFailTransferId] = useState<number | null>(null)
  const [failReason, setFailReason] = useState('')
  const [failing, setFailing] = useState(false)

  const fetchTransfers = () => {
    setLoading(true)
    const param = direction !== 'all' ? `?direction=${direction}` : ''
    api<TransferItem[]>(`/warehouse-portal/transfers${param}`)
      .then((res) => setTransfers(res || []))
      .catch((err) => console.error(err))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    fetchTransfers()
  }, [direction])

  const handleReceive = async (transferId: number) => {
    if (!window.confirm('Xác nhận tiếp nhận hàng điều chuyển đến kho?')) return
    try {
      await api(`/warehouse-portal/transfers/${transferId}/receive`, { method: 'POST' })
      alert('Đã tiếp nhận hàng thành công vào tồn kho chi nhánh!')
      fetchTransfers()
    } catch (err: any) {
      alert(err?.message || 'Không thể tiếp nhận hàng')
    }
  }

  const handleReportFailure = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!failTransferId || !failReason.trim()) return

    setFailing(true)
    try {
      const res: any = await api(`/warehouse-portal/transfers/${failTransferId}/fail`, {
        method: 'POST',
        body: JSON.stringify({ reason: failReason.trim() }),
      })
      alert(`Đã báo sự cố thành công! Hệ thống tự động hủy đơn hàng và hoàn tiền 100% (${res?.refund_amount?.toLocaleString() || ''} đ) cho khách hàng.`)
      setFailTransferId(null)
      setFailReason('')
      fetchTransfers()
    } catch (err: any) {
      alert(err?.message || 'Không thể xử lý sự cố điều chuyển')
    } finally {
      setFailing(false)
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', maxWidth: '1400px', margin: '0 auto' }}>
      {/* Header */}
      <div
        style={{
          background: 'white',
          borderRadius: '16px',
          border: '1px solid #e2e8f0',
          padding: '20px 24px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '16px',
          boxShadow: '0 1px 3px rgba(0,0,0,0.03)',
        }}
      >
        <div>
          <div style={{ fontSize: '11px', fontWeight: 800, color: '#1d4ed8', textTransform: 'uppercase', letterSpacing: '0.8px' }}>
            LUÂN CHUYỂN LIÊN CHI NHÁNH KHO
          </div>
          <h1 style={{ margin: '4px 0 0', fontSize: '22px', fontWeight: 900, color: '#0f172a' }}>
            Điều Chuyển Hàng Nội Bộ
          </h1>
          <p style={{ margin: '4px 0 0', fontSize: '13px', color: '#64748b' }}>
            Tiếp nhận hàng điều chuyển đến hoặc gửi hàng chi viện cho các chi nhánh khác
          </p>
        </div>

        {/* Direction Filter Tabs */}
        <div style={{ display: 'flex', gap: '6px', background: '#f8fafc', padding: '4px', borderRadius: '12px', border: '1px solid #e2e8f0' }}>
          {[
            { key: 'all', label: 'Tất cả lệnh' },
            { key: 'inbound', label: 'Hàng chuyển ĐẾN kho' },
            { key: 'outbound', label: 'Hàng chuyển ĐI khỏi kho' },
          ].map((tab) => {
            const isActive = direction === tab.key
            return (
              <button
                key={tab.key}
                type="button"
                onClick={() => setDirection(tab.key)}
                style={{
                  padding: '7px 14px',
                  borderRadius: '9px',
                  fontSize: '12px',
                  fontWeight: 800,
                  border: 'none',
                  background: isActive ? '#0f172a' : 'transparent',
                  color: isActive ? 'white' : '#64748b',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                }}
              >
                {tab.label}
              </button>
            )
          })}
        </div>
      </div>

      {/* Transfers Table */}
      <div
        style={{
          background: 'white',
          borderRadius: '16px',
          border: '1px solid #e2e8f0',
          overflow: 'hidden',
          boxShadow: '0 1px 3px rgba(0,0,0,0.03)',
        }}
      >
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '13px' }}>
            <thead>
              <tr style={{ background: '#f8fafc', borderBottom: '1px solid #e2e8f0', color: '#64748b', fontSize: '11px', fontWeight: 800, textTransform: 'uppercase' }}>
                <th style={{ padding: '14px 18px' }}>Mã Lệnh Điều Chuyển</th>
                <th style={{ padding: '14px 18px' }}>Kho Xuất Phát</th>
                <th style={{ padding: '14px 18px' }}>Kho Tiếp Nhận</th>
                <th style={{ padding: '14px 18px' }}>Số Mặt Hàng</th>
                <th style={{ padding: '14px 18px' }}>Trạng Thái</th>
                <th style={{ padding: '14px 18px' }}>Thời Gian</th>
                <th style={{ padding: '14px 18px', textAlign: 'right' }}>Thao Tác</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={7} style={{ padding: '40px', textAlign: 'center', color: '#94a3b8', fontWeight: 600 }}>
                    Đang tải danh sách lệnh điều chuyển…
                  </td>
                </tr>
              ) : transfers.length === 0 ? (
                <tr>
                  <td colSpan={7} style={{ padding: '40px', textAlign: 'center', color: '#94a3b8', fontWeight: 600 }}>
                    Không có lệnh điều chuyển nào theo bộ lọc đã chọn.
                  </td>
                </tr>
              ) : (
                transfers.map((t) => {
                  const badge = STATUS_BADGES[t.status] || { label: t.status, bg: '#f1f5f9', color: '#475569' }
                  return (
                    <tr
                      key={t.id}
                      style={{ borderBottom: '1px solid #f1f5f9', transition: 'background 0.15s ease' }}
                      onMouseEnter={(e) => (e.currentTarget.style.background = '#f8fafc')}
                      onMouseLeave={(e) => (e.currentTarget.style.background = 'white')}
                    >
                      <td style={{ padding: '14px 18px', fontFamily: 'monospace', fontWeight: 900, color: '#1d4ed8' }}>
                        {t.transfer_code}
                      </td>

                      <td style={{ padding: '14px 18px' }}>
                        <div style={{ fontWeight: 800, color: '#0f172a' }}>{t.from_warehouse?.name || '—'}</div>
                        <div style={{ fontSize: '11px', color: '#64748b' }}>{t.from_warehouse?.code}</div>
                      </td>

                      <td style={{ padding: '14px 18px' }}>
                        <div style={{ fontWeight: 800, color: '#0f172a' }}>{t.to_warehouse?.name || '—'}</div>
                        <div style={{ fontSize: '11px', color: '#64748b' }}>{t.to_warehouse?.code}</div>
                      </td>

                      <td style={{ padding: '14px 18px' }}>
                        <span
                          style={{
                            background: '#f1f5f9',
                            padding: '3px 8px',
                            borderRadius: '6px',
                            fontSize: '11.5px',
                            fontWeight: 700,
                            color: '#475569',
                          }}
                        >
                          {t.items_count} mặt hàng
                        </span>
                      </td>

                      <td style={{ padding: '14px 18px' }}>
                        <span
                          style={{
                            padding: '4px 10px',
                            borderRadius: '9999px',
                            fontSize: '11px',
                            fontWeight: 800,
                            background: badge.bg,
                            color: badge.color,
                            whiteSpace: 'nowrap',
                          }}
                        >
                          {badge.label}
                        </span>
                      </td>

                      <td style={{ padding: '14px 18px', color: '#64748b', fontSize: '12px' }}>
                        {t.created_at ? new Date(t.created_at).toLocaleString('vi-VN') : '—'}
                      </td>

                      <td style={{ padding: '14px 18px', textAlign: 'right' }}>
                        {t.status === 'IN_TRANSIT' && (
                          <div style={{ display: 'inline-flex', gap: '6px' }}>
                            <button
                              type="button"
                              onClick={() => handleReceive(t.id)}
                              style={{
                                padding: '6px 12px',
                                borderRadius: '8px',
                                border: 'none',
                                background: '#059669',
                                color: 'white',
                                fontSize: '12px',
                                fontWeight: 800,
                                cursor: 'pointer',
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: '4px',
                              }}
                            >
                              <CheckCircle2 size={13} /> Nhận hàng
                            </button>
                            <button
                              type="button"
                              onClick={() => {
                                setFailTransferId(t.id)
                                setFailReason('')
                              }}
                              style={{
                                padding: '6px 12px',
                                borderRadius: '8px',
                                border: '1px solid #fecaca',
                                background: '#fff1f2',
                                color: '#b91c1c',
                                fontSize: '12px',
                                fontWeight: 800,
                                cursor: 'pointer',
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: '4px',
                              }}
                              title="Báo hỏng để tự động hoàn tiền"
                            >
                              <AlertTriangle size={13} /> Báo hỏng
                            </button>
                          </div>
                        )}
                      </td>
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Failure & Auto Refund Modal */}
      {failTransferId && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(15, 23, 42, 0.65)',
            backdropFilter: 'blur(4px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 60,
            padding: '20px',
          }}
        >
          <div
            style={{
              background: 'white',
              borderRadius: '20px',
              maxWidth: '520px',
              width: '100%',
              padding: '26px',
              boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.25)',
              display: 'flex',
              flexDirection: 'column',
              gap: '16px',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid #e2e8f0', paddingBottom: '12px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#b91c1c' }}>
                <AlertTriangle size={20} />
                <h3 style={{ margin: 0, fontSize: '17px', fontWeight: 900, color: '#0f172a' }}>
                  Báo Sự Cố Điều Chuyển Hàng
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setFailTransferId(null)}
                style={{ background: 'none', border: 'none', color: '#94a3b8', cursor: 'pointer', padding: '4px' }}
              >
                <X size={20} />
              </button>
            </div>

            <div
              style={{
                background: '#fff1f2',
                border: '1px solid #fecaca',
                padding: '12px 14px',
                borderRadius: '12px',
                fontSize: '12px',
                color: '#9f1239',
                lineHeight: 1.5,
              }}
            >
              ⚠️ <b>Cơ chế bồi hoàn tự động:</b> Khi hàng điều chuyển bị hỏng hóc hoặc mất mát, hệ thống sẽ <b>tự động hủy toàn bộ đơn hàng và hoàn tiền 100%</b> cho khách hàng ngay lập tức.
            </div>

            <form onSubmit={handleReportFailure} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '11px', fontWeight: 800, color: '#334155', textTransform: 'uppercase', marginBottom: '6px' }}>
                  Lý do sự cố * <span style={{ color: '#ef4444' }}>(Bắt buộc)</span>
                </label>
                <textarea
                  rows={3}
                  value={failReason}
                  onChange={(e) => setFailReason(e.target.value)}
                  placeholder="VD: Thuốc bị vỡ chai trong quá trình luân chuyển đường dài, xe vận chuyển gặp sự cố…"
                  style={{
                    width: '100%',
                    padding: '10px 14px',
                    borderRadius: '10px',
                    border: '1.5px solid #cbd5e1',
                    fontSize: '13px',
                    outline: 'none',
                    resize: 'vertical',
                    boxSizing: 'border-box',
                  }}
                  required
                />
              </div>

              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: '10px', paddingTop: '10px', borderTop: '1px solid #e2e8f0' }}>
                <button
                  type="button"
                  onClick={() => setFailTransferId(null)}
                  style={{
                    padding: '9px 18px',
                    borderRadius: '10px',
                    border: '1px solid #cbd5e1',
                    background: 'white',
                    color: '#64748b',
                    fontSize: '13px',
                    fontWeight: 700,
                    cursor: 'pointer',
                  }}
                >
                  Hủy
                </button>
                <button
                  type="submit"
                  disabled={failing || !failReason.trim()}
                  style={{
                    padding: '9px 20px',
                    borderRadius: '10px',
                    border: 'none',
                    background: '#e11d48',
                    color: 'white',
                    fontSize: '13px',
                    fontWeight: 800,
                    cursor: 'pointer',
                    boxShadow: '0 2px 8px rgba(225, 29, 72, 0.3)',
                  }}
                >
                  {failing ? 'Đang xử lý…' : 'Xác nhận hủy & Hoàn tiền 100%'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
