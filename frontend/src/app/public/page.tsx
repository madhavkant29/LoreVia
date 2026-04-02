"use client"

import Link from "next/link"
import { useEffect, useState } from "react"

import { booksApi } from "@/lib/api/books"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import type { PublicBook } from "@/types/book"

export default function PublicLibraryPage() {
  const [books, setBooks] = useState<PublicBook[]>([])
  const [loading, setLoading] = useState(true)
  const { theme } = usePreferencesStore()
  const isDark = theme === "dark"

  useEffect(() => {
    booksApi.listPublic().then(setBooks).finally(() => setLoading(false))
  }, [])

  return (
    <div className="mx-auto max-w-6xl px-4 py-10">
      <div className="space-y-8">
        <section className={`rounded-[2rem] border p-6 ${isDark ? "border-white/10 bg-slate-950" : "border-slate-200 bg-white"}`}>
          <p className={`text-xs font-semibold uppercase tracking-[0.28em] ${isDark ? "text-slate-400" : "text-slate-500"}`}>Public library</p>
          <h1 className={`mt-3 font-serif text-4xl ${isDark ? "text-white" : "text-slate-950"}`}>Reader-ready public uploads</h1>
          <p className={`mt-3 max-w-3xl text-sm leading-6 ${isDark ? "text-slate-300" : "text-slate-600"}`}>
            Browse chapters that authors or readers have intentionally published for shared reading. These chapter responses are cached globally so public reading stays fast for everyone.
          </p>
        </section>

        {loading ? (
          <div className={`rounded-3xl border border-dashed py-16 text-center ${isDark ? "border-white/15 text-slate-500" : "border-slate-300 text-slate-400"}`}>Loading public books...</div>
        ) : books.length === 0 ? (
          <div className={`rounded-3xl border border-dashed py-16 text-center ${isDark ? "border-white/15 text-slate-500" : "border-slate-300 text-slate-400"}`}>No public books yet.</div>
        ) : (
          <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
            {books.map((book) => (
              <article key={book.id} className={`rounded-[1.5rem] border p-5 ${isDark ? "border-white/10 bg-slate-950" : "border-slate-200 bg-white"}`}>
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h2 className={`text-xl font-semibold ${isDark ? "text-white" : "text-slate-950"}`}>{book.title}</h2>
                    {book.author ? <p className={`mt-1 text-sm ${isDark ? "text-slate-400" : "text-slate-500"}`}>{book.author}</p> : null}
                  </div>
                  <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${isDark ? "bg-white/10 text-slate-200" : "bg-slate-100 text-slate-600"}`}>
                    {book.format.toUpperCase()}
                  </span>
                </div>
                {book.description ? (
                  <p className={`mt-4 text-sm leading-6 ${isDark ? "text-slate-300" : "text-slate-600"}`}>{book.description}</p>
                ) : null}
                <div className={`mt-4 flex flex-wrap gap-2 text-xs ${isDark ? "text-slate-400" : "text-slate-500"}`}>
                  {book.genre ? <span className={isDark ? "rounded-full bg-white/10 px-3 py-1" : "rounded-full bg-slate-100 px-3 py-1"}>{book.genre}</span> : null}
                  {book.total_chapters ? <span className={isDark ? "rounded-full bg-white/10 px-3 py-1" : "rounded-full bg-slate-100 px-3 py-1"}>{book.total_chapters} chapters</span> : null}
                </div>
                <div className="mt-5">
                  <Link
                    href={`/public/${book.id}`}
                    className={`inline-flex rounded-full px-4 py-2 text-sm font-medium transition ${isDark ? "bg-white text-slate-950 hover:bg-slate-200" : "bg-slate-950 text-white hover:bg-slate-800"}`}
                  >
                    Open public book
                  </Link>
                </div>
              </article>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
