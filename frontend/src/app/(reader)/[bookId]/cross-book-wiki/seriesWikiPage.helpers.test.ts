import { describe, expect, it } from "vitest"
import type { CrossBookIntelligence, CrossBookMatch } from "@/types/intelligence"
import { filterSeriesReferences, seriesComparisonIds, seriesReferences, seriesSimilarityLabel } from "./seriesWikiPage.helpers"
const match = (values: Partial<CrossBookMatch> = {}): CrossBookMatch => ({ left_book_id: "book-1", right_book_id: "book-2", left_name: "Nora", right_name: "Nora Veyl", similarity: .96, ...values })
const data = (values: Partial<CrossBookIntelligence> = {}): CrossBookIntelligence => ({ series_name: "Cycle", comparison_book_ids: ["book-1", "book-2", "book-3"], character_matches: [match()], wiki_matches: [], ...values })
const books = [{ id: "book-1", title: "First" }, { id: "book-2", title: "Second" }, { id: "book-3", title: "Third" }]

describe("series comparison references", () => {
  it("handles absent responses and canonicalizes unique comparison ids", () => {
    expect(seriesComparisonIds(null)).toEqual([])
    expect(seriesReferences(null, [], "book-1")).toEqual({ references: [], omitted: 0 })
    expect(seriesComparisonIds(data({ comparison_book_ids: ["first--book-1", "book-1", "", "book-2"] }))).toEqual(["book-1", "book-2"])
  })
  it("orients a right-side current book and labels both actual source books", () => {
    const result = seriesReferences(data(), books, "second--book-2").references[0]
    expect(result).toMatchObject({ firstName: "Nora Veyl", firstBookTitle: "Second", firstBookId: "book-2", secondBookTitle: "First", involvesCurrentBook: true })
  })
  it("preserves pairs between other books without labeling either as the current book", () => {
    const result = seriesReferences(data({ character_matches: [match({ left_book_id: "book-2", right_book_id: "book-3" })] }), books, "book-1").references[0]
    expect(result).toMatchObject({ firstBookTitle: "Second", secondBookTitle: "Third", involvesCurrentBook: false })
  })
  it("retains usable identifiers when title metadata is missing", () => {
    expect(seriesReferences(data(), [], "book-1").references[0]).toMatchObject({ firstBookTitle: "Book book-1", secondBookTitle: "Book book-2" })
  })
  it.each([NaN, Infinity, -1, 1.1])("omits invalid similarity %s", similarity => {
    expect(seriesReferences(data({ character_matches: [match({ similarity })] }), books, "book-1")).toEqual({ references: [], omitted: 1 })
  })
  it.each([{ left_name: " " }, { right_name: "" }, { right_book_id: "book-1" }, { right_book_id: "missing" }])("omits invalid identity %j", values => {
    expect(seriesReferences(data({ character_matches: [match(values)] }), books, "book-1").omitted).toBe(1)
  })
  it("deduplicates reversed pairs using the strongest score while preserving distinct entry types", () => {
    const result = seriesReferences(data({ character_matches: [match(), match({ left_book_id: "book-2", right_book_id: "book-1", left_name: "Nora Veyl", right_name: "Nora", similarity: .98 })], wiki_matches: [match({ entry_type: "place" }), match({ entry_type: "artifact" })] }), books, "book-1")
    expect(result.references).toHaveLength(3)
    expect(result.references[0].similarity).toBe(.98)
    expect(new Set(result.references.map(item => item.key)).size).toBe(3)
  })
  it("filters current/whole-series scope, type, names, titles and exact similarity boundaries", () => {
    const refs = seriesReferences(data({ character_matches: [match(), match({ left_book_id: "book-2", right_book_id: "book-3", similarity: .8999 })], wiki_matches: [match({ left_name: "Glass Road", entry_type: "route", similarity: .94 })] }), books, "book-1").references
    const options = { mode: "all" as const, scope: "current" as const, threshold: 90, query: "" }
    expect(filterSeriesReferences(refs, options)).toHaveLength(2)
    expect(filterSeriesReferences(refs, { ...options, query: "SECOND", mode: "wiki" })).toHaveLength(1)
    expect(filterSeriesReferences(refs, { ...options, query: "route" })).toHaveLength(1)
    expect(filterSeriesReferences(refs, { ...options, threshold: 95 })).toHaveLength(1)
    expect(filterSeriesReferences(refs, { ...options, scope: "series", threshold: 90 })).toHaveLength(2)
    expect(filterSeriesReferences(refs, { ...options, scope: "series", threshold: 0 })).toHaveLength(3)
    expect(filterSeriesReferences(refs, { ...options, query: "missing" })).toEqual([])
  })
  it("does not truncate large returned sets", () => {
    const result = seriesReferences(data({ character_matches: Array.from({ length: 150 }, (_, i) => match({ left_name: `Person ${i}` })) }), books, "book-1")
    expect(result.references).toHaveLength(150)
  })
  it("formats similarity without implying identity confidence", () => {
    expect(seriesSimilarityLabel(.9)).toBe("90%")
    expect(seriesSimilarityLabel(.946)).toBe("94.6%")
    expect(seriesSimilarityLabel(1)).toBe("100%")
  })
})
