import { readerApi } from "@/lib/api/reader"
import type { PlotThread, PlotThreadPageItem } from "@/types/reader"

export const THREAD_STATUS_LABELS: Record<string, string> = {
  introduced: "Introduced", developing: "Developing", ongoing: "Developing", paused: "Paused",
  resolved: "Resolved", contradicted: "Contradicted", forgotten: "Forgotten",
  possibly_abandoned: "Possibly abandoned", abandoned: "Abandoned", unknown: "Unknown",
}
export const THREAD_STATUS_OPTIONS = Object.keys(THREAD_STATUS_LABELS).filter((status) => status !== "ongoing")
export const THREAD_VIEWS = [{ id: "open", label: "Open" }, { id: "attention", label: "Needs attention" }, { id: "resolved", label: "Resolved" }] as const
export type ThreadView = typeof THREAD_VIEWS[number]["id"]

export function threadView(status: string): ThreadView {
  if (status === "resolved") return "resolved"
  return ["introduced", "developing", "ongoing"].includes(status) ? "open" : "attention"
}

export function threadChapterRange(thread: Pick<PlotThreadPageItem, "first_mentioned" | "introduced_at" | "last_mentioned" | "resolved_at">) {
  const valid = (value: number | null) => Number.isInteger(value) && Number(value) > 0
  const first = valid(thread.first_mentioned) ? thread.first_mentioned : thread.introduced_at
  if (!valid(first)) return "Chapter not located"
  const last = valid(thread.resolved_at) ? thread.resolved_at : thread.last_mentioned
  return valid(last) && Number(last) > Number(first) ? `Chapters ${first}–${last}` : `Chapter ${first}`
}

export function threadMatches(thread: PlotThreadPageItem, query: string) {
  const needle = query.trim().toLocaleLowerCase()
  return [thread.title, thread.description, thread.type, ...(thread.tags ?? [])].some((value) => value?.toLocaleLowerCase().includes(needle))
}

export async function loadPlotThreadSummaries(bookId: string, chapter?: number): Promise<PlotThreadPageItem[]> {
  const items = new Map<string, PlotThreadPageItem>()
  const seen = new Set<string>()
  let cursor: string | null = null
  do {
    const page = await readerApi.getPlotThreadsPage(bookId, { chapter, cursor, limit: 100 })
    for (const item of page.items) items.set(item.id, item)
    if (!page.has_more) break
    if (!page.next_cursor || seen.has(page.next_cursor)) throw new Error("Plot thread pagination did not advance")
    cursor = page.next_cursor
    seen.add(cursor)
  } while (cursor)
  return [...items.values()]
}

export function plotThreadNoteContent(thread: PlotThread, note: string, status: string) {
  return [thread.description?.trim(), threadChapterRange(thread), `Status: ${THREAD_STATUS_LABELS[status] ?? "Unknown"}`,
    thread.risk?.trim() ? `## Risk\n\n${thread.risk.trim()}` : "",
    thread.suggested_action?.trim() ? `## Suggested action\n\n${thread.suggested_action.trim()}` : "",
    note.trim() ? `## Private note\n\n${note.trim()}` : "",
  ].filter(Boolean).join("\n\n")
}
