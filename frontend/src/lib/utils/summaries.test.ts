import { describe, expect, it } from "vitest"

import { buildManuscriptRecap, normalizeChapterSummary } from "./summaries"
import type { ChapterSummary } from "@/types/reader"

describe("normalizeChapterSummary", () => {
  it("reads structured recaps and removes malformed detail rows", () => {
    const summary = normalizeChapterSummary({ content: '```json\n{"summary":"The gate opens.","key_events":[null,{"event":"Arrival"}],"char_changes":"bad","clues":[{"clue":3}]}\n```' } as ChapterSummary)
    expect(summary.content).toBe("The gate opens.")
    expect(summary.key_events).toEqual([{ event: "Arrival" }])
    expect(summary.char_changes).toEqual([])
    expect(summary.clues).toEqual([])
  })
  it("retains malformed structured text and safely handles absent content", () => {
    expect(normalizeChapterSummary({ content: "{unfinished" } as ChapterSummary).content).toBe("{unfinished")
    expect(normalizeChapterSummary({ content: null } as unknown as ChapterSummary)).toEqual({ content: "", key_events: [], char_changes: [], clues: [] })
  })
})

describe("buildManuscriptRecap", () => {
  it("returns null when no chapter recap is available", () => {
    expect(buildManuscriptRecap({ read_upto: 2, summaries: [
      { chapter_number: 1, chapter_title: "One", read: true, available: false, content: null, key_events: [] },
    ] })).toBeNull()
  })

  it("orders and normalizes available chapter recaps", () => {
    expect(buildManuscriptRecap({ read_upto: 2, summaries: [
      { chapter_number: 2, chapter_title: "Two", read: true, available: true, content: "The gate  opens.", key_events: [] },
      { chapter_number: 1, chapter_title: "One", read: true, available: true, content: "Nora arrives.\n", key_events: [] },
    ] })).toEqual({ chapterCount: 2, content: "Nora arrives. The gate opens." })
  })

  it("clips a long composite recap without breaking the final word", () => {
    const recap = buildManuscriptRecap({ read_upto: 1, summaries: [
      { chapter_number: 1, chapter_title: "One", read: true, available: true, content: "One two three four five six seven eight nine ten.", key_events: [] },
    ] }, 24)
    expect(recap?.content.endsWith("…")).toBe(true)
    expect(recap?.content).not.toContain("sev…")
  })
})
