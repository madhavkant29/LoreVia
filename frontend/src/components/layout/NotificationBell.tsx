"use client"

import Link from "next/link"
import dynamic from "next/dynamic"
import React from "react"
import { useState } from "react"
import { useNotificationsState } from "@/lib/hooks/useNotifications"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"

const NotificationsPanel = dynamic(
  () => import("@/components/layout/NotificationsPanel").then((module) => module.NotificationsPanel),
  {
    ssr: false,
    loading: () => <PanelLoadingState label="Loading notifications..." />,
  }
)

export function NotificationBell({ enabled = true }: { enabled?: boolean }) {
  const [open, setOpen] = useState(false)
  const { theme } = usePreferencesStore()
  const { unreadCount } = useNotificationsState(10, {
    enabled: enabled || open,
    pollMs: false,
    refreshOnFocus: true,
    syncRevisionDigests: open,
  })
  const isDark = theme === "dark"
  const hasUnread = unreadCount > 0
  const badgeLabel = hasUnread ? `${unreadCount > 9 ? "9+" : unreadCount}` : null
  const buttonTone = hasUnread
    ? "border-rose-400/40 bg-rose-500/10 text-rose-600 hover:bg-rose-500/15"
    : "border-border bg-card text-foreground hover:bg-muted"
  const ariaLabel = hasUnread ? `Open notifications, ${unreadCount} unread` : "Open notifications"

  return (
    <>
      <Link
        href="/notifications"
        className={`relative flex h-10 w-10 items-center justify-center rounded-xl border transition-colors lg:hidden ${buttonTone}`}
        aria-label={ariaLabel}
      >
        <BellIcon hasUnread={hasUnread} />
        {badgeLabel ? (
          <span className="absolute -right-0.5 -top-0.5 flex min-h-4 min-w-4 items-center justify-center rounded-full bg-rose-500 px-1 text-[10px] font-semibold text-white ring-2 ring-background shadow-sm shadow-rose-500/30">
            {badgeLabel}
          </span>
        ) : null}
      </Link>

      <button
        type="button"
        onClick={() => setOpen((current) => !current)}
        className={`relative hidden h-10 w-10 items-center justify-center rounded-xl border transition-colors lg:flex ${buttonTone}`}
        aria-label={hasUnread ? `Toggle notifications, ${unreadCount} unread` : "Toggle notifications"}
      >
        <BellIcon hasUnread={hasUnread} />
        {badgeLabel ? (
          <span className="absolute -right-0.5 -top-0.5 flex min-h-4 min-w-4 items-center justify-center rounded-full bg-rose-500 px-1 text-[10px] font-semibold text-white ring-2 ring-background shadow-sm shadow-rose-500/30">
            {badgeLabel}
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

function PanelLoadingState({ label }: { label: string }) {
  return (
    <div className="flex h-full items-center justify-center p-6 text-sm text-muted-foreground">
      {label}
    </div>
  )
}

function BellIcon({ hasUnread }: { hasUnread: boolean }) {
  return (
    <svg className={`h-5 w-5 transition-colors ${hasUnread ? "text-rose-500" : ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M14.857 17H9.143m5.714 0H18l-1.286-1.286A2 2 0 0116 14.286V11a4 4 0 10-8 0v3.286a2 2 0 01-.714 1.428L6 17h3.143m5.714 0a3 3 0 11-5.714 0" />
    </svg>
  )
}
