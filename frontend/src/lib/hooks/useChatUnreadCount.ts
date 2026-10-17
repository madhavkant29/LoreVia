"use client"

import { useCallback, useEffect, useState } from "react"

import { socialApi } from "@/lib/api/social"
import { useAuthStore } from "@/lib/stores/authStore"
import { useAdaptivePolling } from "./useAdaptivePolling"

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

  const poll = useCallback(async ({ signal }: { signal: AbortSignal }) => {
    if (!user) {
      setUnreadCount(0)
      return { unread_count: 0 }
    }
    try {
      const payload = await socialApi.getConversationUnreadCount({ signal })
      if (!signal.aborted) {
        setUnreadCount(payload.unread_count)
      }
      return payload
    } catch (error) {
      // Keep the last known count if refresh fails.
      if (pollMs === false && !signal.aborted) {
        return null
      }
      if (signal.aborted) throw error
      throw new Error("Could not refresh chat unread count.")
    }
  }, [pollMs, user])

  const { refresh } = useAdaptivePolling({
    enabled: Boolean(hydrated && enabled && user),
    poll,
    getProgress: (result) => result?.unread_count,
    isTerminal: pollMs === false ? () => true : undefined,
    initialDelayMs: typeof pollMs === "number" ? pollMs : 30_000,
    maxDelayMs: typeof pollMs === "number" ? Math.max(pollMs * 4, pollMs) : 30_000,
    resetKey: user?.id,
  })

  useEffect(() => {
    if (user) return
    setUnreadCount(0)
  }, [user])

  useEffect(() => {
    if (typeof window === "undefined") return

    const handleChatsChanged = () => refresh()

    const handleFocus = () => {
      if (!refreshOnFocus) return
      refresh()
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
