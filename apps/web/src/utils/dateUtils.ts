/**
 * PharmaTrust Data Hub - Vietnam Time & Date Utilities
 * Đồng bộ thời gian chuẩn GMT+7 (Asia/Ho_Chi_Minh)
 */

export function parseUTCDate(dateStr: string | Date | null | undefined): Date | null {
  if (!dateStr) return null;
  if (dateStr instanceof Date) return isNaN(dateStr.getTime()) ? null : dateStr;

  let s = String(dateStr).trim();
  if (!s) return null;

  // Nếu là dạng SQLite datetime không có timezone: "2026-10-11 17:02:57" hoặc "2026-10-11T17:02:57"
  // Bổ sung 'Z' để browser hiểu chính xác đây là mốc giờ UTC từ máy chủ
  if (/^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(\.\d+)?$/.test(s)) {
    s = s.replace(' ', 'T') + 'Z';
  }

  const d = new Date(s);
  return isNaN(d.getTime()) ? null : d;
}

/**
 * Định dạng Ngày Giờ chuẩn Việt Nam: HH:mm:ss DD/MM/YYYY (24h)
 */
export function formatDateTimeVN(dateStr: string | Date | null | undefined): string {
  const d = parseUTCDate(dateStr);
  if (!d) return '-';

  return new Intl.DateTimeFormat('vi-VN', {
    timeZone: 'Asia/Ho_Chi_Minh',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour12: false,
  }).format(d);
}

/**
 * Định dạng Ngày chuẩn Việt Nam: DD/MM/YYYY
 */
export function formatDateVN(dateStr: string | Date | null | undefined): string {
  const d = parseUTCDate(dateStr);
  if (!d) return '-';

  return new Intl.DateTimeFormat('vi-VN', {
    timeZone: 'Asia/Ho_Chi_Minh',
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  }).format(d);
}

/**
 * Định dạng Giờ chuẩn Việt Nam: HH:mm:ss
 */
export function formatTimeVN(dateStr: string | Date | null | undefined): string {
  const d = parseUTCDate(dateStr);
  if (!d) return '-';

  return new Intl.DateTimeFormat('vi-VN', {
    timeZone: 'Asia/Ho_Chi_Minh',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).format(d);
}

/**
 * Lấy ngày hôm nay theo chuẩn múi giờ Việt Nam dưới dạng YYYY-MM-DD
 * (Tránh lỗi ngày của UTC toISOString() khi quá 0h đêm)
 */
export function getTodayDateStringVN(): string {
  return new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Ho_Chi_Minh',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(new Date());
}

/**
 * Lấy thông tin chi tiết đồng hồ thời gian thực hiện tại
 */
export function getCurrentVietnamTimeParts(): {
  timeStr: string;
  dateStr: string;
  dayOfWeek: string;
} {
  const now = new Date();
  const timeStr = new Intl.DateTimeFormat('vi-VN', {
    timeZone: 'Asia/Ho_Chi_Minh',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).format(now);

  const dateStr = new Intl.DateTimeFormat('vi-VN', {
    timeZone: 'Asia/Ho_Chi_Minh',
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  }).format(now);

  const dayOfWeek = new Intl.DateTimeFormat('vi-VN', {
    timeZone: 'Asia/Ho_Chi_Minh',
    weekday: 'long',
  }).format(now);

  return { timeStr, dateStr, dayOfWeek };
}
