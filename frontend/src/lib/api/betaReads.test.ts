import { beforeEach, describe, expect, it, vi } from "vitest"

const {
  getMock,
  postMock,
  putMock,
  deleteMock,
  invalidateQueryKeysMock,
} = vi.hoisted(() => ({
  getMock: vi.fn(),
  postMock: vi.fn(),
  putMock: vi.fn(),
  deleteMock: vi.fn(),
  invalidateQueryKeysMock: vi.fn(),
}))

vi.mock("./client", () => ({
  apiClient: {
    get: getMock,
    post: postMock,
    put: putMock,
    delete: deleteMock,
  },
}))

vi.mock("@/lib/query/queryClient", () => ({
  invalidateQueryKeys: invalidateQueryKeysMock,
}))

import { betaReadsApi } from "./betaReads"

describe("betaReads api", () => {
  beforeEach(() => {
    getMock.mockReset()
    postMock.mockReset()
    putMock.mockReset()
    deleteMock.mockReset()
    invalidateQueryKeysMock.mockReset()

    getMock.mockResolvedValue({ data: { items: [], author_questions: [], feedback_items: [], feedback_summary: {} } })
    postMock.mockResolvedValue({ data: { ok: true } })
    putMock.mockResolvedValue({ data: { ok: true } })
    deleteMock.mockResolvedValue({ data: { ok: true } })
  })

  it("creates beta assignments with review requirements and author questions", async () => {
    await betaReadsApi.createAssignment("book-1", {
      readerEmail: "beta@example.com",
      taskLabel: "First-pass response",
      scopeKind: "chapter_range",
      chapterStart: 3,
      chapterEnd: 5,
      windowDays: 4,
      requiredProgressPct: 100,
      requiredCommentCount: 3,
      requiredFeedbackItemCount: 4,
      requireFinalFeedback: true,
      authorQuestions: ["Did Chapter 3 hook you?", "Where did you get confused?"],
    })

    expect(postMock).toHaveBeenCalledWith("/books/book-1/beta-reads", {
      reader_email: "beta@example.com",
      task_label: "First-pass response",
      scope_kind: "chapter_range",
      section_label: undefined,
      chapter_start: 3,
      chapter_end: 5,
      window_days: 4,
      required_progress_pct: 100,
      required_comment_count: 3,
      required_feedback_item_count: 4,
      require_final_feedback: true,
      author_questions: ["Did Chapter 3 hook you?", "Where did you get confused?"],
    })
    expect(invalidateQueryKeysMock).toHaveBeenCalledWith("reader:beta-reads:")
    expect(invalidateQueryKeysMock).toHaveBeenCalledWith("books:list:")
  })

  it("loads the reader detail feed from the dedicated endpoint", async () => {
    await betaReadsApi.getMineDetail("assignment-1")

    expect(getMock).toHaveBeenCalledWith("/beta-reads/assignment-1")
  })

  it("creates structured feedback items with the backend payload shape", async () => {
    await betaReadsApi.createFeedbackItem("assignment-2", {
      kind: "answer",
      chapterNumber: 3,
      questionId: "question-1",
      reaction: null,
      anchorText: "The gate reveal",
      body: "I expected the reveal one page earlier.",
    })

    expect(postMock).toHaveBeenCalledWith("/beta-reads/assignment-2/feedback-items", {
      kind: "answer",
      chapter_number: 3,
      scene_id: null,
      question_id: "question-1",
      reaction: null,
      anchor_text: "The gate reveal",
      body: "I expected the reveal one page earlier.",
    })
  })

  it("submits the final review with a half-step rating", async () => {
    await betaReadsApi.submitReview("assignment-3", "The midpoint landed better than I expected.", 4.5)

    expect(postMock).toHaveBeenCalledWith("/beta-reads/assignment-3/submit-feedback", {
      final_feedback: "The midpoint landed better than I expected.",
      final_rating: 4.5,
    })
    expect(invalidateQueryKeysMock).toHaveBeenCalledWith("reader:beta-reads:")
    expect(invalidateQueryKeysMock).toHaveBeenCalledWith("books:list:")
  })

  it("uses the token-scoped guest endpoints for progress and feedback", async () => {
    await betaReadsApi.getGuestReview("signed/token")
    await betaReadsApi.markGuestChapterRead("signed/token", 4)
    await betaReadsApi.createGuestFeedbackItem("signed/token", {
      kind: "answer",
      questionId: "question-4",
      body: "The reveal landed clearly.",
    })

    expect(getMock).toHaveBeenCalledWith("/beta-review/signed%2Ftoken")
    expect(postMock).toHaveBeenNthCalledWith(1, "/beta-review/signed%2Ftoken/progress", {
      chapter_number: 4,
    })
    expect(postMock).toHaveBeenNthCalledWith(2, "/beta-review/signed%2Ftoken/feedback-items", {
      kind: "answer",
      chapter_number: null,
      question_id: "question-4",
      anchor_text: null,
      body: "The reveal landed clearly.",
    })
  })

  it("updates author triage state for a feedback item", async () => {
    await betaReadsApi.updateBookFeedbackItem("book-1", "assignment-2", "feedback-9", {
      authorStatus: "task_created",
      authorTaskId: "revision-task:feedback-9",
    })

    expect(putMock).toHaveBeenCalledWith("/books/book-1/beta-reads/assignment-2/feedback-items/feedback-9", {
      author_status: "task_created",
      author_task_id: "revision-task:feedback-9",
    })
    expect(invalidateQueryKeysMock).toHaveBeenCalledWith("reader:beta-reads:")
    expect(invalidateQueryKeysMock).toHaveBeenCalledWith("books:list:")
  })

  it("normalizes slugged reader route ids for book-scoped beta-read calls", async () => {
    const routeId = "sky-of-ash--123e4567-e89b-12d3-a456-426614174000"

    await betaReadsApi.listBookAssignments(routeId)
    await betaReadsApi.getBookAssignmentDetail(routeId, "assignment-2")
    await betaReadsApi.appendQuestions(routeId, "assignment-2", ["Did the reveal land?"])
    await betaReadsApi.revokeAssignment(routeId, "assignment-2")
    await betaReadsApi.updateBookFeedbackItem(routeId, "assignment-2", "feedback-9", {
      authorStatus: "reviewed",
    })

    expect(getMock).toHaveBeenNthCalledWith(1, "/books/123e4567-e89b-12d3-a456-426614174000/beta-reads")
    expect(getMock).toHaveBeenNthCalledWith(2, "/books/123e4567-e89b-12d3-a456-426614174000/beta-reads/assignment-2")
    expect(postMock).toHaveBeenNthCalledWith(
      1,
      "/books/123e4567-e89b-12d3-a456-426614174000/beta-reads/assignment-2/questions",
      { questions: ["Did the reveal land?"] }
    )
    expect(postMock).toHaveBeenNthCalledWith(
      2,
      "/books/123e4567-e89b-12d3-a456-426614174000/beta-reads/assignment-2/revoke"
    )
    expect(putMock).toHaveBeenCalledWith(
      "/books/123e4567-e89b-12d3-a456-426614174000/beta-reads/assignment-2/feedback-items/feedback-9",
      {
        author_status: "reviewed",
        author_task_id: null,
      }
    )
  })
})
