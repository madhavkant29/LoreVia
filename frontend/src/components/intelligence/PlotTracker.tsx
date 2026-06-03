"use client"

import Link from "next/link"
import { useQuery } from "@tanstack/react-query"
import { memo, useEffect, useMemo, useState } from "react"

import { booksApi } from "@/lib/api/books"
import { readerApi } from "@/lib/api/reader"
import { asQueryKey, readerCacheKey } from "@/lib/query/cacheKeys"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import { saveContextualVaultNote } from "@/lib/utils/notes"
import type { PlotThread } from "@/types/reader"

interface Props {
  bookId: string
  chapter?: number
  mode?: "compact" | "dashboard"
}

const STATUS_LABELS: Record<string, string> = {
  introduced: "Introduced",
  developing: "Developing",
  ongoing: "Developing",
  paused: "Paused",
  resolved: "Resolved",
  contradicted: "Contradicted",
  forgotten: "Forgotten",
  possibly_abandoned: "Possibly abandoned",
  abandoned: "Abandoned",
  unknown: "Unknown",
}

const STATUS_ORDER = ["developing", "introduced", "paused", "possibly_abandoned", "forgotten", "contradicted", "resolved", "abandoned", "unknown"] as const
const STATUS_OPTIONS = ["introduced", "developing", "paused", "resolved", "contradicted", "forgotten", "possibly_abandoned", "abandoned", "unknown"] as const

function statusClasses(status: string, isDark: boolean) {
  const palette: Record<string, string> = {
    introduced: isDark ? "border-cyan-400/20 bg-cyan-400/10 text-cyan-200" : "border-cyan-200 bg-cyan-50 text-cyan-800",
    developing: isDark ? "border-emerald-400/20 bg-emerald-400/10 text-emerald-200" : "border-emerald-200 bg-emerald-50 text-emerald-800",
    ongoing: isDark ? "border-emerald-400/20 bg-emerald-400/10 text-emerald-200" : "border-emerald-200 bg-emerald-50 text-emerald-800",
    paused: isDark ? "border-amber-400/20 bg-amber-400/10 text-amber-200" : "border-amber-200 bg-amber-50 text-amber-800",
    resolved: isDark ? "border-stone-300/20 bg-stone-200/10 text-stone-200" : "border-stone-300 bg-stone-100 text-stone-700",
    contradicted: isDark ? "border-fuchsia-400/20 bg-fuchsia-400/10 text-fuchsia-200" : "border-fuchsia-200 bg-fuchsia-50 text-fuchsia-800",
    forgotten: isDark ? "border-orange-400/20 bg-orange-400/10 text-orange-200" : "border-orange-200 bg-orange-50 text-orange-800",
    possibly_abandoned: isDark ? "border-rose-300/20 bg-rose-300/10 text-rose-200" : "border-rose-200 bg-rose-50 text-rose-800",
    abandoned: isDark ? "border-rose-400/20 bg-rose-400/10 text-rose-200" : "border-rose-200 bg-rose-50 text-rose-800",
    unknown: isDark ? "border-slate-400/20 bg-slate-400/10 text-slate-200" : "border-slate-200 bg-slate-100 text-slate-700",
  }
  return palette[status] ?? palette.unknown
}

export const PlotTracker = memo(function PlotTracker({ bookId, chapter, mode = "compact" }: Props) {
  const [savingId, setSavingId] = useState<string | null>(null)
  const [vaultSavingId, setVaultSavingId] = useState<string | null>(null)
  const [draftNotes, setDraftNotes] = useState<Record<string, string>>({})
  const [draftStatuses, setDraftStatuses] = useState<Record<string, string>>({})
  const { theme } = usePreferencesStore()
  const isDark = theme === "dark"

  const {
    data: threads = [],
    isLoading: loading,
    refetch: refetchThreads,
  } = useQuery<PlotThread[]>({
    queryKey: asQueryKey(readerCacheKey(bookId, `plot-threads:${chapter ?? "all"}`)),
    queryFn: () => readerApi.getPlotThreads(bookId, chapter),
  })

  useEffect(() => {
    setDraftNotes(Object.fromEntries(threads.map((item) => [item.id, item.note ?? ""])))
    setDraftStatuses(Object.fromEntries(threads.map((item) => [item.id, item.status ?? "unknown"])))
  }, [threads])

  const grouped = useMemo(() => {
    const initial = Object.fromEntries(STATUS_ORDER.map((status) => [status, [] as PlotThread[]])) as Record<string, PlotThread[]>
    for (const thread of threads) {
      const key = STATUS_ORDER.includes(thread.status as typeof STATUS_ORDER[number]) ? thread.status : "unknown"
      initial[key].push(thread)
    }
    return initial
  }, [threads])

  const saveNote = async (threadId: string) => {
    setSavingId(threadId)
    try {
      await readerApi.updatePlotThread(bookId, threadId, {
        note: draftNotes[threadId]?.trim() ? draftNotes[threadId].trim() : null,
        status: draftStatuses[threadId] ?? null,
      })
      await refetchThreads()
    } finally {
      setSavingId(null)
    }
  }

  const saveToVault = async (thread: PlotThread) => {
    setVaultSavingId(thread.id)
    try {
      const chapterBits = [
        typeof thread.first_mentioned === "number" ? `First mentioned in chapter ${thread.first_mentioned}.` : null,
        typeof thread.last_mentioned === "number" ? `Last mentioned in chapter ${thread.last_mentioned}.` : null,
        typeof thread.resolved_at === "number" ? `Resolved in chapter ${thread.resolved_at}.` : null,
      ].filter(Boolean)
      const bodyParts = [
        thread.description?.trim() || "",
        chapterBits.length ? chapterBits.join("\n") : "",
        thread.risk?.trim() ? `## Risk\n\n${thread.risk.trim()}` : "",
        thread.suggested_action?.trim() ? `## Suggested action\n\n${thread.suggested_action.trim()}` : "",
        draftNotes[thread.id]?.trim() ? `## Private note\n\n${draftNotes[thread.id].trim()}` : "",
      ].filter(Boolean)

      await saveContextualVaultNote({
        bookId,
        title: thread.title,
        content: bodyParts.join("\n\n"),
        context: "plot_threads",
        folderSegments: [thread.type || "Threads"],
      })
    } finally {
      setVaultSavingId(null)
      void booksApi.listObsidianNotes(bookId).catch(() => null)
    }
  }

  if (loading) return <div className={`py-4 text-center text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>Loading plot threads...</div>
  if (threads.length === 0) return <div className={`py-4 text-center text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>No plot threads tracked yet.</div>

  if (mode === "compact") {
    return (
      <div className="space-y-3">
        {threads.slice(0, 6).map((thread) => (
          <div key={thread.id} className={`rounded-md border px-3 py-3 text-sm ${isDark ? "border-white/10 bg-white/[0.03] text-slate-200" : "border-stone-200 bg-stone-50 text-stone-700"}`}>
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="font-semibold">{thread.title}</p>
                <p className={`mt-1 text-xs ${isDark ? "text-slate-400" : "text-stone-500"}`}>
                  First mentioned in chapter {thread.first_mentioned ?? thread.introduced_at ?? "?"}
                  {thread.last_mentioned ? ` • Last mentioned in chapter ${thread.last_mentioned}` : ""}
                  {thread.resolved_at ? ` • Resolved in chapter ${thread.resolved_at}` : ""}
                </p>
              </div>
              <span className={`rounded-full border px-2 py-1 text-3xs font-semibold uppercase tracking-[0.16em] ${statusClasses(thread.status, isDark)}`}>
                {STATUS_LABELS[thread.status] ?? STATUS_LABELS.unknown}
              </span>
            </div>
            {thread.risk ? <p className={`mt-2 text-xs leading-5 ${isDark ? "text-amber-200" : "text-amber-800"}`}>{thread.risk}</p> : null}
          </div>
        ))}
        <Link
          href={`/${bookId}/plot-threads`}
          className={`inline-flex rounded-full border px-4 py-2 text-sm font-medium ${isDark ? "border-white/10 bg-white/5 text-slate-200" : "border-stone-200 bg-white text-stone-700"}`}
        >
          Open full plot thread dashboard
        </Link>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        {STATUS_ORDER.map((status) => (
          <div key={status} className={`rounded-md border px-4 py-4 ${isDark ? "border-white/10 bg-white/[0.04]" : "border-stone-200 bg-white/80"}`}>
            <p className={`text-3xs font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-400" : "text-stone-400"}`}>{STATUS_LABELS[status]}</p>
            <p className={`mt-3 text-3xl font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>{grouped[status].length}</p>
          </div>
        ))}
      </div>

      {STATUS_ORDER.map((status) => {
        const statusThreads = grouped[status]
        if (statusThreads.length === 0) return null
        return (
          <section key={status}>
            <div className="mb-3 flex items-center justify-between gap-3">
              <div>
                <p className={`text-xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-400" : "text-stone-400"}`}>{STATUS_LABELS[status]}</p>
                <p className={`mt-1 text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>{statusThreads.length} thread{statusThreads.length === 1 ? "" : "s"}</p>
              </div>
              <span className={`rounded-full border px-3 py-1 text-3xs font-semibold uppercase tracking-[0.16em] ${statusClasses(status, isDark)}`}>
                {STATUS_LABELS[status]}
              </span>
            </div>
            <div className="space-y-3">
              {statusThreads.map((thread) => (
                <div key={thread.id} className={`rounded-lg border p-4 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-stone-200 bg-white/90"}`}>
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <p className={`text-base font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>{thread.title}</p>
                        {thread.type ? <span className={`rounded-full px-2.5 py-1 text-3xs uppercase tracking-[0.16em] ${isDark ? "bg-white/8 text-slate-300" : "bg-stone-100 text-stone-600"}`}>{thread.type}</span> : null}
                      </div>
                      {thread.description ? <p className={`mt-2 max-w-3xl text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-600"}`}>{thread.description}</p> : null}
                      <p className={`mt-2 text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>
                        First mentioned in chapter {thread.first_mentioned ?? thread.introduced_at ?? "?"}
                        {thread.last_mentioned ? ` • Last mentioned in chapter ${thread.last_mentioned}` : ""}
                        {thread.resolved_at ? ` • Resolved in chapter ${thread.resolved_at}` : ""}
                        {thread.related_characters.length > 0 ? ` • ${thread.related_characters.length} linked characters` : ""}
                        {thread.mention_count > 0 ? ` • ${thread.mention_count} mentions tracked` : ""}
                      </p>
                    </div>
                    <span className={`rounded-full border px-3 py-1 text-3xs font-semibold uppercase tracking-[0.16em] ${statusClasses(thread.status, isDark)}`}>
                      {STATUS_LABELS[thread.status] ?? STATUS_LABELS.unknown}
                    </span>
                  </div>

                  {(thread.related_characters.length > 0 || thread.risk || thread.suggested_action) ? (
                    <div className="mt-4 grid gap-3 lg:grid-cols-3">
                      <div className={`rounded-md border px-3 py-3 text-sm ${isDark ? "border-white/10 bg-black/40 text-slate-300" : "border-stone-200 bg-stone-50 text-stone-700"}`}>
                        <p className={`text-3xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-400" : "text-stone-400"}`}>Related characters</p>
                        <p className="mt-2 leading-6">{thread.related_characters.length ? thread.related_characters.join(", ") : "No linked characters yet."}</p>
                      </div>
                      <div className={`rounded-md border px-3 py-3 text-sm ${isDark ? "border-white/10 bg-black/40 text-slate-300" : "border-stone-200 bg-stone-50 text-stone-700"}`}>
                        <p className={`text-3xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-400" : "text-stone-400"}`}>Risk</p>
                        <p className="mt-2 leading-6">{thread.risk || "No immediate closure risk flagged."}</p>
                      </div>
                      <div className={`rounded-md border px-3 py-3 text-sm ${isDark ? "border-white/10 bg-black/40 text-slate-300" : "border-stone-200 bg-stone-50 text-stone-700"}`}>
                        <p className={`text-3xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-400" : "text-stone-400"}`}>Suggested action</p>
                        <p className="mt-2 leading-6">{thread.suggested_action || "No action suggested yet."}</p>
                      </div>
                    </div>
                  ) : null}

                  <div className="mt-4">
                    <div className="grid gap-3 lg:grid-cols-[220px_minmax(0,1fr)]">
                      <div>
                        <label className={`mb-2 block text-xs font-semibold uppercase tracking-[0.2em] ${isDark ? "text-slate-400" : "text-stone-400"}`}>
                          Lifecycle status
                        </label>
                        <select
                          value={draftStatuses[thread.id] ?? thread.status}
                          onChange={(event) => setDraftStatuses((current) => ({ ...current, [thread.id]: event.target.value }))}
                          className={`w-full rounded-md border px-3 py-3 text-sm outline-none ${isDark ? "border-white/10 bg-black text-slate-100" : "border-stone-200 bg-stone-50 text-stone-900"}`}
                        >
                          {STATUS_OPTIONS.map((value) => (
                            <option key={value} value={value}>
                              {STATUS_LABELS[value]}
                            </option>
                          ))}
                        </select>
                      </div>
                      <div>
                        <label className={`mb-2 block text-xs font-semibold uppercase tracking-[0.2em] ${isDark ? "text-slate-400" : "text-stone-400"}`}>
                          Private note
                        </label>
                        <textarea
                          value={draftNotes[thread.id] ?? ""}
                          onChange={(event) => setDraftNotes((current) => ({ ...current, [thread.id]: event.target.value }))}
                          placeholder="Resolve this in arc 5."
                          rows={3}
                          className={`w-full rounded-md border px-3 py-3 text-sm leading-6 outline-none ${isDark ? "border-white/10 bg-black text-slate-100 placeholder:text-slate-500" : "border-stone-200 bg-stone-50 text-stone-900 placeholder:text-stone-400"}`}
                        />
                      </div>
                    </div>
                    <div className="mt-3 flex items-center justify-between gap-3">
                      <p className={`text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>Only visible inside your LoreVia workspace.</p>
                      <div className="flex items-center gap-2">
                        <button
                          type="button"
                          onClick={() => void saveToVault(thread)}
                          disabled={vaultSavingId === thread.id}
                          className={`rounded-full px-4 py-2 text-sm font-medium ${isDark ? "bg-white/8 text-slate-100" : "bg-stone-100 text-stone-700"} disabled:opacity-50`}
                        >
                          {vaultSavingId === thread.id ? "Sending..." : "Save to vault"}
                        </button>
                        <Link
                          href={`/${bookId}/notes`}
                          className={`rounded-full px-4 py-2 text-sm font-medium ${isDark ? "bg-white/8 text-slate-100" : "bg-white text-stone-700"}`}
                        >
                          Open notes
                        </Link>
                        <button
                          onClick={() => void saveNote(thread.id)}
                          disabled={savingId === thread.id}
                          className="rounded-md bg-[#1f615d] px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
                        >
                          {savingId === thread.id ? "Saving..." : "Save thread"}
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </section>
        )
      })}
    </div>
  )
})
