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
