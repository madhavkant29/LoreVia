import axios from "axios"

import type { UserStats } from "@/types/book"
import type {
  WikiEntry,
  WorldBuildingDocument,
  WorldElement,
  WorldGapResult,
  WorldIntegrationResult,
  WorldNote,
} from "@/types/world-building"

export type PrimaryAccent = "teal" | "blue" | "violet"
export type OutlineAccent = "teal" | "amber"
export type BadgeAccent = "teal" | "blue" | "amber"
export type DotAccent = "teal" | "blue" | "violet" | "amber"

export function getApiErrorDetail(error: unknown) {
  if (!axios.isAxiosError(error)) return null
  const detail = error.response?.data?.detail
  return typeof detail === "string" ? detail : null
}

export function panelClass(isDark: boolean) {
  return isDark ? "border-white/10 bg-[#0a1322]" : "border-stone-200 bg-white/90"
}

export function softPanelClass(isDark: boolean) {
  return isDark ? "border-white/10 bg-[#07111f]" : "border-stone-200 bg-stone-50/90"
}

export function eyebrowClass(isDark: boolean) {
  return `text-3xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-400" : "text-stone-500"}`
}

export function titleTextClass(isDark: boolean) {
  return isDark ? "text-white" : "text-stone-950"
}

export function bodyTextClass(isDark: boolean) {
  return isDark ? "text-slate-300" : "text-stone-700"
}

export function mutedTextClass(isDark: boolean) {
  return isDark ? "text-slate-400" : "text-stone-500"
}

export function inputClass(isDark: boolean) {
  return `w-full rounded-md border px-4 py-3 text-sm outline-none transition ${isDark ? "border-white/10 bg-black/25 text-slate-100 focus:border-sky-400/40" : "border-stone-200 bg-white text-stone-900 focus:border-sky-300"}`
}

export function secondaryButtonClass(isDark: boolean) {
  return `inline-flex items-center justify-center rounded-xl border px-4 py-2.5 text-sm font-medium transition ${isDark ? "border-white/10 bg-white/5 text-slate-200 hover:bg-white/10" : "border-stone-200 bg-white text-stone-700 hover:bg-stone-50"}`
}

export function primaryButtonClass(accent: PrimaryAccent) {
  const tones = {
    teal: "bg-[#0f766e] hover:bg-[#115e59]",
    blue: "bg-[#2563eb] hover:bg-[#1d4ed8]",
    violet: "bg-[#6d28d9] hover:bg-[#5b21b6]",
  }
  return `inline-flex items-center justify-center rounded-xl px-4 py-2.5 text-sm font-semibold text-white transition disabled:opacity-50 ${tones[accent]}`
}

export function accentOutlineButtonClass(accent: OutlineAccent, isDark: boolean) {
  if (accent === "amber") {
    return `inline-flex items-center justify-center rounded-xl border px-4 py-2.5 text-sm font-medium transition ${isDark ? "border-amber-300/20 bg-amber-400/10 text-amber-100 hover:bg-amber-400/15" : "border-amber-200 bg-amber-50 text-amber-800 hover:bg-amber-100"}`
  }
  return `inline-flex items-center justify-center rounded-xl border px-4 py-2.5 text-sm font-medium transition ${isDark ? "border-teal-300/20 bg-teal-400/10 text-teal-100 hover:bg-teal-400/15" : "border-teal-200 bg-teal-50 text-teal-800 hover:bg-teal-100"}`
}

export function dangerButtonClass(isDark: boolean) {
  return `inline-flex items-center justify-center rounded-xl border px-4 py-2.5 text-sm font-medium transition ${isDark ? "border-rose-400/20 bg-rose-500/10 text-rose-200 hover:bg-rose-500/15" : "border-rose-200 bg-rose-50 text-rose-700 hover:bg-rose-100"}`
}

export function mutedActionClass(isDark: boolean, accent: "teal") {
  if (accent === "teal") {
    return `inline-flex items-center justify-center rounded-xl px-4 py-2.5 text-sm font-medium ${isDark ? "bg-teal-500/10 text-teal-200 opacity-80" : "bg-teal-50 text-teal-700 opacity-80"}`
  }
  return ""
}

export function badgeClass(isDark: boolean) {
  return `rounded-full px-2.5 py-1 text-3xs font-semibold ${isDark ? "bg-white/[0.08] text-slate-300" : "bg-stone-100 text-stone-600"}`
}

export function accentBadgeClass(accent: BadgeAccent, isDark: boolean) {
  if (accent === "teal") return `rounded-full px-2.5 py-1 text-3xs font-semibold ${isDark ? "bg-teal-500/10 text-teal-200" : "bg-teal-50 text-teal-700"}`
  if (accent === "amber") return `rounded-full px-2.5 py-1 text-3xs font-semibold ${isDark ? "bg-amber-400/15 text-amber-100" : "bg-amber-50 text-amber-800"}`
  return `rounded-full px-2.5 py-1 text-3xs font-semibold ${isDark ? "bg-sky-500/10 text-sky-200" : "bg-sky-50 text-sky-700"}`
}

export function accentDotClass(accent: DotAccent, isDark: boolean) {
  if (accent === "teal") return isDark ? "bg-teal-300" : "bg-teal-500"
  if (accent === "blue") return isDark ? "bg-sky-300" : "bg-sky-500"
  if (accent === "violet") return isDark ? "bg-violet-300" : "bg-violet-500"
  return isDark ? "bg-amber-300" : "bg-amber-500"
}

export function summarizeRecord(record: Record<string, unknown> | string) {
  if (typeof record === "string") return record

  const preferredKeys = [
    "title",
    "label",
    "name",
    "description",
    "summary",
    "message",
    "reason",
    "excerpt",
    "chapter_title",
    "source",
  ]

  for (const key of preferredKeys) {
    const value = record[key]
    if (typeof value === "string" && value.trim()) {
      return value.trim()
    }
  }

  return Object.entries(record)
    .filter(([, value]) => value !== null && value !== undefined && value !== "")
    .slice(0, 3)
    .map(([key, value]) => `${key.replaceAll("_", " ")}: ${String(value)}`)
    .join(" - ")
}

export function formatElementType(type: string) {
  return (type || "element").replaceAll("_", " ")
}

export function worldRecordText(record: Record<string, unknown> | string) {
  if (typeof record === "string") return record
  const keys = ["title", "label", "name", "element_name", "description", "summary", "message", "reason", "excerpt", "chapter_title", "source", "source_scope", "element_type", "suggested_fix", "suggestions"]
  return [...new Set(keys.flatMap((key) => {
    const value = record[key]
    return typeof value === "string" && value.trim() ? [value.trim()] : Array.isArray(value) ? value.filter((item): item is string => typeof item === "string" && !!item.trim()) : []
  }))].join("\n\n") || "No readable details were supplied."
}

export function severityClass(severity: string, isDark: boolean) {
  const normalized = severity.toLowerCase()
  if (normalized === "critical") {
    return isDark
      ? "rounded-full bg-rose-500/15 px-2.5 py-1 text-3xs font-semibold uppercase tracking-[0.18em] text-rose-200"
      : "rounded-full bg-rose-50 px-2.5 py-1 text-3xs font-semibold uppercase tracking-[0.18em] text-rose-700"
  }
  if (normalized === "high") {
    return isDark
      ? "rounded-full bg-amber-400/15 px-2.5 py-1 text-3xs font-semibold uppercase tracking-[0.18em] text-amber-100"
      : "rounded-full bg-amber-50 px-2.5 py-1 text-3xs font-semibold uppercase tracking-[0.18em] text-amber-800"
  }
  return isDark
    ? "rounded-full bg-white/[0.08] px-2.5 py-1 text-3xs font-semibold uppercase tracking-[0.18em] text-slate-200"
    : "rounded-full bg-stone-100 px-2.5 py-1 text-3xs font-semibold uppercase tracking-[0.18em] text-stone-700"
}

export function findSelectedWorldDocument(documents: WorldBuildingDocument[], selectedDocumentId: string | null) {
  if (!selectedDocumentId) return null
  return documents.find((document) => document.id === selectedDocumentId) ?? null
}

export function getOpenGapIds(notes: WorldNote[]) {
  return new Set(notes.filter((note) => note.status !== "addressed" && note.linked_gap_id).map((note) => note.linked_gap_id as string))
}

export function countWorldDocumentWords(documents: WorldBuildingDocument[]) {
  return documents.reduce((sum, document) => sum + (document.word_count ?? 0), 0)
}

export function groupWorldNotesByStatus(notes: WorldNote[]) {
  const open = notes.filter((note) => note.status !== "addressed")
  const addressed = notes.filter((note) => note.status === "addressed")
  return { open, addressed }
}

export function summarizeWikiEntryTypes(entries: WikiEntry[]) {
  return entries.reduce<Record<string, number>>((summary, entry) => {
    const key = entry.entry_type || "entry"
    summary[key] = (summary[key] ?? 0) + 1
    return summary
  }, {})
}

export function summarizeWorldElementTypes(elements: WorldElement[]) {
  return elements.reduce<Record<string, number>>((summary, element) => {
    const key = element.element_type || "element"
    summary[key] = (summary[key] ?? 0) + 1
    return summary
  }, {})
}

export function getSuggestionElements(integration: WorldIntegrationResult | null, analysis: WorldGapResult | null) {
  return (integration?.world_elements ?? analysis?.world_elements ?? []).filter((element) => element.suggestions.length > 0)
}

export function getVisibleWorldElements(elements: WorldElement[], limit = 18) {
  return [...elements]
    .sort((left, right) => {
      const leftScore = left.source_scope === "worldbuilding" ? 1 : 0
      const rightScore = right.source_scope === "worldbuilding" ? 1 : 0
      return rightScore - leftScore || right.usage_count - left.usage_count || left.name.localeCompare(right.name)
    })
    .slice(0, limit)
}

export function getVisibleItems<T>(items: T[], showAll: boolean, initialCount: number) {
  return showAll ? items : items.slice(0, initialCount)
}

export function buildUploadLimitNote(uploadStats: UserStats | null) {
  if (!uploadStats) return null
  const activeWords = (uploadStats.private.active_analyzed_words ?? 0).toLocaleString()
  const activeWordLimit = (uploadStats.private.active_word_limit ?? 0).toLocaleString()
  const sourceStorageGb = ((uploadStats.private.source_storage_bytes ?? 0) / 1024 ** 3).toFixed(1)
  const sourceStorageLimitGb = ((uploadStats.private.source_storage_limit_bytes ?? 0) / 1024 ** 3).toFixed(0)
  const reportingOnly = uploadStats.private.allowances_enforced ? "" : " (reporting only)"
  return `${activeWords}/${activeWordLimit} active words · ${sourceStorageGb}/${sourceStorageLimitGb} GB source storage${reportingOnly}.`
}
