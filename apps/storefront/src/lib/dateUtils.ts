/**
 * H4CARE Storefront - Vietnam Time & Date Utilities
 * Đồng bộ thời gian chuẩn GMT+7 (Asia/Ho_Chi_Minh)
 */

export function parseUTCDate(dateStr: string | Date | null | undefined): Date | null {
  if (!dateStr) return null;
  if (dateStr instanceof Date) return isNaN(dateStr.getTime()) ? null : dateStr;

  let s = String(dateStr).trim();
  if (!s) return null;

  if (/^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(\.\d+)?$/.test(s)) {
    s = s.replace(' ', 'T') + 'Z';
  }

  const d = new Date(s);
  return isNaN(d.getTime()) ? null : d;
}

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

export function getTodayDateStringVN(): string {
  return new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Ho_Chi_Minh',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(new Date());
}

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
