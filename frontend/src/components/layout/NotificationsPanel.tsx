"use client"

import Link from "next/link"
import { useState } from "react"

import { booksApi } from "@/lib/api/books"
import { socialApi } from "@/lib/api/social"
import { useNotifications } from "@/lib/hooks/useNotifications"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import type { RevisionActionItem, RevisionIntelligence } from "@/types/book"
import type { NotificationItem } from "@/types/notifications"

function severityBadgeClass(severity: string, isDark: boolean) {
  if (severity === "high") return isDark ? "bg-rose-500/15 text-rose-200" : "bg-rose-50 text-rose-700"
  if (severity === "medium") return isDark ? "bg-amber-500/15 text-amber-200" : "bg-amber-50 text-amber-700"
  return isDark ? "bg-white/10 text-slate-200" : "border border-stone-200 bg-white text-stone-700"
}

function RevisionDetailCard({ item, isDark }: { item: RevisionActionItem; isDark: boolean }) {
  return (
    <div className={`rounded-[0.9rem] border p-3 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-stone-200 bg-white"}`}>
      <div className="flex flex-wrap items-center gap-2">
        <span className={`rounded-full px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] ${severityBadgeClass(item.severity, isDark)}`}>
          {item.severity}
        </span>
        {item.chapter_ref ? <span className={isDark ? "text-xs text-slate-500" : "text-xs text-stone-400"}>{`Chapter ${item.chapter_ref}`}</span> : null}
      </div>
      <p className={`mt-2 text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{item.title}</p>
      <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-600"}`}>{item.description}</p>
      {item.recommendation ? <p className={`mt-2 text-xs leading-5 ${isDark ? "text-sky-300" : "text-sky-700"}`}>{item.recommendation}</p> : null}
    </div>
  )
}

export function NotificationsPanel({ mode = "sidebar" }: { mode?: "sidebar" | "page" }) {
  const { theme } = usePreferencesStore()
  const isDark = theme === "dark"
  const { items, unreadCount, loading, error, markRead, markAllRead, refresh } = useNotifications()
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [loadingDetailsId, setLoadingDetailsId] = useState<string | null>(null)
  const [detailsErrorId, setDetailsErrorId] = useState<string | null>(null)
  const [revisionDetailsByBookId, setRevisionDetailsByBookId] = useState<Record<string, RevisionIntelligence>>({})

  const toggleDetails = async (item: NotificationItem) => {
    if (expandedId === item.id) {
      setExpandedId(null)
      setDetailsErrorId(null)
      return
    }

    setExpandedId(item.id)
    setDetailsErrorId(null)

    if (item.kind !== "revision_digest" || !item.book_id || revisionDetailsByBookId[item.book_id]) {
      return
    }

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

  const renderNotificationDetails = (item: NotificationItem) => {
    const chapterNumber = typeof item.data?.chapter_number === "number" ? item.data.chapter_number : null
    const characterCount = typeof item.data?.character_count === "number" ? item.data.character_count : null
    const relationshipCount = typeof item.data?.relationship_count === "number" ? item.data.relationship_count : null
    const plotThreadCount = typeof item.data?.plot_thread_count === "number" ? item.data.plot_thread_count : null
    const continuityIssueCount = typeof item.data?.continuity_issue_count === "number" ? item.data.continuity_issue_count : null
    const estimatedMinutes =
      typeof item.data?.estimated_minutes === "number" || typeof item.data?.estimated_minutes === "string"
        ? item.data.estimated_minutes
        : null
    const fileSizeMb = typeof item.data?.file_size_mb === "number" ? item.data.file_size_mb : null
    const analysisComplete = item.data?.analysis_complete === true
    const summary = typeof item.data?.summary === "string" ? item.data.summary : null
    const continuityFlags = Array.isArray(item.data?.continuity_flags)
      ? item.data.continuity_flags.filter((flag): flag is string => typeof flag === "string")
      : []

    if (item.kind === "revision_digest" && item.book_id) {
      const revision = revisionDetailsByBookId[item.book_id]
      if (loadingDetailsId === item.id) {
        return (
          <div className={`mt-4 rounded-[1rem] border p-4 text-sm ${isDark ? "border-white/10 bg-black/20 text-slate-400" : "border-stone-200 bg-stone-50 text-stone-500"}`}>
            Loading revision details...
          </div>
        )
      }
      if (detailsErrorId === item.id) {
        return (
          <div className={`mt-4 rounded-[1rem] border p-4 text-sm ${isDark ? "border-rose-500/20 bg-rose-500/10 text-rose-200" : "border-rose-200 bg-rose-50 text-rose-700"}`}>
            We could not load the revision details for this notification yet.
          </div>
        )
      }
      if (!revision) return null

      return (
        <div className={`mt-4 rounded-[1rem] border p-4 ${isDark ? "border-white/10 bg-black/20" : "border-stone-200 bg-stone-50"}`}>
          <p className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Revision Details</p>
          <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-600"}`}>{revision.summary.hero_message}</p>
          {revision.summary.recent_edit_label ? (
            <p className={`mt-2 text-sm leading-6 ${isDark ? "text-violet-200" : "text-violet-800"}`}>{revision.summary.recent_edit_label}</p>
          ) : null}
          <div className="mt-3 flex flex-wrap gap-2">
            <span className={`rounded-full px-3 py-1 text-[11px] font-semibold ${isDark ? "bg-white/10 text-slate-200" : "border border-stone-200 bg-white text-stone-700"}`}>
              {revision.summary.active_item_count} active items
            </span>
            <span className={`rounded-full px-3 py-1 text-[11px] font-semibold ${isDark ? "bg-rose-500/15 text-rose-200" : "bg-rose-50 text-rose-700"}`}>
              {revision.summary.high_severity_count} high severity
            </span>
            <span className={`rounded-full px-3 py-1 text-[11px] font-semibold ${isDark ? "bg-sky-500/15 text-sky-200" : "bg-sky-50 text-sky-700"}`}>
              {revision.summary.task_ready_count} task-ready
            </span>
          </div>
          <div className="mt-4 space-y-3">
            {revision.change_impacts.length > 0 ? (
              revision.change_impacts.slice(0, 3).map((detail) => (
                <RevisionDetailCard key={detail.id} item={detail} isDark={isDark} />
              ))
            ) : (
              <p className={isDark ? "text-sm text-slate-400" : "text-sm text-stone-500"}>No active downstream impact warnings are surfaced right now.</p>
            )}
          </div>
        </div>
      )
    }

    if (item.kind === "book_ready") {
      return (
        <div className={`mt-4 rounded-[1rem] border p-4 ${isDark ? "border-white/10 bg-black/20" : "border-stone-200 bg-stone-50"}`}>
          <p className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Processing Status</p>
          <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-600"}`}>
            {analysisComplete
              ? "LoreVia has finished the full analysis pass for this manuscript."
              : "LoreVia has finished ingestion and is still completing deeper analysis for this manuscript."}
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            {characterCount !== null ? <span className={`rounded-full px-3 py-1 text-[11px] font-semibold ${isDark ? "bg-white/10 text-slate-200" : "border border-stone-200 bg-white text-stone-700"}`}>{characterCount} characters</span> : null}
            {relationshipCount !== null ? <span className={`rounded-full px-3 py-1 text-[11px] font-semibold ${isDark ? "bg-white/10 text-slate-200" : "border border-stone-200 bg-white text-stone-700"}`}>{relationshipCount} relationships</span> : null}
            {plotThreadCount !== null ? <span className={`rounded-full px-3 py-1 text-[11px] font-semibold ${isDark ? "bg-white/10 text-slate-200" : "border border-stone-200 bg-white text-stone-700"}`}>{plotThreadCount} plot threads</span> : null}
            {continuityIssueCount !== null ? <span className={`rounded-full px-3 py-1 text-[11px] font-semibold ${isDark ? "bg-white/10 text-slate-200" : "border border-stone-200 bg-white text-stone-700"}`}>{continuityIssueCount} continuity issues</span> : null}
          </div>
        </div>
      )
    }

    if (item.kind === "upload_processing") {
      return (
        <div className={`mt-4 rounded-[1rem] border p-4 ${isDark ? "border-white/10 bg-black/20" : "border-stone-200 bg-stone-50"}`}>
          <p className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Processing Estimate</p>
          <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-600"}`}>
            LoreVia is still parsing and indexing this upload. You can leave the page while it finishes in the background.
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            {estimatedMinutes ? <span className={`rounded-full px-3 py-1 text-[11px] font-semibold ${isDark ? "bg-white/10 text-slate-200" : "border border-stone-200 bg-white text-stone-700"}`}>ETA {estimatedMinutes} min</span> : null}
            {fileSizeMb !== null ? <span className={`rounded-full px-3 py-1 text-[11px] font-semibold ${isDark ? "bg-white/10 text-slate-200" : "border border-stone-200 bg-white text-stone-700"}`}>{fileSizeMb} MB upload</span> : null}
          </div>
        </div>
      )
    }

    if (item.kind === "chapter_report" || item.kind === "continuity_risk") {
      return (
        <div className={`mt-4 rounded-[1rem] border p-4 ${isDark ? "border-white/10 bg-black/20" : "border-stone-200 bg-stone-50"}`}>
          <p className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Story Details</p>
          {summary ? <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-600"}`}>{summary}</p> : null}
          {continuityFlags.length > 0 ? (
            <div className="mt-3 space-y-2">
              {continuityFlags.slice(0, 3).map((flag) => (
                <p key={flag} className={`rounded-[0.85rem] border p-3 text-sm leading-6 ${isDark ? "border-white/10 bg-white/[0.03] text-slate-300" : "border-stone-200 bg-white text-stone-600"}`}>{flag}</p>
              ))}
            </div>
          ) : null}
          {chapterNumber ? <p className={`mt-3 text-xs ${isDark ? "text-slate-500" : "text-stone-400"}`}>Focus chapter: {chapterNumber}</p> : null}
        </div>
      )
    }

    return (
      <div className={`mt-4 rounded-[1rem] border p-4 text-sm leading-6 ${isDark ? "border-white/10 bg-black/20 text-slate-300" : "border-stone-200 bg-stone-50 text-stone-600"}`}>
        {item.body}
      </div>
    )
  }

  return (
    <section className={`flex h-full flex-col ${mode === "sidebar" ? "" : "mx-auto max-w-4xl"}`}>
      <div className={`flex items-center justify-between gap-3 border-b px-5 py-4 ${isDark ? "border-white/10" : "border-stone-200"}`}>
        <div>
          <p className={`text-xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Notifications</p>
          <h1 className={`mt-1 text-xl font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>Updates from your writing workspace</h1>
        </div>
        <button
          type="button"
          onClick={markAllRead}
          disabled={unreadCount === 0}
          className={`rounded-full border px-3 py-2 text-xs font-medium transition disabled:opacity-50 ${isDark ? "border-white/10 bg-white/5 text-slate-200 hover:bg-white/10" : "border-stone-200 bg-white text-stone-700 hover:bg-stone-50"}`}
        >
          Mark all read
        </button>
      </div>

      <div className="reader-scrollbar flex-1 overflow-y-auto px-5 py-5">
        {loading ? (
          <div className={`rounded-[1.2rem] border p-5 text-sm ${isDark ? "border-white/10 bg-white/[0.03] text-slate-400" : "border-stone-200 bg-white text-stone-500"}`}>
            Loading notifications...
          </div>
        ) : error ? (
          <div className={`rounded-[1.2rem] border p-5 text-sm ${isDark ? "border-rose-500/20 bg-rose-500/10 text-rose-200" : "border-rose-200 bg-rose-50 text-rose-700"}`}>
            {error}
          </div>
        ) : items.length === 0 ? (
          <div className={`rounded-[1.2rem] border p-6 text-sm ${isDark ? "border-white/10 bg-white/[0.03] text-slate-400" : "border-stone-200 bg-white text-stone-500"}`}>
            Nothing new yet. When LoreVia detects notable chapter changes, they'll appear here.
          </div>
        ) : (
          <div className="space-y-3">
            {items.map((item) => {
              const chapterNumber = typeof item.data?.chapter_number === "number" ? item.data.chapter_number : null
              const characterCount = typeof item.data?.character_count === "number" ? item.data.character_count : null
              const relationshipCount = typeof item.data?.relationship_count === "number" ? item.data.relationship_count : null
              const plotThreadCount = typeof item.data?.plot_thread_count === "number" ? item.data.plot_thread_count : null
              const continuityIssueCount = typeof item.data?.continuity_issue_count === "number" ? item.data.continuity_issue_count : null
              const activeRevisionItems = typeof item.data?.active_item_count === "number" ? item.data.active_item_count : null
              const highRevisionItems = typeof item.data?.high_severity_count === "number" ? item.data.high_severity_count : null
              const revisionTagline = typeof item.data?.tagline === "string" ? item.data.tagline : null
              const revisionHero = typeof item.data?.hero_message === "string" ? item.data.hero_message : null
              const recentEditLabel = typeof item.data?.recent_edit_label === "string" ? item.data.recent_edit_label : null
              const topRevisionTitle = typeof item.data?.top_item_title === "string" ? item.data.top_item_title : null
              const friendRequestId = typeof item.data?.friend_request_id === "string" ? item.data.friend_request_id : null

              return (
                <article
                  key={item.id}
                  className={`rounded-[1.2rem] border p-4 transition ${item.read_at ? (isDark ? "border-white/10 bg-white/[0.03]" : "border-stone-200 bg-white") : (isDark ? "border-indigo-400/30 bg-indigo-400/10" : "border-violet-200 bg-violet-50")}`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{item.title}</p>
                      <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-600"}`}>{item.body}</p>
                      {item.kind === "book_ready" ? (
                        <div className="mt-3 flex flex-wrap gap-2">
                          {characterCount !== null ? <span className={`rounded-full px-3 py-1 text-[11px] font-semibold ${isDark ? "bg-white/10 text-slate-200" : "border border-stone-200 bg-white text-stone-700"}`}>{characterCount} characters</span> : null}
                          {relationshipCount !== null ? <span className={`rounded-full px-3 py-1 text-[11px] font-semibold ${isDark ? "bg-white/10 text-slate-200" : "border border-stone-200 bg-white text-stone-700"}`}>{relationshipCount} relationships</span> : null}
                          {plotThreadCount !== null ? <span className={`rounded-full px-3 py-1 text-[11px] font-semibold ${isDark ? "bg-white/10 text-slate-200" : "border border-stone-200 bg-white text-stone-700"}`}>{plotThreadCount} plot threads</span> : null}
                          {continuityIssueCount !== null ? <span className={`rounded-full px-3 py-1 text-[11px] font-semibold ${isDark ? "bg-white/10 text-slate-200" : "border border-stone-200 bg-white text-stone-700"}`}>{continuityIssueCount} continuity issues</span> : null}
                        </div>
                      ) : null}
                      {item.kind === "revision_digest" ? (
                        <div className="mt-3">
                          {revisionTagline ? <p className={`text-xs font-semibold uppercase tracking-[0.2em] ${isDark ? "text-violet-300" : "text-violet-700"}`}>{revisionTagline}</p> : null}
                          {recentEditLabel ? <p className={`mt-2 text-sm leading-6 ${isDark ? "text-violet-200" : "text-violet-800"}`}>{recentEditLabel}</p> : null}
                          <div className="mt-2 flex flex-wrap gap-2">
                            {activeRevisionItems !== null ? <span className={`rounded-full px-3 py-1 text-[11px] font-semibold ${isDark ? "bg-white/10 text-slate-200" : "border border-stone-200 bg-white text-stone-700"}`}>{activeRevisionItems} active items</span> : null}
                            {highRevisionItems !== null ? <span className={`rounded-full px-3 py-1 text-[11px] font-semibold ${isDark ? "bg-rose-500/15 text-rose-200" : "bg-rose-50 text-rose-700"}`}>{highRevisionItems} high severity</span> : null}
                          </div>
                          {revisionHero ? <p className={`mt-3 text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-600"}`}>{revisionHero}</p> : null}
                          {topRevisionTitle ? <p className={`mt-2 text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>Top issue: {topRevisionTitle}</p> : null}
                        </div>
                      ) : null}
                      <div className={`mt-3 flex flex-wrap items-center gap-3 text-xs ${isDark ? "text-slate-500" : "text-stone-400"}`}>
                        <span>{new Date(item.created_at).toLocaleString()}</span>
                        {chapterNumber ? <span>Chapter {chapterNumber}</span> : null}
                      </div>
                      {item.kind === "friend_request" && friendRequestId ? (
                        <div className="mt-4 flex flex-wrap gap-2">
                          <button
                            type="button"
                            onClick={async () => {
                              await socialApi.acceptFriendRequest(friendRequestId)
                              await markRead(item.id)
                              await refresh()
                            }}
                            className={`rounded-full px-3 py-2 text-xs font-semibold transition ${isDark ? "bg-emerald-400 text-slate-950 hover:bg-emerald-300" : "bg-emerald-600 text-white hover:bg-emerald-500"}`}
                          >
                            Accept
                          </button>
                          <button
                            type="button"
                            onClick={async () => {
                              await socialApi.declineFriendRequest(friendRequestId)
                              await markRead(item.id)
                              await refresh()
                            }}
                            className={`rounded-full border px-3 py-2 text-xs font-semibold transition ${isDark ? "border-white/10 bg-white/5 text-slate-200 hover:bg-white/10" : "border-stone-200 bg-white text-stone-700 hover:bg-stone-50"}`}
                          >
                            Decline
                          </button>
                        </div>
                      ) : (
                        <div className="mt-4 flex flex-wrap gap-3">
                          <button
                            type="button"
                            onClick={() => void toggleDetails(item)}
                            className={`text-sm font-medium transition ${isDark ? "text-sky-300 hover:text-sky-200" : "text-sky-700 hover:text-sky-800"}`}
                          >
                            {expandedId === item.id ? "Hide details" : "View details"}
                          </button>
                        </div>
                      )}
                    </div>
                    {!item.read_at ? (
                      <button
                        type="button"
                        onClick={() => markRead(item.id)}
                        className={`shrink-0 rounded-full border px-3 py-1.5 text-xs font-medium transition ${isDark ? "border-white/10 bg-white/5 text-slate-200 hover:bg-white/10" : "border-stone-200 bg-white text-stone-700 hover:bg-stone-50"}`}
                      >
                        Mark read
                      </button>
                    ) : null}
                  </div>
                  {expandedId === item.id ? renderNotificationDetails(item) : null}
                  {item.book_id ? (
                    <div className="mt-4">
                      <Link
                        href={item.kind === "revision_digest" ? `/${item.book_id}` : chapterNumber ? `/${item.book_id}/chapter/${chapterNumber}` : `/${item.book_id}`}
                        className={`text-sm font-medium transition ${isDark ? "text-indigo-300 hover:text-indigo-200" : "text-violet-700 hover:text-violet-800"}`}
                      >
                        {item.kind === "revision_digest" ? "Open revision command center ->" : "Open in LoreVia ->"}
                      </Link>
                    </div>
                  ) : null}
                </article>
              )
            })}
          </div>
        )}
      </div>
    </section>
  )
}
