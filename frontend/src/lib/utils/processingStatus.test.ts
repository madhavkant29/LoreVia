import { describe, expect, it } from "vitest"

import { normalizeProcessingStatus } from "./processingStatus"

describe("normalizeProcessingStatus", () => {
  it("maps backend processing stages to user-facing state", () => {
    const status = normalizeProcessingStatus({
      status: "processing",
      stage: "analysis",
      progress_pct: 42,
      chapters_completed: 3,
      chapters_total: 7,
    })

    expect(status?.stage).toBe("analyzing")
    expect(status?.label).toBe("Running story analysis")
    expect(status?.detail).toContain("First chapters ready")
    expect(status?.partialReady).toBe(true)
  })

  it("marks failed or retryable states as retry available", () => {
    expect(normalizeProcessingStatus({ status: "failed", stage: "failed" })?.retryAvailable).toBe(true)
    expect(normalizeProcessingStatus({ status: "processing", stage: "analysis", retry_actions: ["wait_for_analysis"] })?.retryAvailable).toBe(false)
    expect(normalizeProcessingStatus({ status: "processing", stage: "analysis", retry_actions: ["retry_analysis"] })?.retryAvailable).toBe(true)
  })
})
