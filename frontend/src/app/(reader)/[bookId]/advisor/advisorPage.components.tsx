"use client"

import { Fragment, type ReactNode } from "react"
import type { AdvisorSuggestion } from "@/types/intelligence"

export type ResponseType = "standard" | "warning" | "opportunity" | "tradeoff"

export function responseTypeStyle(type: ResponseType, isDark: boolean) {
  switch (type) {
    case "warning":
      return {
        border: isDark ? "border-amber-500/35" : "border-amber-400/60",
        bg: isDark ? "bg-amber-500/8" : "bg-amber-50",
        badge: isDark ? "bg-amber-500/20 text-amber-300" : "bg-amber-100 text-amber-700",
        label: "Contradiction",
      }
    case "opportunity":
      return {
        border: isDark ? "border-teal-500/35" : "border-teal-400/60",
        bg: isDark ? "bg-teal-500/8" : "bg-teal-50",
        badge: isDark ? "bg-teal-500/20 text-teal-300" : "bg-teal-100 text-teal-700",
        label: "Opportunity",
      }
    case "tradeoff":
      return {
        border: isDark ? "border-violet-500/35" : "border-violet-400/60",
        bg: isDark ? "bg-violet-500/8" : "bg-violet-50",
        badge: isDark ? "bg-violet-500/20 text-violet-300" : "bg-violet-100 text-violet-700",
        label: "Tradeoff",
      }
    default:
      return {
        border: isDark ? "border-white/10" : "border-stone-200",
        bg: isDark ? "bg-white/[0.04]" : "bg-white",
        badge: isDark ? "bg-white/[0.12] text-slate-300" : "bg-stone-100 text-stone-500",
        label: "Response",
      }
  }
}

// Severity config (Suggestions)
function severityConfig(severity: string) {
  switch (severity) {
    case "warning":
      return {
        color: "border-amber-500/40",
        badge: "bg-amber-500/20 text-amber-300",
        label: "Warning",
      }
    case "direction":
      return {
        color: "border-violet-500/40",
        badge: "bg-violet-500/20 text-violet-300",
        label: "Future Direction",
      }
    case "opportunity":
      return {
        color: "border-teal-500/40",
        badge: "bg-teal-500/20 text-teal-300",
        label: "Opportunity",
      }
    default:
      return {
        color: "border-blue-500/40",
        badge: "bg-blue-500/20 text-blue-300",
        label: "Info",
      }
  }
}

export function buildReplyFollowUps(responseType: ResponseType) {
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

export function worldItemTitle(item: Record<string, unknown>, fallback: string): string {
  return compactWorldText(item.title)
    || compactWorldText(item.element_name)
    || compactWorldText(item.name)
    || compactWorldText(item.category)
    || fallback
}

export function worldItemDescription(item: Record<string, unknown>): string {
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

// Rich message renderer
// Parses structured contradiction, opportunity, and option blocks out of plain text.
// and renders them with distinct visual treatment.
export function RichMessage({ content, isDark }: { content: string; isDark: boolean }) {
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
            <div key={i} className={`rounded-sm border px-4 py-3 ${isDark ? "border-amber-500/30 bg-amber-500/10" : "border-amber-300 bg-amber-50"}`}>
              <p className={`text-sm leading-7 font-medium ${isDark ? "text-amber-100" : "text-amber-900"}`}>{renderFormattedTextBlock(text)}</p>
            </div>
          )
        }
        if (seg.type === "opportunity") {
          return (
            <div key={i} className={`rounded-sm border px-4 py-3 ${isDark ? "border-teal-500/30 bg-teal-500/10" : "border-teal-300 bg-teal-50"}`}>
              <p className={`text-sm leading-7 font-medium ${isDark ? "text-teal-100" : "text-teal-900"}`}>{renderFormattedTextBlock(text)}</p>
            </div>
          )
        }
        if (seg.type === "tradeoff") {
          return (
            <div key={i} className={`rounded-sm border px-4 py-3 ${isDark ? "border-violet-500/30 bg-violet-500/10" : "border-violet-200 bg-violet-50"}`}>
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

// Suggestion group
export type StatKind = "characters" | "plot_threads" | "chapters" | "states" | "open_threads" | "clues" | "relationships" | "world_elements"

export function StoryAdvisorIcon({ kind, className = "h-5 w-5" }: { kind: StatKind; className?: string }) {
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

export function StoryAdvisorSectionLabel({ children, tone = "slate" }: { children: string; tone?: "slate" | "teal" | "violet" | "amber" }) {
  const toneClass = { slate: "text-slate-400", teal: "text-teal-300", violet: "text-violet-300", amber: "text-amber-300" }[tone]
  return <p className={`text-3xs font-semibold uppercase tracking-[0.34em] ${toneClass}`}>{children}</p>
}

export function StoryAdvisorSurface({ children, isDark, className = "" }: { children: ReactNode; isDark: boolean; className?: string }) {
  return <div className={`rounded-lg border ${isDark ? "border-white/10 bg-[#0b1220]/88" : "border-stone-200 bg-white"} ${className}`}>{children}</div>
}

export function StoryAdvisorEmptyState({
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
      : isDark ? "border-white/10 bg-white/[0.04] text-white" : "border-stone-200 bg-white text-stone-900"

  return (
    <StoryAdvisorSurface isDark={isDark} className={`p-10 text-center ${styles}`}>
      <p className="text-sm font-semibold uppercase tracking-[0.24em]">Status</p>
      <p className="mt-3 text-lg font-semibold">{title}</p>
      <p className={`mt-2 text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>{body}</p>
    </StoryAdvisorSurface>
  )
}

export function SuggestionGroup({
  label,
  items,
  isDark,
  onAsk,
  onSaveNote,
  onMarkIntentional,
  onDismiss,
  saving = false,
}: {
  label: string
  items: AdvisorSuggestion[]
  isDark: boolean
  onAsk: (p: string) => void
  onSaveNote: (payload: { chapterNumber: number | null; title: string | null; body: string }) => void
  onMarkIntentional: (id: string) => void
  onDismiss: (id: string) => void
  saving?: boolean
}) {
  if (items.length === 0) return null

  return (
    <div>
      <div className="mb-2 flex items-baseline gap-2">
        <h2 className={`text-sm font-semibold ${isDark ? "text-slate-100" : "text-stone-900"}`}>{label}</h2>
        <span className={`text-xs tabular-nums ${isDark ? "text-slate-500" : "text-stone-500"}`}>{items.length}</span>
      </div>
      <div className={`divide-y border-y ${isDark ? "divide-white/10 border-white/10" : "divide-stone-200 border-stone-200"}`}>
        {items.map(s => {
          const cfg = severityConfig(s.severity)
          return (
            <div
              key={s.id}
              className="py-4"
            >
              <div className={`border-l-2 pl-4 ${cfg.color}`}>
                <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between xl:gap-6">
                  <div className="min-w-0 flex-1">
                  <div className="mb-2 flex flex-wrap items-center gap-2">
                    <span className={`text-3xs font-semibold uppercase tracking-[0.22em] px-2 py-0.5 rounded-full ${cfg.badge}`}>
                      {s.type.replace(/_/g, " ")}
                    </span>
                    {s.source ? (
                      <span className={`text-3xs ${isDark ? "text-slate-500" : "text-stone-400"}`}>
                        {s.source === "proactive_audit" ? "Audit" : s.source === "fallback" ? "Fallback" : "Heuristic"}
                      </span>
                    ) : null}
                    {s.chapter_ref ? <span className={`text-3xs ${isDark ? "text-slate-500" : "text-stone-400"}`}>Ch. {s.chapter_ref}</span> : null}
                  </div>
                  <p className={`mb-2 text-base font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>
                    {s.title}
                  </p>
                  <p className={`max-w-3xl text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-600"}`}>
                    {s.description}
                  </p>
                  {s.evidence_excerpt ? <blockquote className={`mt-3 max-w-3xl border-l-2 pl-3 text-sm leading-6 ${isDark ? "border-slate-600 text-slate-300" : "border-stone-300 text-stone-600"}`}><span className="sr-only">Extracted evidence: </span>{s.evidence_excerpt}</blockquote> : null}
                  </div>
                  <div className="flex shrink-0 flex-wrap items-center gap-x-3 gap-y-2 xl:max-w-[24rem] xl:justify-end">
                    <button
                      onClick={() => onAsk(s.ask_prompt)}
                      className={`rounded-sm px-3.5 py-2 text-xs font-semibold transition ${s.severity === "opportunity"
                        ? "bg-teal-700 text-white hover:bg-teal-600"
                        : s.severity === "info" || s.severity === "direction"
                          ? "bg-violet-600 text-white hover:bg-violet-500"
                          : isDark
                            ? "bg-white/[0.12] text-slate-100 hover:bg-white/[0.16]"
                            : "bg-stone-900 text-white hover:bg-stone-800"}`}
                    >
                      {s.action_label}
                    </button>
                    <button
                      disabled={saving}
                      onClick={() => onSaveNote({
                        chapterNumber: typeof s.chapter_ref === "number" ? s.chapter_ref : null,
                        title: `Scan: ${s.title}`.slice(0, 120),
                        body: [
                          `Continuity scan (${s.severity}): ${s.title}`,
                          s.chapter_ref ? `Chapter: ${s.chapter_ref}` : "",
                          `Type: ${s.type.replace(/_/g, " ")}`,
                          "",
                          s.description,
                          s.evidence_excerpt ? `Extracted evidence: ${s.evidence_excerpt}` : "",
                        ].filter(Boolean).join("\n"),
                      })}
                      className={`text-xs font-medium underline decoration-transparent underline-offset-4 hover:decoration-current ${isDark ? "text-slate-300" : "text-stone-600"}`}
                    >
                      Save note
                    </button>
                    <button
                      onClick={() => onMarkIntentional(s.id)}
                      className={`text-xs font-medium underline decoration-transparent underline-offset-4 hover:decoration-current ${isDark ? "text-slate-400" : "text-stone-500"}`}
                      title="Hide this finding as an intentional choice on this browser"
                    >
                      Mark as intentional
                    </button>
                    <button
                      onClick={() => onDismiss(s.id)}
                      className={`text-xs font-medium underline decoration-transparent underline-offset-4 hover:decoration-current ${isDark ? "text-slate-500 hover:text-slate-300" : "text-stone-400 hover:text-stone-600"}`}
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


export function StatPill({ kind, label, value, isDark }: { kind: StatKind; label: string; value: string; isDark: boolean }) {
  return (
    <div className={`min-w-[9.25rem] rounded-md border px-3.5 py-2 ${isDark ? "border-white/10 bg-white/5" : "border-stone-200 bg-stone-50"}`}>
      <div className="flex items-center gap-3">
        <div className={`${isDark ? "text-slate-300" : "text-stone-600"}`}>
          <StoryAdvisorIcon kind={kind} />
        </div>
        <div className="min-w-0 text-left">
          <p className={`text-3xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>{label}</p>
          <p className={`text-xl font-semibold leading-none ${isDark ? "text-white" : "text-stone-900"}`}>{value}</p>
        </div>
      </div>
    </div>
  )
}
