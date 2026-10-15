import React from 'react'
import type { ConfidenceLabel } from '../types'

export type BadgeTone = 'success' | 'warning' | 'danger' | 'info' | 'neutral'

const labels: Record<string, string> = {
  // Confidence & Verification
  HIGH_OFFICIAL_MATCH: 'Khớp chuẩn',
  REVIEW_REQUIRED: 'Cần kiểm tra',
  INSUFFICIENT_EVIDENCE: 'Chưa đủ chứng cứ',
  BLOCKED: 'Đã tạm khóa',

  // Regulatory / Product Classification
  OTC: 'Không kê đơn (OTC)',
  PRESCRIPTION: 'Kê đơn (Rx)',
  UNKNOWN: 'Chưa xác định',
  ACTIVE: 'Đang hoạt động',
  INACTIVE: 'Ngừng hoạt động',
  RECALLED: 'Thu hồi khẩn cấp',
  QUALITY_VIOLATION: 'Vi phạm chất lượng',
  EXPIRED: 'Đã hết hạn',

  // Severity & Priority
  CRITICAL: 'Nguy cấp',
  HIGH: 'Cao',
  MEDIUM: 'Trung bình',
  LOW: 'Thấp',

  // Task & System Status
  SUCCESS: 'Thành công',
  FAILED: 'Thất bại',
  RUNNING: 'Đang xử lý',
  QUEUED: 'Đang chờ',
  PARTIAL: 'Một phần',

  // Order Lifecycles
  PENDING: 'Chờ xác nhận',
  CONFIRMED: 'Đã xác nhận',
  PROCESSING: 'Đang đóng gói',
  SHIPPING: 'Đang giao hàng',
  COMPLETED: 'Đã hoàn tất',
  DELIVERED: 'Đã giao thành công',
  CANCELLED: 'Đã hủy',

  // Payment Status
  PAID: 'Đã thanh toán',
  UNPAID: 'Chưa thanh toán',
  REFUNDED: 'Đã hoàn tiền',

  // Extraction & Match
  EXTRACTED: 'Mới thu thập',
  MATCHED: 'Đã ghép thuốc',
  REJECTED: 'Đã từ chối',
  APPROVED: 'Đã phê duyệt',
  RESOLVED: 'Đã giải quyết',
  DISMISSED: 'Đã bỏ qua',
  OPEN: 'Chờ xử lý',

  // Publishing
  PUBLISHED: 'Đang bán',
  DRAFT: 'Bản nháp',
  ARCHIVED: 'Lưu trữ',
  MANUAL_REVIEW: 'Duyệt thủ công',
  AUTO_PUBLISH_VALID: 'Tự động xuất bản',

  // Inventory & Batches
  NORMAL: 'Bình thường',
  GOOD: 'Đạt chuẩn',
  LOW_STOCK: 'Sắp hết hàng',
  OUT_OF_STOCK: 'Hết hàng',
  NEAR_EXPIRY: 'Cận hạn dùng',
  QUARANTINED: 'Biệt trữ / Cách ly',

  // Authorities
  REGULATORY: 'Cục Quản lý Dược',
  MANUFACTURER: 'Nhà sản xuất',
  RETAILER: 'Nhà thuốc bán lẻ',
  APPROVED_LEAFLET: 'Hướng dẫn sử dụng',
  MANUAL_UPLOAD: 'Tải tệp thủ công',

  // Conflict types
  STRENGTH_MISMATCH: 'Lệch hàm lượng',
  MANUFACTURER_MISMATCH: 'Khác nhà sản xuất',
  INGREDIENT_MISMATCH: 'Khác hoạt chất',
  DOSAGE_FORM_MISMATCH: 'Khác dạng bào chế',
  FORM_MISMATCH: 'Khác dạng bào chế',

  // Roles
  ADMIN: 'Quản trị viên',
  WAREHOUSE_MANAGER: 'Quản lý kho',
  WAREHOUSE_STAFF: 'Nhân viên kho',
  CUSTOMER: 'Khách hàng',

  // Fulfillment State Machine
  ALLOCATED: 'Đã phân bổ kho',
  WAITING_INTERNAL_TRANSFER: 'Chờ điều chuyển kho',
  TRANSFER_IN_TRANSIT: 'Đang luân chuyển kho',
  CONSOLIDATED: 'Đã gom hàng tại kho',
  PICKING: 'Đang soạn hàng',
  PACKED: 'Đã đóng gói',
}

const toneMap: Record<string, BadgeTone> = {
  // Success (Green)
  HIGH_OFFICIAL_MATCH: 'success',
  ACTIVE: 'success',
  SUCCESS: 'success',
  RESOLVED: 'success',
  COMPLETED: 'success',
  DELIVERED: 'success',
  PAID: 'success',
  PUBLISHED: 'success',
  APPROVED: 'success',
  AUTO_PUBLISH_VALID: 'success',
  GOOD: 'success',
  NORMAL: 'success',
  CONSOLIDATED: 'success',

  // Warning (Amber)
  REVIEW_REQUIRED: 'warning',
  RUNNING: 'warning',
  PARTIAL: 'warning',
  OPEN: 'warning',
  PENDING: 'warning',
  UNPAID: 'warning',
  MEDIUM: 'warning',
  LOW_STOCK: 'warning',
  NEAR_EXPIRY: 'warning',
  MANUAL_REVIEW: 'warning',
  DRAFT: 'warning',
  WAREHOUSE_MANAGER: 'warning',
  WAITING_INTERNAL_TRANSFER: 'warning',

  // Danger (Red)
  BLOCKED: 'danger',
  RECALLED: 'danger',
  QUALITY_VIOLATION: 'danger',
  EXPIRED: 'danger',
  CRITICAL: 'danger',
  HIGH: 'danger',
  FAILED: 'danger',
  CANCELLED: 'danger',
  REJECTED: 'danger',
  OUT_OF_STOCK: 'danger',
  QUARANTINED: 'danger',
  STRENGTH_MISMATCH: 'danger',
  MANUFACTURER_MISMATCH: 'danger',
  INGREDIENT_MISMATCH: 'danger',
  DOSAGE_FORM_MISMATCH: 'danger',
  FORM_MISMATCH: 'danger',

  // Info (Blue/Cyan/Purple)
  CONFIRMED: 'info',
  PROCESSING: 'info',
  SHIPPING: 'info',
  EXTRACTED: 'info',
  MATCHED: 'info',
  PRESCRIPTION: 'info',
  OTC: 'info',
  WAREHOUSE_STAFF: 'info',
  TRANSFER_IN_TRANSIT: 'info',
  PICKING: 'info',
  PACKED: 'info',

  // Neutral (Slate/Gray)
  INSUFFICIENT_EVIDENCE: 'neutral',
  UNKNOWN: 'neutral',
  QUEUED: 'neutral',
  LOW: 'neutral',
  INACTIVE: 'neutral',
  ARCHIVED: 'neutral',
  DISMISSED: 'neutral',
}

export interface StatusBadgeProps {
  value: ConfidenceLabel | string
  tone?: BadgeTone
  showDot?: boolean
  className?: string
  title?: string
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({
  value,
  tone,
  showDot = false,
  className = '',
  title,
}) => {
  const upperValue = String(value || '').toUpperCase()
  const displayTone = tone || toneMap[upperValue] || 'neutral'
  const text = labels[upperValue] || labels[value] || value || 'Không rõ'

  return (
    <span
      className={`admin-badge admin-badge-${displayTone} badge-${String(value).toLowerCase()} ${className}`.trim()}
      title={title || text}
    >
      {showDot && <span className={`admin-badge-dot dot-${displayTone}`} />}
      {text}
    </span>
  )
}
