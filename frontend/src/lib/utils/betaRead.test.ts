import { describe, expect, it } from "vitest"

import { formatFeedbackKindLabel, parseQuestionLines, selectPrimaryAssignment } from "./betaRead"

describe("betaRead utils", () => {
  it("parses question lines and removes blanks", () => {
    expect(parseQuestionLines("Did it hook?\n\nWhere were you confused?  ")).toEqual([
      "Did it hook?",
      "Where were you confused?",
    ])
  })

  it("formats feedback kind labels", () => {
    expect(formatFeedbackKindLabel("scene_reaction")).toBe("Scene Reaction")
  })

  it("picks the active assignment for a book first", () => {
    const assignment = selectPrimaryAssignment(
      [
        { id: "1", book_id: "book-a", view_bucket: "completed" },
        { id: "2", book_id: "book-a", view_bucket: "active" },
        { id: "3", book_id: "book-b", view_bucket: "active" },
      ] as never[],
      "book-a"
    )
    expect(assignment?.id).toBe("2")
  })
})
