import axios from "axios"

export type DailyCapAction = "search" | "prediction" | "high_cost_authoring"

export const DAILY_LIMIT_MESSAGE = "Your daily limit refreshes tomorrow. Want higher limits now? Upgrade."
export const DAILY_CAP_EVENT = "lorevia:daily-cap-hit"

export interface DailyCapEventDetail {
  action: DailyCapAction | null
  status: number
  requestPath: string
  detail: string
}

export function inferDailyCapActionFromRequestPath(requestPath: string): DailyCapAction | null {
  if (requestPath.includes("/reader/") && (requestPath.endsWith("/search") || requestPath.endsWith("/thematic-search"))) {
    return "search"
  }
  if (requestPath.includes("/intelligence/") && (requestPath.endsWith("/qa") || requestPath.includes("/chat/"))) {
    return "prediction"
  }
  if (requestPath.includes("/advisor/")) {
    return "high_cost_authoring"
  }
  if (requestPath.includes("/series/") && requestPath.includes("/advisor/message")) {
    return "high_cost_authoring"
  }
  if (requestPath.includes("/series/") && requestPath.includes("/continuity-check")) {
    return "high_cost_authoring"
  }
  return null
}

export function buildDailyCapEventDetail(error: unknown): DailyCapEventDetail | null {
  if (!axios.isAxiosError(error)) {
    return null
  }

  const status = error.response?.status
  const detailValue = error.response?.data?.detail
  const detail = typeof detailValue === "string" ? detailValue : ""
  const requestUrl = String(error.config?.url ?? "")
  const requestPath = requestUrl.split("?")[0]

  if ((status !== 403 && status !== 429) || detail !== DAILY_LIMIT_MESSAGE) {
    return null
  }

  return {
    action: inferDailyCapActionFromRequestPath(requestPath),
    status,
    requestPath,
    detail,
  }
}

export function dispatchDailyCapEvent(detail: DailyCapEventDetail): void {
  if (typeof window === "undefined") {
    return
  }
  window.dispatchEvent(new CustomEvent<DailyCapEventDetail>(DAILY_CAP_EVENT, { detail }))
}
