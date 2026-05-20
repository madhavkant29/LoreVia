"use client"

import Link from "next/link"
import dynamic from "next/dynamic"
import React from "react"
import { useState } from "react"

import { useChatUnreadCount } from "@/lib/hooks/useChatUnreadCount"
import { useAuthStore } from "@/lib/stores/authStore"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"

const ChatsPanel = dynamic(
  () => import("@/components/layout/ChatsPanel").then((module) => module.ChatsPanel),
  {
    ssr: false,
    loading: () => <PanelLoadingState label="Loading chats..." />,
  }
)

export function ChatLauncher({ enabled = true }: { enabled?: boolean }) {
  const [open, setOpen] = useState(false)
  const { theme } = usePreferencesStore()
  const { user } = useAuthStore()
  const { unreadCount } = useChatUnreadCount({
    enabled: enabled || open,
    pollMs: false,
    refreshOnFocus: true,
  })
  const isDark = theme === "dark"
  const hasUnread = unreadCount > 0
  const badgeLabel = hasUnread ? `${unreadCount > 9 ? "9+" : unreadCount}` : null
  const buttonTone = hasUnread
    ? "border-sky-400/40 bg-sky-500/10 text-sky-600 hover:bg-sky-500/15"
    : "border-border bg-card text-foreground hover:bg-muted"

  if (!user) {
    return null
  }

  return (
    <>
      <Link
        href="/chats"
        className={`relative flex h-10 w-10 items-center justify-center rounded-xl border transition-colors lg:hidden ${buttonTone}`}
        aria-label={hasUnread ? `Open direct messages, ${unreadCount} unread` : "Open direct messages"}
      >
        <ChatIcon hasUnread={hasUnread} />
        {badgeLabel ? (
          <span className="absolute -right-0.5 -top-0.5 flex min-h-4 min-w-4 items-center justify-center rounded-full bg-sky-500 px-1 text-[10px] font-semibold text-white ring-2 ring-background shadow-sm shadow-sky-500/30">
            {badgeLabel}
          </span>
        ) : null}
      </Link>

      <button
        type="button"
        onClick={() => setOpen((current) => !current)}
        className={`relative hidden h-10 w-10 items-center justify-center rounded-xl border transition-colors lg:flex ${buttonTone}`}
        aria-label={hasUnread ? `Toggle direct messages, ${unreadCount} unread` : "Toggle direct messages"}
      >
        <ChatIcon hasUnread={hasUnread} />
        {badgeLabel ? (
          <span className="absolute -right-0.5 -top-0.5 flex min-h-4 min-w-4 items-center justify-center rounded-full bg-sky-500 px-1 text-[10px] font-semibold text-white ring-2 ring-background shadow-sm shadow-sky-500/30">
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
            aria-label="Close chats"
          />
          <aside className={`fixed right-0 top-0 z-50 hidden h-screen w-[min(50vw,56rem)] border-l shadow-[-24px_0_70px_-38px_rgba(0,0,0,0.5)] lg:block ${isDark ? "border-white/10 bg-[#05070a]" : "border-slate-200 bg-white"}`}>
            <ChatsPanel mode="sidebar" />
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

function ChatIcon({ hasUnread }: { hasUnread: boolean }) {
  return (
    <svg className={`h-5 w-5 transition-colors ${hasUnread ? "text-sky-500" : ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M7 8h10M7 12h7m-9 8 2.86-2H18a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h1v2Z" />
    </svg>
  )
}
