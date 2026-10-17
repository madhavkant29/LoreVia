"use client"

import type { Route } from "next"
import Link from "next/link"

import type { BetaReaderEvidence, BetaReaderFinding } from "@/types/intelligence"

export function EvidenceLinks({
  bookId,
  findingId,
  evidence,
}: {
  bookId: string
  findingId: string
  evidence: BetaReaderEvidence[]
}) {
  if (!evidence.length) return <p className="mt-3 text-sm text-[rgb(var(--muted-foreground))]">No source excerpts were returned for this finding.</p>
  return (
    <div className="mt-4 divide-y divide-[rgb(var(--border))] border-y border-[rgb(var(--border))]">
      {evidence.map((item, index) => (
        <div
          key={`${item.chapter_number}-${index}`}
          className="py-3 text-sm"
        >
          <p className="leading-6">“{item.excerpt}”</p>
          {item.chapter_number !== null && Number.isInteger(item.chapter_number) && item.chapter_number > 0 ? (
            <Link
              href={`/${bookId}/manuscript?chapter=${item.chapter_number}&ai_beta_finding=${encodeURIComponent(findingId)}` as Route}
              className="mt-2 inline-block min-h-10 py-2 text-sm font-semibold text-[rgb(var(--accent))]"
            >
              Open chapter {item.chapter_number}
            </Link>
          ) : null}
        </div>
      ))}
    </div>
  )
}

export function FindingCard({
  bookId,
  finding,
  onSave,
  saving = false,
}: {
  bookId: string
  finding: BetaReaderFinding
  onSave: () => void
  saving?: boolean
  }) {
  return (
    <article className="border-t border-[rgb(var(--border))] py-5 first:border-t-0 first:pt-0">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-medium text-[rgb(var(--muted-foreground))]">
            {finding.severity} · {finding.category.replaceAll("_", " ")}
          </p>
          <h3 className="mt-1 text-lg font-semibold">{finding.title}</h3>
        </div>
        <button type="button" onClick={onSave} disabled={saving} className="min-h-10 text-sm font-semibold text-[rgb(var(--accent))] underline underline-offset-4 hover:underline">
          Save finding
        </button>
      </div>
      <p className="app-copy mt-3">{finding.description}</p>
      <p className="mt-3 text-sm">
        <strong>Revision direction:</strong> {finding.recommendation}
      </p>
      {finding.reader_question ? (
        <p className="mt-2 text-sm">
          <strong>Reader question:</strong> {finding.reader_question}
        </p>
      ) : null}
      <EvidenceLinks bookId={bookId} findingId={finding.id} evidence={finding.evidence} />
    </article>
  )
}
