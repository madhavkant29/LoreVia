import { describe, expect, it } from "vitest"
import type { SavedQuote } from "@/types/book"
import { filterQuotes, quoteBooks, quoteSavedDate, quoteSource } from "./quotesPage.helpers"

const quote: SavedQuote = { id: "q1", book_id: "b1", book_title: "The Gate", chapter_number: 3, chapter_title: "Opening", character_name: "Mara", quote_text: "The gate remembers.", note: "An oath", created_at: "2026-01-01" }
describe("saved quote browsing", () => {
  it("searches all saved context and intersects the book filter", () => {
    for (const term of [" gate ", "OPENING", "Mara", "remembers", "oath", "3"]) expect(filterQuotes([quote], term, "b1")).toEqual([quote])
    expect(filterQuotes([quote], "gate", "b2")).toEqual([])
    expect(filterQuotes([quote], "missing", "")).toEqual([])
    expect(filterQuotes([], "", "")).toEqual([])
    expect(filterQuotes([{ ...quote, character_name: null, note: null, chapter_number: null }], "", "")).toHaveLength(1)
  })
  it("counts books by identity and tolerates empty titles", () => {
    expect(quoteBooks([quote, quote, { ...quote, book_id: "b2" }])).toHaveLength(2)
    expect(quoteBooks([{ ...quote, book_title: " " }])[0].title).toBe("Untitled book")
  })
  it("links to chapters only for positive integer references and otherwise offers the book", () => {
    expect(quoteSource(quote)).toEqual({ label: "Chapter 3 · Opening", href: "/b1/chapter/3", action: "Open chapter 3" })
    for (const chapter_number of [null, 0, -1, 1.5, NaN]) expect(quoteSource({ ...quote, chapter_number }).href).toBe("/b1")
    expect(quoteSource({ ...quote, book_id: "" }).href).toBeNull()
  })
  it("formats timestamps without displaying Invalid Date", () => {
    expect(quoteSavedDate("2026-01-01")?.iso).toBe("2026-01-01T00:00:00.000Z")
    expect(quoteSavedDate("bad")).toBeNull()
    expect(quoteSavedDate("")).toBeNull()
  })
})
