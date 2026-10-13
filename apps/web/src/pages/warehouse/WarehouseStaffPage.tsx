import { useEffect, useMemo, useState } from 'react'
import {
  Users,
  UserPlus,
  Lock,
  Unlock,
  Mail,
  Phone,
  ShieldCheck,
  X,
  AlertTriangle,
  CheckCircle2,
  UserCheck,
  UserX,
  KeyRound,
  Edit,
  History,
  Copy,
  Check,
  Eye,
  EyeOff,
  Clock,
  Calendar,
  ShieldAlert,
  Search,
  RefreshCw,
} from 'lucide-react'
import { api } from '../../services/api'
import { useAuth } from '../../services/auth'
import type { User, UserActivityLog } from '../../types'

function generateSecureRandomPassword(length = 12): string {
  const uppers = 'ABCDEFGHJKLMNPQRSTUVWXYZ'
  const lowers = 'abcdefghijkmnopqrstuvwxyz'
  const digits = '23456789'
  const specials = '!@#$%^&*_-+='
  const p1 = uppers[Math.floor(Math.random() * uppers.length)]
  const p2 = lowers[Math.floor(Math.random() * lowers.length)]
  const p3 = digits[Math.floor(Math.random() * digits.length)]
  const p4 = specials[Math.floor(Math.random() * specials.length)]
  const all = uppers + lowers + digits + specials
  let rest = ''
  for (let i = 0; i < length - 4; i++) {
    rest += all[Math.floor(Math.random() * all.length)]
  }
  return (p1 + p2 + p3 + p4 + rest).split('').sort(() => 0.5 - Math.random()).join('')
}

function checkPasswordStrength(p: string): { valid: boolean; message: string } {
  if (p.length < 8) return { valid: false, message: 'Mật khẩu phải có tối thiểu 8 ký tự' }
  if (!/[A-Z]/.test(p)) return { valid: false, message: 'Mật khẩu phải chứa ít nhất 1 chữ hoa (A-Z)' }
  if (!/[a-z]/.test(p)) return { valid: false, message: 'Mật khẩu phải chứa ít nhất 1 chữ thường (a-z)' }
  if (!/[0-9]/.test(p)) return { valid: false, message: 'Mật khẩu phải chứa ít nhất 1 chữ số (0-9)' }
  if (!/[^A-Za-z0-9]/.test(p)) return { valid: false, message: 'Mật khẩu phải chứa ít nhất 1 ký tự đặc biệt' }
  return { valid: true, message: '' }
}

export function WarehouseStaffPage() {
  const { user: currentUser } = useAuth()
  const [staffList, setStaffList] = useState<User[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState<'ALL' | 'ACTIVE' | 'INACTIVE'>('ALL')

  // Modals & Drawers
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [editStaff, setEditStaff] = useState<User | null>(null)
  const [resetPwdStaff, setResetPwdStaff] = useState<User | null>(null)
  const [detailStaff, setDetailStaff] = useState<User | null>(null)
  const [activityLogs, setActivityLogs] = useState<UserActivityLog[]>([])
  const [loadingActivity, setLoadingActivity] = useState(false)

  // Single-use Temporary Password Result Modal
  const [tempPasswordResult, setTempPasswordResult] = useState<{
    userEmail: string
    userName: string
    password: string
    title: string
  } | null>(null)
  const [copied, setCopied] = useState(false)

  // Create Form State
  const [createForm, setCreateForm] = useState({
    full_name: '',
    email: '',
    phone: '',
    useRandomPassword: true,
    manualPassword: '',
  })
  const [creating, setCreating] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)

  // Edit Form State
  const [editForm, setEditForm] = useState({
    full_name: '',
    email: '',
    phone: '',
  })
  const [editing, setEditing] = useState(false)
  const [editError, setEditError] = useState<string | null>(null)

  // Reset Password State
  const [resetPwdMode, setResetPwdMode] = useState<'random' | 'manual'>('random')
  const [resetPwdManual, setResetPwdManual] = useState('')
  const [resetPwdLoading, setResetPwdLoading] = useState(false)
  const [resetPwdError, setResetPwdError] = useState<string | null>(null)
  const [showManualPwd, setShowManualPwd] = useState(false)

  const fetchStaff = () => {
    setLoading(true)
    api<User[]>('/users')
      .then((res) => setStaffList(res || []))
      .catch((err) => console.error('Failed to load warehouse staff:', err))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    fetchStaff()
  }, [])

  // Load activity logs when detail drawer opens
  useEffect(() => {
    if (detailStaff) {
      setLoadingActivity(true)
      api<UserActivityLog[]>(`/users/${detailStaff.id}/activity`)
        .then((logs) => setActivityLogs(logs || []))
        .catch((err) => {
          console.error('Failed to load activity logs:', err)
          setActivityLogs([])
        })
        .finally(() => setLoadingActivity(false))
    } else {
      setActivityLogs([])
    }
  }, [detailStaff])

  // Filtered staff list
  const filteredStaff = useMemo(() => {
    return staffList.filter((s) => {
      const matchesStatus =
        statusFilter === 'ALL' ||
        (statusFilter === 'ACTIVE' && s.is_active) ||
        (statusFilter === 'INACTIVE' && !s.is_active)

      const term = search.toLowerCase().trim()
      const matchesSearch =
        !term ||
        s.full_name.toLowerCase().includes(term) ||
        s.email.toLowerCase().includes(term) ||
        (s.phone && s.phone.includes(term))

      return matchesStatus && matchesSearch
    })
  }, [staffList, statusFilter, search])

  const activeCount = staffList.filter((s) => s.is_active).length
  const lockedCount = staffList.filter((s) => !s.is_active).length

  // Toggle status
  const handleToggleStatus = async (staffId: number, currentActive: boolean, staffName: string) => {
    const action = currentActive ? 'khóa' : 'mở khóa'
    if (!window.confirm(`Bạn có chắc chắn muốn ${action} tài khoản nhân viên "${staffName}"?\nPhiên đăng nhập của nhân viên sẽ bị thu hồi ngay lập tức.`)) {
      return
    }

    try {
      const updated = await api<User>(`/users/${staffId}/status`, { method: 'PATCH' })
      setStaffList((prev) => prev.map((s) => (s.id === staffId ? updated : s)))
      if (detailStaff && detailStaff.id === staffId) {
        setDetailStaff(updated)
      }
    } catch (err: any) {
      alert(err?.message || 'Không thể thay đổi trạng thái nhân viên')
    }
  }

  // Create Staff
  const handleCreateStaff = async (e: React.FormEvent) => {
    e.preventDefault()
    setCreateError(null)

    if (!createForm.full_name.trim() || !createForm.email.trim()) {
      setCreateError('Vui lòng điền đầy đủ họ và tên, email đăng nhập')
      return
    }

    let passwordToSend: string | undefined = undefined
    if (createForm.useRandomPassword) {
      passwordToSend = generateSecureRandomPassword(12)
    } else {
      if (!createForm.manualPassword.trim()) {
        setCreateError('Vui lòng nhập mật khẩu tạm thời hoặc chọn tự động tạo ngẫu nhiên')
        return
      }
      const check = checkPasswordStrength(createForm.manualPassword)
      if (!check.valid) {
        setCreateError(check.message)
        return
      }
      passwordToSend = createForm.manualPassword.trim()
    }

    setCreating(true)
    try {
      const payload = {
        full_name: createForm.full_name.trim(),
        email: createForm.email.trim(),
        phone: createForm.phone.trim() || null,
        password: passwordToSend,
        role: 'WAREHOUSE_STAFF',
        warehouse_id: currentUser?.warehouse_id,
        must_change_password: true,
      }

      const res = await api<{ user: User; temporary_password: string; message: string }>('/users', {
        method: 'POST',
        body: JSON.stringify(payload),
      })

      setShowCreateModal(false)
      setCreateForm({
        full_name: '',
        email: '',
        phone: '',
        useRandomPassword: true,
        manualPassword: '',
      })

      fetchStaff()

      // Show temporary password modal ONCE
      setTempPasswordResult({
        userEmail: res.user.email,
        userName: res.user.full_name,
        password: res.temporary_password,
        title: 'Cấp Tài Khoản Nhân Viên Kho Mới Thành Công',
      })
      setCopied(false)
    } catch (err: any) {
      setCreateError(err?.message || 'Không thể tạo tài khoản nhân viên')
    } finally {
      setCreating(false)
    }
  }

  // Open Edit
  const handleOpenEdit = (staff: User) => {
    setEditStaff(staff)
    setEditError(null)
    setEditForm({
      full_name: staff.full_name || '',
      email: staff.email || '',
      phone: staff.phone || '',
    })
  }

  // Submit Edit
  const handleEditSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!editStaff) return
    setEditError(null)

    if (!editForm.full_name.trim() || !editForm.email.trim()) {
      setEditError('Họ tên và email không được để trống')
      return
    }

    setEditing(true)
    try {
      const payload = {
        full_name: editForm.full_name.trim(),
        email: editForm.email.trim(),
        phone: editForm.phone.trim() || null,
      }

      const updated = await api<User>(`/users/${editStaff.id}`, {
        method: 'PATCH',
        body: JSON.stringify(payload),
      })

      setStaffList((prev) => prev.map((s) => (s.id === editStaff.id ? updated : s)))
      if (detailStaff && detailStaff.id === editStaff.id) {
        setDetailStaff(updated)
      }
      setEditStaff(null)
    } catch (err: any) {
      setEditError(err?.message || 'Không thể cập nhật nhân viên')
    } finally {
      setEditing(false)
    }
  }

  // Open Reset Password
  const handleOpenResetPwd = (staff: User) => {
    setResetPwdStaff(staff)
    setResetPwdError(null)
    setResetPwdMode('random')
    setResetPwdManual('')
    setShowManualPwd(false)
  }

  // Submit Reset Password
  const handleResetPwdSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!resetPwdStaff) return
    setResetPwdError(null)

    let pwdToSend: string | undefined = undefined
    if (resetPwdMode === 'manual') {
      if (!resetPwdManual.trim()) {
        setResetPwdError('Vui lòng nhập mật khẩu tạm thời mới')
        return
      }
      const check = checkPasswordStrength(resetPwdManual)
      if (!check.valid) {
        setResetPwdError(check.message)
        return
      }
      pwdToSend = resetPwdManual.trim()
    }

    setResetPwdLoading(true)
    try {
      const payload = pwdToSend ? { new_password: pwdToSend } : {}
      const res = await api<{ message: string; temporary_password: string; must_change_password: boolean }>(
        `/users/${resetPwdStaff.id}/reset-password`,
        {
          method: 'POST',
          body: JSON.stringify(payload),
        }
      )

      const targetName = resetPwdStaff.full_name
      const targetEmail = resetPwdStaff.email
      setResetPwdStaff(null)

      fetchStaff()

      // Show temporary password modal ONCE
      setTempPasswordResult({
        userEmail: targetEmail,
        userName: targetName,
        password: res.temporary_password,
        title: 'Đặt Lại Mật Khẩu Nhân Viên Thành Công',
      })
      setCopied(false)
    } catch (err: any) {
      setResetPwdError(err?.message || 'Đặt lại mật khẩu thất bại')
    } finally {
      setResetPwdLoading(false)
    }
  }

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2500)
    })
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', maxWidth: '1400px', margin: '0 auto' }}>
      {/* Header Banner */}
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
          <div style={{ fontSize: '11px', fontWeight: 800, color: '#047857', textTransform: 'uppercase', letterSpacing: '0.8px' }}>
            QUẢN LÝ NHÂN SỰ CHI NHÁNH KHO
          </div>
          <h1 style={{ margin: '4px 0 0', fontSize: '22px', fontWeight: 900, color: '#0f172a' }}>
            Nhân Viên Trực Thuộc Kho {currentUser?.warehouse_name ? `• ${currentUser.warehouse_name}` : ''}
          </h1>
          <p style={{ margin: '4px 0 0', fontSize: '13px', color: '#64748b' }}>
            Cấp tài khoản nhân viên kho, đặt lại mật khẩu tạm thời, phân công và giám sát trạng thái hoạt động.
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <button
            type="button"
            onClick={fetchStaff}
            disabled={loading}
            style={{
              background: '#f8fafc',
              color: '#334155',
              border: '1px solid #cbd5e1',
              padding: '10px 14px',
              borderRadius: '12px',
              fontSize: '13px',
              fontWeight: 700,
              cursor: 'pointer',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            <RefreshCw size={14} className={loading ? 'spin' : ''} />
            <span>Làm mới</span>
          </button>

          <button
            type="button"
            onClick={() => {
              setCreateError(null)
              setShowCreateModal(true)
            }}
            style={{
              background: 'linear-gradient(135deg, #059669, #047857)',
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
              boxShadow: '0 3px 10px rgba(5, 150, 105, 0.3)',
            }}
          >
            <UserPlus size={16} />
            <span>Thêm Nhân Viên Kho</span>
          </button>
        </div>
      </div>

      {/* KPI Stats Bar */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
          gap: '16px',
        }}
      >
        <div
          style={{
            background: 'white',
            borderRadius: '14px',
            border: '1px solid #e2e8f0',
            padding: '16px 20px',
            display: 'flex',
            alignItems: 'center',
            gap: '14px',
            boxShadow: '0 1px 3px rgba(0,0,0,0.02)',
          }}
        >
          <div
            style={{
              width: '44px',
              height: '44px',
              borderRadius: '12px',
              background: '#f1f5f9',
              color: '#334155',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <Users size={22} />
          </div>
          <div>
            <div style={{ fontSize: '11.5px', fontWeight: 700, color: '#64748b', textTransform: 'uppercase' }}>
              Tổng nhân sự kho
            </div>
            <div style={{ fontSize: '22px', fontWeight: 900, color: '#0f172a' }}>{staffList.length}</div>
          </div>
        </div>

        <div
          style={{
            background: 'white',
            borderRadius: '14px',
            border: '1px solid #e2e8f0',
            padding: '16px 20px',
            display: 'flex',
            alignItems: 'center',
            gap: '14px',
            boxShadow: '0 1px 3px rgba(0,0,0,0.02)',
          }}
        >
          <div
            style={{
              width: '44px',
              height: '44px',
              borderRadius: '12px',
              background: '#ecfdf5',
              color: '#059669',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <UserCheck size={22} />
          </div>
          <div>
            <div style={{ fontSize: '11.5px', fontWeight: 700, color: '#047857', textTransform: 'uppercase' }}>
              Đang hoạt động
            </div>
            <div style={{ fontSize: '22px', fontWeight: 900, color: '#059669' }}>{activeCount}</div>
          </div>
        </div>

        <div
          style={{
            background: 'white',
            borderRadius: '14px',
            border: '1px solid #e2e8f0',
            padding: '16px 20px',
            display: 'flex',
            alignItems: 'center',
            gap: '14px',
            boxShadow: '0 1px 3px rgba(0,0,0,0.02)',
          }}
        >
          <div
            style={{
              width: '44px',
              height: '44px',
              borderRadius: '12px',
              background: '#fff1f2',
              color: '#e11d48',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <UserX size={22} />
          </div>
          <div>
            <div style={{ fontSize: '11.5px', fontWeight: 700, color: '#be123c', textTransform: 'uppercase' }}>
              Đã tạm khóa
            </div>
            <div style={{ fontSize: '22px', fontWeight: 900, color: '#e11d48' }}>{lockedCount}</div>
          </div>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div
        style={{
          background: 'white',
          borderRadius: '14px',
          border: '1px solid #e2e8f0',
          padding: '12px 18px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '12px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flex: 1, minWidth: '240px' }}>
          <Search size={16} style={{ color: '#94a3b8' }} />
          <input
            type="text"
            placeholder="Tìm theo họ tên, email hoặc số điện thoại nhân viên..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            style={{
              width: '100%',
              border: 'none',
              outline: 'none',
              fontSize: '13px',
              color: '#0f172a',
            }}
          />
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as any)}
            style={{
              padding: '6px 12px',
              borderRadius: '8px',
              border: '1px solid #cbd5e1',
              fontSize: '12.5px',
              color: '#334155',
              background: 'white',
            }}
          >
            <option value="ALL">Tất cả trạng thái</option>
            <option value="ACTIVE">Đang hoạt động</option>
            <option value="INACTIVE">Đã khóa</option>
          </select>
        </div>
      </div>

      {/* Staff Cards Grid */}
      {loading ? (
        <div
          style={{
            background: 'white',
            borderRadius: '16px',
            border: '1px solid #e2e8f0',
            padding: '60px 20px',
            textAlign: 'center',
            color: '#94a3b8',
            fontWeight: 700,
          }}
        >
          <RefreshCw size={24} className="spin" style={{ margin: '0 auto 8px', display: 'block' }} />
          Đang tải danh sách nhân sự trực thuộc kho…
        </div>
      ) : filteredStaff.length === 0 ? (
        <div
          style={{
            background: 'white',
            borderRadius: '16px',
            border: '1.5px dashed #cbd5e1',
            padding: '60px 20px',
            textAlign: 'center',
          }}
        >
          <div
            style={{
              width: '56px',
              height: '56px',
              borderRadius: '50%',
              background: '#ecfdf5',
              color: '#059669',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              margin: '0 auto 16px',
            }}
          >
            <Users size={28} />
          </div>
          <h3 style={{ margin: 0, fontSize: '16px', fontWeight: 800, color: '#0f172a' }}>
            Không tìm thấy nhân viên nào phù hợp
          </h3>
          <p style={{ margin: '6px 0 20px', fontSize: '13px', color: '#64748b' }}>
            Hãy bấm nút bên dưới để cấp tài khoản đầu tiên cho nhân viên soạn & đóng gói hàng của kho.
          </p>
          <button
            type="button"
            onClick={() => {
              setCreateError(null)
              setShowCreateModal(true)
            }}
            style={{
              background: '#047857',
              color: 'white',
              padding: '10px 20px',
              borderRadius: '10px',
              fontSize: '13px',
              fontWeight: 700,
              border: 'none',
              cursor: 'pointer',
            }}
          >
            + Cấp Tài Khoản Nhân Viên
          </button>
        </div>
      ) : (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(360px, 1fr))',
            gap: '18px',
          }}
        >
          {filteredStaff.map((staff) => {
            const firstLetter = (staff.full_name || staff.email || 'N').trim().charAt(0).toUpperCase()
            return (
              <div
                key={staff.id}
                style={{
                  background: 'white',
                  borderRadius: '16px',
                  border: staff.is_active ? '1px solid #e2e8f0' : '1px solid #fecaca',
                  padding: '20px',
                  boxShadow: '0 2px 6px rgba(0,0,0,0.03)',
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'space-between',
                  gap: '16px',
                  transition: 'transform 0.15s ease, box-shadow 0.15s ease',
                }}
              >
                {/* Card Top: Avatar, Name & Status */}
                <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '12px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <div
                      style={{
                        width: '46px',
                        height: '46px',
                        borderRadius: '50%',
                        background: staff.is_active
                          ? 'linear-gradient(135deg, #059669, #10b981)'
                          : 'linear-gradient(135deg, #94a3b8, #64748b)',
                        color: 'white',
                        fontWeight: 900,
                        fontSize: '17px',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        flexShrink: 0,
                        boxShadow: staff.is_active ? '0 2px 6px rgba(5, 150, 105, 0.3)' : 'none',
                      }}
                    >
                      {firstLetter}
                    </div>
                    <div>
                      <h3 style={{ margin: 0, fontSize: '15px', fontWeight: 800, color: '#0f172a' }}>
                        {staff.full_name}
                      </h3>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginTop: '3px' }}>
                        <span
                          style={{
                            padding: '2px 8px',
                            borderRadius: '6px',
                            fontSize: '10.5px',
                            fontWeight: 800,
                            background: '#f1f5f9',
                            color: '#475569',
                            textTransform: 'uppercase',
                            letterSpacing: '0.4px',
                          }}
                        >
                          Nhân Viên Kho (STAFF)
                        </span>
                        <span style={{ fontSize: '11px', color: '#94a3b8' }}>ID: #{staff.id}</span>
                      </div>
                    </div>
                  </div>

                  {/* Status Badge */}
                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '4px' }}>
                    <span
                      style={{
                        padding: '4px 10px',
                        borderRadius: '9999px',
                        fontSize: '11px',
                        fontWeight: 800,
                        background: staff.is_active ? '#ecfdf5' : '#fff1f2',
                        color: staff.is_active ? '#047857' : '#be123c',
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '5px',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      <span
                        style={{
                          width: '6px',
                          height: '6px',
                          borderRadius: '50%',
                          background: staff.is_active ? '#059669' : '#e11d48',
                        }}
                      />
                      {staff.is_active ? 'Hoạt động' : 'Tạm khóa'}
                    </span>

                    {staff.must_change_password && (
                      <span
                        style={{
                          fontSize: '10px',
                          fontWeight: 700,
                          color: '#b45309',
                          background: '#fffbeb',
                          padding: '1px 6px',
                          borderRadius: '4px',
                          border: '1px solid #fef3c7',
                        }}
                      >
                        Bắt buộc đổi MK
                      </span>
                    )}
                  </div>
                </div>

                {/* Card Contact Info */}
                <div
                  style={{
                    background: '#f8fafc',
                    borderRadius: '12px',
                    padding: '12px 14px',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '8px',
                    fontSize: '12.5px',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#334155' }}>
                    <Mail size={14} style={{ color: '#059669', flexShrink: 0 }} />
                    <span style={{ fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {staff.email}
                    </span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#334155' }}>
                    <Phone size={14} style={{ color: '#059669', flexShrink: 0 }} />
                    <span style={{ fontWeight: 600 }}>{staff.phone || 'Chưa cập nhật SĐT'}</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#64748b', fontSize: '11.5px', marginTop: '2px' }}>
                    <Calendar size={13} style={{ color: '#94a3b8', flexShrink: 0 }} />
                    <span>
                      Đăng nhập cuối:{' '}
                      {staff.last_login_at
                        ? new Date(staff.last_login_at).toLocaleString('vi-VN')
                        : 'Chưa đăng nhập'}
                    </span>
                  </div>
                </div>

                {/* Card Footer: Action Buttons */}
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    paddingTop: '8px',
                    borderTop: '1px solid #f1f5f9',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <button
                      type="button"
                      onClick={() => setDetailStaff(staff)}
                      style={{
                        padding: '6px 10px',
                        borderRadius: '8px',
                        fontSize: '11.5px',
                        fontWeight: 700,
                        border: '1px solid #cbd5e1',
                        background: '#f8fafc',
                        color: '#475569',
                        cursor: 'pointer',
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '5px',
                      }}
                      title="Xem chi tiết & lịch sử"
                    >
                      <History size={13} /> Lịch sử
                    </button>

                    <button
                      type="button"
                      onClick={() => handleOpenEdit(staff)}
                      style={{
                        padding: '6px 10px',
                        borderRadius: '8px',
                        fontSize: '11.5px',
                        fontWeight: 700,
                        border: '1px solid #cbd5e1',
                        background: '#f8fafc',
                        color: '#475569',
                        cursor: 'pointer',
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '5px',
                      }}
                      title="Sửa thông tin"
                    >
                      <Edit size={13} /> Sửa
                    </button>

                    <button
                      type="button"
                      onClick={() => handleOpenResetPwd(staff)}
                      style={{
                        padding: '6px 10px',
                        borderRadius: '8px',
                        fontSize: '11.5px',
                        fontWeight: 700,
                        border: '1px solid #fef3c7',
                        background: '#fffbeb',
                        color: '#b45309',
                        cursor: 'pointer',
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '5px',
                      }}
                      title="Đặt lại mật khẩu tạm thời"
                    >
                      <KeyRound size={13} /> Đặt lại MK
                    </button>
                  </div>

                  <button
                    type="button"
                    onClick={() => handleToggleStatus(staff.id, staff.is_active, staff.full_name)}
                    style={{
                      padding: '6px 12px',
                      borderRadius: '8px',
                      fontSize: '11.5px',
                      fontWeight: 700,
                      border: staff.is_active ? '1px solid #fecaca' : '1px solid #a7f3d0',
                      background: staff.is_active ? '#fff1f2' : '#ecfdf5',
                      color: staff.is_active ? '#b91c1c' : '#047857',
                      cursor: 'pointer',
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '5px',
                    }}
                  >
                    {staff.is_active ? (
                      <>
                        <Lock size={12} /> Khóa
                      </>
                    ) : (
                      <>
                        <Unlock size={12} /> Mở khóa
                      </>
                    )}
                  </button>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* 1. MODAL CẤP TÀI KHOẢN NHÂN VIÊN MỚI */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-md border border-slate-200 overflow-hidden">
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100 bg-emerald-50">
              <div className="flex items-center gap-2">
                <UserPlus size={18} className="text-emerald-700" />
                <h3 className="font-semibold text-emerald-950 text-base">Cấp Tài Khoản Nhân Viên Kho</h3>
              </div>
              <button
                type="button"
                className="p-1 text-slate-400 hover:text-slate-600 rounded-lg hover:bg-slate-200 transition-colors"
                onClick={() => setShowCreateModal(false)}
              >
                <X size={18} />
              </button>
            </div>

            <form onSubmit={handleCreateStaff} className="p-6 space-y-4">
              <div className="p-3 bg-emerald-50/60 border border-emerald-200 rounded-lg text-xs text-emerald-800">
                Tài khoản mới sẽ trực thuộc <strong>{currentUser?.warehouse_name || 'kho hiện tại'}</strong> với vai trò Nhân Viên Soạn & Đóng Gói (WAREHOUSE_STAFF).
              </div>

              {createError && (
                <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-600 flex items-center gap-2">
                  <AlertTriangle size={16} className="shrink-0" />
                  <span>{createError}</span>
                </div>
              )}

              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                  Họ và tên nhân viên <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  required
                  placeholder="Ví dụ: Lê Hoàng Nam"
                  className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500"
                  value={createForm.full_name}
                  onChange={(e) => setCreateForm({ ...createForm, full_name: e.target.value })}
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                  Email đăng nhập <span className="text-red-500">*</span>
                </label>
                <input
                  type="email"
                  required
                  placeholder="nam.le@pharmatrust.vn"
                  className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500"
                  value={createForm.email}
                  onChange={(e) => setCreateForm({ ...createForm, email: e.target.value })}
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                  Số điện thoại
                </label>
                <input
                  type="tel"
                  placeholder="0987654321"
                  className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500"
                  value={createForm.phone}
                  onChange={(e) => setCreateForm({ ...createForm, phone: e.target.value })}
                />
              </div>

              {/* Password option */}
              <div className="pt-2 border-t border-slate-100">
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-2">
                  Mật khẩu khởi tạo
                </label>
                <div className="space-y-2">
                  <label className="flex items-center gap-2 text-sm text-slate-700 cursor-pointer">
                    <input
                      type="radio"
                      name="pwdStaffOption"
                      checked={createForm.useRandomPassword}
                      onChange={() => setCreateForm({ ...createForm, useRandomPassword: true })}
                    />
                    <span>Tự động tạo mật khẩu ngẫu nhiên an toàn (Khuyến nghị)</span>
                  </label>
                  <label className="flex items-center gap-2 text-sm text-slate-700 cursor-pointer">
                    <input
                      type="radio"
                      name="pwdStaffOption"
                      checked={!createForm.useRandomPassword}
                      onChange={() => setCreateForm({ ...createForm, useRandomPassword: false })}
                    />
                    <span>Tự nhập mật khẩu tạm thời</span>
                  </label>
                </div>

                {!createForm.useRandomPassword && (
                  <div className="mt-3">
                    <input
                      type="text"
                      placeholder="Tối thiểu 8 ký tự, hoa, thường, số, ký tự đặc biệt"
                      className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500"
                      value={createForm.manualPassword}
                      onChange={(e) => setCreateForm({ ...createForm, manualPassword: e.target.value })}
                    />
                    <p className="text-[11px] text-slate-500 mt-1">
                      Yêu cầu: Tối thiểu 8 ký tự, gồm ít nhất 1 chữ hoa, 1 chữ thường, 1 số và 1 ký tự đặc biệt.
                    </p>
                  </div>
                )}
              </div>

              <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-100">
                <button
                  type="button"
                  className="px-4 py-2 text-sm text-slate-600 hover:bg-slate-100 rounded-lg transition-colors"
                  onClick={() => setShowCreateModal(false)}
                >
                  Hủy
                </button>
                <button
                  type="submit"
                  disabled={creating}
                  className="px-4 py-2 text-sm font-medium text-white bg-emerald-600 hover:bg-emerald-700 rounded-lg disabled:opacity-50 transition-colors flex items-center gap-1.5"
                >
                  {creating && <RefreshCw size={14} className="spin" />}
                  <span>{creating ? 'Đang cấp tài khoản...' : 'Cấp tài khoản'}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* 2. MODAL SỬA THÔNG TIN NHÂN VIÊN */}
      {editStaff && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-md border border-slate-200 overflow-hidden">
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100 bg-slate-50">
              <div className="flex items-center gap-2">
                <Edit size={18} className="text-indigo-600" />
                <h3 className="font-semibold text-slate-800 text-base">Chỉnh Sửa Nhân Viên #{editStaff.id}</h3>
              </div>
              <button
                type="button"
                className="p-1 text-slate-400 hover:text-slate-600 rounded-lg hover:bg-slate-200 transition-colors"
                onClick={() => setEditStaff(null)}
              >
                <X size={18} />
              </button>
            </div>

            <form onSubmit={handleEditSubmit} className="p-6 space-y-4">
              {editError && (
                <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-600 flex items-center gap-2">
                  <AlertTriangle size={16} className="shrink-0" />
                  <span>{editError}</span>
                </div>
              )}

              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                  Họ và tên nhân viên <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  required
                  className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  value={editForm.full_name}
                  onChange={(e) => setEditForm({ ...editForm, full_name: e.target.value })}
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                  Email đăng nhập <span className="text-red-500">*</span>
                </label>
                <input
                  type="email"
                  required
                  className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  value={editForm.email}
                  onChange={(e) => setEditForm({ ...editForm, email: e.target.value })}
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                  Số điện thoại
                </label>
                <input
                  type="tel"
                  placeholder="0987654321"
                  className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  value={editForm.phone}
                  onChange={(e) => setEditForm({ ...editForm, phone: e.target.value })}
                />
              </div>

              <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-100">
                <button
                  type="button"
                  className="px-4 py-2 text-sm text-slate-600 hover:bg-slate-100 rounded-lg transition-colors"
                  onClick={() => setEditStaff(null)}
                >
                  Hủy
                </button>
                <button
                  type="submit"
                  disabled={editing}
                  className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg disabled:opacity-50 transition-colors flex items-center gap-1.5"
                >
                  {editing && <RefreshCw size={14} className="spin" />}
                  <span>{editing ? 'Đang lưu...' : 'Lưu thay đổi'}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* 3. MODAL ĐẶT LẠI MẬT KHẨU NHÂN VIÊN */}
      {resetPwdStaff && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-md border border-slate-200 overflow-hidden">
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100 bg-amber-50">
              <div className="flex items-center gap-2">
                <KeyRound size={18} className="text-amber-600" />
                <h3 className="font-semibold text-amber-950 text-base">Đặt Lại Mật Khẩu Nhân Viên</h3>
              </div>
              <button
                type="button"
                className="p-1 text-slate-400 hover:text-slate-600 rounded-lg hover:bg-slate-200 transition-colors"
                onClick={() => setResetPwdStaff(null)}
              >
                <X size={18} />
              </button>
            </div>

            <form onSubmit={handleResetPwdSubmit} className="p-6 space-y-4">
              <div className="p-3 bg-amber-50/70 border border-amber-200 rounded-lg text-xs text-amber-800 space-y-1">
                <div>
                  Đặt lại mật khẩu cho: <strong>{resetPwdStaff.full_name}</strong> ({resetPwdStaff.email})
                </div>
                <div>
                  ⚠️ Phiên đăng nhập cũ của nhân viên sẽ bị thu hồi và nhân viên bắt buộc đổi mật khẩu ở lần đăng nhập tới.
                </div>
              </div>

              {resetPwdError && (
                <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-600 flex items-center gap-2">
                  <AlertTriangle size={16} className="shrink-0" />
                  <span>{resetPwdError}</span>
                </div>
              )}

              <div className="space-y-2">
                <label className="flex items-center gap-2 text-sm text-slate-700 cursor-pointer">
                  <input
                    type="radio"
                    name="resetStaffOption"
                    checked={resetPwdMode === 'random'}
                    onChange={() => setResetPwdMode('random')}
                  />
                  <span>Tự động tạo mật khẩu ngẫu nhiên an toàn (Khuyến nghị)</span>
                </label>
                <label className="flex items-center gap-2 text-sm text-slate-700 cursor-pointer">
                  <input
                    type="radio"
                    name="resetStaffOption"
                    checked={resetPwdMode === 'manual'}
                    onChange={() => setResetPwdMode('manual')}
                  />
                  <span>Tự nhập mật khẩu tạm thời</span>
                </label>
              </div>

              {resetPwdMode === 'manual' && (
                <div className="mt-3">
                  <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                    Mật khẩu tạm thời mới
                  </label>
                  <div className="relative">
                    <input
                      type={showManualPwd ? 'text' : 'password'}
                      placeholder="Tối thiểu 8 ký tự, hoa, thường, số, đặc biệt"
                      className="w-full px-3 py-2 pr-10 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-amber-500"
                      value={resetPwdManual}
                      onChange={(e) => setResetPwdManual(e.target.value)}
                    />
                    <button
                      type="button"
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                      onClick={() => setShowManualPwd(!showManualPwd)}
                    >
                      {showManualPwd ? <EyeOff size={16} /> : <Eye size={16} />}
                    </button>
                  </div>
                  <p className="text-[11px] text-slate-500 mt-1">
                    Yêu cầu: Tối thiểu 8 ký tự, gồm ít nhất 1 chữ hoa, 1 chữ thường, 1 số và 1 ký tự đặc biệt.
                  </p>
                </div>
              )}

              <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-100">
                <button
                  type="button"
                  className="px-4 py-2 text-sm text-slate-600 hover:bg-slate-100 rounded-lg transition-colors"
                  onClick={() => setResetPwdStaff(null)}
                >
                  Hủy
                </button>
                <button
                  type="submit"
                  disabled={resetPwdLoading}
                  className="px-4 py-2 text-sm font-medium text-white bg-amber-600 hover:bg-amber-700 rounded-lg disabled:opacity-50 transition-colors flex items-center gap-1.5"
                >
                  {resetPwdLoading && <RefreshCw size={14} className="spin" />}
                  <span>{resetPwdLoading ? 'Đang thực hiện...' : 'Xác nhận đặt lại'}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* 4. MODAL HIỂN THỊ MẬT KHẨU TẠM THỜI (HIỂN THỊ DUY NHẤT 1 LẦN) */}
      {tempPasswordResult && (
        <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-md flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md border border-slate-200 overflow-hidden animate-fadeIn">
            <div className="bg-gradient-to-r from-emerald-600 to-teal-600 text-white p-6 text-center">
              <div className="w-14 h-14 mx-auto mb-3 rounded-full bg-white/20 flex items-center justify-center">
                <KeyRound size={28} className="text-white" />
              </div>
              <h3 className="text-lg font-bold">{tempPasswordResult.title}</h3>
              <p className="text-xs text-emerald-100 mt-1">
                Nhân viên: <strong>{tempPasswordResult.userName}</strong> ({tempPasswordResult.userEmail})
              </p>
            </div>

            <div className="p-6 space-y-5">
              <div>
                <label className="block text-xs font-bold text-slate-600 uppercase tracking-wider mb-2">
                  Mật khẩu tạm thời khởi tạo:
                </label>
                <div className="flex items-center gap-2">
                  <div className="flex-1 p-3.5 bg-slate-100 border border-slate-300 rounded-xl font-mono text-base font-extrabold text-slate-900 tracking-wider text-center select-all">
                    {tempPasswordResult.password}
                  </div>
                  <button
                    type="button"
                    onClick={() => copyToClipboard(tempPasswordResult.password)}
                    className={`px-4 py-3.5 rounded-xl text-sm font-semibold flex items-center gap-1.5 transition-colors ${
                      copied
                        ? 'bg-emerald-600 text-white'
                        : 'bg-slate-800 hover:bg-slate-900 text-white'
                    }`}
                  >
                    {copied ? <Check size={16} /> : <Copy size={16} />}
                    <span>{copied ? 'Đã sao chép!' : 'Sao chép'}</span>
                  </button>
                </div>
              </div>

              {/* Warning Alert */}
              <div className="p-4 bg-amber-50 border border-amber-300 rounded-xl text-xs text-amber-900 space-y-2">
                <div className="flex items-center gap-1.5 font-bold text-amber-800">
                  <AlertTriangle size={15} />
                  <span>LƯU Ý BẢO MẬT:</span>
                </div>
                <ul className="list-disc pl-4 space-y-1 text-amber-800/90 leading-relaxed">
                  <li>Mật khẩu này chỉ được hiển thị <strong>DUY NHẤT một lần</strong> trên màn hình này.</li>
                  <li>Sau khi đóng hộp thoại, hệ thống sẽ <strong>KHÔNG THỂ hiển thị lại</strong> mật khẩu này.</li>
                  <li>Nhân viên bắt buộc phải đổi mật khẩu ở lần đăng nhập tiếp theo.</li>
                </ul>
              </div>

              <button
                type="button"
                onClick={() => setTempPasswordResult(null)}
                className="w-full py-3 px-4 bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-bold rounded-xl shadow-md transition-colors"
              >
                Tôi đã lưu mật khẩu an toàn & Đóng hộp thoại
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 5. DRAWER CHI TIẾT & LỊCH SỬ HOẠT ĐỘNG NHÂN VIÊN */}
      {detailStaff && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm flex justify-end">
          <div className="bg-white w-full max-w-xl h-full shadow-2xl flex flex-col border-l border-slate-200 overflow-hidden animate-slideInRight">
            <div className="p-5 border-b border-slate-200 bg-slate-50 flex items-center justify-between">
              <div>
                <div className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">
                  CHI TIẾT NHÂN VIÊN KHO #{detailStaff.id}
                </div>
                <h3 className="text-lg font-bold text-slate-800 mt-0.5">{detailStaff.full_name}</h3>
              </div>
              <button
                type="button"
                className="p-1.5 text-slate-400 hover:text-slate-600 rounded-lg hover:bg-slate-200 transition-colors"
                onClick={() => setDetailStaff(null)}
              >
                <X size={20} />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-6 space-y-6">
              {/* Profile Card */}
              <div className="p-4 bg-slate-50 border border-slate-200 rounded-xl space-y-3">
                <div className="flex items-center justify-between pb-3 border-b border-slate-200">
                  <span className="text-xs font-semibold text-slate-500">Trạng thái:</span>
                  <span
                    style={{
                      padding: '3px 8px',
                      borderRadius: '9999px',
                      fontSize: '11px',
                      fontWeight: 700,
                      background: detailStaff.is_active ? '#ecfdf5' : '#fff1f2',
                      color: detailStaff.is_active ? '#047857' : '#be123c',
                    }}
                  >
                    {detailStaff.is_active ? 'Đang hoạt động' : 'Tạm khóa'}
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-3 text-xs">
                  <div>
                    <span className="text-slate-500 block">Email đăng nhập:</span>
                    <strong className="text-slate-800 font-mono text-[13px]">{detailStaff.email}</strong>
                  </div>
                  <div>
                    <span className="text-slate-500 block">Số điện thoại:</span>
                    <strong className="text-slate-800">{detailStaff.phone || 'Chưa cập nhật'}</strong>
                  </div>
                  <div>
                    <span className="text-slate-500 block">Kho làm việc:</span>
                    <strong className="text-slate-800">{detailStaff.warehouse_name || currentUser?.warehouse_name || 'Kho hiện tại'}</strong>
                  </div>
                  <div>
                    <span className="text-slate-500 block">Ngày tạo:</span>
                    <span className="text-slate-700">
                      {detailStaff.created_at ? new Date(detailStaff.created_at).toLocaleString('vi-VN') : '—'}
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-500 block">Đăng nhập gần nhất:</span>
                    <span className="text-slate-700">
                      {detailStaff.last_login_at ? new Date(detailStaff.last_login_at).toLocaleString('vi-VN') : 'Chưa đăng nhập'}
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-500 block">Bắt buộc đổi mật khẩu:</span>
                    <span className={detailStaff.must_change_password ? 'text-amber-600 font-bold' : 'text-slate-700'}>
                      {detailStaff.must_change_password ? 'Có (Mật khẩu tạm)' : 'Đã kích hoạt'}
                    </span>
                  </div>
                </div>

                <div className="pt-3 border-t border-slate-200 flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => {
                      setDetailStaff(null)
                      handleOpenResetPwd(detailStaff)
                    }}
                    className="flex-1 py-1.5 px-3 bg-amber-50 hover:bg-amber-100 text-amber-800 border border-amber-300 rounded-lg text-xs font-semibold flex items-center justify-center gap-1.5"
                  >
                    <KeyRound size={13} />
                    <span>Đặt lại mật khẩu</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setDetailStaff(null)
                      handleOpenEdit(detailStaff)
                    }}
                    className="flex-1 py-1.5 px-3 bg-indigo-50 hover:bg-indigo-100 text-indigo-800 border border-indigo-300 rounded-lg text-xs font-semibold flex items-center justify-center gap-1.5"
                  >
                    <Edit size={13} />
                    <span>Sửa thông tin</span>
                  </button>
                </div>
              </div>

              {/* Activity Log Section */}
              <div>
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <History size={16} className="text-slate-600" />
                    <h4 className="font-bold text-slate-800 text-sm">Lịch Sử Thao Tác & Hoạt Động</h4>
                  </div>
                  <span className="text-xs text-slate-500">{activityLogs.length} sự kiện</span>
                </div>

                {loadingActivity ? (
                  <div className="p-8 text-center text-slate-400 text-xs">
                    <RefreshCw size={18} className="spin mx-auto mb-2" />
                    Đang tải lịch sử...
                  </div>
                ) : activityLogs.length === 0 ? (
                  <div className="p-8 text-center text-slate-400 text-xs bg-slate-50 rounded-xl border border-slate-200">
                    Chưa có lịch sử thao tác nào được ghi nhận cho nhân viên này.
                  </div>
                ) : (
                  <div className="space-y-2.5">
                    {activityLogs.map((log) => (
                      <div
                        key={log.id}
                        className="p-3 bg-white border border-slate-200 rounded-lg hover:border-slate-300 transition-colors"
                      >
                        <div className="flex items-center justify-between">
                          <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-slate-100 text-slate-700">
                            {log.action}
                          </span>
                          <span className="text-[11px] text-slate-400 flex items-center gap-1">
                            <Clock size={11} />
                            {log.created_at ? new Date(log.created_at).toLocaleString('vi-VN') : '—'}
                          </span>
                        </div>
                        <div className="text-xs text-slate-600 mt-1.5 flex items-center gap-2">
                          <span>Người thao tác: <strong>{log.user_name || 'Hệ thống'}</strong></span>
                          {log.ip_address && (
                            <span className="text-slate-400 font-mono text-[11px]">• IP: {log.ip_address}</span>
                          )}
                        </div>
                        {log.details && (
                          <div className="mt-2 p-2 bg-slate-50 rounded text-[11px] font-mono text-slate-600 overflow-x-auto">
                            {typeof log.details === 'object' ? JSON.stringify(log.details) : String(log.details)}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
