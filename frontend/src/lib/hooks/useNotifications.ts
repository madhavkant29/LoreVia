"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import { type QueryClient, useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { notificationsApi } from "@/lib/api/notifications"
import { asQueryKey, notificationsCacheKey } from "@/lib/query/cacheKeys"
import { useAuthStore } from "@/lib/stores/authStore"
import type { NotificationItem, NotificationListResponse } from "@/types/notifications"

const NOTIFICATIONS_CHANGED_EVENT = "notifications:changed"
const NOTIFICATIONS_LIST_QUERY_PREFIX = "notifications:list:"

type UseNotificationsOptions = {
  enabled?: boolean
  pollMs?: number | false
  refreshOnFocus?: boolean
  syncRevisionDigests?: boolean
}

function emitNotificationsChanged() {
  if (typeof window === "undefined") return
  window.dispatchEvent(new Event(NOTIFICATIONS_CHANGED_EVENT))
}

function isNotificationsListQuery(queryKey: readonly unknown[]) {
  const [firstKey] = queryKey
  return typeof firstKey === "string" && firstKey.startsWith(NOTIFICATIONS_LIST_QUERY_PREFIX)
}

function updateNotificationListCache(
  current: NotificationListResponse | undefined,
  updateItem: (item: NotificationItem) => NotificationItem
) {
  if (!current) return current

  let unreadDelta = 0
  const items = current.items.map((item) => {
    const wasUnread = !item.read_at
    const nextItem = updateItem(item)
    if (wasUnread && nextItem.read_at) {
      unreadDelta += 1
    }
    return nextItem
  })

  return {
    ...current,
    items,
    unread_count: Math.max(0, current.unread_count - unreadDelta),
  }
}

export function applyNotificationReadToNotificationCaches(
  queryClient: QueryClient,
  notification: NotificationItem
) {
  queryClient.setQueriesData<NotificationListResponse>(
    { predicate: (query) => isNotificationsListQuery(query.queryKey) },
    (current) =>
      updateNotificationListCache(current, (item) =>
        item.id === notification.id
          ? { ...item, read_at: notification.read_at ?? item.read_at }
          : item
      )
  )
}

export function applyAllNotificationsReadToNotificationCaches(
  queryClient: QueryClient,
  response: NotificationListResponse
) {
  const readAtById = new Map(response.items.map((item) => [item.id, item.read_at]))
  const fallbackReadAt = new Date().toISOString()

  queryClient.setQueriesData<NotificationListResponse>(
    { predicate: (query) => isNotificationsListQuery(query.queryKey) },
    (current) => {
      if (!current) return current
      return {
        ...current,
        items: current.items.map((item) => ({
          ...item,
          read_at: item.read_at ?? readAtById.get(item.id) ?? fallbackReadAt,
        })),
        unread_count: 0,
      }
    }
  )
}

async function invalidateNotificationListQueries(queryClient: QueryClient) {
  await queryClient.invalidateQueries({
    predicate: (query) => isNotificationsListQuery(query.queryKey),
  })
}

export function useNotifications(limit = 40) {
  return useNotificationsState(limit)
}

export function useNotificationsState(limit = 40, options: UseNotificationsOptions = {}) {
  const user = useAuthStore((state) => state.user)
  const [error, setError] = useState<string | null>(null)
  const [isDocumentVisible, setIsDocumentVisible] = useState(
    typeof document === "undefined" ? true : document.visibilityState === "visible"
  )
  const queryClient = useQueryClient()
  const queryKey = useMemo(() => asQueryKey(notificationsCacheKey(limit)), [limit])
  const enabled = options.enabled ?? true
  const pollMs = options.pollMs ?? 30_000
  const refreshOnFocus = options.refreshOnFocus ?? false
  const syncRevisionDigests = options.syncRevisionDigests ?? true

  const query = useQuery({
    queryKey,
    queryFn: () => notificationsApi.list(limit, { syncRevisionDigests }),
    enabled: Boolean(user) && enabled,
    refetchInterval: user && enabled && pollMs && isDocumentVisible ? pollMs : false,
    refetchIntervalInBackground: false,
  })

  const refresh = useCallback(async () => {
    setError(null)
    try {
      await invalidateNotificationListQueries(queryClient)
    } catch {
      setError("Could not load notifications.")
    }
  }, [queryClient])

  useEffect(() => {
    if (typeof window === "undefined") return

    const handleNotificationsChanged = () => {
      void refresh()
    }

    const handleFocus = () => {
      if (!refreshOnFocus) return
      void refresh()
    }

    const handleVisibilityChange = () => {
      const visible = document.visibilityState === "visible"
      setIsDocumentVisible(visible)
      if (visible && refreshOnFocus) {
        void refresh()
      }
    }

    window.addEventListener(NOTIFICATIONS_CHANGED_EVENT, handleNotificationsChanged)
    window.addEventListener("focus", handleFocus)
    document.addEventListener("visibilitychange", handleVisibilityChange)
    return () => {
      window.removeEventListener(NOTIFICATIONS_CHANGED_EVENT, handleNotificationsChanged)
      window.removeEventListener("focus", handleFocus)
      document.removeEventListener("visibilitychange", handleVisibilityChange)
    }
  }, [refresh, refreshOnFocus])

  const markReadMutation = useMutation({
    mutationFn: (id: string) => notificationsApi.markRead(id),
    onSuccess: (notification) => {
      applyNotificationReadToNotificationCaches(queryClient, notification)
      emitNotificationsChanged()
    },
    onError: () => {
      setError("Could not update notification.")
    },
  })

  const markAllReadMutation = useMutation({
    mutationFn: () => notificationsApi.markAllRead(),
    onSuccess: (response) => {
      applyAllNotificationsReadToNotificationCaches(queryClient, response)
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
