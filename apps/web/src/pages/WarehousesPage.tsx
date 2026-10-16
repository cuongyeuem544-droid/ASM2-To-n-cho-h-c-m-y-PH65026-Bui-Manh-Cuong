import {
  AlertCircle,
  AlertTriangle,
  Building2,
  Calendar,
  CheckCircle2,
  Edit2,
  ExternalLink,
  Layers,
  MapPin,
  Package,
  Phone,
  Plus,
  RefreshCw,
  Search,
  ShieldCheck,
  Tag,
  Trash2,
  X,
} from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { EmptyState } from '../components/EmptyState'
import { api } from '../services/api'
import type { WarehouseItem } from '../types'

interface WarehouseStockDetailItem {
  stock_id: number
  product_id?: number | null
  product_name: string
  registration_number?: string | null
  dosage_form?: string | null
  package_description?: string | null
  manufacturer?: string | null
  rx_otc: string
  is_prescription: boolean
  rx_label: string
  sku_id: number
  sku_code: string
  uom: string
  price?: number | null
  batch_id: number
  batch_number: string
  manufacture_date?: string | null
  expiry_date: string
  days_remaining: number
  risk_level: 'CRITICAL' | 'WARNING' | 'SAFE'
  risk_label: string
  quantity_on_hand: number
  quantity_available: number
  quantity_reserved: number
  location_code: string
  location_name?: string | null
  batch_status: string
  supplier_name: string
}

interface WarehouseStockDetailResponse {
  warehouse: {
    id: number
    code: string
    name: string
    address: string
    district?: string
    province?: string
    phone?: string
    is_central: boolean
    is_active: boolean
  }
  stats: {
    total_products: number
    total_batches: number
    total_on_hand: number
    total_available: number
    total_reserved: number
    rx_count: number
    otc_count: number
    near_expiry_count: number
    expired_count: number
  }
  stocks: WarehouseStockDetailItem[]
}

export function WarehousesPage() {
  const [warehouses, setWarehouses] = useState<WarehouseItem[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [modalOpen, setModalOpen] = useState(false)
  const [editingWh, setEditingWh] = useState<WarehouseItem | null>(null)

  // Delete Warehouse State
  const [deletingWh, setDeletingWh] = useState<WarehouseItem | null>(null)
  const [isDeleting, setIsDeleting] = useState(false)
  const [deleteError, setDeleteError] = useState<string | null>(null)
  const [toastMessage, setToastMessage] = useState<string | null>(null)

  const handleDeleteWarehouse = async () => {
    if (!deletingWh) return
    try {
      setIsDeleting(true)
      setDeleteError(null)
      const res = await api.delete<{ success: boolean; message: string; action: string }>(
        `/warehouses/${deletingWh.id}`
      )
      setToastMessage(res.message || 'Thao tác xóa kho thành công')
      setDeletingWh(null)
      await loadWarehouses()
    } catch (err: any) {
      setDeleteError(err.message || 'Không thể xóa kho')
    } finally {
      setIsDeleting(false)
    }
  }

  // Warehouse Stocks Detail Modal State
  const [detailModalOpen, setDetailModalOpen] = useState(false)
  const [detailLoading, setDetailLoading] = useState(false)
  const [detailData, setDetailData] = useState<WarehouseStockDetailResponse | null>(null)
  const [detailTab, setDetailTab] = useState<'ALL' | 'RX' | 'OTC' | 'NEAR_EXPIRY'>('ALL')
  const [detailSearch, setDetailSearch] = useState('')
  const [detailPage, setDetailPage] = useState(1)
  const [detailPageSize, setDetailPageSize] = useState(25)

  // Form state
  const [code, setCode] = useState('')
  const [name, setName] = useState('')
  const [address, setAddress] = useState('')
  const [district, setDistrict] = useState('')
  const [province, setProvince] = useState('Thành phố Hồ Chí Minh')
  const [phone, setPhone] = useState('')
  const [isCentral, setIsCentral] = useState(false)
  const [isActive, setIsActive] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [formError, setFormError] = useState('')

  function loadWarehouses() {
    setLoading(true)
    api<WarehouseItem[]>('/warehouses')
      .then(res => {
        setWarehouses(res)
        setError('')
      })
      .catch(err => setError(err.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    loadWarehouses()
  }, [])

  async function openWarehouseDetail(wh: WarehouseItem) {
    setDetailModalOpen(true)
    setDetailLoading(true)
    setDetailData(null)
    setDetailTab('ALL')
    setDetailSearch('')
    setDetailPage(1)
    try {
      const data = await api<WarehouseStockDetailResponse>(`/warehouses/${wh.id}/stocks`)
      setDetailData(data)
    } catch (err: any) {
      setError(err.message || 'Không thể tải chi tiết tồn kho chi nhánh')
    } finally {
      setDetailLoading(false)
    }
  }

  const filteredStocks = useMemo(() => {
    if (!detailData || !detailData.stocks) return []
    const q = detailSearch.trim().toLowerCase()
    return detailData.stocks.filter((st) => {
      if (detailTab === 'RX' && !st.is_prescription) return false
      if (detailTab === 'OTC' && st.is_prescription) return false
      if (detailTab === 'NEAR_EXPIRY' && !(st.risk_level === 'CRITICAL' || st.risk_level === 'WARNING')) return false

      if (q) {
        const matchName = (st.product_name || '').toLowerCase().includes(q)
        const matchReg = (st.registration_number || '').toLowerCase().includes(q)
        const matchBatch = (st.batch_number || '').toLowerCase().includes(q)
        const matchMfr = (st.manufacturer || '').toLowerCase().includes(q)
        return matchName || matchReg || matchBatch || matchMfr
      }
      return true
    })
  }, [detailData, detailTab, detailSearch])

  const totalDetailPages = Math.max(1, Math.ceil(filteredStocks.length / detailPageSize))
  const paginatedStocks = useMemo(() => {
    const start = (detailPage - 1) * detailPageSize
    return filteredStocks.slice(start, start + detailPageSize)
  }, [filteredStocks, detailPage, detailPageSize])

  function openCreateModal() {
    setEditingWh(null)
    setCode('')
    setName('')
    setAddress('')
    setDistrict('')
    setProvince('Thành phố Hồ Chí Minh')
    setPhone('')
    setIsCentral(false)
    setIsActive(true)
    setFormError('')
    setModalOpen(true)
  }

  function openEditModal(wh: WarehouseItem) {
    setEditingWh(wh)
    setCode(wh.code)
    setName(wh.name)
    setAddress(wh.address)
    setDistrict(wh.district || '')
    setProvince(wh.province || 'Thành phố Hồ Chí Minh')
    setPhone(wh.phone || '')
    setIsCentral(wh.is_central)
    setIsActive(wh.is_active)
    setFormError('')
    setModalOpen(true)
  }

  async function handleSaveWarehouse(e: React.FormEvent) {
    e.preventDefault()
    setFormError('')
    if (!name.trim() || !address.trim() || (!editingWh && !code.trim())) {
      return setFormError('Vui lòng điền đầy đủ Mã kho, Tên kho và Địa chỉ chi nhánh.')
    }

    setSubmitting(true)
    try {
      if (editingWh) {
        await api(`/warehouses/${editingWh.id}`, {
          method: 'PUT',
          body: JSON.stringify({
            name: name.trim(),
            address: address.trim(),
            district: district.trim() || undefined,
            province: province.trim() || undefined,
            phone: phone.trim() || undefined,
            is_central: isCentral,
            is_active: isActive,
          }),
        })
      } else {
        await api('/warehouses', {
          method: 'POST',
          body: JSON.stringify({
            code: code.trim().toUpperCase(),
            name: name.trim(),
            address: address.trim(),
            district: district.trim() || undefined,
            province: province.trim() || undefined,
            phone: phone.trim() || undefined,
            is_central: isCentral,
            is_active: isActive,
          }),
        })
      }
      setModalOpen(false)
      loadWarehouses()
    } catch (err: any) {
      setFormError(err.message || 'Lỗi khi lưu thông tin kho')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="page">
      <div className="page-heading">
        <div>
          <span className="overline">MẠNG LƯỚI KHO VẬN DƯỢC GSP</span>
          <h1>Quản Lý Kho & Chi Nhánh</h1>
          <p>
            Quản lý kho trung tâm, các kho chi nhánh miền, sơ đồ phân bổ vị trí lưu trữ (Aisle/Shelf/Bin) và tồn kho thực tế.
          </p>
        </div>
        <div>
          <button className="primary-button" onClick={openCreateModal}>
            <Plus size={16} /> Thiết Lập Kho Mới
          </button>
        </div>
      </div>

      {toastMessage && (
        <div
          className="alert alert-success"
          style={{
            marginBottom: '16px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            background: '#ecfdf5',
            borderColor: '#a7f3d0',
            color: '#065f46',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <CheckCircle2 size={16} />
            <span>{toastMessage}</span>
          </div>
          <button
            className="icon-button"
            onClick={() => setToastMessage(null)}
            style={{ padding: '2px', color: '#065f46' }}
          >
            <X size={14} />
          </button>
        </div>
      )}

      {error && <div className="alert alert-error" style={{ marginBottom: '16px' }}>{error}</div>}

      {/* Warehouse Cards Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(380px, 1fr))', gap: '16px' }}>
        {warehouses.map((wh) => (
          <div
            key={wh.id}
            style={{
              background: '#ffffff',
              borderRadius: '14px',
              border: '1px solid #e2e8f0',
              padding: '20px',
              boxShadow: '0 2px 8px rgba(0,0,0,0.03)',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between',
            }}
          >
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '12px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <div
                    style={{
                      width: '42px',
                      height: '42px',
                      borderRadius: '10px',
                      background: wh.is_central ? '#eff6ff' : '#f8fafc',
                      color: wh.is_central ? '#2563eb' : '#475569',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      border: '1px solid #e2e8f0',
                    }}
                  >
                    <Building2 size={22} />
                  </div>
                  <div>
                    <h3 style={{ fontSize: '15px', fontWeight: 700, color: '#0f172a', margin: 0 }}>
                      {wh.name}
                    </h3>
                    <div style={{ display: 'flex', gap: '6px', alignItems: 'center', marginTop: '3px', flexWrap: 'wrap' }}>
                      <span style={{ fontSize: '11px', fontFamily: 'monospace', fontWeight: 600, color: '#64748b' }}>
                        {wh.code}
                      </span>
                      {wh.is_central && (
                        <span
                          style={{
                            fontSize: '10px',
                            fontWeight: 700,
                            background: '#dbeafe',
                            color: '#1d4ed8',
                            padding: '1px 6px',
                            borderRadius: '4px',
                          }}
                        >
                          Kho Tổng Trung Tâm
                        </span>
                      )}
                      {!wh.is_active && (
                        <span
                          style={{
                            fontSize: '10px',
                            fontWeight: 700,
                            background: '#fee2e2',
                            color: '#b91c1c',
                            padding: '1px 6px',
                            borderRadius: '4px',
                          }}
                        >
                          Ngừng hoạt động
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                <div style={{ display: 'flex', gap: '4px', alignItems: 'center' }}>
                  <button
                    className="icon-button"
                    title="Chỉnh sửa thông tin kho"
                    onClick={() => openEditModal(wh)}
                    style={{ padding: '6px' }}
                  >
                    <Edit2 size={15} />
                  </button>
                  <button
                    className="icon-button"
                    title="Xóa kho"
                    onClick={() => {
                      setDeletingWh(wh)
                      setDeleteError(null)
                    }}
                    style={{ padding: '6px', color: '#ef4444' }}
                  >
                    <Trash2 size={15} />
                  </button>
                </div>
              </div>

              {/* Address & Contact */}
              <div style={{ fontSize: '12px', color: '#475569', display: 'flex', flexDirection: 'column', gap: '6px', marginBottom: '16px' }}>
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: '6px' }}>
                  <MapPin size={14} style={{ color: '#94a3b8', flexShrink: 0, marginTop: '2px' }} />
                  <span>{wh.address}</span>
                </div>
                {wh.phone && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <Phone size={14} style={{ color: '#94a3b8', flexShrink: 0 }} />
                    <span>{wh.phone}</span>
                  </div>
                )}
              </div>

              {/* Inventory Statistics */}
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: '1fr 1fr',
                  gap: '8px',
                  background: '#f8fafc',
                  padding: '12px',
                  borderRadius: '10px',
                  marginBottom: '14px',
                }}
              >
                <div>
                  <div style={{ fontSize: '11px', color: '#64748b' }}>Tổng tồn thực tế (On-hand)</div>
                  <div style={{ fontSize: '16px', fontWeight: 800, color: '#0f172a' }}>
                    {(wh.total_on_hand ?? 0).toLocaleString()} <span style={{ fontSize: '11px', fontWeight: 500 }}>đơn vị</span>
                  </div>
                </div>
                <div>
                  <div style={{ fontSize: '11px', color: '#64748b' }}>Tồn khả dụng bán (Available)</div>
                  <div style={{ fontSize: '16px', fontWeight: 800, color: '#16a34a' }}>
                    {(wh.total_available ?? 0).toLocaleString()} <span style={{ fontSize: '11px', fontWeight: 500 }}>đơn vị</span>
                  </div>
                </div>
              </div>

              {/* Storage Locations / Shelves */}
              <div style={{ fontSize: '11px', color: '#64748b', marginBottom: '6px' }}>
                Vị trí lưu kho ({wh.locations.length} khu vực):
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                {wh.locations.map(loc => (
                  <span
                    key={loc.id}
                    title={loc.name || loc.code}
                    style={{
                      background: '#ffffff',
                      border: '1px solid #cbd5e1',
                      borderRadius: '6px',
                      padding: '2px 7px',
                      fontSize: '11px',
                      fontFamily: 'monospace',
                      color: '#334155',
                    }}
                  >
                    {loc.code}
                  </span>
                ))}
              </div>
            </div>

            {/* Status footer & Detail Action */}
            <div
              style={{
                marginTop: '16px',
                paddingTop: '12px',
                borderTop: '1px solid #f1f5f9',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                flexWrap: 'wrap',
                gap: '8px',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px' }}>
                <span
                  style={{
                    width: '8px',
                    height: '8px',
                    borderRadius: '50%',
                    background: wh.is_active ? '#22c55e' : '#94a3b8',
                  }}
                />
                <span style={{ color: wh.is_active ? '#166534' : '#64748b', fontWeight: 600 }}>
                  {wh.is_active ? 'Đang hoạt động' : 'Tạm dừng tiếp nhận'}
                </span>
              </div>

              <button
                type="button"
                className="button button-primary"
                onClick={() => openWarehouseDetail(wh)}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '6px',
                  fontSize: '12.5px',
                  fontWeight: 700,
                  padding: '6px 14px',
                  background: '#0284c7',
                }}
              >
                <Package size={14} /> Xem chi tiết thuốc & hạn dùng
              </button>
            </div>
          </div>
        ))}
      </div>

      {warehouses.length === 0 && !loading && (
        <EmptyState title="Chưa có kho nào được thiết lập" description="Bấm nút Thiết Lập Kho Mới để tạo kho trung tâm đầu tiên." />
      )}

      {/* Modal Create / Edit */}
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
              maxWidth: '520px',
              width: '100%',
              padding: '24px',
              boxShadow: '0 10px 25px rgba(0,0,0,0.15)',
            }}
            onClick={e => e.stopPropagation()}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <h2 style={{ fontSize: '18px', fontWeight: 800, margin: 0, color: '#0f172a' }}>
                {editingWh ? `Chỉnh Sửa Kho: ${editingWh.code}` : 'Thiết Lập Kho & Chi Nhánh Mới'}
              </h2>
              <button className="icon-button" onClick={() => setModalOpen(false)}>
                <X size={18} />
              </button>
            </div>

            {formError && <div className="alert alert-error" style={{ marginBottom: '12px' }}>{formError}</div>}

            <form onSubmit={handleSaveWarehouse} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div>
                <label style={{ fontSize: '12px', fontWeight: 600, color: '#334155', display: 'block', marginBottom: '4px' }}>
                  Mã kho (Code) *
                </label>
                <input
                  disabled={!!editingWh}
                  placeholder="Ví dụ: KHO-DN-01, KHO-CT-01"
                  value={code}
                  onChange={e => setCode(e.target.value.toUpperCase())}
                  style={{ width: '100%', padding: '8px 12px', borderRadius: '8px', border: '1px solid #cbd5e1' }}
                  required
                />
              </div>

              <div>
                <label style={{ fontSize: '12px', fontWeight: 600, color: '#334155', display: 'block', marginBottom: '4px' }}>
                  Tên kho / Chi nhánh *
                </label>
                <input
                  placeholder="Ví dụ: Kho Chi Nhánh Miền Trung (Đà Nẵng)"
                  value={name}
                  onChange={e => setName(e.target.value)}
                  style={{ width: '100%', padding: '8px 12px', borderRadius: '8px', border: '1px solid #cbd5e1' }}
                  required
                />
              </div>

              <div>
                <label style={{ fontSize: '12px', fontWeight: 600, color: '#334155', display: 'block', marginBottom: '4px' }}>
                  Địa chỉ số nhà & đường *
                </label>
                <input
                  placeholder="Số nhà, tên đường, phường..."
                  value={address}
                  onChange={e => setAddress(e.target.value)}
                  style={{ width: '100%', padding: '8px 12px', borderRadius: '8px', border: '1px solid #cbd5e1' }}
                  required
                />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                <div>
                  <label style={{ fontSize: '12px', fontWeight: 600, color: '#334155', display: 'block', marginBottom: '4px' }}>
                    Quận / Huyện
                  </label>
                  <input
                    placeholder="Quận 1, Hoàn Kiếm..."
                    value={district}
                    onChange={e => setDistrict(e.target.value)}
                    style={{ width: '100%', padding: '8px 12px', borderRadius: '8px', border: '1px solid #cbd5e1' }}
                  />
                </div>
                <div>
                  <label style={{ fontSize: '12px', fontWeight: 600, color: '#334155', display: 'block', marginBottom: '4px' }}>
                    Tỉnh / Thành phố
                  </label>
                  <input
                    placeholder="TP. Hồ Chí Minh, Hà Nội..."
                    value={province}
                    onChange={e => setProvince(e.target.value)}
                    style={{ width: '100%', padding: '8px 12px', borderRadius: '8px', border: '1px solid #cbd5e1' }}
                  />
                </div>
              </div>

              <div>
                <label style={{ fontSize: '12px', fontWeight: 600, color: '#334155', display: 'block', marginBottom: '4px' }}>
                  Điện thoại liên hệ
                </label>
                <input
                  placeholder="Số hotline hoặc bàn kho..."
                  value={phone}
                  onChange={e => setPhone(e.target.value)}
                  style={{ width: '100%', padding: '8px 12px', borderRadius: '8px', border: '1px solid #cbd5e1' }}
                />
              </div>

              <div style={{ display: 'flex', gap: '20px', marginTop: '6px' }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '13px', cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={isCentral}
                    onChange={e => setIsCentral(e.target.checked)}
                  />
                  Là Kho Tổng Trung Tâm
                </label>
                <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '13px', cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={isActive}
                    onChange={e => setIsActive(e.target.checked)}
                  />
                  Đang hoạt động tiếp nhận
                </label>
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
                  {submitting ? 'Đang lưu…' : editingWh ? 'Cập Nhật Kho' : 'Khởi Tạo Kho'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
      {/* Delete Warehouse Confirmation Modal */}
      {deletingWh && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(15, 23, 42, 0.6)',
            backdropFilter: 'blur(4px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 200,
            padding: '16px',
          }}
          onClick={() => !isDeleting && setDeletingWh(null)}
        >
          <div
            style={{
              background: '#ffffff',
              borderRadius: '16px',
              maxWidth: '480px',
              width: '100%',
              padding: '24px',
              boxShadow: '0 10px 25px rgba(0,0,0,0.15)',
            }}
            onClick={e => e.stopPropagation()}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <div style={{ width: '36px', height: '36px', borderRadius: '10px', background: '#fee2e2', color: '#ef4444', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <Trash2 size={20} />
                </div>
                <h2 style={{ fontSize: '18px', fontWeight: 800, margin: 0, color: '#0f172a' }}>
                  Xác Nhận Xóa Kho
                </h2>
              </div>
              <button
                className="icon-button"
                onClick={() => !isDeleting && setDeletingWh(null)}
                disabled={isDeleting}
              >
                <X size={18} />
              </button>
            </div>

            {deleteError && (
              <div className="alert alert-error" style={{ marginBottom: '14px', fontSize: '13px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <AlertCircle size={16} style={{ flexShrink: 0 }} />
                <span>{deleteError}</span>
              </div>
            )}

            <div style={{ fontSize: '14px', color: '#334155', lineHeight: 1.6, marginBottom: '16px' }}>
              Bạn có chắc chắn muốn xóa kho <strong>{deletingWh.name}</strong> (<code>{deletingWh.code}</code>)?
            </div>

            <div style={{ background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: '10px', padding: '12px 14px', fontSize: '12.5px', color: '#475569', marginBottom: '20px', lineHeight: 1.5 }}>
              <div style={{ fontWeight: 700, color: '#0f172a', marginBottom: '6px' }}>Quy tắc bảo toàn dữ liệu:</div>
              <ul style={{ margin: 0, paddingLeft: '18px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                <li>Nếu kho mới tạo và chưa phát sinh dữ liệu: Hệ thống sẽ <strong>xóa vĩnh viễn</strong> khỏi cơ sở dữ liệu.</li>
                <li>Nếu kho đã có tồn kho, đơn hàng hoặc lịch sử giao dịch: Hệ thống sẽ chuyển sang trạng thái <strong>Ngừng hoạt động</strong> để bảo toàn toàn vẹn dữ liệu kế toán và loại bỏ khỏi hệ thống điều phối đơn mới.</li>
              </ul>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
              <button
                type="button"
                className="secondary-button"
                onClick={() => setDeletingWh(null)}
                disabled={isDeleting}
              >
                Hủy bỏ
              </button>
              <button
                type="button"
                className="primary-button"
                onClick={handleDeleteWarehouse}
                disabled={isDeleting}
                style={{ background: '#ef4444', borderColor: '#ef4444' }}
              >
                {isDeleting ? 'Đang xử lý…' : 'Xác nhận xóa'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal View Warehouse Stock & Medicine Details */}
      {detailModalOpen && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(15, 23, 42, 0.6)',
            backdropFilter: 'blur(4px)',
            zIndex: 150,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '20px',
          }}
          onClick={() => setDetailModalOpen(false)}
        >
          <div
            style={{
              background: '#ffffff',
              borderRadius: '16px',
              maxWidth: '1150px',
              width: '100%',
              maxHeight: '92vh',
              display: 'flex',
              flexDirection: 'column',
              boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.25)',
              overflow: 'hidden',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div
              style={{
                padding: '20px 24px',
                borderBottom: '1px solid #e2e8f0',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                background: '#f8fafc',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <div
                  style={{
                    width: '42px',
                    height: '42px',
                    borderRadius: '10px',
                    background: detailData?.warehouse.is_central ? '#dbeafe' : '#e0e7ff',
                    color: detailData?.warehouse.is_central ? '#1d4ed8' : '#4338ca',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >
                  <Building2 size={24} />
                </div>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <h2 style={{ margin: 0, fontSize: '18px', fontWeight: 800, color: '#0f172a' }}>
                      {detailData ? detailData.warehouse.name : 'Chi Tiết Tồn Kho Chi Nhánh'}
                    </h2>
                    {detailData && (
                      <span
                        style={{
                          fontSize: '11px',
                          fontWeight: 700,
                          padding: '2px 8px',
                          borderRadius: '6px',
                          background: detailData.warehouse.is_central ? '#dbeafe' : '#f1f5f9',
                          color: detailData.warehouse.is_central ? '#1d4ed8' : '#475569',
                          border: '1px solid #cbd5e1',
                        }}
                      >
                        {detailData.warehouse.code} {detailData.warehouse.is_central ? '• KHO TỔNG' : ''}
                      </span>
                    )}
                  </div>
                  {detailData && (
                    <p style={{ margin: '4px 0 0', fontSize: '12.5px', color: '#64748b' }}>
                      <MapPin size={13} style={{ display: 'inline', marginRight: '4px', verticalAlign: '-1px' }} />
                      {detailData.warehouse.address}
                      {detailData.warehouse.phone ? ` • SĐT: ${detailData.warehouse.phone}` : ''}
                    </p>
                  )}
                </div>
              </div>

              <button
                type="button"
                className="icon-button"
                onClick={() => setDetailModalOpen(false)}
                style={{ padding: '8px', borderRadius: '8px' }}
              >
                <X size={20} />
              </button>
            </div>

            {/* Modal Body */}
            <div style={{ padding: '20px 24px', overflowY: 'auto', flex: 1 }}>
              {detailLoading ? (
                <div style={{ textAlign: 'center', padding: '60px 0', color: '#64748b' }}>
                  <RefreshCw size={28} className="spin" style={{ margin: '0 auto 12px', display: 'block', color: '#0284c7' }} />
                  <span>Đang tải thông tin mặt hàng thuốc và hạn dùng...</span>
                </div>
              ) : !detailData ? (
                <div style={{ textAlign: 'center', padding: '40px 0', color: '#ef4444' }}>
                  Không tải được dữ liệu tồn kho. Vui lòng thử lại.
                </div>
              ) : (
                <>
                  {/* Stats Metric Cards */}
                  <div
                    style={{
                      display: 'grid',
                      gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
                      gap: '12px',
                      marginBottom: '20px',
                    }}
                  >
                    <div style={{ background: '#eff6ff', padding: '12px 14px', borderRadius: '10px', border: '1px solid #bfdbfe' }}>
                      <span style={{ fontSize: '11.5px', color: '#1e40af', fontWeight: 700, display: 'block' }}>MẶT HÀNG THUỐC</span>
                      <strong style={{ fontSize: '22px', color: '#1d4ed8' }}>{detailData.stats.total_products}</strong>
                      <span style={{ fontSize: '11px', color: '#3b82f6', display: 'block', marginTop: '2px' }}>danh mục SKU</span>
                    </div>

                    <div style={{ background: '#f0fdf4', padding: '12px 14px', borderRadius: '10px', border: '1px solid #bbf7d0' }}>
                      <span style={{ fontSize: '11.5px', color: '#166534', fontWeight: 700, display: 'block' }}>TỒN THỰC TẾ (ON-HAND)</span>
                      <strong style={{ fontSize: '22px', color: '#16a34a' }}>{(detailData.stats?.total_on_hand ?? 0).toLocaleString('vi-VN')}</strong>
                      <span style={{ fontSize: '11px', color: '#22c55e', display: 'block', marginTop: '2px' }}>đơn vị thuốc</span>
                    </div>

                    <div style={{ background: '#faf5ff', padding: '12px 14px', borderRadius: '10px', border: '1px solid #e9d5ff' }}>
                      <span style={{ fontSize: '11.5px', color: '#6b21a8', fontWeight: 700, display: 'block' }}>TỔNG SỐ LÔ HÀNG</span>
                      <strong style={{ fontSize: '22px', color: '#7e22ce' }}>{detailData.stats.total_batches}</strong>
                      <span style={{ fontSize: '11px', color: '#9333ea', display: 'block', marginTop: '2px' }}>lô theo dõi FEFO</span>
                    </div>

                    <div style={{ background: '#fff1f2', padding: '12px 14px', borderRadius: '10px', border: '1px solid #fecdd3' }}>
                      <span style={{ fontSize: '11.5px', color: '#9f1239', fontWeight: 700, display: 'block' }}>THUỐC KÊ ĐƠN (Rx)</span>
                      <strong style={{ fontSize: '22px', color: '#be123c' }}>{detailData.stats.rx_count}</strong>
                      <span style={{ fontSize: '11px', color: '#e11d48', display: 'block', marginTop: '2px' }}>cần toa bác sĩ</span>
                    </div>

                    <div style={{ background: '#f0fdfa', padding: '12px 14px', borderRadius: '10px', border: '1px solid #99f6e4' }}>
                      <span style={{ fontSize: '11.5px', color: '#115e59', fontWeight: 700, display: 'block' }}>THUỐC KHÔNG KÊ ĐƠN (OTC)</span>
                      <strong style={{ fontSize: '22px', color: '#0f766e' }}>{detailData.stats.otc_count}</strong>
                      <span style={{ fontSize: '11px', color: '#14b8a6', display: 'block', marginTop: '2px' }}>mở bán tự do</span>
                    </div>

                    <div style={{ background: '#fefce8', padding: '12px 14px', borderRadius: '10px', border: '1px solid #fef08a' }}>
                      <span style={{ fontSize: '11.5px', color: '#854d0e', fontWeight: 700, display: 'block' }}>CẬN HẠN & HẾT HẠN</span>
                      <strong style={{ fontSize: '22px', color: detailData.stats.near_expiry_count > 0 ? '#b45309' : '#16a34a' }}>
                        {detailData.stats.near_expiry_count}
                      </strong>
                      <span style={{ fontSize: '11px', color: '#ca8a04', display: 'block', marginTop: '2px' }}>lô cần ưu tiên xuất</span>
                    </div>
                  </div>

                  {/* Filter Toolbar (Tabs & Search) */}
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      flexWrap: 'wrap',
                      gap: '12px',
                      marginBottom: '14px',
                      background: '#f8fafc',
                      padding: '10px 14px',
                      borderRadius: '8px',
                      border: '1px solid #e2e8f0',
                    }}
                  >
                    <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                      <button
                        type="button"
                        onClick={() => { setDetailTab('ALL'); setDetailPage(1); }}
                        style={{
                          padding: '6px 12px',
                          borderRadius: '6px',
                          border: detailTab === 'ALL' ? '1px solid #0284c7' : '1px solid #cbd5e1',
                          background: detailTab === 'ALL' ? '#0284c7' : '#ffffff',
                          color: detailTab === 'ALL' ? '#ffffff' : '#334155',
                          fontWeight: detailTab === 'ALL' ? 700 : 500,
                          fontSize: '12.5px',
                          cursor: 'pointer',
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '6px',
                        }}
                      >
                        <span>Tất cả</span>
                        <span style={{ background: detailTab === 'ALL' ? 'rgba(255,255,255,0.25)' : '#e2e8f0', color: detailTab === 'ALL' ? '#ffffff' : '#1e293b', borderRadius: 999, padding: '1px 7px', fontSize: '11px', fontWeight: 700 }}>
                          {detailData.stocks.length}
                        </span>
                      </button>

                      <button
                        type="button"
                        onClick={() => { setDetailTab('RX'); setDetailPage(1); }}
                        style={{
                          padding: '6px 12px',
                          borderRadius: '6px',
                          border: detailTab === 'RX' ? '1px solid #be123c' : '1px solid #cbd5e1',
                          background: detailTab === 'RX' ? '#be123c' : '#ffffff',
                          color: detailTab === 'RX' ? '#ffffff' : '#334155',
                          fontWeight: detailTab === 'RX' ? 700 : 500,
                          fontSize: '12.5px',
                          cursor: 'pointer',
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '6px',
                        }}
                      >
                        <span>Thuốc kê đơn (Rx)</span>
                        <span style={{ background: detailTab === 'RX' ? 'rgba(255,255,255,0.25)' : '#ffe4e6', color: detailTab === 'RX' ? '#ffffff' : '#9f1239', borderRadius: 999, padding: '1px 7px', fontSize: '11px', fontWeight: 700 }}>
                          {detailData.stats.rx_count}
                        </span>
                      </button>

                      <button
                        type="button"
                        onClick={() => { setDetailTab('OTC'); setDetailPage(1); }}
                        style={{
                          padding: '6px 12px',
                          borderRadius: '6px',
                          border: detailTab === 'OTC' ? '1px solid #0f766e' : '1px solid #cbd5e1',
                          background: detailTab === 'OTC' ? '#0f766e' : '#ffffff',
                          color: detailTab === 'OTC' ? '#ffffff' : '#334155',
                          fontWeight: detailTab === 'OTC' ? 700 : 500,
                          fontSize: '12.5px',
                          cursor: 'pointer',
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '6px',
                        }}
                      >
                        <span>Thuốc OTC</span>
                        <span style={{ background: detailTab === 'OTC' ? 'rgba(255,255,255,0.25)' : '#ccfbf1', color: detailTab === 'OTC' ? '#ffffff' : '#115e59', borderRadius: 999, padding: '1px 7px', fontSize: '11px', fontWeight: 700 }}>
                          {detailData.stats.otc_count}
                        </span>
                      </button>

                      <button
                        type="button"
                        onClick={() => { setDetailTab('NEAR_EXPIRY'); setDetailPage(1); }}
                        style={{
                          padding: '6px 12px',
                          borderRadius: '6px',
                          border: detailTab === 'NEAR_EXPIRY' ? '1px solid #d97706' : '1px solid #cbd5e1',
                          background: detailTab === 'NEAR_EXPIRY' ? '#d97706' : '#ffffff',
                          color: detailTab === 'NEAR_EXPIRY' ? '#ffffff' : '#334155',
                          fontWeight: detailTab === 'NEAR_EXPIRY' ? 700 : 500,
                          fontSize: '12.5px',
                          cursor: 'pointer',
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '6px',
                        }}
                      >
                        <span>Cận hạn / Hết hạn</span>
                        <span style={{ background: detailTab === 'NEAR_EXPIRY' ? 'rgba(255,255,255,0.25)' : '#fef3c7', color: detailTab === 'NEAR_EXPIRY' ? '#ffffff' : '#b45309', borderRadius: 999, padding: '1px 7px', fontSize: '11px', fontWeight: 700 }}>
                          {detailData.stats.near_expiry_count}
                        </span>
                      </button>
                    </div>

                    <div style={{ position: 'relative', minWidth: '260px' }}>
                      <Search size={14} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: '#94a3b8' }} />
                      <input
                        type="text"
                        placeholder="Tìm tên thuốc, SĐK, số lô..."
                        value={detailSearch}
                        onChange={(e) => { setDetailSearch(e.target.value); setDetailPage(1); }}
                        style={{ width: '100%', padding: '6px 28px 6px 30px', borderRadius: '6px', border: '1px solid #cbd5e1', fontSize: '12.5px', background: '#ffffff' }}
                      />
                      {detailSearch && (
                        <button
                          type="button"
                          onClick={() => setDetailSearch('')}
                          style={{ position: 'absolute', right: 8, top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', cursor: 'pointer', color: '#94a3b8' }}
                        >
                          <X size={13} />
                        </button>
                      )}
                    </div>
                  </div>

                  {/* Stocks Table */}
                  <div
                    style={{
                      maxHeight: '420px',
                      overflowY: 'auto',
                      overflowX: 'auto',
                      border: '1px solid #e2e8f0',
                      borderTopLeftRadius: '8px',
                      borderTopRightRadius: '8px',
                      position: 'relative',
                    }}
                  >
                    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12.5px' }}>
                      <thead style={{ position: 'sticky', top: 0, zIndex: 5, background: '#f8fafc', boxShadow: '0 1px 2px rgba(0,0,0,0.06)' }}>
                        <tr style={{ borderBottom: '1px solid #e2e8f0', color: '#475569', textAlign: 'left' }}>
                          <th style={{ padding: '9px 12px' }}>#</th>
                          <th style={{ padding: '9px 12px' }}>Tên thuốc & Dạng bào chế</th>
                          <th style={{ padding: '9px 12px' }}>Phân loại</th>
                          <th style={{ padding: '9px 12px' }}>Số đăng ký</th>
                          <th style={{ padding: '9px 12px' }}>Số lô</th>
                          <th style={{ padding: '9px 12px' }}>Hạn dùng (FEFO)</th>
                          <th style={{ padding: '9px 12px' }}>Vị trí lưu</th>
                          <th style={{ padding: '9px 12px', textAlign: 'right' }}>Tồn thực tế</th>
                          <th style={{ padding: '9px 12px', textAlign: 'right' }}>Khả dụng</th>
                          <th style={{ padding: '9px 12px', textAlign: 'center' }}>Trạng thái</th>
                        </tr>
                      </thead>
                      <tbody>
                        {paginatedStocks.length === 0 ? (
                          <tr>
                            <td colSpan={10} style={{ textAlign: 'center', padding: '36px 16px', color: '#64748b' }}>
                              Không có thuốc nào phù hợp với bộ lọc trong kho này.
                            </td>
                          </tr>
                        ) : (
                          paginatedStocks.map((st, idx) => (
                            <tr key={st.stock_id} style={{ borderBottom: '1px solid #f1f5f9' }}>
                              <td style={{ padding: '8px 12px', color: '#64748b' }}>
                                #{(detailPage - 1) * detailPageSize + idx + 1}
                              </td>
                              <td style={{ padding: '8px 12px' }}>
                                <div style={{ fontWeight: 700, color: '#0f172a' }}>{st.product_name}</div>
                                <div style={{ fontSize: '11px', color: '#64748b', marginTop: '2px' }}>
                                  {st.dosage_form || '—'} {st.package_description ? `• ${st.package_description}` : ''}
                                </div>
                              </td>
                              <td style={{ padding: '8px 12px' }}>
                                <span
                                  style={{
                                    fontSize: '11px',
                                    fontWeight: 700,
                                    padding: '2px 7px',
                                    borderRadius: '4px',
                                    background: st.is_prescription ? '#ffe4e6' : '#ccfbf1',
                                    color: st.is_prescription ? '#be123c' : '#0f766e',
                                  }}
                                >
                                  {st.rx_label}
                                </span>
                              </td>
                              <td style={{ padding: '8px 12px' }}>
                                <code style={{ fontFamily: 'monospace', color: '#0369a1', fontSize: '12px' }}>
                                  {st.registration_number || '—'}
                                </code>
                              </td>
                              <td style={{ padding: '8px 12px' }}>
                                <span style={{ fontFamily: 'monospace', fontWeight: 600, color: '#334155' }}>
                                  {st.batch_number}
                                </span>
                              </td>
                              <td style={{ padding: '8px 12px' }}>
                                <span
                                  style={{
                                    fontWeight: 700,
                                    padding: '2px 7px',
                                    borderRadius: '4px',
                                    fontSize: '11.5px',
                                    background:
                                      st.risk_level === 'CRITICAL'
                                        ? '#fee2e2'
                                        : st.risk_level === 'WARNING'
                                        ? '#fef3c7'
                                        : '#dcfce7',
                                    color:
                                      st.risk_level === 'CRITICAL'
                                        ? '#b91c1c'
                                        : st.risk_level === 'WARNING'
                                        ? '#b45309'
                                        : '#15803d',
                                  }}
                                >
                                  {st.expiry_date}
                                </span>
                                <div style={{ fontSize: '10.5px', color: '#64748b', marginTop: '2px' }}>
                                  {st.risk_label}
                                </div>
                              </td>
                              <td style={{ padding: '8px 12px' }}>
                                <code style={{ fontSize: '11.5px', background: '#f1f5f9', padding: '2px 6px', borderRadius: '4px' }}>
                                  {st.location_code}
                                </code>
                              </td>
                              <td style={{ padding: '8px 12px', textAlign: 'right', fontWeight: 700, color: '#0f172a' }}>
                                {(st.quantity_on_hand ?? 0).toLocaleString('vi-VN')} {st.uom}
                              </td>
                              <td style={{ padding: '8px 12px', textAlign: 'right', fontWeight: 700, color: '#16a34a' }}>
                                {(st.quantity_available ?? 0).toLocaleString('vi-VN')}
                              </td>
                              <td style={{ padding: '8px 12px', textAlign: 'center' }}>
                                <span
                                  style={{
                                    fontSize: '11px',
                                    fontWeight: 600,
                                    padding: '2px 6px',
                                    borderRadius: '4px',
                                    background: st.batch_status === 'ACTIVE' ? '#f0fdf4' : '#fef2f2',
                                    color: st.batch_status === 'ACTIVE' ? '#166534' : '#b91c1c',
                                  }}
                                >
                                  {st.batch_status}
                                </span>
                              </td>
                            </tr>
                          ))
                        )}
                      </tbody>
                    </table>
                  </div>

                  {/* Pagination footer */}
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      flexWrap: 'wrap',
                      gap: '12px',
                      padding: '10px 14px',
                      background: '#f8fafc',
                      borderTop: '1px solid #e2e8f0',
                      borderBottomLeftRadius: '8px',
                      borderBottomRightRadius: '8px',
                      fontSize: '12.5px',
                    }}
                  >
                    <span style={{ color: '#64748b' }}>
                      Hiển thị <strong>{filteredStocks.length === 0 ? 0 : (detailPage - 1) * detailPageSize + 1} - {Math.min(detailPage * detailPageSize, filteredStocks.length)}</strong> trên tổng <strong>{filteredStocks.length.toLocaleString('vi-VN')}</strong> lô thuốc
                    </span>

                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <button
                        type="button"
                        onClick={() => setDetailPage(p => Math.max(1, p - 1))}
                        disabled={detailPage <= 1}
                        className="button button-secondary"
                        style={{ padding: '4px 10px', fontSize: '12px' }}
                      >
                        Trước
                      </button>
                      <span style={{ fontWeight: 600, padding: '0 6px' }}>
                        Trang {detailPage} / {totalDetailPages}
                      </span>
                      <button
                        type="button"
                        onClick={() => setDetailPage(p => Math.min(totalDetailPages, p + 1))}
                        disabled={detailPage >= totalDetailPages}
                        className="button button-secondary"
                        style={{ padding: '4px 10px', fontSize: '12px' }}
                      >
                        Sau
                      </button>
                    </div>
                  </div>
                </>
              )}
            </div>

            {/* Modal Footer */}
            <div
              style={{
                padding: '14px 24px',
                borderTop: '1px solid #e2e8f0',
                background: '#f8fafc',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                flexWrap: 'wrap',
                gap: '12px',
              }}
            >
              <div style={{ fontSize: '12.5px', color: '#64748b' }}>
                Hệ thống tự động đồng bộ tồn kho thực tế và áp dụng nguyên tắc quản lý thuốc FEFO (Hết hạn trước - Xuất trước).
              </div>
              <div style={{ display: 'flex', gap: '10px' }}>
                {detailData && (
                  <Link
                    to={`/inventory/batches?warehouse_id=${detailData.warehouse.id}`}
                    className="button button-secondary"
                    style={{ textDecoration: 'none', fontSize: '12.5px', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: '6px' }}
                  >
                    <Layers size={14} /> Quản lý lô tại trang Lô thuốc
                  </Link>
                )}
                <Link
                  to="/imports"
                  className="button button-primary"
                  style={{ textDecoration: 'none', fontSize: '12.5px', fontWeight: 700, display: 'inline-flex', alignItems: 'center', gap: '6px', background: '#16a34a' }}
                >
                  <Package size={14} /> Nhập thêm thuốc vào kho này
                </Link>
                <button
                  type="button"
                  className="button button-secondary"
                  onClick={() => setDetailModalOpen(false)}
                  style={{ fontSize: '12.5px' }}
                >
                  Đóng
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
