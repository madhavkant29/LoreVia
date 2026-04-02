"use client"

import { useState } from "react"
import Link from "next/link"
import { useParams, useRouter } from "next/navigation"

import { readerApi } from "@/lib/api/reader"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import type { ThematicSearchResult } from "@/types/reader"

const SUGGESTED_QUERIES = ["family pressure", "transformation", "guilt", "isolation", "money anxiety", "duty"]

export default function ThemesPage() {
  const { bookId } = useParams<{ bookId: string }>()
  const router = useRouter()
  const { theme } = usePreferencesStore()
  const isDark = theme === "dark"

  const [query, setQuery] = useState("")
  const [results, setResults] = useState<ThematicSearchResult[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [hasSearched, setHasSearched] = useState(false)

  const search = async (nextQuery?: string) => {
    const activeQuery = (nextQuery ?? query).trim()
    if (!activeQuery) return
    setQuery(activeQuery)
    setHasSearched(true)
    setError(null)
    setLoading(true)
    try {
      const response = await readerApi.thematicSearch(bookId, activeQuery)
      setResults(response.results)
    } catch (e: any) {
      setError(e.response?.data?.detail ?? "Thematic search unavailable")
      setResults([])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className={`min-h-screen px-4 py-8 transition-colors ${isDark ? "bg-[radial-gradient(circle_at_top,#1a2235,#090c13_62%)] text-stone-100" : "bg-[linear-gradient(180deg,#fcfcfe,#f1f5f9)] text-slate-950"}`}>
      <div className="mx-auto max-w-5xl">
        <div className="flex flex-wrap items-center gap-3">
          <button onClick={() => router.back()} className={isDark ? "rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm text-stone-300 hover:bg-white/10 hover:text-white" : "rounded-full border border-slate-200 bg-white px-4 py-2 text-sm text-slate-600 hover:bg-slate-50 hover:text-slate-950"}>
            {"<- Back"}
          </button>
          <Link href="/library" className={isDark ? "rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm text-stone-300 hover:bg-white/10 hover:text-white" : "rounded-full border border-slate-200 bg-white px-4 py-2 text-sm text-slate-600 hover:bg-slate-50 hover:text-slate-950"}>
            Library
          </Link>
          <Link href="/" className={isDark ? "rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm text-stone-300 hover:bg-white/10 hover:text-white" : "rounded-full border border-slate-200 bg-white px-4 py-2 text-sm text-slate-600 hover:bg-slate-50 hover:text-slate-950"}>
            Home
          </Link>
        </div>

        <section className={`mt-6 overflow-hidden rounded-[2rem] border p-8 shadow-[0_30px_120px_-60px_rgba(15,23,42,0.35)] ${isDark ? "border-white/10 bg-[radial-gradient(circle_at_top_right,rgba(125,211,252,0.16),transparent_28%),linear-gradient(145deg,#101726,#0a0d14)]" : "border-white/70 bg-[radial-gradient(circle_at_top_right,rgba(14,165,233,0.12),transparent_28%),linear-gradient(145deg,#ffffff,#f8fafc)]"}`}>
          <p className={`text-xs font-semibold uppercase tracking-[0.34em] ${isDark ? "text-sky-200" : "text-sky-700"}`}>Themes</p>
          <h1 className={`mt-3 font-serif text-5xl leading-tight ${isDark ? "text-white" : "text-slate-950"}`}>Search by meaning, not just by words.</h1>
          <p className={`mt-4 max-w-3xl text-sm leading-7 ${isDark ? "text-stone-300" : "text-slate-600"}`}>
            Use a motif, pressure, emotional pattern, or conflict. LoreVia searches summaries first and now falls back more gracefully when it needs to inspect raw chapter text.
          </p>

          <div className="mt-6 flex flex-col gap-3 sm:flex-row">
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && search()}
              className={`flex-1 rounded-2xl border px-5 py-4 text-sm ${isDark ? "border-white/10 bg-white/[0.05] text-stone-100 placeholder:text-stone-500" : "border-slate-200 bg-white text-slate-950 placeholder:text-slate-400"}`}
              placeholder='Try "family pressure", "betrayal", or "identity crisis"'
            />
            <button
              onClick={() => search()}
              className={`rounded-2xl px-6 py-4 text-sm font-semibold transition ${loading ? "bg-slate-500 text-white" : isDark ? "bg-white text-slate-950 hover:bg-stone-200" : "bg-slate-950 text-white hover:bg-slate-800"}`}
            >
              {loading ? "Searching..." : "Search themes"}
            </button>
          </div>

          <div className="mt-4 flex flex-wrap gap-2">
            {SUGGESTED_QUERIES.map((suggestion) => (
              <button
                key={suggestion}
                onClick={() => search(suggestion)}
                className={isDark ? "rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-stone-300 hover:bg-white/10 hover:text-white" : "rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-50 hover:text-slate-950"}
              >
                {suggestion}
              </button>
            ))}
          </div>
        </section>

        {error ? <div className={`mt-6 rounded-2xl border px-4 py-3 text-sm ${isDark ? "border-amber-300/30 bg-amber-300/10 text-amber-100" : "border-amber-200 bg-amber-50 text-amber-800"}`}>{error}</div> : null}

        {!error && !loading && !hasSearched ? (
          <div className={`mt-8 rounded-[1.6rem] border p-6 ${isDark ? "border-white/10 bg-white/[0.03] text-stone-300" : "border-slate-200 bg-white text-slate-700"}`}>
            <p className="text-lg font-semibold">Start with a pressure, motif, or emotional current.</p>
            <p className={`mt-2 text-sm leading-6 ${isDark ? "text-stone-400" : "text-slate-500"}`}>
              The best searches are abstract enough to capture multiple scenes: obsession, shame, family duty, hunger, resentment, or sacrifice.
            </p>
          </div>
        ) : null}

        {!error && !loading && hasSearched && results.length === 0 ? (
          <div className={`mt-8 rounded-[1.6rem] border p-6 ${isDark ? "border-white/10 bg-white/[0.03] text-stone-300" : "border-slate-200 bg-white text-slate-700"}`}>
            <p className="text-lg font-semibold">No thematic matches yet.</p>
            <p className={`mt-2 text-sm leading-6 ${isDark ? "text-stone-400" : "text-slate-500"}`}>
              Try a broader phrase. Instead of a specific event, search for a recurring pressure like guilt, distance, family strain, or transformation.
            </p>
          </div>
        ) : null}

        <div className="mt-8 grid gap-4">
          {results.map((result) => (
            <article key={`${result.chapter_number}-${result.score}-${result.chapter_title}`} className={`rounded-[1.6rem] border p-6 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-slate-200 bg-white shadow-[0_18px_60px_-52px_rgba(15,23,42,0.16)]"}`}>
              <div className="flex flex-wrap items-center gap-3">
                <span className={isDark ? "rounded-full bg-sky-300/10 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.22em] text-sky-100" : "rounded-full bg-sky-100 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.22em] text-sky-800"}>
                  Chapter {result.chapter_number}
                </span>
                {result.chapter_title ? <span className={isDark ? "text-xs text-stone-400" : "text-xs text-slate-500"}>{result.chapter_title}</span> : null}
                <span className={isDark ? "ml-auto text-xs text-stone-500" : "ml-auto text-xs text-slate-400"}>Relevance {result.score}</span>
              </div>
              <p className={`mt-4 text-sm leading-7 ${isDark ? "text-stone-200" : "text-slate-700"}`}>{result.summary}</p>
            </article>
          ))}
        </div>
      </div>
    </div>
  )
}
