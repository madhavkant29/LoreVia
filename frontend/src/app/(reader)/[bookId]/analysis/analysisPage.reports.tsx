import { useState } from "react"
import axios from "axios"
import Link from "next/link"
import type { Route } from "next"
import type { ChapterConsistencyReport, ContinuityFinding } from "@/types/book"
import { booksApi } from "@/lib/api/books"
import { findingChapter, summarizeReports } from "./analysisPage.helpers"

export function ChapterReportsView({
  bookId,
  reports,
  findings = [],
  canReprocess = false,
  hasMore = false,
  loadingMore = false,
  onLoadMore,
  isDark,
}: {
  bookId: string
  reports: ChapterConsistencyReport[]
  findings?: ContinuityFinding[]
  canReprocess?: boolean
  hasMore?: boolean
  loadingMore?: boolean
  onLoadMore?: () => void
  isDark: boolean
}) {
  const [chapterFilter, setChapterFilter] = useState("all")
  const [confirmReprocessChapter, setConfirmReprocessChapter] = useState<number | null>(null)
  const [reprocessingChapter, setReprocessingChapter] = useState<number | null>(null)
  const [reprocessStatus, setReprocessStatus] = useState<{ chapter: number; message: string; error: boolean } | null>(null)
  const effectiveFilter = reports.some((report) => String(report.chapter_number) === chapterFilter) ? chapterFilter : "all"
  const visibleReports = effectiveFilter === "all"
    ? reports
    : reports.filter((report) => String(report.chapter_number) === chapterFilter)
  const summary = summarizeReports(visibleReports)

  async function reprocessChapter(chapterNumber: number) {
    if (reprocessingChapter !== null) return
    setReprocessingChapter(chapterNumber)
    setReprocessStatus(null)
    try {
      await booksApi.reprocessChapter(bookId, chapterNumber)
      setConfirmReprocessChapter(null)
      setReprocessStatus({ chapter: chapterNumber, message: `Chapter ${chapterNumber} reprocessing started. Refresh the reports after processing finishes.`, error: false })
    } catch (error) {
      const status = axios.isAxiosError(error) ? error.response?.status : undefined
      const message = status === 429
        ? "Processing allowance is not available right now. Try again after it refreshes."
        : status === 409
          ? "Another chapter is already processing. Try again when it finishes."
          : status === 400
            ? "Save this chapter's content before reprocessing it."
            : "Could not start chapter reprocessing. Please try again."
      setReprocessStatus({ chapter: chapterNumber, message, error: true })
    } finally {
      setReprocessingChapter(null)
    }
  }

  return (
    <div className="mt-8">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 className="text-xl font-semibold">Chapter reports</h2>
          <p className={`mt-1 max-w-2xl text-sm leading-6 ${isDark ? "text-slate-400" : "text-stone-600"}`}>
            Browse reports from newest to oldest. Load older chapters as needed, or filter the reports already loaded.
          </p>
        </div>
        {reports.length > 0 ? (
          <label className={`min-w-0 max-w-full text-sm ${isDark ? "text-slate-400" : "text-stone-600"}`}>
            Chapter
            <select
              aria-label="Filter chapter reports"
              value={effectiveFilter}
              onChange={(event) => setChapterFilter(event.target.value)}
              className={`mt-1 block w-full min-w-0 max-w-xs rounded-sm border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-[#0b1514] text-slate-100" : "border-stone-200 bg-white text-stone-900"}`}
            >
              <option value="all">All chapters</option>
              {reports.map((report) => (
                <option key={report.chapter_number} value={String(report.chapter_number)}>
                  Chapter {report.chapter_number}{report.chapter_title ? ` — ${report.chapter_title}` : ""}
                </option>
              ))}
            </select>
          </label>
        ) : null}
      </div>

      {reports.length > 0 ? (
        <dl className={`mt-5 flex flex-wrap gap-x-6 border-y ${isDark ? "border-white/10" : "border-stone-200"}`} aria-label="Chapter report summary">
          {[["Chapters shown", summary.chapters], ["Recorded changes", summary.changes], ["Continuity flags", summary.flags]].map(([label, value]) => (
            <div key={label} className="flex items-baseline gap-2 py-3">
              <dt className={`text-sm ${isDark ? "text-slate-400" : "text-stone-600"}`}>{label}</dt>
              <dd className="text-sm font-semibold tabular-nums">{value}</dd>
            </div>
          ))}
        </dl>
      ) : null}

      {reports.length === 0 ? (
        <div className={`mt-5 border-y py-6 text-sm leading-6 ${isDark ? "border-white/10 text-slate-400" : "border-stone-200 text-stone-600"}`}>
          <p>No chapter reports are available yet. Open Chapters to check import and processing progress.</p>
          <Link href={`/${bookId}/chapters` as Route} className="mt-3 inline-block underline">Open Chapters</Link>
        </div>
      ) : (
        <div className={`mt-6 divide-y border-y ${isDark ? "divide-white/10 border-white/10" : "divide-stone-200 border-stone-200"}`}>
          {visibleReports.map((report) => {
            const chapterFindings = findings.filter((finding) =>
              !finding.is_stale && !finding.decision && finding.status !== "resolved" && findingChapter(finding) === report.chapter_number
            )
            const editorialConcerns = report.editorial_concerns ?? []
            const revisionQuestion = report.revision_question
            const groups = [
              ["New characters", report.new_characters.map((character) => character.name)],
              ["Relationship changes", report.relationship_changes],
              ["Threads opened", report.plot_threads_opened],
              ["Threads resolved", report.plot_threads_resolved],
            ].filter((entry): entry is [string, string[]] => entry[1].length > 0)

            return (
              <article key={`${report.chapter_number}-${report.chapter_title ?? "untitled"}`} className="py-6">
                <div className="flex flex-wrap items-baseline justify-between gap-3">
                  <div className="min-w-0 max-w-full">
                    <h3 className="break-words text-lg font-semibold">Chapter {report.chapter_number}{report.chapter_title ? ` — ${report.chapter_title}` : ""}</h3>
                    <p className={`mt-2 max-w-3xl break-words text-sm leading-7 ${isDark ? "text-slate-300" : "text-stone-700"}`}>{report.summary}</p>
                  </div>
                  <Link href={`/${bookId}/chapter/${report.chapter_number}` as Route} className={`text-sm font-medium underline decoration-transparent underline-offset-4 hover:decoration-current ${isDark ? "text-teal-300" : "text-teal-800"}`}>
                    Open chapter
                  </Link>
                </div>

                {groups.length > 0 ? (
                  <dl className={`mt-5 divide-y border-y ${isDark ? "divide-white/10 border-white/10" : "divide-stone-200 border-stone-200"}`}>
                    {groups.map(([label, values]) => (
                      <div key={label} className="grid gap-2 py-3 sm:grid-cols-[11rem_minmax(0,1fr)] sm:gap-4">
                        <dt className={`text-xs font-medium ${isDark ? "text-slate-400" : "text-stone-600"}`}>{label}</dt>
                        <dd className={`min-w-0 break-words text-sm leading-6 ${isDark ? "text-slate-200" : "text-stone-700"}`}>{values.join(" · ")}</dd>
                      </div>
                    ))}
                  </dl>
                ) : (
                  <p className={`mt-4 text-sm ${isDark ? "text-slate-400" : "text-stone-600"}`}>No cast, relationship, or plot-thread change was recorded.</p>
                )}

                {report.continuity_flags.length > 0 ? (
                  <div className={`mt-5 border-l-2 pl-4 ${isDark ? "border-amber-400 text-slate-200" : "border-amber-500 text-stone-700"}`}>
                    <p className="text-sm font-semibold">Continuity flags</p>
                    {report.continuity_flags.map((flag) => <p key={flag} className="mt-1 break-words text-sm leading-6">{flag}</p>)}
                  </div>
                ) : null}
                {chapterFindings.length > 0 || editorialConcerns.length > 0 ? (
                  <section className={`mt-5 border-t pt-4 ${isDark ? "border-white/10" : "border-stone-200"}`} aria-label={`Chapter ${report.chapter_number} review concerns`}>
                    <h4 className="text-sm font-semibold">What needs a closer look</h4>
                    {chapterFindings.map((finding) => (
                      <div key={finding.id} className="mt-3">
                        <p className="text-sm font-medium">{finding.title}</p>
                        <p className={`mt-1 text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-700"}`}>{finding.explanation}</p>
                      </div>
                    ))}
                    {editorialConcerns.map((concern, index) => (
                      <div key={`${concern.issue}-${index}`} className="mt-3">
                        <p className="text-sm font-medium">{concern.issue}</p>
                        <blockquote className={`mt-1 border-l-2 pl-3 text-sm leading-6 ${isDark ? "border-slate-600 text-slate-300" : "border-stone-300 text-stone-700"}`}>{concern.evidence}</blockquote>
                        {concern.suggestion ? <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-700"}`}>{concern.suggestion}</p> : null}
                      </div>
                    ))}
                  </section>
                ) : revisionQuestion ? (
                  <section className={`mt-5 border-t pt-4 ${isDark ? "border-white/10" : "border-stone-200"}`} aria-label={`Chapter ${report.chapter_number} revision question`}>
                    <h4 className="text-sm font-semibold">A question for revision</h4>
                    <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-700"}`}>{revisionQuestion.question}</p>
                    <blockquote className={`mt-2 border-l-2 pl-3 text-sm leading-6 ${isDark ? "border-slate-600 text-slate-300" : "border-stone-300 text-stone-700"}`}>{revisionQuestion.evidence}</blockquote>
                  </section>
                ) : report.editorial_concerns == null || report.continuity_flags.length === 0 ? (
                  <div className={`mt-5 text-sm leading-6 ${isDark ? "text-slate-400" : "text-stone-600"}`}>
                    <p>{report.editorial_concerns == null
                      ? "A chapter-level editorial note has not been recorded for this chapter yet. No problem should be inferred from missing analysis."
                      : "This pass found no chapter-specific problem with supporting evidence. That is not a claim that the chapter needs no revision."}</p>
                    {report.editorial_concerns == null && canReprocess ? (
                      <div className="mt-3">
                        {confirmReprocessChapter === report.chapter_number ? (
                          <div className={`rounded-sm border p-3 ${isDark ? "border-white/20" : "border-stone-300"}`} aria-label={`Confirm Chapter ${report.chapter_number} reprocessing`}>
                            <p>This reads the saved chapter again and uses processed-word allowance. Save any manuscript edits first.</p>
                            <div className="mt-3 flex flex-wrap gap-3">
                              <button type="button" onClick={() => void reprocessChapter(report.chapter_number)} disabled={reprocessingChapter !== null} className="min-h-10 rounded-sm bg-teal-700 px-3 text-sm font-semibold text-white disabled:opacity-50">{reprocessingChapter === report.chapter_number ? "Starting…" : "Start chapter reprocess"}</button>
                              <button type="button" onClick={() => setConfirmReprocessChapter(null)} disabled={reprocessingChapter !== null} className="min-h-10 rounded-sm border px-3 text-sm disabled:opacity-50">Cancel</button>
                            </div>
                          </div>
                        ) : (
                          <button type="button" onClick={() => { setConfirmReprocessChapter(report.chapter_number); setReprocessStatus(null) }} disabled={reprocessingChapter !== null} className="min-h-10 font-medium underline underline-offset-4 disabled:opacity-50">Reprocess Chapter {report.chapter_number}</button>
                        )}
                        <Link href={`/${bookId}/manuscript` as Route} className="ml-4 inline-block font-medium underline underline-offset-4">Open Manuscript Editor</Link>
                      </div>
                    ) : null}
                    {reprocessStatus?.chapter === report.chapter_number ? <p role={reprocessStatus.error ? "alert" : "status"} className={`mt-2 ${reprocessStatus.error ? isDark ? "text-amber-300" : "text-amber-800" : isDark ? "text-teal-300" : "text-teal-800"}`}>{reprocessStatus.message}</p> : null}
                  </div>
                ) : null}
              </article>
            )
          })}
        </div>
      )}
      {hasMore && onLoadMore ? (
        <button type="button" onClick={onLoadMore} disabled={loadingMore} className={`mt-5 rounded-sm border px-4 py-2 text-sm font-medium disabled:opacity-50 ${isDark ? "border-white/20 text-slate-100" : "border-stone-300 text-stone-900"}`}>
          {loadingMore ? "Loading older reports…" : "Load older reports"}
        </button>
      ) : null}
    </div>
  )
}
