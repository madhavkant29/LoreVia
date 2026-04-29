import axios from "axios"
import { API_BASE } from "@/lib/constants"
import { useAuthStore } from "@/lib/stores/authStore"
import { clearAuthTokens, getStoredAccessToken, getStoredRefreshToken, persistAuthTokens } from "./tokenStore"

export const apiClient = axios.create({
  baseURL: API_BASE,
  withCredentials: true,
  headers: { "Content-Type": "application/json" },
})

let refreshPromise: Promise<boolean> | null = null
const NON_REFRESHABLE_AUTH_PATHS = [
  "/auth/login",
  "/auth/register",
  "/auth/oauth/supabase",
  "/auth/forgot-password",
  "/auth/reset-password",
  "/auth/refresh",
  "/auth/logout",
  "/auth/me",
  "/auth/tier-limits",
]

function requestPath(url: string, baseURL?: string): string {
  try {
    return new URL(url, baseURL ?? API_BASE).pathname
  } catch {
    return url.startsWith("/") ? url : `/${url}`
  }
}

apiClient.interceptors.request.use((config) => {
  const accessToken = getStoredAccessToken()
  if (accessToken) {
    config.headers = config.headers ?? {}
    config.headers.Authorization = `Bearer ${accessToken}`
  }
  return config
})

async function refreshSession(): Promise<boolean> {
  if (!refreshPromise) {
    const refreshToken = getStoredRefreshToken()
    refreshPromise = apiClient
      .post("/auth/refresh", refreshToken ? { refresh_token: refreshToken } : undefined)
      .then((response) => {
        if (response.data?.access_token && response.data?.refresh_token) {
          persistAuthTokens(response.data)
        }
        return true
      })
      .catch(() => false)
      .finally(() => {
        refreshPromise = null
      })
  }

  return refreshPromise
}

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config
    const path = requestPath(originalRequest?.url ?? "", originalRequest?.baseURL)
    const isNonRefreshableAuthRequest = NON_REFRESHABLE_AUTH_PATHS.includes(path)
    if (error.response?.status === 401 && !originalRequest?._retry && !isNonRefreshableAuthRequest) {
      originalRequest._retry = true
      const refreshed = await refreshSession()
      if (refreshed) {
        const accessToken = getStoredAccessToken()
        if (accessToken) {
          originalRequest.headers = originalRequest.headers ?? {}
          originalRequest.headers.Authorization = `Bearer ${accessToken}`
        }
        return apiClient(originalRequest)
      }
      if (typeof window !== "undefined") {
        useAuthStore.getState().logout()
        clearAuthTokens()
        window.location.replace("/login")
        return new Promise(() => {})
      }
    }
    return Promise.reject(error)
  }
)
