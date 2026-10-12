import { useEffect, useState } from 'react'
import {
  Boxes,
  Search,
  Layers,
  ShieldCheck,
  Package,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react'
import { api } from '../../services/api'

interface StockItem {
  product_id: number
  product_name: string
  registration_number: string | null
  product_type: string | null
  sku_id: number
  sku_code: string
  unit_name: string
  total_on_hand: number
  total_available: number
  total_reserved: number
  batches_count: number
}

export function WarehouseStockPage() {
  const [stock, setStock] = useState<StockItem[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')

  const fetchStock = () => {
    setLoading(true)
    const params = new URLSearchParams({
      page: String(page),
      page_size: '25',
    })
    if (search.trim()) params.append('search', search.trim())

    api<{ items: StockItem[]; total: number }>(`/warehouse-portal/stock?${params.toString()}`)
      .then((res) => {
        setStock(res.items || [])
        setTotal(res.total || 0)
      })
      .catch((err) => console.error(err))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    fetchStock()
  }, [page])

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setPage(1)
    fetchStock()
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
            GIÁM SÁT TỒN KHO THỰC TẾ & KHẢ DỤNG
          </div>
          <h1 style={{ margin: '4px 0 0', fontSize: '22px', fontWeight: 900, color: '#0f172a' }}>
            Tồn Kho Thuốc Chi Nhánh
          </h1>
          <p style={{ margin: '4px 0 0', fontSize: '13px', color: '#64748b' }}>
            Chi tiết số lượng tồn vật lý, số lượng đã giữ chỗ cho đơn và khả dụng bán tại kho
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
          <Boxes size={16} />
          <span>Tổng số: {total} sản phẩm SKU</span>
        </div>
      </div>

      {/* Search Bar */}
      <div
        style={{
          background: 'white',
          borderRadius: '16px',
          border: '1px solid #e2e8f0',
          padding: '16px 20px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          boxShadow: '0 1px 3px rgba(0,0,0,0.03)',
        }}
      >
        <form onSubmit={handleSearchSubmit} style={{ display: 'flex', alignItems: 'center', gap: '8px', flex: '1', maxWidth: '460px' }}>
          <div style={{ position: 'relative', width: '100%' }}>
            <input
              type="text"
              placeholder="Tìm theo tên thuốc, số đăng ký, mã SKU…"
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
              padding: '9px 18px',
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
            Tìm kiếm
          </button>
        </form>
      </div>

      {/* Stock Table */}
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
                <th style={{ padding: '14px 18px' }}>Tên Thuốc & Hoạt Chất</th>
                <th style={{ padding: '14px 18px' }}>Mã SKU</th>
                <th style={{ padding: '14px 18px' }}>Đơn Vị Tính</th>
                <th style={{ padding: '14px 18px' }}>Tổng Lô</th>
                <th style={{ padding: '14px 18px' }}>Tồn Vật Lý</th>
                <th style={{ padding: '14px 18px' }}>Đã Giữ Chỗ</th>
                <th style={{ padding: '14px 18px' }}>Khả Dụng Bán</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={7} style={{ padding: '40px', textAlign: 'center', color: '#94a3b8', fontWeight: 600 }}>
                    Đang tải dữ liệu tồn kho…
                  </td>
                </tr>
              ) : stock.length === 0 ? (
                <tr>
                  <td colSpan={7} style={{ padding: '40px', textAlign: 'center', color: '#94a3b8', fontWeight: 600 }}>
                    Chi nhánh hiện chưa có sản phẩm nào trong kho.
                  </td>
                </tr>
              ) : (
                stock.map((item) => (
                  <tr
                    key={item.sku_id}
                    style={{ borderBottom: '1px solid #f1f5f9', transition: 'background 0.15s ease' }}
                    onMouseEnter={(e) => (e.currentTarget.style.background = '#f8fafc')}
                    onMouseLeave={(e) => (e.currentTarget.style.background = 'white')}
                  >
                    <td style={{ padding: '14px 18px' }}>
                      <div style={{ fontWeight: 800, color: '#0f172a' }}>{item.product_name}</div>
                      <div style={{ fontSize: '11px', color: '#64748b', marginTop: '3px', display: 'flex', gap: '8px' }}>
                        {item.registration_number && <span>SĐK: {item.registration_number}</span>}
                        {item.product_type && (
                          <span style={{ background: '#f1f5f9', padding: '1px 6px', borderRadius: '4px', fontWeight: 700 }}>
                            {item.product_type}
                          </span>
                        )}
                      </div>
                    </td>

                    <td style={{ padding: '14px 18px', fontFamily: 'monospace', fontWeight: 800, color: '#475569' }}>
                      {item.sku_code}
                    </td>

                    <td style={{ padding: '14px 18px', fontWeight: 600, color: '#334155' }}>
                      {item.unit_name}
                    </td>

                    <td style={{ padding: '14px 18px' }}>
                      <span
                        style={{
                          padding: '3px 8px',
                          borderRadius: '6px',
                          background: '#f1f5f9',
                          fontSize: '11.5px',
                          fontWeight: 700,
                          color: '#475569',
                        }}
                      >
                        {item.batches_count} lô
                      </span>
                    </td>

                    <td style={{ padding: '14px 18px', fontWeight: 800, color: '#0f172a' }}>
                      {item.total_on_hand.toLocaleString('vi-VN')}
                    </td>

                    <td style={{ padding: '14px 18px', fontWeight: 700, color: '#d97706' }}>
                      {item.total_reserved.toLocaleString('vi-VN')}
                    </td>

                    <td style={{ padding: '14px 18px', fontWeight: 900, color: '#047857', fontSize: '14px' }}>
                      {item.total_available.toLocaleString('vi-VN')}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
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
              Trang <b>{page}</b> / <b>{totalPages}</b> (Tổng {total} SKU)
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
