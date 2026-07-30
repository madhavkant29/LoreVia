import { beforeEach, describe, expect, it, vi } from "vitest"

import { completeEditedFindingDecision } from "./manuscriptPage.intelligenceActions"

const decideContinuityFindingMock = vi.fn()
const decideRevisionFindingMock = vi.fn()

vi.mock("@/lib/api/books", () => ({
  booksApi: {
    decideContinuityFinding: (...args: unknown[]) => decideContinuityFindingMock(...args),
    decideRevisionFinding: (...args: unknown[]) => decideRevisionFindingMock(...args),
  },
}))

describe("completeEditedFindingDecision", () => {
  beforeEach(() => {
    decideContinuityFindingMock.mockReset()
    decideRevisionFindingMock.mockReset()
  })

  it("resolves continuity findings through the continuity workflow", async () => {
    const result = await completeEditedFindingDecision("book-1", {
      get: (name) => (name === "continuity_finding" ? "continuity-1" : null),
    })

    expect(decideContinuityFindingMock).toHaveBeenCalledWith("book-1", "continuity-1", {
      decision: "resolved",
      action: "manuscript_edit",
      reason: "fixed",
    })
    expect(decideRevisionFindingMock).not.toHaveBeenCalled()
    expect(result).toEqual({ findingId: "continuity-1", source: "continuity" })
  })

  it("preserves the legacy revision-finding workflow", async () => {
    const result = await completeEditedFindingDecision("book-1", {
      get: (name) => (name === "finding" ? "revision-1" : null),
    })

    expect(decideRevisionFindingMock).toHaveBeenCalledWith("book-1", "revision-1", {
      decision: "accepted",
      action: "manuscript_edit",
    })
    expect(decideContinuityFindingMock).not.toHaveBeenCalled()
    expect(result).toEqual({ findingId: "revision-1", source: "revision" })
  })
})
