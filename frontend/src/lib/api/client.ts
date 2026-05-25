import axios from "axios"
import { API_BASE } from "@/lib/constants"
import { buildDailyCapEventDetail, dispatchDailyCapEvent } from "@/lib/limits/dailyCap"

export const apiClient = axios.create({
  baseURL: API_BASE,
  headers: { "Content-Type": "application/json" },
  withCredentials: true,
})

let refreshPromise: Promise<boolean> | null = null
const ADMIN_CSRF_COOKIE_NAME = "lorevia_admin_csrf"

function readCookie(name: string) {
  if (typeof document === "undefined") return null
  const prefix = `${name}=`
  const cookie = document.cookie
    .split(";")
    .map((part) => part.trim())
    .find((part) => part.startsWith(prefix))
  return cookie ? decodeURIComponent(cookie.slice(prefix.length)) : null
}

async function refreshAccessToken(): Promise<boolean> {
  if (!refreshPromise) {
    refreshPromise = axios
      .post(`${API_BASE}/auth/refresh`, null, { withCredentials: true })
      .then(() => true)
      .catch(() => {
        return false
      })
      .finally(() => {
        refreshPromise = null
      })
  }

  return refreshPromise
}

apiClient.interceptors.request.use((config) => {
  // Let the browser set the multipart boundary for FormData requests.
  // Keeping a JSON default header here can make multipart bodies invalid and
  // trigger FastAPI 422 validation/parsing errors.
  if (typeof FormData !== "undefined" && config.data instanceof FormData) {
    if (config.headers) {
      delete config.headers["Content-Type"]
      delete config.headers["content-type"]
    }
  }
  const method = String(config.method ?? "get").toLowerCase()
  const url = String(config.url ?? "")
  if (url.startsWith("/admin/") && !["get", "head", "options"].includes(method)) {
    const csrfToken = readCookie(ADMIN_CSRF_COOKIE_NAME)
    if (csrfToken) {
      config.headers.set?.("X-Admin-CSRF-Token", csrfToken)
      if (!config.headers.set) {
        config.headers["X-Admin-CSRF-Token"] = csrfToken
      }
    }
  }
  return config
})

apiClient.interceptors.response.use(
  (r) => r,
  async (error) => {
    const dailyCapEvent = buildDailyCapEventDetail(error)
    if (dailyCapEvent) {
      dispatchDailyCapEvent(dailyCapEvent)
    }
    const originalRequest = error.config
    const requestUrl = String(originalRequest?.url ?? "")
    const requestPath = requestUrl.split("?")[0]
    const isAuthEndpoint =
      requestPath === "/auth/me" ||
      requestPath === "/auth/refresh" ||
      requestPath === "/auth/login" ||
      requestPath === "/auth/register" ||
      requestPath.startsWith("/auth/oauth/")
    if (error.response?.status === 401 && !originalRequest?._retry && !isAuthEndpoint) {
      originalRequest._retry = true
      const refreshed = await refreshAccessToken()
      if (refreshed) {
        return apiClient(originalRequest)
      }
      if (typeof window !== "undefined") {
        window.location.replace("/login")
      }
    }
    return Promise.reject(error)
  }
)
