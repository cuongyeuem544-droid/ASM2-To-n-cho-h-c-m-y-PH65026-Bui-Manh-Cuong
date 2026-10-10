import {
  AlertCircle,
  AlertTriangle,
  ArrowDownToLine,
  Building2,
  Calendar,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
  Download,
  ExternalLink,
  FileSpreadsheet,
  Filter,
  Layers,
  Package,
  PackageCheck,
  RefreshCw,
  RotateCcw,
  Search,
  Sparkles,
  Tag,
  UploadCloud,
  X,
} from 'lucide-react'
import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { AdminPageHeader } from '../components/AdminPageHeader'
import { api } from '../services/api'

interface WarehouseItem {
  id: number
  code: string
  name: string
  address: string
  district?: string
  province?: string
  is_central?: boolean
}

interface PreviewItem {
  row: number
  name: string
  registration_number?: string | null
  batch_number: string
  expiry_date: string
  quantity: number
  price?: number | null
  manufacturer?: string | null
  dosage_form?: string | null
  package?: string | null
  status: 'NEW' | 'EXISTING' | 'INVALID'
  status_label: string
  is_near_expiry?: boolean
}

interface PreviewResponse {
  filename: string
  warehouse_id?: number | null
  warehouse_name: string
  warehouse_code?: string
  total_rows: number
  valid_rows: number
  duplicate_rows: number
  invalid_rows: number
  total_quantity: number
  default_batch_applied: string
  default_expiry_applied: string
  items: PreviewItem[]
}

interface ProcessedItem {
  row: number
  name: string
  registration_number?: string | null
  price?: number | null
  manufacturer?: string | null
  batch_number?: string
  expiry_date?: string
  quantity?: number
  status: string
  canonical_product_id?: number | null
}

interface ImportResponse {
  message: string
  created: number
  updated: number
  skipped: number
  total_rows: number
  total_quantity?: number
  warehouse_name?: string
  items?: ProcessedItem[]
}

const RECOGNIZED_COLUMNS = [
  'Tên thuốc (name / ten_thuoc)',
  'Số đăng ký (registration_number / so_dang_ky)',
  'Số lô (batch_number / so_lo / lot)',
  'Hạn sử dụng (expiry_date / han_dung / hsd)',
  'Số lượng nhập (quantity / so_luong / sl)',
  'Giá bán (price / gia_ban / don_gia)',
  'Quy cách đóng gói (package / quy_cach)',
  'Dạng bào chế (dosage_form / dang_bao_che)',
  'Hoạt chất chính (ingredients / hoat_chat)',
  'Hàm lượng (strength / ham_luong)',
  'Nhà sản xuất (manufacturer / nha_san_xuat)',
  'Nước sản xuất (manufacturing_country / nuoc_san_xuat)',
  'Phân loại thuốc (rx_otc / loai_thuoc)',
]

interface PaginationBarProps {
  currentPage: number
  totalPages: number
  pageSize: number
  totalItems: number
  filteredCount: number
  onPageChange: (page: number) => void
  onPageSizeChange: (size: number) => void
  pageSizeOptions?: number[]
}

function PaginationBar({
  currentPage,
  totalPages,
  pageSize,
  totalItems,
  filteredCount,
  onPageChange,
  onPageSizeChange,
  pageSizeOptions = [15, 25, 50, 100],
}: PaginationBarProps) {
  const startItem = filteredCount === 0 ? 0 : (currentPage - 1) * pageSize + 1
  const endItem = Math.min(currentPage * pageSize, filteredCount)

  const getPageNumbers = () => {
    if (totalPages <= 7) {
      return Array.from({ length: totalPages }, (_, i) => i + 1)
    }
    if (currentPage <= 4) {
      return [1, 2, 3, 4, 5, '...', totalPages]
    }
    if (currentPage >= totalPages - 3) {
      return [1, '...', totalPages - 4, totalPages - 3, totalPages - 2, totalPages - 1, totalPages]
    }
    return [1, '...', currentPage - 1, currentPage, currentPage + 1, '...', totalPages]
  }

  const pages = getPageNumbers()

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: 12,
        padding: '12px 14px',
        background: '#f8fafc',
        borderTop: '1px solid #e2e8f0',
        borderBottomLeftRadius: 8,
        borderBottomRightRadius: 8,
        fontSize: 13,
      }}
    >
      {/* Items info and page size */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
        <span style={{ color: '#64748b' }}>
          Hiển thị <strong>{startItem} - {endItem}</strong> trong <strong>{filteredCount.toLocaleString('vi-VN')}</strong>
          {filteredCount !== totalItems ? ` (lọc từ ${totalItems.toLocaleString('vi-VN')} thuốc)` : ' thuốc'}
        </span>

        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <label style={{ color: '#64748b', fontSize: 12.5 }}>Dòng/trang:</label>
          <select
            value={pageSize}
            onChange={(e) => onPageSizeChange(Number(e.target.value))}
            style={{
              padding: '4px 8px',
              borderRadius: 6,
              border: '1px solid #cbd5e1',
              background: '#ffffff',
              fontSize: 12.5,
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            {pageSizeOptions.map((sz) => (
              <option key={sz} value={sz}>
                {sz}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Page controls */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
        <button
          type="button"
          onClick={() => onPageChange(1)}
          disabled={currentPage <= 1}
          title="Trang đầu"
          style={{
            padding: '5px 8px',
            borderRadius: 6,
            border: '1px solid #cbd5e1',
            background: currentPage <= 1 ? '#f1f5f9' : '#ffffff',
            color: currentPage <= 1 ? '#94a3b8' : '#334155',
            cursor: currentPage <= 1 ? 'not-allowed' : 'pointer',
            display: 'inline-flex',
            alignItems: 'center',
          }}
        >
          <ChevronsLeft size={15} />
        </button>

        <button
          type="button"
          onClick={() => onPageChange(currentPage - 1)}
          disabled={currentPage <= 1}
          title="Trang trước"
          style={{
            padding: '5px 8px',
            borderRadius: 6,
            border: '1px solid #cbd5e1',
            background: currentPage <= 1 ? '#f1f5f9' : '#ffffff',
            color: currentPage <= 1 ? '#94a3b8' : '#334155',
            cursor: currentPage <= 1 ? 'not-allowed' : 'pointer',
            display: 'inline-flex',
            alignItems: 'center',
          }}
        >
          <ChevronLeft size={15} />
        </button>

        {pages.map((p, idx) => {
          if (p === '...') {
            return (
              <span key={`dots-${idx}`} style={{ padding: '0 6px', color: '#94a3b8', fontWeight: 600 }}>
                ...
              </span>
            )
          }
          const pageNum = p as number
          const isActive = pageNum === currentPage
          return (
            <button
              key={pageNum}
              type="button"
              onClick={() => onPageChange(pageNum)}
              style={{
                minWidth: 32,
                height: 30,
                padding: '0 6px',
                borderRadius: 6,
                border: isActive ? '1px solid #0284c7' : '1px solid #cbd5e1',
                background: isActive ? '#0284c7' : '#ffffff',
                color: isActive ? '#ffffff' : '#334155',
                fontWeight: isActive ? 700 : 500,
                cursor: 'pointer',
                fontSize: 12.5,
              }}
            >
              {pageNum}
            </button>
          )
        })}

        <button
          type="button"
          onClick={() => onPageChange(currentPage + 1)}
          disabled={currentPage >= totalPages}
          title="Trang kế tiếp"
          style={{
            padding: '5px 8px',
            borderRadius: 6,
            border: '1px solid #cbd5e1',
            background: currentPage >= totalPages ? '#f1f5f9' : '#ffffff',
            color: currentPage >= totalPages ? '#94a3b8' : '#334155',
            cursor: currentPage >= totalPages ? 'not-allowed' : 'pointer',
            display: 'inline-flex',
            alignItems: 'center',
          }}
        >
          <ChevronRight size={15} />
        </button>

        <button
          type="button"
          onClick={() => onPageChange(totalPages)}
          disabled={currentPage >= totalPages}
          title="Trang cuối"
          style={{
            padding: '5px 8px',
            borderRadius: 6,
            border: '1px solid #cbd5e1',
            background: currentPage >= totalPages ? '#f1f5f9' : '#ffffff',
            color: currentPage >= totalPages ? '#94a3b8' : '#334155',
            cursor: currentPage >= totalPages ? 'not-allowed' : 'pointer',
            display: 'inline-flex',
            alignItems: 'center',
          }}
        >
          <ChevronsRight size={15} />
        </button>
      </div>
    </div>
  )
}

export function ImportsPage() {
  const [warehouses, setWarehouses] = useState<WarehouseItem[]>([])
  const [selectedWarehouseId, setSelectedWarehouseId] = useState<string>('')
  
  // Default Lot Number & Expiry Date
  const today = new Date()
  const defaultDateStr = today.toISOString().slice(0, 10).replace(/-/g, '')
  const [batchNumber, setBatchNumber] = useState<string>(`LOT-${defaultDateStr}-01`)
  
  const defaultExpDate = new Date(today.getFullYear() + 2, today.getMonth(), today.getDate())
    .toISOString()
    .slice(0, 10)
  const [expiryDate, setExpiryDate] = useState<string>(defaultExpDate)
  const [initialQuantity, setInitialQuantity] = useState<number>(100)

  const [autoApprove, setAutoApprove] = useState(true)
  const [forceUpdate, setForceUpdate] = useState(true)

  const [file, setFile] = useState<File | null>(null)
  const [previewLoading, setPreviewLoading] = useState(false)
  const [previewData, setPreviewData] = useState<PreviewResponse | null>(null)

  const [importBusy, setImportBusy] = useState(false)
  const [importResult, setImportResult] = useState<ImportResponse | null>(null)
  const [error, setError] = useState('')
  const [downloadingTemplate, setDownloadingTemplate] = useState(false)

  // Filter & Pagination state for Preview
  const [previewTab, setPreviewTab] = useState<'ALL' | 'NEW' | 'EXISTING' | 'WARNING'>('ALL')
  const [previewSearch, setPreviewSearch] = useState<string>('')
  const [previewPage, setPreviewPage] = useState<number>(1)
  const [previewPageSize, setPreviewPageSize] = useState<number>(25)

  // Filter & Pagination state for Result
  const [resultTab, setResultTab] = useState<'ALL' | 'CREATED' | 'UPDATED' | 'OTHER'>('ALL')
  const [resultSearch, setResultSearch] = useState<string>('')
  const [resultPage, setResultPage] = useState<number>(1)
  const [resultPageSize, setResultPageSize] = useState<number>(25)

  // Reset page when preview filter changes
  useEffect(() => {
    setPreviewPage(1)
  }, [previewTab, previewSearch])

  // Reset page when result filter changes
  useEffect(() => {
    setResultPage(1)
  }, [resultTab, resultSearch])

  // Count items by category in previewData
  const previewCounts = useMemo(() => {
    if (!previewData || !previewData.items) {
      return { all: 0, new: 0, existing: 0, warning: 0 }
    }
    const items = previewData.items
    let newCount = 0
    let existingCount = 0
    let warningCount = 0
    for (const item of items) {
      if (item.status === 'NEW') newCount++
      else if (item.status === 'EXISTING') existingCount++
      if (item.status === 'INVALID' || item.is_near_expiry) warningCount++
    }
    return {
      all: items.length,
      new: newCount,
      existing: existingCount,
      warning: warningCount,
    }
  }, [previewData])

  // Filter preview items
  const filteredPreviewItems = useMemo(() => {
    if (!previewData || !previewData.items) return []
    const q = previewSearch.trim().toLowerCase()
    return previewData.items.filter((item) => {
      // Tab filter
      if (previewTab === 'NEW' && item.status !== 'NEW') return false
      if (previewTab === 'EXISTING' && item.status !== 'EXISTING') return false
      if (previewTab === 'WARNING' && !(item.status === 'INVALID' || item.is_near_expiry)) return false

      // Search filter
      if (q) {
        const matchName = (item.name || '').toLowerCase().includes(q)
        const matchReg = (item.registration_number || '').toLowerCase().includes(q)
        const matchBatch = (item.batch_number || '').toLowerCase().includes(q)
        const matchMfr = (item.manufacturer || '').toLowerCase().includes(q)
        return matchName || matchReg || matchBatch || matchMfr
      }
      return true
    })
  }, [previewData, previewTab, previewSearch])

  // Paginated preview items
  const totalPreviewPages = Math.max(1, Math.ceil(filteredPreviewItems.length / previewPageSize))
  const paginatedPreviewItems = useMemo(() => {
    const start = (previewPage - 1) * previewPageSize
    return filteredPreviewItems.slice(start, start + previewPageSize)
  }, [filteredPreviewItems, previewPage, previewPageSize])

  // Count items by category in importResult
  const resultCounts = useMemo(() => {
    if (!importResult || !importResult.items) {
      return { all: 0, created: 0, updated: 0, other: 0 }
    }
    const items = importResult.items
    let createdCount = 0
    let updatedCount = 0
    let otherCount = 0
    for (const it of items) {
      if (it.status === 'CREATED') createdCount++
      else if (it.status === 'UPDATED') updatedCount++
      else otherCount++
    }
    return {
      all: items.length,
      created: createdCount,
      updated: updatedCount,
      other: otherCount,
    }
  }, [importResult])

  // Filter result items
  const filteredResultItems = useMemo(() => {
    if (!importResult || !importResult.items) return []
    const q = resultSearch.trim().toLowerCase()
    return importResult.items.filter((it) => {
      if (resultTab === 'CREATED' && it.status !== 'CREATED') return false
      if (resultTab === 'UPDATED' && it.status !== 'UPDATED') return false
      if (resultTab === 'OTHER' && (it.status === 'CREATED' || it.status === 'UPDATED')) return false

      if (q) {
        const matchName = (it.name || '').toLowerCase().includes(q)
        const matchReg = (it.registration_number || '').toLowerCase().includes(q)
        const matchBatch = (it.batch_number || '').toLowerCase().includes(q)
        return matchName || matchReg || matchBatch
      }
      return true
    })
  }, [importResult, resultTab, resultSearch])

  // Paginated result items
  const totalResultPages = Math.max(1, Math.ceil(filteredResultItems.length / resultPageSize))
  const paginatedResultItems = useMemo(() => {
    const start = (resultPage - 1) * resultPageSize
    return filteredResultItems.slice(start, start + resultPageSize)
  }, [filteredResultItems, resultPage, resultPageSize])

  // 1. Fetch warehouses on mount
  useEffect(() => {
    api<WarehouseItem[]>('/warehouses')
      .then((data) => {
        if (Array.isArray(data) && data.length > 0) {
          setWarehouses(data)
          // Ưu tiên kho trung tâm hoặc kho đầu tiên
          const central = data.find((w) => w.is_central) || data[0]
          setSelectedWarehouseId(String(central.id))
        }
      })
      .catch((err) => {
        console.error('Không thể tải danh sách kho', err)
      })
  }, [])

  // 2. Download sample excel template
  const handleDownloadTemplate = async () => {
    setDownloadingTemplate(true)
    setError('')
    try {
      const token = localStorage.getItem('pharmatrust_access_token')
      const res = await fetch('/api/v1/imports/template', {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      })
      if (!res.ok) throw new Error('Không thể tải file mẫu từ máy chủ')
      const blob = await res.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'Mau_Nhap_Don_Thuoc_Pharmatrust.xlsx'
      document.body.appendChild(a)
      a.click()
      a.remove()
      window.URL.revokeObjectURL(url)
    } catch (err: any) {
      setError(err.message || 'Lỗi tải tệp mẫu Excel')
    } finally {
      setDownloadingTemplate(false)
    }
  }

  // 3. Scan & Preview File
  const handleFileChange = async (selectedFile: File | null) => {
    setFile(selectedFile)
    setImportResult(null)
    setPreviewData(null)
    setError('')
    setPreviewTab('ALL')
    setPreviewSearch('')
    setPreviewPage(1)

    if (!selectedFile) return

    setPreviewLoading(true)
    try {
      const formData = new FormData()
      formData.append('file', selectedFile)
      if (selectedWarehouseId) formData.append('warehouse_id', selectedWarehouseId)
      if (batchNumber.trim()) formData.append('batch_number', batchNumber.trim())
      if (expiryDate) formData.append('expiry_date', expiryDate)
      formData.append('initial_quantity', String(initialQuantity || 100))

      const data = await api<PreviewResponse>('/imports/preview', {
        method: 'POST',
        body: formData,
      })
      setPreviewData(data)
    } catch (err: any) {
      setError(err.message || 'Lỗi quét tệp Excel. Vui lòng kiểm tra định dạng.')
    } finally {
      setPreviewLoading(false)
    }
  }

  // 4. Confirm Official Import
  const handleConfirmImport = async (e?: FormEvent) => {
    if (e) e.preventDefault()
    if (!file) {
      setError('Vui lòng chọn tệp Excel hoặc CSV trước khi nhập')
      return
    }
    if (!selectedWarehouseId) {
      setError('Vui lòng chọn Kho / Chi nhánh tiếp nhận thuốc')
      return
    }

    setImportBusy(true)
    setError('')
    setImportResult(null)

    const formData = new FormData()
    formData.append('file', file)
    formData.append('warehouse_id', selectedWarehouseId)
    if (batchNumber.trim()) formData.append('batch_number', batchNumber.trim())
    if (expiryDate) formData.append('expiry_date', expiryDate)
    formData.append('initial_quantity', String(initialQuantity || 100))
    formData.append('auto_approve', String(autoApprove))
    formData.append('force_update', String(forceUpdate))

    try {
      const res = await api<ImportResponse>('/imports/file', {
        method: 'POST',
        body: formData,
      })
      setImportResult(res)
      setPreviewData(null)
    } catch (err: any) {
      setError(err.message || 'Không thể nhập tệp vào kho')
    } finally {
      setImportBusy(false)
    }
  }

  // Reset to import another batch
  const handleReset = () => {
    setFile(null)
    setPreviewData(null)
    setImportResult(null)
    setError('')
    setPreviewTab('ALL')
    setPreviewSearch('')
    setPreviewPage(1)
    setResultTab('ALL')
    setResultSearch('')
    setResultPage(1)
  }

  const selectedWarehouse = warehouses.find((w) => String(w.id) === selectedWarehouseId)

  return (
    <div className="page" style={{ maxWidth: 1200, margin: '0 auto', padding: '24px 28px 60px' }}>
      <AdminPageHeader
        title="Nhập File Excel Đơn Thuốc & Quản Lý Lô Thuốc"
        subtitle="Chọn kho nhập, thiết lập số lô và hạn dùng. Hệ thống tự động quét nhận diện thuốc và phân bổ tồn kho bán hàng."
        breadcrumbs={[
          { label: 'Trang chủ', href: '/' },
          { label: 'Nhập Liệu & Đơn Thuốc', href: '/imports' },
          { label: 'Nhập file Excel' },
        ]}
        actions={
          <button
            type="button"
            className="button button-secondary"
            onClick={handleDownloadTemplate}
            disabled={downloadingTemplate}
            style={{ display: 'inline-flex', alignItems: 'center', gap: 7, fontWeight: 700 }}
          >
            {downloadingTemplate ? (
              <RefreshCw size={15} className="spin" />
            ) : (
              <Download size={15} color="#0284c7" />
            )}
            <span>Tải file Excel mẫu (.xlsx)</span>
          </button>
        }
      />

      {/* Error alert */}
      {error && (
        <div
          className="alert alert-error"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 10,
            marginBottom: 20,
            padding: '12px 16px',
            borderRadius: 10,
          }}
        >
          <AlertCircle size={20} />
          <span>{error}</span>
        </div>
      )}

      {/* STEP 1: FORM SETUP & FILE SELECTION */}
      {!importResult && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          {/* Warehouse and Batch Settings Card */}
          <div
            className="panel"
            style={{
              background: '#ffffff',
              borderRadius: 12,
              border: '1px solid #e2e8f0',
              padding: '20px 24px',
              boxShadow: '0 1px 3px rgba(0,0,0,0.04)',
            }}
          >
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                marginBottom: 16,
                paddingBottom: 12,
                borderBottom: '1px solid #f1f5f9',
              }}
            >
              <Building2 size={20} color="#0284c7" />
              <h2 style={{ fontSize: 16, fontWeight: 750, color: '#0f172a', margin: 0 }}>
                1. Thông Tin Nhập Hàng & Phân Bổ Lô Thuốc
              </h2>
            </div>

            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
                gap: 16,
              }}
            >
              {/* Nhập ở đâu - Kho tiếp nhận */}
              <div>
                <label
                  style={{
                    display: 'block',
                    fontSize: 13,
                    fontWeight: 700,
                    color: '#334155',
                    marginBottom: 6,
                  }}
                >
                  Nhập ở đâu (Kho / Chi nhánh tiếp nhận) <span style={{ color: '#ef4444' }}>*</span>
                </label>
                <select
                  value={selectedWarehouseId}
                  onChange={(e) => {
                    setSelectedWarehouseId(e.target.value)
                    if (file) handleFileChange(file)
                  }}
                  style={{
                    width: '100%',
                    padding: '9px 12px',
                    borderRadius: 8,
                    border: '1px solid #cbd5e1',
                    fontSize: 13.5,
                    fontWeight: 600,
                    color: '#0f172a',
                    background: '#fff',
                  }}
                  required
                >
                  {warehouses.map((wh) => (
                    <option key={wh.id} value={wh.id}>
                      {wh.name} ({wh.code}) {wh.is_central ? '— Kho Tổng' : ''}
                    </option>
                  ))}
                </select>
                <div style={{ fontSize: 11.5, color: '#64748b', marginTop: 4 }}>
                  {selectedWarehouse?.address || 'Chọn kho để lưu trữ tồn kho sau khi quét'}
                </div>
              </div>

              {/* Mã số lô thuốc */}
              <div>
                <label
                  style={{
                    display: 'block',
                    fontSize: 13,
                    fontWeight: 700,
                    color: '#334155',
                    marginBottom: 6,
                  }}
                >
                  Mã số lô thuốc áp dụng <span style={{ color: '#ef4444' }}>*</span>
                </label>
                <div style={{ position: 'relative' }}>
                  <input
                    type="text"
                    value={batchNumber}
                    onChange={(e) => setBatchNumber(e.target.value)}
                    placeholder="VD: LOT-202610-01"
                    style={{
                      width: '100%',
                      padding: '9px 12px 9px 34px',
                      borderRadius: 8,
                      border: '1px solid #cbd5e1',
                      fontSize: 13.5,
                      fontWeight: 600,
                      color: '#0f172a',
                      fontFamily: 'monospace',
                    }}
                    required
                  />
                  <Tag
                    size={15}
                    color="#64748b"
                    style={{ position: 'absolute', left: 10, top: 12 }}
                  />
                </div>
                <div style={{ fontSize: 11.5, color: '#64748b', marginTop: 4 }}>
                  Áp dụng làm mã lô mặc định nếu file Excel không có cột Số lô
                </div>
              </div>

              {/* Hạn của lô thuốc */}
              <div>
                <label
                  style={{
                    display: 'block',
                    fontSize: 13,
                    fontWeight: 700,
                    color: '#334155',
                    marginBottom: 6,
                  }}
                >
                  Hạn của lô thuốc này (Expiry Date) <span style={{ color: '#ef4444' }}>*</span>
                </label>
                <div style={{ position: 'relative' }}>
                  <input
                    type="date"
                    value={expiryDate}
                    onChange={(e) => setExpiryDate(e.target.value)}
                    style={{
                      width: '100%',
                      padding: '8px 12px 8px 34px',
                      borderRadius: 8,
                      border: '1px solid #cbd5e1',
                      fontSize: 13.5,
                      fontWeight: 600,
                      color: '#0f172a',
                    }}
                    required
                  />
                  <Calendar
                    size={15}
                    color="#64748b"
                    style={{ position: 'absolute', left: 10, top: 11 }}
                  />
                </div>
                <div style={{ fontSize: 11.5, color: '#64748b', marginTop: 4 }}>
                  Áp dụng làm hạn sử dụng nếu trong file chưa ghi hạn
                </div>
              </div>

              {/* Số lượng nhập mặc định */}
              <div>
                <label
                  style={{
                    display: 'block',
                    fontSize: 13,
                    fontWeight: 700,
                    color: '#334155',
                    marginBottom: 6,
                  }}
                >
                  Số lượng nhập mặc định mỗi thuốc
                </label>
                <div style={{ position: 'relative' }}>
                  <input
                    type="number"
                    min="1"
                    value={initialQuantity}
                    onChange={(e) => setInitialQuantity(Math.max(1, Number(e.target.value) || 1))}
                    style={{
                      width: '100%',
                      padding: '8px 12px 8px 34px',
                      borderRadius: 8,
                      border: '1px solid #cbd5e1',
                      fontSize: 13.5,
                      fontWeight: 600,
                      color: '#0f172a',
                    }}
                  />
                  <Package
                    size={15}
                    color="#64748b"
                    style={{ position: 'absolute', left: 10, top: 11 }}
                  />
                </div>
                <div style={{ fontSize: 11.5, color: '#64748b', marginTop: 4 }}>
                  Áp dụng khi dòng thuốc trong file không có cột Số lượng
                </div>
              </div>
            </div>

            {/* Checkbox options */}
            <div
              style={{
                display: 'flex',
                gap: 24,
                flexWrap: 'wrap',
                marginTop: 18,
                paddingTop: 14,
                borderTop: '1px dashed #e2e8f0',
              }}
            >
              <label style={{ display: 'inline-flex', alignItems: 'center', gap: 8, cursor: 'pointer', fontSize: 13, color: '#334155', fontWeight: 600 }}>
                <input
                  type="checkbox"
                  checked={autoApprove}
                  onChange={(e) => setAutoApprove(e.target.checked)}
                />
                <span>Tự động duyệt và mở bán ngay trên Website (:3000)</span>
              </label>

              <label style={{ display: 'inline-flex', alignItems: 'center', gap: 8, cursor: 'pointer', fontSize: 13, color: '#334155', fontWeight: 600 }}>
                <input
                  type="checkbox"
                  checked={forceUpdate}
                  onChange={(e) => setForceUpdate(e.target.checked)}
                />
                <span>Cập nhật giá bán và thông tin nếu thuốc đã có trong kho</span>
              </label>
            </div>
          </div>

          {/* File Upload Drop Zone */}
          <div
            className="panel"
            style={{
              background: '#ffffff',
              borderRadius: 12,
              border: '1px solid #e2e8f0',
              padding: '20px 24px',
              boxShadow: '0 1px 3px rgba(0,0,0,0.04)',
            }}
          >
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                marginBottom: 16,
                paddingBottom: 12,
                borderBottom: '1px solid #f1f5f9',
              }}
            >
              <FileSpreadsheet size={20} color="#0284c7" />
              <h2 style={{ fontSize: 16, fontWeight: 750, color: '#0f172a', margin: 0 }}>
                2. Tải Lên Tệp Excel Đơn Thuốc
              </h2>
            </div>

            <label
              className={`drop-zone ${file ? 'has-file' : ''}`}
              style={{
                border: '2px dashed #94a3b8',
                borderRadius: 12,
                padding: '36px 20px',
                textAlign: 'center',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 8,
                cursor: 'pointer',
                background: file ? '#f0fdf4' : '#f8fafc',
                borderColor: file ? '#22c55e' : '#cbd5e1',
                transition: 'all 0.2s',
              }}
            >
              <input
                type="file"
                accept=".xlsx,.csv,.xls"
                onChange={(e) => handleFileChange(e.target.files?.[0] || null)}
                style={{ display: 'none' }}
              />

              {previewLoading ? (
                <>
                  <RefreshCw size={36} className="spin" color="#0284c7" />
                  <strong style={{ fontSize: 15, color: '#0369a1' }}>
                    Hệ thống đang quét và nhận diện thuốc từ tệp...
                  </strong>
                  <span style={{ fontSize: 12.5, color: '#64748b' }}>
                    Vui lòng chờ trong giây lát
                  </span>
                </>
              ) : file ? (
                <>
                  <CheckCircle2 size={40} color="#16a34a" />
                  <strong style={{ fontSize: 15, color: '#15803d' }}>{file.name}</strong>
                  <span style={{ fontSize: 12.5, color: '#64748b' }}>
                    Dung lượng: {(file.size / 1024).toFixed(1)} KB · Nhấp để đổi tệp khác
                  </span>
                </>
              ) : (
                <>
                  <UploadCloud size={44} color="#0284c7" />
                  <strong style={{ fontSize: 15, color: '#0f172a' }}>
                    Kéo thả hoặc nhấp để chọn tệp Excel danh sách đơn thuốc (.xlsx, .csv)
                  </strong>
                  <span style={{ fontSize: 12.5, color: '#64748b' }}>
                    Hỗ trợ đầy đủ định dạng chuẩn. Hệ thống sẽ tự động quét và phân tích trước khi lưu.
                  </span>
                </>
              )}
            </label>
          </div>

          {/* STEP 2: PREVIEW SCAN RESULTS */}
          {previewData && (
            <div
              className="panel"
              style={{
                background: '#ffffff',
                borderRadius: 12,
                border: '1.5px solid #0284c7',
                padding: '24px',
                boxShadow: '0 8px 24px rgba(2, 132, 199, 0.08)',
                animation: 'fadeIn 0.25s ease',
              }}
            >
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  flexWrap: 'wrap',
                  gap: 12,
                  marginBottom: 18,
                  paddingBottom: 14,
                  borderBottom: '1px solid #e2e8f0',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <Sparkles size={22} color="#0284c7" />
                  <div>
                    <h3 style={{ margin: 0, fontSize: 17, fontWeight: 750, color: '#0f172a' }}>
                      Kết Quả Tự Động Quét & Kiểm Tra Tệp ({previewData.filename})
                    </h3>
                    <p style={{ margin: '2px 0 0', fontSize: 12.5, color: '#64748b' }}>
                      Kiểm tra kỹ thông tin thuốc, số lô và hạn dùng bên dưới trước khi xác nhận nhập kho.
                    </p>
                  </div>
                </div>

                <div style={{ display: 'flex', gap: 10 }}>
                  <button
                    type="button"
                    className="button button-secondary"
                    onClick={handleReset}
                    style={{ fontSize: 13 }}
                  >
                    Hủy & Chọn file khác
                  </button>
                  <button
                    type="button"
                    className="button button-primary"
                    onClick={() => handleConfirmImport()}
                    disabled={importBusy || previewData.valid_rows === 0}
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 7,
                      fontSize: 13.5,
                      fontWeight: 700,
                      background: '#16a34a',
                    }}
                  >
                    {importBusy ? (
                      <RefreshCw size={15} className="spin" />
                    ) : (
                      <PackageCheck size={16} />
                    )}
                    <span>Xác nhận nhập {previewData.valid_rows} thuốc vào kho</span>
                  </button>
                </div>
              </div>

              {/* Metric stats cards */}
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
                  gap: 12,
                  marginBottom: 20,
                }}
              >
                <div
                  style={{
                    background: '#eff6ff',
                    padding: '14px 16px',
                    borderRadius: 10,
                    border: '1px solid #bfdbfe',
                  }}
                >
                  <span style={{ fontSize: 12, color: '#1e40af', fontWeight: 700, display: 'block' }}>
                    TỔNG THUỐC QUÉT ĐƯỢC
                  </span>
                  <strong style={{ fontSize: 24, color: '#1d4ed8' }}>
                    {previewData.total_rows}
                  </strong>
                  <span style={{ fontSize: 11.5, color: '#3b82f6', display: 'block', marginTop: 2 }}>
                    dòng trong tệp Excel
                  </span>
                </div>

                <div
                  style={{
                    background: '#f0fdf4',
                    padding: '14px 16px',
                    borderRadius: 10,
                    border: '1px solid #bbf7d0',
                  }}
                >
                  <span style={{ fontSize: 12, color: '#166534', fontWeight: 700, display: 'block' }}>
                    THUỐC HỢP LỆ NHẬP KHO
                  </span>
                  <strong style={{ fontSize: 24, color: '#16a34a' }}>
                    {previewData.valid_rows}
                  </strong>
                  <span style={{ fontSize: 11.5, color: '#22c55e', display: 'block', marginTop: 2 }}>
                    {previewData.duplicate_rows > 0
                      ? `(${previewData.duplicate_rows} thuốc đã có sẽ cập nhật)`
                      : 'Đầy đủ thông tin'}
                  </span>
                </div>

                <div
                  style={{
                    background: '#fefce8',
                    padding: '14px 16px',
                    borderRadius: 10,
                    border: '1px solid #fef08a',
                  }}
                >
                  <span style={{ fontSize: 12, color: '#854d0e', fontWeight: 700, display: 'block' }}>
                    TỔNG SỐ LƯỢNG NHẬP
                  </span>
                  <strong style={{ fontSize: 24, color: '#ca8a04' }}>
                    {previewData.total_quantity.toLocaleString('vi-VN')}
                  </strong>
                  <span style={{ fontSize: 11.5, color: '#a16207', display: 'block', marginTop: 2 }}>
                    đơn vị / hộp thuốc
                  </span>
                </div>

                <div
                  style={{
                    background: '#f8fafc',
                    padding: '14px 16px',
                    borderRadius: 10,
                    border: '1px solid #e2e8f0',
                  }}
                >
                  <span style={{ fontSize: 12, color: '#475569', fontWeight: 700, display: 'block' }}>
                    KHO & HẠN DÙNG ÁP DỤNG
                  </span>
                  <strong style={{ fontSize: 14, color: '#0f172a', display: 'block', marginTop: 4 }}>
                    {previewData.warehouse_name}
                  </strong>
                  <span style={{ fontSize: 11.5, color: '#64748b', display: 'block', marginTop: 2 }}>
                    Lô: {previewData.default_batch_applied} · HSD: {previewData.default_expiry_applied}
                  </span>
                </div>
              </div>

              {/* Preview Filter Tabs & Search */}
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  flexWrap: 'wrap',
                  gap: 12,
                  marginBottom: 12,
                  background: '#f8fafc',
                  padding: '10px 14px',
                  borderRadius: 8,
                  border: '1px solid #e2e8f0',
                }}
              >
                {/* Tabs */}
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                  <button
                    type="button"
                    onClick={() => setPreviewTab('ALL')}
                    style={{
                      padding: '6px 12px',
                      borderRadius: 6,
                      border: previewTab === 'ALL' ? '1px solid #0284c7' : '1px solid #cbd5e1',
                      background: previewTab === 'ALL' ? '#0284c7' : '#ffffff',
                      color: previewTab === 'ALL' ? '#ffffff' : '#334155',
                      fontWeight: previewTab === 'ALL' ? 700 : 500,
                      fontSize: 12.5,
                      cursor: 'pointer',
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 6,
                    }}
                  >
                    <span>Tất cả</span>
                    <span
                      style={{
                        background: previewTab === 'ALL' ? 'rgba(255,255,255,0.25)' : '#e2e8f0',
                        color: previewTab === 'ALL' ? '#ffffff' : '#1e293b',
                        borderRadius: 999,
                        padding: '1px 7px',
                        fontSize: 11,
                        fontWeight: 700,
                      }}
                    >
                      {previewCounts.all}
                    </span>
                  </button>

                  <button
                    type="button"
                    onClick={() => setPreviewTab('NEW')}
                    style={{
                      padding: '6px 12px',
                      borderRadius: 6,
                      border: previewTab === 'NEW' ? '1px solid #16a34a' : '1px solid #cbd5e1',
                      background: previewTab === 'NEW' ? '#16a34a' : '#ffffff',
                      color: previewTab === 'NEW' ? '#ffffff' : '#334155',
                      fontWeight: previewTab === 'NEW' ? 700 : 500,
                      fontSize: 12.5,
                      cursor: 'pointer',
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 6,
                    }}
                  >
                    <span>Thuốc tạo mới</span>
                    <span
                      style={{
                        background: previewTab === 'NEW' ? 'rgba(255,255,255,0.25)' : '#dcfce7',
                        color: previewTab === 'NEW' ? '#ffffff' : '#15803d',
                        borderRadius: 999,
                        padding: '1px 7px',
                        fontSize: 11,
                        fontWeight: 700,
                      }}
                    >
                      {previewCounts.new}
                    </span>
                  </button>

                  <button
                    type="button"
                    onClick={() => setPreviewTab('EXISTING')}
                    style={{
                      padding: '6px 12px',
                      borderRadius: 6,
                      border: previewTab === 'EXISTING' ? '1px solid #2563eb' : '1px solid #cbd5e1',
                      background: previewTab === 'EXISTING' ? '#2563eb' : '#ffffff',
                      color: previewTab === 'EXISTING' ? '#ffffff' : '#334155',
                      fontWeight: previewTab === 'EXISTING' ? 700 : 500,
                      fontSize: 12.5,
                      cursor: 'pointer',
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 6,
                    }}
                  >
                    <span>Thuốc đã có / Cập nhật</span>
                    <span
                      style={{
                        background: previewTab === 'EXISTING' ? 'rgba(255,255,255,0.25)' : '#dbeafe',
                        color: previewTab === 'EXISTING' ? '#ffffff' : '#1d4ed8',
                        borderRadius: 999,
                        padding: '1px 7px',
                        fontSize: 11,
                        fontWeight: 700,
                      }}
                    >
                      {previewCounts.existing}
                    </span>
                  </button>

                  <button
                    type="button"
                    onClick={() => setPreviewTab('WARNING')}
                    style={{
                      padding: '6px 12px',
                      borderRadius: 6,
                      border: previewTab === 'WARNING' ? '1px solid #d97706' : '1px solid #cbd5e1',
                      background: previewTab === 'WARNING' ? '#d97706' : '#ffffff',
                      color: previewTab === 'WARNING' ? '#ffffff' : '#334155',
                      fontWeight: previewTab === 'WARNING' ? 700 : 500,
                      fontSize: 12.5,
                      cursor: 'pointer',
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 6,
                    }}
                  >
                    <span>Cảnh báo / Lỗi / Cận hạn</span>
                    <span
                      style={{
                        background: previewTab === 'WARNING' ? 'rgba(255,255,255,0.25)' : '#fef3c7',
                        color: previewTab === 'WARNING' ? '#ffffff' : '#b45309',
                        borderRadius: 999,
                        padding: '1px 7px',
                        fontSize: 11,
                        fontWeight: 700,
                      }}
                    >
                      {previewCounts.warning}
                    </span>
                  </button>
                </div>

                {/* Instant Search */}
                <div style={{ position: 'relative', minWidth: 260 }}>
                  <Search
                    size={14}
                    style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: '#94a3b8' }}
                  />
                  <input
                    type="text"
                    placeholder="Tìm tên thuốc, SĐK, số lô..."
                    value={previewSearch}
                    onChange={(e) => setPreviewSearch(e.target.value)}
                    style={{
                      width: '100%',
                      padding: '6px 28px 6px 30px',
                      borderRadius: 6,
                      border: '1px solid #cbd5e1',
                      fontSize: 12.5,
                      background: '#ffffff',
                    }}
                  />
                  {previewSearch && (
                    <button
                      type="button"
                      onClick={() => setPreviewSearch('')}
                      style={{
                        position: 'absolute',
                        right: 8,
                        top: '50%',
                        transform: 'translateY(-50%)',
                        background: 'none',
                        border: 'none',
                        cursor: 'pointer',
                        color: '#94a3b8',
                        padding: 2,
                      }}
                    >
                      <X size={13} />
                    </button>
                  )}
                </div>
              </div>

              {/* Preview Table Container (Max height + Sticky header to prevent infinite page stretching) */}
              <div
                style={{
                  overflowX: 'auto',
                  maxHeight: '520px',
                  overflowY: 'auto',
                  border: '1px solid #e2e8f0',
                  borderTopLeftRadius: 8,
                  borderTopRightRadius: 8,
                  position: 'relative',
                }}
              >
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12.5 }}>
                  <thead style={{ position: 'sticky', top: 0, zIndex: 5, background: '#f8fafc', boxShadow: '0 1px 2px rgba(0,0,0,0.06)' }}>
                    <tr style={{ borderBottom: '1px solid #e2e8f0', color: '#475569', textAlign: 'left' }}>
                      <th style={{ padding: '10px 12px' }}>#</th>
                      <th style={{ padding: '10px 12px' }}>Tên thuốc</th>
                      <th style={{ padding: '10px 12px' }}>Số đăng ký</th>
                      <th style={{ padding: '10px 12px' }}>Số lô</th>
                      <th style={{ padding: '10px 12px' }}>Hạn dùng (HSD)</th>
                      <th style={{ padding: '10px 12px', textAlign: 'right' }}>SL nhập</th>
                      <th style={{ padding: '10px 12px', textAlign: 'right' }}>Giá bán</th>
                      <th style={{ padding: '10px 12px' }}>Nhà sản xuất</th>
                      <th style={{ padding: '10px 12px', textAlign: 'center' }}>Đánh giá</th>
                    </tr>
                  </thead>
                  <tbody>
                    {paginatedPreviewItems.length === 0 ? (
                      <tr>
                        <td colSpan={9} style={{ textAlign: 'center', padding: '36px 16px', color: '#64748b' }}>
                          Không có đơn thuốc nào phù hợp với bộ lọc hiện tại.
                        </td>
                      </tr>
                    ) : (
                      paginatedPreviewItems.map((item) => (
                        <tr
                          key={item.row}
                          style={{
                            borderBottom: '1px solid #f1f5f9',
                            background: item.status === 'INVALID' ? '#fef2f2' : 'transparent',
                          }}
                        >
                          <td style={{ padding: '10px 12px', color: '#64748b' }}>#{item.row}</td>
                          <td style={{ padding: '10px 12px', fontWeight: 700, color: '#0f172a' }}>
                            {item.name}
                          </td>
                          <td style={{ padding: '10px 12px' }}>
                            <code style={{ fontFamily: 'monospace', color: '#0369a1' }}>
                              {item.registration_number || '—'}
                            </code>
                          </td>
                          <td style={{ padding: '10px 12px' }}>
                            <span style={{ fontFamily: 'monospace', fontWeight: 600, color: '#334155' }}>
                              {item.batch_number}
                            </span>
                          </td>
                          <td style={{ padding: '10px 12px' }}>
                            <span
                              style={{
                                fontWeight: 600,
                                color: item.is_near_expiry ? '#b45309' : '#047857',
                                background: item.is_near_expiry ? '#fef3c7' : '#dcfce7',
                                padding: '2px 6px',
                                borderRadius: 4,
                                fontSize: 11.5,
                              }}
                            >
                              {item.expiry_date}
                            </span>
                          </td>
                          <td style={{ padding: '10px 12px', textAlign: 'right', fontWeight: 700, color: '#0f172a' }}>
                            {item.quantity.toLocaleString('vi-VN')}
                          </td>
                          <td style={{ padding: '10px 12px', textAlign: 'right', fontWeight: 600, color: '#059669' }}>
                            {item.price ? `${item.price.toLocaleString('vi-VN')} đ` : '—'}
                          </td>
                          <td style={{ padding: '10px 12px', color: '#64748b' }}>
                            {item.manufacturer || '—'}
                          </td>
                          <td style={{ padding: '10px 12px', textAlign: 'center' }}>
                            {item.status === 'NEW' && (
                              <span style={{ background: '#dcfce7', color: '#15803d', padding: '3px 8px', borderRadius: 4, fontWeight: 700, fontSize: 11 }}>
                                Thuốc mới
                              </span>
                            )}
                            {item.status === 'EXISTING' && (
                              <span style={{ background: '#dbeafe', color: '#1d4ed8', padding: '3px 8px', borderRadius: 4, fontWeight: 700, fontSize: 11 }}>
                                Cập nhật lô
                              </span>
                            )}
                            {item.status === 'INVALID' && (
                              <span style={{ background: '#fee2e2', color: '#b91c1c', padding: '3px 8px', borderRadius: 4, fontWeight: 700, fontSize: 11 }}>
                                {item.status_label}
                              </span>
                            )}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>

              {/* Preview Pagination Bar */}
              <PaginationBar
                currentPage={previewPage}
                totalPages={totalPreviewPages}
                pageSize={previewPageSize}
                totalItems={previewCounts.all}
                filteredCount={filteredPreviewItems.length}
                onPageChange={setPreviewPage}
                onPageSizeChange={(sz) => {
                  setPreviewPageSize(sz)
                  setPreviewPage(1)
                }}
              />

              {/* Confirm Bottom Bar */}
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  marginTop: 20,
                  paddingTop: 16,
                  borderTop: '1px solid #f1f5f9',
                }}
              >
                <div style={{ fontSize: 13, color: '#475569' }}>
                  Kho tiếp nhận: <strong>{previewData.warehouse_name}</strong> · Tổng số lượng nhập:{' '}
                  <strong style={{ color: '#16a34a' }}>{previewData.total_quantity.toLocaleString('vi-VN')} đơn vị</strong>
                </div>

                <button
                  type="button"
                  className="button button-primary"
                  onClick={() => handleConfirmImport()}
                  disabled={importBusy || previewData.valid_rows === 0}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 8,
                    padding: '10px 24px',
                    fontSize: 14,
                    fontWeight: 700,
                    background: '#16a34a',
                  }}
                >
                  {importBusy ? (
                    <RefreshCw size={17} className="spin" />
                  ) : (
                    <ArrowDownToLine size={18} />
                  )}
                  <span>Xác nhận nhập kho ngay</span>
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* STEP 3: RESULT VIEW AFTER OFFICIAL IMPORT */}
      {importResult && (
        <div
          className="panel"
          style={{
            background: '#ffffff',
            borderRadius: 14,
            border: '2px solid #22c55e',
            padding: '28px',
            boxShadow: '0 8px 30px rgba(34, 197, 94, 0.12)',
            animation: 'fadeIn 0.25s ease',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
            <CheckCircle2 size={32} color="#16a34a" />
            <div>
              <h2 style={{ margin: 0, fontSize: 20, color: '#15803d', fontWeight: 800 }}>
                Nhập Kho & Nhận Diện Đơn Thuốc Thành Công!
              </h2>
              <p style={{ margin: '4px 0 0', color: '#475569', fontSize: 13.5 }}>
                Hệ thống đã lưu trữ toàn bộ hồ sơ thuốc, phân bổ số lô và cập nhật tồn kho tại{' '}
                <strong>{importResult.warehouse_name || selectedWarehouse?.name}</strong>.
              </p>
            </div>
          </div>

          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))',
              gap: 12,
              margin: '20px 0',
            }}
          >
            <div style={{ background: '#f0fdf4', padding: '14px 16px', borderRadius: 10, border: '1px solid #bbf7d0', textAlign: 'center' }}>
              <span style={{ fontSize: 12, color: '#166534', fontWeight: 700, display: 'block' }}>THUỐC TẠO MỚI</span>
              <strong style={{ fontSize: 26, color: '#16a34a' }}>{importResult.created}</strong>
            </div>
            <div style={{ background: '#eff6ff', padding: '14px 16px', borderRadius: 10, border: '1px solid #bfdbfe', textAlign: 'center' }}>
              <span style={{ fontSize: 12, color: '#1e40af', fontWeight: 700, display: 'block' }}>ĐÃ CẬP NHẬT LÔ & GIÁ</span>
              <strong style={{ fontSize: 26, color: '#2563eb' }}>{importResult.updated}</strong>
            </div>
            <div style={{ background: '#fefce8', padding: '14px 16px', borderRadius: 10, border: '1px solid #fef08a', textAlign: 'center' }}>
              <span style={{ fontSize: 12, color: '#854d0e', fontWeight: 700, display: 'block' }}>TỔNG SL ĐÃ NHẬP KHO</span>
              <strong style={{ fontSize: 26, color: '#ca8a04' }}>
                {(importResult.total_quantity || 0).toLocaleString('vi-VN')}
              </strong>
            </div>
            <div style={{ background: '#f8fafc', padding: '14px 16px', borderRadius: 10, border: '1px solid #e2e8f0', textAlign: 'center' }}>
              <span style={{ fontSize: 12, color: '#64748b', fontWeight: 700, display: 'block' }}>TỔNG DÒNG XỬ LÝ</span>
              <strong style={{ fontSize: 26, color: '#475569' }}>{importResult.total_rows}</strong>
            </div>
          </div>

          {/* Quick links */}
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginTop: 24, paddingTop: 18, borderTop: '1px solid #f1f5f9' }}>
            <Link
              to="/inventory/batches"
              className="button button-primary"
              style={{ display: 'inline-flex', alignItems: 'center', gap: 7, textDecoration: 'none', fontWeight: 700 }}
            >
              <Layers size={16} /> Xem Lô Thuốc & Hạn Dùng Kho
            </Link>
            <Link
              to="/products"
              className="button button-secondary"
              style={{ display: 'inline-flex', alignItems: 'center', gap: 7, textDecoration: 'none', fontWeight: 700 }}
            >
              <Package size={16} /> Xem Danh Mục Thuốc Mở Bán
            </Link>
            <a
              href="http://localhost:3000"
              target="_blank"
              rel="noreferrer"
              className="button button-secondary"
              style={{ display: 'inline-flex', alignItems: 'center', gap: 7, textDecoration: 'none', fontWeight: 700 }}
            >
              <ExternalLink size={16} /> Kiểm tra Website Khách Hàng (:3000)
            </a>
            <button
              type="button"
              className="button"
              onClick={handleReset}
              style={{ display: 'inline-flex', alignItems: 'center', gap: 7, fontWeight: 700, marginLeft: 'auto', background: '#f1f5f9' }}
            >
              <RotateCcw size={15} /> Nhập đợt thuốc mới
            </button>
          </div>

          {/* Result items table */}
          {importResult.items && importResult.items.length > 0 && (
            <div style={{ marginTop: 24 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12, flexWrap: 'wrap', gap: 10 }}>
                <h3 style={{ fontSize: 14.5, fontWeight: 750, color: '#0f172a', margin: 0 }}>
                  Chi tiết các mặt hàng thuốc vừa nhập kho:
                </h3>
              </div>

              {/* Result Filter Tabs & Search */}
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  flexWrap: 'wrap',
                  gap: 12,
                  marginBottom: 12,
                  background: '#f8fafc',
                  padding: '10px 14px',
                  borderRadius: 8,
                  border: '1px solid #e2e8f0',
                }}
              >
                {/* Tabs */}
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                  <button
                    type="button"
                    onClick={() => setResultTab('ALL')}
                    style={{
                      padding: '6px 12px',
                      borderRadius: 6,
                      border: resultTab === 'ALL' ? '1px solid #0284c7' : '1px solid #cbd5e1',
                      background: resultTab === 'ALL' ? '#0284c7' : '#ffffff',
                      color: resultTab === 'ALL' ? '#ffffff' : '#334155',
                      fontWeight: resultTab === 'ALL' ? 700 : 500,
                      fontSize: 12.5,
                      cursor: 'pointer',
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 6,
                    }}
                  >
                    <span>Tất cả</span>
                    <span
                      style={{
                        background: resultTab === 'ALL' ? 'rgba(255,255,255,0.25)' : '#e2e8f0',
                        color: resultTab === 'ALL' ? '#ffffff' : '#1e293b',
                        borderRadius: 999,
                        padding: '1px 7px',
                        fontSize: 11,
                        fontWeight: 700,
                      }}
                    >
                      {resultCounts.all}
                    </span>
                  </button>

                  <button
                    type="button"
                    onClick={() => setResultTab('CREATED')}
                    style={{
                      padding: '6px 12px',
                      borderRadius: 6,
                      border: resultTab === 'CREATED' ? '1px solid #16a34a' : '1px solid #cbd5e1',
                      background: resultTab === 'CREATED' ? '#16a34a' : '#ffffff',
                      color: resultTab === 'CREATED' ? '#ffffff' : '#334155',
                      fontWeight: resultTab === 'CREATED' ? 700 : 500,
                      fontSize: 12.5,
                      cursor: 'pointer',
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 6,
                    }}
                  >
                    <span>Thuốc tạo mới</span>
                    <span
                      style={{
                        background: resultTab === 'CREATED' ? 'rgba(255,255,255,0.25)' : '#dcfce7',
                        color: resultTab === 'CREATED' ? '#ffffff' : '#15803d',
                        borderRadius: 999,
                        padding: '1px 7px',
                        fontSize: 11,
                        fontWeight: 700,
                      }}
                    >
                      {resultCounts.created}
                    </span>
                  </button>

                  <button
                    type="button"
                    onClick={() => setResultTab('UPDATED')}
                    style={{
                      padding: '6px 12px',
                      borderRadius: 6,
                      border: resultTab === 'UPDATED' ? '1px solid #2563eb' : '1px solid #cbd5e1',
                      background: resultTab === 'UPDATED' ? '#2563eb' : '#ffffff',
                      color: resultTab === 'UPDATED' ? '#ffffff' : '#334155',
                      fontWeight: resultTab === 'UPDATED' ? 700 : 500,
                      fontSize: 12.5,
                      cursor: 'pointer',
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 6,
                    }}
                  >
                    <span>Đã cập nhật lô & giá</span>
                    <span
                      style={{
                        background: resultTab === 'UPDATED' ? 'rgba(255,255,255,0.25)' : '#dbeafe',
                        color: resultTab === 'UPDATED' ? '#ffffff' : '#1d4ed8',
                        borderRadius: 999,
                        padding: '1px 7px',
                        fontSize: 11,
                        fontWeight: 700,
                      }}
                    >
                      {resultCounts.updated}
                    </span>
                  </button>
                </div>

                {/* Search */}
                <div style={{ position: 'relative', minWidth: 260 }}>
                  <Search
                    size={14}
                    style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: '#94a3b8' }}
                  />
                  <input
                    type="text"
                    placeholder="Tìm tên thuốc, SĐK, số lô..."
                    value={resultSearch}
                    onChange={(e) => setResultSearch(e.target.value)}
                    style={{
                      width: '100%',
                      padding: '6px 28px 6px 30px',
                      borderRadius: 6,
                      border: '1px solid #cbd5e1',
                      fontSize: 12.5,
                      background: '#ffffff',
                    }}
                  />
                  {resultSearch && (
                    <button
                      type="button"
                      onClick={() => setResultSearch('')}
                      style={{
                        position: 'absolute',
                        right: 8,
                        top: '50%',
                        transform: 'translateY(-50%)',
                        background: 'none',
                        border: 'none',
                        cursor: 'pointer',
                        color: '#94a3b8',
                        padding: 2,
                      }}
                    >
                      <X size={13} />
                    </button>
                  )}
                </div>
              </div>

              {/* Table with max height & sticky header */}
              <div
                style={{
                  overflowX: 'auto',
                  maxHeight: '480px',
                  overflowY: 'auto',
                  border: '1px solid #e2e8f0',
                  borderTopLeftRadius: 8,
                  borderTopRightRadius: 8,
                  position: 'relative',
                }}
              >
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12.5 }}>
                  <thead style={{ position: 'sticky', top: 0, zIndex: 5, background: '#f8fafc', boxShadow: '0 1px 2px rgba(0,0,0,0.06)' }}>
                    <tr style={{ borderBottom: '1px solid #e2e8f0', color: '#475569', textAlign: 'left' }}>
                      <th style={{ padding: '8px 12px' }}>Dòng</th>
                      <th style={{ padding: '8px 12px' }}>Tên thuốc</th>
                      <th style={{ padding: '8px 12px' }}>Số đăng ký</th>
                      <th style={{ padding: '8px 12px' }}>Số lô</th>
                      <th style={{ padding: '8px 12px' }}>Hạn dùng</th>
                      <th style={{ padding: '8px 12px', textAlign: 'right' }}>SL nhập</th>
                      <th style={{ padding: '8px 12px', textAlign: 'right' }}>Giá bán</th>
                      <th style={{ padding: '8px 12px', textAlign: 'center' }}>Trạng thái</th>
                    </tr>
                  </thead>
                  <tbody>
                    {paginatedResultItems.length === 0 ? (
                      <tr>
                        <td colSpan={8} style={{ textAlign: 'center', padding: '36px 16px', color: '#64748b' }}>
                          Không có thuốc nào phù hợp với bộ lọc hiện tại.
                        </td>
                      </tr>
                    ) : (
                      paginatedResultItems.map((it, idx) => (
                        <tr key={idx} style={{ borderBottom: '1px solid #f1f5f9' }}>
                          <td style={{ padding: '8px 12px', color: '#64748b' }}>#{it.row}</td>
                          <td style={{ padding: '8px 12px', fontWeight: 700, color: '#0f172a' }}>{it.name}</td>
                          <td style={{ padding: '8px 12px' }}>
                            <code style={{ fontFamily: 'monospace', color: '#0369a1' }}>
                              {it.registration_number || '—'}
                            </code>
                          </td>
                          <td style={{ padding: '8px 12px', fontFamily: 'monospace' }}>
                            {it.batch_number || batchNumber}
                          </td>
                          <td style={{ padding: '8px 12px', color: '#047857', fontWeight: 600 }}>
                            {it.expiry_date || expiryDate}
                          </td>
                          <td style={{ padding: '8px 12px', textAlign: 'right', fontWeight: 700, color: '#0f172a' }}>
                            {(it.quantity || initialQuantity).toLocaleString('vi-VN')}
                          </td>
                          <td style={{ padding: '8px 12px', textAlign: 'right', color: '#059669', fontWeight: 600 }}>
                            {it.price ? `${it.price.toLocaleString('vi-VN')} đ` : '—'}
                          </td>
                          <td style={{ padding: '8px 12px', textAlign: 'center' }}>
                            {it.status === 'CREATED' && (
                              <span style={{ background: '#dcfce7', color: '#15803d', padding: '3px 8px', borderRadius: 4, fontWeight: 700, fontSize: 11 }}>
                                Đã tạo mới
                              </span>
                            )}
                            {it.status === 'UPDATED' && (
                              <span style={{ background: '#dbeafe', color: '#1d4ed8', padding: '3px 8px', borderRadius: 4, fontWeight: 700, fontSize: 11 }}>
                                Đã cập nhật
                              </span>
                            )}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>

              {/* Result Pagination Bar */}
              <PaginationBar
                currentPage={resultPage}
                totalPages={totalResultPages}
                pageSize={resultPageSize}
                totalItems={resultCounts.all}
                filteredCount={filteredResultItems.length}
                onPageChange={setResultPage}
                onPageSizeChange={(sz) => {
                  setResultPageSize(sz)
                  setResultPage(1)
                }}
              />
            </div>
          )}
        </div>
      )}

      {/* Guide section for recognized columns */}
      <section
        className="panel"
        style={{
          marginTop: 28,
          background: '#ffffff',
          borderRadius: 12,
          border: '1px solid #e2e8f0',
          padding: '20px 24px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
          <FileSpreadsheet size={18} color="#0284c7" />
          <h3 style={{ margin: 0, fontSize: 15, fontWeight: 750, color: '#0f172a' }}>
            Quy Chuẩn Cột Nhận Diện Từ Tệp Excel / CSV
          </h3>
        </div>
        <p style={{ fontSize: 13, color: '#64748b', margin: '0 0 14px' }}>
          Hệ thống tự động quét và đối chiếu linh hoạt tiêu đề các cột trong file, không phân biệt chữ hoa, chữ thường hay dấu tiếng Việt:
        </p>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {RECOGNIZED_COLUMNS.map((col) => (
            <code
              key={col}
              style={{
                padding: '5px 10px',
                borderRadius: 6,
                background: '#f1f5f9',
                color: '#334155',
                fontSize: 12,
                fontWeight: 600,
                border: '1px solid #e2e8f0',
              }}
            >
              {col}
            </code>
          ))}
        </div>
      </section>
    </div>
  )
}
