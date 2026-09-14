import { beforeEach, describe, expect, it, vi } from "vitest"

const { getMock, invalidateQueryKeysMock, postMock } = vi.hoisted(() => ({
  getMock: vi.fn(),
  invalidateQueryKeysMock: vi.fn(),
  postMock: vi.fn(),
}))

vi.mock("./client", () => ({
  apiClient: {
    get: getMock,
    post: postMock,
  },
}))

vi.mock("@/lib/query/queryClient", () => ({
  invalidateQueryKeys: invalidateQueryKeysMock,
}))

import { intelligenceApi } from "./intelligence"

describe("intelligence api", () => {
  beforeEach(() => {
    vi.unstubAllGlobals()
    getMock.mockReset()
    invalidateQueryKeysMock.mockReset()
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

  it("posts selected character ids for voice consistency checks when provided", async () => {
    await intelligenceApi.voiceConsistencyReview("book-1", "Passage text", {
      chapterNum: 4,
      characterId: "char-1",
    })

    expect(postMock).toHaveBeenCalledWith("/intelligence/book-1/advisor/voice-consistency", {
      text: "Passage text",
      chapter_num: 4,
      character_id: "char-1",
    })
  })

  it("serializes AI beta reader requests, status, reports, and revision tasks", async () => {
    postMock.mockResolvedValue({ data: { task_id: "revision-task", candidate_id: "candidate-1", created: true } })

    await intelligenceApi.runBetaReader("book-1", {
      scope: "chapter_range",
      chapter_start: 2,
      chapter_end: 4,
      character_ids: ["char-1", "char-2"],
      checks: ["repetition", "voice", "reader_feedback"],
    })
    await intelligenceApi.getBetaReaderJob("book-1", "job-1")
    await intelligenceApi.getBetaReaderReports("book-1")
    const task = await intelligenceApi.createBetaReaderRevisionTask(
      "book-1",
      "report/1",
      "candidate 1",
    )

    expect(postMock).toHaveBeenCalledWith("/intelligence/book-1/advisor/beta-reader", {
      scope: "chapter_range",
      chapter_start: 2,
      chapter_end: 4,
      character_ids: ["char-1", "char-2"],
      checks: ["repetition", "voice", "reader_feedback"],
    })
    expect(getMock).toHaveBeenCalledWith("/intelligence/book-1/advisor/beta-reader/jobs/job-1")
    expect(getMock).toHaveBeenCalledWith("/intelligence/book-1/advisor/beta-reader/reports")
    expect(postMock).toHaveBeenCalledWith(
      "/intelligence/book-1/advisor/beta-reader/reports/report%2F1/revision-candidates/candidate%201",
    )
    expect(invalidateQueryKeysMock).toHaveBeenCalledWith("book:book-1:revision-intelligence")
    expect(invalidateQueryKeysMock).toHaveBeenCalledWith("book:book-1:writer-workspace")
    expect(task.created).toBe(true)
  })

  it("polls advisor tasks until the result is ready", async () => {
    postMock.mockResolvedValueOnce({ data: { task_id: "task-1", status: "queued", cached: false } })
    getMock
      .mockResolvedValueOnce({ data: { task_id: "task-1", status: "queued", result: null } })
      .mockResolvedValueOnce({ data: { task_id: "task-1", status: "complete", result: { reply: "Ready", intent: "general", response_type: "standard", retrieved_passages: [] } } })

    const result = await intelligenceApi.advisorMessage("book-1", [{ role: "user", content: "Help" }])

    expect(postMock).toHaveBeenCalledWith("/intelligence/book-1/advisor/message-async", {
      messages: [{ role: "user", content: "Help" }],
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
      { onDelta: (content) => chunks.push(content) },
    )

    expect(fetchMock).toHaveBeenCalledWith("/api/v1/intelligence/book-1/advisor/message-stream", expect.objectContaining({
      method: "POST",
      credentials: "include",
      body: JSON.stringify({
        messages: [{ role: "user", content: "Help" }],
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

  it("builds the remaining intelligence request wrappers and optional payloads", async () => {
    await intelligenceApi.answer("book-1", "Who holds the key?", 4)
    await intelligenceApi.getCrossBookIntelligence("book-1")
    await intelligenceApi.advisorGreeting("book-1")
    await intelligenceApi.advisorSuggestionsScan("book-1")
    await intelligenceApi.advisorSuggestionsJobStatus("book-1", "job-1")
    await intelligenceApi.proseTighten("book-1", "Long line")
    await intelligenceApi.whatsTheWord("book-1", "a guarded expression", "scowl")
    await intelligenceApi.continuityReport("book-1", "Passage", "pdf", 3)
    await intelligenceApi.synopsis("book-1", "none")
    await intelligenceApi.seriesContinuityCheck("series-1", "gate--book-1", "Passage", 4)

    expect(postMock).toHaveBeenCalledWith("/intelligence/book-1/qa", { question: "Who holds the key?", current_chapter: 4 })
    expect(getMock).toHaveBeenCalledWith("/intelligence/book-1/cross-book-intelligence")
    expect(postMock).toHaveBeenCalledWith("/intelligence/book-1/advisor/prose-tighten", { text: "Long line", chapter_num: null })
    expect(postMock).toHaveBeenCalledWith("/intelligence/book-1/advisor/whats-the-word", { description: "a guarded expression", previous_word: "scowl" })
    expect(getMock).toHaveBeenCalledWith("/intelligence/book-1/advisor/continuity-report", expect.objectContaining({ responseType: "blob" }))
    expect(getMock).toHaveBeenCalledWith("/intelligence/book-1/advisor/synopsis", { params: { spoiler_level: "none" } })
    expect(postMock).toHaveBeenCalledWith("/intelligence/series/series-1/continuity-check", { book_id: "book-1", text: "Passage", chapter_num: 4 })
  })

  it("returns immediate advisor replies and reports failed async tasks", async () => {
    postMock.mockResolvedValueOnce({ data: { reply: "Immediate", intent: "general", response_type: "standard", retrieved_passages: [] } })
    await expect(intelligenceApi.advisorMessage("book-1", [])).resolves.toEqual(expect.objectContaining({ reply: "Immediate" }))

    postMock.mockResolvedValueOnce({ data: { task_id: "task-failed", status: "queued" } })
    getMock.mockResolvedValueOnce({ data: { status: "failed", error: "Provider failed" } })
    await expect(intelligenceApi.advisorMessage("book-1", [])).rejects.toThrow("Provider failed")

    postMock.mockResolvedValueOnce({ data: { task_id: "series-failed", status: "queued" } })
    getMock.mockResolvedValueOnce({ data: { status: "failed", error: null } })
    await expect(intelligenceApi.seriesAdvisorMessage("series-1", [])).rejects.toThrow("Advisor generation failed")
  })

  it("refreshes a 401 SSE request, sends CSRF, and parses a final buffered event", async () => {
    document.cookie = "lorevia_csrf=token%201; Path=/"
    const encoder = new TextEncoder()
    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(encoder.encode('event: done\ndata: {"tightened_text":"Tight","rationale":[]}'))
        controller.close()
      },
    })
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ ok: false, status: 401, body: null })
      .mockResolvedValueOnce({ ok: true, status: 200, body: stream })
    vi.stubGlobal("fetch", fetchMock)

    const result = await intelligenceApi.proseTightenStream("book-1", "Text", 2)

    expect(postMock).toHaveBeenCalledWith("/auth/refresh")
    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(fetchMock.mock.calls[1]?.[1].headers["X-CSRF-Token"]).toBe("token 1")
    expect(result.tightened_text).toBe("Tight")
  })

  it("reports SSE HTTP, missing-body, event, and incomplete-stream failures", async () => {
    const encoder = new TextEncoder()
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: false,
      status: 422,
      text: vi.fn().mockResolvedValue('{"detail":"bad passage"}'),
    }))
    await expect(intelligenceApi.answerStream("book-1", "?", 1)).rejects.toThrow("bad passage")

    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, status: 200, body: null }))
    await expect(intelligenceApi.answerStream("book-1", "?", 1)).rejects.toThrow("unavailable")

    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      body: new ReadableStream({ start(controller) { controller.enqueue(encoder.encode('event: error\ndata: {"error":"stream exploded"}\n\n')); controller.close() } }),
    }))
    await expect(intelligenceApi.answerStream("book-1", "?", 1)).rejects.toThrow("stream exploded")

    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      body: new ReadableStream({ start(controller) { controller.enqueue(encoder.encode('event: delta\ndata: {"content":"partial"}\n\n')); controller.close() } }),
    }))
    await expect(intelligenceApi.answerStream("book-1", "?", 1)).rejects.toThrow("before a final response")
  })
})
