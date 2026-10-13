import { useEffect, useState, useRef } from 'react'
import {
  UploadCloud,
  FileSpreadsheet,
  Download,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Clock,
  ArrowRight,
  Layers,
  History,
  FileCheck,
  RefreshCw,
} from 'lucide-react'
import { api, tokenStore, API_URL } from '../../services/api'
import { WarehouseImportPreview, WarehouseImportHistoryItem } from '../../types'

export function WarehouseImportsPage() {
  // Wizard Steps: 1 = Upload, 2 = Preview & Validate, 3 = Success
  const [step, setStep] = useState<1 | 2 | 3>(1)
  const [file, setFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [previewData, setPreviewData] = useState<WarehouseImportPreview | null>(null)
  const [previewFilter, setPreviewFilter] = useState<'VALID' | 'INVALID' | 'CANDIDATE'>('VALID')

  // Commit State
  const [committing, setCommitting] = useState(false)
  const [commitResult, setCommitResult] = useState<{ receipt_code: string; total_items: number; total_amount: number } | null>(null)

  // Past History
  const [historyJobs, setHistoryJobs] = useState<WarehouseImportHistoryItem[]>([])
  const [loadingHistory, setLoadingHistory] = useState(false)

  const fileInputRef = useRef<HTMLInputElement>(null)

  const fetchHistory = () => {
    setLoadingHistory(true)
    api<{ items: WarehouseImportHistoryItem[]; total: number }>('/warehouse-portal/imports')
      .then((res) => setHistoryJobs(res.items || []))
      .catch((err) => console.error(err))
      .finally(() => setLoadingHistory(false))
  }

  useEffect(() => {
    fetchHistory()
  }, [])

  const handleDownloadTemplate = async () => {
    try {
      const token = tokenStore.get() || ''
      const response = await fetch(`${API_URL}/warehouse-portal/imports/template`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      })
      if (!response.ok) {
        let msg = 'Không thể tải file mẫu'
        try {
          const errData = await response.json()
          msg = errData.detail || msg
        } catch {}
        throw new Error(msg)
      }
      const blob = await response.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'mau_nhap_kho_pharmatrust_gsp.csv'
      document.body.appendChild(a)
      a.click()
      a.remove()
      window.URL.revokeObjectURL(url)
    } catch (err: any) {
      alert(err.message || 'Lỗi tải template')
    }
  }

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0])
      setUploadError(null)
    }
  }

  const handleUploadPreview = async () => {
    if (!file) {
      setUploadError('Vui lòng chọn một file CSV hoặc Excel (.xlsx)')
      return
    }

    setUploading(true)
    setUploadError(null)

    const formData = new FormData()
    formData.append('file', file)

    try {
      const data = await api<WarehouseImportPreview>('/warehouse-portal/imports/preview', {
        method: 'POST',
        body: formData,
      })

      setPreviewData(data)
      setStep(2)
      if (data.invalid_count > 0 && data.valid_count === 0) {
        setPreviewFilter('INVALID')
      } else if (data.candidate_count > 0 && data.valid_count === 0) {
        setPreviewFilter('CANDIDATE')
      } else {
        setPreviewFilter('VALID')
      }
    } catch (err: any) {
      setUploadError(err.message || 'Lỗi tải và xử lý file')
    } finally {
      setUploading(false)
    }
  }

  const handleCommitImport = async () => {
    if (!previewData) return

    setCommitting(true)
    try {
      const res = await api<{ receipt_code: string; total_items: number; total_amount: number }>(
        `/warehouse-portal/imports/${previewData.import_id}/commit`,
        { method: 'POST' }
      )
      setCommitResult(res)
      setStep(3)
      fetchHistory()
    } catch (err: any) {
      alert(err.message || 'Không thể xác nhận nhập kho')
    } finally {
      setCommitting(false)
    }
  }

  const handleReset = () => {
    setStep(1)
    setFile(null)
    setPreviewData(null)
    setCommitResult(null)
    setUploadError(null)
    if (fileInputRef.current) fileInputRef.current.value = ''
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
          <div style={{ fontSize: '11px', fontWeight: 800, color: '#059669', textTransform: 'uppercase', letterSpacing: '0.8px' }}>
            QUY TRÌNH NHẬP KHO GSP BẰNG TẬP TIN
          </div>
          <h1 style={{ margin: '4px 0 0', fontSize: '22px', fontWeight: 900, color: '#0f172a' }}>
            Nhập Tồn Kho Bằng File (CSV / Excel)
          </h1>
          <p style={{ margin: '4px 0 0', fontSize: '13px', color: '#64748b' }}>
            Hỗ trợ nhập hàng loạt lô thuốc, kiểm định hạn dùng tối thiểu 180 ngày và tự động phát hiện trùng file
          </p>
        </div>

        <button
          onClick={handleDownloadTemplate}
          style={{
            background: '#ecfdf5',
            color: '#059669',
            border: '1px solid #a7f3d0',
            padding: '10px 18px',
            borderRadius: '12px',
            fontSize: '13px',
            fontWeight: 800,
            cursor: 'pointer',
            display: 'inline-flex',
            alignItems: 'center',
            gap: '8px',
          }}
        >
          <Download size={16} /> Tải File Mẫu Chuẩn (14 Cột)
        </button>
      </div>

      {/* Rules Banner */}
      <div
        style={{
          background: '#f8fafc',
          borderRadius: '14px',
          border: '1px solid #e2e8f0',
          padding: '16px 20px',
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
          gap: '14px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: '10px' }}>
          <div style={{ padding: '6px', borderRadius: '8px', background: '#ecfdf5', color: '#059669' }}>
            <CheckCircle2 size={18} />
          </div>
          <div>
            <div style={{ fontSize: '12px', fontWeight: 800, color: '#0f172a' }}>Quy tắc 1: HSD tối thiểu 180 ngày</div>
            <div style={{ fontSize: '11px', color: '#64748b', marginTop: '2px' }}>
              Thuốc nhập kho bắt buộc còn hạn ≥ 6 tháng để đảm bảo an toàn lưu thông.
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'flex-start', gap: '10px' }}>
          <div style={{ padding: '6px', borderRadius: '8px', background: '#fffbeb', color: '#d97706' }}>
            <Clock size={18} />
          </div>
          <div>
            <div style={{ fontSize: '12px', fontWeight: 800, color: '#0f172a' }}>Thuốc mới: Chờ Admin phê duyệt</div>
            <div style={{ fontSize: '11px', color: '#64748b', marginTop: '2px' }}>
              Dòng thuốc chưa có trong hệ thống sẽ tự động chuyển vào hàng chờ duyệt của Admin.
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'flex-start', gap: '10px' }}>
          <div style={{ padding: '6px', borderRadius: '8px', background: '#eff6ff', color: '#2563eb' }}>
            <FileCheck size={18} />
          </div>
          <div>
            <div style={{ fontSize: '12px', fontWeight: 800, color: '#0f172a' }}>Chống trùng lặp mã băm SHA-256</div>
            <div style={{ fontSize: '11px', color: '#64748b', marginTop: '2px' }}>
              Hệ thống tự động phát hiện và chặn nếu tải lại file đã từng nhập trước đó.
            </div>
          </div>
        </div>
      </div>

      {/* STEP 1: Upload File */}
      {step === 1 && (
        <div
          style={{
            background: 'white',
            borderRadius: '16px',
            border: '1px solid #e2e8f0',
            padding: '36px 24px',
            textAlign: 'center',
            boxShadow: '0 1px 3px rgba(0,0,0,0.03)',
          }}
        >
          <div
            style={{
              maxWidth: '520px',
              margin: '0 auto',
              border: '2px dashed #cbd5e1',
              borderRadius: '16px',
              padding: '36px 24px',
              background: '#f8fafc',
            }}
          >
            <div
              style={{
                width: '60px',
                height: '60px',
                borderRadius: '16px',
                background: '#ecfdf5',
                color: '#059669',
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                marginBottom: '16px',
              }}
            >
              <UploadCloud size={32} />
            </div>

            <h3 style={{ margin: '0 0 8px', fontSize: '16px', fontWeight: 800, color: '#0f172a' }}>
              Tải lên file dữ liệu thuốc của kho
            </h3>
            <p style={{ margin: '0 0 20px', fontSize: '12.5px', color: '#64748b' }}>
              Hỗ trợ định dạng tập tin <strong>.csv</strong> hoặc <strong>.xlsx</strong> dung lượng dưới 10MB
            </p>

            <input
              type="file"
              ref={fileInputRef}
              accept=".csv, application/vnd.openxmlformats-officedocument.spreadsheetml.sheet, application/vnd.ms-excel"
              onChange={handleFileChange}
              style={{ display: 'none' }}
              id="file-upload-input"
            />

            <label
              htmlFor="file-upload-input"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '8px',
                padding: '10px 20px',
                background: '#059669',
                color: 'white',
                borderRadius: '10px',
                fontWeight: 700,
                fontSize: '13px',
                cursor: 'pointer',
              }}
            >
              <FileSpreadsheet size={16} /> Chọn File Từ Máy Tính
            </label>

            {file && (
              <div
                style={{
                  marginTop: '16px',
                  padding: '10px 14px',
                  background: 'white',
                  borderRadius: '10px',
                  border: '1px solid #cbd5e1',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px', fontWeight: 700, color: '#0f172a' }}>
                  <FileSpreadsheet size={18} color="#059669" />
                  {file.name} ({(file.size / 1024).toFixed(1)} KB)
                </div>
                <button
                  type="button"
                  onClick={() => setFile(null)}
                  style={{ background: 'none', border: 'none', color: '#94a3b8', cursor: 'pointer', fontSize: '12px' }}
                >
                  Gỡ bỏ
                </button>
              </div>
            )}

            {uploadError && (
              <div
                style={{
                  marginTop: '16px',
                  padding: '10px 14px',
                  background: '#fef2f2',
                  border: '1px solid #fecaca',
                  borderRadius: '10px',
                  color: '#dc2626',
                  fontSize: '12px',
                  fontWeight: 700,
                  textAlign: 'left',
                }}
              >
                ⚠️ {uploadError}
              </div>
            )}
          </div>

          <div style={{ marginTop: '24px' }}>
            <button
              disabled={!file || uploading}
              onClick={handleUploadPreview}
              style={{
                padding: '12px 28px',
                borderRadius: '12px',
                background: !file || uploading ? '#cbd5e1' : 'linear-gradient(135deg, #059669, #047857)',
                color: 'white',
                border: 'none',
                fontWeight: 800,
                fontSize: '14px',
                cursor: !file || uploading ? 'not-allowed' : 'pointer',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '8px',
                boxShadow: !file || uploading ? 'none' : '0 3px 12px rgba(5, 150, 105, 0.3)',
              }}
            >
              {uploading ? (
                <>
                  <RefreshCw size={16} className="animate-spin" /> Đang kiểm tra tính hợp lệ…
                </>
              ) : (
                <>
                  Kiểm Tra Dữ Liệu & Xem Trước <ArrowRight size={16} />
                </>
              )}
            </button>
          </div>
        </div>
      )}

      {/* STEP 2: Preview & Validation Table */}
      {step === 2 && previewData && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {/* Summary Badges */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
              gap: '14px',
            }}
          >
            <div style={{ background: 'white', borderRadius: '14px', border: '1px solid #e2e8f0', padding: '16px' }}>
              <div style={{ fontSize: '11px', fontWeight: 700, color: '#64748b' }}>TỔNG SỐ DÒNG</div>
              <div style={{ fontSize: '24px', fontWeight: 900, color: '#0f172a', marginTop: '2px' }}>
                {previewData.total_rows}
              </div>
              <div style={{ fontSize: '11px', color: '#94a3b8' }}>Dòng dữ liệu trong file</div>
            </div>

            <div style={{ background: '#ecfdf5', borderRadius: '14px', border: '1px solid #a7f3d0', padding: '16px' }}>
              <div style={{ fontSize: '11px', fontWeight: 700, color: '#059669' }}>HỢP LỆ ĐỦ ĐIỀU KIỆN</div>
              <div style={{ fontSize: '24px', fontWeight: 900, color: '#059669', marginTop: '2px' }}>
                {previewData.valid_count}
              </div>
              <div style={{ fontSize: '11px', color: '#059669' }}>Sẵn sàng nhập kho ngay</div>
            </div>

            <div style={{ background: '#fffbeb', borderRadius: '14px', border: '1px solid #fde68a', padding: '16px' }}>
              <div style={{ fontSize: '11px', fontWeight: 700, color: '#d97706' }}>CẢNH BÁO NHẸ</div>
              <div style={{ fontSize: '24px', fontWeight: 900, color: '#d97706', marginTop: '2px' }}>
                {previewData.warning_count}
              </div>
              <div style={{ fontSize: '11px', color: '#d97706' }}>Vẫn được phép nhập</div>
            </div>

            <div style={{ background: '#fef2f2', borderRadius: '14px', border: '1px solid #fecaca', padding: '16px' }}>
              <div style={{ fontSize: '11px', fontWeight: 700, color: '#dc2626' }}>DÒNG LỖI (BỊ TỪ CHỐI)</div>
              <div style={{ fontSize: '24px', fontWeight: 900, color: '#dc2626', marginTop: '2px' }}>
                {previewData.invalid_count}
              </div>
              <div style={{ fontSize: '11px', color: '#dc2626' }}>Sai định dạng / HSD &lt; 180 ngày</div>
            </div>

            <div style={{ background: '#faf5ff', borderRadius: '14px', border: '1px solid #e9d5ff', padding: '16px' }}>
              <div style={{ fontSize: '11px', fontWeight: 700, color: '#9333ea' }}>CHỜ ADMIN DUYỆT</div>
              <div style={{ fontSize: '24px', fontWeight: 900, color: '#9333ea', marginTop: '2px' }}>
                {previewData.candidate_count}
              </div>
              <div style={{ fontSize: '11px', color: '#9333ea' }}>Thuốc chưa có trên hệ thống</div>
            </div>
          </div>

          {/* Action Bar */}
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
              gap: '14px',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <button
                onClick={() => setPreviewFilter('VALID')}
                style={{
                  padding: '7px 14px',
                  borderRadius: '8px',
                  fontSize: '12.5px',
                  fontWeight: 700,
                  border: 'none',
                  cursor: 'pointer',
                  background: previewFilter === 'VALID' ? '#059669' : '#f1f5f9',
                  color: previewFilter === 'VALID' ? 'white' : '#475569',
                }}
              >
                Hợp lệ ({previewData.valid_count + previewData.warning_count})
              </button>
              <button
                onClick={() => setPreviewFilter('INVALID')}
                style={{
                  padding: '7px 14px',
                  borderRadius: '8px',
                  fontSize: '12.5px',
                  fontWeight: 700,
                  border: 'none',
                  cursor: 'pointer',
                  background: previewFilter === 'INVALID' ? '#dc2626' : '#f1f5f9',
                  color: previewFilter === 'INVALID' ? 'white' : '#475569',
                }}
              >
                Dòng lỗi ({previewData.invalid_count})
              </button>
              <button
                onClick={() => setPreviewFilter('CANDIDATE')}
                style={{
                  padding: '7px 14px',
                  borderRadius: '8px',
                  fontSize: '12.5px',
                  fontWeight: 700,
                  border: 'none',
                  cursor: 'pointer',
                  background: previewFilter === 'CANDIDATE' ? '#9333ea' : '#f1f5f9',
                  color: previewFilter === 'CANDIDATE' ? 'white' : '#475569',
                }}
              >
                Chờ duyệt ({previewData.candidate_count})
              </button>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <button
                onClick={handleReset}
                style={{
                  padding: '9px 16px',
                  borderRadius: '10px',
                  border: '1px solid #cbd5e1',
                  background: 'white',
                  color: '#475569',
                  fontWeight: 700,
                  fontSize: '13px',
                  cursor: 'pointer',
                }}
              >
                Hủy / Chọn file khác
              </button>
              <button
                disabled={!previewData.can_commit || committing}
                onClick={handleCommitImport}
                style={{
                  padding: '9px 20px',
                  borderRadius: '10px',
                  background: !previewData.can_commit || committing ? '#cbd5e1' : 'linear-gradient(135deg, #059669, #047857)',
                  color: 'white',
                  border: 'none',
                  fontWeight: 800,
                  fontSize: '13px',
                  cursor: !previewData.can_commit || committing ? 'not-allowed' : 'pointer',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '6px',
                }}
              >
                {committing ? 'Đang ghi nhận kho…' : 'Xác Nhận Nhập Kho Ngay'}
              </button>
            </div>
          </div>

          {/* Table Preview */}
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
              <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '12.5px' }}>
                <thead>
                  <tr style={{ background: '#f8fafc', borderBottom: '1px solid #e2e8f0', color: '#64748b', fontSize: '11px', fontWeight: 800 }}>
                    <th style={{ padding: '12px 14px' }}>Dòng</th>
                    <th style={{ padding: '12px 14px' }}>Tên Thuốc / SĐK / SKU</th>
                    <th style={{ padding: '12px 14px' }}>Số Lô</th>
                    <th style={{ padding: '12px 14px' }}>Hạn Sử Dụng (FEFO)</th>
                    <th style={{ padding: '12px 14px', textAlign: 'center' }}>Số Lượng</th>
                    <th style={{ padding: '12px 14px', textAlign: 'right' }}>Giá Nhập (VNĐ)</th>
                    <th style={{ padding: '12px 14px' }}>Vị Trí</th>
                    <th style={{ padding: '12px 14px' }}>Chi Tiết Trạng Thái</th>
                  </tr>
                </thead>
                <tbody>
                  {(() => {
                    const rowsToShow =
                      previewFilter === 'VALID'
                        ? previewData.preview_rows
                        : previewFilter === 'INVALID'
                        ? previewData.invalid_rows
                        : previewData.candidate_rows

                    if (rowsToShow.length === 0) {
                      return (
                        <tr>
                          <td colSpan={8} style={{ padding: '30px', textAlign: 'center', color: '#94a3b8' }}>
                            Không có dòng dữ liệu nào trong danh mục này.
                          </td>
                        </tr>
                      )
                    }

                    return rowsToShow.map((r, idx) => (
                      <tr key={idx} style={{ borderBottom: '1px solid #f1f5f9' }}>
                        <td style={{ padding: '12px 14px', color: '#64748b', fontWeight: 700 }}>#{r.row_index}</td>
                        <td style={{ padding: '12px 14px' }}>
                          <div style={{ fontWeight: 800, color: '#0f172a' }}>{r.product_name || 'Chưa định danh'}</div>
                          <div style={{ fontSize: '11px', color: '#059669', marginTop: '2px' }}>
                            SĐK: {r.registration_number || '—'} • SKU: {r.sku_code || '—'}
                          </div>
                        </td>
                        <td style={{ padding: '12px 14px', fontFamily: 'monospace', fontWeight: 800 }}>{r.batch_number}</td>
                        <td style={{ padding: '12px 14px' }}>{r.expiry_date}</td>
                        <td style={{ padding: '12px 14px', textAlign: 'center', fontWeight: 800 }}>
                          {r.quantity} {r.uom}
                        </td>
                        <td style={{ padding: '12px 14px', textAlign: 'right', fontWeight: 700 }}>
                          {(r.unit_cost || 0).toLocaleString('vi-VN')}
                        </td>
                        <td style={{ padding: '12px 14px', color: '#64748b' }}>{r.storage_location}</td>
                        <td style={{ padding: '12px 14px' }}>
                          {r.errors && r.errors.length > 0 && (
                            <div style={{ color: '#dc2626', fontSize: '11px', fontWeight: 600 }}>
                              {r.errors.map((e: string, i: number) => (
                                <div key={i}>❌ {e}</div>
                              ))}
                            </div>
                          )}
                          {r.warnings && r.warnings.length > 0 && (
                            <div style={{ color: '#d97706', fontSize: '11px', fontWeight: 600 }}>
                              {r.warnings.map((w: string, i: number) => (
                                <div key={i}>⚠️ {w}</div>
                              ))}
                            </div>
                          )}
                          {(!r.errors || r.errors.length === 0) && (!r.warnings || r.warnings.length === 0) && (
                            <span style={{ color: '#059669', fontSize: '11px', fontWeight: 700 }}>
                              ✓ Đạt chuẩn GSP (≥180 ngày)
                            </span>
                          )}
                        </td>
                      </tr>
                    ))
                  })()}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* STEP 3: Success Screen */}
      {step === 3 && commitResult && (
        <div
          style={{
            background: 'white',
            borderRadius: '16px',
            border: '1px solid #e2e8f0',
            padding: '40px 24px',
            textAlign: 'center',
            boxShadow: '0 1px 3px rgba(0,0,0,0.03)',
          }}
        >
          <div
            style={{
              width: '64px',
              height: '64px',
              borderRadius: '9999px',
              background: '#ecfdf5',
              color: '#059669',
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              marginBottom: '16px',
            }}
          >
            <CheckCircle2 size={36} />
          </div>

          <h2 style={{ margin: '0 0 8px', fontSize: '20px', fontWeight: 900, color: '#0f172a' }}>
            Nhập Kho Hoàn Tất Thành Công!
          </h2>
          <p style={{ margin: '0 0 24px', fontSize: '14px', color: '#64748b' }}>
            Hệ thống đã tự động tạo phiếu nhập kho <strong>{commitResult.receipt_code}</strong> và cập nhật thẻ kho, biến động tồn kho chi tiết.
          </p>

          <div
            style={{
              display: 'inline-flex',
              gap: '24px',
              padding: '16px 28px',
              background: '#f8fafc',
              borderRadius: '12px',
              border: '1px solid #e2e8f0',
              marginBottom: '28px',
            }}
          >
            <div>
              <div style={{ fontSize: '11px', color: '#64748b', fontWeight: 700 }}>TỔNG SẢN PHẨM NHẬP</div>
              <div style={{ fontSize: '18px', fontWeight: 900, color: '#059669', marginTop: '2px' }}>
                {commitResult.total_items.toLocaleString()} đơn vị
              </div>
            </div>
            <div style={{ borderLeft: '1px solid #e2e8f0' }} />
            <div>
              <div style={{ fontSize: '11px', color: '#64748b', fontWeight: 700 }}>TỔNG GIÁ TRỊ NHẬP</div>
              <div style={{ fontSize: '18px', fontWeight: 900, color: '#0f172a', marginTop: '2px' }}>
                {commitResult.total_amount.toLocaleString('vi-VN')} đ
              </div>
            </div>
          </div>

          <div>
            <button
              onClick={handleReset}
              style={{
                padding: '10px 24px',
                borderRadius: '10px',
                background: '#059669',
                color: 'white',
                border: 'none',
                fontWeight: 700,
                fontSize: '13px',
                cursor: 'pointer',
              }}
            >
              Tiếp tục nhập phiên khác
            </button>
          </div>
        </div>
      )}

      {/* Section: History of Imports */}
      <div
        style={{
          background: 'white',
          borderRadius: '16px',
          border: '1px solid #e2e8f0',
          overflow: 'hidden',
          boxShadow: '0 1px 3px rgba(0,0,0,0.03)',
        }}
      >
        <div style={{ padding: '16px 20px', borderBottom: '1px solid #e2e8f0', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <History size={16} color="#059669" />
            <h3 style={{ margin: 0, fontSize: '14px', fontWeight: 800, color: '#0f172a' }}>
              Lịch Sử Các Phiên Nhập File Tại Chi Nhánh
            </h3>
          </div>
          <button
            onClick={fetchHistory}
            style={{ background: 'none', border: 'none', color: '#64748b', cursor: 'pointer', fontSize: '12px', fontWeight: 600 }}
          >
            Làm mới
          </button>
        </div>

        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '12.5px' }}>
            <thead>
              <tr style={{ background: '#f8fafc', borderBottom: '1px solid #e2e8f0', color: '#64748b', fontSize: '11px', fontWeight: 800 }}>
                <th style={{ padding: '12px 14px' }}>Mã Phiên Nhập</th>
                <th style={{ padding: '12px 14px' }}>Tên File</th>
                <th style={{ padding: '12px 14px', textAlign: 'center' }}>Số Dòng Nhập</th>
                <th style={{ padding: '12px 14px', textAlign: 'center' }}>Hợp Lệ</th>
                <th style={{ padding: '12px 14px' }}>Người Thực Hiện</th>
                <th style={{ padding: '12px 14px' }}>Trạng Thái</th>
                <th style={{ padding: '12px 14px' }}>Thời Gian</th>
              </tr>
            </thead>
            <tbody>
              {loadingHistory ? (
                <tr>
                  <td colSpan={7} style={{ padding: '30px', textAlign: 'center', color: '#94a3b8' }}>
                    Đang tải lịch sử…
                  </td>
                </tr>
              ) : historyJobs.length === 0 ? (
                <tr>
                  <td colSpan={7} style={{ padding: '30px', textAlign: 'center', color: '#94a3b8' }}>
                    Chưa có phiên nhập file nào trước đây.
                  </td>
                </tr>
              ) : (
                historyJobs.map((j) => (
                  <tr key={j.id} style={{ borderBottom: '1px solid #f1f5f9' }}>
                    <td style={{ padding: '12px 14px', fontFamily: 'monospace', fontWeight: 800, color: '#0f172a' }}>
                      {j.import_code}
                    </td>
                    <td style={{ padding: '12px 14px', fontWeight: 600, color: '#334155' }}>{j.filename}</td>
                    <td style={{ padding: '12px 14px', textAlign: 'center', fontWeight: 700 }}>{j.total_rows}</td>
                    <td style={{ padding: '12px 14px', textAlign: 'center', color: '#059669', fontWeight: 800 }}>{j.valid_rows}</td>
                    <td style={{ padding: '12px 14px', color: '#64748b' }}>{j.imported_by_name}</td>
                    <td style={{ padding: '12px 14px' }}>
                      <span
                        style={{
                          padding: '3px 8px',
                          borderRadius: '6px',
                          fontSize: '11px',
                          fontWeight: 700,
                          background: j.status === 'COMMITTED' ? '#dcfce7' : '#f1f5f9',
                          color: j.status === 'COMMITTED' ? '#166534' : '#475569',
                        }}
                      >
                        {j.status === 'COMMITTED' ? 'Đã nhập kho' : j.status}
                      </span>
                    </td>
                    <td style={{ padding: '12px 14px', color: '#64748b' }}>
                      {j.committed_at ? new Date(j.committed_at).toLocaleString('vi-VN') : j.created_at ? new Date(j.created_at).toLocaleString('vi-VN') : '—'}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
