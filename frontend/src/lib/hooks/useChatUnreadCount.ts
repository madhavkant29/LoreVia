"use client"

import { useCallback, useEffect, useState } from "react"

import { socialApi } from "@/lib/api/social"
import { useAuthStore } from "@/lib/stores/authStore"

const CHATS_CHANGED_EVENT = "chats:changed"

type UseChatUnreadCountOptions = {
  enabled?: boolean
  pollMs?: number | false
  refreshOnFocus?: boolean
}

export function emitChatsChanged() {
  if (typeof window === "undefined") return
  window.dispatchEvent(new Event(CHATS_CHANGED_EVENT))
}

export function useChatUnreadCount(options: UseChatUnreadCountOptions = {}) {
  const { user, hydrated } = useAuthStore()
  const [unreadCount, setUnreadCount] = useState(0)
  const enabled = options.enabled ?? true
  const pollMs = options.pollMs ?? 30_000
  const refreshOnFocus = options.refreshOnFocus ?? true

  const refresh = useCallback(async () => {
    if (!user) {
      setUnreadCount(0)
      return
    }
    try {
      const payload = await socialApi.listConversations()
      setUnreadCount(payload.unread_count)
    } catch {
      // Keep the last known count if refresh fails.
    }
  }, [user])

  useEffect(() => {
    if (!hydrated || !enabled) return
    void refresh()
  }, [enabled, hydrated, refresh])

  useEffect(() => {
    if (!user || !enabled || !pollMs) return

    const intervalId = window.setInterval(() => {
      void refresh()
    }, pollMs)

    return () => window.clearInterval(intervalId)
  }, [enabled, pollMs, refresh, user])

  useEffect(() => {
    if (typeof window === "undefined") return

    const handleChatsChanged = () => {
      void refresh()
    }

    const handleFocus = () => {
      if (!refreshOnFocus) return
      void refresh()
    }

    window.addEventListener(CHATS_CHANGED_EVENT, handleChatsChanged)
    window.addEventListener("focus", handleFocus)
    return () => {
      window.removeEventListener(CHATS_CHANGED_EVENT, handleChatsChanged)
      window.removeEventListener("focus", handleFocus)
    }
  }, [refresh, refreshOnFocus])

  return { unreadCount, hydrated }
}
