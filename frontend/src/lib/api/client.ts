import axios from "axios"
import { API_BASE } from "@/lib/constants"
import { buildDailyCapEventDetail, dispatchDailyCapEvent } from "@/lib/monetization/limitRecovery"

export const apiClient = axios.create({
  baseURL: API_BASE,
  headers: { "Content-Type": "application/json" },
  withCredentials: true,
})

let refreshPromise: Promise<boolean> | null = null

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
