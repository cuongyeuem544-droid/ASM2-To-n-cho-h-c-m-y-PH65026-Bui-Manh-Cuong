import { AlertTriangle, Check, Filter } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { EmptyState } from '../components/EmptyState'
import { StatusBadge } from '../components/StatusBadge'
import { PaginationBar } from '../components/PaginationBar'
import { api } from '../services/api'
import type { Conflict } from '../types'

const FIELD_NAMES: Record<string, string> = {
  canonical_name: 'Tên thuốc',
  registration_number: 'Số đăng ký',
  manufacturer: 'Nhà sản xuất',
  dosage_form: 'Dạng bào chế',
  package_description: 'Quy cách đóng gói',
  ingredients: 'Hoạt chất',
  rx_otc_status: 'Phân loại kê đơn',
  strength: 'Hàm lượng',
}

export function ConflictsPage() {
  const [items, setItems] = useState<Conflict[]>([])
  const [status, setStatus] = useState('OPEN')
  const [error, setError] = useState('')

  // Phân trang
  const [currentPage, setCurrentPage] = useState<number>(1)
  const [pageSize, setPageSize] = useState<number>(10)

  const load = () => api<Conflict[]>(`/conflicts?status=${status}`).then(setItems).catch(err => setError(err.message))
  
  useEffect(() => { 
    setCurrentPage(1)
    void load() 
  }, [status])

  const totalPages = Math.max(1, Math.ceil(items.length / pageSize))
  const displayedItems = useMemo(() => {
    const start = (currentPage - 1) * pageSize
    return items.slice(start, start + pageSize)
  }, [items, currentPage, pageSize])

  async function resolve(item: Conflict) {
    const note = window.prompt('Ghi chú quyết định xử lý dữ liệu:')
    if (!note) return
    try {
      await api(`/conflicts/${item.id}`, { method: 'PATCH', body: JSON.stringify({ status: 'RESOLVED', resolution_note: note }) })
      await load()
    } catch (err) { setError(err instanceof Error ? err.message : 'Không thể xử lý') }
  }

  return (
    <div className="page">
      <div className="page-heading">
        <div>
          <span className="overline">KIỂM SOÁT DỮ LIỆU</span>
          <h1>Xử Lý Lệch Dữ Liệu & Mâu Thuẫn</h1>
          <p>Đối chiếu sự khác biệt giữa các nguồn thu thập và lưu lại quyết định thống nhất.</p>
        </div>
      </div>
      <div className="toolbar">
        <div className="filter-label"><Filter size={17} /> Trạng thái:</div>
        <select value={status} onChange={e => setStatus(e.target.value)}>
          <option value="OPEN">Chờ xử lý</option>
          <option value="RESOLVED">Đã xử lý xong</option>
          <option value="DISMISSED">Đã bỏ qua</option>
        </select>
      </div>
      {error && <div className="alert alert-error">{error}</div>}
      {!items.length && <EmptyState title="Không có mâu thuẫn nào" description="Dữ liệu đồng nhất, không có bản ghi nào bị lệch." />}
      <div className="conflict-list">
        {displayedItems.map(item => (
          <article className="conflict-card" key={item.id}>
            <div className="conflict-head">
              <span className="conflict-symbol"><AlertTriangle /></span>
              <div>
                <div className="detail-badges">
                  <StatusBadge value={item.severity} />
                  <StatusBadge value={item.conflict_type} />
                </div>
                <h3>{item.description}</h3>
                <p>Mã thuốc #{item.product_id} · Thông tin bị lệch: <strong>{FIELD_NAMES[item.field_name] || item.field_name}</strong></p>
              </div>
              <StatusBadge value={item.status} />
            </div>
            <div className="compare-grid">
              <div>
                <span>DỮ LIỆU NGUỒN A</span>
                <strong>{item.value_a || 'Không có dữ liệu'}</strong>
              </div>
              <div>
                <span>DỮ LIỆU NGUỒN B</span>
                <strong>{item.value_b || 'Không có dữ liệu'}</strong>
              </div>
            </div>
            {item.status === 'OPEN' && (
              <button className="secondary-button" onClick={() => resolve(item)}>
                <Check size={16} /> Xác nhận đã xử lý xong
              </button>
            )}
          </article>
        ))}
      </div>
      {items.length > 0 && (
        <PaginationBar
          currentPage={currentPage}
          totalPages={totalPages}
          pageSize={pageSize}
          totalItems={items.length}
          itemName="mâu thuẫn"
          onPageChange={setCurrentPage}
          onPageSizeChange={setPageSize}
          pageSizeOptions={[5, 10, 20, 50]}
        />
      )}
    </div>
  )
}
