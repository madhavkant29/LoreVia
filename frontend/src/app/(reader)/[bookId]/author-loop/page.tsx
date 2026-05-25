"use client"

import { useMemo, useState } from "react"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import dynamic from "next/dynamic"
import Link from "next/link"
import { useParams } from "next/navigation"

import { betaReadsApi } from "@/lib/api/betaReads"
import { booksApi } from "@/lib/api/books"
import { useBookDetail } from "@/lib/hooks/useBookDetail"
import { asQueryKey, bookCacheKey } from "@/lib/query/cacheKeys"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import { buildAuthorLoopIssueCards, buildAuthorLoopSteps, buildCharacterReviewStats } from "@/lib/utils/authorLoop"
import { applyRevisionBoardState, buildRevisionTask, todayDateKey } from "@/lib/utils/revisionIntelligence"
import type { BetaReadAssignment, BetaReadAssignmentDetail, BetaReadFeedbackItem } from "@/types/betaRead"
import type { Book, GoalCalendarItem, WriterWorkspace } from "@/types/book"
import type { Character } from "@/types/character"

const AuthorToolsNav = dynamic(
  () => import("@/components/layout/AuthorToolsNav").then((module) => module.AuthorToolsNav),
  {
    ssr: false,
    loading: () => <div className="rounded-md border border-white/[0.065] bg-[#0d141c] p-4" />,
  }
)

const UploadModal = dynamic(
  () => import("@/components/modals/UploadModal").then((module) => module.UploadModal),
  {
    ssr: false,
    loading: () => <div className="rounded-md border border-white/[0.065] bg-[#0d141c] p-4" />,
  }
)

function deadlineFromWindow(windowDays: number) {
  const date = new Date()
  date.setDate(date.getDate() + windowDays)
  return date.toISOString().slice(0, 10)
}

function parseDeadlineWindow(deadline: string) {
  const target = new Date(`${deadline}T12:00:00`)
  if (Number.isNaN(target.getTime())) return null
  const current = new Date()
  current.setHours(12, 0, 0, 0)
  const diffMs = target.getTime() - current.getTime()
  const diffDays = Math.ceil(diffMs / 86_400_000)
  if (diffDays < 3 || diffDays > 7) return null
  return diffDays
}

function taskExists(goalCalendar: GoalCalendarItem[], taskId: string) {
  return goalCalendar.some((item) => item.id === taskId)
}

function pushGoalTask(goalCalendar: GoalCalendarItem[], task: GoalCalendarItem) {
  return taskExists(goalCalendar, task.id) ? goalCalendar : [task, ...goalCalendar]
}

function toneClasses(isDark: boolean, tone: "ready" | "working" | "attention") {
  if (tone === "ready") return isDark ? "border-emerald-400/25 bg-emerald-400/10 text-emerald-200" : "border-emerald-200 bg-emerald-50 text-emerald-700"
  if (tone === "attention") return isDark ? "border-amber-400/25 bg-amber-400/10 text-amber-200" : "border-amber-200 bg-amber-50 text-amber-700"
  return isDark ? "border-sky-400/20 bg-sky-400/10 text-sky-200" : "border-sky-200 bg-sky-50 text-sky-700"
}

function severityClasses(isDark: boolean, severity: "high" | "medium" | "low") {
  if (severity === "high") return isDark ? "bg-rose-500/12 text-rose-200" : "bg-rose-50 text-rose-700"
  if (severity === "medium") return isDark ? "bg-amber-500/12 text-amber-200" : "bg-amber-50 text-amber-700"
  return isDark ? "bg-emerald-500/12 text-emerald-200" : "bg-emerald-50 text-emerald-700"
}

function feedbackStatusClasses(isDark: boolean, status: string) {
  if (status === "resolved") return isDark ? "bg-emerald-500/12 text-emerald-200" : "bg-emerald-50 text-emerald-700"
  if (status === "task_created") return isDark ? "bg-violet-500/12 text-violet-200" : "bg-violet-50 text-violet-700"
  if (status === "archived") return isDark ? "bg-slate-500/12 text-slate-300" : "bg-slate-100 text-slate-600"
  return isDark ? "bg-amber-500/12 text-amber-200" : "bg-amber-50 text-amber-700"
}

export default function AuthorLoopPage() {
  const { bookId } = useParams<{ bookId: string }>()
  const { theme } = usePreferencesStore()
  const isDark = theme === "dark"
  const queryClient = useQueryClient()
  const writerWorkspaceKey = asQueryKey(bookCacheKey(bookId, "writer-workspace"))

  const [statusMessage, setStatusMessage] = useState<string | null>(null)
  const [showUploadWorkspace, setShowUploadWorkspace] = useState(false)
  const [readerEmail, setReaderEmail] = useState("")
  const [scopeKind, setScopeKind] = useState("full_book")
  const [chapterStart, setChapterStart] = useState("1")
  const [chapterEnd, setChapterEnd] = useState("3")
  const [deadline, setDeadline] = useState(deadlineFromWindow(7))
  const [authorQuestions, setAuthorQuestions] = useState("Where did you get confused?\nWhich scene stayed with you?\nWhat felt under-explained?")
  const [creatingAssignment, setCreatingAssignment] = useState(false)
  const [selectedAssignmentId, setSelectedAssignmentId] = useState<string | null>(null)
  const [savingIssueId, setSavingIssueId] = useState<string | null>(null)
  const [savingFeedbackId, setSavingFeedbackId] = useState<string | null>(null)

  const { data: book = null } = useBookDetail(bookId, {
    refetchInterval: (query) => {
      const currentBook = query.state.data as Book | undefined
      const canPoll = typeof document === "undefined" || document.visibilityState === "visible"
      return canPoll && currentBook && currentBook.status !== "ready" ? 4_000 : false
    },
    refetchIntervalInBackground: false,
  })
  const { data: characters = [] } = useQuery<Character[]>({
    queryKey: asQueryKey(bookCacheKey(bookId, "characters")),
    queryFn: () => booksApi.getCharacters(bookId),
  })
  const { data: storyHealth = null } = useQuery({
    queryKey: asQueryKey(bookCacheKey(bookId, "story-health")),
    queryFn: () => booksApi.getStoryHealth(bookId),
  })
  const { data: chapterReports = [] } = useQuery({
    queryKey: asQueryKey(bookCacheKey(bookId, "chapter-reports:12")),
    queryFn: () => booksApi.getChapterReports(bookId, 12),
  })
  const { data: revisionIntelligence = null } = useQuery({
    queryKey: asQueryKey(bookCacheKey(bookId, "revision-intelligence")),
    queryFn: () => booksApi.getRevisionIntelligence(bookId),
  })
  const { data: writerWorkspace = null } = useQuery<WriterWorkspace | null>({
    queryKey: writerWorkspaceKey,
    queryFn: () => booksApi.getWriterWorkspace(bookId),
  })
  const { data: assignments = [], refetch: refetchAssignments } = useQuery<BetaReadAssignment[]>({
    queryKey: asQueryKey(`author-loop:${bookId}:beta-assignments`),
    queryFn: () => betaReadsApi.listBookAssignments(bookId).catch(() => []),
  })

  const activeAssignmentId = selectedAssignmentId ?? assignments[0]?.id ?? null
  const { data: selectedAssignment = null, refetch: refetchAssignmentDetail } = useQuery<BetaReadAssignmentDetail | null>({
    queryKey: activeAssignmentId ? asQueryKey(`author-loop:${bookId}:beta-detail:${activeAssignmentId}`) : ["author-loop:no-assignment"],
    queryFn: () => betaReadsApi.getBookAssignmentDetail(bookId, activeAssignmentId as string).catch(() => null),
    enabled: Boolean(activeAssignmentId),
  })

  const issueCards = useMemo(
    () => buildAuthorLoopIssueCards(revisionIntelligence, chapterReports, writerWorkspace),
    [chapterReports, revisionIntelligence, writerWorkspace]
  )
  const characterStats = useMemo(() => buildCharacterReviewStats(characters), [characters])
  const steps = useMemo(
    () => buildAuthorLoopSteps({
      book,
      characters,
      storyHealth,
      issueCards,
      assignments,
      selectedAssignment,
    }),
    [assignments, book, characters, issueCards, selectedAssignment, storyHealth]
  )
  const selectedFeedbackItems = selectedAssignment?.feedback_items ?? []
  const latestCharacters = characters.slice(0, 6)

  const saveWorkspacePatch = async (patch: Partial<WriterWorkspace>) => {
    const updated = await booksApi.updateWriterWorkspace(bookId, patch)
    queryClient.setQueryData(writerWorkspaceKey, updated)
    return updated
  }

  const handleIssueStatus = async (issueId: string, status: "ignored" | "task_created") => {
    if (!writerWorkspace) return
    setSavingIssueId(issueId)
    try {
      let nextBoard = writerWorkspace.revision_board
      let nextGoalCalendar = writerWorkspace.goal_calendar
      if (status === "task_created") {
        const issue = issueCards.find((item) => item.id === issueId)
        if (!issue) return
        const taskId = `revision-task:${issueId}`
        nextGoalCalendar = pushGoalTask(nextGoalCalendar, {
          id: taskId,
          title: issue.title,
          due_date: todayDateKey(),
          quota_value: 1,
          quota_unit: "tasks",
          completed: false,
        })
        nextBoard = applyRevisionBoardState(nextBoard, issueId, {
          status,
          task_id: taskId,
          updated_at: new Date().toISOString(),
        })
      } else {
        nextBoard = applyRevisionBoardState(nextBoard, issueId, {
          status,
          updated_at: new Date().toISOString(),
        })
      }
      await saveWorkspacePatch({ revision_board: nextBoard, goal_calendar: nextGoalCalendar })
      setStatusMessage(status === "task_created" ? "Issue converted into a revision task." : "Issue dismissed from the active queue.")
    } catch {
      setStatusMessage("Could not update that issue right now.")
    } finally {
      setSavingIssueId(null)
    }
  }

  const handleCreateAssignment = async () => {
    const windowDays = parseDeadlineWindow(deadline)
    if (!readerEmail.trim()) {
      setStatusMessage("Add a beta reader email first.")
      return
    }
    if (!windowDays) {
      setStatusMessage("Choose a deadline between 3 and 7 days from today.")
      return
    }
    setCreatingAssignment(true)
    try {
      const created = await betaReadsApi.createAssignment(bookId, {
        readerEmail: readerEmail.trim(),
        taskLabel: scopeKind === "full_book" ? "Focused beta read" : `Scoped beta read: chapters ${chapterStart}-${chapterEnd}`,
        scopeKind,
        chapterStart: scopeKind === "full_book" ? null : Number(chapterStart || "1"),
        chapterEnd: scopeKind === "full_book" ? null : Number(chapterEnd || chapterStart || "1"),
        windowDays,
        requiredProgressPct: 100,
        requiredCommentCount: 0,
        requiredFeedbackItemCount: 1,
        requireFinalFeedback: true,
        authorQuestions: authorQuestions.split(/\r?\n/).map((line) => line.trim()).filter(Boolean),
      })
      await refetchAssignments()
      setSelectedAssignmentId(created.id)
      await refetchAssignmentDetail()
      setReaderEmail("")
      setStatusMessage("Beta reader invite sent with scoped access.")
    } catch {
      setStatusMessage("Could not send that beta reader invite.")
    } finally {
      setCreatingAssignment(false)
    }
  }

  const handleFeedbackStatus = async (item: BetaReadFeedbackItem, authorStatus: "resolved" | "archived" | "task_created") => {
    if (!selectedAssignment || !writerWorkspace) return
    setSavingFeedbackId(item.id)
    try {
      let authorTaskId: string | null = null
      if (authorStatus === "task_created") {
        authorTaskId = `beta-feedback:${item.id}`
        const title = item.chapter_number ? `Review beta feedback from chapter ${item.chapter_number}` : "Review beta feedback"
        const task = buildRevisionTask(
          {
            id: authorTaskId,
            category: "beta_feedback",
            title,
            description: item.body || item.anchor_text || item.question_prompt || "Follow up on beta-reader feedback.",
            severity: "medium",
            status: "pending",
          },
          todayDateKey()
        )
        const nextGoalCalendar = pushGoalTask(writerWorkspace.goal_calendar, task)
        await saveWorkspacePatch({ goal_calendar: nextGoalCalendar })
      }
      await betaReadsApi.updateBookFeedbackItem(bookId, selectedAssignment.assignment.id, item.id, {
        authorStatus,
        authorTaskId,
      })
      await refetchAssignmentDetail()
      setStatusMessage(
        authorStatus === "resolved"
          ? "Feedback marked resolved."
          : authorStatus === "archived"
            ? "Feedback archived."
            : "Feedback converted into a revision task."
      )
    } catch {
      setStatusMessage("Could not update that feedback item.")
    } finally {
      setSavingFeedbackId(null)
    }
  }

  return (
    <div className={`min-h-screen ${isDark ? "bg-[#070b10] text-slate-100" : "bg-[#f7f7fb] text-slate-950"}`}>
      <div className="mx-auto grid max-w-[94rem] gap-5 px-4 pb-28 pt-5 sm:px-6 lg:grid-cols-[18rem_minmax(0,1fr)] lg:px-8">
        <div className="hidden lg:block lg:sticky lg:top-5 lg:self-start">
          <AuthorToolsNav
            bookId={bookId}
            active="author-loop"
            isDark={isDark}
            bookData={book}
            title="Author loop"
            description="Move from manuscript upload to beta feedback without losing citations, edits, or trust."
            mode={book?.mode ?? "author"}
            variant="rail"
          />
        </div>

        <main className="min-w-0 space-y-5">
          <section className={`rounded-md border p-6 ${isDark ? "border-white/[0.065] bg-[#0d141c]" : "border-slate-200/70 bg-white"}`}>
            <p className={`text-xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-amber-300" : "text-amber-700"}`}>Author Loop</p>
            <div className="mt-3 flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
              <div>
                <h1 className={`text-3xl font-semibold ${isDark ? "text-white" : "text-slate-950"}`}>{book?.title ?? "Manuscript"} author loop</h1>
                <p className={`mt-2 max-w-3xl text-sm leading-6 ${isDark ? "text-slate-400" : "text-slate-500"}`}>
                  Upload privately, build the character bible, run cited continuity checks, invite a scoped beta reader, and turn feedback into revision work without juggling six separate tabs.
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <Link href={`/${bookId}/characters`} className={`rounded-full px-4 py-2 text-sm font-semibold ${isDark ? "bg-white/10 text-slate-100" : "bg-slate-100 text-slate-800"}`}>Character bible</Link>
                <Link href={`/${bookId}/beta-feedback`} className={`rounded-full px-4 py-2 text-sm font-semibold ${isDark ? "bg-white/10 text-slate-100" : "bg-slate-100 text-slate-800"}`}>Beta feedback</Link>
                <Link href={`/${bookId}/editorial-review`} className={`rounded-full px-4 py-2 text-sm font-semibold ${isDark ? "bg-violet-500 text-white" : "bg-slate-950 text-white"}`}>Editorial review</Link>
              </div>
            </div>
            {statusMessage ? <p className={`mt-4 text-sm ${isDark ? "text-slate-300" : "text-slate-600"}`}>{statusMessage}</p> : null}
          </section>

          <section className="grid gap-3 xl:grid-cols-6">
            {steps.map((step) => (
              <div key={step.id} className={`rounded-md border p-4 ${toneClasses(isDark, step.tone)}`}>
                <p className="text-[11px] font-semibold uppercase tracking-[0.22em]">{step.label}</p>
                <p className="mt-2 text-sm leading-6">{step.detail}</p>
              </div>
            ))}
          </section>

          <section className="grid gap-5 xl:grid-cols-[minmax(0,0.95fr)_minmax(0,1.05fr)]">
            <div className={`rounded-md border p-5 ${isDark ? "border-white/[0.065] bg-[#0d141c]" : "border-slate-200/70 bg-white"}`}>
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className={`text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-slate-400"}`}>1. Upload manuscript</p>
                  <h2 className={`mt-2 text-lg font-semibold ${isDark ? "text-white" : "text-slate-900"}`}>Clean, private intake</h2>
                </div>
                <button
                  type="button"
                  onClick={() => setShowUploadWorkspace((current) => !current)}
                  className={`rounded-md px-4 py-2 text-sm font-semibold ${isDark ? "bg-white/10 text-slate-100" : "bg-slate-900 text-white"}`}
                >
                  {showUploadWorkspace ? "Hide upload tools" : "Open upload tools"}
                </button>
              </div>
              <div className={`mt-4 rounded-md border p-4 ${isDark ? "border-white/[0.06] bg-[#101720]" : "border-slate-200 bg-slate-50"}`}>
                <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-slate-900"}`}>Supported formats</p>
                <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-300" : "text-slate-600"}`}>DOCX, PDF, EPUB, TXT, and Markdown only. This step stays private, shows processing status, and does not expose public sharing.</p>
                <div className="mt-4 grid gap-3 sm:grid-cols-2">
                  <div className={`rounded-md border p-3 ${isDark ? "border-white/[0.06] bg-black/20" : "border-slate-200 bg-white"}`}>
                    <p className={`text-[11px] font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-slate-400"}`}>Privacy</p>
                    <p className={`mt-2 text-sm ${isDark ? "text-slate-300" : "text-slate-600"}`}>Your manuscript is processed inside your workspace. Beta readers only get chapter-scoped access later if you explicitly invite them.</p>
                  </div>
                  <div className={`rounded-md border p-3 ${isDark ? "border-white/[0.06] bg-black/20" : "border-slate-200 bg-white"}`}>
                    <p className={`text-[11px] font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-slate-400"}`}>Processing</p>
                    <p className={`mt-2 text-sm ${isDark ? "text-slate-300" : "text-slate-600"}`}>
                      {book?.processing?.stage || book?.processing?.status
                        ? `${book.processing.stage ?? book.processing.status}${typeof book.processing.progress_pct === "number" ? ` / ${Math.round(book.processing.progress_pct)}%` : ""}`
                        : book?.status === "ready"
                          ? "Ready for continuity review."
                          : "Upload a manuscript to start extraction and continuity checks."}
                    </p>
                  </div>
                </div>
              </div>
              {showUploadWorkspace ? (
                <div className="mt-5">
                  <UploadModal onClose={() => setShowUploadWorkspace(false)} initialMode="author" initialExistingBookId={bookId} presentation="inline" />
                </div>
              ) : null}
            </div>

            <div className={`rounded-md border p-5 ${isDark ? "border-white/[0.065] bg-[#0d141c]" : "border-slate-200/70 bg-white"}`}>
              <p className={`text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-slate-400"}`}>2. Build character bible</p>
              <div className="mt-3 grid gap-3 sm:grid-cols-3">
                <MetricCard isDark={isDark} label="Profiles" value={String(characterStats.totalCharacters)} />
                <MetricCard isDark={isDark} label="Possible duplicates" value={String(characterStats.duplicateCount)} />
                <MetricCard isDark={isDark} label="Needs review" value={String(characterStats.needsReviewCount)} />
              </div>
              <div className="mt-4 space-y-3">
                {latestCharacters.length > 0 ? latestCharacters.map((character) => (
                  <div key={character.id} className={`rounded-md border p-3 ${isDark ? "border-white/[0.06] bg-[#101720]" : "border-slate-200 bg-slate-50"}`}>
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-slate-900"}`}>{character.name}</p>
                        <p className={`mt-1 text-xs ${isDark ? "text-slate-500" : "text-slate-500"}`}>
                          First cited in chapter {character.first_chapter}
                          {character.aliases.length > 0 ? ` / aliases: ${character.aliases.join(", ")}` : ""}
                        </p>
                      </div>
                      <span className={`rounded-full px-2 py-1 text-[11px] font-semibold ${character.description ? (isDark ? "bg-emerald-500/12 text-emerald-200" : "bg-emerald-50 text-emerald-700") : (isDark ? "bg-amber-500/12 text-amber-200" : "bg-amber-50 text-amber-700")}`}>
                        {character.description ? "Profile ready" : "Needs editing"}
                      </span>
                    </div>
                    <p className={`mt-3 text-sm leading-6 ${isDark ? "text-slate-300" : "text-slate-600"}`}>{character.description || "Open this profile to edit the extracted summary, resolve aliases, or mark the extraction as incorrect."}</p>
                  </div>
                )) : (
                  <div className={`rounded-md border border-dashed p-4 text-sm ${isDark ? "border-white/[0.08] text-slate-500" : "border-slate-200 text-slate-400"}`}>Character extraction starts after the manuscript is processed.</div>
                )}
              </div>
              <div className="mt-4">
                <Link href={`/${bookId}/characters`} className={`text-sm font-semibold ${isDark ? "text-violet-300" : "text-violet-700"}`}>
                  Open character bible to edit profiles, merge duplicates, or remove bad extraction
                </Link>
              </div>
            </div>
          </section>

          <section className={`rounded-md border p-5 ${isDark ? "border-white/[0.065] bg-[#0d141c]" : "border-slate-200/70 bg-white"}`}>
            <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
              <div>
                <p className={`text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-slate-400"}`}>3. Run continuity scan</p>
                <h2 className={`mt-2 text-lg font-semibold ${isDark ? "text-white" : "text-slate-900"}`}>Cited contradictions and gaps</h2>
                <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-300" : "text-slate-600"}`}>
                  LoreVia prioritizes contradictions, dropped threads, timeline drift, character-state changes, and relationship inconsistencies. It cites chapters and avoids overclaiming when the scan is still uncertain.
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <MetricPill isDark={isDark} label="Story health" value={storyHealth ? `${storyHealth.score}` : "Pending"} />
                <MetricPill isDark={isDark} label="Active issues" value={String(issueCards.length)} />
                <MetricPill isDark={isDark} label="Queued tasks" value={String(writerWorkspace?.goal_calendar.length ?? 0)} />
              </div>
            </div>
            <div className="mt-5 space-y-3">
              {issueCards.length > 0 ? issueCards.slice(0, 8).map((issue) => (
                <div key={issue.id} className={`rounded-md border p-4 ${isDark ? "border-white/[0.06] bg-[#101720]" : "border-slate-200 bg-slate-50"}`}>
                  <div className="flex flex-wrap items-center gap-2">
                    <span className={`rounded-full px-2 py-1 text-[11px] font-semibold ${severityClasses(isDark, issue.severity)}`}>{issue.severity}</span>
                    <span className={`text-[11px] ${isDark ? "text-slate-500" : "text-slate-500"}`}>{issue.sourceLabel}</span>
                    <span className={`text-[11px] ${isDark ? "text-slate-500" : "text-slate-500"}`}>{issue.citation}</span>
                    <span className={`rounded-full px-2 py-1 text-[11px] font-semibold ${isDark ? "bg-white/8 text-slate-300" : "bg-white text-slate-600"}`}>{issue.confidence}</span>
                  </div>
                  <div className="mt-3 grid gap-3 xl:grid-cols-[minmax(0,1fr)_14rem]">
                    <div>
                      <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-slate-900"}`}>{issue.title}</p>
                      <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-300" : "text-slate-600"}`}>{issue.explanation}</p>
                      <p className={`mt-3 text-sm ${isDark ? "text-violet-200" : "text-violet-700"}`}>Suggested fix: {issue.suggestedFix}</p>
                      {issue.affected.length > 0 ? (
                        <p className={`mt-3 text-xs ${isDark ? "text-slate-500" : "text-slate-500"}`}>Affected: {issue.affected.join(" / ")}</p>
                      ) : null}
                    </div>
                    <div className="space-y-2">
                      <button
                        type="button"
                        disabled={savingIssueId === issue.id}
                        onClick={() => void handleIssueStatus(issue.id, "task_created")}
                        className={`w-full rounded-md px-4 py-2 text-sm font-semibold ${isDark ? "bg-violet-500 text-white hover:bg-violet-400" : "bg-slate-950 text-white hover:bg-slate-800"} disabled:opacity-50`}
                      >
                        {savingIssueId === issue.id ? "Saving..." : "Convert to task"}
                      </button>
                      <button
                        type="button"
                        disabled={savingIssueId === issue.id}
                        onClick={() => void handleIssueStatus(issue.id, "ignored")}
                        className={`w-full rounded-md px-4 py-2 text-sm font-semibold ${isDark ? "bg-white/10 text-slate-100 hover:bg-white/15" : "bg-white text-slate-700 hover:bg-slate-100"} disabled:opacity-50`}
                      >
                        Dismiss
                      </button>
                    </div>
                  </div>
                </div>
              )) : (
                <div className={`rounded-md border border-dashed p-4 text-sm ${isDark ? "border-white/[0.08] text-slate-500" : "border-slate-200 text-slate-400"}`}>
                  The scan is still building. LoreVia will queue likely review targets instead of declaring the manuscript perfect too early.
                </div>
              )}
            </div>
          </section>

          <section className="grid gap-5 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
            <div className={`rounded-md border p-5 ${isDark ? "border-white/[0.065] bg-[#0d141c]" : "border-slate-200/70 bg-white"}`}>
              <p className={`text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-slate-400"}`}>5. Invite beta reader</p>
              <div className="mt-4 grid gap-3">
                <input
                  value={readerEmail}
                  onChange={(event) => setReaderEmail(event.target.value)}
                  placeholder="reader@example.com"
                  className={`h-11 rounded-md border px-3 text-sm outline-none transition ${isDark ? "border-white/[0.08] bg-[#101720] text-slate-100 placeholder:text-slate-600 focus:border-amber-400" : "border-slate-200 bg-white text-slate-900 placeholder:text-slate-400 focus:border-amber-400"}`}
                />
                <select
                  value={scopeKind}
                  onChange={(event) => setScopeKind(event.target.value)}
                  className={`h-11 rounded-md border px-3 text-sm outline-none transition ${isDark ? "border-white/[0.08] bg-[#101720] text-slate-100 focus:border-amber-400" : "border-slate-200 bg-white text-slate-900 focus:border-amber-400"}`}
                >
                  <option value="full_book">Full book</option>
                  <option value="chapter_range">Chapter range</option>
                </select>
                {scopeKind !== "full_book" ? (
                  <div className="grid gap-3 sm:grid-cols-2">
                    <input
                      type="number"
                      min="1"
                      value={chapterStart}
                      onChange={(event) => setChapterStart(event.target.value)}
                      placeholder="From chapter"
                      className={`h-11 rounded-md border px-3 text-sm outline-none transition ${isDark ? "border-white/[0.08] bg-[#101720] text-slate-100 focus:border-amber-400" : "border-slate-200 bg-white text-slate-900 focus:border-amber-400"}`}
                    />
                    <input
                      type="number"
                      min="1"
                      value={chapterEnd}
                      onChange={(event) => setChapterEnd(event.target.value)}
                      placeholder="Through chapter"
                      className={`h-11 rounded-md border px-3 text-sm outline-none transition ${isDark ? "border-white/[0.08] bg-[#101720] text-slate-100 focus:border-amber-400" : "border-slate-200 bg-white text-slate-900 focus:border-amber-400"}`}
                    />
                  </div>
                ) : null}
                <input
                  type="date"
                  value={deadline}
                  onChange={(event) => setDeadline(event.target.value)}
                  className={`h-11 rounded-md border px-3 text-sm outline-none transition ${isDark ? "border-white/[0.08] bg-[#101720] text-slate-100 focus:border-amber-400" : "border-slate-200 bg-white text-slate-900 focus:border-amber-400"}`}
                />
                <textarea
                  value={authorQuestions}
                  onChange={(event) => setAuthorQuestions(event.target.value)}
                  rows={5}
                  placeholder="One author prompt per line"
                  className={`rounded-md border px-3 py-3 text-sm outline-none transition ${isDark ? "border-white/[0.08] bg-[#101720] text-slate-100 placeholder:text-slate-600 focus:border-amber-400" : "border-slate-200 bg-white text-slate-900 placeholder:text-slate-400 focus:border-amber-400"}`}
                />
                <button
                  type="button"
                  onClick={() => void handleCreateAssignment()}
                  disabled={creatingAssignment}
                  className={`inline-flex h-11 items-center justify-center rounded-md px-4 text-sm font-semibold transition ${isDark ? "bg-amber-400 text-slate-950 hover:bg-amber-300 disabled:bg-amber-400/40" : "bg-amber-500 text-slate-950 hover:bg-amber-400 disabled:bg-amber-200"}`}
                >
                  {creatingAssignment ? "Sending invite..." : "Send beta invite"}
                </button>
              </div>
              <p className={`mt-3 text-xs leading-5 ${isDark ? "text-slate-500" : "text-slate-500"}`}>
                Beta readers get scoped access only. They cannot see unrelated manuscripts or edit author content.
              </p>
            </div>

            <div className={`rounded-md border p-5 ${isDark ? "border-white/[0.065] bg-[#0d141c]" : "border-slate-200/70 bg-white"}`}>
              <p className={`text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-slate-400"}`}>6. Collect scoped feedback</p>
              {assignments.length > 0 ? (
                <div className="mt-4 space-y-4">
                  <div className="flex flex-wrap gap-2">
                    {assignments.map((assignment) => (
                      <button
                        key={assignment.id}
                        type="button"
                        onClick={() => setSelectedAssignmentId(assignment.id)}
                        className={`rounded-full px-3 py-2 text-sm font-semibold transition ${
                          activeAssignmentId === assignment.id
                            ? isDark ? "bg-white text-slate-950" : "bg-slate-950 text-white"
                            : isDark ? "bg-white/10 text-slate-100 hover:bg-white/15" : "bg-slate-100 text-slate-700 hover:bg-slate-200"
                        }`}
                      >
                        {assignment.reader_email}
                      </button>
                    ))}
                  </div>
                  {selectedAssignment ? (
                    <>
                      <div className="grid gap-3 sm:grid-cols-4">
                        <MetricCard isDark={isDark} label="Feedback items" value={String(selectedAssignment.feedback_summary.feedback_item_count)} />
                        <MetricCard isDark={isDark} label="Confusing" value={String(selectedAssignment.feedback_summary.confusing_count)} />
                        <MetricCard isDark={isDark} label="Answers" value={String(selectedAssignment.feedback_summary.answer_count)} />
                        <MetricCard isDark={isDark} label="Favorites" value={String(selectedAssignment.feedback_summary.favorite_count)} />
                      </div>
                      <div className="space-y-3">
                        {selectedFeedbackItems.length > 0 ? selectedFeedbackItems.map((item) => (
                          <div key={item.id} className={`rounded-md border p-4 ${isDark ? "border-white/[0.06] bg-[#101720]" : "border-slate-200 bg-slate-50"}`}>
                            <div className="flex flex-wrap items-center gap-2">
                              <span className={`rounded-full px-2 py-1 text-[11px] font-semibold ${feedbackStatusClasses(isDark, item.author_status)}`}>{item.author_status.replace(/_/g, " ")}</span>
                              <span className={`text-[11px] ${isDark ? "text-slate-500" : "text-slate-500"}`}>
                                {item.chapter_number ? `Chapter ${item.chapter_number}` : "Book-wide"}
                              </span>
                              {item.question_prompt ? <span className={`text-[11px] ${isDark ? "text-slate-500" : "text-slate-500"}`}>Prompt-linked</span> : null}
                            </div>
                            <p className={`mt-3 text-sm font-semibold ${isDark ? "text-white" : "text-slate-900"}`}>{item.question_prompt || item.anchor_text || "Reader feedback"}</p>
                            {item.body ? <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-300" : "text-slate-600"}`}>{item.body}</p> : null}
                            {item.author_task_id ? <p className={`mt-2 text-xs ${isDark ? "text-violet-300" : "text-violet-700"}`}>Task: {item.author_task_id}</p> : null}
                            <div className="mt-4 flex flex-wrap gap-2">
                              <button
                                type="button"
                                disabled={savingFeedbackId === item.id}
                                onClick={() => void handleFeedbackStatus(item, "resolved")}
                                className={`rounded-md px-3 py-2 text-sm font-semibold ${isDark ? "bg-white/10 text-slate-100 hover:bg-white/15" : "bg-white text-slate-700 hover:bg-slate-100"} disabled:opacity-50`}
                              >
                                Resolve
                              </button>
                              <button
                                type="button"
                                disabled={savingFeedbackId === item.id}
                                onClick={() => void handleFeedbackStatus(item, "archived")}
                                className={`rounded-md px-3 py-2 text-sm font-semibold ${isDark ? "bg-white/10 text-slate-100 hover:bg-white/15" : "bg-white text-slate-700 hover:bg-slate-100"} disabled:opacity-50`}
                              >
                                Archive
                              </button>
                              <button
                                type="button"
                                disabled={savingFeedbackId === item.id}
                                onClick={() => void handleFeedbackStatus(item, "task_created")}
                                className={`rounded-md px-3 py-2 text-sm font-semibold ${isDark ? "bg-violet-500 text-white hover:bg-violet-400" : "bg-slate-950 text-white hover:bg-slate-800"} disabled:opacity-50`}
                              >
                                Convert to task
                              </button>
                            </div>
                          </div>
                        )) : (
                          <div className={`rounded-md border border-dashed p-4 text-sm ${isDark ? "border-white/[0.08] text-slate-500" : "border-slate-200 text-slate-400"}`}>
                            No scoped feedback has landed yet. Beta readers can comment, answer your prompts, and mark confusing sections from the beta workspace.
                          </div>
                        )}
                      </div>
                    </>
                  ) : null}
                </div>
              ) : (
                <div className={`mt-4 rounded-md border border-dashed p-4 text-sm ${isDark ? "border-white/[0.08] text-slate-500" : "border-slate-200 text-slate-400"}`}>
                  No beta reader invites yet. Create one here to start collecting chapter-scoped feedback.
                </div>
              )}
            </div>
          </section>
        </main>
      </div>
    </div>
  )
}

function MetricCard({ isDark, label, value }: { isDark: boolean; label: string; value: string }) {
  return (
    <div className={`rounded-md border p-3 ${isDark ? "border-white/[0.06] bg-[#101720]" : "border-slate-200 bg-slate-50"}`}>
      <p className={`text-[11px] font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-slate-400"}`}>{label}</p>
      <p className={`mt-2 text-xl font-semibold ${isDark ? "text-white" : "text-slate-900"}`}>{value}</p>
    </div>
  )
}

function MetricPill({ isDark, label, value }: { isDark: boolean; label: string; value: string }) {
  return (
    <div className={`rounded-full px-3 py-2 text-sm font-semibold ${isDark ? "bg-white/10 text-slate-100" : "bg-slate-100 text-slate-700"}`}>
      {label}: {value}
    </div>
  )
}
