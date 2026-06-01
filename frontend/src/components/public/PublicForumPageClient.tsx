"use client"

import Link from "next/link"
import type { Route } from "next"
import { startTransition, useDeferredValue, useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { useQuery } from "@tanstack/react-query"

import { authApi } from "@/lib/api/auth"
import { booksApi } from "@/lib/api/books"
import { canUseAuthorFeatures } from "@/lib/billing/plans"
import { publicApi } from "@/lib/api/public"
import { asQueryKey } from "@/lib/query/cacheKeys"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import { formatReputationScore, getEligibleForumAuthorBooks } from "@/lib/utils/publicForum"
import type { Book } from "@/types/book"
import type { PublicForumPost, PublicForumPostListResponse } from "@/types/public"
import type { User } from "@/types/user"

const FORUM_PAGE_SIZE = 20
const rankingOptions = [
  { value: "most_popular", label: "Most popular" },
  { value: "top_rated", label: "Top rated" },
  { value: "most_complex", label: "Most complex" },
  { value: "big_cast", label: "Big cast" },
  { value: "most_well_written", label: "Most well written" },
  { value: "beginner_friendly", label: "Beginner friendly" },
  { value: "recently_updated", label: "Recently updated" },
  { value: "recently_released", label: "Recently released" },
] as const
const timeWindowOptions = [
  { value: "daily", label: "Daily" },
  { value: "weekly", label: "Weekly" },
  { value: "monthly", label: "Monthly" },
  { value: "yearly", label: "Yearly" },
  { value: "all_time", label: "All time" },
] as const

export function PublicForumPageClient({
  initialData,
}: {
  initialData?: PublicForumPostListResponse
}) {
  const router = useRouter()
  const [query, setQuery] = useState("")
  const [page, setPage] = useState(initialData?.page ?? 1)
  const [ranking, setRanking] = useState(initialData?.ranking_key ?? "most_popular")
  const [timeWindow, setTimeWindow] = useState(initialData?.time_window ?? "monthly")
  const [viewer, setViewer] = useState<User | null>(null)
  const [authorBooks, setAuthorBooks] = useState<Book[]>([])
  const [composerThreadType, setComposerThreadType] = useState<"novel" | "general">("novel")
  const [selectedBookId, setSelectedBookId] = useState("")
  const [headline, setHeadline] = useState("")
  const [body, setBody] = useState("")
  const [novelTitle, setNovelTitle] = useState("")
  const [novelGenre, setNovelGenre] = useState("")
  const [novelDescription, setNovelDescription] = useState("")
  const [desiredCount, setDesiredCount] = useState("")
  const [allowContactRequests, setAllowContactRequests] = useState(true)
  const [composerStatus, setComposerStatus] = useState<string | null>(null)
  const [creatingPost, setCreatingPost] = useState(false)
  const [authorForumLoadFailed, setAuthorForumLoadFailed] = useState(false)
  const [viewerContextEnabled, setViewerContextEnabled] = useState(false)
  const deferredQuery = useDeferredValue(query)
  const { theme } = usePreferencesStore()
  const isDark = theme === "dark"
  const normalizedQuery = deferredQuery.trim()
  const canOpenPublicDiscussions = canUseAuthorFeatures(viewer?.tier)
  const selectedBook = authorBooks.find((book) => book.id === selectedBookId) ?? null

  useEffect(() => {
    setPage(1)
  }, [normalizedQuery, ranking, timeWindow])

  useEffect(() => {
    if (viewerContextEnabled) return

    const schedule =
      typeof window.requestIdleCallback === "function"
        ? window.requestIdleCallback.bind(window)
        : ((callback: IdleRequestCallback) =>
            window.setTimeout(() => callback({ didTimeout: false, timeRemaining: () => 0 } as IdleDeadline), 150))
    const cancel =
      typeof window.cancelIdleCallback === "function"
        ? window.cancelIdleCallback.bind(window)
        : window.clearTimeout.bind(window)

    const handle = schedule(() => {
      startTransition(() => setViewerContextEnabled(true))
    })

    return () => cancel(handle)
  }, [viewerContextEnabled])

  useEffect(() => {
    if (composerThreadType !== "novel") {
      return
    }
    setNovelTitle(selectedBook?.title ?? "")
    setNovelGenre(selectedBook?.genre ?? "")
    setNovelDescription(selectedBook?.public_description ?? "")
  }, [composerThreadType, selectedBookId, selectedBook?.genre, selectedBook?.public_description, selectedBook?.title])

  useEffect(() => {
    if (!viewerContextEnabled) return

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
      const eligibleBooks = getEligibleForumAuthorBooks(booksPayload, myForumPosts)
      setAuthorForumLoadFailed(false)
      setComposerStatus(null)
      setAuthorBooks(eligibleBooks)
      setSelectedBookId((current) => (
        eligibleBooks.some((book) => book.id === current)
          ? current
          : (eligibleBooks[0]?.id || "")
      ))
    }

    void loadViewerContext()
    const handleWindowRefresh = () => {
      void loadViewerContext()
    }
    window.addEventListener("focus", handleWindowRefresh)
    window.addEventListener("pageshow", handleWindowRefresh)
    return () => {
      active = false
      window.removeEventListener("focus", handleWindowRefresh)
      window.removeEventListener("pageshow", handleWindowRefresh)
    }
  }, [viewerContextEnabled])

  const { data, isLoading: loading, isError } = useQuery<PublicForumPostListResponse>({
    queryKey: asQueryKey(`public:forum:ranked:${ranking}:${timeWindow}:${normalizedQuery || "all"}:${page}`),
    queryFn: () => publicApi.listRankedBetaNovels({
      ranking,
      timeWindow,
      query: normalizedQuery,
      page,
      pageSize: FORUM_PAGE_SIZE,
    }),
    initialData: (
      normalizedQuery.length === 0
      && page === (initialData?.page ?? 1)
      && ranking === (initialData?.ranking_key ?? "most_popular")
      && timeWindow === (initialData?.time_window ?? "monthly")
    ) ? initialData : undefined,
    staleTime: 30_000,
  })
  const posts = data?.items ?? []
  const error = isError ? "Could not load the public forum right now." : null

  const createPost = async () => {
    if (!viewer) {
      setComposerStatus("Sign in to open a discussion.")
      return
    }
    if (composerThreadType === "novel" && authorForumLoadFailed) {
      setComposerStatus("Refresh this page before opening a public discussion so LoreVia can verify your existing forum threads.")
      return
    }
    if (!headline.trim() || !body.trim()) {
      setComposerStatus(composerThreadType === "novel" ? "Choose an eligible manuscript, headline, and discussion brief first." : "Add a headline and body before opening a general discussion.")
      return
    }
    if (headline.trim().length < 3) {
      setComposerStatus("Headline must be at least 3 characters long.")
      return
    }
    if (body.trim().length < 20) {
      setComposerStatus("Discussion brief must be at least 20 characters long.")
      return
    }
    if (composerThreadType === "novel" && !canOpenPublicDiscussions) {
      setComposerStatus("Novel discussions require Trial, Author, or Architect access.")
      return
    }
    if (composerThreadType === "novel" && !selectedBookId) {
      setComposerStatus("Choose an eligible manuscript first.")
      return
    }
    if (composerThreadType === "novel" && (!novelTitle.trim() || !novelGenre.trim() || !novelDescription.trim())) {
      setComposerStatus("Novel discussions require a novel name, genre, and description.")
      return
    }
    const hasDesiredCount = desiredCount.trim().length > 0
    const parsedDesiredCount = hasDesiredCount ? Number.parseInt(desiredCount, 10) : null
    if (composerThreadType === "novel" && hasDesiredCount && (!Number.isFinite(parsedDesiredCount) || (parsedDesiredCount ?? 0) < 1)) {
      setComposerStatus("Desired beta readers must be a whole number greater than zero.")
      return
    }
    setCreatingPost(true)
    setComposerStatus(null)
    try {
      if (composerThreadType === "novel") {
        const updatedBook = await booksApi.updateForumMetadata(selectedBookId, {
          title: novelTitle.trim(),
          genre: novelGenre.trim(),
          description: novelDescription.trim(),
        })
        setAuthorBooks((current) => current.map((book) => book.id === updatedBook.id ? updatedBook : book))
      }
      const created = await publicApi.createForumPost({
        threadType: composerThreadType,
        bookId: composerThreadType === "novel" ? selectedBookId : null,
        headline: headline.trim(),
        body: body.trim(),
        desiredBetaReaderCount: composerThreadType === "novel" ? parsedDesiredCount : null,
        allowContactRequests: composerThreadType === "novel" ? allowContactRequests : false,
      })
      router.push(`/public/forum/${created.id}` as Route)
    } catch (error) {
      const fallback = composerThreadType === "novel"
        ? "Could not open a public discussion for this manuscript. If a discussion already exists, open it from the forum list below and edit it there."
        : "Could not open that general discussion right now."
      const detail = typeof error === "object" && error && "response" in error
        ? String((error as { response?: { data?: { detail?: string } } }).response?.data?.detail || "")
        : ""
      setComposerStatus(detail || fallback)
    } finally {
      setCreatingPost(false)
    }
  }

  return (
    <div className={`min-h-screen ${isDark ? "bg-[#0a0f14] text-slate-100" : "bg-[#edf1f5] text-slate-950"}`}>
      <div className={`border-b backdrop-blur ${isDark ? "border-white/10 bg-[#0f141b]/95" : "border-slate-200 bg-white/95"}`}>
        <div className="mx-auto flex max-w-7xl flex-col gap-4 px-4 py-4 sm:px-6 lg:px-8">
          <Link href="/library" className={`text-sm ${isDark ? "text-slate-400 hover:text-white" : "text-slate-500 hover:text-slate-900"}`}>{"<- Back to library"}</Link>
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2 text-3xs font-semibold uppercase tracking-[0.18em]">
                <span className={`rounded-full px-2.5 py-1 ${isDark ? "bg-[#1d2631] text-slate-200" : "bg-slate-100 text-slate-700"}`}>LoreVia Forum</span>
                <span className={isDark ? "text-slate-500" : "text-slate-500"}>Ranked beta novels</span>
                <MetaDivider isDark={isDark} />
                <span className={isDark ? "text-emerald-300" : "text-emerald-700"}>Live</span>
              </div>
              <h1 className="mt-3 text-2xl font-semibold tracking-tight sm:text-3xl">Beta novel rankings worth opening.</h1>
              <p className={`mt-2 max-w-2xl text-sm leading-6 ${isDark ? "text-slate-400" : "text-slate-600"}`}>
                A ranking feed for public beta-reading threads, shaped around ratings, craft signals, update cadence, and reader intent.
              </p>
            </div>

            <div className="grid grid-cols-3 gap-2 text-center text-sm lg:w-[280px]">
              <StatCard isDark={isDark} value={String(data?.total ?? 0)} label="threads" />
              <StatCard isDark={isDark} value={String(posts.filter((post) => post.allow_contact_requests).length)} label="open notes" />
              <StatCard isDark={isDark} value={String(page)} label="page" />
            </div>
          </div>

          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div className="grid w-full gap-3 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,0.7fr)_minmax(0,0.7fr)]">
              <label className={`flex h-11 w-full items-center gap-3 rounded-2xl border px-4 ${isDark ? "border-white/10 bg-[#151b22]" : "border-slate-200 bg-white"}`}>
                <SearchIcon className={isDark ? "text-slate-500" : "text-slate-400"} />
                <input
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="Search title, genre, author, headline, or body"
                  className={`w-full bg-transparent text-sm outline-none ${isDark ? "placeholder:text-slate-500" : "placeholder:text-slate-400"}`}
                />
              </label>

              <select
                value={ranking}
                onChange={(event) => setRanking(event.target.value)}
                className={`h-11 rounded-2xl border px-4 text-sm outline-none ${isDark ? "border-white/10 bg-[#151b22] text-slate-100" : "border-slate-200 bg-white text-slate-900"}`}
              >
                {rankingOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>

              <select
                value={timeWindow}
                onChange={(event) => setTimeWindow(event.target.value)}
                className={`h-11 rounded-2xl border px-4 text-sm outline-none ${isDark ? "border-white/10 bg-[#151b22] text-slate-100" : "border-slate-200 bg-white text-slate-900"}`}
              >
                {timeWindowOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>

            <div className="flex flex-wrap items-center gap-2 text-xs">
              <ShellChip isDark={isDark} active>
                {posts[0]?.ranking?.label ?? "Ranked beta feed"}
              </ShellChip>
              <ShellChip isDark={isDark}>Open novel threads</ShellChip>
              <ShellChip isDark={isDark}>Ratings and reader notes</ShellChip>
            </div>
          </div>
        </div>
      </div>

      <div className="mx-auto grid max-w-7xl gap-6 px-4 py-6 sm:px-6 lg:grid-cols-[minmax(0,1fr)_320px] lg:px-8">
        <section className="min-w-0">
          {error ? (
            <div className={`rounded-2xl border px-4 py-4 text-sm ${isDark ? "border-rose-500/30 bg-rose-500/10 text-rose-200" : "border-rose-200 bg-rose-50 text-rose-700"}`}>{error}</div>
          ) : null}

          <div className="grid gap-3">
            {loading ? (
              <div className={`rounded-2xl border px-4 py-5 text-sm ${isDark ? "border-white/10 bg-[#121821] text-slate-400" : "border-slate-200 bg-white text-slate-500"}`}>Loading forum posts...</div>
            ) : null}
            {!loading && posts.length === 0 ? (
              <div className={`rounded-2xl border px-4 py-5 text-sm ${isDark ? "border-white/10 bg-[#121821] text-slate-400" : "border-slate-200 bg-white text-slate-500"}`}>No public forum posts match this search yet.</div>
            ) : null}
            {!loading ? posts.map((post) => (
              <ForumFeedCard key={post.id} isDark={isDark} post={post} />
            )) : null}

            {!loading && data && data.total > 0 ? (
              <div className="flex flex-col gap-3 pt-2 sm:flex-row sm:items-center sm:justify-between">
                <p className={`text-sm ${isDark ? "text-slate-400" : "text-slate-600"}`}>
                  Showing {(data.page - 1) * data.page_size + 1}-{Math.min(data.page * data.page_size, data.total)} of {data.total} threads
                </p>
                <div className="flex items-center gap-3">
                  <button
                    type="button"
                    onClick={() => setPage((current) => Math.max(1, current - 1))}
                    disabled={data.page <= 1}
                    className={`inline-flex h-10 items-center justify-center rounded-full px-4 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-50 ${isDark ? "border border-white/10 bg-white/5 text-slate-100 hover:bg-white/10" : "border border-slate-200 bg-white text-slate-900 hover:bg-slate-50"}`}
                  >
                    Previous
                  </button>
                  <span className={`text-sm ${isDark ? "text-slate-300" : "text-slate-700"}`}>Page {data.page}</span>
                  <button
                    type="button"
                    onClick={() => setPage((current) => current + 1)}
                    disabled={!data.has_more}
                    className={`inline-flex h-10 items-center justify-center rounded-full px-4 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-50 ${isDark ? "border border-white/10 bg-white/5 text-slate-100 hover:bg-white/10" : "border border-slate-200 bg-white text-slate-900 hover:bg-slate-50"}`}
                  >
                    Next
                  </button>
                </div>
              </div>
            ) : null}
          </div>
        </section>

        <aside className="space-y-4 lg:sticky lg:top-4 lg:self-start">
          {viewer ? (
            <section className={`rounded-3xl border p-4 shadow-sm ${isDark ? "border-white/10 bg-[#121821]" : "border-slate-200 bg-white"}`}>
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className={`text-3xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-slate-500"}`}>Author tools</p>
                  <h2 className="mt-2 text-lg font-semibold">Open a new thread</h2>
                  <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-400" : "text-slate-600"}`}>
                    Switch between general community conversations and manuscript-specific beta-reader threads.
                  </p>
                </div>
                <span className={`rounded-full px-2.5 py-1 text-3xs font-semibold ${isDark ? "bg-white/[0.06] text-slate-300" : "bg-slate-100 text-slate-700"}`}>@{viewer.username || "member"}</span>
              </div>
              <div className={`mt-4 inline-flex rounded-full p-1 ${isDark ? "bg-white/[0.05]" : "bg-slate-100"}`}>
                <button
                  type="button"
                  onClick={() => setComposerThreadType("novel")}
                  className={`rounded-full px-4 py-2 text-sm font-semibold ${composerThreadType === "novel" ? (isDark ? "bg-amber-400 text-slate-950" : "bg-slate-950 text-white") : (isDark ? "text-slate-300" : "text-slate-700")}`}
                >
                  Novel discussion
                </button>
                <button
                  type="button"
                  onClick={() => setComposerThreadType("general")}
                  className={`rounded-full px-4 py-2 text-sm font-semibold ${composerThreadType === "general" ? (isDark ? "bg-amber-400 text-slate-950" : "bg-slate-950 text-white") : (isDark ? "text-slate-300" : "text-slate-700")}`}
                >
                  General discussion
                </button>
              </div>

              <div className="mt-4 space-y-3">
                {composerThreadType === "novel" ? (
                  <>
                    {!canOpenPublicDiscussions ? (
                      <div className={`rounded-2xl border px-4 py-4 text-sm ${isDark ? "border-amber-400/25 bg-amber-400/10 text-amber-100" : "border-amber-200 bg-amber-50 text-amber-800"}`}>
                        Opening public manuscript discussions is limited to Trial, Author, and Architect access. Free accounts can still browse threads, comment, react, and offer to beta read.
                        <div className="mt-4">
                          <button
                            type="button"
                            onClick={() => router.push("/upgrade" as Route)}
                            className={`inline-flex h-10 items-center justify-center rounded-full px-4 text-sm font-semibold transition ${isDark ? "bg-amber-400 text-slate-950 hover:bg-amber-300" : "bg-[#ff6a1a] text-white hover:bg-[#f05a09]"}`}
                          >
                            View plans
                          </button>
                        </div>
                      </div>
                    ) : authorBooks.length === 0 ? (
                      <div className={`rounded-2xl border border-dashed px-4 py-4 text-sm ${isDark ? "border-white/10 text-slate-400" : "border-slate-200 text-slate-500"}`}>
                        {authorForumLoadFailed
                          ? "LoreVia could not verify your current public forum threads right now. Refresh before opening a new discussion."
                          : "No eligible author projects are available right now. Private drafts and approved public-share novels with an existing open discussion are excluded until that thread is closed."}
                      </div>
                    ) : (
                      <>
                        <select
                          value={selectedBookId}
                          onChange={(event) => setSelectedBookId(event.target.value)}
                          className={`w-full rounded-2xl border px-4 py-3 text-sm outline-none transition ${isDark ? "border-white/10 bg-[#0f141b] text-slate-100 focus:border-amber-400" : "border-slate-200 bg-slate-50 text-slate-900 focus:border-orange-500"}`}
                        >
                          {authorBooks.map((book) => (
                            <option key={book.id} value={book.id}>
                              {book.title}
                            </option>
                          ))}
                        </select>
                        <input
                          value={novelTitle}
                          onChange={(event) => setNovelTitle(event.target.value)}
                          placeholder="Novel name"
                          className={`w-full rounded-2xl border px-4 py-3 text-sm outline-none transition ${isDark ? "border-white/10 bg-[#0f141b] text-slate-100 placeholder:text-slate-600 focus:border-amber-400" : "border-slate-200 bg-slate-50 text-slate-900 placeholder:text-slate-400 focus:border-orange-500"}`}
                        />
                        <input
                          value={novelGenre}
                          onChange={(event) => setNovelGenre(event.target.value)}
                          placeholder="Genre"
                          className={`w-full rounded-2xl border px-4 py-3 text-sm outline-none transition ${isDark ? "border-white/10 bg-[#0f141b] text-slate-100 placeholder:text-slate-600 focus:border-amber-400" : "border-slate-200 bg-slate-50 text-slate-900 placeholder:text-slate-400 focus:border-orange-500"}`}
                        />
                        <textarea
                          value={novelDescription}
                          onChange={(event) => setNovelDescription(event.target.value)}
                          placeholder="Novel description"
                          className={`min-h-[7rem] w-full rounded-2xl border px-4 py-3 text-sm leading-6 outline-none transition ${isDark ? "border-white/10 bg-[#0f141b] text-slate-100 placeholder:text-slate-600 focus:border-amber-400" : "border-slate-200 bg-slate-50 text-slate-900 placeholder:text-slate-400 focus:border-orange-500"}`}
                        />
                        <input
                          value={desiredCount}
                          onChange={(event) => setDesiredCount(event.target.value)}
                          placeholder="Desired readers"
                          inputMode="numeric"
                          className={`w-full rounded-2xl border px-4 py-3 text-sm outline-none transition ${isDark ? "border-white/10 bg-[#0f141b] text-slate-100 placeholder:text-slate-600 focus:border-amber-400" : "border-slate-200 bg-slate-50 text-slate-900 placeholder:text-slate-400 focus:border-orange-500"}`}
                        />
                        <label className={`flex items-center justify-between rounded-2xl border px-4 py-3 text-sm ${isDark ? "border-white/10 bg-[#0f141b] text-slate-100" : "border-slate-200 bg-slate-50 text-slate-900"}`}>
                          <span>Allow contact</span>
                          <input
                            type="checkbox"
                            checked={allowContactRequests}
                            onChange={(event) => setAllowContactRequests(event.target.checked)}
                            className="h-4 w-4"
                          />
                        </label>
                      </>
                    )}
                  </>
                ) : (
                  <div className={`rounded-2xl border px-4 py-4 text-sm ${isDark ? "border-cyan-400/20 bg-cyan-400/10 text-cyan-100" : "border-cyan-200 bg-cyan-50 text-cyan-800"}`}>
                    Any signed-in member can open up to 5 general discussion threads per day for advice, genre talk, and broader writing conversations.
                  </div>
                )}

                <input
                  value={headline}
                  onChange={(event) => setHeadline(event.target.value)}
                  onInput={(event) => setHeadline((event.target as HTMLInputElement).value)}
                  placeholder={composerThreadType === "novel" ? "Discussion headline" : "General discussion headline"}
                  className={`w-full rounded-2xl border px-4 py-3 text-sm outline-none transition ${isDark ? "border-white/10 bg-[#0f141b] text-slate-100 placeholder:text-slate-600 focus:border-amber-400" : "border-slate-200 bg-slate-50 text-slate-900 placeholder:text-slate-400 focus:border-orange-500"}`}
                />
                <textarea
                  value={body}
                  onChange={(event) => setBody(event.target.value)}
                  onInput={(event) => setBody((event.target as HTMLTextAreaElement).value)}
                  placeholder={composerThreadType === "novel" ? "What should readers focus on? Hook, pacing, emotional clarity, worldbuilding..." : "What do you want advice or discussion on?"}
                  className={`min-h-[8rem] w-full rounded-2xl border px-4 py-3 text-sm leading-6 outline-none transition ${isDark ? "border-white/10 bg-[#0f141b] text-slate-100 placeholder:text-slate-600 focus:border-amber-400" : "border-slate-200 bg-slate-50 text-slate-900 placeholder:text-slate-400 focus:border-orange-500"}`}
                />
                {composerStatus ? <p className={`text-sm ${isDark ? "text-slate-400" : "text-slate-600"}`}>{composerStatus}</p> : null}
                <button
                  type="button"
                  onClick={() => void createPost()}
                  disabled={creatingPost || (composerThreadType === "novel" && authorForumLoadFailed)}
                  className={`inline-flex h-11 w-full items-center justify-center rounded-full px-5 text-sm font-semibold transition ${isDark ? "bg-amber-400 text-slate-950 hover:bg-amber-300 disabled:bg-amber-400/40" : "bg-[#ff6a1a] text-white hover:bg-[#f05a09] disabled:bg-slate-300"}`}
                >
                  {creatingPost ? "Opening..." : composerThreadType === "novel" ? "Open novel thread" : "Open general thread"}
                </button>
              </div>
            </section>
          ) : (
            <section className={`rounded-3xl border p-4 shadow-sm ${isDark ? "border-white/10 bg-[#121821]" : "border-slate-200 bg-white"}`}>
              <p className={`text-3xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-slate-500"}`}>Browse first</p>
              <h2 className="mt-2 text-lg font-semibold">Read like a real beta reader</h2>
              <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-400" : "text-slate-600"}`}>
                Sign in to comment on active threads, react to other readers, and send a direct beta-read note when an author is open to contact.
              </p>
            </section>
          )}

          <section className={`rounded-3xl border p-4 shadow-sm ${isDark ? "border-white/10 bg-[#121821]" : "border-slate-200 bg-white"}`}>
            <p className={`text-3xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-slate-500"}`}>How this feed works</p>
            <div className="mt-4 space-y-3 text-sm">
              <InfoRow
                isDark={isDark}
                icon={<CompassIcon className={isDark ? "text-amber-300" : "text-orange-600"} />}
                title="Discovery first"
                body="Novel threads surface through ranking windows like top rated, most popular, big cast, and recently updated."
              />
              <InfoRow
                isDark={isDark}
                icon={<ThreadIcon className={isDark ? "text-amber-300" : "text-orange-600"} />}
                title="Split thread system"
                body="Users can open general discussions daily, but each novel can only have one open manuscript thread at a time."
              />
              <InfoRow
                isDark={isDark}
                icon={<InboxIcon className={isDark ? "text-amber-300" : "text-orange-600"} />}
                title="Reader intent matters"
                body="Authors can collect serious beta-read requests without exposing the manuscript itself."
              />
            </div>
          </section>
        </aside>
      </div>
    </div>
  )
}

function ForumFeedCard({ isDark, post }: { isDark: boolean, post: PublicForumPost }) {
  const isNovelThread = (post.thread_type || "novel") === "novel"
  return (
    <article className={`overflow-hidden rounded-3xl border shadow-[0_14px_32px_rgba(15,23,42,0.08)] transition hover:-translate-y-0.5 ${isDark ? "border-white/10 bg-[#121821]" : "border-slate-200 bg-white"}`}>
      <div className="flex">
        <div className={`flex w-[72px] shrink-0 flex-col items-center justify-start gap-2 border-r px-3 py-4 ${isDark ? "border-white/10 bg-[#0f141b]" : "border-slate-200 bg-slate-50/70"}`}>
          <VoteArrowIcon className={isDark ? "text-slate-500" : "text-slate-400"} />
          <span className="text-lg font-semibold">{Math.round(post.discoverability_score)}</span>
          <span className={`text-3xs uppercase tracking-[0.16em] ${isDark ? "text-slate-500" : "text-slate-500"}`}>pulse</span>
        </div>

        <div className="min-w-0 flex-1 px-4 py-4 sm:px-5">
          <div className="flex flex-wrap items-center gap-2 text-xs">
            {post.ranking?.label ? (
              <span className={`rounded-full px-2 py-1 font-semibold ${isDark ? "bg-amber-400/12 text-amber-200" : "bg-orange-100 text-orange-700"}`}>
                #{post.ranking.position ?? "?"} {post.ranking.label}
              </span>
            ) : null}
            <UserBadge isDark={isDark} username={post.author_username || post.author || "writer"} />
            <MetaText isDark={isDark}>{formatRelativeDay(post.created_at)}</MetaText>
            <MetaDivider isDark={isDark} />
            <MetaText isDark={isDark}>{post.author_trust_level}</MetaText>
            <MetaDivider isDark={isDark} />
            <MetaText isDark={isDark}>rep {formatReputationScore(post.author_reputation_score)}</MetaText>
            <span className={`rounded-full px-2 py-1 font-semibold ${isNovelThread ? (isDark ? "bg-amber-400/12 text-amber-200" : "bg-orange-100 text-orange-700") : (isDark ? "bg-cyan-400/12 text-cyan-200" : "bg-cyan-100 text-cyan-700")}`}>
              {isNovelThread ? "novel" : "general"}
            </span>
            {isNovelThread && post.allow_contact_requests ? (
              <span className={`rounded-full px-2 py-1 font-semibold ${isDark ? "bg-emerald-400/12 text-emerald-200" : "bg-emerald-100 text-emerald-700"}`}>open to reader notes</span>
            ) : null}
          </div>

          <div className="mt-3 flex flex-wrap items-center gap-2 text-3xs font-semibold uppercase tracking-[0.18em]">
            <span className={isDark ? "text-amber-300" : "text-orange-700"}>{post.genre || post.work_type || "discussion"}</span>
            {post.title ? (
              <>
                <MetaDivider isDark={isDark} />
                <span className={isDark ? "text-slate-500" : "text-slate-500"}>{post.title}</span>
              </>
            ) : null}
          </div>

          {isNovelThread && post.description ? (
            <p className={`mt-3 text-sm leading-6 ${isDark ? "text-slate-400" : "text-slate-600"}`}>{truncateBody(post.description)}</p>
          ) : null}

          <Link href={`/public/forum/${post.id}` as Route} className="group mt-2 block">
            <h2 className={`text-xl font-semibold leading-tight tracking-tight transition sm:text-[1.35rem] ${isDark ? "group-hover:text-amber-200" : "group-hover:text-orange-700"}`}>{post.headline}</h2>
          </Link>

          <p className={`mt-3 text-sm leading-6 ${isDark ? "text-slate-300" : "text-slate-700"}`}>{truncateBody(post.body)}</p>
          {post.ranking?.supporting_note ? (
            <p className={`mt-3 text-xs leading-6 ${isDark ? "text-slate-400" : "text-slate-500"}`}>{post.ranking.supporting_note}</p>
          ) : null}

          <div className="mt-4 flex flex-wrap items-center gap-2 text-xs">
            <ActionPill isDark={isDark} icon={<CommentBubbleIcon className="h-3.5 w-3.5" />}>
              {post.comment_count} comments
            </ActionPill>
            <ActionPill isDark={isDark} icon={<VoteArrowIcon className="h-3.5 w-3.5" />}>
              {post.like_count} likes
            </ActionPill>
            <ActionPill isDark={isDark} icon={<DownVoteIcon className="h-3.5 w-3.5" />}>
              {post.dislike_count} dislikes
            </ActionPill>
            {isNovelThread ? (
              <ActionPill isDark={isDark} icon={<InboxIcon className="h-3.5 w-3.5" />}>
                {post.interest_count} reader notes
              </ActionPill>
            ) : null}
            {isNovelThread ? (
              <ActionPill isDark={isDark}>
                {post.rating_summary.average_rating?.toFixed(1) ?? "n/a"} avg from {post.rating_summary.rating_count}
              </ActionPill>
            ) : null}
            {isNovelThread && post.desired_beta_reader_count ? (
              <ActionPill isDark={isDark}>target {post.desired_beta_reader_count}</ActionPill>
            ) : null}
          </div>

          <div className="mt-4 flex flex-wrap items-center gap-3">
            <Link
              href={`/public/forum/${post.id}` as Route}
              className={`inline-flex h-10 items-center justify-center rounded-full px-4 text-sm font-semibold transition ${isDark ? "bg-amber-400 text-slate-950 hover:bg-amber-300" : "bg-[#ff6a1a] text-white hover:bg-[#f05a09]"}`}
            >
              Open thread
            </Link>
            {post.author_username ? (
              <Link
                href={`/chats?username=${encodeURIComponent(post.author_username)}` as Route}
                className={`inline-flex h-10 items-center justify-center rounded-full px-4 text-sm font-semibold transition ${isDark ? "border border-white/10 bg-white/[0.04] text-slate-100 hover:bg-white/[0.08]" : "border border-slate-200 bg-white text-slate-900 hover:bg-slate-50"}`}
              >
                Message @{post.author_username}
              </Link>
            ) : null}
            <MetaText isDark={isDark}>{isNovelThread ? "Rank updates use ratings, comments, reader intent, craft signals, and update cadence." : "General threads are for broader craft and community discussion."}</MetaText>
          </div>
        </div>
      </div>
    </article>
  )
}

function truncateBody(body: string): string {
  return body.length > 260 ? `${body.slice(0, 257).trimEnd()}...` : body
}

function formatRelativeDay(value: string): string {
  const timestamp = new Date(value).getTime()
  const deltaMinutes = Math.max(0, Math.floor((Date.now() - timestamp) / (1000 * 60)))
  if (deltaMinutes < 60) return `${Math.max(deltaMinutes, 1)}m ago`
  const deltaHours = Math.floor(deltaMinutes / 60)
  if (deltaHours < 24) return `${deltaHours}h ago`
  const deltaDays = Math.floor(deltaHours / 24)
  if (deltaDays === 1) return "1d ago"
  return `${deltaDays}d ago`
}

function StatCard({ isDark, value, label }: { isDark: boolean, value: string, label: string }) {
  return (
    <div className={`rounded-2xl px-3 py-3 ${isDark ? "bg-[#151b22]" : "bg-white ring-1 ring-slate-200"}`}>
      <p className="text-lg font-semibold">{value}</p>
      <p className={`mt-1 text-3xs uppercase tracking-[0.16em] ${isDark ? "text-slate-500" : "text-slate-500"}`}>{label}</p>
    </div>
  )
}

function ShellChip({ children, isDark, active = false }: { children: React.ReactNode, isDark: boolean, active?: boolean }) {
  const activeClass = isDark
    ? "border-amber-400/30 bg-amber-400/10 text-amber-100"
    : "border-orange-200 bg-orange-50 text-orange-700"
  const idleClass = isDark
    ? "border-white/10 bg-white/[0.04] text-slate-300"
    : "border-slate-200 bg-white text-slate-600"

  return (
    <span className={`inline-flex items-center rounded-full border px-3 py-2 ${active ? activeClass : idleClass}`}>
      {children}
    </span>
  )
}

function UserBadge({ isDark, username }: { isDark: boolean, username: string }) {
  return (
    <span className={`inline-flex items-center gap-2 rounded-full px-2.5 py-1 font-medium ${isDark ? "bg-white/[0.05] text-slate-100" : "bg-slate-100 text-slate-900"}`}>
      <span className={`flex h-5 w-5 items-center justify-center rounded-full text-3xs font-semibold ${isDark ? "bg-[#202834] text-slate-100" : "bg-white text-slate-700 ring-1 ring-slate-200"}`}>
        {username.slice(0, 1).toUpperCase()}
      </span>
      @{username}
    </span>
  )
}

function ActionPill({ children, icon, isDark }: { children: React.ReactNode, icon?: React.ReactNode, isDark: boolean }) {
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 ${isDark ? "bg-white/[0.04] text-slate-300" : "bg-slate-100 text-slate-700"}`}>
      {icon}
      {children}
    </span>
  )
}

function MetaText({ children, isDark }: { children: React.ReactNode, isDark: boolean }) {
  return <span className={isDark ? "text-slate-500" : "text-slate-500"}>{children}</span>
}

function MetaDivider({ isDark }: { isDark: boolean }) {
  return <span className={`h-1 w-1 rounded-full ${isDark ? "bg-slate-600" : "bg-slate-400"}`} aria-hidden="true" />
}

function InfoRow({
  isDark,
  icon,
  title,
  body,
}: {
  isDark: boolean
  icon: React.ReactNode
  title: string
  body: string
}) {
  return (
    <div className="flex items-start gap-3">
      <span className="mt-0.5">{icon}</span>
      <div>
        <p className="font-medium">{title}</p>
        <p className={isDark ? "text-slate-400" : "text-slate-600"}>{body}</p>
      </div>
    </div>
  )
}

function SearchIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 20 20" fill="none" className={`h-4 w-4 ${className || ""}`} aria-hidden="true">
      <circle cx="9" cy="9" r="5.75" stroke="currentColor" strokeWidth="1.5" />
      <path d="M13.5 13.5 17 17" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  )
}

function VoteArrowIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 20 20" fill="currentColor" className={`h-5 w-5 ${className || ""}`} aria-hidden="true">
      <path d="M10 3.5 16 10h-3.75v6.5h-4.5V10H4z" />
    </svg>
  )
}

function DownVoteIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 20 20" fill="currentColor" className={`${className || "h-5 w-5"} rotate-180`} aria-hidden="true">
      <path d="M10 3.5 16 10h-3.75v6.5h-4.5V10H4z" />
    </svg>
  )
}

function CommentBubbleIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 20 20" fill="none" className={`${className || "h-4 w-4"}`} aria-hidden="true">
      <path d="M4 4.75h12a1.25 1.25 0 0 1 1.25 1.25v7A1.25 1.25 0 0 1 16 14.25H9.5l-3.75 2.5V14.25H4A1.25 1.25 0 0 1 2.75 13V6A1.25 1.25 0 0 1 4 4.75Z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
    </svg>
  )
}

function CompassIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 20 20" fill="none" className={`h-4 w-4 ${className || ""}`} aria-hidden="true">
      <circle cx="10" cy="10" r="7" stroke="currentColor" strokeWidth="1.5" />
      <path d="m12.75 7.25-1.94 5.56-5.56 1.94 1.94-5.56 5.56-1.94Z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
    </svg>
  )
}

function ThreadIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 20 20" fill="none" className={`h-4 w-4 ${className || ""}`} aria-hidden="true">
      <path d="M4.5 5.5h11M4.5 10h8M4.5 14.5h6" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  )
}

function InboxIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 20 20" fill="none" className={`${className || "h-4 w-4"}`} aria-hidden="true">
      <path d="M4 6.5h12l1 6.5h-4.5L10 15.5 7.5 13H3z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
      <path d="M4.5 6.5 6 4.5h8l1.5 2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}
