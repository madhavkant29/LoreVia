"use client"

import { NotificationsPanel } from "@/components/layout/NotificationsPanel"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"

export default function NotificationsPage() {
  const { theme } = usePreferencesStore()
  const isDark = theme === "dark"

  return (
    <div className={`min-h-screen transition-colors ${isDark ? "bg-[linear-gradient(180deg,#000000_0%,#060606_44%,#0d0d0d_100%)] text-slate-100" : "bg-stone-50 text-stone-950"}`}>
      <NotificationsPanel mode="page" />
    </div>
  )
}
