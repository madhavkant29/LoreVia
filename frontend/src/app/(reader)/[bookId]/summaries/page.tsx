"use client"
import { useEffect, useState } from "react"
import { useParams, useRouter } from "next/navigation"

import { booksApi } from "@/lib/api/books"
import { readerApi } from "@/lib/api/reader"
import type { Book } from "@/types/book"
import type { SummaryCollectionResponse } from "@/types/reader"

export default function SummariesPage() {
  const { bookId } = useParams<{ bookId: string }>()
  const router = useRouter()
  const [book, setBook] = useState<Book | null>(null)
  const [data, setData] = useState<SummaryCollectionResponse | null>(null)
  const [theme, setTheme] = useState<"light" | "dark">("light")

  useEffect(() => {
    booksApi.get(bookId).then(setBook).catch(() => {})
    readerApi.getSummaryCollection(bookId).then(setData)
    const stored = window.localStorage.getItem("reader-theme")
    if (stored === "dark" || stored === "light") setTheme(stored)
  }, [bookId])

  return (
    <div className={`min-h-screen px-4 py-8 transition-colors ${theme === "dark" ? "bg-black text-white" : "bg-white text-black"}`}>
      <div className="max-w-4xl mx-auto">
        <div className="flex items-center gap-3 mb-6">
          <button onClick={() => router.back()} className={theme === "dark" ? "text-sm text-gray-400 hover:text-white" : "text-sm text-gray-400 hover:text-gray-600"}>{"<- Back"}</button>
          <div>
            <h1 className="text-2xl font-semibold">Read Chapter Summaries</h1>
            <p className={theme === "dark" ? "text-sm text-gray-400 mt-1" : "text-sm text-gray-500 mt-1"}>
              {book?.mode === "author"
                ? `Showing summaries for all processed chapters through chapter ${data?.read_upto ?? 0}.`
                : `Showing summaries only through chapter ${data?.read_upto ?? 0}.`}
            </p>
          </div>
        </div>

        <div className="flex flex-col gap-4">
          {(data?.summaries ?? []).map((summary) => (
            <article
              key={summary.chapter_number}
              className={theme === "dark" ? "rounded-xl border border-white/10 bg-white/5 p-4" : "rounded-xl border border-gray-200 bg-white p-4"}
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h2 className="text-lg font-semibold">Chapter {summary.chapter_number}</h2>
                  <p className={theme === "dark" ? "text-sm text-gray-400 mt-1" : "text-sm text-gray-500 mt-1"}>
                    {summary.chapter_title || "Untitled chapter"}
                  </p>
                </div>
                <span className={`text-xs px-2 py-1 rounded-full shrink-0 ${
                  summary.available ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700"
                }`}>
                  {summary.available ? "Cached" : "Pending"}
                </span>
              </div>
              <p className={theme === "dark" ? "text-sm text-gray-200 leading-relaxed mt-4" : "text-sm text-gray-700 leading-relaxed mt-4"}>
                {summary.content || (book?.mode === "author"
                  ? "Summary not available yet for this processed chapter."
                  : "Summary not available yet for this read chapter.")}
              </p>
            </article>
          ))}
        </div>
      </div>
    </div>
  )
}
