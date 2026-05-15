"use client"
import { useEffect, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { useParams, useRouter } from "next/navigation"

import RelationshipGraph from "@/components/intelligence/RelationshipGraph"
import { booksApi } from "@/lib/api/books"
import { asQueryKey, bookCacheKey, readerCacheKey } from "@/lib/query/cacheKeys"
import { readerApi } from "@/lib/api/reader"
import { capture } from "@/lib/analytics/posthog"

export default function GraphPage() {
  const { bookId } = useParams<{ bookId: string }>()
  const router = useRouter()
  const [chapter, setChapter] = useState(1)
  const [maxChapter, setMaxChapter] = useState(1)
  const [theme, setTheme] = useState<"light" | "dark">("light")
  const { data: book = null } = useQuery({
    queryKey: asQueryKey(bookCacheKey(bookId, "detail")),
    queryFn: () => booksApi.get(bookId),
  })
  const { data: progress = null } = useQuery({
    queryKey: asQueryKey(readerCacheKey(bookId, "progress")),
    queryFn: () => readerApi.getProgress(bookId),
  })
  const authorMode = book?.mode === "author"

  useEffect(() => {
    const stored = window.localStorage.getItem("reader-theme")
    if (stored === "dark" || stored === "light") setTheme(stored)
  }, [])

  useEffect(() => {
    const readChapter = Math.max(1, progress?.current_chapter ?? 1)
    setChapter(readChapter)
    setMaxChapter(readChapter)
  }, [progress])

  useEffect(() => {
    capture("graph_opened", { book_id: bookId })
  }, [bookId])

  return (
    <div className={`min-h-screen p-4 transition-colors ${theme === "dark" ? "bg-black text-white" : "bg-gray-50 text-black"}`}>
      <div className="flex items-center gap-3 mb-4">
        <button onClick={() => router.back()} className={theme === "dark" ? "text-sm text-gray-400 hover:text-white" : "text-sm text-gray-400 hover:text-gray-600"}>{"<- Back"}</button>
        <h1 className="text-xl font-semibold">Relationship Graph</h1>
        <div className={theme === "dark" ? "ml-auto flex items-center gap-2 text-sm text-gray-300" : "ml-auto flex items-center gap-2 text-sm text-gray-500"}>
          <span>{authorMode ? "Up to manuscript chapter" : "Up to read chapter"}</span>
          <input
            type="number"
            value={chapter}
            min={1}
            max={maxChapter}
            onChange={e => {
              const value = Number(e.target.value)
              setChapter(Math.min(maxChapter, Math.max(1, value)))
            }}
            className={theme === "dark" ? "w-16 border border-white/20 bg-black text-white rounded px-2 py-1 text-sm" : "w-16 border border-gray-300 rounded px-2 py-1 text-sm"}
          />
        </div>
      </div>
      <RelationshipGraph bookId={bookId} upToChapter={chapter} theme={theme} authorMode={authorMode} />
    </div>
  )
}
