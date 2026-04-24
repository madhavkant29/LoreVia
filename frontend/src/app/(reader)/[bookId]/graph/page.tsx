"use client"
import { useEffect, useState } from "react"
import { useParams, useRouter } from "next/navigation"

import { RelationshipGraph } from "@/components/intelligence/RelationshipGraph"
import { booksApi } from "@/lib/api/books"
import { readerApi } from "@/lib/api/reader"
import { capture } from "@/lib/analytics/posthog"

export default function GraphPage() {
  const { bookId } = useParams<{ bookId: string }>()
  const router = useRouter()
  const [chapter, setChapter] = useState(1)
  const [maxChapter, setMaxChapter] = useState(1)
  const [confirmed, setConfirmed] = useState(false)
  const [authorMode, setAuthorMode] = useState(false)
  const [theme, setTheme] = useState<"light" | "dark">("light")

  useEffect(() => {
    const stored = window.localStorage.getItem("reader-theme")
    if (stored === "dark" || stored === "light") setTheme(stored)
    booksApi.get(bookId).then((book) => setAuthorMode(book.mode === "author")).catch(() => {})
    readerApi.getProgress(bookId).then((progress) => {
      const readChapter = Math.max(1, progress?.current_chapter ?? 1)
      setChapter(readChapter)
      setMaxChapter(readChapter)
    }).catch(() => {})
  }, [bookId])

  useEffect(() => {
    if (confirmed) {
      capture("graph_opened", { book_id: bookId })
    }
  }, [bookId, confirmed])

  if (!confirmed) {
    return (
      <div className={`min-h-screen p-4 transition-colors ${theme === "dark" ? "bg-black text-white" : "bg-gray-50 text-black"}`}>
        <div className="max-w-xl mx-auto pt-16">
          <button onClick={() => router.back()} className={theme === "dark" ? "text-sm text-gray-400 hover:text-white mb-6" : "text-sm text-gray-400 hover:text-gray-600 mb-6"}>{"<- Back"}</button>
          <div className={theme === "dark" ? "rounded-2xl border border-amber-400/30 bg-amber-400/10 p-6" : "rounded-2xl border border-amber-300 bg-amber-50 p-6"}>
            <h1 className="text-xl font-semibold">Spoiler warning</h1>
            <p className={theme === "dark" ? "text-sm text-gray-300 mt-3 leading-relaxed" : "text-sm text-gray-700 mt-3 leading-relaxed"}>
              The relationship graph can reveal future connections. It will be limited to your read progress, currently up to chapter {maxChapter}, but it may still feel spoiler-heavy.
            </p>
            <div className="flex gap-3 mt-6">
              <button onClick={() => setConfirmed(true)} className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700">
                Continue
              </button>
              <button onClick={() => router.back()} className={theme === "dark" ? "px-4 py-2 rounded-lg text-sm border border-white/15 hover:bg-white/5" : "px-4 py-2 rounded-lg text-sm border border-gray-300 hover:bg-gray-100"}>
                Cancel
              </button>
            </div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className={`min-h-screen p-4 transition-colors ${theme === "dark" ? "bg-black text-white" : "bg-gray-50 text-black"}`}>
      <div className="flex items-center gap-3 mb-4">
        <button onClick={() => router.back()} className={theme === "dark" ? "text-sm text-gray-400 hover:text-white" : "text-sm text-gray-400 hover:text-gray-600"}>{"<- Back"}</button>
        <h1 className="text-xl font-semibold">Relationship Graph</h1>
        <div className={theme === "dark" ? "ml-auto flex items-center gap-2 text-sm text-gray-300" : "ml-auto flex items-center gap-2 text-sm text-gray-500"}>
          <span>Up to read chapter</span>
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
