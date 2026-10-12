import { useEffect, useMemo, useState } from 'react'
import {
  Users,
  ShieldCheck,
  UserCheck,
  Award,
  RefreshCw,
  Phone,
  Mail,
  Calendar,
  Lock,
  Unlock,
  Building2,
  Plus,
  UserPlus,
  Check,
  X,
  AlertCircle,
} from 'lucide-react'
import { AdminPageHeader } from '../components/AdminPageHeader'
import { StatCard, StatGrid } from '../components/StatCard'
import { FilterBar } from '../components/FilterBar'
import { StatusBadge } from '../components/StatusBadge'
import { PaginationBar } from '../components/PaginationBar'
import { api } from '../services/api'
import { useAuth } from '../services/auth'
import type { User, WarehouseItem, UserRole } from '../types'

export function UsersPage() {
  const { user: currentUser } = useAuth()
  const [users, setUsers] = useState<User[]>([])
  const [warehouses, setWarehouses] = useState<WarehouseItem[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [roleFilter, setRoleFilter] = useState<string>('ALL')
  const [warehouseFilter, setWarehouseFilter] = useState<string>('ALL')

  // Create User Modal state
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [creating, setCreating] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)
  const [formData, setFormData] = useState({
    full_name: '',
    email: '',
    phone: '',
    password: '',
    role: (currentUser?.role === 'WAREHOUSE_MANAGER' ? 'WAREHOUSE_STAFF' : 'WAREHOUSE_MANAGER') as UserRole,
    warehouse_id: currentUser?.warehouse_id || '',
  })

  // Assign Warehouse Modal state
  const [assignUser, setAssignUser] = useState<User | null>(null)
  const [selectedWarehouseId, setSelectedWarehouseId] = useState<number | string>('')
  const [assigning, setAssigning] = useState(false)

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

  const handleToggleStatus = async (targetUser: User) => {
    const actionLabel = targetUser.is_active ? 'khóa' : 'mở khóa'
    if (!window.confirm(`Bạn có chắc chắn muốn ${actionLabel} tài khoản "${targetUser.full_name}"?`)) {
      return
    }

    try {
      const updated = await api<User>(`/users/${targetUser.id}/status`, { method: 'PATCH' })
      if (updated) {
        setUsers((prev) => prev.map((u) => (u.id === targetUser.id ? updated : u)))
      }
    } catch (err: any) {
      alert(err?.message || 'Thao tác cập nhật trạng thái thất bại')
    }
  }

  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault()
    setCreateError(null)

    if (!formData.full_name.trim() || !formData.email.trim() || !formData.password.trim()) {
      setCreateError('Vui lòng điền đầy đủ họ tên, email và mật khẩu')
      return
    }

    setCreating(true)
    try {
      const payload: any = {
        full_name: formData.full_name.trim(),
        email: formData.email.trim(),
        password: formData.password,
        role: formData.role,
        phone: formData.phone.trim() || null,
      }
      if (formData.warehouse_id) {
        payload.warehouse_id = Number(formData.warehouse_id)
      }

      const created = await api<User>('/users', {
        method: 'POST',
        body: JSON.stringify(payload),
      })

      if (created) {
        setShowCreateModal(false)
        setFormData({
          full_name: '',
          email: '',
          phone: '',
          password: '',
          role: (currentUser?.role === 'WAREHOUSE_MANAGER' ? 'WAREHOUSE_STAFF' : 'WAREHOUSE_MANAGER') as UserRole,
          warehouse_id: currentUser?.warehouse_id || '',
        })
        fetchUsers()
      }
    } catch (err: any) {
      setCreateError(err?.message || 'Tạo tài khoản thất bại')
    } finally {
      setCreating(false)
    }
  }

  const handleAssignWarehouse = async () => {
    if (!assignUser) return
    setAssigning(true)
    try {
      let updated: User
      if (selectedWarehouseId) {
        updated = await api<User>(`/users/${assignUser.id}/warehouse/${selectedWarehouseId}`, { method: 'POST' })
      } else {
        updated = await api<User>(`/users/${assignUser.id}/warehouse`, { method: 'DELETE' })
      }
      setUsers((prev) => prev.map((u) => (u.id === assignUser.id ? updated : u)))
      setAssignUser(null)
    } catch (err: any) {
      alert(err?.message || 'Cập nhật kho thất bại')
    } finally {
      setAssigning(false)
    }
  }

  const filteredUsers = users.filter((u) => {
    const matchesRole = roleFilter === 'ALL' || u.role === roleFilter
    const matchesWh =
      warehouseFilter === 'ALL' ||
      (warehouseFilter === 'NONE' && !u.warehouse_id) ||
      String(u.warehouse_id) === warehouseFilter
    const term = search.toLowerCase().trim()
    const matchesSearch =
      !term ||
      u.full_name.toLowerCase().includes(term) ||
      u.email.toLowerCase().includes(term) ||
      (u.phone && u.phone.includes(term)) ||
      (u.warehouse_name && u.warehouse_name.toLowerCase().includes(term))
    return matchesRole && matchesWh && matchesSearch
  })

  // Phân trang
  const [currentPage, setCurrentPage] = useState<number>(1)
  const [pageSize, setPageSize] = useState<number>(15)

  useEffect(() => {
    setCurrentPage(1)
  }, [search, roleFilter, warehouseFilter])

  const totalPages = Math.max(1, Math.ceil(filteredUsers.length / pageSize))
  const displayedUsers = useMemo(() => {
    const start = (currentPage - 1) * pageSize
    return filteredUsers.slice(start, start + pageSize)
  }, [filteredUsers, currentPage, pageSize])

  const totalUsers = users.length
  const totalAdmins = users.filter((u) => u.role === 'ADMIN').length
  const totalWarehouseTeam = users.filter((u) => u.role === 'WAREHOUSE_MANAGER' || u.role === 'WAREHOUSE_STAFF').length
  const totalCustomers = users.filter((u) => u.role === 'CUSTOMER').length

  const canCreateUser = currentUser?.role === 'ADMIN' || currentUser?.role === 'WAREHOUSE_MANAGER'

  return (
    <div className="page">
      <AdminPageHeader
        title="Quản lý người dùng & Phân quyền Kho"
        eyebrow="QUẢN TRỊ HỆ THỐNG • Danh sách tài khoản"
        subtitle="Quản lý định danh, gán kho chi nhánh, và cấp quyền hạn theo mô hình RBAC toàn quốc."
        badge={totalUsers > 0 ? <span className="stat-card-badge">{totalUsers} tài khoản</span> : undefined}
        actions={
          <div className="flex items-center gap-2">
            <button
              type="button"
              className="admin-button button-secondary"
              onClick={fetchUsers}
              disabled={loading}
            >
              <RefreshCw size={14} className={loading ? 'spin' : ''} />
              <span>Làm mới</span>
            </button>
            {canCreateUser && (
              <button
                type="button"
                className="admin-button button-primary"
                onClick={() => {
                  setCreateError(null)
                  setFormData({
                    full_name: '',
                    email: '',
                    phone: '',
                    password: '',
                    role: currentUser?.role === 'WAREHOUSE_MANAGER' ? 'WAREHOUSE_STAFF' : 'WAREHOUSE_MANAGER',
                    warehouse_id: currentUser?.warehouse_id || '',
                  })
                  setShowCreateModal(true)
                }}
              >
                <UserPlus size={14} />
                <span>
                  {currentUser?.role === 'WAREHOUSE_MANAGER' ? 'Thêm nhân viên kho' : 'Tạo tài khoản mới'}
                </span>
              </button>
            )}
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
          subtext="Tài khoản trên toàn hệ thống"
          loading={loading}
        />
        <StatCard
          label="Quản trị viên"
          value={totalAdmins}
          icon={ShieldCheck}
          tone="amber"
          subtext="Toàn quyền vận hành"
          loading={loading}
        />
        <StatCard
          label="Nhân sự Kho vận"
          value={totalWarehouseTeam}
          icon={Building2}
          tone="emerald"
          subtext="Quản lý & Nhân viên soạn hàng"
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

      {/* Standardized FilterBar */}
      <FilterBar
        searchValue={search}
        onSearchChange={setSearch}
        searchPlaceholder="Tìm theo họ tên, email, số điện thoại hoặc tên kho..."
        totalCount={totalUsers}
        filteredCount={filteredUsers.length}
        unitLabel="tài khoản"
        onRefresh={fetchUsers}
        isRefreshing={loading}
      >
        <select
          value={roleFilter}
          onChange={(e) => setRoleFilter(e.target.value)}
          style={{ minWidth: '180px' }}
        >
          <option value="ALL">Tất cả vai trò ({totalUsers})</option>
          <option value="ADMIN">Quản trị viên ({totalAdmins})</option>
          <option value="WAREHOUSE_MANAGER">Quản lý kho</option>
          <option value="WAREHOUSE_STAFF">Nhân viên kho</option>
          <option value="CUSTOMER">Khách hàng ({totalCustomers})</option>
          <option value="DATA_REVIEWER">Kiểm duyệt viên</option>
          <option value="VIEWER">Nhân viên tra cứu</option>
        </select>

        {warehouses.length > 0 && (
          <select
            value={warehouseFilter}
            onChange={(e) => setWarehouseFilter(e.target.value)}
            style={{ minWidth: '220px' }}
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
      </FilterBar>

      {/* Users Table */}
      <div className="admin-data-table-container">
        <div className="admin-table-wrap">
          <table className="admin-table">
            <thead>
              <tr>
                <th style={{ minWidth: '220px' }}>Người dùng</th>
                <th style={{ minWidth: '220px' }}>Thông tin liên hệ</th>
                <th style={{ width: '150px' }}>Vai trò</th>
                <th style={{ minWidth: '200px' }}>Kho trực thuộc</th>
                <th style={{ width: '130px', textAlign: 'center' }}>Trạng thái</th>
                <th style={{ width: '160px' }}>Đăng nhập cuối</th>
                <th style={{ width: '120px', textAlign: 'center' }}>Thao tác</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={7} style={{ padding: '40px 16px', textAlign: 'center', color: '#64748b' }}>
                    <RefreshCw size={20} className="spin" style={{ margin: '0 auto 8px', display: 'block' }} />
                    Đang tải danh sách tài khoản...
                  </td>
                </tr>
              ) : filteredUsers.length === 0 ? (
                <tr>
                  <td colSpan={7} style={{ padding: '40px 16px', textAlign: 'center', color: '#64748b' }}>
                    Không tìm thấy tài khoản nào khớp với bộ lọc hiện tại.
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
                            <strong style={{ display: 'block', color: '#0f172a', fontSize: '13px' }}>
                              {u.full_name}
                              {isSelf && (
                                <span className="ml-1.5 px-1.5 py-0.5 rounded text-[10px] bg-slate-100 text-slate-600 font-normal">
                                  (Bạn)
                                </span>
                              )}
                            </strong>
                            <small style={{ color: '#94a3b8', fontSize: '11px' }}>ID: #{u.id}</small>
                          </div>
                        </div>
                      </td>

                      <td>
                        <div style={{ fontSize: '12.5px' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#334155' }}>
                            <Mail size={13} style={{ color: '#94a3b8', flexShrink: 0 }} /> {u.email}
                          </div>
                          {u.phone && (
                            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#64748b', marginTop: '3px' }}>
                              <Phone size={13} style={{ color: '#94a3b8', flexShrink: 0 }} /> {u.phone}
                            </div>
                          )}
                        </div>
                      </td>

                      <td>
                        <StatusBadge value={u.role} showDot />
                      </td>

                      <td>
                        {u.warehouse_name ? (
                          <div className="flex items-center gap-1.5">
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
                              <Building2 size={12} />
                              <span className="truncate max-w-[170px]" title={u.warehouse_name}>
                                {u.warehouse_name}
                              </span>
                            </span>
                            {currentUser?.role === 'ADMIN' && (
                              <button
                                type="button"
                                className="text-[11px] text-blue-600 hover:underline ml-1"
                                onClick={() => {
                                  setAssignUser(u)
                                  setSelectedWarehouseId(u.warehouse_id || '')
                                }}
                              >
                                Đổi
                              </button>
                            )}
                          </div>
                        ) : isWarehouse ? (
                          <div className="flex items-center gap-1">
                            <span className="text-xs text-amber-600 font-medium">⚠️ Chưa gán kho</span>
                            {currentUser?.role === 'ADMIN' && (
                              <button
                                type="button"
                                className="text-[11px] text-blue-600 hover:underline ml-1"
                                onClick={() => {
                                  setAssignUser(u)
                                  setSelectedWarehouseId('')
                                }}
                              >
                                Gán kho
                              </button>
                            )}
                          </div>
                        ) : (
                          <span className="text-xs text-slate-400">Toàn hệ thống</span>
                        )}
                      </td>

                      <td style={{ textAlign: 'center' }}>
                        <StatusBadge
                          value={u.is_active ? 'ACTIVE' : 'INACTIVE'}
                          tone={u.is_active ? 'success' : 'danger'}
                          showDot
                        />
                      </td>

                      <td>
                        <div style={{ fontSize: '12px', color: '#475569', display: 'flex', alignItems: 'center', gap: '5px' }}>
                          <Calendar size={13} style={{ color: '#94a3b8', flexShrink: 0 }} />
                          {u.last_login_at
                            ? new Date(u.last_login_at).toLocaleString('vi-VN')
                            : 'Chưa đăng nhập'}
                        </div>
                      </td>

                      <td style={{ textAlign: 'center' }}>
                        {!isSelf && (
                          <button
                            type="button"
                            className={`p-1.5 rounded transition-colors ${
                              u.is_active
                                ? 'text-amber-600 hover:bg-amber-50'
                                : 'text-emerald-600 hover:bg-emerald-50'
                            }`}
                            title={u.is_active ? 'Khóa tài khoản' : 'Mở khóa tài khoản'}
                            onClick={() => handleToggleStatus(u)}
                          >
                            {u.is_active ? <Lock size={15} /> : <Unlock size={15} />}
                          </button>
                        )}
                      </td>
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </div>
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

      {/* CREATE USER MODAL */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-lg border border-slate-200 overflow-hidden">
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100 bg-slate-50">
              <div className="flex items-center gap-2">
                <UserPlus size={18} className="text-blue-600" />
                <h3 className="font-semibold text-slate-800 text-base">
                  {currentUser?.role === 'WAREHOUSE_MANAGER' ? 'Thêm Nhân Viên Kho Mới' : 'Tạo Tài Khoản Mới'}
                </h3>
              </div>
              <button
                type="button"
                className="p-1 text-slate-400 hover:text-slate-600 rounded-lg hover:bg-slate-200 transition-colors"
                onClick={() => setShowCreateModal(false)}
              >
                <X size={18} />
              </button>
            </div>

            <form onSubmit={handleCreateUser} className="p-6 space-y-4">
              {createError && (
                <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-600 flex items-center gap-2">
                  <AlertCircle size={16} className="shrink-0" />
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
                  value={formData.full_name}
                  onChange={(e) => setFormData({ ...formData, full_name: e.target.value })}
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
                    value={formData.email}
                    onChange={(e) => setFormData({ ...formData, email: e.target.value })}
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
                    value={formData.phone}
                    onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                  Mật khẩu khởi tạo <span className="text-red-500">*</span>
                </label>
                <input
                  type="password"
                  required
                  minLength={8}
                  placeholder="Tối thiểu 8 ký tự"
                  className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                  value={formData.password}
                  onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                    Vai trò <span className="text-red-500">*</span>
                  </label>
                  {currentUser?.role === 'WAREHOUSE_MANAGER' ? (
                    <input
                      type="text"
                      disabled
                      value="Nhân viên kho (WAREHOUSE_STAFF)"
                      className="w-full px-3 py-2 text-sm border border-slate-200 bg-slate-100 rounded-lg text-slate-600"
                    />
                  ) : (
                    <select
                      className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                      value={formData.role}
                      onChange={(e) => setFormData({ ...formData, role: e.target.value as UserRole })}
                    >
                      <option value="WAREHOUSE_MANAGER">Quản lý kho</option>
                      <option value="WAREHOUSE_STAFF">Nhân viên kho</option>
                      <option value="DATA_REVIEWER">Kiểm duyệt viên Dữ liệu</option>
                      <option value="VIEWER">Nhân viên tra cứu</option>
                      <option value="ADMIN">Quản trị viên toàn hệ thống</option>
                    </select>
                  )}
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                    Kho trực thuộc
                  </label>
                  {currentUser?.role === 'WAREHOUSE_MANAGER' ? (
                    <input
                      type="text"
                      disabled
                      value={currentUser.warehouse_name || 'Kho của bạn'}
                      className="w-full px-3 py-2 text-sm border border-slate-200 bg-slate-100 rounded-lg text-slate-600"
                    />
                  ) : (
                    <select
                      className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                      value={formData.warehouse_id}
                      onChange={(e) => setFormData({ ...formData, warehouse_id: e.target.value })}
                    >
                      <option value="">-- Không gán kho --</option>
                      {warehouses.map((wh) => (
                        <option key={wh.id} value={wh.id}>
                          {wh.code} - {wh.name}
                        </option>
                      ))}
                    </select>
                  )}
                </div>
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
                  className="px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg disabled:opacity-50 transition-colors flex items-center gap-1.5"
                >
                  {creating && <RefreshCw size={14} className="spin" />}
                  <span>{creating ? 'Đang tạo...' : 'Tạo tài khoản'}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ASSIGN WAREHOUSE MODAL (ADMIN ONLY) */}
      {assignUser && (
        <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-md border border-slate-200 overflow-hidden">
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100 bg-slate-50">
              <div className="flex items-center gap-2">
                <Building2 size={18} className="text-emerald-600" />
                <h3 className="font-semibold text-slate-800 text-base">Gán Kho Trực Thuộc</h3>
              </div>
              <button
                type="button"
                className="p-1 text-slate-400 hover:text-slate-600 rounded-lg hover:bg-slate-200 transition-colors"
                onClick={() => setAssignUser(null)}
              >
                <X size={18} />
              </button>
            </div>

            <div className="p-6 space-y-4">
              <p className="text-sm text-slate-600">
                Chọn kho hàng phân công cho nhân viên <strong>{assignUser.full_name}</strong> (Vai trò: {assignUser.role}):
              </p>

              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
                  Kho hàng
                </label>
                <select
                  className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-emerald-500"
                  value={selectedWarehouseId}
                  onChange={(e) => setSelectedWarehouseId(e.target.value)}
                >
                  <option value="">-- Thu hồi gán kho (Không thuộc kho nào) --</option>
                  {warehouses.map((wh) => (
                    <option key={wh.id} value={wh.id}>
                      {wh.code} - {wh.name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-100">
                <button
                  type="button"
                  className="px-4 py-2 text-sm text-slate-600 hover:bg-slate-100 rounded-lg transition-colors"
                  onClick={() => setAssignUser(null)}
                >
                  Hủy
                </button>
                <button
                  type="button"
                  disabled={assigning}
                  className="px-4 py-2 text-sm font-medium text-white bg-emerald-600 hover:bg-emerald-700 rounded-lg disabled:opacity-50 transition-colors flex items-center gap-1.5"
                  onClick={handleAssignWarehouse}
                >
                  {assigning && <RefreshCw size={14} className="spin" />}
                  <span>{assigning ? 'Đang lưu...' : 'Lưu phân công'}</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
