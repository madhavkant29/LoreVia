// @vitest-environment jsdom

import { describe, expect, it } from "vitest"

import {
  booksApiMock,
  click,
  defaultQueryResult,
  pushMock,
  queryRefetchMock,
  renderPage,
  replaceMock,
  resetRenderedPage,
  text,
  useQueryMock,
} from "./runtime-pages-expanded.test-utils"

import BookOverviewPage from "@/app/(reader)/[bookId]/page"

describe("book overview runtime page coverage", () => {
  it("renders loaded and error flows and calls navigation/save handlers", async () => {
    await renderPage(<BookOverviewPage />)

    expect(text()).toContain("Project signals")
    expect(text()).toContain("72% complete")
    await click("Switch reader mode")
    expect(booksApiMock.setMode).toHaveBeenCalledWith("book-1", "reader")
    await click("Read")
    expect(pushMock).toHaveBeenCalledWith("/book-1/chapter/3")
    await click("Open mock manuscript")
    expect(pushMock).toHaveBeenCalledWith("/book-1/manuscript")
    await click("Open mock graph")
    expect(pushMock).toHaveBeenCalledWith("/book-1/graph")
    await click("Save mock goal")
    expect(booksApiMock.updateWriterWorkspace).toHaveBeenCalledWith(
      "book-1",
      expect.objectContaining({ goal_calendar: [{ id: "goal-1" }] }),
    )
    await click("Add scene")
    expect(pushMock).toHaveBeenCalledWith("/book-1/manuscript?newScene=1")

    resetRenderedPage()
    useQueryMock.mockImplementation(({ queryKey }: { queryKey: unknown }) => {
      const key = Array.isArray(queryKey) ? queryKey.join(":") : String(queryKey)
      if (key === "book-1:overview") {
        return {
          data: null,
          isLoading: false,
          isError: true,
          isSuccess: false,
          refetch: queryRefetchMock,
        }
      }
      return defaultQueryResult(null)
    })
    await renderPage(<BookOverviewPage />)
    expect(text()).toContain("Failed to load book overview")
    await click("Retry")
    expect(queryRefetchMock).toHaveBeenCalled()
    expect(replaceMock).toHaveBeenCalledWith("/library")
  })
})
