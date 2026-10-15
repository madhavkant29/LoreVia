import { describe, expect, it } from "vitest"
import { nextTimelineEventOffset, timelineItems, timelineRangeLabel, visibleTimelineSpan } from "./timelinePage.helpers"
import type { TimelineResponse } from "@/types/reader"

const chapters = [1, 3, 5].map((number) => ({ number, title: null }))
const empty: TimelineResponse = { chapters, events: [], character_tracks: [], thread_tracks: [], relationship_markers: [] }

describe("timeline chapter positions", () => {
  it("clips spans to visible sparse chapters without inventing endpoints", () => {
    expect(visibleTimelineSpan(chapters, 2, 4)).toEqual({ start: 1, end: 1 })
    expect(visibleTimelineSpan(chapters, 1, 9)).toEqual({ start: 0, end: 2 })
    expect(visibleTimelineSpan(chapters, 2, 2)).toBeNull()
    expect(visibleTimelineSpan(chapters, 6, 9)).toBeNull()
    expect(visibleTimelineSpan([], 1, 2)).toBeNull()
  })
  it.each([[0, 3], [3, 1], [NaN, 2], [1, Infinity], [1.5, 3]])("rejects malformed range %s to %s", (start, end) => {
    expect(visibleTimelineSpan(chapters, start, end)).toBeNull()
    expect(timelineRangeLabel(start, end)).toBe("Chapter range unavailable")
  })
  it("labels single chapters and spans", () => {
    expect(timelineRangeLabel(1, 1)).toBe("Chapter 1")
    expect(timelineRangeLabel(1, 5)).toBe("Chapters 1–5")
  })
})

describe("timeline lists and pagination", () => {
  it("handles empty tracks and filters without mutating response", () => {
    expect(timelineItems(empty, "all")).toEqual([])
    const data: TimelineResponse = { ...empty, character_tracks: [{ id: "a", name: "Nora", role: null, detail: null, start_chapter: 3, end_chapter: 5 }], relationship_markers: [{ id: "b", title: "Trust changes", detail: null, chapter_number: 1 }], thread_tracks: [{ id: "c", title: "The key", status: "open", start_chapter: 3, end_chapter: 5, note: "", detail: "Still missing" }] }
    expect(timelineItems(data, "all").map((item) => item.title)).toEqual(["Trust changes", "Nora", "The key"])
    expect(timelineItems(data, "characters")[0].kind).toBe("Character")
    expect(timelineItems(data, "plotThreads")[0].detail).toBe("Still missing")
    expect(timelineItems(data, "relationships")).toHaveLength(1)
    expect(timelineItems(data, "events")).toEqual([])
    expect(data.character_tracks).toHaveLength(1)
  })
  it("only advances pagination for valid forward offsets", () => {
    expect(nextTimelineEventOffset({ ...empty, has_more: true, next_offset: 100 }, 0)).toBe(100)
    for (const next_offset of [undefined, null, 0, -1, 0.5, NaN]) expect(nextTimelineEventOffset({ ...empty, has_more: true, next_offset }, 0)).toBeUndefined()
    expect(nextTimelineEventOffset({ ...empty, has_more: false, next_offset: 100 }, 0)).toBeUndefined()
    expect(nextTimelineEventOffset({ ...empty, has_more: true, next_offset: 100 }, 100)).toBeUndefined()
  })
})
