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
    vi.unstubAllGlobals()
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

  it("streams advisor deltas and returns the final response", async () => {
    const encoder = new TextEncoder()
    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(encoder.encode('event: delta\ndata: {"content":"Hel"}\n\n'))
        controller.enqueue(encoder.encode('event: delta\ndata: {"content":"lo"}\n\n'))
        controller.enqueue(encoder.encode('event: done\ndata: {"reply":"Hello","intent":"general","response_type":"standard","retrieved_passages":[],"cached":false}\n\n'))
        controller.close()
      },
    })
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      body: stream,
    })
    vi.stubGlobal("fetch", fetchMock)
    const chunks: string[] = []

    const result = await intelligenceApi.advisorMessageStream(
      "book-1",
      [{ role: "user", content: "Help" }],
      12,
      { onDelta: (content) => chunks.push(content) },
    )

    expect(fetchMock).toHaveBeenCalledWith("/api/v1/intelligence/book-1/advisor/message-stream", expect.objectContaining({
      method: "POST",
      credentials: "include",
      body: JSON.stringify({
        messages: [{ role: "user", content: "Help" }],
        total_chapters: 12,
      }),
    }))
    expect(chunks).toEqual(["Hel", "lo"])
    expect(result.reply).toBe("Hello")
  })

  it("streams grounded answers with stage updates", async () => {
    const encoder = new TextEncoder()
    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(encoder.encode('event: stage\ndata: {"message":"Searching grounded context..."}\n\n'))
        controller.enqueue(encoder.encode('event: delta\ndata: {"content":"Grounded"}\n\n'))
        controller.enqueue(encoder.encode('event: delta\ndata: {"content":" answer"}\n\n'))
        controller.enqueue(encoder.encode('event: done\ndata: {"answer":"Grounded answer","citations":[{"chapter_num":2,"chapter_title":"Two","excerpt":"Evidence","source_type":"passage"}],"cached":false}\n\n'))
        controller.close()
      },
    })
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      body: stream,
    })
    vi.stubGlobal("fetch", fetchMock)
    const stages: string[] = []
    const chunks: string[] = []

    const result = await intelligenceApi.answerStream("book-1", "Who?", 3, {
      onStage: (message) => stages.push(message),
      onDelta: (content) => chunks.push(content),
    })

    expect(fetchMock).toHaveBeenCalledWith("/api/v1/intelligence/book-1/qa-stream", expect.objectContaining({
      method: "POST",
      body: JSON.stringify({ question: "Who?", current_chapter: 3 }),
    }))
    expect(stages).toEqual(["Searching grounded context..."])
    expect(chunks).toEqual(["Grounded", " answer"])
    expect(result.answer).toBe("Grounded answer")
    expect(result.citations[0]?.chapter_num).toBe(2)
  })

  it("streams synopsis requests with GET", async () => {
    const encoder = new TextEncoder()
    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(encoder.encode('event: done\ndata: {"synopsis":"Short synopsis","focus_points":[],"coverage_chapters":[1,2,3],"spoiler_level":"minimal"}\n\n'))
        controller.close()
      },
    })
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      body: stream,
    })
    vi.stubGlobal("fetch", fetchMock)

    const result = await intelligenceApi.synopsisStream("book-1", "minimal")

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/intelligence/book-1/advisor/synopsis-stream?spoiler_level=minimal",
      expect.objectContaining({
        method: "GET",
        body: undefined,
      }),
    )
    expect(result.synopsis).toBe("Short synopsis")
  })
})
