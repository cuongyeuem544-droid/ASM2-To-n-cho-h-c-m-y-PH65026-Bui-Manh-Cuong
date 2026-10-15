import { Database, Play, Plus, RefreshCw, ShieldCheck } from 'lucide-react'
import { useEffect, useState, type FormEvent } from 'react'
import { StatusBadge } from '../components/StatusBadge'
import { api } from '../services/api'
import { useAuth } from '../services/auth'
import type { Source } from '../types'

export function SourcesPage() {
  const { user } = useAuth()
  const [sources, setSources] = useState<Source[]>([])
  const [showForm, setShowForm] = useState(false)
  const [error, setError] = useState('')
  const load = () => api<Source[]>('/sources').then(setSources).catch(err => setError(err.message))
  useEffect(() => { void load() }, [])

  async function run(source: Source) {
    setError('')
    try { await api(`/sources/${source.id}/run`, { method: 'POST' }); window.alert('Đã đưa tác vụ vào hàng chờ.'); }
    catch (err) { setError(err instanceof Error ? err.message : 'Không thể chạy nguồn') }
  }

  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    const baseUrl = String(form.get('base_url') || '').trim()
    const payload = {
      code: String(form.get('code')).toUpperCase(),
      name: form.get('name'),
      source_type: form.get('source_type'),
      base_url: baseUrl || null,
      authority_level: Number(form.get('authority_level')),
      authority_weight: Number(form.get('authority_weight')),
      rate_limit: 1,
      crawl_frequency: form.get('crawl_frequency'),
      enabled: true,
    }
    try { await api('/sources', { method: 'POST', body: JSON.stringify(payload) }); setShowForm(false); await load() }
    catch (err) { setError(err instanceof Error ? err.message : 'Không thể tạo nguồn') }
  }

const SOURCE_TYPES: Record<string, string> = {
  REGULATORY: 'Cơ quan quản lý',
  MANUFACTURER: 'Nhà sản xuất',
  APPROVED_LEAFLET: 'Hướng dẫn sử dụng',
  RETAILER: 'Nhà thuốc bán lẻ',
  MANUAL_UPLOAD: 'Tải tệp thủ công',
}

  return (
    <div className="page">
      <div className="page-heading">
        <div>
          <span className="overline">QUẢN TRỊ NGUỒN</span>
          <h1>Nguồn Thu Thập Dữ Liệu</h1>
          <p>Quản lý các nguồn dữ liệu đối soát, cấp thẩm quyền và kết nối thu thập.</p>
        </div>
        {user?.role === 'ADMIN' && (
          <button className="primary-button" onClick={() => setShowForm(!showForm)}>
            <Plus size={17} /> Thêm nguồn mới
          </button>
        )}
      </div>
      {showForm && (
        <form className="panel source-form" onSubmit={create}>
          <h2>Thêm nguồn dữ liệu mới</h2>
          <div className="form-grid">
            <label>Mã nguồn (viết hoa)<input name="code" placeholder="DAV_PUBLIC" required pattern="[A-Za-z0-9_-]{2,80}" /></label>
            <label>Tên nguồn<input name="name" placeholder="Cục Quản lý Dược Việt Nam" required /></label>
            <label>
              Loại nguồn
              <select name="source_type">
                <option value="REGULATORY">Cơ quan quản lý (Cục Quản lý Dược)</option>
                <option value="MANUFACTURER">Nhà sản xuất dược phẩm</option>
                <option value="APPROVED_LEAFLET">Tờ hướng dẫn sử dụng chuẩn</option>
                <option value="RETAILER">Nhà thuốc bán lẻ (Pharmacity, Long Châu...)</option>
                <option value="MANUAL_UPLOAD">Tải tệp thủ công</option>
              </select>
            </label>
            <label>Đường dẫn trang web (Base URL)<input name="base_url" type="url" placeholder="https://..." /></label>
            <label>Cấp thẩm quyền (1-5)<input name="authority_level" type="number" min="1" max="5" defaultValue="3" /></label>
            <label>Trọng số độ tin cậy (0 - 1)<input name="authority_weight" type="number" min="0" max="1" step="0.05" defaultValue="0.7" /></label>
            <label>
              Lịch chạy định kỳ
              <select name="crawl_frequency">
                <option value="MANUAL">Thủ công khi cần</option>
                <option value="HOURLY">Mỗi giờ</option>
                <option value="DAILY">Hàng ngày</option>
                <option value="WEEKLY">Hàng tuần</option>
              </select>
            </label>
          </div>
          <button className="primary-button">Lưu thông tin nguồn</button>
        </form>
      )}
      {error && <div className="alert alert-error">{error}</div>}
      <div className="source-grid">
        {sources.map(source => (
          <article className="source-card" key={source.id}>
            <div className="source-logo"><Database /></div>
            <div className="source-main">
              <div className="source-title">
                <div>
                  <strong>{source.name}</strong>
                  <code>{source.code}</code>
                </div>
                <span className={`toggle-dot ${source.enabled ? 'on' : ''}`} />
              </div>
              <div className="source-tags">
                <span>{SOURCE_TYPES[source.source_type] || source.source_type}</span>
                <span>Thẩm quyền {source.authority_level}/5</span>
                <span>Trọng số {source.authority_weight}</span>
              </div>
              <p>{source.base_url || 'Nguồn nhập tệp, không có URL thu thập'}</p>
              <div className="source-footer">
                <span><ShieldCheck size={15} /> Chuẩn robots.txt: <b>{source.robots_status}</b></span>
                {source.base_url && user?.role === 'ADMIN' && (
                  <button onClick={() => run(source)}>
                    <Play size={15} /> Thu thập ngay
                  </button>
                )}
              </div>
            </div>
          </article>
        ))}
      </div>
    </div>
  )
}
