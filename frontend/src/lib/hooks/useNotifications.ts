"use client"

import { useCallback, useEffect, useState } from "react"
import { notificationsApi } from "@/lib/api/notifications"
import { useAuthStore } from "@/lib/stores/authStore"
import type { NotificationItem } from "@/types/notifications"

export function useNotifications(limit = 40) {
  const user = useAuthStore((state) => state.user)
  const [items, setItems] = useState<NotificationItem[]>([])
  const [unreadCount, setUnreadCount] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    if (!user) {
      setItems([])
      setUnreadCount(0)
      return
    }
    setLoading(true)
    setError(null)
    try {
      const response = await notificationsApi.list(limit)
      setItems(response.items)
      setUnreadCount(response.unread_count)
    } catch {
      setError("Could not load notifications.")
    } finally {
      setLoading(false)
    }
  }, [limit, user])

  useEffect(() => {
    refresh()
  }, [refresh])

  const markRead = useCallback(async (id: string) => {
    try {
      const updated = await notificationsApi.markRead(id)
      setItems((current) => current.map((item) => item.id === id ? updated : item))
      setUnreadCount((current) => Math.max(0, current - 1))
    } catch {
      setError("Could not update notification.")
    }
  }, [])

  const markAllRead = useCallback(async () => {
    try {
      const response = await notificationsApi.markAllRead()
      setItems(response.items)
      setUnreadCount(response.unread_count)
    } catch {
      setError("Could not update notifications.")
    }
  }, [])

  return {
    items,
    unreadCount,
    loading,
    error,
    refresh,
    markRead,
    markAllRead,
  }
}
