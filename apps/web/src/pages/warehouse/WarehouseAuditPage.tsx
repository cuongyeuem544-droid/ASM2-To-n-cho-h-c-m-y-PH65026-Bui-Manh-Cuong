import { useEffect, useState } from 'react'
import { History, Search, ShieldCheck, Eye, X, Filter } from 'lucide-react'
import { api } from '../../services/api'

interface AuditItem {
  id: number
  action: string
  entity_type: string
  entity_id: string
  user_email: string
  user_name: string
  created_at: string | null
  details: unknown
}

const ACTION_LABELS: Record<string, { label: string; bg: string; color: string }> = {
  CREATE_STOCK_RECEIPT: { label: 'Nhập kho GSP', bg: '#ecfdf5', color: '#047857' },
  STOCK_ADJUSTMENT: { label: 'Kiểm kê điều chỉnh', bg: '#fffbeb', color: '#b45309' },
  CREATE_STOCK_TRANSFER: { label: 'Tạo điều chuyển', bg: '#eff6ff', color: '#1d4ed8' },
  UPDATE_FULFILLMENT_STATUS: { label: 'Cập nhật đơn', bg: '#f0fdfa', color: '#0f766e' },
  REPORT_ORDER_ISSUE: { label: 'Báo sự cố hàng', bg: '#fef2f2', color: '#b91c1c' },
  CREATE_WAREHOUSE_STAFF: { label: 'Tạo nhân viên', bg: '#f5f3ff', color: '#6d28d9' },
  TOGGLE_STAFF_STATUS: { label: 'Khóa / Mở NV', bg: '#fff1f2', color: '#be123c' },
  MIGRATE_LEGACY_ROLE: { label: 'Di trú vai trò', bg: '#e0e7ff', color: '#3730a3' },
}

export function WarehouseAuditPage() {
  const [logs, setLogs] = useState<AuditItem[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [selectedLog, setSelectedLog] = useState<AuditItem | null>(null)

  useEffect(() => {
    setLoading(true)
    api<{ items: AuditItem[]; total: number }>('/warehouse-portal/audit-logs?page_size=50')
      .then((res) => {
        setLogs(res.items || [])
        setTotal(res.total || 0)
      })
      .catch((err) => console.error(err))
      .finally(() => setLoading(false))
  }, [])

  const filteredLogs = logs.filter((l) => {
    if (!search.trim()) return true
    const term = search.toLowerCase()
    return (
      l.action.toLowerCase().includes(term) ||
      l.entity_type.toLowerCase().includes(term) ||
      l.user_name.toLowerCase().includes(term) ||
      l.user_email.toLowerCase().includes(term)
    )
  })

  const formatDetailsPreview = (details: unknown): string => {
    if (!details) return '—'
    if (typeof details === 'string') return details
    try {
      return JSON.stringify(details)
    } catch {
      return String(details)
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', maxWidth: '1400px', margin: '0 auto' }}>
      {/* Header */}
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
          <div style={{ fontSize: '11px', fontWeight: 800, color: '#047857', textTransform: 'uppercase', letterSpacing: '0.8px' }}>
            MINH BẠCH & TRUY XUẤT NGUỒN GỐC GSP
          </div>
          <h1 style={{ margin: '4px 0 0', fontSize: '22px', fontWeight: 900, color: '#0f172a' }}>
            Nhật Ký Thao Tác Trong Kho
          </h1>
          <p style={{ margin: '4px 0 0', fontSize: '13px', color: '#64748b' }}>
            Toàn bộ lịch sử soạn hàng, kiểm kê, nhập kho và thay đổi nhân sự tại chi nhánh
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div style={{ position: 'relative' }}>
            <input
              type="text"
              placeholder="Tìm hành động / người làm…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              style={{
                padding: '8px 14px 8px 34px',
                borderRadius: '10px',
                border: '1px solid #cbd5e1',
                fontSize: '13px',
                outline: 'none',
                width: '240px',
              }}
            />
            <Search size={15} style={{ position: 'absolute', left: '11px', top: '10px', color: '#94a3b8' }} />
          </div>
        </div>
      </div>

      {/* Audit Log Table */}
      <div
        style={{
          background: 'white',
          borderRadius: '16px',
          border: '1px solid #e2e8f0',
          overflow: 'hidden',
          boxShadow: '0 1px 3px rgba(0,0,0,0.03)',
        }}
      >
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '13px' }}>
            <thead>
              <tr style={{ background: '#f8fafc', borderBottom: '1px solid #e2e8f0', color: '#64748b', fontSize: '11px', fontWeight: 800, textTransform: 'uppercase' }}>
                <th style={{ padding: '14px 18px' }}>Hành Động</th>
                <th style={{ padding: '14px 18px' }}>Đối Tượng</th>
                <th style={{ padding: '14px 18px' }}>Người Thực Hiện</th>
                <th style={{ padding: '14px 18px' }}>Thời Gian</th>
                <th style={{ padding: '14px 18px' }}>Chi Tiết Thay Đổi</th>
                <th style={{ padding: '14px 18px', textAlign: 'center' }}>Thao Tác</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={6} style={{ padding: '40px', textAlign: 'center', color: '#94a3b8', fontWeight: 600 }}>
                    Đang tải nhật ký thao tác…
                  </td>
                </tr>
              ) : filteredLogs.length === 0 ? (
                <tr>
                  <td colSpan={6} style={{ padding: '40px', textAlign: 'center', color: '#94a3b8', fontWeight: 600 }}>
                    Chưa có nhật ký nào được ghi nhận.
                  </td>
                </tr>
              ) : (
                filteredLogs.map((l) => {
                  const tag = ACTION_LABELS[l.action] || { label: l.action, bg: '#f1f5f9', color: '#334155' }
                  const previewStr = formatDetailsPreview(l.details)
                  return (
                    <tr
                      key={l.id}
                      style={{ borderBottom: '1px solid #f1f5f9', transition: 'background 0.15s ease' }}
                      onMouseEnter={(e) => (e.currentTarget.style.background = '#f8fafc')}
                      onMouseLeave={(e) => (e.currentTarget.style.background = 'white')}
                    >
                      <td style={{ padding: '14px 18px' }}>
                        <span
                          style={{
                            padding: '4px 10px',
                            borderRadius: '9999px',
                            fontSize: '11px',
                            fontWeight: 800,
                            background: tag.bg,
                            color: tag.color,
                            whiteSpace: 'nowrap',
                          }}
                        >
                          {tag.label}
                        </span>
                      </td>

                      <td style={{ padding: '14px 18px', fontWeight: 700, color: '#1e293b' }}>
                        {l.entity_type} <span style={{ color: '#047857', fontFamily: 'monospace' }}>#{l.entity_id}</span>
                      </td>

                      <td style={{ padding: '14px 18px' }}>
                        <div style={{ fontWeight: 700, color: '#0f172a' }}>{l.user_name}</div>
                        <div style={{ fontSize: '11px', color: '#64748b' }}>{l.user_email}</div>
                      </td>

                      <td style={{ padding: '14px 18px', color: '#64748b', fontSize: '12px' }}>
                        {l.created_at ? new Date(l.created_at).toLocaleString('vi-VN') : '—'}
                      </td>

                      <td style={{ padding: '14px 18px', maxWidth: '320px' }}>
                        <div
                          style={{
                            fontSize: '11.5px',
                            fontFamily: 'monospace',
                            color: '#475569',
                            background: '#f8fafc',
                            padding: '4px 8px',
                            borderRadius: '6px',
                            border: '1px solid #e2e8f0',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap',
                          }}
                          title={previewStr}
                        >
                          {previewStr}
                        </div>
                      </td>

                      <td style={{ padding: '14px 18px', textAlign: 'center' }}>
                        <button
                          type="button"
                          onClick={() => setSelectedLog(l)}
                          style={{
                            padding: '6px 12px',
                            borderRadius: '8px',
                            border: '1px solid #cbd5e1',
                            background: 'white',
                            color: '#0284c7',
                            fontSize: '12px',
                            fontWeight: 700,
                            cursor: 'pointer',
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '4px',
                          }}
                        >
                          <Eye size={13} /> Chi tiết
                        </button>
                      </td>
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Details Modal */}
      {selectedLog && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,0.5)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 60,
            padding: '20px',
          }}
        >
          <div
            style={{
              background: 'white',
              borderRadius: '16px',
              maxWidth: '600px',
              width: '100%',
              padding: '24px',
              boxShadow: '0 20px 25px -5px rgba(0,0,0,0.15)',
              display: 'flex',
              flexDirection: 'column',
              gap: '16px',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid #e2e8f0', paddingBottom: '12px' }}>
              <div>
                <h3 style={{ margin: 0, fontSize: '16px', fontWeight: 800, color: '#0f172a' }}>
                  Chi Tiết Thao Tác #{selectedLog.id}
                </h3>
                <div style={{ fontSize: '11px', color: '#64748b', marginTop: '2px' }}>
                  Hành động: <b>{selectedLog.action}</b> ({selectedLog.entity_type} #{selectedLog.entity_id})
                </div>
              </div>
              <button
                type="button"
                onClick={() => setSelectedLog(null)}
                style={{ background: 'none', border: 'none', color: '#64748b', cursor: 'pointer', padding: '4px' }}
              >
                <X size={20} />
              </button>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', fontSize: '12px', background: '#f8fafc', padding: '12px', borderRadius: '10px' }}>
              <div>
                <span style={{ color: '#64748b' }}>Người thực hiện:</span>{' '}
                <b>{selectedLog.user_name}</b> ({selectedLog.user_email})
              </div>
              <div>
                <span style={{ color: '#64748b' }}>Thời gian:</span>{' '}
                <b>{selectedLog.created_at ? new Date(selectedLog.created_at).toLocaleString('vi-VN') : '—'}</b>
              </div>
            </div>

            <div>
              <div style={{ fontSize: '12px', fontWeight: 700, color: '#334155', marginBottom: '6px' }}>
                Dữ liệu payload thay đổi (JSON Audit):
              </div>
              <pre
                style={{
                  background: '#0f172a',
                  color: '#38bdf8',
                  padding: '16px',
                  borderRadius: '10px',
                  fontSize: '12px',
                  lineHeight: 1.5,
                  overflowX: 'auto',
                  maxHeight: '280px',
                  margin: 0,
                  fontFamily: 'monospace',
                }}
              >
                {selectedLog.details != null
                  ? (typeof selectedLog.details === 'string'
                      ? selectedLog.details
                      : JSON.stringify(selectedLog.details, null, 2))
                  : '(Không có chi tiết)'}
              </pre>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', paddingTop: '8px', borderTop: '1px solid #e2e8f0' }}>
              <button
                type="button"
                onClick={() => setSelectedLog(null)}
                style={{
                  padding: '8px 18px',
                  borderRadius: '8px',
                  background: '#047857',
                  color: 'white',
                  border: 'none',
                  fontSize: '13px',
                  fontWeight: 700,
                  cursor: 'pointer',
                }}
              >
                Đóng
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
