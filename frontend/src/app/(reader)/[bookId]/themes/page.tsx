"use client"
import { useState } from "react"
import { useParams, useRouter } from "next/navigation"
import { readerApi } from "@/lib/api/reader"
import type { ThematicSearchResult } from "@/types/reader"

export default function ThemesPage() {
  const { bookId } = useParams<{ bookId: string }>()
  const router = useRouter()
  const [query, setQuery] = useState("")
  const [results, setResults] = useState<ThematicSearchResult[]>([])
  const [error, setError] = useState<string | null>(null)

  const search = async () => {
    if (!query.trim()) return
    setError(null)
    try {
      const response = await readerApi.thematicSearch(bookId, query)
      setResults(response.results)
    } catch (e: any) {
      setError(e.response?.data?.detail ?? "Thematic search unavailable")
    }
  }

  return (
    <div className="min-h-screen bg-white px-4 py-8 text-black">
      <div className="mx-auto max-w-4xl">
        <button onClick={() => router.back()} className="text-sm text-gray-400 hover:text-gray-600">{"<- Back"}</button>
        <h1 className="mt-4 text-3xl font-semibold">Thematic Search</h1>
        <p className="mt-2 text-sm text-gray-500">Search motifs and scene types like betrayal, political intrigue, loyalty, or romance within read chapters only.</p>
        <div className="mt-6 flex gap-2">
          <input value={query} onChange={(e) => setQuery(e.target.value)} onKeyDown={(e) => e.key === "Enter" && search()} className="flex-1 rounded-xl border border-gray-300 px-4 py-3 text-sm" placeholder='e.g. "betrayal scenes"' />
          <button onClick={search} className="rounded-xl bg-black px-5 py-3 text-sm font-medium text-white">Search</button>
        </div>
        {error ? <div className="mt-6 rounded-xl border border-amber-300 bg-amber-50 p-4 text-sm text-amber-800">{error}</div> : null}
        <div className="mt-8 space-y-4">
          {results.map((result) => (
            <div key={`${result.chapter_number}-${result.score}`} className="rounded-2xl border border-gray-200 bg-white p-5">
              <p className="text-xs uppercase tracking-wide text-indigo-500">Chapter {result.chapter_number} · Score {result.score}</p>
              <p className="mt-2 text-sm leading-relaxed text-gray-700">{result.summary}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
