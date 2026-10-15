import {
  AlertCircle,
  Banknote,
  CheckCircle2,
  Clock,
  CreditCard,
  Eye,
  FileCheck,
  FileText,
  Filter,
  Layers,
  Loader2,
  RefreshCw,
  Search,
  ShieldCheck,
  Smartphone,
  X,
  XCircle,
} from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { AdminPageHeader } from '../components/AdminPageHeader'
import { FilterBar } from '../components/FilterBar'
import { PaginationBar } from '../components/PaginationBar'
import { api } from '../services/api'

interface RefundSummary {
  id: number
  refund_code: string
  order_code: string
  return_code: string | null
  refund_amount: number
  refund_method: string
  status: string
  reconciliation_status: string
  beneficiary_bank: string | null
  beneficiary_account_number: string | null
  beneficiary_account_name: string | null
  bank_transfer_ref: string | null
  gateway_transaction_id: string | null
  created_at: string | null
  processed_at: string | null
}

interface RefundAttemptItem {
  id: number
  attempt_number: number
  provider: string
  status: string
  error_message: string | null
  created_at: string
}

interface RefundDetailData extends RefundSummary {
  order_id: number
  reason: string | null
  failure_reason: string | null
  proof_document_url: string | null
  reconciliation_notes: string | null
  attempts: RefundAttemptItem[]
}

const STATUS_CONFIG: Record<string, { label: string; color: string; bg: string }> = {
  PENDING: { label: 'Chờ chi tiền', color: '#b45309', bg: '#fef3c7' },
  PROCESSING: { label: 'Đang xử lý', color: '#1d4ed8', bg: '#dbeafe' },
  SUCCEEDED: { label: 'Hoàn tiền thành công', color: '#15803d', bg: '#dcfce7' },
  FAILED: { label: 'Thất bại', color: '#b91c1c', bg: '#fee2e2' },
  CANCELLED: { label: 'Đã hủy', color: '#475569', bg: '#f1f5f9' },
}

const RECON_CONFIG: Record<string, { label: string; color: string; bg: string }> = {
  PENDING: { label: 'Chưa đối soát', color: '#475569', bg: '#f1f5f9' },
  MATCHED: { label: 'Khớp sổ sách 100%', color: '#15803d', bg: '#dcfce7' },
  MISMATCH: { label: 'Lệch số dư / Lỗi', color: '#b91c1c', bg: '#fee2e2' },
  NEEDS_REVIEW: { label: 'Kế toán cần kiểm tra', color: '#c2410c', bg: '#ffedd5' },
}

export function RefundsPage() {
  const [refunds, setRefunds] = useState<RefundSummary[]>([])
  const [totalCount, setTotalCount] = useState<number>(0)
  const [loading, setLoading] = useState<boolean>(true)
  const [search, setSearch] = useState<string>('')
  const [statusFilter, setStatusFilter] = useState<string>('')
  const [methodFilter, setMethodFilter] = useState<string>('')
  const [reconFilter, setReconFilter] = useState<string>('')

  // Phân trang
  const [currentPage, setCurrentPage] = useState<number>(1)
  const [pageSize, setPageSize] = useState<number>(15)

  // Detail Modal & Action Modal State
  const [selectedRefundCode, setSelectedRefundCode] = useState<string | null>(null)
  const [refundDetail, setRefundDetail] = useState<RefundDetailData | null>(null)
  const [loadingDetail, setLoadingDetail] = useState<boolean>(false)
  const [actionLoading, setActionLoading] = useState<boolean>(false)
  const [actionError, setActionError] = useState<string>('')

  // Manual bank transfer modal
  const [manualBankCode, setManualBankCode] = useState<string | null>(null)
  const [uncRef, setUncRef] = useState<string>('')
  const [uncProofUrl, setUncProofUrl] = useState<string>('')
  const [uncNotes, setUncNotes] = useState<string>('Kế toán H4Care đã chuyển khoản hoàn tiền thành công theo ủy nhiệm chi.')

  // Reconciliation modal
  const [reconCode, setReconCode] = useState<string | null>(null)
  const [reconStatus, setReconStatus] = useState<string>('MATCHED')
  const [reconNotes, setReconNotes] = useState<string>('Khớp đúng sao kê tài khoản ngân hàng / ví MoMo.')

  const totalPages = Math.max(1, Math.ceil(totalCount / pageSize))

  const loadRefunds = async (page = currentPage, size = pageSize) => {
    setLoading(true)
    try {
      const params = new URLSearchParams()
      if (statusFilter) params.append('status', statusFilter)
      if (methodFilter) params.append('refund_method', methodFilter)
      if (reconFilter) params.append('reconciliation_status', reconFilter)
      if (search.trim()) params.append('search', search.trim())
      params.append('page', String(page))
      params.append('page_size', String(size))

      const res = await api<{ total: number; items?: RefundSummary[]; refunds?: RefundSummary[] }>(
        `/admin/refunds?${params.toString()}`
      )
      const dataList = res.items || res.refunds || []
      setRefunds(dataList)
      setTotalCount(res.total ?? dataList.length)
    } catch (err) {
      console.error('Failed to load admin refunds', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    setCurrentPage(1)
    loadRefunds(1, pageSize)
  }, [statusFilter, methodFilter, reconFilter])

  useEffect(() => {
    const timer = setTimeout(() => {
      setCurrentPage(1)
      loadRefunds(1, pageSize)
    }, 350)
    return () => clearTimeout(timer)
  }, [search])

  const openDetail = async (code: string) => {
    setSelectedRefundCode(code)
    setLoadingDetail(true)
    setActionError('')
    try {
      const detail = await api<RefundDetailData>(`/admin/refunds/${code}`)
      setRefundDetail(detail)
    } catch (err: any) {
      setActionError(err.message || 'Không thể tải chi tiết hoàn tiền')
    } finally {
      setLoadingDetail(false)
    }
  }

  const handleManualBankSubmit = async () => {
    if (!manualBankCode || !uncRef.trim()) {
      setActionError('Vui lòng nhập mã giao dịch / số UNC ngân hàng')
      return
    }
    setActionLoading(true)
    setActionError('')
    try {
      await api(`/admin/refunds/${manualBankCode}/manual-bank`, {
        method: 'POST',
        body: JSON.stringify({
          bank_transfer_ref: uncRef.trim(),
          proof_document_url: uncProofUrl.trim() || undefined,
          notes: uncNotes.trim() || undefined,
        }),
      })
      setManualBankCode(null)
      setUncRef('')
      loadRefunds()
      if (selectedRefundCode === manualBankCode) openDetail(manualBankCode)
    } catch (err: any) {
      setActionError(err.message || 'Xác nhận chuyển khoản thất bại')
    } finally {
      setActionLoading(false)
    }
  }

  const handleMomoRefund = async (code: string) => {
    if (!confirm(`Kích hoạt hoàn tiền tự động qua MoMo API Sandbox cho phiếu #${code}?`)) return
    setActionLoading(true)
    setActionError('')
    try {
      await api(`/admin/refunds/${code}/momo`, {
        method: 'POST',
      })
      loadRefunds()
      if (selectedRefundCode === code) openDetail(code)
    } catch (err: any) {
      alert(`Lỗi cổng MoMo: ${err.message}`)
    } finally {
      setActionLoading(false)
    }
  }

  const handleReconcileSubmit = async () => {
    if (!reconCode) return
    setActionLoading(true)
    setActionError('')
    try {
      await api(`/admin/refunds/${reconCode}/reconcile`, {
        method: 'POST',
        body: JSON.stringify({
          reconciliation_status: reconStatus,
          note: reconNotes.trim() || undefined,
        }),
      })
      setReconCode(null)
      loadRefunds()
      if (selectedRefundCode === reconCode) openDetail(reconCode)
    } catch (err: any) {
      setActionError(err.message || 'Đối soát thất bại')
    } finally {
      setActionLoading(false)
    }
  }

  return (
    <div className="admin-page-container" style={{ padding: '24px 32px' }}>
      <AdminPageHeader
        title="Hoàn Tiền & Đối Soát Tài Chính (Refunds)"
        subtitle="Quản lý ủy nhiệm chi ngân hàng, hoàn tự động qua MoMo và đối soát dòng tiền kế toán GPP."
        breadcrumbs={[
          { label: 'Trang chủ', href: '/' },
          { label: 'Hậu Mãi', href: '/returns' },
          { label: 'Hoàn tiền & Đối soát' },
        ]}
      />

      {/* Filter and Search Bar */}
      <FilterBar
        searchValue={search}
        onSearchChange={setSearch}
        searchPlaceholder="Tìm kiếm theo mã hoàn tiền, mã đơn, số tài khoản, mã UNC..."
        onRefresh={loadRefunds}
        isRefreshing={loading}
        totalCount={totalCount}
        filteredCount={refunds.length}
        unitLabel="phiếu chi"
      >
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            style={{
              padding: '6px 12px',
              borderRadius: 8,
              border: '1px solid #cbd5e1',
              background: '#fff',
              fontSize: 13,
              color: '#1e293b',
              fontWeight: 600,
            }}
          >
            <option value="">Tất cả trạng thái chi</option>
            <option value="PENDING">Chờ chi tiền</option>
            <option value="PROCESSING">Đang xử lý</option>
            <option value="SUCCEEDED">Đã hoàn tiền thành công</option>
            <option value="FAILED">Thất bại</option>
          </select>

          <select
            value={methodFilter}
            onChange={(e) => setMethodFilter(e.target.value)}
            style={{
              padding: '6px 12px',
              borderRadius: 8,
              border: '1px solid #cbd5e1',
              background: '#fff',
              fontSize: 13,
              color: '#1e293b',
              fontWeight: 600,
            }}
          >
            <option value="">Tất cả phương thức</option>
            <option value="BANK_TRANSFER">Chuyển khoản Ngân hàng (UNC)</option>
            <option value="MOMO">Cổng thanh toán MoMo</option>
          </select>

          <select
            value={reconFilter}
            onChange={(e) => setReconFilter(e.target.value)}
            style={{
              padding: '6px 12px',
              borderRadius: 8,
              border: '1px solid #cbd5e1',
              background: '#fff',
              fontSize: 13,
              color: '#1e293b',
              fontWeight: 600,
            }}
          >
            <option value="">Tất cả đối soát kế toán</option>
            <option value="MATCHED">Khớp 100% (MATCHED)</option>
            <option value="PENDING">Chưa đối soát (PENDING)</option>
            <option value="MISMATCH">Lệch dòng tiền (MISMATCH)</option>
            <option value="NEEDS_REVIEW">Cần xem xét (NEEDS_REVIEW)</option>
          </select>
        </div>
      </FilterBar>

      {/* Main Table */}
      <div
        style={{
          background: '#ffffff',
          borderRadius: 14,
          border: '1px solid #e2e8f0',
          overflow: 'hidden',
          boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
          marginTop: 16,
        }}
      >
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: 13 }}>
            <thead>
              <tr style={{ background: '#f8fafc', borderBottom: '1px solid #e2e8f0', color: '#475569', fontWeight: 700 }}>
                <th style={{ padding: '14px 16px' }}>Mã Hoàn Tiền</th>
                <th style={{ padding: '14px 16px' }}>Đơn Hàng / Đổi Trả</th>
                <th style={{ padding: '14px 16px' }}>Số Tiền Hoàn</th>
                <th style={{ padding: '14px 16px' }}>Phương Thức</th>
                <th style={{ padding: '14px 16px' }}>Thụ Hưởng / Tham Chiếu</th>
                <th style={{ padding: '14px 16px' }}>Trạng Thái Chi</th>
                <th style={{ padding: '14px 16px' }}>Đối Soát Kế Toán</th>
                <th style={{ padding: '14px 16px', textAlign: 'right' }}>Thao Tác</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={8} style={{ padding: 40, textAlign: 'center', color: '#64748b' }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}>
                      <RefreshCw size={16} className="spin" />
                      <span>Đang tải danh sách hoàn tiền...</span>
                    </div>
                  </td>
                </tr>
              ) : refunds.length === 0 ? (
                <tr>
                  <td colSpan={8} style={{ padding: 50, textAlign: 'center', color: '#94a3b8' }}>
                    <Banknote size={32} style={{ margin: '0 auto 10px', opacity: 0.5 }} />
                    <p style={{ margin: 0, fontWeight: 600 }}>Không tìm thấy phiếu hoàn tiền nào</p>
                  </td>
                </tr>
              ) : (
                refunds.map((ref) => {
                  const cfg = STATUS_CONFIG[ref.status] || { label: ref.status, color: '#334155', bg: '#f1f5f9' }
                  const reconCfg = RECON_CONFIG[ref.reconciliation_status] || { label: ref.reconciliation_status, color: '#334155', bg: '#f1f5f9' }
                  const isMomo = ref.refund_method === 'MOMO'

                  return (
                    <tr
                      key={ref.refund_code}
                      style={{ borderBottom: '1px solid #f1f5f9', transition: 'background 0.15s' }}
                      onMouseEnter={(e) => (e.currentTarget.style.background = '#f8fafc')}
                      onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                    >
                      <td style={{ padding: '14px 16px', fontWeight: 800 }}>
                        <span style={{ fontFamily: 'monospace', color: '#0369a1' }}>{ref.refund_code}</span>
                      </td>
                      <td style={{ padding: '14px 16px' }}>
                        <div style={{ fontWeight: 700, color: '#0f172a' }}>#{ref.order_code}</div>
                        {ref.return_code && (
                          <div style={{ fontSize: 11, color: '#64748b' }}>Từ yêu cầu: #{ref.return_code}</div>
                        )}
                      </td>
                      <td style={{ padding: '14px 16px', fontWeight: 800, color: '#16a34a', fontSize: 14 }}>
                        {(ref.refund_amount ?? 0).toLocaleString('vi-VN')} đ
                      </td>
                      <td style={{ padding: '14px 16px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                          {isMomo ? <Smartphone size={14} color="#a21caf" /> : <CreditCard size={14} color="#0284c7" />}
                          <span style={{ fontWeight: 600, color: '#334155' }}>
                            {isMomo ? 'MoMo' : 'Chuyển Khoản'}
                          </span>
                        </div>
                      </td>
                      <td style={{ padding: '14px 16px', fontSize: 12 }}>
                        {ref.beneficiary_account_number ? (
                          <div>
                            <div style={{ fontWeight: 700, color: '#0f172a' }}>
                              {ref.beneficiary_bank}: {ref.beneficiary_account_number}
                            </div>
                            <div style={{ color: '#64748b', fontSize: 11 }}>{ref.beneficiary_account_name}</div>
                          </div>
                        ) : ref.bank_transfer_ref ? (
                          <div style={{ fontFamily: 'monospace', color: '#475569' }}>UNC: {ref.bank_transfer_ref}</div>
                        ) : (
                          <span style={{ color: '#94a3b8' }}>--</span>
                        )}
                      </td>
                      <td style={{ padding: '14px 16px' }}>
                        <span
                          style={{
                            fontSize: 12,
                            fontWeight: 700,
                            padding: '4px 10px',
                            borderRadius: 12,
                            color: cfg.color,
                            background: cfg.bg,
                            display: 'inline-block',
                          }}
                        >
                          {cfg.label}
                        </span>
                      </td>
                      <td style={{ padding: '14px 16px' }}>
                        <span
                          style={{
                            fontSize: 11,
                            fontWeight: 700,
                            padding: '3px 8px',
                            borderRadius: 6,
                            color: reconCfg.color,
                            background: reconCfg.bg,
                            display: 'inline-block',
                          }}
                        >
                          {reconCfg.label}
                        </span>
                      </td>
                      <td style={{ padding: '14px 16px', textAlign: 'right' }}>
                        <div style={{ display: 'flex', gap: 6, justifyContent: 'flex-end', alignItems: 'center' }}>
                          {ref.status !== 'SUCCEEDED' && (
                            <>
                              {isMomo ? (
                                <button
                                  type="button"
                                  onClick={() => handleMomoRefund(ref.refund_code)}
                                  disabled={actionLoading}
                                  style={{
                                    padding: '5px 10px',
                                    borderRadius: 6,
                                    background: '#a21caf',
                                    color: '#fff',
                                    border: 'none',
                                    fontWeight: 700,
                                    fontSize: 11,
                                    cursor: 'pointer',
                                  }}
                                  title="Kích hoạt hoàn tiền MoMo Sandbox"
                                >
                                  Hoàn MoMo
                                </button>
                              ) : (
                                <button
                                  type="button"
                                  onClick={() => {
                                    setManualBankCode(ref.refund_code)
                                    setUncRef('')
                                    setActionError('')
                                  }}
                                  style={{
                                    padding: '5px 10px',
                                    borderRadius: 6,
                                    background: '#16a34a',
                                    color: '#fff',
                                    border: 'none',
                                    fontWeight: 700,
                                    fontSize: 11,
                                    cursor: 'pointer',
                                  }}
                                  title="Xác nhận ủy nhiệm chi ngân hàng"
                                >
                                  Xác nhận UNC
                                </button>
                              )}
                            </>
                          )}

                          <button
                            type="button"
                            onClick={() => {
                              setReconCode(ref.refund_code)
                              setReconStatus(ref.reconciliation_status || 'MATCHED')
                            }}
                            style={{
                              padding: '5px 8px',
                              borderRadius: 6,
                              background: '#f8fafc',
                              border: '1px solid #cbd5e1',
                              color: '#334155',
                              fontWeight: 600,
                              fontSize: 11,
                              cursor: 'pointer',
                            }}
                            title="Cập nhật trạng thái đối soát kế toán"
                          >
                            Đối soát
                          </button>

                          <button
                            type="button"
                            onClick={() => openDetail(ref.refund_code)}
                            style={{
                              padding: '5px 10px',
                              borderRadius: 6,
                              background: '#0284c7',
                              color: '#fff',
                              border: 'none',
                              fontWeight: 700,
                              fontSize: 11,
                              cursor: 'pointer',
                              display: 'flex',
                              alignItems: 'center',
                              gap: 4,
                            }}
                          >
                            <Eye size={12} />
                            <span>Chi tiết</span>
                          </button>
                        </div>
                      </td>
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </div>
        {!loading && refunds.length > 0 && (
          <PaginationBar
            currentPage={currentPage}
            totalPages={totalPages}
            pageSize={pageSize}
            totalItems={totalCount}
            itemName="phiếu hoàn tiền"
            onPageChange={(p) => {
              setCurrentPage(p)
              loadRefunds(p, pageSize)
            }}
            onPageSizeChange={(sz) => {
              setPageSize(sz)
              setCurrentPage(1)
              loadRefunds(1, sz)
            }}
            pageSizeOptions={[10, 15, 25, 50]}
          />
        )}
      </div>

      {/* POPUP: Manual Bank Transfer Confirmation */}
      {manualBankCode && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(15, 23, 42, 0.65)',
            backdropFilter: 'blur(3px)',
            zIndex: 1000,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: 20,
          }}
          onClick={() => setManualBankCode(null)}
        >
          <div
            style={{
              background: '#fff',
              borderRadius: 16,
              maxWidth: 520,
              width: '100%',
              padding: 24,
              boxShadow: '0 25px 50px -12px rgba(0,0,0,0.25)',
              border: '1px solid #e2e8f0',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
              <h3 style={{ margin: 0, fontSize: 17, fontWeight: 800, color: '#0f172a' }}>
                Xác Nhận Ủy Nhiệm Chi (UNC) #{manualBankCode}
              </h3>
              <button
                type="button"
                onClick={() => setManualBankCode(null)}
                style={{ background: '#f1f5f9', border: 'none', borderRadius: 8, padding: 6, cursor: 'pointer' }}
              >
                <X size={16} />
              </button>
            </div>

            {actionError && (
              <div style={{ background: '#fef2f2', border: '1px solid #fecaca', padding: '8px 12px', borderRadius: 6, color: '#b91c1c', fontSize: 12, marginBottom: 12 }}>
                {actionError}
              </div>
            )}

            <div style={{ display: 'flex', flexDirection: 'column', gap: 12, fontSize: 13 }}>
              <div>
                <label style={{ display: 'block', fontWeight: 700, color: '#334155', marginBottom: 4 }}>
                  Mã giao dịch ngân hàng / Số UNC (*):
                </label>
                <input
                  type="text"
                  value={uncRef}
                  onChange={(e) => setUncRef(e.target.value)}
                  placeholder="Ví dụ: FT2609088899, UNC-VCB-00123..."
                  style={{ width: '100%', padding: '8px 12px', borderRadius: 8, border: '1px solid #cbd5e1', fontSize: 13 }}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontWeight: 700, color: '#334155', marginBottom: 4 }}>
                  Link chứng từ / Ảnh chụp ủy nhiệm chi:
                </label>
                <input
                  type="text"
                  value={uncProofUrl}
                  onChange={(e) => setUncProofUrl(e.target.value)}
                  placeholder="https://... hoặc mã lưu trữ biên lai"
                  style={{ width: '100%', padding: '8px 12px', borderRadius: 8, border: '1px solid #cbd5e1', fontSize: 13 }}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontWeight: 700, color: '#334155', marginBottom: 4 }}>
                  Ghi chú kế toán:
                </label>
                <textarea
                  value={uncNotes}
                  onChange={(e) => setUncNotes(e.target.value)}
                  style={{ width: '100%', padding: '8px 12px', borderRadius: 8, border: '1px solid #cbd5e1', fontSize: 13 }}
                  rows={2}
                />
              </div>

              <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
                <button
                  type="button"
                  onClick={handleManualBankSubmit}
                  disabled={actionLoading}
                  style={{
                    flex: 1,
                    padding: '10px',
                    borderRadius: 8,
                    background: '#16a34a',
                    color: '#fff',
                    border: 'none',
                    fontWeight: 700,
                    cursor: 'pointer',
                  }}
                >
                  Xác Nhận & Hoàn Tất Chi
                </button>
                <button
                  type="button"
                  onClick={() => setManualBankCode(null)}
                  style={{
                    padding: '10px 16px',
                    borderRadius: 8,
                    background: '#fff',
                    border: '1px solid #cbd5e1',
                    color: '#475569',
                    fontWeight: 600,
                    cursor: 'pointer',
                  }}
                >
                  Hủy
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* POPUP: Reconciliation Update */}
      {reconCode && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(15, 23, 42, 0.65)',
            backdropFilter: 'blur(3px)',
            zIndex: 1000,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: 20,
          }}
          onClick={() => setReconCode(null)}
        >
          <div
            style={{
              background: '#fff',
              borderRadius: 16,
              maxWidth: 480,
              width: '100%',
              padding: 24,
              boxShadow: '0 25px 50px -12px rgba(0,0,0,0.25)',
              border: '1px solid #e2e8f0',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
              <h3 style={{ margin: 0, fontSize: 17, fontWeight: 800, color: '#0f172a' }}>
                Đối Soát Kế Toán #{reconCode}
              </h3>
              <button
                type="button"
                onClick={() => setReconCode(null)}
                style={{ background: '#f1f5f9', border: 'none', borderRadius: 8, padding: 6, cursor: 'pointer' }}
              >
                <X size={16} />
              </button>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 12, fontSize: 13 }}>
              <div>
                <label style={{ display: 'block', fontWeight: 700, color: '#334155', marginBottom: 4 }}>
                  Kết quả đối soát:
                </label>
                <select
                  value={reconStatus}
                  onChange={(e) => setReconStatus(e.target.value)}
                  style={{ width: '100%', padding: '8px 12px', borderRadius: 8, border: '1px solid #cbd5e1', fontWeight: 700 }}
                >
                  <option value="MATCHED">Khớp 100% với sao kê (MATCHED)</option>
                  <option value="PENDING">Chờ sao kê cuối tháng (PENDING)</option>
                  <option value="MISMATCH">Lệch số dư / Lỗi đối soát (MISMATCH)</option>
                  <option value="NEEDS_REVIEW">Cần trưởng phòng kế toán kiểm tra (NEEDS_REVIEW)</option>
                </select>
              </div>

              <div>
                <label style={{ display: 'block', fontWeight: 700, color: '#334155', marginBottom: 4 }}>
                  Ghi chú đối soát:
                </label>
                <textarea
                  value={reconNotes}
                  onChange={(e) => setReconNotes(e.target.value)}
                  style={{ width: '100%', padding: '8px 12px', borderRadius: 8, border: '1px solid #cbd5e1', fontSize: 13 }}
                  rows={2}
                />
              </div>

              <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
                <button
                  type="button"
                  onClick={handleReconcileSubmit}
                  disabled={actionLoading}
                  style={{
                    flex: 1,
                    padding: '10px',
                    borderRadius: 8,
                    background: '#0f172a',
                    color: '#fff',
                    border: 'none',
                    fontWeight: 700,
                    cursor: 'pointer',
                  }}
                >
                  Cập Nhật Đối Soát
                </button>
                <button
                  type="button"
                  onClick={() => setReconCode(null)}
                  style={{
                    padding: '10px 16px',
                    borderRadius: 8,
                    background: '#fff',
                    border: '1px solid #cbd5e1',
                    color: '#475569',
                    fontWeight: 600,
                    cursor: 'pointer',
                  }}
                >
                  Hủy
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* POPUP: Detail Modal */}
      {selectedRefundCode && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(15, 23, 42, 0.65)',
            backdropFilter: 'blur(3px)',
            zIndex: 1000,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: 20,
          }}
          onClick={() => setSelectedRefundCode(null)}
        >
          <div
            style={{
              background: '#fff',
              borderRadius: 16,
              maxWidth: 680,
              width: '100%',
              padding: 24,
              boxShadow: '0 25px 50px -12px rgba(0,0,0,0.25)',
              border: '1px solid #e2e8f0',
              maxHeight: '90vh',
              overflowY: 'auto',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16, borderBottom: '1px solid #f1f5f9', paddingBottom: 12 }}>
              <div>
                <h3 style={{ margin: 0, fontSize: 18, fontWeight: 800, color: '#0f172a' }}>
                  Chi Tiết Phiếu Hoàn Tiền #{selectedRefundCode}
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setSelectedRefundCode(null)}
                style={{ background: '#f1f5f9', border: 'none', borderRadius: 8, padding: 6, cursor: 'pointer' }}
              >
                <X size={16} />
              </button>
            </div>

            {loadingDetail ? (
              <div style={{ padding: 40, textAlign: 'center', color: '#64748b' }}>
                <RefreshCw size={20} className="spin" style={{ margin: '0 auto 8px' }} />
                <span>Đang tải thông tin phiếu chi...</span>
              </div>
            ) : refundDetail ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 16, fontSize: 13 }}>
                <div style={{ background: '#f8fafc', padding: 14, borderRadius: 10, border: '1px solid #e2e8f0', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                  <div>
                    <span style={{ color: '#64748b', fontSize: 11 }}>Số tiền hoàn:</span>
                    <div style={{ fontWeight: 800, color: '#16a34a', fontSize: 16 }}>
                      {(refundDetail.refund_amount ?? 0).toLocaleString('vi-VN')} đ
                    </div>
                  </div>
                  <div>
                    <span style={{ color: '#64748b', fontSize: 11 }}>Đơn hàng:</span>
                    <div style={{ fontWeight: 700, color: '#0f172a' }}>#{refundDetail.order_code}</div>
                  </div>
                  <div>
                    <span style={{ color: '#64748b', fontSize: 11 }}>Trạng thái chi:</span>
                    <div>
                      <span
                        style={{
                          fontSize: 11,
                          fontWeight: 700,
                          padding: '2px 8px',
                          borderRadius: 6,
                          color: STATUS_CONFIG[refundDetail.status]?.color,
                          background: STATUS_CONFIG[refundDetail.status]?.bg,
                        }}
                      >
                        {STATUS_CONFIG[refundDetail.status]?.label || refundDetail.status}
                      </span>
                    </div>
                  </div>
                  <div>
                    <span style={{ color: '#64748b', fontSize: 11 }}>Đối soát:</span>
                    <div>
                      <span
                        style={{
                          fontSize: 11,
                          fontWeight: 700,
                          padding: '2px 8px',
                          borderRadius: 6,
                          color: RECON_CONFIG[refundDetail.reconciliation_status]?.color,
                          background: RECON_CONFIG[refundDetail.reconciliation_status]?.bg,
                        }}
                      >
                        {RECON_CONFIG[refundDetail.reconciliation_status]?.label || refundDetail.reconciliation_status}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Gateway Attempts history */}
                <div>
                  <div style={{ fontWeight: 700, color: '#475569', fontSize: 12, textTransform: 'uppercase', marginBottom: 8 }}>
                    Lịch sử gọi API Cổng thanh toán ({refundDetail.attempts?.length || 0})
                  </div>
                  {refundDetail.attempts && refundDetail.attempts.length > 0 ? (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                      {refundDetail.attempts.map((att) => (
                        <div
                          key={att.id}
                          style={{
                            padding: '8px 12px',
                            background: '#f8fafc',
                            borderRadius: 6,
                            border: '1px solid #e2e8f0',
                            fontSize: 12,
                            display: 'flex',
                            justifyContent: 'space-between',
                          }}
                        >
                          <div>
                            <strong style={{ color: '#0f172a' }}>Lần {att.attempt_number} ({att.provider}):</strong>{' '}
                            <span style={{ color: att.status === 'SUCCEEDED' ? '#16a34a' : '#dc2626', fontWeight: 600 }}>
                              {att.status}
                            </span>
                            {att.error_message && <div style={{ color: '#b91c1c', fontSize: 11 }}>{att.error_message}</div>}
                          </div>
                          <div style={{ color: '#94a3b8', fontSize: 11 }}>
                            {new Date(att.created_at).toLocaleString('vi-VN')}
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div style={{ color: '#94a3b8', fontStyle: 'italic', fontSize: 12 }}>Chưa có lượt giao dịch qua cổng online</div>
                  )}
                </div>
              </div>
            ) : null}
          </div>
        </div>
      )}
    </div>
  )
}
