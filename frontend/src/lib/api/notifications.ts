import { apiClient } from "./client"
import type { NotificationItem, NotificationListResponse } from "@/types/notifications"

export const notificationsApi = {
  list: (limit = 40) =>
    apiClient.get<NotificationListResponse>("/notifications", { params: { limit } }).then((r) => r.data),
  markRead: (id: string) =>
    apiClient.put<NotificationItem>(`/notifications/${id}/read`).then((r) => r.data),
  markAllRead: () =>
    apiClient.put<NotificationListResponse>("/notifications/read-all").then((r) => r.data),
}
