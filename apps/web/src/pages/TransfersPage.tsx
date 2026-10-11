import {
  ArrowLeftRight,
  Building2,
  Calendar,
  CheckCircle2,
  Eye,
  FileText,
  Package,
  Plus,
  Trash2,
  Truck,
  X,
} from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { EmptyState } from '../components/EmptyState'
import { PaginationBar } from '../components/PaginationBar'
import { api } from '../services/api'
import type { InventoryBatchItem, StockTransferItemType, WarehouseItem } from '../types'

export function TransfersPage() {
  const [transfers, setTransfers] = useState<StockTransferItemType[]>([])
  const [warehouses, setWarehouses] = useState<WarehouseItem[]>([])
  const [batches, setBatches] = useState<InventoryBatchItem[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  // Phân trang
  const [currentPage, setCurrentPage] = useState<number>(1)
  const [pageSize, setPageSize] = useState<number>(15)

  const totalPages = Math.max(1, Math.ceil(transfers.length / pageSize))
  const displayedTransfers = useMemo(() => {
    const start = (currentPage - 1) * pageSize
    return transfers.slice(start, start + pageSize)
  }, [transfers, currentPage, pageSize])

  // Create Modal State
  const [modalOpen, setModalOpen] = useState(false)
  const [fromWarehouseId, setFromWarehouseId] = useState<number>(1)
  const [toWarehouseId, setToWarehouseId] = useState<number>(2)
  const [transferNote, setTransferNote] = useState('')
  const [items, setItems] = useState<Array<{ batch_id: number; quantity: number }>>([])
  const [submitting, setSubmitting] = useState(false)
  const [formError, setFormError] = useState('')

  // View Details Modal State
  const [viewingTransfer, setViewingTransfer] = useState<StockTransferItemType | null>(null)

  function loadData() {
    setLoading(true)
    Promise.all([
      api<StockTransferItemType[]>('/inventory/transfers'),
      api<WarehouseItem[]>('/warehouses'),
      api<InventoryBatchItem[]>('/inventory/batches?status=ACTIVE'),
    ])
      .then(([tfs, whs, bts]) => {
        setTransfers(tfs)
        setWarehouses(whs)
        setBatches(bts)
        if (whs.length >= 2) {
          setFromWarehouseId(whs[0].id)
          setToWarehouseId(whs[1].id)
        }
        setError('')
      })
      .catch(err => setError(err.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    loadData()
  }, [])

  // Batches available at source warehouse
  const availableBatchesAtSource = batches.filter(b => {
    const stk = b.stocks.find(s => s.warehouse_id === fromWarehouseId)
    return stk && stk.quantity_available > 0
  })

  function openCreateModal() {
    const firstAvail = availableBatchesAtSource[0]
    setItems([
      {
        batch_id: firstAvail?.id || (batches[0]?.id || 1),
        quantity: 20,
      },
    ])
    setTransferNote('')
    setFormError('')
    setModalOpen(true)
  }

  function addItemLine() {
    const firstAvail = availableBatchesAtSource[0]
    setItems(prev => [
      ...prev,
      {
        batch_id: firstAvail?.id || (batches[0]?.id || 1),
        quantity: 10,
      },
    ])
  }

  function removeItemLine(idx: number) {
    setItems(prev => prev.filter((_, i) => i !== idx))
  }

  function updateItemLine(idx: number, field: string, val: any) {
    setItems(prev =>
      prev.map((item, i) => (i === idx ? { ...item, [field]: val } : item))
    )
  }

  async function handleCreateTransfer(e: React.FormEvent) {
    e.preventDefault()
    setFormError('')
    if (fromWarehouseId === toWarehouseId) {
      return setFormError('Kho xuất và kho tiếp nhận không được trùng nhau.')
    }
    if (items.length === 0) {
      return setFormError('Vui lòng chọn ít nhất một lô thuốc cần điều chuyển.')
    }

    setSubmitting(true)
    try {
      await api('/inventory/transfers', {
        method: 'POST',
        body: JSON.stringify({
          from_warehouse_id: fromWarehouseId,
          to_warehouse_id: toWarehouseId,
          note: transferNote.trim() || undefined,
          items: items.map(it => ({
            batch_id: Number(it.batch_id),
            quantity: Number(it.quantity),
          })),
        }),
      })
      setModalOpen(false)
      loadData()
    } catch (err: any) {
      setFormError(err.message || 'Lỗi khi lập lệnh điều chuyển')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="page">
      <div className="page-heading">
        <div>
          <span className="overline">ĐIỀU PHỐI NỘI BỘ & CÂN ĐỐI TỒN KHO</span>
          <h1>Lệnh Điều Chuyển Kho</h1>
          <p>
            Điều chuyển thuốc và thiết bị y tế giữa kho trung tâm và các kho chi nhánh miền, đảm bảo cân đối tồn kho theo nhu cầu thị trường.
          </p>
        </div>
        <div>
          <button className="primary-button" onClick={openCreateModal}>
            <Plus size={16} /> Lập Lệnh Điều Chuyển
          </button>
        </div>
      </div>

      {error && <div className="alert alert-error" style={{ marginBottom: '16px' }}>{error}</div>}

      {/* Transfers Table */}
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
              <th style={{ padding: '12px 16px' }}>Mã Lệnh</th>
              <th style={{ padding: '12px 14px' }}>Kho Xuất Hàng</th>
              <th style={{ padding: '12px 14px' }}>Kho Tiếp Nhận</th>
              <th style={{ padding: '12px 14px', textAlign: 'center' }}>Số Mặt Hàng</th>
              <th style={{ padding: '12px 14px' }}>Thời Gian</th>
              <th style={{ padding: '12px 14px' }}>Trạng Thái</th>
              <th style={{ padding: '12px 16px', textAlign: 'center' }}>Chi Tiết</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={7} style={{ padding: '36px', textAlign: 'center', color: '#64748b' }}>
                  Đang tải danh sách lệnh điều chuyển…
                </td>
              </tr>
            ) : transfers.length === 0 ? (
              <tr>
                <td colSpan={7} style={{ padding: '40px 16px', textAlign: 'center' }}>
                  <EmptyState title="Chưa có lệnh điều chuyển nào" description="Bấm nút Lập Lệnh Điều Chuyển để luân chuyển thuốc giữa các chi nhánh." />
                </td>
              </tr>
            ) : (
              displayedTransfers.map(tf => (
                <tr key={tf.id} style={{ borderBottom: '1px solid #edf2f7' }} className="hover-row">
                  <td style={{ padding: '12px 16px', fontWeight: 700, fontFamily: 'monospace', color: '#0f172a' }}>
                    {tf.transfer_code}
                  </td>
                  <td style={{ padding: '12px 14px', fontWeight: 600, color: '#dc2626' }}>
                    {tf.from_warehouse_name}
                  </td>
                  <td style={{ padding: '12px 14px', fontWeight: 600, color: '#16a34a' }}>
                    {tf.to_warehouse_name}
                  </td>
                  <td style={{ padding: '12px 14px', textAlign: 'center' }}>
                    <span style={{ background: '#f1f5f9', padding: '2px 8px', borderRadius: '6px', fontWeight: 700 }}>
                      {tf.items_count} lô
                    </span>
                  </td>
                  <td style={{ padding: '12px 14px', color: '#64748b' }}>
                    {tf.created_at?.slice(0, 16).replace('T', ' ')}
                  </td>
                  <td style={{ padding: '12px 14px' }}>
                    <span
                      style={{
                        padding: '3px 8px',
                        borderRadius: '6px',
                        fontSize: '11px',
                        fontWeight: 700,
                        background: tf.status === 'COMPLETED' ? '#dcfce7' : '#ffedd5',
                        color: tf.status === 'COMPLETED' ? '#166534' : '#9a3412',
                      }}
                    >
                      {tf.status === 'COMPLETED' ? 'Đã hoàn tất' : tf.status}
                    </span>
                  </td>
                  <td style={{ padding: '12px 16px', textAlign: 'center' }}>
                    <button
                      className="icon-button"
                      onClick={() => setViewingTransfer(tf)}
                      title="Xem chi tiết các lô điều chuyển"
                    >
                      <Eye size={15} />
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
        {!loading && transfers.length > 0 && (
          <PaginationBar
            currentPage={currentPage}
            totalPages={totalPages}
            pageSize={pageSize}
            totalItems={transfers.length}
            itemName="lệnh điều chuyển"
            onPageChange={setCurrentPage}
            onPageSizeChange={setPageSize}
            pageSizeOptions={[10, 15, 25, 50]}
          />
        )}
      </div>

      {/* Modal Lập Lệnh Điều Chuyển */}
      {modalOpen && (
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
          onClick={() => setModalOpen(false)}
        >
          <div
            style={{
              background: '#ffffff',
              borderRadius: '16px',
              maxWidth: '680px',
              width: '100%',
              maxHeight: '90vh',
              overflowY: 'auto',
              padding: '24px',
              boxShadow: '0 10px 25px rgba(0,0,0,0.15)',
            }}
            onClick={e => e.stopPropagation()}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <div>
                <span className="overline">ĐIỀU CHUYỂN LIÊN KHO</span>
                <h2 style={{ fontSize: '18px', fontWeight: 800, margin: '2px 0 0 0', color: '#0f172a' }}>
                  Lập Lệnh Điều Chuyển Thuốc Giữa Các Chi Nhánh
                </h2>
              </div>
              <button className="icon-button" onClick={() => setModalOpen(false)}>
                <X size={18} />
              </button>
            </div>

            {formError && <div className="alert alert-error" style={{ marginBottom: '12px' }}>{formError}</div>}

            <form onSubmit={handleCreateTransfer} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                <div>
                  <label style={{ fontSize: '12px', fontWeight: 600, color: '#334155', display: 'block', marginBottom: '4px' }}>
                    Kho Xuất Hàng (Source) *
                  </label>
                  <select
                    value={fromWarehouseId}
                    onChange={e => setFromWarehouseId(Number(e.target.value))}
                    style={{ width: '100%', padding: '8px 12px', borderRadius: '8px', border: '1px solid #cbd5e1' }}
                    required
                  >
                    {warehouses.map(w => (
                      <option key={w.id} value={w.id}>
                        {w.name} ({w.code})
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label style={{ fontSize: '12px', fontWeight: 600, color: '#334155', display: 'block', marginBottom: '4px' }}>
                    Kho Tiếp Nhận (Destination) *
                  </label>
                  <select
                    value={toWarehouseId}
                    onChange={e => setToWarehouseId(Number(e.target.value))}
                    style={{ width: '100%', padding: '8px 12px', borderRadius: '8px', border: '1px solid #cbd5e1' }}
                    required
                  >
                    {warehouses.map(w => (
                      <option key={w.id} value={w.id}>
                        {w.name} ({w.code})
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div>
                <label style={{ fontSize: '12px', fontWeight: 600, color: '#334155', display: 'block', marginBottom: '4px' }}>
                  Lý do điều chuyển / Ghi chú vận chuyển
                </label>
                <input
                  placeholder="Ví dụ: Bổ sung lượng hàng thiếu cho đợt cao điểm cúm mùa..."
                  value={transferNote}
                  onChange={e => setTransferNote(e.target.value)}
                  style={{ width: '100%', padding: '8px 12px', borderRadius: '8px', border: '1px solid #cbd5e1' }}
                />
              </div>

              {/* Items List */}
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                  <label style={{ fontSize: '13px', fontWeight: 700, color: '#0f172a' }}>
                    Danh sách Lô Thuốc Cần Điều Chuyển ({items.length})
                  </label>
                  <button
                    type="button"
                    className="secondary-button"
                    onClick={addItemLine}
                    style={{ padding: '4px 10px', fontSize: '12px' }}
                  >
                    <Plus size={14} /> Thêm lô hàng
                  </button>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {items.map((it, idx) => {
                    const selectedB = batches.find(b => b.id === it.batch_id)
                    const srcStock = selectedB?.stocks.find(s => s.warehouse_id === fromWarehouseId)
                    const avail = srcStock?.quantity_available || 0

                    return (
                      <div
                        key={idx}
                        style={{
                          display: 'grid',
                          gridTemplateColumns: '3fr 1.2fr 1fr 36px',
                          gap: '8px',
                          alignItems: 'center',
                          background: '#f8fafc',
                          padding: '10px',
                          borderRadius: '8px',
                          border: '1px solid #e2e8f0',
                        }}
                      >
                        {/* Batch Selector */}
                        <div>
                          <div style={{ fontSize: '11px', color: '#64748b' }}>Chọn Lô & Thuốc</div>
                          <select
                            value={it.batch_id}
                            onChange={e => updateItemLine(idx, 'batch_id', Number(e.target.value))}
                            style={{ width: '100%', padding: '6px', fontSize: '12px', borderRadius: '6px', border: '1px solid #cbd5e1' }}
                          >
                            {batches.map(b => (
                              <option key={b.id} value={b.id}>
                                {b.batch_number} - {b.product_name} (HSD: {b.expiry_date})
                              </option>
                            ))}
                          </select>
                        </div>

                        {/* Available */}
                        <div>
                          <div style={{ fontSize: '11px', color: '#64748b' }}>Khả dụng tại kho xuất</div>
                          <div style={{ fontSize: '13px', fontWeight: 700, color: avail > 0 ? '#16a34a' : '#ef4444', marginTop: '4px' }}>
                            {avail.toLocaleString()}
                          </div>
                        </div>

                        {/* Quantity */}
                        <div>
                          <div style={{ fontSize: '11px', color: '#64748b' }}>Số lượng chuyển</div>
                          <input
                            type="number"
                            min="1"
                            max={avail || 9999}
                            value={it.quantity}
                            onChange={e => updateItemLine(idx, 'quantity', Number(e.target.value))}
                            style={{ width: '100%', padding: '6px', fontSize: '12px', borderRadius: '6px', border: '1px solid #cbd5e1' }}
                            required
                          />
                        </div>

                        {/* Remove */}
                        <div style={{ paddingTop: '16px' }}>
                          <button
                            type="button"
                            className="icon-button"
                            onClick={() => removeItemLine(idx)}
                            style={{ color: '#ef4444' }}
                          >
                            <Trash2 size={15} />
                          </button>
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '16px' }}>
                <button
                  type="button"
                  className="secondary-button"
                  onClick={() => setModalOpen(false)}
                >
                  Hủy bỏ
                </button>
                <button
                  type="submit"
                  className="primary-button"
                  disabled={submitting}
                >
                  {submitting ? 'Đang thực hiện…' : 'Xác Nhận Xuất & Nhập Điều Chuyển'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal Xem Chi Tiết Lệnh Điều Chuyển */}
      {viewingTransfer && (
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
          onClick={() => setViewingTransfer(null)}
        >
          <div
            style={{
              background: '#ffffff',
              borderRadius: '16px',
              maxWidth: '580px',
              width: '100%',
              padding: '24px',
              boxShadow: '0 10px 25px rgba(0,0,0,0.15)',
            }}
            onClick={e => e.stopPropagation()}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <div>
                <span className="overline">LỆNH ĐIỀU CHUYỂN NỘI BỘ</span>
                <h2 style={{ fontSize: '18px', fontWeight: 800, margin: 0, color: '#0f172a' }}>
                  {viewingTransfer.transfer_code}
                </h2>
              </div>
              <button className="icon-button" onClick={() => setViewingTransfer(null)}>
                <X size={18} />
              </button>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', background: '#f8fafc', padding: '12px', borderRadius: '10px', marginBottom: '16px' }}>
              <div>Kho xuất: <strong style={{ color: '#dc2626' }}>{viewingTransfer.from_warehouse_name}</strong></div>
              <div>Kho nhập: <strong style={{ color: '#16a34a' }}>{viewingTransfer.to_warehouse_name}</strong></div>
              <div>Trạng thái: <strong>{viewingTransfer.status}</strong></div>
              <div>Thời gian: <strong>{viewingTransfer.created_at?.slice(0, 16)}</strong></div>
            </div>

            {viewingTransfer.note && (
              <div style={{ fontSize: '12px', color: '#475569', marginBottom: '12px', fontStyle: 'italic' }}>
                Ghi chú: {viewingTransfer.note}
              </div>
            )}

            <div style={{ fontSize: '13px', fontWeight: 700, marginBottom: '8px' }}>Các lô thuốc đã điều chuyển:</div>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }}>
              <thead>
                <tr style={{ background: '#f1f5f9', borderBottom: '1px solid #cbd5e1' }}>
                  <th style={{ padding: '8px' }}>Số Lô</th>
                  <th style={{ padding: '8px' }}>Mã SKU</th>
                  <th style={{ padding: '8px', textAlign: 'right' }}>Số Lượng Xuất</th>
                  <th style={{ padding: '8px', textAlign: 'right' }}>Đã Nhập Kho Đến</th>
                </tr>
              </thead>
              <tbody>
                {viewingTransfer.items.map(it => (
                  <tr key={it.id} style={{ borderBottom: '1px solid #edf2f7' }}>
                    <td style={{ padding: '8px', fontFamily: 'monospace', fontWeight: 700 }}>{it.batch_number}</td>
                    <td style={{ padding: '8px' }}>{it.sku_code}</td>
                    <td style={{ padding: '8px', textAlign: 'right', fontWeight: 600 }}>{it.quantity}</td>
                    <td style={{ padding: '8px', textAlign: 'right', fontWeight: 700, color: '#16a34a' }}>{it.received_quantity}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
