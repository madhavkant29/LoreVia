import { QueryClient } from "@tanstack/react-query"
import { describe, expect, it } from "vitest"

import { asQueryKey, notificationsCacheKey } from "@/lib/query/cacheKeys"
import type { NotificationListResponse } from "@/types/notifications"
import {
  applyAllNotificationsReadToNotificationCaches,
  applyNotificationReadToNotificationCaches,
} from "./useNotifications"

function notificationPayload(readAt: string | null = null): NotificationListResponse {
  return {
    unread_count: readAt ? 0 : 1,
    items: [
      {
        id: "notification-1",
        book_id: "book-1",
        kind: "revision_digest",
        title: "Revision risk",
        body: "Review the downstream edit.",
        data: null,
        read_at: readAt,
        created_at: "2026-06-15T09:00:00Z",
      },
    ],
  }
}

describe("notification cache reconciliation", () => {
  it("marks a notification read across all cached notification list limits", () => {
    const queryClient = new QueryClient()
    const bellQueryKey = asQueryKey(notificationsCacheKey(10))
    const panelQueryKey = asQueryKey(notificationsCacheKey(40))

    queryClient.setQueryData(bellQueryKey, notificationPayload())
    queryClient.setQueryData(panelQueryKey, notificationPayload())

    applyNotificationReadToNotificationCaches(queryClient, {
      ...notificationPayload().items[0],
      read_at: "2026-06-15T09:05:00Z",
    })

    expect(queryClient.getQueryData<NotificationListResponse>(bellQueryKey)?.unread_count).toBe(0)
    expect(queryClient.getQueryData<NotificationListResponse>(bellQueryKey)?.items[0]?.read_at).toBe("2026-06-15T09:05:00Z")
    expect(queryClient.getQueryData<NotificationListResponse>(panelQueryKey)?.unread_count).toBe(0)
    expect(queryClient.getQueryData<NotificationListResponse>(panelQueryKey)?.items[0]?.read_at).toBe("2026-06-15T09:05:00Z")
  })

  it("marks every cached notification list read after mark all read succeeds", () => {
    const queryClient = new QueryClient()
    const bellQueryKey = asQueryKey(notificationsCacheKey(10))
    const panelQueryKey = asQueryKey(notificationsCacheKey(40))

    queryClient.setQueryData(bellQueryKey, notificationPayload())
    queryClient.setQueryData(panelQueryKey, notificationPayload())

    applyAllNotificationsReadToNotificationCaches(queryClient, notificationPayload("2026-06-15T09:10:00Z"))

    expect(queryClient.getQueryData<NotificationListResponse>(bellQueryKey)?.unread_count).toBe(0)
    expect(queryClient.getQueryData<NotificationListResponse>(bellQueryKey)?.items[0]?.read_at).toBe("2026-06-15T09:10:00Z")
    expect(queryClient.getQueryData<NotificationListResponse>(panelQueryKey)?.unread_count).toBe(0)
    expect(queryClient.getQueryData<NotificationListResponse>(panelQueryKey)?.items[0]?.read_at).toBe("2026-06-15T09:10:00Z")
  })
})
