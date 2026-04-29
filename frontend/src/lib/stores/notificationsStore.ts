import { create } from "zustand"
import { notificationsApi } from "@/lib/api/notifications"
import type { NotificationItem, NotificationListResponse } from "@/types/notifications"

interface NotificationsStore {
  items: NotificationItem[]
  unreadCount: number
  loading: boolean
  error: string | null
  initialized: boolean
  lastUserId: string | null
  listLimit: number
  reset: () => void
  refresh: (userId: string, limit: number) => Promise<void>
  markRead: (userId: string, id: string, limit: number) => Promise<void>
  markAllRead: (userId: string, limit: number) => Promise<void>
}

function applyNotificationList(
  set: (partial: Partial<NotificationsStore>) => void,
  response: NotificationListResponse,
  userId: string,
  limit: number,
) {
  set({
    items: response.items,
    unreadCount: response.unread_count,
    loading: false,
    error: null,
    initialized: true,
    lastUserId: userId,
    listLimit: limit,
  })
}

export const useNotificationsStore = create<NotificationsStore>()((set, get) => ({
  items: [],
  unreadCount: 0,
  loading: false,
  error: null,
  initialized: false,
  lastUserId: null,
  listLimit: 0,

  reset: () =>
    set({
      items: [],
      unreadCount: 0,
      loading: false,
      error: null,
      initialized: false,
      lastUserId: null,
      listLimit: 0,
    }),

  refresh: async (userId, limit) => {
    const effectiveLimit = Math.max(limit, get().listLimit)
    set({ loading: true, error: null })
    try {
      const response = await notificationsApi.list(effectiveLimit)
      applyNotificationList(set, response, userId, effectiveLimit)
    } catch {
      set({ loading: false, error: "Could not load notifications." })
    }
  },

  markRead: async (userId, id, limit) => {
    try {
      const updatedNotification = await notificationsApi.markRead(id)
      const existingItem = get().items.find((item) => item.id === id)
      const wasUnread = Boolean(existingItem && !existingItem.read_at)

      set((state) => ({
        items: state.items.map((item) => (item.id === id ? updatedNotification : item)),
        unreadCount: wasUnread ? Math.max(state.unreadCount - 1, 0) : state.unreadCount,
        error: null,
        initialized: true,
        lastUserId: userId,
        listLimit: Math.max(limit, state.listLimit),
      }))
    } catch {
      set({ error: "Could not update notification." })
    }
  },

  markAllRead: async (userId, limit) => {
    const effectiveLimit = Math.max(limit, get().listLimit)
    try {
      const response = await notificationsApi.markAllRead()
      applyNotificationList(set, response, userId, effectiveLimit)
    } catch {
      set({ error: "Could not update notifications." })
    }
  },
}))
