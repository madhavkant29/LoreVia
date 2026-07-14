// @vitest-environment jsdom

import { act } from "react"
import { describe, expect, it } from "vitest"

import {
  click,
  flush,
  getContainer,
  render,
  rerender,
  setInputValue,
  text,
} from "./runtime-reader-routes.test-utils"

import AnalysisPage from "@/app/(reader)/[bookId]/analysis/page"
import CrossBookWikiPage from "@/app/(reader)/[bookId]/cross-book-wiki/page"
import GraphPage from "@/app/(reader)/[bookId]/graph/page"

describe("reader analysis runtime routes", () => {
  it("renders analysis, relationship graph, and cross-book wiki filters", async () => {
    await render(<AnalysisPage />)
    expect(text()).toContain("Analysis workspace")
    expect(text()).toContain("Voice consistency")
    expect(text()).toContain("Ask LoreVia")

    await rerender(<GraphPage />)
    await flush()
    expect(text()).toContain("Relationship graph")
    expect(text()).toContain("Up to manuscript chapter")
    expect(text()).toContain("Dynamic route section")
    setInputValue('input[aria-label="Up to manuscript chapter"]', "99")
    await act(flush)
    const chapterInput = getContainer()?.querySelector(
      'input[aria-label="Up to manuscript chapter"]',
    ) as HTMLInputElement | null
    expect(chapterInput?.value).toBe("2")

    await rerender(<CrossBookWikiPage />)
    expect(text()).toContain("Series wiki connections")
    expect(text()).toContain("Gate Cycle")
    expect(text()).toContain("Mara Vale")
    expect(text()).toContain("The Ash Door")
    setInputValue('input[aria-label="Search matches"]', "moon")
    await act(flush)
    expect(text()).toContain("No matches found")
    setInputValue('input[type="range"]', "50")
    await act(flush)
    expect(text()).toContain("Moon Gate")
    await click("Wiki entries")
    expect(text()).toContain("Lunar Gate")
    await click("Characters")
    expect(text()).toContain("No matches found")
  })
})
