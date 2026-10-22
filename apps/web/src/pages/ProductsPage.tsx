import {
  AlertTriangle,
  Boxes,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Download,
  Eye,
  FileSpreadsheet,
  Filter,
  Package,
  Pill,
  Search,
  Sparkles,
} from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { AdminPageHeader } from '../components/AdminPageHeader'
import { FilterBar } from '../components/FilterBar'
import { EmptyState } from '../components/EmptyState'
import { StatusBadge } from '../components/StatusBadge'
import { PaginationBar } from '../components/PaginationBar'
import { API_URL, api, tokenStore } from '../services/api'
import type { Product, ProductPage } from '../types'

export function ProductsPage() {
  const [data, setData] = useState<ProductPage | null>(null)
  const [loading, setLoading] = useState(false)
  const [searchInput, setSearchInput] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [rxOtcStatus, setRxOtcStatus] = useState('')
  const [productType, setProductType] = useState('')
  const [categorySlug, setCategorySlug] = useState('')
  const [publishStatus, setPublishStatus] = useState('')
  const [stockFilter, setStockFilter] = useState<'ALL' | 'IN_STOCK' | 'OUT_OF_STOCK' | 'NEAR_EXPIRY'>('ALL')
  const [pageSize, setPageSize] = useState(25)
  const [page, setPage] = useState(1)
  const [error, setError] = useState('')
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null)
  const [categoriesTree, setCategoriesTree] = useState<any[]>([])

  useEffect(() => {
    api<any[]>('/admin/categories/tree')
      .then(res => setCategoriesTree(res))
      .catch(() => {})
  }, [])

  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedSearch(searchInput.trim())
      setPage(1)
    }, 300)
    return () => clearTimeout(handler)
  }, [searchInput])

  useEffect(() => {
    setLoading(true)
    const query = new URLSearchParams({ page: String(page), page_size: String(pageSize) })
    if (debouncedSearch) query.set('search', debouncedSearch)
    if (rxOtcStatus) query.set('rx_otc_status', rxOtcStatus)
    if (productType) query.set('product_type', productType)
    if (categorySlug) query.set('category_slug', categorySlug)
    if (publishStatus) query.set('publish_status', publishStatus)

    api<ProductPage>(`/products?${query}`)
      .then(res => {
        setData(res)
        setError('')
      })
      .catch(err => setError(err.message))
      .finally(() => setLoading(false))
  }, [page, pageSize, debouncedSearch, rxOtcStatus, productType, categorySlug, publishStatus])

  // Filter items in memory for stock filter
  const displayedItems = (data?.items || []).filter(item => {
    if (stockFilter === 'IN_STOCK') return (item.total_stock || 0) > 0
    if (stockFilter === 'OUT_OF_STOCK') return (item.total_stock || 0) <= 0
    if (stockFilter === 'NEAR_EXPIRY') return (item.near_expiry_count || 0) > 0
    return true
  })

  async function downloadCsv() {
    const response = await fetch(`${API_URL}/exports/products?format=csv&include_demo=false`, {
      headers: { Authorization: `Bearer ${tokenStore.get()}` },
    })
    if (!response.ok) return setError('Không thể xuất dữ liệu CSV')
    const url = URL.createObjectURL(await response.blob())
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = 'pharmatrust-products.csv'
    anchor.click()
    URL.revokeObjectURL(url)
  }

  async function downloadXlsx() {
    const response = await fetch(`${API_URL}/exports/products?format=xlsx&include_demo=false`, {
      headers: { Authorization: `Bearer ${tokenStore.get()}` },
    })
    if (!response.ok) return setError('Không thể xuất dữ liệu Excel')
    const url = URL.createObjectURL(await response.blob())
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = 'pharmatrust-products.xlsx'
    anchor.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="page" style={{ position: 'relative' }}>
      {/* 1. Page Heading */}
      <AdminPageHeader
        title="Hồ sơ thuốc & Duyệt bán"
        eyebrow="HỒ SƠ & BÁN HÀNG • Danh mục sản phẩm"
        subtitle="Bảng kê danh mục sản phẩm y tế, quản lý phân loại kê đơn (Rx/OTC), giá bán niêm yết và tồn kho thực tế đa chi nhánh."
        badge={data?.total !== undefined ? <span className="stat-card-badge">{data.total.toLocaleString('vi-VN')} thuốc</span> : undefined}
        actions={
          <div style={{ display: 'flex', gap: '8px' }}>
            <button className="admin-button button-secondary" onClick={downloadCsv} title="Xuất toàn bộ danh mục dạng CSV">
              <Download size={14} /> Xuất CSV
            </button>
            <button className="admin-button button-primary" onClick={downloadXlsx} title="Xuất báo cáo danh mục thuốc Excel">
              <FileSpreadsheet size={14} /> Xuất Excel (.xlsx)
            </button>
          </div>
        }
      />

      {/* 2. Standardized FilterBar */}
      <FilterBar
        searchValue={searchInput}
        onSearchChange={setSearchInput}
        searchPlaceholder="Tìm theo tên thuốc, số đăng ký, hoạt chất…"
        totalCount={data?.total}
        filteredCount={displayedItems.length}
        unitLabel="thuốc"
        onRefresh={() => {
          setLoading(true)
          const query = new URLSearchParams({ page: String(page), page_size: String(pageSize) })
          if (debouncedSearch) query.set('search', debouncedSearch)
          if (rxOtcStatus) query.set('rx_otc_status', rxOtcStatus)
          if (publishStatus) query.set('publish_status', publishStatus)
          api<ProductPage>(`/products?${query}`)
            .then(res => { setData(res); setError('') })
            .catch(err => setError(err.message))
            .finally(() => setLoading(false))
        }}
        isRefreshing={loading}
      >
        <select
          value={productType}
          onChange={e => {
            setProductType(e.target.value)
            setPage(1)
          }}
          style={{ minWidth: '150px' }}
        >
          <option value="">Tất cả loại sản phẩm</option>
          <option value="MEDICINE">Thuốc</option>
          <option value="SUPPLEMENT">Thực phẩm BVSK</option>
          <option value="COSMETIC">Mỹ phẩm</option>
          <option value="MEDICAL_DEVICE">Thiết bị y tế</option>
          <option value="MOTHER_BABY">Mẹ & Bé</option>
          <option value="PERSONAL_CARE">Chăm sóc cá nhân</option>
        </select>

        <select
          value={categorySlug}
          onChange={e => {
            setCategorySlug(e.target.value)
            setPage(1)
          }}
          style={{ minWidth: '160px' }}
        >
          <option value="">Tất cả danh mục</option>
          {categoriesTree.map((cat: any) => (
            <optgroup key={cat.dbId} label={cat.name}>
              <option value={cat.slug}>{cat.name} (Tất cả)</option>
              {(cat.subCategories || []).map((sub: any) => (
                <option key={sub.dbId} value={sub.slug}>-- {sub.name}</option>
              ))}
            </optgroup>
          ))}
        </select>

        <select
          value={rxOtcStatus}
          onChange={e => {
            setRxOtcStatus(e.target.value)
            setPage(1)
          }}
          style={{ minWidth: '150px' }}
        >
          <option value="">Tất cả phân loại (Rx/OTC)</option>
          <option value="OTC">Thuốc không kê đơn (OTC)</option>
          <option value="PRESCRIPTION">Thuốc kê đơn (Rx)</option>
        </select>

        <select
          value={publishStatus}
          onChange={e => {
            setPublishStatus(e.target.value)
            setPage(1)
          }}
          style={{ minWidth: '160px' }}
        >
          <option value="">Tất cả trạng thái bán</option>
          <option value="PUBLISHED">Đang mở bán</option>
          <option value="DRAFT">Bản nháp</option>
          <option value="REVIEW_REQUIRED">Chờ duyệt</option>
          <option value="BLOCKED">Tạm khóa</option>
        </select>

        <select
          value={stockFilter}
          onChange={e => setStockFilter(e.target.value as any)}
          style={{ minWidth: '150px' }}
        >
          <option value="ALL">Tất cả trạng thái kho</option>
          <option value="IN_STOCK">Còn hàng tồn kho</option>
          <option value="OUT_OF_STOCK">Hết hàng (Stock = 0)</option>
          <option value="NEAR_EXPIRY">Có lô cận hạn (&lt;90 ngày)</option>
        </select>

        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', color: '#64748b' }}>
          <span>Trang:</span>
          <select
            value={pageSize}
            onChange={e => {
              setPageSize(Number(e.target.value))
              setPage(1)
            }}
            style={{ width: '85px', padding: '6px 8px' }}
          >
            <option value="10">10 dòng</option>
            <option value="25">25 dòng</option>
            <option value="50">50 dòng</option>
          </select>
        </div>
      </FilterBar>

      {error && <div className="alert alert-error" style={{ marginBottom: '16px' }}>{error}</div>}

      {/* 3. Professional Tabular View */}
      <div
        className="table-container"
        style={{
          background: 'var(--color-surface, #ffffff)',
          borderRadius: '14px',
          border: '1px solid var(--color-border, #e2e8f0)',
          overflowX: 'auto',
          boxShadow: '0 1px 4px rgba(0,0,0,0.03)',
        }}
      >
        <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '13px' }}>
          <thead>
            <tr style={{ background: '#f8fafc', borderBottom: '2px solid #e2e8f0', color: '#475569', fontWeight: 600 }}>
              <th style={{ padding: '12px 16px', width: '60px' }}>ID</th>
              <th style={{ padding: '12px 16px', minWidth: '240px' }}>Tên Sản Phẩm</th>
              <th style={{ padding: '12px 14px', width: '130px' }}>Số Đăng Ký</th>
              <th style={{ padding: '12px 14px', minWidth: '160px' }}>Hoạt Chất Chính</th>
              <th style={{ padding: '12px 14px', width: '130px' }}>Dạng Bào Chế</th>
              <th style={{ padding: '12px 14px', width: '130px' }}>Phân Loại</th>
              <th style={{ padding: '12px 14px', width: '130px', textAlign: 'right' }}>Giá Niêm Yết</th>
              <th style={{ padding: '12px 14px', width: '140px', textAlign: 'center' }}>Tồn Kho Khả Dụng</th>
              <th style={{ padding: '12px 14px', width: '130px' }}>Trạng Thái</th>
              <th style={{ padding: '12px 16px', width: '90px', textAlign: 'center' }}>Thao Tác</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={10} style={{ padding: '36px', textAlign: 'center', color: '#64748b' }}>
                  <div style={{ display: 'inline-flex', alignItems: 'center', gap: '8px' }}>
                    <span className="spinner" /> Đang tải dữ liệu hồ sơ thuốc…
                  </div>
                </td>
              </tr>
            ) : displayedItems.length === 0 ? (
              <tr>
                <td colSpan={10} style={{ padding: '40px 16px', textAlign: 'center' }}>
                  <EmptyState title="Không tìm thấy sản phẩm phù hợp" description="Thử thay đổi từ khóa tìm kiếm hoặc điều chỉnh các bộ lọc phân loại/tồn kho." />
                </td>
              </tr>
            ) : (
              displayedItems.map((prod) => {
                const isRx = prod.rx_otc_status === 'PRESCRIPTION'
                const stock = prod.total_stock ?? 0
                const price = prod.price

                return (
                  <tr
                    key={prod.id}
                    style={{
                      borderBottom: '1px solid #edf2f7',
                      transition: 'background-color 0.15s',
                    }}
                    className="hover-row"
                  >
                    {/* ID */}
                    <td style={{ padding: '12px 16px', color: '#94a3b8', fontFamily: 'monospace' }}>
                      #{prod.id}
                    </td>

                    {/* Tên sản phẩm */}
                    <td style={{ padding: '12px 16px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                        {prod.image_url ? (
                          <img
                            src={prod.image_url}
                            alt={prod.canonical_name}
                            onError={(e) => { (e.target as HTMLElement).style.display = 'none' }}
                            style={{ width: '38px', height: '38px', objectFit: 'cover', borderRadius: '8px', border: '1px solid #e2e8f0', flexShrink: 0 }}
                          />
                        ) : (
                          <div
                            style={{
                              width: '38px',
                              height: '38px',
                              borderRadius: '8px',
                              background: '#f1f5f9',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              color: '#64748b',
                              flexShrink: 0,
                            }}
                          >
                            <Pill size={18} />
                          </div>
                        )}
                        <div>
                          <Link
                            to={`/products/${prod.id}`}
                            style={{ fontWeight: 600, color: '#0f172a', textDecoration: 'none' }}
                            className="hover-link"
                          >
                            {prod.canonical_name}
                          </Link>
                          {prod.product_type && (
                            <span style={{ marginLeft: '6px', fontSize: '10px', padding: '2px 6px', borderRadius: '4px', background: '#e0e7ff', color: '#4338ca', fontWeight: 600 }}>
                              {prod.product_type}
                            </span>
                          )}
                          <div style={{ fontSize: '11px', color: '#64748b', marginTop: '2px' }}>
                            {prod.manufacturer || 'Chưa rõ NSX'}
                          </div>
                        </div>
                      </div>
                    </td>

                    {/* Số đăng ký */}
                    <td style={{ padding: '12px 14px', fontFamily: 'monospace', fontWeight: 500, color: '#334155' }}>
                      {prod.registration_number || <span style={{ color: '#cbd5e1' }}>—</span>}
                    </td>

                    {/* Hoạt chất */}
                    <td style={{ padding: '12px 14px', color: '#475569' }}>
                      <span title={prod.active_ingredient || ''} style={{ display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
                        {prod.active_ingredient || <span style={{ color: '#cbd5e1' }}>—</span>}
                      </span>
                    </td>

                    {/* Dạng bào chế & Quy cách */}
                    <td style={{ padding: '12px 14px', color: '#475569' }}>
                      <div>{prod.dosage_form || 'Viên nén'}</div>
                      <div style={{ fontSize: '11px', color: '#94a3b8' }}>{prod.package_description || 'Hộp'}</div>
                    </td>

                    {/* Phân loại Rx / OTC */}
                    <td style={{ padding: '12px 14px' }}>
                      {isRx ? (
                        <span
                          style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '4px',
                            background: '#fee2e2',
                            color: '#991b1b',
                            padding: '3px 8px',
                            borderRadius: '6px',
                            fontSize: '11px',
                            fontWeight: 700,
                          }}
                        >
                          <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#ef4444' }} />
                          Thuốc kê đơn (Rx)
                        </span>
                      ) : (
                        <span
                          style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '4px',
                            background: '#dcfce7',
                            color: '#166534',
                            padding: '3px 8px',
                            borderRadius: '6px',
                            fontSize: '11px',
                            fontWeight: 600,
                          }}
                        >
                          <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#22c55e' }} />
                          Không kê đơn (OTC)
                        </span>
                      )}
                    </td>

                    {/* Giá bán */}
                    <td style={{ padding: '12px 14px', textAlign: 'right', fontWeight: 600, color: '#0f172a' }}>
                      {price != null && price > 0 ? (
                        <span>{price.toLocaleString('vi-VN')} đ</span>
                      ) : (
                        <span style={{ color: '#94a3b8', fontWeight: 400 }}>Chưa định giá</span>
                      )}
                    </td>

                    {/* Tồn kho */}
                    <td style={{ padding: '12px 14px', textAlign: 'center' }}>
                      {stock > 0 ? (
                        <div>
                          <span
                            style={{
                              display: 'inline-block',
                              padding: '2px 8px',
                              borderRadius: '12px',
                              background: '#eff6ff',
                              color: '#1d4ed8',
                              fontWeight: 700,
                              fontSize: '12px',
                            }}
                          >
                            {stock.toLocaleString()}
                          </span>
                          {(prod.near_expiry_count || 0) > 0 && (
                            <div style={{ fontSize: '10px', color: '#d97706', marginTop: '2px' }} title="Có lô cận hạn cần lưu ý xuất trước theo FEFO">
                              ⚠️ {prod.near_expiry_count} lô cận hạn
                            </div>
                          )}
                        </div>
                      ) : (
                        <span
                          style={{
                            display: 'inline-block',
                            padding: '2px 8px',
                            borderRadius: '12px',
                            background: '#f1f5f9',
                            color: '#64748b',
                            fontSize: '11px',
                          }}
                        >
                          Hết hàng (0)
                        </span>
                      )}
                    </td>

                    {/* Trạng thái */}
                    <td style={{ padding: '12px 14px' }}>
                      <StatusBadge value={prod.publish_status} />
                    </td>

                    {/* Thao tác */}
                    <td style={{ padding: '12px 16px', textAlign: 'center' }}>
                      <div style={{ display: 'inline-flex', gap: '6px' }}>
                        <button
                          className="icon-button"
                          title="Xem nhanh thông tin"
                          onClick={() => setSelectedProduct(prod)}
                          style={{ padding: '5px' }}
                        >
                          <Eye size={15} />
                        </button>
                        <Link
                          to={`/products/${prod.id}`}
                          className="icon-button"
                          title="Đến trang quản lý chi tiết"
                          style={{ padding: '5px' }}
                        >
                          <Boxes size={15} />
                        </Link>
                      </div>
                    </td>
                  </tr>
                )
              })
            )}
          </tbody>
        </table>
      </div>

      {/* 4. Pagination */}
      {data && (
        <div style={{ marginTop: '16px', borderRadius: '12px', overflow: 'hidden', border: '1px solid var(--color-border, #e2e8f0)' }}>
          <PaginationBar
            currentPage={page}
            totalPages={data.pages}
            pageSize={pageSize}
            totalItems={data.total}
            filteredCount={displayedItems.length !== (data.items || []).length ? displayedItems.length : undefined}
            itemName="thuốc"
            onPageChange={setPage}
            onPageSizeChange={setPageSize}
            pageSizeOptions={[15, 25, 50, 100]}
          />
        </div>
      )}

      {/* 5. Quick View Drawer / Modal */}
      {selectedProduct && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(15, 23, 42, 0.45)',
            backdropFilter: 'blur(3px)',
            zIndex: 100,
            display: 'flex',
            justifyContent: 'flex-end',
          }}
          onClick={() => setSelectedProduct(null)}
        >
          <div
            style={{
              width: '100%',
              maxWidth: '520px',
              height: '100%',
              background: '#ffffff',
              boxShadow: '-4px 0 24px rgba(0,0,0,0.15)',
              padding: '24px',
              overflowY: 'auto',
              display: 'flex',
              flexDirection: 'column',
              gap: '16px',
            }}
            onClick={e => e.stopPropagation()}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <div>
                <span className="overline">THÔNG TIN NHANH SẢN PHẨM</span>
                <h2 style={{ fontSize: '18px', fontWeight: 800, marginTop: '4px', color: '#0f172a' }}>
                  {selectedProduct.canonical_name}
                </h2>
              </div>
              <button
                className="icon-button"
                onClick={() => setSelectedProduct(null)}
                style={{ fontSize: '16px', padding: '6px 10px' }}
              >
                ✕
              </button>
            </div>

            {selectedProduct.image_url && (
              <img
                src={selectedProduct.image_url}
                alt={selectedProduct.canonical_name}
                onError={(e) => { (e.target as HTMLElement).style.display = 'none' }}
                style={{ width: '100%', height: '200px', objectFit: 'cover', borderRadius: '12px', border: '1px solid #e2e8f0' }}
              />
            )}

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', background: '#f8fafc', padding: '14px', borderRadius: '10px' }}>
              <div>
                <div style={{ fontSize: '11px', color: '#64748b' }}>Số Đăng Ký</div>
                <div style={{ fontWeight: 600, fontFamily: 'monospace' }}>{selectedProduct.registration_number || 'Chưa có'}</div>
              </div>
              <div>
                <div style={{ fontSize: '11px', color: '#64748b' }}>Phân Loại</div>
                <div style={{ fontWeight: 600, color: selectedProduct.rx_otc_status === 'PRESCRIPTION' ? '#ef4444' : '#16a34a' }}>
                  {selectedProduct.rx_otc_status === 'PRESCRIPTION' ? 'Kê đơn (Rx)' : 'Không kê đơn (OTC)'}
                </div>
              </div>
              <div>
                <div style={{ fontSize: '11px', color: '#64748b' }}>Giá Bán Niêm Yết</div>
                <div style={{ fontWeight: 700, color: '#0f172a' }}>
                  {selectedProduct.price ? `${selectedProduct.price.toLocaleString('vi-VN')} đ` : 'Chưa định giá'}
                </div>
              </div>
              <div>
                <div style={{ fontSize: '11px', color: '#64748b' }}>Tổng Tồn Kho Khả Dụng</div>
                <div style={{ fontWeight: 700, color: '#2563eb' }}>
                  {(selectedProduct.total_stock || 0).toLocaleString()} đơn vị
                </div>
              </div>
            </div>

            <div>
              <h4 style={{ fontSize: '13px', fontWeight: 700, color: '#334155', marginBottom: '6px' }}>Hoạt Chất & Nồng Độ</h4>
              <p style={{ fontSize: '13px', color: '#475569', lineHeight: 1.5 }}>{selectedProduct.active_ingredient || 'Xem tờ hướng dẫn sử dụng'}</p>
            </div>

            <div>
              <h4 style={{ fontSize: '13px', fontWeight: 700, color: '#334155', marginBottom: '6px' }}>Chỉ Định Điều Trị</h4>
              <p style={{ fontSize: '13px', color: '#475569', lineHeight: 1.5 }}>{selectedProduct.indications || 'Theo công bố nhà sản xuất'}</p>
            </div>

            <div style={{ marginTop: 'auto', paddingTop: '16px', borderTop: '1px solid #e2e8f0', display: 'flex', gap: '10px' }}>
              <Link
                to={`/products/${selectedProduct.id}`}
                className="primary-button"
                style={{ flex: 1, textAlign: 'center', justifyContent: 'center' }}
              >
                Mở Trang Quản Lý Chi Tiết
              </Link>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
