"use client"

import Link from "next/link"
import type { Route } from "next"
import { useState } from "react"

import { booksApi } from "@/lib/api/books"
import { socialApi } from "@/lib/api/social"
import { useNotificationsState } from "@/lib/hooks/useNotifications"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import type { RevisionIntelligence } from "@/types/book"
import type { NotificationItem } from "@/types/notifications"

function detailSupported(item: NotificationItem) {
  return ["revision_digest", "book_ready", "upload_processing", "chapter_report", "continuity_risk"].includes(item.kind)
}

function notificationHref(item: NotificationItem) {
  const explicitHref = typeof item.data?.href === "string" && item.data.href.startsWith("/") ? item.data.href : null
  if (explicitHref) return explicitHref
  if (!item.book_id) return null
  const chapterNumber = typeof item.data?.chapter_number === "number" ? item.data.chapter_number : null
  return chapterNumber ? `/${item.book_id}/chapter/${chapterNumber}` : `/${item.book_id}`
}

function relativeTime(value: string) {
  const date = new Date(value)
  const elapsedMinutes = Math.max(0, Math.floor((Date.now() - date.getTime()) / 60_000))
  if (elapsedMinutes < 1) return "Just now"
  if (elapsedMinutes < 60) return `${elapsedMinutes}m ago`
  if (elapsedMinutes < 1_440) return `${Math.floor(elapsedMinutes / 60)}h ago`
  if (elapsedMinutes < 10_080) return `${Math.floor(elapsedMinutes / 1_440)}d ago`
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric", year: date.getFullYear() === new Date().getFullYear() ? undefined : "numeric" })
}

export function NotificationsPanel({ mode = "sidebar", enabled = true }: { mode?: "sidebar" | "page"; enabled?: boolean }) {
  const { theme } = usePreferencesStore()
  const isDark = theme === "dark"
  const { items, unreadCount, loading, loadingMore, hasMore, error, markRead, markAllRead, refresh, loadMore } = useNotificationsState(40, {
    enabled,
    pollMs: 60_000,
    refreshOnFocus: true,
  })
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [loadingDetailsId, setLoadingDetailsId] = useState<string | null>(null)
  const [detailsErrorId, setDetailsErrorId] = useState<string | null>(null)
  const [revisionDetailsByBookId, setRevisionDetailsByBookId] = useState<Record<string, RevisionIntelligence>>({})
  const border = isDark ? "border-white/10" : "border-stone-200"
  const muted = isDark ? "text-slate-400" : "text-stone-600"

  async function toggleDetails(item: NotificationItem) {
    if (expandedId === item.id) {
      setExpandedId(null)
      setDetailsErrorId(null)
      return
    }
    setExpandedId(item.id)
    setDetailsErrorId(null)
    if (item.kind !== "revision_digest" || !item.book_id || revisionDetailsByBookId[item.book_id]) return

    setLoadingDetailsId(item.id)
    try {
      const revision = await booksApi.getRevisionIntelligence(item.book_id)
      setRevisionDetailsByBookId((current) => ({ ...current, [item.book_id!]: revision }))
    } catch {
      setDetailsErrorId(item.id)
    } finally {
      setLoadingDetailsId(null)
    }
  }

  async function acceptFriendRequest(item: NotificationItem, requestId: string) {
    await socialApi.acceptFriendRequest(requestId)
    await markRead(item.id)
    await refresh()
  }

  async function declineFriendRequest(item: NotificationItem, requestId: string) {
    await socialApi.declineFriendRequest(requestId)
    await markRead(item.id)
    await refresh()
  }

  function handleMarkRead(id: string) {
    void markRead(id).catch(() => undefined)
  }

  function handleMarkAllRead() {
    void markAllRead().catch(() => undefined)
  }

  return (
    <section className={`flex h-full flex-col ${mode === "sidebar" ? "" : "mx-auto max-w-4xl border-x"} ${border}`}>
      <header className={`flex items-start justify-between gap-4 border-b px-5 py-5 ${border}`}>
        <div>
          <h1 className={`text-xl font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>Notifications</h1>
          <p className={`mt-1 text-sm ${muted}`}>{unreadCount > 0 ? `${unreadCount} unread update${unreadCount === 1 ? "" : "s"}` : "You’re up to date"}</p>
        </div>
        <button type="button" onClick={handleMarkAllRead} disabled={unreadCount === 0} className={`border px-3 py-2 text-xs font-medium transition disabled:opacity-50 ${isDark ? "border-white/10 text-slate-200 hover:bg-white/5" : "border-stone-300 text-stone-700 hover:bg-stone-50"}`}>
          Mark all read
        </button>
      </header>

      <div className="reader-scrollbar flex-1 overflow-y-auto px-4 py-5 sm:px-5">
        {loading ? (
          <div className={`border p-5 text-sm ${border} ${muted}`}>Loading notifications…</div>
        ) : error ? (
          <div className="border border-rose-300/50 bg-rose-50 p-5 text-sm text-rose-800 dark:bg-rose-950/20 dark:text-rose-200">{error}</div>
        ) : items.length === 0 ? (
          <div className={`border p-6 text-sm ${border} ${muted}`}>Nothing new yet. Important workspace changes will appear here.</div>
        ) : (
          <div className={`divide-y border ${border} ${isDark ? "divide-white/10" : "divide-stone-200"}`}>
            {items.map((item) => {
              const unread = !item.read_at
              const requestId = typeof item.data?.friend_request_id === "string" ? item.data.friend_request_id : null
              const href = notificationHref(item)
              return (
                <article key={item.id} className={`relative px-4 py-4 sm:px-5 ${unread ? (isDark ? "bg-sky-400/[0.06]" : "bg-sky-50/70") : (isDark ? "bg-white/[0.02]" : "bg-white")}`}>
                  {unread ? <span className={`absolute bottom-4 left-0 top-4 w-0.5 ${isDark ? "bg-sky-300" : "bg-sky-600"}`} aria-label="Unread" /> : null}
                  <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-start">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                        <h2 className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{item.title}</h2>
                        <time dateTime={item.created_at} title={new Date(item.created_at).toLocaleString()} className={`text-xs ${muted}`}>{relativeTime(item.created_at)}</time>
                      </div>
                      <p className={`mt-1 text-sm leading-6 ${muted}`}>{item.body}</p>
                    </div>
                    {unread ? (
                      <button type="button" onClick={() => handleMarkRead(item.id)} className={`w-fit text-xs font-medium hover:underline ${muted}`}>Mark read</button>
                    ) : null}
                  </div>

                  {item.kind === "friend_request" && requestId ? (
                    <div className="mt-3 flex flex-wrap gap-2">
                      <button type="button" onClick={() => void acceptFriendRequest(item, requestId).catch(() => undefined)} className="bg-emerald-700 px-3 py-2 text-xs font-semibold text-white hover:bg-emerald-600">Accept</button>
                      <button type="button" onClick={() => void declineFriendRequest(item, requestId).catch(() => undefined)} className={`border px-3 py-2 text-xs font-semibold ${isDark ? "border-white/10 text-slate-200" : "border-stone-300 text-stone-700"}`}>Decline</button>
                    </div>
                  ) : (
                    <div className="mt-3 flex flex-wrap gap-4">
                      {href ? <Link href={href as Route} onClick={() => handleMarkRead(item.id)} className={`text-sm font-semibold hover:underline ${isDark ? "text-teal-300" : "text-teal-700"}`}>Open</Link> : null}
                      {detailSupported(item) ? <button type="button" onClick={() => void toggleDetails(item)} className={`text-sm font-medium hover:underline ${muted}`}>{expandedId === item.id ? "Hide details" : "View details"}</button> : null}
                    </div>
                  )}

                  {expandedId === item.id ? (
                    <NotificationDetails
                      item={item}
                      revision={item.book_id ? revisionDetailsByBookId[item.book_id] ?? null : null}
                      loading={loadingDetailsId === item.id}
                      failed={detailsErrorId === item.id}
                      isDark={isDark}
                    />
                  ) : null}
                </article>
              )
            })}
          </div>
        )}

        {mode === "page" && hasMore ? (
          <button type="button" onClick={() => void loadMore()} disabled={loadingMore} className={`mt-4 w-full border px-4 py-3 text-sm font-medium disabled:opacity-50 ${border} ${muted}`}>
            {loadingMore ? "Loading older notifications…" : "Load older notifications"}
          </button>
        ) : null}
      </div>
    </section>
  )
}

function NotificationDetails({ item, revision, loading, failed, isDark }: { item: NotificationItem; revision: RevisionIntelligence | null; loading: boolean; failed: boolean; isDark: boolean }) {
  const muted = isDark ? "text-slate-400" : "text-stone-600"
  const border = isDark ? "border-white/10" : "border-stone-200"
  if (loading) return <div className={`mt-4 border-t pt-4 text-sm ${border} ${muted}`}>Loading revision details…</div>
  if (failed) return <div className="mt-4 border-t border-rose-300 pt-4 text-sm text-rose-700 dark:text-rose-200">We could not load the revision details yet.</div>

  if (item.kind === "revision_digest" && revision) {
    return (
      <div className={`mt-4 border-t pt-4 ${border}`}>
        <h3 className="text-sm font-semibold">Revision Details</h3>
        <p className={`mt-1 text-sm leading-6 ${muted}`}>{revision.summary.hero_message}</p>
        {revision.summary.recent_edit_label ? <p className={`mt-2 text-sm leading-6 ${muted}`}>{revision.summary.recent_edit_label}</p> : null}
        <dl className={`mt-3 grid grid-cols-3 divide-x border ${border} ${isDark ? "divide-white/10" : "divide-stone-200"}`}>
          <DetailMetric label="Active" value={revision.summary.active_item_count} muted={muted} />
          <DetailMetric label="High severity" value={revision.summary.high_severity_count} muted={muted} />
          <DetailMetric label="Task-ready" value={revision.summary.task_ready_count} muted={muted} />
        </dl>
        {revision.change_impacts.length ? (
          <div className={`mt-4 divide-y border-y ${border} ${isDark ? "divide-white/10" : "divide-stone-200"}`}>
            {revision.change_impacts.slice(0, 3).map((impact) => (
              <div key={impact.id} className="py-3">
                <p className="text-xs font-medium">{impact.severity} · {impact.chapter_ref ? `Chapter ${impact.chapter_ref}` : "Manuscript"}</p>
                <p className="mt-1 text-sm font-semibold">{impact.title}</p>
                <p className={`mt-1 text-sm leading-6 ${muted}`}>{impact.description}</p>
                {impact.recommendation ? <p className={`mt-1 text-sm leading-6 ${muted}`}>{impact.recommendation}</p> : null}
              </div>
            ))}
          </div>
        ) : null}
      </div>
    )
  }

  const chapterNumber = typeof item.data?.chapter_number === "number" ? item.data.chapter_number : null
  const summary = typeof item.data?.summary === "string" ? item.data.summary : null
  const analysisComplete = item.data?.analysis_complete === true
  const facts = [
    typeof item.data?.character_count === "number" ? `${item.data.character_count} characters` : null,
    typeof item.data?.relationship_count === "number" ? `${item.data.relationship_count} relationships` : null,
    typeof item.data?.plot_thread_count === "number" ? `${item.data.plot_thread_count} plot threads` : null,
    typeof item.data?.continuity_issue_count === "number" ? `${item.data.continuity_issue_count} continuity issues` : null,
    typeof item.data?.file_size_mb === "number" ? `${item.data.file_size_mb} MB upload` : null,
    chapterNumber ? `Chapter ${chapterNumber}` : null,
  ].filter((value): value is string => Boolean(value))
  const continuityFlags = Array.isArray(item.data?.continuity_flags) ? item.data.continuity_flags.filter((value): value is string => typeof value === "string") : []
  const description = item.kind === "book_ready"
    ? analysisComplete ? "The full manuscript analysis is complete." : "Ingestion is complete; deeper analysis is still running."
    : item.kind === "upload_processing"
      ? "This upload is still being parsed and indexed. You can leave while it finishes."
      : summary

  return (
    <div className={`mt-4 border-t pt-4 ${border}`}>
      {description ? <p className={`text-sm leading-6 ${muted}`}>{description}</p> : null}
      {facts.length ? <p className={`mt-2 text-sm ${muted}`}>{facts.join(" · ")}</p> : null}
      {continuityFlags.length ? <ul className={`mt-3 list-disc space-y-1 pl-5 text-sm leading-6 ${muted}`}>{continuityFlags.slice(0, 3).map((flag) => <li key={flag}>{flag}</li>)}</ul> : null}
    </div>
  )
}

function DetailMetric({ label, value, muted }: { label: string; value: number; muted: string }) {
  return <div className="px-3 py-2"><dt className={`text-xs ${muted}`}>{label}</dt><dd className="mt-1 text-lg font-semibold">{value}</dd></div>
}
