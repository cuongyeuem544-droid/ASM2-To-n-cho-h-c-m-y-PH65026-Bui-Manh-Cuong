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
} from 'lucide-react'
import { AdminPageHeader } from '../components/AdminPageHeader'
import { StatCard, StatGrid } from '../components/StatCard'
import { FilterBar } from '../components/FilterBar'
import { StatusBadge } from '../components/StatusBadge'
import { PaginationBar } from '../components/PaginationBar'
import { api } from '../services/api'
import type { User } from '../types'

export function UsersPage() {
  const [users, setUsers] = useState<User[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [roleFilter, setRoleFilter] = useState<string>('ALL')

  const fetchUsers = () => {
    setLoading(true)
    api<User[]>('/users')
      .then((data) => setUsers(data))
      .catch((err) => console.error('Failed to load users:', err))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    fetchUsers()
  }, [])

  const filteredUsers = users.filter((u) => {
    const matchesRole = roleFilter === 'ALL' || u.role === roleFilter
    const term = search.toLowerCase().trim()
    const matchesSearch =
      !term ||
      u.full_name.toLowerCase().includes(term) ||
      u.email.toLowerCase().includes(term) ||
      (u.phone && u.phone.includes(term))
    return matchesRole && matchesSearch
  })

  // Phân trang
  const [currentPage, setCurrentPage] = useState<number>(1)
  const [pageSize, setPageSize] = useState<number>(15)

  useEffect(() => {
    setCurrentPage(1)
  }, [search, roleFilter])

  const totalPages = Math.max(1, Math.ceil(filteredUsers.length / pageSize))
  const displayedUsers = useMemo(() => {
    const start = (currentPage - 1) * pageSize
    return filteredUsers.slice(start, start + pageSize)
  }, [filteredUsers, currentPage, pageSize])

  const totalUsers = users.length
  const totalAdmins = users.filter((u) => u.role === 'ADMIN').length
  const totalCustomers = users.filter((u) => u.role === 'CUSTOMER').length
  const totalReviewers = users.filter((u) => u.role === 'DATA_REVIEWER').length

  return (
    <div className="page">
      <AdminPageHeader
        title="Quản lý người dùng & Phân quyền"
        eyebrow="QUẢN TRỊ HỆ THỐNG • Danh sách tài khoản"
        subtitle="Quản lý định danh, cấp phát quyền hạn giữa Ban quản trị và Khách hàng mua thuốc H4CARE."
        badge={totalUsers > 0 ? <span className="stat-card-badge">{totalUsers} tài khoản</span> : undefined}
        actions={
          <button
            type="button"
            className="admin-button button-secondary"
            onClick={fetchUsers}
            disabled={loading}
          >
            <RefreshCw size={14} className={loading ? 'spin' : ''} />
            <span>Làm mới danh sách</span>
          </button>
        }
      />

      {/* KPI Stats Grid */}
      <StatGrid columns={4}>
        <StatCard
          label="Tổng tài khoản"
          value={totalUsers}
          icon={Users}
          tone="blue"
          subtext="Toàn bộ tài khoản hệ thống"
          loading={loading}
        />
        <StatCard
          label="Quản trị viên"
          value={totalAdmins}
          icon={ShieldCheck}
          tone="amber"
          subtext="Toàn quyền vận hành hệ thống"
          loading={loading}
        />
        <StatCard
          label="Khách hàng thành viên"
          value={totalCustomers}
          icon={UserCheck}
          tone="emerald"
          subtext="Tài khoản mua hàng Storefront"
          loading={loading}
        />
        <StatCard
          label="Kiểm duyệt viên"
          value={totalReviewers}
          icon={Award}
          tone="purple"
          subtext="Thẩm định dữ liệu thuốc & dược"
          loading={loading}
        />
      </StatGrid>

      {/* Standardized FilterBar */}
      <FilterBar
        searchValue={search}
        onSearchChange={setSearch}
        searchPlaceholder="Tìm theo họ tên, email hoặc số điện thoại..."
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
          <option value="CUSTOMER">Khách hàng ({totalCustomers})</option>
          <option value="DATA_REVIEWER">Kiểm duyệt viên ({totalReviewers})</option>
          <option value="VIEWER">Nhân viên tra cứu</option>
        </select>
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
                <th style={{ width: '130px', textAlign: 'center' }}>Điểm tích lũy</th>
                <th style={{ width: '140px', textAlign: 'center' }}>Trạng thái</th>
                <th style={{ width: '170px' }}>Lần đăng nhập cuối</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={6} style={{ padding: '40px 16px', textAlign: 'center', color: '#64748b' }}>
                    <RefreshCw size={20} className="spin" style={{ margin: '0 auto 8px', display: 'block' }} />
                    Đang tải danh sách tài khoản...
                  </td>
                </tr>
              ) : filteredUsers.length === 0 ? (
                <tr>
                  <td colSpan={6} style={{ padding: '40px 16px', textAlign: 'center', color: '#64748b' }}>
                    Không tìm thấy tài khoản nào khớp với bộ lọc hiện tại.
                  </td>
                </tr>
              ) : (
                displayedUsers.map((u) => {
                  const isAdmin = u.role === 'ADMIN'
                  const isCustomer = u.role === 'CUSTOMER'
                  return (
                    <tr key={u.id}>
                      <td>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                          <div
                            style={{
                              width: '36px',
                              height: '36px',
                              borderRadius: '10px',
                              background: isAdmin ? '#fef3c7' : isCustomer ? '#dbeafe' : '#f1f5f9',
                              color: isAdmin ? '#b45309' : isCustomer ? '#1d4ed8' : '#475569',
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

                      <td style={{ textAlign: 'center' }}>
                        <span style={{ fontWeight: 700, color: '#0284c7', fontSize: '13px' }}>
                          {u.loyalty_points ? u.loyalty_points.toLocaleString('vi-VN') : 0}
                        </span>{' '}
                        <small style={{ color: '#94a3b8', fontSize: '11px' }}>điểm</small>
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
    </div>
  )
}
