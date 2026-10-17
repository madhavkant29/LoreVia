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
    useQueryMock.mockImplementation((options) => String(options.queryKey[0]).endsWith(":chapters")
      ? { data: { chapters: Array.from({ length: useQueryReturn.data?.total_chapters ?? 0 }, (_, index) => ({ number: index + 1 })) }, error: null }
      : useQueryReturn)

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

    expect(useQueryMock).toHaveBeenCalledTimes(2)
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

  it("ignores context that arrives after closing the panel", async () => {
    render("book-1", 1)
    let resolve: (value: { type: "search"; results: [] }) => void = () => {}
    getContextMock.mockReturnValue(new Promise((done) => { resolve = done }))
    let pending: Promise<void> | undefined
    act(() => { pending = hookResult?.tap("Mara") })
    act(() => { hookResult?.clearContext() })
    await act(async () => { resolve({ type: "search", results: [] }); await pending })
    expect(hookResult?.contextResult).toBeNull()
    expect(hookResult?.contextLoading).toBe(false)
  })

  it("preserves the newest context when requests resolve out of order", async () => {
    render("book-1", 1)
    let resolve: (value: { type: "search"; results: [] }) => void = () => {}
    getContextMock.mockReturnValueOnce(new Promise((done) => { resolve = done }))
    getContextMock.mockResolvedValueOnce({ type: "character", character: { name: "Theo" } })
    let first: Promise<void> | undefined
    act(() => { first = hookResult?.tap("Mara") })
    await act(async () => { await hookResult?.tap("Theo") })
    await act(async () => { resolve({ type: "search", results: [] }); await first })
    expect(hookResult?.contextResult?.character?.name).toBe("Theo")
  })

  it("shows context and progress failures and retries the submitted values", async () => {
    render("book-1", 2)
    getContextMock.mockRejectedValueOnce(new Error("Offline")).mockResolvedValueOnce({ type: "search", results: [] })
    updateProgressMock.mockRejectedValueOnce(new Error("Offline")).mockResolvedValueOnce({})
    await act(async () => { await hookResult?.tap("Mara"); await hookResult?.saveProgress(0.75) })
    expect(hookResult?.contextError).toContain("Could not load")
    expect(hookResult?.progressError).toBe(true)
    await act(async () => { await hookResult?.retryContext(); await hookResult?.retryProgress() })
    expect(getContextMock).toHaveBeenLastCalledWith("book-1", "Mara", 2)
    expect(updateProgressMock).toHaveBeenLastCalledWith("book-1", 2, 0.75)
    expect(hookResult?.contextError).toBeNull()
    expect(hookResult?.progressError).toBe(false)
  })
})
