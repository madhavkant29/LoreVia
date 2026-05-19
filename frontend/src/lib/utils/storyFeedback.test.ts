import { describe, expect, it } from "vitest"

import { buildIssueDisplay } from "./storyFeedback"

describe("buildIssueDisplay", () => {
  it("preserves real issue counts when issues exist", () => {
    expect(buildIssueDisplay(3)).toEqual({
      displayCount: 3,
      label: "3 issues detected",
    })
  })

  it("queues review targets instead of showing zero issues", () => {
    expect(buildIssueDisplay(0)).toEqual({
      displayCount: 2,
      label: "2 review targets queued",
    })
  })

  it("pluralizes singular issue counts correctly", () => {
    expect(buildIssueDisplay(1)).toEqual({
      displayCount: 1,
      label: "1 issue detected",
    })
  })
})
