"use client"

import { useEffect, useMemo, useState } from "react"
import Link from "next/link"

import { booksApi } from "@/lib/api/books"
import { intelligenceApi } from "@/lib/api/intelligence"
import { useAuthStore } from "@/lib/stores/authStore"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import type { Book, BookSeries } from "@/types/book"
import type { AdvisorMessage, AdvisorResponse, SeriesContinuityResponse } from "@/types/intelligence"

function formatMarkdown(text: string): React.ReactNode {
  const paragraphs = text.split(/\n\n+/)
  return paragraphs.map((paragraph, pIndex) => {
    let formatted = paragraph.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    formatted = formatted.replace(/\*(.*?)\*/g, '<em>$1</em>')
    formatted = formatted.replace(/\n/g, '<br />')
    return <p key={pIndex} dangerouslySetInnerHTML={{ __html: formatted }} />
  })
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

  async function load() {
    const [seriesRows, bookRows] = await Promise.all([booksApi.listSeries(), booksApi.list()])
    setSeries(seriesRows)
    setBooks(bookRows)
  }

  useEffect(() => {
    if (user?.tier === "pro" || user?.tier === "power" || user?.tier === "admin") {
      load().catch(() => {})
    }
  }, [user?.tier])

  const unassignedBooks = useMemo(
    () => books.filter((book) => !book.primary_series_id && !book.series_name),
    [books]
  )

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

  async function handleSeriesAsk(seriesId: string) {
    if (!askQuery.trim()) return
    setAskLoading(true)
    const newMessages: AdvisorMessage[] = [...askMessages, { role: "user", content: askQuery }]
    setAskMessages(newMessages)
    setAskQuery("")
    try {
      const response = await intelligenceApi.seriesAdvisorMessage(seriesId, newMessages)
      setAskMessages(prev => [...prev, { role: "assistant", content: response.reply }])
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
    setContinuityResult(null)
    try {
      const result = await intelligenceApi.seriesContinuityCheck(
        seriesId,
        continuityBookId,
        continuityText,
        continuityChapterNum ? parseInt(continuityChapterNum) : undefined
      )
      setContinuityResult(result as typeof continuityResult)
    } catch {
      setContinuityResult(null)
    } finally {
      setContinuityLoading(false)
    }
  }

  if (!user || user.tier === "free") {
    return (
      <div className={`rounded-[2rem] border p-8 ${isDark ? "border-white/10 bg-white/5" : "border-amber-300 bg-amber-50"}`}>
        <h1 className={`text-3xl font-serif ${isDark ? "text-white" : "text-stone-900"}`}>Series workspace</h1>
        <p className={`mt-3 text-sm leading-7 ${isDark ? "text-gray-300" : "text-stone-700"}`}>
          Series mode is reserved for paid plans. It is built for readers carrying continuity across multiple books without losing where each volume stands.
        </p>
      </div>
    )
  }

  return (
    <div className={`min-h-screen space-y-8 ${isDark ? "bg-[radial-gradient(circle_at_top,#111827_0%,#05070d_100%)]" : "bg-[linear-gradient(180deg,#fcfdff_0%,#eef3f9_100%)]"}`}>
      <section className={`rounded-[2rem] border p-5 shadow-[0_24px_80px_-48px_rgba(15,23,42,0.32)] ${isDark ? "border-white/10 bg-[linear-gradient(145deg,rgba(30,41,59,0.75),rgba(15,23,42,0.94)_55%,rgba(56,189,248,0.12))]" : "border-white/70 bg-[linear-gradient(145deg,#ffffff,#f8fbff_55%,#eef4ff)]"}`}>
        <p className={`text-xs font-semibold uppercase tracking-[0.3em] ${isDark ? "text-sky-200" : "text-sky-700"}`}>Series workspace</p>
        <h1 className={`mt-2 font-serif text-4xl ${isDark ? "text-white" : "text-stone-900"}`}>Track sagas</h1>
        <p className={`mt-2 max-w-3xl text-sm font-light leading-7 ${isDark ? "text-gray-300" : "text-stone-600"}`}>
          Create named series, slot books into proper volume order, and manage your reading continuity across volumes.
        </p>
      </section>

      <section className={`rounded-[1.75rem] border p-5 ${isDark ? "border-white/10 bg-white/5" : "border-stone-200 bg-white"}`}>
        <div className="grid gap-3 md:grid-cols-[1.2fr_1.5fr_auto]">
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Create a new series"
            className={`rounded-2xl border px-4 py-3 text-sm ${isDark ? "border-white/10 bg-black/20 text-white placeholder:text-gray-500" : "border-stone-200 bg-stone-50 text-stone-900 placeholder:text-stone-400"}`}
          />
          <input
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Short note about this series"
            className={`rounded-2xl border px-4 py-3 text-sm ${isDark ? "border-white/10 bg-black/20 text-white placeholder:text-gray-500" : "border-stone-200 bg-stone-50 text-stone-900 placeholder:text-stone-400"}`}
          />
          <button
            onClick={createSeries}
            disabled={busyKey === "create"}
            className={`rounded-full px-5 py-3 text-sm font-semibold transition disabled:opacity-60 ${isDark ? "bg-amber-300 text-stone-950 hover:bg-amber-200" : "bg-stone-900 text-white hover:bg-stone-800"}`}
          >
            {busyKey === "create" ? "Creating..." : "Create series"}
          </button>
        </div>
      </section>

      {series.length === 0 ? (
        <div className={`rounded-3xl border border-dashed py-14 text-center ${isDark ? "border-white/15 bg-white/5 text-gray-400" : "border-stone-300 bg-stone-50 text-stone-500"}`}>
          <p className="font-medium">No series yet</p>
          <p className={`mt-1 text-sm ${isDark ? "text-gray-400" : "text-stone-500"}`}>Create one above to start organizing your books</p>
        </div>
      ) : (
        <div className="space-y-6">
          {series.map((lane) => (
            <section key={lane.id} className={`rounded-[1.75rem] border p-6 transition-all duration-200 hover:shadow-lg ${isDark ? "border-white/10 bg-white/5 hover:border-white/20" : "border-stone-200 bg-white hover:border-stone-300"}`}>
              <div className="flex flex-wrap items-center justify-between gap-4">
                <div>
                  <h2 className={`text-2xl font-bold ${isDark ? "text-white" : "text-stone-900"}`}>{lane.name}</h2>
                  {lane.description ? <p className={`mt-1 text-sm font-light ${isDark ? "text-gray-400" : "text-stone-500"}`}>{lane.description}</p> : null}
                </div>
                <div className="flex items-center gap-3">
                  <span className={`rounded-full px-3 py-1.5 text-xs font-medium ${isDark ? "bg-white/10 text-gray-300" : "bg-stone-100 text-stone-600"}`}>
                    {lane.books.length} volume{lane.books.length === 1 ? "" : "s"}
                  </span>
                  {lane.books.length > 0 && (
                    <Link
                    href={`/series/${lane.id}/ask`}
                    className={`inline-flex items-center gap-1.5 rounded-full px-4 py-1.5 text-xs font-semibold transition ${isDark ? "bg-amber-300 text-stone-950 hover:bg-amber-200" : "bg-stone-900 text-white hover:bg-stone-800"}`}
                  >
                    <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                    </svg>
                    Ask
                  </Link>
                  )}
                </div>
              </div>

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
                <div className={`mt-5 rounded-2xl border border-dashed p-5 text-sm ${isDark ? "border-white/10 text-gray-400" : "border-stone-300 text-stone-500"}`}>
                  No books in this series yet.
                </div>
              )}

              <div className="mt-5">
                <p className={`mb-3 text-xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-gray-400" : "text-stone-500"}`}>Add a book</p>
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
          ))}
        </div>
      )}

      {unassignedBooks.length > 0 ? (
        <section className={`rounded-[1.75rem] border p-6 ${isDark ? "border-white/10 bg-black/20" : "border-stone-200 bg-white/80"}`}>
          <h2 className={`text-2xl font-bold ${isDark ? "text-white" : "text-stone-900"}`}>Unassigned books</h2>
          <p className={`mt-1 text-sm font-light ${isDark ? "text-gray-400" : "text-stone-500"}`}>These books are not connected to any series yet</p>
          <div className="mt-4 flex flex-wrap gap-2">
            {unassignedBooks.map((book) => (
              <span key={book.id} className={`inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm font-medium ${isDark ? "bg-white/10 text-gray-200 hover:bg-white/20" : "bg-stone-100 text-stone-700 hover:bg-stone-200"}`}>
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
        return (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm">
            <div className={`w-full max-w-2xl rounded-[1.8rem] border shadow-[0_32px_80px_-24px_rgba(0,0,0,0.5)] ${isDark ? "border-white/10 bg-[#0f1117]" : "border-stone-200 bg-white"}`}>

              {/* Modal header */}
              <div className={`flex items-center justify-between border-b px-6 py-4 ${isDark ? "border-white/10" : "border-stone-200"}`}>
                <div>
                  <p className={`text-[11px] font-semibold uppercase tracking-[0.26em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Series intelligence</p>
                  <h3 className={`mt-0.5 text-lg font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{activeSeries?.name}</h3>
                </div>
                <button
                  onClick={() => setAskSeriesId(null)}
                  className={`rounded-full border px-3 py-1.5 text-xs font-medium ${isDark ? "border-white/10 text-slate-300 hover:bg-white/10" : "border-stone-200 text-stone-600 hover:bg-stone-50"}`}
                >
                  Close
                </button>
              </div>

              {/* Tab bar */}
              <div className={`flex gap-1 border-b px-6 py-3 ${isDark ? "border-white/10" : "border-stone-200"}`}>
                {(["ask", "continuity"] as const).map(tab => (
                  <button
                    key={tab}
                    onClick={() => setSeriesModalTab(tab)}
                    className={`rounded-full px-4 py-1.5 text-sm font-medium transition ${seriesModalTab === tab ? isDark ? "bg-white text-slate-950" : "bg-stone-900 text-white" : isDark ? "text-slate-400 hover:text-slate-200" : "text-stone-500 hover:text-stone-900"}`}
                  >
                    {tab === "ask" ? "Ask the series" : "Series continuity check"}
                  </button>
                ))}
              </div>

              <div className="max-h-[65vh] overflow-y-auto p-6 space-y-4">

                {/* ── Ask tab ── */}
                {seriesModalTab === "ask" && (
                  <>
                    <p className={`text-xs leading-5 ${isDark ? "text-slate-400" : "text-stone-500"}`}>
                      Ask anything about characters, continuity, or plot threads across all books in this series. Responses are grounded in aggregated story context.
                    </p>

                    {/* Conversation */}
                    {askMessages.length > 0 && (
                      <div className={`max-h-64 space-y-3 overflow-y-auto rounded-[1.2rem] border p-4 ${isDark ? "border-white/10 bg-black/30" : "border-stone-200 bg-stone-50"}`}>
                        {askMessages.map((msg, i) => (
                          <div key={i} className={`text-sm leading-6 ${msg.role === "user" ? isDark ? "text-slate-300" : "text-stone-700" : isDark ? "text-white" : "text-stone-900"}`}>
                            <span className={`mr-2 text-[10px] font-bold uppercase tracking-[0.2em] ${msg.role === "user" ? isDark ? "text-slate-500" : "text-stone-400" : isDark ? "text-amber-300" : "text-amber-600"}`}>
                              {msg.role === "user" ? "You" : "Series AI"}
                            </span>
                            {msg.role === "assistant" ? (
                              <div className="prose prose-invert max-w-none">
                                {formatMarkdown(msg.content)}
                              </div>
                            ) : (
                              msg.content
                            )}
                          </div>
                        ))}
                        {askLoading && <p className={`text-xs ${isDark ? "text-slate-500" : "text-stone-400"}`}>Analyzing series…</p>}
                      </div>
                    )}

                    {askResponse?.cached && (
                      <p className={`text-[11px] ${isDark ? "text-amber-400" : "text-amber-600"}`}>Cached response</p>
                    )}

                    <div className="flex gap-2">
                      <input
                        value={askQuery}
                        onChange={e => setAskQuery(e.target.value)}
                        placeholder="Ask about continuity, characters, or plot across all books…"
                        className={`flex-1 rounded-[0.9rem] border px-4 py-2.5 text-sm ${isDark ? "border-white/10 bg-black/20 text-white placeholder:text-slate-500" : "border-stone-200 bg-stone-50 text-stone-900 placeholder:text-stone-400"}`}
                        onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSeriesAsk(askSeriesId) } }}
                      />
                      <button
                        onClick={() => handleSeriesAsk(askSeriesId)}
                        disabled={askLoading || !askQuery.trim()}
                        className={`rounded-full px-5 py-2.5 text-sm font-semibold disabled:opacity-50 ${isDark ? "bg-amber-300 text-stone-950 hover:bg-amber-200" : "bg-stone-900 text-white hover:bg-stone-800"}`}
                      >
                        {askLoading ? "…" : "Ask"}
                      </button>
                    </div>
                  </>
                )}

                {/* ── Series Continuity Check tab ── */}
                {seriesModalTab === "continuity" && (
                  <>
                    <p className={`text-xs leading-5 ${isDark ? "text-slate-400" : "text-stone-500"}`}>
                      Paste a passage from your new book and check it against the earlier volumes in this series for character, plot, and world-building consistency.
                    </p>

                    <div className="grid gap-3 sm:grid-cols-2">
                      <div>
                        <label className={`mb-1 block text-[11px] font-semibold uppercase tracking-[0.2em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>New book</label>
                        <select
                          value={continuityBookId}
                          onChange={e => setContinuityBookId(e.target.value)}
                          className={`w-full rounded-[0.8rem] border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-black/20 text-white" : "border-stone-200 bg-white text-stone-900"}`}
                        >
                          <option value="">Select book…</option>
                          {seriesBooks.map(b => <option key={b.id} value={b.id}>{b.title}</option>)}
                        </select>
                      </div>
                      <div>
                        <label className={`mb-1 block text-[11px] font-semibold uppercase tracking-[0.2em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Chapter (optional)</label>
                        <input
                          type="number" min={1}
                          value={continuityChapterNum}
                          onChange={e => setContinuityChapterNum(e.target.value)}
                          placeholder="e.g. 5"
                          className={`w-full rounded-[0.8rem] border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-black/20 text-white placeholder:text-slate-500" : "border-stone-200 bg-white text-stone-900 placeholder:text-stone-400"}`}
                        />
                      </div>
                    </div>

                    <textarea
                      rows={6}
                      value={continuityText}
                      onChange={e => setContinuityText(e.target.value)}
                      placeholder="Paste the passage you want to cross-check against earlier books…"
                      className={`w-full resize-none rounded-[1rem] border px-4 py-3 text-sm leading-7 outline-none ${isDark ? "border-white/10 bg-black/20 text-slate-200 placeholder:text-slate-600" : "border-stone-200 bg-stone-50 text-stone-900 placeholder:text-stone-400"}`}
                    />

                    <button
                      onClick={() => handleSeriesContinuityCheck(askSeriesId)}
                      disabled={continuityLoading || !continuityText.trim() || !continuityBookId}
                      className={`w-full rounded-full px-5 py-3 text-sm font-semibold disabled:opacity-50 ${isDark ? "bg-[linear-gradient(135deg,#4f46e5,#4338ca)] text-white" : "bg-stone-900 text-white hover:bg-stone-800"}`}
                    >
                      {continuityLoading ? "Checking across series…" : "Run series continuity check"}
                    </button>

                    {continuityResult && (
                      <div className="space-y-4">
                        {continuityResult.cached && (
                          <p className={`text-[11px] ${isDark ? "text-amber-400" : "text-amber-600"}`}>Cached response</p>
                        )}

                        {/* Verdict */}
                        <div className={`rounded-[1.2rem] border px-4 py-3 ${isDark ? "border-indigo-500/25 bg-indigo-500/10" : "border-violet-200 bg-violet-50"}`}>
                          <p className={`text-[10px] font-bold uppercase tracking-[0.24em] mb-1 ${isDark ? "text-indigo-300" : "text-violet-600"}`}>Overall verdict</p>
                          <p className={`text-sm leading-6 font-medium ${isDark ? "text-slate-100" : "text-stone-800"}`}>{continuityResult.review.overall_verdict}</p>
                        </div>

                        {/* Thematic fit */}
                        <div className={`rounded-[1.2rem] border px-4 py-3 ${
                          continuityResult.review.thematic_fit.score === "strong" ? isDark ? "border-teal-500/25 bg-teal-500/10" : "border-teal-200 bg-teal-50"
                          : continuityResult.review.thematic_fit.score === "weak" ? isDark ? "border-red-500/25 bg-red-500/10" : "border-red-200 bg-red-50"
                          : isDark ? "border-amber-500/25 bg-amber-500/10" : "border-amber-100 bg-amber-50"
                        }`}>
                          <div className="flex items-center gap-2 mb-1">
                            <p className={`text-[10px] font-bold uppercase tracking-[0.24em] ${isDark ? "text-slate-400" : "text-stone-400"}`}>Thematic fit</p>
                            <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase ${
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
                            <p className={`text-[10px] font-bold uppercase tracking-[0.24em] ${isDark ? "text-amber-300" : "text-amber-700"}`}>Issues ({continuityResult.review.continuity_issues.length})</p>
                            {continuityResult.review.continuity_issues.map((issue, i) => (
                              <div key={i} className={`rounded-[1rem] border px-4 py-3 text-sm ${
                                issue.severity === "critical" ? isDark ? "border-red-500/30 bg-red-500/10" : "border-red-200 bg-red-50"
                                : isDark ? "border-amber-500/25 bg-amber-500/8" : "border-amber-200 bg-amber-50"
                              }`}>
                                <p className={`font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{issue.title}</p>
                                <p className={`mt-1 text-xs leading-5 ${isDark ? "text-slate-300" : "text-stone-600"}`}>{issue.description}</p>
                                {issue.suggestion && <p className={`mt-1.5 text-xs font-medium ${isDark ? "text-indigo-300" : "text-violet-700"}`}>→ {issue.suggestion}</p>}
                              </div>
                            ))}
                          </div>
                        )}

                        {/* Cross-book opportunities */}
                        {continuityResult.review.cross_book_opportunities.length > 0 && (
                          <div className="space-y-2">
                            <p className={`text-[10px] font-bold uppercase tracking-[0.24em] ${isDark ? "text-teal-300" : "text-teal-700"}`}>Opportunities</p>
                            {continuityResult.review.cross_book_opportunities.map((opp, i) => (
                              <div key={i} className={`rounded-[1rem] border px-4 py-3 text-sm ${isDark ? "border-teal-500/20 bg-teal-500/8" : "border-teal-200 bg-teal-50"}`}>
                                <p className={`font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{opp.title}</p>
                                <p className={`mt-1 text-xs leading-5 ${isDark ? "text-slate-300" : "text-stone-600"}`}>{opp.description}</p>
                              </div>
                            ))}
                          </div>
                        )}

                        {/* Retrieved passages */}
                        {continuityResult.retrieved_passages.length > 0 && (
                          <div>
                            <p className={`text-[10px] font-bold uppercase tracking-[0.24em] mb-2 ${isDark ? "text-slate-500" : "text-stone-400"}`}>Cross-referenced from earlier volumes</p>
                            <div className="grid gap-2 sm:grid-cols-2">
                              {continuityResult.retrieved_passages.map((p, i) => (
                                <div key={i} className={`rounded-[0.9rem] border px-3 py-2 text-xs ${isDark ? "border-white/10 bg-white/[0.03]" : "border-stone-200 bg-stone-50"}`}>
                                  <p className={`font-semibold mb-1 ${isDark ? "text-indigo-300" : "text-violet-600"}`}>{p.book_title} · Ch. {p.chapter_num}</p>
                                  <p className={`leading-5 ${isDark ? "text-slate-400" : "text-stone-600"}`}>{p.excerpt}</p>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {continuityResult.review.continuity_issues.length === 0 && (
                          <div className={`rounded-[1.2rem] border p-4 text-center ${isDark ? "border-teal-500/20 bg-teal-500/8" : "border-teal-200 bg-teal-50"}`}>
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
  const isComplete = progress >= 100
  const progressColor = isComplete
    ? (isDark ? "bg-emerald-500 shadow-[0_0_10px_rgba(16,185,129,0.5)]" : "bg-emerald-500 shadow-[0_0_10px_rgba(16,185,129,0.3)]")
    : (isDark ? "bg-indigo-500" : "bg-indigo-500")

  return (
    <div className={`rounded-[1.4rem] border p-5 transition-all duration-200 hover:shadow-md ${isDark ? "border-white/10 bg-black/20 hover:border-white/20" : "border-stone-200 bg-stone-50 hover:border-stone-300"}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <p className={`text-sm font-bold truncate ${isDark ? "text-white" : "text-stone-900"}`}>
            {book.series_order ? `Vol ${book.series_order} · ` : ""}
            {book.title}
          </p>
          {book.author ? <p className={`mt-1 text-xs font-light ${isDark ? "text-gray-400" : "text-stone-500"}`}>{book.author}</p> : null}
        </div>
        <Link href={`/${book.id}`} className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium transition ${isDark ? "border-white/20 text-gray-200 hover:bg-white/10" : "border-stone-300 text-stone-700 hover:bg-stone-50"}`}>
          <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            <path strokeLinecap="round" strokeLinejoin="round" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
          </svg>
          Open
        </Link>
      </div>

      <div className="mt-4">
        <div className="mb-2 flex items-center justify-between text-xs">
          <span className={`font-medium ${isDark ? "text-gray-400" : "text-stone-500"}`}>Completion</span>
          <span className={`font-semibold ${isDark ? "text-gray-200" : "text-stone-700"}`}>{progress}%</span>
        </div>
        <div className={`h-3 overflow-hidden rounded-full ${isDark ? "bg-white/10" : "bg-stone-200"}`}>
          <div className={`h-full rounded-full transition-all duration-500 ${progressColor}`} style={{ width: `${Math.max(0, Math.min(progress, 100))}%` }} />
        </div>
        <p className={`mt-2 text-xs font-light ${isDark ? "text-gray-400" : "text-stone-500"}`}>
          {book.chapters_read_count ?? 0} read · {book.chapters_left ?? 0} left
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
          className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium transition disabled:opacity-50 ${isDark ? "border-white/20 text-gray-200 hover:bg-white/10" : "border-stone-300 text-stone-700 hover:bg-stone-50"}`}
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
  const [position, setPosition] = useState(book.series_order ? String(book.series_order) : "")

  return (
    <div className={`rounded-2xl border p-4 transition-all duration-200 hover:shadow-md ${isDark ? "border-white/10 bg-black/20 hover:border-white/20" : "border-stone-200 bg-stone-50 hover:border-stone-300"}`}>
      <div className="flex items-center gap-2">
        <span className={`flex h-8 w-8 items-center justify-center rounded-full text-xs font-medium ${isDark ? "bg-white/10 text-gray-300" : "bg-stone-200 text-stone-600"}`}>
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
          placeholder="Vol #"
          className={`w-20 rounded-xl border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-white/5 text-white placeholder:text-gray-500" : "border-stone-200 bg-white text-stone-900 placeholder:text-stone-400"}`}
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
          className={`flex-1 inline-flex items-center justify-center gap-1.5 rounded-full px-4 py-2 text-sm font-medium transition disabled:opacity-50 ${isDark ? "bg-white text-stone-950 hover:bg-gray-200" : "bg-stone-900 text-white hover:bg-stone-800"}`}
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
