import { apiClient } from "./client"
import type {
  DirectConversationListResponse,
  DirectMessage,
  DirectMessageListResponse,
  FriendRequestItem,
  SocialRelationshipListResponse,
  UnreadCountResponse,
  UserSearchResponse,
} from "@/types/social"

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
  getConversationUnreadCount: () =>
    apiClient.get<UnreadCountResponse>("/social/conversations/unread-count").then((r) => r.data),
  listConversations: () =>
    apiClient.get<DirectConversationListResponse>("/social/conversations").then((r) => r.data),
  openDirectConversation: (targetUserId: string) =>
    apiClient.post<DirectConversationListResponse>("/social/conversations/direct", { target_user_id: targetUserId }).then((r) => r.data),
  listMessages: (conversationId: string, limit = 50) =>
    apiClient.get<DirectMessageListResponse>(`/social/conversations/${conversationId}/messages`, { params: { limit } }).then((r) => r.data),
  sendMessage: (conversationId: string, body: string) =>
    apiClient.post<DirectMessage>(`/social/conversations/${conversationId}/messages`, { body }).then((r) => r.data),
  markConversationRead: (conversationId: string) =>
    apiClient.post(`/social/conversations/${conversationId}/read`).then((r) => r.data),
}
