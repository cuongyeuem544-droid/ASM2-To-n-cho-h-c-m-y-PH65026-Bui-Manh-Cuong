import React, { useEffect, useMemo, useState } from 'react'
import {
  AlertCircle,
  CalendarCheck,
  CheckCircle2,
  Edit,
  Eye,
  PauseCircle,
  PlayCircle,
  Plus,
  RefreshCw,
  Search,
  Sparkles,
  ThermometerSnowflake,
  Trash2,
  X,
} from 'lucide-react'
import { EmptyState } from '../components/EmptyState'
import { PaginationBar } from '../components/PaginationBar'
import { api } from '../services/api'

interface RecommendedProduct {
  id: number
  dbId: number
  name: string
  price: number
  dosage_form?: string
}

interface CampaignItem {
  id: number
  slug: string
  title: string
  disease_name: string
  season: string
  symptoms: string
  prevention: string
  status: 'ACTIVE' | 'PAUSED' | 'ENDED' | string
  banner_image_url?: string | null
  recommended_products: RecommendedProduct[]
  created_at: string
}

const SEASONS = [
  { value: 'MUA_MUA', label: 'Mùa Mưa (Ẩm Thấp, Dịch Muỗi)' },
  { value: 'DONG', label: 'Mùa Đông - Xuân (Hô Hấp, Cúm)' },
  { value: 'HA', label: 'Mùa Hè (Nắng Nóng, Điện Giải)' },
  { value: 'THU', label: 'Mùa Thu (Dị Ứng, Giao Mùa)' },
  { value: 'XUAN', label: 'Mùa Xuân' },
  { value: 'QUANH_NAM', label: 'Quanh Năm (Bệnh Mãn Tính)' },
]

export function CampaignsPage() {
  const [campaigns, setCampaigns] = useState<CampaignItem[]>([])
  const [loading, setLoading] = useState(true)
  const [statusFilter, setStatusFilter] = useState<string>('ALL')
  const [searchQuery, setSearchQuery] = useState('')
  const [notification, setNotification] = useState<{ type: 'success' | 'error'; message: string } | null>(null)

  // Modal State
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [editingCampaign, setEditingCampaign] = useState<CampaignItem | null>(null)
  const [modalTitle, setModalTitle] = useState('')
  const [diseaseName, setDiseaseName] = useState('')
  const [season, setSeason] = useState('MUA_MUA')
  const [symptoms, setSymptoms] = useState('')
  const [prevention, setPrevention] = useState('')
  const [productIdsStr, setProductIdsStr] = useState('')
  const [bannerUrl, setBannerUrl] = useState('')
  const [campaignStatus, setCampaignStatus] = useState('ACTIVE')
  const [saving, setSaving] = useState(false)
  const [formError, setFormError] = useState('')

  async function loadCampaigns() {
    setLoading(true)
    try {
      let url = '/admin/campaigns'
      if (statusFilter !== 'ALL') {
        url += `?status=${statusFilter}`
      }
      const data = await api<CampaignItem[]>(url)
      setCampaigns(data || [])
    } catch (err: any) {
      setNotification({
        type: 'error',
        message: err.message || 'Không thể tải danh sách chiến dịch',
      })
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadCampaigns()
  }, [statusFilter])

  function handleOpenCreate() {
    setEditingCampaign(null)
    setModalTitle('')
    setDiseaseName('')
    setSeason('MUA_MUA')
    setSymptoms('')
    setPrevention('')
    setProductIdsStr('')
    setBannerUrl('')
    setCampaignStatus('ACTIVE')
    setFormError('')
    setIsModalOpen(true)
  }

  function handleOpenEdit(c: CampaignItem) {
    setEditingCampaign(c)
    setModalTitle(c.title)
    setDiseaseName(c.disease_name)
    setSeason(c.season)
    setSymptoms(c.symptoms)
    setPrevention(c.prevention)
    setProductIdsStr(c.recommended_products.map((p) => p.id).join(', '))
    setBannerUrl(c.banner_image_url || '')
    setCampaignStatus(c.status)
    setFormError('')
    setIsModalOpen(true)
  }

  async function handleSaveCampaign(e: React.FormEvent) {
    e.preventDefault()
    setFormError('')

    if (!modalTitle.trim() || !diseaseName.trim() || !symptoms.trim() || !prevention.trim()) {
      setFormError('Vui lòng điền đầy đủ các thông tin chuyên đề y tế bắt buộc')
      return
    }

    // Parse product IDs
    const parsedIds: number[] = productIdsStr
      .split(',')
      .map((s) => parseInt(s.trim()))
      .filter((n) => !isNaN(n) && n > 0)

    setSaving(true)
    try {
      if (editingCampaign) {
        // Update
        await api(`/admin/campaigns/${editingCampaign.id}`, {
          method: 'PUT',
          body: JSON.stringify({
            title: modalTitle.trim(),
            disease_name: diseaseName.trim(),
            season,
            symptoms: symptoms.trim(),
            prevention: prevention.trim(),
            recommended_product_ids: parsedIds,
            status: campaignStatus,
            banner_image_url: bannerUrl.trim() || undefined,
          }),
        })
        setNotification({
          type: 'success',
          message: `Đã cập nhật chiến dịch "${modalTitle}" thành công`,
        })
      } else {
        // Create
        await api('/admin/campaigns', {
          method: 'POST',
          body: JSON.stringify({
            title: modalTitle.trim(),
            disease_name: diseaseName.trim(),
            season,
            symptoms: symptoms.trim(),
            prevention: prevention.trim(),
            recommended_product_ids: parsedIds,
            status: campaignStatus,
            banner_image_url: bannerUrl.trim() || undefined,
          }),
        })
        setNotification({
          type: 'success',
          message: `Đã khởi tạo chiến dịch cẩm nang "${modalTitle}" thành công`,
        })
      }
      setIsModalOpen(false)
      await loadCampaigns()
    } catch (err: any) {
      setFormError(err.message || 'Lỗi khi lưu chiến dịch')
    } finally {
      setSaving(false)
    }
  }

  async function handleToggleStatus(c: CampaignItem) {
    const nextStatus = c.status === 'ACTIVE' ? 'PAUSED' : 'ACTIVE'
    try {
      await api(`/admin/campaigns/${c.id}/status?status=${nextStatus}`, {
        method: 'PATCH',
      })
      setNotification({
        type: 'success',
        message: `Đã chuyển trạng thái chiến dịch #${c.id} sang ${nextStatus}`,
      })
      await loadCampaigns()
    } catch (err: any) {
      setNotification({
        type: 'error',
        message: err.message || 'Lỗi khi thay đổi trạng thái',
      })
    }
  }

  async function handleDelete(c: CampaignItem) {
    if (!window.confirm(`Bạn có chắc chắn muốn xóa chiến dịch "${c.title}"?`)) {
      return
    }

    try {
      await api(`/admin/campaigns/${c.id}`, { method: 'DELETE' })
      setNotification({
        type: 'success',
        message: `Đã xóa chiến dịch #${c.id}`,
      })
      await loadCampaigns()
    } catch (err: any) {
      setNotification({
        type: 'error',
        message: err.message || 'Lỗi khi xóa chiến dịch',
      })
    }
  }

  // Filtered by local search query
  const filteredCampaigns = campaigns.filter((c) => {
    if (!searchQuery.trim()) return true
    const q = searchQuery.toLowerCase()
    return (
      c.title.toLowerCase().includes(q) ||
      c.disease_name.toLowerCase().includes(q) ||
      c.slug.toLowerCase().includes(q)
    )
  })

  // Phân trang
  const [currentPage, setCurrentPage] = useState<number>(1)
  const [pageSize, setPageSize] = useState<number>(10)

  useEffect(() => {
    setCurrentPage(1)
  }, [statusFilter, searchQuery])

  const totalPages = Math.max(1, Math.ceil(filteredCampaigns.length / pageSize))
  const displayedCampaigns = useMemo(() => {
    const start = (currentPage - 1) * pageSize
    return filteredCampaigns.slice(start, start + pageSize)
  }, [filteredCampaigns, currentPage, pageSize])

  // Metrics
  const totalCount = campaigns.length
  const activeCount = campaigns.filter((c) => c.status === 'ACTIVE').length
  const pausedCount = campaigns.filter((c) => c.status === 'PAUSED').length

  return (
    <div className="page-container">
      {/* Header */}
      <div className="page-header">
        <div>
          <div className="breadcrumb">Hồ sơ & Bán hàng / Chiến dịch mùa bệnh</div>
          <h1 className="page-title">Chuyên Đề & Cẩm Nang Bệnh Theo Mùa</h1>
          <p className="page-subtitle">
            Quản trị cẩm nang dịch tễ, lời khuyên Dược sĩ GPP và thiết lập toa thuốc điều trị theo mùa trên Storefront.
          </p>
        </div>
        <div className="header-actions">
          <button
            className="button button-secondary"
            onClick={loadCampaigns}
            disabled={loading}
          >
            <RefreshCw size={16} className={loading ? 'spin' : ''} />
            Làm mới
          </button>
          <button className="button button-primary" onClick={handleOpenCreate}>
            <Plus size={16} />
            Tạo chiến dịch mới
          </button>
        </div>
      </div>

      {/* Notifications */}
      {notification && (
        <div className={`banner banner-${notification.type}`} style={{ marginBottom: '1.25rem' }}>
          {notification.type === 'success' ? <CheckCircle2 size={18} /> : <AlertCircle size={18} />}
          <span>{notification.message}</span>
          <button
            className="icon-button"
            onClick={() => setNotification(null)}
            style={{ marginLeft: 'auto' }}
          >
            ×
          </button>
        </div>
      )}

      {/* Metrics */}
      <div className="stats-grid" style={{ marginBottom: '1.5rem' }}>
        <div className="stat-card">
          <div className="stat-label">Tổng số chiến dịch</div>
          <div className="stat-value">{totalCount}</div>
          <div className="stat-help">Tất cả các mùa dịch bệnh</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Đang phát sóng (ACTIVE)</div>
          <div className="stat-value text-emerald-600">{activeCount}</div>
          <div className="stat-help">Hiển thị trực tiếp trang chủ</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Tạm dừng (PAUSED)</div>
          <div className="stat-value text-amber-600">{pausedCount}</div>
          <div className="stat-help">Chờ đến chu kỳ thời tiết</div>
        </div>
      </div>

      {/* Filters Toolbar */}
      <div className="toolbar" style={{ marginBottom: '1.25rem', display: 'flex', flexWrap: 'wrap', gap: '0.75rem', alignItems: 'center', justifyContent: 'space-between' }}>
        <div className="filter-group">
          <span className="filter-label">Trạng thái:</span>
          <div className="segmented-control">
            <button
              className={`segment-btn ${statusFilter === 'ALL' ? 'active' : ''}`}
              onClick={() => setStatusFilter('ALL')}
            >
              Tất cả ({totalCount})
            </button>
            <button
              className={`segment-btn ${statusFilter === 'ACTIVE' ? 'active' : ''}`}
              onClick={() => setStatusFilter('ACTIVE')}
            >
              Đang chạy ({activeCount})
            </button>
            <button
              className={`segment-btn ${statusFilter === 'PAUSED' ? 'active' : ''}`}
              onClick={() => setStatusFilter('PAUSED')}
            >
              Tạm dừng ({pausedCount})
            </button>
          </div>
        </div>

        <div className="search-box" style={{ maxWidth: '320px', width: '100%' }}>
          <Search size={16} />
          <input
            type="text"
            placeholder="Tìm theo tiêu đề, tên bệnh, slug..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>
      </div>

      {/* Campaigns Table */}
      <div className="card">
        {loading ? (
          <div className="card-loading">Đang tải danh sách chiến dịch…</div>
        ) : filteredCampaigns.length === 0 ? (
          <EmptyState
            title="Chưa có chiến dịch bệnh theo mùa nào"
            description="Bấm 'Tạo chiến dịch mới' để thiết lập cẩm nang sức khỏe cho khách hàng."
          />
        ) : (
          <div className="table-responsive">
            <table className="table">
              <thead>
                <tr>
                  <th style={{ width: '60px' }}>ID</th>
                  <th style={{ width: '260px' }}>Chiến dịch & Tên bệnh</th>
                  <th style={{ width: '150px' }}>Mùa áp dụng</th>
                  <th>Triệu chứng & Lời khuyên Dược sĩ</th>
                  <th style={{ width: '140px' }}>Thuốc chỉ định</th>
                  <th style={{ width: '120px' }}>Trạng thái</th>
                  <th style={{ width: '130px', textAlign: 'right' }}>Thao tác</th>
                </tr>
              </thead>
              <tbody>
                {displayedCampaigns.map((c) => (
                  <tr key={c.id}>
                    <td>
                      <span className="font-mono text-muted">#{c.id}</span>
                    </td>
                    <td>
                      <strong className="d-block text-truncate" style={{ maxWidth: '240px' }}>
                        {c.title}
                      </strong>
                      <div className="text-xs text-muted mt-0.5">
                        Bệnh: <span className="font-bold text-slate-800">{c.disease_name}</span>
                      </div>
                      <div className="text-xs font-mono text-muted">/{c.slug}</div>
                    </td>
                    <td>
                      <span className="tag tag-info" style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                        <ThermometerSnowflake size={12} />
                        {c.season}
                      </span>
                    </td>
                    <td>
                      <div style={{ fontSize: '0.82rem', lineHeight: '1.4' }}>
                        <strong className="text-amber-800">Triệu chứng: </strong>
                        <span className="text-muted line-clamp-1">{c.symptoms}</span>
                      </div>
                      <div style={{ fontSize: '0.82rem', lineHeight: '1.4', marginTop: '4px' }}>
                        <strong className="text-emerald-800">Phòng bệnh: </strong>
                        <span className="text-muted line-clamp-1">{c.prevention}</span>
                      </div>
                    </td>
                    <td>
                      <div className="font-bold">{c.recommended_products.length} sản phẩm</div>
                      {c.recommended_products.length > 0 && (
                        <div className="text-xs text-muted line-clamp-1">
                          {c.recommended_products.map((p) => p.name).join(', ')}
                        </div>
                      )}
                    </td>
                    <td>
                      {c.status === 'ACTIVE' ? (
                        <span className="badge badge-success">Đang kích hoạt</span>
                      ) : c.status === 'PAUSED' ? (
                        <span className="badge badge-warning">Tạm dừng</span>
                      ) : (
                        <span className="badge badge-secondary">{c.status}</span>
                      )}
                    </td>
                    <td style={{ textAlign: 'right' }}>
                      <div style={{ display: 'flex', gap: '6px', justifyContent: 'flex-end' }}>
                        <button
                          className="button button-xs button-secondary"
                          title={c.status === 'ACTIVE' ? 'Tạm dừng' : 'Kích hoạt'}
                          onClick={() => handleToggleStatus(c)}
                        >
                          {c.status === 'ACTIVE' ? <PauseCircle size={14} /> : <PlayCircle size={14} />}
                        </button>
                        <button
                          className="button button-xs button-secondary"
                          title="Chỉnh sửa"
                          onClick={() => handleOpenEdit(c)}
                        >
                          <Edit size={14} />
                        </button>
                        <button
                          className="button button-xs button-danger"
                          title="Xóa chiến dịch"
                          onClick={() => handleDelete(c)}
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {!loading && filteredCampaigns.length > 0 && (
          <PaginationBar
            currentPage={currentPage}
            totalPages={totalPages}
            pageSize={pageSize}
            totalItems={campaigns.length}
            filteredCount={filteredCampaigns.length}
            itemName="chiến dịch"
            onPageChange={setCurrentPage}
            onPageSizeChange={setPageSize}
            pageSizeOptions={[5, 10, 20, 50]}
          />
        )}
      </div>

      {/* Create / Edit Modal */}
      {isModalOpen && (
        <div className="modal-overlay">
          <div className="modal modal-md">
            <div className="modal-header">
              <h3>{editingCampaign ? 'Chỉnh sửa chiến dịch' : 'Tạo mới chiến dịch mùa bệnh'}</h3>
              <button
                className="icon-button"
                onClick={() => setIsModalOpen(false)}
                disabled={saving}
              >
                <X size={18} />
              </button>
            </div>

            <form onSubmit={handleSaveCampaign}>
              <div className="modal-body" style={{ maxHeight: '70vh', overflowY: 'auto' }}>
                {formError && (
                  <div className="banner banner-error" style={{ marginBottom: '1rem' }}>
                    <AlertCircle size={16} />
                    <span>{formError}</span>
                  </div>
                )}

                <div className="form-group">
                  <label className="form-label">
                    Tiêu đề chiến dịch <span className="text-danger">*</span>
                  </label>
                  <input
                    type="text"
                    className="form-input"
                    placeholder="VD: Phòng Ngừa & Chăm Sóc Sốt Xuất Huyết Mùa Mưa"
                    value={modalTitle}
                    onChange={(e) => setModalTitle(e.target.value)}
                    required
                  />
                </div>

                <div className="form-row" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                  <div className="form-group">
                    <label className="form-label">
                      Tên bệnh dịch tễ <span className="text-danger">*</span>
                    </label>
                    <input
                      type="text"
                      className="form-input"
                      placeholder="VD: Sốt Xuất Huyết Dengue"
                      value={diseaseName}
                      onChange={(e) => setDiseaseName(e.target.value)}
                      required
                    />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Mùa áp dụng</label>
                    <select
                      className="form-select"
                      value={season}
                      onChange={(e) => setSeason(e.target.value)}
                    >
                      {SEASONS.map((s) => (
                        <option key={s.value} value={s.value}>
                          {s.label}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                <div className="form-group">
                  <label className="form-label">
                    Triệu chứng nhận biết <span className="text-danger">*</span>
                  </label>
                  <textarea
                    rows={2}
                    className="form-input"
                    placeholder="VD: Sốt cao đột ngột từ 39-40°C, đau hốc mắt, nốt xuất huyết..."
                    value={symptoms}
                    onChange={(e) => setSymptoms(e.target.value)}
                    required
                  />
                </div>

                <div className="form-group">
                  <label className="form-label">
                    Lời khuyên phòng bệnh chuẩn GPP <span className="text-danger">*</span>
                  </label>
                  <textarea
                    rows={3}
                    className="form-input"
                    placeholder="VD: Dùng thuốc hạ sốt Paracetamol đúng liều, tuyệt đối không dùng Aspirin/Ibuprofen, bù điện giải Oresol..."
                    value={prevention}
                    onChange={(e) => setPrevention(e.target.value)}
                    required
                  />
                </div>

                <div className="form-group">
                  <label className="form-label">ID sản phẩm chỉ định (cách nhau dấu phẩy)</label>
                  <input
                    type="text"
                    className="form-input"
                    placeholder="VD: 72, 230, 43"
                    value={productIdsStr}
                    onChange={(e) => setProductIdsStr(e.target.value)}
                  />
                  <div className="form-help">
                    Nhập ID các sản phẩm thuốc trong hệ thống cần khuyến nghị đính kèm trong chuyên đề này.
                  </div>
                </div>

                <div className="form-row" style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '1rem' }}>
                  <div className="form-group">
                    <label className="form-label">URL Ảnh bìa (tùy chọn)</label>
                    <input
                      type="url"
                      className="form-input"
                      placeholder="https://..."
                      value={bannerUrl}
                      onChange={(e) => setBannerUrl(e.target.value)}
                    />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Trạng thái</label>
                    <select
                      className="form-select"
                      value={campaignStatus}
                      onChange={(e) => setCampaignStatus(e.target.value)}
                    >
                      <option value="ACTIVE">Kích hoạt (ACTIVE)</option>
                      <option value="PAUSED">Tạm dừng (PAUSED)</option>
                      <option value="ENDED">Kết thúc (ENDED)</option>
                    </select>
                  </div>
                </div>
              </div>

              <div className="modal-footer">
                <button
                  type="button"
                  className="button button-secondary"
                  onClick={() => setIsModalOpen(false)}
                  disabled={saving}
                >
                  Hủy
                </button>
                <button
                  type="submit"
                  className="button button-primary"
                  disabled={saving}
                >
                  {saving ? 'Đang lưu…' : editingCampaign ? 'Cập nhật' : 'Tạo mới'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
