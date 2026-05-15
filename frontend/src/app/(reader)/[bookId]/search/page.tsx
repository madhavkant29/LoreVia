"use client"

import Link from "next/link"
import { useParams, useRouter, useSearchParams } from "next/navigation"
import { useEffect, useState } from "react"
import { useQuery } from "@tanstack/react-query"

import { booksApi } from "@/lib/api/books"
import { buildDailyCapEventDetail } from "@/lib/monetization/limitRecovery"
import { readerApi } from "@/lib/api/reader"
import { asQueryKey, bookCacheKey } from "@/lib/query/cacheKeys"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import { capture } from "@/lib/analytics/posthog"
import type { Book } from "@/types/book"
import type { SearchResult, ThematicSearchResult } from "@/types/reader"

const AUTHOR_PROMPTS = [
  "Find every scene where Aria and Marcus are alone together.",
  "Show me all mentions of the prophecy.",
  "Find chapters where Kael uses his powers.",
  "Where does the Shadow Council first appear?",
]

export default function SearchPage() {
  const { bookId } = useParams<{ bookId: string }>()
  const router = useRouter()
  const searchParams = useSearchParams()
  const { theme } = usePreferencesStore()
  const isDark = theme === "dark"

  const [query, setQuery] = useState("")
  const [results, setResults] = useState<SearchResult[]>([])
  const [thematicResults, setThematicResults] = useState<ThematicSearchResult[]>([])
  const [mode, setMode] = useState<"semantic" | "thematic">("semantic")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const { data: book = null } = useQuery<Book>({
    queryKey: asQueryKey(bookCacheKey(bookId, "detail")),
    queryFn: () => booksApi.get(bookId),
    staleTime: 20_000,
  })

  useEffect(() => {
    const seededQuery = searchParams.get("q")?.trim()
    if (!seededQuery || query || loading || results.length > 0 || thematicResults.length > 0) return
    runSearch(seededQuery).catch(() => {})
  }, [loading, query, results.length, searchParams, thematicResults.length])

  const runSearch = async (nextQuery = query) => {
    const trimmed = nextQuery.trim()
    if (!trimmed) return
    setQuery(trimmed)
    setLoading(true)
    setError(null)
    capture("search_submitted", { book_id: bookId, query_len: trimmed.length, workspace: isAuthor ? "author" : "reader" })
    try {
      if (mode === "thematic") {
        const data = await readerApi.thematicSearch(bookId, trimmed)
        setThematicResults(data.results)
        setResults([])
        capture("search_results_loaded", { book_id: bookId, result_count: data.results.length, mode })
      } else {
        const data = await readerApi.search(bookId, trimmed, 9999)
        setResults(data)
        setThematicResults([])
        capture("search_results_loaded", { book_id: bookId, result_count: data.length, mode })
      }
    } catch (err: unknown) {
      setResults([])
      setThematicResults([])
      const dailyCap = buildDailyCapEventDetail(err)
      setError(dailyCap ? "You reached today's search limit. Use the upgrade or points options to keep going." : "Search failed. Please try again.")
    } finally {
      setLoading(false)
    }
  }

  const isAuthor = book?.mode === "author"

  return (
    <div className={`min-h-screen px-4 py-8 transition-colors ${isDark ? "bg-[linear-gradient(180deg,#000000_0%,#060606_44%,#0d0d0d_100%)] text-slate-100" : "bg-[linear-gradient(180deg,#fcf7ef_0%,#f8f3ec_46%,#f5f0ea_100%)] text-stone-950"}`}>
      <div className="mx-auto max-w-5xl">
        <button onClick={() => router.back()} className={`text-sm font-medium transition ${isDark ? "text-slate-400 hover:text-white" : "text-stone-500 hover:text-stone-900"}`}>{"<- Back"}</button>

        <div className="mt-4 flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className={`text-[11px] font-semibold uppercase tracking-[0.28em] ${isDark ? "text-slate-400" : "text-stone-500"}`}>
              {isAuthor ? "Author workspace" : "Reader workspace"}
            </p>
            <h1 className={`mt-2 font-serif text-5xl ${isDark ? "text-white" : "text-stone-950"}`}>
              {isAuthor ? "Search Your Writing" : "Search Book"}
            </h1>
            <p className={`mt-3 max-w-3xl text-sm leading-7 ${isDark ? "text-slate-300" : "text-stone-600"}`}>
              {isAuthor
                ? "Semantic recall across your manuscript. Ask for scenes, motifs, characters, props, or any thread you need to relocate fast."
                : "Ask for scenes, characters, or moments from the book and LoreVia will retrieve the best matching passages."}
            </p>
            <p className={`mt-2 text-xs leading-6 ${isDark ? "text-slate-500" : "text-stone-500"}`}>
              Need a short answer with chapter citations instead?{" "}
              <Link
                href={`/${bookId}/ask`}
                className={`font-semibold transition ${isDark ? "text-indigo-300 hover:text-indigo-200" : "text-violet-700 hover:text-violet-800"}`}
              >
                Use Natural Language Query
              </Link>
              .
            </p>
          </div>
          {isAuthor ? (
            <Link href={`/${bookId}/reports`} className={`rounded-full border px-4 py-2 text-sm ${isDark ? "border-white/10 bg-white/5 text-slate-200" : "border-stone-200 bg-white text-stone-700"}`}>
              View chapter reports
            </Link>
          ) : null}
        </div>

        <div className={`mt-8 rounded-[1.8rem] border p-5 sm:p-6 ${isDark ? "border-white/10 bg-black/70" : "border-stone-200 bg-white/90"}`}>
          <div className="flex flex-col gap-3 sm:flex-row">
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              onKeyDown={(event) => event.key === "Enter" && runSearch()}
              placeholder={isAuthor ? 'Find every scene where two characters are alone together' : 'Search for a scene, clue, or character moment'}
              className={`flex-1 rounded-[1rem] border px-4 py-3 text-sm outline-none ${isDark ? "border-white/10 bg-black text-white placeholder:text-slate-500" : "border-stone-200 bg-stone-50 text-stone-950 placeholder:text-stone-400"}`}
            />
            <button onClick={() => runSearch()} disabled={loading} className="rounded-[1rem] bg-[linear-gradient(135deg,#115e59,#0f766e)] px-5 py-3 text-sm font-semibold text-white disabled:opacity-50">
              {loading ? "Searching..." : isAuthor ? "Search manuscript" : "Search"}
            </button>
          </div>

          <div className="mt-4 flex flex-wrap gap-2">
            {([
              ["semantic", "Passages"],
              ["thematic", "Themes"],
            ] as Array<["semantic" | "thematic", string]>).map(([value, label]) => (
              <button
                key={value}
                type="button"
                onClick={() => setMode(value)}
                className={`rounded-full border px-3 py-2 text-xs font-semibold ${mode === value
                  ? isDark ? "border-emerald-300/30 bg-emerald-400/10 text-emerald-100" : "border-emerald-200 bg-emerald-50 text-emerald-800"
                  : isDark ? "border-white/10 bg-white/[0.03] text-slate-300" : "border-stone-200 bg-stone-50 text-stone-600"
                }`}
              >
                {label}
              </button>
            ))}
          </div>

          {isAuthor ? (
            <div className="mt-4 flex flex-wrap gap-2">
              {AUTHOR_PROMPTS.map((prompt) => (
                <button
                  key={prompt}
                  onClick={() => runSearch(prompt)}
                  className={`rounded-full border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-white/[0.03] text-slate-200" : "border-stone-200 bg-stone-50 text-stone-700"}`}
                >
                  {prompt}
                </button>
              ))}
            </div>
          ) : null}
        </div>

        {error ? <div className={`mt-6 rounded-[1.4rem] border p-4 text-sm ${isDark ? "border-rose-500/20 bg-rose-500/10 text-rose-200" : "border-rose-200 bg-rose-50 text-rose-700"}`}>{error}</div> : null}

        <div className="mt-6 space-y-4">
          {thematicResults.map((result, index) => (
            <div key={`theme-${result.chapter_number}-${index}`} className={`rounded-[1.6rem] border p-5 ${isDark ? "border-white/10 bg-white/[0.04]" : "border-stone-200 bg-white/90"}`}>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <p className={`text-xs font-semibold uppercase tracking-[0.22em] ${isDark ? "text-cyan-300" : "text-cyan-700"}`}>
                  Chapter {result.chapter_number}{result.chapter_title ? ` - ${result.chapter_title}` : ""}
                </p>
                <span className={`rounded-full px-3 py-1 text-xs ${isDark ? "bg-white/10 text-slate-300" : "bg-stone-100 text-stone-600"}`}>
                  {Math.round(result.score * 100)}% theme match
                </span>
              </div>
              <p className={`mt-3 text-sm leading-7 ${isDark ? "text-slate-300" : "text-stone-600"}`}>
                {result.summary || "Matched this theme in the chapter text or intelligence notes."}
              </p>
            </div>
          ))}

          {results.map((result, index) => (
            <div key={`${result.chapter_num}-${index}`} className={`rounded-[1.6rem] border p-5 ${isDark ? "border-white/10 bg-white/[0.04]" : "border-stone-200 bg-white/90"}`}>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <p className={`text-xs font-semibold uppercase tracking-[0.22em] ${isDark ? "text-emerald-300" : "text-emerald-700"}`}>
                  Chapter {result.chapter_num}{result.chapter_title ? ` - ${result.chapter_title}` : ""}
                </p>
                <span className={`rounded-full px-3 py-1 text-xs ${isDark ? "bg-white/10 text-slate-300" : "bg-stone-100 text-stone-600"}`}>
                  {Math.round(result.relevance * 100)}% match
                </span>
              </div>
              <p className={`mt-3 text-sm font-medium leading-7 ${isDark ? "text-white" : "text-stone-900"}`}>{result.summary}</p>
              <p className={`mt-3 text-sm leading-7 ${isDark ? "text-slate-300" : "text-stone-600"}`}>{result.text}</p>
            </div>
          ))}

          {results.length === 0 && thematicResults.length === 0 && !loading && query ? (
            <div className={`rounded-[1.6rem] border p-5 text-sm ${isDark ? "border-white/10 bg-white/[0.04] text-slate-400" : "border-stone-200 bg-white/90 text-stone-500"}`}>
              No matching passages yet. Try a broader query, a character name, or a concrete scene description.
            </div>
          ) : null}
        </div>
      </div>
    </div>
  )
}
