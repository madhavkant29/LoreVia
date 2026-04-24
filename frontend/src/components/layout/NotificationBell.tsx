"use client"

import Link from "next/link"
import { useState } from "react"
import { NotificationsPanel } from "@/components/layout/NotificationsPanel"
import { useNotifications } from "@/lib/hooks/useNotifications"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"

export function NotificationBell() {
  const [open, setOpen] = useState(false)
  const { theme } = usePreferencesStore()
  const { unreadCount } = useNotifications(10)
  const isDark = theme === "dark"

  return (
    <>
      <Link
        href="/notifications"
        className="relative flex h-10 w-10 items-center justify-center rounded-xl border border-border bg-card text-foreground transition-colors hover:bg-muted lg:hidden"
        aria-label="Open notifications"
      >
        <BellIcon />
        {unreadCount > 0 ? (
          <span className="absolute right-1 top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-rose-500 px-1 text-[10px] font-semibold text-white">
            {Math.min(unreadCount, 9)}
          </span>
        ) : null}
      </Link>

      <button
        type="button"
        onClick={() => setOpen((current) => !current)}
        className="relative hidden h-10 w-10 items-center justify-center rounded-xl border border-border bg-card text-foreground transition-colors hover:bg-muted lg:flex"
        aria-label="Toggle notifications"
      >
        <BellIcon />
        {unreadCount > 0 ? (
          <span className="absolute right-1 top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-rose-500 px-1 text-[10px] font-semibold text-white">
            {Math.min(unreadCount, 9)}
          </span>
        ) : null}
      </button>

      {open ? (
        <>
          <button
            type="button"
            onClick={() => setOpen(false)}
            className="fixed inset-0 z-40 hidden bg-black/30 lg:block"
            aria-label="Close notifications"
          />
          <aside className={`fixed right-0 top-0 z-50 hidden h-screen w-[26rem] border-l shadow-[-24px_0_70px_-38px_rgba(0,0,0,0.5)] lg:block ${isDark ? "border-white/10 bg-[#050505]" : "border-stone-200 bg-stone-50"}`}>
            <NotificationsPanel mode="sidebar" />
          </aside>
        </>
      ) : null}
    </>
  )
}

function BellIcon() {
  return (
    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M14.857 17H9.143m5.714 0H18l-1.286-1.286A2 2 0 0116 14.286V11a4 4 0 10-8 0v3.286a2 2 0 01-.714 1.428L6 17h3.143m5.714 0a3 3 0 11-5.714 0" />
    </svg>
  )
}
