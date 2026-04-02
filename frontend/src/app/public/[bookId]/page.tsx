"use client"

import Link from "next/link"
import { useEffect, useState } from "react"
import { useParams } from "next/navigation"

import { booksApi } from "@/lib/api/books"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import type { PublicBookDetail } from "@/types/book"

export default function PublicBookPage() {
  const { bookId } = useParams<{ bookId: string }>()
  const [book, setBook] = useState<PublicBookDetail | null>(null)
  const { theme } = usePreferencesStore()
  const isDark = theme === "dark"

  useEffect(() => {
    booksApi.getPublic(bookId).then(setBook)
  }, [bookId])

  if (!book) {
    return <div className={`mx-auto max-w-5xl px-4 py-20 text-center ${isDark ? "text-slate-500" : "text-slate-400"}`}>Loading public book...</div>
  }

  return (
    <div className="mx-auto max-w-5xl px-4 py-10">
      <div className="space-y-8">
        <section className={`rounded-[2rem] border p-6 ${isDark ? "border-white/10 bg-slate-950" : "border-slate-200 bg-white"}`}>
          <Link href="/public" className={`text-sm ${isDark ? "text-slate-400 hover:text-white" : "text-slate-500 hover:text-slate-900"}`}>
            {"<- Back to public library"}
          </Link>
          <h1 className={`mt-4 font-serif text-4xl ${isDark ? "text-white" : "text-slate-950"}`}>{book.title}</h1>
          {book.author ? <p className={`mt-2 text-lg ${isDark ? "text-slate-300" : "text-slate-600"}`}>by {book.author}</p> : null}
          {book.description ? <p className={`mt-4 max-w-3xl text-sm leading-7 ${isDark ? "text-slate-300" : "text-slate-600"}`}>{book.description}</p> : null}
        </section>

        <section className="space-y-4">
          <h2 className={`text-2xl font-semibold ${isDark ? "text-white" : "text-slate-950"}`}>Chapters</h2>
          <div className="grid gap-4">
            {book.chapters.map((chapter) => (
              <Link
                key={chapter.number}
                href={`/public/${book.id}/chapter/${chapter.number}`}
                className={`rounded-[1.25rem] border p-4 transition ${isDark ? "border-white/10 bg-slate-950 hover:bg-white/5" : "border-slate-200 bg-white hover:bg-slate-50"}`}
              >
                <p className={`text-sm font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-400" : "text-slate-500"}`}>
                  Chapter {chapter.number}
                </p>
                <p className={`mt-2 text-lg font-semibold ${isDark ? "text-white" : "text-slate-950"}`}>{chapter.title || `Chapter ${chapter.number}`}</p>
                {chapter.description ? <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-300" : "text-slate-600"}`}>{chapter.description}</p> : null}
              </Link>
            ))}
          </div>
        </section>
      </div>
    </div>
  )
}
