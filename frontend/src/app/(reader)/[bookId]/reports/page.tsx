"use client"

import Link from "next/link"
import { useEffect } from "react"
import { useQuery } from "@tanstack/react-query"
import { useParams } from "next/navigation"

import { booksApi } from "@/lib/api/books"
import { asQueryKey, bookCacheKey } from "@/lib/query/cacheKeys"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import { capture } from "@/lib/analytics/posthog"
import type { ChapterConsistencyReport } from "@/types/book"

export default function ChapterReportsPage() {
  const { bookId } = useParams<{ bookId: string }>()
  const { theme } = usePreferencesStore()
  const isDark = theme === "dark"

  useEffect(() => {
    capture("author_reports_opened", { book_id: bookId })
  }, [bookId])
  const { data: reports = [], isLoading: loading } = useQuery<ChapterConsistencyReport[]>({
    queryKey: asQueryKey(bookCacheKey(bookId, "chapter-reports:12")),
    queryFn: () => booksApi.getChapterReports(bookId),
    staleTime: 30_000,
  })

  return (
    <div className={`min-h-screen ${isDark ? "bg-[linear-gradient(180deg,#000000_0%,#060606_44%,#0d0d0d_100%)] text-slate-100" : "bg-[linear-gradient(180deg,#fcf7ef_0%,#f8f3ec_46%,#f5f0ea_100%)] text-stone-950"}`}>
      <div className="mx-auto max-w-5xl px-4 pb-16 pt-6 sm:px-6 lg:px-8">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className={`font-serif text-4xl ${isDark ? "text-white" : "text-stone-950"}`}>Chapter Analysis</h1>
            <p className={`mt-3 max-w-3xl text-sm leading-7 ${isDark ? "text-slate-300" : "text-stone-600"}`}>
              Track characters, relationships, plot threads, and continuity across each chapter.
            </p>
          </div>
          <div className="flex gap-2">
            <Link href={`/${bookId}/plot-threads`} className="rounded-full bg-[linear-gradient(135deg,#115e59,#0f766e)] px-4 py-2 text-sm font-semibold text-white">Plot threads</Link>
          </div>
        </div>

        {loading ? (
          <div className={`mt-8 rounded-[1.6rem] border p-5 text-sm ${isDark ? "border-white/10 bg-white/5 text-slate-300" : "border-stone-200 bg-white/70 text-stone-600"}`}>
            Loading reports...
          </div>
        ) : null}

        <div className="mt-8 space-y-4">
          {reports.map((report) => (
            <div key={`${report.chapter_number}-${report.chapter_title ?? "untitled"}`} className={`rounded-[1.6rem] border p-5 ${isDark ? "border-white/10 bg-black/60" : "border-stone-200 bg-white/90"}`}>
              <p className={`text-xs font-semibold uppercase tracking-[0.22em] ${isDark ? "text-emerald-300" : "text-emerald-700"}`}>
                Chapter {report.chapter_number}{report.chapter_title ? ` - ${report.chapter_title}` : ""}
              </p>
              <p className={`mt-3 text-sm leading-7 ${isDark ? "text-slate-200" : "text-stone-700"}`}>{report.summary}</p>
              <div className="mt-4 grid gap-4 sm:grid-cols-2">
                <ReportGroup title="New characters" items={report.new_characters.map((character) => character.name)} isDark={isDark} empty="No new characters detected." />
                <ReportGroup title="Relationship changes" items={report.relationship_changes} isDark={isDark} empty="No relationship changes detected." />
                <ReportGroup title="Threads opened" items={report.plot_threads_opened} isDark={isDark} empty="No new threads opened." />
                <ReportGroup title="Threads resolved" items={report.plot_threads_resolved} isDark={isDark} empty="No threads resolved." />
              </div>
              {report.continuity_flags.length > 0 ? (
                <div className={`mt-4 rounded-[1rem] border p-4 ${isDark ? "border-amber-500/20 bg-amber-500/10" : "border-amber-200 bg-amber-50"}`}>
                  <p className={`text-xs font-semibold uppercase tracking-[0.2em] ${isDark ? "text-amber-200" : "text-amber-800"}`}>Continuity flags</p>
                  <div className="mt-2 space-y-2">
                    {report.continuity_flags.map((flag) => (
                      <p key={flag} className={`text-sm ${isDark ? "text-slate-200" : "text-stone-700"}`}>{flag}</p>
                    ))}
                  </div>
                </div>
              ) : null}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function ReportGroup({
  title,
  items,
  isDark,
  empty,
}: {
  title: string
  items: string[]
  isDark: boolean
  empty: string
}) {
  return (
    <div className={`rounded-[1rem] border p-4 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-stone-200 bg-stone-50"}`}>
      <p className={`text-xs font-semibold uppercase tracking-[0.2em] ${isDark ? "text-slate-400" : "text-stone-400"}`}>{title}</p>
      <div className="mt-2 space-y-2">
        {items.length > 0 ? items.map((item) => (
          <p key={item} className={`text-sm ${isDark ? "text-slate-200" : "text-stone-700"}`}>{item}</p>
        )) : <p className={`text-sm ${isDark ? "text-slate-500" : "text-stone-500"}`}>{empty}</p>}
      </div>
    </div>
  )
}
