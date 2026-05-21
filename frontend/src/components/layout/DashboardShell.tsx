"use client"

import { useEffect } from "react"
import { Navbar } from "@/components/layout/Navbar"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"

export function DashboardShell({ children }: { children: React.ReactNode }) {
  const { theme } = usePreferencesStore()

  useEffect(() => {
    document.documentElement.dataset.theme = theme
  }, [theme])

  return (
    <div className="app-shell min-h-screen transition-colors duration-300">
      <div className="app-shell__mesh" />
      <Navbar />
      <main className="relative mx-auto max-w-7xl px-4 py-8 md:px-8 lg:px-10">
        {children}
      </main>
    </div>
  )
}
