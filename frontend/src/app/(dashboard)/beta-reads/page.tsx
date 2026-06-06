"use client"

import { useMemo, useState } from "react"
import { useQueries, useQuery } from "@tanstack/react-query"
import type { Route } from "next"
import { useRouter } from "next/navigation"

import {
  WorkspaceEmptyState,
  WorkspaceHeader,
  WorkspacePage,
  WorkspacePanel,
  WorkspaceTabButton,
} from "@/components/ui/Workspace"
import { betaReadsApi } from "@/lib/api/betaReads"
import { readerApi } from "@/lib/api/reader"
import {
  betaReadDeadlineDetail,
  betaReadDeadlineLabel,
  betaReadIsUrgent,
  betaReadMissedWarning,
  betaReadPrimaryHref,
  betaReadProgressLabel,
  betaReadRequirementLines,
} from "@/lib/utils/betaReads"
import { asQueryKey } from "@/lib/query/cacheKeys"
import type { BetaReadAssignment, BetaReadViewBucket } from "@/types/reader"
import type { BetaReadAssignmentDetail } from "@/types/betaRead"

const TAB_OPTIONS: Array<{ value: BetaReadViewBucket; label: string }> = [
  { value: "active", label: "Active" },
  { value: "scheduled", label: "Scheduled" },
  { value: "completed", label: "Completed" },
  { value: "missed", label: "Missed" },
]

const DATE_TIME_FORMATTER = new Intl.DateTimeFormat("en-US", {
  dateStyle: "medium",
  timeStyle: "short",
})

function formatWindow(assignment: BetaReadAssignment) {
  return `${DATE_TIME_FORMATTER.format(new Date(assignment.starts_at))} to ${DATE_TIME_FORMATTER.format(new Date(assignment.expires_at))}`
}

function completedResultLabel(assignment: BetaReadAssignment) {
  if (assignment.completed_at) return "Review completed"
  if (assignment.state === "disqualified") {
    return "Requirements not met before the deadline"
  }
  return "Awaiting completion processing"
}

function submissionStatusLabel(assignment: BetaReadAssignment) {
  if (assignment.completed_at) return "Completed"
  if (assignment.submitted_at) return "Submitted"
  if (assignment.submission_allowed) return "Ready to submit"
  return assignment.status_label
}

export default function BetaReadsPage() {
  const router = useRouter()
  const [bucket, setBucket] = useState<BetaReadViewBucket>("active")
  const [pendingId, setPendingId] = useState<string | null>(null)
  const {
    data: items = [],
    isLoading: loading,
    isError,
    refetch,
  } = useQuery<BetaReadAssignment[]>({
    queryKey: asQueryKey(`reader:beta-reads:${bucket}`),
    queryFn: () => readerApi.listBetaReads(bucket),
    staleTime: 12_000,
  })
  const detailQueries = useQueries({
    queries: items.map((assignment) => ({
      queryKey: asQueryKey(`reader:beta-reads:detail:${assignment.id}`),
      queryFn: () => betaReadsApi.getMineDetail(assignment.id),
      enabled: assignment.view_bucket !== "completed" && assignment.view_bucket !== "missed",
      staleTime: 12_000,
    })),
  })
  const detailByAssignmentId = useMemo(
    () =>
      new Map<string, { data: BetaReadAssignmentDetail | null; isLoading: boolean }>(
        items.map((assignment, index) => [
          assignment.id,
          {
            data: (detailQueries[index]?.data as BetaReadAssignmentDetail | undefined) ?? null,
            isLoading: Boolean(detailQueries[index]?.isLoading),
          },
        ])
      ),
    [detailQueries, items]
  )

  const headerMeta = useMemo(
    () => (
      <div className="flex flex-wrap justify-end gap-3">
        <div className="app-chip">{items.length.toLocaleString()} assignments</div>
        <div className="app-chip">Deadline-based review workflow</div>
      </div>
    ),
    [items.length]
  )

  async function handlePrimaryAction(assignment: BetaReadAssignment) {
    setPendingId(assignment.id)
    try {
      if (assignment.primary_action === "Start") {
        await readerApi.startBetaRead(assignment.id)
        await refetch()
        router.push(betaReadPrimaryHref(assignment) as Route)
        return
      }
      if (assignment.primary_action === "Continue") {
        router.push(betaReadPrimaryHref(assignment) as Route)
        return
      }
      router.push(`/${assignment.book_id}/beta-feedback` as Route)
    } finally {
      setPendingId(null)
    }
  }

  function renderCard(assignment: BetaReadAssignment) {
    const urgent = betaReadIsUrgent(assignment.expires_at)
    const requirementLines = betaReadRequirementLines(assignment)
    const missedWarning = betaReadMissedWarning(assignment)
    const detailState = detailByAssignmentId.get(assignment.id)
    const assignmentDetail = detailState?.data ?? null
    const authorQuestions = assignmentDetail?.author_questions ?? []
    const authorQuestionsLoading = detailState?.isLoading ?? false

    return (
      <article
        key={assignment.id}
        className="rounded-md border border-[rgba(var(--border),0.75)] bg-[rgba(255,255,255,0.55)] p-5 dark:bg-[rgba(255,255,255,0.03)]"
      >
        <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
          <div className="space-y-2">
            <div>
              <p className="app-eyebrow">{assignment.author_name}</p>
              <h2 className="mt-2 text-2xl font-semibold text-[rgb(var(--foreground))]">
                {assignment.book_title}
              </h2>
            </div>
            <p className="text-sm font-medium text-[rgb(var(--foreground))]">{assignment.task_label}</p>
            <p className={`text-sm ${urgent ? "text-rose-600 dark:text-rose-300" : "text-[rgb(var(--muted-foreground))]"}`}>
              {betaReadDeadlineLabel(assignment.expires_at)}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <span className="app-chip">{assignment.status_label}</span>
            <span className="app-chip">{assignment.window_days}-day window</span>
          </div>
        </div>

        <div className="mt-5 grid gap-4 lg:grid-cols-2">
          <div className="space-y-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[rgb(var(--muted-foreground))]">
                Reading window
              </p>
              <p className="mt-1 text-sm text-[rgb(var(--foreground))]">{formatWindow(assignment)}</p>
            </div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[rgb(var(--muted-foreground))]">
                Deadline
              </p>
              <p className={`mt-1 text-sm ${urgent ? "text-rose-600 dark:text-rose-300" : "text-[rgb(var(--foreground))]"}`}>
                {betaReadDeadlineDetail(assignment.expires_at)}
              </p>
            </div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[rgb(var(--muted-foreground))]">
                Progress
              </p>
              <div className="mt-2 h-2 overflow-hidden rounded-full bg-[rgba(var(--border),0.65)]">
                <div
                  className={`h-full rounded-full ${urgent ? "bg-rose-500" : "bg-[rgb(var(--accent))]"}`}
                  style={{ width: `${Math.max(4, Math.round(assignment.progress_pct))}%` }}
                />
              </div>
              <p className="mt-2 text-sm text-[rgb(var(--muted-foreground))]">{betaReadProgressLabel(assignment)}</p>
            </div>
          </div>

          <div className="space-y-3">
            {assignment.view_bucket === "completed" ? (
              <>
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[rgb(var(--muted-foreground))]">
                    Result
                  </p>
                  <p className="mt-1 text-sm text-[rgb(var(--foreground))]">{completedResultLabel(assignment)}</p>
                </div>
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[rgb(var(--muted-foreground))]">
                    Completed date
                  </p>
                  <p className="mt-1 text-sm text-[rgb(var(--foreground))]">
                    {assignment.completed_at ? DATE_TIME_FORMATTER.format(new Date(assignment.completed_at)) : "Pending completion processing"}
                  </p>
                </div>
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[rgb(var(--muted-foreground))]">
                    Feedback submitted
                  </p>
                  <p className="mt-1 text-sm text-[rgb(var(--foreground))]">
                    {assignment.submitted_at ? DATE_TIME_FORMATTER.format(new Date(assignment.submitted_at)) : "Not submitted"}
                  </p>
                </div>
              </>
            ) : assignment.view_bucket === "missed" ? (
              <>
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[rgb(var(--muted-foreground))]">
                    Deadline missed
                  </p>
                  <p className="mt-1 text-sm text-[rgb(var(--foreground))]">{betaReadDeadlineDetail(assignment.expires_at)}</p>
                </div>
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[rgb(var(--muted-foreground))]">
                    Outcome
                  </p>
                  <p className="mt-1 text-sm text-[rgb(var(--foreground))]">This assignment expired before completion.</p>
                </div>
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[rgb(var(--muted-foreground))]">
                    Missed streak
                  </p>
                  <p className="mt-1 text-sm text-[rgb(var(--foreground))]">
                    {assignment.counted_toward_missed_streak
                      ? "Counted toward your consecutive missed beta reads"
                      : "Did not count toward your consecutive missed beta reads"}
                  </p>
                </div>
                {missedWarning ? (
                  <div className="rounded-md border border-amber-300/40 bg-amber-100/70 px-4 py-3 text-sm text-amber-900 dark:bg-amber-300/10 dark:text-amber-100">
                    {missedWarning}
                  </div>
                ) : null}
              </>
            ) : (
              <>
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[rgb(var(--muted-foreground))]">
                    Required
                  </p>
                  <ul className="mt-2 space-y-2 text-sm text-[rgb(var(--foreground))]">
                    {requirementLines.map((line) => (
                      <li key={line}>{line}</li>
                    ))}
                  </ul>
                </div>
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[rgb(var(--muted-foreground))]">
                    Completion gate
                  </p>
                  <p className="mt-1 text-sm text-[rgb(var(--foreground))]">
                    {assignment.require_final_feedback
                      ? "Require final feedback before completion"
                      : "Final feedback is not required before completion"}
                  </p>
                </div>
                {authorQuestions.length > 0 ? (
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[rgb(var(--muted-foreground))]">
                      Author questions
                    </p>
                    <ul className="mt-2 space-y-2 text-sm text-[rgb(var(--foreground))]">
                      {authorQuestions.map((question) => (
                        <li key={question.id}>{question.prompt}</li>
                      ))}
                    </ul>
                  </div>
                ) : assignment.question_count > 0 && authorQuestionsLoading ? (
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[rgb(var(--muted-foreground))]">
                      Author questions
                    </p>
                    <p className="mt-1 text-sm text-[rgb(var(--muted-foreground))]">Loading author questions...</p>
                  </div>
                ) : null}
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[rgb(var(--muted-foreground))]">
                    Submission status
                  </p>
                  <p className="mt-1 text-sm text-[rgb(var(--foreground))]">{submissionStatusLabel(assignment)}</p>
                </div>
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[rgb(var(--muted-foreground))]">
                    Feedback progress
                  </p>
                  <p className="mt-1 text-sm text-[rgb(var(--foreground))]">
                    {assignment.feedback_item_count} of {assignment.required_feedback_item_count} feedback items - {assignment.answered_question_count} of {assignment.question_count} questions answered
                  </p>
                </div>
              </>
            )}
          </div>
        </div>

        <div className="mt-5 flex flex-wrap gap-3">
          <button
            type="button"
            onClick={() => void handlePrimaryAction(assignment)}
            disabled={pendingId === assignment.id}
            className="inline-flex h-11 items-center justify-center rounded-full bg-[rgb(var(--accent))] px-5 text-sm font-semibold text-white transition hover:opacity-90 disabled:opacity-60"
          >
            {pendingId === assignment.id ? "Working..." : assignment.primary_action}
          </button>
          <button
            type="button"
            onClick={() => router.push(`/${assignment.book_id}/notes` as Route)}
            className="inline-flex h-11 items-center justify-center rounded-full border border-[rgba(var(--border),0.9)] px-5 text-sm font-semibold text-[rgb(var(--foreground))] transition hover:bg-[rgba(var(--border),0.16)]"
          >
            Open notes
          </button>
          {assignment.view_bucket !== "completed" && assignment.view_bucket !== "missed" ? (
            <button
              type="button"
              onClick={() => router.push(`/${assignment.book_id}/beta-feedback` as Route)}
              className="inline-flex h-11 items-center justify-center rounded-full border border-[rgba(var(--border),0.9)] px-5 text-sm font-semibold text-[rgb(var(--foreground))] transition hover:bg-[rgba(var(--border),0.16)]"
            >
              Submit feedback
            </button>
          ) : null}
        </div>
      </article>
    )
  }

  return (
    <WorkspacePage className="min-h-0 bg-transparent">
      <div className="space-y-8 pb-12">
        <WorkspacePanel tone="strong" className="p-6 sm:p-8">
          <WorkspaceHeader
            eyebrow="Beta Reads"
            title="Upcoming Beta Reads"
            description="Track assigned beta reads, deadlines, and review requirements from one place."
            meta={headerMeta}
          />
        </WorkspacePanel>

        <WorkspacePanel className="p-6">
          <div className="flex flex-wrap gap-3">
            {TAB_OPTIONS.map((tab) => (
              <WorkspaceTabButton
                key={tab.value}
                active={bucket === tab.value}
                onClick={() => setBucket(tab.value)}
              >
                {tab.label}
              </WorkspaceTabButton>
            ))}
          </div>

          {isError ? (
            <div className="mt-5 rounded-md border border-rose-300/40 bg-rose-100/70 px-4 py-3 text-sm text-rose-900 dark:bg-rose-300/10 dark:text-rose-100">
              We could not load your beta reads right now.
            </div>
          ) : null}

          <div className="mt-5 space-y-4">
            {loading ? (
              <WorkspaceEmptyState
                title="Loading beta reads"
                body="We are syncing your assigned reads, deadlines, and review requirements."
              />
            ) : items.length === 0 ? (
              <WorkspaceEmptyState
                title={`No ${bucket} beta reads`}
                body="When an author assigns you a beta read, it will appear here with its deadline, progress, and review requirements."
              />
            ) : (
              items.map(renderCard)
            )}
          </div>
        </WorkspacePanel>
      </div>
    </WorkspacePage>
  )
}
