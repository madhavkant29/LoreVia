import { apiClient } from "./client"
import type { AxiosRequestConfig } from "axios"
import type {
  DirectConversationListResponse,
  DirectConversationPageResponse,
  DirectMessage,
  DirectMessageListResponse,
  DirectMessagePageResponse,
  FriendRequestItem,
  SocialRelationshipListResponse,
  UnreadCountResponse,
  UserSearchResponse,
} from "@/types/social"

type RequestOptions = Pick<AxiosRequestConfig, "signal">

export const socialApi = {
  searchUsers: (query: string) =>
    apiClient.get<UserSearchResponse>("/social/users/search", { params: { q: query } }).then((r) => r.data),
  listRelationships: () =>
    apiClient.get<SocialRelationshipListResponse>("/social/relationships").then((r) => r.data),
  sendFriendRequest: (targetUserId: string) =>
    apiClient.post<FriendRequestItem>("/social/friend-requests", { target_user_id: targetUserId }).then((r) => r.data),
  acceptFriendRequest: (requestId: string) =>
    apiClient.post<FriendRequestItem>(`/social/friend-requests/${requestId}/accept`).then((r) => r.data),
  declineFriendRequest: (requestId: string) =>
    apiClient.post<FriendRequestItem>(`/social/friend-requests/${requestId}/decline`).then((r) => r.data),
  cancelFriendRequest: (requestId: string) =>
    apiClient.post<FriendRequestItem>(`/social/friend-requests/${requestId}/cancel`).then((r) => r.data),
  getConversationUnreadCount: (options?: RequestOptions) =>
    apiClient.get<UnreadCountResponse>("/social/conversations/unread-count", options).then((r) => r.data),
  listConversations: () =>
    apiClient.get<DirectConversationListResponse>("/social/conversations").then((r) => r.data),
  listConversationsPage: (limit = 30, cursor?: string | null, options?: RequestOptions) =>
    apiClient.get<DirectConversationPageResponse>("/social/conversations/page", {
      params: { limit, ...(cursor ? { cursor } : {}) },
      ...options,
    }).then((r) => r.data),
  openDirectConversation: (targetUserId: string) =>
    apiClient.post<DirectConversationListResponse>("/social/conversations/direct", { target_user_id: targetUserId }).then((r) => r.data),
  listMessages: (conversationId: string, limit = 50) =>
    apiClient.get<DirectMessageListResponse>(`/social/conversations/${conversationId}/messages`, { params: { limit } }).then((r) => r.data),
  listMessagesPage: (
    conversationId: string,
    limit = 50,
    cursor?: string | null,
    options?: RequestOptions,
  ) =>
    apiClient.get<DirectMessagePageResponse>(
      `/social/conversations/${conversationId}/messages/page`,
      { params: { limit, ...(cursor ? { cursor } : {}) }, ...options },
    ).then((r) => r.data),
  sendMessage: (conversationId: string, body: string) =>
    apiClient.post<DirectMessage>(`/social/conversations/${conversationId}/messages`, { body }).then((r) => r.data),
  markConversationRead: (conversationId: string) =>
    apiClient.post(`/social/conversations/${conversationId}/read`).then((r) => r.data),
}
