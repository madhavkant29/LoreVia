// @vitest-environment jsdom

import { describe, expect, it } from "vitest"

import {
  authState,
  bookModeState,
  booksApiMock,
  click,
  flush,
  getContainer,
  intelligenceApiMock,
  readerApiMock,
  render,
  rerender,
  routerMock,
  setTextareaValue,
  pressTextareaEnter,
  text,
  waitForText,
} from "./runtime-reader-routes.test-utils"

import SeriesAskPage from "@/app/(dashboard)/series/[seriesId]/ask/page"
import AskPage from "@/app/(reader)/[bookId]/ask/page"
import ChapterListPage from "@/app/(reader)/[bookId]/chapters/page"
import BookNotesPage from "@/app/(reader)/[bookId]/notes/page"

describe("reader core runtime routes", () => {
  it("keeps the question and partial response after an interrupted stream", async () => {
    bookModeState.value = "reader"
    intelligenceApiMock.answerStream.mockImplementationOnce(async (_book, _question, _chapter, handlers) => { handlers.onDelta("A partial answer"); throw new Error("stream ended") })
    await render(<AskPage />)
    setTextareaValue("Where is the gate?")
    await pressTextareaEnter()
    await flush()
    expect(text()).toContain("A partial answer")
    expect(text()).toContain("The answer did not finish")
    expect(getContainer()?.querySelector("textarea")?.value).toBe("Where is the gate?")
    const unload = new Event("beforeunload", { cancelable: true })
    window.dispatchEvent(unload)
    expect(unload.defaultPrevented).toBe(true)
  })
  it("reports failed chapter read updates and retries the same intended status", async () => {
    readerApiMock.updateChapterReadStatus.mockRejectedValueOnce(new Error("Unavailable"))
    await render(<ChapterListPage />)
    await click("Toggle read 1")
    await waitForText("Could not update chapter 1")
    await click("Retry")
    await waitForText("Chapter 1 marked as read.")
    expect(readerApiMock.updateChapterReadStatus).toHaveBeenLastCalledWith("book-1", 1, true)
  })

  it("reports failed bulk read updates and allows a retry", async () => {
    readerApiMock.markBookRead.mockRejectedValueOnce(new Error("Unavailable"))
    await render(<ChapterListPage />)
    await click("Mark book as read")
    await waitForText("Could not mark the book as read")
    await click("Retry")
    await waitForText("Book marked as read.")
  })

  it("renders chapter, notes vault, ask, and series ask routes with core actions", async () => {
    await render(<ChapterListPage />)
    expect(text()).toContain("The Lantern Gate")
    expect(text()).toContain("Chapter list mock")
    await click("Home")
    expect(routerMock.back).toHaveBeenCalled()
    await click("Mark book as read")
    expect(readerApiMock.markBookRead).toHaveBeenCalledWith("book-1")
    await click("Toggle read 1")
    expect(readerApiMock.updateChapterReadStatus).toHaveBeenCalledWith("book-1", 1, true)
    await click("Open 1")
    expect(routerMock.push).toHaveBeenCalledWith("/book-1/chapter/1")
    await click("Remove 1")
    expect(booksApiMock.deleteChapter).toHaveBeenCalledWith("book-1", 1)

    await rerender(<BookNotesPage />)
    await waitForText("Chapter-linked notes")
    expect(text()).toContain("The Lantern Gate")
    expect(text()).toContain("Chapter-linked notes")
    await click("Chapter-linked notes")
    await waitForText("Continuity note")
    expect(text()).toContain("Continuity note")

    bookModeState.value = "reader"
    await rerender(<AskPage />)
    setTextareaValue("What happened at the gate?")
    await pressTextareaEnter()
    await flush()
    expect(intelligenceApiMock.answerStream).toHaveBeenCalled()
    expect(text()).toContain("The answer cites chapter two.")

    bookModeState.value = "author"
    await rerender(<AskPage />)
    expect(routerMock.replace).toHaveBeenCalledWith("/book-1/advisor?mode=ask")

    await rerender(<SeriesAskPage />)
    expect(text()).toContain("Gate Cycle")
    await click("Which character changes most across the series?")
    await flush()
    expect(intelligenceApiMock.seriesAdvisorMessageStream).toHaveBeenCalled()
    expect(text()).toContain("Series answer")

    authState.user = { id: "free-user", tier: "free" }
    await rerender(<SeriesAskPage />)
    expect(text()).toContain("Series mode is reserved for paid plans")
  })
})
