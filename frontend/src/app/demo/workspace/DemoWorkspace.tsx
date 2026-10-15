"use client"

import Link from "next/link"
import Image from "next/image"
import { useEffect, useState } from "react"

import { FindingReviewPanel } from "@/components/reader/FindingReviewPanel"
import { capture } from "@/lib/analytics/posthog"
import type { RevisionActionItem } from "@/types/book"

const fixture: RevisionActionItem[] = [
  {
    id: "dracula-arrival-date", title: "Jonathan's arrival timing conflicts with the journal sequence",
    description: "The dated entries imply two different travel durations between Bistritz and the castle.",
    why_flagged: "The May 4 entry places Jonathan in Bistritz, while the next dated account compresses a journey described as lasting through the night.",
    recommendation: "Clarify whether the castle entry begins after midnight or adjust the displayed journal date.",
    category: "timeline", severity: "high", status: "pending", chapter_ref: 1, evidence_strength: "strong", is_stale: false,
    evidence: [
      { chapter_ref: 1, excerpt: "3 May. Bistritz.—Left Munich at 8:35 P. M.", source_label: "Jonathan Harker's Journal", source_content_version: 1 },
      { chapter_ref: 2, excerpt: "5 May. The Castle.—The grey of the morning has passed", source_label: "Jonathan Harker's Journal", source_content_version: 1 },
    ],
  },
  {
    id: "dracula-door-access", title: "The locked-door rule needs a clearer exception",
    description: "Jonathan describes every exit as locked, but Dracula later appears through an unexplained route.",
    why_flagged: "The manuscript establishes the doors as a hard confinement rule, then shows movement without identifying a separate passage.",
    recommendation: "Seed the concealed route earlier or make Jonathan explicitly uncertain that he checked every door.",
    category: "continuity", severity: "medium", status: "pending", chapter_ref: 3, evidence_strength: "moderate", is_stale: false,
    evidence: [{ chapter_ref: 2, excerpt: "The castle is a veritable prison, and I am a prisoner!", source_label: "Castle context", source_content_version: 1 }],
  },
  {
    id: "dracula-letter-knowledge", title: "Mina's knowledge precedes the letter that supplies it",
    description: "A planning note assumes information from a letter not yet received in the simulated chapter order.",
    why_flagged: "The knowledge graph has no earlier source connecting Mina to the castle details.",
    recommendation: "Move the letter delivery earlier or rewrite the planning note as suspicion rather than confirmed knowledge.",
    category: "knowledge", severity: "medium", status: "pending", chapter_ref: 5, evidence_strength: "strong", is_stale: false,
    evidence: [{ chapter_ref: 5, excerpt: "I want to keep up with Jonathan's studies", source_label: "Mina Murray's Journal", source_content_version: 1 }],
  },
]

export function DemoWorkspace() {
  const [findings, setFindings] = useState(fixture)
  const [selectedId, setSelectedId] = useState<string | null>(fixture[0].id)
  const [revisionPlan, setRevisionPlan] = useState<RevisionActionItem[]>([])
  const [chapter, setChapter] = useState<number | null>(null)
  useEffect(() => capture("demo_workspace_viewed", { fixture: "dracula", finding_count: fixture.length }), [])
  const progress = fixture.length - findings.length
  const decide = (finding: RevisionActionItem, decision: "accepted" | "dismissed") => {
    if (decision === "accepted") setRevisionPlan((current) => [...current, finding])
    const remaining = findings.filter((item) => item.id !== finding.id)
    setFindings(remaining)
    setSelectedId(remaining[0]?.id ?? null)
    capture("demo_finding_decided", { fixture: "dracula", decision, category: finding.category })
  }
  const reset = () => {
    setFindings(fixture); setRevisionPlan([]); setSelectedId(fixture[0].id); setChapter(null)
    capture("demo_workspace_reset", { fixture: "dracula" })
  }
  return (
    <main className="min-h-screen overflow-x-hidden bg-[#08110f] px-4 py-5 text-[#f4f1ea] sm:px-6 lg:px-10">
      <div className="mx-auto max-w-7xl">
        <header className="flex flex-wrap items-center justify-between gap-4 border-b border-white/10 pb-5">
          <Link href="/" aria-label="LoreVia home">
            <Image src="/logoandtext.png" alt="LoreVia" width={640} height={160} className="h-9 w-auto" priority />
          </Link>
          <div className="flex flex-wrap gap-3">
            <button type="button" onClick={reset} className="rounded-md border border-white/15 px-4 py-2 text-sm font-semibold transition hover:bg-white/[0.05]">
              Reset demo
            </button>
            <Link href="/register" className="rounded-md bg-[#d6a84f] px-4 py-2 text-sm font-semibold text-[#15120b] transition hover:bg-[#e1b65f]">
              Analyze your manuscript
            </Link>
          </div>
        </header>
        <section className="border-b border-white/10 py-8 md:py-10">
          <p className="text-sm font-semibold text-[#79c8b8]">Interactive sample · Dracula</p>
          <h1 className="mt-3 max-w-3xl text-3xl font-semibold tracking-[-0.03em] sm:text-5xl">Review Dracula continuity findings</h1>
          <p className="mt-4 max-w-3xl text-sm leading-7 text-[#aeb9b3]">
            Inspect the cited passage, then add the finding to a revision plan or dismiss it. This sample runs locally and makes no upload, storage, API, or AI request.
          </p>
        </section>
        <div className="grid min-w-0 lg:grid-cols-[minmax(0,1fr)_19rem]">
          <section data-testid="demo-review-task" className="min-w-0 py-7 lg:pr-8">
            <div className="mb-5 flex items-center justify-between gap-4 border-b border-white/10 pb-4">
              <h2 className="text-lg font-semibold">Findings to review</h2>
              <span className="text-sm text-[#8fa19a]">{progress} of {fixture.length} reviewed</span>
            </div>
            {findings.length ? (
              <FindingReviewPanel
                findings={findings}
                selectedId={selectedId}
                isDark
                onOpen={(finding) => setSelectedId(finding.id)}
                onDecision={decide}
                onOpenChapter={(finding) => setChapter(finding.chapter_ref ?? null)}
              />
            ) : (
              <div className="border-y border-teal-400/20 py-6 text-teal-100" role="status">
                Review complete. Your revision plan is ready.
              </div>
            )}
          </section>
          <aside data-testid="demo-context-rail" className="min-w-0 border-t border-white/10 py-7 lg:border-l lg:border-t-0 lg:pl-8">
            <section>
              <div className="flex items-center justify-between gap-3">
                <h2 className="font-semibold">Review progress</h2>
                <span className="text-sm text-[#8fa19a]">{progress}/{fixture.length} reviewed</span>
              </div>
              <div className="mt-3 h-1.5 overflow-hidden bg-white/10" aria-hidden="true">
                <div className="h-full bg-[#4fb5a3] transition-[width]" style={{ width: `${(progress / fixture.length) * 100}%` }} />
              </div>
            </section>

            {chapter ? (
              <section className="mt-7 border-t border-white/10 pt-6">
                <h2 className="font-semibold">Chapter context</h2>
                <p className="mt-3 text-sm leading-7 text-[#c3cdc8]">
                  Chapter {chapter} is open in this simulated context. Evidence remains attached to its source version.
                </p>
              </section>
            ) : null}

            {revisionPlan.length ? (
              <section className="mt-7 border-t border-white/10 pt-6" aria-live="polite">
                <h2 className="font-semibold">Revision plan</h2>
                <ol className="mt-4 divide-y divide-white/[0.08] text-sm leading-6 text-[#c3cdc8]">
                  {revisionPlan.map((finding) => (
                    <li key={finding.id} className="py-3 first:pt-0 last:pb-0">{finding.title}</li>
                  ))}
                </ol>
              </section>
            ) : (
              <section className="mt-7 border-t border-white/10 pt-6">
                <h2 className="font-semibold">How to review</h2>
                <ol className="mt-4 space-y-3 text-sm leading-6 text-[#8fa19a]">
                  <li>1. Open the highest-ranked finding.</li>
                  <li>2. Compare the explanation with its cited passage.</li>
                  <li>3. Add useful work to the plan or dismiss it.</li>
                </ol>
              </section>
            )}
          </aside>
        </div>
      </div>
    </main>
  )
}
