"use client"

import { useEffect, useMemo, useRef, useState } from "react"
import Link from "next/link"
import { useSearchParams } from "next/navigation"

import { socialApi } from "@/lib/api/social"
import { emitChatsChanged } from "@/lib/hooks/useChatUnreadCount"
import { useAuthStore } from "@/lib/stores/authStore"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import type {
  DirectConversationSummary,
  DirectMessage,
  SocialRelationshipListResponse,
  SocialUserSummary,
} from "@/types/social"

const SIDEBAR_CONVERSATION_POLL_MS = 45_000
const PAGE_CONVERSATION_POLL_MS = 30_000
const SIDEBAR_MESSAGE_POLL_MS = 15_000
const PAGE_MESSAGE_POLL_MS = 8_000

export function ChatsPanel({ mode = "sidebar" }: { mode?: "sidebar" | "page" }) {
  const { user, hydrated } = useAuthStore()
  const { theme } = usePreferencesStore()
  const searchParams = useSearchParams()
  const isDark = theme === "dark"
  const usernamePrefill = searchParams.get("username")?.trim() || ""

  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState(usernamePrefill)
  const [searching, setSearching] = useState(false)
  const [searchResults, setSearchResults] = useState<SocialUserSummary[]>([])
  const [relationships, setRelationships] = useState<SocialRelationshipListResponse | null>(null)
  const [conversations, setConversations] = useState<DirectConversationSummary[]>([])
  const [selectedConversationId, setSelectedConversationId] = useState<string | null>(null)
  const [selectedSearchUser, setSelectedSearchUser] = useState<SocialUserSummary | null>(null)
  const [messages, setMessages] = useState<DirectMessage[]>([])
  const [messageDraft, setMessageDraft] = useState("")
  const [sending, setSending] = useState(false)
  const [status, setStatus] = useState<string | null>(null)
  const [refreshTick, setRefreshTick] = useState(0)
  const listIntervalRef = useRef<number | null>(null)
  const messageIntervalRef = useRef<number | null>(null)
  const conversationPollMs = mode === "sidebar" ? SIDEBAR_CONVERSATION_POLL_MS : PAGE_CONVERSATION_POLL_MS
  const messagePollMs = mode === "sidebar" ? SIDEBAR_MESSAGE_POLL_MS : PAGE_MESSAGE_POLL_MS

  const selectedConversation = useMemo(
    () => conversations.find((item) => item.id === selectedConversationId) ?? null,
    [conversations, selectedConversationId],
  )

  const loadRelationships = async () => {
    if (!user) return
    try {
      const relationshipPayload = await socialApi.listRelationships()
      setRelationships(relationshipPayload)
    } catch {
      // Keep the last known relationship state if the background refresh fails.
    }
  }

  const hydrateConversations = async (options?: { keepSelection?: boolean; silent?: boolean }) => {
    if (!user) return
    if (!options?.silent) {
      setLoading(true)
    }
    try {
      const conversationPayload = await socialApi.listConversations()
      setConversations(conversationPayload.items)
      emitChatsChanged()
      if (!options?.keepSelection) {
        setSelectedConversationId((current) => current || conversationPayload.items[0]?.id || null)
      }
      setStatus(null)
    } catch {
      setStatus("Could not load chats right now.")
    } finally {
      if (!options?.silent) {
        setLoading(false)
      }
    }
  }

  const loadMessages = async (conversationId: string, options?: { markRead?: boolean }) => {
    try {
      const payload = await socialApi.listMessages(conversationId)
      setMessages(payload.items)
      if (options?.markRead !== false) {
        await socialApi.markConversationRead(conversationId)
        emitChatsChanged()
        setConversations((current) => current.map((item) => item.id === conversationId ? { ...item, unread_count: 0 } : item))
      }
      setStatus(null)
    } catch {
      setStatus("Could not load messages for this conversation.")
    }
  }

  const runSearch = async (query: string) => {
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
  }

  useEffect(() => {
    if (!user) return
    void hydrateConversations()
  }, [user, refreshTick])

  useEffect(() => {
    if (!user) return
    void loadRelationships()
  }, [user, refreshTick])

  useEffect(() => {
    if (usernamePrefill) {
      void runSearch(usernamePrefill)
    }
  }, [usernamePrefill])

  useEffect(() => {
    if (!selectedConversationId) {
      setMessages([])
      return
    }
      void loadMessages(selectedConversationId)
  }, [selectedConversationId])

  useEffect(() => {
    if (!user) return
    listIntervalRef.current = window.setInterval(() => {
      if (document.visibilityState !== "visible") return
      void hydrateConversations({ keepSelection: true, silent: true })
    }, conversationPollMs)
    return () => {
      if (listIntervalRef.current) window.clearInterval(listIntervalRef.current)
    }
  }, [conversationPollMs, user])

  useEffect(() => {
    if (!selectedConversationId) return
    messageIntervalRef.current = window.setInterval(() => {
      if (document.visibilityState !== "visible") return
      void loadMessages(selectedConversationId, { markRead: (selectedConversation?.unread_count ?? 0) > 0 })
    }, messagePollMs)
    return () => {
      if (messageIntervalRef.current) window.clearInterval(messageIntervalRef.current)
    }
  }, [messagePollMs, selectedConversation, selectedConversationId])

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
          <div className={`rounded-3xl border px-6 py-6 text-sm ${isDark ? "border-white/10 bg-[#0c1219] text-slate-400" : "border-slate-200 bg-white text-slate-600"}`}>
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
          <div className={`max-w-md rounded-3xl border px-6 py-6 ${isDark ? "border-white/10 bg-[#0c1219]" : "border-slate-200 bg-white"}`}>
            <p className="text-lg font-semibold">Sign in to use direct messages</p>
            <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-400" : "text-slate-600"}`}>
              Private chats are only available to signed-in members. Friend requests are approved from notifications after you sign in.
            </p>
            <Link
              href="/login"
              className={`mt-4 inline-flex rounded-full px-4 py-2 text-sm font-semibold ${isDark ? "bg-amber-400 text-slate-950 hover:bg-amber-300" : "bg-[#ff6a1a] text-white hover:bg-[#f05a09]"}`}
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
          className={`rounded-full border px-3 py-2 text-xs font-medium transition ${isDark ? "border-white/10 bg-white/5 text-slate-200 hover:bg-white/10" : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50"}`}
        >
          Refresh
        </button>
      </div>

      <div className="grid min-h-0 flex-1 lg:grid-cols-[18rem_minmax(0,1fr)]">
        <aside className={`min-h-0 border-b p-4 lg:border-b-0 lg:border-r ${isDark ? "border-white/10 bg-[#0a0f14]" : "border-slate-200 bg-slate-50/60"}`}>
          <label className={`flex h-11 items-center gap-3 rounded-2xl border px-4 ${isDark ? "border-white/10 bg-[#111822]" : "border-slate-200 bg-white"}`}>
            <SearchIcon className={isDark ? "text-slate-500" : "text-slate-400"} />
            <input
              value={search}
              onChange={(event) => void runSearch(event.target.value)}
              placeholder="Search usernames"
              className={`w-full bg-transparent text-sm outline-none ${isDark ? "placeholder:text-slate-600" : "placeholder:text-slate-400"}`}
            />
          </label>

          {relationships?.incoming_requests.length ? (
            <div className="mt-4 space-y-2">
              <p className={`text-[11px] font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-slate-500"}`}>Pending for you</p>
              {relationships.incoming_requests.slice(0, 3).map((request) => (
                <div key={request.id} className={`rounded-2xl border px-3 py-3 text-sm ${isDark ? "border-white/10 bg-white/[0.03] text-slate-300" : "border-slate-200 bg-white text-slate-700"}`}>
                  @{request.requester_username || "member"} wants to connect.
                </div>
              ))}
            </div>
          ) : null}

          <div className="mt-4">
            <p className={`text-[11px] font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-slate-500"}`}>Conversations</p>
            <div className="mt-3 space-y-2">
              {loading ? (
                <div className={`rounded-2xl border px-3 py-4 text-sm ${isDark ? "border-white/10 bg-white/[0.03] text-slate-400" : "border-slate-200 bg-white text-slate-500"}`}>Loading chats...</div>
              ) : conversations.length === 0 ? (
                <div className={`rounded-2xl border px-3 py-4 text-sm ${isDark ? "border-white/10 bg-white/[0.03] text-slate-400" : "border-slate-200 bg-white text-slate-500"}`}>No conversations yet.</div>
              ) : conversations.map((conversation) => (
                <button
                  key={conversation.id}
                  type="button"
                  onClick={() => {
                    setSelectedConversationId(conversation.id)
                    setSelectedSearchUser(null)
                  }}
                  className={`w-full rounded-2xl border px-3 py-3 text-left transition ${selectedConversationId === conversation.id ? (isDark ? "border-amber-400/30 bg-amber-400/10" : "border-orange-200 bg-orange-50") : (isDark ? "border-white/10 bg-white/[0.03] hover:bg-white/[0.05]" : "border-slate-200 bg-white hover:bg-slate-50")}`}
                >
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-sm font-semibold">@{conversation.other_user.username}</p>
                    {conversation.unread_count > 0 ? (
                      <span className="rounded-full bg-rose-500 px-2 py-0.5 text-[11px] font-semibold text-white">{Math.min(conversation.unread_count, 9)}</span>
                    ) : null}
                  </div>
                  <p className={`mt-1 line-clamp-2 text-xs leading-5 ${isDark ? "text-slate-400" : "text-slate-600"}`}>{conversation.last_message_preview || "No messages yet."}</p>
                </button>
              ))}
            </div>
          </div>

          {search.length >= 2 ? (
            <div className="mt-4">
              <p className={`text-[11px] font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-slate-500"}`}>Search results</p>
              <div className="mt-3 space-y-2">
                {searching ? (
                  <div className={`rounded-2xl border px-3 py-4 text-sm ${isDark ? "border-white/10 bg-white/[0.03] text-slate-400" : "border-slate-200 bg-white text-slate-500"}`}>Searching...</div>
                ) : searchResults.length === 0 ? (
                  <div className={`rounded-2xl border px-3 py-4 text-sm ${isDark ? "border-white/10 bg-white/[0.03] text-slate-400" : "border-slate-200 bg-white text-slate-500"}`}>No matching usernames.</div>
                ) : searchResults.map((result) => (
                  <button
                    key={result.id}
                    type="button"
                    onClick={() => setSelectedSearchUser(result)}
                    className={`w-full rounded-2xl border px-3 py-3 text-left transition ${selectedSearchUser?.id === result.id ? (isDark ? "border-cyan-400/30 bg-cyan-400/10" : "border-cyan-200 bg-cyan-50") : (isDark ? "border-white/10 bg-white/[0.03]" : "border-slate-200 bg-white")}`}
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
            <div className={`mb-4 rounded-2xl border px-4 py-3 text-sm ${isDark ? "border-white/10 bg-white/[0.03] text-slate-300" : "border-slate-200 bg-slate-50 text-slate-700"}`}>{status}</div>
          ) : null}

          {selectedConversation ? (
            <div className="flex h-full min-h-[28rem] flex-col">
              <div className={`rounded-3xl border px-4 py-4 ${isDark ? "border-white/10 bg-[#0c1219]" : "border-slate-200 bg-slate-50"}`}>
                <p className="text-lg font-semibold">@{selectedConversation.other_user.username}</p>
                <p className={`mt-1 text-sm ${isDark ? "text-slate-400" : "text-slate-600"}`}>
                  {selectedConversation.other_user.messaging_permission === "friends_only" ? "Friends only messaging" : "Open to messages from anyone"}
                </p>
              </div>

              <div className={`reader-scrollbar mt-4 flex-1 overflow-y-auto rounded-3xl border p-4 ${isDark ? "border-white/10 bg-[#0c1219]" : "border-slate-200 bg-white"}`}>
                <div className="space-y-3">
                  {messages.map((message) => {
                    const mine = message.sender_user_id === user?.id
                    return (
                      <div key={message.id} className={`flex ${mine ? "justify-end" : "justify-start"}`}>
                        <div className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-6 ${mine ? (isDark ? "bg-amber-400 text-slate-950" : "bg-[#ff6a1a] text-white") : (isDark ? "bg-white/[0.05] text-slate-100" : "bg-slate-100 text-slate-800")}`}>
                          <p>{message.body}</p>
                          <p className={`mt-2 text-[11px] ${mine ? "text-current/80" : (isDark ? "text-slate-500" : "text-slate-500")}`}>{new Date(message.created_at).toLocaleString()}</p>
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
                  placeholder="Write a message"
                  className={`min-h-[6rem] flex-1 rounded-2xl border px-4 py-3 text-sm leading-6 outline-none ${isDark ? "border-white/10 bg-[#0c1219] text-slate-100 placeholder:text-slate-600" : "border-slate-200 bg-white text-slate-900 placeholder:text-slate-400"}`}
                />
                <button
                  type="button"
                  onClick={() => void handleSendMessage()}
                  disabled={sending || !messageDraft.trim()}
                  className={`self-end rounded-full px-4 py-3 text-sm font-semibold transition ${isDark ? "bg-amber-400 text-slate-950 hover:bg-amber-300 disabled:bg-amber-400/40" : "bg-[#ff6a1a] text-white hover:bg-[#f05a09] disabled:bg-slate-300"}`}
                >
                  {sending ? "Sending..." : "Send"}
                </button>
              </div>
            </div>
          ) : selectedSearchUser ? (
            <div className={`rounded-3xl border p-5 ${isDark ? "border-white/10 bg-[#0c1219]" : "border-slate-200 bg-white"}`}>
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
                    className={`rounded-full px-4 py-3 text-sm font-semibold transition ${isDark ? "bg-amber-400 text-slate-950 hover:bg-amber-300" : "bg-[#ff6a1a] text-white hover:bg-[#f05a09]"}`}
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
                    className={`rounded-full px-4 py-3 text-sm font-semibold transition ${isDark ? "border border-white/10 bg-white/[0.03] text-slate-100 hover:bg-white/[0.05]" : "border border-slate-200 bg-white text-slate-900 hover:bg-slate-50"}`}
                  >
                    Send friend request
                  </button>
                )}
              </div>
            </div>
          ) : (
            <div className={`rounded-3xl border p-6 ${isDark ? "border-white/10 bg-[#0c1219] text-slate-400" : "border-slate-200 bg-white text-slate-600"}`}>
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
