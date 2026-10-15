import { describe, expect, it } from "vitest"
import { parseSearchChapter, searchFailureMessage, searchMatches } from "./searchPage.helpers"

describe("search scope and evidence", () => {
  it("accepts optional positive chapter limits including sparse numbering and rejects malformed values", () => {
    expect(parseSearchChapter(" ")).toBeUndefined()
    expect(parseSearchChapter(" 2 ")).toBe(2)
    expect(parseSearchChapter("99")).toBe(99)
    for (const value of ["0", "-1", "1.5", "2e2", "no", "9007199254740992"]) expect(parseSearchChapter(value)).toBeNull()
  })
  it("maps passage evidence and withholds results beyond the submitted scope", () => {
    const passage = { chapter_num: 2, chapter_title: "Gate", text: "Excerpt", summary: "Summary", relevance: 0.7 }
    expect(searchMatches([passage, { ...passage, chapter_num: 3 }, { ...passage, chapter_num: 0 }], "semantic", 2)).toEqual([{ chapter: 2, title: "Gate", text: "Excerpt", summary: "Summary" }])
    expect(searchMatches([], "semantic")).toEqual([])
  })
  it("preserves sparse theme evidence without inventing percentage scores or source text", () => {
    expect(searchMatches([{ chapter_number: 2, chapter_title: null, summary: null, score: 7 }], "thematic")).toEqual([{ chapter: 2, title: null, summary: null }])
  })
  it("distinguishes access and rate failures from generic search failure", () => {
    expect(searchFailureMessage(new Error("oops"))).toBe("Search failed. Please try again.")
    expect(searchFailureMessage({ isAxiosError: true, response: { status: 403 } })).toContain("Check your access")
    expect(searchFailureMessage({ isAxiosError: true, response: { status: 429 } })).toContain("temporarily rate limited")
    expect(searchFailureMessage({ isAxiosError: true, response: { status: 429, data: { detail: "Your daily limit refreshes tomorrow. Want higher limits now? Upgrade." } } })).toContain("today's search limit")
  })
})
