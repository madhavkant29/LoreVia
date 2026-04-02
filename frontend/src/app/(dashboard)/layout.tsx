"use client"

import { useEffect } from "react"
import { Navbar } from "@/components/layout/Navbar"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const { theme } = usePreferencesStore()
  const isDark = theme === "dark"

  useEffect(() => {
    document.documentElement.dataset.theme = theme
  }, [theme])

  return (
    <div
      className={`min-h-screen transition-colors ${
        isDark
          ? "bg-[radial-gradient(circle_at_top_left,#1f2937,transparent_24%),radial-gradient(circle_at_top_right,#111827,transparent_28%),linear-gradient(180deg,#020617_0%,#0f172a_100%)] text-white"
          : "bg-[radial-gradient(circle_at_top_left,#fff2d6,transparent_24%),radial-gradient(circle_at_top_right,#e7f1ff,transparent_28%),linear-gradient(180deg,#f8f3eb_0%,#f7f7f5_100%)] text-stone-900"
      }`}
    >
      <Navbar />
      <main className="mx-auto max-w-6xl px-4 py-5 md:px-6 md:py-8">{children}</main>
    </div>
  )
}
