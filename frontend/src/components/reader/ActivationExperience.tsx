"use client"

import { useCallback, useEffect, useRef, useState } from "react"

import { ContinuityInbox } from "@/components/continuity/ContinuityInbox"
import { FindingReviewPanel } from "@/components/reader/FindingReviewPanel"
import { capture } from "@/lib/analytics/posthog"
import { booksApi } from "@/lib/api/books"
import { intelligenceApi } from "@/lib/api/intelligence"
import type { RevisionActionItem, RevisionIntelligence } from "@/types/book"
import type { FirstImpressionResponse } from "@/types/intelligence"

type Props = {
  bookId: string
  bookCreatedAt?: string | null
  bookTitle: string
  bookWorkType?: "novel" | "screenplay" | string | null
  chapterCount: number
  isDark: boolean
  revision: RevisionIntelligence
  enableFirstImpression?: boolean
  onRevisionChange: (revision: RevisionIntelligence) => void
  onNavigate: (href: string) => void
}

export function ActivationExperience({
  bookId,
  bookCreatedAt,
  bookTitle,
  bookWorkType,
  chapterCount,
  isDark,
  revision,
  enableFirstImpression = false,
  onRevisionChange,
  onNavigate,
}: Props) {
  const findings = revision.priority_findings ?? []
  const [selectedId, setSelectedId] = useState<string | null>(findings[0]?.id ?? null)
  const [savingId, setSavingId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [firstImpression, setFirstImpression] = useState<FirstImpressionResponse | null>(null)
  const [firstImpressionLoading, setFirstImpressionLoading] = useState(enableFirstImpression)
  const [firstImpressionError, setFirstImpressionError] = useState<string | null>(null)
  const [retrying, setRetrying] = useState(false)
  const [pollNonce, setPollNonce] = useState(0)
  const [showExistingAnalysis, setShowExistingAnalysis] = useState(!enableFirstImpression)
  const viewedRef = useRef(false)
  const supportiveResultCapturedRef = useRef(false)
  const whatsWorkingViewedRef = useRef(false)
  const queuedCapturedRef = useRef(false)
  const failedCapturedRef = useRef(false)
  const completionSavingRef = useRef(false)

  useEffect(() => {
    if (viewedRef.current) return
    viewedRef.current = true
    capture("activation_experience_viewed", {
      book_id: bookId,
      chapter_count: chapterCount,
      finding_count: findings.length,
      analysis_complete: revision.analysis_complete,
      supportive_first_read_enabled: enableFirstImpression,
    })
  }, [bookId, chapterCount, enableFirstImpression, findings.length, revision.analysis_complete])

  useEffect(() => {
    if (!enableFirstImpression || !revision.analysis_complete) return
    let cancelled = false
    let timer: ReturnType<typeof setTimeout> | null = null

    async function load() {
      try {
        const next = await intelligenceApi.getFirstImpression(bookId)
        if (cancelled) return
        setFirstImpression(next)
        setFirstImpressionError(null)
        setFirstImpressionLoading(false)
        if (next.status === "complete" || next.status === "not_started") {
          setShowExistingAnalysis(true)
        } else if (["queued", "running"].includes(next.status)) {
          timer = setTimeout(() => { void load() }, 1800)
        }
      } catch {
        if (cancelled) return
        setFirstImpressionLoading(false)
        setFirstImpressionError("LoreVia could not load the supportive first read. Your existing analysis is still available.")
      }
    }

    void load()
    return () => {
      cancelled = true
      if (timer) clearTimeout(timer)
    }
  }, [bookId, enableFirstImpression, pollNonce, revision.analysis_complete])

  useEffect(() => {
    if (!firstImpression) return
    if (["queued", "running"].includes(firstImpression.status) && !queuedCapturedRef.current) {
      queuedCapturedRef.current = true
      capture("first_impression_queued", {
        $insert_id: `first-impression-queued:${bookId}:${firstImpression.task_id ?? "pending"}`,
        book_id: bookId,
        task_id: firstImpression.task_id,
      })
    }
    if (firstImpression.status === "failed" && !failedCapturedRef.current) {
      failedCapturedRef.current = true
      capture("first_impression_failed", {
        $insert_id: `first-impression-failed:${bookId}:${firstImpression.task_id ?? "unknown"}`,
        book_id: bookId,
        task_id: firstImpression.task_id,
        error: firstImpression.error,
      })
    }
  }, [bookId, firstImpression])

  useEffect(() => {
    const report = firstImpression?.report
    if (firstImpression?.status !== "complete" || !report || supportiveResultCapturedRef.current) return
    supportiveResultCapturedRef.current = true
    const createdAtMs = bookCreatedAt ? Date.parse(bookCreatedAt) : Number.NaN
    const reportCreatedAtMs = Date.parse(report.created_at)
    const latencyMs = Number.isFinite(createdAtMs) && Number.isFinite(reportCreatedAtMs) && reportCreatedAtMs >= createdAtMs
      ? reportCreatedAtMs - createdAtMs
      : null
    capture("first_impression_completed", {
      $insert_id: `first-impression-completed:${bookId}:${report.report_id}`,
      book_id: bookId,
      report_id: report.report_id,
      chapter_count: report.coverage.analyzed_chapters.length,
      strength_count: report.strengths.length,
      latency_ms: latencyMs,
    })
    if (latencyMs !== null) {
      capture("time_to_first_supportive_result", {
        $insert_id: `time-to-first-supportive-result:${bookId}`,
        book_id: bookId,
        latency_ms: latencyMs,
        report_id: report.report_id,
      })
    }
  }, [bookCreatedAt, bookId, firstImpression])

  useEffect(() => {
    if (firstImpression?.status !== "complete" || !firstImpression.report || whatsWorkingViewedRef.current) return
    whatsWorkingViewedRef.current = true
    capture("whats_working_viewed", {
      book_id: bookId,
      report_id: firstImpression.report.report_id,
      strength_count: firstImpression.report.strengths.length,
    })
  }, [bookId, firstImpression])

  const completeActivation = useCallback(async (
    action: "reviewed_first_read" | "verified_clean_scan",
    updateUi: boolean,
  ) => {
    if (completionSavingRef.current) return
    completionSavingRef.current = true
    setError(null)
    const completedAt = new Date().toISOString()
    try {
      await booksApi.updateWriterWorkspace(bookId, {
        activation: {
          completed_at: completedAt,
          completion_action: action,
          completed_finding_id: null,
        },
      })
      capture("activation_completed", { book_id: bookId, action })
      if (updateUi) {
        onRevisionChange({
          ...revision,
          activation: {
            eligible: false,
            completed: true,
            completed_at: completedAt,
            completion_action: action,
            completed_finding_id: null,
          },
        })
      }
    } catch {
      setError("LoreVia could not save your activation progress. Please try again.")
    } finally {
      completionSavingRef.current = false
    }
  }, [bookId, onRevisionChange, revision])

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

  const retryFirstRead = async () => {
    setRetrying(true)
    setFirstImpressionError(null)
    try {
      const next = await intelligenceApi.retryFirstImpression(bookId)
      setFirstImpression(next)
      setShowExistingAnalysis(false)
      setPollNonce((value) => value + 1)
      capture("first_impression_retry_requested", { book_id: bookId, task_id: next.task_id })
    } catch {
      setFirstImpressionError("LoreVia could not restart the first read. Please try again.")
    } finally {
      setRetrying(false)
    }
  }

  const revealExistingAnalysis = () => {
    setShowExistingAnalysis(true)
    capture("first_impression_existing_analysis_opened", {
      book_id: bookId,
      first_impression_status: firstImpression?.status ?? "loading",
    })
  }

  const shell = isDark
    ? "border-white/10 bg-[#0b1220] text-slate-100"
    : "border-stone-200 bg-white text-stone-950"
  const muted = isDark ? "text-slate-300" : "text-stone-600"
  const softPanel = isDark ? "border-white/10 bg-white/[0.035]" : "border-stone-200 bg-stone-50"

  if (!revision.analysis_complete) {
    return (
      <section className={`rounded-lg border p-6 sm:p-8 ${shell}`} data-testid="activation-incomplete">
        <p className="text-xs font-semibold uppercase tracking-[0.22em] text-amber-500">Analysis status</p>
        <h1 className="mt-3 text-3xl font-semibold">Your manuscript is ready, but the evidence pass is incomplete.</h1>
        <p className={`mt-4 max-w-3xl text-sm leading-7 ${muted}`}>
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

  const report = firstImpression?.report
  const groundedStrengths = report?.strengths.map((item) => item.trim()).filter(Boolean) ?? []
  const progress = firstImpression?.progress
  const progressPercent = progress && progress.total > 0
    ? Math.max(0, Math.min(100, Math.round((progress.completed / progress.total) * 100)))
    : null
  const unitLabel = bookWorkType === "screenplay" ? "scene" : "chapter"

  return (
    <section className={`rounded-lg border p-5 sm:p-8 ${shell}`} data-testid="activation-experience">
      {enableFirstImpression ? (
        <div data-testid="supportive-first-read">
          {firstImpressionLoading ? (
            <FirstReadProgress
              title="LoreVia is reading your manuscript as a whole."
              body="It is looking first for the characters, scenes, voice, and emotional moments that give the draft its identity."
              progressPercent={null}
              progressLabel="Preparing the supportive first read"
              isDark={isDark}
              onContinue={revealExistingAnalysis}
            />
          ) : null}

          {!firstImpressionLoading && firstImpression?.status === "not_started" ? (
            <div className={`rounded-xl border p-6 sm:p-8 ${softPanel}`} data-testid="first-read-not-started">
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-teal-500">Analysis complete</p>
              <h1 className="mt-3 text-3xl font-semibold">Your manuscript analysis is ready.</h1>
              <p className={`mt-4 max-w-3xl text-sm leading-7 ${muted}`}>
                This project does not have an automatic first read saved yet. You can continue with the evidence-backed analysis now or open AI Beta Reader for a fresh full-manuscript read.
              </p>
              <button type="button" onClick={() => onNavigate(`/${bookId}/ai-beta-reader`)} className="mt-6 rounded-md bg-teal-700 px-4 py-2.5 text-sm font-semibold text-white hover:bg-teal-600">
                Open AI Beta Reader
              </button>
            </div>
          ) : null}

          {!firstImpressionLoading && firstImpression && ["queued", "running"].includes(firstImpression.status) ? (
            <FirstReadProgress
              title="Your first read is underway."
              body={`LoreVia is considering all ${chapterCount} ${unitLabel}${chapterCount === 1 ? "" : "s"} together before it offers detailed critique.`}
              progressPercent={progressPercent}
              progressLabel={progress?.message ?? (firstImpression.status === "queued" ? "Waiting to begin" : "LoreVia is reading for what makes this manuscript itself")}
              isDark={isDark}
              onContinue={revealExistingAnalysis}
            />
          ) : null}

          {firstImpressionError || firstImpression?.status === "failed" ? (
            <div className={`rounded-xl border p-6 sm:p-8 ${softPanel}`} data-testid="first-read-failed">
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-amber-500">The first read paused</p>
              <h1 className="mt-3 text-3xl font-semibold">Your manuscript and existing analysis are safe.</h1>
              <p className={`mt-4 max-w-3xl text-sm leading-7 ${muted}`}>
                {firstImpressionError ?? "LoreVia could not finish this reader pass. You can retry it at no extra scan cost or continue into the existing analysis now."}
              </p>
              <div className="mt-6 flex flex-wrap gap-3">
                {firstImpression?.can_retry ? (
                  <button type="button" disabled={retrying} onClick={() => void retryFirstRead()} className="rounded-md bg-teal-700 px-4 py-2.5 text-sm font-semibold text-white hover:bg-teal-600 disabled:opacity-60">
                    {retrying ? "Restarting…" : "Retry first read"}
                  </button>
                ) : null}
                <button type="button" onClick={revealExistingAnalysis} className={`rounded-md border px-4 py-2.5 text-sm font-semibold ${isDark ? "border-white/20 hover:bg-white/5" : "border-stone-300 hover:bg-stone-100"}`}>
                  Continue to existing analysis
                </button>
              </div>
            </div>
          ) : null}

          {firstImpression?.status === "complete" && report ? (
            <div data-testid="whats-working-section">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <p className="text-xs font-semibold uppercase tracking-[0.22em] text-teal-500">Validate · Your first read</p>
                {report.is_stale ? <span className="rounded-full bg-amber-100 px-3 py-1 text-xs font-semibold text-amber-800">Uploaded-draft snapshot</span> : null}
              </div>
              <h1 className="mt-3 text-3xl font-semibold sm:text-4xl">What’s Working</h1>
              <p className={`mt-4 max-w-3xl text-base leading-7 ${muted}`}>
                {report.overall_impression || "LoreVia completed the reader pass, but could not ground a reliable overall impression."}
              </p>
              {groundedStrengths.length > 0 ? (
                <ul className="mt-7 grid gap-3 sm:grid-cols-2">
                  {groundedStrengths.slice(0, 5).map((strength) => (
                    <li key={strength} className={`rounded-lg border p-4 text-sm leading-6 ${softPanel}`}>
                      <span className="mr-2 text-teal-500" aria-hidden="true">◆</span>{strength}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className={`mt-6 rounded-lg border p-4 text-sm leading-6 ${softPanel}`}>
                  LoreVia did not find enough grounded evidence to name a specific strength confidently. It will keep the detailed review transparent rather than inventing praise.
                </p>
              )}
              {report.is_stale ? (
                <button type="button" onClick={() => onNavigate(`/${bookId}/ai-beta-reader`)} className="mt-4 text-sm font-semibold text-teal-600 hover:underline">
                  Run a new read in AI Beta Reader
                </button>
              ) : null}
            </div>
          ) : null}

          {firstImpression?.status === "complete" && report ? (
            <div className={`mt-10 border-t pt-8 ${isDark ? "border-white/10" : "border-stone-200"}`} data-testid="story-understanding-section">
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-sky-500">Understand · The story LoreVia read</p>
              <h2 className="mt-3 text-2xl font-semibold">The Story LoreVia Is Seeing</h2>
              <div className={`mt-5 rounded-lg border p-4 ${softPanel}`}>
                <p className={`text-xs font-semibold uppercase tracking-[0.16em] ${isDark ? "text-slate-400" : "text-stone-500"}`}>Reader vibe</p>
                <p className={`mt-2 text-sm leading-7 ${muted}`}>
                  {report.reader_vibe || "The report did not return a reliable vibe summary."}
                </p>
              </div>
              <p className={`mt-4 max-w-3xl text-sm leading-7 ${muted}`}>
                {report.story_understanding || report.overall_impression || "The reader pass completed, but it could not summarize the story’s intent with enough confidence."}
              </p>
              <div className={`mt-5 rounded-lg border px-4 py-3 text-sm ${softPanel}`} data-testid="first-read-coverage">
                <p className="font-semibold">
                  {report.coverage.missing_chapters.length === 0
                    ? `Full coverage: all ${report.coverage.requested_chapters.length} requested ${unitLabel}s were analyzed.`
                    : `Partial coverage: ${report.coverage.analyzed_chapters.length} of ${report.coverage.requested_chapters.length} requested ${unitLabel}s were analyzed.`}
                </p>
                <p className={`mt-1 ${muted}`}>
                  {report.coverage.word_count.toLocaleString()} words considered
                  {report.coverage.missing_chapters.length > 0 ? ` · Missing ${unitLabel}s: ${report.coverage.missing_chapters.join(", ")}` : ""}
                </p>
              </div>
            </div>
          ) : null}
        </div>
      ) : (
        <div className="max-w-3xl">
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-teal-500">Analysis complete</p>
          <h1 className="mt-3 text-3xl font-semibold sm:text-4xl">We analyzed {chapterCount} chapter{chapterCount === 1 ? "" : "s"} in {bookTitle}.</h1>
          <p className={`mt-4 text-base leading-7 ${muted}`}>
            Start in the Continuity Inbox. Verified conflicts show side-by-side evidence; a clean scan is a successful result.
          </p>
        </div>
      )}

      {error ? <p role="alert" className="mt-5 rounded-md border border-rose-300 bg-rose-50 p-3 text-sm text-rose-700">{error}</p> : null}

      {showExistingAnalysis ? (
        <div className={`mt-10 border-t pt-8 ${isDark ? "border-white/10" : "border-stone-200"}`} data-testid="existing-analysis">
          {enableFirstImpression ? (
            <div className="mb-6 max-w-3xl">
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-amber-500">Critique · What Needs Attention</p>
              <h2 className="mt-3 text-2xl font-semibold">Evidence-backed continuity review</h2>
              <p className={`mt-3 text-sm leading-7 ${muted}`}>Now that the draft’s intent and strengths are visible, review specific conflicts and decide what belongs in your revision plan.</p>
            </div>
          ) : null}
          <ContinuityInbox
            bookId={bookId}
            bookCreatedAt={bookCreatedAt}
            chapterCount={chapterCount}
            isDark={isDark}
            revision={revision}
            onNavigate={onNavigate}
            onVerifiedClean={enableFirstImpression ? () => { void completeActivation("verified_clean_scan", false) } : undefined}
          />

          {enableFirstImpression ? (
            <div className={`mt-8 border-t pt-8 ${isDark ? "border-white/10" : "border-stone-200"}`} data-testid="improve-section">
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-teal-500">Improve · Where to Go Next</p>
              <h2 className="mt-3 text-2xl font-semibold">Turn the read into a revision path</h2>
              {report?.prioritized_revisions.length ? (
                <ul className={`mt-4 space-y-2 text-sm leading-7 ${muted}`}>
                  {report.prioritized_revisions.slice(0, 5).map((item) => <li key={item}>• {item}</li>)}
                </ul>
              ) : (
                <p className={`mt-4 text-sm leading-7 ${muted}`}>The first read did not return grounded revision priorities. Use the evidence review below or continue into the manuscript without making a decision.</p>
              )}
              <div className="mt-5 flex flex-wrap gap-3">
                <button type="button" onClick={() => onNavigate(`/${bookId}/manuscript`)} className={`rounded-md border px-4 py-2 text-sm font-semibold ${isDark ? "border-white/20 hover:bg-white/5" : "border-stone-300 hover:bg-stone-100"}`}>Open manuscript</button>
                <button type="button" onClick={() => onNavigate(`/${bookId}/author-loop`)} className={`rounded-md border px-4 py-2 text-sm font-semibold ${isDark ? "border-white/20 hover:bg-white/5" : "border-stone-300 hover:bg-stone-100"}`}>Open revision workflow</button>
                <button type="button" onClick={() => onNavigate(`/${bookId}/ai-beta-reader`)} className={`rounded-md border px-4 py-2 text-sm font-semibold ${isDark ? "border-white/20 hover:bg-white/5" : "border-stone-300 hover:bg-stone-100"}`}>Open full AI Beta Reader</button>
              </div>
            </div>
          ) : null}

          {findings.length > 0 ? (
            <div className="mt-8">
              <p className={`mb-4 text-xs font-semibold uppercase tracking-[0.2em] ${isDark ? "text-slate-400" : "text-stone-500"}`}>Additional revision priorities</p>
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
          ) : null}

          {enableFirstImpression ? (
            <div className={`mt-8 flex flex-col gap-3 rounded-lg border p-5 sm:flex-row sm:items-center sm:justify-between ${softPanel}`}>
              <div>
                <p className="font-semibold">You can return to every part of this analysis.</p>
                <p className={`mt-1 text-sm ${muted}`}>Continue without accepting or dismissing any finding.</p>
              </div>
              <button type="button" onClick={() => void completeActivation("reviewed_first_read", true)} className="rounded-md bg-teal-700 px-4 py-2.5 text-sm font-semibold text-white hover:bg-teal-600">
                Continue to workspace
              </button>
            </div>
          ) : null}
        </div>
      ) : null}
    </section>
  )
}

function FirstReadProgress({
  title,
  body,
  progressPercent,
  progressLabel,
  isDark,
  onContinue,
}: {
  title: string
  body: string
  progressPercent: number | null
  progressLabel: string
  isDark: boolean
  onContinue: () => void
}) {
  return (
    <div data-testid="first-read-progress">
      <p className="text-xs font-semibold uppercase tracking-[0.22em] text-teal-500">Your supportive first read</p>
      <h1 className="mt-3 text-3xl font-semibold sm:text-4xl">{title}</h1>
      <p className={`mt-4 max-w-3xl text-base leading-7 ${isDark ? "text-slate-300" : "text-stone-600"}`}>{body}</p>
      <div className="mt-7 max-w-2xl">
        <div className={`h-2 overflow-hidden rounded-full ${isDark ? "bg-white/10" : "bg-stone-200"}`}>
          <div
            className={`h-full rounded-full bg-teal-600 transition-[width] duration-500 ${progressPercent === null ? "w-1/3 animate-pulse" : ""}`}
            style={progressPercent === null ? undefined : { width: `${progressPercent}%` }}
          />
        </div>
        <p className={`mt-2 text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>{progressLabel}</p>
      </div>
      <button type="button" onClick={onContinue} className={`mt-6 rounded-md border px-4 py-2.5 text-sm font-semibold ${isDark ? "border-white/20 hover:bg-white/5" : "border-stone-300 hover:bg-stone-100"}`}>
        Continue to existing analysis
      </button>
    </div>
  )
}
