"use client"
import { useEffect, useState } from "react"
import { useParams, useRouter } from "next/navigation"
import { readerApi } from "@/lib/api/reader"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import type { RelationshipEvolutionPair } from "@/types/reader"

export default function RelationshipEvolutionPage() {
  const { bookId } = useParams<{ bookId: string }>()
  const router = useRouter()
  const [pairs, setPairs] = useState<RelationshipEvolutionPair[]>([])
  const [chapter, setChapter] = useState(1)
  const [error, setError] = useState<string | null>(null)
  const { theme } = usePreferencesStore()
  const isDark = theme === "dark"

  useEffect(() => {
    readerApi.getProgress(bookId).then((progress) => {
      const current = Math.max(1, progress?.current_chapter ?? 1)
      setChapter(current)
      return readerApi.getRelationshipEvolution(bookId, current)
    }).then((res) => setPairs(res.pairs)).catch((e) => {
      setError(e.response?.data?.detail ?? "Relationship evolution unavailable")
    })
  }, [bookId])

  return (
    <div className={`min-h-screen px-4 py-8 transition-colors ${isDark ? "bg-[linear-gradient(180deg,#07111f_0%,#0b1830_44%,#0d1b35_100%)] text-slate-100" : "bg-[linear-gradient(180deg,#fcf7ef_0%,#f8f3ec_46%,#f5f0ea_100%)] text-stone-950"}`}>
      <div className="mx-auto max-w-5xl">
        <button onClick={() => router.back()} className={`text-sm font-medium transition ${isDark ? "text-indigo-300 hover:text-indigo-200" : "text-violet-700 hover:text-violet-800"}`}>{"<- Back"}</button>
        <h1 className={`mt-4 font-serif text-5xl ${isDark ? "text-white" : "text-stone-950"}`}>Relationship Evolution</h1>
        <p className={`mt-3 text-sm leading-7 ${isDark ? "text-slate-300" : "text-stone-600"}`}>See how alliances and tensions shift over time, and which event changed the relationship.</p>
        <p className={`mt-4 text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>Showing relationship events through chapter {chapter}.</p>
        {error ? <div className={`mt-6 rounded-[1.5rem] border p-5 text-sm ${isDark ? "border-amber-400/30 bg-amber-500/10 text-amber-200" : "border-amber-300 bg-amber-50 text-amber-800"}`}>{error}</div> : null}
        <div className="mt-8 space-y-4">
          {pairs.map((pair) => (
            <div key={pair.characters.join("-")} className={`rounded-[1.6rem] border p-5 ${isDark ? "border-white/10 bg-white/[0.04]" : "border-stone-200/80 bg-white/90"}`}>
              <h2 className={`font-serif text-2xl ${isDark ? "text-white" : "text-stone-950"}`}>{pair.characters.join(" ↔ ")}</h2>
              <div className="mt-4 space-y-3">
                {pair.events.map((event, index) => (
                  <div key={index} className={`rounded-[1.2rem] border p-4 ${isDark ? "border-white/10 bg-white/5" : "border-stone-200 bg-stone-50"}`}>
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
