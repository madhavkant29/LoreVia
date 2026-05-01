export interface User {
  id: string
  email: string
  username?: string | null
  tier: "free" | "pro" | "power" | "admin"
  reading_mode: "casual" | "analyst" | "speed"
  created_at: string
}
