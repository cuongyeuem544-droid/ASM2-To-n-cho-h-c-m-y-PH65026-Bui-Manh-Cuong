import { History } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { EmptyState } from '../components/EmptyState'
import { PaginationBar } from '../components/PaginationBar'
import { api } from '../services/api'

interface Audit { id: number; user_id: number | null; action: string; entity_type: string; entity_id: string | null; before_json: unknown; after_json: unknown; ip_address: string | null; created_at: string }

const ACTION_NAMES: Record<string, string> = {
  RECALCULATE_SCORE: 'Tính lại điểm',
  RESOLVE_CONFLICT: 'Xử lý mâu thuẫn',
  PUBLISH_PRODUCT: 'Duyệt đăng bán',
  UNPUBLISH_PRODUCT: 'Tạm ẩn sản phẩm',
  IMPORT_FILE: 'Nhập tệp dữ liệu',
  UPDATE_STATUS: 'Cập nhật trạng thái',
  ASSIGN_CATEGORY: 'Phân loại danh mục',
}

export function AuditPage() {
  const [items, setItems] = useState<Audit[]>([])
  const [error, setError] = useState('')

  // Phân trang
  const [currentPage, setCurrentPage] = useState<number>(1)
  const [pageSize, setPageSize] = useState<number>(15)

  useEffect(() => { api<Audit[]>('/audit-logs').then(setItems).catch(err => setError(err.message)) }, [])

  const totalPages = Math.max(1, Math.ceil(items.length / pageSize))
  const displayedItems = useMemo(() => {
    const start = (currentPage - 1) * pageSize
    return items.slice(start, start + pageSize)
  }, [items, currentPage, pageSize])

  return (
    <div className="page">
      <div className="page-heading">
        <div>
          <span className="overline">LỊCH SỬ THAO TÁC</span>
          <h1>Nhật Ký Thao Tác Quản Trị</h1>
          <p>Ghi nhận minh bạch người thực hiện, hành vi chỉnh sửa dữ liệu và thời điểm cập nhật.</p>
        </div>
        <History />
      </div>
      {error && <div className="alert alert-error">{error}</div>}
      {!items.length ? (
        <EmptyState title="Chưa có nhật ký thao tác" description="Mọi hành động duyệt, sửa đổi thuốc sẽ được ghi nhận tại đây." />
      ) : (
        <div className="panel table-wrap">
          <table>
            <thead>
              <tr>
                <th>Thời gian</th>
                <th>Người thực hiện</th>
                <th>Hành động</th>
                <th>Đối tượng</th>
                <th>Địa chỉ IP</th>
                <th>Chi tiết thay đổi</th>
              </tr>
            </thead>
            <tbody>
              {displayedItems.map(item => (
                <tr key={item.id}>
                  <td>{new Date(item.created_at).toLocaleString('vi-VN')}</td>
                  <td>#{item.user_id || 'Hệ thống tự động'}</td>
                  <td><strong>{ACTION_NAMES[item.action] || item.action}</strong></td>
                  <td>{item.entity_type} #{item.entity_id}</td>
                  <td>{item.ip_address || '—'}</td>
                  <td>
                    <details>
                      <summary>Xem chi tiết thay đổi</summary>
                      <pre>{JSON.stringify({ trước: item.before_json, sau: item.after_json }, null, 2)}</pre>
                    </details>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {items.length > 0 && (
            <PaginationBar
              currentPage={currentPage}
              totalPages={totalPages}
              pageSize={pageSize}
              totalItems={items.length}
              itemName="nhật ký thao tác"
              onPageChange={setCurrentPage}
              onPageSizeChange={setPageSize}
              pageSizeOptions={[10, 15, 25, 50]}
            />
          )}
        </div>
      )}
    </div>
  )
}

