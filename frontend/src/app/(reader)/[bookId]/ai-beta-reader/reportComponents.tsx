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
  if (!evidence.length) return null
  return (
    <div className="mt-3 space-y-2">
      {evidence.map((item, index) => (
        <div
          key={`${item.chapter_number}-${index}`}
          className="rounded-md border border-[rgb(var(--border))] bg-[rgba(var(--foreground),0.025)] p-3 text-sm"
        >
          <p className="leading-6">“{item.excerpt}”</p>
          {item.chapter_number ? (
            <Link
              href={`/${bookId}/manuscript?chapter=${item.chapter_number}&ai_beta_finding=${encodeURIComponent(findingId)}` as Route}
              className="mt-2 inline-block text-xs font-semibold text-[rgb(var(--accent))]"
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
}: {
  bookId: string
  finding: BetaReaderFinding
  onSave: () => void
}) {
  return (
    <article className="rounded-md border border-[rgb(var(--border))] p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="app-eyebrow">
            {finding.severity} · {finding.category.replaceAll("_", " ")}
          </p>
          <h3 className="mt-2 text-lg font-semibold">{finding.title}</h3>
        </div>
        <button type="button" onClick={onSave} className="app-button-secondary">
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
