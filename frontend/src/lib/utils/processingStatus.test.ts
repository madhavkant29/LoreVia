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

  it("treats a cancelled rebuild as an interrupted retryable state", () => {
    const status = normalizeProcessingStatus({
      status: "cancelled",
      stage: "cancelled",
      chapters_completed: 0,
      chapters_total: 2,
      progress_pct: 0,
      last_error: "The manuscript changed during reprocessing.",
    })

    expect(status?.stage).toBe("failed")
    expect(status?.ready).toBe(false)
    expect(status?.failed).toBe(true)
    expect(status?.retryAvailable).toBe(true)
    expect(status?.detail).toBe("Retry is available")
  })

  it("exposes allowance-paused processing as resumable", () => {
    const status = normalizeProcessingStatus({
      status: "processing",
      stage: "allowance_paused",
      resume_available: true,
      retry_actions: ["continue_processing"],
      resume_blockers: [{ kind: "monthly_processed_words", detail: "Wait for reset" }],
    })

    expect(status?.paused).toBe(true)
    expect(status?.resumeAvailable).toBe(true)
    expect(status?.label).toBe("Processing paused")
    expect(status?.detail).toBe("Wait for reset")
  })
})
