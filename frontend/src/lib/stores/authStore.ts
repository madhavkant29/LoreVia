import { create } from "zustand"
import type { User } from "@/types/user"

interface AuthStore {
  user: User | null
  hydrated: boolean
  setUser: (user: User) => void
  logout: () => void
}

export const useAuthStore = create<AuthStore>()((set) => ({
  user: null,
  hydrated: false,
  setUser: (user) => set({ user, hydrated: true }),
  logout: () => set({ user: null, hydrated: true }),
}))
