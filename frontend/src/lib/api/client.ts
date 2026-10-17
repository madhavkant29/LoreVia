import axios from "axios"
import { captureApiFailure } from "@/lib/analytics/browserTelemetry"
import { API_BASE } from "@/lib/constants"
import { buildDailyCapEventDetail, dispatchDailyCapEvent } from "@/lib/limits/dailyCap"

export const DEFAULT_API_TIMEOUT_MS = 60_000
export const AUTH_REFRESH_TIMEOUT_MS = 15_000
export const LARGE_TRANSFER_TIMEOUT_MS = 10 * 60_000

export const apiClient = axios.create({
  baseURL: API_BASE,
  headers: { "Content-Type": "application/json" },
  timeout: DEFAULT_API_TIMEOUT_MS,
  withCredentials: true,
})

let refreshPromise: Promise<boolean> | null = null
let csrfBootstrapPromise: Promise<boolean> | null = null
const AUTH_CSRF_COOKIE_NAME = "lorevia_csrf"
const AUTH_CSRF_HEADER_NAME = "X-CSRF-Token"
const ADMIN_CSRF_COOKIE_NAME = "lorevia_admin_csrf"
const ADMIN_CSRF_HEADER_NAME = "X-Admin-CSRF-Token"
const AUTH_COOKIE_NAMES = ["lorevia_access_token", "lorevia_refresh_token", "lorevia_csrf"]
const SAFE_HTTP_METHODS = new Set(["get", "head", "options"])

function isCsrfFailure(error: { response?: { status?: number; data?: { detail?: unknown } } }) {
  const detail = error.response?.data?.detail
  return error.response?.status === 403 && typeof detail === "string" && detail.startsWith("Invalid CSRF token")
}

async function bootstrapAuthCsrfCookie(): Promise<boolean> {
  if (!csrfBootstrapPromise) {
    csrfBootstrapPromise = axios
      .get(`${API_BASE}/auth/csrf`, {
        withCredentials: true,
        timeout: AUTH_REFRESH_TIMEOUT_MS,
      })
      .then(() => true)
      .catch(() => false)
      .finally(() => {
        csrfBootstrapPromise = null
      })
  }

  return csrfBootstrapPromise
}

export function clearAuthCookies() {
  if (typeof document === "undefined") return
  const hostname = window.location.hostname
  for (const name of AUTH_COOKIE_NAMES) {
    // Try every plausible Domain+Path combination so httpOnly cookies set by
    // the backend are guaranteed to be overwritten regardless of the exact
    // Domain attribute the Set-Cookie header used.
    for (const domain of [hostname, `.${hostname}`, ""]) {
      for (const path of ["/", "/api", "/api/v1"]) {
        const domainPart = domain ? `; Domain=${domain}` : ""
        document.cookie = `${name}=; Max-Age=0; Path=${path}${domainPart}; Secure; SameSite=Lax`
        document.cookie = `${name}=; Max-Age=0; Path=${path}${domainPart}; SameSite=Lax`
      }
    }
  }
}

function readCookie(name: string) {
  if (typeof document === "undefined") return null
  const prefix = `${name}=`
  const cookies = document.cookie
    .split(";")
    .map((part) => part.trim())
    .filter((part) => part.startsWith(prefix))
  const cookie = cookies.at(-1)
  return cookie ? decodeURIComponent(cookie.slice(prefix.length)) : null
}

export function getAuthCsrfHeaders(): Record<string, string> {
  const csrfToken = readCookie(AUTH_CSRF_COOKIE_NAME)
  return csrfToken ? { [AUTH_CSRF_HEADER_NAME]: csrfToken } : {}
}

async function refreshAccessToken(): Promise<boolean> {
  const csrfHeaders = getAuthCsrfHeaders()
  if (!refreshPromise) {
    refreshPromise = axios
      .post(`${API_BASE}/auth/refresh`, null, {
        withCredentials: true,
        headers: Object.keys(csrfHeaders).length > 0 ? csrfHeaders : undefined,
        timeout: AUTH_REFRESH_TIMEOUT_MS,
      })
      .then(() => {
        if (typeof document !== "undefined") {
          document.cookie = "lorevia_session_dead=; Max-Age=0; Path=/"
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

apiClient.interceptors.request.use((config) => {
  const isFormData = typeof FormData !== "undefined" && config.data instanceof FormData
  // Let the browser set the multipart boundary for FormData requests.
  // Keeping a JSON default header here can make multipart bodies invalid and
  // trigger FastAPI 422 validation/parsing errors.
  if (isFormData) {
    if (config.headers) {
      delete config.headers["Content-Type"]
      delete config.headers["content-type"]
    }
  }
  if (
    (isFormData || config.responseType === "blob") &&
    (config.timeout === undefined || config.timeout === DEFAULT_API_TIMEOUT_MS)
  ) {
    config.timeout = LARGE_TRANSFER_TIMEOUT_MS
  }
  const method = String(config.method ?? "get").toLowerCase()
  const url = String(config.url ?? "")
  if (!SAFE_HTTP_METHODS.has(method)) {
    const csrfToken = getAuthCsrfHeaders()[AUTH_CSRF_HEADER_NAME]
    if (csrfToken) {
      config.headers.set?.(AUTH_CSRF_HEADER_NAME, csrfToken)
      if (!config.headers.set) {
        config.headers[AUTH_CSRF_HEADER_NAME] = csrfToken
      }
    }
  }
  if (url.startsWith("/admin/") && !SAFE_HTTP_METHODS.has(method)) {
    const csrfToken = readCookie(ADMIN_CSRF_COOKIE_NAME)
    if (csrfToken) {
      config.headers.set?.(ADMIN_CSRF_HEADER_NAME, csrfToken)
      if (!config.headers.set) {
        config.headers[ADMIN_CSRF_HEADER_NAME] = csrfToken
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
    if (
      isCsrfFailure(error) &&
      originalRequest &&
      !originalRequest._csrfRetry &&
      requestPath !== "/auth/csrf"
    ) {
      originalRequest._csrfRetry = true
      if (await bootstrapAuthCsrfCookie()) {
        return apiClient(originalRequest)
      }
    }
    const isAuthEndpoint =
      requestPath === "/auth/me" ||
      requestPath === "/auth/refresh" ||
      requestPath === "/auth/session" ||
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
        clearAuthCookies()
        // Set a short-lived flag so the middleware knows these cookies are
        // dead and must not redirect /login → /library, preventing the loop.
        document.cookie = "lorevia_session_dead=1; Max-Age=30; Path=/; Secure; SameSite=Lax"
        window.location.replace("/login")
      }
    }
    captureApiFailure(error)
    return Promise.reject(error)
  }
)
