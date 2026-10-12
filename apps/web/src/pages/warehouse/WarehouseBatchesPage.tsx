import { useEffect, useState } from 'react'
import {
  Layers,
  Search,
  AlertTriangle,
  CheckCircle2,
  Calendar,
  Filter,
  XCircle,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react'
import { api } from '../../services/api'

interface BatchItem {
  id: number
  batch_id: number
  batch_number: string
  product_name: string
  sku_code: string
  unit_name: string
  manufacture_date: string | null
  expiry_date: string
  quantity_on_hand: number
  quantity_available: number
  quantity_reserved: number
  status: string
  is_near_expiry: boolean
  is_expired: boolean
  fefo_eligible: boolean
}

export function WarehouseBatchesPage() {
  const [batches, setBatches] = useState<BatchItem[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [nearExpiryOnly, setNearExpiryOnly] = useState(false)

  const fetchBatches = () => {
    setLoading(true)
    const params = new URLSearchParams({
      page: String(page),
      page_size: '25',
    })
    if (nearExpiryOnly) params.append('near_expiry_only', 'true')
    if (search.trim()) params.append('search', search.trim())

    api<{ items: BatchItem[]; total: number }>(`/warehouse-portal/batches?${params.toString()}`)
      .then((res) => {
        setBatches(res.items || [])
        setTotal(res.total || 0)
      })
      .catch((err) => console.error(err))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    fetchBatches()
  }, [page, nearExpiryOnly])

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setPage(1)
    fetchBatches()
  }

  const totalPages = Math.ceil(total / 25) || 1

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
          <div style={{ fontSize: '11px', fontWeight: 800, color: '#047857', textTransform: 'uppercase', letterSpacing: '0.8px' }}>
            KIỂM SOÁT HẠN DÙNG DƯỢC PHẨM
          </div>
          <h1 style={{ margin: '4px 0 0', fontSize: '22px', fontWeight: 900, color: '#0f172a' }}>
            Lô Thuốc & Hạn Sử Dụng (FEFO)
          </h1>
          <p style={{ margin: '4px 0 0', fontSize: '13px', color: '#64748b' }}>
            Giám sát chất lượng lô thuốc, ưu tiên xuất lô cận hạn và ngăn chặn xuất hàng hết hạn
          </p>
        </div>

        <div
          style={{
            background: '#ecfdf5',
            border: '1px solid #a7f3d0',
            padding: '8px 16px',
            borderRadius: '12px',
            fontSize: '13px',
            fontWeight: 800,
            color: '#047857',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
          }}
        >
          <Layers size={16} />
          <span>Tổng cộng: {total} lô thuốc</span>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div
        style={{
          background: 'white',
          borderRadius: '16px',
          border: '1px solid #e2e8f0',
          padding: '16px 20px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '14px',
          boxShadow: '0 1px 3px rgba(0,0,0,0.03)',
        }}
      >
        <form onSubmit={handleSearchSubmit} style={{ display: 'flex', alignItems: 'center', gap: '8px', flex: '1', minWidth: '280px', maxWidth: '420px' }}>
          <div style={{ position: 'relative', width: '100%' }}>
            <input
              type="text"
              placeholder="Tìm theo số lô, tên thuốc, SKU…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              style={{
                width: '100%',
                padding: '9px 14px 9px 36px',
                borderRadius: '10px',
                border: '1px solid #cbd5e1',
                fontSize: '13px',
                outline: 'none',
                boxSizing: 'border-box',
              }}
            />
            <Search size={16} style={{ position: 'absolute', left: '11px', top: '11px', color: '#94a3b8' }} />
          </div>
          <button
            type="submit"
            style={{
              padding: '9px 16px',
              borderRadius: '10px',
              border: 'none',
              background: '#047857',
              color: 'white',
              fontSize: '13px',
              fontWeight: 700,
              cursor: 'pointer',
              whiteSpace: 'nowrap',
            }}
          >
            Tìm
          </button>
        </form>

        <button
          type="button"
          onClick={() => {
            setNearExpiryOnly(!nearExpiryOnly)
            setPage(1)
          }}
          style={{
            padding: '9px 16px',
            borderRadius: '10px',
            fontSize: '12.5px',
            fontWeight: 800,
            border: nearExpiryOnly ? '1px solid #e11d48' : '1px solid #fecaca',
            background: nearExpiryOnly ? '#e11d48' : '#fff1f2',
            color: nearExpiryOnly ? 'white' : '#be123c',
            cursor: 'pointer',
            display: 'inline-flex',
            alignItems: 'center',
            gap: '6px',
            transition: 'all 0.15s ease',
          }}
        >
          <AlertTriangle size={15} /> Chỉ xem lô cận hạn (&lt; 180 ngày)
        </button>
      </div>

      {/* Batches Table */}
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
                <th style={{ padding: '14px 18px' }}>Mã Lô Thuốc</th>
                <th style={{ padding: '14px 18px' }}>Tên Thuốc & Quy Cách</th>
                <th style={{ padding: '14px 18px' }}>Ngày Sản Xuất</th>
                <th style={{ padding: '14px 18px' }}>Hạn Sử Dụng</th>
                <th style={{ padding: '14px 18px' }}>Tồn Thực Tế</th>
                <th style={{ padding: '14px 18px' }}>Khả Dụng</th>
                <th style={{ padding: '14px 18px', textAlign: 'center' }}>Tiêu Chuẩn FEFO</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={7} style={{ padding: '40px', textAlign: 'center', color: '#94a3b8', fontWeight: 600 }}>
                    Đang tải danh sách lô thuốc…
                  </td>
                </tr>
              ) : batches.length === 0 ? (
                <tr>
                  <td colSpan={7} style={{ padding: '40px', textAlign: 'center', color: '#94a3b8', fontWeight: 600 }}>
                    Không tìm thấy lô thuốc nào phù hợp.
                  </td>
                </tr>
              ) : (
                batches.map((b) => {
                  let fefoLabel = 'Đạt chuẩn FEFO'
                  let fefoBg = '#ecfdf5'
                  let fefoColor = '#047857'

                  if (b.is_expired) {
                    fefoLabel = 'Đã hết hạn'
                    fefoBg = '#fef2f2'
                    fefoColor = '#b91c1c'
                  } else if (b.is_near_expiry) {
                    fefoLabel = 'Cận hạn (< 180d)'
                    fefoBg = '#fffbeb'
                    fefoColor = '#b45309'
                  }

                  return (
                    <tr
                      key={b.id || b.batch_id}
                      style={{ borderBottom: '1px solid #f1f5f9', transition: 'background 0.15s ease' }}
                      onMouseEnter={(e) => (e.currentTarget.style.background = '#f8fafc')}
                      onMouseLeave={(e) => (e.currentTarget.style.background = 'white')}
                    >
                      <td style={{ padding: '14px 18px' }}>
                        <span
                          style={{
                            fontFamily: 'monospace',
                            fontWeight: 900,
                            color: '#0f172a',
                            background: '#f1f5f9',
                            padding: '4px 8px',
                            borderRadius: '6px',
                            border: '1px solid #e2e8f0',
                            fontSize: '12px',
                          }}
                        >
                          {b.batch_number}
                        </span>
                      </td>

                      <td style={{ padding: '14px 18px' }}>
                        <div style={{ fontWeight: 800, color: '#0f172a' }}>{b.product_name}</div>
                        <div style={{ fontSize: '11px', color: '#64748b', marginTop: '2px' }}>
                          SKU: {b.sku_code} • ĐVT: {b.unit_name}
                        </div>
                      </td>

                      <td style={{ padding: '14px 18px', color: '#64748b', fontSize: '12px' }}>
                        {b.manufacture_date ? new Date(b.manufacture_date).toLocaleDateString('vi-VN') : '—'}
                      </td>

                      <td style={{ padding: '14px 18px' }}>
                        <div
                          style={{
                            fontWeight: 800,
                            fontSize: '12.5px',
                            color: b.is_expired ? '#b91c1c' : b.is_near_expiry ? '#b45309' : '#0f172a',
                          }}
                        >
                          {new Date(b.expiry_date).toLocaleDateString('vi-VN')}
                        </div>
                        {b.is_near_expiry && !b.is_expired && (
                          <div style={{ fontSize: '10.5px', color: '#b45309', fontWeight: 700, marginTop: '2px' }}>
                            ⚠️ Ưu tiên xuất trước
                          </div>
                        )}
                      </td>

                      <td style={{ padding: '14px 18px', fontWeight: 800, color: '#0f172a' }}>
                        {b.quantity_on_hand.toLocaleString('vi-VN')}
                      </td>

                      <td style={{ padding: '14px 18px', fontWeight: 900, color: '#047857' }}>
                        {b.quantity_available.toLocaleString('vi-VN')}
                      </td>

                      <td style={{ padding: '14px 18px', textAlign: 'center' }}>
                        <span
                          style={{
                            padding: '4px 10px',
                            borderRadius: '9999px',
                            fontSize: '11px',
                            fontWeight: 800,
                            background: fefoBg,
                            color: fefoColor,
                            whiteSpace: 'nowrap',
                          }}
                        >
                          {fefoLabel}
                        </span>
                      </td>
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination Bar */}
        {totalPages > 1 && (
          <div
            style={{
              padding: '14px 20px',
              borderTop: '1px solid #e2e8f0',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              background: '#f8fafc',
            }}
          >
            <div style={{ fontSize: '12.5px', color: '#64748b' }}>
              Trang <b>{page}</b> / <b>{totalPages}</b> (Tổng {total} lô)
            </div>

            <div style={{ display: 'flex', gap: '8px' }}>
              <button
                type="button"
                disabled={page <= 1}
                onClick={() => setPage(page - 1)}
                style={{
                  padding: '6px 12px',
                  borderRadius: '8px',
                  border: '1px solid #cbd5e1',
                  background: 'white',
                  cursor: page <= 1 ? 'not-allowed' : 'pointer',
                  opacity: page <= 1 ? 0.5 : 1,
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px',
                  fontSize: '12px',
                  fontWeight: 700,
                }}
              >
                <ChevronLeft size={14} /> Trước
              </button>
              <button
                type="button"
                disabled={page >= totalPages}
                onClick={() => setPage(page + 1)}
                style={{
                  padding: '6px 12px',
                  borderRadius: '8px',
                  border: '1px solid #cbd5e1',
                  background: 'white',
                  cursor: page >= totalPages ? 'not-allowed' : 'pointer',
                  opacity: page >= totalPages ? 0.5 : 1,
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px',
                  fontSize: '12px',
                  fontWeight: 700,
                }}
              >
                Sau <ChevronRight size={14} />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
