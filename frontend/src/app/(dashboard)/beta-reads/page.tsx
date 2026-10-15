"use client"

import { useMemo, useState } from "react"
import { useQueries, useQuery } from "@tanstack/react-query"
import type { Route } from "next"
import { useRouter } from "next/navigation"

import { WorkspaceEmptyState, WorkspaceHeader, WorkspacePage } from "@/components/ui/Workspace"
import { betaReadsApi } from "@/lib/api/betaReads"
import { readerApi } from "@/lib/api/reader"
import { asQueryKey } from "@/lib/query/cacheKeys"
import {
  betaReadDeadlineDetail,
  betaReadDeadlineLabel,
  betaReadIsUrgent,
  betaReadMissedWarning,
  betaReadPrimaryHref,
  betaReadProgressLabel,
  betaReadRequirementLines,
} from "@/lib/utils/betaReads"
import type { BetaReadAssignmentDetail } from "@/types/betaRead"
import type { BetaReadAssignment, BetaReadViewBucket } from "@/types/reader"

type AssignmentView = "assigned" | "in_progress" | "completed"

const VIEW_OPTIONS: Array<{ value: AssignmentView; label: string; buckets: BetaReadViewBucket[] }> = [
  { value: "assigned", label: "Assigned", buckets: ["scheduled"] },
  { value: "in_progress", label: "In progress", buckets: ["active"] },
  { value: "completed", label: "Completed", buckets: ["completed", "missed"] },
]

const DATE_TIME_FORMATTER = new Intl.DateTimeFormat("en-US", {
  dateStyle: "medium",
  timeStyle: "short",
})

function formatWindow(assignment: BetaReadAssignment) {
  return `${DATE_TIME_FORMATTER.format(new Date(assignment.starts_at))} – ${DATE_TIME_FORMATTER.format(new Date(assignment.expires_at))}`
}

function historyOutcome(assignment: BetaReadAssignment) {
  if (assignment.completed_at) return `Completed ${DATE_TIME_FORMATTER.format(new Date(assignment.completed_at))}`
  if (assignment.state === "disqualified") return "Requirements were not met before the deadline"
  if (assignment.view_bucket === "missed") return "Deadline missed"
  return "Completion is still being processed"
}

function primaryActionLabel(assignment: BetaReadAssignment) {
  return assignment.primary_action === "View" ? "Open project" : assignment.primary_action
}

export default function BetaReadsPage() {
  const router = useRouter()
  const [view, setView] = useState<AssignmentView>("in_progress")
  const [selectedAssignmentId, setSelectedAssignmentId] = useState<string | null>(null)
  const [pendingId, setPendingId] = useState<string | null>(null)
  const [actionError, setActionError] = useState(false)
  const selectedView = VIEW_OPTIONS.find((option) => option.value === view) ?? VIEW_OPTIONS[1]
  const listQueries = useQueries({
    queries: selectedView.buckets.map((bucket) => ({
      queryKey: asQueryKey(`reader:beta-reads:${bucket}`),
      queryFn: () => readerApi.listBetaReads(bucket),
      staleTime: 12_000,
    })),
  })
  const items = useMemo(
    () => listQueries.flatMap((query) => (query.data as BetaReadAssignment[] | undefined) ?? []),
    [listQueries],
  )
  const selectedAssignment = items.find((assignment) => assignment.id === selectedAssignmentId) ?? null
  const shouldLoadDetail = Boolean(
    selectedAssignment
    && selectedAssignment.view_bucket !== "completed"
    && selectedAssignment.view_bucket !== "missed",
  )
  const detailQuery = useQuery<BetaReadAssignmentDetail>({
    queryKey: asQueryKey(`reader:beta-reads:detail:${selectedAssignmentId ?? "none"}`),
    queryFn: () => betaReadsApi.getMineDetail(selectedAssignmentId as string),
    enabled: shouldLoadDetail,
    staleTime: 12_000,
  })
  const loading = listQueries.some((query) => query.isLoading)
  const isError = listQueries.some((query) => query.isError)

  async function refreshLists() {
    await Promise.all(listQueries.map((query) => query.refetch()))
  }

  async function handlePrimaryAction(assignment: BetaReadAssignment) {
    setPendingId(assignment.id)
    setActionError(false)
    try {
      if (assignment.primary_action === "Start") {
        await readerApi.startBetaRead(assignment.id)
        await refreshLists()
        router.push(betaReadPrimaryHref(assignment) as Route)
        return
      }
      if (assignment.primary_action === "Continue" || assignment.primary_action === "View") {
        router.push(betaReadPrimaryHref(assignment) as Route)
        return
      }
      router.push(`/${assignment.book_id}/beta-feedback` as Route)
    } catch {
      setActionError(true)
    } finally {
      setPendingId(null)
    }
  }

  function selectView(nextView: AssignmentView) {
    setView(nextView)
    setSelectedAssignmentId(null)
  }

  return (
    <WorkspacePage className="min-h-0 bg-transparent">
      <div className="px-4 pb-12 sm:px-0">
        <WorkspaceHeader
          eyebrow="Beta Reads"
          title="Reading assignments"
          description="See what is assigned, what needs attention now, and what has already closed."
        />

        <div className="mt-6 border-b border-[rgba(var(--border),0.9)]" role="tablist" aria-label="Assignment status">
          <div className="flex gap-6 overflow-x-auto">
            {VIEW_OPTIONS.map((option) => (
              <button
                key={option.value}
                type="button"
                role="tab"
                aria-selected={view === option.value}
                onClick={() => selectView(option.value)}
                className={`shrink-0 border-b-2 px-1 pb-3 text-sm font-semibold transition ${
                  view === option.value
                    ? "border-[rgb(var(--accent))] text-[rgb(var(--foreground))]"
                    : "border-transparent text-[rgb(var(--muted-foreground))] hover:text-[rgb(var(--foreground))]"
                }`}
              >
                {option.label}
              </button>
            ))}
          </div>
        </div>

        {isError ? (
          <div role="alert" className="mt-5 flex flex-wrap items-center justify-between gap-3 border border-rose-300/50 bg-rose-50 px-4 py-3 text-sm text-rose-900 dark:bg-rose-950/20 dark:text-rose-100">
            <p>{items.length > 0 ? "Some assignments could not be refreshed. Showing the last loaded list." : "We could not load your beta reads right now."}</p>
            <button type="button" onClick={() => void refreshLists()} className="border border-current px-3 py-2 font-semibold hover:bg-black/[0.04] dark:hover:bg-white/[0.06]">
              Retry assignments
            </button>
          </div>
        ) : null}
        {actionError ? (
          <p role="alert" className="mt-4 border-l-2 border-rose-500 pl-3 text-sm text-rose-800 dark:text-rose-200">
            We could not confirm that action. Refresh assignments before trying again.
          </p>
        ) : null}

        <section className="mt-5" aria-label={`${selectedView.label} assignments`}>
          {loading ? (
            <WorkspaceEmptyState title="Loading assignments" body="Syncing deadlines and reading progress." />
          ) : isError && items.length === 0 ? (
            <WorkspaceEmptyState title="Assignments unavailable" body="The assignment list did not load, so it is not being shown as empty." />
          ) : items.length === 0 ? (
            <WorkspaceEmptyState
              title={`No ${selectedView.label.toLowerCase()} assignments`}
              body={view === "completed" ? "Completed and missed assignments will appear here." : "New author assignments will appear here with their deadline and requirements."}
            />
          ) : (
            <div className="border border-[rgba(var(--border),0.9)] bg-[rgba(255,255,255,0.55)] dark:bg-[rgba(255,255,255,0.02)]">
              {items.map((assignment) => {
                const selected = assignment.id === selectedAssignmentId
                const urgent = betaReadIsUrgent(assignment.expires_at) && assignment.view_bucket !== "completed"
                return (
                  <article key={assignment.id} className="border-b border-[rgba(var(--border),0.75)] last:border-b-0">
                    <div className="grid gap-4 px-4 py-4 sm:px-5 lg:grid-cols-[minmax(0,1fr)_12rem_auto] lg:items-center">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                          <h2 className="truncate text-base font-semibold text-[rgb(var(--foreground))]">{assignment.book_title}</h2>
                          <span className="text-xs text-[rgb(var(--muted-foreground))]">by {assignment.author_name}</span>
                        </div>
                        <p className="mt-1 text-sm text-[rgb(var(--foreground))]">{assignment.task_label}</p>
                        <p className={`mt-1 text-xs ${urgent ? "text-rose-600 dark:text-rose-300" : "text-[rgb(var(--muted-foreground))]"}`}>
                          {view === "completed" ? historyOutcome(assignment) : betaReadDeadlineLabel(assignment.expires_at)}
                        </p>
                      </div>

                      <div>
                        <div className="flex items-center justify-between gap-3 text-xs">
                          <span className="font-medium text-[rgb(var(--foreground))]">{assignment.status_label}</span>
                          <span className="text-[rgb(var(--muted-foreground))]">{Math.round(assignment.progress_pct)}%</span>
                        </div>
                        <div className="mt-2 h-1.5 overflow-hidden bg-[rgba(var(--border),0.65)]">
                          <div className={`h-full ${urgent ? "bg-rose-500" : "bg-[rgb(var(--accent))]"}`} style={{ width: `${Math.max(0, Math.min(100, Math.round(assignment.progress_pct)))}%` }} />
                        </div>
                      </div>

                      <div className="flex flex-wrap gap-2 lg:justify-end">
                        <button type="button" onClick={() => setSelectedAssignmentId(selected ? null : assignment.id)} className="border border-[rgba(var(--border),0.9)] px-3 py-2 text-xs font-semibold text-[rgb(var(--foreground))] hover:bg-[rgba(var(--border),0.14)]">
                          {selected ? "Hide details" : "View details"}
                        </button>
                        <button type="button" onClick={() => void handlePrimaryAction(assignment)} disabled={pendingId === assignment.id} className="bg-[rgb(var(--accent))] px-4 py-2 text-xs font-semibold text-white dark:text-[#08110f] hover:opacity-90 disabled:opacity-50">
                          {pendingId === assignment.id ? "Working…" : primaryActionLabel(assignment)}
                        </button>
                      </div>
                    </div>

                    {selected ? (
                      <AssignmentDetails
                        assignment={assignment}
                        detail={detailQuery.data ?? null}
                        detailLoading={shouldLoadDetail && detailQuery.isFetching}
                        detailError={detailQuery.isError}
                        onRetryDetails={() => void detailQuery.refetch()}
                        onOpenNotes={() => router.push(`/${assignment.book_id}/notes` as Route)}
                        onSubmitFeedback={() => router.push(`/${assignment.book_id}/beta-feedback` as Route)}
                      />
                    ) : null}
                  </article>
                )
              })}
            </div>
          )}
        </section>
      </div>
    </WorkspacePage>
  )
}

function AssignmentDetails({ assignment, detail, detailLoading, detailError, onRetryDetails, onOpenNotes, onSubmitFeedback }: { assignment: BetaReadAssignment; detail: BetaReadAssignmentDetail | null; detailLoading: boolean; detailError: boolean; onRetryDetails: () => void; onOpenNotes: () => void; onSubmitFeedback: () => void }) {
  const requirementLines = betaReadRequirementLines(assignment)
  const authorQuestions = detail?.author_questions ?? []
  const missedWarning = betaReadMissedWarning(assignment)
  const isHistory = assignment.view_bucket === "completed" || assignment.view_bucket === "missed"
  return (
    <div className="border-t border-[rgba(var(--border),0.75)] bg-[rgba(var(--border),0.08)] px-4 py-5 sm:px-5">
      <dl className="grid gap-x-8 gap-y-4 text-sm sm:grid-cols-2 lg:grid-cols-3">
        <div><dt className="text-xs font-medium text-[rgb(var(--muted-foreground))]">Reading window</dt><dd className="mt-1 text-[rgb(var(--foreground))]">{formatWindow(assignment)}</dd></div>
        <div><dt className="text-xs font-medium text-[rgb(var(--muted-foreground))]">Deadline</dt><dd className="mt-1 text-[rgb(var(--foreground))]">{betaReadDeadlineDetail(assignment.expires_at)}</dd></div>
        <div><dt className="text-xs font-medium text-[rgb(var(--muted-foreground))]">Progress</dt><dd className="mt-1 text-[rgb(var(--foreground))]">{betaReadProgressLabel(assignment)}</dd></div>
      </dl>

      {isHistory ? (
        <div className="mt-5">
          <h3 className="text-sm font-semibold text-[rgb(var(--foreground))]">Outcome</h3>
          <p className="mt-1 text-sm text-[rgb(var(--muted-foreground))]">{historyOutcome(assignment)}</p>
          {assignment.submitted_at ? <p className="mt-1 text-sm text-[rgb(var(--muted-foreground))]">Feedback submitted {DATE_TIME_FORMATTER.format(new Date(assignment.submitted_at))}</p> : null}
          {missedWarning ? <p className="mt-3 border-l-2 border-amber-500 pl-3 text-sm text-amber-800 dark:text-amber-200">{missedWarning}</p> : null}
        </div>
      ) : (
        <div className="mt-5 grid gap-6 lg:grid-cols-2">
          <div>
            <h3 className="text-sm font-semibold text-[rgb(var(--foreground))]">Requirements</h3>
            <ul className="mt-2 space-y-1 text-sm text-[rgb(var(--muted-foreground))]">{requirementLines.map((line) => <li key={line}>{line}</li>)}</ul>
            <p className="mt-2 text-sm text-[rgb(var(--muted-foreground))]">{assignment.require_final_feedback ? "Require final feedback before completion" : "Final feedback is optional"}</p>
          </div>
          <div>
            <h3 className="text-sm font-semibold text-[rgb(var(--foreground))]">Author questions</h3>
            {detailError ? (
              <div role="alert" className="mt-2 border-l-2 border-rose-500 pl-3 text-sm text-rose-800 dark:text-rose-200">
                <p>{authorQuestions.length > 0 ? "Questions could not be refreshed. Showing the last loaded questions." : "We could not load the author questions."}</p>
                <button type="button" onClick={onRetryDetails} className="mt-2 border border-current px-2.5 py-1.5 font-semibold">Retry questions</button>
              </div>
            ) : detailLoading ? (
              <p className="mt-2 text-sm text-[rgb(var(--muted-foreground))]">Loading questions…</p>
            ) : authorQuestions.length ? (
              <ul className="mt-2 space-y-1 text-sm text-[rgb(var(--muted-foreground))]">{authorQuestions.map((question) => <li key={question.id}>{question.prompt}</li>)}</ul>
            ) : (
              <p className="mt-2 text-sm text-[rgb(var(--muted-foreground))]">No additional questions.</p>
            )}
          </div>
        </div>
      )}

      <div className="mt-5 flex flex-wrap gap-2">
        <button type="button" onClick={onOpenNotes} className="border border-[rgba(var(--border),0.9)] px-3 py-2 text-xs font-semibold text-[rgb(var(--foreground))]">Open notes</button>
        {!isHistory ? <button type="button" onClick={onSubmitFeedback} className="border border-[rgba(var(--border),0.9)] px-3 py-2 text-xs font-semibold text-[rgb(var(--foreground))]">Submit feedback</button> : null}
      </div>
    </div>
  )
}
