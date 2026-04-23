export interface NotificationItem {
  id: string
  book_id: string | null
  kind: string
  title: string
  body: string
  data: Record<string, unknown> | null
  read_at: string | null
  created_at: string
}

export interface NotificationListResponse {
  items: NotificationItem[]
  unread_count: number
}
