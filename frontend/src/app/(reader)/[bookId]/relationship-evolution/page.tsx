"use client"
import { useEffect, useState } from "react"
import { useParams, useRouter } from "next/navigation"
import { readerApi } from "@/lib/api/reader"
import type { RelationshipEvolutionPair } from "@/types/reader"

export default function RelationshipEvolutionPage() {
  const { bookId } = useParams<{ bookId: string }>()
  const router = useRouter()
  const [pairs, setPairs] = useState<RelationshipEvolutionPair[]>([])
  const [chapter, setChapter] = useState(1)
  const [error, setError] = useState<string | null>(null)

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
    <div className="min-h-screen bg-white px-4 py-8 text-black">
      <div className="mx-auto max-w-4xl">
        <button onClick={() => router.back()} className="text-sm text-gray-400 hover:text-gray-600">{"<- Back"}</button>
        <h1 className="mt-4 text-3xl font-semibold">Relationship Evolution</h1>
        <p className="mt-2 text-sm text-gray-500">See how alliances and tensions shift over time, and which event changed the relationship.</p>
        <p className="mt-4 text-sm text-gray-500">Showing relationship events through chapter {chapter}.</p>
        {error ? <div className="mt-6 rounded-xl border border-amber-300 bg-amber-50 p-4 text-sm text-amber-800">{error}</div> : null}
        <div className="mt-8 space-y-4">
          {pairs.map((pair) => (
            <div key={pair.characters.join("-")} className="rounded-2xl border border-gray-200 bg-white p-5">
              <h2 className="text-lg font-semibold text-gray-900">{pair.characters.join(" ↔ ")}</h2>
              <div className="mt-4 space-y-3">
                {pair.events.map((event, index) => (
                  <div key={index} className="rounded-xl bg-gray-50 p-3">
                    <p className="text-xs uppercase tracking-wide text-indigo-500">Chapter {event.chapter} · {event.type}</p>
                    {event.description ? <p className="mt-2 text-sm leading-relaxed text-gray-700">{event.description}</p> : null}
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
