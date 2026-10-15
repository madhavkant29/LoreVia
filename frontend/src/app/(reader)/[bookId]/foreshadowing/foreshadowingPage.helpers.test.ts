import { expect, it } from "vitest"
import type { ForeshadowingItem } from "@/types/reader"
import { hasSuggestedConnection, signalChapters, signalMatches } from "./foreshadowingPage.helpers"
const item: ForeshadowingItem = { chapter_number: 3, chapter_title: "The river", clue: "A brass key", foreshadows: "A hidden gate" }
it("distinguishes recorded connections from blank or missing fields", () => {
  expect(hasSuggestedConnection(item)).toBe(true)
  expect(hasSuggestedConnection({ ...item, foreshadows: "   " })).toBe(false)
  expect(hasSuggestedConnection({ ...item, foreshadows: null })).toBe(false)
})
it("combines view, case-insensitive text, and source filters", () => {
  expect(signalMatches(item, "linked", " KEY ", "3")).toBe(true)
  expect(signalMatches(item, "all", "River", "")).toBe(true)
  expect(signalMatches(item, "all", "Chapter 3", "")).toBe(true)
  expect(signalMatches(item, "all", "gate", "")).toBe(true)
  expect(signalMatches(item, "unlinked", "", "")).toBe(false)
  expect(signalMatches(item, "all", "", "2")).toBe(false)
  expect(signalMatches(item, "linked", "missing", "")).toBe(false)
  expect(signalMatches({ ...item, foreshadows: null, chapter_title: null }, "unlinked", "", "")).toBe(true)
})
it("provides unique, sorted positive chapter options without mutating inputs", () => {
  const items = [5, 1, 5, 0, -1, 1.5].map((chapter_number) => ({ ...item, chapter_number }))
  expect(signalChapters(items)).toEqual([1, 5])
  expect(items[0].chapter_number).toBe(5)
  expect(signalChapters([])).toEqual([])
})
