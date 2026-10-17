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
    expect(text()).toContain("Search the manuscript")
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
    setInputValue('input[type="search"]', "ash motif")
    await click("Search manuscript")
    expect(text()).toContain("The ash theme returns")

    readerApiMock.thematicSearch.mockRejectedValueOnce(new Error("boom"))
    setInputValue('input[type="search"]', "broken")
    await click("Search manuscript")
    expect(text()).toContain("Search failed. Please try again.")
    expect(text()).toContain("The ash theme returns")
    await click("Passages")
    expect(text()).toContain("Mara finds the gate")
    expect(text()).not.toContain("Results for “broken”")
  })

  it("honors chapter scope from a link and rejects malformed chapter input", async () => {
    searchParamsState.value = new URLSearchParams("q=gate&chapter=2")
    readerApiMock.search.mockResolvedValueOnce([])
    await render(<SearchPage />)
    await flush()
    expect(readerApiMock.search).toHaveBeenCalledWith("book-1", "gate", 2)
    expect(text()).toContain("chapters 1–2")
    setInputValue('input[inputmode="numeric"]', "-1")
    await flush()
    expect(text()).toContain("Enter a whole chapter number")
    await click("Search manuscript")
    expect(readerApiMock.search).toHaveBeenCalledTimes(1)
  })
})
