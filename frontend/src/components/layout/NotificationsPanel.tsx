"use client"

import Link from "next/link"
import { useNotifications } from "@/lib/hooks/useNotifications"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"

export function NotificationsPanel({ mode = "sidebar" }: { mode?: "sidebar" | "page" }) {
  const { theme } = usePreferencesStore()
  const isDark = theme === "dark"
  const { items, unreadCount, loading, error, markRead, markAllRead } = useNotifications()

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
            Nothing new yet. When LoreVia detects notable chapter changes, they’ll appear here.
          </div>
        ) : (
          <div className="space-y-3">
            {items.map((item) => {
              const chapterNumber = typeof item.data?.chapter_number === "number" ? item.data.chapter_number : null
              const characterCount = typeof item.data?.character_count === "number" ? item.data.character_count : null
              const relationshipCount = typeof item.data?.relationship_count === "number" ? item.data.relationship_count : null
              const plotThreadCount = typeof item.data?.plot_thread_count === "number" ? item.data.plot_thread_count : null
              const continuityIssueCount = typeof item.data?.continuity_issue_count === "number" ? item.data.continuity_issue_count : null
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
                          {characterCount !== null ? <span className={`rounded-full px-3 py-1 text-[11px] font-semibold ${isDark ? "bg-white/10 text-slate-200" : "bg-white text-stone-700 border border-stone-200"}`}>{characterCount} characters</span> : null}
                          {relationshipCount !== null ? <span className={`rounded-full px-3 py-1 text-[11px] font-semibold ${isDark ? "bg-white/10 text-slate-200" : "bg-white text-stone-700 border border-stone-200"}`}>{relationshipCount} relationships</span> : null}
                          {plotThreadCount !== null ? <span className={`rounded-full px-3 py-1 text-[11px] font-semibold ${isDark ? "bg-white/10 text-slate-200" : "bg-white text-stone-700 border border-stone-200"}`}>{plotThreadCount} plot threads</span> : null}
                          {continuityIssueCount !== null ? <span className={`rounded-full px-3 py-1 text-[11px] font-semibold ${isDark ? "bg-white/10 text-slate-200" : "bg-white text-stone-700 border border-stone-200"}`}>{continuityIssueCount} continuity issues</span> : null}
                        </div>
                      ) : null}
                      <div className={`mt-3 flex flex-wrap items-center gap-3 text-xs ${isDark ? "text-slate-500" : "text-stone-400"}`}>
                        <span>{new Date(item.created_at).toLocaleString()}</span>
                        {chapterNumber ? <span>Chapter {chapterNumber}</span> : null}
                      </div>
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
                  {item.book_id ? (
                    <div className="mt-4">
                      <Link
                        href={chapterNumber ? `/${item.book_id}/chapter/${chapterNumber}` : `/${item.book_id}`}
                        className={`text-sm font-medium transition ${isDark ? "text-indigo-300 hover:text-indigo-200" : "text-violet-700 hover:text-violet-800"}`}
                      >
                        Open in LoreVia →
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
