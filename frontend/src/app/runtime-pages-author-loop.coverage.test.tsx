// @vitest-environment jsdom

import { act } from "react"
import { describe, expect, it } from "vitest"

import {
  betaReadsApiMock,
  booksApiMock,
  click,
  field,
  renderPage,
  setFieldValue,
  text,
  useQueryMock,
} from "./runtime-pages-expanded.test-utils"

import AuthorLoopPage from "@/app/(reader)/[bookId]/author-loop/page"

async function flush() {
  await Promise.resolve()
  await new Promise((resolve) => window.setTimeout(resolve, 0))
  await Promise.resolve()
}

describe("author loop runtime page coverage", () => {
  it("renders and exercises upload, issue, invite, and feedback actions", async () => {
    await renderPage(<AuthorLoopPage />)

    expect(text()).toContain("Revision workflow")
    expect(text()).not.toContain("Mara")
    expect(text()).not.toContain("reader@example.com")
    await click("Open upload tools")
    expect(text()).toContain("Hide upload tools")
    expect(text()).toContain("Dynamic runtime panel")

    await click("Characters")
    expect(text()).toContain("Mara")

    await click("Revision queue")
    await click("Convert to task")
    expect(booksApiMock.updateWriterWorkspace).toHaveBeenCalled()

    await click("Invite readers")
    setFieldValue(field<HTMLInputElement>('input[aria-label="Reader email"]'), "beta@example.com")
    setFieldValue(field<HTMLSelectElement>('select[aria-label="Scope"]'), "chapter_range")
    await act(flush)
    setFieldValue(field<HTMLInputElement>('input[aria-label="From chapter"]'), "2")
    setFieldValue(field<HTMLInputElement>('input[aria-label="Through chapter"]'), "5")
    await click("Send beta invite")
    expect(betaReadsApiMock.createAssignment).toHaveBeenCalledWith(
      "book-1",
      expect.objectContaining({ readerEmail: "beta@example.com" }),
    )

    await click("Reader feedback")
    expect(text()).toContain("reader@example.com")
    await click("Convert to task")
    expect(betaReadsApiMock.updateBookFeedbackItem).toHaveBeenCalled()
  })

  it("defers secondary data until its workflow step is selected", async () => {
    await renderPage(<AuthorLoopPage />)

    const queryOptions = useQueryMock.mock.calls.map(([options]) => options as { queryKey: unknown; enabled?: boolean })
    const optionsFor = (suffix: string) => queryOptions.find(({ queryKey }) => {
      const key = Array.isArray(queryKey) ? queryKey.join(":") : String(queryKey)
      return key.endsWith(suffix)
    })

    expect(optionsFor("characters:author-loop")?.enabled).toBe(false)
    expect(optionsFor("story-health")?.enabled).toBe(false)
    expect(optionsFor("chapter-reports:12")?.enabled).toBe(false)
    expect(optionsFor("revision-intelligence")?.enabled).toBe(false)
    expect(optionsFor("beta-assignments")?.enabled).toBe(false)
  })
})
