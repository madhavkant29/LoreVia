import { describe, expect, it } from "vitest"

import {
  DAILY_LIMIT_MESSAGE,
  buildDailyCapEventDetail,
  inferDailyCapActionFromRequestPath,
  isDailyLimitDetail,
} from "./dailyCap"

function axiosError(url: string, status: number, detail: string) {
  return {
    isAxiosError: true,
    response: { status, data: { detail } },
    config: { url },
  } as unknown as Error
}

describe("dailyCap", () => {
  it("recognizes the generic and limit-specific daily cap messages", () => {
    expect(isDailyLimitDetail(DAILY_LIMIT_MESSAGE)).toBe(true)
    expect(
      isDailyLimitDetail(
        "You've reached your daily limit of 60 Story Advisor turns. It refreshes tomorrow.",
      ),
    ).toBe(true)
    expect(
      isDailyLimitDetail(
        "You've reached your daily limit of 30 continuity and editorial scans. It refreshes tomorrow.",
      ),
    ).toBe(true)
    expect(isDailyLimitDetail("Some other validation error")).toBe(false)
  })

  it("builds a daily cap event for an architect advisor limit response", () => {
    const detail = buildDailyCapEventDetail(
      axiosError(
        "/api/v1/books/book-1/advisor/message",
        429,
        "You've reached your daily limit of 60 Story Advisor turns. It refreshes tomorrow.",
      ),
    )

    expect(detail?.action).toBe("high_cost_authoring")
    expect(detail?.detail).toContain("60 Story Advisor turns")
  })

  it("builds a daily cap event for an architect continuity scan limit response", () => {
    const detail = buildDailyCapEventDetail(
      axiosError(
        "/api/v1/books/book-1/continuity-check",
        429,
        "You've reached your daily limit of 60 continuity and editorial scans. It refreshes tomorrow.",
      ),
    )

    expect(detail?.detail).toContain("60 continuity and editorial scans")
  })

  it("ignores unrelated errors", () => {
    expect(buildDailyCapEventDetail(axiosError("/api/v1/auth/me", 500, "Server error"))).toBeNull()
  })

  it("infers the daily cap action from the request path", () => {
    expect(inferDailyCapActionFromRequestPath("/api/v1/books/book-1/advisor/message")).toBe(
      "high_cost_authoring",
    )
    expect(inferDailyCapActionFromRequestPath("/api/v1/reader/book-1/search")).toBe("search")
    expect(inferDailyCapActionFromRequestPath("/api/v1/auth/me")).toBeNull()
  })
})
