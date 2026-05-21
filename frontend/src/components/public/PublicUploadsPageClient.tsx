"use client"

import Link from "next/link"
import type { Route } from "next"
import { useDeferredValue, useState } from "react"
import { useQuery } from "@tanstack/react-query"

import { publicApi } from "@/lib/api/public"
import { asQueryKey } from "@/lib/query/cacheKeys"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import type { PublicBook } from "@/types/book"
import type { PublicUploadsOverview } from "@/types/public"

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
    <article className={`rounded-2xl border p-5 ${isDark ? "border-white/10 bg-white/[0.04]" : "border-stone-200 bg-white"}`}>
      <p className={`text-[11px] font-semibold uppercase tracking-[0.2em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>{label}</p>
      <p className="mt-3 text-3xl font-semibold">{value}</p>
      <p className={`mt-2 text-sm ${isDark ? "text-slate-400" : "text-stone-600"}`}>{note}</p>
    </article>
  )
}

function CreatorBookCard({ book, isDark }: { book: PublicBook; isDark: boolean }) {
  return (
    <article className={`rounded-2xl border p-6 ${isDark ? "border-white/10 bg-white/[0.04]" : "border-stone-200 bg-white"}`}>
      <p className={`text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>
        Creator-published original
        {book.genre ? ` - ${book.genre}` : ""}
      </p>
      <h2 className="mt-3 text-2xl font-semibold">{book.title}</h2>
      {book.author_username ? (
        <Link href={`/public/writers/${book.author_username}` as Route} className={`mt-2 inline-flex text-sm font-semibold ${isDark ? "text-cyan-200 hover:text-white" : "text-cyan-700 hover:text-cyan-900"}`}>
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
        <span>{formatCompactDate(book.published_at)}</span>
      </div>
      <div className="mt-6 flex flex-wrap gap-3">
        <Link
          href={`/public/${book.public_slug || book.id}` as Route}
          className={`inline-flex rounded-full px-4 py-2 text-sm font-semibold ${isDark ? "bg-white text-stone-950 hover:bg-slate-200" : "bg-stone-950 text-white hover:bg-stone-800"}`}
        >
          Open book
        </Link>
        {book.active_forum_post_id ? (
          <Link
            href={`/public/forum/${book.active_forum_post_id}` as Route}
            className={`inline-flex rounded-full px-4 py-2 text-sm font-semibold ${isDark ? "border border-white/10 bg-white/5 text-white hover:bg-white/10" : "border border-stone-200 bg-white text-stone-900 hover:bg-stone-50"}`}
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
  initialOverview = null,
}: {
  initialBooks?: PublicBook[]
  initialOverview?: PublicUploadsOverview | null
}) {
  const { theme } = usePreferencesStore()
  const isDark = theme === "dark"
  const [search, setSearch] = useState("")
  const deferredSearch = useDeferredValue(search)

  const { data: books = initialBooks, isLoading: booksLoading } = useQuery<PublicBook[]>({
    queryKey: asQueryKey(`public:uploads:${deferredSearch}`),
    queryFn: () => publicApi.listCreatorUploads({ search: deferredSearch }),
    staleTime: 60_000,
    initialData: !deferredSearch && initialBooks.length > 0 ? initialBooks : undefined,
  })

  const { data: overview = initialOverview } = useQuery<PublicUploadsOverview | null>({
    queryKey: asQueryKey("public:uploads:overview"),
    queryFn: () => publicApi.getUploadsAnalytics(),
    staleTime: 120_000,
    initialData: initialOverview ?? undefined,
  })

  return (
    <main className={`min-h-screen ${isDark ? "bg-black text-white" : "bg-stone-50 text-stone-950"}`}>
      <div className="mx-auto max-w-6xl px-4 py-10">
        <div className="flex flex-wrap items-start justify-between gap-6">
          <div className="max-w-3xl">
            <p className={`text-xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-cyan-300" : "text-cyan-700"}`}>Public uploads</p>
            <h1 className="mt-4 text-4xl font-semibold tracking-tight">Browse creator-published books from LoreVia authors.</h1>
            <p className={`mt-4 text-base leading-8 ${isDark ? "text-slate-300" : "text-stone-600"}`}>
              This catalog only shows books published by authors through LoreVia. Public-domain demos stay in the broader public library.
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            <Link href="/public" className={`rounded-full border px-4 py-2 text-sm font-semibold ${isDark ? "border-white/10 bg-white/[0.04] text-white hover:bg-white/[0.08]" : "border-stone-200 bg-white text-stone-900 hover:bg-stone-50"}`}>
              Open mixed public library
            </Link>
            <Link href="/public/analytics" className={`rounded-full px-4 py-2 text-sm font-semibold ${isDark ? "bg-white text-stone-950 hover:bg-slate-200" : "bg-stone-950 text-white hover:bg-stone-800"}`}>
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

        <section className="mt-10">
          <label className="block">
            <span className={`text-sm font-medium ${isDark ? "text-slate-300" : "text-stone-700"}`}>Search creator-published books</span>
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search by title, author, genre, or description"
              className={`mt-3 w-full rounded-2xl border px-4 py-3 text-sm outline-none transition ${isDark ? "border-white/10 bg-white/[0.04] text-white placeholder:text-slate-500" : "border-stone-200 bg-white text-stone-950 placeholder:text-stone-400"}`}
            />
          </label>
        </section>

        {booksLoading ? (
          <div className={`mt-12 rounded-2xl border px-6 py-12 text-center ${isDark ? "border-white/10 bg-white/5 text-slate-400" : "border-stone-200 bg-white text-stone-500"}`}>
            Loading creator uploads...
          </div>
        ) : books.length === 0 ? (
          <div className={`mt-12 rounded-2xl border px-6 py-12 text-center ${isDark ? "border-white/10 bg-white/5 text-slate-400" : "border-stone-200 bg-white text-stone-500"}`}>
            No creator-published public books matched that search yet.
          </div>
        ) : (
          <div className="mt-12 grid gap-5 md:grid-cols-2 xl:grid-cols-3">
            {books.map((book) => (
              <CreatorBookCard key={book.id} book={book} isDark={isDark} />
            ))}
          </div>
        )}
      </div>
    </main>
  )
}
