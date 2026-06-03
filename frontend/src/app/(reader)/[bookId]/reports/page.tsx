"use client"

import { useEffect } from "react"
import { useQuery } from "@tanstack/react-query"
import { useParams } from "next/navigation"

import { booksApi } from "@/lib/api/books"
import { WorkspaceFamilyHeader } from "@/components/reader/WorkspaceFamilyHeader"
import { WorkspaceEmptyState, WorkspacePage, WorkspacePanel } from "@/components/ui/Workspace"
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
    <WorkspacePage className={isDark ? "text-slate-100" : "text-stone-950"}>
      <div className="mx-auto max-w-5xl px-0 pb-16 pt-6 sm:px-2 lg:px-4">
        <WorkspaceFamilyHeader
          active="reports"
          bookId={bookId}
          family="review-center"
          title="Chapter reports"
          description="Review chapter-level evidence for new characters, relationship changes, plot movement, and continuity warnings."
        />

        {loading ? (
          <WorkspacePanel tone="subtle" className="mt-6 p-5 text-sm text-[rgb(var(--muted-foreground))]">
            Loading reports...
          </WorkspacePanel>
        ) : null}

        {!loading && reports.length === 0 ? (
          <WorkspaceEmptyState
            className="mt-6"
            title="No chapter reports yet"
            body="Reports will appear here after LoreVia finishes analyzing chapters in this manuscript."
          />
        ) : null}

        <div className="mt-6 space-y-4">
          {reports.map((report) => (
            <WorkspacePanel key={`${report.chapter_number}-${report.chapter_title ?? "untitled"}`} className="p-5">
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
                <div className={`mt-4 rounded-md border p-4 ${isDark ? "border-amber-500/20 bg-amber-500/10" : "border-amber-200 bg-amber-50"}`}>
                  <p className={`text-xs font-semibold uppercase tracking-[0.2em] ${isDark ? "text-amber-200" : "text-amber-800"}`}>Continuity flags</p>
                  <div className="mt-2 space-y-2">
                    {report.continuity_flags.map((flag) => (
                      <p key={flag} className={`text-sm ${isDark ? "text-slate-200" : "text-stone-700"}`}>{flag}</p>
                    ))}
                  </div>
                </div>
              ) : null}
            </WorkspacePanel>
          ))}
        </div>
      </div>
    </WorkspacePage>
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
    <div className={`rounded-md border p-4 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-stone-200 bg-stone-50"}`}>
      <p className={`text-xs font-semibold uppercase tracking-[0.2em] ${isDark ? "text-slate-400" : "text-stone-400"}`}>{title}</p>
      <div className="mt-2 space-y-2">
        {items.length > 0 ? items.map((item) => (
          <p key={item} className={`text-sm ${isDark ? "text-slate-200" : "text-stone-700"}`}>{item}</p>
        )) : <p className={`text-sm ${isDark ? "text-slate-500" : "text-stone-500"}`}>{empty}</p>}
      </div>
    </div>
  )
}
