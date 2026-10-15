import { useEffect, useState } from 'react'
import {
  ClipboardCheck,
  Plus,
  AlertCircle,
  CheckCircle2,
  X,
  History,
  FileText,
  ShieldAlert,
  Check,
} from 'lucide-react'
import { api } from '../../services/api'
import { useAuth } from '../../services/auth'

interface AdjustmentItem {
  id: number
  adjustment_code: string
  reason: string
  status: string
  is_large_adjustment?: boolean
  total_quantity_variance?: number
  total_amount_variance?: number
  created_at: string | null
  items_count: number
}

export function WarehouseAdjustmentsPage() {
  const { user } = useAuth()
  const [adjustments, setAdjustments] = useState<AdjustmentItem[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)

  // Modal State
  const [showModal, setShowModal] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [reason, setReason] = useState('')
  const [batchId, setBatchId] = useState(1)
  const [actualQuantity, setActualQuantity] = useState(100)
  const [formError, setFormError] = useState<string | null>(null)

  const fetchAdjustments = () => {
    setLoading(true)
    api<{ items: AdjustmentItem[]; total: number }>('/warehouse-portal/adjustments')
      .then((res) => {
        setAdjustments(res.items || [])
        setTotal(res.total || 0)
      })
      .catch((err) => console.error(err))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    fetchAdjustments()
  }, [])

  const handleCreateAdjustment = async (e: React.FormEvent) => {
    e.preventDefault()
    setFormError(null)

    if (!reason.trim() || reason.trim().length < 5) {
      setFormError('Bắt buộc phải nhập lý do điều chỉnh rõ ràng (tối thiểu 5 ký tự)')
      return
    }

    setSubmitting(true)
    try {
      await api('/warehouse-portal/adjustments', {
        method: 'POST',
        body: JSON.stringify({
          reason: reason.trim(),
          items: [
            {
              batch_id: batchId,
              actual_quantity: actualQuantity,
              reason: reason.trim(),
            },
          ],
        }),
      })
      setShowModal(false)
      setReason('')
      fetchAdjustments()
      alert('Đã ghi nhận phiếu kiểm kê và điều chỉnh tồn kho thành công!')
    } catch (err: any) {
      setFormError(err?.message || 'Không thể tạo phiếu điều chỉnh')
    } finally {
      setSubmitting(false)
    }
  }

  const handleApprove = async (id: number) => {
    if (!window.confirm('Bạn có chắc chắn muốn phê duyệt phiếu điều chỉnh tồn kho lớn này?')) return
    try {
      await api(`/warehouse-portal/adjustments/${id}/admin-approve`, { method: 'POST' })
      alert('Đã phê duyệt và áp dụng số lượng tồn kho thành công!')
      fetchAdjustments()
    } catch (err: any) {
      alert(err.message || 'Không thể phê duyệt')
    }
  }

  const handleReject = async (id: number) => {
    const reasonPrompt = window.prompt('Nhập lý do từ chối phiếu điều chỉnh:')
    if (!reasonPrompt) return
    try {
      await api(`/warehouse-portal/adjustments/${id}/admin-reject`, {
        method: 'POST',
        body: JSON.stringify({ reason: reasonPrompt }),
      })
      alert('Đã từ chối phiếu điều chỉnh!')
      fetchAdjustments()
    } catch (err: any) {
      alert(err.message || 'Không thể từ chối')
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
          <div style={{ fontSize: '11px', fontWeight: 800, color: '#d97706', textTransform: 'uppercase', letterSpacing: '0.8px' }}>
            KIỂM KÊ VẬT LÝ & ĐỐI SOÁT GSP
          </div>
          <h1 style={{ margin: '4px 0 0', fontSize: '22px', fontWeight: 900, color: '#0f172a' }}>
            Kiểm Kê & Điều Chỉnh Tồn Kho
          </h1>
          <p style={{ margin: '4px 0 0', fontSize: '13px', color: '#64748b' }}>
            Cân đối số lượng thực tế với phần mềm. Biến động lớn (&ge;50 sp hoặc &ge;10M VNĐ) cần Admin duyệt.
          </p>
        </div>

        <button
          type="button"
          onClick={() => {
            setFormError(null)
            setShowModal(true)
          }}
          style={{
            background: 'linear-gradient(135deg, #d97706, #b45309)',
            color: 'white',
            padding: '10px 18px',
            borderRadius: '12px',
            fontSize: '13px',
            fontWeight: 800,
            border: 'none',
            cursor: 'pointer',
            display: 'inline-flex',
            alignItems: 'center',
            gap: '8px',
            boxShadow: '0 3px 10px rgba(217, 119, 6, 0.3)',
          }}
        >
          <Plus size={16} /> Phiếu Kiểm Kê Mới
        </button>
      </div>

      {/* Adjustments Table */}
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
                <th style={{ padding: '14px 18px' }}>Mã Phiếu Kiểm Kê</th>
                <th style={{ padding: '14px 18px' }}>Lý Do Bắt Buộc (Giải Trình)</th>
                <th style={{ padding: '14px 18px' }}>Số Lô Cân Đối</th>
                <th style={{ padding: '14px 18px' }}>Trạng Thái & Phê Duyệt</th>
                <th style={{ padding: '14px 18px' }}>Thời Gian Ghi Nhận</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={5} style={{ padding: '40px', textAlign: 'center', color: '#94a3b8', fontWeight: 600 }}>
                    Đang tải lịch sử kiểm kê & điều chỉnh…
                  </td>
                </tr>
              ) : adjustments.length === 0 ? (
                <tr>
                  <td colSpan={5} style={{ padding: '40px', textAlign: 'center', color: '#94a3b8', fontWeight: 600 }}>
                    Chưa có phiếu kiểm kê hoặc điều chỉnh tồn kho nào.
                  </td>
                </tr>
              ) : (
                adjustments.map((a) => (
                  <tr
                    key={a.id}
                    style={{ borderBottom: '1px solid #f1f5f9', transition: 'background 0.15s ease' }}
                    onMouseEnter={(e) => (e.currentTarget.style.background = '#f8fafc')}
                    onMouseLeave={(e) => (e.currentTarget.style.background = 'white')}
                  >
                    <td style={{ padding: '14px 18px', fontFamily: 'monospace', fontWeight: 900, color: '#b45309' }}>
                      {a.adjustment_code}
                    </td>

                    <td style={{ padding: '14px 18px', fontWeight: 700, color: '#0f172a' }}>
                      {a.reason}
                    </td>

                    <td style={{ padding: '14px 18px' }}>
                      <span
                        style={{
                          background: '#f1f5f9',
                          padding: '3px 8px',
                          borderRadius: '6px',
                          fontSize: '11.5px',
                          fontWeight: 700,
                          color: '#475569',
                        }}
                      >
                        {a.items_count} lô thuốc
                      </span>
                    </td>

                    <td style={{ padding: '14px 18px' }}>
                      {a.status === 'CONFIRMED' ? (
                        <span
                          style={{
                            padding: '4px 10px',
                            borderRadius: '9999px',
                            fontSize: '11px',
                            fontWeight: 800,
                            background: '#dcfce7',
                            color: '#166534',
                          }}
                        >
                          ✓ Đã xác nhận & Cập nhật tồn
                        </span>
                      ) : a.status === 'PENDING_ADMIN_APPROVAL' ? (
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                          <span
                            style={{
                              padding: '4px 10px',
                              borderRadius: '9999px',
                              fontSize: '11px',
                              fontWeight: 800,
                              background: '#fffbeb',
                              color: '#b45309',
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '4px',
                            }}
                          >
                            ⚠️ Chờ Admin duyệt ({a.total_quantity_variance} sp)
                          </span>
                          {user?.role === 'ADMIN' && (
                            <div style={{ display: 'flex', gap: '4px' }}>
                              <button
                                onClick={() => handleApprove(a.id)}
                                style={{
                                  background: '#059669',
                                  color: 'white',
                                  border: 'none',
                                  padding: '3px 8px',
                                  borderRadius: '6px',
                                  fontSize: '11px',
                                  fontWeight: 700,
                                  cursor: 'pointer',
                                }}
                              >
                                Duyệt
                              </button>
                              <button
                                onClick={() => handleReject(a.id)}
                                style={{
                                  background: '#dc2626',
                                  color: 'white',
                                  border: 'none',
                                  padding: '3px 8px',
                                  borderRadius: '6px',
                                  fontSize: '11px',
                                  fontWeight: 700,
                                  cursor: 'pointer',
                                }}
                              >
                                Từ chối
                              </button>
                            </div>
                          )}
                        </div>
                      ) : (
                        <span
                          style={{
                            padding: '4px 10px',
                            borderRadius: '9999px',
                            fontSize: '11px',
                            fontWeight: 800,
                            background: '#fee2e2',
                            color: '#991b1b',
                          }}
                        >
                          ✕ {a.status}
                        </span>
                      )}
                    </td>

                    <td style={{ padding: '14px 18px', color: '#64748b', fontSize: '12px' }}>
                      {a.created_at ? new Date(a.created_at).toLocaleString('vi-VN') : '—'}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Create Modal */}
      {showModal && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(15, 23, 42, 0.65)',
            backdropFilter: 'blur(4px)',
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
              borderRadius: '20px',
              maxWidth: '520px',
              width: '100%',
              padding: '28px',
              boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.25)',
              display: 'flex',
              flexDirection: 'column',
              gap: '18px',
            }}
          >
            {/* Modal Header */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid #e2e8f0', paddingBottom: '14px' }}>
              <div>
                <h3 style={{ margin: 0, fontSize: '18px', fontWeight: 900, color: '#0f172a' }}>
                  Tạo Phiếu Điều Chỉnh Tồn Kho
                </h3>
                <p style={{ margin: '4px 0 0', fontSize: '12px', color: '#64748b' }}>
                  Ghi nhận chênh lệch kiểm đếm thực tế tại chi nhánh
                </p>
              </div>
              <button
                type="button"
                onClick={() => setShowModal(false)}
                style={{ background: 'none', border: 'none', color: '#94a3b8', cursor: 'pointer', padding: '4px' }}
              >
                <X size={20} />
              </button>
            </div>

            <div
              style={{
                background: '#fffbeb',
                border: '1px solid #fde68a',
                borderRadius: '10px',
                padding: '10px 14px',
                fontSize: '12px',
                color: '#92400e',
                lineHeight: '1.5',
              }}
            >
              ℹ️ <strong>Quy tắc giám sát tồn kho (Rule 2):</strong> Nếu số lượng chênh lệch &ge; 50 sản phẩm hoặc giá trị biến động &ge; 10.000.000 VNĐ, phiếu sẽ tự động chuyển sang trạng thái <strong>"Chờ Admin phê duyệt"</strong> trước khi áp dụng tồn kho.
            </div>

            {formError && (
              <div
                style={{
                  background: '#fef2f2',
                  border: '1px solid #fecaca',
                  borderRadius: '10px',
                  padding: '12px 14px',
                  color: '#b91c1c',
                  fontSize: '12.5px',
                  fontWeight: 600,
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                }}
              >
                <AlertCircle size={16} style={{ flexShrink: 0 }} /> {formError}
              </div>
            )}

            <form onSubmit={handleCreateAdjustment} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '11px', fontWeight: 800, color: '#334155', textTransform: 'uppercase', marginBottom: '6px' }}>
                  Mã Lô Thuốc Cần Điều Chỉnh (Batch ID) *
                </label>
                <input
                  type="number"
                  min={1}
                  value={batchId}
                  onChange={(e) => setBatchId(Number(e.target.value))}
                  style={{
                    width: '100%',
                    padding: '10px 14px',
                    borderRadius: '10px',
                    border: '1.5px solid #cbd5e1',
                    fontSize: '13.5px',
                    outline: 'none',
                    boxSizing: 'border-box',
                  }}
                  required
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '11px', fontWeight: 800, color: '#334155', textTransform: 'uppercase', marginBottom: '6px' }}>
                  Số Lượng Đếm Thực Tế Tại Kho (Actual Quantity) *
                </label>
                <input
                  type="number"
                  min={0}
                  value={actualQuantity}
                  onChange={(e) => setActualQuantity(Number(e.target.value))}
                  style={{
                    width: '100%',
                    padding: '10px 14px',
                    borderRadius: '10px',
                    border: '1.5px solid #cbd5e1',
                    fontSize: '13.5px',
                    fontWeight: 700,
                    outline: 'none',
                    boxSizing: 'border-box',
                  }}
                  required
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '11px', fontWeight: 800, color: '#334155', textTransform: 'uppercase', marginBottom: '6px' }}>
                  Lý Do Điều Chỉnh * <span style={{ color: '#ef4444' }}>(Bắt buộc theo chuẩn GSP)</span>
                </label>
                <textarea
                  rows={3}
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  placeholder="VD: Bao bì bị móp méo trong quá trình bốc xếp; Kiểm đếm định kỳ sai lệch 2 hộp…"
                  style={{
                    width: '100%',
                    padding: '10px 14px',
                    borderRadius: '10px',
                    border: '1.5px solid #cbd5e1',
                    fontSize: '13px',
                    outline: 'none',
                    resize: 'vertical',
                    boxSizing: 'border-box',
                  }}
                  required
                />
                <div style={{ fontSize: '11px', color: '#64748b', marginTop: '4px' }}>
                  Mọi thao tác điều chỉnh tồn kho sẽ được lưu lại trong Nhật Ký Thao Tác Kho để truy vết.
                </div>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: '10px', paddingTop: '10px', borderTop: '1px solid #e2e8f0' }}>
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  style={{
                    padding: '10px 18px',
                    borderRadius: '10px',
                    border: '1px solid #cbd5e1',
                    background: 'white',
                    color: '#64748b',
                    fontSize: '13px',
                    fontWeight: 700,
                    cursor: 'pointer',
                  }}
                >
                  Hủy
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  style={{
                    padding: '10px 22px',
                    borderRadius: '10px',
                    border: 'none',
                    background: 'linear-gradient(135deg, #d97706, #b45309)',
                    color: 'white',
                    fontSize: '13px',
                    fontWeight: 800,
                    cursor: 'pointer',
                    boxShadow: '0 2px 8px rgba(217, 119, 6, 0.3)',
                  }}
                >
                  {submitting ? 'Đang cập nhật…' : 'Xác nhận điều chỉnh'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
