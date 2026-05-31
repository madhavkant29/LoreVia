"use client"

import Link from "next/link"
import { useEffect, useMemo, useRef, useState } from "react"
import { useQuery } from "@tanstack/react-query"

import { betaReadsApi } from "@/lib/api/betaReads"
import { booksApi } from "@/lib/api/books"
import { useBookDetail } from "@/lib/hooks/useBookDetail"
import { asQueryKey, bookCacheKey } from "@/lib/query/cacheKeys"
import type { BetaReadAssignment } from "@/types/betaRead"
import type { ChapterBetaFeedback } from "@/types/reader"

type ReaderChapterFeedbackProps = {
  bookId: string
  chapterNum: number
  theme: "light" | "dark"
  chapterFeedback: ChapterBetaFeedback[]
}

export function ReaderChapterFeedback({ bookId, chapterNum, theme, chapterFeedback }: ReaderChapterFeedbackProps) {
  const { data: book } = useBookDetail(bookId)
  const [chapterComment, setChapterComment] = useState("")
  const [commentStatus, setCommentStatus] = useState<string | null>(null)
  const [savingComment, setSavingComment] = useState(false)
  const [localFeedback, setLocalFeedback] = useState<ChapterBetaFeedback[]>(chapterFeedback)
  const commentInputRef = useRef<HTMLTextAreaElement | null>(null)

  useEffect(() => {
    setLocalFeedback(chapterFeedback)
  }, [chapterFeedback])

  const canSeeChapterFeedback = Boolean(
    book?.access_class === "owner" ||
      (book?.access_class === "reader_collaborator" && book?.workspace_shell === "reader")
  )
  const canLeaveChapterComment = Boolean(
    book?.access_class === "reader_collaborator" &&
      book?.workspace_shell === "reader" &&
      book?.collaboration_permissions?.can_comment
  )

  const annotationsQuery = useQuery({
    queryKey: asQueryKey(bookCacheKey(bookId, `annotations:${chapterNum}`)),
    queryFn: () => booksApi.getManuscriptAnnotations(bookId, chapterNum),
    enabled: canLeaveChapterComment,
    staleTime: 20_000,
  })

  const betaAssignmentsQuery = useQuery({
    queryKey: ["reader:beta-reads", bookId],
    queryFn: () => betaReadsApi.listMine("active"),
    enabled: canLeaveChapterComment,
    staleTime: 20_000,
  })

  const activeBetaAssignment = useMemo(() => {
    const assignments = betaAssignmentsQuery.data ?? []
    return (
      assignments.find((assignment) => assignment.book_id === bookId && chapterMatchesAssignment(chapterNum, assignment)) ??
      assignments.find((assignment) => assignment.book_id === bookId) ??
      null
    )
  }, [betaAssignmentsQuery.data, bookId, chapterNum])

  const visibleFeedback = useMemo(
    () => [...localFeedback].sort((left, right) => Date.parse(right.created_at) - Date.parse(left.created_at)),
    [localFeedback]
  )

  const existingChapterCommentCount = activeBetaAssignment
    ? visibleFeedback.length
    : (annotationsQuery.data?.length ?? 0)

  const saveChapterComment = async () => {
    const nextComment = chapterComment.trim() || commentInputRef.current?.value.trim() || ""
    if (!nextComment) return
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
          .filter((item) => item.kind === "chapter_comment" && item.chapter_number === chapterNum)
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
        await booksApi.saveManuscriptAnnotation(bookId, {
          chapterNumber: chapterNum,
          category: "general",
          visibility: "shared",
          quote: `Chapter ${chapterNum}`,
          comment: nextComment,
        })
        void annotationsQuery.refetch()
      }
      setChapterComment("")
      setCommentStatus("Comment saved.")
      void betaAssignmentsQuery.refetch()
    } catch {
      setCommentStatus("Could not save comment.")
    } finally {
      setSavingComment(false)
    }
  }

  if (!canSeeChapterFeedback) return null

  return (
    <section
      className={`mx-auto mt-8 w-full max-w-[980px] rounded-lg border px-5 py-5 sm:px-6 ${
        theme === "dark"
          ? "border-white/10 bg-white/[0.04] text-stone-100"
          : "border-stone-200 bg-white/85 text-slate-950"
      }`}
      style={{ contentVisibility: "auto", containIntrinsicSize: "420px" }}
    >
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className={`text-3xs font-semibold uppercase tracking-[0.24em] ${theme === "dark" ? "text-slate-500" : "text-stone-400"}`}>
            Reader feedback
          </p>
          <h2 className={`mt-1 text-lg font-semibold ${theme === "dark" ? "text-white" : "text-slate-950"}`}>
            {canLeaveChapterComment ? "Leave a chapter comment" : "Chapter beta comments"}
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

      {visibleFeedback.length > 0 ? (
        <div className="mt-4 space-y-3">
          {visibleFeedback.map((item) => (
            <article
              key={item.id}
              className={`rounded-2xl border px-4 py-4 ${
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
          <textarea
            ref={commentInputRef}
            value={chapterComment}
            onChange={(event) => setChapterComment(event.target.value)}
            placeholder="What landed, confused you, or needs another pass in this chapter?"
            className={`mt-4 min-h-28 w-full rounded-2xl border px-4 py-3 text-sm outline-none ${
              theme === "dark"
                ? "border-white/10 bg-[#121722] text-white placeholder:text-slate-500"
                : "border-stone-200 bg-white text-slate-950 placeholder:text-stone-400"
            }`}
          />
          <div className="mt-3 flex items-center justify-between gap-3">
            <p className={`text-xs ${theme === "dark" ? "text-slate-500" : "text-stone-500"}`}>
              {commentStatus ?? "Comments are shared with the author on this chapter."}
            </p>
            <button
              type="button"
              onClick={saveChapterComment}
              disabled={savingComment || !chapterComment.trim()}
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
}

function chapterMatchesAssignment(chapterNum: number, assignment: BetaReadAssignment) {
  if (typeof assignment.chapter_start === "number" && chapterNum < assignment.chapter_start) return false
  if (typeof assignment.chapter_end === "number" && chapterNum > assignment.chapter_end) return false
  return true
}
