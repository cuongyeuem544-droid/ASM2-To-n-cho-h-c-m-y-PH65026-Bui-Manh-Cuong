import { ArrowLeft, Beaker, CheckCircle2, FileSearch, RefreshCw, ShieldAlert } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ScoreRing } from '../components/ScoreRing'
import { StatusBadge } from '../components/StatusBadge'
import { api } from '../services/api'
import type { Conflict, Product } from '../types'

interface ProductDetail extends Product {
  dosage_form: string | null
  route: string | null
  manufacturing_country: string | null
  package_description: string | null
  ingredients: Array<{ name: string; strength_value: number | null; strength_unit: string | null }>
  source_fields: Array<{ id: number; source_id: number; field_name: string; original_value: string | null; field_confidence: number; observed_at: string; is_selected_value: boolean }>
  conflicts: Conflict[]
  latest_score: null | Record<string, number | string>
}

const scoreNames: Record<string, string> = {
  registration_match_score: 'Số đăng ký',
  otc_status_score: 'Trạng thái OTC',
  ingredient_strength_score: 'Hoạt chất & hàm lượng',
  manufacturer_score: 'Nhà sản xuất',
  package_score: 'Quy cách',
  source_consensus_score: 'Đồng thuận nguồn',
  recency_score: 'Độ mới',
  completeness_score: 'Độ đầy đủ',
  penalty: 'Điểm trừ',
}

export function ProductDetailPage() {
  const { id } = useParams()
  const [product, setProduct] = useState<ProductDetail | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const load = () => api<ProductDetail>(`/products/${id}`).then(setProduct).catch(err => setError(err.message))
  useEffect(() => { void load() }, [id])

  async function recalculate() {
    setBusy(true)
    try { await api(`/products/${id}/recalculate`, { method: 'POST' }); await load() }
    catch (err) { setError(err instanceof Error ? err.message : 'Không thể tính lại') }
    finally { setBusy(false) }
  }

  async function handlePublish() {
    setBusy(true)
    try {
      await api(`/products/${id}/publish`, { method: 'POST' })
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể duyệt đăng bán')
    } finally {
      setBusy(false)
    }
  }

  async function handleUnpublish() {
    setBusy(true)
    try {
      await api(`/products/${id}/unpublish`, { method: 'POST' })
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể ẩn sản phẩm')
    } finally {
      setBusy(false)
    }
  }

  if (error) return <div className="page"><Link to="/products" className="back-link"><ArrowLeft /> Quay lại</Link><div className="alert alert-error">{error}</div></div>
  if (!product) return <div className="page loading-page"><RefreshCw className="spin" /> Đang tải hồ sơ…</div>
  const scoreEntries = Object.entries(product.latest_score || {}).filter(([key]) => key in scoreNames)

  return (
    <div className="page">
      <Link to="/products" className="back-link"><ArrowLeft size={17} /> Hồ sơ sản phẩm</Link>
      
      {/* Moderation & Storefront Publishing Action Banner */}
      <div style={{
        background: product.publish_status === 'PUBLISHED' ? '#f0fdf4' : '#fffbeb',
        border: `1px solid ${product.publish_status === 'PUBLISHED' ? '#bbf7d0' : '#fde68a'}`,
        borderRadius: '12px',
        padding: '16px 20px',
        marginBottom: '16px',
        display: 'flex',
        flexWrap: 'wrap',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: '12px',
        boxShadow: '0 1px 3px rgba(0,0,0,0.05)'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <span style={{
            fontSize: '11px',
            fontWeight: 800,
            padding: '5px 12px',
            borderRadius: '999px',
            background: product.publish_status === 'PUBLISHED' ? '#16a34a' : '#d97706',
            color: '#fff',
            letterSpacing: '0.04em'
          }}>
            {product.publish_status === 'PUBLISHED' ? '● ĐANG ĐĂNG BÁN' : '○ BẢN NHÁP / CHỜ DUYỆT'}
          </span>
          <span style={{ fontSize: '13px', color: '#475569', fontWeight: 500 }}>
            {product.publish_status === 'PUBLISHED'
              ? 'Thuốc đang hiển thị công khai trên Storefront khách hàng. Khách có thể tìm kiếm và đặt mua.'
              : 'Thuốc đang ở trạng thái bản nháp. Khách hàng chưa thấy thuốc này trên website bán hàng.'}
          </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {product.publish_status === 'PUBLISHED' ? (
            <>
              <a
                href={`http://localhost:3000/product/prod-db-${product.id}`}
                target="_blank"
                rel="noreferrer"
                className="secondary-button"
                style={{ textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: '6px', fontSize: '12px' }}
              >
                <span>Xem trên Storefront (Cổng 3000) ↗</span>
              </a>
              <button
                className="secondary-button"
                style={{ color: '#d97706', borderColor: '#fde68a', fontSize: '12px' }}
                onClick={handleUnpublish}
                disabled={busy}
              >
                Tạm ẩn / Ngừng bán
              </button>
            </>
          ) : (
            <button
              className="primary-button"
              style={{ background: '#16a34a', borderColor: '#16a34a', fontSize: '13px', fontWeight: 700 }}
              onClick={handlePublish}
              disabled={busy}
            >
              ✓ Duyệt & Đăng Bán Lên Kệ Hàng
            </button>
          )}
        </div>
      </div>

      <div className="detail-hero">
        <div className="detail-title"><div className="data-icon"><Beaker /></div><div><div className="detail-badges"><StatusBadge value={product.confidence_label} />{product.is_demo && <span className="demo-pill">DỮ LIỆU DEMO</span>}</div><h1>{product.canonical_name}</h1><p>{product.registration_number || 'Chưa xác định số đăng ký'}</p></div></div>
        <div className="detail-score"><ScoreRing score={product.overall_score} size={92} /><button className="secondary-button" onClick={recalculate} disabled={busy}><RefreshCw size={16} className={busy ? 'spin' : ''} /> Tính lại điểm</button></div>
      </div>
      <div className="notice-banner"><ShieldAlert size={19} /><span>Điểm này chỉ phản ánh mức độ khớp của hồ sơ dữ liệu. Không xác nhận chất lượng, tính chính hãng hoặc sự phù hợp điều trị.</span></div>
      <div className="detail-grid">
        <section className="panel">
          <div className="panel-heading"><div><h2>Thông tin chi tiết</h2><p>Giá trị hiện được hệ thống lựa chọn</p></div><CheckCircle2 size={20} /></div>
          <div className="info-grid">
            <Info label="Nhà sản xuất" value={product.manufacturer} />
            <Info label="Quốc gia" value={product.manufacturing_country} />
            <Info label="Dạng bào chế" value={product.dosage_form} />
            <Info label="Đường dùng" value={product.route} />
            <Info label="Quy cách" value={product.package_description} wide />
            <Info label="Trạng thái quản lý" value={product.regulatory_status} badge />
            <Info label="Phân loại" value={product.rx_otc_status} badge />
          </div>
          <h3 className="subheading">Hoạt chất quan sát</h3>
          <div className="ingredient-list">{product.ingredients.map((item, index) => <span key={index}><Beaker size={15} />{item.name} <strong>{item.strength_value} {item.strength_unit}</strong></span>)}</div>
        </section>
        <section className="panel score-breakdown">
          <div className="panel-heading"><div><h2>Cấu phần điểm</h2><p>Phiên bản luật chấm điểm hiện tại</p></div></div>
          {scoreEntries.map(([key, value]) => {
            const number = Number(value)
            const max = key === 'registration_match_score' ? 30 : key === 'otc_status_score' || key === 'ingredient_strength_score' ? 20 : key === 'manufacturer_score' ? 10 : 20
            return <div className="score-row" key={key}><span>{scoreNames[key]}</span><div><i style={{ width: `${Math.min(100, number / max * 100)}%` }} /></div><strong>{key === 'penalty' ? '-' : '+'}{number}</strong></div>
          })}
        </section>
      </div>

      {(product.usage_instructions || product.indications || product.contraindications || product.side_effects || product.image_url) && (
        <section className="panel leaflet-section">
          <div className="panel-heading">
            <div>
              <h2>Tờ Hướng Dẫn Sử Dụng & Thông Tin Lâm Sàng</h2>
              <p>Trích xuất trực tiếp từ hồ sơ đăng ký thuốc hoặc nhà thuốc đối chiếu</p>
            </div>
          </div>
          <div className="leaflet-grid" style={{ display: 'grid', gridTemplateColumns: product.image_url ? '260px 1fr' : '1fr', gap: '20px' }}>
            {product.image_url && (
              <div className="product-photo-box" style={{ background: '#f8fafc', borderRadius: '12px', padding: '16px', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                <img
                  src={product.image_url}
                  alt={product.canonical_name}
                  style={{ maxWidth: '100%', maxHeight: '240px', objectFit: 'contain', borderRadius: '8px' }}
                  onError={(e) => { (e.target as HTMLElement).style.display = 'none' }}
                />
              </div>
            )}
            <div className="leaflet-details-box" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              {product.description && (
                <div style={{ background: '#f1f5f9', padding: '12px 16px', borderRadius: '8px' }}>
                  <p style={{ margin: 0, color: '#334155', lineHeight: 1.6 }}>{product.description}</p>
                </div>
              )}
              {product.indications && (
                <div>
                  <h4 style={{ margin: '0 0 6px 0', color: '#0f172a', display: 'flex', alignItems: 'center', gap: '6px' }}>📋 Chỉ định điều trị</h4>
                  <div style={{ whiteSpace: 'pre-line', color: '#475569', lineHeight: 1.6, background: '#fafafa', padding: '12px', borderRadius: '8px', border: '1px solid #f1f5f9' }}>{product.indications}</div>
                </div>
              )}
              {product.usage_instructions && (
                <div>
                  <h4 style={{ margin: '0 0 6px 0', color: '#0f172a', display: 'flex', alignItems: 'center', gap: '6px' }}>💊 Cách dùng & Liều dùng</h4>
                  <div style={{ whiteSpace: 'pre-line', color: '#475569', lineHeight: 1.6, background: '#fafafa', padding: '12px', borderRadius: '8px', border: '1px solid #f1f5f9' }}>{product.usage_instructions}</div>
                </div>
              )}
              {product.contraindications && (
                <div>
                  <h4 style={{ margin: '0 0 6px 0', color: '#b91c1c', display: 'flex', alignItems: 'center', gap: '6px' }}>⚠️ Chống chỉ định</h4>
                  <div style={{ whiteSpace: 'pre-line', color: '#7f1d1d', lineHeight: 1.6, background: '#fef2f2', padding: '12px', borderRadius: '8px', border: '1px solid #fee2e2' }}>{product.contraindications}</div>
                </div>
              )}
              {product.side_effects && (
                <div>
                  <h4 style={{ margin: '0 0 6px 0', color: '#c2410c', display: 'flex', alignItems: 'center', gap: '6px' }}>🚨 Tác dụng phụ</h4>
                  <div style={{ whiteSpace: 'pre-line', color: '#475569', lineHeight: 1.6, background: '#fff7ed', padding: '12px', borderRadius: '8px', border: '1px solid #ffedd5' }}>{product.side_effects}</div>
                </div>
              )}
              {product.storage_conditions && (
                <div>
                  <h4 style={{ margin: '0 0 6px 0', color: '#0f172a', display: 'flex', alignItems: 'center', gap: '6px' }}>📦 Bảo quản</h4>
                  <div style={{ whiteSpace: 'pre-line', color: '#475569', lineHeight: 1.6, background: '#fafafa', padding: '12px', borderRadius: '8px', border: '1px solid #f1f5f9' }}>{product.storage_conditions}</div>
                </div>
              )}
            </div>
          </div>
        </section>
      )}

      <section className="panel">
        <div className="panel-heading"><div><h2>Bằng chứng và nguồn dữ liệu</h2><p>Mỗi thông tin thuốc đều gắn liền với nguồn gốc và thời điểm đối soát</p></div><FileSearch size={20} /></div>
        <div className="table-wrap"><table><thead><tr><th>Thông tin</th><th>Giá trị ghi nhận</th><th>Nguồn</th><th>Độ tin cậy</th><th>Sử dụng</th></tr></thead><tbody>
          {product.source_fields.map(field => <tr key={field.id}><td><strong>{field.field_name}</strong></td><td>{field.original_value || '—'}</td><td>Nguồn #{field.source_id}</td><td>{Math.round(field.field_confidence * 100)}%</td><td>{field.is_selected_value ? <CheckCircle2 className="text-success" size={18} /> : '—'}</td></tr>)}
        </tbody></table></div>
      </section>
      {product.conflicts.length > 0 && <section className="panel conflict-section"><div className="panel-heading"><div><h2>Mâu thuẫn liên quan</h2><p>{product.conflicts.filter(item => item.status === 'OPEN').length} cảnh báo đang mở</p></div></div>{product.conflicts.map(item => <div className="conflict-inline" key={item.id}><StatusBadge value={item.severity} /><div><strong>{item.description}</strong><small>{item.value_a || '—'} ↔ {item.value_b || '—'}</small></div><StatusBadge value={item.status} /></div>)}</section>}
    </div>
  )
}

function Info({ label, value, wide, badge }: { label: string; value: string | null; wide?: boolean; badge?: boolean }) {
  return <div className={wide ? 'wide' : ''}><span>{label}</span>{badge && value ? <StatusBadge value={value} /> : <strong>{value || 'Chưa xác định'}</strong>}</div>
}
