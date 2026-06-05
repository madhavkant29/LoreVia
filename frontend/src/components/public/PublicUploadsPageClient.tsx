"use client"

import Link from "next/link"
import type { Route } from "next"
import { useDeferredValue, useEffect, useState } from "react"
import { useQuery } from "@tanstack/react-query"

import { publicApi } from "@/lib/api/public"
import { asQueryKey } from "@/lib/query/cacheKeys"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import type { PublicBook } from "@/types/book"
import type { PublicRankedBookListResponse, PublicUploadsOverview } from "@/types/public"

const UPLOADS_PAGE_SIZE = 24

const rankingOptions = [
  { value: "most_popular", label: "Most popular" },
  { value: "top_rated", label: "Top rated" },
  { value: "most_complex", label: "Most complex" },
  { value: "big_cast", label: "Big cast" },
  { value: "most_well_written", label: "Most well written" },
  { value: "beginner_friendly", label: "Beginner friendly" },
  { value: "recently_updated", label: "Recently updated" },
  { value: "recently_released", label: "Recently released" },
] as const

const timeWindowOptions = [
  { value: "daily", label: "Daily" },
  { value: "weekly", label: "Weekly" },
  { value: "monthly", label: "Monthly" },
  { value: "yearly", label: "Yearly" },
  { value: "all_time", label: "All time" },
] as const

function formatCompactDate(value?: string | null) {
  if (!value) return "Unpublished date hidden"
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return "Unpublished date hidden"
  return parsed.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })
}

function formatNumber(value: number) {
  return value.toLocaleString()
}

function MetricCard({ label, value, note, isDark }: { label: string; value: string; note: string; isDark: boolean }) {
  return (
    <article className={`rounded-lg border p-5 ${isDark ? "border-white/10 bg-white/[0.035]" : "border-stone-200 bg-white"}`}>
      <p className={`text-3xs font-semibold uppercase tracking-[0.2em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>{label}</p>
      <p className="mt-3 text-3xl font-semibold">{value}</p>
      <p className={`mt-2 text-sm ${isDark ? "text-slate-400" : "text-stone-600"}`}>{note}</p>
    </article>
  )
}

function RankingSelect({
  label,
  value,
  options,
  onChange,
  isDark,
}: {
  label: string
  value: string
  options: ReadonlyArray<{ value: string; label: string }>
  onChange: (value: string) => void
  isDark: boolean
}) {
  return (
    <label className="block">
      <span className={`text-sm font-medium ${isDark ? "text-slate-300" : "text-stone-700"}`}>{label}</span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className={`mt-3 w-full rounded-md border px-4 py-3 text-sm outline-none transition ${isDark ? "border-white/10 bg-white/[0.04] text-white" : "border-stone-200 bg-white text-stone-950"}`}
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  )
}

function CreatorBookCard({ book, isDark }: { book: PublicBook; isDark: boolean }) {
  return (
    <article className={`rounded-lg border p-6 ${isDark ? "border-white/10 bg-white/[0.035]" : "border-stone-200 bg-white"}`}>
      {book.ranking?.label ? (
        <div className="flex flex-wrap items-center gap-2">
          <span className={`rounded-full px-3 py-1 text-3xs font-semibold uppercase tracking-[0.18em] ${isDark ? "bg-teal-300/10 text-teal-200" : "bg-teal-50 text-teal-800"}`}>
            #{book.ranking.position ?? "?"} {book.ranking.label}
          </span>
        </div>
      ) : null}
      <p className={`mt-3 text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>
        Creator-published original
        {book.genre ? ` - ${book.genre}` : ""}
      </p>
      <h2 className="mt-3 text-2xl font-semibold">{book.title}</h2>
      {book.author_username ? (
        <Link href={`/public/writers/${book.author_username}` as Route} className={`mt-2 inline-flex text-sm font-semibold ${isDark ? "text-teal-200 hover:text-white" : "text-teal-700 hover:text-teal-900"}`}>
          @{book.author_username}
        </Link>
      ) : book.author ? (
        <p className={`mt-2 text-sm ${isDark ? "text-slate-300" : "text-stone-600"}`}>by {book.author}</p>
      ) : null}
      {book.description ? (
        <p className={`mt-4 text-sm leading-7 ${isDark ? "text-slate-300" : "text-stone-600"}`}>{book.description}</p>
      ) : null}
      <div className={`mt-5 flex flex-wrap gap-2 text-xs ${isDark ? "text-slate-400" : "text-stone-500"}`}>
        <span>{book.total_chapters ?? 0} chapters</span>
        <span>-</span>
        <span>{formatCompactDate(book.public_updated_at || book.published_at)}</span>
      </div>
      {book.ranking?.supporting_note ? (
        <p className={`mt-4 text-xs leading-6 ${isDark ? "text-slate-400" : "text-stone-500"}`}>{book.ranking.supporting_note}</p>
      ) : null}
      <div className="mt-6 flex flex-wrap gap-3">
        <Link
          href={`/public/${book.public_slug || book.id}` as Route}
          className={`inline-flex rounded-md px-4 py-2 text-sm font-semibold ${isDark ? "bg-teal-300 text-slate-950 hover:bg-teal-200" : "bg-[#1f615d] text-white hover:bg-[#174c49]"}`}
        >
          Open book
        </Link>
        {book.active_forum_post_id ? (
          <Link
            href={`/public/forum/${book.active_forum_post_id}` as Route}
            className={`inline-flex rounded-md px-4 py-2 text-sm font-semibold ${isDark ? "border border-white/10 bg-white/5 text-white hover:bg-white/10" : "border border-stone-200 bg-white text-stone-900 hover:bg-stone-50"}`}
          >
            Open discussion
          </Link>
        ) : null}
      </div>
    </article>
  )
}

export function PublicUploadsPageClient({
  initialBooks = [],
  initialRankingData,
  initialOverview = null,
}: {
  initialBooks?: PublicBook[]
  initialRankingData?: PublicRankedBookListResponse
  initialOverview?: PublicUploadsOverview | null
}) {
  const { theme } = usePreferencesStore()
  const isDark = theme === "dark"
  const [search, setSearch] = useState("")
  const [ranking, setRanking] = useState(initialRankingData?.ranking_key ?? "most_popular")
  const [timeWindow, setTimeWindow] = useState(initialRankingData?.time_window ?? "monthly")
  const [page, setPage] = useState(initialRankingData?.page ?? 1)
  const deferredSearch = useDeferredValue(search)

  useEffect(() => {
    setPage(1)
  }, [deferredSearch, ranking, timeWindow])

  const { data: rankingData, isLoading: booksLoading } = useQuery<PublicRankedBookListResponse>({
    queryKey: asQueryKey(`public:uploads:ranked:${ranking}:${timeWindow}:${deferredSearch}:${page}`),
    queryFn: () => publicApi.listRankedCreatorUploads({
      ranking,
      timeWindow,
      search: deferredSearch,
      page,
      limit: UPLOADS_PAGE_SIZE,
    }),
    staleTime: 60_000,
    initialData: (
      initialRankingData
      && page === (initialRankingData.page ?? 1)
      && ranking === initialRankingData.ranking_key
      && timeWindow === initialRankingData.time_window
      && deferredSearch.trim().length === 0
    )
      ? initialRankingData
      : undefined,
  })

  const books = rankingData?.items ?? initialBooks

  const { data: overview = initialOverview } = useQuery<PublicUploadsOverview | null>({
    queryKey: asQueryKey("public:uploads:overview"),
    queryFn: () => publicApi.getUploadsAnalytics(),
    staleTime: 120_000,
    initialData: initialOverview ?? undefined,
  })

  return (
    <main className={`min-h-screen ${isDark ? "bg-[#071211] text-white" : "bg-stone-50 text-stone-950"}`}>
      <div className="mx-auto max-w-6xl px-4 py-10">
        <div className="flex flex-wrap items-start justify-between gap-6">
          <div className="max-w-3xl">
            <p className={`text-xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-teal-300" : "text-teal-700"}`}>Public uploads</p>
            <h1 className="mt-4 text-4xl font-semibold tracking-tight">Browse creator-published books from LoreVia authors.</h1>
            <p className={`mt-4 text-base leading-8 ${isDark ? "text-slate-300" : "text-stone-600"}`}>
              This catalog only shows books published by authors through LoreVia. Public-domain demos stay in the broader public library.
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            <Link href="/public" className={`rounded-md border px-4 py-2 text-sm font-semibold ${isDark ? "border-white/10 bg-white/[0.04] text-white hover:bg-white/[0.08]" : "border-stone-200 bg-white text-stone-900 hover:bg-stone-50"}`}>
              Open mixed public library
            </Link>
            <Link href="/public/analytics" className={`rounded-md px-4 py-2 text-sm font-semibold ${isDark ? "bg-teal-300 text-slate-950 hover:bg-teal-200" : "bg-[#1f615d] text-white hover:bg-[#174c49]"}`}>
              View public upload analytics
            </Link>
          </div>
        </div>

        {overview ? (
          <section className="mt-10 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <MetricCard isDark={isDark} label="Public books" value={formatNumber(overview.total_public_books)} note="Creator-published titles currently visible." />
            <MetricCard isDark={isDark} label="Authors" value={formatNumber(overview.total_authors)} note="Distinct writers with visible public uploads." />
            <MetricCard isDark={isDark} label="Visible words" value={formatNumber(overview.total_visible_words)} note={`${formatNumber(overview.total_visible_chapters)} chapters across public uploads.`} />
            <MetricCard isDark={isDark} label="New in 30 days" value={formatNumber(overview.uploads_last_30_days)} note="Recently published creator uploads." />
          </section>
        ) : null}

        <section className="mt-10 grid gap-4 lg:grid-cols-[minmax(0,1.3fr)_minmax(0,0.7fr)_minmax(0,0.7fr)]">
          <label className="block">
            <span className={`text-sm font-medium ${isDark ? "text-slate-300" : "text-stone-700"}`}>Search creator-published books</span>
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              className={`mt-3 w-full rounded-md border px-4 py-3 text-sm outline-none transition ${isDark ? "border-white/10 bg-white/[0.04] text-white" : "border-stone-200 bg-white text-stone-950"}`}
            />
            <span className={`mt-2 block text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>Search by title, author, genre, or description.</span>
          </label>
          <RankingSelect label="Rank by" value={ranking} options={rankingOptions} onChange={setRanking} isDark={isDark} />
          <RankingSelect label="Window" value={timeWindow} options={timeWindowOptions} onChange={setTimeWindow} isDark={isDark} />
        </section>

        {rankingData?.items?.[0]?.ranking?.label ? (
          <div className={`mt-6 rounded-md border px-5 py-4 text-sm ${isDark ? "border-white/10 bg-white/[0.04] text-slate-300" : "border-stone-200 bg-white text-stone-700"}`}>
            <span className="font-semibold">{rankingData.items[0].ranking.label}</span>
            {rankingData.items[0].ranking.supporting_note ? ` / ${rankingData.items[0].ranking.supporting_note}` : ""}
          </div>
        ) : null}

        {booksLoading ? (
          <div className={`mt-12 rounded-md border px-6 py-12 text-center ${isDark ? "border-white/10 bg-white/5 text-slate-400" : "border-stone-200 bg-white text-stone-500"}`}>
            Loading creator uploads...
          </div>
        ) : books.length === 0 ? (
          <div className={`mt-12 rounded-md border px-6 py-12 text-center ${isDark ? "border-white/10 bg-white/5 text-slate-400" : "border-stone-200 bg-white text-stone-500"}`}>
            No creator-published public books matched that ranking yet.
          </div>
        ) : (
          <>
            <div className="mt-12 grid gap-5 md:grid-cols-2 xl:grid-cols-3">
              {books.map((book) => (
                <CreatorBookCard key={book.id} book={book} isDark={isDark} />
              ))}
            </div>

            {rankingData && rankingData.total > 0 ? (
              <div className="mt-8 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <p className={`text-sm ${isDark ? "text-slate-400" : "text-stone-600"}`}>
                  Showing {(rankingData.page - 1) * rankingData.limit + 1}-{Math.min(rankingData.page * rankingData.limit, rankingData.total)} of {rankingData.total} ranked uploads
                </p>
                <div className="flex items-center gap-3">
                  <button
                    type="button"
                    onClick={() => setPage((current) => Math.max(1, current - 1))}
                    disabled={rankingData.page <= 1}
                    className={`inline-flex h-10 items-center justify-center rounded-md px-4 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-50 ${isDark ? "border border-white/10 bg-white/5 text-slate-100 hover:bg-white/10" : "border border-stone-200 bg-white text-stone-900 hover:bg-stone-50"}`}
                  >
                    Previous
                  </button>
                  <span className={`text-sm ${isDark ? "text-slate-300" : "text-stone-700"}`}>Page {rankingData.page}</span>
                  <button
                    type="button"
                    onClick={() => setPage((current) => current + 1)}
                    disabled={!rankingData.has_more}
                    className={`inline-flex h-10 items-center justify-center rounded-md px-4 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-50 ${isDark ? "border border-white/10 bg-white/5 text-slate-100 hover:bg-white/10" : "border border-stone-200 bg-white text-stone-900 hover:bg-stone-50"}`}
                  >
                    Next
                  </button>
                </div>
              </div>
            ) : null}
          </>
        )}
      </div>
    </main>
  )
}
