import { apiClient } from "./client"
import { normalizeUser } from "@/lib/billing/plans"
import type { User } from "@/types/user"
import axios from "axios"
import { supabase } from "@/lib/supabase"

const LOGOUT_REQUEST_TIMEOUT_MS = 3_000

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
  author_max_uploads: number
  architect_uploads_unlimited: boolean
  free_total_token_budget: number
  free_search_per_day: number
  free_summary_per_hour: number
  free_prediction_per_day: number
  free_recall_per_day: number
  author_prediction_per_day: number
  architect_prediction_per_day: number
  trial_high_cost_turns_per_day: number
  author_high_cost_turns_per_day: number
  architect_high_cost_turns_per_day: number
  free_advisor_per_day: number
  free_advisor_per_week: number
  free_advisor_per_month: number
  free_continuity_per_day: number
  author_advisor_per_day: number
  author_advisor_per_week: number
  author_advisor_per_month: number
  architect_advisor_per_day: number
  architect_advisor_per_week: number
  architect_advisor_per_month: number
  free_continuity_per_minute: number
  author_continuity_per_minute: number
  architect_continuity_per_minute: number
}

export interface AccountDeletionResponse {
  ok: boolean
  deletion_status: string
  scheduled_for?: string | null
  provider_followup_required: boolean
}

export const authApi = {
  register: (email: string, username: string, password: string, accepted_terms: boolean, device_id: string) =>
    apiClient.post<RegisterResponse>("/auth/register", { email, username, password, accepted_terms, device_id }).then(r => r.data),
  login: (email: string, password: string, device_id: string) =>
    apiClient.post<User>("/auth/login", { email, password, device_id }).then(r => normalizeUser(r.data)),
  loginWithSupabaseToken: (token: string, device_id: string, accepted_terms = false) =>
    apiClient.post<User>("/auth/oauth/supabase", { token, accepted_terms, device_id }).then(r => normalizeUser(r.data)),
  verifyEmail: (token: string) =>
    apiClient.post<User>("/auth/verify-email", { token }).then(r => normalizeUser(r.data)),
  resendVerification: (email: string) =>
    apiClient.post("/auth/resend-verification", { email }).then(r => r.data),
  forgotPassword: (email: string) =>
    apiClient.post("/auth/forgot-password", { email }).then(r => r.data),
  resetPassword: (token: string, password: string) =>
    apiClient.post("/auth/reset-password", { token, password }).then(r => r.data),
  refresh: () =>
    apiClient.post<User>("/auth/refresh").then(r => normalizeUser(r.data)),
  session: () =>
    apiClient.post<User>("/auth/session").then(r => normalizeUser(r.data)),
  logout: async () => {
    try {
      return await apiClient
        .post("/auth/logout", undefined, { timeout: LOGOUT_REQUEST_TIMEOUT_MS })
        .then(r => r.data)
    } finally {
      // Provider-local cleanup must not extend the bounded backend revocation path.
      void supabase?.auth.signOut({ scope: "local" }).catch(() => undefined)
    }
  },
  me: async () => {
    try {
      return await apiClient.get<User>("/auth/me").then(r => normalizeUser(r.data))
    } catch (error) {
      if (axios.isAxiosError(error) && error.response?.status === 401) {
        return null
      }
      throw error
    }
  },
  exportData: () =>
    apiClient.get<Blob>("/auth/me/data-export", { responseType: "blob" }).then(r => r.data),
  deleteAccount: async (payload: { confirmationText: string; password?: string }) => {
    const response = await apiClient.delete<AccountDeletionResponse>("/auth/me", {
      data: {
        confirmation_text: payload.confirmationText,
        password: payload.password || null,
      },
    })
    try {
      await supabase?.auth.signOut({ scope: "local" })
    } catch {
      // Local provider-session cleanup should not mask a completed account deletion.
    }
    return response.data
  },
  setReadingMode: (mode: string) =>
    apiClient.patch<User>(`/auth/me/reading-mode?mode=${mode}`).then(r => normalizeUser(r.data)),
  setDailyWordGoal: (dailyWordGoal: number) =>
    apiClient.patch<User>("/auth/me/daily-word-goal", { daily_word_goal: dailyWordGoal }).then(r => normalizeUser(r.data)),
  setMessagingPermission: (messagingPermission: "anyone" | "friends_only") =>
    apiClient.patch<User>("/auth/me/messaging-permission", { messaging_permission: messagingPermission }).then(r => normalizeUser(r.data)),
  setUsername: (username: string) =>
    apiClient.patch<User>("/auth/me/username", null, { params: { username } }).then(r => normalizeUser(r.data)),
  getTierLimits: () => apiClient.get<TierLimits>("/auth/tier-limits").then(r => r.data),
}
