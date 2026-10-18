import { api } from './api'

export interface LiveChatMessageItem {
  id: number
  session_id: number
  sender_type: 'CUSTOMER' | 'STAFF' | 'SYSTEM'
  sender_name: string
  sender_role_title?: string
  content: string
  attachment_url?: string
  attachment_type?: string
  client_msg_id?: string
  created_at: string
}

export interface LiveChatSessionItem {
  id: number
  session_code: string
  customer_name: string
  customer_email?: string
  customer_phone?: string
  customer_id?: number
  assigned_staff_id?: number
  assigned_staff_name?: string
  assigned_staff_title?: string
  status: 'WAITING' | 'ACTIVE' | 'CLOSED'
  subject?: string
  initial_context?: string
  rating?: number
  feedback?: string
  created_at: string
  updated_at: string
  closed_at?: string
  last_message_at: string
  messages?: LiveChatMessageItem[]
}

export interface StaffInfo {
  id: number
  full_name: string
  email: string
  role: string
  role_title: string
}

export interface SessionListResponse {
  items: LiveChatSessionItem[]
  total: number
  page: number
  page_size: number
  waiting_count: number
  my_active_count: number
}

export const liveChatService = {
  // 1. Lấy danh sách phiên chat theo bộ lọc
  getStaffSessions: (statusFilter = 'ALL', page = 1, pageSize = 30, search = '') => {
    const params = new URLSearchParams({
      page: String(page),
      page_size: String(pageSize),
    })
    if (statusFilter && statusFilter !== 'ALL') params.append('status_filter', statusFilter)
    if (search.trim()) params.append('search', search.trim())

    return api<SessionListResponse>(`/live-chat/staff/sessions?${params.toString()}`)
  },

  // 2. Lấy chi tiết phiên chat và lịch sử
  getSessionDetail: (sessionCode: string) => {
    return api<LiveChatSessionItem>(`/live-chat/sessions/${sessionCode}`)
  },

  // 3. Nhân viên tiếp nhận ca chat
  claimSession: (sessionCode: string) => {
    return api<LiveChatSessionItem>(`/live-chat/staff/sessions/${sessionCode}/claim`, {
      method: 'POST',
    })
  },

  // 4. Phân công ca chat cho nhân viên khác
  assignSession: (sessionCode: string, staffId: number) => {
    return api<LiveChatSessionItem>(`/live-chat/staff/sessions/${sessionCode}/assign`, {
      method: 'POST',
      body: JSON.stringify({ staff_id: staffId }),
    })
  },

  // 5. Gửi tin nhắn trả lời khách hàng
  sendMessage: (
    sessionCode: string,
    content: string,
    attachmentUrl?: string,
    attachmentType?: string,
    clientMsgId?: string
  ) => {
    return api<LiveChatMessageItem>(`/live-chat/staff/sessions/${sessionCode}/messages`, {
      method: 'POST',
      body: JSON.stringify({
        content,
        attachment_url: attachmentUrl,
        attachment_type: attachmentType,
        client_msg_id: clientMsgId,
      }),
    })
  },

  // 6. Kết thúc ca chat
  closeSession: (sessionCode: string) => {
    return api<{ status: string; message: string }>(`/live-chat/staff/sessions/${sessionCode}/close`, {
      method: 'POST',
    })
  },

  // 7. Lấy danh sách nhân viên để phân công
  getStaffList: () => {
    return api<StaffInfo[]>('/live-chat/staff/staff-list')
  },

  // 8. Tải ảnh đính kèm
  uploadAttachment: (file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return api<{ url: string; content_type: string; filename: string; size: number }>('/live-chat/upload', {
      method: 'POST',
      body: formData,
    })
  },
}
