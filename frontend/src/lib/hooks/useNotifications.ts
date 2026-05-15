"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { notificationsApi } from "@/lib/api/notifications"
import { asQueryKey, notificationsCacheKey } from "@/lib/query/cacheKeys"
import { useAuthStore } from "@/lib/stores/authStore"

const NOTIFICATIONS_CHANGED_EVENT = "notifications:changed"

function emitNotificationsChanged() {
  if (typeof window === "undefined") return
  window.dispatchEvent(new Event(NOTIFICATIONS_CHANGED_EVENT))
}

export function useNotifications(limit = 40) {
  const user = useAuthStore((state) => state.user)
  const [error, setError] = useState<string | null>(null)
  const queryClient = useQueryClient()
  const queryKey = useMemo(() => asQueryKey(notificationsCacheKey(limit)), [limit])

  const query = useQuery({
    queryKey,
    queryFn: () => notificationsApi.list(limit),
    enabled: Boolean(user),
  })

  const refresh = useCallback(async () => {
    setError(null)
    try {
      await queryClient.invalidateQueries({ queryKey })
    } catch {
      setError("Could not load notifications.")
    }
  }, [queryClient, queryKey])

  useEffect(() => {
    if (typeof window === "undefined") return

    const handleNotificationsChanged = () => {
      refresh()
    }

    window.addEventListener(NOTIFICATIONS_CHANGED_EVENT, handleNotificationsChanged)
    return () => window.removeEventListener(NOTIFICATIONS_CHANGED_EVENT, handleNotificationsChanged)
  }, [refresh])

  const markReadMutation = useMutation({
    mutationFn: (id: string) => notificationsApi.markRead(id),
    onSuccess: () => {
      emitNotificationsChanged()
    },
    onError: () => {
      setError("Could not update notification.")
    },
  })

  const markAllReadMutation = useMutation({
    mutationFn: () => notificationsApi.markAllRead(),
    onSuccess: () => {
      emitNotificationsChanged()
    },
    onError: () => {
      setError("Could not update notifications.")
    },
  })

  const markRead = useCallback(async (id: string) => {
    await markReadMutation.mutateAsync(id)
  }, [markReadMutation])

  const markAllRead = useCallback(async () => {
    await markAllReadMutation.mutateAsync()
  }, [markAllReadMutation])

  return {
    items: user ? query.data?.items ?? [] : [],
    unreadCount: user ? query.data?.unread_count ?? 0 : 0,
    loading: query.isLoading || query.isFetching,
    error: error ?? (query.isError ? "Could not load notifications." : null),
    refresh,
    markRead,
    markAllRead,
  }
}
