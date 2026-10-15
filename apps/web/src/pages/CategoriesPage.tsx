import {
  Boxes,
  ChevronDown,
  ChevronRight,
  Edit2,
  FolderTree,
  Layers,
  Plus,
  RefreshCw,
  Trash2,
  AlertCircle,
  CheckCircle2,
} from 'lucide-react'
import { useEffect, useState } from 'react'
import { AdminPageHeader } from '../components/AdminPageHeader'
import { api } from '../services/api'

interface SubCategoryItem {
  id: string
  dbId: number
  code: string
  name: string
  slug: string
  isPopular?: boolean
  badge?: string
  sortOrder: number
  productCount: number
}

interface CategoryRoot {
  id: string
  dbId: number
  code: string
  name: string
  slug: string
  categoryKind: string
  allowedProductType?: string
  iconName?: string
  badge?: string
  description?: string
  productCount: number
  subCategories: SubCategoryItem[]
}

export function CategoriesPage() {
  const [tree, setTree] = useState<CategoryRoot[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [expanded, setExpanded] = useState<Record<number, boolean>>({ 1: true, 2: true, 3: true, 4: true, 5: true, 6: true })

  // Modal create subcategory
  const [showAddModal, setShowAddModal] = useState(false)
  const [parentTarget, setParentTarget] = useState<CategoryRoot | null>(null)
  const [newCode, setNewCode] = useState('')
  const [newSlug, setNewSlug] = useState('')
  const [newName, setNewName] = useState('')
  const [newBadge, setNewBadge] = useState('')
  const [saving, setSaving] = useState(false)

  const loadTree = () => {
    setLoading(true)
    api<CategoryRoot[]>('/admin/categories/tree')
      .then(res => {
        setTree(res)
        setError('')
      })
      .catch(err => setError(err.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    loadTree()
  }, [])

  const toggleExpand = (id: number) => {
    setExpanded(prev => ({ ...prev, [id]: !prev[id] }))
  }

  const handleOpenAdd = (parent: CategoryRoot) => {
    setParentTarget(parent)
    setNewCode(`SUB_${parent.code.replace('CAT_', '')}_`)
    setNewSlug('')
    setNewName('')
    setNewBadge('')
    setShowAddModal(true)
  }

  const handleCreateSubcategory = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!parentTarget || !newCode.trim() || !newSlug.trim() || !newName.trim()) return

    setSaving(true)
    setError('')
    try {
      await api('/admin/categories', {
        method: 'POST',
        body: JSON.stringify({
          parent_id: parentTarget.dbId,
          code: newCode.trim(),
          slug: newSlug.trim(),
          name: newName.trim(),
          badge: newBadge.trim() || undefined,
          allowed_product_type: parentTarget.allowedProductType,
        }),
      })
      setSuccess(`Đã tạo mới danh mục con "${newName}" thành công!`)
      setShowAddModal(false)
      loadTree()
      setTimeout(() => setSuccess(''), 4000)
    } catch (err: any) {
      setError(err.message || 'Lỗi tạo danh mục con')
    } finally {
      setSaving(false)
    }
  }

  const handleDeleteCategory = async (catId: number, name: string) => {
    if (!window.confirm(`Bạn có chắc muốn xóa danh mục "${name}"? Thao tác này chỉ thành công nếu danh mục không có sản phẩm liên kết.`)) {
      return
    }

    try {
      await api(`/admin/categories/${catId}`, { method: 'DELETE' })
      setSuccess(`Đã xóa danh mục "${name}" thành công!`)
      loadTree()
      setTimeout(() => setSuccess(''), 4000)
    } catch (err: any) {
      setError(err.message || 'Không thể xóa danh mục')
    }
  }

  return (
    <div className="page">
      <AdminPageHeader
        title="Cây danh mục dược phẩm chuẩn"
        eyebrow="HỒ SƠ & BÁN HÀNG • Danh mục phân cấp 6 nhóm"
        subtitle="Quản trị cấu trúc cây danh mục bán hàng Storefront, đồng bộ phân loại y tế pháp lý và số lượng sản phẩm thực tế."
        badge={<span className="stat-card-badge">{tree.length} nhóm lớn</span>}
        actions={
          <button className="admin-button button-secondary" onClick={loadTree} disabled={loading}>
            <RefreshCw size={14} className={loading ? 'spin' : ''} /> Làm mới
          </button>
        }
      />

      {error && <div className="alert alert-error" style={{ marginBottom: '16px' }}>{error}</div>}
      {success && <div className="alert alert-success" style={{ marginBottom: '16px' }}><CheckCircle2 size={16} /> {success}</div>}

      <div style={{ display: 'grid', gap: '16px' }}>
        {tree.map(root => {
          const isExp = expanded[root.dbId] ?? true
          return (
            <div
              key={root.dbId}
              style={{
                background: '#fff',
                border: '1px solid #e2e8f0',
                borderRadius: '14px',
                overflow: 'hidden',
                boxShadow: '0 1px 3px rgba(0,0,0,0.03)',
              }}
            >
              {/* Header của Nhóm lớn */}
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '16px 20px',
                  background: '#f8fafc',
                  borderBottom: isExp ? '1px solid #e2e8f0' : 'none',
                  cursor: 'pointer',
                }}
                onClick={() => toggleExpand(root.dbId)}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <button
                    style={{ background: 'transparent', border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center' }}
                  >
                    {isExp ? <ChevronDown size={18} color="#64748b" /> : <ChevronRight size={18} color="#64748b" />}
                  </button>
                  <div style={{ width: '34px', height: '34px', borderRadius: '10px', background: '#e0f2fe', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#0369a1', fontWeight: 700 }}>
                    <Layers size={18} />
                  </div>
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span style={{ fontSize: '15px', fontWeight: 700, color: '#0f172a' }}>{root.name}</span>
                      <code style={{ fontSize: '11px', background: '#e2e8f0', padding: '2px 6px', borderRadius: '6px', color: '#475569' }}>
                        {root.slug}
                      </code>
                      {root.badge && (
                        <span style={{ fontSize: '10px', fontWeight: 700, background: '#cffafe', color: '#0e7490', padding: '2px 8px', borderRadius: '999px' }}>
                          {root.badge}
                        </span>
                      )}
                    </div>
                    <p style={{ margin: '2px 0 0 0', fontSize: '12px', color: '#64748b' }}>
                      {root.description || 'Nhóm sản phẩm cấp 1'} • Loại pháp lý: <strong>{root.allowedProductType || 'Đa loại (Mẹ & Bé)'}</strong>
                    </p>
                  </div>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }} onClick={e => e.stopPropagation()}>
                  <span style={{ fontSize: '13px', fontWeight: 600, color: '#0369a1', background: '#f0f9ff', padding: '4px 12px', borderRadius: '999px', border: '1px solid #bae6fd' }}>
                    {root.productCount.toLocaleString('vi-VN')} sản phẩm
                  </span>
                  <button
                    className="admin-button button-secondary"
                    style={{ fontSize: '12px', padding: '6px 10px' }}
                    onClick={() => handleOpenAdd(root)}
                    title="Thêm danh mục con"
                  >
                    <Plus size={13} /> Thêm nhóm con
                  </button>
                </div>
              </div>

              {/* Danh sách nhóm con */}
              {isExp && (
                <div style={{ padding: '12px 20px', background: '#fff' }}>
                  {root.subCategories.length === 0 ? (
                    <p style={{ fontSize: '13px', color: '#94a3b8', margin: '8px 0', fontStyle: 'italic' }}>Chưa có danh mục con.</p>
                  ) : (
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: '10px' }}>
                      {root.subCategories.map(sub => (
                        <div
                          key={sub.dbId}
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                            padding: '10px 14px',
                            borderRadius: '10px',
                            border: '1px solid #f1f5f9',
                            background: '#f8fafc',
                          }}
                        >
                          <div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                              <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#0284c7' }} />
                              <span style={{ fontSize: '13px', fontWeight: 600, color: '#1e293b' }}>{sub.name}</span>
                              {sub.badge && (
                                <span style={{ fontSize: '9px', fontWeight: 700, background: '#fef3c7', color: '#b45309', padding: '1px 6px', borderRadius: '4px' }}>
                                  {sub.badge}
                                </span>
                              )}
                            </div>
                            <span style={{ fontSize: '11px', color: '#94a3b8', marginLeft: '12px' }}>/{sub.slug}</span>
                          </div>

                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                            <span style={{ fontSize: '11px', fontWeight: 700, color: '#475569', background: '#e2e8f0', padding: '2px 8px', borderRadius: '6px' }}>
                              {sub.productCount}
                            </span>
                            <button
                              style={{ background: 'transparent', border: 'none', color: '#ef4444', cursor: 'pointer', padding: '4px' }}
                              onClick={() => handleDeleteCategory(sub.dbId, sub.name)}
                              title="Xóa danh mục con"
                            >
                              <Trash2 size={13} />
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* Modal tạo danh mục con */}
      {showAddModal && parentTarget && (
        <div style={{ position: 'fixed', inset: 0, zIndex: 999, background: 'rgba(15,23,42,0.6)', backdropFilter: 'blur(4px)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '16px' }}>
          <div style={{ background: '#fff', borderRadius: '16px', maxWidth: '480px', width: '100%', padding: '24px', boxShadow: '0 20px 25px -5px rgba(0,0,0,0.2)' }}>
            <h3 style={{ margin: '0 0 6px 0', fontSize: '17px', fontWeight: 700, color: '#0f172a' }}>
              Thêm danh mục con vào "{parentTarget.name}"
            </h3>
            <p style={{ margin: '0 0 16px 0', fontSize: '12px', color: '#64748b' }}>
              Danh mục con sẽ kế thừa Loại sản phẩm pháp lý ({parentTarget.allowedProductType || 'Đa loại'}) từ nhóm cha.
            </p>

            <form onSubmit={handleCreateSubcategory} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div>
                <label style={{ fontSize: '12px', fontWeight: 600, color: '#334155', display: 'block', marginBottom: '4px' }}>Mã danh mục (Code)</label>
                <input
                  type="text"
                  required
                  value={newCode}
                  onChange={e => setNewCode(e.target.value)}
                  style={{ width: '100%', padding: '8px 12px', borderRadius: '8px', border: '1px solid #cbd5e1', fontSize: '13px' }}
                  placeholder="Ví dụ: SUB_OTC_VITAMIN"
                />
              </div>

              <div>
                <label style={{ fontSize: '12px', fontWeight: 600, color: '#334155', display: 'block', marginBottom: '4px' }}>Tên danh mục con</label>
                <input
                  type="text"
                  required
                  value={newName}
                  onChange={e => {
                    setNewName(e.target.value)
                    if (!newSlug) {
                      setNewSlug(e.target.value.toLowerCase().replace(/[^a-z0-9]/g, '-').replace(/-+/g, '-').replace(/^-|-$/g, ''))
                    }
                  }}
                  style={{ width: '100%', padding: '8px 12px', borderRadius: '8px', border: '1px solid #cbd5e1', fontSize: '13px' }}
                  placeholder="Ví dụ: Men vi sinh & Tiêu hóa trẻ em"
                />
              </div>

              <div>
                <label style={{ fontSize: '12px', fontWeight: 600, color: '#334155', display: 'block', marginBottom: '4px' }}>Slug đường dẫn (URL)</label>
                <input
                  type="text"
                  required
                  value={newSlug}
                  onChange={e => setNewSlug(e.target.value)}
                  style={{ width: '100%', padding: '8px 12px', borderRadius: '8px', border: '1px solid #cbd5e1', fontSize: '13px' }}
                  placeholder="Ví dụ: men-vi-sinh-be"
                />
              </div>

              <div>
                <label style={{ fontSize: '12px', fontWeight: 600, color: '#334155', display: 'block', marginBottom: '4px' }}>Nhãn nổi bật (Badge - tùy chọn)</label>
                <input
                  type="text"
                  value={newBadge}
                  onChange={e => setNewBadge(e.target.value)}
                  style={{ width: '100%', padding: '8px 12px', borderRadius: '8px', border: '1px solid #cbd5e1', fontSize: '13px' }}
                  placeholder="Ví dụ: Hot, Mới"
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '12px' }}>
                <button
                  type="button"
                  className="admin-button button-secondary"
                  onClick={() => setShowAddModal(false)}
                  disabled={saving}
                >
                  Hủy
                </button>
                <button
                  type="submit"
                  className="admin-button button-primary"
                  disabled={saving}
                >
                  {saving ? 'Đang lưu…' : 'Lưu danh mục con'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
