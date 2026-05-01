import { create } from "zustand"
import type { User } from "@/types/user"

interface AuthStore {
  user: User | null
  hydrated: boolean
  setUser: (user: User) => void
  setHydrated: () => void
  logout: () => void
}

export const useAuthStore = create<AuthStore>()((set) => ({
  user: null,
  hydrated: false,
  setUser: (user) => set({ user, hydrated: true }),
  setHydrated: () => set({ hydrated: true }),
  logout: () => {
    if (typeof window !== "undefined") {
      window.localStorage.removeItem("lorevia-auth")
    }
    set({ user: null, hydrated: true })
  },
}))
