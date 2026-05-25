export type MessagingPermission = "anyone" | "friends_only"
export type FriendState = "none" | "outgoing_pending" | "incoming_pending" | "accepted"

export interface SocialUserSummary {
  id: string
  username: string
  messaging_permission: MessagingPermission
  friend_state: FriendState
  can_message: boolean
}

export interface UserSearchResponse {
  items: SocialUserSummary[]
}

export interface FriendRequestItem {
  id: string
  requester_user_id: string
  addressee_user_id: string
  requester_username?: string | null
  addressee_username?: string | null
  status: string
  created_at: string
  responded_at?: string | null
}

export interface FriendSummary {
  user_id: string
  username: string
  since: string
}

export interface SocialRelationshipListResponse {
  friends: FriendSummary[]
  incoming_requests: FriendRequestItem[]
  outgoing_requests: FriendRequestItem[]
}

export interface DirectConversationSummary {
  id: string
  other_user: SocialUserSummary
  last_message_preview?: string | null
  last_message_at?: string | null
  unread_count: number
}

export interface DirectConversationListResponse {
  items: DirectConversationSummary[]
  unread_count: number
}

export interface UnreadCountResponse {
  unread_count: number
}

export interface DirectMessage {
  id: string
  conversation_id: string
  sender_user_id: string
  recipient_user_id: string
  body: string
  recipient_read_at?: string | null
  created_at: string
}

export interface DirectMessageListResponse {
  items: DirectMessage[]
}
