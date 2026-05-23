"use client"

import dynamic from "next/dynamic"

import { usePreferencesStore } from "@/lib/stores/preferencesStore"

const NotificationsPanel = dynamic(
  () => import("@/components/layout/NotificationsPanel").then((module) => module.NotificationsPanel),
  {
    ssr: false,
    loading: () => <div className="min-h-screen rounded-[1.5rem] border p-6" />,
  }
)

export default function NotificationsPage() {
  const { theme } = usePreferencesStore()
  const isDark = theme === "dark"

  return (
    <div className={`min-h-screen transition-colors ${isDark ? "bg-[linear-gradient(180deg,#000000_0%,#060606_44%,#0d0d0d_100%)] text-slate-100" : "bg-stone-50 text-stone-950"}`}>
      <NotificationsPanel mode="page" />
    </div>
  )
}
