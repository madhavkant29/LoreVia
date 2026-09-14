import axios from "axios"

export function getApiErrorDetail(error: unknown): string | null {
  if (!axios.isAxiosError(error)) return null
  const detail = error.response?.data?.detail
  if (typeof detail === "string") return detail
  if (detail && typeof detail === "object" && "message" in detail) {
    const message = (detail as { message?: unknown }).message
    return typeof message === "string" ? message : null
  }
  return null
}
