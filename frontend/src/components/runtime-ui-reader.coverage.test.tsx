// @vitest-environment jsdom

import { act } from "react"
import { describe, expect, it, vi } from "vitest"

import {
  ReaderView,
  cleanupRuntimeUi,
  click,
  flush,
  makeLoadedReaderState,
  readerState,
  renderElement,
  replaceMock,
  text,
} from "./runtime-ui-components.test-utils"

describe("runtime ReaderView", () => {
  it("renders loading, error, and loaded interaction states", async () => {
    readerState.value = {
      data: null,
      loading: true,
      error: null,
      tap: vi.fn(),
      contextResult: null,
      contextLoading: false,
      clearContext: vi.fn(),
      saveProgress: vi.fn(),
    }
    await renderElement(<ReaderView bookId="book-1" chapterNum={2} />)
    expect(text()).toContain("Loading chapter")

    cleanupRuntimeUi()
    readerState.value = {
      data: null,
      loading: false,
      error: "Chapter unavailable",
      tap: vi.fn(),
      contextResult: null,
      contextLoading: false,
      clearContext: vi.fn(),
      saveProgress: vi.fn(),
    }
    await renderElement(<ReaderView bookId="book-1" chapterNum={2} />)
    await act(flush)
    expect(replaceMock).not.toHaveBeenCalled()
    expect(text()).toContain("Retry chapter")
    expect(text()).toContain("Chapter unavailable")

    cleanupRuntimeUi()
    readerState.value = makeLoadedReaderState()
    await renderElement(<ReaderView bookId="book-1" chapterNum={2} />)
    expect(text()).toContain("The Door")
    expect(text()).toContain("Mara opens the gate")
    expect(text()).toContain("Context answer")

    await click("Summary toolbar")
    expect(text()).toContain("dynamic-panel")
    await click("Toggle theme")
    await click("Bigger font")
    await click("Relax display")
    await click("Quote mode")
    await click("Select quote")
    expect(text()).toContain("Selected quote")
    await click("Close panel")
    expect(text()).not.toContain("Selected quote")
  })
})
