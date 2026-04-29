import axios from "axios"
import { apiClient } from "./client"
import { clearAuthTokens, persistAuthTokens } from "./tokenStore"
import type { TokenResponse, User } from "@/types/user"

export interface TierLimits {
  free_max_books: number
  free_total_token_budget: number
  free_search_per_hour: number
  free_summary_per_hour: number
  free_chat_per_day: number
  free_advisor_per_day: number
  free_advisor_per_week: number
  free_advisor_per_month: number
  pro_chat_per_day: number
  pro_advisor_per_day: number
  pro_advisor_per_week: number
  pro_advisor_per_month: number
  power_advisor_per_day: number
  power_advisor_per_week: number
  power_advisor_per_month: number
  free_continuity_per_minute: number
  pro_continuity_per_minute: number
  power_continuity_per_minute: number
}

function isUnauthorized(error: unknown): boolean {
  return axios.isAxiosError(error) && error.response?.status === 401
}

export const authApi = {
  register: (email: string, username: string, password: string, accepted_terms: boolean) =>
    apiClient.post<TokenResponse>("/auth/register", { email, username, password, accepted_terms }).then(r => {
      persistAuthTokens(r.data)
      return r.data
    }),
  login: (email: string, password: string) =>
    apiClient.post<TokenResponse>("/auth/login", { email, password }).then(r => {
      persistAuthTokens(r.data)
      return r.data
    }),
  loginWithSupabaseToken: (token: string, accepted_terms = false) =>
    apiClient.post<TokenResponse>("/auth/oauth/supabase", { token, accepted_terms }).then(r => {
      persistAuthTokens(r.data)
      return r.data
    }),
  forgotPassword: (email: string) =>
    apiClient.post("/auth/forgot-password", { email }).then(r => r.data),
  resetPassword: (token: string, password: string) =>
    apiClient.post("/auth/reset-password", { token, password }).then(r => r.data),
  refresh: async () => {
    try {
      return await apiClient.post<TokenResponse>("/auth/refresh").then(r => {
        persistAuthTokens(r.data)
        return r.data
      })
    } catch (error) {
      if (isUnauthorized(error)) return null
      throw error
    }
  },
  logout: () => apiClient.post("/auth/logout").then(r => {
    clearAuthTokens()
    return r.data
  }).catch((error) => {
    clearAuthTokens()
    throw error
  }),
  me: async () => {
    try {
      return await apiClient.get<User>("/auth/me").then(r => r.data)
    } catch (error) {
      if (isUnauthorized(error)) return null
      throw error
    }
  },
  setReadingMode: (mode: string) =>
    apiClient.patch(`/auth/me/reading-mode?mode=${mode}`).then(r => r.data),
  setUsername: (username: string) =>
    apiClient.patch<User>("/auth/me/username", null, { params: { username } }).then(r => r.data),
  getTierLimits: () => apiClient.get<TierLimits>("/auth/tier-limits").then(r => r.data),
}
