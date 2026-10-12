import { useEffect, useState } from 'react'
import {
  Users,
  UserPlus,
  Lock,
  Unlock,
  Mail,
  Phone,
  ShieldCheck,
  X,
  AlertCircle,
  CheckCircle2,
  UserCheck,
  UserX,
} from 'lucide-react'
import { api } from '../../services/api'
import type { User } from '../../types'

export function WarehouseStaffPage() {
  const [staffList, setStaffList] = useState<User[]>([])
  const [loading, setLoading] = useState(true)

  // Create Modal
  const [showModal, setShowModal] = useState(false)
  const [creating, setCreating] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)
  const [formData, setFormData] = useState({
    full_name: '',
    email: '',
    phone: '',
    password: '',
  })

  const fetchStaff = () => {
    setLoading(true)
    api<User[]>('/warehouse-portal/staff')
      .then((res) => setStaffList(res || []))
      .catch((err) => console.error(err))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    fetchStaff()
  }, [])

  const handleToggleStatus = async (staffId: number, currentActive: boolean, staffName: string) => {
    const action = currentActive ? 'khóa' : 'mở khóa'
    if (!window.confirm(`Bạn có chắc chắn muốn ${action} tài khoản nhân viên "${staffName}"?`)) return

    try {
      await api(`/warehouse-portal/staff/${staffId}/toggle-status`, { method: 'PATCH' })
      fetchStaff()
    } catch (err: any) {
      alert(err?.message || 'Không thể thay đổi trạng thái nhân viên')
    }
  }

  const handleCreateStaff = async (e: React.FormEvent) => {
    e.preventDefault()
    setFormError(null)

    if (!formData.full_name.trim() || !formData.email.trim() || !formData.password.trim()) {
      setFormError('Vui lòng điền đầy đủ họ tên, email và mật khẩu')
      return
    }

    if (formData.password.length < 8) {
      setFormError('Mật khẩu nhân viên tối thiểu 8 ký tự')
      return
    }

    setCreating(true)
    try {
      await api('/warehouse-portal/staff', {
        method: 'POST',
        body: JSON.stringify(formData),
      })
      setShowModal(false)
      setFormData({ full_name: '', email: '', phone: '', password: '' })
      fetchStaff()
      alert('Tạo tài khoản Nhân Viên Kho mới thành công!')
    } catch (err: any) {
      setFormError(err?.message || 'Không thể tạo tài khoản nhân viên')
    } finally {
      setCreating(false)
    }
  }

  const activeCount = staffList.filter((s) => s.is_active).length
  const lockedCount = staffList.filter((s) => !s.is_active).length

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
            Nhân Viên Trực Thuộc Kho
          </h1>
          <p style={{ margin: '4px 0 0', fontSize: '13px', color: '#64748b' }}>
            Cấp tài khoản, phân quyền soạn hàng, đóng gói và giám sát trạng thái nhân viên
          </p>
        </div>

        <button
          type="button"
          onClick={() => {
            setFormError(null)
            setShowModal(true)
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
            transition: 'transform 0.15s ease, box-shadow 0.15s ease',
          }}
          onMouseEnter={(e) => (e.currentTarget.style.transform = 'translateY(-1px)')}
          onMouseLeave={(e) => (e.currentTarget.style.transform = 'translateY(0)')}
        >
          <UserPlus size={16} /> Thêm Nhân Viên Kho
        </button>
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
          Đang tải danh sách nhân sự trực thuộc kho…
        </div>
      ) : staffList.length === 0 ? (
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
            Chi nhánh hiện chưa có nhân viên nào
          </h3>
          <p style={{ margin: '6px 0 20px', fontSize: '13px', color: '#64748b' }}>
            Hãy bấm nút bên dưới để cấp tài khoản đầu tiên cho nhân viên soạn & đóng gói hàng.
          </p>
          <button
            type="button"
            onClick={() => {
              setFormError(null)
              setShowModal(true)
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
            + Thêm Nhân Viên Kho
          </button>
        </div>
      ) : (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))',
            gap: '18px',
          }}
        >
          {staffList.map((staff) => {
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
                onMouseEnter={(e) => {
                  e.currentTarget.style.transform = 'translateY(-2px)'
                  e.currentTarget.style.boxShadow = '0 8px 16px rgba(0,0,0,0.06)'
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.transform = 'translateY(0)'
                  e.currentTarget.style.boxShadow = '0 2px 6px rgba(0,0,0,0.03)'
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
                      <div style={{ marginTop: '3px' }}>
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
                          Nhân Viên Soạn Hàng (STAFF)
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Status Badge */}
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
                </div>

                {/* Card Footer: Action Button */}
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', paddingTop: '8px' }}>
                  <button
                    type="button"
                    onClick={() => handleToggleStatus(staff.id, staff.is_active, staff.full_name)}
                    style={{
                      padding: '7px 14px',
                      borderRadius: '9px',
                      fontSize: '12px',
                      fontWeight: 700,
                      border: staff.is_active ? '1px solid #fecaca' : '1px solid #a7f3d0',
                      background: staff.is_active ? '#fff1f2' : '#ecfdf5',
                      color: staff.is_active ? '#b91c1c' : '#047857',
                      cursor: 'pointer',
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '6px',
                      transition: 'all 0.15s ease',
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.background = staff.is_active ? '#fee2e2' : '#d1fae5'
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.background = staff.is_active ? '#fff1f2' : '#ecfdf5'
                    }}
                  >
                    {staff.is_active ? (
                      <>
                        <Lock size={13} /> Khóa tài khoản
                      </>
                    ) : (
                      <>
                        <Unlock size={13} /> Mở khóa tài khoản
                      </>
                    )}
                  </button>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* Create Staff Modal */}
      {showModal && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(15, 23, 42, 0.65)',
            backdropFilter: 'blur(4px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 60,
            padding: '20px',
          }}
        >
          <div
            style={{
              background: 'white',
              borderRadius: '20px',
              maxWidth: '480px',
              width: '100%',
              padding: '28px',
              boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.25)',
              display: 'flex',
              flexDirection: 'column',
              gap: '20px',
            }}
          >
            {/* Modal Header */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid #e2e8f0', paddingBottom: '14px' }}>
              <div>
                <h3 style={{ margin: 0, fontSize: '18px', fontWeight: 900, color: '#0f172a' }}>
                  Cấp Tài Khoản Nhân Viên Kho
                </h3>
                <p style={{ margin: '4px 0 0', fontSize: '12px', color: '#64748b' }}>
                  Tài khoản mới sẽ trực thuộc kho hiện tại để thực hiện soạn và đóng gói
                </p>
              </div>
              <button
                type="button"
                onClick={() => setShowModal(false)}
                style={{ background: 'none', border: 'none', color: '#94a3b8', cursor: 'pointer', padding: '4px' }}
              >
                <X size={20} />
              </button>
            </div>

            {/* Error Notification */}
            {formError && (
              <div
                style={{
                  background: '#fef2f2',
                  border: '1px solid #fecaca',
                  borderRadius: '10px',
                  padding: '12px 14px',
                  color: '#b91c1c',
                  fontSize: '12.5px',
                  fontWeight: 600,
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                }}
              >
                <AlertCircle size={16} style={{ flexShrink: 0 }} /> {formError}
              </div>
            )}

            {/* Form */}
            <form onSubmit={handleCreateStaff} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '11px', fontWeight: 800, color: '#334155', textTransform: 'uppercase', marginBottom: '6px' }}>
                  Họ và tên nhân viên *
                </label>
                <input
                  type="text"
                  placeholder="VD: Trần Văn Bình"
                  value={formData.full_name}
                  onChange={(e) => setFormData({ ...formData, full_name: e.target.value })}
                  style={{
                    width: '100%',
                    padding: '10px 14px',
                    borderRadius: '10px',
                    border: '1.5px solid #cbd5e1',
                    fontSize: '13.5px',
                    outline: 'none',
                    boxSizing: 'border-box',
                  }}
                  required
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '11px', fontWeight: 800, color: '#334155', textTransform: 'uppercase', marginBottom: '6px' }}>
                  Email đăng nhập *
                </label>
                <input
                  type="email"
                  placeholder="VD: nv.binh@pharmatrust.vn"
                  value={formData.email}
                  onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                  style={{
                    width: '100%',
                    padding: '10px 14px',
                    borderRadius: '10px',
                    border: '1.5px solid #cbd5e1',
                    fontSize: '13.5px',
                    outline: 'none',
                    boxSizing: 'border-box',
                  }}
                  required
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '11px', fontWeight: 800, color: '#334155', textTransform: 'uppercase', marginBottom: '6px' }}>
                  Số điện thoại liên hệ
                </label>
                <input
                  type="text"
                  placeholder="VD: 0987654321"
                  value={formData.phone}
                  onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                  style={{
                    width: '100%',
                    padding: '10px 14px',
                    borderRadius: '10px',
                    border: '1.5px solid #cbd5e1',
                    fontSize: '13.5px',
                    outline: 'none',
                    boxSizing: 'border-box',
                  }}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '11px', fontWeight: 800, color: '#334155', textTransform: 'uppercase', marginBottom: '6px' }}>
                  Mật khẩu khởi tạo * (Tối thiểu 8 ký tự)
                </label>
                <input
                  type="password"
                  placeholder="Nhập mật khẩu cho nhân viên"
                  value={formData.password}
                  onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                  style={{
                    width: '100%',
                    padding: '10px 14px',
                    borderRadius: '10px',
                    border: '1.5px solid #cbd5e1',
                    fontSize: '13.5px',
                    outline: 'none',
                    boxSizing: 'border-box',
                  }}
                  required
                />
              </div>

              {/* Form Actions */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: '10px', paddingTop: '10px', borderTop: '1px solid #e2e8f0' }}>
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  style={{
                    padding: '10px 18px',
                    borderRadius: '10px',
                    border: '1px solid #cbd5e1',
                    background: 'white',
                    color: '#64748b',
                    fontSize: '13px',
                    fontWeight: 700,
                    cursor: 'pointer',
                  }}
                >
                  Hủy
                </button>
                <button
                  type="submit"
                  disabled={creating}
                  style={{
                    padding: '10px 22px',
                    borderRadius: '10px',
                    border: 'none',
                    background: 'linear-gradient(135deg, #059669, #047857)',
                    color: 'white',
                    fontSize: '13px',
                    fontWeight: 800,
                    cursor: 'pointer',
                    boxShadow: '0 2px 8px rgba(5, 150, 105, 0.3)',
                  }}
                >
                  {creating ? 'Đang tạo…' : 'Cấp tài khoản'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
