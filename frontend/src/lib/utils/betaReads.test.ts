import { describe, expect, it } from "vitest"

import { betaReadDeadlineDetail, betaReadDeadlineLabel, betaReadIsUrgent, betaReadRequirementLines } from "./betaReads"

describe("beta read helpers", () => {
  it("formats same-day deadlines as due today", () => {
    const label = betaReadDeadlineLabel("2026-05-14T18:00:00Z", new Date("2026-05-14T09:00:00Z"))

    expect(label).toBe("Due today")
  })

  it("formats near-term deadlines as days left", () => {
    const label = betaReadDeadlineLabel("2026-05-16T18:00:00Z", new Date("2026-05-14T09:00:00Z"))

    expect(label).toBe("2 days left")
  })

  it("flags urgent deadlines inside 24 hours", () => {
    expect(betaReadIsUrgent("2026-05-14T20:00:00Z", new Date("2026-05-14T09:00:00Z"))).toBe(true)
    expect(betaReadIsUrgent("2026-05-16T20:00:00Z", new Date("2026-05-14T09:00:00Z"))).toBe(false)
  })

  it("includes time details for same-day due dates", () => {
    const sameDayNow = new Date(2026, 4, 14, 9, 0, 0)
    const sameDayDeadline = new Date(2026, 4, 14, 23, 59, 0).toISOString()
    const detail = betaReadDeadlineDetail(sameDayDeadline, sameDayNow)

    expect(detail).toContain("Today")
  })

  it("builds requirement lines from assignment rules", () => {
    const lines = betaReadRequirementLines({
      required_progress_pct: 100,
      required_comment_count: 3,
      required_feedback_item_count: 2,
      require_final_feedback: true,
    } as never)

    expect(lines).toEqual([
      "Finish 100% of the assigned reading",
      "Leave at least 3 comments",
      "Add at least 2 feedback items",
      "Submit final feedback",
    ])
  })
})
