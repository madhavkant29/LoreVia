"use client"

import { useEffect, useMemo, useRef, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import Link from "next/link"
import { useParams } from "next/navigation"

import { booksApi } from "@/lib/api/books"
import { intelligenceApi } from "@/lib/api/intelligence"
import { isPaidTier } from "@/lib/billing/plans"
import { asQueryKey, booksSeriesCacheKey } from "@/lib/query/cacheKeys"
import { useAuthStore } from "@/lib/stores/authStore"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import { renderMarkdownHtml } from "@/lib/utils/richText"
import { Skeleton } from "@/components/ui/Skeleton"
import type { PaginatedSeries } from "@/types/book"
import type { AdvisorMessage } from "@/types/intelligence"

const SUGGESTED_QUESTIONS = [
  { category: "Characters", question: "Who is the most recurring side character?" },
  { category: "Plot", question: "Summarize the conflict in Book 2." },
  { category: "Continuity", question: "Are there any unresolved plot threads?" },
  { category: "Lore", question: "Explain the significance of the main artifact." },
  { category: "Arcs", question: "How does the protagonist's attitude change?" },
  { category: "Timeline", question: "Did the characters know the secret in Book 1?" },
]

export default function SeriesAskPage() {
  const { seriesId } = useParams<{ seriesId: string }>()
  const user = useAuthStore((state) => state.user)
  const { theme } = usePreferencesStore()
  const isDark = theme === "dark"
  const { data: paginatedSeries } = useQuery<PaginatedSeries>({
    queryKey: asQueryKey(booksSeriesCacheKey()),
    queryFn: () => booksApi.listSeries(),
    enabled: Boolean(seriesId),
  })
  const seriesList = useMemo(() => paginatedSeries?.items ?? [], [paginatedSeries?.items])
  const [askQuery, setAskQuery] = useState("")
  const [askMessages, setAskMessages] = useState<AdvisorMessage[]>([])
  const [askLoading, setAskLoading] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const series = useMemo(() => seriesList.find((s) => s.id === seriesId) ?? null, [seriesId, seriesList])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [askMessages, askLoading])

  async function handleSeriesAsk(customQuery?: string) {
    const query = customQuery || askQuery
    if (!query.trim() || !seriesId) return
    setAskLoading(true)
    const newMessages: AdvisorMessage[] = [...askMessages, { role: "user", content: query }]
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
    } catch {
      setAskMessages((prev) => [
        ...prev,
        { role: "assistant", content: "I could not answer that right now. Please try again." },
      ])
    } finally {
      setAskLoading(false)
    }
  }

  const bookCount = series?.books?.length || 0
  const hasStarted = askMessages.length > 0

  if (!user || !isPaidTier(user.tier)) {
    return (
      <div className={`min-h-screen flex items-center justify-center px-4 ${isDark ? "bg-[#0a0a0a]" : "bg-[#f5efe6]"}`}>
        <div className={`rounded-lg border p-8 max-w-md ${isDark ? "border-white/10 bg-white/5" : "border-amber-300 bg-amber-50"}`}>
          <h1 className={`text-3xl font-serif ${isDark ? "text-white" : "text-stone-900"}`}>Series intelligence</h1>
          <p className={`mt-3 text-sm leading-7 ${isDark ? "text-gray-300" : "text-stone-700"}`}>
            Series mode is reserved for paid plans.
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className={`flex min-h-screen flex-col ${isDark ? "bg-[#071211]" : "bg-stone-50"}`}>
      {/* Header */}
      <header className={`border-b px-4 py-4 ${isDark ? "border-white/10 bg-black/20" : "border-stone-200 bg-white/50"}`}>
        <div className="mx-auto max-w-3xl flex items-center justify-between">
          <Link href="/series" className={`inline-flex items-center gap-2 text-sm transition ${isDark ? "text-slate-400 hover:text-slate-200" : "text-stone-500 hover:text-stone-700"}`}>
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
            </svg>
            Back to Series
          </Link>
          <div className={`flex items-center gap-4 text-xs ${isDark ? "text-slate-400" : "text-stone-500"}`}>
            <span className="flex items-center gap-1.5">
              <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
              </svg>
              {bookCount} {bookCount === 1 ? "Book" : "Books"}
            </span>
            <span className="flex items-center gap-1.5">
              <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
              </svg>
              AI Powered
            </span>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className={`flex-1 px-4 ${hasStarted ? "py-6" : "flex items-center justify-center py-10"}`}>
        <div className="mx-auto w-full max-w-3xl">
          {/* Title Section - Only show when empty */}
          {!hasStarted && (
            <div className="text-center mb-10">
              <h1 className={`font-serif text-5xl leading-tight ${isDark ? "text-white" : "text-slate-950"}`}>
                {series?.name || "Series Intelligence"}
              </h1>
              {series?.description && (
                <p className={`mt-3 text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>{series.description}</p>
              )}
              <div className={`mt-4 inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs ${isDark ? "bg-white/10 text-slate-300" : "bg-stone-100 text-stone-600"}`}>
                <span className="relative flex h-2 w-2">
                  <span className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${isDark ? "bg-emerald-400" : "bg-emerald-500"}`}></span>
                  <span className={`relative inline-flex rounded-full h-2 w-2 ${isDark ? "bg-emerald-400" : "bg-emerald-500"}`}></span>
                </span>
                Grounded in {bookCount} book{bookCount !== 1 ? "s" : ""}
              </div>
            </div>
          )}

          {/* Chat Messages */}
          {hasStarted && (
            <div className={`space-y-6 mb-6 ${isDark ? "" : ""}`}>
              {askMessages.map((msg, i) => (
                <div key={i} className={`flex gap-4 ${msg.role === "user" ? "flex-row-reverse" : ""}`}>
                  <div className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold ${msg.role === "user" ? (isDark ? "bg-slate-700 text-slate-200" : "bg-stone-200 text-stone-700") : (isDark ? "bg-amber-500/20 text-amber-300" : "bg-amber-100 text-amber-700")}`}>
                    {msg.role === "user" ? "You" : "AI"}
                  </div>
                  <div className={`flex-1 ${msg.role === "user" ? "text-right" : ""}`}>
                    <div className={`inline-block rounded-md px-5 py-3 text-left text-sm leading-7 ${msg.role === "user" ? (isDark ? "bg-slate-700/50 text-slate-200" : "bg-stone-200 text-stone-800") : (isDark ? "text-white" : "text-stone-900")}`}>
                      {msg.role === "assistant" ? (
                        <div dangerouslySetInnerHTML={{ __html: renderMarkdownHtml(msg.content) }} />
                      ) : msg.content}
                    </div>
                  </div>
                </div>
              ))}
              {askLoading && (
                <div className="flex gap-4">
                  <div className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold ${isDark ? "bg-amber-500/20 text-amber-300" : "bg-amber-100 text-amber-700"}`}>
                    AI
                  </div>
                  <div className="flex items-center gap-2 text-sm">
                    <span className={`animate-bounce ${isDark ? "text-slate-400" : "text-stone-400"}`}>.</span>
                    <span className={`animate-bounce delay-100 ${isDark ? "text-slate-400" : "text-stone-400"}`}>.</span>
                    <span className={`animate-bounce delay-200 ${isDark ? "text-slate-400" : "text-stone-400"}`}>.</span>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
          )}

          {/* Empty State - Suggested Questions */}
          {!hasStarted && !askLoading && (
            <div className="mb-8">
              <p className={`text-center text-sm mb-4 ${isDark ? "text-slate-400" : "text-stone-500"}`}>Try asking about:</p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {SUGGESTED_QUESTIONS.map((item, i) => (
                  <button
                    key={i}
                    onClick={() => handleSeriesAsk(item.question)}
                    className={`group rounded-md border p-4 text-left transition-colors ${isDark ? "border-white/10 bg-white/5 hover:border-white/20 hover:bg-white/10" : "border-stone-200 bg-white hover:border-stone-300"}`}
                  >
                    <div>
                      <p className={`text-xs font-medium uppercase tracking-wide mb-1 ${isDark ? "text-slate-400" : "text-stone-500"}`}>{item.category}</p>
                      <p className={`text-sm leading-relaxed ${isDark ? "text-slate-200 group-hover:text-white" : "text-stone-700 group-hover:text-stone-900"}`}>{item.question}</p>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Input Bar - Docked at bottom when chat started, centered when empty */}
          <div className={`${hasStarted ? "sticky bottom-6" : ""}`}>
            <div className={`relative rounded-md border ${isDark ? "border-white/10 bg-[#0f172a]" : "border-stone-200 bg-white"}`}>
              <div className="relative flex items-end gap-2 p-2">
                <input
                  value={askQuery}
                  onChange={(e) => setAskQuery(e.target.value)}
                  aria-label={hasStarted ? "Ask a follow-up question" : "Ask about continuity, characters, or plot across all books"}
                  className={`flex-1 bg-transparent border-0 px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-transparent ${isDark ? "text-white" : "text-stone-900"}`}
                  onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSeriesAsk() } }}
                />
                <button
                  onClick={() => handleSeriesAsk()}
                  disabled={askLoading || !askQuery.trim()}
                  aria-label={askLoading ? "Asking series question" : "Ask series question"}
                  className="flex-shrink-0 rounded-md bg-violet-700 px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-violet-600 disabled:opacity-40"
                >
                  {askLoading ? (
                    <Skeleton className="h-5 w-5 rounded-full bg-white/35" />
                  ) : (
                    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                    </svg>
                  )}
                </button>
              </div>
            </div>
            <p className={`mt-2 text-center text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>
              {hasStarted ? "Ask a follow-up question." : "Ask about continuity, characters, or plot across all books."}
            </p>
            
            {/* Footer Note */}
            <p className={`text-center text-xs mt-3 ${isDark ? "text-slate-500" : "text-stone-400"}`}>
              Responses are grounded in your series data. AI may occasionally make mistakes.
            </p>
          </div>
        </div>
      </main>
    </div>
  )
}
