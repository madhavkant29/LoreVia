import { beforeEach, expect, it, vi } from "vitest"
import { loadPlotThreadSummaries, plotThreadNoteContent, threadChapterRange, threadMatches, threadView } from "./PlotTracker.helpers"
import type { PlotThread, PlotThreadPageItem } from "@/types/reader"
const getPage = vi.hoisted(() => vi.fn())
vi.mock("@/lib/api/reader", () => ({ readerApi: { getPlotThreadsPage: getPage } }))
const thread: PlotThreadPageItem = { id: "1", title: "River oath", description: null, status: "developing", type: "Promise", introduced_at: 2, first_mentioned: null, last_mentioned: 5, resolved_at: null, mention_count: 2, importance: 1, tags: ["payoff"] }
beforeEach(() => getPage.mockReset())
it.each([["introduced", "open"], ["ongoing", "open"], ["resolved", "resolved"], ["abandoned", "attention"], ["new status", "attention"]])("places %s in %s", (status, view) => expect(threadView(status)).toBe(view))
it("formats only valid, ordered chapter ranges", () => {
  expect(threadChapterRange(thread)).toBe("Chapters 2–5")
  expect(threadChapterRange({ ...thread, last_mentioned: 1 })).toBe("Chapter 2")
  expect(threadChapterRange({ ...thread, introduced_at: -1, first_mentioned: 0 })).toBe("Chapter not located")
  expect(threadChapterRange({ ...thread, resolved_at: 7 })).toBe("Chapters 2–7")
})
it("searches title, type, and tags with empty and null fields", () => {
  for (const search of [" RIVER ", "promise", "PAYOFF", ""]) expect(threadMatches(thread, search)).toBe(true)
  expect(threadMatches(thread, "missing")).toBe(false)
})
it("loads subsequent pages and deduplicates IDs", async () => {
  getPage.mockResolvedValueOnce({ items: [thread], has_more: true, next_cursor: "next" }).mockResolvedValueOnce({ items: [thread, { ...thread, id: "2" }], has_more: false, next_cursor: null })
  expect(await loadPlotThreadSummaries("book", 4)).toHaveLength(2)
  expect(getPage).toHaveBeenLastCalledWith("book", { chapter: 4, cursor: "next", limit: 100 })
})
it.each([null, "same"])("rejects an incomplete page with a missing or repeated cursor (%s)", async (cursor) => {
  getPage.mockResolvedValue({ items: [thread], has_more: true, next_cursor: cursor })
  await expect(loadPlotThreadSummaries("book")).rejects.toThrow("pagination did not advance")
})
it("propagates page failures instead of reporting a partial list as complete", async () => {
  getPage.mockResolvedValueOnce({ items: [thread], has_more: true, next_cursor: "next" }).mockRejectedValueOnce(new Error("offline"))
  await expect(loadPlotThreadSummaries("book")).rejects.toThrow("offline")
})
it("copies the edited status and note with the available evidence", () => {
  const detail: PlotThread = { ...thread, note: "old", character_ids: [], related_characters: [], risk: "Unfulfilled promise", suggested_action: "Return to the river" }
  expect(plotThreadNoteContent(detail, "New reminder", "resolved")).toContain("Status: Resolved")
  expect(plotThreadNoteContent(detail, "New reminder", "resolved")).toContain("New reminder")
  expect(plotThreadNoteContent(detail, "", "developing")).not.toContain("## Private note")
})
