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

    expect(text()).toContain("The Lantern Gate author loop")
    expect(text()).toContain("Mara")
    expect(text()).toContain("reader@example.com")
    await click("Open upload tools")
    expect(text()).toContain("Hide upload tools")
    expect(text()).toContain("Dynamic runtime panel")
    await click("Convert to task")
    expect(booksApiMock.updateWriterWorkspace).toHaveBeenCalled()

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

    await click("Convert to task", 2)
    expect(betaReadsApiMock.updateBookFeedbackItem).toHaveBeenCalled()
  })
})
