"use client"

import Link from "next/link"
import type { Route } from "next"
import { useInfiniteQuery } from "@tanstack/react-query"

import { publicApi } from "@/lib/api/public"
import { asQueryKey } from "@/lib/query/cacheKeys"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import type { PublicBook, PublicBookPage } from "@/types/book"

const PUBLIC_BOOK_PAGE_LIMIT = 24

type PublicLibraryPageClientProps = {
  /**
   * The cursor page rendered on the server. Keeping initialBooks temporarily
   * supports callers that have not moved to the paged contract yet.
   */
  initialPage?: PublicBookPage
  initialBooks?: PublicBook[]
}

export function PublicLibraryPageClient({ initialPage, initialBooks = [] }: PublicLibraryPageClientProps) {
  const { theme } = usePreferencesStore()
  const isDark = theme === "dark"
  const legacyInitialPage = initialBooks.length > 0
    ? { items: initialBooks, next_cursor: null, has_more: false }
    : undefined
  const seedPage = initialPage ?? legacyInitialPage
  const {
    data,
    isLoading: loading,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
  } = useInfiniteQuery({
    queryKey: asQueryKey("public:books:page"),
    initialPageParam: null as string | null,
    queryFn: ({ pageParam }) => publicApi.listBooksPage({
      cursor: pageParam,
      limit: PUBLIC_BOOK_PAGE_LIMIT,
    }),
    getNextPageParam: (page) => page.has_more ? page.next_cursor ?? undefined : undefined,
    staleTime: 60_000,
    ...(seedPage ? { initialData: { pages: [seedPage], pageParams: [null] } } : {}),
  })
  const books = data?.pages.flatMap((page) => page.items) ?? []

  return (
    <main className={`min-h-screen ${isDark ? "bg-[#0a0f14] text-slate-100" : "bg-[#f4f5f2] text-stone-950"}`}>
      <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <div className="flex flex-col gap-5 border-b pb-7 sm:flex-row sm:items-end sm:justify-between">
          <div className="max-w-3xl">
          <p className={`text-xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-teal-300" : "text-teal-700"}`}>LoreVia public library</p>
          <h1 className="mt-4 font-display text-4xl tracking-[-0.035em] sm:text-5xl">Published work for focused reading.</h1>
          <p className={`mt-4 text-base leading-8 ${isDark ? "text-slate-300" : "text-stone-600"}`}>
            Browse creator-published originals and public-domain demonstrations. Private author workspaces stay separate from this catalog.
          </p>
          </div>
          <nav className="flex flex-wrap gap-2 text-sm font-semibold">
            <Link href="/public/forum" className={`rounded-md border px-4 py-2 transition ${isDark ? "border-white/10 bg-white/[0.04] text-slate-100 hover:bg-white/[0.08]" : "border-stone-200 bg-white text-stone-800 hover:bg-stone-50"}`}>
              Book discussions
            </Link>
            <Link href="/register" className={`rounded-md px-4 py-2 transition ${isDark ? "bg-teal-400 text-slate-950 hover:bg-teal-300" : "bg-[#1f615d] text-white hover:bg-[#174c49]"}`}>
              Create author account
            </Link>
          </nav>
        </div>

        {loading && books.length === 0 ? (
          <div className={`mt-8 rounded-lg border px-6 py-12 text-center ${isDark ? "border-white/10 bg-white/5 text-slate-400" : "border-stone-200 bg-white text-stone-500"}`}>
            Loading public books...
          </div>
        ) : books.length === 0 ? (
          <div className={`mt-8 rounded-lg border px-6 py-12 text-center ${isDark ? "border-white/10 bg-white/5 text-slate-400" : "border-stone-200 bg-white text-stone-500"}`}>
            No public showcase books are available yet.
          </div>
        ) : (
          <div className="mt-8 space-y-3">
            {books.map((book) => (
              <article
                key={book.id}
                className={`grid gap-5 rounded-lg border p-5 transition sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center ${isDark ? "border-white/10 bg-[#121821] hover:border-teal-300/30" : "border-stone-200 bg-white hover:border-teal-700/30"}`}
              >
                <div className="min-w-0">
                  <p className={`text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>
                    {book.content_source_type === "public_domain" ? "Public-domain demo" : "Creator-published original"}
                    {book.genre ? ` / ${book.genre}` : ""}
                  </p>
                  <h2 className="mt-2 text-2xl font-semibold">{book.title}</h2>
                  {book.author_username ? (
                    <Link href={`/public/writers/${book.author_username}` as Route} className={`mt-2 inline-flex text-sm font-semibold ${isDark ? "text-teal-200 hover:text-white" : "text-teal-700 hover:text-teal-900"}`}>
                      @{book.author_username}
                    </Link>
                  ) : book.author ? (
                    <p className={`mt-2 text-sm ${isDark ? "text-slate-300" : "text-stone-600"}`}>by {book.author}</p>
                  ) : null}
                  {book.description ? (
                    <p className={`mt-3 max-w-3xl text-sm leading-7 ${isDark ? "text-slate-300" : "text-stone-600"}`}>{book.description}</p>
                  ) : null}
                  <div className={`mt-4 flex flex-wrap gap-x-4 gap-y-2 text-xs ${isDark ? "text-slate-400" : "text-stone-500"}`}>
                    <span>{book.total_chapters ?? "?"} chapters</span>
                    <span>{book.status}</span>
                    <span>{(book.analytics?.book_view_count ?? 0).toLocaleString()} views</span>
                  </div>
                </div>
                <div className="flex flex-wrap gap-2 sm:flex-col sm:items-stretch">
                  <Link
                    href={`/public/${book.public_slug || book.id}` as Route}
                    className={`inline-flex justify-center rounded-md px-4 py-2 text-sm font-semibold ${isDark ? "bg-teal-400 text-slate-950 hover:bg-teal-300" : "bg-[#1f615d] text-white hover:bg-[#174c49]"}`}
                  >
                    Read book
                  </Link>
                  {book.active_forum_post_id ? (
                    <Link
                      href={`/public/forum/${book.active_forum_post_id}` as Route}
                      className={`inline-flex justify-center rounded-md border px-4 py-2 text-sm font-semibold ${isDark ? "border-white/10 bg-white/5 text-white hover:bg-white/10" : "border-stone-200 bg-white text-stone-900 hover:bg-stone-50"}`}
                    >
                      Discussion
                    </Link>
                  ) : null}
                </div>
              </article>
            ))}
            {hasNextPage ? (
              <div className="pt-3 text-center">
                <button
                  type="button"
                  onClick={() => void fetchNextPage()}
                  disabled={isFetchingNextPage}
                  className={`rounded-md border px-4 py-2 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-60 ${isDark ? "border-white/10 bg-white/[0.04] text-slate-100 hover:bg-white/[0.08]" : "border-stone-200 bg-white text-stone-800 hover:bg-stone-50"}`}
                >
                  {isFetchingNextPage ? "Loading more…" : "Load more books"}
                </button>
              </div>
            ) : null}
          </div>
        )}
      </div>
    </main>
  )
}
