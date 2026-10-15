import { useState } from "react"
import Link from "next/link"
import type { Route } from "next"
import type { ChapterConsistencyReport } from "@/types/book"
import { summarizeReports } from "./analysisPage.helpers"

export function ChapterReportsView({
  bookId,
  reports,
  isDark,
}: {
  bookId: string
  reports: ChapterConsistencyReport[]
  isDark: boolean
}) {
  const [chapterFilter, setChapterFilter] = useState("all")
  const effectiveFilter = reports.some((report) => String(report.chapter_number) === chapterFilter) ? chapterFilter : "all"
  const visibleReports = effectiveFilter === "all"
    ? reports
    : reports.filter((report) => String(report.chapter_number) === chapterFilter)
  const summary = summarizeReports(visibleReports)

  return (
    <div className="mt-8">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 className="text-xl font-semibold">Chapter reports</h2>
          <p className={`mt-1 max-w-2xl text-sm leading-6 ${isDark ? "text-slate-400" : "text-stone-600"}`}>
            Browse reports for up to 50 of the latest chapters by chapter number. Filter to focus on one chapter.
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
              </article>
            )
          })}
        </div>
      )}
    </div>
  )
}
