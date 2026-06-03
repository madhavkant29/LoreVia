"use client"

import Link from "next/link"
import dynamic from "next/dynamic"
import React, { memo, useEffect, useRef, useState } from "react"
import { useNotificationsState } from "@/lib/hooks/useNotifications"
import { prefetchNotificationsSidebarData } from "@/lib/query/sidebarPrefetch"
import { useAuthStore } from "@/lib/stores/authStore"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"

type NotificationsPanelProps = {
  mode?: "sidebar" | "page"
  enabled?: boolean
}

type PreloadableComponent<Props> = React.ComponentType<Props> & {
  preload?: () => void
}

const loadNotificationsPanel = () => import("@/components/layout/NotificationsPanel").then((module) => module.NotificationsPanel)

const NotificationsPanel = dynamic<NotificationsPanelProps>(
  loadNotificationsPanel,
  {
    ssr: false,
    loading: () => <PanelLoadingState label="Loading notifications..." />,
  }
) as PreloadableComponent<NotificationsPanelProps>

function preloadNotificationsPanel() {
  if (NotificationsPanel.preload) {
    NotificationsPanel.preload()
    return
  }
  void loadNotificationsPanel()
}

export const NotificationBell = memo(function NotificationBell({ enabled = true }: { enabled?: boolean }) {
  const [open, setOpen] = useState(false)
  const [panelMounted, setPanelMounted] = useState(false)
  const toggleButtonRef = useRef<HTMLButtonElement | null>(null)
  const panelRef = useRef<HTMLElement | null>(null)
  const { user } = useAuthStore()
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

  const preloadPanelAssets = () => {
    preloadNotificationsPanel()
    if (user) {
      void prefetchNotificationsSidebarData()
    }
  }

  const togglePanel = () => {
    preloadPanelAssets()
    setPanelMounted(true)
    setOpen((current) => !current)
  }

  useEffect(() => {
    if (!open) {
      return
    }

    const handlePointerDown = (event: MouseEvent) => {
      const target = event.target
      if (!(target instanceof Node)) {
        return
      }
      if (toggleButtonRef.current?.contains(target) || panelRef.current?.contains(target)) {
        return
      }
      setOpen(false)
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false)
      }
    }

    document.addEventListener("mousedown", handlePointerDown)
    document.addEventListener("keydown", handleKeyDown)

    return () => {
      document.removeEventListener("mousedown", handlePointerDown)
      document.removeEventListener("keydown", handleKeyDown)
    }
  }, [open])

  return (
    <>
      <Link
        href="/notifications"
        className={`relative flex h-10 w-10 items-center justify-center rounded-xl border transition-colors lg:hidden ${buttonTone}`}
        aria-label={ariaLabel}
      >
        <BellIcon hasUnread={hasUnread} />
        {badgeLabel ? (
          <span className="absolute -right-0.5 -top-0.5 flex min-h-4 min-w-4 items-center justify-center rounded-full bg-rose-500 px-1 text-3xs font-semibold text-white ring-2 ring-background shadow-sm shadow-rose-500/30">
            {badgeLabel}
          </span>
        ) : null}
      </Link>

      <button
        ref={toggleButtonRef}
        type="button"
        onMouseEnter={preloadPanelAssets}
        onFocus={preloadPanelAssets}
        onClick={togglePanel}
        className={`relative hidden h-10 w-10 items-center justify-center rounded-xl border transition-colors lg:flex ${buttonTone}`}
        aria-label={hasUnread ? `Toggle notifications, ${unreadCount} unread` : "Toggle notifications"}
        aria-expanded={open}
      >
        <BellIcon hasUnread={hasUnread} />
        {badgeLabel ? (
          <span className="absolute -right-0.5 -top-0.5 flex min-h-4 min-w-4 items-center justify-center rounded-full bg-rose-500 px-1 text-3xs font-semibold text-white ring-2 ring-background shadow-sm shadow-rose-500/30">
            {badgeLabel}
          </span>
        ) : null}
      </button>

      {panelMounted ? (
        <>
          <div
            className={`fixed inset-0 z-40 hidden bg-black/30 transition-opacity lg:block ${open ? "opacity-100" : "pointer-events-none opacity-0"}`}
            aria-hidden="true"
          />
          <aside
            ref={panelRef}
            inert={open ? undefined : true}
            aria-hidden={!open}
            className={`fixed right-0 top-0 z-50 hidden h-screen w-[26rem] border-l transition duration-150 lg:block ${open ? "translate-x-0 opacity-100" : "pointer-events-none translate-x-full opacity-0"} ${isDark ? "border-white/10 bg-[#050505]" : "border-stone-200 bg-stone-50"}`}
          >
            <NotificationsPanel mode="sidebar" enabled={open} />
          </aside>
        </>
      ) : null}
    </>
  )
})

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
