import React, { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const useQueryClientMock = vi.hoisted(() => vi.fn())
const prefetchQueryMock = vi.hoisted(() => vi.fn())
const getReaderBootstrapMock = vi.hoisted(() => vi.fn())
const getManuscriptBootstrapMock = vi.hoisted(() => vi.fn())
const advisorGreetingMock = vi.hoisted(() => vi.fn())
const getCharactersMock = vi.hoisted(() => vi.fn())
const getWorldBootstrapMock = vi.hoisted(() => vi.fn())

vi.mock("@tanstack/react-query", () => ({
  useQueryClient: useQueryClientMock,
}))

import * as useNavigationPrefetchModule from "./useNavigationPrefetch"

const { useNavigationPrefetch } = useNavigationPrefetchModule

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
    getReaderBootstrapMock.mockReset()
    getManuscriptBootstrapMock.mockReset()
    advisorGreetingMock.mockReset()
    getCharactersMock.mockReset()
    getWorldBootstrapMock.mockReset()

    hookResult = null
    useQueryClientMock.mockReturnValue({
      prefetchQuery: prefetchQueryMock,
    })
    vi.spyOn(useNavigationPrefetchModule.prefetchLoaders, "loadBooksApi").mockResolvedValue({
      getReaderBootstrap: getReaderBootstrapMock,
      getManuscriptBootstrap: getManuscriptBootstrapMock,
      getCharacters: getCharactersMock,
    } as unknown as Awaited<ReturnType<typeof useNavigationPrefetchModule.prefetchLoaders.loadBooksApi>>)
    vi.spyOn(useNavigationPrefetchModule.prefetchLoaders, "loadIntelligenceApi").mockResolvedValue({
      advisorGreeting: advisorGreetingMock,
    } as unknown as Awaited<ReturnType<typeof useNavigationPrefetchModule.prefetchLoaders.loadIntelligenceApi>>)
    vi.spyOn(useNavigationPrefetchModule.prefetchLoaders, "loadWorldBuildingApi").mockResolvedValue({
      getBootstrap: getWorldBootstrapMock,
    } as unknown as Awaited<ReturnType<typeof useNavigationPrefetchModule.prefetchLoaders.loadWorldBuildingApi>>)
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
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
      queryKey: ["book:book-1:reader-bootstrap"],
      queryFn: expect.any(Function),
      staleTime: 20_000,
    })
  })

  it("prefetches manuscript bootstrap when manuscript navId is triggered", () => {
    render("book-1")

    act(() => {
      hookResult?.prefetchByNavId("manuscript")
    })
    advanceTimers()

    expect(prefetchQueryMock).toHaveBeenCalledTimes(1)
    expect(prefetchQueryMock).toHaveBeenCalledWith({
      queryKey: ["book:book-1:manuscript-bootstrap"],
      queryFn: expect.any(Function),
      staleTime: 30_000,
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

  it("prefetches world-gap bootstrap", () => {
    render("book-1")

    act(() => {
      hookResult?.prefetchByNavId("world-gap")
    })
    advanceTimers()

    expect(prefetchQueryMock).toHaveBeenCalledTimes(1)
    expect(prefetchQueryMock).toHaveBeenCalledWith({
      queryKey: ["worldbuilding:book-1:bootstrap:gap"],
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

  it("invokes the correct API functions", async () => {
    getReaderBootstrapMock.mockResolvedValue({})
    getManuscriptBootstrapMock.mockResolvedValue({})
    advisorGreetingMock.mockResolvedValue({})
    getCharactersMock.mockResolvedValue([])
    getWorldBootstrapMock.mockResolvedValue({})

    render("book-1")

    act(() => {
      hookResult?.prefetchByNavId("overview")
      hookResult?.prefetchByNavId("manuscript")
      hookResult?.prefetchByNavId("advisor")
      hookResult?.prefetchByNavId("characters")
      hookResult?.prefetchByNavId("world-gap")
    })
    advanceTimers()

    const calls = prefetchQueryMock.mock.calls as Array<[{ queryFn: () => Promise<unknown> }]>
    await Promise.all(calls.map((call) => call[0].queryFn()))

    expect(getReaderBootstrapMock).toHaveBeenCalledWith("book-1", { profile: "critical" })
    expect(getManuscriptBootstrapMock).toHaveBeenCalledWith("book-1", { profile: "critical" })
    expect(advisorGreetingMock).toHaveBeenCalledWith("book-1")
    expect(getCharactersMock).toHaveBeenCalledWith("book-1")
    expect(getWorldBootstrapMock).toHaveBeenCalledWith("book-1", { focus: "gap" })
  })
})
