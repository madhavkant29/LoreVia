export type UserTier = "free" | "reader" | "author" | "architect" | "admin"

export interface User {
  id: string
  email: string
  username?: string | null
  tier: UserTier
  plan_tier: UserTier
  tier_label: string
  trial_active: boolean
  trial_ends_at?: string | null
  reading_mode: "casual" | "analyst" | "speed"
  daily_word_goal: number
  today_word_count: number
  last_login_at?: string | null
  login_streak_days: number
  longest_login_streak_days: number
  login_activity_dates: string[]
  email_verified: boolean
  created_at: string
}
