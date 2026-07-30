"use client"

import { useEffect, useMemo, useRef, useState, type ReactNode } from "react"

import { capture } from "@/lib/analytics/posthog"
import { booksApi } from "@/lib/api/books"
import type { ContinuityFinding, ContinuityScan, RevisionIntelligence } from "@/types/book"

type Props = {
  bookId: string
  bookCreatedAt?: string | null
  chapterCount: number
  isDark: boolean
  revision: RevisionIntelligence
  onNavigate: (href: string) => void
}

type FindingDecision = "accepted" | "dismissed" | "intentional" | "resolved"

export function ContinuityInbox({
  bookId,
  bookCreatedAt,
  chapterCount,
  isDark,
  revision,
  onNavigate,
}: Props) {
  const [scan, setScan] = useState<ContinuityScan | null>(null)
  const [findings, setFindings] = useState<ContinuityFinding[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [savingId, setSavingId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const cleanViewedRef = useRef(false)
  const usableResultCapturedRef = useRef(false)
  const selected = useMemo(
    () => findings.find((finding) => finding.id === selectedId) ?? findings[0] ?? null,
    [findings, selectedId],
  )

  useEffect(() => {
    let cancelled = false
    async function load() {
      setLoading(true)
      setError(null)
      const captureFirstUsableResult = (
        resultType: "verified_clean" | "continuity_findings",
        currentScan?: ContinuityScan,
      ) => {
        if (usableResultCapturedRef.current) return
        const createdAtMs = bookCreatedAt ? Date.parse(bookCreatedAt) : Number.NaN
        const completedAt = currentScan?.completed_at ?? revision.continuity_completed_at
        const completedAtMs = completedAt ? Date.parse(completedAt) : Number.NaN
        const elapsedToResult = Number.isFinite(createdAtMs) && Number.isFinite(completedAtMs)
          ? completedAtMs - createdAtMs
          : Number.NaN
        const persistedDurationMs = currentScan?.duration_ms ?? revision.continuity_duration_ms
        const latencyMs = Number.isFinite(elapsedToResult) && elapsedToResult >= 0
          ? elapsedToResult
          : typeof persistedDurationMs === "number" && persistedDurationMs >= 0
            ? persistedDurationMs
            : null
        if (latencyMs === null) return
        usableResultCapturedRef.current = true
        capture("first_usable_result_latency", {
          $insert_id: `first-usable-result:${bookId}`,
          book_id: bookId,
          latency_ms: latencyMs,
          result_type: resultType,
          scan_id: currentScan?.id ?? revision.continuity_scan_id,
          scan_duration_ms: persistedDurationMs,
        })
      }
      try {
        const existing = await booksApi.getContinuityFindings(bookId, { includeStale: true })
        if (cancelled) return
        if (existing.length > 0 || revision.continuity_status === "clean") {
          setFindings(existing)
          setSelectedId(existing.find((item) => !item.is_stale)?.id ?? existing[0]?.id ?? null)
          if (revision.continuity_status === "clean") {
            captureFirstUsableResult("verified_clean")
          } else if (existing.some((item) => !item.is_stale)) {
            captureFirstUsableResult("continuity_findings")
          }
          return
        }
        const nextScan = await booksApi.createContinuityScan(bookId)
        if (cancelled) return
        setScan(nextScan)
        if (nextScan.status === "failed") {
          setError(
            nextScan.error_detail
              ? `LoreVia could not complete the continuity scan: ${nextScan.error_detail}`
              : "LoreVia could not complete the continuity scan. Your manuscript is unchanged.",
          )
          capture("continuity_scan_failed", {
            book_id: bookId,
            scan_id: nextScan.id,
            failure_detail: nextScan.error_detail ?? "unknown",
          })
          return
        }
        setFindings(nextScan.findings)
        setSelectedId(nextScan.findings[0]?.id ?? null)
        capture("continuity_scan_completed", {
          book_id: bookId,
          continuity_status: nextScan.continuity_status,
          finding_count: nextScan.finding_count,
          duration_ms: nextScan.duration_ms,
          word_count: nextScan.word_count,
        })
        if (nextScan.continuity_status === "clean") {
          captureFirstUsableResult("verified_clean", nextScan)
        } else if (nextScan.findings.some((item) => !item.is_stale)) {
          captureFirstUsableResult("continuity_findings", nextScan)
        }
      } catch {
        if (cancelled) return
        setError("LoreVia could not complete the continuity scan. Your manuscript is unchanged.")
        capture("continuity_scan_failed", { book_id: bookId })
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    void load()
    return () => { cancelled = true }
  }, [bookCreatedAt, bookId, revision.continuity_status])

  const continuityStatus = scan?.continuity_status ?? revision.continuity_status
  useEffect(() => {
    if (continuityStatus !== "clean" || cleanViewedRef.current) return
    cleanViewedRef.current = true
    capture("clean_scan_viewed", { book_id: bookId, chapter_count: chapterCount })
    capture("activation_completed", { book_id: bookId, action: "verified_clean_scan" })
  }, [bookId, chapterCount, continuityStatus])

  const openFinding = (finding: ContinuityFinding) => {
    setSelectedId(finding.id)
    capture("continuity_finding_opened", {
      book_id: bookId,
      finding_id: finding.id,
      category: finding.category,
      severity: finding.severity,
      confidence: finding.confidence,
      is_stale: finding.is_stale,
    })
  }

  const decide = async (
    finding: ContinuityFinding,
    decision: FindingDecision,
    action: "added_to_revision_plan" | null = null,
  ) => {
    setSavingId(finding.id)
    setError(null)
    try {
      const updated = await booksApi.decideContinuityFinding(bookId, finding.id, {
        decision,
        action,
        reason: decision === "intentional" ? "intentional" : decision === "dismissed" ? "not_relevant" : decision === "resolved" ? "fixed" : null,
      })
      setFindings((items) => items.map((item) => item.id === updated.id ? updated : item))
      capture(`continuity_finding_${decision}`, {
        book_id: bookId,
        finding_id: finding.id,
        category: finding.category,
        severity: finding.severity,
        action,
      })
      if (action === "added_to_revision_plan") {
        capture("continuity_revision_task_created", {
          book_id: bookId,
          finding_id: finding.id,
          category: finding.category,
          severity: finding.severity,
        })
      }
      if (decision === "accepted") {
        capture("activation_completed", {
          book_id: bookId,
          finding_id: finding.id,
          action: "accepted_finding",
        })
      }
    } catch {
      setError("LoreVia could not save this decision. Please try again.")
    } finally {
      setSavingId(null)
    }
  }

  const recheck = async (finding: ContinuityFinding) => {
    setSavingId(finding.id)
    setError(null)
    try {
      const nextScan = await booksApi.recheckContinuityFinding(bookId, finding.id)
      setScan(nextScan)
      setFindings(nextScan.findings)
      setSelectedId(nextScan.findings[0]?.id ?? null)
      capture("continuity_finding_rechecked", {
        book_id: bookId,
        finding_id: finding.id,
        finding_count: nextScan.finding_count,
      })
    } catch {
      setError("LoreVia could not recheck this finding.")
    } finally {
      setSavingId(null)
    }
  }

  const shell = isDark ? "border-white/10 bg-[#0b1220]" : "border-stone-200 bg-white"
  const muted = isDark ? "text-slate-400" : "text-stone-600"

  if (loading) {
    return (
      <section className={`rounded-lg border p-6 ${shell}`} data-testid="continuity-inbox-loading">
        <p className="text-xs font-semibold uppercase tracking-[0.22em] text-teal-500">Continuity Inbox</p>
        <h2 className="mt-3 text-2xl font-semibold">Checking canon across every chapter…</h2>
        <p className={`mt-3 text-sm ${muted}`}>Cast and coverage can appear first; verified findings follow when the evidence pass finishes.</p>
      </section>
    )
  }

  if (continuityStatus === "clean" && findings.length === 0) {
    return (
      <section className={`rounded-lg border p-6 sm:p-8 ${shell}`} data-testid="continuity-inbox-clean">
        <p className="text-xs font-semibold uppercase tracking-[0.22em] text-emerald-500">Verified clean scan</p>
        <h2 className="mt-3 text-3xl font-semibold">No supported continuity conflicts found.</h2>
        <p className={`mt-4 max-w-3xl text-sm leading-7 ${muted}`}>
          LoreVia checked {String(scan?.coverage.chapters_analyzed ?? revision.coverage?.chapters_analyzed ?? chapterCount)} chapters and found no evidence-backed conflict. This is a successful result, not an incomplete pass.
        </p>
        <button type="button" onClick={() => onNavigate(`/${bookId}/manuscript`)} className="mt-6 rounded-md bg-teal-700 px-4 py-2.5 text-sm font-semibold text-white hover:bg-teal-600">
          Open manuscript
        </button>
      </section>
    )
  }

  return (
    <section className={`rounded-lg border p-5 sm:p-8 ${shell}`} data-testid="continuity-inbox">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-teal-500">Continuity Inbox</p>
          <h2 className="mt-2 text-3xl font-semibold">{findings.filter((item) => !item.is_stale && !item.decision).length} findings need review</h2>
          <p className={`mt-3 text-sm ${muted}`}>Each direct conflict includes two versioned manuscript citations. Absence findings show their checked range and limitations.</p>
        </div>
        {revision.stale_finding_count || findings.some((item) => item.is_stale) ? (
          <span className="rounded-full bg-amber-500/15 px-3 py-1 text-xs font-semibold text-amber-500">Some findings are stale after edits</span>
        ) : null}
      </div>

      {error ? <p role="alert" className="mt-5 rounded-md border border-rose-300 bg-rose-50 p-3 text-sm text-rose-700">{error}</p> : null}

      {findings.length === 0 ? (
        <div className={`mt-6 rounded-md border p-4 text-sm ${isDark ? "border-white/10" : "border-stone-200"} ${muted}`}>
          The current manuscript does not yet contain enough cited observations for a verified continuity result.
        </div>
      ) : (
        <div className="mt-7 grid gap-5 lg:grid-cols-[minmax(220px,0.8fr)_minmax(0,1.5fr)]">
          <div className="space-y-2">
            {findings.map((finding) => (
              <button
                key={finding.id}
                type="button"
                onClick={() => openFinding(finding)}
                className={`w-full rounded-md border p-3 text-left transition ${selected?.id === finding.id ? "border-teal-500 bg-teal-500/10" : isDark ? "border-white/10 hover:border-white/20" : "border-stone-200 hover:border-stone-300"} ${finding.is_stale ? "opacity-60" : ""}`}
              >
                <span className="text-xs font-semibold uppercase tracking-wide text-amber-500">{finding.severity} · {Math.round(finding.confidence * 100)}%</span>
                <span className="mt-1 block text-sm font-semibold">{finding.title}</span>
                <span className={`mt-1 block text-xs ${muted}`}>{finding.decision ? `Marked ${finding.decision}` : finding.is_stale ? "Needs recheck" : "Awaiting review"}</span>
              </button>
            ))}
          </div>

          {selected ? (
            <article className={`rounded-md border p-5 ${isDark ? "border-white/10" : "border-stone-200"}`}>
              <h3 className="text-xl font-semibold">{selected.title}</h3>
              <p className={`mt-3 text-sm leading-7 ${muted}`}>{selected.explanation}</p>
              <div className="mt-5 grid gap-3 md:grid-cols-2">
                {selected.evidence.map((evidence) => (
                  <button
                    key={evidence.observation_id}
                    type="button"
                    onClick={() => onNavigate(`/${bookId}/manuscript?chapter=${evidence.chapter_number}&continuity_finding=${selected.id}`)}
                    className={`rounded-md border p-4 text-left ${isDark ? "border-white/10 bg-white/[0.03]" : "border-stone-200 bg-stone-50"}`}
                  >
                    <span className="text-xs font-semibold uppercase tracking-wide text-teal-500">Chapter {evidence.chapter_number} · v{evidence.content_version}</span>
                    <q className={`mt-2 block text-sm leading-6 ${muted}`}>{evidence.excerpt}</q>
                  </button>
                ))}
              </div>
              {selected.recommendation ? <p className={`mt-4 text-sm ${muted}`}><strong>Next step:</strong> {selected.recommendation}</p> : null}
              <div className="mt-5 flex flex-wrap gap-2">
                <ActionButton disabled={savingId === selected.id || selected.is_stale} onClick={() => void decide(selected, "accepted")}>Accept</ActionButton>
                <ActionButton disabled={savingId === selected.id || selected.is_stale} onClick={() => void decide(selected, "accepted", "added_to_revision_plan")}>Create task</ActionButton>
                <ActionButton disabled={savingId === selected.id || selected.is_stale} onClick={() => void decide(selected, "intentional")}>Mark intentional</ActionButton>
                <ActionButton disabled={savingId === selected.id || selected.is_stale} onClick={() => void decide(selected, "dismissed")}>Dismiss</ActionButton>
                <ActionButton disabled={savingId === selected.id || selected.is_stale} onClick={() => void decide(selected, "resolved")}>Resolve</ActionButton>
                <ActionButton disabled={savingId === selected.id} onClick={() => void recheck(selected)}>Recheck</ActionButton>
              </div>
            </article>
          ) : null}
        </div>
      )}
    </section>
  )
}

function ActionButton({
  children,
  disabled,
  onClick,
}: {
  children: ReactNode
  disabled: boolean
  onClick: () => void
}) {
  return (
    <button type="button" disabled={disabled} onClick={onClick} className="rounded-md border border-teal-600 px-3 py-2 text-xs font-semibold text-teal-500 hover:bg-teal-500/10 disabled:cursor-not-allowed disabled:opacity-50">
      {children}
    </button>
  )
}
