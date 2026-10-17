import { describe, expect, it } from "vitest"

import { getTrialCountdown } from "./trialCountdown"

describe("trial countdown", () => {
  const now = Date.parse("2026-08-30T10:00:00Z")

  it("formats active trials with days and hours", () => {
    expect(getTrialCountdown("2026-09-02T14:30:00Z", now)).toEqual({
      expired: false,
      label: "3 days, 4 hours remaining",
    })
  })

  it("shows minute precision near the end of a trial", () => {
    expect(getTrialCountdown("2026-08-30T10:42:00Z", now)?.label).toBe("42 minutes remaining")
  })

  it("handles expired, missing, and malformed trial dates", () => {
    expect(getTrialCountdown("2026-08-30T09:59:00Z", now)).toEqual({
      expired: true,
      label: "Trial ended",
    })
    expect(getTrialCountdown(null, now)).toBeNull()
    expect(getTrialCountdown("not-a-date", now)).toBeNull()
  })
})
