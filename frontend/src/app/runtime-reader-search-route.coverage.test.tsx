// @vitest-environment jsdom

import { describe, expect, it } from "vitest"

import {
  click,
  flush,
  readerApiMock,
  render,
  searchParamsState,
  setInputValue,
  text,
} from "./runtime-reader-routes.test-utils"

import SearchPage from "@/app/(reader)/[bookId]/search/page"

describe("reader search runtime route", () => {
  it("drives semantic, thematic, seeded, empty, and error search states", async () => {
    searchParamsState.value = new URLSearchParams("q=seeded gate")
    readerApiMock.search.mockResolvedValueOnce([
      {
        chapter_num: 2,
        chapter_title: "The Key",
        relevance: 0.84,
        summary: "Mara finds the gate",
        text: "The gate opens.",
      },
    ])
    await render(<SearchPage />)
    await flush()
    expect(text()).toContain("Search Your Writing")
    expect(text()).toContain("Mara finds the gate")

    await click("Themes")
    readerApiMock.thematicSearch.mockResolvedValueOnce({
      results: [
        {
          chapter_number: 3,
          chapter_title: "Ash",
          score: 0.91,
          summary: "The ash theme returns.",
        },
      ],
    })
    setInputValue('input[aria-label="Search manuscript"]', "ash motif")
    await click("Search manuscript")
    expect(text()).toContain("The ash theme returns")

    readerApiMock.thematicSearch.mockRejectedValueOnce(new Error("boom"))
    setInputValue('input[aria-label="Search manuscript"]', "broken")
    await click("Search manuscript")
    expect(text()).toContain("Search failed. Please try again.")
  })
})
