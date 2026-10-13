import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { api, tokenStore } from './api'
import type { User } from '../types'

interface AuthState {
  user: User | null
  loading: boolean
  login: (email: string, password: string) => Promise<void>
  logout: () => void
  refreshProfile: () => Promise<void>
  updateUser: (u: User) => void
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  const refreshProfile = async () => {
    if (!tokenStore.get()) return
    try {
      const profile = await api<User>('/auth/me')
      if ((profile.role as string) === 'CUSTOMER') {
        tokenStore.clear()
        setUser(null)
      } else {
        setUser(profile)
      }
    } catch {
      // ignore
    }
  }

  const updateUser = (u: User) => {
    setUser(u)
  }

  useEffect(() => {
    // 1. Handshake token from URL query parameters (cross-app auth from Storefront)
    try {
      const urlParams = new URLSearchParams(window.location.search)
      const urlToken = urlParams.get('token')
      const urlRefresh = urlParams.get('refresh')
      if (urlToken) {
        tokenStore.set(urlToken, urlRefresh || '')
        const cleanUrl = window.location.pathname + window.location.hash
        window.history.replaceState({}, document.title, cleanUrl || '/')
      }
    } catch {
      // ignore
    }

    if (!tokenStore.get()) {
      setLoading(false)
      return
    }
    api<User>('/auth/me')
      .then((profile) => {
        if ((profile.role as string) === 'CUSTOMER') {
          tokenStore.clear()
          setUser(null)
        } else {
          setUser(profile)
        }
      })
      .catch(() => tokenStore.clear())
      .finally(() => setLoading(false))
  }, [])

  async function login(email: string, password: string) {
    const tokens = await api<{ access_token: string; refresh_token: string }>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    })
    tokenStore.set(tokens.access_token, tokens.refresh_token)
    const profile = await api<User>('/auth/me')
    if ((profile.role as string) === 'CUSTOMER') {
      tokenStore.clear()
      setUser(null)
      throw new Error('Tài khoản khách hàng không có quyền truy cập trang quản trị dữ liệu. Vui lòng đăng nhập tại website bán hàng (Storefront).')
    }
    setUser(profile)
  }

  function logout() {
    tokenStore.clear()
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, refreshProfile, updateUser }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const value = useContext(AuthContext)
  if (!value) throw new Error('useAuth phải nằm trong AuthProvider')
  return value
}

