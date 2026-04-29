"use client"

import { useCallback, useEffect } from "react"
import { useAuthStore } from "@/lib/stores/authStore"
import { useNotificationsStore } from "@/lib/stores/notificationsStore"

export function useNotifications(limit = 40) {
  const user = useAuthStore((state) => state.user)
  const items = useNotificationsStore((state) => state.items)
  const unreadCount = useNotificationsStore((state) => state.unreadCount)
  const loading = useNotificationsStore((state) => state.loading)
  const error = useNotificationsStore((state) => state.error)
  const initialized = useNotificationsStore((state) => state.initialized)
  const lastUserId = useNotificationsStore((state) => state.lastUserId)
  const listLimit = useNotificationsStore((state) => state.listLimit)
  const resetStore = useNotificationsStore((state) => state.reset)
  const refreshStore = useNotificationsStore((state) => state.refresh)
  const markReadStore = useNotificationsStore((state) => state.markRead)
  const markAllReadStore = useNotificationsStore((state) => state.markAllRead)

  const refresh = useCallback(async () => {
    if (!user) {
      resetStore()
      return
    }
    await refreshStore(user.id, limit)
  }, [limit, refreshStore, resetStore, user])

  useEffect(() => {
    if (!user) {
      resetStore()
      return
    }
    if (lastUserId && lastUserId !== user.id) {
      resetStore()
      void refreshStore(user.id, limit)
      return
    }
    if (!initialized || lastUserId !== user.id || limit > listLimit) {
      void refreshStore(user.id, limit)
    }
  }, [initialized, lastUserId, limit, listLimit, refreshStore, resetStore, user])

  const markRead = useCallback(async (id: string) => {
    if (!user) {
      return
    }
    await markReadStore(user.id, id, limit)
  }, [limit, markReadStore, user])

  const markAllRead = useCallback(async () => {
    if (!user) {
      return
    }
    await markAllReadStore(user.id, limit)
  }, [limit, markAllReadStore, user])

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
