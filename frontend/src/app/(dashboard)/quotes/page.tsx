"use client"
import { useEffect, useState } from "react"
import Link from "next/link"
import { booksApi } from "@/lib/api/books"
import type { SavedQuote } from "@/types/book"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"

export default function QuotesPage() {
  const [quotes, setQuotes] = useState<SavedQuote[]>([])
  const { theme } = usePreferencesStore()
  const isDark = theme === "dark"

  useEffect(() => {
    booksApi.listQuotes().then(setQuotes).catch(() => {})
  }, [])

  return (
    <div className="space-y-6">
      <section className={`rounded-[2rem] border p-6 ${isDark ? "border-white/10 bg-white/5" : "border-white/70 bg-white/85"}`}>
        <h1 className={`text-3xl font-serif ${isDark ? "text-white" : "text-stone-900"}`}>Saved Quotes</h1>
        <p className={`mt-3 max-w-2xl text-sm leading-6 ${isDark ? "text-gray-300" : "text-stone-600"}`}>
          Keep the lines that matter. Every saved passage carries its book, chapter, and optional character context so you can return to it with full orientation.
        </p>
      </section>
      <div className="space-y-4">
        {quotes.map((quote) => (
          <article key={quote.id} className={`rounded-[1.75rem] border p-5 shadow-[0_20px_70px_-52px_rgba(15,23,42,0.35)] ${isDark ? "border-white/10 bg-white/5" : "border-stone-200 bg-white"}`}>
            <div className="flex flex-wrap items-center gap-2 text-xs uppercase tracking-wide text-indigo-500">
              <Link href={`/${quote.book_id}`} className="hover:underline">{quote.book_title}</Link>
              {quote.chapter_number ? <span>Chapter {quote.chapter_number}</span> : null}
              {quote.character_name ? <span>{quote.character_name}</span> : null}
            </div>
            <p className={`mt-3 text-base leading-relaxed ${isDark ? "text-gray-100" : "text-gray-800"}`}>{quote.quote_text}</p>
            {quote.note ? <p className={`mt-3 text-sm ${isDark ? "text-gray-400" : "text-gray-500"}`}>{quote.note}</p> : null}
          </article>
        ))}
      </div>
    </div>
  )
}
