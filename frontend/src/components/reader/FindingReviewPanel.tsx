"use client"

import type { RevisionActionItem } from "@/types/book"

type Props = {
  findings: RevisionActionItem[]
  selectedId: string | null
  savingId?: string | null
  isDark?: boolean
  onOpen: (finding: RevisionActionItem) => void
  onDecision: (finding: RevisionActionItem, decision: "accepted" | "dismissed") => void
  onOpenChapter?: (finding: RevisionActionItem) => void
}

export function FindingReviewPanel({ findings, selectedId, savingId = null, isDark = false, onOpen, onDecision, onOpenChapter }: Props) {
  return (
    <div className="space-y-4" aria-label="Ranked manuscript findings">
      {findings.map((finding, index) => {
        const expanded = selectedId === finding.id
        return (
          <article key={finding.id} className={`rounded-md border ${isDark ? "border-white/10 bg-white/[0.03]" : "border-stone-200 bg-stone-50"}`}>
            <button type="button" onClick={() => onOpen(finding)} aria-expanded={expanded} className="flex w-full items-start justify-between gap-4 p-5 text-left">
              <span>
                <span className="text-xs font-semibold uppercase tracking-[0.18em] text-teal-500">Priority {index + 1} · {finding.severity}</span>
                <span className="mt-2 block text-lg font-semibold">{finding.title}</span>
                <span className={`mt-2 block text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>
                  {finding.chapter_ref ? `Chapter ${finding.chapter_ref} · ` : ""}{finding.evidence_strength ?? "limited"} evidence{finding.is_stale ? " · stale after an edit" : ""}
                </span>
              </span>
              <span aria-hidden="true" className="text-xl">{expanded ? "−" : "+"}</span>
            </button>
            {expanded ? (
              <div className={`border-t p-5 ${isDark ? "border-white/10" : "border-stone-200"}`}>
                <h2 className="text-sm font-semibold">Why this was flagged</h2>
                <p className={`mt-2 text-sm leading-7 ${isDark ? "text-slate-300" : "text-stone-600"}`}>{finding.why_flagged ?? finding.description}</p>
                {finding.evidence?.length ? finding.evidence.map((evidence) => (
                  <blockquote key={`${evidence.chapter_ref}-${evidence.source_content_version}`} className={`mt-4 border-l-2 pl-4 text-sm leading-7 ${isDark ? "border-teal-400 text-slate-300" : "border-teal-600 text-stone-700"}`}>
                    “{evidence.excerpt}”
                    <footer className={`mt-2 text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>Chapter {evidence.chapter_ref}{evidence.source_label ? ` · ${evidence.source_label}` : ""}</footer>
                  </blockquote>
                )) : <p className="mt-4 text-sm text-amber-600">No exact manuscript excerpt is available for this finding.</p>}
                {finding.recommendation ? <p className={`mt-4 text-sm leading-7 ${isDark ? "text-sky-300" : "text-sky-700"}`}>{finding.recommendation}</p> : null}
                <div className="mt-5 flex flex-wrap gap-3">
                  <button disabled={savingId === finding.id} type="button" onClick={() => onDecision(finding, "accepted")} className="rounded-md bg-teal-700 px-4 py-2.5 text-sm font-semibold text-white hover:bg-teal-600 disabled:opacity-50">Add to revision plan</button>
                  <button disabled={savingId === finding.id} type="button" onClick={() => onDecision(finding, "dismissed")} className={`rounded-md border px-4 py-2.5 text-sm font-semibold disabled:opacity-50 ${isDark ? "border-white/15 hover:bg-white/5" : "border-stone-300 hover:bg-white"}`}>Not an issue</button>
                  {finding.chapter_ref && onOpenChapter ? <button type="button" onClick={() => onOpenChapter(finding)} className="px-2 py-2.5 text-sm font-semibold text-sky-600">Open chapter</button> : null}
                </div>
              </div>
            ) : null}
          </article>
        )
      })}
    </div>
  )
}
