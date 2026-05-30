import React, { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const useQueryClientMock = vi.hoisted(() => vi.fn())
const prefetchQueryMock = vi.hoisted(() => vi.fn())
const getOverviewMock = vi.hoisted(() => vi.fn())
const advisorGreetingMock = vi.hoisted(() => vi.fn())
const getCharactersMock = vi.hoisted(() => vi.fn())
const listDocumentsMock = vi.hoisted(() => vi.fn())
const listElementsMock = vi.hoisted(() => vi.fn())

vi.mock("@tanstack/react-query", () => ({
  useQueryClient: useQueryClientMock,
}))

vi.mock("@/lib/api/books", () => ({
  booksApi: {
    getOverview: getOverviewMock,
    getCharacters: getCharactersMock,
  },
}))

vi.mock("@/lib/api/intelligence", () => ({
  intelligenceApi: {
    advisorGreeting: advisorGreetingMock,
  },
}))

vi.mock("@/lib/api/worldBuilding", () => ({
  worldBuildingApi: {
    listDocuments: listDocumentsMock,
    listElements: listElementsMock,
  },
}))

import { useNavigationPrefetch } from "./useNavigationPrefetch"

describe("useNavigationPrefetch", () => {
  let container: HTMLDivElement | null = null
  let root: Root | null = null
  let hookResult: ReturnType<typeof useNavigationPrefetch> | null = null

  beforeEach(() => {
    ;(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
  })

  beforeEach(() => {
    vi.useFakeTimers()
    useQueryClientMock.mockReset()
    prefetchQueryMock.mockReset()
    getOverviewMock.mockReset()
    advisorGreetingMock.mockReset()
    getCharactersMock.mockReset()
    listDocumentsMock.mockReset()
    listElementsMock.mockReset()

    hookResult = null
    useQueryClientMock.mockReturnValue({
      prefetchQuery: prefetchQueryMock,
    })
  })

  afterEach(() => {
    vi.useRealTimers()
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

  function render(bookId: string) {
    function TestComponent() {
      hookResult = useNavigationPrefetch(bookId)
      return null
    }

    container = document.createElement("div")
    document.body.appendChild(container)
    root = createRoot(container)

    act(() => {
      root?.render(<TestComponent />)
    })
  }

  function advanceTimers() {
    act(() => {
      vi.advanceTimersByTime(150)
    })
  }

  it("prefetches overview data when overview navId is triggered", () => {
    render("book-1")

    act(() => {
      hookResult?.prefetchByNavId("overview")
    })
    advanceTimers()

    expect(prefetchQueryMock).toHaveBeenCalledTimes(1)
    expect(prefetchQueryMock).toHaveBeenCalledWith({
      queryKey: ["book:book-1:overview"],
      queryFn: expect.any(Function),
      staleTime: 20_000,
    })
  })

  it("prefetches advisor greeting when advisor navId is triggered", () => {
    render("book-1")

    act(() => {
      hookResult?.prefetchByNavId("advisor")
    })
    advanceTimers()

    expect(prefetchQueryMock).toHaveBeenCalledTimes(1)
    expect(prefetchQueryMock).toHaveBeenCalledWith({
      queryKey: ["advisor:book-1:greeting"],
      queryFn: expect.any(Function),
      staleTime: 30_000,
    })
  })

  it("prefetches characters when characters navId is triggered", () => {
    render("book-1")

    act(() => {
      hookResult?.prefetchByNavId("characters")
    })
    advanceTimers()

    expect(prefetchQueryMock).toHaveBeenCalledTimes(1)
    expect(prefetchQueryMock).toHaveBeenCalledWith({
      queryKey: ["book:book-1:characters"],
      queryFn: expect.any(Function),
      staleTime: 30_000,
    })
  })

  it("prefetches world-gap documents and elements", () => {
    render("book-1")

    act(() => {
      hookResult?.prefetchByNavId("world-gap")
    })
    advanceTimers()

    expect(prefetchQueryMock).toHaveBeenCalledTimes(2)
    expect(prefetchQueryMock).toHaveBeenCalledWith({
      queryKey: ["worldbuilding:book-1:documents"],
      queryFn: expect.any(Function),
      staleTime: 30_000,
    })
    expect(prefetchQueryMock).toHaveBeenCalledWith({
      queryKey: ["worldbuilding:book-1:elements"],
      queryFn: expect.any(Function),
      staleTime: 30_000,
    })
  })

  it("deduplicates prefetch calls for the same navId", () => {
    render("book-1")

    act(() => {
      hookResult?.prefetchByNavId("overview")
    })
    advanceTimers()
    expect(prefetchQueryMock).toHaveBeenCalledTimes(1)

    act(() => {
      hookResult?.prefetchByNavId("overview")
    })
    advanceTimers()
    expect(prefetchQueryMock).toHaveBeenCalledTimes(1)
  })

  it("allows prefetching different navIds", () => {
    render("book-1")

    act(() => {
      hookResult?.prefetchByNavId("overview")
    })
    advanceTimers()

    act(() => {
      hookResult?.prefetchByNavId("advisor")
    })
    advanceTimers()

    expect(prefetchQueryMock).toHaveBeenCalledTimes(2)
  })

  it("debounces prefetch calls within the debounce window", () => {
    render("book-1")

    act(() => {
      hookResult?.prefetchByNavId("overview")
    })

    act(() => {
      vi.advanceTimersByTime(50)
    })

    // second call within debounce window resets timer
    act(() => {
      hookResult?.prefetchByNavId("overview")
    })

    act(() => {
      vi.advanceTimersByTime(50)
    })

    expect(prefetchQueryMock).not.toHaveBeenCalled()

    // advance past the full debounce window
    act(() => {
      vi.advanceTimersByTime(100)
    })

    expect(prefetchQueryMock).toHaveBeenCalledTimes(1)
  })

  it("does not prefetch when bookId is empty", () => {
    render("")

    act(() => {
      hookResult?.prefetchByNavId("overview")
    })
    advanceTimers()

    expect(prefetchQueryMock).not.toHaveBeenCalled()
  })

  it("does not error on unknown navId", () => {
    render("book-1")

    expect(() => {
      act(() => {
        hookResult?.prefetchByNavId("unknown-page")
      })
      advanceTimers()
    }).not.toThrow()

    expect(prefetchQueryMock).not.toHaveBeenCalled()
  })

  it("invokes the correct API functions", () => {
    getOverviewMock.mockResolvedValue({})
    advisorGreetingMock.mockResolvedValue({})
    getCharactersMock.mockResolvedValue([])
    listDocumentsMock.mockResolvedValue([])
    listElementsMock.mockResolvedValue([])

    render("book-1")

    act(() => {
      hookResult?.prefetchByNavId("overview")
      hookResult?.prefetchByNavId("advisor")
      hookResult?.prefetchByNavId("characters")
      hookResult?.prefetchByNavId("world-gap")
    })
    advanceTimers()

    const calls = prefetchQueryMock.mock.calls as Array<[{ queryFn: () => Promise<unknown> }]>
    for (const call of calls) {
      void call[0].queryFn()
    }

    expect(getOverviewMock).toHaveBeenCalledWith("book-1")
    expect(advisorGreetingMock).toHaveBeenCalledWith("book-1")
    expect(getCharactersMock).toHaveBeenCalledWith("book-1")
    expect(listDocumentsMock).toHaveBeenCalledWith("book-1")
    expect(listElementsMock).toHaveBeenCalledWith("book-1")
  })
})
