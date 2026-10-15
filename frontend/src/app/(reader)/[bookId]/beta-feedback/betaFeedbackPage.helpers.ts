import { parseQuestionLines } from "@/lib/utils/betaRead"
import type { BetaReadAssignment, BetaReadAssignmentDetail } from "@/types/betaRead"

export function validateQuestions(text: string): string | null {
  const questions = parseQuestionLines(text)
  if (questions.length > 12) return "Add at most 12 questions at a time."
  if (questions.some((question) => question.length > 300)) return "Each question must be 300 characters or fewer."
  return null
}

export function validateInvitation(draft: { readerEmail: string; taskLabel: string; scopeKind: string; sectionLabel: string; chapterStart: string; chapterEnd: string; windowDays: string; requiredProgressPct: string; requiredCommentCount: string; requiredFeedbackItemCount: string; authorQuestionsText: string }, totalChapters: number): string | null {
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(draft.readerEmail.trim()) || draft.readerEmail.trim().length > 320) return "Enter a valid reader email address."
  if (draft.taskLabel.trim().length < 3 || draft.taskLabel.trim().length > 200) return "Use a task label between 3 and 200 characters."
  if (!["full_book", "chapter_range", "section"].includes(draft.scopeKind)) return "Choose a valid manuscript scope."
  if (draft.scopeKind === "section" && (!draft.sectionLabel.trim() || draft.sectionLabel.trim().length > 200)) return "Name the section using 1–200 characters."
  if (draft.scopeKind !== "full_book") {
    const start = Number(draft.chapterStart), end = Number(draft.chapterEnd)
    if (!/^\d+$/.test(draft.chapterStart) || !/^\d+$/.test(draft.chapterEnd) || !Number.isSafeInteger(start) || !Number.isSafeInteger(end) || start < 1 || end < start || (totalChapters > 0 && end > totalChapters)) return "Choose whole chapter numbers in ascending order within this manuscript."
  }
  const fields: Array<[string, string, number, number]> = [["Window days", draft.windowDays, 3, 7], ["Progress percent", draft.requiredProgressPct, 1, 100], ["Required comments", draft.requiredCommentCount, 0, 1000], ["Required review items", draft.requiredFeedbackItemCount, 1, 1000]]
  for (const [label, value, min, max] of fields) if (!/^\d+$/.test(value) || !Number.isInteger(Number(value)) || Number(value) < min || Number(value) > max) return `${label} must be a whole number from ${min} to ${max}.`
  return validateQuestions(draft.authorQuestionsText)
}

export function canEditFeedback(assignment: BetaReadAssignment, now = Date.now()): boolean {
  return ["active", "in_progress", "ready_to_submit"].includes(assignment.state) && assignment.view_bucket !== "scheduled" && !(Date.parse(assignment.starts_at) > now) && !(Date.parse(assignment.expires_at) <= now)
}

export function validateFeedback(draft: { feedbackKind: string; feedbackChapter: string; feedbackReaction: string; feedbackAnchor: string; feedbackBody: string; selectedQuestionId: string }, detail: BetaReadAssignmentDetail, totalChapters: number): string | null {
  if (!canEditFeedback(detail.assignment)) return "This assignment is not open for new feedback. Refresh to check its current status."
  const { feedbackKind: kind, feedbackChapter: chapter, feedbackBody: body, feedbackAnchor: anchor, feedbackReaction: reaction, selectedQuestionId: question } = draft
  if (!["chapter_comment", "scene_reaction", "answer", "confusing", "boring", "favorite"].includes(kind)) return "Choose a feedback type."
  if (chapter) {
    const n = Number(chapter), start = detail.assignment.chapter_start ?? 1, end = detail.assignment.chapter_end ?? totalChapters
    if (!/^\d+$/.test(chapter) || !Number.isSafeInteger(n) || n < start || (end > 0 && n > end)) return "Choose a whole chapter number within the assigned scope, or leave it blank for book-wide feedback."
  }
  if (body.length > 10000 || anchor.length > 500 || reaction.length > 64) return "Use up to 10,000 characters for feedback, 500 for anchor text, and 64 for a reaction."
  if (question && !detail.author_questions.some((entry) => entry.id === question)) return "Choose a question from this assignment."
  if (kind === "answer" && (!question || !body.trim())) return "Select an author question and write your answer."
  if (kind === "chapter_comment" && (!chapter || !body.trim())) return "Chapter comments need a chapter number and feedback text."
  if (kind === "scene_reaction" && (!chapter || (!reaction.trim() && !body.trim()))) return "Scene reactions need a chapter number and a reaction or feedback text."
  if (["confusing", "boring", "favorite"].includes(kind) && !chapter) return "Choose the chapter where this marked moment occurs."
  if (["confusing", "boring", "favorite"].includes(kind) && !anchor.trim() && !body.trim()) return "Add anchor text or feedback to describe this moment."
  return null
}

export function reviewRequirements(detail: BetaReadAssignmentDetail): string[] {
  const a = detail.assignment, issues: string[] = []
  if (a.comment_count < a.required_comment_count) issues.push(`Leave at least ${a.required_comment_count} comments (you have ${a.comment_count}).`)
  if (a.feedback_item_count < a.required_feedback_item_count) issues.push(`Add at least ${a.required_feedback_item_count} feedback items (you have ${a.feedback_item_count}).`)
  if (a.progress_pct < a.required_progress_pct) issues.push(`Finish ${a.required_progress_pct}% of the assigned reading (you are at ${a.progress_pct}%).`)
  const unanswered = detail.author_questions.filter((question) => question.answer_count === 0)
  if (unanswered.length) issues.push(`Answer ${unanswered.length} remaining author question${unanswered.length === 1 ? "" : "s"}.`)
  return issues
}
