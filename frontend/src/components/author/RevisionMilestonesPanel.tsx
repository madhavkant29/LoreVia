"use client"

import { useRef, useState } from "react"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { booksApi } from "@/lib/api/books"
import { asQueryKey, bookCacheKey } from "@/lib/query/cacheKeys"
import { getApiErrorDetail } from "@/lib/utils/apiErrors"
import type { RevisionRound, RevisionRoundComparison } from "@/types/book"

export type RevisionComparisonView = { label: string; result: RevisionRoundComparison }

export function RevisionMilestonesPanel({ bookId, label, onLabelChange, busy, onBusyChange, comparison, onComparisonChange }: {
  bookId: string; label: string; onLabelChange: (value: string) => void; busy: boolean; onBusyChange: (value: boolean) => void
  comparison: RevisionComparisonView | null; onComparisonChange: (value: RevisionComparisonView) => void
}) {
  const client = useQueryClient()
  const key = asQueryKey(bookCacheKey(bookId, "revision-rounds"))
  const query = useQuery({ queryKey: key, queryFn: () => booksApi.listRevisionRounds(bookId), retry: false, refetchOnWindowFocus: false })
  const rounds = query.data ?? []
  const lock = useRef(false)
  const [message, setMessage] = useState<string | null>(null)
  const [showAll, setShowAll] = useState(false)

  async function create() {
    if (lock.current || busy || !label.trim()) return
    if (label.trim().length > 120) { setMessage("Use a snapshot label of 120 characters or fewer."); return }
    lock.current = true; onBusyChange(true); setMessage(null)
    try {
      const saved = await booksApi.createRevisionRound(bookId, { label: label.trim() })
      client.setQueryData<RevisionRound[]>(key, (current = []) => [...current.filter((round) => round.id !== saved.id), saved])
      onLabelChange(""); setMessage(`Captured ${saved.label}.`)
    } catch (error) { setMessage(`${getApiErrorDetail(error) ?? "Could not confirm snapshot capture."} Your label is retained. Refresh snapshots before trying again to avoid a duplicate.`) }
    finally { lock.current = false; onBusyChange(false) }
  }

  async function compare(round: RevisionRound) {
    if (lock.current || busy) return
    lock.current = true; onBusyChange(true); setMessage(null)
    try { onComparisonChange({ label: round.label, result: await booksApi.compareRevisionRound(bookId, round.id) }) }
    catch (error) { setMessage(`${getApiErrorDetail(error) ?? "Could not compare that snapshot."} The previous comparison is retained. Try again.`) }
    finally { lock.current = false; onBusyChange(false) }
  }

  return <section className="border-y border-[rgb(var(--border))] py-6" aria-label="Revision snapshots">
    <h2 className="text-lg font-semibold">Revision snapshots</h2>
    <p className="mt-1 text-sm text-[rgb(var(--muted-foreground))]">Capture the current manuscript before a substantial pass, then compare it with the live draft.</p>
    {message ? <p className="mt-3 text-sm" role="status">{message}</p> : null}
    {query.isError ? <p className="mt-3 text-sm" role="alert">Snapshots could not be loaded or refreshed. Last loaded snapshots remain available.</p> : null}
    <button type="button" className="app-button-secondary mt-3" disabled={busy || query.isFetching} onClick={() => void query.refetch()}>Refresh snapshots</button>
    <div className="mt-4 flex flex-wrap gap-2">
      <label className="min-w-0 flex-1 text-sm">Revision round label<input aria-label="Revision round label" maxLength={120} value={label} disabled={busy} onChange={(event) => onLabelChange(event.target.value)} placeholder={`Round ${rounds.length + 1}: structural pass`} className="mt-2 block min-h-11 w-full border border-[rgb(var(--border))] bg-[rgb(var(--background))] px-3 text-sm" /></label>
      <button type="button" disabled={busy || !label.trim() || query.isLoading || query.isError} onClick={() => void create()} className="app-button-primary self-end">Capture round</button>
    </div>
    {comparison ? <div className="mt-5 border-l-2 border-[rgb(var(--accent))] pl-3 text-sm" role="status">
      <h3 className="font-semibold">Compared with {comparison.label}</h3>
      <p className="mt-1">{comparison.result.word_count_delta >= 0 ? "+" : ""}{comparison.result.word_count_delta.toLocaleString()} words · {comparison.result.scene_count_delta >= 0 ? "+" : ""}{comparison.result.scene_count_delta} scenes</p>
      <p>Changed chapters: {comparison.result.changed_chapters.join(", ") || "None"}</p>
      <p>Added chapters: {comparison.result.added_chapters.join(", ") || "None"}</p>
      <p>Removed chapters: {comparison.result.removed_chapters.join(", ") || "None"}</p>
      <p>Open findings: {comparison.result.open_finding_delta >= 0 ? "+" : ""}{comparison.result.open_finding_delta} · Open reader feedback: {comparison.result.open_beta_feedback_delta >= 0 ? "+" : ""}{comparison.result.open_beta_feedback_delta}</p>
      <p className="mt-2 text-[rgb(var(--muted-foreground))]">This comparison reflects the manuscript when requested. Compare again after editing.</p>
    </div> : null}
    {query.isLoading ? <p className="mt-4" role="status">Loading snapshots…</p> : null}
    <div className="mt-4 divide-y divide-[rgb(var(--border))]">{rounds.slice().reverse().slice(0, showAll ? rounds.length : 5).map((round) => <div key={round.id} className="flex flex-wrap items-center justify-between gap-3 py-4">
      <div className="min-w-0"><h3 className="text-sm font-semibold">{round.label}</h3><p className="text-sm text-[rgb(var(--muted-foreground))]">{new Date(round.created_at).toLocaleString()} · {round.summary.word_count.toLocaleString()} words · {round.summary.open_finding_count} open findings</p></div>
      <button type="button" disabled={busy} aria-label={`Compare snapshot: ${round.label}`} onClick={() => void compare(round)} className="app-button-secondary">Compare now</button>
    </div>)}</div>
    {rounds.length > 5 ? <button type="button" className="app-button-secondary" onClick={() => setShowAll(!showAll)}>{showAll ? "Show fewer snapshots" : `Show all ${rounds.length} snapshots`}</button> : null}
    {!query.isLoading && !query.isError && !rounds.length ? <p className="mt-4 text-sm">No snapshots captured yet.</p> : null}
  </section>
}
