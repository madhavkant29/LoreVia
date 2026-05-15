"use client"

import { useMemo, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import Link from "next/link"
import { useParams } from "next/navigation"

import { intelligenceApi } from "@/lib/api/intelligence"
import { booksApi } from "@/lib/api/books"
import { asQueryKey, booksListCacheKey } from "@/lib/query/cacheKeys"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import type { Book } from "@/types/book"
import type { CrossBookIntelligence, CrossBookMatch } from "@/types/intelligence"

type MatchMode = "all" | "characters" | "wiki"

type MatchWithBooks = CrossBookMatch & {
  source: "characters" | "wiki"
  left_book_title?: string
  right_book_title?: string
}

export default function CrossBookWikiPage() {
  const { bookId } = useParams<{ bookId: string }>()
  const { theme } = usePreferencesStore()
  const isDark = theme === "dark"
  const { data: intelligenceData = null, isLoading: intelligenceLoading } = useQuery<CrossBookIntelligence | null>({
    queryKey: asQueryKey(`cross-book-wiki:${bookId}`),
    queryFn: () => intelligenceApi.getCrossBookIntelligence(bookId),
  })
  const { data: booksData = [], isLoading: booksLoading } = useQuery<Book[]>({
    queryKey: asQueryKey(booksListCacheKey()),
    queryFn: () => booksApi.list(),
  })
  const [mode, setMode] = useState<MatchMode>("all")
  const [threshold, setThreshold] = useState(60)
  const [query, setQuery] = useState("")
  const loading = intelligenceLoading || booksLoading
  const books = useMemo(() => new Map(booksData.map((book) => [book.id, book])), [booksData])

  const matches = useMemo(() => {
    const allMatches: MatchWithBooks[] = [
      ...((intelligenceData?.character_matches ?? []).map((item) => ({
        ...item,
        source: "characters" as const,
        left_book_title: books.get(item.left_book_id)?.title,
        right_book_title: books.get(item.right_book_id)?.title,
      }))),
      ...((intelligenceData?.wiki_matches ?? []).map((item) => ({
        ...item,
        source: "wiki" as const,
        left_book_title: books.get(item.left_book_id)?.title,
        right_book_title: books.get(item.right_book_id)?.title,
      }))),
    ]
    const normalizedQuery = query.trim().toLowerCase()
    return allMatches
      .filter((item) => mode === "all" || item.source === mode)
      .filter((item) => Math.round(item.similarity * 100) >= threshold)
      .filter((item) => {
        if (!normalizedQuery) return true
        return [
          item.left_name,
          item.right_name,
          item.left_book_title ?? "",
          item.right_book_title ?? "",
          item.entry_type ?? "",
        ].some((value) => value.toLowerCase().includes(normalizedQuery))
      })
      .sort((a, b) => b.similarity - a.similarity)
  }, [intelligenceData, mode, query, threshold, books])

  return (
    <div className={`min-h-screen px-4 py-10 ${isDark ? "bg-[radial-gradient(circle_at_top,#111827,#05070d_65%)] text-stone-100" : "bg-[linear-gradient(180deg,#fcfdff,#eef3f9)] text-slate-950"}`}>
      <div className="mx-auto max-w-6xl space-y-8">
        <div className="flex flex-wrap gap-3">
          <Link href={`/${bookId}`} className={pillClass(isDark)}>Back to book</Link>
          <Link href="/series" className={pillClass(isDark)}>Series</Link>
          <Link href="/library" className={pillClass(isDark)}>Library</Link>
        </div>

        <section className={`rounded-[2rem] border p-6 shadow-[0_28px_100px_-56px_rgba(15,23,42,0.45)] ${isDark ? "border-white/10 bg-[linear-gradient(145deg,#0f172a,#0a1020_55%,#13243a)]" : "border-white/70 bg-[linear-gradient(145deg,#ffffff,#f8fbff_55%,#edf4ff)]"}`}>
          <p className={`text-xs font-semibold uppercase tracking-[0.32em] ${isDark ? "text-sky-200" : "text-sky-700"}`}>Cross-book wiki</p>
          <h1 className={`mt-3 font-serif text-5xl leading-tight ${isDark ? "text-white" : "text-slate-950"}`}>Find connections across your series</h1>
          <p className={`mt-4 max-w-3xl text-sm leading-7 ${isDark ? "text-stone-300" : "text-slate-600"}`}>
            This tool identifies similar characters and wiki entries across different books in your series. It helps you spot recurring themes, character archetypes, and continuity points.
          </p>

          <div className="mt-6 grid gap-4 lg:grid-cols-[1fr_auto] lg:items-start">
            <div className={`rounded-[1.4rem] border p-4 ${isDark ? "border-white/10 bg-black/20" : "border-slate-200 bg-white/85"}`}>
              <label className={`text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-stone-400" : "text-slate-500"}`}>Search matches</label>
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search by name, book title, or type..."
                className={`mt-3 w-full rounded-2xl border px-4 py-3 text-sm outline-none transition ${isDark ? "border-white/10 bg-white/5 text-white placeholder:text-stone-500 focus:border-sky-300/40" : "border-slate-200 bg-white text-slate-950 placeholder:text-slate-400 focus:border-slate-400"}`}
              />
              <div className={`mt-4 flex flex-wrap gap-2`}>
                {(["all", "characters", "wiki"] as MatchMode[]).map((value) => (
                  <button
                    key={value}
                    onClick={() => setMode(value)}
                    className={`rounded-full px-4 py-2 text-sm font-medium transition ${
                      mode === value
                        ? (isDark ? "bg-amber-300 text-slate-950" : "bg-slate-950 text-white")
                        : (isDark ? "border border-white/10 bg-white/5 text-stone-300 hover:bg-white/10" : "border border-slate-200 bg-white text-slate-600 hover:bg-slate-50")
                    }`}
                  >
                    {value === "all" ? "All matches" : value === "characters" ? "Characters" : "Wiki entries"}
                  </button>
                ))}
              </div>

              <div className={`mt-4 rounded-[1.2rem] border p-4 ${isDark ? "border-white/10 bg-white/[0.04]" : "border-slate-200 bg-slate-50"}`}>
                <div className="flex items-center justify-between">
                  <label className={`text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-stone-400" : "text-slate-500"}`}>Similarity threshold: {threshold}%</label>
                  <span className={`text-xs ${isDark ? "text-stone-500" : "text-slate-500"}`}>Only show matches above this score</span>
                </div>
                <div className="mt-2 flex items-center gap-4">
                  <input
                    type="range"
                    min={40}
                    max={95}
                    value={threshold}
                    onChange={(event) => setThreshold(Number(event.target.value))}
                    className="w-full"
                  />
                  <span className={`min-w-[3rem] text-sm font-semibold ${isDark ? "text-white" : "text-slate-900"}`}>{threshold}%</span>
                </div>
                <div className={`mt-2 flex justify-between text-xs ${isDark ? "text-stone-500" : "text-slate-500"}`}>
                  <span>40% (loose)</span>
                  <span>95% (strict)</span>
                </div>
              </div>
            </div>

            <div className={`grid grid-cols-1 gap-3 text-sm ${isDark ? "text-stone-300" : "text-slate-600"} lg:w-[18rem]`}>
              <div className={`rounded-2xl border p-3 ${isDark ? "border-white/10 bg-white/5" : "border-slate-200 bg-slate-50"}`}>
                <p className="text-xs uppercase tracking-[0.2em] opacity-70">Series</p>
                <p className="mt-2 font-semibold">{intelligenceData?.series_name ?? "Unassigned"}</p>
              </div>
              <div className={`rounded-2xl border p-3 ${isDark ? "border-white/10 bg-white/5" : "border-slate-200 bg-slate-50"}`}>
                <p className="text-xs uppercase tracking-[0.2em] opacity-70">Matches found</p>
                <p className="mt-2 font-semibold">{matches.length}</p>
              </div>
              <div className={`rounded-2xl border p-3 ${isDark ? "border-white/10 bg-white/5" : "border-slate-200 bg-slate-50"}`}>
                <p className="text-xs uppercase tracking-[0.2em] opacity-70">Books compared</p>
                <p className="mt-2 font-semibold">{intelligenceData?.comparison_book_ids.length ?? 0}</p>
              </div>
            </div>
          </div>
        </section>

        {loading ? (
          <div className={`rounded-[1.8rem] border border-dashed py-20 text-center ${isDark ? "border-white/10 text-stone-400" : "border-slate-300 text-slate-500"}`}>Loading cross-book connections...</div>
        ) : matches.length === 0 ? (
          <div className={`rounded-[1.8rem] border p-8 ${isDark ? "border-white/10 bg-white/[0.04]" : "border-slate-200 bg-white/85"}`}>
            <h2 className={`text-2xl font-semibold ${isDark ? "text-white" : "text-slate-950"}`}>No matches found</h2>
            <p className={`mt-3 max-w-2xl text-sm leading-7 ${isDark ? "text-stone-300" : "text-slate-600"}`}>
              {intelligenceData?.comparison_book_ids.length === 0 || (intelligenceData?.comparison_book_ids.length ?? 0) < 2
                ? "You need at least 2 books in the same series to find cross-book connections. Add more books to your series and try again."
                : "Try lowering the similarity threshold or clearing the search filters to see more results."
              }
            </p>
          </div>
        ) : (
          <section className={`overflow-hidden rounded-[1.8rem] border ${isDark ? "border-white/10 bg-white/[0.04]" : "border-slate-200 bg-white/85"}`}>
            <div className={`grid grid-cols-[1fr_1fr_auto] gap-3 px-5 py-4 text-sm ${isDark ? "border-b border-white/10 text-stone-300" : "border-b border-slate-200 text-slate-600"}`}>
              <p className="font-semibold uppercase tracking-[0.22em]">This book</p>
              <p className="font-semibold uppercase tracking-[0.22em]">Connected to</p>
              <p className="font-semibold uppercase tracking-[0.22em] text-right">Similarity</p>
            </div>
            <div className={`divide-y ${isDark ? "divide-white/10" : "divide-slate-200"}`}>
              {matches.slice(0, 120).map((match) => {
                const score = Math.round(match.similarity * 100)
                const scoreColor = score >= 80
                  ? (isDark ? "bg-emerald-500/20 text-emerald-300" : "bg-emerald-100 text-emerald-700")
                  : score >= 60
                    ? (isDark ? "bg-amber-500/20 text-amber-300" : "bg-amber-100 text-amber-700")
                    : (isDark ? "bg-slate-500/20 text-slate-300" : "bg-slate-100 text-slate-600")
                const isCurrentBook = match.left_book_id === bookId
                const currentBookName = isCurrentBook ? match.left_name : match.right_name
                const currentBookTitle = isCurrentBook ? match.left_book_title : match.right_book_title
                const otherBookName = isCurrentBook ? match.right_name : match.left_name
                const otherBookTitle = isCurrentBook ? match.right_book_title : match.left_book_title
                const otherBookId = isCurrentBook ? match.right_book_id : match.left_book_id

                return (
                  <div key={`${match.source}:${match.left_book_id}:${match.left_name}:${match.right_book_id}:${match.right_name}`} className={`px-5 py-4 ${isDark ? "bg-transparent" : "bg-transparent"}`}>
                    <div className="flex items-start gap-4">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <p className={`text-xs font-semibold uppercase tracking-[0.18em] ${match.source === "wiki" ? (isDark ? "text-sky-200" : "text-sky-700") : (isDark ? "text-amber-200" : "text-amber-700")}`}>
                            {match.source === "wiki" ? "Wiki" : "Character"}
                          </p>
                          {match.entry_type && (
                            <p className={`text-xs ${isDark ? "text-stone-500" : "text-slate-500"}`}>
                              · {match.entry_type}
                            </p>
                          )}
                        </div>
                        <p className={`mt-2 truncate text-base font-semibold ${isDark ? "text-white" : "text-slate-950"}`}>
                          {currentBookName}
                        </p>
                        <p className={`mt-1 text-xs ${isDark ? "text-stone-400" : "text-slate-500"}`}>
                          {currentBookTitle || "Unknown book"}
                        </p>
                      </div>
                      <div className={`flex-1 min-w-0`}>
                        <p className={`mt-6 truncate text-base font-semibold ${isDark ? "text-white" : "text-slate-950"}`}>
                          {otherBookName}
                        </p>
                        <p className={`mt-1 text-xs ${isDark ? "text-stone-400" : "text-slate-500"}`}>
                          {otherBookTitle || "Unknown book"}
                        </p>
                        {otherBookId && (
                          <Link
                            href={`/${otherBookId}`}
                            className={`mt-2 inline-block text-xs font-medium ${isDark ? "text-sky-300 hover:text-sky-200" : "text-sky-600 hover:text-sky-700"}`}
                          >
                            View book →
                          </Link>
                        )}
                      </div>
                      <div className={`shrink-0 rounded-full px-3 py-1 text-sm font-semibold ${scoreColor}`}>
                        {score}%
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
            {matches.length > 120 ? (
              <div className={`px-5 py-4 text-sm ${isDark ? "border-t border-white/10 text-stone-400" : "border-t border-slate-200 text-slate-500"}`}>
                Showing top 120 of {matches.length} matches. Use filters to narrow results.
              </div>
            ) : null}
          </section>
        )}
      </div>
    </div>
  )
}

function pillClass(isDark: boolean) {
  return isDark
    ? "rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm text-stone-300 hover:bg-white/10 hover:text-white"
    : "rounded-full border border-slate-200 bg-white px-4 py-2 text-sm text-slate-600 hover:bg-slate-50 hover:text-slate-950"
}
