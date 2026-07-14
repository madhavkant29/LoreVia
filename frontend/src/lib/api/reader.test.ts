import { beforeEach, describe, expect, it, vi } from "vitest"

const {
  getMock,
  postMock,
  putMock,
  invalidateQueryKeysMock,
} = vi.hoisted(() => ({
  getMock: vi.fn(),
  postMock: vi.fn(),
  putMock: vi.fn(),
  invalidateQueryKeysMock: vi.fn(),
}))

vi.mock("./client", () => ({
  apiClient: {
    get: getMock,
    post: postMock,
    put: putMock,
  },
}))

vi.mock("@/lib/query/queryClient", () => ({
  invalidateQueryKeys: invalidateQueryKeysMock,
}))

import { readerApi } from "./reader"

describe("reader api", () => {
  beforeEach(() => {
    getMock.mockReset()
    postMock.mockReset()
    putMock.mockReset()
    invalidateQueryKeysMock.mockReset()

    getMock.mockResolvedValue({ data: { ok: true } })
    postMock.mockResolvedValue({ data: { ok: true } })
    putMock.mockResolvedValue({ data: { ok: true } })
  })

  it("loads upcoming beta reads", async () => {
    getMock.mockResolvedValue({ data: { items: [{ id: "assignment-1" }] } })

    const items = await readerApi.getUpcomingBetaReads()

    expect(getMock).toHaveBeenCalledWith("/beta-reads/upcoming")
    expect(items).toEqual([{ id: "assignment-1" }])
  })

  it("loads bucketed beta reads with query params", async () => {
    getMock.mockResolvedValue({ data: { items: [{ id: "assignment-2" }] } })

    await readerApi.listBetaReads("missed")

    expect(getMock).toHaveBeenCalledWith("/beta-reads", { params: { bucket: "missed" } })
  })

  it("loads story recall", async () => {
    getMock.mockResolvedValue({ data: { recall: "Nora crossed the gate.", last_chapter: 3 } })

    const recall = await readerApi.getRecall("book-7")

    expect(getMock).toHaveBeenCalledWith("/reader/book-7/recall")
    expect(recall).toEqual({ recall: "Nora crossed the gate.", last_chapter: 3 })
  })

  it("loads chapter data with the full default include set", async () => {
    await readerApi.getChapter("book-7", 4)

    expect(getMock).toHaveBeenCalledWith("/reader/book-7/chapter/4", {
      params: {
        include: "characters,media,tags,beta_feedback,text_content,html_content,text_url",
        fields: undefined,
      },
    })
  })

  it("loads chapter data with explicit includes and fields", async () => {
    await readerApi.getChapter("book-7", 4, {
      include: ["text_content", "html_content"],
      fields: ["content_version"],
    })

    expect(getMock).toHaveBeenCalledWith("/reader/book-7/chapter/4", {
      params: {
        include: "text_content,html_content",
        fields: "content_version",
      },
    })
  })

  it("serializes an empty chapter include set as an explicit no-op include", async () => {
    await readerApi.getChapter("book-7", 4, {
      include: [],
      fields: ["content_version"],
    })

    expect(getMock).toHaveBeenCalledWith("/reader/book-7/chapter/4", {
      params: {
        include: "__none__",
        fields: "content_version",
      },
    })
  })

  it("loads timeline data with the default track include set", async () => {
    await readerApi.getTimeline("book-7")

    expect(getMock).toHaveBeenCalledWith("/reader/book-7/timeline", {
      params: {
        limit: 100,
        offset: 0,
        include: "chapters,character_tracks,thread_tracks,relationship_markers",
      },
    })
  })

  it("loads timeline data with an explicit include set", async () => {
    await readerApi.getTimeline("book-7", { limit: 25, include: "events" })

    expect(getMock).toHaveBeenCalledWith("/reader/book-7/timeline", {
      params: {
        limit: 25,
        offset: 0,
        include: "events",
      },
    })
  })

  it("starts a beta read and invalidates beta-read caches", async () => {
    await readerApi.startBetaRead("assignment-3")

    expect(postMock).toHaveBeenCalledWith("/beta-reads/assignment-3/start")
    expect(invalidateQueryKeysMock).toHaveBeenCalledWith("reader:beta-reads:")
    expect(invalidateQueryKeysMock).toHaveBeenCalledWith("books:list:")
  })

  it("submits feedback with the backend payload shape", async () => {
    await readerApi.submitBetaReadFeedback("assignment-4", "Strong midpoint pacing.", 4.5)

    expect(postMock).toHaveBeenCalledWith("/beta-reads/assignment-4/submit-feedback", {
      final_feedback: "Strong midpoint pacing.",
      final_rating: 4.5,
    })
  })
})
