import React, { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const useQueryMock = vi.hoisted(() => vi.fn())
const useQueryClientMock = vi.hoisted(() => vi.fn())
const prefetchQueryMock = vi.hoisted(() => vi.fn())
const getChapterMock = vi.hoisted(() => vi.fn())
const getContextMock = vi.hoisted(() => vi.fn())
const updateProgressMock = vi.hoisted(() => vi.fn())

vi.mock("@tanstack/react-query", () => ({
  useQuery: useQueryMock,
  useQueryClient: useQueryClientMock,
}))

vi.mock("@/lib/api/reader", () => ({
  readerApi: {
    getChapter: getChapterMock,
    getContext: getContextMock,
    updateProgress: updateProgressMock,
  },
}))

import { useReader } from "./useReader"
import type { ChapterData } from "@/types/reader"

describe("useReader", () => {
  let container: HTMLDivElement | null = null
  let root: Root | null = null
  let hookResult: ReturnType<typeof useReader> | null = null

  beforeEach(() => {
    ;(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
  })

  beforeEach(() => {
    useQueryMock.mockReset()
    useQueryClientMock.mockReset()
    prefetchQueryMock.mockReset()
    getChapterMock.mockReset()
    getContextMock.mockReset()
    updateProgressMock.mockReset()

    hookResult = null
    useQueryClientMock.mockReturnValue({
      prefetchQuery: prefetchQueryMock,
    })
  })

  afterEach(() => {
    if (root) {
      act(() => {
        root?.unmount()
      })
    }
    if (container) {
      container.remove()
    }
    container = null
    root = null
    hookResult = null
  })

  function render(bookId: string, chapterNum: number, useQueryReturn: { data: ChapterData | undefined; isLoading: boolean; error: Error | null } = { data: undefined, isLoading: true, error: null }) {
    useQueryMock.mockReturnValue(useQueryReturn)

    function TestComponent() {
      hookResult = useReader(bookId, chapterNum)
      return null
    }

    container = document.createElement("div")
    document.body.appendChild(container)
    root = createRoot(container)

    act(() => {
      root?.render(<TestComponent />)
    })
  }

  it("passes the correct cache key to useQuery", () => {
    render("book-1", 3)

    expect(useQueryMock).toHaveBeenCalledTimes(1)
    const options = useQueryMock.mock.calls[0]?.[0]
    expect(options.queryKey).toEqual(["reader", "book-1", "3"])
    expect(options.staleTime).toBe(60_000)
  })

  it("returns loading state when query is loading", () => {
    render("book-1", 1, { data: undefined, isLoading: true, error: null })

    expect(hookResult?.loading).toBe(true)
    expect(hookResult?.data).toBeNull()
    expect(hookResult?.error).toBeNull()
  })

  it("returns chapter data on success", () => {
    const chapter = { chapter_number: 1, chapter_title: "Chapter One", total_chapters: 5, text_url: null, characters: [] }
    render("book-1", 1, { data: chapter, isLoading: false, error: null })

    expect(hookResult?.loading).toBe(false)
    expect(hookResult?.data).toBe(chapter)
    expect(hookResult?.error).toBeNull()
  })

  it("returns error state when query fails", () => {
    render("book-1", 1, { data: undefined, isLoading: false, error: new Error("Network error") })

    expect(hookResult?.loading).toBe(false)
    expect(hookResult?.data).toBeNull()
    expect(hookResult?.error).toBe("Failed to load chapter")
  })

  it("prefetches adjacent chapters when total_chapters is available", () => {
    const chapter = { chapter_number: 3, chapter_title: "Chapter Three", total_chapters: 5, text_url: null, characters: [] }
    render("book-1", 3, { data: chapter, isLoading: false, error: null })

    expect(prefetchQueryMock).toHaveBeenCalledTimes(2)
    expect(prefetchQueryMock).toHaveBeenCalledWith({
      queryKey: ["reader", "book-1", "2"],
      queryFn: expect.any(Function),
      staleTime: 60_000,
    })
    expect(prefetchQueryMock).toHaveBeenCalledWith({
      queryKey: ["reader", "book-1", "4"],
      queryFn: expect.any(Function),
      staleTime: 60_000,
    })
  })

  it("does not prefetch beyond chapter range", () => {
    const chapter = { chapter_number: 1, chapter_title: "Chapter One", total_chapters: 3, text_url: null, characters: [] }
    render("book-1", 1, { data: chapter, isLoading: false, error: null })

    expect(prefetchQueryMock).toHaveBeenCalledTimes(1)
    expect(prefetchQueryMock).toHaveBeenCalledWith({
      queryKey: ["reader", "book-1", "2"],
      queryFn: expect.any(Function),
      staleTime: 60_000,
    })
  })

  it("does not prefetch when total_chapters is not available", () => {
    const chapter = { chapter_number: 1, chapter_title: "Chapter One", total_chapters: null, text_url: null, characters: [] }
    render("book-1", 1, { data: chapter, isLoading: false, error: null })

    expect(prefetchQueryMock).not.toHaveBeenCalled()
  })
})
