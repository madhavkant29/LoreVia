"use client"
import { useEffect, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import Link from "next/link"
import { useParams } from "next/navigation"
import { asQueryKey, readerCacheKey } from "@/lib/query/cacheKeys"
import { readerApi } from "@/lib/api/reader"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import type { RelationshipEvolutionPair } from "@/types/reader"

export default function RelationshipEvolutionPage() {
  const { bookId } = useParams<{ bookId: string }>()
  const [chapter, setChapter] = useState(1)
  const { theme } = usePreferencesStore()
  const isDark = theme === "dark"
  const { data: progress = null } = useQuery({
    queryKey: asQueryKey(readerCacheKey(bookId, "progress")),
    queryFn: () => readerApi.getProgress(bookId),
  })
  const { data: evolution = null } = useQuery({
    queryKey: asQueryKey(`reader:${bookId}:relationship-evolution:${chapter}`),
    queryFn: () => readerApi.getRelationshipEvolution(bookId, chapter),
    enabled: chapter > 0,
  })

  useEffect(() => {
    setChapter(Math.max(1, progress?.current_chapter ?? 1))
  }, [progress])

  const pairs: RelationshipEvolutionPair[] = evolution?.pairs ?? []
  const error = !evolution ? "Relationship evolution unavailable" : null

  return (
    <div className={`min-h-screen px-4 py-8 transition-colors ${isDark ? "bg-[#071211] text-slate-100" : "bg-stone-50 text-stone-950"}`}>
      <div className="mx-auto max-w-5xl">
        <Link href={`/${bookId}`} className={`text-sm font-medium transition ${isDark ? "text-indigo-300 hover:text-indigo-200" : "text-violet-700 hover:text-violet-800"}`}>Home</Link>
        <h1 className={`mt-4 font-serif text-5xl ${isDark ? "text-white" : "text-stone-950"}`}>Relationship Evolution</h1>
        <p className={`mt-3 text-sm leading-7 ${isDark ? "text-slate-300" : "text-stone-600"}`}>See how alliances and tensions shift over time, and which event changed the relationship.</p>
        <p className={`mt-4 text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>Showing relationship events through chapter {chapter}.</p>
        {error ? <div className={`mt-6 rounded-lg border p-5 text-sm ${isDark ? "border-amber-400/30 bg-amber-500/10 text-amber-200" : "border-amber-300 bg-amber-50 text-amber-800"}`}>{error}</div> : null}
        <div className="mt-8 space-y-4">
          {pairs.map((pair) => (
            <div key={pair.characters.join("-")} className={`rounded-lg border p-5 ${isDark ? "border-white/10 bg-white/[0.04]" : "border-stone-200/80 bg-white/90"}`}>
              <h2 className={`font-serif text-2xl ${isDark ? "text-white" : "text-stone-950"}`}>{pair.characters.join(" ↔ ")}</h2>
              <div className="mt-4 space-y-3">
                {pair.events.map((event, index) => (
                  <div key={index} className={`rounded-md border p-4 ${isDark ? "border-white/10 bg-white/5" : "border-stone-200 bg-stone-50"}`}>
                    <p className={`text-xs font-semibold uppercase tracking-[0.22em] ${isDark ? "text-indigo-300" : "text-violet-600"}`}>Chapter {event.chapter} · {event.type}</p>
                    {event.description ? <p className={`mt-2 text-sm leading-7 ${isDark ? "text-slate-300" : "text-stone-700"}`}>{event.description}</p> : null}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
