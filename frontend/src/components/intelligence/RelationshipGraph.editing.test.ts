import { describe, expect, it } from "vitest"
import { relationshipDraft, relationshipDraftError } from "./RelationshipGraph.editing"

describe("relationship correction validation", () => {
  it("preserves optional values and labels when preparing a draft", () => {
    expect(relationshipDraft(null)).toEqual({ relType: "", description: "", sentiment: "0", fromChapter: "", toChapter: "", sharedLabels: [], sourceToTargetLabels: [], targetToSourceLabels: [] })
    expect(relationshipDraft({ id: "r", source: "a", target: "b", type: "friend", description: null, sentiment: -0.5, from_chapter: 2, to_chapter: 8, label: "", shared_labels: ["friend"] })).toMatchObject({ sentiment: "-0.5", fromChapter: "2", toChapter: "8", sharedLabels: ["friend"] })
  })
  it("accepts blank optional fields and valid boundaries", () => {
    expect(relationshipDraftError({ ...relationshipDraft(null), relType: "friend", sentiment: "", fromChapter: "", toChapter: "" })).toBeNull()
    expect(relationshipDraftError({ ...relationshipDraft(null), relType: "friend", sentiment: "-1", fromChapter: "1", toChapter: "1" })).toBeNull()
  })
  it.each([{ relType: "" }, { sentiment: "2" }, { sentiment: "NaN" }, { sentiment: "Infinity" }, { fromChapter: "0" }, { fromChapter: "1.5" }, { toChapter: "bad" }, { fromChapter: "3", toChapter: "2" }])("rejects malformed corrections %j", (change) => {
    expect(relationshipDraftError({ ...relationshipDraft(null), relType: "friend", ...change })).toBeTruthy()
  })
})
