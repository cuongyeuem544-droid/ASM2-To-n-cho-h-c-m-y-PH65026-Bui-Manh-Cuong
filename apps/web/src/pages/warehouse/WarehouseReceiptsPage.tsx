import { useEffect, useState } from 'react'
import {
  ArrowDownToLine,
  Plus,
  Search,
  CheckCircle2,
  Calendar,
  Building2,
  Layers,
  X,
  Trash2,
} from 'lucide-react'
import { api } from '../../services/api'

interface ReceiptItem {
  id: number
  receipt_code: string
  supplier_name: string
  status: string
  total_amount: number
  received_date: string | null
  note?: string | null
  items_count: number
  created_at: string | null
}

export function WarehouseReceiptsPage() {
  const [receipts, setReceipts] = useState<ReceiptItem[]>([])
  const [loading, setLoading] = useState(true)
  const [total, setTotal] = useState(0)

  // Create Modal state
  const [showModal, setShowModal] = useState(false)
  const [creating, setCreating] = useState(false)
  const [note, setNote] = useState('')
  const [supplierId, setSupplierId] = useState(1)
  const [items, setItems] = useState<Array<{
    sku_id: number
    batch_number: string
    manufacture_date: string
    expiry_date: string
    quantity: number
    purchase_unit_price: number
  }>>([
    {
      sku_id: 1,
      batch_number: `BAT-${Date.now().toString().slice(-6)}`,
      manufacture_date: '2026-01-01',
      expiry_date: '2028-01-01',
      quantity: 100,
      purchase_unit_price: 25000,
    },
  ])

  const fetchReceipts = () => {
    setLoading(true)
    api<{ items: ReceiptItem[]; total: number }>('/warehouse-portal/receipts')
      .then((res) => {
        setReceipts(res.items || [])
        setTotal(res.total || 0)
      })
      .catch((err) => console.error(err))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    fetchReceipts()
  }, [])

  const handleAddItem = () => {
    setItems((prev) => [
      ...prev,
      {
        sku_id: 1,
        batch_number: `BAT-${Date.now().toString().slice(-6)}`,
        manufacture_date: '2026-01-01',
        expiry_date: '2028-01-01',
        quantity: 50,
        purchase_unit_price: 30000,
      },
    ])
  }

  const handleRemoveItem = (index: number) => {
    setItems((prev) => prev.filter((_, i) => i !== index))
  }

  const handleCreateReceipt = async (e: React.FormEvent) => {
    e.preventDefault()
    if (items.length === 0) {
      alert('Vui lòng thêm ít nhất 1 dòng thuốc để nhập kho')
      return
    }

    setCreating(true)
    try {
      await api('/warehouse-portal/receipts', {
        method: 'POST',
        body: JSON.stringify({
          supplier_id: supplierId,
          note: note || undefined,
          items,
        }),
      })
      setShowModal(false)
      fetchReceipts()
      alert('Tạo phiếu nhập kho và cập nhật tồn kho thành công!')
    } catch (err: any) {
      alert(err?.message || 'Không thể tạo phiếu nhập kho')
    } finally {
      setCreating(false)
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
          <div style={{ fontSize: '11px', fontWeight: 800, color: '#047857', textTransform: 'uppercase', letterSpacing: '0.8px' }}>
            QUY TRÌNH NHẬP DƯỢC PHẨM GSP
          </div>
          <h1 style={{ margin: '4px 0 0', fontSize: '22px', fontWeight: 900, color: '#0f172a' }}>
            Phiếu Nhập Kho (GSP)
          </h1>
          <p style={{ margin: '4px 0 0', fontSize: '13px', color: '#64748b' }}>
            Ghi nhận thuốc nhập từ nhà sản xuất, tạo mã lô, ngày sản xuất và hạn sử dụng
          </p>
        </div>

        <button
          type="button"
          onClick={() => setShowModal(true)}
          style={{
            background: 'linear-gradient(135deg, #059669, #047857)',
            color: 'white',
            padding: '10px 18px',
            borderRadius: '12px',
            fontSize: '13px',
            fontWeight: 800,
            border: 'none',
            cursor: 'pointer',
            display: 'inline-flex',
            alignItems: 'center',
            gap: '8px',
            boxShadow: '0 3px 10px rgba(5, 150, 105, 0.3)',
          }}
        >
          <Plus size={16} /> Tạo Phiếu Nhập Kho
        </button>
      </div>

      {/* Receipts Table */}
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
                <th style={{ padding: '14px 18px' }}>Mã Phiếu Nhập</th>
                <th style={{ padding: '14px 18px' }}>Nhà Cung Cấp</th>
                <th style={{ padding: '14px 18px' }}>Tổng Giá Trị</th>
                <th style={{ padding: '14px 18px' }}>Số Mặt Hàng</th>
                <th style={{ padding: '14px 18px' }}>Trạng Thái</th>
                <th style={{ padding: '14px 18px' }}>Ngày Nhập Kho</th>
                <th style={{ padding: '14px 18px' }}>Ghi Chú</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={7} style={{ padding: '40px', textAlign: 'center', color: '#94a3b8', fontWeight: 600 }}>
                    Đang tải danh sách phiếu nhập kho…
                  </td>
                </tr>
              ) : receipts.length === 0 ? (
                <tr>
                  <td colSpan={7} style={{ padding: '40px', textAlign: 'center', color: '#94a3b8', fontWeight: 600 }}>
                    Chi nhánh hiện chưa có phiếu nhập kho nào.
                  </td>
                </tr>
              ) : (
                receipts.map((r) => (
                  <tr
                    key={r.id}
                    style={{ borderBottom: '1px solid #f1f5f9', transition: 'background 0.15s ease' }}
                    onMouseEnter={(e) => (e.currentTarget.style.background = '#f8fafc')}
                    onMouseLeave={(e) => (e.currentTarget.style.background = 'white')}
                  >
                    <td style={{ padding: '14px 18px', fontFamily: 'monospace', fontWeight: 900, color: '#047857' }}>
                      {r.receipt_code}
                    </td>

                    <td style={{ padding: '14px 18px', fontWeight: 800, color: '#0f172a' }}>
                      {r.supplier_name}
                    </td>

                    <td style={{ padding: '14px 18px', fontWeight: 800, color: '#0f172a' }}>
                      {r.total_amount.toLocaleString('vi-VN')} đ
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
                        {r.items_count} mặt hàng
                      </span>
                    </td>

                    <td style={{ padding: '14px 18px' }}>
                      <span
                        style={{
                          padding: '4px 10px',
                          borderRadius: '9999px',
                          fontSize: '11px',
                          fontWeight: 800,
                          background: '#ecfdf5',
                          color: '#047857',
                        }}
                      >
                        {r.status}
                      </span>
                    </td>

                    <td style={{ padding: '14px 18px', color: '#64748b', fontSize: '12px' }}>
                      {r.received_date ? new Date(r.received_date).toLocaleDateString('vi-VN') : '—'}
                    </td>

                    <td style={{ padding: '14px 18px', color: '#64748b', fontSize: '12px' }}>
                      {r.note || '—'}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Create Modal */}
      {showModal && (
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
              maxWidth: '780px',
              width: '100%',
              maxHeight: '90vh',
              overflowY: 'auto',
              padding: '26px',
              boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.25)',
              display: 'flex',
              flexDirection: 'column',
              gap: '18px',
            }}
          >
            {/* Modal Header */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid #e2e8f0', paddingBottom: '14px' }}>
              <div>
                <h3 style={{ margin: 0, fontSize: '18px', fontWeight: 900, color: '#0f172a' }}>
                  Tạo Phiếu Nhập Kho GSP Mới
                </h3>
                <p style={{ margin: '4px 0 0', fontSize: '12px', color: '#64748b' }}>
                  Khai báo nhà cung cấp và thông tin từng lô thuốc để tăng tồn kho tự động
                </p>
              </div>
              <button
                type="button"
                onClick={() => setShowModal(false)}
                style={{ background: 'none', border: 'none', color: '#94a3b8', cursor: 'pointer', padding: '4px' }}
              >
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleCreateReceipt} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '14px' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '11px', fontWeight: 800, color: '#334155', textTransform: 'uppercase', marginBottom: '6px' }}>
                    Nhà cung cấp dược phẩm *
                  </label>
                  <select
                    value={supplierId}
                    onChange={(e) => setSupplierId(Number(e.target.value))}
                    style={{
                      width: '100%',
                      padding: '10px 14px',
                      borderRadius: '10px',
                      border: '1.5px solid #cbd5e1',
                      fontSize: '13.5px',
                      outline: 'none',
                      background: 'white',
                      boxSizing: 'border-box',
                    }}
                  >
                    <option value={1}>Tổng Công Ty Dược Việt Nam (Vinapharm)</option>
                    <option value={2}>Công Ty Cổ Phần Dược Hậu Giang (DHG Pharma)</option>
                    <option value={3}>Công Ty CP Traphaco</option>
                  </select>
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '11px', fontWeight: 800, color: '#334155', textTransform: 'uppercase', marginBottom: '6px' }}>
                    Ghi chú phiếu nhập
                  </label>
                  <input
                    type="text"
                    value={note}
                    onChange={(e) => setNote(e.target.value)}
                    placeholder="VD: Nhập định kỳ GSP từ Vinapharm"
                    style={{
                      width: '100%',
                      padding: '10px 14px',
                      borderRadius: '10px',
                      border: '1.5px solid #cbd5e1',
                      fontSize: '13.5px',
                      outline: 'none',
                      boxSizing: 'border-box',
                    }}
                  />
                </div>
              </div>

              {/* Items List */}
              <div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                  <span style={{ fontSize: '12px', fontWeight: 800, color: '#334155', textTransform: 'uppercase' }}>
                    Danh sách các lô thuốc nhập kho ({items.length})
                  </span>
                  <button
                    type="button"
                    onClick={handleAddItem}
                    style={{
                      background: '#ecfdf5',
                      border: '1px solid #a7f3d0',
                      color: '#047857',
                      padding: '5px 12px',
                      borderRadius: '8px',
                      fontSize: '12px',
                      fontWeight: 700,
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '4px',
                    }}
                  >
                    <Plus size={14} /> Thêm lô thuốc
                  </button>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                  {items.map((item, idx) => (
                    <div
                      key={idx}
                      style={{
                        background: '#f8fafc',
                        borderRadius: '12px',
                        border: '1px solid #e2e8f0',
                        padding: '12px 14px',
                        display: 'grid',
                        gridTemplateColumns: '80px 1.5fr 1fr 90px 1.2fr 36px',
                        gap: '10px',
                        alignItems: 'center',
                      }}
                    >
                      <div>
                        <label style={{ display: 'block', fontSize: '10px', fontWeight: 800, color: '#64748b', textTransform: 'uppercase' }}>SKU ID</label>
                        <input
                          type="number"
                          min={1}
                          value={item.sku_id}
                          onChange={(e) => {
                            const val = Number(e.target.value)
                            setItems((prev) => prev.map((it, i) => i === idx ? { ...it, sku_id: val } : it))
                          }}
                          style={{ width: '100%', padding: '6px 8px', borderRadius: '6px', border: '1px solid #cbd5e1', fontSize: '12px', boxSizing: 'border-box' }}
                        />
                      </div>

                      <div>
                        <label style={{ display: 'block', fontSize: '10px', fontWeight: 800, color: '#64748b', textTransform: 'uppercase' }}>Mã Số Lô</label>
                        <input
                          type="text"
                          value={item.batch_number}
                          onChange={(e) => {
                            const val = e.target.value
                            setItems((prev) => prev.map((it, i) => i === idx ? { ...it, batch_number: val } : it))
                          }}
                          style={{ width: '100%', padding: '6px 8px', borderRadius: '6px', border: '1px solid #cbd5e1', fontSize: '12px', fontFamily: 'monospace', boxSizing: 'border-box' }}
                        />
                      </div>

                      <div>
                        <label style={{ display: 'block', fontSize: '10px', fontWeight: 800, color: '#64748b', textTransform: 'uppercase' }}>Hạn Dùng</label>
                        <input
                          type="date"
                          value={item.expiry_date}
                          onChange={(e) => {
                            const val = e.target.value
                            setItems((prev) => prev.map((it, i) => i === idx ? { ...it, expiry_date: val } : it))
                          }}
                          style={{ width: '100%', padding: '6px 8px', borderRadius: '6px', border: '1px solid #cbd5e1', fontSize: '12px', boxSizing: 'border-box' }}
                        />
                      </div>

                      <div>
                        <label style={{ display: 'block', fontSize: '10px', fontWeight: 800, color: '#64748b', textTransform: 'uppercase' }}>Số Lượng</label>
                        <input
                          type="number"
                          min={1}
                          value={item.quantity}
                          onChange={(e) => {
                            const val = Number(e.target.value)
                            setItems((prev) => prev.map((it, i) => i === idx ? { ...it, quantity: val } : it))
                          }}
                          style={{ width: '100%', padding: '6px 8px', borderRadius: '6px', border: '1px solid #cbd5e1', fontSize: '12px', fontWeight: 700, boxSizing: 'border-box' }}
                        />
                      </div>

                      <div>
                        <label style={{ display: 'block', fontSize: '10px', fontWeight: 800, color: '#64748b', textTransform: 'uppercase' }}>Giá Nhập (đ)</label>
                        <input
                          type="number"
                          value={item.purchase_unit_price}
                          onChange={(e) => {
                            const val = Number(e.target.value)
                            setItems((prev) => prev.map((it, i) => i === idx ? { ...it, purchase_unit_price: val } : it))
                          }}
                          style={{ width: '100%', padding: '6px 8px', borderRadius: '6px', border: '1px solid #cbd5e1', fontSize: '12px', boxSizing: 'border-box' }}
                        />
                      </div>

                      <div style={{ paddingTop: '14px' }}>
                        {items.length > 1 && (
                          <button
                            type="button"
                            onClick={() => handleRemoveItem(idx)}
                            style={{ background: 'none', border: 'none', color: '#ef4444', cursor: 'pointer', padding: '4px' }}
                            title="Xóa dòng"
                          >
                            <Trash2 size={16} />
                          </button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Actions */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: '10px', paddingTop: '12px', borderTop: '1px solid #e2e8f0' }}>
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  style={{
                    padding: '10px 18px',
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
                  disabled={creating}
                  style={{
                    padding: '10px 22px',
                    borderRadius: '10px',
                    border: 'none',
                    background: 'linear-gradient(135deg, #059669, #047857)',
                    color: 'white',
                    fontSize: '13px',
                    fontWeight: 800,
                    cursor: 'pointer',
                    boxShadow: '0 2px 8px rgba(5, 150, 105, 0.3)',
                  }}
                >
                  {creating ? 'Đang tạo…' : 'Xác nhận nhập kho'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
