import { useEffect, useMemo, useState } from 'react'
import {
  AlertCircle,
  CheckCircle2,
  Eye,
  EyeOff,
  MessageSquare,
  RefreshCw,
  ShieldCheck,
  Star,
  Trash2,
} from 'lucide-react'
import { AdminPageHeader } from '../components/AdminPageHeader'
import { StatCard, StatGrid } from '../components/StatCard'
import { FilterBar } from '../components/FilterBar'
import { StatusBadge } from '../components/StatusBadge'
import { ConfirmModal } from '../components/ConfirmModal'
import { EmptyState } from '../components/EmptyState'
import { PaginationBar } from '../components/PaginationBar'
import { api } from '../services/api'

interface ReviewItem {
  id: number
  canonical_product_id: number
  product_name: string
  customer_name: string
  rating: number
  comment: string
  is_verified_purchase: boolean
  is_approved: boolean
  order_code?: string | null
  created_at: string
}

export function ReviewsPage() {
  const [reviews, setReviews] = useState<ReviewItem[]>([])
  const [loading, setLoading] = useState(true)
  const [statusFilter, setStatusFilter] = useState<'ALL' | 'APPROVED' | 'HIDDEN'>('ALL')
  const [verifiedFilter, setVerifiedFilter] = useState<boolean | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [notification, setNotification] = useState<{ type: 'success' | 'error'; message: string } | null>(null)

  // Action states
  const [actionLoadingId, setActionLoadingId] = useState<number | null>(null)
  const [reviewToDelete, setReviewToDelete] = useState<ReviewItem | null>(null)
  const [isDeleting, setIsDeleting] = useState(false)

  async function loadReviews() {
    setLoading(true)
    try {
      let url = '/admin/reviews?limit=100'
      if (statusFilter === 'APPROVED') url += '&is_approved=true'
      if (statusFilter === 'HIDDEN') url += '&is_approved=false'
      if (verifiedFilter !== null) url += `&verified_only=${verifiedFilter}`

      const data = await api<ReviewItem[]>(url)
      setReviews(data || [])
    } catch (err: any) {
      setNotification({
        type: 'error',
        message: err.message || 'Không thể tải danh sách đánh giá',
      })
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadReviews()
  }, [statusFilter, verifiedFilter])

  async function handleToggleStatus(rev: ReviewItem) {
    setActionLoadingId(rev.id)
    try {
      await api(`/admin/reviews/${rev.id}/status`, {
        method: 'PATCH',
        body: JSON.stringify({ is_approved: !rev.is_approved }),
      })
      setNotification({
        type: 'success',
        message: !rev.is_approved
          ? `Đã duyệt hiển thị đánh giá #${rev.id}`
          : `Đã ẩn đánh giá #${rev.id} khỏi cửa hàng`,
      })
      await loadReviews()
    } catch (err: any) {
      setNotification({
        type: 'error',
        message: err.message || 'Lỗi khi cập nhật trạng thái đánh giá',
      })
    } finally {
      setActionLoadingId(null)
    }
  }

  async function confirmDeleteReview() {
    if (!reviewToDelete) return
    setIsDeleting(true)
    try {
      await api(`/admin/reviews/${reviewToDelete.id}`, { method: 'DELETE' })
      setNotification({
        type: 'success',
        message: `Đã xóa vĩnh viễn đánh giá #${reviewToDelete.id}`,
      })
      setReviewToDelete(null)
      await loadReviews()
    } catch (err: any) {
      setNotification({
        type: 'error',
        message: err.message || 'Lỗi khi xóa đánh giá',
      })
    } finally {
      setIsDeleting(false)
    }
  }

  // Filtered by local search query
  const filteredReviews = reviews.filter((r) => {
    if (!searchQuery.trim()) return true
    const q = searchQuery.toLowerCase()
    return (
      r.customer_name.toLowerCase().includes(q) ||
      r.product_name.toLowerCase().includes(q) ||
      (r.order_code && r.order_code.toLowerCase().includes(q)) ||
      r.comment.toLowerCase().includes(q)
    )
  })

  // Phân trang
  const [currentPage, setCurrentPage] = useState<number>(1)
  const [pageSize, setPageSize] = useState<number>(15)

  useEffect(() => {
    setCurrentPage(1)
  }, [statusFilter, verifiedFilter, searchQuery])

  const totalPages = Math.max(1, Math.ceil(filteredReviews.length / pageSize))
  const displayedReviews = useMemo(() => {
    const start = (currentPage - 1) * pageSize
    return filteredReviews.slice(start, start + pageSize)
  }, [filteredReviews, currentPage, pageSize])

  // Derived statistics
  const totalCount = reviews.length
  const approvedCount = reviews.filter((r) => r.is_approved).length
  const hiddenCount = reviews.filter((r) => !r.is_approved).length
  const verifiedCount = reviews.filter((r) => r.is_verified_purchase).length

  return (
    <div className="page">
      <AdminPageHeader
        title="Đánh giá & Nhận xét"
        eyebrow="HỒ SƠ & BÁN HÀNG • Kiểm duyệt phản hồi khách hàng"
        subtitle="Kiểm duyệt nội dung phản hồi khách hàng, xác thực đơn mua hàng chính hãng và nâng cao chất lượng dịch vụ GPP."
        badge={totalCount > 0 ? <span className="stat-card-badge">{totalCount} nhận xét</span> : undefined}
        actions={
          <button
            type="button"
            className="admin-button button-secondary"
            onClick={loadReviews}
            disabled={loading}
          >
            <RefreshCw size={14} className={loading ? 'spin' : ''} />
            <span>Làm mới dữ liệu</span>
          </button>
        }
      />

      {/* Notifications */}
      {notification && (
        <div
          className={`alert ${notification.type === 'success' ? 'alert-success' : 'alert-error'}`}
          style={{ marginBottom: '1.25rem' }}
        >
          {notification.type === 'success' ? <CheckCircle2 size={18} /> : <AlertCircle size={18} />}
          <span>{notification.message}</span>
          <button
            type="button"
            className="admin-icon-button"
            onClick={() => setNotification(null)}
            style={{ marginLeft: 'auto' }}
          >
            ×
          </button>
        </div>
      )}

      {/* Metric Cards */}
      <StatGrid columns={4}>
        <StatCard
          label="Tổng số nhận xét"
          value={totalCount}
          icon={MessageSquare}
          tone="blue"
          subtext="Toàn bộ phản hồi trên sàn"
          loading={loading}
        />
        <StatCard
          label="Đang hiển thị"
          value={approvedCount}
          icon={CheckCircle2}
          tone="emerald"
          subtext="Đã kiểm duyệt đạt chuẩn"
          loading={loading}
        />
        <StatCard
          label="Chờ duyệt / Đã ẩn"
          value={hiddenCount}
          icon={AlertCircle}
          tone={hiddenCount > 0 ? 'amber' : 'slate'}
          subtext="Cần xem xét nội dung"
          loading={loading}
        />
        <StatCard
          label="Đã mua hàng thật"
          value={verifiedCount}
          icon={ShieldCheck}
          tone="purple"
          subtext="Có mã đơn hàng hợp lệ"
          loading={loading}
        />
      </StatGrid>

      {/* Standardized FilterBar */}
      <FilterBar
        searchValue={searchQuery}
        onSearchChange={setSearchQuery}
        searchPlaceholder="Tìm theo tên thuốc, người gửi, mã đơn, nội dung..."
        totalCount={totalCount}
        filteredCount={filteredReviews.length}
        unitLabel="nhận xét"
        onRefresh={loadReviews}
        isRefreshing={loading}
      >
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          <button
            type="button"
            className={`admin-button ${statusFilter === 'ALL' ? 'button-primary' : 'button-secondary'}`}
            onClick={() => setStatusFilter('ALL')}
            style={{ fontSize: 12, padding: '5px 10px' }}
          >
            Tất cả ({totalCount})
          </button>
          <button
            type="button"
            className={`admin-button ${statusFilter === 'APPROVED' ? 'button-primary' : 'button-secondary'}`}
            onClick={() => setStatusFilter('APPROVED')}
            style={{ fontSize: 12, padding: '5px 10px' }}
          >
            Đang hiển thị ({approvedCount})
          </button>
          <button
            type="button"
            className={`admin-button ${statusFilter === 'HIDDEN' ? 'button-primary' : 'button-secondary'}`}
            onClick={() => setStatusFilter('HIDDEN')}
            style={{ fontSize: 12, padding: '5px 10px' }}
          >
            Đã ẩn ({hiddenCount})
          </button>
        </div>

        <select
          value={verifiedFilter === null ? 'ALL' : verifiedFilter ? 'VERIFIED' : 'UNVERIFIED'}
          onChange={(e) => {
            const v = e.target.value
            setVerifiedFilter(v === 'ALL' ? null : v === 'VERIFIED')
          }}
          style={{ minWidth: '150px' }}
        >
          <option value="ALL">Tất cả nguồn gửi</option>
          <option value="VERIFIED">Đã mua thật (Verified)</option>
          <option value="UNVERIFIED">Khách vãng lai</option>
        </select>
      </FilterBar>

      {/* Reviews Table */}
      <div className="admin-data-table-container">
        <div className="admin-table-wrap">
          <table className="admin-table">
            <thead>
              <tr>
                <th style={{ width: '80px' }}>ID</th>
                <th style={{ minWidth: '220px' }}>Sản phẩm</th>
                <th style={{ width: '180px' }}>Khách hàng</th>
                <th style={{ width: '110px' }}>Đánh giá</th>
                <th style={{ minWidth: '260px' }}>Nội dung nhận xét</th>
                <th style={{ width: '140px' }}>Trạng thái</th>
                <th style={{ width: '130px', textAlign: 'right' }}>Thao tác</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={7} style={{ padding: '40px 16px', textAlign: 'center', color: '#64748b' }}>
                    <RefreshCw size={20} className="spin" style={{ margin: '0 auto 8px', display: 'block' }} />
                    Đang tải dữ liệu nhận xét…
                  </td>
                </tr>
              ) : filteredReviews.length === 0 ? (
                <tr>
                  <td colSpan={7} style={{ padding: '40px 16px', textAlign: 'center' }}>
                    <EmptyState
                      title="Không có đánh giá nào phù hợp"
                      description="Hãy thử đổi bộ lọc trạng thái hoặc tìm kiếm từ khóa khác."
                    />
                  </td>
                </tr>
              ) : (
                displayedReviews.map((rev) => (
                  <tr key={rev.id}>
                    <td>
                      <span style={{ fontFamily: 'monospace', fontWeight: 700, color: '#64748b' }}>#{rev.id}</span>
                      <div style={{ fontSize: '11px', color: '#94a3b8', marginTop: '2px' }}>{rev.created_at}</div>
                    </td>
                    <td>
                      <strong style={{ display: 'block', color: '#0f172a', fontSize: '13px' }}>
                        {rev.product_name}
                      </strong>
                      <span style={{ fontSize: '11px', color: '#64748b' }}>Mã SP: #{rev.canonical_product_id}</span>
                    </td>
                    <td>
                      <div style={{ fontWeight: 700, color: '#0f172a', fontSize: '13px' }}>{rev.customer_name}</div>
                      {rev.is_verified_purchase ? (
                        <span
                          style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '3px',
                            background: '#ecfdf5',
                            color: '#065f46',
                            border: '1px solid #a7f3d0',
                            borderRadius: '4px',
                            padding: '1px 5px',
                            fontSize: '10.5px',
                            fontWeight: 700,
                            marginTop: '3px',
                          }}
                        >
                          <ShieldCheck size={11} />
                          Đã mua #{rev.order_code || 'GPP'}
                        </span>
                      ) : (
                        <span style={{ fontSize: '11px', color: '#94a3b8' }}>Khách vãng lai</span>
                      )}
                    </td>
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '3px' }}>
                        <span style={{ fontWeight: 800, color: '#d97706', fontSize: '13px' }}>{rev.rating}</span>
                        <Star size={14} style={{ fill: '#f59e0b', color: '#f59e0b' }} />
                      </div>
                    </td>
                    <td>
                      <p style={{ margin: 0, fontSize: '12.5px', lineHeight: 1.5, color: '#334155' }}>
                        {rev.comment}
                      </p>
                    </td>
                    <td>
                      <StatusBadge
                        value={rev.is_approved ? 'PUBLISHED' : 'DRAFT'}
                        tone={rev.is_approved ? 'success' : 'warning'}
                        showDot
                      />
                    </td>
                    <td style={{ textAlign: 'right' }}>
                      <div style={{ display: 'flex', gap: '6px', justifyContent: 'flex-end' }}>
                        <button
                          type="button"
                          className={`admin-button ${rev.is_approved ? 'button-secondary' : 'button-primary'}`}
                          style={{ padding: '4px 8px', fontSize: '11.5px' }}
                          title={rev.is_approved ? 'Ẩn khỏi cửa hàng' : 'Duyệt hiển thị'}
                          disabled={actionLoadingId === rev.id}
                          onClick={() => handleToggleStatus(rev)}
                        >
                          {rev.is_approved ? <EyeOff size={13} /> : <Eye size={13} />}
                          <span>{rev.is_approved ? 'Ẩn' : 'Duyệt'}</span>
                        </button>
                        <button
                          type="button"
                          className="admin-button button-danger"
                          style={{ padding: '4px 8px', fontSize: '11.5px' }}
                          title="Xóa vĩnh viễn"
                          disabled={actionLoadingId === rev.id}
                          onClick={() => setReviewToDelete(rev)}
                        >
                          <Trash2 size={13} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
        {!loading && filteredReviews.length > 0 && (
          <PaginationBar
            currentPage={currentPage}
            totalPages={totalPages}
            pageSize={pageSize}
            totalItems={reviews.length}
            filteredCount={filteredReviews.length}
            itemName="nhận xét"
            onPageChange={setCurrentPage}
            onPageSizeChange={setPageSize}
            pageSizeOptions={[10, 15, 25, 50]}
          />
        )}
      </div>

      {/* Clean Confirm Modal replacing window.confirm */}
      <ConfirmModal
        isOpen={!!reviewToDelete}
        title="Xóa đánh giá vĩnh viễn"
        message={
          reviewToDelete ? (
            <div>
              Bạn có chắc chắn muốn xóa vĩnh viễn đánh giá <strong>#{reviewToDelete.id}</strong> của khách hàng{' '}
              <strong>{reviewToDelete.customer_name}</strong> cho sản phẩm <strong>{reviewToDelete.product_name}</strong>?
              <div style={{ marginTop: '8px', color: '#dc2626', fontSize: '12px' }}>
                Hành động này không thể hoàn tác.
              </div>
            </div>
          ) : null
        }
        confirmLabel="Xác nhận xóa"
        cancelLabel="Hủy bỏ"
        tone="danger"
        isLoading={isDeleting}
        onConfirm={confirmDeleteReview}
        onClose={() => setReviewToDelete(null)}
      />
    </div>
  )
}
