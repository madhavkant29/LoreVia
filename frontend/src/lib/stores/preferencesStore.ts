"use client"

import { create } from "zustand"
import { persist } from "zustand/middleware"

export type AppTheme = "light" | "dark"

interface PreferencesStore {
  theme: AppTheme
  setTheme: (theme: AppTheme) => void
  toggleTheme: () => void
  timelineCollapsedSections: Record<string, boolean>
  setTimelineCollapsedSection: (sectionId: string, collapsed: boolean) => void
  setTimelineAllCollapsed: (collapsed: boolean) => void
}

export const usePreferencesStore = create<PreferencesStore>()(
  persist(
    (set, get) => ({
      theme: "light",
      timelineCollapsedSections: { characters: true, plotThreads: true, relationships: true },
      setTheme: (theme) => {
        if (typeof window !== "undefined") {
          window.localStorage.setItem("app-theme", theme)
          window.localStorage.setItem("reader-theme", theme)
          document.documentElement.dataset.theme = theme
          if (theme === "dark") {
            document.documentElement.classList.add("dark")
          } else {
            document.documentElement.classList.remove("dark")
          }
        }
        set({ theme })
      },
      toggleTheme: () => {
        const next = get().theme === "dark" ? "light" : "dark"
        if (typeof window !== "undefined") {
          window.localStorage.setItem("app-theme", next)
          window.localStorage.setItem("reader-theme", next)
          document.documentElement.dataset.theme = next
          if (next === "dark") {
            document.documentElement.classList.add("dark")
          } else {
            document.documentElement.classList.remove("dark")
          }
        }
        set({ theme: next })
      },
      setTimelineCollapsedSection: (sectionId, collapsed) => {
        set((state) => ({
          timelineCollapsedSections: { ...state.timelineCollapsedSections, [sectionId]: collapsed },
        }))
      },
      setTimelineAllCollapsed: (collapsed) => {
        set({
          timelineCollapsedSections: { characters: collapsed, plotThreads: collapsed, relationships: collapsed },
        })
      },
    }),
    {
      name: "lorevia-preferences",
      onRehydrateStorage: () => (state) => {
        if (typeof window !== "undefined" && state?.theme) {
          window.localStorage.setItem("app-theme", state.theme)
          window.localStorage.setItem("reader-theme", state.theme)
          document.documentElement.dataset.theme = state.theme
          if (state.theme === "dark") {
            document.documentElement.classList.add("dark")
          } else {
            document.documentElement.classList.remove("dark")
          }
        }
      },
    }
  )
)
