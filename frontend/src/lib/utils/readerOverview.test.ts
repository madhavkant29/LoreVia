import { describe, expect, it } from "vitest"

import {
  buildReaderChapterPreview,
  estimateChapterRemainingReadingMinutes,
  estimateRemainingReadingMinutes,
  formatBookFormatLabel,
  formatReadingDuration,
} from "./readerOverview"

describe("reader overview utils", () => {
  it("formats short reading durations in minutes", () => {
    expect(formatReadingDuration(42)).toBe("42 min")
  })

  it("formats longer reading durations in hours and minutes", () => {
    expect(formatReadingDuration(252)).toBe("4h 12m")
  })

  it("maps book formats into reader-facing labels", () => {
    expect(formatBookFormatLabel("epub")).toBe("ePub")
    expect(formatBookFormatLabel("md")).toBe("Markdown")
  })

  it("estimates remaining reading time from progress and word count", () => {
    expect(estimateRemainingReadingMinutes({
      total_words: 92000,
      total_tokens: null,
      total_chapters: 20,
      work_type: "novel",
    }, {
      percent_complete: 50,
      chapters_left: 10,
      chapters_read_count: 10,
    })).toBe(200)
  })

  it("does not invent reading time when the stored word count is unavailable", () => {
    expect(estimateRemainingReadingMinutes({
      total_words: undefined,
      total_tokens: 12000,
      total_chapters: 5,
      work_type: "novel",
    }, null)).toBeNull()
    expect(formatReadingDuration(null)).toBe("Not available")
  })

  it("estimates chapter time from its measured word count and saved position", () => {
    expect(estimateChapterRemainingReadingMinutes(2300, 0.5)).toBe(5)
    expect(estimateChapterRemainingReadingMinutes(undefined, 0.5)).toBeNull()
  })

  it("builds a chapter preview window around the current chapter", () => {
    const chapters = Array.from({ length: 12 }, (_, index) => ({
      number: index + 1,
      title: `Chapter ${index + 1}`,
      processed: true,
      read: index < 5,
    }))

    expect(buildReaderChapterPreview(chapters, 7).map((chapter) => chapter.number)).toEqual([5, 6, 7, 8, 9, 10, 11, 12])
  })
})
