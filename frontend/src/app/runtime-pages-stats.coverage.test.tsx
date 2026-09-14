// @vitest-environment jsdom

import { describe, expect, it } from "vitest"

import {
  queryRefetchMock,
  renderPage,
  resetRenderedPage,
  text,
  useQueryMock,
} from "./runtime-pages-expanded.test-utils"

import StatsPage from "@/app/(dashboard)/stats/page"

describe("stats runtime page coverage", () => {
  it("renders populated, loading, unavailable, and gated states", async () => {
    await renderPage(<StatsPage />)

    expect(text()).toContain("Writing momentum overview")
    expect(text()).toContain("No entries saved today")
    expect(text()).toContain("Books finished")
    expect(text()).toContain("AI capacity")

    resetRenderedPage()
    useQueryMock.mockReturnValueOnce({
      data: null,
      isLoading: true,
      isError: false,
      refetch: queryRefetchMock,
    })
    await renderPage(<StatsPage />)
    expect(text()).toContain("Loading dashboard")

    resetRenderedPage()
    useQueryMock.mockReturnValueOnce({
      data: null,
      isLoading: false,
      isError: false,
      refetch: queryRefetchMock,
    })
    await renderPage(<StatsPage />)
    expect(text()).toContain("Stats unavailable")
  })
})
