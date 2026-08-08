import { create } from "zustand"
import { resetIdentity } from "@/lib/analytics/posthog"
import { normalizeUser } from "@/lib/billing/plans"
import type { User } from "@/types/user"
import { useUiPreferencesStore } from "./uiPreferencesStore"

const AUTH_USER_STORAGE_KEY = "lorevia-auth-user"

function readCachedAuthUser() {
  if (typeof window === "undefined") return null
  try {
    const raw = window.sessionStorage.getItem(AUTH_USER_STORAGE_KEY)
    if (!raw) return null
    return normalizeUser(JSON.parse(raw) as User)
  } catch {
    return null
  }
}

function writeCachedAuthUser(user: User) {
  if (typeof window === "undefined") return
  try {
    window.sessionStorage.setItem(AUTH_USER_STORAGE_KEY, JSON.stringify(normalizeUser(user)))
  } catch {
    // Ignore storage errors so auth state still updates in memory.
  }
}

function clearCachedAuthUser() {
  if (typeof window === "undefined") return
  try {
    window.sessionStorage.removeItem(AUTH_USER_STORAGE_KEY)
  } catch {
    // Ignore storage errors so logout still clears in-memory auth.
  }
}

interface AuthStore {
  user: User | null
  hydrated: boolean
  setUser: (user: User) => void
  setHydrated: () => void
  logout: () => void
}

export const useAuthStore = create<AuthStore>()((set) => ({
  user: readCachedAuthUser(),
  hydrated: false,
  setUser: (user) => {
    const normalizedUser = normalizeUser(user)
    writeCachedAuthUser(normalizedUser)
    const previousUserId = useAuthStore.getState().user?.id ?? null
    if (previousUserId && previousUserId !== normalizedUser.id) {
      useUiPreferencesStore.getState().clearActiveUser()
      resetIdentity()
    }
    set({ user: normalizedUser, hydrated: true })
    void useUiPreferencesStore.getState().hydrateForUser(normalizedUser.id)
  },
  setHydrated: () => set({ hydrated: true }),
  logout: () => {
    clearCachedAuthUser()
    useUiPreferencesStore.getState().clearActiveUser()
    resetIdentity()
    set({ user: null, hydrated: true })
  },
}))
