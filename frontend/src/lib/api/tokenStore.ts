import { API_BASE } from "@/lib/constants"
import type { TokenResponse } from "@/types/user"

const ACCESS_TOKEN_KEY = "lorevia_access_token"
const REFRESH_TOKEN_KEY = "lorevia_refresh_token"
const LOCAL_HOSTNAMES = new Set(["localhost", "127.0.0.1", "::1", "host.docker.internal"])

function isLocalAuthFallbackEnabled() {
  if (typeof window === "undefined" || typeof window.localStorage === "undefined") return false

  try {
    const apiHostname = new URL(API_BASE, window.location.origin).hostname.toLowerCase()
    const appHostname = window.location.hostname.toLowerCase()
    return LOCAL_HOSTNAMES.has(apiHostname) || LOCAL_HOSTNAMES.has(appHostname) || apiHostname.endsWith(".local")
  } catch {
    return false
  }
}

function canUseStorage() {
  return isLocalAuthFallbackEnabled()
}

export function persistAuthTokens(tokens: Pick<TokenResponse, "access_token" | "refresh_token">) {
  if (!canUseStorage()) return
  window.localStorage.setItem(ACCESS_TOKEN_KEY, tokens.access_token)
  window.localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refresh_token)
}

export function getStoredAccessToken() {
  if (!canUseStorage()) return null
  return window.localStorage.getItem(ACCESS_TOKEN_KEY)
}

export function getStoredRefreshToken() {
  if (!canUseStorage()) return null
  return window.localStorage.getItem(REFRESH_TOKEN_KEY)
}

export function clearAuthTokens() {
  if (!canUseStorage()) return
  window.localStorage.removeItem(ACCESS_TOKEN_KEY)
  window.localStorage.removeItem(REFRESH_TOKEN_KEY)
}
