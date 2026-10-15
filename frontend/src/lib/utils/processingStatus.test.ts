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

  it("renders administratively frozen imports as interrupted without retry", () => {
    const status = normalizeProcessingStatus({
      status: "failed",
      stage: "frozen",
      frozen: true,
      freeze_message:
        "Import interrupted - please upload again. Your project and files have been preserved.",
      retry_actions: [],
      last_error: "ignored",
    })

    expect(status?.stage).toBe("frozen")
    expect(status?.frozen).toBe(true)
    expect(status?.label).toBe("Import interrupted")
    expect(status?.retryAvailable).toBe(false)
    expect(status?.failureKind).toBeNull()
    expect(status?.stateVariant).toBe("frozen")
    expect(status?.detail).toContain("upload again")
    expect(status?.lastError).toBeNull()
  })

  it("falls back to a clear frozen message and never offers retry", () => {
    const status = normalizeProcessingStatus({ status: "failed", frozen: true } as never)

    expect(status?.frozen).toBe(true)
    expect(status?.label).toBe("Import interrupted")
    expect(status?.retryAvailable).toBe(false)
    expect(status?.detail).toContain("upload again")
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

  it("exposes token pauses as automatic and hides manual retry", () => {
    const status = normalizeProcessingStatus({
      status: "paused",
      stage: "usage_limited",
      chapters_completed: 2,
      chapters_total: 4,
      pause_reason: "llm_token_limit",
      auto_resume: true,
      resume_available: false,
      retry_available: true,
      next_resume_at: "2026-08-30T12:00:00Z",
      resume_blockers: [{
        kind: "llm_tokens",
        detail: "Token limit exceeded",
        auto_resume: true,
        next_resume_at: "2026-08-30T12:00:00Z",
      }],
    })

    expect(status?.paused).toBe(true)
    expect(status?.autoResume).toBe(true)
    expect(status?.resumeAvailable).toBe(false)
    expect(status?.retryAvailable).toBe(false)
    expect(status?.detail).toContain("resume automatically around")
    expect(status?.detail).toContain("2/4 chapters complete")
  })

  it("describes budget pauses as monthly AI capacity instead of token limits", () => {
    const status = normalizeProcessingStatus({
      status: "paused",
      stage: "budget_limited",
      chapters_completed: 8,
      chapters_total: 10,
      pause_reason: "llm_budget",
      auto_resume: true,
      resume_available: false,
      retry_available: true,
      next_resume_at: "2026-09-01T00:00:00Z",
      resume_blockers: [{
        kind: "llm_budget",
        detail: "Monthly AI capacity has been reached.",
        auto_resume: true,
        next_resume_at: "2026-09-01T00:00:00Z",
      }],
    })

    expect(status?.paused).toBe(true)
    expect(status?.autoResume).toBe(true)
    expect(status?.retryAvailable).toBe(false)
    expect(status?.detail).toContain("Monthly AI capacity reached")
    expect(status?.detail).not.toContain("Token limit reached")
  })

  it("distinguishes support-required failures from retryable failures", () => {
    const status = normalizeProcessingStatus({
      status: "failed",
      stage: "failed",
      retry_available: false,
    })

    expect(status?.retryAvailable).toBe(false)
    expect(status?.failureKind).toBe("support_required")
    expect(status?.stateVariant).toBe("support_required")
  })
})
