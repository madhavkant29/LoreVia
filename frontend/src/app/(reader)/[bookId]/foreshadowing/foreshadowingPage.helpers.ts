import type { ForeshadowingItem } from "@/types/reader"

export type SignalView = "all" | "linked" | "unlinked"
export const SIGNAL_VIEWS = [{ id: "all", label: "All setups" }, { id: "linked", label: "Linked" }, { id: "unlinked", label: "Unlinked" }] as const

export function hasSuggestedConnection(item: ForeshadowingItem) {
  return typeof item.foreshadows === "string" && !!item.foreshadows.trim()
}

export function signalMatches(item: ForeshadowingItem, view: SignalView, query: string, chapter: string) {
  if (view === "linked" && !hasSuggestedConnection(item)) return false
  if (view === "unlinked" && hasSuggestedConnection(item)) return false
  if (chapter && String(item.chapter_number) !== chapter) return false
  const needle = query.trim().toLocaleLowerCase()
  return !needle || [item.clue, item.foreshadows, item.chapter_title, `Chapter ${item.chapter_number}`].some((value) => typeof value === "string" && value.toLocaleLowerCase().includes(needle))
}

export function signalChapters(items: ForeshadowingItem[]) {
  return [...new Set(items.map((item) => item.chapter_number).filter((number) => Number.isInteger(number) && number > 0))].sort((a, b) => a - b)
}
