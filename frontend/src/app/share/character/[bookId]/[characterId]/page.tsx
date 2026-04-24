"use client"

import { useEffect, useState } from "react"
import { useParams, useSearchParams } from "next/navigation"
import { API_BASE } from "@/lib/constants"

interface SharedCharacterCard {
  book_title: string
  name: string
  aliases: string[]
  role: string | null
  status: string
  description: string
  first_appearance: number
  last_appearance: number | null
  mentions_count: number
  personality_tags: string[]
  motivations: string[]
  fears: string[]
  arc_summary: string | null
  growth_events: Array<{ chapter?: number | null; event: string; impact?: string | null }>
  relationships: Array<{ name: string; type: string; description?: string | null; from_chapter?: number | null; to_chapter?: number | null }>
}

export default function SharedCharacterPage() {
  const { bookId, characterId } = useParams<{ bookId: string; characterId: string }>()
  const searchParams = useSearchParams()
  const token = searchParams.get("token")
  const [card, setCard] = useState<SharedCharacterCard | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!token) {
      setError("Missing share token.")
      return
    }
    fetch(`${API_BASE}/books/${bookId}/characters/${characterId}/card?token=${encodeURIComponent(token)}`)
      .then(async (response) => {
        if (!response.ok) throw new Error("Unable to load shared character card.")
        return response.json()
      })
      .then(setCard)
      .catch(() => setError("This shared card is unavailable or has expired."))
  }, [bookId, characterId, token])

  return (
    <div className="min-h-screen bg-[linear-gradient(180deg,#f7f3ed_0%,#efe7dc_100%)] px-4 py-10 text-stone-900">
      <div className="mx-auto max-w-4xl rounded-[1.75rem] border border-stone-200 bg-white/90 p-6 shadow-[0_30px_90px_-70px_rgba(15,23,42,0.5)] sm:p-8">
        {error ? (
          <div className="rounded-2xl border border-red-200 bg-red-50 p-5 text-sm text-red-700">{error}</div>
        ) : !card ? (
          <div className="rounded-2xl border border-stone-200 bg-stone-50 p-5 text-sm text-stone-600">Loading shared card...</div>
        ) : (
          <div className="space-y-8">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.3em] text-stone-500">LoreVia Character Card</p>
              <h1 className="mt-3 font-serif text-5xl leading-none">{card.name}</h1>
              <p className="mt-3 text-sm text-stone-500">{card.book_title}</p>
            </div>

            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {[
                ["Status", card.status],
                ["Role", card.role || "-"],
                ["First appearance", card.first_appearance ? `Chapter ${card.first_appearance}` : "-"],
                ["Last appearance", card.last_appearance ? `Chapter ${card.last_appearance}` : "-"],
                ["Mentions", String(card.mentions_count)],
                ["Aliases", card.aliases.join(", ") || "-"],
              ].map(([label, value]) => (
                <div key={label} className="rounded-[1rem] border border-stone-200 bg-stone-50/80 p-4">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-stone-400">{label}</p>
                  <p className="mt-2 text-sm leading-6 text-stone-700">{value}</p>
                </div>
              ))}
            </div>

            <section>
              <h2 className="text-sm font-semibold uppercase tracking-[0.2em] text-stone-500">Overview</h2>
              <p className="mt-3 text-base leading-8 text-stone-700">{card.description}</p>
            </section>

            {card.arc_summary ? (
              <section>
                <h2 className="text-sm font-semibold uppercase tracking-[0.2em] text-stone-500">Arc summary</h2>
                <p className="mt-3 text-base leading-8 text-stone-700">{card.arc_summary}</p>
              </section>
            ) : null}

            {card.growth_events?.length ? (
              <section>
                <h2 className="text-sm font-semibold uppercase tracking-[0.2em] text-stone-500">Key growth events</h2>
                <div className="mt-3 space-y-3">
                  {card.growth_events.map((event, index) => (
                    <div key={`${event.event}-${index}`} className="rounded-[1rem] border border-stone-200 bg-stone-50/80 p-4">
                      <p className="font-medium text-stone-900">{event.chapter ? `Chapter ${event.chapter}: ` : ""}{event.event}</p>
                      {event.impact ? <p className="mt-1 text-sm leading-6 text-stone-600">{event.impact}</p> : null}
                    </div>
                  ))}
                </div>
              </section>
            ) : null}

            {card.relationships?.length ? (
              <section>
                <h2 className="text-sm font-semibold uppercase tracking-[0.2em] text-stone-500">Relationships</h2>
                <div className="mt-3 overflow-hidden rounded-[1rem] border border-stone-200">
                  <table className="w-full border-collapse text-left text-sm">
                    <thead className="bg-stone-100 text-stone-600">
                      <tr>
                        <th className="px-4 py-3 font-semibold">Character</th>
                        <th className="px-4 py-3 font-semibold">Type</th>
                        <th className="px-4 py-3 font-semibold">Range</th>
                        <th className="px-4 py-3 font-semibold">Note</th>
                      </tr>
                    </thead>
                    <tbody>
                      {card.relationships.map((relationship, index) => (
                        <tr key={`${relationship.name}-${index}`} className="border-t border-stone-200 bg-white">
                          <td className="px-4 py-3 text-stone-900">{relationship.name}</td>
                          <td className="px-4 py-3 text-stone-700">{relationship.type}</td>
                          <td className="px-4 py-3 text-stone-700">
                            {relationship.from_chapter ? `Chapter ${relationship.from_chapter}` : "-"}
                            {relationship.to_chapter ? ` to Chapter ${relationship.to_chapter}` : " onward"}
                          </td>
                          <td className="px-4 py-3 text-stone-600">{relationship.description || "-"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
            ) : null}
          </div>
        )}
      </div>
    </div>
  )
}
