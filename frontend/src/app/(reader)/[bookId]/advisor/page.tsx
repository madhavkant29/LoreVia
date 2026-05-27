"use client"

import { useQuery } from "@tanstack/react-query"
import { Fragment, type ReactNode, useCallback, useEffect, useRef, useState } from "react"
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
import type {
  AdvisorMessage,
  AdvisorPassage,
  AdvisorScanMeta,
  AdvisorSuggestion,
  AdvisorGreeting,
  AdvisorWorldAnalysis,
} from "@/types/intelligence"

// ─── Response type visual config (4 variants) ────────────────────────────────
type ResponseType = "standard" | "warning" | "opportunity" | "tradeoff"
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
      <div className="rounded-[1.6rem] border border-white/10 bg-[#0b1220]/88 p-6 text-sm text-slate-400">
        Loading editorial review...
      </div>
    ),
  },
)

function scanStorageKey(bookId: string) {
  return `lorevia-advisor-scan:${bookId}`
}

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
type StatKind = "characters" | "plot_threads" | "chapters" | "states" | "open_threads" | "clues" | "relationships" | "world_elements"

function StoryAdvisorIcon({ kind, className = "h-5 w-5" }: { kind: StatKind; className?: string }) {
  const shared = {
    className,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.7,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    "aria-hidden": true,
  }

  switch (kind) {
    case "characters":
      return <svg {...shared}><path d="M16 19a4 4 0 0 0-8 0" /><circle cx="12" cy="9" r="3.5" /></svg>
    case "plot_threads":
      return <svg {...shared}><path d="M7 7h4v4H7zM13 13h4v4h-4z" /><path d="M11 9h2m-4 6h4m0-4v2m-2-4v2" /></svg>
    case "chapters":
      return <svg {...shared}><path d="M5 6.5A2.5 2.5 0 0 1 7.5 4H19v15H7.5A2.5 2.5 0 0 0 5 21z" /><path d="M5 6.5V19" /></svg>
    case "states":
      return <svg {...shared}><path d="M4 13h4l2-7 4 12 2-5h4" /></svg>
    case "open_threads":
      return <svg {...shared}><path d="M7.5 9.5A4.5 4.5 0 1 1 12 14H9l-3 2 .9-3.3A4.5 4.5 0 0 1 7.5 9.5Z" /></svg>
    case "clues":
      return <svg {...shared}><circle cx="10" cy="10" r="4" /><path d="m14 14 5 5" /></svg>
    case "relationships":
      return <svg {...shared}><circle cx="8" cy="9" r="2.5" /><circle cx="16" cy="9" r="2.5" /><path d="M4.5 18a4 4 0 0 1 7 0M12.5 18a4 4 0 0 1 7 0" /></svg>
    case "world_elements":
      return <svg {...shared}><circle cx="12" cy="12" r="8" /><path d="M4 12h16M12 4a13 13 0 0 1 0 16M12 4a13 13 0 0 0 0 16" /></svg>
    default:
      return null
  }
}

function StoryAdvisorSectionLabel({ children, tone = "slate" }: { children: string; tone?: "slate" | "teal" | "violet" | "amber" }) {
  const toneClass = { slate: "text-slate-400", teal: "text-teal-300", violet: "text-violet-300", amber: "text-amber-300" }[tone]
  return <p className={`text-[11px] font-semibold uppercase tracking-[0.34em] ${toneClass}`}>{children}</p>
}

function StoryAdvisorSurface({ children, isDark, className = "" }: { children: ReactNode; isDark: boolean; className?: string }) {
  return <div className={`rounded-[1.6rem] border ${isDark ? "border-white/10 bg-[#0b1220]/88" : "border-stone-200 bg-white"} ${className}`}>{children}</div>
}

function StoryAdvisorEmptyState({
  title,
  body,
  isDark,
  accent = "neutral",
}: {
  title: string
  body: string
  isDark: boolean
  accent?: "neutral" | "danger" | "success"
}) {
  const styles = accent === "danger"
    ? isDark ? "border-red-500/20 bg-red-500/8 text-red-100" : "border-red-200 bg-red-50 text-red-800"
    : accent === "success"
      ? isDark ? "border-teal-500/20 bg-teal-500/8 text-teal-100" : "border-teal-200 bg-teal-50 text-teal-800"
      : isDark ? "border-white/10 bg-white/4 text-white" : "border-stone-200 bg-white text-stone-900"

  return (
    <StoryAdvisorSurface isDark={isDark} className={`p-10 text-center ${styles}`}>
      <p className="text-sm font-semibold uppercase tracking-[0.24em]">Status</p>
      <p className="mt-3 text-lg font-semibold">{title}</p>
      <p className={`mt-2 text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>{body}</p>
    </StoryAdvisorSurface>
  )
}

function SuggestionGroup({
  label,
  icon,
  items,
  isDark,
  onAsk,
  onSaveNote,
  onMarkIntentional,
  onDismiss,
}: {
  label: string
  icon: string
  items: AdvisorSuggestion[]
  isDark: boolean
  onAsk: (p: string) => void
  onSaveNote: (payload: { chapterNumber: number | null; title: string | null; body: string }) => void
  onMarkIntentional: (id: string) => void
  onDismiss: (id: string) => void
}) {
  if (items.length === 0) return null
  const tone = items[0]?.severity ?? "info"
  const sectionTone = tone === "opportunity" ? "teal" : tone === "info" || tone === "direction" ? "violet" : tone === "warning" ? "amber" : "slate"

  return (
    <div>
      <div className="mb-3 flex items-center gap-2">
        <span className={`text-sm ${sectionTone === "teal" ? "text-teal-300" : sectionTone === "violet" ? "text-violet-300" : sectionTone === "amber" ? "text-amber-300" : isDark ? "text-slate-300" : "text-stone-500"}`}>{icon}</span>
        <StoryAdvisorSectionLabel tone={sectionTone === "slate" ? "slate" : sectionTone}>{label}</StoryAdvisorSectionLabel>
        <span className={`rounded-full px-1.5 py-0.5 text-[10px] font-semibold ${isDark ? "bg-white/8 text-slate-400" : "bg-stone-100 text-stone-500"}`}>{items.length}</span>
      </div>
      <div className="space-y-3">
        {items.map(s => {
          const cfg = severityConfig(s.severity)
          return (
            <div
              key={s.id}
              className={`rounded-[1.5rem] border px-4 py-4 transition-all duration-300 ${cfg.color}`}
              style={{ animationName: "fadeSlideIn", animationDuration: "0.3s", animationFillMode: "both" }}
            >
              <div className="flex flex-col gap-4 xl:flex-row xl:items-stretch xl:gap-5">
                <div className={`flex shrink-0 items-center border-l pl-3 xl:min-w-[5.75rem] xl:items-start xl:pl-4 ${isDark ? "border-white/10" : "border-stone-200"}`}>
                  <span className={`text-[1.85rem] font-semibold tracking-tight ${s.severity === "opportunity" ? "text-teal-300" : s.severity === "info" || s.severity === "direction" ? "text-violet-300" : s.severity === "warning" ? "text-amber-300" : isDark ? "text-slate-200" : "text-stone-700"}`}>{cfg.icon}</span>
                </div>
                <div className="min-w-0 flex-1">
                  <div className="mb-2 flex flex-wrap items-center gap-2">
                    <span className={`text-[10px] font-semibold uppercase tracking-[0.22em] px-2 py-0.5 rounded-full ${cfg.badge}`}>
                      {s.type.replace(/_/g, " ")}
                    </span>
                    {s.source ? (
                      <span className={`text-[10px] ${isDark ? "text-slate-500" : "text-stone-400"}`}>
                        {s.source === "proactive_audit" ? "Audit" : s.source === "fallback" ? "Fallback" : "Heuristic"}
                      </span>
                    ) : null}
                    {s.chapter_ref ? <span className={`text-[10px] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Ch. {s.chapter_ref}</span> : null}
                  </div>
                  <p className={`mb-2 text-base font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>
                    {s.title}
                  </p>
                  <p className={`max-w-3xl text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-600"}`}>
                    {s.description}
                  </p>
                </div>
                <div className="flex shrink-0 flex-wrap items-start gap-2 xl:max-w-[22rem] xl:justify-end">
                    <button
                      onClick={() => onAsk(s.ask_prompt)}
                      className={`rounded-[0.85rem] px-3.5 py-2 text-xs font-semibold transition ${s.severity === "opportunity"
                        ? "bg-[linear-gradient(135deg,rgba(45,212,191,0.24),rgba(56,189,248,0.28))] text-teal-50 hover:brightness-110"
                        : s.severity === "info" || s.severity === "direction"
                          ? "bg-[linear-gradient(135deg,rgba(124,58,237,0.8),rgba(99,102,241,0.9))] text-white hover:brightness-110"
                          : isDark
                            ? "bg-white/12 text-slate-100 hover:bg-white/16"
                            : "bg-stone-900 text-white hover:bg-stone-800"}`}
                    >
                      {s.action_label} &rarr;
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
                      className={`rounded-[0.85rem] border px-3.5 py-2 text-xs font-semibold transition ${isDark ? "border-white/10 bg-white/8 text-slate-200 hover:bg-white/12" : "border-stone-200 bg-white text-stone-700 hover:bg-stone-50"}`}
                    >
                      Save note
                    </button>
                    <button
                      onClick={() => onMarkIntentional(s.id)}
                      className={`rounded-[0.85rem] border px-3.5 py-2 text-xs font-medium transition ${isDark ? "border-white/10 bg-white/5 text-slate-400 hover:bg-white/10" : "border-stone-200 bg-white text-stone-500 hover:bg-stone-50"}`}
                      title="Mark as a deliberate authorial choice that will not reappear"
                    >
                      Mark as intentional
                    </button>
                    <button
                      onClick={() => onDismiss(s.id)}
                      className={`rounded-[0.85rem] px-3 py-2 text-xs font-medium transition ${isDark ? "text-slate-600 hover:bg-white/5 hover:text-slate-300" : "text-stone-400 hover:bg-stone-50 hover:text-stone-600"}`}
                    >
                      Dismiss
                    </button>
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

  const { data: greeting = null } = useQuery<AdvisorGreeting | null>({
    queryKey: [`advisor:${bookId}:greeting`],
    queryFn: () => intelligenceApi.advisorGreeting(bookId),
  })
  const {
    data: suggestionsPayload = null,
    isLoading: suggestionsLoading,
    refetch: refetchSuggestions,
  } = useQuery<{ suggestions: AdvisorSuggestion[]; meta: AdvisorScanMeta }>({
    queryKey: [`advisor:${bookId}:suggestions`],
    queryFn: () => intelligenceApi.advisorSuggestions(bookId),
  })
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
    if (autoOpenedScan || tab !== "checker" || !suggestionsPayload || suggestionsPayload.suggestions.length === 0) return
    setTab("suggestions")
    setAutoOpenedScan(true)
  }, [autoOpenedScan, suggestionsPayload, tab])

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
    window.localStorage.setItem(
      scanStorageKey(bookId),
      JSON.stringify({
        dismissed: [...dismissedIds],
        intentional: [...intentionalIds],
      })
    )
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
        setError("You reached today's Story Advisor limit. Upgrade for more daily capacity or continue tomorrow.")
      } else if (msg.includes("429")) {
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
    void refetchSuggestions()
  }, [refetchSuggestions])

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

      <div className={`min-h-screen ${isDark ? "bg-[radial-gradient(circle_at_top,#152238_0%,#09101c_32%,#050912_72%,#04070d_100%)] text-slate-100" : "bg-stone-50 text-stone-950"}`}>

        {noteToast ? (
          <div className="fixed bottom-5 left-1/2 z-50 w-[min(92vw,32rem)] -translate-x-1/2">
            <div className={`rounded-full border px-4 py-2 text-center text-sm font-medium shadow-lg ${isDark ? "border-white/10 bg-black/80 text-slate-200" : "border-stone-200 bg-white text-stone-700"}`}>
              {noteToast}
            </div>
          </div>
        ) : null}

        {/* ── Header ─────────────────────────────────────────────────────────── */}
        <header className={`sticky top-0 z-30 border-b px-4 py-4 backdrop-blur-xl sm:px-6 ${isDark ? "border-white/8 bg-[#050912]/88" : "border-stone-200 bg-white/85"}`}>
          <div className="mx-auto flex w-full max-w-[84rem] flex-wrap items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <Link
                href={`/${bookId}`}
                className={`text-sm font-medium transition ${isDark ? "text-teal-200 hover:text-teal-100" : "text-violet-700 hover:text-violet-800"}`}
              >
                ← Overview
              </Link>
              <span className={`text-sm ${isDark ? "text-slate-600" : "text-stone-300"}`}>/</span>
              <span className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>
                Story Advisor
              </span>
            </div>

            <div className="flex flex-wrap items-center justify-end gap-2 md:gap-3">
              {greeting && (
                <>
                  <StatPill kind="characters" label="Characters" value={String(greeting.stats.characters)} isDark={isDark} />
                  <StatPill kind="plot_threads" label="Plot Threads" value={String(greeting.stats.plot_threads)} isDark={isDark} />
                  {greeting.stats.total_chapters && (
                    <StatPill kind="chapters" label="Chapters" value={String(greeting.stats.total_chapters)} isDark={isDark} />
                  )}
                </>
              )}
            </div>
          </div>
        </header>

        <div className="mx-auto max-w-[84rem] px-4 py-8 sm:px-6 lg:px-8 lg:pb-12">

          {/* ── Title ─────────────────────────────────────────────────────────── */}
          <div className="mb-8 flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
            <div className="max-w-3xl">
              <StoryAdvisorSectionLabel tone="violet">Author Intelligence</StoryAdvisorSectionLabel>
              <h1 className={`mt-3 font-serif text-5xl leading-none sm:text-6xl ${isDark ? "text-white" : "text-stone-950"}`}>
                Story Advisor
              </h1>
              <p className={`mt-4 max-w-2xl text-base leading-8 ${isDark ? "text-slate-300" : "text-stone-600"}`}>
                Ask anything about your manuscript, including lore, canon, world gaps, and story logic. The advisor will counter contradictions,
                surface foreshadowing, and walk you through the tradeoffs of every story decision.
              </p>
            </div>
            <Link
              href={`/${bookId}/notes`}
              className={`inline-flex items-center justify-center rounded-[1rem] border px-4 py-3 text-sm font-medium transition ${isDark ? "border-teal-500/35 bg-teal-500/8 text-teal-100 hover:bg-teal-500/12" : "border-stone-300 bg-white text-stone-900 hover:bg-stone-50"}`}
            >
              Open notes workspace
            </Link>
          </div>

          {/* ── Tab switcher ──────────────────────────────────────────────────── */}
          <div role="tablist" aria-label="Story Advisor mode" className={`mb-8 inline-flex flex-wrap overflow-hidden rounded-[1rem] border p-1 ${isDark ? "border-white/10 bg-white/5 shadow-[0_20px_40px_-34px_rgba(15,23,42,0.95)]" : "border-stone-200 bg-white"}`}>
            <button
              type="button"
              id="advisor-tab-chat"
              role="tab"
              aria-selected={tab === "checker"}
              aria-controls="advisor-checker-panel"
              onClick={() => setTab("checker")}
              className={`rounded-[0.8rem] px-5 py-2.5 text-sm font-medium transition ${tab === "checker" ? isDark ? "bg-teal-500/18 text-teal-50 ring-1 ring-inset ring-teal-400/30" : "bg-stone-900 text-white" : isDark ? "text-slate-300 hover:bg-white/8" : "text-stone-600 hover:bg-stone-50"}`}
            >
              Continuity Checker
            </button>
            <button
              type="button"
              id="advisor-tab-scan"
              role="tab"
              aria-selected={tab === "suggestions"}
              aria-controls="advisor-scan-panel"
              onClick={() => setTab("suggestions")}
              className={`relative rounded-[0.8rem] px-5 py-2.5 text-sm font-medium transition ${tab === "suggestions" ? isDark ? "bg-teal-500/18 text-teal-50 ring-1 ring-inset ring-teal-400/30" : "bg-stone-900 text-white" : isDark ? "text-slate-300 hover:bg-white/8" : "text-stone-600 hover:bg-stone-50"}`}
            >
              Continuity Scan
              {warnCount > 0 && (
                <span className="absolute -right-1 -top-1 flex h-4 w-4 items-center justify-center rounded-full bg-amber-500 text-[10px] font-bold text-white">
                  {warnCount}
                </span>
              )}
            </button>
          </div>

          {/* ══ CHAT TAB ════════════════════════════════════════════════════════ */}
          {tab === "checker" && (
            <div id="advisor-checker-panel" role="tabpanel" aria-labelledby="advisor-tab-chat" className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_22rem]">

              {/* Chat area */}
              <StoryAdvisorSurface isDark={isDark} className="flex min-h-[62vh] flex-col overflow-hidden shadow-[0_36px_90px_-54px_rgba(2,6,23,0.95)]">
                <div className={`border-b px-5 py-4 ${isDark ? "border-white/8 bg-[#0d1524]/72" : "border-stone-100"}`}>
                  <StoryAdvisorSectionLabel tone="slate">Continuity Checker</StoryAdvisorSectionLabel>
                  <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-400" : "text-stone-500"}`}>
                    Ask targeted questions about contradictions, lore gaps, world rules, endings, and tradeoffs. The advisor preserves the current conversation flow and answer formatting.
                  </p>
                </div>
                <div className="flex-1 overflow-y-auto px-4 py-5 sm:px-5" style={{ maxHeight: "60vh" }}>
                  <div className="mx-auto w-full max-w-[52rem] space-y-4">

                  {/* Opening question */}
                  {messages.length === 0 && (
                    <div className={`rounded-[1.35rem] border px-5 py-5 ${isDark ? "border-violet-500/20 bg-violet-500/8 shadow-[0_18px_40px_-30px_rgba(139,92,246,0.7)]" : "border-violet-100 bg-violet-50"}`}>
                      <StoryAdvisorSectionLabel tone="violet">Story Advisor</StoryAdvisorSectionLabel>
                      <p className={`text-base leading-7 ${isDark ? "text-slate-200" : "text-stone-700"}`}>
                        {greeting?.message ?? "What aspect of your story feels unsolved right now?"}
                      </p>
                      <div className="mt-4 flex flex-wrap gap-2">
                        {ADVISOR_STARTER_PROMPTS.map(prompt => (
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
                          ? `rounded-[1.25rem] border p-5 ${style!.border} ${style!.bg} ${style!.glow}`
                          : `ml-auto max-w-[36rem] rounded-[1.25rem] border px-5 py-4 ${isDark ? "border-violet-500/30 bg-violet-500/18 shadow-[0_18px_38px_-28px_rgba(124,58,237,0.85)]" : "border-violet-200 bg-violet-600/12"}`
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
                </div>

                {/* Input bar */}
                <div className={`border-t px-4 py-4 ${isDark ? "border-white/8 bg-[#09101b]" : "border-stone-100"}`}>
                  <div className="mx-auto w-full max-w-[52rem]">
                    <div className={`rounded-[1.2rem] border px-4 py-3 ${isDark ? "border-white/10 bg-[#0b1322] shadow-[0_16px_40px_-32px_rgba(15,23,42,0.95)]" : "border-stone-200 bg-stone-50"} transition`}>
                      <div className="flex items-end gap-3">
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
                      className="shrink-0 rounded-[0.85rem] bg-[linear-gradient(135deg,#7c3aed,#4f46e5)] px-4 py-2 text-sm font-semibold text-white shadow-[0_10px_24px_-14px_rgba(99,102,241,0.72)] transition disabled:opacity-40 hover:-translate-y-[1px]"
                    >
                      {loading ? "..." : "Send"}
                    </button>
                    </div>
                  </div>
                  <p className={`mt-2 text-[10px] ${isDark ? "text-slate-600" : "text-stone-400"}`}>
                    Enter to send · Shift+Enter for new line · Contradictions and world gaps flagged automatically
                  </p>
                </div>
                </div>
              </StoryAdvisorSurface>

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
                <StoryAdvisorSurface isDark={isDark} className="p-5">
                  <StoryAdvisorSectionLabel tone="teal">Retrieved Passages</StoryAdvisorSectionLabel>
                  <p className={`mt-1 mb-4 text-xs leading-5 ${isDark ? "text-slate-500" : "text-stone-400"}`}>
                    Manuscript sections the advisor used to answer your last question.
                  </p>
                  {passages.length === 0 ? (
                    <div className={`rounded-[1rem] border border-dashed p-5 text-center ${isDark ? "border-white/10 bg-black/10" : "border-stone-200 bg-stone-50"}`}>
                      <p className={`text-sm leading-6 ${isDark ? "text-slate-500" : "text-stone-400"}`}>
                        Send a message to see which passages were retrieved.
                      </p>
                    </div>
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
                </StoryAdvisorSurface>

                {/* Response type legend */}
                <StoryAdvisorSurface isDark={isDark} className="p-5">
                  <StoryAdvisorSectionLabel tone="slate">Response Types</StoryAdvisorSectionLabel>
                  <div className="space-y-2">
                    {RESPONSE_TYPE_LEGEND.map(({ icon, label, desc }) => (
                      <div key={label} className={`flex items-start gap-3 rounded-[0.95rem] border px-3 py-3 ${isDark ? "border-white/8 bg-black/10" : "border-stone-200 bg-stone-50"}`}>
                        <span className={`mt-0.5 inline-flex min-w-[2.6rem] justify-center rounded-full px-2 py-1 text-[10px] font-semibold ${icon === "WRN" ? "bg-amber-500/15 text-amber-300" : icon === "OPP" ? "bg-teal-500/15 text-teal-300" : icon === "TRD" ? "bg-violet-500/15 text-violet-300" : "bg-blue-500/15 text-blue-300"}`}>{icon}</span>
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

          {/* ══ SUGGESTIONS TAB ═════════════════════════════════════════════════ */}
          {tab === "suggestions" && (
            <div id="advisor-scan-panel" role="tabpanel" aria-labelledby="advisor-tab-scan">

              {/* Sub-tab switcher */}
              <div className="hidden">
                <button
                  type="button"
                  id="suggestions-tab-scan"
                  onClick={() => setSugTab("scan")}
                  className={`px-5 py-2.5 text-sm font-medium transition ${sugTab === "scan" ? isDark ? "bg-white text-slate-950" : "bg-stone-900 text-white" : isDark ? "text-slate-300 hover:bg-white/8" : "text-stone-600 hover:bg-stone-50"}`}
                >
                  Continuity Scan
                </button>
                <button
                  type="button"
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
                  <div className="mb-5 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                    <p className={`max-w-2xl text-sm leading-7 ${isDark ? "text-slate-400" : "text-stone-500"}`}>
                      Proactive analysis of your manuscript, including structural issues, direction decisions, and foreshadowing
                      opportunities. Powered by extracted story data, not the full book.
                    </p>
                    <button
                      onClick={refreshSuggestions}
                      className={`shrink-0 rounded-[0.9rem] border px-4 py-2 text-xs font-medium transition ${isDark ? "border-white/10 bg-white/5 text-slate-300 hover:bg-white/10" : "border-stone-200 bg-white text-stone-600 hover:bg-stone-50"}`}
                    >
                      Refresh
                    </button>
                  </div>

                  <StoryAdvisorSurface isDark={isDark} className="mb-6 p-4 sm:p-5">
                    <div className="flex flex-wrap items-center gap-2">
                      <StoryAdvisorSectionLabel tone="slate">Heuristic Summary</StoryAdvisorSectionLabel>
                      {suggestionsMeta.fallback_applied ? (
                        <span className={`rounded-full px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] ${isDark ? "bg-teal-500/15 text-teal-200" : "bg-teal-100 text-teal-700"}`}>
                          Fallback Cards
                        </span>
                      ) : null}
                    </div>
                    <div className="mt-3 flex flex-wrap items-center gap-2">
                      <span className={`rounded-full px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] ${isDark ? "bg-white/8 text-slate-300" : "bg-stone-100 text-stone-700"}`}>
                        {suggestionsMeta.heuristic_count} heuristic card{suggestionsMeta.heuristic_count === 1 ? "" : "s"}
                      </span>
                      {suggestionsMeta.proactive_audit_applied ? (
                        <span className={`rounded-full px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] ${isDark ? "bg-teal-500/15 text-teal-200" : "bg-teal-100 text-teal-700"}`}>
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
                        <div key={item.label} className={`rounded-[1rem] border px-3 py-3 ${isDark ? "border-white/8 bg-black/20" : "border-stone-100 bg-stone-50"}`}>
                          <div className="flex items-center gap-3">
                            <div className={`${isDark ? "text-teal-300" : "text-teal-700"}`}>
                              <StoryAdvisorIcon kind={item.kind} />
                            </div>
                            <div className="min-w-0">
                              <p className={`text-[10px] font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>{item.label}</p>
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

                  {suggestionsLoading ? (
                    <div className="space-y-3">
                      {[1, 2, 3].map(i => (
                        <div key={i} className={`h-28 animate-pulse rounded-[1.5rem] border ${isDark ? "border-white/8 bg-white/4" : "border-stone-100 bg-stone-50"}`} />
                      ))}
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

function StatPill({ kind, label, value, isDark }: { kind: StatKind; label: string; value: string; isDark: boolean }) {
  return (
    <div className={`min-w-[9.25rem] rounded-[1rem] border px-3.5 py-2 ${isDark ? "border-white/10 bg-white/5" : "border-stone-200 bg-stone-50"}`}>
      <div className="flex items-center gap-3">
        <div className={`${isDark ? "text-slate-300" : "text-stone-600"}`}>
          <StoryAdvisorIcon kind={kind} />
        </div>
        <div className="min-w-0 text-left">
          <p className={`text-[10px] font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>{label}</p>
          <p className={`text-xl font-semibold leading-none ${isDark ? "text-white" : "text-stone-900"}`}>{value}</p>
        </div>
      </div>
    </div>
  )
}
