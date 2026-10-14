import {
  ArrowDownToLine,
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
import { getTodayDateStringVN } from '../utils/dateUtils'
import type { Product, StockReceiptItemType, SupplierItem, WarehouseItem } from '../types'

export function ReceiptsPage() {
  const [receipts, setReceipts] = useState<StockReceiptItemType[]>([])
  const [warehouses, setWarehouses] = useState<WarehouseItem[]>([])
  const [suppliers, setSuppliers] = useState<SupplierItem[]>([])
  const [products, setProducts] = useState<Product[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  // Phân trang danh sách phiếu nhập
  const [currentPage, setCurrentPage] = useState<number>(1)
  const [pageSize, setPageSize] = useState<number>(15)

  const totalPages = Math.max(1, Math.ceil(receipts.length / pageSize))
  const displayedReceipts = useMemo(() => {
    const start = (currentPage - 1) * pageSize
    return receipts.slice(start, start + pageSize)
  }, [receipts, currentPage, pageSize])

  // Create Modal State
  const [modalOpen, setModalOpen] = useState(false)
  const [selectedWarehouseId, setSelectedWarehouseId] = useState<number>(1)
  const [selectedSupplierId, setSelectedSupplierId] = useState<number>(1)
  const [receiptNote, setReceiptNote] = useState('')
  const [items, setItems] = useState<Array<{
    sku_id: number
    batch_number: string
    manufacture_date: string
    expiry_date: string
    quantity: number
    purchase_unit_price: number
  }>>([])
  const [submitting, setSubmitting] = useState(false)
  const [formError, setFormError] = useState('')

  // View Details Modal State
  const [viewingReceipt, setViewingReceipt] = useState<StockReceiptItemType | null>(null)

  function loadData() {
    setLoading(true)
    Promise.all([
      api<StockReceiptItemType[]>('/inventory/receipts'),
      api<WarehouseItem[]>('/warehouses'),
      api<SupplierItem[]>('/inventory/suppliers'),
      api<{ items: Product[] }>('/products?page_size=100'),
    ])
      .then(([recs, whs, sups, prods]) => {
        setReceipts(recs)
        setWarehouses(whs)
        setSuppliers(sups)
        setProducts(prods.items)
        if (whs.length > 0) setSelectedWarehouseId(whs[0].id)
        if (sups.length > 0) setSelectedSupplierId(sups[0].id)
        setError('')
      })
      .catch(err => setError(err.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    loadData()
  }, [])

  function openCreateModal() {
    const todayStr = getTodayDateStringVN()
    const expDate = new Date()
    expDate.setFullYear(expDate.getFullYear() + 2)
    const expStr = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Ho_Chi_Minh', year: 'numeric', month: '2-digit', day: '2-digit' }).format(expDate)

    setItems([
      {
        sku_id: products[0]?.id || 1,
        batch_number: `LOT-${Date.now().toString().slice(-6)}`,
        manufacture_date: todayStr,
        expiry_date: expStr,
        quantity: 100,
        purchase_unit_price: 35000,
      },
    ])
    setReceiptNote('')
    setFormError('')
    setModalOpen(true)
  }

  function addItemLine() {
    const todayStr = getTodayDateStringVN()
    const expDate = new Date()
    expDate.setFullYear(expDate.getFullYear() + 2)
    const expStr = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Ho_Chi_Minh', year: 'numeric', month: '2-digit', day: '2-digit' }).format(expDate)

    setItems(prev => [
      ...prev,
      {
        sku_id: products[0]?.id || 1,
        batch_number: `LOT-${Date.now().toString().slice(-6)}`,
        manufacture_date: todayStr,
        expiry_date: expStr,
        quantity: 50,
        purchase_unit_price: 40000,
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

  async function handleCreateReceipt(e: React.FormEvent) {
    e.preventDefault()
    setFormError('')
    if (items.length === 0) {
      return setFormError('Vui lòng thêm ít nhất một dòng thuốc nhập kho.')
    }

    setSubmitting(true)
    try {
      await api('/inventory/receipts', {
        method: 'POST',
        body: JSON.stringify({
          warehouse_id: selectedWarehouseId,
          supplier_id: selectedSupplierId,
          note: receiptNote.trim() || undefined,
          items: items.map(it => ({
            sku_id: Number(it.sku_id),
            batch_number: it.batch_number.trim().toUpperCase(),
            manufacture_date: it.manufacture_date || undefined,
            expiry_date: it.expiry_date,
            quantity: Number(it.quantity),
            purchase_unit_price: Number(it.purchase_unit_price),
          })),
        }),
      })
      setModalOpen(false)
      loadData()
    } catch (err: any) {
      setFormError(err.message || 'Lỗi khi lập phiếu nhập kho')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="page">
      <div className="page-heading">
        <div>
          <span className="overline">QUẢN LÝ NHẬP HÀNG & CHỨNG TỪ GSP</span>
          <h1>Phiếu Nhập Kho Dược Phẩm</h1>
          <p>
            Tạo và theo dõi chứng từ nhập kho từ nhà cung cấp đạt chuẩn GSP, sinh tự động số lô, hạn dùng và thẻ kho.
          </p>
        </div>
        <div>
          <button className="primary-button" onClick={openCreateModal}>
            <Plus size={16} /> Lập Phiếu Nhập Mới
          </button>
        </div>
      </div>

      {error && <div className="alert alert-error" style={{ marginBottom: '16px' }}>{error}</div>}

      {/* Receipts Table */}
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
              <th style={{ padding: '12px 16px' }}>Mã Phiếu</th>
              <th style={{ padding: '12px 14px' }}>Kho Tiếp Nhận</th>
              <th style={{ padding: '12px 14px' }}>Nhà Cung Cấp</th>
              <th style={{ padding: '12px 14px', textAlign: 'center' }}>Số Mặt Hàng</th>
              <th style={{ padding: '12px 14px', textAlign: 'right' }}>Tổng Giá Trị</th>
              <th style={{ padding: '12px 14px' }}>Thời Gian</th>
              <th style={{ padding: '12px 14px' }}>Trạng Thái</th>
              <th style={{ padding: '12px 16px', textAlign: 'center' }}>Chi Tiết</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={8} style={{ padding: '36px', textAlign: 'center', color: '#64748b' }}>
                  Đang tải danh sách phiếu nhập kho…
                </td>
              </tr>
            ) : receipts.length === 0 ? (
              <tr>
                <td colSpan={8} style={{ padding: '40px 16px', textAlign: 'center' }}>
                  <EmptyState title="Chưa có phiếu nhập kho nào" description="Bấm nút Lập Phiếu Nhập Mới để nhập hàng đầu kỳ." />
                </td>
              </tr>
            ) : (
              displayedReceipts.map(rec => (
                <tr key={rec.id} style={{ borderBottom: '1px solid #edf2f7' }} className="hover-row">
                  <td style={{ padding: '12px 16px', fontWeight: 700, fontFamily: 'monospace', color: '#0f172a' }}>
                    {rec.receipt_code}
                  </td>
                  <td style={{ padding: '12px 14px', fontWeight: 500, color: '#334155' }}>
                    {rec.warehouse_name}
                  </td>
                  <td style={{ padding: '12px 14px', color: '#475569' }}>
                    {rec.supplier_name}
                  </td>
                  <td style={{ padding: '12px 14px', textAlign: 'center' }}>
                    <span style={{ background: '#f1f5f9', padding: '2px 8px', borderRadius: '6px', fontWeight: 700 }}>
                      {rec.items_count} mặt hàng
                    </span>
                  </td>
                  <td style={{ padding: '12px 14px', textAlign: 'right', fontWeight: 700, color: '#0f172a' }}>
                    {(rec.total_amount ?? 0).toLocaleString('vi-VN')} đ
                  </td>
                  <td style={{ padding: '12px 14px', color: '#64748b' }}>
                    {rec.received_date?.slice(0, 16).replace('T', ' ')}
                  </td>
                  <td style={{ padding: '12px 14px' }}>
                    <span
                      style={{
                        padding: '3px 8px',
                        borderRadius: '6px',
                        fontSize: '11px',
                        fontWeight: 700,
                        background: rec.status === 'CONFIRMED' ? '#dcfce7' : '#f1f5f9',
                        color: rec.status === 'CONFIRMED' ? '#166534' : '#64748b',
                      }}
                    >
                      {rec.status === 'CONFIRMED' ? 'Đã nhập kho' : rec.status}
                    </span>
                  </td>
                  <td style={{ padding: '12px 16px', textAlign: 'center' }}>
                    <button
                      className="icon-button"
                      onClick={() => setViewingReceipt(rec)}
                      title="Xem danh sách thuốc nhập"
                    >
                      <Eye size={15} />
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>

        {/* Phân trang danh sách phiếu nhập */}
        {!loading && receipts.length > 0 && (
          <PaginationBar
            currentPage={currentPage}
            totalPages={totalPages}
            pageSize={pageSize}
            totalItems={receipts.length}
            itemName="phiếu nhập kho"
            onPageChange={setCurrentPage}
            onPageSizeChange={setPageSize}
            pageSizeOptions={[10, 15, 25, 50]}
          />
        )}
      </div>

      {/* Modal Lập Phiếu Nhập */}
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
              maxWidth: '780px',
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
                <span className="overline">QUY TRÌNH TIẾP NHẬN GSP</span>
                <h2 style={{ fontSize: '18px', fontWeight: 800, margin: '2px 0 0 0', color: '#0f172a' }}>
                  Lập Phiếu Nhập Kho Dược Phẩm Mới
                </h2>
              </div>
              <button className="icon-button" onClick={() => setModalOpen(false)}>
                <X size={18} />
              </button>
            </div>

            {formError && <div className="alert alert-error" style={{ marginBottom: '12px' }}>{formError}</div>}

            <form onSubmit={handleCreateReceipt} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                <div>
                  <label style={{ fontSize: '12px', fontWeight: 600, color: '#334155', display: 'block', marginBottom: '4px' }}>
                    Kho Tiếp Nhận *
                  </label>
                  <select
                    value={selectedWarehouseId}
                    onChange={e => setSelectedWarehouseId(Number(e.target.value))}
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
                    Nhà Cung Cấp Dược *
                  </label>
                  <select
                    value={selectedSupplierId}
                    onChange={e => setSelectedSupplierId(Number(e.target.value))}
                    style={{ width: '100%', padding: '8px 12px', borderRadius: '8px', border: '1px solid #cbd5e1' }}
                    required
                  >
                    {suppliers.map(s => (
                      <option key={s.id} value={s.id}>
                        {s.name} ({s.code})
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div>
                <label style={{ fontSize: '12px', fontWeight: 600, color: '#334155', display: 'block', marginBottom: '4px' }}>
                  Ghi chú chứng từ / Số hóa đơn đỏ
                </label>
                <input
                  placeholder="Ví dụ: Nhập theo hóa đơn GTGT số 00129..."
                  value={receiptNote}
                  onChange={e => setReceiptNote(e.target.value)}
                  style={{ width: '100%', padding: '8px 12px', borderRadius: '8px', border: '1px solid #cbd5e1' }}
                />
              </div>

              {/* Items List */}
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                  <label style={{ fontSize: '13px', fontWeight: 700, color: '#0f172a' }}>
                    Danh sách Thuốc & Số Lô Nhập ({items.length})
                  </label>
                  <button
                    type="button"
                    className="secondary-button"
                    onClick={addItemLine}
                    style={{ padding: '4px 10px', fontSize: '12px' }}
                  >
                    <Plus size={14} /> Thêm dòng thuốc
                  </button>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {items.map((it, idx) => (
                    <div
                      key={idx}
                      style={{
                        display: 'grid',
                        gridTemplateColumns: '2fr 1.5fr 1.2fr 1.2fr 1fr 1.2fr 36px',
                        gap: '8px',
                        alignItems: 'center',
                        background: '#f8fafc',
                        padding: '10px',
                        borderRadius: '8px',
                        border: '1px solid #e2e8f0',
                      }}
                    >
                      {/* Product */}
                      <div>
                        <div style={{ fontSize: '11px', color: '#64748b' }}>Thuốc</div>
                        <select
                          value={it.sku_id}
                          onChange={e => updateItemLine(idx, 'sku_id', Number(e.target.value))}
                          style={{ width: '100%', padding: '6px', fontSize: '12px', borderRadius: '6px', border: '1px solid #cbd5e1' }}
                        >
                          {products.map(p => (
                            <option key={p.id} value={p.id}>
                              {p.canonical_name}
                            </option>
                          ))}
                        </select>
                      </div>

                      {/* Batch Number */}
                      <div>
                        <div style={{ fontSize: '11px', color: '#64748b' }}>Số lô</div>
                        <input
                          value={it.batch_number}
                          onChange={e => updateItemLine(idx, 'batch_number', e.target.value.toUpperCase())}
                          style={{ width: '100%', padding: '6px', fontSize: '12px', borderRadius: '6px', border: '1px solid #cbd5e1' }}
                          required
                        />
                      </div>

                      {/* Mfg Date */}
                      <div>
                        <div style={{ fontSize: '11px', color: '#64748b' }}>Ngày SX</div>
                        <input
                          type="date"
                          value={it.manufacture_date}
                          onChange={e => updateItemLine(idx, 'manufacture_date', e.target.value)}
                          style={{ width: '100%', padding: '5px', fontSize: '11px', borderRadius: '6px', border: '1px solid #cbd5e1' }}
                        />
                      </div>

                      {/* Expiry Date */}
                      <div>
                        <div style={{ fontSize: '11px', color: '#64748b' }}>Hạn dùng *</div>
                        <input
                          type="date"
                          value={it.expiry_date}
                          onChange={e => updateItemLine(idx, 'expiry_date', e.target.value)}
                          style={{ width: '100%', padding: '5px', fontSize: '11px', borderRadius: '6px', border: '1px solid #cbd5e1' }}
                          required
                        />
                      </div>

                      {/* Quantity */}
                      <div>
                        <div style={{ fontSize: '11px', color: '#64748b' }}>Số lượng</div>
                        <input
                          type="number"
                          min="1"
                          value={it.quantity}
                          onChange={e => updateItemLine(idx, 'quantity', Number(e.target.value))}
                          style={{ width: '100%', padding: '6px', fontSize: '12px', borderRadius: '6px', border: '1px solid #cbd5e1' }}
                          required
                        />
                      </div>

                      {/* Purchase Unit Price */}
                      <div>
                        <div style={{ fontSize: '11px', color: '#64748b' }}>Giá mua (đ)</div>
                        <input
                          type="number"
                          min="0"
                          step="1000"
                          value={it.purchase_unit_price}
                          onChange={e => updateItemLine(idx, 'purchase_unit_price', Number(e.target.value))}
                          style={{ width: '100%', padding: '6px', fontSize: '12px', borderRadius: '6px', border: '1px solid #cbd5e1' }}
                          required
                        />
                      </div>

                      {/* Remove Button */}
                      <div style={{ paddingTop: '16px' }}>
                        <button
                          type="button"
                          className="icon-button"
                          onClick={() => removeItemLine(idx)}
                          title="Xóa dòng này"
                          style={{ color: '#ef4444' }}
                        >
                          <Trash2 size={15} />
                        </button>
                      </div>
                    </div>
                  ))}
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
                  {submitting ? 'Đang ghi nhận…' : 'Xác Nhận Nhập Kho (CONFIRMED)'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal Xem Chi Tiết Phiếu Nhập */}
      {viewingReceipt && (
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
          onClick={() => setViewingReceipt(null)}
        >
          <div
            style={{
              background: '#ffffff',
              borderRadius: '16px',
              maxWidth: '680px',
              width: '100%',
              padding: '24px',
              boxShadow: '0 10px 25px rgba(0,0,0,0.15)',
            }}
            onClick={e => e.stopPropagation()}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <div>
                <span className="overline">CHI TIẾT CHỨNG TỪ GSP</span>
                <h2 style={{ fontSize: '18px', fontWeight: 800, margin: 0, color: '#0f172a' }}>
                  {viewingReceipt.receipt_code}
                </h2>
              </div>
              <button className="icon-button" onClick={() => setViewingReceipt(null)}>
                <X size={18} />
              </button>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', background: '#f8fafc', padding: '12px', borderRadius: '10px', marginBottom: '16px' }}>
              <div>Kho tiếp nhận: <strong>{viewingReceipt.warehouse_name}</strong></div>
              <div>Nhà cung cấp: <strong>{viewingReceipt.supplier_name}</strong></div>
              <div>Tổng tiền hàng: <strong>{(viewingReceipt.total_amount ?? 0).toLocaleString('vi-VN')} đ</strong></div>
              <div>Thời gian: <strong>{viewingReceipt.received_date?.slice(0, 16)}</strong></div>
            </div>

            <div style={{ fontSize: '13px', fontWeight: 700, marginBottom: '8px' }}>Danh sách các lô thuốc nhập:</div>
            <div style={{ maxHeight: '300px', overflowY: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }}>
                <thead>
                  <tr style={{ background: '#f1f5f9', borderBottom: '1px solid #cbd5e1' }}>
                    <th style={{ padding: '8px' }}>Số Lô</th>
                    <th style={{ padding: '8px' }}>Hạn Dùng</th>
                    <th style={{ padding: '8px', textAlign: 'right' }}>Số Lượng</th>
                    <th style={{ padding: '8px', textAlign: 'right' }}>Đơn Giá</th>
                    <th style={{ padding: '8px', textAlign: 'right' }}>Thành Tiền</th>
                  </tr>
                </thead>
                <tbody>
                  {viewingReceipt.items.map(it => (
                    <tr key={it.id} style={{ borderBottom: '1px solid #edf2f7' }}>
                      <td style={{ padding: '8px', fontFamily: 'monospace', fontWeight: 700 }}>{it.batch_number}</td>
                      <td style={{ padding: '8px' }}>{it.expiry_date}</td>
                      <td style={{ padding: '8px', textAlign: 'right', fontWeight: 600 }}>{it.quantity}</td>
                      <td style={{ padding: '8px', textAlign: 'right' }}>{(it.purchase_unit_price ?? 0).toLocaleString()} đ</td>
                      <td style={{ padding: '8px', textAlign: 'right', fontWeight: 700 }}>{(it.line_total ?? 0).toLocaleString()} đ</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
