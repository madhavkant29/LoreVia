import type { Book } from "@/types/book"
import type { BookVisibilitySummaryItem, UiPreferenceOperation, UserBookUiPreference } from "@/types/uiPreferences"
import type { ResolvedWorkspaceTool } from "@/lib/workspace/toolResolver"

export function publicAccessStatus(book: Book) {
  const status = (book.public_status ?? "").trim().toLowerCase()
  const moderation = (book.moderation_status ?? "").trim().toLowerCase()
  if (book.archived_at || book.hidden_at || ["hidden", "removed"].includes(status) || ["hidden", "removed", "under_review"].includes(moderation)) {
    return { label: "Not public", detail: "This book is hidden, archived, removed, or restricted by moderation.", href: null }
  }
  if (status === "pending_review" || (!book.is_public && book.public_share_status === "pending")) return { label: "Awaiting review", detail: "The public submission is waiting for review. A saved link does not make it public.", href: null }
  if (!book.is_public || (status && status !== "published")) return { label: "Not public", detail: "The current publication settings do not make this book publicly readable.", href: null }
  if (status !== "published" || (moderation && !["clean", "reported"].includes(moderation))) return { label: "Public status unverified", detail: "Publication state is incomplete or unrecognized. Review the public upload before sharing its link.", href: null }
  return { label: "Public page active", detail: "A public edition is published. Workspace access remains separate from public reading access.", href: `/public/${encodeURIComponent(book.public_slug || book.id)}` }
}

export function visibilityStateLabel(item: BookVisibilitySummaryItem): string {
  const state = item.state?.trim().replaceAll("_", " ") || "Unknown"
  const label = state.charAt(0).toUpperCase() + state.slice(1)
  return typeof item.count === "number" && Number.isFinite(item.count) && item.count >= 0 ? `${item.count} · ${label}` : label
}

export function navigationToolOperations(preference: UserBookUiPreference, toolId: string, visible: boolean): UiPreferenceOperation[] {
  return [
    { op: "set", path: "/hidden_book_tools", value: visible ? preference.hidden_book_tools.filter(id => id !== toolId) : Array.from(new Set([...preference.hidden_book_tools, toolId])) },
    { op: "set", path: `/overview_cards/${toolId}`, value: visible ? "visible" : "user_hidden" },
  ]
}

export function restoreNavigationToolOperations(current: UserBookUiPreference, previous: UserBookUiPreference, toolId: string): UiPreferenceOperation[] {
  return [
    { op: "set", path: "/hidden_book_tools", value: previous.hidden_book_tools.includes(toolId) ? Array.from(new Set([...current.hidden_book_tools, toolId])) : current.hidden_book_tools.filter(id => id !== toolId) },
    Object.prototype.hasOwnProperty.call(previous.overview_cards, toolId)
      ? { op: "set", path: `/overview_cards/${toolId}`, value: previous.overview_cards[toolId] }
      : { op: "unset", path: `/overview_cards/${toolId}` },
  ]
}

export function navigationToolDetail(item: ResolvedWorkspaceTool): string {
  const reasons: Record<string, string> = { hidden_by_user: "Hidden by your choice", hidden_by_preset: "Hidden by this book’s preset", hidden_by_advanced_override: "Advanced tools hidden for this book", hidden_by_mode: "Hidden by your workspace mode" }
  const access: Record<string, string> = { plan_locked: "Requires an Author or Architect plan", permission_denied: "Your access does not include this tool", processing_blocked: "Available after processing finishes" }
  return [item.hidden ? reasons[item.reason ?? ""] ?? "Hidden in navigation" : "Shown in navigation", access[item.access]].filter(Boolean).join(" · ")
}
