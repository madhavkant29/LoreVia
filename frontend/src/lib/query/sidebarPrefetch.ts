"use client"

import { notificationsApi } from "@/lib/api/notifications"
import { socialApi } from "@/lib/api/social"
import {
  asQueryKey,
  notificationsCacheKey,
  socialConversationsCacheKey,
  socialRelationshipsCacheKey,
} from "@/lib/query/cacheKeys"
import { queryClient } from "@/lib/query/queryClient"
import type { NotificationListResponse } from "@/types/notifications"

export const NOTIFICATIONS_SIDEBAR_LIMIT = 40
export const SOCIAL_CONVERSATIONS_SIDEBAR_LIMIT = 30

export const NOTIFICATIONS_SIDEBAR_QUERY_KEY = asQueryKey(notificationsCacheKey(NOTIFICATIONS_SIDEBAR_LIMIT))
export const SOCIAL_CONVERSATIONS_QUERY_KEY = asQueryKey(socialConversationsCacheKey())
export const SOCIAL_RELATIONSHIPS_QUERY_KEY = asQueryKey(socialRelationshipsCacheKey())

export function prefetchNotificationsSidebarData() {
  return queryClient.prefetchInfiniteQuery({
    queryKey: NOTIFICATIONS_SIDEBAR_QUERY_KEY,
    initialPageParam: null as string | null,
    queryFn: ({ pageParam }) =>
      notificationsApi.list(NOTIFICATIONS_SIDEBAR_LIMIT, {
        cursor: typeof pageParam === "string" ? pageParam : null,
      }),
    getNextPageParam: (page: NotificationListResponse) =>
      page.has_more && page.next_cursor ? page.next_cursor : undefined,
  })
}

export function prefetchChatsSidebarData() {
  return Promise.all([
    queryClient.prefetchQuery({
      queryKey: SOCIAL_CONVERSATIONS_QUERY_KEY,
      queryFn: () => socialApi.listConversationsPage(SOCIAL_CONVERSATIONS_SIDEBAR_LIMIT),
    }),
    queryClient.prefetchQuery({
      queryKey: SOCIAL_RELATIONSHIPS_QUERY_KEY,
      queryFn: socialApi.listRelationships,
    }),
  ])
}
