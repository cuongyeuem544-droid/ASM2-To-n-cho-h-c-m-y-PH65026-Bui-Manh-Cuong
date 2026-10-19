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
  Clock,
} from 'lucide-react'
import { AdminPageHeader } from '../components/AdminPageHeader'
import { StatCard, StatGrid } from '../components/StatCard'
import { FilterBar } from '../components/FilterBar'
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
    <div className="page-container" style={{ padding: '24px 32px' }}>
      {/* Header */}
      <AdminPageHeader
        title="Chuyên Đề & Cẩm Nang Bệnh Theo Mùa"
        eyebrow="HỒ SƠ & BÁN HÀNG • Quản trị dịch tễ & phác đồ GPP"
        subtitle="Quản trị cẩm nang dịch tễ, lời khuyên Dược sĩ GPP và thiết lập toa thuốc điều trị theo mùa trên Storefront."
        badge={
          <span className="stat-card-badge" style={{ background: '#e0f2fe', color: '#0369a1' }}>
            <ThermometerSnowflake size={12} /> {totalCount} chuyên đề
          </span>
        }
        actions={
          <div style={{ display: 'flex', gap: '8px' }}>
            <button
              type="button"
              className="admin-button button-secondary"
              onClick={loadCampaigns}
              disabled={loading}
              title="Làm mới danh sách"
            >
              <RefreshCw size={14} className={loading ? 'spin' : ''} />
              Làm mới
            </button>
            <button
              type="button"
              className="admin-button button-primary"
              onClick={handleOpenCreate}
            >
              <Plus size={14} />
              Tạo chiến dịch mới
            </button>
          </div>
        }
      />

      {/* Notifications */}
      {notification && (
        <div className={`banner banner-${notification.type}`} style={{ marginBottom: '1.25rem' }}>
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

      {/* Metrics */}
      <StatGrid columns={3}>
        <StatCard
          label="Tổng số chiến dịch"
          value={totalCount}
          icon={ThermometerSnowflake}
          tone="blue"
          subtext="Tất cả các mùa dịch bệnh"
          loading={loading}
        />
        <StatCard
          label="Đang phát sóng (ACTIVE)"
          value={activeCount}
          icon={CheckCircle2}
          tone="emerald"
          subtext="Hiển thị trực tiếp trang chủ"
          loading={loading}
        />
        <StatCard
          label="Tạm dừng (PAUSED)"
          value={pausedCount}
          icon={Clock}
          tone={pausedCount > 0 ? 'amber' : 'slate'}
          subtext="Chờ đến chu kỳ thời tiết"
          loading={loading}
        />
      </StatGrid>

      {/* Filters Toolbar */}
      <FilterBar
        searchValue={searchQuery}
        onSearchChange={setSearchQuery}
        searchPlaceholder="Tìm theo tiêu đề, tên bệnh, slug..."
        totalCount={totalCount}
        filteredCount={filteredCampaigns.length}
        unitLabel="chiến dịch"
        onRefresh={loadCampaigns}
        isRefreshing={loading}
      >
        <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
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
            className={`admin-button ${statusFilter === 'ACTIVE' ? 'button-primary' : 'button-secondary'}`}
            onClick={() => setStatusFilter('ACTIVE')}
            style={{ fontSize: 12, padding: '5px 10px' }}
          >
            Đang chạy ({activeCount})
          </button>
          <button
            type="button"
            className={`admin-button ${statusFilter === 'PAUSED' ? 'button-primary' : 'button-secondary'}`}
            onClick={() => setStatusFilter('PAUSED')}
            style={{ fontSize: 12, padding: '5px 10px' }}
          >
            Tạm dừng ({pausedCount})
          </button>
        </div>
      </FilterBar>

      {/* Campaigns Table */}
      <div className="admin-data-table-container">
        <div className="admin-table-wrap">
          <table className="admin-table">
            <thead>
              <tr>
                <th style={{ width: '70px' }}>ID</th>
                <th style={{ minWidth: '240px' }}>Chiến dịch & Tên bệnh</th>
                <th style={{ width: '160px' }}>Mùa áp dụng</th>
                <th style={{ minWidth: '300px' }}>Triệu chứng & Lời khuyên Dược sĩ</th>
                <th style={{ width: '150px' }}>Thuốc chỉ định</th>
                <th style={{ width: '130px' }}>Trạng thái</th>
                <th style={{ width: '140px', textAlign: 'right' }}>Thao tác</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={7} style={{ padding: '40px 16px', textAlign: 'center', color: '#64748b' }}>
                    <RefreshCw size={20} className="spin" style={{ margin: '0 auto 8px', display: 'block' }} />
                    Đang tải danh sách chiến dịch…
                  </td>
                </tr>
              ) : filteredCampaigns.length === 0 ? (
                <tr>
                  <td colSpan={7} style={{ padding: '40px 16px', textAlign: 'center' }}>
                    <EmptyState
                      title="Chưa có chiến dịch bệnh theo mùa nào"
                      description="Bấm 'Tạo chiến dịch mới' để thiết lập cẩm nang sức khỏe cho khách hàng."
                    />
                  </td>
                </tr>
              ) : (
                displayedCampaigns.map((c) => (
                  <tr key={c.id}>
                    <td>
                      <span style={{ fontFamily: 'monospace', fontWeight: 700, color: '#64748b' }}>#{c.id}</span>
                    </td>
                    <td>
                      <strong className="d-block line-clamp-2" style={{ maxWidth: '240px', color: '#0f172a', fontSize: '13px' }} title={c.title}>
                        {c.title}
                      </strong>
                      <div style={{ fontSize: '12px', color: '#475569', marginTop: '2px' }} className="line-clamp-1" title={c.disease_name}>
                        Bệnh: <span style={{ fontWeight: 700, color: '#0f172a' }}>{c.disease_name}</span>
                      </div>
                      <div style={{ fontSize: '11px', fontFamily: 'monospace', color: '#0284c7', marginTop: '1px' }} className="text-truncate" title={`/${c.slug}`}>/{c.slug}</div>
                    </td>
                    <td>
                      <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', padding: '4px 8px', borderRadius: '6px', fontSize: '11.5px', fontWeight: 600, background: '#eff6ff', color: '#1d4ed8', border: '1px solid #bfdbfe' }}>
                        <ThermometerSnowflake size={12} />
                        {SEASONS.find(s => s.value === c.season)?.label.split(' (')[0] || c.season}
                      </span>
                    </td>
                    <td style={{ maxWidth: '340px' }}>
                      <div style={{ fontSize: '12px', lineHeight: '1.45' }}>
                        <strong style={{ color: '#b45309' }}>Triệu chứng: </strong>
                        <span style={{ color: '#334155' }} className="line-clamp-2" title={c.symptoms}>{c.symptoms}</span>
                      </div>
                      <div style={{ fontSize: '12px', lineHeight: '1.45', marginTop: '4px' }}>
                        <strong style={{ color: '#15803d' }}>Phòng bệnh: </strong>
                        <span style={{ color: '#334155' }} className="line-clamp-2" title={c.prevention}>{c.prevention}</span>
                      </div>
                    </td>
                    <td>
                      <div style={{ fontWeight: 700, fontSize: '12.5px', color: '#0f172a' }}>{c.recommended_products.length} sản phẩm</div>
                      {c.recommended_products.length > 0 && (
                        <div style={{ fontSize: '11px', color: '#64748b', marginTop: '2px' }} className="line-clamp-1" title={c.recommended_products.map((p) => p.name).join(', ')}>
                          {c.recommended_products.map((p) => p.name).join(', ')}
                        </div>
                      )}
                    </td>
                    <td>
                      {c.status === 'ACTIVE' ? (
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', padding: '3px 8px', borderRadius: '6px', fontSize: '11px', fontWeight: 700, background: '#dcfce7', color: '#15803d' }}>
                          <CheckCircle2 size={12} /> Đang chạy
                        </span>
                      ) : c.status === 'PAUSED' ? (
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', padding: '3px 8px', borderRadius: '6px', fontSize: '11px', fontWeight: 700, background: '#fef3c7', color: '#b45309' }}>
                          <PauseCircle size={12} /> Tạm dừng
                        </span>
                      ) : (
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', padding: '3px 8px', borderRadius: '6px', fontSize: '11px', fontWeight: 700, background: '#f1f5f9', color: '#64748b' }}>
                          {c.status}
                        </span>
                      )}
                    </td>
                    <td style={{ textAlign: 'right' }}>
                      <div style={{ display: 'flex', gap: '6px', justifyContent: 'flex-end' }}>
                        <button
                          type="button"
                          className="admin-button button-secondary"
                          style={{ padding: '4px 8px', fontSize: '11.5px' }}
                          title={c.status === 'ACTIVE' ? 'Tạm dừng chiến dịch' : 'Kích hoạt chiến dịch'}
                          onClick={() => handleToggleStatus(c)}
                        >
                          {c.status === 'ACTIVE' ? <PauseCircle size={13} /> : <PlayCircle size={13} />}
                        </button>
                        <button
                          type="button"
                          className="admin-button button-secondary"
                          style={{ padding: '4px 8px', fontSize: '11.5px' }}
                          title="Chỉnh sửa chiến dịch"
                          onClick={() => handleOpenEdit(c)}
                        >
                          <Edit size={13} />
                        </button>
                        <button
                          type="button"
                          className="admin-button button-danger"
                          style={{ padding: '4px 8px', fontSize: '11.5px' }}
                          title="Xóa chiến dịch"
                          onClick={() => handleDelete(c)}
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
        {!loading && filteredCampaigns.length > 0 && (
          <PaginationBar
            currentPage={currentPage}
            totalPages={totalPages}
            pageSize={pageSize}
            totalItems={filteredCampaigns.length}
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

                <div className="form-row" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1rem' }}>
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

                <div className="form-row" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem' }}>
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

              <div className="modal-footer" style={{ padding: '14px 24px', background: '#f8fafc', borderTop: '1px solid #e2e8f0', display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
                <button
                  type="button"
                  className="admin-button button-secondary"
                  onClick={() => setIsModalOpen(false)}
                  disabled={saving}
                >
                  Hủy
                </button>
                <button
                  type="submit"
                  className="admin-button button-primary"
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
