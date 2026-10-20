import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Database,
  FileStack,
  Layers,
  RefreshCw,
  ShieldCheck,
  TrendingUp,
} from 'lucide-react'
import { useEffect, useState } from 'react'
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts'
import { AdminPageHeader } from '../components/AdminPageHeader'
import { StatCard, StatGrid } from '../components/StatCard'
import { StatusBadge } from '../components/StatusBadge'
import { ErrorState } from '../components/ErrorState'
import { api } from '../services/api'

interface Summary {
  documents: number
  products: number
  high_match: number
  review_required: number
  insufficient: number
  blocked: number
  open_conflicts: number
  recent_runs: Array<{
    id: number
    source_id: number
    status: string
    products_discovered: number
    started_at: string | null
  }>
}

const PIE_COLORS = ['#059669', '#d97706', '#64748b', '#dc2626']

export function DashboardPage() {
  const [data, setData] = useState<Summary | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = () => {
    setLoading(true)
    setError('')
    api<Summary>('/dashboard/summary')
      .then((res) => {
        setData(res)
      })
      .catch((err) => {
        setError(err.message || 'Không thể tải dữ liệu tổng quan')
      })
      .finally(() => {
        setLoading(false)
      })
  }

  useEffect(() => {
    void load()
  }, [])

  if (error) {
    return (
      <div className="page">
        <AdminPageHeader
          title="Tổng quan hệ thống"
          eyebrow="PharmaTrust Data Hub • Giám sát dữ liệu"
          subtitle="Theo dõi chất lượng danh mục thuốc, cảnh báo đồng bộ và hoạt động thu thập tự động."
        />
        <ErrorState
          title="Lỗi tải dữ liệu tổng quan"
          message={error}
          onRetry={load}
        />
      </div>
    )
  }

  const chartData = data
    ? [
        { name: 'Khớp chính thức', value: data.high_match },
        { name: 'Cần kiểm tra', value: data.review_required },
        { name: 'Thiếu chứng cứ', value: data.insufficient },
        { name: 'Đã tạm khóa', value: data.blocked },
      ]
    : []

  return (
    <div className="page">
      <AdminPageHeader
        title="Tổng quan hệ thống"
        eyebrow="PharmaTrust Data Hub • Bảng điều khiển vận hành"
        subtitle="Theo dõi độ tin cậy dữ liệu thuốc, kiểm định đối soát liên nguồn và tác vụ tự động hóa."
        actions={
          <button
            type="button"
            className="admin-button button-secondary"
            onClick={load}
            disabled={loading}
          >
            <RefreshCw size={14} className={loading ? 'spin' : ''} />
            <span>Làm mới dữ liệu</span>
          </button>
        }
      />

      {/* Operational Notice */}
      <div className="notice-banner" style={{ background: '#f0fdf4', borderColor: '#bbf7d0', color: '#166534', marginBottom: '20px' }}>
        <ShieldCheck size={18} style={{ color: '#16a34a' }} />
        <span>
          <strong>Quy chuẩn kiểm soát:</strong> Dữ liệu thuốc bắt buộc phải vượt qua đối soát tự động giữa Cục Quản lý Dược và nhà sản xuất trước khi kích hoạt hiển thị trên Storefront H4CARE.
        </span>
      </div>

      {/* 4 Core Operational Stat Cards */}
      <StatGrid columns={4}>
        <StatCard
          label="Tài liệu thu thập"
          value={data?.documents?.toLocaleString('vi-VN') || 0}
          icon={FileStack}
          tone="blue"
          subtext="Văn bản, thông tư & nhãn thuốc"
          loading={loading}
        />
        <StatCard
          label="Danh mục thuốc"
          value={data?.products?.toLocaleString('vi-VN') || 0}
          icon={Database}
          tone="purple"
          subtext="Hồ sơ hoạt chất & dạng bào chế"
          loading={loading}
        />
        <StatCard
          label="Thuốc khớp chính thức"
          value={data?.high_match?.toLocaleString('vi-VN') || 0}
          icon={CheckCircle2}
          tone="emerald"
          badge={data && data.products > 0 ? `${Math.round((data.high_match / data.products) * 100)}%` : undefined}
          subtext="Độ tin cậy cao, sẵn sàng duyệt bán"
          loading={loading}
        />
        <StatCard
          label="Mâu thuẫn cần xử lý"
          value={data?.open_conflicts?.toLocaleString('vi-VN') || 0}
          icon={AlertTriangle}
          tone={data && data.open_conflicts > 0 ? 'red' : 'slate'}
          subtext="Lệch hàm lượng hoặc nhà sản xuất"
          loading={loading}
        />
      </StatGrid>

      {/* Grid: Drug Verification Quality Chart & Recent Collection Runs */}
      <div className="dashboard-grid" style={{ marginTop: '20px' }}>
        {/* Verification Status Card */}
        <section className="panel chart-panel" style={{ borderRadius: '12px', border: '1px solid #e2e8f0', padding: '20px', background: '#fff' }}>
          <div className="panel-heading" style={{ marginBottom: '16px' }}>
            <div>
              <h2 style={{ fontSize: '15px', fontWeight: 700, margin: 0, color: '#0f172a' }}>
                Kiểm định độ tin cậy danh mục
              </h2>
              <p style={{ margin: '4px 0 0', fontSize: '12px', color: '#64748b' }}>
                Phân bổ thuốc theo các cấp độ chứng cứ xác thực
              </p>
            </div>
            <Layers size={18} style={{ color: '#64748b' }} />
          </div>

          <div className="chart-wrap" style={{ position: 'relative', height: '240px' }}>
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={chartData}
                  dataKey="value"
                  nameKey="name"
                  innerRadius={68}
                  outerRadius={92}
                  paddingAngle={4}
                >
                  {chartData.map((_, i) => (
                    <Cell key={`cell-${i}`} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
            <div className="chart-center" style={{ position: 'absolute', top: '78px', left: 0, right: 0, textAlign: 'center', pointerEvents: 'none' }}>
              <strong style={{ fontSize: '24px', fontWeight: 800, color: '#0f172a', display: 'block' }}>
                {data?.products?.toLocaleString('vi-VN') || 0}
              </strong>
              <span style={{ fontSize: '11px', color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                Tổng thuốc
              </span>
            </div>
          </div>

          <div className="legend" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px 16px', borderTop: '1px solid #f1f5f9', paddingTop: '16px', marginTop: '8px' }}>
            {chartData.map((item, i) => (
              <span key={item.name} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '12px', color: '#475569' }}>
                <span style={{ display: 'flex', alignItems: 'center', gap: '7px' }}>
                  <i style={{ width: '8px', height: '8px', borderRadius: '50%', background: PIE_COLORS[i % PIE_COLORS.length], display: 'inline-block' }} />
                  {item.name}
                </span>
                <strong style={{ color: '#0f172a' }}>{(item.value ?? 0).toLocaleString('vi-VN')}</strong>
              </span>
            ))}
          </div>
        </section>

        {/* Recent Automation Runs Card */}
        <section className="panel" style={{ borderRadius: '12px', border: '1px solid #e2e8f0', padding: '20px', background: '#fff' }}>
          <div className="panel-heading" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
            <div>
              <h2 style={{ fontSize: '15px', fontWeight: 700, margin: 0, color: '#0f172a' }}>
                Phiên thu thập dữ liệu gần đây
              </h2>
              <p style={{ margin: '4px 0 0', fontSize: '12px', color: '#64748b' }}>
                Lịch sử tiến trình cào tự động và đồng bộ từ các nguồn
              </p>
            </div>
            <Activity size={18} style={{ color: '#0284c7' }} />
          </div>

          <div className="activity-list" style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {data?.recent_runs && data.recent_runs.length > 0 ? (
              data.recent_runs.map((run) => (
                <div
                  className="activity-row"
                  key={run.id}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '12px',
                    padding: '10px 12px',
                    borderRadius: '8px',
                    background: '#f8fafc',
                    border: '1px solid #f1f5f9',
                  }}
                >
                  <span
                    style={{
                      width: '32px',
                      height: '32px',
                      borderRadius: '8px',
                      display: 'grid',
                      placeItems: 'center',
                      background: '#e0f2fe',
                      color: '#0284c7',
                      flexShrink: 0,
                    }}
                  >
                    <Database size={15} />
                  </span>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <strong style={{ fontSize: '12.5px', color: '#0f172a', display: 'block' }}>
                      Phiên cào #{run.id}
                    </strong>
                    <small style={{ fontSize: '11px', color: '#64748b', display: 'block', marginTop: '2px' }}>
                      Nguồn dữ liệu #{run.source_id} · {run.products_discovered} thuốc mới
                    </small>
                  </div>
                  <StatusBadge value={run.status} showDot />
                </div>
              ))
            ) : (
              <div style={{ padding: '36px 16px', textAlign: 'center', color: '#94a3b8', fontSize: '13px' }}>
                Chưa có phiên thu thập nào được ghi nhận.
              </div>
            )}
          </div>
        </section>
      </div>
    </div>
  )
}
