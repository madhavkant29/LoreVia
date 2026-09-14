"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import { useQueryClient } from "@tanstack/react-query"
import Link from "next/link"
import { useSearchParams } from "next/navigation"

import { socialApi } from "@/lib/api/social"
import { useAdaptivePolling } from "@/lib/hooks/useAdaptivePolling"
import { emitChatsChanged } from "@/lib/hooks/useChatUnreadCount"
import {
  SOCIAL_CONVERSATIONS_QUERY_KEY,
  SOCIAL_RELATIONSHIPS_QUERY_KEY,
} from "@/lib/query/sidebarPrefetch"
import { useAuthStore } from "@/lib/stores/authStore"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import type {
  DirectConversationPageResponse,
  DirectConversationSummary,
  DirectMessage,
  SocialRelationshipListResponse,
  SocialUserSummary,
} from "@/types/social"

const SIDEBAR_CONVERSATION_POLL_MS = 45_000
const PAGE_CONVERSATION_POLL_MS = 30_000
const SIDEBAR_MESSAGE_POLL_MS = 15_000
const PAGE_MESSAGE_POLL_MS = 8_000

export function ChatsPanel({ mode = "sidebar", enabled = true }: { mode?: "sidebar" | "page"; enabled?: boolean }) {
  const queryClient = useQueryClient()
  const cachedConversations = queryClient.getQueryData<DirectConversationPageResponse>(SOCIAL_CONVERSATIONS_QUERY_KEY)
  const cachedRelationships = queryClient.getQueryData<SocialRelationshipListResponse>(SOCIAL_RELATIONSHIPS_QUERY_KEY)
  const { user, hydrated } = useAuthStore()
  const { theme } = usePreferencesStore()
  const searchParams = useSearchParams()
  const isDark = theme === "dark"
  const usernamePrefill = searchParams.get("username")?.trim() || ""

  const [loading, setLoading] = useState(!cachedConversations)
  const [search, setSearch] = useState(usernamePrefill)
  const [searching, setSearching] = useState(false)
  const [searchResults, setSearchResults] = useState<SocialUserSummary[]>([])
  const [relationships, setRelationships] = useState<SocialRelationshipListResponse | null>(cachedRelationships ?? null)
  const [conversations, setConversations] = useState<DirectConversationSummary[]>(cachedConversations?.items ?? [])
  const [nextConversationCursor, setNextConversationCursor] = useState<string | null>(cachedConversations?.next_cursor ?? null)
  const [loadingMoreConversations, setLoadingMoreConversations] = useState(false)
  const [selectedConversationId, setSelectedConversationId] = useState<string | null>(cachedConversations?.items[0]?.id ?? null)
  const [selectedSearchUser, setSelectedSearchUser] = useState<SocialUserSummary | null>(null)
  const [messages, setMessages] = useState<DirectMessage[]>([])
  const [nextMessageCursor, setNextMessageCursor] = useState<string | null>(null)
  const [loadingOlderMessages, setLoadingOlderMessages] = useState(false)
  const [messageDraft, setMessageDraft] = useState("")
  const [sending, setSending] = useState(false)
  const [status, setStatus] = useState<string | null>(null)
  const [refreshTick, setRefreshTick] = useState(0)
  const conversationPollMs = mode === "sidebar" ? SIDEBAR_CONVERSATION_POLL_MS : PAGE_CONVERSATION_POLL_MS
  const messagePollMs = mode === "sidebar" ? SIDEBAR_MESSAGE_POLL_MS : PAGE_MESSAGE_POLL_MS

  const selectedConversation = useMemo(
    () => conversations.find((item) => item.id === selectedConversationId) ?? null,
    [conversations, selectedConversationId],
  )

  const loadRelationships = useCallback(async (options?: { force?: boolean }) => {
    if (!user) return
    try {
      if (options?.force) {
        await queryClient.invalidateQueries({ queryKey: SOCIAL_RELATIONSHIPS_QUERY_KEY })
      }
      const relationshipPayload = await queryClient.fetchQuery({
        queryKey: SOCIAL_RELATIONSHIPS_QUERY_KEY,
        queryFn: socialApi.listRelationships,
      })
      setRelationships(relationshipPayload)
    } catch {
      // Keep the last known relationship state if the background refresh fails.
    }
  }, [queryClient, user])

  const hydrateConversations = useCallback(async (options?: {
    keepSelection?: boolean
    silent?: boolean
    force?: boolean
    signal?: AbortSignal
  }) => {
    if (!user) return undefined
    const hasCachedPayload = Boolean(queryClient.getQueryData<DirectConversationPageResponse>(SOCIAL_CONVERSATIONS_QUERY_KEY))
    const showLoading = !options?.silent && !hasCachedPayload
    if (showLoading) {
      setLoading(true)
    }
    try {
      if (options?.force) {
        await queryClient.invalidateQueries({ queryKey: SOCIAL_CONVERSATIONS_QUERY_KEY })
      }
      const conversationPayload = await queryClient.fetchQuery({
        queryKey: SOCIAL_CONVERSATIONS_QUERY_KEY,
        queryFn: () => socialApi.listConversationsPage(30, undefined, { signal: options?.signal }),
      })
      setConversations(conversationPayload.items)
      setNextConversationCursor(conversationPayload.next_cursor)
      emitChatsChanged()
      if (!options?.keepSelection) {
        setSelectedConversationId((current) => current || conversationPayload.items[0]?.id || null)
      }
      setStatus(null)
      return conversationPayload
    } catch {
      setStatus("Could not load chats right now.")
      return undefined
    } finally {
      if (showLoading) {
        setLoading(false)
      }
    }
  }, [queryClient, user])

  const loadMessages = useCallback(async (conversationId: string, options?: {
    markRead?: boolean
    signal?: AbortSignal
  }) => {
    try {
      const payload = await socialApi.listMessagesPage(
        conversationId,
        50,
        undefined,
        { signal: options?.signal },
      )
      setMessages(payload.items)
      setNextMessageCursor(payload.next_cursor)
      if (options?.markRead !== false) {
        await socialApi.markConversationRead(conversationId)
        emitChatsChanged()
        setConversations((current) => current.map((item) => item.id === conversationId ? { ...item, unread_count: 0 } : item))
      }
      setStatus(null)
      return payload
    } catch {
      setStatus("Could not load messages for this conversation.")
      return undefined
    }
  }, [])

  const loadMoreConversations = useCallback(async () => {
    if (!nextConversationCursor || loadingMoreConversations) return
    setLoadingMoreConversations(true)
    try {
      const payload = await socialApi.listConversationsPage(30, nextConversationCursor)
      setConversations((current) => {
        const known = new Set(current.map((item) => item.id))
        return [...current, ...payload.items.filter((item) => !known.has(item.id))]
      })
      setNextConversationCursor(payload.next_cursor)
      setStatus(null)
    } catch {
      setStatus("Could not load more chats right now.")
    } finally {
      setLoadingMoreConversations(false)
    }
  }, [loadingMoreConversations, nextConversationCursor])

  const loadOlderMessages = useCallback(async () => {
    if (!selectedConversationId || !nextMessageCursor || loadingOlderMessages) return
    setLoadingOlderMessages(true)
    try {
      const payload = await socialApi.listMessagesPage(
        selectedConversationId,
        50,
        nextMessageCursor,
      )
      setMessages((current) => {
        const known = new Set(current.map((item) => item.id))
        return [...payload.items.filter((item) => !known.has(item.id)), ...current]
      })
      setNextMessageCursor(payload.next_cursor)
      setStatus(null)
    } catch {
      setStatus("Could not load older messages right now.")
    } finally {
      setLoadingOlderMessages(false)
    }
  }, [loadingOlderMessages, nextMessageCursor, selectedConversationId])

  const runSearch = useCallback(async (query: string) => {
    const trimmed = query.trim()
    setSearch(query)
    if (trimmed.length < 2) {
      setSearchResults([])
      return
    }
    setSearching(true)
    try {
      const payload = await socialApi.searchUsers(trimmed)
      setSearchResults(payload.items)
      const exactMatch = payload.items.find((item) => item.username.toLowerCase() === trimmed.toLowerCase()) ?? payload.items[0] ?? null
      if (usernamePrefill && exactMatch) {
        setSelectedSearchUser(exactMatch)
      }
      setStatus(null)
    } catch {
      setStatus("Could not search for users.")
    } finally {
      setSearching(false)
    }
  }, [usernamePrefill])

  useAdaptivePolling({
    enabled: Boolean(enabled && user),
    poll: ({ signal }) => hydrateConversations({
      keepSelection: Boolean(selectedConversationId),
      silent: false,
      force: refreshTick > 0,
      signal,
    }),
    getProgress: (payload) => payload?.items
      .map((item) => `${item.id}:${item.last_message_at ?? ""}:${item.unread_count}`)
      .join("|") ?? "",
    initialDelayMs: conversationPollMs,
    maxDelayMs: conversationPollMs * 4,
    resetKey: `${user?.id ?? "anonymous"}:${refreshTick}`,
  })

  useEffect(() => {
    if (!enabled || !user) return
    void loadRelationships({ force: refreshTick > 0 })
  }, [enabled, loadRelationships, refreshTick, user])

  useEffect(() => {
    if (!enabled) return
    if (usernamePrefill) {
      void runSearch(usernamePrefill)
    }
  }, [enabled, runSearch, usernamePrefill])

  useEffect(() => {
    if (!enabled) return
    if (!selectedConversationId) {
      setMessages([])
      setNextMessageCursor(null)
    }
  }, [enabled, selectedConversationId])

  useAdaptivePolling({
    enabled: Boolean(enabled && selectedConversationId),
    poll: ({ signal }) => loadMessages(selectedConversationId as string, {
      markRead: (selectedConversation?.unread_count ?? 0) > 0,
      signal,
    }),
    getProgress: (payload) => payload?.items
      .map((item) => `${item.id}:${item.created_at}:${item.recipient_read_at ?? ""}`)
      .join("|") ?? "",
    initialDelayMs: messagePollMs,
    maxDelayMs: messagePollMs * 4,
    resetKey: `${selectedConversationId ?? "none"}:${refreshTick}`,
  })

  const handleOpenConversation = async (targetUserId: string) => {
    try {
      const payload = await socialApi.openDirectConversation(targetUserId)
      const conversation = payload.items[0]
      if (!conversation) return
      setSelectedConversationId(conversation.id)
      setSelectedSearchUser(null)
      setRefreshTick((current) => current + 1)
      setStatus(null)
    } catch {
      setStatus("This user is not available for direct messages yet.")
    }
  }

  const handleSendFriendRequest = async (targetUserId: string) => {
    try {
      await socialApi.sendFriendRequest(targetUserId)
      setSearchResults((current) => current.map((item) => item.id === targetUserId ? { ...item, friend_state: "outgoing_pending", can_message: false } : item))
      setSelectedSearchUser((current) => current && current.id === targetUserId ? { ...current, friend_state: "outgoing_pending", can_message: false } : current)
      setRefreshTick((current) => current + 1)
      setStatus("Friend request sent.")
    } catch {
      setStatus("Could not send a friend request right now.")
    }
  }

  const handleSendMessage = async () => {
    if (!selectedConversationId || !messageDraft.trim()) return
    const optimisticBody = messageDraft.trim()
    const optimisticMessage: DirectMessage = {
      id: `optimistic-${Date.now()}`,
      conversation_id: selectedConversationId,
      sender_user_id: user?.id || "",
      recipient_user_id: selectedConversation?.other_user.id || "",
      body: optimisticBody,
      created_at: new Date().toISOString(),
      recipient_read_at: null,
    }
    setSending(true)
    setMessages((current) => [...current, optimisticMessage])
    setMessageDraft("")
    try {
      const created = await socialApi.sendMessage(selectedConversationId, optimisticBody)
      setMessages((current) => current.map((item) => item.id === optimisticMessage.id ? created : item))
      emitChatsChanged()
      setRefreshTick((current) => current + 1)
      setStatus(null)
    } catch {
      setMessages((current) => current.filter((item) => item.id !== optimisticMessage.id))
      setMessageDraft(optimisticBody)
      setStatus("Could not send that message.")
    } finally {
      setSending(false)
    }
  }

  const shellClass = mode === "sidebar" ? "h-full" : "mx-auto max-w-7xl min-h-[calc(100vh-8rem)]"

  if (!hydrated) {
    return (
      <section className={`flex ${shellClass} flex-col ${isDark ? "bg-[#05070a] text-slate-100" : "bg-white text-slate-950"}`}>
        <div className="flex flex-1 items-center justify-center p-8">
          <div className={`rounded-lg border px-6 py-6 text-sm ${isDark ? "border-white/10 bg-[#0c1219] text-slate-400" : "border-slate-200 bg-white text-slate-600"}`}>
            Loading chats...
          </div>
        </div>
      </section>
    )
  }

  if (!user) {
    return (
      <section className={`flex ${shellClass} flex-col ${isDark ? "bg-[#05070a] text-slate-100" : "bg-white text-slate-950"}`}>
        <div className="flex flex-1 items-center justify-center p-8">
          <div className={`max-w-md rounded-lg border px-6 py-6 ${isDark ? "border-white/10 bg-[#0c1219]" : "border-slate-200 bg-white"}`}>
            <p className="text-lg font-semibold">Sign in to use direct messages</p>
            <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-400" : "text-slate-600"}`}>
              Private chats are only available to signed-in members. Friend requests are approved from notifications after you sign in.
            </p>
            <Link
              href="/login"
              className={`mt-4 inline-flex rounded-md px-4 py-2 text-sm font-semibold ${isDark ? "bg-teal-300 text-slate-950 hover:bg-teal-200" : "bg-[#1f615d] text-white hover:bg-[#174c49]"}`}
            >
              Go to login
            </Link>
          </div>
        </div>
      </section>
    )
  }

  return (
    <section className={`flex ${shellClass} flex-col ${isDark ? "bg-[#05070a] text-slate-100" : "bg-white text-slate-950"}`}>
      <div className={`flex items-center justify-between gap-3 border-b px-5 py-4 ${isDark ? "border-white/10" : "border-slate-200"}`}>
        <div>
          <p className={`text-xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-500" : "text-slate-500"}`}>Direct messages</p>
          <h1 className="mt-1 text-xl font-semibold">Private chats</h1>
        </div>
        <button
          type="button"
          onClick={() => setRefreshTick((current) => current + 1)}
          className={`rounded-md border px-3 py-2 text-xs font-medium transition ${isDark ? "border-white/10 bg-white/5 text-slate-200 hover:bg-white/10" : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50"}`}
        >
          Refresh
        </button>
      </div>

      <div className="grid min-h-0 flex-1 lg:grid-cols-[18rem_minmax(0,1fr)]">
        <aside className={`min-h-0 border-b p-4 lg:border-b-0 lg:border-r ${isDark ? "border-white/10 bg-[#0a0f14]" : "border-slate-200 bg-slate-50/60"}`}>
          <label className={`flex h-11 items-center gap-3 rounded-md border px-4 ${isDark ? "border-white/10 bg-[#111822]" : "border-slate-200 bg-white"}`}>
            <SearchIcon className={isDark ? "text-slate-500" : "text-slate-400"} />
            <input
              value={search}
              onChange={(event) => void runSearch(event.target.value)}
              aria-label="Search usernames"
              className="w-full bg-transparent text-sm outline-none"
            />
          </label>

          {relationships?.incoming_requests.length ? (
            <div className="mt-4 space-y-2">
              <p className={`text-3xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-slate-500"}`}>Pending for you</p>
              {relationships.incoming_requests.slice(0, 3).map((request) => (
                <div key={request.id} className={`rounded-md border px-3 py-3 text-sm ${isDark ? "border-white/10 bg-white/[0.03] text-slate-300" : "border-slate-200 bg-white text-slate-700"}`}>
                  @{request.requester_username || "member"} wants to connect.
                </div>
              ))}
            </div>
          ) : null}

          <div className="mt-4">
            <p className={`text-3xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-slate-500"}`}>Conversations</p>
            <div className="mt-3 space-y-2">
              {loading ? (
                <div className={`rounded-md border px-3 py-4 text-sm ${isDark ? "border-white/10 bg-white/[0.03] text-slate-400" : "border-slate-200 bg-white text-slate-500"}`}>Loading chats...</div>
              ) : conversations.length === 0 ? (
                <div className={`rounded-md border px-3 py-4 text-sm ${isDark ? "border-white/10 bg-white/[0.03] text-slate-400" : "border-slate-200 bg-white text-slate-500"}`}>No conversations yet.</div>
              ) : conversations.map((conversation) => (
                <button
                  key={conversation.id}
                  type="button"
                  onClick={() => {
                    setSelectedConversationId(conversation.id)
                    setSelectedSearchUser(null)
                  }}
                  className={`w-full rounded-md border px-3 py-3 text-left transition ${selectedConversationId === conversation.id ? (isDark ? "border-teal-300/30 bg-teal-300/10" : "border-teal-200 bg-teal-50") : (isDark ? "border-white/10 bg-white/[0.03] hover:bg-white/[0.05]" : "border-slate-200 bg-white hover:bg-slate-50")}`}
                >
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-sm font-semibold">@{conversation.other_user.username}</p>
                    {conversation.unread_count > 0 ? (
                      <span className="rounded-full bg-rose-500 px-2 py-0.5 text-3xs font-semibold text-white">{Math.min(conversation.unread_count, 9)}</span>
                    ) : null}
                  </div>
                  <p className={`mt-1 line-clamp-2 text-xs leading-5 ${isDark ? "text-slate-400" : "text-slate-600"}`}>{conversation.last_message_preview || "No messages yet."}</p>
                </button>
              ))}
              {nextConversationCursor ? (
                <button
                  type="button"
                  onClick={() => void loadMoreConversations()}
                  disabled={loadingMoreConversations}
                  className={`w-full rounded-md border px-3 py-2 text-xs font-medium transition ${isDark ? "border-white/10 bg-white/[0.03] text-slate-300 hover:bg-white/[0.05] disabled:text-slate-500" : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50 disabled:text-slate-400"}`}
                >
                  {loadingMoreConversations ? "Loading chats..." : "Load more chats"}
                </button>
              ) : null}
            </div>
          </div>

          {search.length >= 2 ? (
            <div className="mt-4">
              <p className={`text-3xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-slate-500"}`}>Search results</p>
              <div className="mt-3 space-y-2">
                {searching ? (
                  <div className={`rounded-md border px-3 py-4 text-sm ${isDark ? "border-white/10 bg-white/[0.03] text-slate-400" : "border-slate-200 bg-white text-slate-500"}`}>Searching...</div>
                ) : searchResults.length === 0 ? (
                  <div className={`rounded-md border px-3 py-4 text-sm ${isDark ? "border-white/10 bg-white/[0.03] text-slate-400" : "border-slate-200 bg-white text-slate-500"}`}>No matching usernames.</div>
                ) : searchResults.map((result) => (
                  <button
                    key={result.id}
                    type="button"
                    onClick={() => setSelectedSearchUser(result)}
                    className={`w-full rounded-md border px-3 py-3 text-left transition ${selectedSearchUser?.id === result.id ? (isDark ? "border-teal-300/30 bg-teal-300/10" : "border-teal-200 bg-teal-50") : (isDark ? "border-white/10 bg-white/[0.03]" : "border-slate-200 bg-white")}`}
                  >
                    <p className="text-sm font-semibold">@{result.username}</p>
                    <p className={`mt-1 text-xs ${isDark ? "text-slate-400" : "text-slate-600"}`}>
                      {result.messaging_permission === "friends_only" ? "Friends only" : "Anyone can message"}
                    </p>
                  </button>
                ))}
              </div>
            </div>
          ) : null}
        </aside>

        <div className="min-h-0 p-4 lg:p-5">
          {status ? (
            <div className={`mb-4 rounded-md border px-4 py-3 text-sm ${isDark ? "border-white/10 bg-white/[0.03] text-slate-300" : "border-slate-200 bg-slate-50 text-slate-700"}`}>{status}</div>
          ) : null}

          {selectedConversation ? (
            <div className="flex h-full min-h-[28rem] flex-col">
              <div className={`rounded-lg border px-4 py-4 ${isDark ? "border-white/10 bg-[#0c1219]" : "border-slate-200 bg-slate-50"}`}>
                <p className="text-lg font-semibold">@{selectedConversation.other_user.username}</p>
                <p className={`mt-1 text-sm ${isDark ? "text-slate-400" : "text-slate-600"}`}>
                  {selectedConversation.other_user.messaging_permission === "friends_only" ? "Friends only messaging" : "Open to messages from anyone"}
                </p>
              </div>

              <div className={`reader-scrollbar mt-4 flex-1 overflow-y-auto rounded-lg border p-4 ${isDark ? "border-white/10 bg-[#0c1219]" : "border-slate-200 bg-white"}`}>
                <div className="space-y-3">
                  {nextMessageCursor ? (
                    <div className="flex justify-center">
                      <button
                        type="button"
                        onClick={() => void loadOlderMessages()}
                        disabled={loadingOlderMessages}
                        className={`rounded-md border px-3 py-2 text-xs font-medium transition ${isDark ? "border-white/10 bg-white/[0.03] text-slate-300 hover:bg-white/[0.05] disabled:text-slate-500" : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50 disabled:text-slate-400"}`}
                      >
                        {loadingOlderMessages ? "Loading messages..." : "Load older messages"}
                      </button>
                    </div>
                  ) : null}
                  {messages.map((message) => {
                    const mine = message.sender_user_id === user?.id
                    return (
                      <div key={message.id} className={`flex ${mine ? "justify-end" : "justify-start"}`}>
                        <div className={`max-w-[85%] rounded-lg px-4 py-3 text-sm leading-6 ${mine ? (isDark ? "bg-teal-300 text-slate-950" : "bg-[#1f615d] text-white") : (isDark ? "bg-white/[0.05] text-slate-100" : "bg-slate-100 text-slate-800")}`}>
                          <p>{message.body}</p>
                          <p className={`mt-2 text-3xs ${mine ? "text-current/80" : (isDark ? "text-slate-500" : "text-slate-500")}`}>{new Date(message.created_at).toLocaleString()}</p>
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>

              <div className="mt-4 flex gap-3">
                <textarea
                  value={messageDraft}
                  onChange={(event) => setMessageDraft(event.target.value)}
                  aria-label="Message"
                  className={`min-h-[6rem] flex-1 rounded-md border px-4 py-3 text-sm leading-6 outline-none ${isDark ? "border-white/10 bg-[#0c1219] text-slate-100" : "border-slate-200 bg-white text-slate-900"}`}
                />
                <button
                  type="button"
                  onClick={() => void handleSendMessage()}
                  disabled={sending || !messageDraft.trim()}
                  className={`self-end rounded-md px-4 py-3 text-sm font-semibold transition ${isDark ? "bg-teal-300 text-slate-950 hover:bg-teal-200 disabled:bg-teal-300/40" : "bg-[#1f615d] text-white hover:bg-[#174c49] disabled:bg-slate-300"}`}
                >
                  {sending ? "Sending..." : "Send"}
                </button>
              </div>
            </div>
          ) : selectedSearchUser ? (
            <div className={`rounded-lg border p-5 ${isDark ? "border-white/10 bg-[#0c1219]" : "border-slate-200 bg-white"}`}>
              <p className="text-lg font-semibold">@{selectedSearchUser.username}</p>
              <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-400" : "text-slate-600"}`}>
                {selectedSearchUser.messaging_permission === "friends_only"
                  ? "This user only accepts direct messages from friends."
                  : "This user accepts direct messages from anyone."}
              </p>
              <div className="mt-4 flex flex-wrap gap-3">
                {selectedSearchUser.can_message ? (
                  <button
                    type="button"
                    onClick={() => void handleOpenConversation(selectedSearchUser.id)}
                    className={`rounded-md px-4 py-3 text-sm font-semibold transition ${isDark ? "bg-teal-300 text-slate-950 hover:bg-teal-200" : "bg-[#1f615d] text-white hover:bg-[#174c49]"}`}
                  >
                    Open chat
                  </button>
                ) : selectedSearchUser.friend_state === "outgoing_pending" ? (
                  <span className={`rounded-full px-4 py-3 text-sm font-medium ${isDark ? "bg-white/[0.05] text-slate-300" : "bg-slate-100 text-slate-700"}`}>Friend request pending</span>
                ) : selectedSearchUser.friend_state === "incoming_pending" ? (
                  <span className={`rounded-full px-4 py-3 text-sm font-medium ${isDark ? "bg-white/[0.05] text-slate-300" : "bg-slate-100 text-slate-700"}`}>Accept from notifications first</span>
                ) : (
                  <button
                    type="button"
                    onClick={() => void handleSendFriendRequest(selectedSearchUser.id)}
                    className={`rounded-md px-4 py-3 text-sm font-semibold transition ${isDark ? "border border-white/10 bg-white/[0.03] text-slate-100 hover:bg-white/[0.05]" : "border border-slate-200 bg-white text-slate-900 hover:bg-slate-50"}`}
                  >
                    Send friend request
                  </button>
                )}
              </div>
            </div>
          ) : (
            <div className={`rounded-lg border p-6 ${isDark ? "border-white/10 bg-[#0c1219] text-slate-400" : "border-slate-200 bg-white text-slate-600"}`}>
              Pick a conversation or search for a username to start a private chat.
            </div>
          )}
        </div>
      </div>
    </section>
  )
}

function SearchIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 20 20" fill="none" className={`h-4 w-4 ${className || ""}`} aria-hidden="true">
      <circle cx="9" cy="9" r="5.75" stroke="currentColor" strokeWidth="1.5" />
      <path d="M13.5 13.5 17 17" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  )
}
