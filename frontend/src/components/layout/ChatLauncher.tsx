"use client"

import Link from "next/link"
import dynamic from "next/dynamic"
import React, { memo, useEffect, useRef, useState } from "react"

import { useChatUnreadCount } from "@/lib/hooks/useChatUnreadCount"
import { prefetchChatsSidebarData } from "@/lib/query/sidebarPrefetch"
import { useAuthStore } from "@/lib/stores/authStore"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"

type ChatsPanelProps = {
  mode?: "sidebar" | "page"
  enabled?: boolean
}

type PreloadableComponent<Props> = React.ComponentType<Props> & {
  preload?: () => void
}

const loadChatsPanel = () => import("@/components/layout/ChatsPanel").then((module) => module.ChatsPanel)

const ChatsPanel = dynamic<ChatsPanelProps>(
  loadChatsPanel,
  {
    ssr: false,
    loading: () => <PanelLoadingState label="Loading chats..." />,
  }
) as PreloadableComponent<ChatsPanelProps>

function preloadChatsPanel() {
  if (ChatsPanel.preload) {
    ChatsPanel.preload()
    return
  }
  void loadChatsPanel()
}

export const ChatLauncher = memo(function ChatLauncher({ enabled = true }: { enabled?: boolean }) {
  const [open, setOpen] = useState(false)
  const [panelMounted, setPanelMounted] = useState(false)
  const toggleButtonRef = useRef<HTMLButtonElement | null>(null)
  const panelRef = useRef<HTMLElement | null>(null)
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

  const preloadPanelAssets = () => {
    preloadChatsPanel()
    if (user) {
      void prefetchChatsSidebarData()
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
          <span className="absolute -right-0.5 -top-0.5 flex min-h-4 min-w-4 items-center justify-center rounded-full bg-sky-500 px-1 text-3xs font-semibold text-white ring-2 ring-background shadow-sm shadow-sky-500/30">
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
        aria-label={hasUnread ? `Toggle direct messages, ${unreadCount} unread` : "Toggle direct messages"}
        aria-expanded={open}
      >
        <ChatIcon hasUnread={hasUnread} />
        {badgeLabel ? (
          <span className="absolute -right-0.5 -top-0.5 flex min-h-4 min-w-4 items-center justify-center rounded-full bg-sky-500 px-1 text-3xs font-semibold text-white ring-2 ring-background shadow-sm shadow-sky-500/30">
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
            className={`fixed right-0 top-0 z-50 hidden h-screen w-[min(50vw,56rem)] border-l transition duration-150 lg:block ${open ? "translate-x-0 opacity-100" : "pointer-events-none translate-x-full opacity-0"} ${isDark ? "border-white/10 bg-[#05070a]" : "border-slate-200 bg-white"}`}
          >
            <ChatsPanel mode="sidebar" enabled={open} />
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

function ChatIcon({ hasUnread }: { hasUnread: boolean }) {
  return (
    <svg className={`h-5 w-5 transition-colors ${hasUnread ? "text-sky-500" : ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M7 8h10M7 12h7m-9 8 2.86-2H18a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h1v2Z" />
    </svg>
  )
}
