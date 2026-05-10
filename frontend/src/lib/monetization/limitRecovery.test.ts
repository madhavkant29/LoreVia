import { describe, expect, it, vi } from "vitest"

import {
  DAILY_LIMIT_MESSAGE,
  buildDailyCapEventDetail,
  inferPointActionFromRequestPath,
} from "./limitRecovery"

vi.mock("axios", () => ({
  default: {
    isAxiosError: (value: unknown) => Boolean((value as { isAxiosError?: boolean })?.isAxiosError),
  },
}))

describe("limit recovery", () => {
  it("maps reader search requests to search overflow", () => {
    expect(inferPointActionFromRequestPath("/reader/book-1/search")).toBe("search")
    expect(inferPointActionFromRequestPath("/reader/book-1/thematic-search")).toBe("search")
  })

  it("maps grounded qa requests to prediction overflow", () => {
    expect(inferPointActionFromRequestPath("/intelligence/book-1/qa")).toBe("prediction")
  })

  it("maps advisor requests to high-cost overflow", () => {
    expect(inferPointActionFromRequestPath("/intelligence/book-1/advisor/message")).toBe("high_cost_authoring")
  })

  it("builds a daily cap event from matching axios errors", () => {
    const detail = buildDailyCapEventDetail({
      isAxiosError: true,
      config: { url: "/intelligence/book-1/qa" },
      response: {
        status: 429,
        data: { detail: DAILY_LIMIT_MESSAGE },
      },
    })

    expect(detail).toEqual({
      action: "prediction",
      status: 429,
      requestPath: "/intelligence/book-1/qa",
      detail: DAILY_LIMIT_MESSAGE,
    })
  })

  it("ignores non-daily-cap failures", () => {
    const detail = buildDailyCapEventDetail({
      isAxiosError: true,
      config: { url: "/intelligence/book-1/qa" },
      response: {
        status: 429,
        data: { detail: "Rate limit exceeded" },
      },
    })

    expect(detail).toBeNull()
  })
})
