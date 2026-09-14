import { apiClient } from "./client"
import type { NotificationItem, NotificationListResponse } from "@/types/notifications"

export function normalizeNotificationListResponse(
  response: Partial<NotificationListResponse> | null | undefined,
): NotificationListResponse {
  const items = Array.isArray(response?.items) ? response.items : []
  const unreadCount = typeof response?.unread_count === "number" && Number.isFinite(response.unread_count)
    ? response.unread_count
    : items.filter((item) => !item.read_at).length

  return {
    items,
    unread_count: Math.max(0, unreadCount),
    next_cursor: response?.next_cursor ?? null,
    has_more: Boolean(response?.has_more && response?.next_cursor),
  }
}

export const notificationsApi = {
  list: (
    limit = 40,
    options?: { cursor?: string | null; signal?: AbortSignal; syncRevisionDigests?: boolean },
  ) =>
    apiClient
      .get<NotificationListResponse>("/notifications", {
        params: {
          limit,
          ...(options?.cursor ? { cursor: options.cursor } : {}),
          // Compatibility for older callers. The server treats this as a
          // deprecated no-op, and current clients never send it.
          ...(options?.syncRevisionDigests ? { sync_revision_digests: true } : {}),
        },
        signal: options?.signal,
      })
      .then((r) => normalizeNotificationListResponse(r.data)),
  markRead: (id: string) =>
    apiClient.put<NotificationItem>(`/notifications/${id}/read`).then((r) => r.data),
  markAllRead: () =>
    apiClient
      .put<NotificationListResponse>("/notifications/read-all")
      .then((r) => normalizeNotificationListResponse(r.data)),
}
