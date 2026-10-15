import { useState } from 'react'
import { ShieldAlert, Lock, CheckCircle2, XCircle, LogOut, ArrowRight, Eye, EyeOff } from 'lucide-react'
import { api } from '../services/api'
import { useAuth } from '../services/auth'

export function ForceChangePasswordModal() {
  const { user, logout, updateUser } = useAuth()
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [showCurrent, setShowCurrent] = useState(false)
  const [showNew, setShowNew] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)

  if (!user || !user.must_change_password) {
    return null
  }

  const hasLength = newPassword.length >= 8
  const hasUpper = /[A-Z]/.test(newPassword)
  const hasLower = /[a-z]/.test(newPassword)
  const hasNumber = /[0-9]/.test(newPassword)
  const hasSpecial = /[^A-Za-z0-9]/.test(newPassword)
  const isMatch = newPassword.length > 0 && newPassword === confirmPassword
  const isStrong = hasLength && hasUpper && hasLower && hasNumber && hasSpecial

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)

    if (!currentPassword.trim()) {
      setError('Vui lòng nhập mật khẩu hiện tại (mật khẩu tạm thời).')
      return
    }

    if (!isStrong) {
      setError('Mật khẩu mới chưa đạt tiêu chuẩn bảo mật.')
      return
    }

    if (!isMatch) {
      setError('Mật khẩu xác nhận không trùng khớp.')
      return
    }

    setLoading(true)
    try {
      await api('/auth/change-password', {
        method: 'POST',
        body: JSON.stringify({
          current_password: currentPassword,
          new_password: newPassword,
        }),
      })

      setSuccess(true)
      setTimeout(() => {
        updateUser({
          ...user,
          must_change_password: false,
        })
      }, 1200)
    } catch (err: any) {
      setError(err?.message || 'Không thể đổi mật khẩu. Vui lòng kiểm tra lại mật khẩu hiện tại.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 9999,
        background: 'rgba(15, 23, 42, 0.85)',
        backdropFilter: 'blur(8px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '16px',
      }}
    >
      <div
        style={{
          background: 'white',
          borderRadius: '16px',
          boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.35)',
          width: '100%',
          maxWidth: '520px',
          overflow: 'hidden',
          border: '1px solid #cbd5e1',
          animation: 'fadeIn 0.2s ease-out',
        }}
      >
        {/* Header */}
        <div
          style={{
            background: 'linear-gradient(135deg, #0f766e 0%, #0d9488 100%)',
            color: 'white',
            padding: '24px',
            textAlign: 'center',
          }}
        >
          <div
            style={{
              width: '56px',
              height: '56px',
              borderRadius: '50%',
              background: 'rgba(255, 255, 255, 0.2)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              margin: '0 auto 12px',
            }}
          >
            <ShieldAlert size={32} color="#ffffff" />
          </div>
          <h2 style={{ margin: 0, fontSize: '20px', fontWeight: 800 }}>Yêu Cầu Đổi Mật Khẩu Khởi Tạo</h2>
          <p style={{ margin: '6px 0 0', fontSize: '13px', opacity: 0.9 }}>
            Tài khoản <strong>{user.email}</strong> đang sử dụng mật khẩu tạm thời. Vui lòng thiết lập mật khẩu mới an toàn để bắt đầu làm việc.
          </p>
        </div>

        {/* Content */}
        <form onSubmit={handleSubmit} style={{ padding: '24px' }}>
          {error && (
            <div
              style={{
                marginBottom: '16px',
                padding: '12px',
                borderRadius: '8px',
                background: '#fef2f2',
                border: '1px solid #fecaca',
                color: '#b91c1c',
                fontSize: '13px',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
              }}
            >
              <XCircle size={18} style={{ flexShrink: 0 }} />
              <span>{error}</span>
            </div>
          )}

          {success && (
            <div
              style={{
                marginBottom: '16px',
                padding: '12px',
                borderRadius: '8px',
                background: '#f0fdf4',
                border: '1px solid #bbf7d0',
                color: '#15803d',
                fontSize: '13px',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
              }}
            >
              <CheckCircle2 size={18} style={{ flexShrink: 0 }} />
              <span>Đổi mật khẩu thành công! Đang chuyển hướng...</span>
            </div>
          )}

          {/* Current Password */}
          <div style={{ marginBottom: '14px' }}>
            <label style={{ display: 'block', fontSize: '12px', fontWeight: 700, color: '#334155', marginBottom: '6px', textTransform: 'uppercase' }}>
              Mật khẩu tạm thời hiện tại <span style={{ color: '#ef4444' }}>*</span>
            </label>
            <div style={{ position: 'relative' }}>
              <input
                type={showCurrent ? 'text' : 'password'}
                required
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                placeholder="Nhập mật khẩu tạm thời được cấp"
                style={{
                  width: '100%',
                  padding: '10px 40px 10px 12px',
                  borderRadius: '8px',
                  border: '1px solid #cbd5e1',
                  fontSize: '14px',
                  outline: 'none',
                  boxSizing: 'border-box',
                }}
              />
              <button
                type="button"
                onClick={() => setShowCurrent(!showCurrent)}
                style={{
                  position: 'absolute',
                  right: '10px',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                  color: '#64748b',
                  padding: 0,
                }}
              >
                {showCurrent ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </div>

          {/* New Password */}
          <div style={{ marginBottom: '14px' }}>
            <label style={{ display: 'block', fontSize: '12px', fontWeight: 700, color: '#334155', marginBottom: '6px', textTransform: 'uppercase' }}>
              Mật khẩu mới an toàn <span style={{ color: '#ef4444' }}>*</span>
            </label>
            <div style={{ position: 'relative' }}>
              <input
                type={showNew ? 'text' : 'password'}
                required
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                placeholder="Nhập mật khẩu mới (tối thiểu 8 ký tự)"
                style={{
                  width: '100%',
                  padding: '10px 40px 10px 12px',
                  borderRadius: '8px',
                  border: '1px solid #cbd5e1',
                  fontSize: '14px',
                  outline: 'none',
                  boxSizing: 'border-box',
                }}
              />
              <button
                type="button"
                onClick={() => setShowNew(!showNew)}
                style={{
                  position: 'absolute',
                  right: '10px',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                  color: '#64748b',
                  padding: 0,
                }}
              >
                {showNew ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </div>

          {/* Confirm Password */}
          <div style={{ marginBottom: '16px' }}>
            <label style={{ display: 'block', fontSize: '12px', fontWeight: 700, color: '#334155', marginBottom: '6px', textTransform: 'uppercase' }}>
              Xác nhận mật khẩu mới <span style={{ color: '#ef4444' }}>*</span>
            </label>
            <input
              type="password"
              required
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              placeholder="Nhập lại mật khẩu mới"
              style={{
                width: '100%',
                padding: '10px 12px',
                borderRadius: '8px',
                border: '1px solid #cbd5e1',
                fontSize: '14px',
                outline: 'none',
                boxSizing: 'border-box',
              }}
            />
          </div>

          {/* Security Checklist */}
          <div
            style={{
              padding: '12px 14px',
              borderRadius: '8px',
              background: '#f8fafc',
              border: '1px solid #e2e8f0',
              marginBottom: '20px',
            }}
          >
            <div style={{ fontSize: '12px', fontWeight: 700, color: '#475569', marginBottom: '8px' }}>
              Tiêu chuẩn mật khẩu an toàn:
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px', fontSize: '12px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: hasLength ? '#15803d' : '#94a3b8' }}>
                {hasLength ? <CheckCircle2 size={14} /> : <XCircle size={14} />} Tối thiểu 8 ký tự
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: hasUpper ? '#15803d' : '#94a3b8' }}>
                {hasUpper ? <CheckCircle2 size={14} /> : <XCircle size={14} />} Chữ in hoa (A-Z)
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: hasLower ? '#15803d' : '#94a3b8' }}>
                {hasLower ? <CheckCircle2 size={14} /> : <XCircle size={14} />} Chữ thường (a-z)
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: hasNumber ? '#15803d' : '#94a3b8' }}>
                {hasNumber ? <CheckCircle2 size={14} /> : <XCircle size={14} />} Chữ số (0-9)
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: hasSpecial ? '#15803d' : '#94a3b8' }}>
                {hasSpecial ? <CheckCircle2 size={14} /> : <XCircle size={14} />} Ký tự đặc biệt
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: isMatch ? '#15803d' : '#94a3b8' }}>
                {isMatch ? <CheckCircle2 size={14} /> : <XCircle size={14} />} Khớp mật khẩu
              </div>
            </div>
          </div>

          {/* Action Buttons */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '12px' }}>
            <button
              type="button"
              onClick={logout}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '9px 14px',
                borderRadius: '8px',
                border: '1px solid #cbd5e1',
                background: '#f1f5f9',
                color: '#475569',
                fontSize: '13px',
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              <LogOut size={15} />
              <span>Đăng xuất</span>
            </button>

            <button
              type="submit"
              disabled={loading || !isStrong || !isMatch}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '10px 18px',
                borderRadius: '8px',
                border: 'none',
                background: !isStrong || !isMatch || loading ? '#94a3b8' : '#0f766e',
                color: 'white',
                fontSize: '13px',
                fontWeight: 700,
                cursor: !isStrong || !isMatch || loading ? 'not-allowed' : 'pointer',
                transition: 'background 0.15s ease',
              }}
            >
              <span>{loading ? 'Đang lưu...' : 'Lưu mật khẩu mới & Tiếp tục'}</span>
              <ArrowRight size={16} />
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
