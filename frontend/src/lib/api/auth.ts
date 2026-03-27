import { apiClient } from "./client"
import type { TokenResponse, User } from "@/types/user"

export const authApi = {
  register: (email: string, password: string) =>
    apiClient.post<TokenResponse>("/auth/register", { email, password }).then(r => r.data),
  login: (email: string, password: string) =>
    apiClient.post<TokenResponse>("/auth/login", { email, password }).then(r => r.data),
  me: () => apiClient.get<User>("/auth/me").then(r => r.data),
  setReadingMode: (mode: string) =>
    apiClient.patch(`/auth/me/reading-mode?mode=${mode}`).then(r => r.data),
}
