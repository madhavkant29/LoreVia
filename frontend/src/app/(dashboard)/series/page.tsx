"use client"

import { useEffect, useMemo, useState } from "react"
import Link from "next/link"
import type { Route } from "next"

import { booksApi } from "@/lib/api/books"
import { intelligenceApi } from "@/lib/api/intelligence"
import { isPaidTier } from "@/lib/billing/plans"
import { WorkspaceEmptyState, WorkspaceHeader, WorkspacePage } from "@/components/ui/Workspace"
import { worldBuildingApi } from "@/lib/api/worldBuilding"
import { useAuthStore } from "@/lib/stores/authStore"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import { getBookHref } from "@/lib/utils/bookRoutes"
import { renderMarkdownHtml } from "@/lib/utils/richText"
import type { Book, BookSeries, SeriesBible } from "@/types/book"
import type { AdvisorMessage, AdvisorResponse, SeriesContinuityResponse } from "@/types/intelligence"

function storyUnitName(workType?: Book["work_type"], plural = false) {
  if (workType === "screenplay") return plural ? "scenes" : "scene"
  return plural ? "chapters" : "chapter"
}

function collectionUnitName(hasScreenplayEpisodes: boolean, plural = false) {
  if (hasScreenplayEpisodes) return plural ? "episodes" : "episode"
  return plural ? "volumes" : "volume"
}

function collectionUnitLabel(hasScreenplayEpisodes: boolean, order?: number | null) {
  if (!order) return ""
  return hasScreenplayEpisodes ? `Ep ${order} · ` : `Vol ${order} · `
}

function seriesSurfaceClass(isDark: boolean, tone: "default" | "subtle" = "default") {
  if (tone === "subtle") {
    return isDark ? "border-slate-700/70 bg-[#121921]" : "border-slate-200 bg-[#fbfcfd]"
  }
  return isDark ? "border-slate-700/70 bg-[#11171d]" : "border-slate-200 bg-white"
}

function seriesPrimaryButtonClass(isDark: boolean) {
  return isDark
    ? "bg-[#165c52] text-white hover:bg-[#1a695e]"
    : "bg-[#1f615d] text-white hover:bg-[#174c49]"
}

function seriesSecondaryButtonClass(isDark: boolean) {
  return isDark
    ? "border-white/[0.08] bg-[#1f2427] text-[#ebe7df] hover:bg-[#252b2f]"
    : "border-stone-200 bg-white text-stone-800 hover:bg-stone-50"
}

export default function SeriesPage() {
  const user = useAuthStore((state) => state.user)
  const { theme } = usePreferencesStore()
  const isDark = theme === "dark"
  const [series, setSeries] = useState<BookSeries[]>([])
  const [books, setBooks] = useState<Book[]>([])
  const [busyKey, setBusyKey] = useState<string | null>(null)
  const [name, setName] = useState("")
  const [description, setDescription] = useState("")
  const [seriesBibleById, setSeriesBibleById] = useState<Record<string, SeriesBible>>({})
  const [openSeriesBibleId, setOpenSeriesBibleId] = useState<string | null>(null)
  const [seriesBibleLoadingId, setSeriesBibleLoadingId] = useState<string | null>(null)
  const [askSeriesId, setAskSeriesId] = useState<string | null>(null)
  const [askQuery, setAskQuery] = useState("")
  const [askMessages, setAskMessages] = useState<AdvisorMessage[]>([])
  const [askResponse, setAskResponse] = useState<AdvisorResponse | null>(null)
  const [askLoading, setAskLoading] = useState(false)
  const [seriesModalTab, setSeriesModalTab] = useState<"ask" | "continuity">("ask")
  const [continuityText, setContinuityText] = useState("")
  const [continuityChapterNum, setContinuityChapterNum] = useState("")
  const [continuityBookId, setContinuityBookId] = useState("")
  const [continuityResult, setContinuityResult] = useState<SeriesContinuityResponse | null>(null)
  const [continuityLoading, setContinuityLoading] = useState(false)
  const [continuityStatus, setContinuityStatus] = useState<string | null>(null)
  const [worldAnalysisBySeriesId, setWorldAnalysisBySeriesId] = useState<Record<string, any>>({})
  const [worldAnalysisLoadingId, setWorldAnalysisLoadingId] = useState<string | null>(null)

  async function load() {
    const [seriesResponse, bookRows] = await Promise.all([booksApi.listSeries(), booksApi.list()])
    setSeries(seriesResponse.items)
    setBooks(bookRows)
  }

  useEffect(() => {
    if (isPaidTier(user?.tier)) {
      load().catch(() => {})
    }
  }, [user?.tier])

  const unassignedBooks = useMemo(
    () => books.filter((book) => !book.primary_series_id && !book.series_name),
    [books]
  )
  const pageBackground = isDark ? "bg-[#0d1318] text-slate-100" : "bg-[#f4f5f7] text-stone-950"
  const mutedText = isDark ? "text-slate-400" : "text-stone-600"
  const subMutedText = isDark ? "text-slate-500" : "text-stone-500"
  const surfaceClass = seriesSurfaceClass(isDark)
  const subtleSurfaceClass = seriesSurfaceClass(isDark, "subtle")
  const controlClass = isDark ? "border-slate-700/70 bg-[#121921] text-white placeholder:text-slate-500" : "border-stone-200 bg-white text-stone-900 placeholder:text-stone-400"
  const primaryButtonClass = seriesPrimaryButtonClass(isDark)
  const secondaryButtonClass = seriesSecondaryButtonClass(isDark)

  async function createSeries() {
    if (!name.trim()) return
    setBusyKey("create")
    try {
      await booksApi.createSeries({ name: name.trim(), description: description.trim() || null })
      setName("")
      setDescription("")
      await load()
    } finally {
      setBusyKey(null)
    }
  }

  async function toggleSeriesBible(seriesId: string) {
    if (openSeriesBibleId === seriesId) {
      setOpenSeriesBibleId(null)
      return
    }
    setOpenSeriesBibleId(seriesId)
    if (seriesBibleById[seriesId]) return
    setSeriesBibleLoadingId(seriesId)
    try {
      const payload = await booksApi.getSeriesBible(seriesId)
      setSeriesBibleById((current) => ({ ...current, [seriesId]: payload }))
    } finally {
      setSeriesBibleLoadingId(null)
    }
  }

  async function handleSeriesAsk(seriesId: string) {
    if (!askQuery.trim()) return
    setAskLoading(true)
    const newMessages: AdvisorMessage[] = [...askMessages, { role: "user", content: askQuery }]
    setAskMessages(newMessages)
    setAskQuery("")
    try {
      const response = await intelligenceApi.seriesAdvisorMessageStream(seriesId, newMessages, {
        onDelta: (content) => {
          if (!content) return
          setAskMessages((prev) => {
            const last = prev[prev.length - 1]
            if (last?.role === "assistant") {
              return [...prev.slice(0, -1), { ...last, content: `${last.content}${content}` }]
            }
            return [...prev, { role: "assistant", content }]
          })
        },
      })
      setAskMessages((prev) => {
        const last = prev[prev.length - 1]
        if (last?.role === "assistant") {
          return [...prev.slice(0, -1), { role: "assistant", content: response.reply }]
        }
        return [...prev, { role: "assistant", content: response.reply }]
      })
      setAskResponse(response)
    } catch {
      setAskResponse({ reply: "Failed to get a response. Please try again.", intent: "general", response_type: "standard", retrieved_passages: [], cached: false })
    } finally {
      setAskLoading(false)
    }
  }

  async function handleSeriesContinuityCheck(seriesId: string) {
    if (!continuityText.trim() || !continuityBookId) return
    setContinuityLoading(true)
    setContinuityStatus(null)
    setContinuityResult(null)
    try {
      const result = await intelligenceApi.seriesContinuityCheckStream(
        seriesId,
        continuityBookId,
        continuityText,
        continuityChapterNum ? parseInt(continuityChapterNum) : undefined,
        { onStage: setContinuityStatus },
      )
      setContinuityResult(result as typeof continuityResult)
    } catch {
      setContinuityResult(null)
    } finally {
      setContinuityLoading(false)
      setContinuityStatus(null)
    }
  }

  async function loadSeriesWorldAnalysis(seriesId: string) {
    setWorldAnalysisLoadingId(seriesId)
    try {
      const payload = await worldBuildingApi.getSeriesAnalysis(seriesId)
      setWorldAnalysisBySeriesId((current) => ({ ...current, [seriesId]: payload }))
    } finally {
      setWorldAnalysisLoadingId(null)
    }
  }

  if (!user || !isPaidTier(user.tier)) {
    return (
      <WorkspacePage className={pageBackground}>
        <div className="mx-auto w-full max-w-[1220px] px-4 py-8 sm:px-6 lg:px-8">
          <section className={`rounded-lg border-2 p-6 ${surfaceClass}`}>
            <h1 className="text-[2rem] font-semibold tracking-[-0.03em]">Series workspace</h1>
            <p className={`mt-3 max-w-2xl text-sm leading-7 ${mutedText}`}>
              Series mode is reserved for paid plans. It is built for authors carrying continuity across multiple books without losing where each story stands.
            </p>
          </section>
        </div>
      </WorkspacePage>
    )
  }

  return (
    <WorkspacePage className={pageBackground}>
      <div className="mx-auto w-full max-w-[1220px] px-4 py-8 sm:px-6 lg:px-8">
        <div className="space-y-5 pb-12">
      <section className={`rounded-lg border-2 ${surfaceClass}`}>
        <div className="px-6 py-8 sm:px-8 sm:py-10 lg:px-12 lg:py-12">
          <WorkspaceHeader
            eyebrow="Series workspace"
            title="Track sagas"
            description="Create named series, slot books into the right order, and manage your reading continuity across the whole run."
          />
        </div>
      </section>

      <section className={`rounded-md border-2 p-5 ${surfaceClass}`}>
        <div className="grid gap-3 md:grid-cols-[1.2fr_1.5fr_auto]">
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Create a new series"
            className={`rounded-md border-2 px-4 py-3 text-sm outline-none ${controlClass}`}
          />
          <input
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Short note about this series"
            className={`rounded-md border-2 px-4 py-3 text-sm outline-none ${controlClass}`}
          />
          <button
            onClick={createSeries}
            disabled={busyKey === "create"}
            className={`rounded-md px-5 py-3 text-sm font-semibold transition disabled:opacity-60 ${primaryButtonClass}`}
          >
            {busyKey === "create" ? "Creating..." : "Create series"}
          </button>
        </div>
      </section>

      {series.length === 0 ? (
        <section className={`rounded-md border-2 p-6 ${surfaceClass}`}>
          <WorkspaceEmptyState title="No series yet" body="Create one above to start organizing your books." />
        </section>
      ) : (
        <div className="space-y-4">
          {series.map((lane) => {
            const hasScreenplayEpisodes = lane.books.some((book) => book.work_type === "screenplay")
            const collectionPlural = collectionUnitName(hasScreenplayEpisodes, true)
            const collectionSingular = collectionUnitName(hasScreenplayEpisodes, false)
            const seriesBible = seriesBibleById[lane.id]
            const bibleOpen = openSeriesBibleId === lane.id
            return (
              <section key={lane.id} className={`rounded-md border-2 p-6 transition ${surfaceClass}`}>
              <div className="flex flex-wrap items-center justify-between gap-4">
                <div>
                  <h2 className="text-[1.6rem] font-semibold tracking-[-0.03em]">{lane.name}</h2>
                  {lane.description ? <p className={`mt-1 text-sm leading-6 ${mutedText}`}>{lane.description}</p> : null}
                </div>
                <div className="flex flex-wrap items-center gap-3">
                  <span className={`rounded-full px-3 py-1.5 text-xs font-medium ${isDark ? "bg-[#172029] text-slate-300" : "bg-[#edf6f4] text-[#1f615d]"}`}>
                    {lane.books.length} {lane.books.length === 1 ? collectionSingular : collectionPlural}
                  </span>
                  {lane.books.length > 0 && (
                    <button
                      type="button"
                      onClick={() => {
                        setAskSeriesId(lane.id)
                        setSeriesModalTab("ask")
                        setAskMessages([])
                        setAskResponse(null)
                        setAskQuery("")
                        setContinuityResult(null)
                      }}
                      className={`inline-flex items-center gap-1.5 rounded-sm px-4 py-2 text-xs font-semibold transition ${primaryButtonClass}`}
                    >
                      <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                      </svg>
                      Ask
                    </button>
                  )}
                  {hasScreenplayEpisodes ? (
                    <button
                      onClick={() => void toggleSeriesBible(lane.id)}
                      className={`inline-flex items-center gap-1.5 rounded-sm border px-4 py-2 text-xs font-semibold transition ${secondaryButtonClass}`}
                    >
                      {seriesBibleLoadingId === lane.id ? "Opening..." : bibleOpen ? "Hide Series Bible" : "View Series Bible"}
                    </button>
                  ) : null}
                  <button
                    type="button"
                    onClick={() => void loadSeriesWorldAnalysis(lane.id)}
                    className={`inline-flex items-center gap-1.5 rounded-sm border px-4 py-2 text-xs font-semibold transition ${secondaryButtonClass}`}
                  >
                    {worldAnalysisLoadingId === lane.id ? "Analyzing..." : "World analysis"}
                  </button>
                </div>
              </div>

              {worldAnalysisBySeriesId[lane.id] ? (
                <div className={`mt-5 rounded-md border-2 p-5 ${subtleSurfaceClass}`}>
                  <p className={`text-3xs font-semibold uppercase tracking-[0.22em] ${subMutedText}`}>Series world analysis</p>
                  <div className="mt-3 grid gap-3 md:grid-cols-3">
                    <SeriesBibleStat label="Books" value={String(worldAnalysisBySeriesId[lane.id].book_count ?? lane.books.length)} isDark={isDark} />
                    <SeriesBibleStat label="Analyses" value={String(worldAnalysisBySeriesId[lane.id].analysis_count ?? 0)} isDark={isDark} />
                    <SeriesBibleStat label="Context blocks" value={String((worldAnalysisBySeriesId[lane.id].world_context ?? []).length ?? 0)} isDark={isDark} />
                  </div>
                  <div className="mt-3 grid gap-2 md:grid-cols-2">
                    {(worldAnalysisBySeriesId[lane.id].world_context ?? []).slice(0, 6).map((item: any, index: number) => (
                      <div key={`${lane.id}-world-${index}`} className={`rounded-sm border-2 px-3 py-2 text-sm ${subtleSurfaceClass} ${isDark ? "text-slate-200" : "text-stone-700"}`}>
                        {typeof item === "string" ? item : item.name || item.title || item.description || JSON.stringify(item)}
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}

              {bibleOpen ? (
                <div className={`mt-5 rounded-md border-2 p-5 ${subtleSurfaceClass}`}>
                  {seriesBible ? (
                    <div className="space-y-4">
                      <div className="flex flex-wrap items-center gap-3">
                        <span className={`rounded-full px-3 py-1.5 text-3xs font-semibold uppercase tracking-[0.2em] ${isDark ? "bg-[#172029] text-[#7fd2bf]" : "bg-[#edf6f4] text-[#1f615d]"}`}>Series Bible</span>
                        <span className={`text-sm ${mutedText}`}>{seriesBible.episode_count} episode{seriesBible.episode_count === 1 ? "" : "s"} tracked</span>
                      </div>

                      <div className="grid gap-3 md:grid-cols-4">
                        <SeriesBibleStat label="Recurring characters" value={String(seriesBible.recurring_characters.length)} isDark={isDark} />
                        <SeriesBibleStat label="Recurring relationships" value={String(seriesBible.recurring_relationships.length)} isDark={isDark} />
                        <SeriesBibleStat label="Open plot threads" value={String(seriesBible.unresolved_plot_threads.length)} isDark={isDark} />
                        <SeriesBibleStat label="Continuity risks" value={String(seriesBible.continuity_risks.length)} isDark={isDark} />
                      </div>

                      <div className="grid gap-4 lg:grid-cols-2">
                        <SeriesBibleList
                          title="Episodes"
                          items={seriesBible.episodes.map((episode) => `${episode.episode_number ? `Ep ${episode.episode_number}` : "Episode"} - ${episode.title} - ${episode.total_scenes} scenes - ${episode.total_dialogue_lines} dialogue lines`)}
                          emptyLabel="No screenplay episodes have been parsed yet."
                          isDark={isDark}
                        />
                        <SeriesBibleList
                          title="Recurring characters"
                          items={seriesBible.recurring_characters.slice(0, 6).map((character) => `${character.name} - ${character.episode_count} episodes - ${character.total_mentions} mentions`)}
                          emptyLabel="No recurring characters detected across episodes yet."
                          isDark={isDark}
                        />
                        <SeriesBibleList
                          title="Open plot threads"
                          items={seriesBible.unresolved_plot_threads.slice(0, 6).map((thread) => `${thread.title} - ${thread.status} - ${thread.episode_count} episodes`)}
                          emptyLabel="No unresolved cross-episode plot threads yet."
                          isDark={isDark}
                        />
                        <SeriesBibleList
                          title="Continuity risks"
                          items={seriesBible.continuity_risks.slice(0, 6)}
                          emptyLabel="No obvious cross-episode continuity risks surfaced yet."
                          isDark={isDark}
                        />
                      </div>
                    </div>
                  ) : (
                    <p className={`text-sm ${mutedText}`}>Loading the aggregated screenplay workspace...</p>
                  )}
                </div>
              ) : null}

              {lane.books.length > 0 ? (
                <div className="mt-5 grid gap-4 lg:grid-cols-2">
                  {lane.books.map((book) => (
                    <SeriesBookCard
                      key={book.id}
                      laneId={lane.id}
                      book={book}
                      isDark={isDark}
                      busy={busyKey === `${lane.id}:${book.id}`}
                      onRefresh={load}
                      onBusy={setBusyKey}
                    />
                  ))}
                </div>
              ) : (
                <div className={`mt-5 rounded-md border border-dashed p-5 text-sm ${isDark ? "border-white/[0.08] text-slate-400" : "border-stone-300 text-stone-500"}`}>
                  No books in this series yet.
                </div>
              )}

              <div className="mt-5">
                <p className={`mb-3 text-xs font-semibold uppercase tracking-[0.24em] ${subMutedText}`}>Add a book</p>
                <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                  {books
                    .filter((book) => !lane.books.find((item) => item.id === book.id))
                    .map((book) => (
                      <AddBookCard
                        key={book.id}
                        laneId={lane.id}
                        book={book}
                        isDark={isDark}
                        onRefresh={load}
                        onBusy={setBusyKey}
                        busy={busyKey === `add:${lane.id}:${book.id}`}
                      />
                    ))}
                </div>
              </div>
              </section>
            )
          })}
        </div>
      )}

      {unassignedBooks.length > 0 ? (
        <section className={`rounded-md border-2 p-6 ${surfaceClass}`}>
          <h2 className="text-[1.45rem] font-semibold tracking-[-0.03em]">Unassigned books</h2>
          <p className={`mt-1 text-sm leading-6 ${mutedText}`}>These books are not connected to any series yet</p>
          <div className="mt-4 flex flex-wrap gap-2">
            {unassignedBooks.map((book) => (
              <span key={book.id} className={`inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm font-medium ${isDark ? "bg-[#172029] text-slate-200" : "bg-stone-100 text-stone-700"}`}>
                {book.title}
              </span>
            ))}
          </div>
        </section>
      ) : null}

      {/* Series Ask Modal */}
      {askSeriesId && (() => {
        const activeSeries = series.find(s => s.id === askSeriesId)
        const seriesBooks = activeSeries?.books ?? []
        const modalHasScreenplayEpisodes = seriesBooks.some((book) => book.work_type === "screenplay")
        const modalCollectionPlural = collectionUnitName(modalHasScreenplayEpisodes, true)
        const modalCollectionSingular = collectionUnitName(modalHasScreenplayEpisodes, false)
        return (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
            <div className={`w-full max-w-2xl rounded-lg border-2 ${surfaceClass}`}>

              {/* Modal header */}
              <div className={`flex items-center justify-between border-b px-6 py-4 ${isDark ? "border-slate-700/70" : "border-stone-200"}`}>
                <div>
                  <p className={`text-3xs font-semibold uppercase tracking-[0.26em] ${subMutedText}`}>Series intelligence</p>
                  <h3 className="mt-0.5 text-lg font-semibold">{activeSeries?.name}</h3>
                </div>
                <button
                  onClick={() => setAskSeriesId(null)}
                  className={`rounded-sm border px-3 py-1.5 text-xs font-medium ${secondaryButtonClass}`}
                >
                  Close
                </button>
              </div>

              {/* Tab bar */}
              <div className={`flex gap-1 border-b px-6 py-3 ${isDark ? "border-slate-700/70" : "border-stone-200"}`}>
                {(["ask", "continuity"] as const).map(tab => (
                  <button
                    key={tab}
                    onClick={() => setSeriesModalTab(tab)}
                    className={`rounded-sm px-4 py-1.5 text-sm font-medium transition ${seriesModalTab === tab ? primaryButtonClass : isDark ? "text-slate-400 hover:text-slate-200" : "text-stone-500 hover:text-stone-900"}`}
                  >
                    {tab === "ask" ? "Ask the series" : "Series continuity check"}
                  </button>
                ))}
              </div>

              <div className="max-h-[65vh] overflow-y-auto p-6 space-y-4">

                {/* Ask tab */}
                {seriesModalTab === "ask" && (
                  <>
                    <p className={`text-xs leading-5 ${isDark ? "text-slate-400" : "text-stone-500"}`}>
                      Ask anything about characters, continuity, or plot threads across all books in this series. Responses are grounded in aggregated story context.
                    </p>

                    {/* Conversation */}
                    {askMessages.length > 0 && (
                      <div className={`max-h-64 space-y-3 overflow-y-auto rounded-md border-2 p-4 ${subtleSurfaceClass}`}>
                        {askMessages.map((msg, i) => (
                          <div key={i} className={`text-sm leading-6 ${msg.role === "user" ? isDark ? "text-slate-300" : "text-stone-700" : isDark ? "text-white" : "text-stone-900"}`}>
                            <span className={`mr-2 text-3xs font-bold uppercase tracking-[0.2em] ${msg.role === "user" ? isDark ? "text-slate-500" : "text-stone-400" : isDark ? "text-amber-300" : "text-amber-600"}`}>
                              {msg.role === "user" ? "You" : "Series AI"}
                            </span>
                            {msg.role === "assistant" ? (
                              <div className="prose prose-invert max-w-none">
                                <div dangerouslySetInnerHTML={{ __html: renderMarkdownHtml(msg.content) }} />
                              </div>
                            ) : (
                              msg.content
                            )}
                          </div>
                        ))}
                        {askLoading && <p className={`text-xs ${isDark ? "text-slate-500" : "text-stone-400"}`}>Analyzing series...</p>}
                      </div>
                    )}

                    {askResponse?.cached && (
                      <p className={`text-3xs ${isDark ? "text-amber-400" : "text-amber-600"}`}>Cached response</p>
                    )}

                    <div className="flex gap-2">
                      <input
                        value={askQuery}
                        onChange={e => setAskQuery(e.target.value)}
                        placeholder="Ask about continuity, characters, or plot across all books..."
                        className={`flex-1 rounded-md border-2 px-4 py-2.5 text-sm outline-none ${controlClass}`}
                        onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSeriesAsk(askSeriesId) } }}
                      />
                      <button
                        onClick={() => handleSeriesAsk(askSeriesId)}
                        disabled={askLoading || !askQuery.trim()}
                        className={`rounded-md px-5 py-2.5 text-sm font-semibold disabled:opacity-50 ${primaryButtonClass}`}
                      >
                        {askLoading ? "..." : "Ask"}
                      </button>
                    </div>
                  </>
                )}

                {/* Series continuity check tab */}
                {seriesModalTab === "continuity" && (
                  <>
                    <p className={`text-xs leading-5 ${isDark ? "text-slate-400" : "text-stone-500"}`}>
                      Paste a passage from your new {modalCollectionSingular} and check it against the earlier {modalCollectionPlural} in this series for character, plot, and world-building consistency.
                    </p>

                    <div className="grid gap-3 sm:grid-cols-2">
                      <div>
                        <label className={`mb-1 block text-3xs font-semibold uppercase tracking-[0.2em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>New book</label>
                        <select
                          value={continuityBookId}
                          onChange={e => setContinuityBookId(e.target.value)}
                          className={`w-full rounded-md border-2 px-3 py-2 text-sm outline-none ${controlClass}`}
                        >
                          <option value="">Select book...</option>
                          {seriesBooks.map(b => <option key={b.id} value={b.id}>{b.title}</option>)}
                        </select>
                      </div>
                      <div>
                        <label className={`mb-1 block text-3xs font-semibold uppercase tracking-[0.2em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>{modalHasScreenplayEpisodes ? "Scene (optional)" : "Chapter (optional)"}</label>
                        <input
                          type="number" min={1}
                          value={continuityChapterNum}
                          onChange={e => setContinuityChapterNum(e.target.value)}
                          placeholder={modalHasScreenplayEpisodes ? "e.g. 12" : "e.g. 5"}
                          className={`w-full rounded-md border-2 px-3 py-2 text-sm outline-none ${controlClass}`}
                        />
                      </div>
                    </div>

                    <textarea
                      rows={6}
                      value={continuityText}
                      onChange={e => setContinuityText(e.target.value)}
                      placeholder="Paste the passage you want to cross-check against earlier books..."
                      className={`w-full resize-none rounded-md border-2 px-4 py-3 text-sm leading-7 outline-none ${controlClass}`}
                    />

                    <button
                      onClick={() => handleSeriesContinuityCheck(askSeriesId)}
                      disabled={continuityLoading || !continuityText.trim() || !continuityBookId}
                      className={`w-full rounded-md px-5 py-3 text-sm font-semibold disabled:opacity-50 ${primaryButtonClass}`}
                    >
                      {continuityLoading ? "Checking across series..." : "Run series continuity check"}
                    </button>

                    {continuityLoading && continuityStatus ? (
                      <p className={`text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>{continuityStatus}</p>
                    ) : null}

                    {continuityResult && (
                      <div className="space-y-4">
                        {continuityResult.cached && (
                          <p className={`text-3xs ${isDark ? "text-amber-400" : "text-amber-600"}`}>Cached response</p>
                        )}

                        {/* Verdict */}
                        <div className={`rounded-md border-2 px-4 py-3 ${subtleSurfaceClass}`}>
                          <p className={`mb-1 text-3xs font-bold uppercase tracking-[0.24em] ${subMutedText}`}>Overall verdict</p>
                          <p className="text-sm font-medium leading-6">{continuityResult.review.overall_verdict}</p>
                        </div>

                        {/* Thematic fit */}
                        <div className={`rounded-md border px-4 py-3 ${
                          continuityResult.review.thematic_fit.score === "strong" ? isDark ? "border-teal-500/25 bg-teal-500/10" : "border-teal-200 bg-teal-50"
                          : continuityResult.review.thematic_fit.score === "weak" ? isDark ? "border-red-500/25 bg-red-500/10" : "border-red-200 bg-red-50"
                          : isDark ? "border-amber-500/25 bg-amber-500/10" : "border-amber-100 bg-amber-50"
                        }`}>
                          <div className="flex items-center gap-2 mb-1">
                            <p className={`text-3xs font-bold uppercase tracking-[0.24em] ${isDark ? "text-slate-400" : "text-stone-400"}`}>Thematic fit</p>
                            <span className={`rounded-full px-2 py-0.5 text-3xs font-bold uppercase ${
                              continuityResult.review.thematic_fit.score === "strong" ? isDark ? "bg-teal-500/20 text-teal-300" : "bg-teal-100 text-teal-700"
                              : continuityResult.review.thematic_fit.score === "weak" ? isDark ? "bg-red-500/20 text-red-300" : "bg-red-100 text-red-700"
                              : isDark ? "bg-amber-500/20 text-amber-300" : "bg-amber-100 text-amber-700"
                            }`}>{continuityResult.review.thematic_fit.score}</span>
                          </div>
                          <p className={`text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-600"}`}>{continuityResult.review.thematic_fit.notes}</p>
                        </div>

                        {/* Continuity issues */}
                        {continuityResult.review.continuity_issues.length > 0 && (
                          <div className="space-y-2">
                            <p className={`text-3xs font-bold uppercase tracking-[0.24em] ${isDark ? "text-amber-300" : "text-amber-700"}`}>Issues ({continuityResult.review.continuity_issues.length})</p>
                            {continuityResult.review.continuity_issues.map((issue, i) => (
                              <div key={i} className={`rounded-md border px-4 py-3 text-sm ${
                                issue.severity === "critical" ? isDark ? "border-red-500/30 bg-red-500/10" : "border-red-200 bg-red-50"
                                : isDark ? "border-amber-500/25 bg-amber-500/8" : "border-amber-200 bg-amber-50"
                              }`}>
                                <p className={`font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{issue.title}</p>
                                <p className={`mt-1 text-xs leading-5 ${isDark ? "text-slate-300" : "text-stone-600"}`}>{issue.description}</p>
                                {issue.suggestion && <p className={`mt-1.5 text-xs font-medium ${isDark ? "text-indigo-300" : "text-violet-700"}`}>Suggestion: {issue.suggestion}</p>}
                              </div>
                            ))}
                          </div>
                        )}

                        {/* Cross-book opportunities */}
                        {continuityResult.review.cross_book_opportunities.length > 0 && (
                          <div className="space-y-2">
                            <p className={`text-3xs font-bold uppercase tracking-[0.24em] ${isDark ? "text-teal-300" : "text-teal-700"}`}>Opportunities</p>
                            {continuityResult.review.cross_book_opportunities.map((opp, i) => (
                              <div key={i} className={`rounded-md border px-4 py-3 text-sm ${isDark ? "border-teal-500/20 bg-teal-500/8" : "border-teal-200 bg-teal-50"}`}>
                                <p className={`font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{opp.title}</p>
                                <p className={`mt-1 text-xs leading-5 ${isDark ? "text-slate-300" : "text-stone-600"}`}>{opp.description}</p>
                              </div>
                            ))}
                          </div>
                        )}

                        {/* Retrieved passages */}
                        {continuityResult.retrieved_passages.length > 0 && (
                          <div>
                            <p className={`text-3xs font-bold uppercase tracking-[0.24em] mb-2 ${isDark ? "text-slate-500" : "text-stone-400"}`}>Cross-referenced from earlier {modalCollectionPlural}</p>
                            <div className="grid gap-2 sm:grid-cols-2">
                              {continuityResult.retrieved_passages.map((p, i) => (
                                <div key={i} className={`rounded-sm border px-3 py-2 text-xs ${isDark ? "border-white/10 bg-white/[0.03]" : "border-stone-200 bg-stone-50"}`}>
                                  <p className={`font-semibold mb-1 ${isDark ? "text-indigo-300" : "text-violet-600"}`}>{p.book_title} · {modalHasScreenplayEpisodes ? "Sc." : "Ch."} {p.chapter_num}</p>
                                  <p className={`leading-5 ${isDark ? "text-slate-400" : "text-stone-600"}`}>{p.excerpt}</p>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {continuityResult.review.continuity_issues.length === 0 && (
                          <div className={`rounded-md border p-4 text-center ${isDark ? "border-teal-500/20 bg-teal-500/8" : "border-teal-200 bg-teal-50"}`}>
                            <p className={`text-sm font-semibold ${isDark ? "text-teal-200" : "text-teal-800"}`}>No cross-series continuity issues found</p>
                          </div>
                        )}
                      </div>
                    )}
                  </>
                )}
              </div>
            </div>
          </div>
        )
      })()}
        </div>
      </div>
    </WorkspacePage>
  )
}

function SeriesBibleStat({
  label,
  value,
  isDark,
}: {
  label: string
  value: string
  isDark: boolean
}) {
  return (
    <div className={`rounded-md border-2 px-4 py-3 ${seriesSurfaceClass(isDark, "subtle")}`}>
      <p className={`text-lg font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{value}</p>
      <p className={`mt-1 text-xs uppercase tracking-[0.18em] ${isDark ? "text-slate-400" : "text-stone-500"}`}>{label}</p>
    </div>
  )
}

function SeriesBibleList({
  title,
  items,
  emptyLabel,
  isDark,
}: {
  title: string
  items: string[]
  emptyLabel: string
  isDark: boolean
}) {
  return (
    <div className={`rounded-md border-2 p-4 ${seriesSurfaceClass(isDark, "subtle")}`}>
      <p className={`text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-stone-500"}`}>{title}</p>
      {items.length > 0 ? (
        <div className="mt-3 space-y-2">
          {items.map((item, index) => (
            <div key={`${title}-${index}-${item}`} className={`rounded-sm border-2 px-3 py-2 text-sm leading-6 ${seriesSurfaceClass(isDark, "subtle")} ${isDark ? "text-slate-200" : "text-stone-700"}`}>
              {item}
            </div>
          ))}
        </div>
      ) : (
        <p className={`mt-3 text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>{emptyLabel}</p>
      )}
    </div>
  )
}

function SeriesBookCard({
  laneId,
  book,
  isDark,
  busy,
  onRefresh,
  onBusy,
}: {
  laneId: string
  book: Book
  isDark: boolean
  busy: boolean
  onRefresh: () => Promise<void>
  onBusy: (value: string | null) => void
}) {
  const progress = book.progress_pct ?? 0
  const isScreenplay = book.work_type === 'screenplay'
  const isComplete = progress >= 100
  const progressColor = isComplete
    ? "bg-emerald-500"
    : "bg-[#1f615d]"

  return (
    <div className={`rounded-md border-2 p-5 transition ${seriesSurfaceClass(isDark, "subtle")}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <p className={`text-sm font-bold truncate ${isDark ? "text-white" : "text-stone-900"}`}>
            {collectionUnitLabel(isScreenplay, book.series_order)}
            {book.title}
          </p>
          {book.author ? <p className={`mt-1 text-xs ${isDark ? "text-slate-400" : "text-stone-500"}`}>{book.author}</p> : null}
        </div>
        <Link href={getBookHref(book) as Route} className={`inline-flex items-center gap-1.5 rounded-sm border px-3 py-1.5 text-xs font-medium transition ${seriesSecondaryButtonClass(isDark)}`}>
          <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            <path strokeLinecap="round" strokeLinejoin="round" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
          </svg>
          Open
        </Link>
      </div>

      <div className="mt-4">
        <div className="mb-2 flex items-center justify-between text-xs">
          <span className={`font-medium ${isDark ? "text-slate-400" : "text-stone-500"}`}>Completion</span>
          <span className={`font-semibold ${isDark ? "text-slate-200" : "text-stone-700"}`}>{progress}%</span>
        </div>
        <div className={`h-3 overflow-hidden rounded-full ${isDark ? "bg-white/10" : "bg-stone-200"}`}>
          <div className={`h-full rounded-full transition-all duration-500 ${progressColor}`} style={{ width: `${Math.max(0, Math.min(progress, 100))}%` }} />
        </div>
        <p className={`mt-2 text-xs ${isDark ? "text-slate-400" : "text-stone-500"}`}>
          {book.chapters_read_count ?? 0} {storyUnitName(book.work_type, true)} read · {book.chapters_left ?? 0} left
        </p>
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        <button
          onClick={async () => {
            onBusy(`${laneId}:${book.id}`)
            try {
              await booksApi.setSeriesBookStatus(laneId, book.id, true)
              await onRefresh()
            } finally {
              onBusy(null)
            }
          }}
          disabled={busy}
          className={`inline-flex items-center gap-1.5 rounded-sm border px-3 py-1.5 text-xs font-medium transition disabled:opacity-50 ${seriesSecondaryButtonClass(isDark)}`}
        >
          <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
          </svg>
          {busy ? "Saving..." : "Mark read"}
        </button>
        <button
          onClick={async () => {
            onBusy(`${laneId}:${book.id}`)
            try {
              await booksApi.removeBookFromSeries(laneId, book.id)
              await onRefresh()
            } finally {
              onBusy(null)
            }
          }}
          disabled={busy}
          className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium transition disabled:opacity-50 ${isDark ? "border-red-500/30 text-red-300 hover:bg-red-500/10" : "border-red-200 text-red-600 hover:bg-red-50"}`}
        >
          <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
          </svg>
          Remove
        </button>
      </div>
    </div>
  )
}

function AddBookCard({
  laneId,
  book,
  isDark,
  onRefresh,
  onBusy,
  busy,
}: {
  laneId: string
  book: Book
  isDark: boolean
  onRefresh: () => Promise<void>
  onBusy: (value: string | null) => void
  busy: boolean
}) {
  const [position, setPosition] = useState(book.series_order ? String(book.series_order) : '')
  const isScreenplay = book.work_type === 'screenplay'

  return (
    <div className={`rounded-md border-2 p-4 transition ${seriesSurfaceClass(isDark, "subtle")}`}>
      <div className="flex items-center gap-2">
        <span className={`flex h-8 w-8 items-center justify-center rounded-full text-xs font-medium ${isDark ? "bg-[#172029] text-slate-300" : "bg-stone-200 text-stone-600"}`}>
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
          </svg>
        </span>
        <p className={`text-sm font-bold ${isDark ? "text-white" : "text-stone-900"}`}>{book.title}</p>
      </div>
      <div className="mt-3 flex gap-2">
        <input
          value={position}
          onChange={(e) => setPosition(e.target.value.replace(/[^\d]/g, ""))}
          placeholder={isScreenplay ? "Ep #" : "Vol #"}
          className={`w-20 rounded-sm border-2 px-3 py-2 text-sm outline-none ${isDark ? "border-slate-700/70 bg-[#0f151c] text-white placeholder:text-slate-500" : "border-stone-200 bg-white text-stone-900 placeholder:text-stone-400"}`}
        />
        <button
          onClick={async () => {
            onBusy(`add:${laneId}:${book.id}`)
            try {
              await booksApi.addBookToSeries(laneId, book.id, { position: position ? Number(position) : null })
              await onRefresh()
            } finally {
              onBusy(null)
            }
          }}
          disabled={busy}
          className={`flex-1 inline-flex items-center justify-center gap-1.5 rounded-sm px-4 py-2 text-sm font-medium transition disabled:opacity-50 ${seriesPrimaryButtonClass(isDark)}`}
        >
          <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
          </svg>
          {busy ? "Adding..." : "Add"}
        </button>
      </div>
    </div>
  )
}




