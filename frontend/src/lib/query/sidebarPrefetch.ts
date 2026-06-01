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

export const NOTIFICATIONS_SIDEBAR_LIMIT = 40

export const NOTIFICATIONS_SIDEBAR_QUERY_KEY = asQueryKey(notificationsCacheKey(NOTIFICATIONS_SIDEBAR_LIMIT))
export const SOCIAL_CONVERSATIONS_QUERY_KEY = asQueryKey(socialConversationsCacheKey())
export const SOCIAL_RELATIONSHIPS_QUERY_KEY = asQueryKey(socialRelationshipsCacheKey())

export function prefetchNotificationsSidebarData() {
  return queryClient.prefetchQuery({
    queryKey: NOTIFICATIONS_SIDEBAR_QUERY_KEY,
    queryFn: () => notificationsApi.list(NOTIFICATIONS_SIDEBAR_LIMIT, { syncRevisionDigests: false }),
  })
}

export function prefetchChatsSidebarData() {
  return Promise.all([
    queryClient.prefetchQuery({
      queryKey: SOCIAL_CONVERSATIONS_QUERY_KEY,
      queryFn: socialApi.listConversations,
    }),
    queryClient.prefetchQuery({
      queryKey: SOCIAL_RELATIONSHIPS_QUERY_KEY,
      queryFn: socialApi.listRelationships,
    }),
  ])
}
