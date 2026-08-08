"use client"

import { useQuery } from "@tanstack/react-query"
import { useCallback, useEffect, useRef, useState } from "react"
import Link from "next/link"
import dynamic from "next/dynamic"
import { useParams } from "next/navigation"
import { intelligenceApi } from "@/lib/api/intelligence"
import { canUseAuthorFeatures } from "@/lib/billing/plans"
import { buildDailyCapEventDetail } from "@/lib/limits/dailyCap"
import { useAuthStore } from "@/lib/stores/authStore"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import { capture } from "@/lib/analytics/posthog"
import { saveContextualVaultNote } from "@/lib/utils/notes"
import { Button } from "@/components/ui/Button"
import { Skeleton } from "@/components/ui/Skeleton"
import { WorkspaceFamilyHeader } from "@/components/reader/WorkspaceFamilyHeader"
import {
  buildReplyFollowUps,
  RichMessage,
  responseTypeStyle,
  StoryAdvisorEmptyState,
  StoryAdvisorIcon,
  StoryAdvisorSectionLabel,
  StoryAdvisorSurface,
  SuggestionGroup,
  worldItemDescription,
  worldItemTitle,
  type ResponseType,
} from "./advisorPage.components"
import type {
  AdvisorMessage,
  AdvisorPassage,
  AdvisorScanMeta,
  AdvisorSuggestion,
  AdvisorGreeting,
  AdvisorWorldAnalysis,
} from "@/types/intelligence"

// Response type visual config (4 variants)
type AdvisorPanel = "checker" | "suggestions"

const defaultScanMeta: AdvisorScanMeta = {
  character_count: 0,
  state_count: 0,
  open_thread_count: 0,
  clue_count: 0,
  relationship_count: 0,
  world_element_count: 0,
  heuristic_count: 0,
  fallback_applied: false,
  proactive_audit_applied: false,
  scan_basis: [],
  data_gaps: [],
  audit_summary: null,
}

const ADVISOR_STARTER_PROMPTS = [
  "Are there any plotholes I should know about?",
  "What foreshadowing opportunities am I missing?",
  "Help me think through how to end the current arc.",
  "Is there a consistency issue with my magic system?",
  "I want to suddenly change the genre. Is that a good idea?",
]

const RESPONSE_TYPE_LEGEND = [
  { icon: "WRN", label: "Contradiction", desc: "Your plan clashes with the text" },
  { icon: "OPP", label: "Opportunity", desc: "Foreshadowing or arc connection found" },
  { icon: "TRD", label: "Tradeoff", desc: "Multiple endings debated" },
  { icon: "RSP", label: "Response", desc: "General analysis or advice" },
]

const StoryAdvisorEditorialPanel = dynamic(
  () => import("@/components/reader/StoryAdvisorEditorialPanel").then(mod => mod.StoryAdvisorEditorialPanel),
  {
    loading: () => (
      <div className="rounded-lg border border-white/10 bg-[#0b1220]/88 p-6" role="status" aria-label="Loading editorial review" aria-busy="true">
        <span className="sr-only">Loading editorial review</span>
        <Skeleton className="h-4 w-40 bg-white/10" />
        <Skeleton className="mt-4 h-24 rounded-md bg-white/10" />
        <div className="mt-4 flex gap-2">
          <Skeleton className="h-9 w-32 rounded-sm bg-white/10" />
          <Skeleton className="h-9 w-28 rounded-sm bg-white/10" />
        </div>
      </div>
    ),
  },
)

function scanStorageKey(bookId: string) {
  return `lorevia-advisor-scan:${bookId}`
}


// Main page
export default function AdvisorPage() {
  const { bookId } = useParams<{ bookId: string }>()
  const { theme } = usePreferencesStore()
  const userTier = useAuthStore((state) => state.user?.tier)
  const canUseAuthorMode = canUseAuthorFeatures(userTier)
  const isDark = theme === "dark"

  const { data: greeting = null } = useQuery<AdvisorGreeting | null>({
    queryKey: [`advisor:${bookId}:greeting`],
    queryFn: () => intelligenceApi.advisorGreeting(bookId),
  })

  const [suggestionsPayload, setSuggestionsPayload] = useState<{ suggestions: AdvisorSuggestion[]; meta: AdvisorScanMeta } | null>(null)
  const [suggestionsLoading, setSuggestionsLoading] = useState(false)
  const [scanJobId, setScanJobId] = useState<string | null>(null)
  const [scanStatus, setScanStatus] = useState<"idle" | "scanning" | "complete" | "failed">("idle")
  const [scanError, setScanError] = useState<string | null>(null)
  const scanPollRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const loadSuggestions = useCallback(async () => {
    if (!canUseAuthorMode) {
      setSuggestionsPayload({ suggestions: [], meta: defaultScanMeta })
      return
    }
    setSuggestionsLoading(true)
    try {
      const data = await intelligenceApi.advisorSuggestions(bookId)
      setSuggestionsPayload(data)
    } catch {
      setSuggestionsPayload(null)
    } finally {
      setSuggestionsLoading(false)
    }
  }, [bookId, canUseAuthorMode])

  useEffect(() => {
    void loadSuggestions()
  }, [loadSuggestions])

  const startScan = useCallback(async () => {
    if (!canUseAuthorMode) {
      setScanStatus("failed")
      setScanError("Continuity scans require an active trial, Author, or Architect plan.")
      return
    }
    if (scanStatus === "scanning") return
    setScanStatus("scanning")
    setScanError(null)
    try {
      const { job_id, cached } = await intelligenceApi.advisorSuggestionsScan(bookId)
      if (cached) {
        await loadSuggestions()
        setScanStatus("complete")
        return
      }
      setScanJobId(job_id)
      pollScanJob(job_id)
    } catch (err: unknown) {
      setScanStatus("failed")
      setScanError(err instanceof Error ? err.message : "Scan failed to start")
    }
  }, [bookId, canUseAuthorMode, scanStatus, loadSuggestions])

  const pollScanJob = useCallback((jobId: string) => {
    const poll = async (attempt: number) => {
      try {
        const response = await intelligenceApi.advisorSuggestionsJobStatus(bookId, jobId)
        if (response.status === "complete" && response.result) {
          setSuggestionsPayload(response.result)
          setScanStatus("complete")
          setScanJobId(null)
          return
        }
        if (response.status === "failed") {
          setScanStatus("failed")
          setScanError(response.error || "Scan failed")
          setScanJobId(null)
          return
        }
        if (attempt < 120) {
          scanPollRef.current = setTimeout(() => poll(attempt + 1), attempt < 10 ? 1000 : 2000)
        } else {
          setScanStatus("failed")
          setScanError("Scan timed out")
          setScanJobId(null)
        }
      } catch (err: unknown) {
        if (attempt < 120) {
          scanPollRef.current = setTimeout(() => poll(attempt + 1), attempt < 10 ? 1000 : 2000)
        } else {
          setScanStatus("failed")
          setScanError(err instanceof Error ? err.message : "Polling failed")
          setScanJobId(null)
        }
      }
    }
    poll(0)
  }, [bookId])

  useEffect(() => {
    return () => {
      if (scanPollRef.current) clearTimeout(scanPollRef.current)
    }
  }, [])
  const suggestions = suggestionsPayload?.suggestions ?? []
  const suggestionsMeta = suggestionsPayload?.meta ?? defaultScanMeta

  const [tab, setTab] = useState<AdvisorPanel>("checker")
  const [autoOpenedScan, setAutoOpenedScan] = useState(false)
  const [messages, setMessages] = useState<AdvisorMessage[]>([])
  const [passages, setPassages] = useState<AdvisorPassage[]>([])
  const [worldAnalysis, setWorldAnalysis] = useState<AdvisorWorldAnalysis | null>(null)
  const [input, setInput] = useState("")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [responseTypes, setResponseTypes] = useState<ResponseType[]>([]) // per-assistant message

  const [dismissedIds, setDismissedIds] = useState<Set<string>>(new Set())
  const [intentionalIds, setIntentionalIds] = useState<Set<string>>(new Set())
  const [sugTab, setSugTab] = useState<"scan" | "editorial">("scan")
  const [noteToast, setNoteToast] = useState<string | null>(null)

  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    capture("author_advisor_opened", { book_id: bookId })
  }, [bookId])

  useEffect(() => {
    if (canUseAuthorMode || tab !== "suggestions") return
    setTab("checker")
  }, [canUseAuthorMode, tab])

  useEffect(() => {
    if (!canUseAuthorMode || autoOpenedScan || tab !== "checker" || !suggestionsPayload || suggestionsPayload.suggestions.length === 0) return
    setTab("suggestions")
    setAutoOpenedScan(true)
  }, [autoOpenedScan, canUseAuthorMode, suggestionsPayload, tab])

  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(scanStorageKey(bookId))
      if (!raw) return
      const parsed = JSON.parse(raw) as { dismissed?: string[]; intentional?: string[] }
      setDismissedIds(new Set(parsed.dismissed ?? []))
      setIntentionalIds(new Set(parsed.intentional ?? []))
    } catch {
      setDismissedIds(new Set())
      setIntentionalIds(new Set())
    }
  }, [bookId])

  useEffect(() => {
    try {
      window.localStorage.setItem(
        scanStorageKey(bookId),
        JSON.stringify({
          dismissed: [...dismissedIds],
          intentional: [...intentionalIds],
        })
      )
    } catch {
      // localStorage unavailable (e.g. test environment)
    }
  }, [bookId, dismissedIds, intentionalIds])

  // Auto-scroll chat
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages, loading])

  const sendMessage = useCallback(async (text: string) => {
    if (!text.trim() || loading) return
    const userMsg: AdvisorMessage = { role: "user", content: text.trim() }
    const next = [...messages, userMsg]
    setMessages(next)
    setInput("")
    setError(null)
    setLoading(true)
    try {
      const res = await intelligenceApi.advisorMessageStream(
        bookId,
        next,
        greeting?.stats.total_chapters ?? 9999,
        {
          onDelta: (content) => {
            if (!content) return
            setMessages(prev => {
              const last = prev[prev.length - 1]
              if (last?.role === "assistant") {
                return [...prev.slice(0, -1), { ...last, content: `${last.content}${content}` }]
              }
              return [...prev, { role: "assistant", content }]
            })
          },
        }
      )
      setMessages(prev => {
        const last = prev[prev.length - 1]
        if (last?.role === "assistant") {
          return [...prev.slice(0, -1), { role: "assistant", content: res.reply }]
        }
        return [...prev, { role: "assistant", content: res.reply }]
      })
      setPassages(res.retrieved_passages)
      setWorldAnalysis(res.world_analysis ?? null)
      setResponseTypes(prev => [...prev, (res.response_type ?? "standard") as ResponseType])
    } catch (err: unknown) {
      const dailyCap = buildDailyCapEventDetail(err)
      const msg = err instanceof Error ? err.message : ""
      if (dailyCap) {
        setError(canUseAuthorMode ? "You reached today's Story Advisor limit. Upgrade for more daily capacity or continue tomorrow." : "You reached this week's free Story Advisor turn. Upgrade for more capacity.")
      } else if (msg.includes("429")) {
        setError("Too many Story Advisor requests right now. Please try again in a bit.")
      } else if (msg.includes("403")) {
        setError("This advisor action requires an active trial, Author, or Architect plan.")
      } else {
        setError("The advisor couldn't respond. Try again.")
      }
    } finally {
      setLoading(false)
      inputRef.current?.focus()
    }
  }, [bookId, canUseAuthorMode, greeting, loading, messages])

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      sendMessage(input)
    }
  }

  const handleSuggestionAsk = (prompt: string) => {
    setTab("checker")
    setInput(prompt)
    setTimeout(() => inputRef.current?.focus(), 100)
  }

  const refreshSuggestions = useCallback(() => {
    void startScan()
  }, [startScan])

  const dismissSuggestion = (id: string) => setDismissedIds(prev => new Set([...prev, id]))
  const markIntentional = (id: string) => {
    setIntentionalIds(prev => new Set([...prev, id]))
    setDismissedIds(prev => new Set([...prev, id]))
  }

  const saveQuickNote = useCallback(async (payload: { chapterNumber: number | null; title: string | null; body: string }) => {
    try {
      await saveContextualVaultNote({
        bookId,
        title: payload.title?.trim() || "Advisor note",
        content: payload.body,
        context: "story_advisor",
        folderSegments: payload.chapterNumber ? [`Chapter ${payload.chapterNumber}`] : [],
      })
      setNoteToast(`Saved to Story Advisor${payload.chapterNumber ? ` / Chapter ${payload.chapterNumber}` : ""}.`)
    } catch {
      setNoteToast("Could not save note. Please try again.")
    } finally {
      window.setTimeout(() => setNoteToast(null), 2400)
    }
  }, [bookId])

  const visibleSuggestions = suggestions.filter(s => !dismissedIds.has(s.id))
  const warnCount = visibleSuggestions.filter(s => s.severity === "warning").length
  const allSuggestionsDismissed = suggestions.length > 0 && visibleSuggestions.length === 0

  // Group suggestions for display
  const grouped = {
    warning: visibleSuggestions.filter(s => s.severity === "warning"),
    direction: visibleSuggestions.filter(s => s.severity === "direction"),
    opportunity: visibleSuggestions.filter(s => s.severity === "opportunity"),
    info: visibleSuggestions.filter(s => s.severity === "info"),
  }

  // Count assistant messages to pair with responseTypes
  let assistantIdx = -1

  return (
    <>
      <style>{`
        @keyframes fadeSlideIn {
          from { opacity: 0; transform: translateY(6px); }
          to   { opacity: 1; transform: translateY(0); }
        }
      `}</style>

      <div className={`min-h-screen ${isDark ? "bg-[#071211] text-slate-100" : "bg-stone-50 text-stone-950"}`}>

        {noteToast ? (
          <div className="fixed bottom-5 left-1/2 z-50 w-[min(92vw,32rem)] -translate-x-1/2">
            <div className={`rounded-full border px-4 py-2 text-center text-sm font-medium shadow-lg ${isDark ? "border-white/10 bg-black/80 text-slate-200" : "border-stone-200 bg-white text-stone-700"}`}>
              {noteToast}
            </div>
          </div>
        ) : null}

        <div className="mx-auto max-w-[84rem] px-4 py-8 sm:px-6 lg:px-8 lg:pb-12">

          {/* Title */}
          <WorkspaceFamilyHeader
            active="advisor"
            bookId={bookId}
            family="review-center"
            title="Story advisor"
            description="Ask about lore, canon, world gaps, and story logic. The advisor counters contradictions, surfaces foreshadowing, and explains the tradeoffs behind story decisions."
            actions={
              canUseAuthorMode ? (
                <Link
                  href={`/${bookId}/notes`}
                  className={`inline-flex items-center justify-center rounded-md border px-4 py-3 text-sm font-medium transition ${isDark ? "border-teal-500/35 bg-teal-500/8 text-teal-100 hover:bg-teal-500/12" : "border-stone-300 bg-white text-stone-900 hover:bg-stone-50"}`}
                >
                  Open notes workspace
                </Link>
              ) : null
            }
          />

          {!canUseAuthorMode ? (
            <div className={`mb-6 rounded-lg border px-5 py-4 text-sm leading-6 ${isDark ? "border-amber-400/25 bg-amber-400/10 text-amber-100" : "border-amber-200 bg-amber-50 text-amber-800"}`} role="status">
              Free accounts include one Story Advisor turn per week. Continuity scans, editorial review, saved advisor notes, and deeper author tools require an active trial, Author, or Architect plan.
            </div>
          ) : null}

          {/* Tab switcher */}
          <div role="tablist" aria-label="Story Advisor mode" className={`mb-8 inline-flex flex-wrap overflow-hidden rounded-md border p-1 ${isDark ? "border-white/10 bg-white/5" : "border-stone-200 bg-white"}`}>
            <Button
              variant={tab === "checker" ? "primary" : "ghost"}
              size="md"
              id="advisor-tab-chat"
              role="tab"
              aria-selected={tab === "checker"}
              aria-controls="advisor-checker-panel"
              onClick={() => setTab("checker")}
              className="rounded-sm"
            >
              Continuity Checker
            </Button>
            {canUseAuthorMode ? (
              <Button
                variant={tab === "suggestions" ? "primary" : "ghost"}
                size="md"
                id="advisor-tab-scan"
                role="tab"
                aria-selected={tab === "suggestions"}
                aria-controls="advisor-scan-panel"
                onClick={() => setTab("suggestions")}
                className="relative rounded-sm"
              >
                Continuity Scan
                {warnCount > 0 && (
                  <span className="absolute -right-1 -top-1 flex h-4 w-4 items-center justify-center rounded-full bg-amber-500 text-3xs font-bold text-white">
                    {warnCount}
                  </span>
                )}
              </Button>
            ) : null}
          </div>

          {/* Chat tab */}
          {tab === "checker" && (
            <div id="advisor-checker-panel" role="tabpanel" aria-labelledby="advisor-tab-chat" className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_22rem]">

              {/* Chat area */}
              <StoryAdvisorSurface isDark={isDark} className="flex min-h-[62vh] flex-col overflow-hidden">
                <div className={`border-b px-5 py-4 ${isDark ? "border-white/[0.08] bg-[#0d1524]/72" : "border-stone-100"}`}>
                  <StoryAdvisorSectionLabel tone="slate">Continuity Checker</StoryAdvisorSectionLabel>
                  <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-400" : "text-stone-500"}`}>
                    Ask targeted questions about contradictions, lore gaps, world rules, endings, and tradeoffs. The advisor preserves the current conversation flow and answer formatting.
                  </p>
                </div>
                <div className="flex-1 overflow-y-auto px-4 py-5 sm:px-5" style={{ maxHeight: "60vh" }}>
                  <div className="mx-auto w-full max-w-[52rem] space-y-4">

                  {/* Opening question */}
                  {messages.length === 0 && (
                    <div className={`rounded-lg border px-5 py-5 ${isDark ? "border-violet-500/20 bg-violet-500/8" : "border-violet-100 bg-violet-50"}`}>
                      <StoryAdvisorSectionLabel tone="violet">Story Advisor</StoryAdvisorSectionLabel>
                      <p className={`text-base leading-7 ${isDark ? "text-slate-200" : "text-stone-700"}`}>
                        {greeting?.message ?? "What aspect of your story feels unsolved right now?"}
                      </p>
                      <div className="mt-4 flex flex-wrap gap-2">
                        {ADVISOR_STARTER_PROMPTS.map(prompt => (
                          <Button
                            key={prompt}
                            variant="ghost"
                            size="sm"
                            onClick={() => void sendMessage(prompt)}
                            className="rounded-sm"
                          >
                            {prompt}
                          </Button>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Message list */}
                  {messages.map((msg, i) => {
                    const isAssistant = msg.role === "assistant"
                    if (isAssistant) assistantIdx++
                    const rType: ResponseType = isAssistant
                      ? (responseTypes[assistantIdx] ?? "standard")
                      : "standard"
                    const style = isAssistant ? responseTypeStyle(rType, isDark) : null

                    return (
                      <div
                        key={i}
                        style={{ animationName: "fadeSlideIn", animationDuration: "0.25s", animationFillMode: "both" }}
                        className={isAssistant
                          ? `rounded-md border p-5 ${style!.border} ${style!.bg}`
                          : `ml-auto max-w-[36rem] rounded-md border px-5 py-4 ${isDark ? "border-violet-500/30 bg-violet-500/18" : "border-violet-200 bg-violet-600/12"}`
                        }
                      >
                        {isAssistant && (
                          <div className="flex items-center gap-2 mb-3">
                            <span className={`text-3xs font-semibold uppercase tracking-[0.26em] px-2 py-0.5 rounded-full ${style!.badge}`}>
                              {style!.label}
                            </span>
                          </div>
                        )}
                        {isAssistant ? (
                          <div className="space-y-4">
                            <RichMessage content={msg.content} isDark={isDark} />
                            <div className="flex flex-wrap gap-2">
                              {buildReplyFollowUps(rType).map((prompt) => (
                                <Button
                                  key={`${i}-${prompt}`}
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => void sendMessage(prompt)}
                                  disabled={loading}
                                  className="rounded-sm"
                                >
                                  {prompt}
                                </Button>
                              ))}
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => void saveQuickNote({
                                  chapterNumber: null,
                                  title: "Advisor insight",
                                  body: msg.content,
                                })}
                                className="rounded-sm"
                              >
                                Save to notes
                              </Button>
                            </div>
                          </div>
                        ) : (
                          <p className={`text-sm leading-7 whitespace-pre-wrap ${isDark ? "text-slate-200" : "text-stone-700"}`}>
                            {msg.content}
                          </p>
                        )}
                      </div>
                    )
                  })}

                  {/* Loading */}
                  {loading && (
                    <div className={`rounded-md border p-5 ${isDark ? "border-white/[0.08] bg-white/[0.04]" : "border-stone-100 bg-stone-50"}`} role="status" aria-label="Loading advisor response" aria-busy="true">
                      <span className="sr-only">Loading advisor response</span>
                      <Skeleton className="mb-3 h-2.5 w-24 rounded-full" />
                      <Skeleton className="mb-2 h-2.5 w-full rounded-full" />
                      <Skeleton className="mb-2 h-2.5 w-3/4 rounded-full" />
                      <Skeleton className="h-2.5 w-1/2 rounded-full" />
                    </div>
                  )}

                  {error && (
                    <p className={`text-sm px-2 py-2 rounded-sm ${isDark ? "text-amber-300 bg-amber-500/10 border border-amber-500/20" : "text-red-600 bg-red-50 border border-red-200"}`}>
                      {error}
                    </p>
                  )}

                    <div ref={bottomRef} />
                  </div>
                </div>

                {/* Input bar */}
                <div className={`border-t px-4 py-4 ${isDark ? "border-white/[0.08] bg-[#09101b]" : "border-stone-100"}`}>
                  <div className="mx-auto w-full max-w-[52rem]">
                    <div className={`rounded-md border px-4 py-3 ${isDark ? "border-white/10 bg-[#0b1322]" : "border-stone-200 bg-stone-50"} transition`}>
                      <div className="flex items-end gap-3">
                    <textarea
                      ref={inputRef}
                      id="advisor-input"
                      value={input}
                      onChange={e => setInput(e.target.value)}
                      onKeyDown={handleKeyDown}
                      rows={2}
                      disabled={loading}
                      aria-label="Advisor question"
                      className={`flex-1 resize-none bg-transparent text-sm leading-6 outline-none ${isDark ? "text-slate-100" : "text-stone-800"}`}
                    />
                    <Button
                      id="advisor-send"
                      variant="primary"
                      size="md"
                      onClick={() => void sendMessage(input)}
                      disabled={!input.trim() || loading}
                      className="shrink-0 rounded-sm bg-violet-600 hover:bg-violet-500"
                    >
                      {loading ? "..." : "Send"}
                    </Button>
                    </div>
                    <p className={`mt-2 text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>Ask about plotholes, lore gaps, world rules, arc endings, or consistency issues.</p>
                  </div>
                  <p className={`mt-2 text-3xs ${isDark ? "text-slate-600" : "text-stone-400"}`}>
                    Enter to send / Shift+Enter for new line / Contradictions and world gaps flagged automatically
                  </p>
                </div>
                </div>
              </StoryAdvisorSurface>

              {/* Right panel: retrieved passages + how it works */}
              <div className="space-y-4">
                {worldAnalysis ? (
                  <div className={`rounded-lg border p-5 ${isDark ? "border-emerald-500/20 bg-emerald-500/6" : "border-emerald-200 bg-emerald-50"}`}>
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p className={`text-3xs font-semibold uppercase tracking-[0.28em] ${isDark ? "text-emerald-300" : "text-emerald-700"}`}>
                        World analysis
                      </p>
                      <span className={`rounded-full px-2.5 py-1 text-3xs font-semibold uppercase tracking-[0.18em] ${isDark ? "bg-emerald-400/10 text-emerald-200" : "bg-white text-emerald-700"}`}>
                        {worldAnalysis.mode === "story_integration" ? "Integration" : "Gap detection"}
                      </span>
                    </div>
                    <p className={`mt-3 text-xs leading-6 line-clamp-5 ${isDark ? "text-emerald-50/80" : "text-emerald-950/75"}`}>
                      {worldAnalysis.answer}
                    </p>
                    {worldAnalysis.logic_alerts.length > 0 ? (
                      <div className="mt-4 space-y-2">
                        <p className={`text-3xs font-semibold uppercase tracking-[0.22em] ${isDark ? "text-emerald-300/80" : "text-emerald-800"}`}>Alerts</p>
                        {worldAnalysis.logic_alerts.slice(0, 3).map((item, index) => (
                          <div key={`world-alert-${index}`} className={`rounded-md border p-3 ${isDark ? "border-white/[0.08] bg-black/15" : "border-emerald-100 bg-white/70"}`}>
                            <p className={`text-xs font-semibold ${isDark ? "text-slate-100" : "text-stone-800"}`}>{worldItemTitle(item, `Alert ${index + 1}`)}</p>
                            {worldItemDescription(item) ? (
                              <p className={`mt-1 text-xs leading-5 ${isDark ? "text-slate-400" : "text-stone-600"}`}>{worldItemDescription(item)}</p>
                            ) : null}
                          </div>
                        ))}
                      </div>
                    ) : null}
                    {worldAnalysis.suggestions.length > 0 ? (
                      <div className="mt-4 space-y-2">
                        <p className={`text-3xs font-semibold uppercase tracking-[0.22em] ${isDark ? "text-emerald-300/80" : "text-emerald-800"}`}>Next moves</p>
                        {worldAnalysis.suggestions.slice(0, 3).map((item, index) => (
                          <div key={`world-suggestion-${index}`} className={`rounded-md border p-3 ${isDark ? "border-white/[0.08] bg-black/15" : "border-emerald-100 bg-white/70"}`}>
                            <p className={`text-xs font-semibold ${isDark ? "text-slate-100" : "text-stone-800"}`}>{worldItemTitle(item, `Suggestion ${index + 1}`)}</p>
                            {worldItemDescription(item) ? (
                              <p className={`mt-1 text-xs leading-5 ${isDark ? "text-slate-400" : "text-stone-600"}`}>{worldItemDescription(item)}</p>
                            ) : null}
                          </div>
                        ))}
                      </div>
                    ) : null}
                    {worldAnalysis.citations.length > 0 ? (
                      <div className="mt-4 flex flex-wrap gap-2">
                        {worldAnalysis.citations.slice(0, 4).map((citation, index) => (
                          <span key={`world-citation-${index}`} className={`rounded-full px-2.5 py-1 text-3xs font-medium ${isDark ? "bg-white/[0.08] text-slate-300" : "bg-white text-stone-600"}`}>
                            {worldItemTitle(citation, `Source ${index + 1}`)}
                          </span>
                        ))}
                      </div>
                    ) : null}
                  </div>
                ) : null}
                <StoryAdvisorSurface isDark={isDark} className="p-5">
                  <StoryAdvisorSectionLabel tone="teal">Retrieved Passages</StoryAdvisorSectionLabel>
                  <p className={`mt-1 mb-4 text-xs leading-5 ${isDark ? "text-slate-500" : "text-stone-400"}`}>
                    Manuscript sections the advisor used to answer your last question.
                  </p>
                  {passages.length === 0 ? (
                    <div className={`rounded-md border border-dashed p-5 text-center ${isDark ? "border-white/10 bg-black/10" : "border-stone-200 bg-stone-50"}`}>
                      <p className={`text-sm leading-6 ${isDark ? "text-slate-500" : "text-stone-400"}`}>
                        Send a message to see which passages were retrieved.
                      </p>
                    </div>
                  ) : (
                    <div className="space-y-3">
                      {passages.map((p, i) => (
                        <div key={i} className={`rounded-md border p-4 ${isDark ? "border-white/[0.08] bg-white/[0.03]" : "border-stone-100 bg-stone-50"}`}>
                          <div className="flex items-center justify-between mb-2">
                            <span className={`text-3xs font-semibold uppercase tracking-[0.22em] ${isDark ? "text-indigo-300" : "text-violet-600"}`}>
                              Ch. {p.chapter_num}{p.chapter_title ? `: ${p.chapter_title}` : ""}
                            </span>
                            <span className={`text-3xs tabular-nums ${isDark ? "text-slate-600" : "text-stone-400"}`}>
                              {Math.round(p.relevance * 100)}% match
                            </span>
                          </div>
                          <p className={`text-xs leading-5 line-clamp-4 ${isDark ? "text-slate-400" : "text-stone-600"}`}>
                            {p.excerpt}
                          </p>
                        </div>
                      ))}
                    </div>
                  )}
                </StoryAdvisorSurface>

                {/* Response type legend */}
                <StoryAdvisorSurface isDark={isDark} className="p-5">
                  <StoryAdvisorSectionLabel tone="slate">Response Types</StoryAdvisorSectionLabel>
                  <div className="space-y-2">
                    {RESPONSE_TYPE_LEGEND.map(({ icon, label, desc }) => (
                      <div key={label} className={`flex items-start gap-3 rounded-md border px-3 py-3 ${isDark ? "border-white/[0.08] bg-black/10" : "border-stone-200 bg-stone-50"}`}>
                        <span className={`mt-0.5 inline-flex min-w-[2.6rem] justify-center rounded-full px-2 py-1 text-3xs font-semibold ${icon === "WRN" ? "bg-amber-500/15 text-amber-300" : icon === "OPP" ? "bg-teal-500/15 text-teal-300" : icon === "TRD" ? "bg-violet-500/15 text-violet-300" : "bg-blue-500/15 text-blue-300"}`}>{icon}</span>
                        <div className="space-y-1">
                          <p className={`text-sm font-semibold ${isDark ? "text-slate-200" : "text-stone-700"}`}>{label}</p>
                          <p className={`text-xs ${isDark ? "text-slate-500" : "text-stone-400"}`}>{desc}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </StoryAdvisorSurface>
              </div>
            </div>
          )}

          {/* Suggestions tab */}
          {tab === "suggestions" && (
            <div id="advisor-scan-panel" role="tabpanel" aria-labelledby="advisor-tab-scan">

              {/* Sub-tab switcher */}
              <div className="hidden">
                <button
                  type="button"
                  id="suggestions-tab-scan"
                  onClick={() => setSugTab("scan")}
                  className={`px-5 py-2.5 text-sm font-medium transition ${sugTab === "scan" ? isDark ? "bg-white text-slate-950" : "bg-stone-900 text-white" : isDark ? "text-slate-300 hover:bg-white/[0.08]" : "text-stone-600 hover:bg-stone-50"}`}
                >
                  Continuity Scan
                </button>
                <button
                  type="button"
                  id="suggestions-tab-editorial"
                  onClick={() => setSugTab("editorial")}
                  className={`px-5 py-2.5 text-sm font-medium transition ${sugTab === "editorial" ? isDark ? "bg-white text-slate-950" : "bg-stone-900 text-white" : isDark ? "text-slate-300 hover:bg-white/[0.08]" : "text-stone-600 hover:bg-stone-50"}`}
                >
                  ✏️ Editorial Review
                </button>
              </div>

              {/* Continuity scan */}
              {sugTab === "scan" && (
                <div>
                  <div className="mb-5 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                    <p className={`max-w-2xl text-sm leading-7 ${isDark ? "text-slate-400" : "text-stone-500"}`}>
                      Proactive analysis of your manuscript, including structural issues, direction decisions, and foreshadowing
                      opportunities. Powered by extracted story data, not the full book.
                    </p>
                    <button
                      onClick={refreshSuggestions}
                      disabled={scanStatus === "scanning"}
                      className={`shrink-0 rounded-sm border px-4 py-2 text-xs font-medium transition disabled:opacity-50 ${isDark ? "border-white/10 bg-white/5 text-slate-300 hover:bg-white/10" : "border-stone-200 bg-white text-stone-600 hover:bg-stone-50"}`}
                    >
                      {scanStatus === "scanning" ? "Scanning..." : "Check Story Health"}
                    </button>
                  </div>

                  <StoryAdvisorSurface isDark={isDark} className="mb-6 p-4 sm:p-5">
                    <div className="flex flex-wrap items-center gap-2">
                      <StoryAdvisorSectionLabel tone="slate">Heuristic Summary</StoryAdvisorSectionLabel>
                      {suggestionsMeta.fallback_applied ? (
                        <span className={`rounded-full px-2.5 py-1 text-3xs font-semibold uppercase tracking-[0.18em] ${isDark ? "bg-teal-500/15 text-teal-200" : "bg-teal-100 text-teal-700"}`}>
                          Fallback Cards
                        </span>
                      ) : null}
                    </div>
                    <div className="mt-3 flex flex-wrap items-center gap-2">
                      <span className={`rounded-full px-2.5 py-1 text-3xs font-semibold uppercase tracking-[0.18em] ${isDark ? "bg-white/[0.08] text-slate-300" : "bg-stone-100 text-stone-700"}`}>
                        {suggestionsMeta.heuristic_count} heuristic card{suggestionsMeta.heuristic_count === 1 ? "" : "s"}
                      </span>
                      {suggestionsMeta.proactive_audit_applied ? (
                        <span className={`rounded-full px-2.5 py-1 text-3xs font-semibold uppercase tracking-[0.18em] ${isDark ? "bg-teal-500/15 text-teal-200" : "bg-teal-100 text-teal-700"}`}>
                          Proactive audit added
                        </span>
                      ) : null}
                    </div>
                    <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
                      {[
                        { label: "Characters", value: suggestionsMeta.character_count, kind: "characters" as const },
                        { label: "States", value: suggestionsMeta.state_count, kind: "states" as const },
                        { label: "Open Threads", value: suggestionsMeta.open_thread_count, kind: "open_threads" as const },
                        { label: "Clues", value: suggestionsMeta.clue_count, kind: "clues" as const },
                        { label: "Relationships", value: suggestionsMeta.relationship_count, kind: "relationships" as const },
                        { label: "World Elements", value: suggestionsMeta.world_element_count, kind: "world_elements" as const },
                      ].map((item) => (
                        <div key={item.label} className={`rounded-md border px-3 py-3 ${isDark ? "border-white/[0.08] bg-black/20" : "border-stone-100 bg-stone-50"}`}>
                          <div className="flex items-center gap-3">
                            <div className={`${isDark ? "text-teal-300" : "text-teal-700"}`}>
                              <StoryAdvisorIcon kind={item.kind} />
                            </div>
                            <div className="min-w-0">
                              <p className={`text-3xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>{item.label}</p>
                              <p className={`mt-1 text-lg font-semibold leading-none ${isDark ? "text-slate-100" : "text-stone-900"}`}>{item.value}</p>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                    <p className={`mt-3 text-xs leading-5 ${isDark ? "text-slate-400" : "text-stone-500"}`}>
                      Data sources: {suggestionsMeta.scan_basis.length > 0 ? suggestionsMeta.scan_basis.join(", ") : "none yet"}.
                      {suggestionsMeta.data_gaps.length > 0 ? ` Missing: ${suggestionsMeta.data_gaps.join(", ")}.` : ""}
                    </p>
                    {suggestionsMeta.audit_summary ? (
                      <p className={`mt-2 text-xs leading-5 ${isDark ? "text-teal-200" : "text-teal-800"}`}>{suggestionsMeta.audit_summary}</p>
                    ) : null}
                  </StoryAdvisorSurface>

                  {suggestionsLoading || scanStatus === "scanning" ? (
                    <div className="space-y-3">
                      {scanStatus === "scanning" && (
                        <div className={`mb-3 rounded-md border px-4 py-3 ${isDark ? "border-violet-500/30 bg-violet-500/10" : "border-violet-200 bg-violet-50"}`} role="status" aria-label="Running continuity scan" aria-busy="true">
                          <span className="sr-only">Running continuity scan across extracted story data</span>
                          <Skeleton className="h-4 w-72 max-w-full" />
                          <Skeleton className="mt-2 h-3 w-96 max-w-full" />
                        </div>
                      )}
                      {[1, 2, 3].map(i => (
                        <Skeleton key={i} variant="card" className={`h-28 rounded-lg border ${isDark ? "border-white/[0.08] bg-white/[0.04]" : "border-stone-100 bg-stone-50"}`} />
                      ))}
                    </div>
                  ) : scanStatus === "failed" && scanError ? (
                    <div className={`rounded-lg border p-6 ${isDark ? "border-red-500/30 bg-red-500/10" : "border-red-200 bg-red-50"}`}>
                      <p className={`text-sm font-medium ${isDark ? "text-red-300" : "text-red-700"}`}>Scan failed</p>
                      <p className={`mt-1 text-xs leading-5 ${isDark ? "text-red-200" : "text-red-600"}`}>{scanError}</p>
                      <button
                        onClick={() => void startScan()}
                        className={`mt-3 rounded-sm border px-4 py-2 text-xs font-medium transition ${isDark ? "border-white/10 bg-white/5 text-slate-300 hover:bg-white/10" : "border-stone-200 bg-white text-stone-600 hover:bg-stone-50"}`}
                      >
                        Retry
                      </button>
                    </div>
                  ) : suggestionsPayload === null ? (
                    <StoryAdvisorEmptyState title="Scan could not load" body="The continuity scan could not be loaded right now." isDark={isDark} accent="danger" />
                  ) : allSuggestionsDismissed ? (
                    <StoryAdvisorEmptyState title="All current scan cards are dismissed" body="Refresh after your next extraction pass to pull a new scan." isDark={isDark} />
                  ) : visibleSuggestions.length === 0 ? (
                    <StoryAdvisorEmptyState title="No active scan findings" body="The scan did not surface active cards from the current manuscript data. Refresh after your next extraction pass or run a proactive story audit from the checker." isDark={isDark} accent="success" />
                  ) : (
                    <div className="space-y-8">
                      <SuggestionGroup label="Warnings" icon="WRN" items={grouped.warning} isDark={isDark} onAsk={handleSuggestionAsk} onSaveNote={saveQuickNote} onMarkIntentional={markIntentional} onDismiss={dismissSuggestion} />
                      <SuggestionGroup label="Future Direction" icon="DIR" items={grouped.direction} isDark={isDark} onAsk={handleSuggestionAsk} onSaveNote={saveQuickNote} onMarkIntentional={markIntentional} onDismiss={dismissSuggestion} />
                      <SuggestionGroup label="Opportunities" icon="OPP" items={grouped.opportunity} isDark={isDark} onAsk={handleSuggestionAsk} onSaveNote={saveQuickNote} onMarkIntentional={markIntentional} onDismiss={dismissSuggestion} />
                      <SuggestionGroup label="Info" icon="INF" items={grouped.info} isDark={isDark} onAsk={handleSuggestionAsk} onSaveNote={saveQuickNote} onMarkIntentional={markIntentional} onDismiss={dismissSuggestion} />

                      {intentionalIds.size > 0 && (
                        <div className={`rounded-lg border p-5 ${isDark ? "border-white/[0.08] bg-white/[0.03]" : "border-stone-100 bg-stone-50"}`}>
                          <p className={`text-3xs font-semibold uppercase tracking-[0.24em] mb-1 ${isDark ? "text-slate-500" : "text-stone-400"}`}>
                            Intentional choices ({intentionalIds.size})
                          </p>
                          <p className={`text-xs leading-5 ${isDark ? "text-slate-500" : "text-stone-400"}`}>
                            {intentionalIds.size} suggestion{intentionalIds.size !== 1 ? "s" : ""} marked as deliberate authorial decisions. These won't reappear in future scans.
                          </p>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}

              {/* Editorial review */}
              {sugTab === "editorial" && (
                <StoryAdvisorEditorialPanel
                  bookId={bookId}
                  isDark={isDark}
                  canUseAuthorMode={canUseAuthorMode}
                  onSaveNote={saveQuickNote}
                />
              )}
            </div>
          )}
        </div>
      </div>
    </>
  )
}
