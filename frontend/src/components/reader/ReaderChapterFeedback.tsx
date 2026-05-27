"use client"

import Link from "next/link"
import { useMemo, useState } from "react"
import { useQuery } from "@tanstack/react-query"

import { betaReadsApi } from "@/lib/api/betaReads"
import { booksApi } from "@/lib/api/books"
import { useBookDetail } from "@/lib/hooks/useBookDetail"
import { asQueryKey, bookCacheKey } from "@/lib/query/cacheKeys"
import type { BetaReadAssignment } from "@/types/betaRead"

type ReaderChapterFeedbackProps = {
  bookId: string
  chapterNum: number
  theme: "light" | "dark"
}

export function ReaderChapterFeedback({ bookId, chapterNum, theme }: ReaderChapterFeedbackProps) {
  const { data: book } = useBookDetail(bookId)
  const [chapterComment, setChapterComment] = useState("")
  const [commentStatus, setCommentStatus] = useState<string | null>(null)
  const [savingComment, setSavingComment] = useState(false)

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

  const saveChapterComment = async () => {
    const nextComment = chapterComment.trim()
    if (!nextComment) return
    setSavingComment(true)
    setCommentStatus("Saving comment...")
    try {
      await booksApi.saveManuscriptAnnotation(bookId, {
        chapterNumber: chapterNum,
        category: "general",
        visibility: "shared",
        quote: `Chapter ${chapterNum}`,
        comment: nextComment,
      })
      setChapterComment("")
      setCommentStatus("Comment saved.")
      void annotationsQuery.refetch()
      void betaAssignmentsQuery.refetch()
    } catch {
      setCommentStatus("Could not save comment.")
    } finally {
      setSavingComment(false)
    }
  }

  if (!canLeaveChapterComment) return null

  return (
    <section className={`mx-auto mt-8 w-full max-w-[980px] rounded-[1.75rem] border px-5 py-5 sm:px-6 ${
      theme === "dark"
        ? "border-white/10 bg-white/[0.04] text-stone-100"
        : "border-stone-200 bg-white/85 text-slate-950"
    }`} style={{ contentVisibility: "auto", containIntrinsicSize: "420px" }}>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className={`text-[11px] font-semibold uppercase tracking-[0.24em] ${theme === "dark" ? "text-slate-500" : "text-stone-400"}`}>
            Reader feedback
          </p>
          <h2 className={`mt-1 text-lg font-semibold ${theme === "dark" ? "text-white" : "text-slate-950"}`}>
            Leave a chapter comment
          </h2>
          <p className={`mt-1 text-sm ${theme === "dark" ? "text-slate-400" : "text-stone-500"}`}>
            {annotationsQuery.data?.length
              ? `${annotationsQuery.data.length} chapter comment${annotationsQuery.data.length === 1 ? "" : "s"} already live here.`
              : "Comments on this chapter stay anchored to the reading flow."}
          </p>
        </div>
        {activeBetaAssignment ? (
          <Link
            href={`/${bookId}/beta-feedback`}
            className={`inline-flex min-h-11 items-center justify-center rounded-xl px-4 text-sm font-semibold ${
              theme === "dark" ? "bg-teal-700 text-white" : "bg-teal-800 text-white"
            }`}
          >
            Open full beta review
          </Link>
        ) : null}
      </div>
      <textarea
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
    </section>
  )
}

function chapterMatchesAssignment(chapterNum: number, assignment: BetaReadAssignment) {
  if (typeof assignment.chapter_start === "number" && chapterNum < assignment.chapter_start) return false
  if (typeof assignment.chapter_end === "number" && chapterNum > assignment.chapter_end) return false
  return true
}
