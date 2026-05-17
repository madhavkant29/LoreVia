"use client"

import Link from "next/link"
import type { Route } from "next"
import { useQuery } from "@tanstack/react-query"

import { publicApi } from "@/lib/api/public"
import { asQueryKey } from "@/lib/query/cacheKeys"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import type { PublicBook } from "@/types/book"

export default function PublicLibraryPage() {
  const { theme } = usePreferencesStore()
  const isDark = theme === "dark"
  const { data: books = [], isLoading: loading } = useQuery<PublicBook[]>({
    queryKey: asQueryKey("public:books"),
    queryFn: () => publicApi.listBooks(),
    staleTime: 60_000,
  })

  return (
    <main className={`min-h-screen ${isDark ? "bg-black text-white" : "bg-stone-50 text-stone-950"}`}>
      <div className="mx-auto max-w-6xl px-4 py-10">
        <div className="max-w-3xl">
          <p className={`text-xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-cyan-300" : "text-cyan-700"}`}>Optional public showcase</p>
          <h1 className="mt-4 text-4xl font-semibold tracking-tight">Explore public LoreVia demos and author-shared samples.</h1>
          <p className={`mt-4 text-base leading-8 ${isDark ? "text-slate-300" : "text-stone-600"}`}>
            This library is a secondary showcase surface for public-domain examples and author-shared samples. LoreVia's core workflow still lives in the private author workspace.
          </p>
        </div>

        {loading ? (
          <div className={`mt-12 rounded-2xl border px-6 py-12 text-center ${isDark ? "border-white/10 bg-white/5 text-slate-400" : "border-stone-200 bg-white text-stone-500"}`}>
            Loading public books...
          </div>
        ) : books.length === 0 ? (
          <div className={`mt-12 rounded-2xl border px-6 py-12 text-center ${isDark ? "border-white/10 bg-white/5 text-slate-400" : "border-stone-200 bg-white text-stone-500"}`}>
            No public showcase books are available yet.
          </div>
        ) : (
          <div className="mt-12 grid gap-5 md:grid-cols-2 xl:grid-cols-3">
            {books.map((book) => (
              <article
                key={book.id}
                className={`rounded-2xl border p-6 ${isDark ? "border-white/10 bg-white/[0.04]" : "border-stone-200 bg-white"}`}
              >
                <p className={`text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>
                  {book.work_type}
                  {book.genre ? ` - ${book.genre}` : ""}
                </p>
                <h2 className="mt-3 text-2xl font-semibold">{book.title}</h2>
                {book.author_username ? (
                  <Link href={`/public/writers/${book.author_username}` as Route} className={`mt-2 inline-flex text-sm font-semibold ${isDark ? "text-cyan-200 hover:text-white" : "text-cyan-700 hover:text-cyan-900"}`}>
                    @{book.author_username}
                  </Link>
                ) : book.author ? (
                  <p className={`mt-2 text-sm ${isDark ? "text-slate-300" : "text-stone-600"}`}>by {book.author}</p>
                ) : null}
                {book.description ? (
                  <p className={`mt-4 text-sm leading-7 ${isDark ? "text-slate-300" : "text-stone-600"}`}>{book.description}</p>
                ) : null}
                <div className={`mt-5 flex flex-wrap gap-2 text-xs ${isDark ? "text-slate-400" : "text-stone-500"}`}>
                  <span>{book.total_chapters ?? "?"} chapters</span>
                  <span>-</span>
                  <span>{book.status}</span>
                </div>
                <div className="mt-6">
                  <Link
                    href={`/public/${book.id}` as Route}
                    className={`inline-flex rounded-full px-4 py-2 text-sm font-semibold ${isDark ? "bg-white text-stone-950 hover:bg-slate-200" : "bg-stone-950 text-white hover:bg-stone-800"}`}
                  >
                    Open sample
                  </Link>
                </div>
              </article>
            ))}
          </div>
        )}
      </div>
    </main>
  )
}
