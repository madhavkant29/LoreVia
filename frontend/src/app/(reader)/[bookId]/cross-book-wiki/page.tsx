"use client"

import { useEffect, useMemo, useState } from "react"
import Link from "next/link"
import { useParams } from "next/navigation"

import { intelligenceApi } from "@/lib/api/intelligence"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import type { CrossBookIntelligence, CrossBookMatch } from "@/types/intelligence"

type MatchMode = "all" | "characters" | "wiki"

export default function CrossBookWikiPage() {
  const { bookId } = useParams<{ bookId: string }>()
  const { theme } = usePreferencesStore()
  const isDark = theme === "dark"
  const [data, setData] = useState<CrossBookIntelligence | null>(null)
  const [loading, setLoading] = useState(true)
  const [mode, setMode] = useState<MatchMode>("all")
  const [threshold, setThreshold] = useState(60)
  const [query, setQuery] = useState("")

  useEffect(() => {
    intelligenceApi.getCrossBookIntelligence(bookId).then(setData).finally(() => setLoading(false))
  }, [bookId])

  const matches = useMemo(() => {
    const allMatches: Array<CrossBookMatch & { source: "characters" | "wiki" }> = [
      ...((data?.character_matches ?? []).map((item) => ({ ...item, source: "characters" as const }))),
      ...((data?.wiki_matches ?? []).map((item) => ({ ...item, source: "wiki" as const }))),
    ]
    const normalizedQuery = query.trim().toLowerCase()
    return allMatches
      .filter((item) => mode === "all" || item.source === mode)
      .filter((item) => Math.round(item.similarity * 100) >= threshold)
      .filter((item) => {
        if (!normalizedQuery) return true
        return [item.left_name, item.right_name, item.entry_type ?? ""].some((value) => value.toLowerCase().includes(normalizedQuery))
      })
      .sort((a, b) => b.similarity - a.similarity)
  }, [data, mode, query, threshold])

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
          <h1 className={`mt-3 font-serif text-5xl leading-tight ${isDark ? "text-white" : "text-slate-950"}`}>See where people, archetypes, and world logic start to rhyme.</h1>
          <p className={`mt-4 max-w-3xl text-sm leading-7 ${isDark ? "text-stone-300" : "text-slate-600"}`}>
            This workspace compares character and wiki embeddings across books in the same owned series, so you can inspect recurring roles, mirrored entries, and continuity bridges with more control than the overview card.
          </p>

          <div className="mt-6 grid gap-4 lg:grid-cols-[1.2fr_0.8fr]">
            <div className={`rounded-[1.4rem] border p-4 ${isDark ? "border-white/10 bg-black/20" : "border-slate-200 bg-white/85"}`}>
              <p className={`text-xs font-semibold uppercase tracking-[0.22em] ${isDark ? "text-stone-400" : "text-slate-500"}`}>Filter matches</p>
              <div className="mt-4 flex flex-wrap gap-2">
                {(["all", "characters", "wiki"] as MatchMode[]).map((value) => (
                  <button
                    key={value}
                    onClick={() => setMode(value)}
                    className={`rounded-full px-4 py-2 text-sm font-medium transition ${mode === value ? (isDark ? "bg-amber-300 text-slate-950" : "bg-slate-950 text-white") : (isDark ? "border border-white/10 bg-white/5 text-stone-300 hover:bg-white/10" : "border border-slate-200 bg-white text-slate-600 hover:bg-slate-50")}`}
                  >
                    {value === "all" ? "All matches" : value === "characters" ? "Character echoes" : "Wiki overlaps"}
                  </button>
                ))}
              </div>
              <div className="mt-5">
                <label className={`text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-stone-400" : "text-slate-500"}`}>Minimum similarity</label>
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
              </div>
            </div>

            <div className={`rounded-[1.4rem] border p-4 ${isDark ? "border-white/10 bg-black/20" : "border-slate-200 bg-white/85"}`}>
              <label className={`text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-stone-400" : "text-slate-500"}`}>Search names or entry type</label>
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Gregor, father figure, prophecy..."
                className={`mt-3 w-full rounded-2xl border px-4 py-3 text-sm outline-none transition ${isDark ? "border-white/10 bg-white/5 text-white placeholder:text-stone-500 focus:border-sky-300/40" : "border-slate-200 bg-white text-slate-950 placeholder:text-slate-400 focus:border-slate-400"}`}
              />
              <div className={`mt-5 grid grid-cols-2 gap-3 text-sm ${isDark ? "text-stone-300" : "text-slate-600"}`}>
                <div className={`rounded-2xl border p-3 ${isDark ? "border-white/10 bg-white/5" : "border-slate-200 bg-slate-50"}`}>
                  <p className="text-xs uppercase tracking-[0.2em] opacity-70">Series</p>
                  <p className="mt-2 font-semibold">{data?.series_name ?? "Unassigned"}</p>
                </div>
                <div className={`rounded-2xl border p-3 ${isDark ? "border-white/10 bg-white/5" : "border-slate-200 bg-slate-50"}`}>
                  <p className="text-xs uppercase tracking-[0.2em] opacity-70">Visible matches</p>
                  <p className="mt-2 font-semibold">{matches.length}</p>
                </div>
              </div>
            </div>
          </div>
        </section>

        {loading ? (
          <div className={`rounded-[1.8rem] border border-dashed py-20 text-center ${isDark ? "border-white/10 text-stone-400" : "border-slate-300 text-slate-500"}`}>Loading cross-book similarities...</div>
        ) : matches.length === 0 ? (
          <div className={`rounded-[1.8rem] border p-8 ${isDark ? "border-white/10 bg-white/[0.04]" : "border-slate-200 bg-white/85"}`}>
            <h2 className={`text-2xl font-semibold ${isDark ? "text-white" : "text-slate-950"}`}>No matches in the current filter window.</h2>
            <p className={`mt-3 max-w-2xl text-sm leading-7 ${isDark ? "text-stone-300" : "text-slate-600"}`}>
              Try lowering the similarity threshold, broadening the search, or adding more books from the same series so LoreVia has enough material to compare across volumes.
            </p>
          </div>
        ) : (
          <section className="grid gap-4 lg:grid-cols-2">
            {matches.map((match) => (
              <article key={`${match.source}:${match.left_book_id}:${match.left_name}:${match.right_book_id}:${match.right_name}`} className={`rounded-[1.6rem] border p-5 ${isDark ? "border-white/10 bg-white/[0.04]" : "border-slate-200 bg-white/85"}`}>
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <p className={`text-xs font-semibold uppercase tracking-[0.24em] ${match.source === "wiki" ? (isDark ? "text-sky-200" : "text-sky-700") : (isDark ? "text-amber-200" : "text-amber-700")}`}>
                      {match.source === "wiki" ? "Wiki overlap" : "Character echo"}
                    </p>
                    <h2 className={`mt-3 text-2xl font-semibold ${isDark ? "text-white" : "text-slate-950"}`}>
                      {match.left_name} {"<->"} {match.right_name}
                    </h2>
                  </div>
                  <div className={`rounded-full px-3 py-1 text-sm font-semibold ${isDark ? "bg-white/8 text-white" : "bg-slate-100 text-slate-900"}`}>
                    {Math.round(match.similarity * 100)}%
                  </div>
                </div>
                <div className={`mt-5 grid gap-3 sm:grid-cols-2 ${isDark ? "text-stone-300" : "text-slate-600"}`}>
                  <div className={`rounded-2xl border p-4 ${isDark ? "border-white/10 bg-black/20" : "border-slate-200 bg-slate-50"}`}>
                    <p className="text-xs uppercase tracking-[0.18em] opacity-70">Left side</p>
                    <p className="mt-2 font-medium">{match.left_name}</p>
                  </div>
                  <div className={`rounded-2xl border p-4 ${isDark ? "border-white/10 bg-black/20" : "border-slate-200 bg-slate-50"}`}>
                    <p className="text-xs uppercase tracking-[0.18em] opacity-70">Right side</p>
                    <p className="mt-2 font-medium">{match.right_name}</p>
                  </div>
                </div>
                {match.entry_type ? (
                  <p className={`mt-4 text-sm ${isDark ? "text-stone-400" : "text-slate-500"}`}>
                    Entry type: <span className={isDark ? "text-stone-200" : "text-slate-800"}>{match.entry_type}</span>
                  </p>
                ) : null}
              </article>
            ))}
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
