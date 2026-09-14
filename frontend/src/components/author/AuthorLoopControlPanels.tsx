"use client"

import Link from "next/link"
import { useMemo, useState } from "react"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { ArrowRight, BookmarkPlus, GitCompareArrows, Sparkles, Users } from "lucide-react"

import { booksApi } from "@/lib/api/books"
import { asQueryKey, bookCacheKey } from "@/lib/query/cacheKeys"
import { useUiPreferencesStore } from "@/lib/stores/uiPreferencesStore"
import { resolveNextBestActions, type NextBestActionCandidate } from "@/lib/workspace/nextBestActionResolver"
import type { BetaReadConsensus } from "@/types/betaRead"

function panelClasses(isDark: boolean) {
  return `rounded-md border p-5 ${isDark ? "border-white/[0.065] bg-[#0d141c]" : "border-slate-200/70 bg-white"}`
}

export function ProjectNextActionPanel({ actions, isDark }: { actions: NextBestActionCandidate[]; isDark: boolean }) {
  const stored = useUiPreferencesStore((state) => state.preferences.recommendation_snoozes)
  const snooze = useUiPreferencesStore((state) => state.snoozeRecommendation)
  const visible = useMemo(() => resolveNextBestActions(actions, stored), [actions, stored])
  const primary = visible[0]
  if (!primary) return null
  return (
    <section className={`rounded-md border p-5 ${isDark ? "border-violet-400/20 bg-violet-400/[0.08]" : "border-violet-200 bg-violet-50"}`} aria-label="Recommended next action">
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div><p className={`text-3xs font-semibold uppercase tracking-[0.22em] ${isDark ? "text-violet-300" : "text-violet-700"}`}>Recommended next action</p><h2 className="mt-2 text-lg font-semibold">{primary.label}</h2>{primary.description ? <p className={`mt-1 text-sm ${isDark ? "text-slate-300" : "text-slate-600"}`}>{primary.description}</p> : null}</div>
        <div className="flex shrink-0 gap-2"><button type="button" onClick={() => void snooze(primary.id, primary.fingerprint, 24)} className={`rounded-md px-3 py-2 text-xs font-semibold ${isDark ? "bg-white/10 text-slate-200" : "bg-white text-slate-600"}`}>Tomorrow</button>{primary.href ? <Link href={primary.href} className="inline-flex items-center gap-2 rounded-md bg-violet-700 px-4 py-2 text-sm font-semibold text-white">Open <ArrowRight className="h-4 w-4" /></Link> : null}</div>
      </div>
      {visible.length > 1 ? <div className={`mt-4 border-t pt-3 text-xs ${isDark ? "border-white/10 text-slate-400" : "border-violet-200 text-slate-600"}`}>Also next: {visible.slice(1, 3).map((item) => item.label).join(" · ")}</div> : null}
    </section>
  )
}

export function BetaConsensusPanel({ consensus, isDark }: { consensus: BetaReadConsensus | null; isDark: boolean }) {
  if (!consensus) return null
  const summary = consensus.summary
  return (
    <section id="beta-consensus" className={panelClasses(isDark)}>
      <div className="flex flex-wrap items-start justify-between gap-3"><div><p className={`text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-slate-400"}`}>Reader consensus map</p><h2 className="mt-2 text-lg font-semibold">See patterns, not a pile of comments</h2></div><div className="flex gap-2 text-xs"><span className="rounded-full bg-violet-500/10 px-3 py-1.5"><Users className="mr-1 inline h-3 w-3" />{summary.reader_count} readers</span><span className="rounded-full bg-amber-500/10 px-3 py-1.5">{summary.open_feedback_count} open</span></div></div>
      {consensus.chapter_hotspots.length ? <div className="mt-5 grid gap-3 lg:grid-cols-3">{consensus.chapter_hotspots.slice(0, 6).map((hotspot) => <article key={hotspot.chapter_number} className={`rounded-md border p-4 ${isDark ? "border-white/[0.06] bg-[#101720]" : "border-slate-200 bg-slate-50"}`}><div className="flex items-center justify-between"><strong className="text-sm">Chapter {hotspot.chapter_number}</strong><span className="text-xs">signal {hotspot.signal_score}</span></div><p className={`mt-2 text-xs ${isDark ? "text-slate-400" : "text-slate-600"}`}>{hotspot.confusing_count} confusing · {hotspot.boring_count} slow · {hotspot.favorite_count} favorite</p>{hotspot.disagreement ? <p className="mt-2 text-xs font-semibold text-amber-600">Reader disagreement — inspect before revising</p> : null}{hotspot.evidence[0] ? <p className={`mt-3 line-clamp-3 text-sm ${isDark ? "text-slate-300" : "text-slate-700"}`}>“{hotspot.evidence[0]}”</p> : null}</article>)}</div> : <p className={`mt-4 text-sm ${isDark ? "text-slate-400" : "text-slate-600"}`}>Signals will group here as readers leave chapter notes and reactions.</p>}
      {consensus.themes.length ? <div className="mt-4 flex flex-wrap gap-2">{consensus.themes.slice(0, 8).map((theme) => <span key={theme.label} className={`rounded-full px-3 py-1.5 text-xs ${isDark ? "bg-white/[0.07] text-slate-300" : "bg-slate-100 text-slate-700"}`}>{theme.label} · {theme.reader_count}</span>)}</div> : null}
    </section>
  )
}

export function RevisionMilestonesPanel({ bookId, isDark }: { bookId: string; isDark: boolean }) {
  const queryClient = useQueryClient()
  const key = asQueryKey(bookCacheKey(bookId, "revision-rounds"))
  const { data: roundsData } = useQuery({ queryKey: key, queryFn: () => booksApi.listRevisionRounds(bookId) })
  const rounds = roundsData ?? []
  const [label, setLabel] = useState("")
  const [busy, setBusy] = useState(false)
  const [comparison, setComparison] = useState<string | null>(null)
  const create = async () => {
    if (!label.trim()) return
    setBusy(true)
    try { await booksApi.createRevisionRound(bookId, { label: label.trim() }); setLabel(""); await queryClient.invalidateQueries({ queryKey: key }) } finally { setBusy(false) }
  }
  const compare = async (roundId: string) => {
    setBusy(true)
    try { const result = await booksApi.compareRevisionRound(bookId, roundId); setComparison(`${result.changed_chapters.length} changed, ${result.added_chapters.length} added · ${result.word_count_delta >= 0 ? "+" : ""}${result.word_count_delta.toLocaleString()} words`) } finally { setBusy(false) }
  }
  return (
    <section className={panelClasses(isDark)}>
      <div className="flex items-start gap-3"><BookmarkPlus className="mt-1 h-5 w-5 text-violet-500" /><div><p className={`text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-slate-400"}`}>Whole-draft milestones</p><h2 className="mt-1 text-lg font-semibold">Capture the manuscript before a revision pass</h2><p className={`mt-1 text-sm ${isDark ? "text-slate-400" : "text-slate-600"}`}>Each round snapshots every chapter and its review-health summary, then compares safely with the live draft.</p></div></div>
      <div className="mt-4 flex gap-2"><input aria-label="Revision round label" value={label} onChange={(event) => setLabel(event.target.value)} placeholder={`Round ${rounds.length + 1}: structural pass`} className={`min-w-0 flex-1 rounded-md border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-[#101720]" : "border-slate-200 bg-white"}`} /><button type="button" disabled={busy || !label.trim()} onClick={() => void create()} className="rounded-md bg-slate-950 px-4 py-2 text-sm font-semibold text-white disabled:opacity-40">Capture round</button></div>
      {comparison ? <p className="mt-3 text-sm text-violet-500"><GitCompareArrows className="mr-1 inline h-4 w-4" />{comparison}</p> : null}
      <div className="mt-4 space-y-2">{rounds.slice().reverse().slice(0, 5).map((round) => <div key={round.id} className={`flex items-center justify-between gap-3 rounded-md border p-3 ${isDark ? "border-white/[0.06]" : "border-slate-200"}`}><div><p className="text-sm font-semibold">{round.label}</p><p className={`text-xs ${isDark ? "text-slate-500" : "text-slate-500"}`}>{new Date(round.created_at).toLocaleString()} · {round.summary.word_count.toLocaleString()} words · {round.summary.open_finding_count} open findings</p></div><button type="button" disabled={busy} onClick={() => void compare(round.id)} className={`rounded-md px-3 py-2 text-xs font-semibold ${isDark ? "bg-white/10" : "bg-slate-100"}`}>Compare now</button></div>)}</div>
      {!rounds.length ? <p className={`mt-4 text-sm ${isDark ? "text-slate-500" : "text-slate-500"}`}><Sparkles className="mr-1 inline h-4 w-4" />No rounds captured yet.</p> : null}
    </section>
  )
}
