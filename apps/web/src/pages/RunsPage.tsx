import { Activity, Clock3 } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { EmptyState } from '../components/EmptyState'
import { StatusBadge } from '../components/StatusBadge'
import { PaginationBar } from '../components/PaginationBar'
import { api } from '../services/api'

interface Run { id: number; source_id: number; status: string; started_at: string | null; finished_at: string | null; pages_requested: number; pages_success: number; pages_failed: number; products_discovered: number; error_message: string | null }

export function RunsPage() {
  const [items, setItems] = useState<Run[]>([])

  // Phân trang
  const [currentPage, setCurrentPage] = useState<number>(1)
  const [pageSize, setPageSize] = useState<number>(10)

  useEffect(() => { api<Run[]>('/crawl-runs').then(setItems) }, [])

  const totalPages = Math.max(1, Math.ceil(items.length / pageSize))
  const displayedItems = useMemo(() => {
    const start = (currentPage - 1) * pageSize
    return items.slice(start, start + pageSize)
  }, [items, currentPage, pageSize])

  return (
    <div className="page">
      <div className="page-heading">
        <div>
          <span className="overline">TIẾN TRÌNH VẬN HÀNH</span>
          <h1>Nhật Ký Thu Thập Dữ Liệu</h1>
          <p>Theo dõi tiến độ, số trang thành công và kết quả của các phiên cào dữ liệu.</p>
        </div>
      </div>
      {!items.length ? (
        <EmptyState title="Chưa có phiên thu thập nào" description="Bạn có thể kích hoạt cào từ trang Thu thập tự động hoặc Nguồn dữ liệu." />
      ) : (
        <>
          <div className="run-timeline">
            {displayedItems.map(item => (
              <article className="run-card" key={item.id}>
                <span className="timeline-dot"><Activity size={17} /></span>
                <div className="run-main">
                  <div>
                    <strong>Phiên cào #{item.id}</strong>
                    <span>Nguồn #{item.source_id}</span>
                  </div>
                  <div className="run-metrics">
                    <span>{item.pages_success}/{item.pages_requested} trang thành công</span>
                    <span>{item.pages_failed} trang lỗi</span>
                    <span>{item.products_discovered} thuốc tìm thấy</span>
                  </div>
                  {item.error_message && <p className="error-text">{item.error_message}</p>}
                </div>
                <div className="run-meta">
                  <StatusBadge value={item.status} />
                  <small><Clock3 size={13} />{item.started_at ? new Date(item.started_at).toLocaleString('vi-VN') : 'Chưa bắt đầu'}</small>
                </div>
              </article>
            ))}
          </div>
          {items.length > 0 && (
            <PaginationBar
              currentPage={currentPage}
              totalPages={totalPages}
              pageSize={pageSize}
              totalItems={items.length}
              itemName="phiên thu thập"
              onPageChange={setCurrentPage}
              onPageSizeChange={setPageSize}
              pageSizeOptions={[5, 10, 20, 50]}
            />
          )}
        </>
      )}
    </div>
  )
}

