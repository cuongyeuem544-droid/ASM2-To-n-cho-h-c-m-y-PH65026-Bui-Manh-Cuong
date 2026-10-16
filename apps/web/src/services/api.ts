const defaultApiUrl = '/api/v1'

const API_URL = import.meta.env.VITE_API_URL || defaultApiUrl

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

export const tokenStore = {
  get: () => localStorage.getItem('pharmatrust_access_token') || localStorage.getItem('access_token'),
  getRefresh: () => localStorage.getItem('pharmatrust_refresh_token') || localStorage.getItem('refresh_token'),
  set: (access: string, refresh: string) => {
    localStorage.setItem('pharmatrust_access_token', access)
    localStorage.setItem('pharmatrust_refresh_token', refresh)
    // Synchronize legacy key for backwards compatibility
    localStorage.setItem('access_token', access)
    localStorage.setItem('refresh_token', refresh)
  },
  clear: () => {
    localStorage.removeItem('pharmatrust_access_token')
    localStorage.removeItem('pharmatrust_refresh_token')
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
  },
}

async function refreshAccessToken(): Promise<boolean> {
  const refreshToken = tokenStore.getRefresh()
  if (!refreshToken) return false
  const response = await fetch(`${API_URL}/auth/refresh`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: refreshToken }),
  })
  if (!response.ok) return false
  const data = await response.json()
  tokenStore.set(data.access_token, data.refresh_token)
  return true
}

export async function api<T>(path: string, options: RequestInit = {}, retry = true): Promise<T> {
  const headers = new Headers(options.headers)
  if (!(options.body instanceof FormData)) headers.set('Content-Type', 'application/json')
  const token = tokenStore.get()
  if (token) headers.set('Authorization', `Bearer ${token}`)
  const response = await fetch(`${API_URL}${path}`, { ...options, headers })
  if (response.status === 401 && retry && await refreshAccessToken()) return api<T>(path, options, false)
  if (!response.ok) {
    let message = 'Đã xảy ra lỗi khi kết nối máy chủ'
    try {
      const body = await response.json()
      message = body.detail || body.message || message
    } catch { /* response is not JSON */ }
    throw new ApiError(response.status, message)
  }
  if (response.status === 204) return undefined as T
  return response.json()
}

api.get = <T>(path: string, options?: RequestInit) => api<T>(path, { ...options, method: 'GET' })
api.post = <T>(path: string, body?: any, options?: RequestInit) =>
  api<T>(path, {
    ...options,
    method: 'POST',
    body: body instanceof FormData ? body : body !== undefined ? JSON.stringify(body) : undefined,
  })
api.put = <T>(path: string, body?: any, options?: RequestInit) =>
  api<T>(path, {
    ...options,
    method: 'PUT',
    body: body instanceof FormData ? body : body !== undefined ? JSON.stringify(body) : undefined,
  })
api.patch = <T>(path: string, body?: any, options?: RequestInit) =>
  api<T>(path, {
    ...options,
    method: 'PATCH',
    body: body instanceof FormData ? body : body !== undefined ? JSON.stringify(body) : undefined,
  })
api.delete = <T>(path: string, options?: RequestInit) => api<T>(path, { ...options, method: 'DELETE' })

export { API_URL }

