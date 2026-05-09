import { apiClient } from "./client"
import type { User } from "@/types/user"
import axios from "axios"

export interface RegisterResponse {
  id: string
  email: string
  username: string
  email_verification_required: boolean
  verification_email_sent: boolean
  verification_url?: string | null
}

export interface TierLimits {
  free_max_books: number
  free_total_token_budget: number
  free_search_per_day: number
  free_summary_per_hour: number
  free_prediction_per_day: number
  reader_prediction_per_day: number
  author_prediction_per_day: number
  architect_prediction_per_day: number
  trial_high_cost_turns_per_day: number
  author_high_cost_turns_per_day: number
  architect_high_cost_turns_per_day: number
  free_advisor_per_day: number
  free_advisor_per_week: number
  free_advisor_per_month: number
  reader_advisor_per_day: number
  reader_advisor_per_week: number
  reader_advisor_per_month: number
  author_advisor_per_day: number
  author_advisor_per_week: number
  author_advisor_per_month: number
  architect_advisor_per_day: number
  architect_advisor_per_week: number
  architect_advisor_per_month: number
  free_continuity_per_minute: number
  reader_continuity_per_minute: number
  author_continuity_per_minute: number
  architect_continuity_per_minute: number
}

export const authApi = {
  register: (email: string, username: string, password: string, accepted_terms: boolean, device_id: string) =>
    apiClient.post<RegisterResponse>("/auth/register", { email, username, password, accepted_terms, device_id }).then(r => r.data),
  login: (email: string, password: string) =>
    apiClient.post<User>("/auth/login", { email, password }).then(r => r.data),
  loginWithSupabaseToken: (token: string, device_id: string, accepted_terms = false) =>
    apiClient.post<User>("/auth/oauth/supabase", { token, accepted_terms, device_id }).then(r => r.data),
  verifyEmail: (token: string) =>
    apiClient.post<User>("/auth/verify-email", { token }).then(r => r.data),
  resendVerification: (email: string) =>
    apiClient.post("/auth/resend-verification", { email }).then(r => r.data),
  forgotPassword: (email: string) =>
    apiClient.post("/auth/forgot-password", { email }).then(r => r.data),
  resetPassword: (token: string, password: string) =>
    apiClient.post("/auth/reset-password", { token, password }).then(r => r.data),
  refresh: () =>
    apiClient.post<User>("/auth/refresh").then(r => r.data),
  logout: () => apiClient.post("/auth/logout").then(r => r.data),
  me: async () => {
    try {
      return await apiClient.get<User>("/auth/me").then(r => r.data)
    } catch (error) {
      if (axios.isAxiosError(error) && error.response?.status === 401) {
        return null
      }
      throw error
    }
  },
  setReadingMode: (mode: string) =>
    apiClient.patch(`/auth/me/reading-mode?mode=${mode}`).then(r => r.data),
  setDailyWordGoal: (dailyWordGoal: number) =>
    apiClient.patch<User>("/auth/me/daily-word-goal", { daily_word_goal: dailyWordGoal }).then(r => r.data),
  setUsername: (username: string) =>
    apiClient.patch<User>("/auth/me/username", null, { params: { username } }).then(r => r.data),
  getTierLimits: () => apiClient.get<TierLimits>("/auth/tier-limits").then(r => r.data),
}
