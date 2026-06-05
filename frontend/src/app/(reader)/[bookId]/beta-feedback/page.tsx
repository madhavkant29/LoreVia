"use client"

import { useQuery } from "@tanstack/react-query"
import dynamic from "next/dynamic"
import { useEffect, useMemo, useState } from "react"
import type { ReactNode } from "react"
import { useParams } from "next/navigation"

import { WorkspaceFamilyHeader } from "@/components/reader/WorkspaceFamilyHeader"
import { betaReadsApi } from "@/lib/api/betaReads"
import { booksApi } from "@/lib/api/books"
import { asQueryKey, bookCacheKey } from "@/lib/query/cacheKeys"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import { formatFeedbackKindLabel, parseQuestionLines, selectPrimaryAssignment } from "@/lib/utils/betaRead"
import type { BetaReadAssignment, BetaReadAssignmentDetail } from "@/types/betaRead"
import type { Book } from "@/types/book"

const AuthorToolsNav = dynamic(
  () => import("@/components/layout/AuthorToolsNav").then((module) => module.AuthorToolsNav),
  {
    ssr: false,
    loading: () => <div className="rounded-md border border-white/[0.065] bg-[#0d141c] p-4" />,
  }
)

const FEEDBACK_KIND_OPTIONS = [
  { value: "chapter_comment", label: "Chapter comment", detail: "General comments on pacing, flow, or impact in a chapter." },
  { value: "scene_reaction", label: "Scene reaction", detail: "Quick emotional or craft reaction to a specific scene." },
  { value: "answer", label: "Answer question", detail: "Respond directly to one of the author's review prompts." },
  { value: "confusing", label: "Confusing part", detail: "Mark a moment that was hard to follow." },
  { value: "boring", label: "Boring part", detail: "Flag a section that dragged or lost momentum." },
  { value: "favorite", label: "Favorite moment", detail: "Capture what landed hardest or felt most memorable." },
] as const
const FINAL_RATING_OPTIONS = [5, 4.5, 4, 3.5, 3, 2.5, 2, 1.5, 1] as const

function StatPill({ label, value, isDark }: { label: string; value: string; isDark: boolean }) {
  return (
    <div className={`rounded-xl border px-3 py-2 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-slate-200 bg-slate-50"}`}>
      <p className={`text-3xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-slate-400"}`}>{label}</p>
      <p className={`mt-1 text-sm font-semibold ${isDark ? "text-white" : "text-slate-900"}`}>{value}</p>
    </div>
  )
}

function LabeledField({
  label,
  detail,
  isDark,
  children,
}: {
  label: string
  detail?: string
  isDark: boolean
  children: ReactNode
}) {
  return (
    <label className="grid gap-2">
      <span className={`text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-400" : "text-slate-500"}`}>{label}</span>
      {children}
      {detail ? <span className={`text-xs leading-5 ${isDark ? "text-slate-500" : "text-slate-500"}`}>{detail}</span> : null}
    </label>
  )
}

export default function BetaFeedbackPage() {
  const { bookId } = useParams<{ bookId: string }>()
  const { theme } = usePreferencesStore()
  const isDark = theme === "dark"
  const [status, setStatus] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [selectedAuthorAssignmentId, setSelectedAuthorAssignmentId] = useState<string | null>(null)

  const { data: book = null, isLoading: bookLoading } = useQuery<Book | null>({
    queryKey: asQueryKey(bookCacheKey(bookId, "detail")),
    queryFn: () => booksApi.get(bookId),
  })
  const {
    data: authorAssignments = [],
    isLoading: authorAssignmentsLoading,
    refetch: refetchAuthorAssignments,
  } = useQuery<BetaReadAssignment[]>({
    queryKey: asQueryKey(`beta-feedback:${bookId}:author-assignments`),
    queryFn: () => betaReadsApi.listBookAssignments(bookId).catch(() => []),
  })
  const {
    data: myAssignments = [],
    isLoading: myAssignmentsLoading,
  } = useQuery<BetaReadAssignment[]>({
    queryKey: asQueryKey(`beta-feedback:${bookId}:my-assignments`),
    queryFn: () => betaReadsApi.listMine().catch(() => []),
  })
  const {
    data: authorDetail = null,
    refetch: refetchAuthorDetail,
  } = useQuery<BetaReadAssignmentDetail | null>({
    queryKey: selectedAuthorAssignmentId ? asQueryKey(`beta-feedback:${bookId}:author-detail:${selectedAuthorAssignmentId}`) : ["beta-feedback:author-detail:none"],
    queryFn: () => betaReadsApi.getBookAssignmentDetail(bookId, selectedAuthorAssignmentId as string).catch(() => null),
    enabled: Boolean(selectedAuthorAssignmentId),
  })
  const primaryReaderAssignment = useMemo(() => selectPrimaryAssignment(myAssignments, bookId), [bookId, myAssignments])
  const {
    data: readerDetail = null,
    refetch: refetchReaderDetail,
  } = useQuery<BetaReadAssignmentDetail | null>({
    queryKey: primaryReaderAssignment ? asQueryKey(`beta-feedback:${bookId}:reader-detail:${primaryReaderAssignment.id}`) : ["beta-feedback:reader-detail:none"],
    queryFn: () => betaReadsApi.getMineDetail(primaryReaderAssignment?.id as string).catch(() => null),
    enabled: Boolean(primaryReaderAssignment?.id),
  })
  const loading = bookLoading || authorAssignmentsLoading || myAssignmentsLoading

  const [readerEmail, setReaderEmail] = useState("")
  const [taskLabel, setTaskLabel] = useState("First-pass reader response")
  const [scopeKind, setScopeKind] = useState("full_book")
  const [chapterStart, setChapterStart] = useState("1")
  const [chapterEnd, setChapterEnd] = useState("3")
  const [windowDays, setWindowDays] = useState("7")
  const [requiredProgressPct, setRequiredProgressPct] = useState("100")
  const [requiredCommentCount, setRequiredCommentCount] = useState("1")
  const [requiredFeedbackItemCount, setRequiredFeedbackItemCount] = useState("2")
  const [authorQuestionsText, setAuthorQuestionsText] = useState("Did Chapter 3 hook you?\nWhere did you get confused?")
  const [extraQuestionsText, setExtraQuestionsText] = useState("")

  const [feedbackKind, setFeedbackKind] = useState("chapter_comment")
  const [feedbackChapter, setFeedbackChapter] = useState("1")
  const [feedbackReaction, setFeedbackReaction] = useState("")
  const [feedbackAnchor, setFeedbackAnchor] = useState("")
  const [feedbackBody, setFeedbackBody] = useState("")
  const [selectedQuestionId, setSelectedQuestionId] = useState("")
  const [finalReview, setFinalReview] = useState("")
  const [finalRating, setFinalRating] = useState("4")

  useEffect(() => {
    if (authorAssignments.length === 0) {
      setSelectedAuthorAssignmentId(null)
      return
    }
    if (selectedAuthorAssignmentId && authorAssignments.some((assignment) => assignment.id === selectedAuthorAssignmentId)) return
    setSelectedAuthorAssignmentId(authorAssignments[0].id)
  }, [authorAssignments, selectedAuthorAssignmentId])

  const isAuthorView = useMemo(
    () => Boolean(book && book.workspace_shell === "author" && book.access_class !== "reader_collaborator"),
    [book]
  )
  const canLeaveFeedback = Boolean(book?.collaboration_permissions?.can_comment || book?.collaboration_permissions?.can_edit_manuscript)

  const refreshAuthorDetail = async (assignmentId: string) => {
    await refetchAuthorAssignments()
    setSelectedAuthorAssignmentId(assignmentId)
    await refetchAuthorDetail()
  }

  const refreshReaderDetail = async (assignmentId: string) => {
    if (primaryReaderAssignment?.id !== assignmentId) return
    await refetchReaderDetail()
  }

  const createAssignment = async () => {
    setSaving(true)
    setStatus(null)
    try {
      const created = await betaReadsApi.createAssignment(bookId, {
        readerEmail,
        taskLabel,
        scopeKind,
        chapterStart: scopeKind === "full_book" ? null : Number(chapterStart || "1"),
        chapterEnd: scopeKind === "full_book" ? null : Number(chapterEnd || chapterStart || "1"),
        windowDays: Number(windowDays || "7"),
        requiredProgressPct: Number(requiredProgressPct || "100"),
        requiredCommentCount: Number(requiredCommentCount || "0"),
        requiredFeedbackItemCount: Number(requiredFeedbackItemCount || "1"),
        requireFinalFeedback: true,
        authorQuestions: parseQuestionLines(authorQuestionsText),
      })
      await refetchAuthorAssignments()
      setSelectedAuthorAssignmentId(created.id)
      await refetchAuthorDetail()
      setReaderEmail("")
      setStatus("Beta read assignment created.")
    } catch {
      setStatus("Could not create this beta read assignment.")
    } finally {
      setSaving(false)
    }
  }

  const appendQuestions = async () => {
    if (!authorDetail) return
    const questions = parseQuestionLines(extraQuestionsText)
    if (questions.length === 0) return
    setSaving(true)
    setStatus(null)
    try {
      await betaReadsApi.appendQuestions(bookId, authorDetail.assignment.id, questions)
      await refreshAuthorDetail(authorDetail.assignment.id)
      setExtraQuestionsText("")
      setStatus("Questions added.")
    } catch {
      setStatus("Could not add those questions.")
    } finally {
      setSaving(false)
    }
  }

  const revokeAssignment = async (assignmentId: string) => {
    setSaving(true)
    setStatus(null)
    try {
      await betaReadsApi.revokeAssignment(bookId, assignmentId)
      const { data: assignments = [] } = await refetchAuthorAssignments()
      if (selectedAuthorAssignmentId === assignmentId) {
        setSelectedAuthorAssignmentId(assignments[0]?.id ?? null)
      }
      setStatus("Assignment revoked.")
    } catch {
      setStatus("Could not revoke this assignment.")
    } finally {
      setSaving(false)
    }
  }

  const startAssignment = async () => {
    if (!readerDetail) return
    setSaving(true)
    setStatus(null)
    try {
      await betaReadsApi.start(readerDetail.assignment.id)
      await refreshReaderDetail(readerDetail.assignment.id)
      setStatus("Beta read started.")
    } catch {
      setStatus("Could not start this beta read.")
    } finally {
      setSaving(false)
    }
  }

  const createFeedbackItem = async () => {
    if (!readerDetail) return
    setSaving(true)
    setStatus(null)
    try {
      await betaReadsApi.createFeedbackItem(readerDetail.assignment.id, {
        kind: feedbackKind,
        chapterNumber: feedbackChapter ? Number(feedbackChapter) : null,
        questionId: selectedQuestionId || null,
        reaction: feedbackReaction || null,
        anchorText: feedbackAnchor || null,
        body: feedbackBody || null,
      })
      await refreshReaderDetail(readerDetail.assignment.id)
      setFeedbackReaction("")
      setFeedbackAnchor("")
      setFeedbackBody("")
      setSelectedQuestionId("")
      setStatus("Feedback saved.")
    } catch {
      setStatus("Could not save that feedback item.")
    } finally {
      setSaving(false)
    }
  }

  const deleteFeedbackItem = async (feedbackItemId: string) => {
    if (!readerDetail) return
    setSaving(true)
    setStatus(null)
    try {
      await betaReadsApi.deleteFeedbackItem(readerDetail.assignment.id, feedbackItemId)
      await refreshReaderDetail(readerDetail.assignment.id)
      setStatus("Feedback removed.")
    } catch {
      setStatus("Could not remove that feedback item.")
    } finally {
      setSaving(false)
    }
  }

  const submitReview = async () => {
    if (!readerDetail || !finalReview.trim()) return
    setSaving(true)
    setStatus(null)
    try {
      await betaReadsApi.submitReview(readerDetail.assignment.id, finalReview.trim(), Number(finalRating))
      await refreshReaderDetail(readerDetail.assignment.id)
      setStatus("Review submitted.")
    } catch {
      setStatus("Could not submit this review yet.")
    } finally {
      setSaving(false)
    }
  }

  const activeFeedbackKind = FEEDBACK_KIND_OPTIONS.find((option) => option.value === feedbackKind)

  return (
    <div className={`min-h-screen ${isDark ? "bg-[#070b10] text-slate-100" : "bg-[#f7f7fb] text-slate-950"}`}>
      <div className="mx-auto grid max-w-[94rem] gap-5 px-4 pb-28 pt-5 sm:px-6 lg:grid-cols-[18rem_minmax(0,1fr)] lg:px-8">
        <div className="hidden lg:block lg:sticky lg:top-5 lg:self-start">
          <AuthorToolsNav
            bookId={bookId}
            active="beta-feedback"
            isDark={isDark}
            bookData={book}
            title="Beta feedback"
            description="Close the loop between draft sharing, reader response, and review-gated rewards."
            mode={book?.mode ?? "author"}
            variant="rail"
            railSize="compact"
          />
        </div>

        <main className="min-w-0 space-y-5">
          <WorkspaceFamilyHeader
            active="beta-feedback"
            bookId={bookId}
            family="review-center"
            title={`${book?.title ?? "Story"} beta feedback`}
            description="Share a read-only draft, ask direct plain-text questions, and capture structured reader signals before the final review is submitted."
          />
          {status ? <p className={`text-sm font-semibold ${status.includes("Could") ? "text-rose-400" : "text-emerald-400"}`}>{status}</p> : null}

          {loading ? (
            <section className={`rounded-md border p-6 text-sm ${isDark ? "border-white/[0.065] bg-[#0d141c] text-slate-400" : "border-slate-200/70 bg-white text-slate-500"}`}>
              Loading beta feedback workspace...
            </section>
          ) : null}

          {!loading && isAuthorView ? (
            <section className="grid gap-5 xl:grid-cols-[minmax(0,1.05fr)_minmax(0,0.95fr)]">
              <div className={`rounded-md border p-5 ${isDark ? "border-white/[0.065] bg-[#0d141c]" : "border-slate-200/70 bg-white"}`}>
                <h2 className={`text-sm font-semibold ${isDark ? "text-white" : "text-slate-900"}`}>Create beta read</h2>
                <div className="mt-5 grid gap-3">
                  <LabeledField label="Reader email" detail="Invite the account that should receive read-only beta access." isDark={isDark}>
                    <input
                      value={readerEmail}
                      onChange={(event) => setReaderEmail(event.target.value)}
                      aria-label="Reader email"
                      className={`h-11 rounded-md border px-3 text-sm outline-none transition ${isDark ? "border-white/[0.08] bg-[#101720] text-slate-100 focus:border-amber-400" : "border-slate-200 bg-white text-slate-900 focus:border-amber-400"}`}
                    />
                  </LabeledField>
                  <LabeledField label="Task label" detail="Name the pass so the reader knows what kind of feedback you want." isDark={isDark}>
                    <input
                      value={taskLabel}
                      onChange={(event) => setTaskLabel(event.target.value)}
                      aria-label="Task label"
                      className={`h-11 rounded-md border px-3 text-sm outline-none transition ${isDark ? "border-white/[0.08] bg-[#101720] text-slate-100 focus:border-amber-400" : "border-slate-200 bg-white text-slate-900 focus:border-amber-400"}`}
                    />
                  </LabeledField>
                  <LabeledField label="Scope" detail="Choose whether this beta read covers the full manuscript or a narrowed packet." isDark={isDark}>
                    <select
                      value={scopeKind}
                      onChange={(event) => setScopeKind(event.target.value)}
                      aria-label="Scope"
                      className={`h-11 rounded-md border px-3 text-sm outline-none transition ${isDark ? "border-white/[0.08] bg-[#101720] text-slate-100 focus:border-amber-400" : "border-slate-200 bg-white text-slate-900 focus:border-amber-400"}`}
                    >
                      <option value="full_book">Full book</option>
                      <option value="chapter_range">Chapter range</option>
                      <option value="section">Section</option>
                    </select>
                  </LabeledField>
                  {scopeKind !== "full_book" ? (
                    <div className="grid gap-3 sm:grid-cols-2">
                      <LabeledField label="From chapter" isDark={isDark}>
                        <input
                          type="number"
                          min="1"
                          value={chapterStart}
                          onChange={(event) => setChapterStart(event.target.value)}
                          aria-label="From chapter"
                          className={`h-11 rounded-md border px-3 text-sm outline-none transition ${isDark ? "border-white/[0.08] bg-[#101720] text-slate-100 focus:border-amber-400" : "border-slate-200 bg-white text-slate-900 focus:border-amber-400"}`}
                        />
                      </LabeledField>
                      <LabeledField label="Through chapter" isDark={isDark}>
                        <input
                          type="number"
                          min="1"
                          value={chapterEnd}
                          onChange={(event) => setChapterEnd(event.target.value)}
                          aria-label="Through chapter"
                          className={`h-11 rounded-md border px-3 text-sm outline-none transition ${isDark ? "border-white/[0.08] bg-[#101720] text-slate-100 focus:border-amber-400" : "border-slate-200 bg-white text-slate-900 focus:border-amber-400"}`}
                        />
                      </LabeledField>
                    </div>
                  ) : null}
                  <div className="grid gap-3 sm:grid-cols-1">
                    <LabeledField label="Window days" detail="Beta-read windows must stay between 3 and 7 days." isDark={isDark}>
                      <input
                        type="number"
                        min="3"
                        max="7"
                        value={windowDays}
                        onChange={(event) => setWindowDays(event.target.value)}
                        aria-label="Window days"
                        className={`h-11 rounded-md border px-3 text-sm outline-none transition ${isDark ? "border-white/[0.08] bg-[#101720] text-slate-100 focus:border-amber-400" : "border-slate-200 bg-white text-slate-900 focus:border-amber-400"}`}
                      />
                    </LabeledField>
                  </div>
                  <div className="grid gap-3 sm:grid-cols-3">
                    <LabeledField label="Progress %" isDark={isDark}>
                      <input
                        type="number"
                        min="1"
                        max="100"
                        value={requiredProgressPct}
                        onChange={(event) => setRequiredProgressPct(event.target.value)}
                        aria-label="Progress percent"
                        className={`h-11 rounded-md border px-3 text-sm outline-none transition ${isDark ? "border-white/[0.08] bg-[#101720] text-slate-100 focus:border-amber-400" : "border-slate-200 bg-white text-slate-900 focus:border-amber-400"}`}
                      />
                    </LabeledField>
                    <LabeledField label="Comments" isDark={isDark}>
                      <input
                        type="number"
                        min="0"
                        value={requiredCommentCount}
                        onChange={(event) => setRequiredCommentCount(event.target.value)}
                        aria-label="Required comments"
                        className={`h-11 rounded-md border px-3 text-sm outline-none transition ${isDark ? "border-white/[0.08] bg-[#101720] text-slate-100 focus:border-amber-400" : "border-slate-200 bg-white text-slate-900 focus:border-amber-400"}`}
                      />
                    </LabeledField>
                    <LabeledField label="Review items" isDark={isDark}>
                      <input
                        type="number"
                        min="1"
                        value={requiredFeedbackItemCount}
                        onChange={(event) => setRequiredFeedbackItemCount(event.target.value)}
                        aria-label="Required review items"
                        className={`h-11 rounded-md border px-3 text-sm outline-none transition ${isDark ? "border-white/[0.08] bg-[#101720] text-slate-100 focus:border-amber-400" : "border-slate-200 bg-white text-slate-900 focus:border-amber-400"}`}
                      />
                    </LabeledField>
                  </div>
                  <LabeledField label="Author questions" detail="Add one plain-text prompt per line for this reader." isDark={isDark}>
                    <textarea
                      value={authorQuestionsText}
                      onChange={(event) => setAuthorQuestionsText(event.target.value)}
                      rows={5}
                      aria-label="Author questions"
                      className={`rounded-md border px-3 py-3 text-sm outline-none transition ${isDark ? "border-white/[0.08] bg-[#101720] text-slate-100 focus:border-amber-400" : "border-slate-200 bg-white text-slate-900 focus:border-amber-400"}`}
                    />
                  </LabeledField>
                </div>

                <div className="mt-5 grid gap-3 sm:grid-cols-4">
                  <StatPill label="Completion gate" value="Submitted review" isDark={isDark} />
                  <StatPill label="Reader must add" value={`${requiredFeedbackItemCount || "1"} feedback items`} isDark={isDark} />
                  <StatPill label="Question format" value="Plain text prompts" isDark={isDark} />
                  <StatPill label="Draft access" value="Read-only share" isDark={isDark} />
                </div>

                <button
                  type="button"
                  onClick={() => void createAssignment()}
                  disabled={saving || !readerEmail.trim() || !taskLabel.trim()}
                  className={`mt-6 inline-flex h-11 w-full items-center justify-center rounded-md px-4 text-sm font-semibold transition ${isDark ? "bg-amber-500 text-slate-950 hover:bg-amber-400 disabled:bg-amber-500/40 disabled:text-slate-900/70" : "bg-amber-500 text-slate-950 hover:bg-amber-400 disabled:bg-amber-200 disabled:text-slate-700"}`}
                >
                  {saving ? "Saving..." : "Create beta read"}
                </button>
              </div>

              <div className={`rounded-md border p-5 ${isDark ? "border-white/[0.065] bg-[#0d141c]" : "border-slate-200/70 bg-white"}`}>
                <div className="flex items-center justify-between gap-3">
                  <h2 className={`text-sm font-semibold ${isDark ? "text-white" : "text-slate-900"}`}>Assignments</h2>
                  <span className={`text-xs ${isDark ? "text-slate-500" : "text-slate-400"}`}>{authorAssignments.length} total</span>
                </div>
                <div className="mt-5 space-y-3">
                  {authorAssignments.length > 0 ? authorAssignments.map((assignment) => (
                    <button
                      type="button"
                      key={assignment.id}
                      onClick={() => void refreshAuthorDetail(assignment.id)}
                      className={`block w-full rounded-md border p-4 text-left transition ${authorDetail?.assignment.id === assignment.id ? (isDark ? "border-amber-400/60 bg-amber-400/10" : "border-amber-400 bg-amber-50") : (isDark ? "border-white/[0.06] bg-[#101720] hover:bg-white/[0.05]" : "border-slate-200 bg-slate-50 hover:bg-white")}`}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-slate-900"}`}>{assignment.reader_email}</p>
                          <p className={`mt-1 text-xs ${isDark ? "text-slate-500" : "text-slate-500"}`}>{assignment.task_label}</p>
                        </div>
                        <span className={`rounded-full px-2.5 py-1 text-3xs font-semibold ${assignment.view_bucket === "completed" ? "bg-emerald-500/10 text-emerald-400" : assignment.view_bucket === "missed" ? "bg-rose-500/10 text-rose-400" : "bg-sky-500/10 text-sky-400"}`}>
                          {assignment.status_label}
                        </span>
                      </div>
                      <div className="mt-3 grid gap-2 sm:grid-cols-3">
                        <StatPill label="Window" value={`${assignment.window_days} days`} isDark={isDark} />
                        <StatPill label="Comments" value={`${assignment.comment_count}/${assignment.required_comment_count}`} isDark={isDark} />
                        <StatPill label="Review items" value={`${assignment.feedback_item_count}/${assignment.required_feedback_item_count}`} isDark={isDark} />
                      </div>
                    </button>
                  )) : (
                    <div className={`rounded-md border border-dashed p-5 text-sm ${isDark ? "border-white/[0.08] text-slate-500" : "border-slate-200 text-slate-400"}`}>
                      No beta read assignments yet.
                    </div>
                  )}
                </div>

                {authorDetail ? (
                  <div className={`mt-5 rounded-md border p-4 ${isDark ? "border-white/[0.06] bg-[#101720]" : "border-slate-200 bg-slate-50"}`}>
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-slate-900"}`}>Selected assignment</p>
                        <p className={`mt-1 text-xs ${isDark ? "text-slate-500" : "text-slate-500"}`}>{authorDetail.assignment.reader_email}</p>
                      </div>
                      {authorDetail.assignment.view_bucket === "active" || authorDetail.assignment.view_bucket === "scheduled" ? (
                        <button type="button" onClick={() => void revokeAssignment(authorDetail.assignment.id)} className="text-xs font-semibold text-rose-400">
                          Revoke
                        </button>
                      ) : null}
                    </div>

                    <div className="mt-4 grid gap-3 sm:grid-cols-4">
                      <StatPill label="Progress" value={`${authorDetail.assignment.progress_pct}%`} isDark={isDark} />
                      <StatPill label="Answers" value={`${authorDetail.feedback_summary.answer_count}`} isDark={isDark} />
                      <StatPill label="Confusing" value={`${authorDetail.feedback_summary.confusing_count}`} isDark={isDark} />
                      <StatPill label="Favorites" value={`${authorDetail.feedback_summary.favorite_count}`} isDark={isDark} />
                    </div>

                    <div className="mt-4">
                      <p className={`text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-400" : "text-slate-500"}`}>Author questions</p>
                      <div className="mt-3 space-y-2">
                        {authorDetail.author_questions.length > 0 ? authorDetail.author_questions.map((question) => (
                          <div key={question.id} className={`rounded-md border px-3 py-2 text-sm ${isDark ? "border-white/[0.06] bg-white/[0.02] text-slate-200" : "border-slate-200 bg-white text-slate-700"}`}>
                            <div className="flex items-center justify-between gap-3">
                              <span>{question.prompt}</span>
                              <span className={`text-3xs ${isDark ? "text-slate-500" : "text-slate-400"}`}>{question.answer_count} answers</span>
                            </div>
                          </div>
                        )) : (
                          <p className={`text-sm ${isDark ? "text-slate-500" : "text-slate-500"}`}>No author questions attached yet.</p>
                        )}
                      </div>
                      <textarea
                        value={extraQuestionsText}
                        onChange={(event) => setExtraQuestionsText(event.target.value)}
                        rows={3}
                        aria-label="Additional author questions"
                        className={`mt-3 w-full rounded-md border px-3 py-3 text-sm outline-none transition ${isDark ? "border-white/[0.08] bg-[#0d141c] text-slate-100 focus:border-amber-400" : "border-slate-200 bg-white text-slate-900 focus:border-amber-400"}`}
                      />
                      <p className={`mt-2 text-xs ${isDark ? "text-slate-500" : "text-slate-500"}`}>Add more questions, one per line.</p>
                      <button
                        type="button"
                        onClick={() => void appendQuestions()}
                        disabled={saving || parseQuestionLines(extraQuestionsText).length === 0}
                        className={`mt-3 inline-flex h-10 items-center justify-center rounded-md px-4 text-sm font-semibold transition ${isDark ? "bg-white/10 text-slate-100 hover:bg-white/15 disabled:bg-white/5 disabled:text-slate-500" : "bg-slate-900 text-white hover:bg-slate-800 disabled:bg-slate-200 disabled:text-slate-500"}`}
                      >
                        Add questions
                      </button>
                    </div>
                  </div>
                ) : null}
              </div>
            </section>
          ) : null}

          {!loading && canLeaveFeedback && readerDetail ? (
            <section className="grid gap-5 xl:grid-cols-[minmax(0,0.95fr)_minmax(0,1.05fr)]">
              <div className={`rounded-md border p-5 ${isDark ? "border-white/[0.065] bg-[#0d141c]" : "border-slate-200/70 bg-white"}`}>
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h2 className={`text-sm font-semibold ${isDark ? "text-white" : "text-slate-900"}`}>Your beta read</h2>
                    <p className={`mt-1 text-sm ${isDark ? "text-slate-400" : "text-slate-500"}`}>{readerDetail.assignment.task_label}</p>
                  </div>
                  <span className={`rounded-full px-2.5 py-1 text-3xs font-semibold ${readerDetail.assignment.submission_allowed ? "bg-emerald-500/10 text-emerald-400" : "bg-sky-500/10 text-sky-400"}`}>
                    {readerDetail.assignment.status_label}
                  </span>
                </div>

                <div className="mt-5 grid gap-3 sm:grid-cols-4">
                  <StatPill label="Window" value={`${readerDetail.assignment.window_days} days`} isDark={isDark} />
                  <StatPill label="Progress" value={`${readerDetail.assignment.progress_pct}%`} isDark={isDark} />
                  <StatPill label="Comments" value={`${readerDetail.assignment.comment_count}/${readerDetail.assignment.required_comment_count}`} isDark={isDark} />
                  <StatPill label="Review items" value={`${readerDetail.assignment.feedback_item_count}/${readerDetail.assignment.required_feedback_item_count}`} isDark={isDark} />
                </div>

                <div className={`mt-5 rounded-md border p-4 ${isDark ? "border-white/[0.06] bg-[#101720]" : "border-slate-200 bg-slate-50"}`}>
                  <p className={`text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-400" : "text-slate-500"}`}>Author questions</p>
                  <div className="mt-3 space-y-2">
                    {readerDetail.author_questions.length > 0 ? readerDetail.author_questions.map((question) => (
                      <div key={question.id} className={`rounded-md border px-3 py-2 text-sm ${isDark ? "border-white/[0.06] bg-white/[0.02] text-slate-200" : "border-slate-200 bg-white text-slate-700"}`}>
                        {question.prompt}
                      </div>
                    )) : (
                      <p className={`text-sm ${isDark ? "text-slate-500" : "text-slate-500"}`}>No direct author questions on this assignment.</p>
                    )}
                  </div>
                </div>

                <div className="mt-5">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <h3 className={`text-sm font-semibold ${isDark ? "text-white" : "text-slate-900"}`}>Add structured feedback</h3>
                      <p className={`mt-1 text-xs ${isDark ? "text-slate-500" : "text-slate-500"}`}>{activeFeedbackKind?.detail}</p>
                    </div>
                    {readerDetail.assignment.state === "active" ? (
                      <button type="button" onClick={() => void startAssignment()} className={`rounded-md px-3 py-2 text-xs font-semibold ${isDark ? "bg-white/10 text-slate-100" : "bg-slate-900 text-white"}`}>
                        Start
                      </button>
                    ) : null}
                  </div>
                  <div className="mt-4 grid gap-3">
                    <select
                      value={feedbackKind}
                      onChange={(event) => setFeedbackKind(event.target.value)}
                      className={`h-11 rounded-md border px-3 text-sm outline-none transition ${isDark ? "border-white/[0.08] bg-[#101720] text-slate-100 focus:border-sky-400" : "border-slate-200 bg-white text-slate-900 focus:border-sky-400"}`}
                    >
                      {FEEDBACK_KIND_OPTIONS.map((option) => (
                        <option key={option.value} value={option.value}>{option.label}</option>
                      ))}
                    </select>
                    <div className="grid gap-3 sm:grid-cols-2">
                      <LabeledField label="Chapter number" isDark={isDark}>
                        <input
                          type="number"
                          min="1"
                          value={feedbackChapter}
                          onChange={(event) => setFeedbackChapter(event.target.value)}
                          aria-label="Feedback chapter number"
                          className={`h-11 rounded-md border px-3 text-sm outline-none transition ${isDark ? "border-white/[0.08] bg-[#101720] text-slate-100 focus:border-sky-400" : "border-slate-200 bg-white text-slate-900 focus:border-sky-400"}`}
                        />
                      </LabeledField>
                      <LabeledField label="Linked question" isDark={isDark}>
                        <select
                          value={selectedQuestionId}
                          onChange={(event) => setSelectedQuestionId(event.target.value)}
                          aria-label="Linked author question"
                          className={`h-11 rounded-md border px-3 text-sm outline-none transition ${isDark ? "border-white/[0.08] bg-[#101720] text-slate-100 focus:border-sky-400" : "border-slate-200 bg-white text-slate-900 focus:border-sky-400"}`}
                        >
                          <option value="">No linked author question</option>
                          {readerDetail.author_questions.map((question) => (
                            <option key={question.id} value={question.id}>{question.prompt}</option>
                          ))}
                        </select>
                      </LabeledField>
                    </div>
                    <LabeledField label="Reaction label" detail="Use this for quick scene reactions, if this item needs one." isDark={isDark}>
                      <input
                        value={feedbackReaction}
                        onChange={(event) => setFeedbackReaction(event.target.value)}
                        aria-label="Reaction label"
                        className={`h-11 rounded-md border px-3 text-sm outline-none transition ${isDark ? "border-white/[0.08] bg-[#101720] text-slate-100 focus:border-sky-400" : "border-slate-200 bg-white text-slate-900 focus:border-sky-400"}`}
                      />
                    </LabeledField>
                    <LabeledField label="Anchor text" detail="Quote the passage or marker this feedback refers to." isDark={isDark}>
                      <input
                        value={feedbackAnchor}
                        onChange={(event) => setFeedbackAnchor(event.target.value)}
                        aria-label="Anchor text"
                        className={`h-11 rounded-md border px-3 text-sm outline-none transition ${isDark ? "border-white/[0.08] bg-[#101720] text-slate-100 focus:border-sky-400" : "border-slate-200 bg-white text-slate-900 focus:border-sky-400"}`}
                      />
                    </LabeledField>
                    <LabeledField label="Feedback body" detail="Write what landed, dragged, confused you, or directly answers the author." isDark={isDark}>
                      <textarea
                        value={feedbackBody}
                        onChange={(event) => setFeedbackBody(event.target.value)}
                        rows={5}
                        aria-label="Feedback body"
                        className={`rounded-md border px-3 py-3 text-sm outline-none transition ${isDark ? "border-white/[0.08] bg-[#101720] text-slate-100 focus:border-sky-400" : "border-slate-200 bg-white text-slate-900 focus:border-sky-400"}`}
                      />
                    </LabeledField>
                    <button
                      type="button"
                      onClick={() => void createFeedbackItem()}
                      disabled={saving}
                      className={`inline-flex h-11 items-center justify-center rounded-md px-4 text-sm font-semibold transition ${isDark ? "bg-sky-400 text-slate-950 hover:bg-sky-300 disabled:bg-sky-400/40 disabled:text-slate-900/70" : "bg-sky-600 text-white hover:bg-sky-500 disabled:bg-sky-200 disabled:text-slate-500"}`}
                    >
                      Save feedback item
                    </button>
                  </div>
                </div>
              </div>

              <div className={`rounded-md border p-5 ${isDark ? "border-white/[0.065] bg-[#0d141c]" : "border-slate-200/70 bg-white"}`}>
                <h2 className={`text-sm font-semibold ${isDark ? "text-white" : "text-slate-900"}`}>Review trail</h2>
                <div className="mt-5 grid gap-3 sm:grid-cols-4">
                  <StatPill label="Answers" value={`${readerDetail.feedback_summary.answer_count}`} isDark={isDark} />
                  <StatPill label="Confusing" value={`${readerDetail.feedback_summary.confusing_count}`} isDark={isDark} />
                  <StatPill label="Boring" value={`${readerDetail.feedback_summary.boring_count}`} isDark={isDark} />
                  <StatPill label="Favorites" value={`${readerDetail.feedback_summary.favorite_count}`} isDark={isDark} />
                </div>
                <div className="mt-5 space-y-3">
                  {readerDetail.feedback_items.length > 0 ? readerDetail.feedback_items.map((item) => (
                    <div key={item.id} className={`rounded-md border p-4 ${isDark ? "border-white/[0.06] bg-[#101720]" : "border-slate-200 bg-slate-50"}`}>
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-slate-900"}`}>{formatFeedbackKindLabel(item.kind)}</p>
                          <p className={`mt-1 text-xs ${isDark ? "text-slate-500" : "text-slate-500"}`}>
                            {item.chapter_number ? `Chapter ${item.chapter_number}` : "Book-wide"}{item.scene_title ? ` / ${item.scene_title}` : ""}
                          </p>
                        </div>
                        {(readerDetail.assignment.view_bucket === "active" || readerDetail.assignment.view_bucket === "scheduled") ? (
                          <button type="button" onClick={() => void deleteFeedbackItem(item.id)} className="text-xs font-semibold text-rose-400">
                            Remove
                          </button>
                        ) : null}
                      </div>
                      {item.question_prompt ? <p className={`mt-3 text-xs font-semibold ${isDark ? "text-amber-300" : "text-amber-700"}`}>Q: {item.question_prompt}</p> : null}
                      {item.reaction ? <p className={`mt-3 text-xs font-semibold ${isDark ? "text-sky-300" : "text-sky-700"}`}>Reaction: {formatFeedbackKindLabel(item.reaction)}</p> : null}
                      {item.anchor_text ? <p className={`mt-3 text-sm italic ${isDark ? "text-slate-300" : "text-slate-700"}`}>{item.anchor_text}</p> : null}
                      {item.body ? <p className={`mt-3 text-sm leading-6 ${isDark ? "text-slate-300" : "text-slate-700"}`}>{item.body}</p> : null}
                    </div>
                  )) : (
                    <div className={`rounded-md border border-dashed p-5 text-sm ${isDark ? "border-white/[0.08] text-slate-500" : "border-slate-200 text-slate-400"}`}>
                      No structured feedback saved yet.
                    </div>
                  )}
                </div>

                <div className={`mt-5 rounded-md border p-4 ${isDark ? "border-white/[0.06] bg-[#101720]" : "border-slate-200 bg-slate-50"}`}>
                  <p className={`text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-400" : "text-slate-500"}`}>Final review</p>
                  <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-400" : "text-slate-500"}`}>
                    Submit a written review and a 1 to 5 rating in 0.5 steps to finish this assignment cleanly. Stronger-rated books rise in discovery for future readers.
                  </p>
                  <select
                    value={finalRating}
                    onChange={(event) => setFinalRating(event.target.value)}
                    className={`mt-4 h-11 w-full rounded-md border px-3 text-sm outline-none transition ${isDark ? "border-white/[0.08] bg-[#0d141c] text-slate-100 focus:border-emerald-400" : "border-slate-200 bg-white text-slate-900 focus:border-emerald-400"}`}
                  >
                    {FINAL_RATING_OPTIONS.map((rating) => (
                      <option key={rating} value={rating.toString()}>{`${rating.toFixed(1)} / 5`}</option>
                    ))}
                  </select>
                  <textarea
                    value={finalReview}
                    onChange={(event) => setFinalReview(event.target.value)}
                    rows={6}
                    aria-label="Final review"
                    className={`mt-4 w-full rounded-md border px-3 py-3 text-sm outline-none transition ${isDark ? "border-white/[0.08] bg-[#0d141c] text-slate-100 focus:border-emerald-400" : "border-slate-200 bg-white text-slate-900 focus:border-emerald-400"}`}
                  />
                  <p className={`mt-2 text-xs ${isDark ? "text-slate-500" : "text-slate-500"}`}>Summarize what hooked you, what felt predictable, what confused you, and who you cared about most.</p>
                  <button
                    type="button"
                    onClick={() => void submitReview()}
                    disabled={saving || !finalReview.trim()}
                    className={`mt-4 inline-flex h-11 w-full items-center justify-center rounded-md px-4 text-sm font-semibold transition ${isDark ? "bg-emerald-400 text-slate-950 hover:bg-emerald-300 disabled:bg-emerald-400/40 disabled:text-slate-900/70" : "bg-emerald-600 text-white hover:bg-emerald-500 disabled:bg-emerald-200 disabled:text-slate-500"}`}
                  >
                    Submit review
                  </button>
                </div>
              </div>
            </section>
          ) : null}

          {!loading && !isAuthorView && !readerDetail ? (
            <section className={`rounded-md border p-6 text-sm ${isDark ? "border-white/[0.065] bg-[#0d141c] text-slate-400" : "border-slate-200/70 bg-white text-slate-500"}`}>
              No active beta read was found for this book on your account yet.
            </section>
          ) : null}
        </main>
      </div>
    </div>
  )
}
