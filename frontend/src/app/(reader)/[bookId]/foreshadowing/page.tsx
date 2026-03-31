"use client"
import { useEffect, useState } from "react"
import { useParams, useRouter } from "next/navigation"
import { readerApi } from "@/lib/api/reader"
import type { ForeshadowingItem } from "@/types/reader"

export default function ForeshadowingPage() {
  const { bookId } = useParams<{ bookId: string }>()
  const router = useRouter()
  const [items, setItems] = useState<ForeshadowingItem[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    readerApi.getForeshadowing(bookId).then((res) => setItems(res.items)).catch((e) => {
      setError(e.response?.data?.detail ?? "Foreshadowing unavailable")
    })
  }, [bookId])

  return (
    <div className="min-h-screen bg-white px-4 py-8 text-black">
      <div className="mx-auto max-w-4xl">
        <button onClick={() => router.back()} className="text-sm text-gray-400 hover:text-gray-600">{"<- Back"}</button>
        <h1 className="mt-4 text-3xl font-semibold">Foreshadowing Highlights</h1>
        <p className="mt-2 text-sm text-gray-500">Hints from read chapters that echo later in the story without reaching into unread material.</p>
        {error ? <div className="mt-6 rounded-xl border border-amber-300 bg-amber-50 p-4 text-sm text-amber-800">{error}</div> : null}
        <div className="mt-8 flex flex-col gap-4">
          {items.map((item, index) => (
            <article key={`${item.chapter_number}-${index}`} className="rounded-2xl border border-gray-200 bg-white p-5">
              <p className="text-xs uppercase tracking-wide text-indigo-500">Chapter {item.chapter_number}</p>
              <p className="mt-2 text-base font-medium text-gray-900">{item.clue}</p>
              {item.foreshadows ? <p className="mt-2 text-sm leading-relaxed text-gray-600">{item.foreshadows}</p> : null}
            </article>
          ))}
        </div>
      </div>
    </div>
  )
}
