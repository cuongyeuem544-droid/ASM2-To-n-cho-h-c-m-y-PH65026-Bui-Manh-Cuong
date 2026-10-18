import React, { useEffect, useMemo, useState } from 'react'
import {
  AlertCircle,
  CheckCircle2,
  Clock,
  Eye,
  Mail,
  RefreshCw,
  Send,
  X,
  XCircle,
} from 'lucide-react'
import { PaginationBar } from '../components/PaginationBar'
import { api } from '../services/api'

interface EmailOutboxItem {
  id: number
  recipient_email: string
  subject: string
  reference_type?: string
  reference_id?: string
  status: 'PENDING' | 'SENT' | 'FAILED' | string
  retry_count: number
  max_retries: number
  last_error?: string
  sent_at?: string
  created_at?: string
}

interface EmailOutboxDetail extends EmailOutboxItem {
  body_html: string
  body_text?: string
}

export function EmailsPage() {
  const [emails, setEmails] = useState<EmailOutboxItem[]>([])
  const [loading, setLoading] = useState(true)
  const [statusFilter, setStatusFilter] = useState<string>('ALL')
  const [searchRef, setSearchRef] = useState('')
  const [notification, setNotification] = useState<{ type: 'success' | 'error'; message: string } | null>(null)

  // Phân trang
  const [currentPage, setCurrentPage] = useState<number>(1)
  const [pageSize, setPageSize] = useState<number>(15)

  useEffect(() => {
    setCurrentPage(1)
  }, [statusFilter, searchRef])

  const totalPages = Math.max(1, Math.ceil(emails.length / pageSize))
  const displayedEmails = useMemo(() => {
    const start = (currentPage - 1) * pageSize
    return emails.slice(start, start + pageSize)
  }, [emails, currentPage, pageSize])

  // Detail Modal state
  const [selectedEmail, setSelectedEmail] = useState<EmailOutboxDetail | null>(null)
  const [loadingDetail, setLoadingDetail] = useState(false)

  // Resending state
  const [resendingId, setResendingId] = useState<number | null>(null)

  // Test Email Modal state
  const [isTestModalOpen, setIsTestModalOpen] = useState(false)
  const [testRecipient, setTestRecipient] = useState('')
  const [isSendingTest, setIsSendingTest] = useState(false)

  async function loadEmails() {
    setLoading(true)
    try {
      let url = '/emails/outbox?limit=100'
      if (statusFilter !== 'ALL') {
        url += `&status=${statusFilter}`
      }
      if (searchRef.trim()) {
        url += `&reference_id=${encodeURIComponent(searchRef.trim())}`
      }
      const data = await api<EmailOutboxItem[]>(url)
      setEmails(data)
    } catch (err: any) {
      setNotification({ type: 'error', message: err?.message || 'Không thể tải danh sách email outbox' })
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadEmails()
  }, [statusFilter])

  async function handleOpenDetail(id: number) {
    setLoadingDetail(true)
    try {
      const data = await api<EmailOutboxDetail>(`/emails/outbox/${id}`)
      setSelectedEmail(data)
    } catch (err: any) {
      alert('Không tải được nội dung thư: ' + (err?.message || 'Lỗi mạng'))
    } finally {
      setLoadingDetail(false)
    }
  }

  async function handleResend(id: number) {
    setResendingId(id)
    setNotification(null)
    try {
      const res = await api<any>(`/emails/outbox/${id}/resend`, { method: 'POST' })
      setNotification({ type: 'success', message: res?.message || 'Đã gửi lại email thành công!' })
      await loadEmails()
      if (selectedEmail && selectedEmail.id === id) {
        handleOpenDetail(id)
      }
    } catch (err: any) {
      setNotification({ type: 'error', message: err?.message || 'Không thể gửi lại email' })
    } finally {
      setResendingId(null)
    }
  }

  async function handleSendTest(e: React.FormEvent) {
    e.preventDefault()
    if (!testRecipient.trim()) return
    setIsSendingTest(true)
    setNotification(null)
    try {
      const res = await api<any>('/emails/test', {
        method: 'POST',
        body: JSON.stringify({ recipient_email: testRecipient.trim() }),
      })
      setNotification({ type: 'success', message: res?.message || 'Đã gửi email kiểm tra thành công!' })
      setIsTestModalOpen(false)
      setTestRecipient('')
      if (statusFilter !== 'ALL') {
        setStatusFilter('ALL')
      } else {
        await loadEmails()
      }
    } catch (err: any) {
      setNotification({ type: 'error', message: err?.message || 'Không thể gửi email kiểm tra' })
    } finally {
      setIsSendingTest(false)
    }
  }

  const sentCount = emails.filter((e) => e.status === 'SENT').length
  const failedCount = emails.filter((e) => e.status === 'FAILED').length
  const pendingCount = emails.filter((e) => e.status === 'PENDING').length

  return (
    <div className="page-container" style={{ padding: '24px 32px' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20, flexWrap: 'wrap', gap: 12 }}>
        <div>
          <h1 style={{ fontSize: 24, fontWeight: 800, color: '#0f172a', margin: '0 0 4px', display: 'flex', alignItems: 'center', gap: 8 }}>
            <Mail className="text-brand-blue-600" size={26} />
            Hộp thư Điện tử & Outbox
          </h1>
          <p style={{ margin: 0, fontSize: 13, color: '#64748b' }}>
            Theo dõi vết email xác nhận đơn hàng, gửi lại thư lỗi và kiểm tra kết nối Gmail SMTP.
          </p>
        </div>

        <div style={{ display: 'flex', gap: 8 }}>
          <button
            type="button"
            onClick={() => setIsTestModalOpen(true)}
            className="secondary-button"
            style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, fontWeight: 700 }}
          >
            <Send size={14} />
            Gửi email kiểm tra SMTP
          </button>
          <button
            type="button"
            onClick={loadEmails}
            className="secondary-button"
            style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13 }}
            title="Làm mới danh sách"
          >
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
            Làm mới
          </button>
        </div>
      </div>

      {/* KPI Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 14, marginBottom: 20 }}>
        <div style={{ background: '#ffffff', border: '1px solid #e2e8f0', borderRadius: 12, padding: '14px 18px' }}>
          <span style={{ fontSize: 12, color: '#64748b', fontWeight: 600 }}>Tổng thư trong Outbox</span>
          <div style={{ fontSize: 22, fontWeight: 800, color: '#0f172a', marginTop: 4 }}>{emails.length}</div>
        </div>
        <div style={{ background: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: 12, padding: '14px 18px' }}>
          <span style={{ fontSize: 12, color: '#166534', fontWeight: 600 }}>Gửi thành công (SENT)</span>
          <div style={{ fontSize: 22, fontWeight: 800, color: '#15803d', marginTop: 4 }}>{sentCount}</div>
        </div>
        <div style={{ background: '#fef2f2', border: '1px solid #fecaca', borderRadius: 12, padding: '14px 18px' }}>
          <span style={{ fontSize: 12, color: '#991b1b', fontWeight: 600 }}>Thất bại (FAILED)</span>
          <div style={{ fontSize: 22, fontWeight: 800, color: '#b91c1c', marginTop: 4 }}>{failedCount}</div>
        </div>
        <div style={{ background: '#fefce8', border: '1px solid #fef08a', borderRadius: 12, padding: '14px 18px' }}>
          <span style={{ fontSize: 12, color: '#854d0e', fontWeight: 600 }}>Đang chờ (PENDING)</span>
          <div style={{ fontSize: 22, fontWeight: 800, color: '#a16207', marginTop: 4 }}>{pendingCount}</div>
        </div>
      </div>

      {/* Notification banner */}
      {notification && (
        <div
          style={{
            marginBottom: 16,
            padding: '10px 16px',
            borderRadius: 8,
            fontSize: 13,
            fontWeight: 600,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            background: notification.type === 'success' ? '#dcfce7' : '#fee2e2',
            color: notification.type === 'success' ? '#15803d' : '#b91c1c',
            border: `1px solid ${notification.type === 'success' ? '#86efac' : '#fca5a5'}`,
          }}
        >
          <span>{notification.message}</span>
          <button type="button" onClick={() => setNotification(null)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'inherit' }}>
            ✕
          </button>
        </div>
      )}

      {/* Filter Toolbar */}
      <div style={{ background: '#ffffff', border: '1px solid #e2e8f0', borderRadius: 12, padding: 14, marginBottom: 18, display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', gap: 6 }}>
          {['ALL', 'SENT', 'FAILED', 'PENDING'].map((st) => (
            <button
              key={st}
              type="button"
              onClick={() => setStatusFilter(st)}
              style={{
                padding: '6px 12px',
                fontSize: 12,
                fontWeight: 700,
                borderRadius: 8,
                border: statusFilter === st ? '1px solid #0284c7' : '1px solid #e2e8f0',
                background: statusFilter === st ? '#e0f2fe' : '#ffffff',
                color: statusFilter === st ? '#0369a1' : '#64748b',
                cursor: 'pointer',
              }}
            >
              {st === 'ALL' ? 'Tất cả' : st === 'SENT' ? 'Đã gửi' : st === 'FAILED' ? 'Thất bại' : 'Chờ gửi'}
            </button>
          ))}
        </div>

        <div style={{ flex: 1, minWidth: 200, display: 'flex', gap: 8 }}>
          <input
            type="text"
            placeholder="Tìm theo mã đơn (ví dụ: PT-260930)..."
            value={searchRef}
            onChange={(e) => setSearchRef(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') loadEmails()
            }}
            style={{
              flex: 1,
              padding: '6px 12px',
              fontSize: 13,
              borderRadius: 8,
              border: '1px solid #cbd5e1',
              outline: 'none',
            }}
          />
          <button
            type="button"
            onClick={loadEmails}
            className="secondary-button"
            style={{ padding: '6px 14px', fontSize: 13, fontWeight: 600 }}
          >
            Tìm
          </button>
        </div>
      </div>

      {/* Table */}
      <div style={{ background: '#ffffff', border: '1px solid #e2e8f0', borderRadius: 12, overflow: 'hidden' }}>
        {loading ? (
          <div style={{ padding: 40, textAlign: 'center', color: '#64748b', fontSize: 13 }}>
            <div className="inline-block w-6 h-6 border-2 border-brand-blue-600 border-t-transparent rounded-full animate-spin mb-2" />
            <div>Đang tải dữ liệu hộp thư...</div>
          </div>
        ) : emails.length === 0 ? (
          <div style={{ padding: 50, textAlign: 'center', color: '#94a3b8', fontSize: 13 }}>
            <Mail size={36} style={{ margin: '0 auto 10px', opacity: 0.5 }} />
            <div>Không có email nào trong hộp thư outbox.</div>
          </div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13, textAlign: 'left' }}>
            <thead>
              <tr style={{ background: '#f8fafc', borderBottom: '1px solid #e2e8f0', color: '#475569', fontSize: 12, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                <th style={{ padding: '12px 16px' }}>Mã / Tham chiếu</th>
                <th style={{ padding: '12px 16px' }}>Người nhận</th>
                <th style={{ padding: '12px 16px' }}>Tiêu đề thư</th>
                <th style={{ padding: '12px 16px' }}>Trạng thái</th>
                <th style={{ padding: '12px 16px' }}>Thời gian gửi</th>
                <th style={{ padding: '12px 16px', textAlign: 'right' }}>Thao tác</th>
              </tr>
            </thead>
            <tbody>
              {displayedEmails.map((m) => (
                <tr key={m.id} style={{ borderBottom: '1px solid #f1f5f9' }}>
                  <td style={{ padding: '12px 16px', fontWeight: 700, color: '#1e40af', fontFamily: 'monospace' }}>
                    {m.reference_id || `#${m.id}`}
                    <div style={{ fontSize: 11, color: '#94a3b8', fontWeight: 400 }}>{m.reference_type}</div>
                  </td>
                  <td style={{ padding: '12px 16px' }}>
                    <div style={{ fontWeight: 600, color: '#1e293b' }}>{m.recipient_email}</div>
                  </td>
                  <td style={{ padding: '12px 16px', maxWidth: 280, color: '#334155' }}>
                    <div className="line-clamp-1" title={m.subject}>
                      {m.subject}
                    </div>
                    {m.last_error && (
                      <div style={{ fontSize: 11, color: '#dc2626', marginTop: 2 }} className="line-clamp-1" title={m.last_error}>
                        ⚠️ {m.last_error}
                      </div>
                    )}
                  </td>
                  <td style={{ padding: '12px 16px' }}>
                    {m.status === 'SENT' ? (
                      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, padding: '3px 8px', borderRadius: 6, fontSize: 11, fontWeight: 700, background: '#dcfce7', color: '#15803d' }}>
                        <CheckCircle2 size={12} /> Đã gửi
                      </span>
                    ) : m.status === 'FAILED' ? (
                      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, padding: '3px 8px', borderRadius: 6, fontSize: 11, fontWeight: 700, background: '#fee2e2', color: '#b91c1c' }}>
                        <XCircle size={12} /> Lỗi gửi ({m.retry_count}/{m.max_retries})
                      </span>
                    ) : m.status === 'SENDING' ? (
                      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, padding: '3px 8px', borderRadius: 6, fontSize: 11, fontWeight: 700, background: '#e0f2fe', color: '#0369a1' }}>
                        <RefreshCw size={12} className="animate-spin" /> Đang gửi...
                      </span>
                    ) : (
                      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, padding: '3px 8px', borderRadius: 6, fontSize: 11, fontWeight: 700, background: '#fef3c7', color: '#b45309' }}>
                        <Clock size={12} /> Đang chờ
                      </span>
                    )}
                  </td>
                  <td style={{ padding: '12px 16px', fontSize: 12, color: '#64748b' }}>
                    {m.sent_at ? new Date(m.sent_at).toLocaleString('vi-VN') : m.created_at ? new Date(m.created_at).toLocaleString('vi-VN') : '—'}
                  </td>
                  <td style={{ padding: '12px 16px', textAlign: 'right' }}>
                    <div style={{ display: 'flex', gap: 6, justifyContent: 'flex-end' }}>
                      <button
                        type="button"
                        onClick={() => handleOpenDetail(m.id)}
                        className="secondary-button"
                        style={{ padding: '4px 8px', fontSize: 12 }}
                        title="Xem bản xem trước HTML"
                      >
                        <Eye size={13} /> Xem thư
                      </button>
                      <button
                        type="button"
                        disabled={resendingId === m.id || m.status === 'SENT'}
                        onClick={() => handleResend(m.id)}
                        className="primary-button"
                        style={{
                          padding: '4px 8px',
                          fontSize: 12,
                          background: m.status === 'SENT' ? '#94a3b8' : '#0284c7',
                          borderColor: m.status === 'SENT' ? '#94a3b8' : '#0284c7',
                          cursor: m.status === 'SENT' ? 'not-allowed' : 'pointer',
                        }}
                        title={m.status === 'SENT' ? 'Email đã gửi thành công, không gửi lại' : 'Gửi lại email này'}
                      >
                        <Send size={13} className={resendingId === m.id ? 'animate-spin' : ''} /> Gửi lại
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {!loading && emails.length > 0 && (
          <PaginationBar
            currentPage={currentPage}
            totalPages={totalPages}
            pageSize={pageSize}
            totalItems={emails.length}
            itemName="email"
            onPageChange={setCurrentPage}
            onPageSizeChange={setPageSize}
            pageSizeOptions={[10, 15, 25, 50]}
          />
        )}
      </div>

      {/* DETAIL MODAL WITH HTML PREVIEW */}
      {selectedEmail && (
        <div className="modal-backdrop" onClick={() => setSelectedEmail(null)}>
          <div
            className="modal-window"
            style={{
              maxWidth: 720,
              width: '100%',
              maxHeight: '90vh',
              overflowY: 'auto',
              background: '#ffffff',
              borderRadius: 16,
              padding: 24,
              boxShadow: '0 20px 60px rgba(0,0,0,0.3)',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid #e2e8f0', paddingBottom: 12, marginBottom: 16 }}>
              <div>
                <span style={{ fontSize: 11, fontWeight: 700, color: '#64748b', textTransform: 'uppercase' }}>Bản xem trước Email Outbox</span>
                <h3 style={{ margin: '2px 0 0', fontSize: 18, color: '#0f172a', fontWeight: 800 }}>{selectedEmail.subject}</h3>
              </div>
              <button
                type="button"
                onClick={() => setSelectedEmail(null)}
                style={{ background: '#f1f5f9', border: 'none', borderRadius: 8, padding: 6, cursor: 'pointer', color: '#64748b' }}
              >
                <X size={18} />
              </button>
            </div>

            {/* Email Meta */}
            <div style={{ background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 10, padding: 12, fontSize: 12, color: '#334155', marginBottom: 16, lineHeight: 1.6 }}>
              <div><b>Gửi tới:</b> {selectedEmail.recipient_email}</div>
              <div><b>Mã tham chiếu:</b> {selectedEmail.reference_id || 'N/A'} ({selectedEmail.reference_type})</div>
              <div>
                <b>Trạng thái:</b>{' '}
                <span style={{ fontWeight: 700, color: selectedEmail.status === 'SENT' ? '#15803d' : '#b91c1c' }}>
                  {selectedEmail.status}
                </span>{' '}
                (Đã thử {selectedEmail.retry_count}/{selectedEmail.max_retries} lần)
              </div>
              {selectedEmail.last_error && (
                <div style={{ color: '#b91c1c', marginTop: 4 }}>
                  <b>Lỗi gần nhất:</b> {selectedEmail.last_error}
                </div>
              )}
            </div>

            {/* Rendered HTML */}
            <div style={{ border: '1px solid #cbd5e1', borderRadius: 12, overflow: 'hidden', marginBottom: 16, background: '#f8fafc' }}>
              <iframe
                title="Email Preview"
                srcDoc={selectedEmail.body_html}
                style={{ width: '100%', height: 420, border: 'none' }}
              />
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
              <button
                type="button"
                onClick={() => setSelectedEmail(null)}
                className="secondary-button"
                style={{ padding: '8px 16px', fontSize: 13 }}
              >
                Đóng
              </button>
              <button
                type="button"
                disabled={resendingId === selectedEmail.id || selectedEmail.status === 'SENT'}
                onClick={() => handleResend(selectedEmail.id)}
                className="primary-button"
                style={{
                  padding: '8px 18px',
                  fontSize: 13,
                  background: selectedEmail.status === 'SENT' ? '#94a3b8' : '#0284c7',
                  borderColor: selectedEmail.status === 'SENT' ? '#94a3b8' : '#0284c7',
                  cursor: selectedEmail.status === 'SENT' ? 'not-allowed' : 'pointer',
                }}
                title={selectedEmail.status === 'SENT' ? 'Email đã gửi thành công, không gửi lại' : 'Gửi lại ngay'}
              >
                <Send size={14} className={resendingId === selectedEmail.id ? 'animate-spin' : ''} /> Gửi lại ngay
              </button>
            </div>
          </div>
        </div>
      )}

      {/* TEST EMAIL MODAL */}
      {isTestModalOpen && (
        <div className="modal-backdrop" onClick={() => setIsTestModalOpen(false)}>
          <div
            className="modal-window"
            style={{
              maxWidth: 460,
              width: '100%',
              background: '#ffffff',
              borderRadius: 16,
              padding: 24,
              boxShadow: '0 20px 60px rgba(0,0,0,0.3)',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid #e2e8f0', paddingBottom: 12, marginBottom: 16 }}>
              <h3 style={{ margin: 0, fontSize: 17, color: '#0f172a', fontWeight: 800 }}>Kiểm tra kết nối Gmail SMTP</h3>
              <button
                type="button"
                onClick={() => setIsTestModalOpen(false)}
                style={{ background: '#f1f5f9', border: 'none', borderRadius: 8, padding: 6, cursor: 'pointer', color: '#64748b' }}
              >
                <X size={18} />
              </button>
            </div>

            <form onSubmit={handleSendTest} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              <div>
                <label style={{ display: 'block', fontSize: 12, fontWeight: 700, color: '#334155', marginBottom: 4 }}>
                  Email người nhận kiểm tra <span style={{ color: '#ef4444' }}>*</span>
                </label>
                <input
                  type="email"
                  required
                  placeholder="Ví dụ: your_email@gmail.com"
                  value={testRecipient}
                  onChange={(e) => setTestRecipient(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '8px 12px',
                    fontSize: 13,
                    borderRadius: 8,
                    border: '1px solid #cbd5e1',
                    outline: 'none',
                    boxSizing: 'border-box',
                  }}
                />
                <p style={{ margin: '6px 0 0', fontSize: 11, color: '#64748b' }}>
                  Hệ thống sẽ thử kết nối trực tiếp tới cổng SMTP của Gmail và gửi một bức thư chào mừng mẫu.
                </p>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 10 }}>
                <button
                  type="button"
                  onClick={() => setIsTestModalOpen(false)}
                  className="secondary-button"
                  style={{ padding: '8px 14px', fontSize: 13 }}
                >
                  Hủy
                </button>
                <button
                  type="submit"
                  disabled={isSendingTest}
                  className="primary-button"
                  style={{ padding: '8px 18px', fontSize: 13, background: '#0284c7', borderColor: '#0284c7' }}
                >
                  {isSendingTest ? 'Đang gửi...' : 'Gửi kiểm tra ngay'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
