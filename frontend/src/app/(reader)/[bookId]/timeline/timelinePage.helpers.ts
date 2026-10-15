import type { TimelineChapter, TimelineResponse } from "@/types/reader"

export type TimelineLane = "all" | "characters" | "plotThreads" | "relationships" | "events"
export type TimelineView = "auto" | "list" | "lanes"
export type TimelineItem = { id: string; title: string; kind: string; detail?: string | null; start: number; end: number; lane: Exclude<TimelineLane, "all" | "events"> }

export function visibleTimelineSpan(chapters: TimelineChapter[], start: number, end: number) {
  if (!Number.isInteger(start) || !Number.isInteger(end) || start < 1 || end < start) return null
  const indices = chapters.flatMap((chapter, index) => chapter.number >= start && chapter.number <= end ? [index] : [])
  return indices.length ? { start: indices[0], end: indices[indices.length - 1] } : null
}

export function timelineRangeLabel(start: number, end: number) {
  if (!Number.isInteger(start) || !Number.isInteger(end) || start < 1 || end < start) return "Chapter range unavailable"
  return start === end ? `Chapter ${start}` : `Chapters ${start}–${end}`
}

export function timelineItems(timeline: TimelineResponse, lane: TimelineLane): TimelineItem[] {
  const items: TimelineItem[] = [
    ...(timeline.character_tracks ?? []).map((track) => ({ id: `character-${track.id}`, title: track.name, kind: track.role || "Character", detail: track.detail, start: track.start_chapter, end: track.end_chapter, lane: "characters" as const })),
    ...(timeline.thread_tracks ?? []).map((track) => ({ id: `thread-${track.id}`, title: track.title, kind: track.status, detail: track.note || track.detail, start: track.start_chapter, end: track.end_chapter, lane: "plotThreads" as const })),
    ...(timeline.relationship_markers ?? []).map((marker) => ({ id: `relationship-${marker.id}`, title: marker.title, kind: "Relationship shift", detail: marker.detail, start: marker.chapter_number, end: marker.chapter_number, lane: "relationships" as const })),
  ]
  return items.filter((item) => lane === "all" || item.lane === lane).sort((a, b) => a.start - b.start || a.title.localeCompare(b.title))
}

export function nextTimelineEventOffset(page: TimelineResponse, currentOffset: number) {
  const next = page.next_offset
  return page.has_more && typeof next === "number" && Number.isInteger(next) && next > currentOffset ? next : undefined
}
