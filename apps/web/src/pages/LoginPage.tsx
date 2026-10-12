import { AlertCircle, ArrowRight, ShieldCheck, Sparkles, Lock, Mail, Eye, EyeOff, ArrowLeft } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Navigate } from 'react-router-dom'
import { useAuth } from '../services/auth'

export function LoginPage() {
  const { user, login } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  if (user) return <Navigate to="/" replace />

  async function submit(event: FormEvent) {
    event.preventDefault()
    setError('')
    setBusy(true)
    try {
      await login(email, password)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Không thể đăng nhập')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="login-page">
      {/* Top Floating Glass Bar */}
      <header
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          maxWidth: '1200px',
          margin: '0 auto',
          padding: '20px 24px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          zIndex: 20,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontWeight: 800, fontSize: '18px', color: '#0369a1' }}>
          <div
            style={{
              width: '32px',
              height: '32px',
              borderRadius: '10px',
              background: 'linear-gradient(135deg, #0284c7, #0052cc)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'white',
              boxShadow: '0 4px 12px rgba(2, 132, 199, 0.3)',
            }}
          >
            <ShieldCheck size={18} />
          </div>
          <span>H4CARE <span style={{ color: '#0f172a', fontWeight: 700 }}>Data Hub</span></span>
        </div>

        <a
          href="http://localhost:3000"
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '6px',
            padding: '7px 14px',
            borderRadius: '9999px',
            fontSize: '12px',
            fontWeight: 700,
            color: '#334155',
            background: 'rgba(255, 255, 255, 0.85)',
            border: '1px solid rgba(186, 230, 253, 0.8)',
            textDecoration: 'none',
            backdropFilter: 'blur(8px)',
            transition: 'all 0.15s ease',
            boxShadow: '0 2px 6px rgba(0,0,0,0.04)',
          }}
        >
          <ArrowLeft size={14} style={{ color: '#0284c7' }} />
          <span>Về Web Bán Hàng</span>
        </a>
      </header>

      {/* Main Login Panel */}
      <section className="login-panel">
        <form className="login-form" onSubmit={submit}>
          <div className="overline">
            <ShieldCheck size={13} />
            <span>CỔNG QUẢN TRỊ DỮ LIỆU • H4CARE</span>
          </div>

          <h2>Đăng nhập quản trị</h2>
          <p>Nhập tài khoản Quản trị viên hoặc Dược sĩ để quản trị dữ liệu thuốc và vận hành hệ thống.</p>

          {error && (
            <div className="alert alert-error" style={{ borderRadius: '12px', marginBottom: '16px' }}>
              <AlertCircle size={17} />
              <span>{error}</span>
            </div>
          )}

          <label>
            <span>Email hoặc Số điện thoại</span>
            <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
              <input
                type="text"
                value={email}
                onChange={e => setEmail(e.target.value)}
                placeholder="admin@pharmatrust.vn"
                required
                style={{ width: '100%', paddingLeft: '38px' }}
              />
              <Mail size={16} style={{ position: 'absolute', left: '12px', color: '#0284c7' }} />
            </div>
          </label>

          <label>
            <span>Mật khẩu</span>
            <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
              <input
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={e => setPassword(e.target.value)}
                placeholder="••••••••"
                required
                style={{ width: '100%', paddingLeft: '38px', paddingRight: '38px' }}
              />
              <Lock size={16} style={{ position: 'absolute', left: '12px', color: '#0284c7' }} />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                style={{
                  position: 'absolute',
                  right: '10px',
                  background: 'none',
                  border: 'none',
                  color: '#64748b',
                  cursor: 'pointer',
                  padding: '4px',
                  display: 'flex',
                  alignItems: 'center',
                }}
                aria-label={showPassword ? 'Ẩn mật khẩu' : 'Hiện mật khẩu'}
              >
                {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </label>

          <button className="primary-button login-button" disabled={busy}>
            <span>{busy ? 'Đang xác thực thông tin…' : 'Đăng nhập Quản trị viên'}</span>
            <ArrowRight size={17} />
          </button>

          {/* Quick Demo Fill Buttons */}
          <div style={{ marginTop: '20px', padding: '12px', background: '#f8fafc', borderRadius: '12px', border: '1px solid #e2e8f0' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
              <span style={{ fontSize: '11px', fontWeight: 700, color: '#475569', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                Chọn vai trò Demo:
              </span>
              <span style={{ fontSize: '10px', color: '#0284c7', fontFamily: 'monospace', fontWeight: 700 }}>DEMO MODE</span>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: '6px' }}>
              <button
                type="button"
                onClick={() => {
                  setEmail('admin@pharmatrust.vn')
                  setPassword('Admin@123456')
                  setError('')
                }}
                style={{ padding: '6px 8px', borderRadius: '8px', border: '1px solid #c7d2fe', background: '#eef2ff', color: '#4338ca', fontSize: '11px', fontWeight: 600, cursor: 'pointer', textAlign: 'center' }}
              >
                🛡️ Admin
              </button>
              <button
                type="button"
                onClick={() => {
                  setEmail('manager.hcm@pharmatrust.vn')
                  setPassword('Warehouse@2026')
                  setError('')
                }}
                style={{ padding: '6px 8px', borderRadius: '8px', border: '1px solid #a7f3d0', background: '#ecfdf5', color: '#047857', fontSize: '11px', fontWeight: 600, cursor: 'pointer', textAlign: 'center' }}
              >
                📦 QL Kho HCM
              </button>
              <button
                type="button"
                onClick={() => {
                  setEmail('staff.hcm@pharmatrust.vn')
                  setPassword('Staff@2026')
                  setError('')
                }}
                style={{ padding: '6px 8px', borderRadius: '8px', border: '1px solid #99f6e4', background: '#f0fdfa', color: '#0f766e', fontSize: '11px', fontWeight: 600, cursor: 'pointer', textAlign: 'center' }}
              >
                📋 NV Kho HCM
              </button>
              <button
                type="button"
                onClick={() => {
                  setEmail('manager.hn@pharmatrust.vn')
                  setPassword('Warehouse@2026')
                  setError('')
                }}
                style={{ padding: '6px 8px', borderRadius: '8px', border: '1px solid #bae6fd', background: '#f0f9ff', color: '#0369a1', fontSize: '11px', fontWeight: 600, cursor: 'pointer', textAlign: 'center' }}
              >
                📦 QL Kho HN
              </button>
              <button
                type="button"
                onClick={() => {
                  setEmail('reviewer@pharmatrust.vn')
                  setPassword('Reviewer@123456')
                  setError('')
                }}
                style={{ padding: '6px 8px', borderRadius: '8px', border: '1px solid #fde68a', background: '#fffbeb', color: '#b45309', fontSize: '11px', fontWeight: 600, cursor: 'pointer', textAlign: 'center' }}
              >
                🔬 Dược Sĩ
              </button>
            </div>
          </div>

          <div style={{ marginTop: '20px', textAlign: 'center' }}>
            <a
              href="http://localhost:3000"
              style={{
                color: '#0284c7',
                fontSize: '12px',
                fontWeight: 700,
                textDecoration: 'none',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '4px',
              }}
            >
              ← Quay lại Website Khách Hàng (Storefront :3000)
            </a>
          </div>
        </form>
      </section>
    </div>
  )
}
