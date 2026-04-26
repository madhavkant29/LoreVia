"use client"

import { useEffect, useMemo, useState } from "react"
import Link from "next/link"

import { booksApi } from "@/lib/api/books"
import { intelligenceApi } from "@/lib/api/intelligence"
import { useAuthStore } from "@/lib/stores/authStore"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import type { Book, BookSeries } from "@/types/book"
import type { AdvisorMessage, AdvisorResponse } from "@/types/intelligence"

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
  const [continuityResult, setContinuityResult] = useState<null | { review: { overall_verdict: string; continuity_issues: Array<{title: string; description: string; severity: string; suggestion?: string}>; cross_book_opportunities: Array<{title: string; description: string}>; thematic_fit: {score: string; notes: string} }; retrieved_passages: Array<{book_title?: string; chapter_num: number; excerpt: string}>; cached?: boolean }>(null)
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
    <div className="space-y-8">
      <section className={`rounded-[2rem] border p-6 shadow-[0_24px_80px_-48px_rgba(15,23,42,0.32)] ${isDark ? "border-white/10 bg-[linear-gradient(145deg,rgba(30,41,59,0.75),rgba(15,23,42,0.94)_55%,rgba(56,189,248,0.12))]" : "border-white/70 bg-[linear-gradient(145deg,#ffffff,#f8fbff_55%,#eef4ff)]"}`}>
        <p className={`text-xs font-semibold uppercase tracking-[0.3em] ${isDark ? "text-sky-200" : "text-sky-700"}`}>Series workspace</p>
        <h1 className={`mt-3 font-serif text-4xl ${isDark ? "text-white" : "text-stone-900"}`}>Track sagas as connected reading lanes, not isolated uploads.</h1>
        <p className={`mt-3 max-w-3xl text-sm leading-7 ${isDark ? "text-gray-300" : "text-stone-600"}`}>
          Create named series, slot books into proper volume order, mark earlier volumes as already finished, and let the bigger picture stay visible while each book keeps its own chapter history.
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
          No series yet. Create one above, then start assigning books.
        </div>
      ) : (
        <div className="space-y-6">
          {series.map((lane) => (
            <section key={lane.id} className={`rounded-[1.75rem] border p-5 ${isDark ? "border-white/10 bg-white/5" : "border-stone-200 bg-white"}`}>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h2 className={`text-2xl font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{lane.name}</h2>
                  {lane.description ? <p className={`mt-1 text-sm ${isDark ? "text-gray-400" : "text-stone-500"}`}>{lane.description}</p> : null}
                </div>
                <div className="flex items-center gap-2">
                  <span className={isDark ? "rounded-full bg-white/10 px-3 py-1 text-xs text-gray-300" : "rounded-full bg-stone-100 px-3 py-1 text-xs text-stone-600"}>
                    {lane.books.length} volume{lane.books.length === 1 ? "" : "s"}
                  </span>
                  {lane.books.length > 0 && (
                    <button
                    onClick={() => {
                      setAskSeriesId(lane.id)
                      setAskQuery("")
                      setAskMessages([])
                      setAskResponse(null)
                      setContinuityText("")
                      setContinuityChapterNum("")
                      setContinuityBookId(lane.books[0]?.id ?? "")
                      setContinuityResult(null)
                      setSeriesModalTab("ask")
                    }}
                    className={`rounded-full px-3 py-1 text-xs font-semibold ${isDark ? "bg-amber-300 text-stone-950 hover:bg-amber-200" : "bg-stone-900 text-white hover:bg-stone-800"}`}
                  >
                    Ask
                  </button>
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
        <section className={`rounded-[1.75rem] border p-5 ${isDark ? "border-white/10 bg-black/20" : "border-stone-200 bg-white/80"}`}>
          <h2 className={`text-2xl font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>Unassigned books</h2>
          <p className={`mt-1 text-sm ${isDark ? "text-gray-400" : "text-stone-500"}`}>These books are not connected to any series yet.</p>
          <div className="mt-4 flex flex-wrap gap-2">
            {unassignedBooks.map((book) => (
              <span key={book.id} className={isDark ? "rounded-full bg-white/10 px-3 py-1 text-sm text-gray-200" : "rounded-full bg-stone-100 px-3 py-1 text-sm text-stone-700"}>
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
                            {msg.content}
                          </div>
                        ))}
                        {askLoading && <p className={`text-xs ${isDark ? "text-slate-500" : "text-stone-400"}`}>Analyzing series…</p>}
                      </div>
                    )}

                    {askResponse?.cached && (
                      <p className={`text-[11px] ${isDark ? "text-amber-400" : "text-amber-600"}`}>⚡ Cached response</p>
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
                          <p className={`text-[11px] ${isDark ? "text-amber-400" : "text-amber-600"}`}>⚡ Cached response</p>
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
                            <p className={`text-[10px] font-bold uppercase tracking-[0.24em] ${isDark ? "text-amber-300" : "text-amber-700"}`}>⚠️ Issues ({continuityResult.review.continuity_issues.length})</p>
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
                            <p className={`text-[10px] font-bold uppercase tracking-[0.24em] ${isDark ? "text-teal-300" : "text-teal-700"}`}>✨ Opportunities</p>
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
                            <p className="text-2xl mb-1">✅</p>
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

  return (
    <div className={`rounded-[1.4rem] border p-4 ${isDark ? "border-white/10 bg-black/20" : "border-stone-200 bg-stone-50"}`}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>
            {book.series_order ? `Vol ${book.series_order} · ` : ""}
            {book.title}
          </p>
          {book.author ? <p className={`mt-1 text-xs ${isDark ? "text-gray-400" : "text-stone-500"}`}>{book.author}</p> : null}
        </div>
        <Link href={`/${book.id}`} className={`rounded-full px-3 py-1 text-xs font-semibold ${isDark ? "bg-white text-stone-950" : "bg-stone-900 text-white"}`}>
          Open
        </Link>
      </div>

      <div className="mt-4">
        <div className="mb-2 flex items-center justify-between text-xs">
          <span className={isDark ? "text-gray-400" : "text-stone-500"}>Completion</span>
          <span className={isDark ? "text-gray-200" : "text-stone-700"}>{progress}%</span>
        </div>
        <div className={`h-2 overflow-hidden rounded-full ${isDark ? "bg-white/10" : "bg-stone-200"}`}>
          <div className="h-full rounded-full bg-indigo-500" style={{ width: `${Math.max(0, Math.min(progress, 100))}%` }} />
        </div>
        <p className={`mt-2 text-xs ${isDark ? "text-gray-400" : "text-stone-500"}`}>
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
          className={`rounded-full px-4 py-2 text-sm font-medium transition disabled:opacity-60 ${isDark ? "bg-amber-300 text-stone-950 hover:bg-amber-200" : "bg-stone-900 text-white hover:bg-stone-800"}`}
        >
          {busy ? "Saving..." : "Mark book read"}
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
          className={`rounded-full px-4 py-2 text-sm font-medium transition disabled:opacity-60 ${isDark ? "border border-white/15 text-gray-200 hover:bg-white/10" : "border border-stone-300 text-stone-700 hover:bg-stone-50"}`}
        >
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
    <div className={`rounded-2xl border p-4 ${isDark ? "border-white/10 bg-black/20" : "border-stone-200 bg-stone-50"}`}>
      <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{book.title}</p>
      <div className="mt-3 flex gap-2">
        <input
          value={position}
          onChange={(e) => setPosition(e.target.value.replace(/[^\d]/g, ""))}
          placeholder="Vol"
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
          className={`flex-1 rounded-full px-4 py-2 text-sm font-medium transition disabled:opacity-60 ${isDark ? "bg-white text-stone-950 hover:bg-gray-200" : "bg-stone-900 text-white hover:bg-stone-800"}`}
        >
          {busy ? "Adding..." : "Add to series"}
        </button>
      </div>
    </div>
  )
}
