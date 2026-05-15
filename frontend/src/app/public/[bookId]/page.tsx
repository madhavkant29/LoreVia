"use client"

import Link from "next/link"
import type { Route } from "next"
import { useQuery } from "@tanstack/react-query"
import { useParams } from "next/navigation"

import { publicApi } from "@/lib/api/public"
import { asQueryKey } from "@/lib/query/cacheKeys"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import type { PublicBookDetail } from "@/types/book"

export default function PublicBookPage() {
  const { bookId } = useParams<{ bookId: string }>()
  const { theme } = usePreferencesStore()
  const isDark = theme === "dark"
  const { data: book = null, isLoading: loading } = useQuery<PublicBookDetail | null>({
    queryKey: asQueryKey(`public:book:${bookId}`),
    queryFn: () => publicApi.getBook(bookId),
    staleTime: 60_000,
  })

  if (loading) {
    return <div className={`mx-auto max-w-5xl px-4 py-20 text-center ${isDark ? "text-slate-400" : "text-stone-500"}`}>Loading public book...</div>
  }

  if (!book) {
    return <div className={`mx-auto max-w-5xl px-4 py-20 text-center ${isDark ? "text-slate-400" : "text-stone-500"}`}>Public book not found.</div>
  }

  return (
    <main className={`min-h-screen ${isDark ? "bg-black text-white" : "bg-stone-50 text-stone-950"}`}>
      <div className="mx-auto max-w-5xl px-4 py-10">
        <div className="flex flex-wrap items-center gap-3">
          <Link href="/public" className={`text-sm ${isDark ? "text-slate-400 hover:text-white" : "text-stone-500 hover:text-stone-900"}`}>
            {"<- Back to public library"}
          </Link>
        </div>

        <div className="mt-8 max-w-3xl">
          <p className={`text-xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-cyan-300" : "text-cyan-700"}`}>Public book</p>
          <h1 className="mt-4 text-4xl font-semibold tracking-tight">{book.title}</h1>
          {book.author_username ? (
            <Link href={`/public/writers/${book.author_username}` as Route} className={`mt-3 inline-flex text-lg font-semibold ${isDark ? "text-cyan-200 hover:text-white" : "text-cyan-700 hover:text-cyan-900"}`}>
              @{book.author_username}
            </Link>
          ) : book.author ? (
            <p className={`mt-3 text-lg ${isDark ? "text-slate-300" : "text-stone-600"}`}>by {book.author}</p>
          ) : null}
          {book.description ? (
            <p className={`mt-5 text-base leading-8 ${isDark ? "text-slate-300" : "text-stone-600"}`}>{book.description}</p>
          ) : null}
          {book.author_username ? (
            <p className={`mt-5 text-sm leading-7 ${isDark ? "text-slate-400" : "text-stone-500"}`}>
              Want the trust context before reading? Visit this writer&apos;s public profile for forum reputation and visible participation.
            </p>
          ) : null}
        </div>

        <section className="mt-10">
          <div className={`rounded-2xl border p-6 ${isDark ? "border-white/10 bg-white/[0.04]" : "border-stone-200 bg-white"}`}>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 className="text-2xl font-semibold">Chapters</h2>
              <p className={`text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>{book.total_chapters ?? book.chapters.length} available</p>
            </div>
            <div className="mt-6 grid gap-3">
              {book.chapters.map((chapter) => (
                <Link
                  key={chapter.number}
                  href={`/public/${book.id}/chapter/${chapter.number}` as Route}
                  className={`rounded-xl border px-4 py-4 transition ${isDark ? "border-white/10 bg-white/[0.03] hover:bg-white/[0.06]" : "border-stone-200 bg-stone-50 hover:bg-stone-100"}`}
                >
                  <p className="font-semibold">{chapter.title || `Chapter ${chapter.number}`}</p>
                  {chapter.description ? (
                    <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-400" : "text-stone-600"}`}>{chapter.description}</p>
                  ) : null}
                </Link>
              ))}
            </div>
          </div>
        </section>
      </div>
    </main>
  )
}
