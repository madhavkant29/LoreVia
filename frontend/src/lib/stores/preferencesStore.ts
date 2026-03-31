"use client"

import { create } from "zustand"
import { persist } from "zustand/middleware"

export type AppTheme = "light" | "dark"

interface PreferencesStore {
  theme: AppTheme
  setTheme: (theme: AppTheme) => void
  toggleTheme: () => void
}

export const usePreferencesStore = create<PreferencesStore>()(
  persist(
    (set, get) => ({
      theme: "light",
      setTheme: (theme) => {
        if (typeof window !== "undefined") {
          window.localStorage.setItem("app-theme", theme)
          window.localStorage.setItem("reader-theme", theme)
          document.documentElement.dataset.theme = theme
        }
        set({ theme })
      },
      toggleTheme: () => {
        const next = get().theme === "dark" ? "light" : "dark"
        if (typeof window !== "undefined") {
          window.localStorage.setItem("app-theme", next)
          window.localStorage.setItem("reader-theme", next)
          document.documentElement.dataset.theme = next
        }
        set({ theme: next })
      },
    }),
    {
      name: "lorevia-preferences",
      onRehydrateStorage: () => (state) => {
        if (typeof window !== "undefined" && state?.theme) {
          window.localStorage.setItem("app-theme", state.theme)
          window.localStorage.setItem("reader-theme", state.theme)
          document.documentElement.dataset.theme = state.theme
        }
      },
    }
  )
)
