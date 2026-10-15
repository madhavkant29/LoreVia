import { describe, expect, it } from "vitest"
import { canEditFeedback, reviewRequirements, validateFeedback, validateInvitation, validateQuestions } from "./betaFeedbackPage.helpers"
import type { BetaReadAssignmentDetail } from "@/types/betaRead"

const invitation = { readerEmail: "reader@example.com", taskLabel: "First pass", scopeKind: "full_book", sectionLabel: "", chapterStart: "1", chapterEnd: "3", windowDays: "7", requiredProgressPct: "100", requiredCommentCount: "0", requiredFeedbackItemCount: "1", authorQuestionsText: "What was clear?" }
const detail = { assignment: { state: "active", view_bucket: "active", chapter_start: 2, chapter_end: 4, starts_at: "2020-01-01", expires_at: "2099-01-01", comment_count: 2, required_comment_count: 1, feedback_item_count: 2, required_feedback_item_count: 2, progress_pct: 100, required_progress_pct: 100 }, author_questions: [{ id: "q1", answer_count: 2 }, { id: "q2", answer_count: 0 }], feedback_summary: { answer_count: 2 } } as BetaReadAssignmentDetail
const feedback = { feedbackKind: "chapter_comment", feedbackChapter: "2", feedbackReaction: "", feedbackAnchor: "", feedbackBody: "Clear opening.", selectedQuestionId: "" }

describe("beta feedback validation", () => {
  it("accepts exact invitation boundaries and rejects missing, fractional, excessive, or reversed values", () => {
    expect(validateInvitation(invitation, 5)).toBeNull()
    for (const patch of [{ readerEmail: "invalid" }, { taskLabel: "ab" }, { windowDays: "" }, { windowDays: "7.5" }, { windowDays: "8" }, { requiredProgressPct: "0" }, { requiredCommentCount: "-1" }, { requiredFeedbackItemCount: "1001" }, { scopeKind: "chapter_range", chapterStart: "3", chapterEnd: "2" }, { scopeKind: "chapter_range", chapterEnd: "6" }]) expect(validateInvitation({ ...invitation, ...patch }, 5)).not.toBeNull()
    expect(validateInvitation({ ...invitation, windowDays: "3", requiredProgressPct: "1", requiredCommentCount: "1000", requiredFeedbackItemCount: "1000" }, 5)).toBeNull()
  })
  it("requires a section label and bounds question count and length without truncation", () => {
    expect(validateInvitation({ ...invitation, scopeKind: "section" }, 5)).toMatch(/section/)
    expect(validateInvitation({ ...invitation, scopeKind: "section", sectionLabel: "Opening" }, 5)).toBeNull()
    expect(validateQuestions("")).toBeNull()
    expect(validateQuestions("q".repeat(300))).toBeNull()
    expect(validateQuestions("q".repeat(301))).toMatch(/300/)
    expect(validateQuestions(Array(13).fill("Question").join("\n"))).toMatch(/12/)
  })
  it("locks feedback outside the active window and terminal states", () => {
    expect(canEditFeedback(detail.assignment)).toBe(true)
    for (const patch of [{ state: "submitted" }, { state: "revoked" }, { view_bucket: "scheduled" }, { starts_at: "2099-01-01" }, { expires_at: "2020-01-01" }]) expect(canEditFeedback({ ...detail.assignment, ...patch })).toBe(false)
  })
  it("validates each feedback kind and the assigned chapter boundaries", () => {
    expect(validateFeedback(feedback, detail, 12)).toBeNull()
    for (const patch of [{ feedbackChapter: "1" }, { feedbackChapter: "5" }, { feedbackChapter: "2.5" }, { feedbackBody: " " }, { feedbackKind: "answer", selectedQuestionId: "missing" }, { feedbackKind: "favorite", feedbackChapter: "" }, { feedbackKind: "scene_reaction", feedbackBody: "" }, { feedbackAnchor: "x".repeat(501) }]) expect(validateFeedback({ ...feedback, ...patch }, detail, 12)).not.toBeNull()
    expect(validateFeedback({ ...feedback, feedbackKind: "answer", feedbackChapter: "", selectedQuestionId: "q1" }, detail, 12)).toBeNull()
    expect(validateFeedback({ ...feedback, feedbackKind: "favorite", feedbackBody: "", feedbackAnchor: "Signal" }, detail, 12)).toBeNull()
    expect(validateFeedback({ ...feedback, feedbackKind: "scene_reaction", feedbackBody: "", feedbackReaction: "Tense" }, detail, 12)).toBeNull()
  })
  it("counts unanswered questions individually rather than counting duplicate answers", () => {
    expect(reviewRequirements(detail)).toEqual(["Answer 1 remaining author question."])
    expect(reviewRequirements({ ...detail, author_questions: [] })).toEqual([])
    expect(reviewRequirements({ ...detail, assignment: { ...detail.assignment, progress_pct: 0, comment_count: 0, feedback_item_count: 0 } })).toHaveLength(4)
  })
})
