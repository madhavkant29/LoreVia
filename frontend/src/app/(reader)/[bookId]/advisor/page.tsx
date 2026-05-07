"use client"

import { Fragment, useCallback, useEffect, useRef, useState } from "react"
import Link from "next/link"
import { useParams } from "next/navigation"
import { booksApi } from "@/lib/api/books"
import { intelligenceApi } from "@/lib/api/intelligence"
import { canUseAuthorFeatures } from "@/lib/billing/plans"
import { useAuthStore } from "@/lib/stores/authStore"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import { capture } from "@/lib/analytics/posthog"
import { saveContextualVaultNote } from "@/lib/utils/notes"
import type {
  AdvisorMessage,
  AdvisorPassage,
  AdvisorSuggestion,
  AdvisorGreeting,
  AdvisorWorldAnalysis,
  EditorialReview,
  EditorialReviewPassage,
} from "@/types/intelligence"

// ─── Response type visual config (4 variants) ────────────────────────────────
type ResponseType = "standard" | "warning" | "opportunity" | "tradeoff"
type AdvisorPanel = "checker" | "suggestions"

function responseTypeStyle(type: ResponseType, isDark: boolean) {
  switch (type) {
    case "warning":
      return {
        border: isDark ? "border-amber-500/35" : "border-amber-400/60",
        bg: isDark ? "bg-amber-500/8" : "bg-amber-50",
        badge: isDark ? "bg-amber-500/20 text-amber-300" : "bg-amber-100 text-amber-700",
        label: "Contradiction",
        glow: isDark ? "shadow-[0_0_20px_-8px_rgba(245,158,11,0.4)]" : "",
      }
    case "opportunity":
      return {
        border: isDark ? "border-teal-500/35" : "border-teal-400/60",
        bg: isDark ? "bg-teal-500/8" : "bg-teal-50",
        badge: isDark ? "bg-teal-500/20 text-teal-300" : "bg-teal-100 text-teal-700",
        label: "Opportunity",
        glow: isDark ? "shadow-[0_0_20px_-8px_rgba(20,184,166,0.4)]" : "",
      }
    case "tradeoff":
      return {
        border: isDark ? "border-violet-500/35" : "border-violet-400/60",
        bg: isDark ? "bg-violet-500/8" : "bg-violet-50",
        badge: isDark ? "bg-violet-500/20 text-violet-300" : "bg-violet-100 text-violet-700",
        label: "Tradeoff",
        glow: isDark ? "shadow-[0_0_20px_-8px_rgba(139,92,246,0.4)]" : "",
      }
    default:
      return {
        border: isDark ? "border-white/10" : "border-stone-200",
        bg: isDark ? "bg-white/4" : "bg-white",
        badge: isDark ? "bg-white/12 text-slate-300" : "bg-stone-100 text-stone-500",
        label: "Response",
        glow: "",
      }
  }
}

// ─── Severity config (Suggestions) ───────────────────────────────────────────
function severityConfig(severity: string) {
  switch (severity) {
    case "warning":
      return {
        icon: "WRN",
        color: "border-amber-500/30 bg-amber-500/8",
        badge: "bg-amber-500/20 text-amber-300",
        dot: "bg-amber-400",
        label: "Warning",
      }
    case "direction":
      return {
        icon: "DIR",
        color: "border-violet-500/30 bg-violet-500/8",
        badge: "bg-violet-500/20 text-violet-300",
        dot: "bg-violet-400",
        label: "Future Direction",
      }
    case "opportunity":
      return {
        icon: "OPP",
        color: "border-teal-500/30 bg-teal-500/8",
        badge: "bg-teal-500/20 text-teal-300",
        dot: "bg-teal-400",
        label: "Opportunity",
      }
    default:
      return {
        icon: "INF",
        color: "border-blue-500/30 bg-blue-500/8",
        badge: "bg-blue-500/20 text-blue-300",
        dot: "bg-blue-400",
        label: "Info",
      }
  }
}

function buildReplyFollowUps(responseType: ResponseType) {
  switch (responseType) {
    case "warning":
      return [
        "How can I fix this without breaking continuity?",
        "What setup should I add earlier to support this?",
        "Is this contradiction salvageable if I make it intentional?",
      ]
    case "opportunity":
      return [
        "What foreshadowing beats should I plant now?",
        "How can I turn this into a stronger payoff?",
        "Which character best carries this opportunity?",
      ]
    case "tradeoff":
      return [
        "Which option best fits the manuscript so far?",
        "What would each ending cost thematically?",
        "What setup is missing for the strongest option?",
      ]
    default:
      return [
        "Are there any plotholes I should know about?",
        "Are my world rules creating any gaps?",
        "Help me think through how to end the current arc.",
      ]
  }
}

function compactWorldText(value: unknown, fallback = ""): string {
  if (typeof value === "string") return value.trim()
  if (typeof value === "number") return String(value)
  if (Array.isArray(value)) return value.map(item => compactWorldText(item)).filter(Boolean).join(", ")
  return fallback
}

function worldItemTitle(item: Record<string, unknown>, fallback: string): string {
  return compactWorldText(item.title)
    || compactWorldText(item.element_name)
    || compactWorldText(item.name)
    || compactWorldText(item.category)
    || fallback
}

function worldItemDescription(item: Record<string, unknown>): string {
  return compactWorldText(item.description)
    || compactWorldText(item.problem)
    || compactWorldText(item.suggested_fix)
    || compactWorldText(item.what_to_add)
}

function renderInlineFormatting(text: string) {
  const parts = text.split(/(\*\*[^*]+\*\*)/)
  return parts.map((part, index) => {
    if (part.startsWith("**") && part.endsWith("**") && part.length > 4) {
      return <strong key={index} className="font-semibold">{part.slice(2, -2)}</strong>
    }
    return <Fragment key={index}>{part}</Fragment>
  })
}

function renderFormattedTextBlock(text: string) {
  return text.split("\n").map((line, index) => (
    <Fragment key={index}>
      {index > 0 ? <br /> : null}
      {renderInlineFormatting(line)}
    </Fragment>
  ))
}

// ─── Rich message renderer ────────────────────────────────────────────────────
// Parses structured contradiction, opportunity, and option blocks out of plain text.
// and renders them with distinct visual treatment.
function RichMessage({ content, isDark }: { content: string; isDark: boolean }) {
  // Split on block starters while keeping the delimiter
  const lines = content.split("\n")
  const segments: { type: "text" | "warning" | "opportunity" | "tradeoff"; lines: string[] }[] = []
  let current: (typeof segments)[0] | null = null

  for (const line of lines) {
    const trimmed = line.trim()
    if (/^(?:[^\w\s]+)?\s*Contradiction\b/i.test(trimmed)) {
      if (current) segments.push(current)
      current = { type: "warning", lines: [line] }
    } else if (/^(?:[^\w\s]+)?\s*Opportunity\b/i.test(trimmed)) {
      if (current) segments.push(current)
      current = { type: "opportunity", lines: [line] }
    } else if (/^(?:[^\w\s]+)?\s*Option\b/i.test(trimmed)) {
      if (current && current.type !== "tradeoff") segments.push(current)
      if (!current || current.type !== "tradeoff") current = { type: "tradeoff", lines: [] }
      current.lines.push(line)
    } else {
      if (!current) current = { type: "text", lines: [] }
      if (current.type === "text") {
        current.lines.push(line)
      } else {
        // Check if this is a continuation line for a structured block
        // (indented or part of the block pattern)
        current.lines.push(line)
      }
    }
  }
  if (current) segments.push(current)

  return (
    <div className="space-y-3">
      {segments.map((seg, i) => {
        const text = seg.lines.join("\n").trim()
        if (!text) return null

        if (seg.type === "warning") {
          return (
            <div key={i} className={`rounded-[0.9rem] border px-4 py-3 ${isDark ? "border-amber-500/30 bg-amber-500/10" : "border-amber-300 bg-amber-50"}`}>
              <p className={`text-sm leading-7 font-medium ${isDark ? "text-amber-100" : "text-amber-900"}`}>{renderFormattedTextBlock(text)}</p>
            </div>
          )
        }
        if (seg.type === "opportunity") {
          return (
            <div key={i} className={`rounded-[0.9rem] border px-4 py-3 ${isDark ? "border-teal-500/30 bg-teal-500/10" : "border-teal-300 bg-teal-50"}`}>
              <p className={`text-sm leading-7 font-medium ${isDark ? "text-teal-100" : "text-teal-900"}`}>{renderFormattedTextBlock(text)}</p>
            </div>
          )
        }
        if (seg.type === "tradeoff") {
          return (
            <div key={i} className={`rounded-[0.9rem] border px-4 py-3 ${isDark ? "border-violet-500/30 bg-violet-500/10" : "border-violet-200 bg-violet-50"}`}>
              <p className={`text-sm leading-7 font-medium ${isDark ? "text-violet-100" : "text-violet-900"}`}>{renderFormattedTextBlock(text)}</p>
            </div>
          )
        }
        return (
          <p key={i} className={`text-sm leading-7 ${isDark ? "text-slate-200" : "text-stone-700"}`}>{renderFormattedTextBlock(text)}</p>
        )
      })}
    </div>
  )
}

// ─── Suggestion group ─────────────────────────────────────────────────────────
function SuggestionGroup({
  label,
  icon,
  items,
  isDark,
  intentionalIds,
  onAsk,
  onSaveNote,
  onMarkIntentional,
  onDismiss,
}: {
  label: string
  icon: string
  items: AdvisorSuggestion[]
  isDark: boolean
  intentionalIds: Set<string>
  onAsk: (p: string) => void
  onSaveNote: (payload: { chapterNumber: number | null; title: string | null; body: string }) => void
  onMarkIntentional: (id: string) => void
  onDismiss: (id: string) => void
}) {
  if (items.length === 0) return null
  return (
    <div>
      <div className="flex items-center gap-2 mb-3">
        <span className="text-base">{icon}</span>
        <span className={`text-[11px] font-bold uppercase tracking-[0.3em] ${isDark ? "text-slate-400" : "text-stone-400"}`}>{label}</span>
        <span className={`ml-1 text-[10px] px-1.5 py-0.5 rounded-full font-semibold ${isDark ? "bg-white/8 text-slate-400" : "bg-stone-100 text-stone-400"}`}>{items.length}</span>
      </div>
      <div className="space-y-2.5">
        {items.map(s => {
          const cfg = severityConfig(s.severity)
          return (
            <div
              key={s.id}
              className={`rounded-[1.4rem] border p-5 transition-all duration-300 ${cfg.color}`}
              style={{ animationName: "fadeSlideIn", animationDuration: "0.3s", animationFillMode: "both" }}
            >
              <div className="flex items-start gap-3">
                <span className="text-xl shrink-0 mt-0.5">{cfg.icon}</span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap mb-1">
                    <span className={`text-[10px] font-semibold uppercase tracking-[0.22em] px-2 py-0.5 rounded-full ${cfg.badge}`}>
                      {s.type.replace(/_/g, " ")}
                    </span>
                    {s.chapter_ref && (
                      <span className={`text-[10px] ${isDark ? "text-slate-500" : "text-stone-400"}`}>
                        Ch. {s.chapter_ref}
                      </span>
                    )}
                  </div>
                  <p className={`font-semibold text-sm mb-2 ${isDark ? "text-white" : "text-stone-900"}`}>
                    {s.title}
                  </p>
                  <p className={`text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-600"}`}>
                    {s.description}
                  </p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <button
                      onClick={() => onAsk(s.ask_prompt)}
                      className={`rounded-[0.7rem] px-3 py-1.5 text-xs font-semibold transition ${isDark ? "bg-indigo-500/20 text-indigo-200 hover:bg-indigo-500/30" : "bg-violet-100 text-violet-700 hover:bg-violet-200"}`}
                    >
                      {s.action_label} →
                    </button>
                    <button
                      onClick={() => onSaveNote({
                        chapterNumber: typeof s.chapter_ref === "number" ? s.chapter_ref : null,
                        title: `Scan: ${s.title}`.slice(0, 120),
                        body: [
                          `Continuity scan (${s.severity}): ${s.title}`,
                          s.chapter_ref ? `Chapter: ${s.chapter_ref}` : "",
                          `Type: ${s.type.replace(/_/g, " ")}`,
                          "",
                          s.description,
                        ].filter(Boolean).join("\n"),
                      })}
                      className={`rounded-[0.7rem] px-3 py-1.5 text-xs font-semibold transition ${isDark ? "bg-white/10 text-slate-200 hover:bg-white/15" : "bg-white text-stone-700 hover:bg-stone-50"}`}
                    >
                      Save note
                    </button>
                    <button
                      onClick={() => onMarkIntentional(s.id)}
                      className={`rounded-[0.7rem] px-3 py-1.5 text-xs font-medium transition ${isDark ? "border border-white/10 bg-white/5 text-slate-400 hover:bg-white/10" : "border border-stone-200 bg-white text-stone-500 hover:bg-stone-50"}`}
                      title="Mark as a deliberate authorial choice that will not reappear"
                    >
                      Mark as intentional
                    </button>
                    <button
                      onClick={() => onDismiss(s.id)}
                      className={`rounded-[0.7rem] px-3 py-1.5 text-xs font-medium transition ${isDark ? "text-slate-600 hover:text-slate-400" : "text-stone-400 hover:text-stone-600"}`}
                    >
                      Dismiss
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}


// ─── Main page ────────────────────────────────────────────────────────────────
export default function AdvisorPage() {
  const { bookId } = useParams<{ bookId: string }>()
  const { theme } = usePreferencesStore()
  const userTier = useAuthStore((state) => state.user?.tier)
  const canUseAuthorMode = canUseAuthorFeatures(userTier)
  const isDark = theme === "dark"

  const [tab, setTab] = useState<AdvisorPanel>("checker")
  const [greeting, setGreeting] = useState<AdvisorGreeting | null>(null)
  const [messages, setMessages] = useState<AdvisorMessage[]>([])
  const [passages, setPassages] = useState<AdvisorPassage[]>([])
  const [worldAnalysis, setWorldAnalysis] = useState<AdvisorWorldAnalysis | null>(null)
  const [input, setInput] = useState("")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [bookMode, setBookMode] = useState<"reader" | "author">("author")
  const [responseTypes, setResponseTypes] = useState<ResponseType[]>([]) // per-assistant message

  const [suggestions, setSuggestions] = useState<AdvisorSuggestion[]>([])
  const [suggestionsLoading, setSuggestionsLoading] = useState(false)
  const [suggestionsLoaded, setSuggestionsLoaded] = useState(false)
  const [dismissedIds, setDismissedIds] = useState<Set<string>>(new Set())
  const [intentionalIds, setIntentionalIds] = useState<Set<string>>(new Set())

  const [sugTab, setSugTab] = useState<"scan" | "editorial">("scan")
  const [editText, setEditText] = useState("")
  const [editChapter, setEditChapter] = useState<string>("")
  const [editLoading, setEditLoading] = useState(false)
  const [editError, setEditError] = useState<string | null>(null)
  const [editResult, setEditResult] = useState<EditorialReview | null>(null)
  const [editPassages, setEditPassages] = useState<EditorialReviewPassage[]>([])
  const [importFiles, setImportFiles] = useState<File[]>([])
  const [replaceExisting, setReplaceExisting] = useState(false)
  const [chunkLongDocuments, setChunkLongDocuments] = useState(false)
  const [splitIntoChapters, setSplitIntoChapters] = useState(true)
  const [importLoading, setImportLoading] = useState(false)
  const [importMessage, setImportMessage] = useState<string | null>(null)
  const [noteToast, setNoteToast] = useState<string | null>(null)

  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  // Fetch greeting + suggestions on mount (badge needs count before tab opens)
  useEffect(() => {
    capture("author_advisor_opened", { book_id: bookId })
    booksApi.get(bookId).then((book) => setBookMode(book.mode ?? "author")).catch(() => {})
    intelligenceApi.advisorGreeting(bookId).then(setGreeting).catch(() => {})
    intelligenceApi.advisorSuggestions(bookId)
      .then(r => { setSuggestions(r.suggestions); setSuggestionsLoaded(true) })
      .catch(() => { setSuggestionsLoaded(true) })
  }, [bookId])

  // Auto-scroll chat
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages, loading])

  // Lazy-load suggestions when continuity scan opens if not loaded yet
  useEffect(() => {
    if (tab !== "suggestions" || suggestionsLoaded) return
    setSuggestionsLoading(true)
    intelligenceApi.advisorSuggestions(bookId)
      .then(r => setSuggestions(r.suggestions))
      .catch(() => setSuggestions([]))
      .finally(() => { setSuggestionsLoading(false); setSuggestionsLoaded(true) })
  }, [tab, bookId, suggestionsLoaded])

  const sendMessage = useCallback(async (text: string) => {
    if (!text.trim() || loading) return
    const userMsg: AdvisorMessage = { role: "user", content: text.trim() }
    const next = [...messages, userMsg]
    setMessages(next)
    setInput("")
    setError(null)
    setLoading(true)
    try {
      const res = await intelligenceApi.advisorMessage(
        bookId,
        next,
        greeting?.stats.total_chapters ?? 9999
      )
      setMessages(prev => [...prev, { role: "assistant", content: res.reply }])
      setPassages(res.retrieved_passages)
      setWorldAnalysis(res.world_analysis ?? null)
      setResponseTypes(prev => [...prev, (res.response_type ?? "standard") as ResponseType])
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : ""
      if (msg.includes("429")) {
        setError("Too many Story Advisor requests right now. Please try again in a bit.")
      } else {
        setError("The advisor couldn't respond. Try again.")
      }
    } finally {
      setLoading(false)
      inputRef.current?.focus()
    }
  }, [bookId, greeting, loading, messages])

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
    setSuggestions([])
    setSuggestionsLoaded(false)
    setSuggestionsLoading(true)
    intelligenceApi.advisorSuggestions(bookId)
      .then(r => setSuggestions(r.suggestions))
      .catch(() => setSuggestions([]))
      .finally(() => { setSuggestionsLoading(false); setSuggestionsLoaded(true) })
  }, [bookId])

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

      <div className={`min-h-screen ${isDark ? "bg-[linear-gradient(180deg,#000000_0%,#060606_44%,#0d0d0d_100%)] text-slate-100" : "bg-stone-50 text-stone-950"}`}>

        {noteToast ? (
          <div className="fixed bottom-5 left-1/2 z-50 w-[min(92vw,32rem)] -translate-x-1/2">
            <div className={`rounded-full border px-4 py-2 text-center text-sm font-medium shadow-lg ${isDark ? "border-white/10 bg-black/80 text-slate-200" : "border-stone-200 bg-white text-stone-700"}`}>
              {noteToast}
            </div>
          </div>
        ) : null}

        {/* ── Header ─────────────────────────────────────────────────────────── */}
        <header className={`sticky top-0 z-30 flex items-center justify-between px-4 py-3 backdrop-blur-xl border-b sm:px-6 ${isDark ? "border-white/8 bg-black/85" : "border-stone-200 bg-white/85"}`}>
          <div className="mx-auto max-w-7xl flex items-center justify-between w-full gap-4">
            <div className="flex items-center gap-3">
              <Link
                href={`/${bookId}`}
                className={`text-sm font-medium transition ${isDark ? "text-indigo-300 hover:text-indigo-200" : "text-violet-700 hover:text-violet-800"}`}
              >
                ← Overview
              </Link>
              <span className={`text-sm ${isDark ? "text-slate-600" : "text-stone-300"}`}>/</span>
              <span className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>
                Story Advisor
              </span>
            </div>

            <div className="hidden md:flex items-center gap-3">
              {greeting && (
                <>
                  <StatPill label="Characters" value={String(greeting.stats.characters)} isDark={isDark} />
                  <StatPill label="Plot threads" value={String(greeting.stats.plot_threads)} isDark={isDark} />
                  {greeting.stats.total_chapters && (
                    <StatPill label="Chapters" value={String(greeting.stats.total_chapters)} isDark={isDark} />
                  )}
                </>
              )}
            </div>
          </div>
        </header>

        <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8 lg:pb-10">

          {/* ── Title ─────────────────────────────────────────────────────────── */}
          <div className="mb-6 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <p className={`text-[11px] font-semibold uppercase tracking-[0.34em] ${isDark ? "text-indigo-300" : "text-violet-500"}`}>
                Author Intelligence
              </p>
              <h1 className={`mt-2 font-serif text-4xl leading-tight ${isDark ? "text-white" : "text-stone-950"}`}>
                Story Advisor
              </h1>
              <p className={`mt-2 max-w-xl text-sm leading-6 ${isDark ? "text-slate-400" : "text-stone-500"}`}>
                Ask anything about your manuscript, including lore, canon, world gaps, and story logic. The advisor will counter contradictions,
                surface foreshadowing, and walk you through the tradeoffs of every story decision.
              </p>
            </div>
            <Link
              href={`/${bookId}/notes`}
              className={`inline-flex items-center justify-center rounded-full px-4 py-2.5 text-sm font-medium ${isDark ? "bg-white/10 text-slate-100" : "bg-stone-900 text-white"}`}
            >
              Open notes workspace
            </Link>
          </div>

          {/* ── Tab switcher ──────────────────────────────────────────────────── */}
          <div className={`mb-6 inline-flex overflow-hidden rounded-[1rem] border ${isDark ? "border-white/10 bg-white/5" : "border-stone-200 bg-white"}`}>
            <button
              id="advisor-tab-chat"
              onClick={() => setTab("checker")}
              className={`px-5 py-2.5 text-sm font-medium transition ${tab === "checker" ? isDark ? "bg-white text-slate-950" : "bg-stone-900 text-white" : isDark ? "text-slate-300 hover:bg-white/8" : "text-stone-600 hover:bg-stone-50"}`}
            >
              Continuity Checker
            </button>
            <button
              id="advisor-tab-scan"
              onClick={() => { setTab("suggestions"); setSugTab("scan") }}
              className={`relative px-5 py-2.5 text-sm font-medium transition ${tab === "suggestions" && sugTab === "scan" ? isDark ? "bg-white text-slate-950" : "bg-stone-900 text-white" : isDark ? "text-slate-300 hover:bg-white/8" : "text-stone-600 hover:bg-stone-50"}`}
            >
              Continuity Scan
              {warnCount > 0 && (
                <span className="absolute -right-1 -top-1 flex h-4 w-4 items-center justify-center rounded-full bg-amber-500 text-[10px] font-bold text-white">
                  {warnCount}
                </span>
              )}
            </button>
            <button
              id="advisor-tab-editorial"
              onClick={() => { setTab("suggestions"); setSugTab("editorial") }}
              className={`px-5 py-2.5 text-sm font-medium transition ${tab === "suggestions" && sugTab === "editorial" ? isDark ? "bg-white text-slate-950" : "bg-stone-900 text-white" : isDark ? "text-slate-300 hover:bg-white/8" : "text-stone-600 hover:bg-stone-50"}`}
            >
              Editorial Review
            </button>
          </div>

          {/* ══ CHAT TAB ════════════════════════════════════════════════════════ */}
          {tab === "checker" && (
            <div className="grid gap-5 lg:grid-cols-[1fr_22rem]">

              {/* Chat area */}
              <div className={`flex flex-col overflow-hidden rounded-[1.8rem] border ${isDark ? "border-white/10 bg-black/80" : "border-stone-200 bg-white"}`} style={{ minHeight: "62vh" }}>
                <div className="flex-1 overflow-y-auto p-5 space-y-4" style={{ maxHeight: "60vh" }}>

                  {/* Opening question */}
                  {messages.length === 0 && (
                    <div className={`rounded-[1.2rem] border p-5 ${isDark ? "border-indigo-500/20 bg-indigo-500/8" : "border-violet-100 bg-violet-50"}`}>
                      <p className={`text-[11px] font-semibold uppercase tracking-[0.28em] mb-2 ${isDark ? "text-indigo-300" : "text-violet-500"}`}>Story Advisor</p>
                      <p className={`text-base leading-7 ${isDark ? "text-slate-200" : "text-stone-700"}`}>
                        {greeting?.message ?? "What aspect of your story feels unsolved right now?"}
                      </p>
                      <div className="mt-4 flex flex-wrap gap-2">
                        {[
                          "Are there any plotholes I should know about?",
                          "What foreshadowing opportunities am I missing?",
                          "Help me think through how to end the current arc.",
                          "Is there a consistency issue with my magic system?",
                          "I want to suddenly change the genre. Is that a good idea?",
                        ].map(prompt => (
                          <button
                            key={prompt}
                            onClick={() => void sendMessage(prompt)}
                            className={`rounded-[0.9rem] border px-3 py-1.5 text-xs font-medium transition ${isDark ? "border-white/10 bg-white/5 text-slate-200 hover:bg-white/12" : "border-stone-200 bg-white text-stone-700 hover:bg-stone-50"}`}
                          >
                            {prompt}
                          </button>
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
                          ? `rounded-[1.2rem] border p-5 ${style!.border} ${style!.bg} ${style!.glow}`
                          : `ml-auto max-w-[80%] rounded-[1.2rem] px-5 py-4 ${isDark ? "bg-indigo-600/30 border border-indigo-500/30" : "bg-violet-600/12 border border-violet-200"}`
                        }
                      >
                        {isAssistant && (
                          <div className="flex items-center gap-2 mb-3">
                            <span className={`text-[10px] font-semibold uppercase tracking-[0.26em] px-2 py-0.5 rounded-full ${style!.badge}`}>
                              {style!.label}
                            </span>
                          </div>
                        )}
                        {isAssistant ? (
                          <div className="space-y-4">
                            <RichMessage content={msg.content} isDark={isDark} />
                            <div className="flex flex-wrap gap-2">
                              {buildReplyFollowUps(rType).map((prompt) => (
                                <button
                                  key={`${i}-${prompt}`}
                                  onClick={() => void sendMessage(prompt)}
                                  disabled={loading}
                                  className={`rounded-[0.85rem] border px-3 py-1.5 text-xs font-medium transition disabled:opacity-40 ${isDark ? "border-white/10 bg-white/5 text-slate-200 hover:bg-white/12" : "border-stone-200 bg-white text-stone-700 hover:bg-stone-50"}`}
                                >
                                  {prompt}
                                </button>
                              ))}
                              <button
                                onClick={() => void saveQuickNote({
                                  chapterNumber: null,
                                  title: `Advisor insight`,
                                  body: msg.content,
                                })}
                                className={`rounded-[0.85rem] border px-3 py-1.5 text-xs font-medium transition ${isDark ? "border-white/10 bg-white/5 text-slate-400 hover:bg-white/10 hover:text-slate-200" : "border-stone-200 bg-white text-stone-400 hover:text-stone-700"}`}
                              >
                                Save to notes
                              </button>
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
                    <div className={`rounded-[1.2rem] border p-5 animate-pulse ${isDark ? "border-white/8 bg-white/4" : "border-stone-100 bg-stone-50"}`}>
                      <div className={`h-2.5 w-24 rounded-full mb-3 ${isDark ? "bg-white/10" : "bg-stone-200"}`} />
                      <div className={`h-2.5 w-full rounded-full mb-2 ${isDark ? "bg-white/8" : "bg-stone-100"}`} />
                      <div className={`h-2.5 w-3/4 rounded-full mb-2 ${isDark ? "bg-white/8" : "bg-stone-100"}`} />
                      <div className={`h-2.5 w-1/2 rounded-full ${isDark ? "bg-white/6" : "bg-stone-100"}`} />
                    </div>
                  )}

                  {error && (
                    <p className={`text-sm px-2 py-2 rounded-[0.8rem] ${isDark ? "text-amber-300 bg-amber-500/10 border border-amber-500/20" : "text-red-600 bg-red-50 border border-red-200"}`}>
                      {error}
                    </p>
                  )}

                  <div ref={bottomRef} />
                </div>

                {/* Input bar */}
                <div className={`border-t p-4 ${isDark ? "border-white/8" : "border-stone-100"}`}>
                  <div className={`flex items-end gap-3 rounded-[1.2rem] border px-4 py-3 ${isDark ? "border-white/10 bg-white/5 focus-within:border-indigo-500/50" : "border-stone-200 bg-stone-50 focus-within:border-violet-300"} transition`}>
                    <textarea
                      ref={inputRef}
                      id="advisor-input"
                      value={input}
                      onChange={e => setInput(e.target.value)}
                      onKeyDown={handleKeyDown}
                      placeholder="Ask about plotholes, lore gaps, world rules, arc endings, consistency issues..."
                      rows={2}
                      disabled={loading}
                      className={`flex-1 resize-none bg-transparent text-sm leading-6 outline-none ${isDark ? "text-slate-100 placeholder:text-slate-500" : "text-stone-800 placeholder:text-stone-400"}`}
                    />
                    <button
                      id="advisor-send"
                      onClick={() => void sendMessage(input)}
                      disabled={!input.trim() || loading}
                      className="shrink-0 rounded-[0.8rem] bg-[linear-gradient(135deg,#4f46e5,#4338ca)] px-4 py-2 text-sm font-semibold text-white shadow-[0_8px_24px_-12px_rgba(79,70,229,0.7)] transition disabled:opacity-40 hover:-translate-y-[1px]"
                    >
                      {loading ? "…" : "Send"}
                    </button>
                  </div>
                  <p className={`mt-2 text-[10px] ${isDark ? "text-slate-600" : "text-stone-400"}`}>
                    Enter to send · Shift+Enter for new line · Contradictions and world gaps flagged automatically
                  </p>
                </div>
              </div>

              {/* Right panel: retrieved passages + how it works */}
              <div className="space-y-4">
                {worldAnalysis ? (
                  <div className={`rounded-[1.8rem] border p-5 ${isDark ? "border-emerald-500/20 bg-emerald-500/6" : "border-emerald-200 bg-emerald-50"}`}>
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p className={`text-[11px] font-semibold uppercase tracking-[0.28em] ${isDark ? "text-emerald-300" : "text-emerald-700"}`}>
                        World analysis
                      </p>
                      <span className={`rounded-full px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] ${isDark ? "bg-emerald-400/10 text-emerald-200" : "bg-white text-emerald-700"}`}>
                        {worldAnalysis.mode === "story_integration" ? "Integration" : "Gap detection"}
                      </span>
                    </div>
                    <p className={`mt-3 text-xs leading-6 line-clamp-5 ${isDark ? "text-emerald-50/80" : "text-emerald-950/75"}`}>
                      {worldAnalysis.answer}
                    </p>
                    {worldAnalysis.logic_alerts.length > 0 ? (
                      <div className="mt-4 space-y-2">
                        <p className={`text-[10px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-emerald-300/80" : "text-emerald-800"}`}>Alerts</p>
                        {worldAnalysis.logic_alerts.slice(0, 3).map((item, index) => (
                          <div key={`world-alert-${index}`} className={`rounded-[1rem] border p-3 ${isDark ? "border-white/8 bg-black/15" : "border-emerald-100 bg-white/70"}`}>
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
                        <p className={`text-[10px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-emerald-300/80" : "text-emerald-800"}`}>Next moves</p>
                        {worldAnalysis.suggestions.slice(0, 3).map((item, index) => (
                          <div key={`world-suggestion-${index}`} className={`rounded-[1rem] border p-3 ${isDark ? "border-white/8 bg-black/15" : "border-emerald-100 bg-white/70"}`}>
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
                          <span key={`world-citation-${index}`} className={`rounded-full px-2.5 py-1 text-[10px] font-medium ${isDark ? "bg-white/8 text-slate-300" : "bg-white text-stone-600"}`}>
                            {worldItemTitle(citation, `Source ${index + 1}`)}
                          </span>
                        ))}
                      </div>
                    ) : null}
                  </div>
                ) : null}
                <div className={`rounded-[1.8rem] border p-5 ${isDark ? "border-white/10 bg-white/4" : "border-stone-200 bg-white"}`}>
                  <p className={`text-[11px] font-semibold uppercase tracking-[0.28em] ${isDark ? "text-slate-400" : "text-stone-400"}`}>
                    Retrieved passages
                  </p>
                  <p className={`mt-1 mb-4 text-xs leading-5 ${isDark ? "text-slate-500" : "text-stone-400"}`}>
                    Manuscript sections the advisor used to answer your last question.
                  </p>
                  {passages.length === 0 ? (
                    <p className={`text-sm leading-6 ${isDark ? "text-slate-500" : "text-stone-400"}`}>
                      Send a message to see which passages were retrieved.
                    </p>
                  ) : (
                    <div className="space-y-3">
                      {passages.map((p, i) => (
                        <div key={i} className={`rounded-[1rem] border p-4 ${isDark ? "border-white/8 bg-white/3" : "border-stone-100 bg-stone-50"}`}>
                          <div className="flex items-center justify-between mb-2">
                            <span className={`text-[10px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-indigo-300" : "text-violet-600"}`}>
                              Ch. {p.chapter_num}{p.chapter_title ? `: ${p.chapter_title}` : ""}
                            </span>
                            <span className={`text-[10px] tabular-nums ${isDark ? "text-slate-600" : "text-stone-400"}`}>
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
                </div>

                {/* Response type legend */}
                <div className={`rounded-[1.5rem] border p-5 ${isDark ? "border-white/8 bg-white/3" : "border-stone-100 bg-stone-50"}`}>
                  <p className={`text-[11px] font-semibold uppercase tracking-[0.26em] mb-3 ${isDark ? "text-slate-500" : "text-stone-400"}`}>Response types</p>
                  <div className="space-y-2">
                    {[
                      { icon: "WRN", label: "Contradiction", desc: "Your plan clashes with the text" },
                      { icon: "OPP", label: "Opportunity", desc: "Foreshadowing or arc connection found" },
                      { icon: "TRD", label: "Tradeoff", desc: "Multiple endings debated" },
                      { icon: "RSP", label: "Response", desc: "General analysis or advice" },
                    ].map(({ icon, label, desc }) => (
                      <div key={label} className="flex gap-2.5 items-start">
                        <span className="text-sm shrink-0 mt-0.5">{icon}</span>
                        <div>
                          <span className={`text-xs font-semibold ${isDark ? "text-slate-300" : "text-stone-600"}`}>{label}</span>
                          <span className={`text-xs ml-1.5 ${isDark ? "text-slate-500" : "text-stone-400"}`}>{desc}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* ══ SUGGESTIONS TAB ═════════════════════════════════════════════════ */}
          {tab === "suggestions" && (
            <div>

              {/* Sub-tab switcher */}
              <div className="hidden">
                <button
                  id="suggestions-tab-scan"
                  onClick={() => setSugTab("scan")}
                  className={`px-5 py-2.5 text-sm font-medium transition ${sugTab === "scan" ? isDark ? "bg-white text-slate-950" : "bg-stone-900 text-white" : isDark ? "text-slate-300 hover:bg-white/8" : "text-stone-600 hover:bg-stone-50"}`}
                >
                  Continuity Scan
                </button>
                <button
                  id="suggestions-tab-editorial"
                  onClick={() => setSugTab("editorial")}
                  className={`px-5 py-2.5 text-sm font-medium transition ${sugTab === "editorial" ? isDark ? "bg-white text-slate-950" : "bg-stone-900 text-white" : isDark ? "text-slate-300 hover:bg-white/8" : "text-stone-600 hover:bg-stone-50"}`}
                >
                  ✏️ Editorial Review
                </button>
              </div>

              {/* ── Continuity Scan ─────────────────────────────────────────── */}
              {sugTab === "scan" && (
                <div>
                  <div className="mb-5 flex items-start justify-between gap-4">
                    <p className={`text-sm leading-6 max-w-xl ${isDark ? "text-slate-400" : "text-stone-500"}`}>
                      Proactive analysis of your manuscript, including structural issues, direction decisions, and foreshadowing
                      opportunities. Powered by extracted story data, not the full book.
                    </p>
                    <button
                      onClick={refreshSuggestions}
                      className={`shrink-0 rounded-[0.8rem] border px-4 py-2 text-xs font-medium transition ${isDark ? "border-white/10 bg-white/5 text-slate-300 hover:bg-white/10" : "border-stone-200 bg-white text-stone-600 hover:bg-stone-50"}`}
                    >
                      ↺ Refresh
                    </button>
                  </div>

                  {suggestionsLoading ? (
                    <div className="space-y-3">
                      {[1, 2, 3].map(i => (
                        <div key={i} className={`h-28 animate-pulse rounded-[1.5rem] border ${isDark ? "border-white/8 bg-white/4" : "border-stone-100 bg-stone-50"}`} />
                      ))}
                    </div>
                  ) : visibleSuggestions.length === 0 ? (
                    <div className={`rounded-[1.8rem] border p-10 text-center ${isDark ? "border-white/10 bg-white/4" : "border-stone-200 bg-white"}`}>
                      <p className="text-sm font-semibold uppercase tracking-[0.24em] mb-3">Ready</p>
                      <p className={`font-semibold text-lg ${isDark ? "text-white" : "text-stone-900"}`}>Scan warming up</p>
                      <p className={`mt-2 text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>
                        No scan cards are available yet. Refresh after your next extraction pass or ask the continuity checker for a proactive story audit.
                      </p>
                    </div>
                  ) : (
                    <div className="space-y-8">
                      <SuggestionGroup label="Warnings" icon="WRN" items={grouped.warning} isDark={isDark} intentionalIds={intentionalIds} onAsk={handleSuggestionAsk} onSaveNote={saveQuickNote} onMarkIntentional={markIntentional} onDismiss={dismissSuggestion} />
                      <SuggestionGroup label="Future Direction" icon="DIR" items={grouped.direction} isDark={isDark} intentionalIds={intentionalIds} onAsk={handleSuggestionAsk} onSaveNote={saveQuickNote} onMarkIntentional={markIntentional} onDismiss={dismissSuggestion} />
                      <SuggestionGroup label="Opportunities" icon="OPP" items={grouped.opportunity} isDark={isDark} intentionalIds={intentionalIds} onAsk={handleSuggestionAsk} onSaveNote={saveQuickNote} onMarkIntentional={markIntentional} onDismiss={dismissSuggestion} />
                      <SuggestionGroup label="Info" icon="INF" items={grouped.info} isDark={isDark} intentionalIds={intentionalIds} onAsk={handleSuggestionAsk} onSaveNote={saveQuickNote} onMarkIntentional={markIntentional} onDismiss={dismissSuggestion} />

                      {intentionalIds.size > 0 && (
                        <div className={`rounded-[1.5rem] border p-5 ${isDark ? "border-white/8 bg-white/3" : "border-stone-100 bg-stone-50"}`}>
                          <p className={`text-[11px] font-semibold uppercase tracking-[0.24em] mb-1 ${isDark ? "text-slate-500" : "text-stone-400"}`}>
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

              {/* ── Editorial Review ─────────────────────────────────────────── */}
              {sugTab === "editorial" && (
                <div className="space-y-6">
                  <p className={`text-sm leading-6 max-w-2xl ${isDark ? "text-slate-400" : "text-stone-500"}`}>
                    Paste a passage you've written. The advisor will cross-check it against your characters'
                    personalities, established events, tone, and themes, and it will also flag grammar and formatting issues.
                  </p>

                  <div className={`rounded-[1.8rem] border p-6 ${isDark ? "border-white/10 bg-black/80" : "border-stone-200 bg-white"}`}>
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <p className={`text-[11px] font-semibold uppercase tracking-[0.26em] ${isDark ? "text-slate-400" : "text-stone-400"}`}>
                          Manuscript import
                        </p>
                        <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-400" : "text-stone-500"}`}>
                          Paste a chapter, upload a replacement chapter, import a folder of small PDFs, or convert this upload into an author workspace.
                        </p>
                      </div>
                      <button
                        onClick={async () => {
                          if (!canUseAuthorMode) return
                          if (bookMode === "author") return
                          try {
                            const updated = await booksApi.setMode(bookId, "author")
                            setBookMode(updated.mode)
                            setImportMessage("This upload now behaves like an author workspace.")
                          } catch {
                            setImportMessage("Could not switch this upload to author mode right now.")
                          }
                        }}
                        disabled={!canUseAuthorMode}
                        className={`rounded-[0.8rem] border px-4 py-2 text-xs font-semibold transition disabled:cursor-not-allowed disabled:opacity-55 ${isDark ? "border-white/10 bg-white/5 text-slate-200 hover:bg-white/10" : "border-stone-200 bg-stone-50 text-stone-700 hover:bg-white"}`}
                      >
                        {bookMode === "author" ? "Author mode active" : canUseAuthorMode ? "Convert reader upload to author upload" : "Author mode locked"}
                      </button>
                    </div>

                    <div className="mt-5 flex flex-col gap-4">
                      <input
                        type="file"
                        multiple
                        accept=".pdf,.epub,.docx,.txt,.md"
                        onChange={(event) => setImportFiles(Array.from(event.target.files ?? []))}
                        className={`rounded-[0.9rem] border px-3 py-3 text-sm ${isDark ? "border-white/10 bg-white/5 text-slate-200" : "border-stone-200 bg-stone-50 text-stone-700"}`}
                      />
                      <div className="flex flex-wrap gap-3">
                        <label className={`flex items-center gap-2 text-sm ${isDark ? "text-slate-300" : "text-stone-600"}`}>
                          <input type="checkbox" checked={replaceExisting} onChange={(event) => setReplaceExisting(event.target.checked)} />
                          Update current chapter
                        </label>
                        <label className={`flex items-center gap-2 text-sm ${isDark ? "text-slate-300" : "text-stone-600"}`}>
                          <input type="checkbox" checked={splitIntoChapters} onChange={(event) => setSplitIntoChapters(event.target.checked)} />
                          Split PDFs into chapters
                        </label>
                        <label className={`flex items-center gap-2 text-sm ${isDark ? "text-slate-300" : "text-stone-600"}`}>
                          <input type="checkbox" checked={chunkLongDocuments} onChange={(event) => setChunkLongDocuments(event.target.checked)} />
                          Chunk long documents
                        </label>
                      </div>
                      <div className="flex flex-wrap gap-3">
                        <button
                          onClick={async () => {
                            if ((!editText.trim() && importFiles.length === 0) || importLoading) return
                            setImportLoading(true)
                            setImportMessage(null)
                            try {
                              const result = await booksApi.importManuscript(bookId, {
                                text: editText.trim() || undefined,
                                chapterNumber: editChapter ? parseInt(editChapter) : undefined,
                                replaceExisting,
                                chunkLongDocuments,
                                splitIntoChapters,
                                files: importFiles,
                              })
                              setBookMode(result.mode)
                              setImportMessage(`Imported chapters ${result.imported_chapters.join(", ")}.`)
                            } catch {
                              setImportMessage("Import failed. Check the files or chapter number and try again.")
                            } finally {
                              setImportLoading(false)
                            }
                          }}
                          disabled={importLoading || (!editText.trim() && importFiles.length === 0)}
                          className="rounded-[0.8rem] bg-[linear-gradient(135deg,#0f766e,#115e59)] px-5 py-2.5 text-sm font-semibold text-white transition disabled:opacity-40"
                        >
                          {importLoading ? "Importing…" : replaceExisting ? "Update current upload" : "Add to current upload"}
                        </button>
                        {importMessage ? (
                          <p className={`self-center text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>{importMessage}</p>
                        ) : null}
                      </div>
                    </div>
                  </div>

                  {/* Input panel */}
                  <div className={`rounded-[1.8rem] border p-6 ${isDark ? "border-white/10 bg-black/80" : "border-stone-200 bg-white"}`}>
                    <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:gap-3 mb-4">
                      <div className="flex-1">
                        <label className={`block text-[11px] font-semibold uppercase tracking-[0.26em] mb-2 ${isDark ? "text-slate-400" : "text-stone-400"}`}>
                          Chapter number (optional)
                        </label>
                        <input
                          type="number"
                          min={1}
                          value={editChapter}
                          onChange={e => setEditChapter(e.target.value)}
                          placeholder="e.g. 42"
                          className={`w-32 rounded-[0.8rem] border px-3 py-2 text-sm outline-none transition ${isDark ? "border-white/10 bg-white/5 text-slate-200 placeholder:text-slate-600 focus:border-indigo-500/50" : "border-stone-200 bg-stone-50 text-stone-800 placeholder:text-stone-400 focus:border-violet-300"}`}
                        />
                      </div>
                      <button
                        onClick={async () => {
                          if (!editText.trim()) return
                          setEditLoading(true)
                          setEditError(null)
                          setEditResult(null)
                          try {
                            const res = await intelligenceApi.editorialReview(
                              bookId,
                              editText,
                              editChapter ? parseInt(editChapter) : undefined
                            )
                            setEditResult(res.review)
                            setEditPassages(res.retrieved_passages)
                          } catch {
                            setEditError("Review failed. Check your connection and try again.")
                          } finally {
                            setEditLoading(false)
                          }
                        }}
                        disabled={!editText.trim() || editLoading}
                        className="shrink-0 self-end rounded-[0.8rem] bg-[linear-gradient(135deg,#4f46e5,#4338ca)] px-5 py-2.5 text-sm font-semibold text-white shadow-[0_8px_24px_-12px_rgba(79,70,229,0.7)] transition disabled:opacity-40 hover:-translate-y-[1px]"
                      >
                        {editLoading ? "Reviewing…" : "Run Editorial Review"}
                      </button>
                    </div>

                    <textarea
                      value={editText}
                      onChange={e => setEditText(e.target.value)}
                      placeholder="Paste your passage here: a paragraph, a scene, or a full chapter section."
                      rows={10}
                      className={`w-full resize-y rounded-[1rem] border px-4 py-3 text-sm leading-7 outline-none transition ${isDark ? "border-white/10 bg-white/4 text-slate-200 placeholder:text-slate-600 focus:border-indigo-500/40" : "border-stone-200 bg-stone-50 text-stone-800 placeholder:text-stone-400 focus:border-violet-300"}`}
                    />

                    {editError && (
                      <p className={`mt-3 text-sm rounded-[0.8rem] border px-4 py-2 ${isDark ? "border-red-500/25 bg-red-500/10 text-red-300" : "border-red-200 bg-red-50 text-red-700"}`}>
                        {editError}
                      </p>
                    )}

                    {editLoading && (
                      <div className={`mt-4 animate-pulse space-y-2 rounded-[1rem] border p-4 ${isDark ? "border-white/8 bg-white/3" : "border-stone-100 bg-stone-50"}`}>
                        <div className={`h-2.5 w-40 rounded-full ${isDark ? "bg-white/10" : "bg-stone-200"}`} />
                        <div className={`h-2.5 w-full rounded-full ${isDark ? "bg-white/8" : "bg-stone-100"}`} />
                        <div className={`h-2.5 w-3/4 rounded-full ${isDark ? "bg-white/6" : "bg-stone-100"}`} />
                      </div>
                    )}
                  </div>

                  {/* Results */}
                  {editResult && (
                    <div className="space-y-5">

                      {/* Overall verdict */}
                      <div className={`rounded-[1.5rem] border px-6 py-5 ${isDark ? "border-indigo-500/25 bg-indigo-500/8" : "border-violet-100 bg-violet-50"}`}>
                        <p className={`text-[11px] font-bold uppercase tracking-[0.28em] mb-2 ${isDark ? "text-indigo-300" : "text-violet-600"}`}>Overall Verdict</p>
                        <p className={`text-base leading-7 font-medium ${isDark ? "text-slate-100" : "text-stone-800"}`}>{editResult.overall_verdict}</p>
                        <div className="mt-4 flex flex-wrap gap-2">
                          <button
                            onClick={async () => {
                              const blob = await intelligenceApi.continuityReport(
                                bookId,
                                editText,
                                "pdf",
                                editChapter ? parseInt(editChapter) : undefined
                              )
                              const url = URL.createObjectURL(blob)
                              const link = document.createElement("a")
                              link.href = url
                              link.download = "continuity-report.pdf"
                              link.click()
                              URL.revokeObjectURL(url)
                            }}
                            className={`rounded-[0.8rem] border px-4 py-2 text-xs font-semibold ${isDark ? "border-white/10 bg-white/5 text-slate-200 hover:bg-white/10" : "border-stone-200 bg-white text-stone-700 hover:bg-stone-50"}`}
                          >
                            Download continuity report
                          </button>
                        </div>
                      </div>

                      {/* Thematic fit */}
                      <div className={`rounded-[1.5rem] border px-5 py-4 ${
                        editResult.thematic_fit.score === "strong"
                          ? isDark ? "border-teal-500/25 bg-teal-500/8" : "border-teal-200 bg-teal-50"
                          : editResult.thematic_fit.score === "weak"
                          ? isDark ? "border-red-500/25 bg-red-500/8" : "border-red-200 bg-red-50"
                          : isDark ? "border-amber-500/25 bg-amber-500/8" : "border-amber-100 bg-amber-50"
                      }`}>
                        <div className="flex items-center gap-2 mb-2">
                          <p className={`text-[11px] font-bold uppercase tracking-[0.28em] ${isDark ? "text-slate-400" : "text-stone-400"}`}>Thematic Fit</p>
                          <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-[0.18em] ${
                            editResult.thematic_fit.score === "strong"
                              ? isDark ? "bg-teal-500/20 text-teal-300" : "bg-teal-100 text-teal-700"
                              : editResult.thematic_fit.score === "weak"
                              ? isDark ? "bg-red-500/20 text-red-300" : "bg-red-100 text-red-700"
                              : isDark ? "bg-amber-500/20 text-amber-300" : "bg-amber-100 text-amber-700"
                          }`}>
                            {editResult.thematic_fit.score}
                          </span>
                        </div>
                        <p className={`text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-600"}`}>{editResult.thematic_fit.notes}</p>
                      </div>

                      {/* Continuity issues */}
                      {editResult.continuity_issues.length > 0 && (
                        <div>
                          <p className={`text-[11px] font-bold uppercase tracking-[0.28em] mb-3 ${isDark ? "text-amber-300" : "text-amber-700"}`}>
                            Continuity Issues ({editResult.continuity_issues.length})
                          </p>
                          <div className="space-y-3">
                            {editResult.continuity_issues.map((issue, i) => (
                              <div key={i} className={`rounded-[1.2rem] border px-5 py-4 ${
                                issue.severity === "critical"
                                  ? isDark ? "border-red-500/30 bg-red-500/10" : "border-red-200 bg-red-50"
                                  : issue.severity === "moderate"
                                  ? isDark ? "border-amber-500/30 bg-amber-500/8" : "border-amber-200 bg-amber-50"
                                  : isDark ? "border-white/10 bg-white/4" : "border-stone-100 bg-stone-50"
                              }`}>
                                <div className="flex items-center gap-2 mb-2 flex-wrap">
                                  <span className={`text-[10px] font-bold uppercase tracking-[0.22em] px-2 py-0.5 rounded-full ${
                                    issue.severity === "critical"
                                      ? isDark ? "bg-red-500/20 text-red-300" : "bg-red-100 text-red-700"
                                      : issue.severity === "moderate"
                                      ? isDark ? "bg-amber-500/20 text-amber-300" : "bg-amber-100 text-amber-700"
                                      : isDark ? "bg-white/10 text-slate-400" : "bg-stone-100 text-stone-500"
                                  }`}>{issue.severity}</span>
                                  <span className={`text-[10px] font-medium ${isDark ? "text-slate-500" : "text-stone-400"}`}>{issue.type.replace(/_/g, " ")}</span>
                                  <button
                                    type="button"
                                    onClick={() => void saveQuickNote({
                                      chapterNumber: editChapter ? parseInt(editChapter) : null,
                                      title: `Continuity: ${issue.title}`.slice(0, 120),
                                      body: [
                                        `Continuity issue: ${issue.title}`,
                                        `Severity: ${issue.severity}`,
                                        `Type: ${issue.type.replace(/_/g, " ")}`,
                                        "",
                                        issue.description,
                                        issue.suggestion ? `\nSuggestion: ${issue.suggestion}` : "",
                                      ].join("\n").trim(),
                                    })}
                                    className={`ml-auto rounded-full px-3 py-1 text-[11px] font-semibold transition ${isDark ? "bg-white/10 text-slate-200 hover:bg-white/15" : "bg-white text-stone-700 hover:bg-stone-50"}`}
                                  >
                                    Save note
                                  </button>
                                </div>
                                <p className={`text-sm font-semibold mb-1 ${isDark ? "text-white" : "text-stone-900"}`}>{issue.title}</p>
                                <p className={`text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-600"}`}>{issue.description}</p>
                                {issue.suggestion && (
                                  <p className={`mt-2 text-xs leading-5 font-medium ${isDark ? "text-indigo-300" : "text-violet-700"}`}>
                                    → {issue.suggestion}
                                  </p>
                                )}
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Grammar issues */}
                      {editResult.grammar_issues.length > 0 && (
                        <div>
                          <p className={`text-[11px] font-bold uppercase tracking-[0.28em] mb-3 ${isDark ? "text-slate-400" : "text-stone-400"}`}>
                            Grammar & Spelling ({editResult.grammar_issues.length})
                          </p>
                          <div className="space-y-2.5">
                            {editResult.grammar_issues.map((g, i) => (
                              <div key={i} className={`rounded-[1.1rem] border px-4 py-4 ${isDark ? "border-white/8 bg-white/4" : "border-stone-100 bg-stone-50"}`}>
                                <div className="flex items-start gap-3">
                                  <div className="flex-1 min-w-0">
                                    <p className={`text-[10px] font-semibold uppercase tracking-[0.2em] mb-1 ${isDark ? "text-slate-500" : "text-stone-400"}`}>{g.issue}</p>
                                    <p className={`text-sm mb-1 line-through opacity-60 ${isDark ? "text-slate-400" : "text-stone-500"}`}>"{g.original}"</p>
                                    <p className={`text-sm font-medium ${isDark ? "text-teal-300" : "text-teal-700"}`}>→ "{g.fix}"</p>
                                    <div className="mt-3">
                                      <button
                                        type="button"
                                        onClick={() => void saveQuickNote({
                                          chapterNumber: editChapter ? parseInt(editChapter) : null,
                                          title: `Grammar: ${g.issue}`.slice(0, 120),
                                          body: [
                                            `Grammar issue: ${g.issue}`,
                                            "",
                                            `Original: "${g.original}"`,
                                            `Fix: "${g.fix}"`,
                                          ].join("\n"),
                                        })}
                                        className={`rounded-full px-3 py-1 text-[11px] font-semibold transition ${isDark ? "bg-white/10 text-slate-200 hover:bg-white/15" : "bg-white text-stone-700 hover:bg-stone-50"}`}
                                      >
                                        Save note
                                      </button>
                                    </div>
                                  </div>
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Formatting notes */}
                      {editResult.formatting_notes.length > 0 && (
                        <div>
                          <p className={`text-[11px] font-bold uppercase tracking-[0.28em] mb-3 ${isDark ? "text-slate-400" : "text-stone-400"}`}>
                            Formatting Notes
                          </p>
                          <div className={`rounded-[1.2rem] border px-5 py-4 space-y-2 ${isDark ? "border-white/8 bg-white/4" : "border-stone-100 bg-stone-50"}`}>
                            {editResult.formatting_notes.map((note, i) => (
                              <div key={i} className="flex items-start gap-2.5">
                                <span className={`mt-0.5 text-xs shrink-0 ${isDark ? "text-slate-500" : "text-stone-400"}`}>·</span>
                                <div className="flex-1">
                                  <p className={`text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-600"}`}>{note}</p>
                                  <button
                                    type="button"
                                    onClick={() => void saveQuickNote({
                                      chapterNumber: editChapter ? parseInt(editChapter) : null,
                                      title: "Formatting note",
                                      body: `Formatting note:\n${note}`,
                                    })}
                                    className={`mt-2 rounded-full px-3 py-1 text-[11px] font-semibold transition ${isDark ? "bg-white/10 text-slate-200 hover:bg-white/15" : "bg-white text-stone-700 hover:bg-stone-50"}`}
                                  >
                                    Save note
                                  </button>
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Retrieved passages used */}
                      {editPassages.length > 0 && (
                        <div>
                          <p className={`text-[11px] font-bold uppercase tracking-[0.28em] mb-3 ${isDark ? "text-slate-500" : "text-stone-400"}`}>
                            Cross-referenced passages
                          </p>
                          <div className="grid gap-2 sm:grid-cols-2">
                            {editPassages.map((p, i) => (
                              <div key={i} className={`rounded-[1rem] border p-4 ${isDark ? "border-white/8 bg-white/3" : "border-stone-100 bg-stone-50"}`}>
                                <p className={`text-[10px] font-bold uppercase tracking-[0.22em] mb-1 ${isDark ? "text-indigo-300" : "text-violet-600"}`}>
                                  Ch. {p.chapter_num}{p.chapter_title ? `: ${p.chapter_title}` : ""}
                                </p>
                                <p className={`text-xs leading-5 line-clamp-3 ${isDark ? "text-slate-400" : "text-stone-600"}`}>{p.excerpt}</p>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {editResult.continuity_issues.length === 0 && editResult.grammar_issues.length === 0 && (
                        <div className={`rounded-[1.5rem] border p-6 text-center ${isDark ? "border-teal-500/20 bg-teal-500/8" : "border-teal-200 bg-teal-50"}`}>
                          <p className="text-sm font-semibold uppercase tracking-[0.24em] mb-2">Clear</p>
                          <p className={`font-semibold ${isDark ? "text-teal-200" : "text-teal-800"}`}>No continuity or grammar issues found</p>
                          <p className={`mt-1 text-xs ${isDark ? "text-teal-400" : "text-teal-600"}`}>The passage is consistent with established story facts.</p>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </>
  )
}

function StatPill({ label, value, isDark }: { label: string; value: string; isDark: boolean }) {
  return (
    <div className={`rounded-[0.8rem] border px-3 py-1.5 text-center ${isDark ? "border-white/10 bg-white/5" : "border-stone-200 bg-stone-50"}`}>
      <p className={`text-[10px] font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>{label}</p>
      <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{value}</p>
    </div>
  )
}
