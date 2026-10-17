"use client"

import Link from "next/link"
import { useMemo } from "react"
import { ArrowRight, Users } from "lucide-react"

import { useUiPreferencesStore } from "@/lib/stores/uiPreferencesStore"
import { resolveNextBestActions, type NextBestActionCandidate } from "@/lib/workspace/nextBestActionResolver"
import type { BetaReadConsensus } from "@/types/betaRead"

function panelClasses(isDark: boolean) {
  return `border-y py-6 sm:rounded-md sm:border sm:p-6 ${isDark ? "border-white/10 sm:bg-[#0d141c]" : "border-stone-200 sm:bg-white"}`
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
