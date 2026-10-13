import { useEffect, useState } from 'react'
import {
  AlertTriangle,
  Bell,
  CheckCircle2,
  Clock,
  Layers,
  ShieldAlert,
  Info,
  Check,
  CheckCheck,
  Filter,
} from 'lucide-react'
import { api } from '../../services/api'
import { WarehouseAlertItem } from '../../types'

export function WarehouseAlertsPage() {
  const [alerts, setAlerts] = useState<WarehouseAlertItem[]>([])
  const [total, setTotal] = useState(0)
  const [unreadTotal, setUnreadTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [severityFilter, setSeverityFilter] = useState('ALL')
  const [readFilter, setReadFilter] = useState<'ALL' | 'UNREAD' | 'READ'>('ALL')
  const [page, setPage] = useState(1)
  const pageSize = 20

  const fetchAlerts = () => {
    setLoading(true)
    const params = new URLSearchParams({
      page: page.toString(),
      page_size: pageSize.toString(),
    })
    if (severityFilter !== 'ALL') {
      params.set('severity', severityFilter)
    }
    if (readFilter === 'UNREAD') {
      params.set('is_read', 'false')
    } else if (readFilter === 'READ') {
      params.set('is_read', 'true')
    }

    api<{ items: WarehouseAlertItem[]; total: number; unread_total: number }>(`/warehouse-portal/alerts?${params.toString()}`)
      .then((res) => {
        setAlerts(res.items || [])
        setTotal(res.total || 0)
        setUnreadTotal(res.unread_total || 0)
      })
      .catch((err) => console.error(err))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    fetchAlerts()
  }, [page, severityFilter, readFilter])

  const handleMarkAsRead = async (alertId: number) => {
    try {
      await api(`/warehouse-portal/alerts/${alertId}/read`, { method: 'PATCH' })
      setAlerts((prev) =>
        prev.map((a) => (a.id === alertId ? { ...a, is_read: true } : a))
      )
      setUnreadTotal((prev) => Math.max(0, prev - 1))
    } catch (err: any) {
      console.error('Không thể đánh dấu đã đọc:', err)
    }
  }

  const handleMarkAllRead = async () => {
    try {
      await api('/warehouse-portal/alerts/mark-all-read', { method: 'POST' })
      setAlerts((prev) => prev.map((a) => ({ ...a, is_read: true })))
      setUnreadTotal(0)
    } catch (err: any) {
      alert('Lỗi đánh dấu tất cả đã đọc: ' + (err.message || ''))
    }
  }

  const getSeverityBadge = (severity: string) => {
    switch (severity) {
      case 'CRITICAL':
        return (
          <span style={{ padding: '3px 10px', borderRadius: '9999px', fontSize: '11px', fontWeight: 800, background: '#fee2e2', color: '#991b1b' }}>
            🔴 Nghiêm trọng (Critical)
          </span>
        )
      case 'WARNING':
        return (
          <span style={{ padding: '3px 10px', borderRadius: '9999px', fontSize: '11px', fontWeight: 800, background: '#fef3c7', color: '#92400e' }}>
            ⚠️ Cảnh báo (Warning)
          </span>
        )
      case 'INFO':
      default:
        return (
          <span style={{ padding: '3px 10px', borderRadius: '9999px', fontSize: '11px', fontWeight: 800, background: '#eff6ff', color: '#1e40af' }}>
            ℹ️ Thông tin (Info)
          </span>
        )
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', maxWidth: '1400px', margin: '0 auto' }}>
      {/* Top Header */}
      <div
        style={{
          background: 'white',
          borderRadius: '16px',
          border: '1px solid #e2e8f0',
          padding: '20px 24px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '16px',
          boxShadow: '0 1px 3px rgba(0,0,0,0.03)',
        }}
      >
        <div>
          <div style={{ fontSize: '11px', fontWeight: 800, color: '#dc2626', textTransform: 'uppercase', letterSpacing: '0.8px' }}>
            GIÁM SÁT RỦI RO & BẤT THƯỜNG VẬN HÀNH
          </div>
          <h1 style={{ margin: '4px 0 0', fontSize: '22px', fontWeight: 900, color: '#0f172a' }}>
            Cảnh Báo Kho & Tồn Kho Bất Thường
          </h1>
          <p style={{ margin: '4px 0 0', fontSize: '13px', color: '#64748b' }}>
            Phát hiện theo thời gian thực: thuốc cận hạn, hết hàng, lô bị cách ly, chênh lệch kiểm kê lớn
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          {unreadTotal > 0 && (
            <button
              onClick={handleMarkAllRead}
              style={{
                background: '#f8fafc',
                color: '#475569',
                border: '1px solid #cbd5e1',
                padding: '9px 16px',
                borderRadius: '10px',
                fontSize: '12.5px',
                fontWeight: 700,
                cursor: 'pointer',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
              }}
            >
              <CheckCheck size={16} /> Đánh dấu tất cả đã đọc ({unreadTotal})
            </button>
          )}

          <div
            style={{
              padding: '9px 16px',
              borderRadius: '10px',
              background: unreadTotal > 0 ? '#fee2e2' : '#ecfdf5',
              border: `1px solid ${unreadTotal > 0 ? '#fecaca' : '#a7f3d0'}`,
              fontSize: '13px',
              fontWeight: 800,
              color: unreadTotal > 0 ? '#dc2626' : '#059669',
            }}
          >
            {unreadTotal > 0 ? `🚨 ${unreadTotal} cảnh báo chưa đọc` : '✓ Trạng thái an toàn'}
          </div>
        </div>
      </div>

      {/* Filter Bar */}
      <div
        style={{
          background: 'white',
          borderRadius: '16px',
          border: '1px solid #e2e8f0',
          padding: '16px 20px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '12px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
          <span style={{ fontSize: '12px', fontWeight: 700, color: '#64748b' }}>Mức độ:</span>
          {[
            { id: 'ALL', label: 'Tất cả mức độ' },
            { id: 'CRITICAL', label: '🔴 Nghiêm trọng' },
            { id: 'WARNING', label: '⚠️ Cảnh báo' },
            { id: 'INFO', label: 'ℹ️ Thông tin' },
          ].map((s) => (
            <button
              key={s.id}
              onClick={() => {
                setSeverityFilter(s.id)
                setPage(1)
              }}
              style={{
                padding: '6px 12px',
                borderRadius: '8px',
                fontSize: '12px',
                fontWeight: 700,
                border: 'none',
                cursor: 'pointer',
                background: severityFilter === s.id ? '#0f172a' : '#f1f5f9',
                color: severityFilter === s.id ? 'white' : '#475569',
              }}
            >
              {s.label}
            </button>
          ))}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontSize: '12px', fontWeight: 700, color: '#64748b' }}>Xem:</span>
          {[
            { id: 'ALL', label: 'Tất cả' },
            { id: 'UNREAD', label: 'Chưa đọc' },
            { id: 'READ', label: 'Đã đọc' },
          ].map((r) => (
            <button
              key={r.id}
              onClick={() => {
                setReadFilter(r.id as any)
                setPage(1)
              }}
              style={{
                padding: '6px 12px',
                borderRadius: '8px',
                fontSize: '12px',
                fontWeight: 700,
                border: 'none',
                cursor: 'pointer',
                background: readFilter === r.id ? '#059669' : '#f1f5f9',
                color: readFilter === r.id ? 'white' : '#475569',
              }}
            >
              {r.label}
            </button>
          ))}
        </div>
      </div>

      {/* Alerts List */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
        {loading ? (
          <div style={{ textAlign: 'center', padding: '40px', color: '#94a3b8', background: 'white', borderRadius: '16px' }}>
            Đang tải dữ liệu cảnh báo…
          </div>
        ) : alerts.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '40px', color: '#059669', background: 'white', borderRadius: '16px', border: '1px solid #e2e8f0' }}>
            <CheckCircle2 size={36} color="#059669" style={{ marginBottom: '8px', display: 'inline-block' }} />
            <div style={{ fontWeight: 800, fontSize: '15px' }}>Không có cảnh báo bất thường nào tại chi nhánh kho!</div>
            <div style={{ fontSize: '12px', color: '#64748b', marginTop: '4px' }}>Mọi chỉ số tồn kho, hạn dùng và điều chuyển đều đang trong ngưỡng an toàn GSP.</div>
          </div>
        ) : (
          alerts.map((a) => (
            <div
              key={a.id}
              style={{
                background: a.is_read ? '#fafafa' : 'white',
                borderRadius: '14px',
                border: `1px solid ${a.is_read ? '#e2e8f0' : a.severity === 'CRITICAL' ? '#fecaca' : '#fed7aa'}`,
                padding: '18px 20px',
                display: 'flex',
                alignItems: 'flex-start',
                justifyContent: 'space-between',
                gap: '16px',
                boxShadow: a.is_read ? 'none' : '0 2px 8px rgba(0,0,0,0.04)',
                transition: 'all 0.15s ease',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'flex-start', gap: '14px' }}>
                <div
                  style={{
                    width: '38px',
                    height: '38px',
                    borderRadius: '10px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    background: a.severity === 'CRITICAL' ? '#fee2e2' : a.severity === 'WARNING' ? '#fef3c7' : '#eff6ff',
                    color: a.severity === 'CRITICAL' ? '#dc2626' : a.severity === 'WARNING' ? '#d97706' : '#2563eb',
                    flexShrink: 0,
                  }}
                >
                  {a.severity === 'CRITICAL' ? <ShieldAlert size={20} /> : a.severity === 'WARNING' ? <AlertTriangle size={20} /> : <Info size={20} />}
                </div>

                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                    {getSeverityBadge(a.severity)}
                    <span style={{ fontSize: '11px', color: '#64748b', fontWeight: 600 }}>
                      Mã: {a.alert_type} {a.reference_id && `• Tham chiếu: ${a.reference_id}`}
                    </span>
                    {!a.is_read && (
                      <span style={{ width: '8px', height: '8px', borderRadius: '9999px', background: '#dc2626' }} title="Chưa đọc" />
                    )}
                  </div>

                  <h3 style={{ margin: '6px 0 4px', fontSize: '15px', fontWeight: 800, color: '#0f172a' }}>
                    {a.title}
                  </h3>

                  <p style={{ margin: 0, fontSize: '13px', color: '#475569', lineHeight: '1.5' }}>
                    {a.message}
                  </p>

                  <div style={{ fontSize: '11px', color: '#94a3b8', marginTop: '8px', display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <Clock size={12} /> {a.created_at ? new Date(a.created_at).toLocaleString('vi-VN') : '—'}
                  </div>
                </div>
              </div>

              {!a.is_read && (
                <button
                  onClick={() => handleMarkAsRead(a.id)}
                  style={{
                    background: '#f1f5f9',
                    border: '1px solid #cbd5e1',
                    color: '#334155',
                    padding: '6px 12px',
                    borderRadius: '8px',
                    fontSize: '12px',
                    fontWeight: 700,
                    cursor: 'pointer',
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '4px',
                    flexShrink: 0,
                  }}
                >
                  <Check size={14} /> Đã xem
                </button>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  )
}
