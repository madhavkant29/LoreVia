import { beforeEach, describe, expect, it, vi } from "vitest"

const { getMock, postMock } = vi.hoisted(() => ({
  getMock: vi.fn(),
  postMock: vi.fn(),
}))

vi.mock("./client", () => ({
  apiClient: {
    get: getMock,
    post: postMock,
  },
}))

import { intelligenceApi } from "./intelligence"

describe("intelligence api", () => {
  beforeEach(() => {
    getMock.mockReset()
    postMock.mockReset()
    getMock.mockResolvedValue({ data: { ok: true } })
    postMock.mockResolvedValue({ data: { ok: true } })
  })

  it("loads advisor suggestions with normalized book ids", async () => {
    await intelligenceApi.advisorSuggestions("sky-harbor--123e4567-e89b-12d3-a456-426614174000")

    expect(getMock).toHaveBeenCalledWith("/intelligence/123e4567-e89b-12d3-a456-426614174000/advisor/suggestions")
  })

  it("posts editorial review payloads with null chapter numbers when omitted", async () => {
    await intelligenceApi.editorialReview("book-1", "Passage text")

    expect(postMock).toHaveBeenCalledWith("/intelligence/book-1/advisor/editorial-review", {
      text: "Passage text",
      chapter_num: null,
    })
  })

  it("truncates long advisor passages before posting inline continuity checks", async () => {
    const longText = "a".repeat(12_500)

    await intelligenceApi.inlineContinuity("book-1", longText, 3)

    expect(postMock).toHaveBeenCalledWith("/intelligence/book-1/advisor/inline-continuity", {
      text: "a".repeat(12_000),
      chapter_num: 3,
    })
  })

  it("truncates long advisor passages before posting voice consistency checks", async () => {
    const longText = "b".repeat(12_345)

    await intelligenceApi.voiceConsistencyReview("book-1", longText)

    expect(postMock).toHaveBeenCalledWith("/intelligence/book-1/advisor/voice-consistency", {
      text: "b".repeat(12_000),
      chapter_num: null,
    })
  })

  it("polls advisor tasks until the result is ready", async () => {
    postMock.mockResolvedValueOnce({ data: { task_id: "task-1", status: "queued", cached: false } })
    getMock
      .mockResolvedValueOnce({ data: { task_id: "task-1", status: "queued", result: null } })
      .mockResolvedValueOnce({ data: { task_id: "task-1", status: "complete", result: { reply: "Ready", intent: "general", response_type: "standard", retrieved_passages: [] } } })

    const result = await intelligenceApi.advisorMessage("book-1", [{ role: "user", content: "Help" }], 12)

    expect(postMock).toHaveBeenCalledWith("/intelligence/book-1/advisor/message-async", {
      messages: [{ role: "user", content: "Help" }],
      total_chapters: 12,
    })
    expect(getMock).toHaveBeenCalledWith("/intelligence/book-1/advisor/message-async/task-1")
    expect(result.reply).toBe("Ready")
  })

  it("polls series advisor tasks until the result is ready", async () => {
    postMock.mockResolvedValueOnce({ data: { task_id: "series-task-1", status: "queued", cached: false } })
    getMock
      .mockResolvedValueOnce({ data: { task_id: "series-task-1", status: "queued", result: null } })
      .mockResolvedValueOnce({ data: { task_id: "series-task-1", status: "complete", result: { reply: "Series ready", intent: "general", response_type: "standard", retrieved_passages: [] } } })

    const result = await intelligenceApi.seriesAdvisorMessage("series-1", [{ role: "user", content: "Across the series?" }])

    expect(postMock).toHaveBeenCalledWith("/intelligence/series/series-1/advisor/message", {
      messages: [{ role: "user", content: "Across the series?" }],
    })
    expect(getMock).toHaveBeenCalledWith("/intelligence/series/series-1/advisor/message/series-task-1")
    expect(result.reply).toBe("Series ready")
  })
})
