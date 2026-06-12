import { describe, expect, it } from "vitest"

import {
  graphLabelKey,
  graphStorageKey,
  nodeInitial,
  relationshipFacetLabel,
  relationshipFacetSummary,
  relationshipLabel,
  sentimentLabel,
  zoomPercentLabel,
} from "./relationshipGraphDisplay"

describe("relationshipGraphDisplay", () => {
  it("builds stable local-storage keys", () => {
    expect(graphStorageKey("book-7", 3)).toBe("lorevia:graph-layout:book-7:3")
    expect(graphLabelKey("book-7")).toBe("lorevia:graph-labels:book-7")
  })

  it("humanizes relationship labels", () => {
    expect(relationshipLabel("found_family")).toBe("found family")
    expect(relationshipLabel(null)).toBe("connection")
  })

  it("formats complex relationship facets", () => {
    expect(relationshipFacetLabel("friend_toxic")).toBe("friend (toxic)")
    expect(relationshipFacetLabel("pawn_tool")).toBe("pawn (tool)")
    expect(relationshipFacetLabel("one_sided_friend")).toBe("one-sided friend")
    expect(relationshipFacetLabel("mother_in_law")).toBe("mother-in-law")
    expect(relationshipFacetSummary(["half_sister", "spouse", "forbidden_romance"], "family")).toBe("half-sister, spouse, forbidden romance")
    expect(relationshipFacetSummary([], "family")).toBe("family")
  })

  it("maps edge sentiment bands to readable copy", () => {
    expect(sentimentLabel(0.6)).toBe("Strongly positive")
    expect(sentimentLabel(0.2)).toBe("Positive")
    expect(sentimentLabel(-0.2)).toBe("Tense")
    expect(sentimentLabel(-0.7)).toBe("Strongly tense")
    expect(sentimentLabel(0.01)).toBe("Mixed or neutral")
    expect(sentimentLabel("0.5")).toBeNull()
  })

  it("formats zoom and initials for the inspector chrome", () => {
    expect(zoomPercentLabel(1.234)).toBe("123%")
    expect(nodeInitial("Gregor")).toBe("G")
    expect(nodeInitial("  ")).toBe("?")
  })
})
