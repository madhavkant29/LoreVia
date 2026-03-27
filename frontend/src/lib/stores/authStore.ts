import { create } from "zustand"
import { persist } from "zustand/middleware"
import type { User } from "@/types/user"

interface AuthStore {
  user: User | null
  accessToken: string | null
  setAuth: (access: string, refresh: string) => void
  setUser: (user: User) => void
  logout: () => void
}

export const useAuthStore = create<AuthStore>()(
  persist(
    (set) => ({
      user: null,
      accessToken: null,
      setAuth: (accessToken) => {
        if (typeof window !== "undefined") localStorage.setItem("access_token", accessToken)
        set({ accessToken })
      },
      setUser: (user) => set({ user }),
      logout: () => {
        if (typeof window !== "undefined") localStorage.removeItem("access_token")
        set({ user: null, accessToken: null })
      },
    }),
    { name: "lorevia-auth", partialize: (s) => ({ accessToken: s.accessToken }) }
  )
)
