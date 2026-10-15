import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight } from 'lucide-react'

export interface PaginationBarProps {
  currentPage: number
  totalPages: number
  pageSize: number
  totalItems: number
  filteredCount?: number
  itemName?: string
  onPageChange: (page: number) => void
  onPageSizeChange: (size: number) => void
  pageSizeOptions?: number[]
}

export function PaginationBar({
  currentPage,
  totalPages,
  pageSize,
  totalItems,
  filteredCount,
  itemName = 'mục',
  onPageChange,
  onPageSizeChange,
  pageSizeOptions = [10, 20, 50, 100],
}: PaginationBarProps) {
  const count = filteredCount !== undefined ? filteredCount : totalItems
  const startItem = count === 0 ? 0 : (currentPage - 1) * pageSize + 1
  const endItem = Math.min(currentPage * pageSize, count)

  const getPageNumbers = () => {
    if (totalPages <= 7) {
      return Array.from({ length: totalPages }, (_, i) => i + 1)
    }
    if (currentPage <= 4) {
      return [1, 2, 3, 4, 5, '...', totalPages]
    }
    if (currentPage >= totalPages - 3) {
      return [1, '...', totalPages - 4, totalPages - 3, totalPages - 2, totalPages - 1, totalPages]
    }
    return [1, '...', currentPage - 1, currentPage, currentPage + 1, '...', totalPages]
  }

  const pages = getPageNumbers()

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: 12,
        padding: '12px 16px',
        background: '#f8fafc',
        borderTop: '1px solid #e2e8f0',
        borderBottomLeftRadius: 10,
        borderBottomRightRadius: 10,
        fontSize: 13,
      }}
    >
      {/* Items info and page size */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
        <span style={{ color: '#64748b' }}>
          Hiển thị <strong>{startItem} - {endItem}</strong> trong <strong>{(count ?? 0).toLocaleString('vi-VN')}</strong> {itemName}
          {filteredCount !== undefined && filteredCount !== totalItems ? ` (lọc từ ${(totalItems ?? 0).toLocaleString('vi-VN')} tổng)` : ''}
        </span>

        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <label style={{ color: '#64748b', fontSize: 12.5 }}>Dòng/trang:</label>
          <select
            value={pageSize}
            onChange={(e) => {
              onPageSizeChange(Number(e.target.value))
              onPageChange(1)
            }}
            style={{
              padding: '4px 8px',
              borderRadius: 6,
              border: '1px solid #cbd5e1',
              background: '#ffffff',
              fontSize: 12.5,
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            {pageSizeOptions.map((sz) => (
              <option key={sz} value={sz}>
                {sz}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Page controls */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
        <button
          type="button"
          onClick={() => onPageChange(1)}
          disabled={currentPage <= 1}
          title="Trang đầu"
          style={{
            padding: '5px 8px',
            borderRadius: 6,
            border: '1px solid #cbd5e1',
            background: currentPage <= 1 ? '#f1f5f9' : '#ffffff',
            color: currentPage <= 1 ? '#94a3b8' : '#334155',
            cursor: currentPage <= 1 ? 'not-allowed' : 'pointer',
            display: 'inline-flex',
            alignItems: 'center',
          }}
        >
          <ChevronsLeft size={15} />
        </button>

        <button
          type="button"
          onClick={() => onPageChange(currentPage - 1)}
          disabled={currentPage <= 1}
          title="Trang trước"
          style={{
            padding: '5px 8px',
            borderRadius: 6,
            border: '1px solid #cbd5e1',
            background: currentPage <= 1 ? '#f1f5f9' : '#ffffff',
            color: currentPage <= 1 ? '#94a3b8' : '#334155',
            cursor: currentPage <= 1 ? 'not-allowed' : 'pointer',
            display: 'inline-flex',
            alignItems: 'center',
          }}
        >
          <ChevronLeft size={15} />
        </button>

        {pages.map((p, idx) => {
          if (p === '...') {
            return (
              <span key={`dots-${idx}`} style={{ padding: '0 6px', color: '#94a3b8', fontWeight: 600 }}>
                ...
              </span>
            )
          }
          const pageNum = p as number
          const isActive = pageNum === currentPage
          return (
            <button
              key={pageNum}
              type="button"
              onClick={() => onPageChange(pageNum)}
              style={{
                minWidth: 32,
                height: 30,
                padding: '0 6px',
                borderRadius: 6,
                border: isActive ? '1px solid #0284c7' : '1px solid #cbd5e1',
                background: isActive ? '#0284c7' : '#ffffff',
                color: isActive ? '#ffffff' : '#334155',
                fontWeight: isActive ? 700 : 500,
                cursor: 'pointer',
                fontSize: 12.5,
              }}
            >
              {pageNum}
            </button>
          )
        })}

        <button
          type="button"
          onClick={() => onPageChange(currentPage + 1)}
          disabled={currentPage >= totalPages}
          title="Trang kế tiếp"
          style={{
            padding: '5px 8px',
            borderRadius: 6,
            border: '1px solid #cbd5e1',
            background: currentPage >= totalPages ? '#f1f5f9' : '#ffffff',
            color: currentPage >= totalPages ? '#94a3b8' : '#334155',
            cursor: currentPage >= totalPages ? 'not-allowed' : 'pointer',
            display: 'inline-flex',
            alignItems: 'center',
          }}
        >
          <ChevronRight size={15} />
        </button>

        <button
          type="button"
          onClick={() => onPageChange(totalPages)}
          disabled={currentPage >= totalPages}
          title="Trang cuối"
          style={{
            padding: '5px 8px',
            borderRadius: 6,
            border: '1px solid #cbd5e1',
            background: currentPage >= totalPages ? '#f1f5f9' : '#ffffff',
            color: currentPage >= totalPages ? '#94a3b8' : '#334155',
            cursor: currentPage >= totalPages ? 'not-allowed' : 'pointer',
            display: 'inline-flex',
            alignItems: 'center',
          }}
        >
          <ChevronsRight size={15} />
        </button>
      </div>
    </div>
  )
}
