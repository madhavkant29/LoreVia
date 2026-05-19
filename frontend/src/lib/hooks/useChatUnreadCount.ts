"use client"

import { useCallback, useEffect, useState } from "react"

import { socialApi } from "@/lib/api/social"
import { useAuthStore } from "@/lib/stores/authStore"

const CHATS_CHANGED_EVENT = "chats:changed"
const CHAT_UNREAD_POLL_MS = 30000

export function emitChatsChanged() {
  if (typeof window === "undefined") return
  window.dispatchEvent(new Event(CHATS_CHANGED_EVENT))
}

export function useChatUnreadCount() {
  const { user, hydrated } = useAuthStore()
  const [unreadCount, setUnreadCount] = useState(0)

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
    if (!hydrated) return
    void refresh()
  }, [hydrated, refresh])

  useEffect(() => {
    if (!user) return

    const intervalId = window.setInterval(() => {
      void refresh()
    }, CHAT_UNREAD_POLL_MS)

    return () => window.clearInterval(intervalId)
  }, [refresh, user])

  useEffect(() => {
    if (typeof window === "undefined") return

    const handleChatsChanged = () => {
      void refresh()
    }

    const handleFocus = () => {
      void refresh()
    }

    window.addEventListener(CHATS_CHANGED_EVENT, handleChatsChanged)
    window.addEventListener("focus", handleFocus)
    return () => {
      window.removeEventListener(CHATS_CHANGED_EVENT, handleChatsChanged)
      window.removeEventListener("focus", handleFocus)
    }
  }, [refresh])

  return { unreadCount, hydrated }
}
