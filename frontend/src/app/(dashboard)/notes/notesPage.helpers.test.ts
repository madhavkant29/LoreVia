// @vitest-environment jsdom
import { describe, expect, it } from "vitest"
import type { BookNote } from "@/types/book"
import { filterNotes, indexNotes, noteBooks, noteChapterHref, noteUpdatedDate } from "./notesPage.helpers"

const note: BookNote = { id: "n1", book_id: "b1", book_title: "Same title", chapter_number: 3, chapter_title: "Opening", title: "Oath", body: '<p>Silver <strong>key</strong> &amp; gate</p>', tags: ["revision"], created_at: "2026-01-01", updated_at: "2026-01-01" }

describe("account notes index", () => {
  it("searches readable text across formatting boundaries and tags without matching HTML markup", () => {
    const entries = indexNotes([note])
    expect(entries[0].plainText).toBe("Silver key & gate")
    expect(filterNotes(entries, " SILVER KEY ", "")).toHaveLength(1)
    expect(filterNotes(entries, "revision", "")).toHaveLength(1)
    expect(filterNotes(entries, "strong", "")).toHaveLength(0)
    expect(filterNotes(entries, "key", "b2")).toHaveLength(0)
  })
  it("handles empty and missing optional fields without inventing note text", () => {
    expect(indexNotes([])).toEqual([])
    expect(indexNotes([{ ...note, body: null, title: null, tags: undefined } as unknown as BookNote])[0].plainText).toBe("")
  })
  it("keeps manuscripts with identical titles distinct and removes duplicate options", () => {
    expect(noteBooks([note, note, { ...note, book_id: "b2" }])).toEqual([{ id: "b1", title: "Same title" }, { id: "b2", title: "Same title" }])
    expect(noteBooks([{ ...note, book_title: "" }])[0].title).toBe("Untitled manuscript")
  })
  it("formats dates and identifies missing or invalid timestamps", () => {
    expect(noteUpdatedDate("2026-01-01")?.iso).toBe("2026-01-01T00:00:00.000Z")
    expect(noteUpdatedDate("")).toBeNull()
    expect(noteUpdatedDate("not-a-date")).toBeNull()
  })
  it("links only positive integer chapter numbers", () => {
    expect(noteChapterHref(note)).toBe("/b1/chapter/3")
    for (const chapter_number of [null, 0, -1, 1.5, NaN]) expect(noteChapterHref({ ...note, chapter_number })).toBeNull()
    expect(noteChapterHref({ ...note, book_id: "" })).toBeNull()
  })
})
