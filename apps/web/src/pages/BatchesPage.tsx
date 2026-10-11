import {
  AlertCircle,
  AlertTriangle,
  Building2,
  Calendar,
  CheckCircle2,
  Clock,
  Eye,
  FileText,
  Filter,
  History,
  Layers,
  MapPin,
  Package,
  RefreshCw,
  Search,
  ShieldAlert,
  ShieldCheck,
  X,
} from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { AdminPageHeader } from '../components/AdminPageHeader'
import { FilterBar } from '../components/FilterBar'
import { PaginationBar } from '../components/PaginationBar'
import { StatusBadge } from '../components/StatusBadge'
import { EmptyState } from '../components/EmptyState'
import { api } from '../services/api'
import type { InventoryBatchItem, StockMovementItem, WarehouseItem } from '../types'

export function BatchesPage() {
  const [batches, setBatches] = useState<InventoryBatchItem[]>([])
  const [warehouses, setWarehouses] = useState<WarehouseItem[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [searchInput, setSearchInput] = useState('')
  const [warehouseFilter, setWarehouseFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [nearExpiryOnly, setNearExpiryOnly] = useState(false)

  // Phân trang danh sách lô & hạn dùng
  const [currentPage, setCurrentPage] = useState<number>(1)
  const [pageSize, setPageSize] = useState<number>(15)

  const totalPages = Math.max(1, Math.ceil(batches.length / pageSize))
  const displayedBatches = useMemo(() => {
    const start = (currentPage - 1) * pageSize
    return batches.slice(start, start + pageSize)
  }, [batches, currentPage, pageSize])

  // Status Modal State
  const [statusModalOpen, setStatusModalOpen] = useState(false)
  const [selectedBatch, setSelectedBatch] = useState<InventoryBatchItem | null>(null)
  const [newStatus, setNewStatus] = useState<string>('QUARANTINED')
  const [statusReason, setStatusReason] = useState('')
  const [statusSubmitting, setStatusSubmitting] = useState(false)

  // Card Movements / The Kho Drawer State
  const [movementsDrawerOpen, setMovementsDrawerOpen] = useState(false)
  const [batchMovements, setBatchMovements] = useState<StockMovementItem[]>([])
  const [movementsLoading, setMovementsLoading] = useState(false)

  function loadBatches() {
    setLoading(true)
    const query = new URLSearchParams()
    if (warehouseFilter) query.set('warehouse_id', warehouseFilter)
    if (statusFilter) query.set('status', statusFilter)
    if (nearExpiryOnly) query.set('near_expiry', 'true')
    if (searchInput.trim()) query.set('search', searchInput.trim())

    api<InventoryBatchItem[]>(`/inventory/batches?${query}`)
      .then(res => {
        setBatches(res)
        setError('')
      })
      .catch(err => setError(err.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    api<WarehouseItem[]>('/warehouses').then(setWarehouses).catch(() => {})
  }, [])

  useEffect(() => {
    setCurrentPage(1)
    loadBatches()
  }, [warehouseFilter, statusFilter, nearExpiryOnly])

  function handleSearchSubmit(e: React.FormEvent) {
    e.preventDefault()
    loadBatches()
  }

  function openStatusModal(batch: InventoryBatchItem) {
    setSelectedBatch(batch)
    setNewStatus(batch.status === 'ACTIVE' ? 'QUARANTINED' : 'ACTIVE')
    setStatusReason('')
    setStatusModalOpen(true)
  }

  async function handleUpdateStatus(e: React.FormEvent) {
    e.preventDefault()
    if (!selectedBatch) return
    setStatusSubmitting(true)
    try {
      await api(`/inventory/batches/${selectedBatch.id}/status`, {
        method: 'PATCH',
        body: JSON.stringify({
          status: newStatus,
          reason: statusReason.trim() || undefined,
        }),
      })
      setStatusModalOpen(false)
      loadBatches()
    } catch (err: any) {
      alert(err.message || 'Lỗi khi cập nhật trạng thái lô')
    } finally {
      setStatusSubmitting(false)
    }
  }

  function openMovementsDrawer(batch: InventoryBatchItem) {
    setSelectedBatch(batch)
    setMovementsDrawerOpen(true)
    setMovementsLoading(true)
    api<StockMovementItem[]>(`/inventory/movements?batch_id=${batch.id}`)
      .then(res => setBatchMovements(res))
      .catch(() => setBatchMovements([]))
      .finally(() => setMovementsLoading(false))
  }

  return (
    <div className="page">
      {/* 1. Page Header */}
      <AdminPageHeader
        title="Lô thuốc & Hạn dùng"
        eyebrow="KHO VẬN & LÔ HẠN DÙNG • Quản trị chuẩn FEFO"
        subtitle="Theo dõi chi tiết số lô sản xuất, hạn sử dụng, cảnh báo cận hạn theo mã màu trực quan và thực thi nguyên tắc First-Expired First-Out."
        badge={batches.length > 0 ? <span className="stat-card-badge">{batches.length} lô</span> : undefined}
        actions={
          <button type="button" onClick={loadBatches} disabled={loading} className="admin-button button-secondary">
            <RefreshCw size={14} className={loading ? 'spin' : ''} />
            <span>Làm mới danh sách</span>
          </button>
        }
      />

      {/* 2. Standardized FilterBar */}
      <FilterBar
        searchValue={searchInput}
        onSearchChange={setSearchInput}
        searchPlaceholder="Tìm theo số lô hoặc tên sản phẩm…"
        totalCount={batches.length}
        unitLabel="lô thuốc"
        onRefresh={loadBatches}
        isRefreshing={loading}
      >
        <select
          value={warehouseFilter}
          onChange={e => setWarehouseFilter(e.target.value)}
          style={{ minWidth: '170px' }}
        >
          <option value="">Tất cả kho chi nhánh</option>
          {warehouses.map(w => (
            <option key={w.id} value={String(w.id)}>
              {w.name}
            </option>
          ))}
        </select>

        <select
          value={statusFilter}
          onChange={e => setStatusFilter(e.target.value)}
          style={{ minWidth: '150px' }}
        >
          <option value="">Tất cả trạng thái lô</option>
          <option value="ACTIVE">Hoạt động (ACTIVE)</option>
          <option value="QUARANTINED">Đang cách ly (QUARANTINED)</option>
          <option value="RECALLED">Thu hồi khẩn cấp (RECALLED)</option>
          <option value="EXPIRED">Đã hết hạn (EXPIRED)</option>
        </select>

        <label
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            fontSize: '12px',
            fontWeight: 650,
            color: nearExpiryOnly ? '#b45309' : '#475569',
            background: nearExpiryOnly ? '#fef3c7' : '#f8fafc',
            border: `1px solid ${nearExpiryOnly ? '#fcd34d' : '#e2e8f0'}`,
            padding: '6px 10px',
            borderRadius: '7px',
            cursor: 'pointer',
          }}
        >
          <input
            type="checkbox"
            checked={nearExpiryOnly}
            onChange={e => setNearExpiryOnly(e.target.checked)}
          />
          ⚠️ Chỉ xem lô cận hạn (&lt;90 ngày)
        </label>
      </FilterBar>

      {error && <div className="alert alert-error" style={{ marginBottom: '16px' }}>{error}</div>}

      {/* 3. Batches Table */}
      <div
        className="table-container"
        style={{
          background: '#ffffff',
          borderRadius: '14px',
          border: '1px solid #e2e8f0',
          overflowX: 'auto',
          boxShadow: '0 1px 4px rgba(0,0,0,0.03)',
        }}
      >
        <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '13px' }}>
          <thead>
            <tr style={{ background: '#f8fafc', borderBottom: '2px solid #e2e8f0', color: '#475569', fontWeight: 600 }}>
              <th style={{ padding: '12px 14px', width: '130px' }}>Số Lô (Batch)</th>
              <th style={{ padding: '12px 14px', minWidth: '220px' }}>Tên Thuốc & Quy Cách</th>
              <th style={{ padding: '12px 12px', width: '110px' }}>Ngày Sản Xuất</th>
              <th style={{ padding: '12px 14px', width: '160px' }}>Hạn Dùng & Cảnh Báo</th>
              <th style={{ padding: '12px 14px', minWidth: '180px' }}>Phân Bổ Tồn Kho Theo Chi Nhánh</th>
              <th style={{ padding: '12px 12px', width: '110px', textAlign: 'center' }}>Khả Dụng</th>
              <th style={{ padding: '12px 12px', width: '120px' }}>Trạng Thái</th>
              <th style={{ padding: '12px 14px', width: '110px', textAlign: 'center' }}>Thao Tác</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={8} style={{ padding: '36px', textAlign: 'center', color: '#64748b' }}>
                  <div style={{ display: 'inline-flex', alignItems: 'center', gap: '8px' }}>
                    <span className="spinner" /> Đang kiểm tra dữ liệu lô và hạn dùng…
                  </div>
                </td>
              </tr>
            ) : batches.length === 0 ? (
              <tr>
                <td colSpan={8} style={{ padding: '40px 16px', textAlign: 'center' }}>
                  <EmptyState title="Không có lô thuốc nào phù hợp" description="Thử thay đổi bộ lọc kho hoặc trạng thái lô." />
                </td>
              </tr>
            ) : (
              displayedBatches.map(batch => {
                // Color highlight based on risk level
                let riskBadgeStyle = { background: '#ecfdf5', color: '#065f46', border: '1px solid #a7f3d0' }
                if (batch.risk_level === 'WARNING') {
                  riskBadgeStyle = { background: '#fffbeb', color: '#92400e', border: '1px solid #fde68a' }
                } else if (batch.risk_level === 'CRITICAL') {
                  riskBadgeStyle = { background: '#fef2f2', color: '#991b1b', border: '1px solid #fecaca' }
                }

                return (
                  <tr key={batch.id} style={{ borderBottom: '1px solid #edf2f7' }} className="hover-row">
                    {/* Số Lô */}
                    <td style={{ padding: '12px 14px' }}>
                      <span
                        style={{
                          fontWeight: 700,
                          fontFamily: 'monospace',
                          color: '#0f172a',
                          background: '#f1f5f9',
                          padding: '3px 8px',
                          borderRadius: '6px',
                        }}
                      >
                        {batch.batch_number}
                      </span>
                      <div style={{ fontSize: '11px', color: '#64748b', marginTop: '3px' }}>
                        NSX: {batch.supplier_name}
                      </div>
                    </td>

                    {/* Tên Thuốc & Quy cách */}
                    <td style={{ padding: '12px 14px' }}>
                      <div style={{ fontWeight: 600, color: '#0f172a' }}>{batch.product_name}</div>
                      <div style={{ fontSize: '11px', color: '#64748b', marginTop: '2px', display: 'flex', gap: '6px' }}>
                        <span>SKU: {batch.sku_code}</span>
                        <span>•</span>
                        <span>ĐVT: {batch.uom}</span>
                      </div>
                    </td>

                    {/* Ngày sản xuất */}
                    <td style={{ padding: '12px 12px', color: '#475569' }}>
                      {batch.manufacture_date || '—'}
                    </td>

                    {/* Hạn dùng & Cảnh báo FEFO */}
                    <td style={{ padding: '12px 14px' }}>
                      <div style={{ fontWeight: 600, color: '#0f172a' }}>{batch.expiry_date}</div>
                      <span
                        style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '4px',
                          fontSize: '11px',
                          fontWeight: 700,
                          padding: '2px 7px',
                          borderRadius: '6px',
                          marginTop: '4px',
                          ...riskBadgeStyle,
                        }}
                      >
                        <Clock size={11} />
                        {batch.days_remaining > 0
                          ? `Còn ${batch.days_remaining} ngày`
                          : `Quá hạn ${Math.abs(batch.days_remaining)} ngày`}
                      </span>
                    </td>

                    {/* Phân bổ theo kho */}
                    <td style={{ padding: '12px 14px' }}>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                        {batch.stocks.map(stk => (
                          <div
                            key={stk.warehouse_id}
                            style={{
                              display: 'flex',
                              justifyContent: 'space-between',
                              fontSize: '11px',
                              background: '#f8fafc',
                              padding: '3px 8px',
                              borderRadius: '4px',
                            }}
                          >
                            <span style={{ fontWeight: 600, color: '#334155' }}>
                              {stk.warehouse_code || stk.warehouse_name}:
                            </span>
                            <span style={{ color: '#0f172a' }}>
                              Tồn: <strong>{stk.quantity_on_hand}</strong> | Bán: <strong style={{ color: '#16a34a' }}>{stk.quantity_available}</strong>
                            </span>
                          </div>
                        ))}
                      </div>
                    </td>

                    {/* Khả dụng */}
                    <td style={{ padding: '12px 12px', textAlign: 'center' }}>
                      <span
                        style={{
                          fontWeight: 800,
                          fontSize: '14px',
                          color: batch.total_available > 0 ? '#16a34a' : '#94a3b8',
                        }}
                      >
                        {batch.total_available.toLocaleString()}
                      </span>
                    </td>

                    {/* Trạng thái Lô */}
                    <td style={{ padding: '12px 12px' }}>
                      <span
                        style={{
                          display: 'inline-block',
                          fontSize: '11px',
                          fontWeight: 700,
                          padding: '3px 8px',
                          borderRadius: '6px',
                          background:
                            batch.status === 'ACTIVE'
                              ? '#dcfce7'
                              : batch.status === 'QUARANTINED'
                              ? '#ffedd5'
                              : '#fee2e2',
                          color:
                            batch.status === 'ACTIVE'
                              ? '#166534'
                              : batch.status === 'QUARANTINED'
                              ? '#9a3412'
                              : '#991b1b',
                        }}
                      >
                        {batch.status === 'ACTIVE'
                          ? 'Đang mở bán'
                          : batch.status === 'QUARANTINED'
                          ? 'Đang cách ly'
                          : batch.status === 'RECALLED'
                          ? 'Thu hồi'
                          : 'Hết hạn'}
                      </span>
                    </td>

                    {/* Thao tác */}
                    <td style={{ padding: '12px 14px', textAlign: 'center' }}>
                      <div style={{ display: 'inline-flex', gap: '6px' }}>
                        <button
                          className="icon-button"
                          title="Xem lịch sử Thẻ Kho"
                          onClick={() => openMovementsDrawer(batch)}
                          style={{ padding: '5px' }}
                        >
                          <History size={15} />
                        </button>
                        <button
                          className="icon-button"
                          title="Chuyển trạng thái lô (Cách ly/Mở bán)"
                          onClick={() => openStatusModal(batch)}
                          style={{ padding: '5px' }}
                        >
                          <ShieldAlert size={15} />
                        </button>
                      </div>
                    </td>
                  </tr>
                )
              })
            )}
          </tbody>
        </table>

        {/* Phân trang danh sách lô & hạn dùng */}
        {!loading && batches.length > 0 && (
          <PaginationBar
            currentPage={currentPage}
            totalPages={totalPages}
            pageSize={pageSize}
            totalItems={batches.length}
            itemName="lô thuốc"
            onPageChange={setCurrentPage}
            onPageSizeChange={setPageSize}
            pageSizeOptions={[10, 15, 25, 50]}
          />
        )}
      </div>

      {/* Modal Chuyển Trạng Thái Lô */}
      {statusModalOpen && selectedBatch && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(15, 23, 42, 0.5)',
            backdropFilter: 'blur(3px)',
            zIndex: 100,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '16px',
          }}
          onClick={() => setStatusModalOpen(false)}
        >
          <div
            style={{
              background: '#ffffff',
              borderRadius: '16px',
              maxWidth: '480px',
              width: '100%',
              padding: '24px',
              boxShadow: '0 10px 25px rgba(0,0,0,0.15)',
            }}
            onClick={e => e.stopPropagation()}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <h2 style={{ fontSize: '17px', fontWeight: 800, margin: 0, color: '#0f172a' }}>
                Kiểm Soát Trạng Thái Lô: {selectedBatch.batch_number}
              </h2>
              <button className="icon-button" onClick={() => setStatusModalOpen(false)}>
                <X size={18} />
              </button>
            </div>

            <p style={{ fontSize: '13px', color: '#475569', marginBottom: '16px' }}>
              Sản phẩm: <strong>{selectedBatch.product_name}</strong>. Khi chuyển sang trạng thái <em>Cách ly (QUARANTINED)</em> hoặc <em>Thu hồi (RECALLED)</em>, toàn bộ số lượng khả dụng sẽ lập tức bị khóa để chống bán trực tuyến.
            </p>

            <form onSubmit={handleUpdateStatus} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div>
                <label style={{ fontSize: '12px', fontWeight: 600, color: '#334155', display: 'block', marginBottom: '4px' }}>
                  Trạng thái lô mới *
                </label>
                <select
                  value={newStatus}
                  onChange={e => setNewStatus(e.target.value)}
                  style={{ width: '100%', padding: '8px 12px', borderRadius: '8px', border: '1px solid #cbd5e1' }}
                  required
                >
                  <option value="ACTIVE">Hoạt động (ACTIVE) - Cho phép xuất bán</option>
                  <option value="QUARANTINED">Cách ly (QUARANTINED) - Nghi vấn chất lượng/Cận hạn</option>
                  <option value="RECALLED">Thu hồi (RECALLED) - Quyết định Cục Quản Lý Dược</option>
                  <option value="EXPIRED">Hết hạn sử dụng (EXPIRED) - Hủy bỏ</option>
                </select>
              </div>

              <div>
                <label style={{ fontSize: '12px', fontWeight: 600, color: '#334155', display: 'block', marginBottom: '4px' }}>
                  Lý do điều chỉnh / Ghi chú kiểm dịch
                </label>
                <textarea
                  rows={3}
                  placeholder="Ví dụ: Theo công văn thu hồi số... hoặc phát hiện bao bì móp méo..."
                  value={statusReason}
                  onChange={e => setStatusReason(e.target.value)}
                  style={{ width: '100%', padding: '8px 12px', borderRadius: '8px', border: '1px solid #cbd5e1' }}
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '12px' }}>
                <button
                  type="button"
                  className="secondary-button"
                  onClick={() => setStatusModalOpen(false)}
                >
                  Hủy bỏ
                </button>
                <button
                  type="submit"
                  className="primary-button"
                  disabled={statusSubmitting}
                >
                  {statusSubmitting ? 'Đang cập nhật…' : 'Xác Nhận Thay Đổi'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Drawer Thẻ Kho (Stock Movements) */}
      {movementsDrawerOpen && selectedBatch && (
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
          onClick={() => setMovementsDrawerOpen(false)}
        >
          <div
            style={{
              width: '100%',
              maxWidth: '560px',
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
                <span className="overline">LỊCH SỬ THẺ KHO (STOCK MOVEMENTS)</span>
                <h2 style={{ fontSize: '18px', fontWeight: 800, color: '#0f172a', margin: '4px 0' }}>
                  Lô: {selectedBatch.batch_number}
                </h2>
                <div style={{ fontSize: '12px', color: '#64748b' }}>
                  {selectedBatch.product_name}
                </div>
              </div>
              <button className="icon-button" onClick={() => setMovementsDrawerOpen(false)}>
                ✕
              </button>
            </div>

            {movementsLoading ? (
              <div style={{ textAlign: 'center', padding: '36px', color: '#64748b' }}>
                Đang tải thẻ kho…
              </div>
            ) : batchMovements.length === 0 ? (
              <EmptyState title="Chưa có phát sinh biến động" description="Lô này chưa có phát sinh giao dịch xuất/nhập/điều chuyển." />
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                {batchMovements.map(m => (
                  <div
                    key={m.id}
                    style={{
                      border: '1px solid #e2e8f0',
                      borderRadius: '10px',
                      padding: '12px',
                      background: '#f8fafc',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                      <span
                        style={{
                          fontWeight: 700,
                          fontSize: '11px',
                          padding: '2px 6px',
                          borderRadius: '4px',
                          background: m.quantity > 0 ? '#dcfce7' : '#fee2e2',
                          color: m.quantity > 0 ? '#166534' : '#991b1b',
                        }}
                      >
                        {m.movement_type}
                      </span>
                      <span style={{ fontSize: '11px', color: '#64748b' }}>{m.created_at?.slice(0, 19)}</span>
                    </div>

                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                      <div style={{ fontSize: '12px', color: '#334155' }}>
                        Kho: <strong>{m.warehouse_name}</strong>
                      </div>
                      <div style={{ fontSize: '14px', fontWeight: 800, color: m.quantity > 0 ? '#16a34a' : '#dc2626' }}>
                        {m.quantity > 0 ? `+${m.quantity}` : m.quantity}
                      </div>
                    </div>

                    {m.note && (
                      <div style={{ fontSize: '11px', color: '#64748b', marginTop: '6px', fontStyle: 'italic' }}>
                        {m.note}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
