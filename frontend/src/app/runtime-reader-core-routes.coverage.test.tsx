// @vitest-environment jsdom

import { describe, expect, it } from "vitest"

import {
  authState,
  booksApiMock,
  click,
  flush,
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
  it("renders chapter, notes vault, ask, and series ask routes with core actions", async () => {
    await render(<ChapterListPage />)
    expect(text()).toContain("The Lantern Gate")
    expect(text()).toContain("Chapter list mock")
    await click("Back to Manuscripts")
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
    await waitForText("Chapter-linked manuscript notes")
    expect(text()).toContain("The Lantern Gate")
    expect(text()).toContain("Chapter-linked manuscript notes")
    expect(text()).toContain("Continuity note")

    await rerender(<AskPage />)
    setTextareaValue("What happened at the gate?")
    await pressTextareaEnter()
    await flush()
    expect(intelligenceApiMock.answerStream).toHaveBeenCalled()
    expect(text()).toContain("The answer cites chapter two.")

    await rerender(<SeriesAskPage />)
    expect(text()).toContain("Gate Cycle")
    await click("Who is the most recurring side character?")
    await flush()
    expect(intelligenceApiMock.seriesAdvisorMessageStream).toHaveBeenCalled()
    expect(text()).toContain("Series answer")

    authState.user = { id: "free-user", tier: "free" }
    await rerender(<SeriesAskPage />)
    expect(text()).toContain("Series mode is reserved for paid plans")
  })
})
