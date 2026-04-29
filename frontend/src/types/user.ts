export interface User {
  id: string
  email: string
  username?: string | null
  tier: "free" | "pro" | "power" | "admin"
  reading_mode: "casual" | "analyst" | "speed"
  created_at: string
}

export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
  user?: User
}
