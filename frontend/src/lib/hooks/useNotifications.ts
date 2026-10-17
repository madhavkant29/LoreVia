"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import {
  type InfiniteData,
  type QueryClient,
  useInfiniteQuery,
  useMutation,
  useQueryClient,
} from "@tanstack/react-query"

import { notificationsApi } from "@/lib/api/notifications"
import { asQueryKey, notificationsCacheKey } from "@/lib/query/cacheKeys"
import { useAuthStore } from "@/lib/stores/authStore"
import type { NotificationItem, NotificationListResponse } from "@/types/notifications"
import { useAdaptivePolling } from "./useAdaptivePolling"

const NOTIFICATIONS_CHANGED_EVENT = "notifications:changed"
const NOTIFICATIONS_LIST_QUERY_PREFIX = "notifications:list:"

type UseNotificationsOptions = {
  enabled?: boolean
  pollMs?: number | false
  refreshOnFocus?: boolean
}

function emitNotificationsChanged() {
  if (typeof window === "undefined") return
  window.dispatchEvent(new Event(NOTIFICATIONS_CHANGED_EVENT))
}

function isNotificationsListQuery(queryKey: readonly unknown[]) {
  const [firstKey] = queryKey
  return typeof firstKey === "string" && firstKey.startsWith(NOTIFICATIONS_LIST_QUERY_PREFIX)
}

function notificationItems(page: NotificationListResponse | undefined): NotificationItem[] {
  return Array.isArray(page?.items) ? page.items : []
}

function updateNotificationListPage(
  current: NotificationListResponse,
  updateItem: (item: NotificationItem) => NotificationItem
) {
  let unreadDelta = 0
  const items = notificationItems(current).map((item) => {
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

function isInfiniteNotificationData(
  current: NotificationListResponse | InfiniteData<NotificationListResponse> | undefined,
): current is InfiniteData<NotificationListResponse> {
  return Boolean(current && "pages" in current && Array.isArray(current.pages))
}

function ensureInfiniteNotificationCache(
  queryClient: QueryClient,
  queryKey: readonly unknown[],
) {
  const current = queryClient.getQueryData<NotificationListResponse | InfiniteData<NotificationListResponse>>(queryKey)
  if (!current || isInfiniteNotificationData(current)) return

  queryClient.setQueryData<InfiniteData<NotificationListResponse>>(queryKey, {
    pages: [current],
    pageParams: [null],
  })
}

function updateNotificationListCache(
  current: NotificationListResponse | InfiniteData<NotificationListResponse> | undefined,
  updateItem: (item: NotificationItem) => NotificationItem,
) {
  if (!current) return current
  if (isInfiniteNotificationData(current)) {
    return {
      ...current,
      pages: current.pages.map((page) => updateNotificationListPage(page, updateItem)),
    }
  }
  return updateNotificationListPage(current, updateItem)
}

export function applyNotificationReadToNotificationCaches(
  queryClient: QueryClient,
  notification: NotificationItem
) {
  queryClient.setQueriesData<NotificationListResponse | InfiniteData<NotificationListResponse>>(
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
  const readAtById = new Map(notificationItems(response).map((item) => [item.id, item.read_at]))
  const fallbackReadAt = new Date().toISOString()

  const markPageRead = (current: NotificationListResponse): NotificationListResponse => ({
    ...current,
    items: notificationItems(current).map((item) => ({
      ...item,
      read_at: item.read_at ?? readAtById.get(item.id) ?? fallbackReadAt,
    })),
    unread_count: 0,
  })

  queryClient.setQueriesData<NotificationListResponse | InfiniteData<NotificationListResponse>>(
    { predicate: (query) => isNotificationsListQuery(query.queryKey) },
    (current) => {
      if (!current) return current
      if (isInfiniteNotificationData(current)) {
        return { ...current, pages: current.pages.map(markPageRead) }
      }
      return {
        ...markPageRead(current),
      }
    }
  )
}

function notificationPageIdentity(page: NotificationListResponse) {
  return `${page.next_cursor ?? ""}:${notificationItems(page).map((item) => item.id).join("|")}`
}

function replacePolledNotificationPage(
  queryClient: QueryClient,
  queryKey: readonly unknown[],
  page: NotificationListResponse,
) {
  queryClient.setQueryData<InfiniteData<NotificationListResponse>>(queryKey, (current) => {
    if (!isInfiniteNotificationData(current)) {
      return { pages: [page], pageParams: [null] }
    }

    const firstPage = current.pages[0]
    // A changed first page shifts cursor boundaries. Drop stale later pages to
    // avoid showing duplicate or skipped notifications; they can be loaded again.
    if (!firstPage || notificationPageIdentity(firstPage) !== notificationPageIdentity(page)) {
      return { pages: [page], pageParams: [null] }
    }
    return { ...current, pages: [page, ...current.pages.slice(1)] }
  })
}

export function useNotifications(limit = 40) {
  return useNotificationsState(limit)
}

export function useNotificationsState(limit = 40, options: UseNotificationsOptions = {}) {
  const user = useAuthStore((state) => state.user)
  const [error, setError] = useState<string | null>(null)
  const queryClient = useQueryClient()
  const queryKey = useMemo(() => asQueryKey(notificationsCacheKey(limit)), [limit])
  const enabled = options.enabled ?? true
  const pollMs = options.pollMs ?? 30_000
  const refreshOnFocus = options.refreshOnFocus ?? false
  ensureInfiniteNotificationCache(queryClient, queryKey)
  const query = useInfiniteQuery({
    queryKey,
    initialPageParam: null as string | null,
    queryFn: ({ pageParam, signal }) => notificationsApi.list(limit, { cursor: pageParam, signal }),
    getNextPageParam: (page) => (page?.has_more && page.next_cursor ? page.next_cursor : undefined),
    // The shared poller below owns automatic loading and cancellation. Keeping
    // this observer disabled preserves TanStack Query's pagination/mutation API
    // without a second interval or duplicate initial request.
    enabled: false,
  })

  const pollNotifications = useCallback(async ({ signal }: { signal: AbortSignal }) => {
    try {
      const page = await notificationsApi.list(limit, { cursor: null, signal })
      if (!signal.aborted) {
        replacePolledNotificationPage(queryClient, queryKey, page)
        setError(null)
      }
      return page
    } catch (pollError) {
      if (signal.aborted) throw pollError
      if (pollMs === false) {
        setError("Could not load notifications.")
        return null
      }
      throw pollError
    }
  }, [limit, pollMs, queryClient, queryKey])

  const { isPolling, refresh: refreshAdaptivePolling } = useAdaptivePolling({
    enabled: Boolean(user) && enabled,
    poll: pollNotifications,
    getProgress: (page) => page
      ? `${page.unread_count}:${notificationItems(page).map((item) => `${item.id}:${item.read_at ?? ""}`).join("|")}`
      : "",
    isTerminal: pollMs === false ? () => true : undefined,
    initialDelayMs: typeof pollMs === "number" ? pollMs : 30_000,
    maxDelayMs: typeof pollMs === "number" ? Math.max(pollMs * 4, pollMs) : 30_000,
    resetKey: `${user?.id ?? "anonymous"}:${limit}:${pollMs}`,
    onError: () => setError("Could not load notifications."),
  })

  const refresh = useCallback(() => {
    setError(null)
    refreshAdaptivePolling()
  }, [refreshAdaptivePolling])

  useEffect(() => {
    if (typeof window === "undefined") return

    const handleNotificationsChanged = () => {
      void refresh()
    }

    const handleFocus = () => {
      if (!refreshOnFocus) return
      refresh()
    }

    window.addEventListener(NOTIFICATIONS_CHANGED_EVENT, handleNotificationsChanged)
    window.addEventListener("focus", handleFocus)
    return () => {
      window.removeEventListener(NOTIFICATIONS_CHANGED_EVENT, handleNotificationsChanged)
      window.removeEventListener("focus", handleFocus)
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

  const pages = isInfiniteNotificationData(query.data) ? query.data.pages : []

  return {
    items: user ? pages.flatMap((page) => notificationItems(page)) : [],
    unreadCount: user ? pages[0]?.unread_count ?? 0 : 0,
    loading: query.isLoading || query.isFetching || isPolling,
    loadingMore: query.isFetchingNextPage,
    hasMore: Boolean(query.hasNextPage),
    error: error ?? (query.isError ? "Could not load notifications." : null),
    refresh,
    loadMore: query.fetchNextPage,
    markRead,
    markAllRead,
  }
}
