import { useEffect, useMemo, useState } from 'react'
import {
  Users,
  ShieldCheck,
  UserCheck,
  Building2,
  RefreshCw,
  Phone,
  Mail,
  Calendar,
  Lock,
  Unlock,
  KeyRound,
  Edit,
  History,
  Copy,
  Check,
  Eye,
  EyeOff,
  UserPlus,
  AlertTriangle,
  X,
  Clock,
  ShieldAlert,
  Search,
  Filter,
} from 'lucide-react'
import { AdminPageHeader } from '../components/AdminPageHeader'
import { StatCard, StatGrid } from '../components/StatCard'
import { FilterBar } from '../components/FilterBar'
import { StatusBadge } from '../components/StatusBadge'
import { PaginationBar } from '../components/PaginationBar'
import { api } from '../services/api'
import { useAuth } from '../services/auth'
import type { User, WarehouseItem, UserRole, UserActivityLog } from '../types'

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

export function UsersPage() {
  const { user: currentUser } = useAuth()
  const [users, setUsers] = useState<User[]>([])
  const [warehouses, setWarehouses] = useState<WarehouseItem[]>([])
  const [loading, setLoading] = useState(true)

  // Filters
  const [search, setSearch] = useState('')
  const [roleFilter, setRoleFilter] = useState<string>('ALL')
  const [warehouseFilter, setWarehouseFilter] = useState<string>('ALL')
  const [statusFilter, setStatusFilter] = useState<string>('ALL')
  const [mustChangePwdFilter, setMustChangePwdFilter] = useState<string>('ALL')

  // Pagination
  const [currentPage, setCurrentPage] = useState<number>(1)
  const [pageSize, setPageSize] = useState<number>(15)

  // Modals & Drawers
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [editUser, setEditUser] = useState<User | null>(null)
  const [resetPwdUser, setResetPwdUser] = useState<User | null>(null)
  const [detailUser, setDetailUser] = useState<User | null>(null)
  const [userActivityLogs, setUserActivityLogs] = useState<UserActivityLog[]>([])
  const [loadingActivity, setLoadingActivity] = useState(false)

  // Temporary password display modal (shown EXACTLY ONCE)
  const [tempPasswordResult, setTempPasswordResult] = useState<{
    userEmail: string
    userName: string
    password: string
    title: string
  } | null>(null)
  const [copied, setCopied] = useState(false)

  // Create Form State
  const [createFormData, setCreateFormData] = useState({
    full_name: '',
    email: '',
    phone: '',
    role: 'WAREHOUSE_MANAGER' as UserRole,
    warehouse_id: '',
    useRandomPassword: true,
    manualPassword: '',
  })
  const [createLoading, setCreateLoading] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)

  // Edit Form State
  const [editFormData, setEditFormData] = useState({
    full_name: '',
    email: '',
    phone: '',
    role: 'CUSTOMER' as UserRole,
    warehouse_id: '',
  })
  const [editLoading, setEditLoading] = useState(false)
  const [editError, setEditError] = useState<string | null>(null)

  // Reset Password Form State
  const [resetPwdMode, setResetPwdMode] = useState<'random' | 'manual'>('random')
  const [resetPwdManual, setResetPwdManual] = useState('')
  const [resetPwdLoading, setResetPwdLoading] = useState(false)
  const [resetPwdError, setResetPwdError] = useState<string | null>(null)
  const [showManualPwd, setShowManualPwd] = useState(false)

  // Data fetching
  const fetchUsers = () => {
    setLoading(true)
    api<User[]>('/users')
      .then((data) => setUsers(data || []))
      .catch((err) => console.error('Failed to load users:', err))
      .finally(() => setLoading(false))
  }

  const fetchWarehouses = () => {
    api<WarehouseItem[]>('/warehouses')
      .then((data) => setWarehouses(data || []))
      .catch((err) => console.error('Failed to load warehouses:', err))
  }

  useEffect(() => {
    fetchUsers()
    fetchWarehouses()
  }, [])

  // Load activity logs when detail drawer opens
  useEffect(() => {
    if (detailUser) {
      setLoadingActivity(true)
      api<UserActivityLog[]>(`/users/${detailUser.id}/activity`)
        .then((logs) => setUserActivityLogs(logs || []))
        .catch((err) => {
          console.error('Failed to load activity logs:', err)
          setUserActivityLogs([])
        })
        .finally(() => setLoadingActivity(false))
    } else {
      setUserActivityLogs([])
    }
  }, [detailUser])

  // Filtered users
  const filteredUsers = useMemo(() => {
    return users.filter((u) => {
      const matchesRole = roleFilter === 'ALL' || u.role === roleFilter
      const matchesWh =
        warehouseFilter === 'ALL' ||
        (warehouseFilter === 'NONE' && !u.warehouse_id) ||
        String(u.warehouse_id) === warehouseFilter
      const matchesStatus =
        statusFilter === 'ALL' ||
        (statusFilter === 'ACTIVE' && u.is_active) ||
        (statusFilter === 'INACTIVE' && !u.is_active)
      const matchesMustChange =
        mustChangePwdFilter === 'ALL' ||
        (mustChangePwdFilter === 'YES' && u.must_change_password) ||
        (mustChangePwdFilter === 'NO' && !u.must_change_password)

      const term = search.toLowerCase().trim()
      const matchesSearch =
        !term ||
        u.full_name.toLowerCase().includes(term) ||
        u.email.toLowerCase().includes(term) ||
        (u.phone && u.phone.includes(term)) ||
        (u.warehouse_name && u.warehouse_name.toLowerCase().includes(term))

      return matchesRole && matchesWh && matchesStatus && matchesMustChange && matchesSearch
    })
  }, [users, roleFilter, warehouseFilter, statusFilter, mustChangePwdFilter, search])

  // Reset page when filters change
  useEffect(() => {
    setCurrentPage(1)
  }, [search, roleFilter, warehouseFilter, statusFilter, mustChangePwdFilter])

  const totalPages = Math.max(1, Math.ceil(filteredUsers.length / pageSize))
  const displayedUsers = useMemo(() => {
    const start = (currentPage - 1) * pageSize
    return filteredUsers.slice(start, start + pageSize)
  }, [filteredUsers, currentPage, pageSize])

  // Statistics
  const totalUsers = users.length
  const totalAdmins = users.filter((u) => u.role === 'ADMIN').length
  const totalWarehouseManagers = users.filter((u) => u.role === 'WAREHOUSE_MANAGER').length
  const totalWarehouseStaff = users.filter((u) => u.role === 'WAREHOUSE_STAFF').length
  const totalCustomers = users.filter((u) => u.role === 'CUSTOMER').length
  const totalLocked = users.filter((u) => !u.is_active).length

  // Lock / Unlock Handler
  const handleToggleStatus = async (target: User) => {
    const actionLabel = target.is_active ? 'khóa' : 'mở khóa'
    if (!window.confirm(`Bạn có chắc chắn muốn ${actionLabel} tài khoản "${target.full_name}" (${target.email})?\nPhiên làm việc hiện tại của tài khoản sẽ bị thu hồi.`)) {
      return
    }

    try {
      const updated = await api<User>(`/users/${target.id}/status`, { method: 'PATCH' })
      if (updated) {
        setUsers((prev) => prev.map((u) => (u.id === target.id ? updated : u)))
        if (detailUser && detailUser.id === target.id) {
          setDetailUser(updated)
        }
      }
    } catch (err: any) {
      alert(err?.message || 'Thao tác cập nhật trạng thái thất bại')
    }
  }

  // Handle Create User
  const handleCreateSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setCreateError(null)

    if (!createFormData.full_name.trim() || !createFormData.email.trim()) {
      setCreateError('Vui lòng điền đầy đủ họ và tên, email đăng nhập')
      return
    }

    let passwordToSend: string | undefined = undefined
    if (createFormData.useRandomPassword) {
      // Auto-generated password
      passwordToSend = generateSecureRandomPassword(12)
    } else {
      if (!createFormData.manualPassword.trim()) {
        setCreateError('Vui lòng nhập mật khẩu tạm thời hoặc chọn tự động tạo ngẫu nhiên')
        return
      }
      const check = checkPasswordStrength(createFormData.manualPassword)
      if (!check.valid) {
        setCreateError(check.message)
        return
      }
      passwordToSend = createFormData.manualPassword.trim()
    }

    setCreateLoading(true)
    try {
      const payload: any = {
        full_name: createFormData.full_name.trim(),
        email: createFormData.email.trim(),
        role: createFormData.role,
        phone: createFormData.phone.trim() || null,
        password: passwordToSend,
        must_change_password: true,
      }
      if (createFormData.warehouse_id) {
        payload.warehouse_id = Number(createFormData.warehouse_id)
      }

      const res = await api<{ user: User; temporary_password: string; message: string }>('/users', {
        method: 'POST',
        body: JSON.stringify(payload),
      })

      setShowCreateModal(false)
      setCreateFormData({
        full_name: '',
        email: '',
        phone: '',
        role: 'WAREHOUSE_MANAGER',
        warehouse_id: '',
        useRandomPassword: true,
        manualPassword: '',
      })

      fetchUsers()

      // Show temporary password modal
      setTempPasswordResult({
        userEmail: res.user.email,
        userName: res.user.full_name,
        password: res.temporary_password,
        title: 'Tài Khoản Mới Đã Được Tạo Thành Công',
      })
      setCopied(false)
    } catch (err: any) {
      setCreateError(err?.message || 'Tạo tài khoản thất bại')
    } finally {
      setCreateLoading(false)
    }
  }

  // Open Edit Modal
  const handleOpenEdit = (user: User) => {
    setEditUser(user)
    setEditError(null)
    setEditFormData({
      full_name: user.full_name || '',
      email: user.email || '',
      phone: user.phone || '',
      role: user.role,
      warehouse_id: user.warehouse_id ? String(user.warehouse_id) : '',
    })
  }

  // Handle Edit Submit
  const handleEditSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!editUser) return
    setEditError(null)

    if (!editFormData.full_name.trim() || !editFormData.email.trim()) {
      setEditError('Họ tên và email không được để trống')
      return
    }

    setEditLoading(true)
    try {
      const payload: any = {
        full_name: editFormData.full_name.trim(),
        email: editFormData.email.trim(),
        phone: editFormData.phone.trim() || null,
        role: editFormData.role,
        warehouse_id: editFormData.warehouse_id ? Number(editFormData.warehouse_id) : 0,
      }

      const updated = await api<User>(`/users/${editUser.id}`, {
        method: 'PATCH',
        body: JSON.stringify(payload),
      })

      setUsers((prev) => prev.map((u) => (u.id === editUser.id ? updated : u)))
      if (detailUser && detailUser.id === editUser.id) {
        setDetailUser(updated)
      }
      setEditUser(null)
    } catch (err: any) {
      setEditError(err?.message || 'Cập nhật tài khoản thất bại')
    } finally {
      setEditLoading(false)
    }
  }

  // Open Reset Password Modal
  const handleOpenResetPwd = (user: User) => {
    setResetPwdUser(user)
    setResetPwdError(null)
    setResetPwdMode('random')
    setResetPwdManual('')
    setShowManualPwd(false)
  }

  // Handle Reset Password Submit
  const handleResetPwdSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!resetPwdUser) return
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
        `/users/${resetPwdUser.id}/reset-password`,
        {
          method: 'POST',
          body: JSON.stringify(payload),
        }
      )

      const targetName = resetPwdUser.full_name
      const targetEmail = resetPwdUser.email
      setResetPwdUser(null)

      // Refresh users to show updated status
      fetchUsers()

      // Show temporary password modal ONCE
      setTempPasswordResult({
        userEmail: targetEmail,
        userName: targetName,
        password: res.temporary_password,
        title: 'Đặt Lại Mật Khẩu Thành Công',
      })
      setCopied(false)
    } catch (err: any) {
      setResetPwdError(err?.message || 'Đặt lại mật khẩu thất bại')
    } finally {
      setResetPwdLoading(false)
    }
  }

  // Copy to clipboard helper
  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2500)
    })
  }

  return (
    <div className="page">
      <AdminPageHeader
        title="Quản lý tài khoản & Phân quyền RBAC"
        eyebrow="QUẢN TRỊ HỆ THỐNG • TÀI KHOẢN & BẢO MẬT"
        subtitle="Quản lý định danh toàn hệ thống, gán kho chi nhánh, đặt lại mật khẩu và giám sát an ninh phiên làm việc."
        badge={totalUsers > 0 ? <span className="stat-card-badge">{totalUsers} tài khoản</span> : undefined}
        actions={
          <div className="flex items-center gap-2">
            <button
              type="button"
              className="admin-button button-secondary"
              onClick={fetchUsers}
              disabled={loading}
              title="Tải lại danh sách"
            >
              <RefreshCw size={14} className={loading ? 'spin' : ''} />
              <span>Làm mới</span>
            </button>
            <button
              type="button"
              className="admin-button button-primary"
              onClick={() => {
                setCreateError(null)
                setShowCreateModal(true)
              }}
            >
              <UserPlus size={15} />
              <span>Thêm tài khoản mới</span>
            </button>
          </div>
        }
      />

      {/* KPI Stats Grid */}
      <StatGrid columns={4}>
        <StatCard
          label="Tổng tài khoản"
          value={totalUsers}
          icon={Users}
          tone="blue"
          subtext={`${totalLocked} tài khoản đang bị khóa`}
          loading={loading}
        />
        <StatCard
          label="Quản trị viên"
          value={totalAdmins}
          icon={ShieldCheck}
          tone="amber"
          subtext="Toàn quyền điều hành hệ thống"
          loading={loading}
        />
        <StatCard
          label="Nhân sự Kho vận"
          value={totalWarehouseManagers + totalWarehouseStaff}
          icon={Building2}
          tone="emerald"
          subtext={`${totalWarehouseManagers} Quản lý kho • ${totalWarehouseStaff} Nhân viên`}
          loading={loading}
        />
        <StatCard
          label="Khách hàng thành viên"
          value={totalCustomers}
          icon={UserCheck}
          tone="purple"
          subtext="Người mua hàng trên website"
          loading={loading}
        />
      </StatGrid>

      {/* FilterBar */}
      <FilterBar
        searchValue={search}
        onSearchChange={setSearch}
        searchPlaceholder="Tìm theo họ tên, email, số điện thoại hoặc kho làm việc..."
        totalCount={totalUsers}
        filteredCount={filteredUsers.length}
        unitLabel="tài khoản"
        onRefresh={fetchUsers}
        isRefreshing={loading}
      >
        <select
          value={roleFilter}
          onChange={(e) => setRoleFilter(e.target.value)}
          style={{ minWidth: '170px' }}
        >
          <option value="ALL">Tất cả vai trò ({totalUsers})</option>
          <option value="ADMIN">Quản trị viên ({totalAdmins})</option>
          <option value="WAREHOUSE_MANAGER">Quản lý kho ({totalWarehouseManagers})</option>
          <option value="WAREHOUSE_STAFF">Nhân viên kho ({totalWarehouseStaff})</option>
          <option value="CUSTOMER">Khách hàng ({totalCustomers})</option>
        </select>

        {warehouses.length > 0 && (
          <select
            value={warehouseFilter}
            onChange={(e) => setWarehouseFilter(e.target.value)}
            style={{ minWidth: '200px' }}
          >
            <option value="ALL">Tất cả kho ({warehouses.length} kho)</option>
            <option value="NONE">Chưa gán kho / Toàn hệ thống</option>
            {warehouses.map((wh) => (
              <option key={wh.id} value={String(wh.id)}>
                {wh.code} - {wh.name}
              </option>
            ))}
          </select>
        )}

        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          style={{ minWidth: '150px' }}
        >
          <option value="ALL">Tất cả trạng thái</option>
          <option value="ACTIVE">Đang hoạt động</option>
          <option value="INACTIVE">Đã khóa ({totalLocked})</option>
        </select>

        <select
          value={mustChangePwdFilter}
          onChange={(e) => setMustChangePwdFilter(e.target.value)}
          style={{ minWidth: '170px' }}
        >
          <option value="ALL">Tất cả bảo mật</option>
          <option value="YES">Bắt buộc đổi MK</option>
          <option value="NO">Bình thường</option>
        </select>
      </FilterBar>

      {/* Users Table */}
      <div className="admin-data-table-container">
        <div className="admin-table-wrap">
          <table className="admin-table">
            <thead>
              <tr>
                <th style={{ width: '60px', textAlign: 'center' }}>ID</th>
                <th style={{ minWidth: '220px' }}>Họ và tên / Định danh</th>
                <th style={{ minWidth: '200px' }}>Tên đăng nhập (Email / SĐT)</th>
                <th style={{ width: '150px' }}>Vai trò</th>
                <th style={{ minWidth: '180px' }}>Kho làm việc</th>
                <th style={{ width: '130px', textAlign: 'center' }}>Trạng thái</th>
                <th style={{ width: '140px', textAlign: 'center' }}>Bảo mật MK</th>
                <th style={{ minWidth: '150px' }}>Đăng nhập cuối</th>
                <th style={{ width: '180px', textAlign: 'center' }}>Thao tác</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={9} style={{ padding: '40px 16px', textAlign: 'center', color: '#64748b' }}>
                    <RefreshCw size={22} className="spin" style={{ margin: '0 auto 8px', display: 'block' }} />
                    Đang tải danh sách tài khoản...
                  </td>
                </tr>
              ) : filteredUsers.length === 0 ? (
                <tr>
                  <td colSpan={9} style={{ padding: '40px 16px', textAlign: 'center', color: '#64748b' }}>
                    Không tìm thấy tài khoản nào phù hợp với bộ lọc hiện tại.
                  </td>
                </tr>
              ) : (
                displayedUsers.map((u) => {
                  const isAdmin = u.role === 'ADMIN'
                  const isCustomer = u.role === 'CUSTOMER'
                  const isWarehouse = u.role === 'WAREHOUSE_MANAGER' || u.role === 'WAREHOUSE_STAFF'
                  const isSelf = currentUser?.id === u.id

                  return (
                    <tr key={u.id}>
                      <td style={{ textAlign: 'center', fontWeight: 700, color: '#64748b', fontSize: '12px' }}>
                        #{u.id}
                      </td>

                      <td>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                          <div
                            style={{
                              width: '36px',
                              height: '36px',
                              borderRadius: '10px',
                              background: isAdmin
                                ? '#fef3c7'
                                : isWarehouse
                                ? '#dcfce7'
                                : isCustomer
                                ? '#dbeafe'
                                : '#f1f5f9',
                              color: isAdmin
                                ? '#b45309'
                                : isWarehouse
                                ? '#15803d'
                                : isCustomer
                                ? '#1d4ed8'
                                : '#475569',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              fontWeight: 800,
                              fontSize: '14px',
                              flexShrink: 0,
                            }}
                          >
                            {u.full_name ? u.full_name.charAt(0).toUpperCase() : 'U'}
                          </div>
                          <div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                              <strong style={{ color: '#0f172a', fontSize: '13.5px' }}>{u.full_name}</strong>
                              {isSelf && (
                                <span
                                  style={{
                                    fontSize: '10px',
                                    fontWeight: 700,
                                    padding: '1px 6px',
                                    borderRadius: '4px',
                                    background: '#e0f2fe',
                                    color: '#0369a1',
                                  }}
                                >
                                  Bạn
                                </span>
                              )}
                            </div>
                            <div style={{ fontSize: '11px', color: '#94a3b8', marginTop: '2px' }}>
                              {u.created_by_name ? `Tạo bởi: ${u.created_by_name}` : 'Tạo tự động qua hệ thống'}
                            </div>
                          </div>
                        </div>
                      </td>

                      <td>
                        <div style={{ fontSize: '12.5px' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#334155', fontWeight: 500 }}>
                            <Mail size={13} style={{ color: '#94a3b8', flexShrink: 0 }} />
                            <span>{u.email}</span>
                          </div>
                          {u.phone ? (
                            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#64748b', marginTop: '3px' }}>
                              <Phone size={13} style={{ color: '#94a3b8', flexShrink: 0 }} />
                              <span>{u.phone}</span>
                            </div>
                          ) : (
                            <div style={{ fontSize: '11px', color: '#cbd5e1', marginTop: '2px' }}>Chưa có SĐT</div>
                          )}
                        </div>
                      </td>

                      <td>
                        <StatusBadge value={u.role} showDot />
                      </td>

                      <td>
                        {u.warehouse_name ? (
                          <span className="inline-flex items-center gap-1.5 px-2 py-1 rounded-md text-xs font-semibold bg-emerald-50 text-emerald-800 border border-emerald-200">
                            <Building2 size={13} className="text-emerald-600" />
                            <span className="truncate max-w-[160px]" title={u.warehouse_name}>
                              {u.warehouse_name}
                            </span>
                          </span>
                        ) : isWarehouse ? (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-amber-50 text-amber-700 border border-amber-200">
                            <AlertTriangle size={12} /> Chưa gán kho
                          </span>
                        ) : (
                          <span style={{ fontSize: '12px', color: '#94a3b8' }}>Toàn hệ thống</span>
                        )}
                      </td>

                      <td style={{ textAlign: 'center' }}>
                        <StatusBadge
                          value={u.is_active ? 'ACTIVE' : 'INACTIVE'}
                          tone={u.is_active ? 'success' : 'danger'}
                          showDot
                        />
                      </td>

                      <td style={{ textAlign: 'center' }}>
                        {u.must_change_password ? (
                          <span
                            style={{
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '4px',
                              padding: '2px 8px',
                              borderRadius: '999px',
                              fontSize: '11px',
                              fontWeight: 700,
                              background: '#fffbeb',
                              color: '#b45309',
                              border: '1px solid #fef3c7',
                            }}
                          >
                            <ShieldAlert size={12} /> Bắt buộc đổi
                          </span>
                        ) : (
                          <span
                            style={{
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '4px',
                              padding: '2px 8px',
                              borderRadius: '999px',
                              fontSize: '11px',
                              fontWeight: 600,
                              background: '#f8fafc',
                              color: '#64748b',
                              border: '1px solid #e2e8f0',
                            }}
                          >
                            Đã kích hoạt
                          </span>
                        )}
                      </td>

                      <td>
                        <div style={{ fontSize: '12px', color: '#475569', display: 'flex', alignItems: 'center', gap: '5px' }}>
                          <Calendar size={13} style={{ color: '#94a3b8', flexShrink: 0 }} />
                          {u.last_login_at ? new Date(u.last_login_at).toLocaleString('vi-VN') : 'Chưa đăng nhập'}
                        </div>
                      </td>

                      <td style={{ textAlign: 'center' }}>
                        <div style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                          {/* Chi tiết / Lịch sử */}
                          <button
                            type="button"
                            className="p-1.5 rounded text-slate-600 hover:text-blue-600 hover:bg-blue-50 transition-colors"
                            title="Xem chi tiết & Lịch sử hoạt động"
                            onClick={() => setDetailUser(u)}
                          >
                            <History size={15} />
                          </button>

                          {/* Sửa thông tin */}
                          <button
                            type="button"
                            className="p-1.5 rounded text-slate-600 hover:text-indigo-600 hover:bg-indigo-50 transition-colors"
                            title="Chỉnh sửa thông tin tài khoản"
                            onClick={() => handleOpenEdit(u)}
                          >
                            <Edit size={15} />
                          </button>

                          {/* Đặt lại mật khẩu */}
                          <button
                            type="button"
                            className="p-1.5 rounded text-slate-600 hover:text-amber-600 hover:bg-amber-50 transition-colors"
                            title="Đặt lại mật khẩu tạm thời"
                            onClick={() => handleOpenResetPwd(u)}
                          >
                            <KeyRound size={15} />
                          </button>

                          {/* Khóa / Mở khóa (không tự khóa chính mình) */}
                          {!isSelf && (
                            <button
                              type="button"
                              className={`p-1.5 rounded transition-colors ${
                                u.is_active
                                  ? 'text-slate-500 hover:text-red-600 hover:bg-red-50'
                                  : 'text-slate-500 hover:text-emerald-600 hover:bg-emerald-50'
                              }`}
                              title={u.is_active ? 'Khóa tài khoản' : 'Mở khóa tài khoản'}
                              onClick={() => handleToggleStatus(u)}
                            >
                              {u.is_active ? <Lock size={15} /> : <Unlock size={15} />}
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {!loading && filteredUsers.length > 0 && (
          <PaginationBar
            currentPage={currentPage}
            totalPages={totalPages}
            pageSize={pageSize}
            totalItems={users.length}
            filteredCount={filteredUsers.length}
            itemName="tài khoản"
            onPageChange={setCurrentPage}
            onPageSizeChange={setPageSize}
            pageSizeOptions={[10, 15, 25, 50]}
          />
        )}
      </div>

      {/* 1. MODAL TẠO TÀI KHOẢN MỚI */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-lg border border-slate-200 overflow-hidden">
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100 bg-slate-50">
              <div className="flex items-center gap-2">
                <UserPlus size={18} className="text-blue-600" />
                <h3 className="font-semibold text-slate-800 text-base">Tạo Tài Khoản Mới</h3>
              </div>
              <button
                type="button"
                className="p-1 text-slate-400 hover:text-slate-600 rounded-lg hover:bg-slate-200 transition-colors"
                onClick={() => setShowCreateModal(false)}
              >
                <X size={18} />
              </button>
            </div>

            <form onSubmit={handleCreateSubmit} className="p-6 space-y-4">
              {createError && (
                <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-600 flex items-center gap-2">
                  <AlertTriangle size={16} className="shrink-0" />
                  <span>{createError}</span>
                </div>
              )}

              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                  Họ và tên <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  required
                  placeholder="Ví dụ: Nguyễn Văn Nam"
                  className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                  value={createFormData.full_name}
                  onChange={(e) => setCreateFormData({ ...createFormData, full_name: e.target.value })}
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                    Email đăng nhập <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="email"
                    required
                    placeholder="nam.nv@pharmatrust.vn"
                    className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                    value={createFormData.email}
                    onChange={(e) => setCreateFormData({ ...createFormData, email: e.target.value })}
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                    Số điện thoại
                  </label>
                  <input
                    type="tel"
                    placeholder="0912345678"
                    className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                    value={createFormData.phone}
                    onChange={(e) => setCreateFormData({ ...createFormData, phone: e.target.value })}
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                    Vai trò <span className="text-red-500">*</span>
                  </label>
                  <select
                    className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                    value={createFormData.role}
                    onChange={(e) => setCreateFormData({ ...createFormData, role: e.target.value as UserRole })}
                  >
                    <option value="WAREHOUSE_MANAGER">Quản lý kho</option>
                    <option value="WAREHOUSE_STAFF">Nhân viên kho</option>
                    <option value="CUSTOMER">Khách hàng</option>
                    <option value="ADMIN">Quản trị viên toàn hệ thống</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                    Kho trực thuộc
                  </label>
                  <select
                    className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                    value={createFormData.warehouse_id}
                    onChange={(e) => setCreateFormData({ ...createFormData, warehouse_id: e.target.value })}
                    disabled={createFormData.role === 'CUSTOMER' || createFormData.role === 'ADMIN'}
                  >
                    <option value="">-- Không gán kho / Toàn hệ thống --</option>
                    {warehouses.map((wh) => (
                      <option key={wh.id} value={wh.id}>
                        {wh.code} - {wh.name}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Password option */}
              <div className="pt-2 border-t border-slate-100">
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-2">
                  Thiết lập mật khẩu khởi tạo
                </label>
                <div className="space-y-2">
                  <label className="flex items-center gap-2 text-sm text-slate-700 cursor-pointer">
                    <input
                      type="radio"
                      name="pwdOption"
                      checked={createFormData.useRandomPassword}
                      onChange={() => setCreateFormData({ ...createFormData, useRandomPassword: true })}
                    />
                    <span>Tự động tạo mật khẩu ngẫu nhiên an toàn (Khuyến nghị)</span>
                  </label>
                  <label className="flex items-center gap-2 text-sm text-slate-700 cursor-pointer">
                    <input
                      type="radio"
                      name="pwdOption"
                      checked={!createFormData.useRandomPassword}
                      onChange={() => setCreateFormData({ ...createFormData, useRandomPassword: false })}
                    />
                    <span>Tự nhập mật khẩu tạm thời</span>
                  </label>
                </div>

                {!createFormData.useRandomPassword && (
                  <div className="mt-3">
                    <input
                      type="text"
                      placeholder="Nhập mật khẩu (tối thiểu 8 ký tự, hoa, thường, số, ký tự đặc biệt)"
                      className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                      value={createFormData.manualPassword}
                      onChange={(e) => setCreateFormData({ ...createFormData, manualPassword: e.target.value })}
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
                  disabled={createLoading}
                  className="px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg disabled:opacity-50 transition-colors flex items-center gap-1.5"
                >
                  {createLoading && <RefreshCw size={14} className="spin" />}
                  <span>{createLoading ? 'Đang tạo...' : 'Tạo tài khoản'}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* 2. MODAL CHỈNH SỬA TÀI KHOẢN */}
      {editUser && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-lg border border-slate-200 overflow-hidden">
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100 bg-slate-50">
              <div className="flex items-center gap-2">
                <Edit size={18} className="text-indigo-600" />
                <h3 className="font-semibold text-slate-800 text-base">Chỉnh Sửa Tài Khoản #{editUser.id}</h3>
              </div>
              <button
                type="button"
                className="p-1 text-slate-400 hover:text-slate-600 rounded-lg hover:bg-slate-200 transition-colors"
                onClick={() => setEditUser(null)}
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
                  Họ và tên <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  required
                  className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  value={editFormData.full_name}
                  onChange={(e) => setEditFormData({ ...editFormData, full_name: e.target.value })}
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                    Email đăng nhập <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="email"
                    required
                    className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    value={editFormData.email}
                    onChange={(e) => setEditFormData({ ...editFormData, email: e.target.value })}
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                    Số điện thoại
                  </label>
                  <input
                    type="tel"
                    placeholder="0912345678"
                    className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    value={editFormData.phone}
                    onChange={(e) => setEditFormData({ ...editFormData, phone: e.target.value })}
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                    Vai trò <span className="text-red-500">*</span>
                  </label>
                  <select
                    className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    value={editFormData.role}
                    onChange={(e) => setEditFormData({ ...editFormData, role: e.target.value as UserRole })}
                  >
                    <option value="WAREHOUSE_MANAGER">Quản lý kho</option>
                    <option value="WAREHOUSE_STAFF">Nhân viên kho</option>
                    <option value="CUSTOMER">Khách hàng</option>
                    <option value="ADMIN">Quản trị viên toàn hệ thống</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                    Kho trực thuộc
                  </label>
                  <select
                    className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    value={editFormData.warehouse_id}
                    onChange={(e) => setEditFormData({ ...editFormData, warehouse_id: e.target.value })}
                  >
                    <option value="">-- Không gán kho / Toàn hệ thống --</option>
                    {warehouses.map((wh) => (
                      <option key={wh.id} value={wh.id}>
                        {wh.code} - {wh.name}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-100">
                <button
                  type="button"
                  className="px-4 py-2 text-sm text-slate-600 hover:bg-slate-100 rounded-lg transition-colors"
                  onClick={() => setEditUser(null)}
                >
                  Hủy
                </button>
                <button
                  type="submit"
                  disabled={editLoading}
                  className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg disabled:opacity-50 transition-colors flex items-center gap-1.5"
                >
                  {editLoading && <RefreshCw size={14} className="spin" />}
                  <span>{editLoading ? 'Đang lưu...' : 'Lưu thay đổi'}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* 3. MODAL ĐẶT LẠI MẬT KHẨU */}
      {resetPwdUser && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-md border border-slate-200 overflow-hidden">
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100 bg-amber-50">
              <div className="flex items-center gap-2">
                <KeyRound size={18} className="text-amber-600" />
                <h3 className="font-semibold text-amber-950 text-base">Đặt Lại Mật Khẩu</h3>
              </div>
              <button
                type="button"
                className="p-1 text-slate-400 hover:text-slate-600 rounded-lg hover:bg-slate-200 transition-colors"
                onClick={() => setResetPwdUser(null)}
              >
                <X size={18} />
              </button>
            </div>

            <form onSubmit={handleResetPwdSubmit} className="p-6 space-y-4">
              <div className="p-3 bg-amber-50/70 border border-amber-200 rounded-lg text-xs text-amber-800 space-y-1">
                <div>
                  Đặt lại mật khẩu cho: <strong>{resetPwdUser.full_name}</strong> ({resetPwdUser.email})
                </div>
                <div>
                  ⚠️ Toàn bộ phiên đăng nhập cũ sẽ bị thu hồi và người dùng bắt buộc đổi mật khẩu ở lần đăng nhập tiếp theo.
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
                    name="resetOption"
                    checked={resetPwdMode === 'random'}
                    onChange={() => setResetPwdMode('random')}
                  />
                  <span>Tự động tạo mật khẩu ngẫu nhiên an toàn (Khuyến nghị)</span>
                </label>
                <label className="flex items-center gap-2 text-sm text-slate-700 cursor-pointer">
                  <input
                    type="radio"
                    name="resetOption"
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
                  onClick={() => setResetPwdUser(null)}
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
                Tài khoản: <strong>{tempPasswordResult.userName}</strong> ({tempPasswordResult.userEmail})
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
                  <span>LƯU Ý BẢO MẬT QUAN TRỌNG:</span>
                </div>
                <ul className="list-disc pl-4 space-y-1 text-amber-800/90 leading-relaxed">
                  <li>Mật khẩu tạm thời này chỉ hiển thị <strong>DUY NHẤT một lần</strong> trên màn hình này.</li>
                  <li>Sau khi đóng hộp thoại, hệ thống sẽ <strong>KHÔNG THỂ hiển thị lại</strong> mật khẩu này.</li>
                  <li>Người dùng bắt buộc phải đổi mật khẩu ngay ở lần đăng nhập tiếp theo.</li>
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

      {/* 5. DRAWER / MODAL CHI TIẾT & LỊCH SỬ HOẠT ĐỘNG */}
      {detailUser && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm flex justify-end">
          <div className="bg-white w-full max-w-xl h-full shadow-2xl flex flex-col border-l border-slate-200 overflow-hidden animate-slideInRight">
            {/* Drawer Header */}
            <div className="p-5 border-b border-slate-200 bg-slate-50 flex items-center justify-between">
              <div>
                <div className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">
                  CHI TIẾT TÀI KHOẢN #{detailUser.id}
                </div>
                <h3 className="text-lg font-bold text-slate-800 mt-0.5">{detailUser.full_name}</h3>
              </div>
              <button
                type="button"
                className="p-1.5 text-slate-400 hover:text-slate-600 rounded-lg hover:bg-slate-200 transition-colors"
                onClick={() => setDetailUser(null)}
              >
                <X size={20} />
              </button>
            </div>

            {/* Drawer Body */}
            <div className="flex-1 overflow-y-auto p-6 space-y-6">
              {/* Profile Card */}
              <div className="p-4 bg-slate-50 border border-slate-200 rounded-xl space-y-3">
                <div className="flex items-center justify-between pb-3 border-b border-slate-200">
                  <span className="text-xs font-semibold text-slate-500">Trạng thái tài khoản:</span>
                  <StatusBadge
                    value={detailUser.is_active ? 'ACTIVE' : 'INACTIVE'}
                    tone={detailUser.is_active ? 'success' : 'danger'}
                    showDot
                  />
                </div>

                <div className="grid grid-cols-2 gap-3 text-xs">
                  <div>
                    <span className="text-slate-500 block">Tên đăng nhập / Email:</span>
                    <strong className="text-slate-800 font-mono text-[13px]">{detailUser.email}</strong>
                  </div>
                  <div>
                    <span className="text-slate-500 block">Số điện thoại:</span>
                    <strong className="text-slate-800">{detailUser.phone || 'Chưa cập nhật'}</strong>
                  </div>
                  <div>
                    <span className="text-slate-500 block">Vai trò:</span>
                    <strong className="text-slate-800">{detailUser.role}</strong>
                  </div>
                  <div>
                    <span className="text-slate-500 block">Kho làm việc:</span>
                    <strong className="text-slate-800">{detailUser.warehouse_name || 'Toàn hệ thống'}</strong>
                  </div>
                  <div>
                    <span className="text-slate-500 block">Ngày tạo:</span>
                    <span className="text-slate-700">
                      {detailUser.created_at ? new Date(detailUser.created_at).toLocaleString('vi-VN') : '—'}
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-500 block">Đăng nhập gần nhất:</span>
                    <span className="text-slate-700">
                      {detailUser.last_login_at ? new Date(detailUser.last_login_at).toLocaleString('vi-VN') : 'Chưa đăng nhập'}
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-500 block">Người tạo:</span>
                    <span className="text-slate-700">{detailUser.created_by_name || 'Hệ thống'}</span>
                  </div>
                  <div>
                    <span className="text-slate-500 block">Yêu cầu đổi mật khẩu:</span>
                    <span className={detailUser.must_change_password ? 'text-amber-600 font-bold' : 'text-slate-700'}>
                      {detailUser.must_change_password ? 'Có (Bắt buộc)' : 'Không'}
                    </span>
                  </div>
                </div>

                {/* Quick actions inside drawer */}
                <div className="pt-3 border-t border-slate-200 flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => {
                      setDetailUser(null)
                      handleOpenResetPwd(detailUser)
                    }}
                    className="flex-1 py-1.5 px-3 bg-amber-50 hover:bg-amber-100 text-amber-800 border border-amber-300 rounded-lg text-xs font-semibold flex items-center justify-center gap-1.5"
                  >
                    <KeyRound size={13} />
                    <span>Đặt lại mật khẩu</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setDetailUser(null)
                      handleOpenEdit(detailUser)
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
                    <h4 className="font-bold text-slate-800 text-sm">Nhật Ký Hoạt Động & Đăng Nhập</h4>
                  </div>
                  <span className="text-xs text-slate-500">{userActivityLogs.length} sự kiện</span>
                </div>

                {loadingActivity ? (
                  <div className="p-8 text-center text-slate-400 text-xs">
                    <RefreshCw size={18} className="spin mx-auto mb-2" />
                    Đang tải nhật ký...
                  </div>
                ) : userActivityLogs.length === 0 ? (
                  <div className="p-8 text-center text-slate-400 text-xs bg-slate-50 rounded-xl border border-slate-200">
                    Chưa có nhật ký hoạt động nào được ghi nhận cho tài khoản này.
                  </div>
                ) : (
                  <div className="space-y-2.5">
                    {userActivityLogs.map((log) => (
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
                          <span>Người thực hiện: <strong>{log.user_name || 'Hệ thống'}</strong></span>
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
