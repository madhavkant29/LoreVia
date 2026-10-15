"use client"

import Link from "next/link"
import { memo, useMemo, useRef, useState } from "react"
import { useQuery } from "@tanstack/react-query"

import { betaReadsApi } from "@/lib/api/betaReads"
import { booksApi } from "@/lib/api/books"
import { useBookDetail } from "@/lib/hooks/useBookDetail"
import { useReaderDraftGuard } from "@/lib/hooks/useReaderDraftGuard"
import { normalizeBookRouteId } from "@/lib/utils/bookRoutes"
import { asQueryKey, bookCacheKey } from "@/lib/query/cacheKeys"
import type { BetaReadAssignment } from "@/types/betaRead"
import type { ManuscriptAnnotation } from "@/types/book"
import type { ChapterBetaFeedback } from "@/types/reader"

type ReaderChapterFeedbackProps = {
  bookId: string
  chapterNum: number
  theme: "light" | "dark"
  chapterFeedback: ChapterBetaFeedback[]
}

export const ReaderChapterFeedback = memo(function ReaderChapterFeedback({ bookId, chapterNum, theme, chapterFeedback }: ReaderChapterFeedbackProps) {
  const bookQuery = useBookDetail(bookId)
  const book = bookQuery.data
  const [chapterComment, setChapterComment] = useState("")
  const [commentStatus, setCommentStatus] = useState<string | null>(null)
  const [savingComment, setSavingComment] = useState(false)
  const [localFeedback, setLocalFeedback] = useState<ChapterBetaFeedback[]>([])
  const [savedAnnotations, setSavedAnnotations] = useState<ManuscriptAnnotation[]>([])
  const savingRef = useRef(false)
  const commentInputRef = useRef<HTMLTextAreaElement | null>(null)

  useReaderDraftGuard(Boolean(chapterComment.trim()), savingComment)

  const canSeeChapterFeedback = Boolean(
    book?.access_class === "owner" ||
      book?.access_class === "reader_collaborator" ||
      book?.access_class === "author_collaborator"
  )
  const canLeaveChapterComment = Boolean(
    book?.access_class === "owner" ||
      book?.collaboration_permissions?.can_comment ||
      book?.collaboration_permissions?.can_edit_manuscript
  )

  const annotationsQuery = useQuery({
    queryKey: asQueryKey(bookCacheKey(bookId, `annotations:${chapterNum}`)),
    queryFn: () => booksApi.getManuscriptAnnotations(bookId, chapterNum),
    enabled: canSeeChapterFeedback,
    staleTime: 20_000,
    retry: false,
  })

  const betaAssignmentsQuery = useQuery({
    queryKey: ["reader:beta-reads", bookId],
    queryFn: () => betaReadsApi.listMine("active"),
    enabled: canLeaveChapterComment && book?.access_class !== "owner",
    staleTime: 20_000,
    retry: false,
  })

  const activeBetaAssignment = useMemo(() => {
    const assignments = book?.access_class === "owner" ? [] : betaAssignmentsQuery.data ?? []
    return (
      assignments.find((assignment) => assignment.book_id === normalizeBookRouteId(bookId) && chapterMatchesAssignment(chapterNum, assignment)) ??
      null
    )
  }, [betaAssignmentsQuery.data, bookId, chapterNum, book?.access_class])

  const visibleFeedback = useMemo(
    () => [...new Map([...chapterFeedback, ...localFeedback].map((item) => [item.id, item])).values()].sort((left, right) => Date.parse(right.created_at) - Date.parse(left.created_at)),
    [chapterFeedback, localFeedback]
  )
  const visibleAnnotations = useMemo(
    () => [...new Map([...(annotationsQuery.data ?? []), ...savedAnnotations].map((item) => [item.id, item])).values()].sort((left, right) => Date.parse(right.updated_at) - Date.parse(left.updated_at)),
    [annotationsQuery.data, savedAnnotations]
  )

  const existingChapterCommentCount = visibleFeedback.length + visibleAnnotations.length
  const assignmentsUnavailable = book?.access_class !== "owner" && Boolean(betaAssignmentsQuery.isLoading || betaAssignmentsQuery.isError)

  const saveChapterComment = async () => {
    const nextComment = chapterComment.trim() || commentInputRef.current?.value.trim() || ""
    if (!nextComment || savingRef.current || !canLeaveChapterComment || assignmentsUnavailable) return
    if (nextComment.length > 10000) { setCommentStatus("Keep chapter comments within 10,000 characters."); return }
    savingRef.current = true
    setSavingComment(true)
    setCommentStatus("Saving comment...")
    try {
      if (activeBetaAssignment) {
        const detail = await betaReadsApi.createFeedbackItem(activeBetaAssignment.id, {
          kind: "chapter_comment",
          chapterNumber: chapterNum,
          body: nextComment,
        })
        const latestFeedback = [...detail.feedback_items]
          .filter((item) => item.kind === "chapter_comment" && item.chapter_number === chapterNum && item.body === nextComment)
          .sort((left, right) => Date.parse(right.created_at) - Date.parse(left.created_at))[0]
        if (latestFeedback) {
          const nextFeedback: ChapterBetaFeedback = {
            id: latestFeedback.id,
            assignment_id: activeBetaAssignment.id,
            collaborator_id: activeBetaAssignment.collaborator_id ?? null,
            reader_user_id: activeBetaAssignment.reader_user_id ?? null,
            reader_email: activeBetaAssignment.reader_email,
            reader_display_name: "You",
            task_label: activeBetaAssignment.task_label,
            kind: latestFeedback.kind,
            chapter_number: latestFeedback.chapter_number ?? null,
            anchor_text: latestFeedback.anchor_text ?? null,
            body: latestFeedback.body ?? null,
            author_status: latestFeedback.author_status,
            created_at: latestFeedback.created_at,
            updated_at: latestFeedback.updated_at,
          }
          setLocalFeedback((current) => {
            const withoutExisting = current.filter((item) => item.id !== nextFeedback.id)
            return [nextFeedback, ...withoutExisting]
          })
        }
      } else {
        const annotation = await booksApi.saveManuscriptAnnotation(bookId, {
          chapterNumber: chapterNum,
          category: "general",
          visibility: "shared",
          quote: `Chapter ${chapterNum}`,
          comment: nextComment,
        })
        if (annotation?.id) setSavedAnnotations((current) => [annotation, ...current.filter((item) => item.id !== annotation.id)])
        void annotationsQuery.refetch()
      }
      setChapterComment("")
      setCommentStatus("Comment saved.")
      if (book?.access_class !== "owner") void betaAssignmentsQuery.refetch()
    } catch {
      setCommentStatus("Could not confirm the comment save. Your draft is still here; check the comments before retrying.")
    } finally {
      setSavingComment(false)
      savingRef.current = false
    }
  }

  if (bookQuery.isError && !book) return <p role="alert" className="mx-auto max-w-[980px] py-6 text-sm">Could not load comment access. <button type="button" className="underline" onClick={() => void bookQuery.refetch()}>Retry comments</button></p>
  if (!canSeeChapterFeedback) return null

  return (
    <section
      data-chapter-feedback
      aria-label="Chapter comments"
      className={`mx-auto mt-8 w-full max-w-[980px] rounded-lg border px-5 py-5 sm:px-6 ${
        theme === "dark"
          ? "border-white/10 bg-white/[0.04] text-stone-100"
          : "border-stone-200 bg-white/85 text-slate-950"
      }`}
    >
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className={`text-3xs font-semibold uppercase tracking-[0.24em] ${theme === "dark" ? "text-slate-500" : "text-stone-400"}`}>
            Reader feedback
          </p>
          <h2 className={`mt-1 text-lg font-semibold ${theme === "dark" ? "text-white" : "text-slate-950"}`}>
            {canLeaveChapterComment ? "Leave a chapter comment" : "Chapter comments"}
          </h2>
          <p className={`mt-1 text-sm ${theme === "dark" ? "text-slate-400" : "text-stone-500"}`}>
            {existingChapterCommentCount
              ? `${existingChapterCommentCount} chapter comment${existingChapterCommentCount === 1 ? "" : "s"} visible here.`
              : "Comments on this chapter stay attached to the chapter where they were left."}
          </p>
        </div>
        <Link
          href={`/${bookId}/beta-feedback`}
          className={`inline-flex min-h-11 items-center justify-center rounded-xl px-4 text-sm font-semibold ${
            theme === "dark" ? "bg-teal-700 text-white" : "bg-teal-800 text-white"
          }`}
        >
          Open full beta review
        </Link>
      </div>

      {annotationsQuery.isLoading ? <p role="status" className="mt-4 text-sm">Loading chapter comments…</p> : null}
      {annotationsQuery.isError ? <p role="alert" className="mt-4 text-sm">Could not load all comments. <button type="button" className="min-h-11 underline" onClick={() => void annotationsQuery.refetch()}>Retry comments</button></p> : null}
      {betaAssignmentsQuery.isError && book?.access_class !== "owner" ? <p role="alert" className="mt-4 text-sm">Could not check your beta assignment. <button type="button" className="min-h-11 underline" onClick={() => void betaAssignmentsQuery.refetch()}>Retry assignment</button></p> : null}

      {visibleFeedback.length > 0 || visibleAnnotations.length > 0 ? (
        <div className="mt-4 space-y-3">
          {visibleAnnotations.map((annotation) => (
            <AnnotationCommentCard key={annotation.id} annotation={annotation} theme={theme} />
          ))}
          {visibleFeedback.map((item) => (
            <article
              key={item.id}
              className={`rounded-md border px-4 py-4 ${
                theme === "dark"
                  ? "border-white/10 bg-[#121722]"
                  : "border-stone-200 bg-stone-50"
              }`}
            >
              <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <p className={`text-sm font-semibold ${theme === "dark" ? "text-white" : "text-slate-950"}`}>
                    {item.reader_display_name}
                  </p>
                  <p className={`mt-1 text-xs ${theme === "dark" ? "text-slate-500" : "text-stone-500"}`}>
                    {item.task_label}
                  </p>
                </div>
                <p className={`text-xs ${theme === "dark" ? "text-slate-500" : "text-stone-500"}`}>
                  {new Date(item.created_at).toLocaleString()}
                </p>
              </div>
              {item.body ? (
                <p className={`mt-3 whitespace-pre-wrap text-sm leading-6 ${theme === "dark" ? "text-slate-200" : "text-slate-700"}`}>
                  {item.body}
                </p>
              ) : null}
            </article>
          ))}
        </div>
      ) : null}

      {canLeaveChapterComment ? (
        <>
          {activeBetaAssignment ? <p className="mt-4 text-sm">This comment counts toward your beta assignment: <strong>{activeBetaAssignment.task_label}</strong>.</p> : null}
          <label htmlFor="reader-chapter-comment" className={`mt-4 block text-sm font-semibold ${theme === "dark" ? "text-slate-300" : "text-stone-600"}`}>
            Chapter comment
          </label>
          <textarea
            id="reader-chapter-comment"
            disabled={savingComment}
            aria-describedby="reader-comment-status"
            ref={commentInputRef}
            value={chapterComment}
            onChange={(event) => { setChapterComment(event.target.value); setCommentStatus(null) }}
            aria-label="Chapter comment"
            className={`mt-2 min-h-28 w-full rounded-md border px-4 py-3 text-sm outline-none ${
              theme === "dark"
                ? "border-white/10 bg-[#121722] text-white"
                : "border-stone-200 bg-white text-slate-950"
            }`}
          />
          <p className="mt-2 text-sm" aria-live="polite">{chapterComment.length.toLocaleString()} / 10,000 characters{chapterComment.length > 10000 ? " — shorten your comment to save." : ""}</p>
          <div className="mt-3 flex items-center justify-between gap-3">
            <p id="reader-comment-status" role="status" className={`text-sm ${theme === "dark" ? "text-slate-300" : "text-stone-600"}`}>
              {commentStatus ?? "Write what landed, confused you, or needs another pass. Comments are shared with the author on this chapter."}
            </p>
            <button
              type="button"
              onClick={saveChapterComment}
              disabled={savingComment || !chapterComment.trim() || assignmentsUnavailable || chapterComment.trim().length > 10000}
              className={`inline-flex min-h-11 items-center justify-center rounded-xl px-4 text-sm font-semibold ${
                savingComment || !chapterComment.trim()
                  ? theme === "dark"
                    ? "bg-white/10 text-slate-500"
                    : "bg-stone-100 text-stone-400"
                  : theme === "dark"
                    ? "bg-white text-slate-950"
                    : "bg-slate-950 text-white"
              }`}
            >
              {savingComment ? "Saving..." : "Leave chapter comment"}
            </button>
          </div>
        </>
      ) : null}
    </section>
  )
})

function chapterMatchesAssignment(chapterNum: number, assignment: BetaReadAssignment) {
  if (["submitted", "completed", "revoked", "missed", "disqualified"].includes(assignment.state)) return false
  if (Date.parse(assignment.starts_at) > Date.now() || Date.parse(assignment.expires_at) <= Date.now()) return false
  if (typeof assignment.chapter_start === "number" && chapterNum < assignment.chapter_start) return false
  if (typeof assignment.chapter_end === "number" && chapterNum > assignment.chapter_end) return false
  return true
}

function AnnotationCommentCard({ annotation, theme }: { annotation: ManuscriptAnnotation; theme: "light" | "dark" }) {
  return (
    <article
      className={`rounded-md border px-4 py-4 ${
        theme === "dark"
          ? "border-white/10 bg-[#121722]"
          : "border-stone-200 bg-stone-50"
      }`}
    >
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className={`text-sm font-semibold ${theme === "dark" ? "text-white" : "text-slate-950"}`}>
            {annotation.created_by_label}
          </p>
          <p className={`mt-1 text-xs ${theme === "dark" ? "text-slate-500" : "text-stone-500"}`}>
            {annotation.category.replace(/_/g, " ")} annotation · {annotation.visibility}
          </p>
        </div>
        <p className={`text-xs ${theme === "dark" ? "text-slate-500" : "text-stone-500"}`}>
          {new Date(annotation.updated_at).toLocaleString()}
        </p>
      </div>
      {annotation.quote ? (
        <blockquote className={`mt-3 border-l-2 pl-3 text-sm leading-6 ${theme === "dark" ? "border-teal-300/40 text-slate-300" : "border-teal-700/30 text-stone-600"}`}>
          {annotation.quote}
        </blockquote>
      ) : null}
      <p className={`mt-3 whitespace-pre-wrap text-sm leading-6 ${theme === "dark" ? "text-slate-200" : "text-slate-700"}`}>
        {annotation.comment}
      </p>
    </article>
  )
}
