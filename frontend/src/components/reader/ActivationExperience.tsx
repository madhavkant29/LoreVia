"use client"

import { useEffect, useRef, useState } from "react"

import { FindingReviewPanel } from "@/components/reader/FindingReviewPanel"
import { capture } from "@/lib/analytics/posthog"
import { booksApi } from "@/lib/api/books"
import type { RevisionActionItem, RevisionIntelligence } from "@/types/book"

type Props = {
  bookId: string
  bookTitle: string
  chapterCount: number
  isDark: boolean
  revision: RevisionIntelligence
  onRevisionChange: (revision: RevisionIntelligence) => void
  onNavigate: (href: string) => void
}

export function ActivationExperience({
  bookId,
  bookTitle,
  chapterCount,
  isDark,
  revision,
  onRevisionChange,
  onNavigate,
}: Props) {
  const findings = revision.priority_findings ?? []
  const [selectedId, setSelectedId] = useState<string | null>(findings[0]?.id ?? null)
  const [savingId, setSavingId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const viewedRef = useRef(false)

  useEffect(() => {
    if (viewedRef.current) return
    viewedRef.current = true
    capture("activation_experience_viewed", {
      book_id: bookId,
      chapter_count: chapterCount,
      finding_count: findings.length,
      analysis_complete: revision.analysis_complete,
    })
  }, [bookId, chapterCount, findings.length, revision.analysis_complete])

  const openFinding = (finding: RevisionActionItem) => {
    setSelectedId(finding.id)
    capture("finding_opened", {
      book_id: bookId,
      finding_id: finding.id,
      category: finding.category,
      severity: finding.severity,
      evidence_strength: finding.evidence_strength ?? "limited",
      is_stale: finding.is_stale,
    })
  }

  const decide = async (finding: RevisionActionItem, decision: "accepted" | "dismissed") => {
    setSavingId(finding.id)
    setError(null)
    try {
      const next = await booksApi.decideRevisionFinding(bookId, finding.id, decision === "accepted"
        ? { decision, action: "added_to_revision_plan" }
        : { decision, reason: "not_relevant" })
      capture(decision === "accepted" ? "finding_accepted" : "finding_dismissed", {
        book_id: bookId,
        finding_id: finding.id,
        category: finding.category,
        severity: finding.severity,
        evidence_strength: finding.evidence_strength ?? "limited",
      })
      if (decision === "accepted") {
        capture("activation_completed", {
          book_id: bookId,
          finding_id: finding.id,
          action: "added_to_revision_plan",
        })
      }
      onRevisionChange(next)
      setSelectedId(next.priority_findings?.[0]?.id ?? null)
    } catch {
      setError("LoreVia could not save this finding decision. Please try again.")
    } finally {
      setSavingId(null)
    }
  }

  const shell = isDark
    ? "border-white/10 bg-[#0b1220] text-slate-100"
    : "border-stone-200 bg-white text-stone-950"

  if (!revision.analysis_complete || findings.length === 0) {
    return (
      <section className={`rounded-lg border p-6 sm:p-8 ${shell}`} data-testid="activation-incomplete">
        <p className="text-xs font-semibold uppercase tracking-[0.22em] text-amber-500">Analysis status</p>
        <h1 className="mt-3 text-3xl font-semibold">Your manuscript is ready, but the evidence pass is incomplete.</h1>
        <p className={`mt-4 max-w-3xl text-sm leading-7 ${isDark ? "text-slate-300" : "text-stone-600"}`}>
          LoreVia will not manufacture continuity findings without enough manuscript evidence. Existing writing and chapter tools remain available while intelligence catches up.
        </p>
        {revision.analysis_limitations?.length ? (
          <ul className={`mt-5 space-y-2 text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>
            {revision.analysis_limitations.map((item) => <li key={item}>• {item}</li>)}
          </ul>
        ) : null}
        <button type="button" onClick={() => onNavigate(`/${bookId}/manuscript`)} className="mt-6 rounded-md bg-teal-700 px-4 py-2.5 text-sm font-semibold text-white hover:bg-teal-600">
          Open manuscript
        </button>
      </section>
    )
  }

  return (
    <section className={`rounded-lg border p-5 sm:p-8 ${shell}`} data-testid="activation-experience">
      <div className="max-w-3xl">
        <p className="text-xs font-semibold uppercase tracking-[0.22em] text-teal-500">Analysis complete</p>
        <h1 className="mt-3 text-3xl font-semibold sm:text-4xl">We analyzed {chapterCount} chapter{chapterCount === 1 ? "" : "s"} in {bookTitle}.</h1>
        <p className={`mt-4 text-base leading-7 ${isDark ? "text-slate-300" : "text-stone-600"}`}>
          Start with the three findings most likely to affect continuity. Every finding shows its evidence and why LoreVia raised it.
        </p>
      </div>

      {error ? <p role="alert" className="mt-5 rounded-md border border-rose-300 bg-rose-50 p-3 text-sm text-rose-700">{error}</p> : null}

      <div className="mt-7">
        <FindingReviewPanel
          findings={findings}
          selectedId={selectedId}
          savingId={savingId}
          isDark={isDark}
          onOpen={openFinding}
          onDecision={(finding, decision) => void decide(finding, decision)}
          onOpenChapter={(finding) => onNavigate(`/${bookId}/manuscript?chapter=${finding.chapter_ref}&finding=${finding.id}`)}
        />
      </div>
    </section>
  )
}
