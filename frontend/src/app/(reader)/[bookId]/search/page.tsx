"use client"
import { useParams, useRouter } from "next/navigation"
import { useEffect, useState } from "react"
import { readerApi } from "@/lib/api/reader"
import type { SearchResult } from "@/types/reader"

export default function SearchPage() {
  const { bookId } = useParams<{ bookId: string }>()
  const [query, setQuery] = useState("")
  const [results, setResults] = useState<SearchResult[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [theme, setTheme] = useState<"light" | "dark">("light")
  const router = useRouter()

  useEffect(() => {
    const stored = window.localStorage.getItem("reader-theme")
    if (stored === "dark" || stored === "light") setTheme(stored)
  }, [])

  const search = async () => {
    if (!query.trim()) return
    setLoading(true)
    setError(null)
    try {
      const data = await readerApi.search(bookId, query, 9999)
      setResults(data)
    } catch {
      setResults([])
      setError("Search failed. Please try again.")
    } finally { setLoading(false) }
  }

  return (
    <div className={`min-h-screen px-4 py-8 transition-colors ${theme === "dark" ? "bg-black text-white" : "bg-white text-black"}`}>
      <div className="max-w-2xl mx-auto">
        <div className="flex items-center gap-3 mb-6">
          <button onClick={() => router.back()} className={theme === "dark" ? "text-sm text-gray-400 hover:text-white" : "text-sm text-gray-400 hover:text-gray-600"}>{"<- Back"}</button>
          <h1 className="text-2xl font-semibold">Search Book</h1>
        </div>
        <div className="flex gap-2 mb-6">
          <input
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={e => e.key === "Enter" && search()}
            placeholder='e.g. "when did X betray Y"'
            className={theme === "dark"
              ? "flex-1 border border-white/20 bg-black text-white rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-white"
              : "flex-1 border border-gray-300 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"}
          />
          <button onClick={search} disabled={loading}
            className="px-4 py-2.5 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 disabled:opacity-50">
            {loading ? "..." : "Search"}
          </button>
        </div>
        <div className="flex flex-col gap-3">
          {error && (
            <p className={theme === "dark" ? "text-sm text-red-300" : "text-sm text-red-600"}>{error}</p>
          )}
          {results.map((r, i) => (
            <div key={i} className={theme === "dark" ? "bg-white/5 rounded-xl border border-white/10 p-4" : "bg-white rounded-xl border border-gray-200 p-4"}>
              <p className="text-xs text-indigo-500 mb-1">Chapter {r.chapter_num}{r.chapter_title ? ` - ${r.chapter_title}` : ""}</p>
              <p className={theme === "dark" ? "text-sm font-medium text-white leading-relaxed" : "text-sm font-medium text-gray-900 leading-relaxed"}>
                {r.summary}
              </p>
              <p className={theme === "dark" ? "text-sm text-gray-100 leading-relaxed" : "text-sm text-gray-700 leading-relaxed"}>{r.text}</p>
              <p className={theme === "dark" ? "text-xs text-gray-400 mt-2" : "text-xs text-gray-400 mt-2"}>Relevance: {Math.round(r.relevance * 100)}%</p>
            </div>
          ))}
          {results.length === 0 && !loading && query && (
            <p className={theme === "dark" ? "text-center py-8 text-gray-500 text-sm" : "text-center py-8 text-gray-400 text-sm"}>No results found</p>
          )}
        </div>
      </div>
    </div>
  )
}
