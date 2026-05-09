import { beforeEach, describe, expect, it, vi } from "vitest"

import { cachedGet, clearCachedGets, invalidateCachedGets } from "./requestCache"

describe("request cache", () => {
  beforeEach(() => {
    clearCachedGets()
    vi.restoreAllMocks()
  })

  it("returns the fetcher result on first request", async () => {
    const value = await cachedGet("books:list", 1000, async () => ["a"])

    expect(value).toEqual(["a"])
  })

  it("returns the cached value before ttl expiry", async () => {
    const fetcher = vi.fn(async () => ["cached"])

    const first = await cachedGet("books:list", 1000, fetcher)
    const second = await cachedGet("books:list", 1000, fetcher)

    expect(first).toEqual(["cached"])
    expect(second).toEqual(["cached"])
    expect(fetcher).toHaveBeenCalledTimes(1)
  })

  it("re-fetches after ttl expiry", async () => {
    const nowSpy = vi.spyOn(Date, "now")
    nowSpy.mockReturnValueOnce(1000).mockReturnValueOnce(1000).mockReturnValueOnce(2500).mockReturnValueOnce(2500)
    const fetcher = vi.fn(async () => fetcher.mock.calls.length)

    const first = await cachedGet("books:stats", 1000, fetcher)
    const second = await cachedGet("books:stats", 1000, fetcher)

    expect(first).toBe(1)
    expect(second).toBe(2)
  })

  it("deduplicates in-flight requests for the same key", async () => {
    let resolveFetch: ((value: string) => void) | null = null
    const fetcher = vi.fn(
      () =>
        new Promise<string>((resolve) => {
          resolveFetch = resolve
        })
    )

    const first = cachedGet("reader:1:chapter:1", 1000, fetcher)
    const second = cachedGet("reader:1:chapter:1", 1000, fetcher)
    resolveFetch?.("chapter")

    await expect(first).resolves.toBe("chapter")
    await expect(second).resolves.toBe("chapter")
    expect(fetcher).toHaveBeenCalledTimes(1)
  })

  it("invalidates cached keys by string prefix", async () => {
    const alpha = vi.fn(async () => "alpha")
    const beta = vi.fn(async () => "beta")

    await cachedGet("books:list:active", 1000, alpha)
    await cachedGet("reader:1:progress", 1000, beta)
    invalidateCachedGets("books:")
    await cachedGet("books:list:active", 1000, alpha)
    await cachedGet("reader:1:progress", 1000, beta)

    expect(alpha).toHaveBeenCalledTimes(2)
    expect(beta).toHaveBeenCalledTimes(1)
  })

  it("invalidates cached keys by regex matcher", async () => {
    const events = vi.fn(async () => "events")
    const graph = vi.fn(async () => "graph")

    await cachedGet("book:1:events", 1000, events)
    await cachedGet("book:1:graph", 1000, graph)
    invalidateCachedGets(/graph$/)
    await cachedGet("book:1:events", 1000, events)
    await cachedGet("book:1:graph", 1000, graph)

    expect(events).toHaveBeenCalledTimes(1)
    expect(graph).toHaveBeenCalledTimes(2)
  })

  it("clears cached and in-flight entries with clearCachedGets", async () => {
    const fetcher = vi.fn(async () => fetcher.mock.calls.length)

    await cachedGet("reader:1:timeline", 1000, fetcher)
    clearCachedGets()
    await cachedGet("reader:1:timeline", 1000, fetcher)

    expect(fetcher).toHaveBeenCalledTimes(2)
  })
})
