import { Check, CheckCheck, CheckCircle2, FileSearch, RefreshCw, X } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { EmptyState } from '../components/EmptyState'
import { StatusBadge } from '../components/StatusBadge'
import { PaginationBar } from '../components/PaginationBar'
import { api } from '../services/api'

interface Candidate {
  id: number
  observed_name: string
  registration_number_text: string | null
  manufacturer_text: string | null
  extraction_confidence: number
  extraction_method: string
  processing_status: string
  canonical_product_id: number | null
  created_at: string
}

export function CandidatesPage() {
  const [items, setItems] = useState<Candidate[]>([])
  const [status, setStatus] = useState('')
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [loading, setLoading] = useState(false)
  const [actionId, setActionId] = useState<number | null>(null)

  function loadCandidates() {
    setLoading(true)
    api<Candidate[]>(`/candidates${status ? `?status=${status}` : ''}`)
      .then(setItems)
      .catch(err => setError(err.message))
      .finally(() => setLoading(false))
  }

  // Phân trang
  const [currentPage, setCurrentPage] = useState<number>(1)
  const [pageSize, setPageSize] = useState<number>(15)

  useEffect(() => {
    setCurrentPage(1)
  }, [status])

  const totalPages = Math.max(1, Math.ceil(items.length / pageSize))
  const displayedCandidates = useMemo(() => {
    const start = (currentPage - 1) * pageSize
    return items.slice(start, start + pageSize)
  }, [items, currentPage, pageSize])

  useEffect(() => {
    loadCandidates()
  }, [status])

  async function handleApprove(id: number) {
    setActionId(id)
    setError('')
    try {
      const res = await api<{ message: string; product_id?: number }>(`/candidates/${id}/approve`, {
        method: 'POST',
      })
      setSuccess(res.message || 'Đã duyệt thuốc vào kho thành công!')
      loadCandidates()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Lỗi khi duyệt thuốc')
    } finally {
      setActionId(null)
    }
  }

  async function handleReject(id: number) {
    if (!confirm('Bạn có chắc chắn muốn từ chối bản ghi này?')) return
    setActionId(id)
    setError('')
    try {
      const res = await api<{ message: string }>(`/candidates/${id}/reject`, {
        method: 'POST',
      })
      setSuccess(res.message || 'Đã từ chối bản ghi')
      loadCandidates()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Lỗi khi từ chối')
    } finally {
      setActionId(null)
    }
  }

  async function handleApproveAll() {
    const pendingCount = items.filter(i => ['EXTRACTED', 'REVIEW_REQUIRED', 'NEW'].includes(i.processing_status)).length
    if (pendingCount === 0) {
      alert('Không có bản ghi nào đang chờ duyệt.')
      return
    }
    if (!confirm(`Bạn có chắc chắn muốn duyệt tất cả ${pendingCount} thuốc đang chờ vào kho chính thức?`)) return

    setLoading(true)
    setError('')
    try {
      const res = await api<{ message: string; approved_count: number }>('/candidates/approve-all', {
        method: 'POST',
      })
      setSuccess(res.message || 'Đã duyệt toàn bộ thuốc vào kho thành công!')
      loadCandidates()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Lỗi khi duyệt tất cả')
    } finally {
      setLoading(false)
    }
  }

  const pendingCount = items.filter(i => ['EXTRACTED', 'REVIEW_REQUIRED', 'NEW'].includes(i.processing_status)).length

  return (
    <div className="page">
      <div className="page-heading" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <span className="overline">KHU VỰC CHỜ DUYỆT</span>
          <h1>Thuốc Chờ Duyệt (Dữ Liệu Mới)</h1>
          <p>Danh sách thuốc vừa được thu thập hoặc nhập từ tệp Excel/CSV, chờ đối soát và duyệt nhập kho.</p>
        </div>

        <div style={{ display: 'flex', gap: '10px' }}>
          <button
            className="secondary-button"
            onClick={loadCandidates}
            disabled={loading}
            style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}
          >
            <RefreshCw size={16} className={loading ? 'animate-spin' : ''} /> Làm mới
          </button>

          {pendingCount > 0 && (
            <button
              className="primary-button"
              onClick={handleApproveAll}
              disabled={loading}
              style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', background: '#16a34a' }}
            >
              <CheckCheck size={18} /> Duyệt tất cả ({pendingCount}) vào kho
            </button>
          )}
        </div>
      </div>

      <div className="toolbar" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div className="filter-label"><FileSearch size={17} /> Trạng thái xử lý:</div>
          <select value={status} onChange={e => setStatus(e.target.value)}>
            <option value="">Tất cả trạng thái</option>
            <option value="EXTRACTED">Mới thu thập / Chờ duyệt</option>
            <option value="MATCHED">Đã khớp / Đã duyệt vào kho</option>
            <option value="REVIEW_REQUIRED">Cần kiểm tra</option>
            <option value="REJECTED">Đã từ chối</option>
          </select>
        </div>

        <span style={{ fontSize: '0.875rem', color: '#64748b' }}>
          Tổng cộng: <strong>{items.length}</strong> bản ghi (<strong>{pendingCount}</strong> chờ duyệt)
        </span>
      </div>

      {success && (
        <div className="alert alert-success" style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
          <CheckCircle2 size={18} />
          <span>{success}</span>
        </div>
      )}

      {error && (
        <div className="alert alert-error" style={{ marginBottom: '16px' }}>
          {error}
        </div>
      )}

      {!items.length ? (
        <EmptyState
          title="Chưa có dữ liệu chờ duyệt"
          description="Hãy tải lên tệp Excel (.xlsx) danh sách thuốc hoặc chạy thu thập tự động để bắt đầu."
        />
      ) : (
        <div className="panel table-wrap">
          <table>
            <thead>
              <tr>
                <th style={{ width: '60px' }}>Mã</th>
                <th>Tên thuốc thu thập</th>
                <th>Số đăng ký</th>
                <th>Nhà sản xuất</th>
                <th>Nguồn lấy</th>
                <th>Độ tin cậy</th>
                <th>Trạng thái</th>
                <th style={{ width: '170px', textAlign: 'center' }}>Thao tác</th>
              </tr>
            </thead>
            <tbody>
              {displayedCandidates.map(item => {
                const isPending = ['EXTRACTED', 'REVIEW_REQUIRED', 'NEW'].includes(item.processing_status)
                const isMatched = item.processing_status === 'MATCHED'
                const isBusy = actionId === item.id

                return (
                  <tr key={item.id}>
                    <td>#{item.id}</td>
                    <td>
                      <strong>{item.observed_name}</strong>
                    </td>
                    <td><code>{item.registration_number_text || '—'}</code></td>
                    <td>{item.manufacturer_text || '—'}</td>
                    <td><code>{item.extraction_method}</code></td>
                    <td>
                      <div className="confidence-bar">
                        <i style={{ width: `${item.extraction_confidence * 100}%` }} />
                      </div>
                      {Math.round(item.extraction_confidence * 100)}%
                    </td>
                    <td><StatusBadge value={item.processing_status} /></td>
                    <td style={{ textAlign: 'center' }}>
                      {isPending && (
                        <div style={{ display: 'flex', gap: '6px', justifyContent: 'center' }}>
                          <button
                            type="button"
                            className="button"
                            onClick={() => handleApprove(item.id)}
                            disabled={isBusy}
                            style={{
                              background: '#16a34a',
                              color: '#fff',
                              border: 'none',
                              padding: '4px 10px',
                              borderRadius: '4px',
                              fontSize: '0.8rem',
                              cursor: 'pointer',
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '4px',
                            }}
                            title="Duyệt vào kho chính thức"
                          >
                            <Check size={14} /> {isBusy ? '...' : 'Duyệt'}
                          </button>
                          <button
                            type="button"
                            className="button"
                            onClick={() => handleReject(item.id)}
                            disabled={isBusy}
                            style={{
                              background: '#fee2e2',
                              color: '#b91c1c',
                              border: '1px solid #fca5a5',
                              padding: '4px 8px',
                              borderRadius: '4px',
                              fontSize: '0.8rem',
                              cursor: 'pointer',
                              display: 'inline-flex',
                              alignItems: 'center',
                            }}
                            title="Từ chối bản ghi"
                          >
                            <X size={14} />
                          </button>
                        </div>
                      )}

                      {isMatched && (
                        <Link
                          to="/products"
                          style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '4px',
                            color: '#16a34a',
                            fontWeight: 600,
                            fontSize: '0.85rem',
                            textDecoration: 'none',
                          }}
                        >
                          <CheckCircle2 size={16} /> Trong kho
                        </Link>
                      )}

                      {item.processing_status === 'REJECTED' && (
                        <span style={{ color: '#94a3b8', fontSize: '0.85rem' }}>Đã từ chối</span>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
          {!loading && items.length > 0 && (
            <PaginationBar
              currentPage={currentPage}
              totalPages={totalPages}
              pageSize={pageSize}
              totalItems={items.length}
              itemName="bản ghi"
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
