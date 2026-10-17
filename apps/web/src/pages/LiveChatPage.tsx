import {
  AlertCircle,
  CheckCircle2,
  Clock,
  Headphones,
  Image as ImageIcon,
  Loader2,
  RefreshCw,
  Search,
  Send,
  ShieldCheck,
  User,
  UserCheck,
  UserPlus,
  X,
  XCircle,
  Phone,
  Mail,
  Sparkles,
  Info,
} from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useAuth } from '../services/auth'
import {
  LiveChatMessageItem,
  LiveChatSessionItem,
  StaffInfo,
  liveChatService,
} from '../services/liveChatService'
import { tokenStore } from '../services/api'
import { formatDateTimeVN } from '../utils/dateUtils'

export function LiveChatPage() {
  const { user } = useAuth()
  const [sessions, setSessions] = useState<LiveChatSessionItem[]>([])
  const [selectedSession, setSelectedSession] = useState<LiveChatSessionItem | null>(null)
  const [messages, setMessages] = useState<LiveChatMessageItem[]>([])
  const [statusFilter, setStatusFilter] = useState<'ALL' | 'WAITING' | 'MY_CHATS' | 'ACTIVE' | 'CLOSED'>('WAITING')
  const [searchQuery, setSearchQuery] = useState('')
  const [loading, setLoading] = useState(false)
  const [sending, setSending] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [inputText, setInputText] = useState('')
  const [selectedImage, setSelectedImage] = useState<File | null>(null)
  const [imagePreview, setImagePreview] = useState<string | null>(null)
  const [zoomImageUrl, setZoomImageUrl] = useState<string | null>(null)

  // Counts
  const [waitingCount, setWaitingCount] = useState(0)
  const [myActiveCount, setMyActiveCount] = useState(0)

  // Assign staff modal
  const [showAssignModal, setShowAssignModal] = useState(false)
  const [staffList, setStaffList] = useState<StaffInfo[]>([])
  const [selectedStaffId, setSelectedStaffId] = useState<number | null>(null)

  const messagesEndRef = useRef<HTMLDivElement | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const fileInputRef = useRef<HTMLInputElement | null>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  // 1. Tải danh sách các cuộc trò chuyện
  const fetchSessions = async (keepSelection = true) => {
    setLoading(true)
    try {
      const res = await liveChatService.getStaffSessions(statusFilter, 1, 50, searchQuery)
      setSessions(res.items || [])
      setWaitingCount(res.waiting_count || 0)
      setMyActiveCount(res.my_active_count || 0)

      if (keepSelection && selectedSession) {
        const updated = res.items.find((s) => s.session_code === selectedSession.session_code)
        if (updated) setSelectedSession(updated)
      } else if (!keepSelection && res.items.length > 0) {
        handleSelectSession(res.items[0])
      }
    } catch (err: any) {
      console.error('Lỗi tải danh sách phiên chat:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchSessions(false)
  }, [statusFilter, searchQuery])

  // 2. Chọn một phiên chat để xem chi tiết
  const handleSelectSession = async (session: LiveChatSessionItem) => {
    setSelectedSession(session)
    try {
      const detail = await liveChatService.getSessionDetail(session.session_code)
      setSelectedSession(detail)
      setMessages(detail.messages || [])
    } catch {
      setMessages([])
    }
  }

  // 3. Kết nối Realtime WebSocket cho Staff
  useEffect(() => {
    const token = tokenStore.get()
    if (!token) return

    const wsUrl = `ws://127.0.0.1:8000/api/v1/live-chat/ws/staff?token=${token}`
    let socket: WebSocket

    try {
      socket = new WebSocket(wsUrl)
      wsRef.current = socket

      socket.onopen = () => {
        // Connected
      }

      socket.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data)

          if (payload.type === 'NEW_MESSAGE') {
            const incoming: LiveChatMessageItem = payload.message
            // Cập nhật messages nếu phiên đang được chọn
            if (selectedSession && incoming.session_id === selectedSession.id) {
              setMessages((prev) => {
                if (prev.some((m) => m.id === incoming.id)) return prev
                return [...prev, incoming]
              })
            }
            // Cập nhật thời gian last_message_at trong danh sách sessions
            setSessions((prev) =>
              prev.map((s) =>
                s.id === incoming.session_id
                  ? { ...s, last_message_at: incoming.created_at }
                  : s
              )
            )
          } else if (payload.type === 'NEW_SESSION') {
            // Có phiên mới -> cập nhật danh sách và badge
            fetchSessions(true)
          } else if (payload.type === 'SESSION_CLAIMED' || payload.type === 'SESSION_ASSIGNED') {
            fetchSessions(true)
          } else if (payload.type === 'SESSION_CLOSED') {
            fetchSessions(true)
          }
        } catch (e) {
          console.warn('Staff WS error:', e)
        }
      }

      socket.onclose = () => {
        // Socket closed
      }
    } catch {
      // WS connection fallback
    }

    return () => {
      if (socket && socket.readyState === WebSocket.OPEN) {
        socket.close()
      }
    }
  }, [selectedSession?.id])

  // 4. Tiếp nhận cuộc trò chuyện (Claim)
  const handleClaimSession = async () => {
    if (!selectedSession) return
    try {
      const updated = await liveChatService.claimSession(selectedSession.session_code)
      setSelectedSession(updated)
      setMessages(updated.messages || [])
      fetchSessions(true)
    } catch (err: any) {
      alert(err.message || 'Không thể tiếp nhận cuộc trò chuyện')
    }
  }

  // 5. Phân công ca chat cho nhân viên khác
  const handleOpenAssignModal = async () => {
    try {
      const list = await liveChatService.getStaffList()
      setStaffList(list)
      setSelectedStaffId(list[0]?.id || null)
      setShowAssignModal(true)
    } catch (err: any) {
      alert(err.message || 'Không thể tải danh sách nhân viên')
    }
  }

  const handleConfirmAssign = async () => {
    if (!selectedSession || !selectedStaffId) return
    try {
      const updated = await liveChatService.assignSession(selectedSession.session_code, selectedStaffId)
      setSelectedSession(updated)
      setMessages(updated.messages || [])
      setShowAssignModal(false)
      fetchSessions(true)
    } catch (err: any) {
      alert(err.message || 'Lỗi khi phân công ca')
    }
  }

  // 6. Gửi tin nhắn trả lời khách hàng
  const handleSendMessage = async (e?: React.FormEvent) => {
    if (e) e.preventDefault()
    const text = inputText.trim()
    if ((!text && !selectedImage) || sending || !selectedSession) return

    setSending(true)
    let uploadedUrl: string | undefined = undefined
    let uploadedType: string | undefined = undefined

    // Upload ảnh nếu có
    if (selectedImage) {
      setUploading(true)
      try {
        const uploadRes = await liveChatService.uploadAttachment(selectedImage)
        uploadedUrl = `http://127.0.0.1:8000${uploadRes.url}`
        uploadedType = uploadRes.content_type
      } catch (err: any) {
        alert(err.message || 'Không thể tải ảnh lên')
        setSending(false)
        setUploading(false)
        return
      } finally {
        setUploading(false)
      }
    }

    const clientMsgId = `staff-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`

    try {
      const newMsg = await liveChatService.sendMessage(
        selectedSession.session_code,
        text || '(Hình ảnh đính kèm)',
        uploadedUrl,
        uploadedType,
        clientMsgId
      )

      setMessages((prev) => {
        if (prev.some((m) => m.id === newMsg.id)) return prev
        return [...prev, newMsg]
      })

      setInputText('')
      setSelectedImage(null)
      setImagePreview(null)
      fetchSessions(true)
    } catch (err: any) {
      alert(err.message || 'Không thể gửi tin nhắn')
    } finally {
      setSending(false)
    }
  }

  // 7. Kết thúc cuộc trò chuyện
  const handleCloseSession = async () => {
    if (!selectedSession) return
    if (!window.confirm(`Xác nhận hoàn thành và kết thúc phiên chat [${selectedSession.session_code}]?`)) return

    try {
      await liveChatService.closeSession(selectedSession.session_code)
      fetchSessions(true)
      const detail = await liveChatService.getSessionDetail(selectedSession.session_code)
      setSelectedSession(detail)
      setMessages(detail.messages || [])
    } catch (err: any) {
      alert(err.message || 'Không thể kết thúc phiên')
    }
  }

  // 8. Chọn ảnh đính kèm
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    if (!file.type.startsWith('image/')) {
      alert('Vui lòng chọn tệp hình ảnh (JPG, PNG, WEBP)')
      return
    }
    if (file.size > 5 * 1024 * 1024) {
      alert('Dung lượng tệp tối đa là 5MB')
      return
    }
    setSelectedImage(file)
    const reader = new FileReader()
    reader.onload = () => setImagePreview(reader.result as string)
    reader.readAsDataURL(file)
  }

  return (
    <div className="flex flex-col h-[calc(100vh-80px)] p-4 bg-slate-50 overflow-hidden">
      {/* Header Trang */}
      <div className="flex items-center justify-between pb-3 border-b border-slate-200">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-brand-blue-600 text-white flex items-center justify-center shadow-xs">
            <Headphones className="w-5 h-5" />
          </div>
          <div>
            <h1 className="text-xl font-black text-slate-800 tracking-tight flex items-center gap-2">
              Tư Vấn Khách Hàng Trực Tuyến (Live Chat)
            </h1>
            <p className="text-xs text-slate-500">
              Kênh hỗ trợ người thật giữa Khách hàng và Dược sĩ / Nhân viên chăm sóc khách hàng
            </p>
          </div>
        </div>

        <button
          type="button"
          onClick={() => fetchSessions(true)}
          disabled={loading}
          className="px-3 py-1.5 rounded-xl border border-slate-200 hover:bg-white text-slate-700 text-xs font-bold flex items-center gap-1.5 shadow-2xs transition-colors"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          <span>Làm mới</span>
        </button>
      </div>

      {/* Nội dung chính: 2 Cột */}
      <div className="flex-1 flex gap-4 mt-3 overflow-hidden">
        {/* CỘT TRÁI: DANH SÁCH CUỘC TRÒ CHUYỆN */}
        <div className="w-80 lg:w-96 bg-white rounded-2xl border border-slate-200/90 shadow-xs flex flex-col overflow-hidden shrink-0">
          {/* Tabs bộ lọc */}
          <div className="p-2 border-b border-slate-100 flex items-center gap-1 overflow-x-auto scrollbar-none text-xs">
            <button
              type="button"
              onClick={() => setStatusFilter('WAITING')}
              className={`px-2.5 py-1.5 rounded-xl font-bold flex items-center gap-1.5 transition-colors shrink-0 ${
                statusFilter === 'WAITING'
                  ? 'bg-amber-500 text-white shadow-2xs'
                  : 'text-slate-600 hover:bg-slate-100'
              }`}
            >
              <span>Chờ tiếp nhận</span>
              {waitingCount > 0 && (
                <span className="px-1.5 py-0.2 bg-white text-amber-600 rounded-full text-[10px] font-black">
                  {waitingCount}
                </span>
              )}
            </button>

            <button
              type="button"
              onClick={() => setStatusFilter('MY_CHATS')}
              className={`px-2.5 py-1.5 rounded-xl font-bold flex items-center gap-1.5 transition-colors shrink-0 ${
                statusFilter === 'MY_CHATS'
                  ? 'bg-brand-blue-600 text-white shadow-2xs'
                  : 'text-slate-600 hover:bg-slate-100'
              }`}
            >
              <span>Ca của tôi</span>
              {myActiveCount > 0 && (
                <span className="px-1.5 py-0.2 bg-white text-brand-blue-600 rounded-full text-[10px] font-black">
                  {myActiveCount}
                </span>
              )}
            </button>

            <button
              type="button"
              onClick={() => setStatusFilter('ACTIVE')}
              className={`px-2.5 py-1.5 rounded-xl font-bold transition-colors shrink-0 ${
                statusFilter === 'ACTIVE'
                  ? 'bg-teal-600 text-white shadow-2xs'
                  : 'text-slate-600 hover:bg-slate-100'
              }`}
            >
              Đang chat
            </button>

            <button
              type="button"
              onClick={() => setStatusFilter('CLOSED')}
              className={`px-2.5 py-1.5 rounded-xl font-bold transition-colors shrink-0 ${
                statusFilter === 'CLOSED'
                  ? 'bg-slate-700 text-white shadow-2xs'
                  : 'text-slate-600 hover:bg-slate-100'
              }`}
            >
              Đã xong
            </button>

            <button
              type="button"
              onClick={() => setStatusFilter('ALL')}
              className={`px-2.5 py-1.5 rounded-xl font-bold transition-colors shrink-0 ${
                statusFilter === 'ALL'
                  ? 'bg-slate-800 text-white shadow-2xs'
                  : 'text-slate-600 hover:bg-slate-100'
              }`}
            >
              Tất cả
            </button>
          </div>

          {/* Ô tìm kiếm */}
          <div className="p-2.5 border-b border-slate-100">
            <div className="relative">
              <Search className="w-3.5 h-3.5 absolute left-3 top-2.5 text-slate-400" />
              <input
                type="text"
                placeholder="Tìm mã phiên, tên, số điện thoại..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-8 pr-3 py-1.5 text-xs border border-slate-200 rounded-xl focus:outline-none focus:ring-1 focus:ring-brand-blue-500"
              />
            </div>
          </div>

          {/* Danh sách các phiên */}
          <div className="flex-1 overflow-y-auto divide-y divide-slate-100">
            {sessions.length === 0 ? (
              <div className="p-8 text-center text-xs text-slate-400">
                Không có cuộc trò chuyện nào trong mục này.
              </div>
            ) : (
              sessions.map((s) => {
                const isSelected = selectedSession?.session_code === s.session_code
                return (
                  <div
                    key={s.id}
                    onClick={() => handleSelectSession(s)}
                    className={`p-3 cursor-pointer transition-all hover:bg-slate-50 flex items-start justify-between gap-2 ${
                      isSelected ? 'bg-brand-blue-50/70 border-l-4 border-brand-blue-600' : ''
                    }`}
                  >
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-1.5">
                        <span className="font-extrabold text-xs text-slate-800 truncate">
                          {s.customer_name}
                        </span>
                        {s.status === 'WAITING' ? (
                          <span className="px-1.5 py-0.2 bg-amber-100 text-amber-800 rounded text-[9px] font-bold">
                            Chờ nhận
                          </span>
                        ) : s.status === 'ACTIVE' ? (
                          <span className="px-1.5 py-0.2 bg-emerald-100 text-emerald-800 rounded text-[9px] font-bold">
                            Đang chat
                          </span>
                        ) : (
                          <span className="px-1.5 py-0.2 bg-slate-100 text-slate-600 rounded text-[9px] font-bold">
                            Đã đóng
                          </span>
                        )}
                      </div>

                      <p className="text-[11px] text-slate-500 truncate mt-0.5">
                        {s.subject || 'Tư vấn sức khỏe'}
                      </p>

                      <div className="flex items-center gap-2 mt-1.5 text-[10px] text-slate-400">
                        <span className="font-mono text-slate-500">{s.session_code}</span>
                        <span>•</span>
                        <span>{formatDateTimeVN(s.last_message_at || s.created_at)}</span>
                      </div>
                    </div>

                    {s.assigned_staff_name && (
                      <span className="text-[10px] text-brand-blue-700 bg-brand-blue-50 px-1.5 py-0.5 rounded-md font-semibold truncate max-w-[90px]">
                        {s.assigned_staff_name.split(' ').pop()}
                      </span>
                    )}
                  </div>
                )
              })
            )}
          </div>
        </div>

        {/* CỘT PHẢI: KHUNG CHAT CHI TIẾT */}
        <div className="flex-1 bg-white rounded-2xl border border-slate-200/90 shadow-xs flex flex-col overflow-hidden">
          {selectedSession ? (
            <>
              {/* Header của cuộc trò chuyện được chọn */}
              <div className="p-3.5 border-b border-slate-200 flex items-center justify-between bg-slate-50/70 shrink-0">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-full bg-gradient-to-tr from-brand-blue-600 to-teal-500 text-white flex items-center justify-center font-bold text-sm shadow-xs">
                    {selectedSession.customer_name.slice(0, 1).toUpperCase()}
                  </div>

                  <div>
                    <div className="flex items-center gap-2">
                      <h2 className="text-sm font-extrabold text-slate-900">
                        {selectedSession.customer_name}
                      </h2>
                      <span className="font-mono text-xs text-slate-500">
                        ({selectedSession.session_code})
                      </span>
                    </div>

                    <div className="flex items-center gap-3 text-xs text-slate-500 mt-0.5">
                      {selectedSession.customer_phone && (
                        <span className="flex items-center gap-1 text-[11px]">
                          <Phone className="w-3 h-3 text-slate-400" />
                          {selectedSession.customer_phone}
                        </span>
                      )}
                      {selectedSession.customer_email && (
                        <span className="flex items-center gap-1 text-[11px]">
                          <Mail className="w-3 h-3 text-slate-400" />
                          {selectedSession.customer_email}
                        </span>
                      )}
                      <span className="text-[11px] text-slate-400">
                        Bắt đầu: {formatDateTimeVN(selectedSession.created_at)}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Các nút hành động quản lý ca */}
                <div className="flex items-center gap-2">
                  {/* Nếu ca chưa có người nhận -> Nút Tiếp nhận */}
                  {selectedSession.status !== 'CLOSED' && !selectedSession.assigned_staff_id && (
                    <button
                      type="button"
                      onClick={handleClaimSession}
                      className="px-3 py-1.5 rounded-xl bg-amber-500 hover:bg-amber-600 text-white text-xs font-bold flex items-center gap-1.5 shadow-xs transition-colors"
                    >
                      <UserCheck className="w-4 h-4" />
                      <span>Tiếp nhận ca</span>
                    </button>
                  )}

                  {/* Nút phân công ca */}
                  {selectedSession.status !== 'CLOSED' && (
                    <button
                      type="button"
                      onClick={handleOpenAssignModal}
                      className="px-3 py-1.5 rounded-xl border border-slate-200 hover:bg-slate-100 text-slate-700 text-xs font-semibold flex items-center gap-1.5 transition-colors"
                    >
                      <UserPlus className="w-3.5 h-3.5 text-slate-500" />
                      <span>
                        {selectedSession.assigned_staff_name
                          ? `Giao: ${selectedSession.assigned_staff_name}`
                          : 'Phân công'}
                      </span>
                    </button>
                  )}

                  {/* Nút kết thúc ca */}
                  {selectedSession.status !== 'CLOSED' && (
                    <button
                      type="button"
                      onClick={handleCloseSession}
                      className="px-3 py-1.5 rounded-xl border border-rose-200 text-rose-600 hover:bg-rose-50 text-xs font-bold transition-colors"
                    >
                      Kết thúc ca
                    </button>
                  )}
                </div>
              </div>

              {/* Ngữ cảnh tóm tắt từ Trợ lý AI (nếu có) */}
              {selectedSession.initial_context && (
                <div className="mx-4 mt-3 p-3 rounded-xl bg-amber-50/80 border border-amber-200 text-xs text-amber-900 flex items-start gap-2 shrink-0">
                  <Sparkles className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                  <div>
                    <strong className="block font-bold mb-0.5">
                      Ngữ cảnh câu hỏi khách đã chia sẻ từ Trợ lý AI:
                    </strong>
                    <p className="text-[11px] font-mono text-amber-800 leading-relaxed whitespace-pre-wrap">
                      {selectedSession.initial_context}
                    </p>
                  </div>
                </div>
              )}

              {/* Khung hiển thị danh sách tin nhắn */}
              <div className="flex-1 p-4 overflow-y-auto space-y-3.5 bg-slate-50/50">
                {messages.map((m, idx) => {
                  const isStaff = m.sender_type === 'STAFF'
                  const isSystem = m.sender_type === 'SYSTEM'

                  if (isSystem) {
                    return (
                      <div key={m.id || idx} className="flex justify-center my-2">
                        <div className="max-w-[80%] px-3 py-1.5 rounded-xl bg-slate-200 text-slate-600 text-xs text-center">
                          {m.content}
                        </div>
                      </div>
                    )
                  }

                  return (
                    <div
                      key={m.id || idx}
                      className={`flex items-end gap-2 ${isStaff ? 'justify-end' : 'justify-start'}`}
                    >
                      {/* Avatar nếu là khách */}
                      {!isStaff && (
                        <div className="w-8 h-8 rounded-full bg-slate-200 text-slate-700 flex items-center justify-center text-xs font-bold shrink-0">
                          {m.sender_name.slice(0, 1).toUpperCase()}
                        </div>
                      )}

                      <div className={`max-w-[70%] flex flex-col ${isStaff ? 'items-end' : 'items-start'}`}>
                        <div className="flex items-center gap-1.5 mb-1 px-1 text-[11px] text-slate-500">
                          <span className="font-bold text-slate-700">{m.sender_name}</span>
                          {m.sender_role_title && (
                            <span className="px-1.5 py-0.2 rounded bg-slate-100 text-[9px] font-semibold">
                              {m.sender_role_title}
                            </span>
                          )}
                          <span>•</span>
                          <span>{formatDateTimeVN(m.created_at)}</span>
                        </div>

                        <div
                          className={`p-3 rounded-2xl text-xs leading-relaxed shadow-2xs break-words ${
                            isStaff
                              ? 'bg-brand-blue-600 text-white rounded-br-xs'
                              : 'bg-white text-slate-800 border border-slate-200 rounded-bl-xs'
                          }`}
                        >
                          {m.attachment_url && (
                            <div className="mb-2 rounded-xl overflow-hidden cursor-pointer">
                              <img
                                src={m.attachment_url}
                                alt="Đính kèm"
                                onClick={() => setZoomImageUrl(m.attachment_url!)}
                                className="max-h-56 w-auto object-cover hover:opacity-95 transition-opacity"
                              />
                            </div>
                          )}

                          <p className="whitespace-pre-wrap">{m.content}</p>
                        </div>
                      </div>

                      {/* Avatar nếu là nhân viên */}
                      {isStaff && (
                        <div className="w-8 h-8 rounded-full bg-brand-blue-700 text-white flex items-center justify-center text-xs font-bold shrink-0 shadow-xs">
                          {m.sender_name.slice(0, 1).toUpperCase()}
                        </div>
                      )}
                    </div>
                  )
                })}
                <div ref={messagesEndRef} />
              </div>

              {/* Preview ảnh đính kèm chuẩn bị gửi */}
              {imagePreview && (
                <div className="px-4 py-2 bg-slate-100 border-t border-slate-200 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <img src={imagePreview} alt="Preview" className="w-12 h-12 object-cover rounded-lg border" />
                    <span className="text-xs text-slate-600 font-medium truncate max-w-xs">
                      {selectedImage?.name}
                    </span>
                  </div>
                  <button
                    type="button"
                    onClick={() => {
                      setSelectedImage(null)
                      setImagePreview(null)
                    }}
                    className="p-1 text-slate-400 hover:text-slate-700 rounded"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
              )}

              {/* Ô gõ tin nhắn trả lời */}
              {selectedSession.status !== 'CLOSED' ? (
                <form
                  onSubmit={handleSendMessage}
                  className="p-3 border-t border-slate-200 flex items-center gap-2 bg-white shrink-0"
                >
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept="image/jpeg,image/png,image/webp"
                    className="hidden"
                    onChange={handleFileChange}
                  />

                  <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    disabled={sending || uploading}
                    className="p-2 text-slate-500 hover:text-brand-blue-600 hover:bg-slate-100 rounded-xl transition-colors disabled:opacity-50"
                    title="Gửi hình ảnh"
                  >
                    <ImageIcon className="w-5 h-5" />
                  </button>

                  <input
                    type="text"
                    value={inputText}
                    onChange={(e) => setInputText(e.target.value)}
                    disabled={sending}
                    placeholder="Nhập nội dung tư vấn cho khách hàng (nhấn Enter để gửi)..."
                    className="flex-1 px-3.5 py-2 text-xs border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-brand-blue-500"
                  />

                  <button
                    type="submit"
                    disabled={(!inputText.trim() && !selectedImage) || sending}
                    className="px-4 py-2 bg-brand-blue-600 hover:bg-brand-blue-700 text-white rounded-xl text-xs font-bold flex items-center gap-1.5 transition-colors disabled:opacity-50"
                  >
                    {sending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                    <span>Gửi</span>
                  </button>
                </form>
              ) : (
                <div className="p-3 bg-slate-100 border-t border-slate-200 text-center text-xs text-slate-500 font-medium">
                  Cuộc trò chuyện này đã kết thúc. Không thể gửi thêm tin nhắn.
                </div>
              )}
            </>
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center p-8 text-slate-400">
              <Headphones className="w-12 h-12 mb-3 text-slate-300" />
              <p className="text-sm font-bold text-slate-600">Chưa chọn cuộc trò chuyện nào</p>
              <p className="text-xs text-slate-400 mt-1">
                Vui lòng chọn một ca trò chuyện từ danh sách bên trái để tiếp nhận và phản hồi khách hàng.
              </p>
            </div>
          )}
        </div>
      </div>

      {/* MODAL PHÂN CÔNG CA CHO NHÂN VIÊN */}
      {showAssignModal && (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-5 shadow-xl">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <h3 className="font-extrabold text-sm text-slate-800">
                Phân công ca tư vấn cho nhân sự
              </h3>
              <button
                type="button"
                onClick={() => setShowAssignModal(false)}
                className="text-slate-400 hover:text-slate-600"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="py-4">
              <label className="block text-xs font-bold text-slate-700 mb-2">
                Chọn nhân viên / dược sĩ phụ trách:
              </label>
              <select
                value={selectedStaffId || ''}
                onChange={(e) => setSelectedStaffId(Number(e.target.value))}
                className="w-full p-2.5 text-xs border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-brand-blue-500"
              >
                {staffList.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.full_name} ({s.role_title} - {s.email})
                  </option>
                ))}
              </select>
            </div>

            <div className="flex justify-end gap-2 pt-2 border-t border-slate-100">
              <button
                type="button"
                onClick={() => setShowAssignModal(false)}
                className="px-3 py-1.5 rounded-xl border border-slate-200 text-xs font-semibold text-slate-600 hover:bg-slate-50"
              >
                Hủy
              </button>
              <button
                type="button"
                onClick={handleConfirmAssign}
                className="px-4 py-1.5 rounded-xl bg-brand-blue-600 text-white text-xs font-bold hover:bg-brand-blue-700 shadow-xs"
              >
                Xác nhận phân công
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL PHÓNG TO ẢNH */}
      {zoomImageUrl && (
        <div
          className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4 cursor-pointer"
          onClick={() => setZoomImageUrl(null)}
        >
          <div className="relative max-w-full max-h-full">
            <img src={zoomImageUrl} alt="Zoom" className="max-h-[88vh] max-w-[90vw] object-contain rounded-2xl" />
            <button
              type="button"
              className="absolute -top-3 -right-3 w-8 h-8 rounded-full bg-white text-slate-800 flex items-center justify-center shadow-lg"
              onClick={() => setZoomImageUrl(null)}
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
