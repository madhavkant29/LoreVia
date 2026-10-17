"use client"

import { useInfiniteQuery, useQuery } from "@tanstack/react-query"
import type { Route } from "next"
import Link from "next/link"
import { useParams, useSearchParams } from "next/navigation"

import { ChapterReportsView } from "./analysisPage.reports"
import { FindingsList } from "./analysisPage.findings"
import { summarizeEditorialReview } from "./analysisPage.helpers"
import { SUPPORT_HELP_EVENT } from "@/components/ui/ShortcutHelp"
import { WorkspaceFamilyHeader } from "@/components/reader/WorkspaceFamilyHeader"
import { WorkspacePage } from "@/components/ui/Workspace"
import { booksApi } from "@/lib/api/books"
import { asQueryKey, bookCacheKey } from "@/lib/query/cacheKeys"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import type { Book, ChapterConsistencyReport, ContinuityFinding, StoryHealth } from "@/types/book"

type ReviewLink = {
  href: string
  title: string
  description: string
}

const MANUSCRIPT_REVIEW_LINKS: ReviewLink[] = [
  { href: "advisor", title: "Story advisor", description: "Ask a grounded question or review LoreVia's recommended continuity checks." },
  { href: "analysis?view=chapters", title: "Chapter reports", description: "Inspect chapter-level character, relationship, thread, and continuity evidence." },
  { href: "editorial-review", title: "Editorial review", description: "Review completed prose and structure passes alongside their source document." },
  { href: "ai-beta-reader", title: "AI Beta Reader", description: "Check reader experience, repeated language, voice differences, and revision priorities." },
  { href: "voice", title: "Voice consistency", description: "Run a focused character or chapter voice review." },
]

const STRUCTURE_REVIEW_LINKS: ReviewLink[] = [
  { href: "foreshadowing", title: "Setup & Payoff", description: "Review setups, intended outcomes, and unresolved returns." },
  { href: "timeline", title: "Timeline", description: "Check chapter order, character presence, and structural turns." },
  { href: "plot-threads", title: "Plot threads", description: "Triage open, weak, and resolved story threads." },
  { href: "graph?view=evolution", title: "Relationship changes", description: "Inspect when a relationship changes and which scene supports the turn." },
  { href: "world-gap", title: "World gaps", description: "Compare manuscript statements with canon evidence and cleanup notes." },
]

function ReviewLinkList({ bookId, items, isDark }: { bookId: string; items: ReviewLink[]; isDark: boolean }) {
  return (
    <div className={`divide-y border-y ${isDark ? "divide-white/10 border-white/10" : "divide-stone-200 border-stone-200"}`}>
      {items.map((item) => (
        <Link
          key={item.href}
          href={`/${bookId}/${item.href}` as Route}
          prefetch={false}
          className="group grid gap-1 py-4 sm:grid-cols-[11rem_minmax(0,1fr)_auto] sm:items-baseline sm:gap-4"
        >
          <span className={`text-sm font-semibold ${isDark ? "text-slate-100" : "text-stone-900"}`}>{item.title}</span>
          <span className={`text-sm leading-6 ${isDark ? "text-slate-400" : "text-stone-600"}`}>{item.description}</span>
          <span className={`text-sm group-hover:underline ${isDark ? "text-teal-300" : "text-teal-800"}`}>Open</span>
        </Link>
      ))}
    </div>
  )
}

export default function AnalysisPage() {
  const { bookId } = useParams<{ bookId: string }>()
  const searchParams = useSearchParams()
  const { theme } = usePreferencesStore()
  const isDark = theme === "dark"
  const activeView = searchParams.get("view") === "chapters" ? "chapters" : "findings"
  const bookQuery = useQuery<Book>({
    queryKey: asQueryKey(bookCacheKey(bookId, "detail")),
    queryFn: () => booksApi.get(bookId),
    staleTime: 20_000,
  })
  const findingsQuery = useQuery<ContinuityFinding[]>({
    queryKey: asQueryKey(bookCacheKey(bookId, "continuity-findings")),
    queryFn: () => booksApi.getContinuityFindings(bookId, { includeStale: true }),
    staleTime: 30_000,
  })
  const reportsQuery = useInfiniteQuery<ChapterConsistencyReport[]>({
    queryKey: asQueryKey(bookCacheKey(bookId, "chapter-reports:pages:50")),
    initialPageParam: null as number | null,
    queryFn: ({ pageParam }) => booksApi.getChapterReports(bookId, 50, typeof pageParam === "number" ? pageParam : undefined),
    getNextPageParam: (lastPage) => lastPage.length === 50 ? lastPage[lastPage.length - 1].chapter_number : undefined,
    staleTime: 30_000,
  })
  const reports = reportsQuery.data?.pages.flat() ?? null
  const healthQuery = useQuery<StoryHealth>({
    queryKey: asQueryKey(bookCacheKey(bookId, "story-health")),
    queryFn: () => booksApi.getStoryHealth(bookId),
    staleTime: 30_000,
  })

  const book = bookQuery.data
  const activeQuery = activeView === "findings" ? findingsQuery : reportsQuery
  const seriesLink = book?.primary_series_id
    ? { href: `/series/${book.primary_series_id}/ask`, title: "Series questions", description: "Ask across every book connected to this series." }
    : null
  const review = summarizeEditorialReview({
    health: healthQuery.data ?? null,
    findings: findingsQuery.data ?? null,
    reports,
    failed: findingsQuery.isError || reportsQuery.isError,
  })

  return (
    <WorkspacePage className={isDark ? "text-slate-100" : "text-stone-950"}>
      <main data-analysis-workspace className="mx-auto max-w-6xl px-0 pb-16 pt-6 sm:px-2 lg:px-4">
        <WorkspaceFamilyHeader
          active="analysis"
          bookId={bookId}
          family="review-center"
          title="Findings"
          actions={<><button type="button" disabled={activeQuery.isFetching} onClick={() => void activeQuery.refetch()} className="min-h-11 rounded-sm border border-[rgb(var(--border))] px-3 text-sm disabled:opacity-50">{activeQuery.isFetching ? "Refreshing…" : "Refresh"}</button><button type="button" onClick={() => window.dispatchEvent(new Event(SUPPORT_HELP_EVENT))} className="min-h-11 rounded-sm border border-[rgb(var(--border))] px-3 text-sm">Help</button></>}
          description="Review evidence that may require an author decision, then open the focused review best suited to the issue."
        />

        {bookQuery.isError ? <div role="alert" className="mt-4 border-l-2 border-amber-400 pl-4 text-sm"><p>Book details could not load.</p><button type="button" disabled={bookQuery.isFetching} onClick={() => void bookQuery.refetch()} className="min-h-10 underline">Retry book details</button></div> : null}
        <section aria-label="Review in brief" className={`mt-6 rounded-md border p-5 sm:p-6 ${isDark ? "border-white/10 bg-[#101a20]" : "border-stone-200 bg-white"}`}>
          <p className={`text-xs font-semibold uppercase tracking-[0.14em] ${isDark ? "text-slate-400" : "text-stone-500"}`}>Review in brief</p>
          <p className="mt-3 max-w-4xl font-serif text-xl leading-8">{review.leadSentence}</p>
          {review.contextSentence ? <p className={`mt-3 max-w-4xl text-sm leading-7 ${isDark ? "text-slate-300" : "text-stone-700"}`}>{review.contextSentence}</p> : null}
          {review.storySentence ? <p className={`mt-2 max-w-4xl text-sm leading-7 ${isDark ? "text-slate-300" : "text-stone-700"}`}>{review.storySentence}</p> : null}
          <p className={`mt-4 border-t pt-3 text-xs leading-6 ${isDark ? "border-white/10 text-slate-400" : "border-stone-200 text-stone-600"}`}>{review.scopeSentence}</p>
          {findingsQuery.isError || reportsQuery.isError ? (
            <div role="alert" className={`mt-3 flex flex-wrap items-center gap-x-4 gap-y-2 text-sm ${isDark ? "text-amber-300" : "text-amber-800"}`}>
              <span>Part of this review could not load.</span>
              {findingsQuery.isError ? <button type="button" onClick={() => void findingsQuery.refetch()} className="underline underline-offset-4">Retry findings evidence</button> : null}
              {reportsQuery.isError ? <button type="button" onClick={() => void reportsQuery.refetch()} className="underline underline-offset-4">Retry chapter coverage</button> : null}
            </div>
          ) : null}
        </section>
        <div onKeyDown={(event) => {
          if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return
          const tabs = Array.from(event.currentTarget.querySelectorAll<HTMLAnchorElement>("[role=tab]"))
          const index = tabs.indexOf(event.target as HTMLAnchorElement)
          if (index < 0) return
          event.preventDefault()
          const next = event.key === "Home" ? 0 : event.key === "End" ? tabs.length - 1 : (index + (event.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length
          tabs[next].focus(); tabs[next].click()
        }} role="tablist" aria-label="Findings views" className={`mt-5 flex gap-1 overflow-x-auto border-b ${isDark ? "border-white/10" : "border-stone-200"}`}>
          <Link
            href={`/${bookId}/analysis` as Route}
            role="tab"
            aria-selected={activeView === "findings"}
            id="analysis-tab-findings"
            aria-controls="analysis-view"
            tabIndex={activeView === "findings" ? 0 : -1}
            className={`shrink-0 border-b-2 px-4 py-3 text-sm font-medium ${activeView === "findings" ? (isDark ? "border-teal-300 text-white" : "border-teal-700 text-stone-950") : (isDark ? "border-transparent text-slate-400" : "border-transparent text-stone-600")}`}
          >
            Findings list
          </Link>
          <Link
            href={`/${bookId}/analysis?view=chapters` as Route}
            role="tab"
            aria-selected={activeView === "chapters"}
            id="analysis-tab-chapters"
            aria-controls="analysis-view"
            tabIndex={activeView === "chapters" ? 0 : -1}
            className={`shrink-0 border-b-2 px-4 py-3 text-sm font-medium ${activeView === "chapters" ? (isDark ? "border-teal-300 text-white" : "border-teal-700 text-stone-950") : (isDark ? "border-transparent text-slate-400" : "border-transparent text-stone-600")}`}
          >
            Chapter reports
          </Link>
        </div>

        <div id="analysis-view" role="tabpanel" aria-labelledby={`analysis-tab-${activeView}`} aria-busy={activeQuery.isFetching}>
        {activeQuery.isError ? <div role="alert" className="mt-5 border-l-2 border-amber-400 py-2 pl-4 text-sm"><p>{activeView === "findings" ? "Continuity findings could not load." : "Chapter reports could not load."} {activeQuery.data ? "Previously loaded evidence remains below." : "Try again to check the available evidence."}</p><button type="button" disabled={activeQuery.isFetching} onClick={() => void activeQuery.refetch()} className="min-h-10 underline">Retry {activeView === "findings" ? "findings" : "chapter reports"}</button></div> : null}
        {activeQuery.isLoading ? <p role="status" className="border-b py-8 text-sm">Loading {activeView === "findings" ? "continuity findings" : "chapter reports"}…</p> : null}
        {activeView === "findings" ? <>
        {findingsQuery.data ? <FindingsList bookId={bookId} findings={findingsQuery.data} isDark={isDark} /> : null}

        <section className="mt-10" aria-label="Manuscript review">
          <h2 className="text-xl font-semibold">Manuscript review</h2>
          <p className={`mt-1 mb-4 text-sm leading-6 ${isDark ? "text-slate-400" : "text-stone-600"}`}>Choose a review by the decision you need to make.</p>
          <ReviewLinkList bookId={bookId} items={MANUSCRIPT_REVIEW_LINKS} isDark={isDark} />
        </section>

        <section className="mt-10" aria-label="Structure and canon">
          <h2 className="text-xl font-semibold">Structure and canon</h2>
          <p className={`mt-1 mb-4 text-sm leading-6 ${isDark ? "text-slate-400" : "text-stone-600"}`}>Inspect the story system around a finding without loading every workspace at once.</p>
          <ReviewLinkList bookId={bookId} items={STRUCTURE_REVIEW_LINKS} isDark={isDark} />
        </section>

        {seriesLink ? (
          <section className={`mt-10 border-t pt-5 ${isDark ? "border-white/10" : "border-stone-200"}`}>
            <Link href={seriesLink.href as Route} prefetch={false} className="group grid gap-1 sm:grid-cols-[11rem_minmax(0,1fr)_auto] sm:items-baseline sm:gap-4">
              <span className={`text-sm font-semibold ${isDark ? "text-slate-100" : "text-stone-900"}`}>{seriesLink.title}</span>
              <span className={`text-sm leading-6 ${isDark ? "text-slate-400" : "text-stone-600"}`}>{seriesLink.description}</span>
              <span className={`text-sm group-hover:underline ${isDark ? "text-teal-300" : "text-teal-800"}`}>Open</span>
            </Link>
          </section>
        ) : null}
        </> : (
          reports ? <ChapterReportsView bookId={bookId} reports={reports} findings={findingsQuery.data ?? []} canReprocess={book?.mode === "author" && book?.access_class === "owner"} hasMore={reportsQuery.hasNextPage} loadingMore={reportsQuery.isFetchingNextPage} onLoadMore={() => void reportsQuery.fetchNextPage()} isDark={isDark} /> : null
        )}
        </div>
      </main>
    </WorkspacePage>
  )
}
