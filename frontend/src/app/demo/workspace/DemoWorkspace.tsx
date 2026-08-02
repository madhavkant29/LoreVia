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
    <main className="min-h-screen overflow-x-hidden bg-[#08110f] px-4 py-6 text-[#f4f1ea] sm:px-6 lg:px-10">
      <div className="mx-auto max-w-7xl">
        <header className="flex flex-wrap items-center justify-between gap-4 border-b border-white/10 pb-5">
          <Link href="/" aria-label="LoreVia home"><Image src="/logoandtext.png" alt="LoreVia" width={150} height={42} priority /></Link>
          <div className="flex gap-3"><button type="button" onClick={reset} className="rounded-md border border-white/15 px-4 py-2 text-sm font-semibold">Reset demo</button><Link href="/register" className="rounded-md bg-[#d6a84f] px-4 py-2 text-sm font-semibold text-[#15120b]">Analyze your manuscript</Link></div>
        </header>
        <section className="py-8">
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-[#6fae9f]">Interactive workspace · local fixture</p>
          <h1 className="mt-3 max-w-3xl text-3xl font-semibold sm:text-5xl">Review Dracula continuity findings</h1>
          <p className="mt-4 max-w-3xl text-sm leading-7 text-[#aeb9b3]">No login, upload, storage, API, or AI call is used. Accept or dismiss evidence-backed findings and watch the revision plan update.</p>
        </section>
        <div className="grid min-w-0 gap-6 lg:grid-cols-[minmax(0,1.65fr)_minmax(18rem,0.75fr)]">
          <section className="min-w-0 rounded-lg border border-white/10 bg-[#0b1220] p-4 sm:p-6">
            <div className="mb-5 flex items-center justify-between gap-4"><h2 className="text-lg font-semibold">Ranked findings</h2><span className="text-sm text-slate-400">{progress}/{fixture.length} reviewed</span></div>
            {findings.length ? <FindingReviewPanel findings={findings} selectedId={selectedId} isDark onOpen={(finding) => setSelectedId(finding.id)} onDecision={decide} onOpenChapter={(finding) => setChapter(finding.chapter_ref ?? null)} /> : <div className="rounded-md border border-teal-400/20 bg-teal-500/10 p-6" role="status">Review complete. Your revision plan is ready.</div>}
          </section>
          <aside className="min-w-0 space-y-5">
            <section className="rounded-lg border border-white/10 bg-white/[0.04] p-5"><h2 className="font-semibold">Chapter context</h2><p className="mt-3 text-sm leading-7 text-slate-300">{chapter ? `Chapter ${chapter} is open in this simulated context. Evidence remains attached to its source version.` : "Open a chapter from any expanded finding to inspect its simulated context."}</p></section>
            <section className="rounded-lg border border-white/10 bg-white/[0.04] p-5" aria-live="polite"><h2 className="font-semibold">Revision plan</h2>{revisionPlan.length ? <ol className="mt-4 space-y-3 text-sm text-slate-300">{revisionPlan.map((finding) => <li key={finding.id}>{finding.title}</li>)}</ol> : <p className="mt-3 text-sm text-slate-400">Accepted findings appear here.</p>}</section>
          </aside>
        </div>
      </div>
    </main>
  )
}
