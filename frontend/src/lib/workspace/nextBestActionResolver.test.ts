import { describe, expect, it } from "vitest"

import {
  recommendationIsSuppressed,
  resolveNextBestActions,
  type NextBestActionCandidate,
} from "./nextBestActionResolver"

const failed: NextBestActionCandidate = {
  id: "failed",
  label: "Fix processing",
  priority: "failed_processing",
  fingerprint: "failed:v1",
}

const drafting: NextBestActionCandidate = {
  id: "drafting",
  label: "Continue draft",
  priority: "active_drafting",
  fingerprint: "draft:v1",
}

describe("next best action resolver", () => {
  it("prioritizes failed processing over active drafting", () => {
    expect(resolveNextBestActions([drafting, failed]).map((action) => action.id)).toEqual([
      "failed",
      "drafting",
    ])
  })

  it("suppresses matching snoozes until they expire", () => {
    const now = new Date("2026-08-05T12:00:00Z")
    const stored = {
      failed: {
        fingerprint: "failed:v1",
        snoozed_until: "2026-08-06T12:00:00Z",
      },
    }

    expect(recommendationIsSuppressed(failed, stored, now)).toBe(true)
    expect(resolveNextBestActions([failed, drafting], stored, now).map((action) => action.id)).toEqual([
      "drafting",
    ])
  })

  it("resurfaces a recommendation when its state fingerprint changes", () => {
    const changed = { ...failed, fingerprint: "failed:v2" }
    const stored = {
      failed: {
        fingerprint: "failed:v1",
        dismissed_at: "2026-08-05T10:00:00Z",
      },
    }

    expect(recommendationIsSuppressed(changed, stored)).toBe(false)
  })
})
