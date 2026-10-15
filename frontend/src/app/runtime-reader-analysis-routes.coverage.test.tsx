// @vitest-environment jsdom

import { act } from "react"
import { describe, expect, it } from "vitest"

import {
  flush,
  getContainer,
  render,
  rerender,
  searchParamsState,
  setInputValue,
  text,
} from "./runtime-reader-routes.test-utils"

import AnalysisPage from "@/app/(reader)/[bookId]/analysis/page"
import CrossBookWikiPage from "@/app/(reader)/[bookId]/cross-book-wiki/page"
import GraphPage from "@/app/(reader)/[bookId]/graph/page"

describe("reader analysis runtime routes", () => {
  it("renders analysis, relationship graph, and cross-book wiki filters", async () => {
    await render(<AnalysisPage />)
    expect(text()).toContain("Findings")
    expect(text()).toContain("The gate oath changes between chapters")
    expect(text()).toContain("Voice consistency")
    expect(text()).toContain("Story advisor")

    searchParamsState.value = new URLSearchParams("view=chapters")
    await rerender(<AnalysisPage />)
    expect(text()).toContain("Mara opens the gate and changes her alliance")
    expect(text()).toContain("Mara now trusts Theo")
    expect(text()).not.toContain("Threads resolved")

    await rerender(<GraphPage />)
    await flush()
    expect(text()).toContain("Relationships")
    expect(text()).toContain("Chapter")
    expect(text()).toContain("Dynamic route section")
    setInputValue('select[aria-label="Up to manuscript chapter"]', "2")
    await act(flush)
    const chapterInput = getContainer()?.querySelector(
      'select[aria-label="Up to manuscript chapter"]',
    ) as HTMLSelectElement | null
    expect(chapterInput?.value).toBe("2")

    searchParamsState.value = new URLSearchParams("view=evolution")
    await rerender(<GraphPage />)
    await flush()
    expect(text()).toContain("Mara ↔ Joren")
    expect(text()).toContain("They share the key.")

    await rerender(<CrossBookWikiPage />)
    expect(text()).toContain("Series wiki")
    expect(text()).toContain("Gate Cycle")
    expect(text()).toContain("Mara Vale")
    expect(text()).toContain("The Ash Door")
    setInputValue('select[aria-label="Minimum similarity"]', "95")
    setInputValue('input[aria-label="Search references"]', "moon")
    await act(flush)
    expect(text()).toContain("No matches found")
    setInputValue('select[aria-label="Minimum similarity"]', "90")
    await act(flush)
    expect(text()).toContain("Moon Gate")
    setInputValue('select[aria-label="Reference type"]', "wiki")
    await act(flush)
    expect(text()).toContain("Lunar Gate")
    setInputValue('select[aria-label="Reference type"]', "characters")
    await act(flush)
    expect(text()).toContain("No matches found")
  })
})
