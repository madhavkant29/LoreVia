"use client"

import Link from "next/link"
import type { Route } from "next"
import { useDeferredValue, useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { useQuery } from "@tanstack/react-query"

import { authApi } from "@/lib/api/auth"
import { booksApi } from "@/lib/api/books"
import { canUseAuthorFeatures } from "@/lib/billing/plans"
import { publicApi } from "@/lib/api/public"
import { asQueryKey } from "@/lib/query/cacheKeys"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import { formatReputationScore } from "@/lib/utils/publicForum"
import type { Book } from "@/types/book"
import type { PublicForumPost, PublicForumPostListResponse } from "@/types/public"
import type { User } from "@/types/user"

const FORUM_PAGE_SIZE = 20

function getEligibleAuthorBooks(books: Book[], myForumPosts: PublicForumPost[]) {
  const openDiscussionBookIds = new Set(
    myForumPosts
      .filter((post) => post.status === "open")
      .map((post) => post.book_id),
  )
  return books.filter((book) => (
    book.mode === "author"
    && !book.is_public
    && !book.hidden_at
    && !book.archived_at
    && !openDiscussionBookIds.has(book.id)
  ))
}

export default function PublicForumPage() {
  const router = useRouter()
  const [query, setQuery] = useState("")
  const [page, setPage] = useState(1)
  const [viewer, setViewer] = useState<User | null>(null)
  const [authorBooks, setAuthorBooks] = useState<Book[]>([])
  const [selectedBookId, setSelectedBookId] = useState("")
  const [headline, setHeadline] = useState("")
  const [body, setBody] = useState("")
  const [desiredCount, setDesiredCount] = useState("")
  const [allowContactRequests, setAllowContactRequests] = useState(true)
  const [composerStatus, setComposerStatus] = useState<string | null>(null)
  const [creatingPost, setCreatingPost] = useState(false)
  const [authorForumLoadFailed, setAuthorForumLoadFailed] = useState(false)
  const deferredQuery = useDeferredValue(query)
  const { theme } = usePreferencesStore()
  const isDark = theme === "dark"
  const normalizedQuery = deferredQuery.trim()
  const canOpenPublicDiscussions = canUseAuthorFeatures(viewer?.tier)

  useEffect(() => {
    setPage(1)
  }, [normalizedQuery])

  useEffect(() => {
    let active = true

    const loadViewerContext = async () => {
      const viewerPayload = await authApi.me().catch(() => null)
      if (!active) return
      setViewer(viewerPayload)
      if (!viewerPayload) {
        setAuthorBooks([])
        setSelectedBookId("")
        setAuthorForumLoadFailed(false)
        setComposerStatus(null)
        return
      }
      const [booksPayload, myForumPosts] = await Promise.all([
        booksApi.list(true).catch(() => null),
        publicApi.listMyForumPosts().catch(() => null),
      ])
      if (!active) return
      if (booksPayload === null) {
        setAuthorBooks([])
        setSelectedBookId("")
        setAuthorForumLoadFailed(true)
        setComposerStatus("Could not load your author manuscripts right now. Refresh before opening a public discussion.")
        return
      }
      if (myForumPosts === null) {
        setAuthorBooks([])
        setSelectedBookId("")
        setAuthorForumLoadFailed(true)
        setComposerStatus("Could not load your existing public discussions right now. Refresh before opening a new one.")
        return
      }
      const eligibleBooks = getEligibleAuthorBooks(booksPayload, myForumPosts)
      setAuthorForumLoadFailed(false)
      setComposerStatus(null)
      setAuthorBooks(eligibleBooks)
      setSelectedBookId((current) => current || eligibleBooks[0]?.id || "")
    }

    void loadViewerContext()
    return () => {
      active = false
    }
  }, [])

  const { data, isLoading: loading, isError } = useQuery<PublicForumPostListResponse>({
    queryKey: asQueryKey(`public:forum:${normalizedQuery || "all"}:${page}`),
    queryFn: () => publicApi.listForumPosts(normalizedQuery, page, FORUM_PAGE_SIZE),
  })
  const posts = data?.items ?? []
  const error = isError ? "Could not load the public forum right now." : null

  const createPost = async () => {
    if (authorForumLoadFailed) {
      setComposerStatus("Refresh this page before opening a public discussion so LoreVia can verify your existing forum threads.")
      return
    }
    if (!selectedBookId || !headline.trim() || !body.trim()) {
      setComposerStatus("Choose a private manuscript, headline, and discussion brief first.")
      return
    }
    const hasDesiredCount = desiredCount.trim().length > 0
    const parsedDesiredCount = hasDesiredCount ? Number.parseInt(desiredCount, 10) : null
    if (hasDesiredCount && (!Number.isFinite(parsedDesiredCount) || (parsedDesiredCount ?? 0) < 1)) {
      setComposerStatus("Desired beta readers must be a whole number greater than zero.")
      return
    }
    setCreatingPost(true)
    setComposerStatus(null)
    try {
      const created = await publicApi.createForumPost({
        bookId: selectedBookId,
        headline: headline.trim(),
        body: body.trim(),
        desiredBetaReaderCount: parsedDesiredCount,
        allowContactRequests,
      })
      router.push(`/public/forum/${created.id}` as Route)
    } catch {
      setComposerStatus("Could not open a public discussion for this manuscript. If a discussion already exists, open it from the forum list below and edit it there.")
    } finally {
      setCreatingPost(false)
    }
  }

  return (
    <div className={`min-h-screen ${isDark ? "bg-[#071019] text-slate-100" : "bg-[#f4efe7] text-slate-950"}`}>
      <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6 lg:px-8">
        <div className="rounded-[2rem] border px-6 py-8 shadow-[0_24px_80px_rgba(15,23,42,0.12)] backdrop-blur-sm sm:px-8 lg:px-10">
          <div className={isDark ? "border-white/10 bg-[radial-gradient(circle_at_top_left,rgba(251,191,36,0.12),transparent_42%)]" : "border-[#d8c6ab] bg-[radial-gradient(circle_at_top_left,rgba(217,119,6,0.12),transparent_42%)]"}>
            <p className={`text-xs font-semibold uppercase tracking-[0.28em] ${isDark ? "text-amber-300" : "text-amber-700"}`}>Optional public forum</p>
            <div className="mt-4 flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
              <div className="max-w-3xl">
                <h1 className="font-serif text-4xl tracking-tight sm:text-5xl">See which authors choose to open a public conversation around their work.</h1>
                <p className={`mt-4 max-w-2xl text-sm leading-7 ${isDark ? "text-slate-300" : "text-slate-600"}`}>
                  This forum is a trust and discovery layer for authors who want outside visibility. It is not the main LoreVia product path, which stays centered on private author workspaces and invited collaborators.
                </p>
                <p className={`mt-3 text-xs font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-400" : "text-slate-500"}`}>
                  Current status: public
                </p>
              </div>
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search title, genre, username, or headline"
                className={`h-12 w-full rounded-full border px-5 text-sm outline-none transition lg:max-w-md ${isDark ? "border-white/10 bg-white/5 text-slate-100 placeholder:text-slate-500 focus:border-amber-400" : "border-[#d8c6ab] bg-white/90 text-slate-900 placeholder:text-slate-400 focus:border-amber-500"}`}
              />
            </div>
          </div>
        </div>

        {viewer ? (
          <section className={`mt-8 rounded-[2rem] border p-6 sm:p-8 ${isDark ? "border-white/10 bg-white/[0.04]" : "border-[#dfd3c2] bg-white/92"}`}>
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div className="max-w-3xl">
                <p className={`text-xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-400" : "text-slate-500"}`}>Author-only setup</p>
                <h2 className="mt-2 font-serif text-3xl tracking-tight">Open a public beta discussion for one private manuscript.</h2>
                <p className={`mt-3 text-sm leading-7 ${isDark ? "text-slate-300" : "text-slate-600"}`}>
                  Use this only when you want outside discovery. Your main manuscript workflow and invited beta-reader collaboration stay inside the private author workspace.
                </p>
              </div>
              <p className={`text-xs ${isDark ? "text-slate-500" : "text-slate-500"}`}>Signed in as @{viewer.username || "member"}</p>
            </div>

            {!canOpenPublicDiscussions ? (
              <div className={`mt-5 rounded-3xl border px-5 py-6 text-sm ${isDark ? "border-amber-400/25 bg-amber-400/10 text-amber-100" : "border-amber-200 bg-amber-50 text-amber-800"}`}>
                Public manuscript discussions are limited to Author and Architect plans. Free accounts can still browse discussions, comment, react, and offer to beta read.
                <div className="mt-4">
                  <button
                    type="button"
                    onClick={() => router.push("/upgrade" as Route)}
                    className={`inline-flex h-11 items-center justify-center rounded-full px-5 text-sm font-semibold transition ${isDark ? "bg-amber-400 text-slate-950 hover:bg-amber-300" : "bg-slate-950 text-white hover:bg-slate-800"}`}
                  >
                    View plans
                  </button>
                </div>
              </div>
            ) : authorBooks.length === 0 ? (
              <div className={`mt-5 rounded-3xl border border-dashed px-5 py-6 text-sm ${isDark ? "border-white/10 text-slate-400" : "border-[#d8c6ab] text-slate-500"}`}>
                {authorForumLoadFailed
                  ? "LoreVia could not verify your current public forum threads right now. Refresh before opening a new discussion."
                  : "No eligible private author manuscripts are available for a public beta discussion right now. Manuscripts with an existing open discussion are excluded until that thread is closed."}
              </div>
            ) : (
              <div className="mt-6 space-y-4">
                <select
                  value={selectedBookId}
                  onChange={(event) => setSelectedBookId(event.target.value)}
                  className={`w-full rounded-3xl border px-5 py-3 text-sm outline-none transition ${isDark ? "border-white/10 bg-[#0b131b] text-slate-100 focus:border-amber-400" : "border-[#d8c6ab] bg-[#fffdfa] text-slate-900 focus:border-amber-500"}`}
                >
                  {authorBooks.map((book) => (
                    <option key={book.id} value={book.id}>
                      {book.title}
                    </option>
                  ))}
                </select>
                <input
                  value={headline}
                  onChange={(event) => setHeadline(event.target.value)}
                  placeholder="Discussion headline"
                  className={`w-full rounded-3xl border px-5 py-3 text-sm outline-none transition ${isDark ? "border-white/10 bg-[#0b131b] text-slate-100 placeholder:text-slate-600 focus:border-amber-400" : "border-[#d8c6ab] bg-[#fffdfa] text-slate-900 placeholder:text-slate-400 focus:border-amber-500"}`}
                />
                <textarea
                  value={body}
                  onChange={(event) => setBody(event.target.value)}
                  placeholder="Describe the kind of beta feedback you want and what collaborators should pay attention to."
                  className={`min-h-[10rem] w-full rounded-3xl border px-5 py-4 text-sm leading-7 outline-none transition ${isDark ? "border-white/10 bg-[#0b131b] text-slate-100 placeholder:text-slate-600 focus:border-amber-400" : "border-[#d8c6ab] bg-[#fffdfa] text-slate-900 placeholder:text-slate-400 focus:border-amber-500"}`}
                />
                <div className="grid gap-4 sm:grid-cols-2">
                  <input
                    value={desiredCount}
                    onChange={(event) => setDesiredCount(event.target.value)}
                    placeholder="Desired beta readers"
                    inputMode="numeric"
                    className={`w-full rounded-3xl border px-5 py-3 text-sm outline-none transition ${isDark ? "border-white/10 bg-[#0b131b] text-slate-100 placeholder:text-slate-600 focus:border-amber-400" : "border-[#d8c6ab] bg-[#fffdfa] text-slate-900 placeholder:text-slate-400 focus:border-amber-500"}`}
                  />
                  <label className={`flex items-center justify-between rounded-3xl border px-5 py-3 text-sm ${isDark ? "border-white/10 bg-[#0b131b] text-slate-100" : "border-[#d8c6ab] bg-[#fffdfa] text-slate-900"}`}>
                    <span>Allow collaborator contact requests</span>
                    <input
                      type="checkbox"
                      checked={allowContactRequests}
                      onChange={(event) => setAllowContactRequests(event.target.checked)}
                      className="h-4 w-4"
                    />
                  </label>
                </div>
                {composerStatus ? <p className={`text-sm ${isDark ? "text-slate-400" : "text-slate-600"}`}>{composerStatus}</p> : null}
                <div className="flex flex-wrap items-center gap-3">
                  <button
                    type="button"
                    onClick={() => void createPost()}
                    disabled={creatingPost || authorForumLoadFailed}
                    className={`inline-flex h-11 items-center justify-center rounded-full px-5 text-sm font-semibold transition ${isDark ? "bg-amber-400 text-slate-950 hover:bg-amber-300 disabled:bg-amber-400/40" : "bg-slate-950 text-white hover:bg-slate-800 disabled:bg-slate-300"}`}
                  >
                    {creatingPost ? "Opening..." : "Open public discussion"}
                  </button>
                </div>
              </div>
            )}
          </section>
        ) : null}

        {error ? (
          <div className={`mt-6 rounded-3xl border px-5 py-4 text-sm ${isDark ? "border-rose-500/30 bg-rose-500/10 text-rose-200" : "border-rose-200 bg-rose-50 text-rose-700"}`}>{error}</div>
        ) : null}

        <div className="mt-8 grid gap-5">
          {loading ? (
            <div className={`rounded-3xl border px-5 py-6 text-sm ${isDark ? "border-white/10 bg-white/[0.04] text-slate-400" : "border-[#dfd3c2] bg-white/90 text-slate-500"}`}>Loading forum posts...</div>
          ) : null}
          {!loading && posts.length === 0 ? (
            <div className={`rounded-3xl border px-5 py-6 text-sm ${isDark ? "border-white/10 bg-white/[0.04] text-slate-400" : "border-[#dfd3c2] bg-white/90 text-slate-500"}`}>No public forum posts match this search yet.</div>
          ) : null}
          {!loading ? posts.map((post) => (
            <article key={post.id} className={`rounded-3xl border p-6 ${isDark ? "border-white/10 bg-white/[0.04]" : "border-[#dfd3c2] bg-white/92"}`}>
              <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em]">
                    <span className={isDark ? "text-amber-300" : "text-amber-700"}>{post.genre || post.work_type}</span>
                    <span className={isDark ? "text-slate-500" : "text-slate-400"}>{new Date(post.created_at).toLocaleDateString()}</span>
                  </div>
                  <h2 className="mt-3 font-serif text-2xl tracking-tight">{post.headline}</h2>
                  <p className={`mt-2 text-base ${isDark ? "text-slate-300" : "text-slate-600"}`}>{post.title}</p>
                  <p className={`mt-4 max-w-3xl text-sm leading-7 ${isDark ? "text-slate-300" : "text-slate-600"}`}>{post.body}</p>
                </div>
                <div className={`min-w-[14rem] rounded-2xl border px-4 py-4 text-sm ${isDark ? "border-white/10 bg-black/20" : "border-[#eadfce] bg-[#fbf7f0]"}`}>
                  <p className={`text-[11px] font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-400" : "text-slate-500"}`}>Writer</p>
                  {post.author_username ? (
                    <Link href={`/public/writers/${post.author_username}` as Route} className={`mt-2 block font-semibold ${isDark ? "text-white hover:text-amber-300" : "text-slate-900 hover:text-amber-700"}`}>
                      @{post.author_username}
                    </Link>
                  ) : (
                    <p className="mt-2 font-semibold">{post.author || "Unknown author"}</p>
                  )}
                  <p className={`mt-2 text-sm ${isDark ? "text-slate-400" : "text-slate-600"}`}>{post.author_trust_level} | reputation {formatReputationScore(post.author_reputation_score)}</p>
                  <div className="mt-4 flex flex-wrap gap-2 text-xs">
                    <span className={`rounded-full px-3 py-1 ${isDark ? "bg-white/6 text-slate-300" : "bg-white text-slate-600"}`}>{post.interest_count} interest</span>
                    <span className={`rounded-full px-3 py-1 ${isDark ? "bg-white/6 text-slate-300" : "bg-white text-slate-600"}`}>{post.comment_count} comments</span>
                    <span className={`rounded-full px-3 py-1 ${isDark ? "bg-white/6 text-slate-300" : "bg-white text-slate-600"}`}>Score {Math.round(post.discoverability_score)}</span>
                  </div>
                </div>
              </div>
              <div className="mt-6 flex flex-wrap items-center gap-3">
                <Link href={`/public/forum/${post.id}` as Route} className={`inline-flex h-11 items-center justify-center rounded-full px-5 text-sm font-semibold transition ${isDark ? "bg-amber-400 text-slate-950 hover:bg-amber-300" : "bg-slate-950 text-white hover:bg-slate-800"}`}>
                  Open discussion
                </Link>
                <p className={`text-xs ${isDark ? "text-slate-500" : "text-slate-500"}`}>
                  Avg rating {post.rating_summary.average_rating?.toFixed(1) ?? "n/a"} from {post.rating_summary.rating_count} beta review{post.rating_summary.rating_count === 1 ? "" : "s"}.
                </p>
              </div>
            </article>
          )) : null}

          {!loading && data && data.total > 0 ? (
            <div className="flex flex-col gap-3 pt-2 sm:flex-row sm:items-center sm:justify-between">
              <p className={`text-sm ${isDark ? "text-slate-400" : "text-slate-600"}`}>
                Showing {(data.page - 1) * data.page_size + 1}-{Math.min(data.page * data.page_size, data.total)} of {data.total} posts
              </p>
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={() => setPage((current) => Math.max(1, current - 1))}
                  disabled={data.page <= 1}
                  className={`inline-flex h-10 items-center justify-center rounded-full px-4 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-50 ${isDark ? "border border-white/10 bg-white/5 text-slate-100 hover:bg-white/10" : "border border-[#d8c6ab] bg-white text-slate-900 hover:bg-[#f8f1e7]"}`}
                >
                  Previous
                </button>
                <span className={`text-sm ${isDark ? "text-slate-300" : "text-slate-700"}`}>Page {data.page}</span>
                <button
                  type="button"
                  onClick={() => setPage((current) => current + 1)}
                  disabled={!data.has_more}
                  className={`inline-flex h-10 items-center justify-center rounded-full px-4 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-50 ${isDark ? "border border-white/10 bg-white/5 text-slate-100 hover:bg-white/10" : "border border-[#d8c6ab] bg-white text-slate-900 hover:bg-[#f8f1e7]"}`}
                >
                  Next
                </button>
              </div>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  )
}
