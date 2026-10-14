import { useEffect, useState } from 'react'
import {
  Boxes,
  Search,
  Filter,
  Eye,
  X,
  AlertTriangle,
  Clock,
  Layers,
  ArrowUpDown,
  ShoppingBag,
  Info,
  CheckCircle2,
  Calendar,
  Building2,
  FileText,
  ShieldAlert,
  Tag,
  ChevronRight,
} from 'lucide-react'
import { api } from '../../services/api'
import { WarehouseProductItem, WarehouseProductDetail } from '../../types'

export function WarehouseProductsPage() {
  const [products, setProducts] = useState<WarehouseProductItem[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('ALL')
  const [page, setPage] = useState(1)
  const pageSize = 15

  // 5-Tab Detail Drawer State
  const [selectedSkuId, setSelectedSkuId] = useState<number | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [detailData, setDetailData] = useState<WarehouseProductDetail | null>(null)
  const [activeTab, setActiveTab] = useState<'info' | 'stock' | 'batches' | 'movements' | 'orders'>('info')

  const fetchProducts = () => {
    setLoading(true)
    const params = new URLSearchParams({
      page: page.toString(),
      page_size: pageSize.toString(),
      status_filter: statusFilter,
    })
    if (search.trim()) {
      params.set('search', search.trim())
    }

    api<{ items: WarehouseProductItem[]; total: number }>(`/warehouse-portal/products?${params.toString()}`)
      .then((res) => {
        setProducts(res.items || [])
        setTotal(res.total || 0)
      })
      .catch((err) => console.error(err))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    fetchProducts()
  }, [page, statusFilter])

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setPage(1)
    fetchProducts()
  }

  const handleOpenDetail = (skuId: number) => {
    setSelectedSkuId(skuId)
    setActiveTab('info')
    setDetailLoading(true)
    api<WarehouseProductDetail>(`/warehouse-portal/products/${skuId}`)
      .then((res) => setDetailData(res))
      .catch((err) => console.error(err))
      .finally(() => setDetailLoading(false))
  }

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'IN_STOCK':
        return (
          <span style={{ padding: '3px 10px', borderRadius: '9999px', fontSize: '11px', fontWeight: 800, background: '#dcfce7', color: '#166534' }}>
            ● Đủ hàng
          </span>
        )
      case 'LOW_STOCK':
        return (
          <span style={{ padding: '3px 10px', borderRadius: '9999px', fontSize: '11px', fontWeight: 800, background: '#fef3c7', color: '#92400e' }}>
            ⚠️ Sắp hết hàng
          </span>
        )
      case 'OUT_OF_STOCK':
        return (
          <span style={{ padding: '3px 10px', borderRadius: '9999px', fontSize: '11px', fontWeight: 800, background: '#fee2e2', color: '#991b1b' }}>
            ✕ Hết hàng
          </span>
        )
      case 'NEAR_EXPIRY':
        return (
          <span style={{ padding: '3px 10px', borderRadius: '9999px', fontSize: '11px', fontWeight: 800, background: '#ffedd5', color: '#9a3412' }}>
            ⏳ Có lô cận hạn
          </span>
        )
      default:
        return <span>{status}</span>
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
          <div style={{ fontSize: '11px', fontWeight: 800, color: '#059669', textTransform: 'uppercase', letterSpacing: '0.8px' }}>
            DANH MỤC THUỐC TẠI CHI NHÁNH KHO
          </div>
          <h1 style={{ margin: '4px 0 0', fontSize: '22px', fontWeight: 900, color: '#0f172a' }}>
            Thuốc & Tồn Kho Chi Nhánh
          </h1>
          <p style={{ margin: '4px 0 0', fontSize: '13px', color: '#64748b' }}>
            Quản lý số lượng tồn vật lý, hạn dùng FEFO và hồ sơ thuốc dùng chung toàn hệ thống
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div
            style={{
              padding: '8px 14px',
              borderRadius: '10px',
              background: '#f8fafc',
              border: '1px solid #e2e8f0',
              fontSize: '13px',
              fontWeight: 700,
              color: '#334155',
            }}
          >
            Tổng số: <span style={{ color: '#059669', fontWeight: 900 }}>{total}</span> loại thuốc
          </div>
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
          gap: '12px',
        }}
      >
        <form onSubmit={handleSearchSubmit} style={{ display: 'flex', alignItems: 'center', gap: '8px', flex: 1, minWidth: '280px' }}>
          <div style={{ position: 'relative', flex: 1 }}>
            <Search size={16} style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: '#94a3b8' }} />
            <input
              type="text"
              placeholder="Tìm theo tên thuốc, số đăng ký, mã SKU…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              style={{
                width: '100%',
                padding: '9px 12px 9px 36px',
                borderRadius: '10px',
                border: '1px solid #cbd5e1',
                fontSize: '13px',
                outline: 'none',
              }}
            />
          </div>
          <button
            type="submit"
            style={{
              background: '#059669',
              color: 'white',
              border: 'none',
              borderRadius: '10px',
              padding: '9px 16px',
              fontSize: '13px',
              fontWeight: 700,
              cursor: 'pointer',
            }}
          >
            Tìm kiếm
          </button>
        </form>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
          <span style={{ fontSize: '12px', fontWeight: 700, color: '#64748b' }}>Trạng thái:</span>
          {[
            { id: 'ALL', label: 'Tất cả' },
            { id: 'IN_STOCK', label: 'Đủ hàng' },
            { id: 'LOW_STOCK', label: 'Sắp hết' },
            { id: 'OUT_OF_STOCK', label: 'Hết hàng' },
            { id: 'NEAR_EXPIRY', label: 'Cận hạn (≤180d)' },
          ].map((st) => (
            <button
              key={st.id}
              onClick={() => {
                setStatusFilter(st.id)
                setPage(1)
              }}
              style={{
                padding: '6px 12px',
                borderRadius: '8px',
                fontSize: '12px',
                fontWeight: 700,
                border: 'none',
                cursor: 'pointer',
                background: statusFilter === st.id ? '#059669' : '#f1f5f9',
                color: statusFilter === st.id ? 'white' : '#475569',
                transition: 'all 0.15s ease',
              }}
            >
              {st.label}
            </button>
          ))}
        </div>
      </div>

      {/* Products Table */}
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
              <tr
                style={{
                  background: '#f8fafc',
                  borderBottom: '1px solid #e2e8f0',
                  color: '#64748b',
                  fontSize: '11px',
                  fontWeight: 800,
                  textTransform: 'uppercase',
                  letterSpacing: '0.5px',
                }}
              >
                <th style={{ padding: '14px 18px' }}>Thông Tin Thuốc</th>
                <th style={{ padding: '14px 18px' }}>Quy Cách (UOM)</th>
                <th style={{ padding: '14px 18px', textAlign: 'center' }}>Tồn Vật Lý</th>
                <th style={{ padding: '14px 18px', textAlign: 'center' }}>Khả Dụng</th>
                <th style={{ padding: '14px 18px', textAlign: 'center' }}>Đang Giữ</th>
                <th style={{ padding: '14px 18px' }}>Số Lô / HSD Sớm Nhất</th>
                <th style={{ padding: '14px 18px' }}>Trạng Thái</th>
                <th style={{ padding: '14px 18px', textAlign: 'right' }}>Thao Tác</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={8} style={{ padding: '40px', textAlign: 'center', color: '#94a3b8', fontWeight: 600 }}>
                    Đang tải danh mục thuốc trong kho…
                  </td>
                </tr>
              ) : products.length === 0 ? (
                <tr>
                  <td colSpan={8} style={{ padding: '40px', textAlign: 'center', color: '#94a3b8', fontWeight: 600 }}>
                    Không tìm thấy thuốc nào phù hợp với bộ lọc.
                  </td>
                </tr>
              ) : (
                products.map((p) => (
                  <tr
                    key={p.sku_id}
                    style={{ borderBottom: '1px solid #f1f5f9', transition: 'background 0.15s ease' }}
                    onMouseEnter={(e) => (e.currentTarget.style.background = '#f8fafc')}
                    onMouseLeave={(e) => (e.currentTarget.style.background = 'white')}
                  >
                    <td style={{ padding: '14px 18px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                        <div
                          style={{
                            width: '40px',
                            height: '40px',
                            borderRadius: '8px',
                            background: '#f1f5f9',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            overflow: 'hidden',
                            flexShrink: 0,
                          }}
                        >
                          {p.image_url ? (
                            <img src={p.image_url} alt={p.product_name} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                          ) : (
                            <Boxes size={20} color="#94a3b8" />
                          )}
                        </div>
                        <div>
                          <div style={{ fontWeight: 800, color: '#0f172a', fontSize: '13.5px' }}>{p.product_name}</div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '2px' }}>
                            <span style={{ fontSize: '11px', color: '#059669', fontWeight: 700 }}>SĐK: {p.registration_number || '—'}</span>
                            <span style={{ fontSize: '11px', color: '#94a3b8' }}>•</span>
                            <span style={{ fontSize: '11px', color: '#64748b', fontFamily: 'monospace' }}>{p.sku_code}</span>
                          </div>
                        </div>
                      </div>
                    </td>

                    <td style={{ padding: '14px 18px' }}>
                      <span
                        style={{
                          background: '#f1f5f9',
                          padding: '4px 8px',
                          borderRadius: '6px',
                          fontSize: '12px',
                          fontWeight: 700,
                          color: '#475569',
                        }}
                      >
                        {p.uom || 'Hộp'}
                      </span>
                    </td>

                    <td style={{ padding: '14px 18px', textAlign: 'center', fontWeight: 800, color: '#0f172a' }}>
                      {(p.total_on_hand ?? 0).toLocaleString()}
                    </td>

                    <td style={{ padding: '14px 18px', textAlign: 'center' }}>
                      <span
                        style={{
                          fontWeight: 900,
                          color: (p.total_available ?? 0) <= 10 ? '#dc2626' : '#059669',
                          fontSize: '14px',
                        }}
                      >
                        {(p.total_available ?? 0).toLocaleString()}
                      </span>
                    </td>

                    <td style={{ padding: '14px 18px', textAlign: 'center', color: '#64748b', fontWeight: 700 }}>
                      {(p.total_reserved ?? 0).toLocaleString()}
                    </td>

                    <td style={{ padding: '14px 18px' }}>
                      <div style={{ fontSize: '12px', fontWeight: 700, color: '#0f172a' }}>{p.batches_count} lô lưu trữ</div>
                      <div style={{ fontSize: '11px', color: '#64748b', marginTop: '2px' }}>
                        HSD sớm: {p.earliest_expiry ? new Date(p.earliest_expiry).toLocaleDateString('vi-VN') : '—'}
                      </div>
                    </td>

                    <td style={{ padding: '14px 18px' }}>{getStatusBadge(p.stock_status)}</td>

                    <td style={{ padding: '14px 18px', textAlign: 'right' }}>
                      <button
                        onClick={() => handleOpenDetail(p.sku_id)}
                        style={{
                          background: '#ecfdf5',
                          border: '1px solid #a7f3d0',
                          color: '#059669',
                          padding: '6px 12px',
                          borderRadius: '8px',
                          fontSize: '12px',
                          fontWeight: 700,
                          cursor: 'pointer',
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '5px',
                        }}
                      >
                        <Eye size={14} /> Chi tiết 5 mục
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {total > pageSize && (
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
            <div style={{ fontSize: '12px', color: '#64748b', fontWeight: 600 }}>
              Hiển thị {(page - 1) * pageSize + 1} - {Math.min(page * pageSize, total)} trong tổng số {total} thuốc
            </div>
            <div style={{ display: 'flex', gap: '8px' }}>
              <button
                disabled={page <= 1}
                onClick={() => setPage(page - 1)}
                style={{
                  padding: '5px 12px',
                  borderRadius: '6px',
                  border: '1px solid #cbd5e1',
                  background: 'white',
                  fontSize: '12px',
                  fontWeight: 600,
                  cursor: page <= 1 ? 'not-allowed' : 'pointer',
                  opacity: page <= 1 ? 0.5 : 1,
                }}
              >
                Trang trước
              </button>
              <button
                disabled={page * pageSize >= total}
                onClick={() => setPage(page + 1)}
                style={{
                  padding: '5px 12px',
                  borderRadius: '6px',
                  border: '1px solid #cbd5e1',
                  background: 'white',
                  fontSize: '12px',
                  fontWeight: 600,
                  cursor: page * pageSize >= total ? 'not-allowed' : 'pointer',
                  opacity: page * pageSize >= total ? 0.5 : 1,
                }}
              >
                Trang sau
              </button>
            </div>
          </div>
        )}
      </div>

      {/* 5-Tab Detail Drawer / Modal */}
      {selectedSkuId && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(15, 23, 42, 0.6)',
            backdropFilter: 'blur(3px)',
            zIndex: 100,
            display: 'flex',
            justifyContent: 'flex-end',
          }}
        >
          <div
            style={{
              width: '100%',
              maxWidth: '820px',
              height: '100%',
              background: 'white',
              boxShadow: '-4px 0 24px rgba(0,0,0,0.15)',
              display: 'flex',
              flexDirection: 'column',
              animation: 'slideInRight 0.25s ease-out',
            }}
          >
            {/* Drawer Header */}
            <div
              style={{
                padding: '20px 24px',
                borderBottom: '1px solid #e2e8f0',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                background: '#f8fafc',
              }}
            >
              <div>
                <div style={{ fontSize: '11px', fontWeight: 800, color: '#059669', textTransform: 'uppercase', letterSpacing: '0.8px' }}>
                  HỒ SƠ THUỐC VÀ TỒN KHO CHI TIẾT
                </div>
                <div style={{ fontSize: '18px', fontWeight: 900, color: '#0f172a', marginTop: '2px' }}>
                  {detailData?.general_info.canonical_name || 'Đang tải dữ liệu…'}
                </div>
                {detailData && (
                  <div style={{ fontSize: '12px', color: '#64748b', marginTop: '2px' }}>
                    SĐK: <strong style={{ color: '#0f172a' }}>{detailData.general_info.registration_number}</strong> • SKU:{' '}
                    <strong style={{ color: '#0f172a' }}>{detailData.general_info.sku_code}</strong>
                  </div>
                )}
              </div>
              <button
                onClick={() => {
                  setSelectedSkuId(null)
                  setDetailData(null)
                }}
                style={{
                  background: '#f1f5f9',
                  border: 'none',
                  borderRadius: '8px',
                  padding: '8px',
                  cursor: 'pointer',
                  color: '#64748b',
                }}
              >
                <X size={20} />
              </button>
            </div>

            {/* 5 Tabs Header */}
            <div
              style={{
                display: 'flex',
                borderBottom: '1px solid #e2e8f0',
                padding: '0 24px',
                background: 'white',
                gap: '8px',
                overflowX: 'auto',
              }}
            >
              {[
                { id: 'info', label: 'Tab A: Thông Tin Chung (Admin)', icon: Info },
                { id: 'stock', label: 'Tab B: Mức Tồn Kho', icon: Boxes },
                { id: 'batches', label: 'Tab C: Danh Sách Lô', icon: Layers },
                { id: 'movements', label: 'Tab D: Biến Động Kho', icon: ArrowUpDown },
                { id: 'orders', label: 'Tab E: Đơn Hàng Liên Quan', icon: ShoppingBag },
              ].map((t) => {
                const Icon = t.icon
                const isActive = activeTab === t.id
                return (
                  <button
                    key={t.id}
                    onClick={() => setActiveTab(t.id as any)}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '6px',
                      padding: '12px 14px',
                      fontSize: '12.5px',
                      fontWeight: isActive ? 800 : 600,
                      color: isActive ? '#059669' : '#64748b',
                      border: 'none',
                      borderBottom: isActive ? '3px solid #059669' : '3px solid transparent',
                      background: 'none',
                      cursor: 'pointer',
                      whiteSpace: 'nowrap',
                      transition: 'all 0.15s ease',
                    }}
                  >
                    <Icon size={15} />
                    {t.label}
                  </button>
                )
              })}
            </div>

            {/* Tab Body */}
            <div style={{ flex: 1, overflowY: 'auto', padding: '24px' }}>
              {detailLoading ? (
                <div style={{ textAlign: 'center', padding: '60px', color: '#94a3b8', fontWeight: 600 }}>
                  Đang tải thông tin chi tiết…
                </div>
              ) : !detailData ? (
                <div style={{ textAlign: 'center', padding: '60px', color: '#ef4444', fontWeight: 600 }}>
                  Không tìm thấy thông tin thuốc.
                </div>
              ) : (
                <>
                  {/* TAB A: Thông tin chung */}
                  {activeTab === 'info' && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                      <div
                        style={{
                          padding: '12px 16px',
                          borderRadius: '10px',
                          background: '#ecfdf5',
                          border: '1px solid #a7f3d0',
                          fontSize: '12px',
                          color: '#065f46',
                        }}
                      >
                        ℹ️ <strong>Dữ liệu thuốc dùng chung toàn hệ thống:</strong> Do Admin quản lý. Mọi chi nhánh kho đều xem chung dữ liệu y tế này và Quản lý kho không chỉnh sửa các thông số dược lý.
                      </div>

                      <div
                        style={{
                          display: 'grid',
                          gridTemplateColumns: 'repeat(2, 1fr)',
                          gap: '16px',
                          background: '#f8fafc',
                          padding: '18px',
                          borderRadius: '12px',
                          border: '1px solid #e2e8f0',
                        }}
                      >
                        <div>
                          <div style={{ fontSize: '11px', color: '#64748b', fontWeight: 700 }}>TÊN GỐC DƯỢC PHẨM</div>
                          <div style={{ fontSize: '14px', fontWeight: 800, color: '#0f172a', marginTop: '2px' }}>
                            {detailData.general_info.canonical_name}
                          </div>
                        </div>

                        <div>
                          <div style={{ fontSize: '11px', color: '#64748b', fontWeight: 700 }}>SỐ ĐĂNG KÝ (SDK)</div>
                          <div style={{ fontSize: '14px', fontWeight: 800, color: '#059669', marginTop: '2px' }}>
                            {detailData.general_info.registration_number || '—'}
                          </div>
                        </div>

                        <div>
                          <div style={{ fontSize: '11px', color: '#64748b', fontWeight: 700 }}>HOẠT CHẤT & HÀM LƯỢNG</div>
                          <div style={{ fontSize: '13px', fontWeight: 600, color: '#0f172a', marginTop: '2px' }}>
                            {detailData.general_info.active_ingredients || '—'}
                          </div>
                        </div>

                        <div>
                          <div style={{ fontSize: '11px', color: '#64748b', fontWeight: 700 }}>DẠNG BÀO CHẾ & ĐƯỜNG DÙNG</div>
                          <div style={{ fontSize: '13px', fontWeight: 600, color: '#0f172a', marginTop: '2px' }}>
                            {detailData.general_info.dosage_form || '—'} • {detailData.general_info.route_of_administration || 'Uống'}
                          </div>
                        </div>

                        <div>
                          <div style={{ fontSize: '11px', color: '#64748b', fontWeight: 700 }}>NHÀ SẢN XUẤT & QUỐC GIA</div>
                          <div style={{ fontSize: '13px', fontWeight: 600, color: '#0f172a', marginTop: '2px' }}>
                            {detailData.general_info.manufacturer || '—'} ({detailData.general_info.country_of_origin || 'Việt Nam'})
                          </div>
                        </div>

                        <div>
                          <div style={{ fontSize: '11px', color: '#64748b', fontWeight: 700 }}>QUY CÁCH ĐÓNG GÓI</div>
                          <div style={{ fontSize: '13px', fontWeight: 600, color: '#0f172a', marginTop: '2px' }}>
                            {detailData.general_info.package_description || detailData.general_info.uom}
                          </div>
                        </div>

                        <div>
                          <div style={{ fontSize: '11px', color: '#64748b', fontWeight: 700 }}>PHÂN LOẠI KÊ ĐƠN</div>
                          <div style={{ fontSize: '13px', fontWeight: 800, marginTop: '2px', color: detailData.general_info.is_prescription ? '#dc2626' : '#059669' }}>
                            {detailData.general_info.is_prescription ? '🔴 Thuốc kê đơn (Rx)' : '🟢 Thuốc không kê đơn (OTC)'}
                          </div>
                        </div>

                        <div>
                          <div style={{ fontSize: '11px', color: '#64748b', fontWeight: 700 }}>GIÁ NIÊM YẾT HỆ THỐNG</div>
                          <div style={{ fontSize: '14px', fontWeight: 900, color: '#0f172a', marginTop: '2px' }}>
                            {detailData.general_info.base_price ? detailData.general_info.base_price.toLocaleString('vi-VN') + ' đ' : 'Theo chi nhánh'}
                          </div>
                        </div>
                      </div>

                      {detailData.general_info.description && (
                        <div style={{ background: '#f8fafc', padding: '16px', borderRadius: '12px', border: '1px solid #e2e8f0' }}>
                          <div style={{ fontSize: '11px', color: '#64748b', fontWeight: 700, marginBottom: '6px' }}>MÔ TẢ VÀ CHỈ ĐỊNH DƯỢC LÝ</div>
                          <div style={{ fontSize: '13px', color: '#334155', lineHeight: '1.6' }}>{detailData.general_info.description}</div>
                        </div>
                      )}
                    </div>
                  )}

                  {/* TAB B: Mức Tồn Kho */}
                  {activeTab === 'stock' && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                      <div
                        style={{
                          display: 'grid',
                          gridTemplateColumns: 'repeat(4, 1fr)',
                          gap: '12px',
                        }}
                      >
                        <div style={{ background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: '12px', padding: '16px' }}>
                          <div style={{ fontSize: '11px', fontWeight: 700, color: '#64748b' }}>TỒN VẬT LÝ</div>
                          <div style={{ fontSize: '22px', fontWeight: 900, color: '#0f172a', marginTop: '4px' }}>
                            {(detailData.stock_levels?.total_on_hand ?? 0).toLocaleString()}
                          </div>
                          <div style={{ fontSize: '11px', color: '#94a3b8', marginTop: '2px' }}>{detailData.general_info.uom}</div>
                        </div>

                        <div style={{ background: '#ecfdf5', border: '1px solid #a7f3d0', borderRadius: '12px', padding: '16px' }}>
                          <div style={{ fontSize: '11px', fontWeight: 700, color: '#059669' }}>KHẢ DỤNG (BÁN ĐƯỢC)</div>
                          <div style={{ fontSize: '22px', fontWeight: 900, color: '#059669', marginTop: '4px' }}>
                            {(detailData.stock_levels?.total_available ?? 0).toLocaleString()}
                          </div>
                          <div style={{ fontSize: '11px', color: '#059669', marginTop: '2px' }}>{detailData.general_info.uom}</div>
                        </div>

                        <div style={{ background: '#fffbeb', border: '1px solid #fde68a', borderRadius: '12px', padding: '16px' }}>
                          <div style={{ fontSize: '11px', fontWeight: 700, color: '#d97706' }}>ĐANG GIỮ CHO ĐƠN</div>
                          <div style={{ fontSize: '22px', fontWeight: 900, color: '#d97706', marginTop: '4px' }}>
                            {(detailData.stock_levels?.total_reserved ?? 0).toLocaleString()}
                          </div>
                          <div style={{ fontSize: '11px', color: '#d97706', marginTop: '2px' }}>{detailData.general_info.uom}</div>
                        </div>

                        <div style={{ background: '#fef2f2', border: '1px solid #fecaca', borderRadius: '12px', padding: '16px' }}>
                          <div style={{ fontSize: '11px', fontWeight: 700, color: '#dc2626' }}>CÁCH LY / LỖI</div>
                          <div style={{ fontSize: '22px', fontWeight: 900, color: '#dc2626', marginTop: '4px' }}>
                            {(detailData.stock_levels?.total_quarantined ?? 0).toLocaleString()}
                          </div>
                          <div style={{ fontSize: '11px', color: '#dc2626', marginTop: '2px' }}>{detailData.general_info.uom}</div>
                        </div>
                      </div>

                      <div style={{ background: '#f8fafc', padding: '18px', borderRadius: '12px', border: '1px solid #e2e8f0' }}>
                        <h4 style={{ margin: '0 0 12px', fontSize: '13px', fontWeight: 800, color: '#0f172a' }}>
                          ĐỊNH MỨC AN TOÀN TẠI KHO (MIN - MAX)
                        </h4>
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '16px' }}>
                          <div>
                            <div style={{ fontSize: '11px', color: '#64748b', fontWeight: 700 }}>TỒN TỐI THIỂU (MIN)</div>
                            <div style={{ fontSize: '16px', fontWeight: 800, color: '#0f172a', marginTop: '2px' }}>
                              {detailData.stock_levels.min_stock} {detailData.general_info.uom}
                            </div>
                          </div>
                          <div>
                            <div style={{ fontSize: '11px', color: '#64748b', fontWeight: 700 }}>ĐIỂM ĐẶT HÀNG LẠI</div>
                            <div style={{ fontSize: '16px', fontWeight: 800, color: '#059669', marginTop: '2px' }}>
                              {detailData.stock_levels.reorder_point} {detailData.general_info.uom}
                            </div>
                          </div>
                          <div>
                            <div style={{ fontSize: '11px', color: '#64748b', fontWeight: 700 }}>TỒN TỐI ĐA (MAX)</div>
                            <div style={{ fontSize: '16px', fontWeight: 800, color: '#0f172a', marginTop: '2px' }}>
                              {detailData.stock_levels.max_stock} {detailData.general_info.uom}
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* TAB C: Danh sách lô */}
                  {activeTab === 'batches' && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                      <div style={{ fontSize: '12px', color: '#64748b' }}>
                        Các lô thuốc được sắp xếp theo hạn sử dụng sớm nhất (FEFO) để ưu tiên soạn hàng.
                      </div>
                      {detailData.batches.length === 0 ? (
                        <div style={{ textAlign: 'center', padding: '40px', color: '#94a3b8' }}>Chưa có lô thuốc nào trong kho này.</div>
                      ) : (
                        <div style={{ border: '1px solid #e2e8f0', borderRadius: '12px', overflow: 'hidden' }}>
                          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '12.5px' }}>
                            <thead>
                              <tr style={{ background: '#f8fafc', borderBottom: '1px solid #e2e8f0', color: '#64748b', fontSize: '11px', fontWeight: 800 }}>
                                <th style={{ padding: '12px 14px' }}>Số Lô</th>
                                <th style={{ padding: '12px 14px' }}>Hạn Sử Dụng (FEFO)</th>
                                <th style={{ padding: '12px 14px', textAlign: 'center' }}>Tồn Vật Lý</th>
                                <th style={{ padding: '12px 14px', textAlign: 'center' }}>Khả Dụng</th>
                                <th style={{ padding: '12px 14px' }}>Vị Trí Kệ</th>
                                <th style={{ padding: '12px 14px' }}>Trạng Thái Lô</th>
                              </tr>
                            </thead>
                            <tbody>
                              {detailData.batches.map((b) => (
                                <tr key={b.batch_id} style={{ borderBottom: '1px solid #f1f5f9' }}>
                                  <td style={{ padding: '12px 14px', fontWeight: 800, color: '#0f172a', fontFamily: 'monospace' }}>
                                    {b.batch_number}
                                  </td>
                                  <td style={{ padding: '12px 14px' }}>
                                    <div style={{ fontWeight: 700, color: b.is_expired ? '#dc2626' : b.is_near_expiry ? '#ea580c' : '#0f172a' }}>
                                      {b.expiry_date ? new Date(b.expiry_date).toLocaleDateString('vi-VN') : '—'}
                                    </div>
                                    <div style={{ fontSize: '11px', color: '#64748b' }}>
                                      {b.is_expired ? 'Đã hết hạn' : `Còn ${b.days_left} ngày`}
                                    </div>
                                  </td>
                                  <td style={{ padding: '12px 14px', textAlign: 'center', fontWeight: 700 }}>
                                    {(b.quantity_on_hand ?? 0).toLocaleString()}
                                  </td>
                                  <td style={{ padding: '12px 14px', textAlign: 'center', fontWeight: 800, color: '#059669' }}>
                                    {(b.quantity_available ?? 0).toLocaleString()}
                                  </td>
                                  <td style={{ padding: '12px 14px', color: '#475569' }}>{b.location_name}</td>
                                  <td style={{ padding: '12px 14px' }}>
                                    {b.status === 'ACTIVE' ? (
                                      <span style={{ padding: '3px 8px', borderRadius: '6px', fontSize: '11px', fontWeight: 700, background: '#dcfce7', color: '#166534' }}>
                                        Hoạt động
                                      </span>
                                    ) : (
                                      <span style={{ padding: '3px 8px', borderRadius: '6px', fontSize: '11px', fontWeight: 700, background: '#fee2e2', color: '#991b1b' }}>
                                        {b.status}
                                      </span>
                                    )}
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      )}
                    </div>
                  )}

                  {/* TAB D: Biến Động Kho */}
                  {activeTab === 'movements' && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                      <div style={{ fontSize: '12px', color: '#64748b' }}>Lịch sử 50 giao dịch nhập, xuất, điều chỉnh gần nhất của thuốc này tại kho.</div>
                      {detailData.movements.length === 0 ? (
                        <div style={{ textAlign: 'center', padding: '40px', color: '#94a3b8' }}>Chưa có biến động kho nào ghi nhận.</div>
                      ) : (
                        <div style={{ border: '1px solid #e2e8f0', borderRadius: '12px', overflow: 'hidden' }}>
                          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '12px' }}>
                            <thead>
                              <tr style={{ background: '#f8fafc', borderBottom: '1px solid #e2e8f0', color: '#64748b', fontSize: '11px', fontWeight: 800 }}>
                                <th style={{ padding: '10px 12px' }}>Mã Biến Động</th>
                                <th style={{ padding: '10px 12px' }}>Loại Biến Động</th>
                                <th style={{ padding: '10px 12px' }}>Lô</th>
                                <th style={{ padding: '10px 12px', textAlign: 'center' }}>Số Lượng</th>
                                <th style={{ padding: '10px 12px', textAlign: 'center' }}>Tồn Sau Cùng</th>
                                <th style={{ padding: '10px 12px' }}>Chứng Từ Tham Chiếu</th>
                                <th style={{ padding: '10px 12px' }}>Thời Gian</th>
                              </tr>
                            </thead>
                            <tbody>
                              {detailData.movements.map((m) => (
                                <tr key={m.id} style={{ borderBottom: '1px solid #f1f5f9' }}>
                                  <td style={{ padding: '10px 12px', fontFamily: 'monospace', fontWeight: 700, color: '#0f172a' }}>
                                    {m.movement_code}
                                  </td>
                                  <td style={{ padding: '10px 12px' }}>
                                    <span
                                      style={{
                                        padding: '2px 6px',
                                        borderRadius: '4px',
                                        fontSize: '10.5px',
                                        fontWeight: 800,
                                        background: m.movement_type === 'RECEIPT' ? '#dcfce7' : '#f1f5f9',
                                        color: m.movement_type === 'RECEIPT' ? '#166534' : '#475569',
                                      }}
                                    >
                                      {m.movement_type}
                                    </span>
                                  </td>
                                  <td style={{ padding: '10px 12px', fontFamily: 'monospace' }}>{m.batch_number}</td>
                                  <td style={{ padding: '10px 12px', textAlign: 'center', fontWeight: 800 }}>{m.quantity}</td>
                                  <td style={{ padding: '10px 12px', textAlign: 'center', color: '#64748b' }}>{m.balance_after}</td>
                                  <td style={{ padding: '10px 12px', color: '#059669', fontWeight: 600 }}>{m.reference_id || '—'}</td>
                                  <td style={{ padding: '10px 12px', color: '#64748b' }}>
                                    {m.created_at ? new Date(m.created_at).toLocaleString('vi-VN') : '—'}
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      )}
                    </div>
                  )}

                  {/* TAB E: Đơn hàng liên quan */}
                  {activeTab === 'orders' && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                      <div style={{ fontSize: '12px', color: '#64748b' }}>Các đơn hàng đang phân bổ hoặc đã xuất thuốc này tại kho.</div>
                      {detailData.related_orders.length === 0 ? (
                        <div style={{ textAlign: 'center', padding: '40px', color: '#94a3b8' }}>Chưa có đơn hàng nào phân bổ thuốc này.</div>
                      ) : (
                        <div style={{ border: '1px solid #e2e8f0', borderRadius: '12px', overflow: 'hidden' }}>
                          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '12.5px' }}>
                            <thead>
                              <tr style={{ background: '#f8fafc', borderBottom: '1px solid #e2e8f0', color: '#64748b', fontSize: '11px', fontWeight: 800 }}>
                                <th style={{ padding: '12px 14px' }}>Mã Đơn</th>
                                <th style={{ padding: '12px 14px' }}>Khách Hàng</th>
                                <th style={{ padding: '12px 14px', textAlign: 'center' }}>SL Phân Bổ</th>
                                <th style={{ padding: '12px 14px' }}>Lô Xuất</th>
                                <th style={{ padding: '12px 14px' }}>Trạng Thái Soạn</th>
                                <th style={{ padding: '12px 14px' }}>Thời Gian</th>
                              </tr>
                            </thead>
                            <tbody>
                              {detailData.related_orders.map((o, idx) => (
                                <tr key={idx} style={{ borderBottom: '1px solid #f1f5f9' }}>
                                  <td style={{ padding: '12px 14px', fontWeight: 800, color: '#059669', fontFamily: 'monospace' }}>
                                    {o.order_code}
                                  </td>
                                  <td style={{ padding: '12px 14px', fontWeight: 600, color: '#0f172a' }}>{o.customer_name}</td>
                                  <td style={{ padding: '12px 14px', textAlign: 'center', fontWeight: 800 }}>{o.allocated_quantity}</td>
                                  <td style={{ padding: '12px 14px', fontFamily: 'monospace' }}>{o.batch_number}</td>
                                  <td style={{ padding: '12px 14px' }}>
                                    <span style={{ padding: '3px 8px', borderRadius: '6px', fontSize: '11px', fontWeight: 700, background: '#f1f5f9', color: '#475569' }}>
                                      {o.fulfillment_status}
                                    </span>
                                  </td>
                                  <td style={{ padding: '12px 14px', color: '#64748b' }}>
                                    {o.created_at ? new Date(o.created_at).toLocaleDateString('vi-VN') : '—'}
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      )}
                    </div>
                  )}
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
