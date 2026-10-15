import { describe, expect, it } from "vitest"
import { chapterScrollFraction, parseReaderBookmark, readerFontSize } from "./readerPosition"

describe("reader position values", () => {
  it("validates bookmark identity and safely bounds stored positions", () => {
    const raw = JSON.stringify({ bookId: "sky-of-ash--book-1", chapter: 2, scrollPct: 1.4, selectedText: "old draft" })
    expect(parseReaderBookmark(raw, "book-1", 2)).toMatchObject({ scrollPct: 1, selectedText: null })
    expect(parseReaderBookmark(raw, "book-2", 2)).toBeNull()
    expect(parseReaderBookmark(raw, "book-1", 3)).toBeNull()
    for (const value of [null, "broken", "{}", '{"bookId":5}', '{"bookId":"book-1","chapter":2,"scrollPct":"0.5"}']) {
      expect(parseReaderBookmark(value, "book-1", 2)).toBeNull()
    }
  })
  it("bounds font size and rejects malformed stored preferences", () => {
    expect(readerFontSize("24")).toBe(24)
    expect(readerFontSize("500")).toBe(32)
    expect(readerFontSize("4")).toBe(12)
    for (const value of [null, "", "abc", "Infinity"]) expect(readerFontSize(value)).toBe(20)
  })
  it("reports scroll position for short chapters and clamps overscroll", () => {
    expect(chapterScrollFraction(100, 500, 300)).toBe(0.5)
    expect(chapterScrollFraction(0, 200, 300)).toBe(1)
    expect(chapterScrollFraction(-10, 500, 300)).toBe(0)
    expect(chapterScrollFraction(800, 500, 300)).toBe(1)
  })
})
