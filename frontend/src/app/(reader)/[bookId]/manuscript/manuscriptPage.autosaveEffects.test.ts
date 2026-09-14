import { beforeEach, describe, expect, it, vi } from "vitest"

const getAuthCsrfHeadersMock = vi.hoisted(() => vi.fn())

vi.mock("@/lib/api/client", () => ({
  getAuthCsrfHeaders: getAuthCsrfHeadersMock,
}))

import { persistManuscriptDraftOnPageHide } from "./manuscriptPage.autosaveEffects"

describe("persistManuscriptDraftOnPageHide", () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    getAuthCsrfHeadersMock.mockReset()
    getAuthCsrfHeadersMock.mockReturnValue({ "X-CSRF-Token": "csrf-token" })
  })

  it("uses an authenticated keepalive request with the CSRF header", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 202 }))
    vi.stubGlobal("fetch", fetchMock)

    expect(
      persistManuscriptDraftOnPageHide({
        activeChapterNumber: 4,
        bookId: "book-1",
        draft: { html: "<p>Safe draft</p>", text: "Safe draft", title: "Chapter Four" },
      })
    ).toBe(true)

    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toBe("/api/v1/books/book-1/manuscript/import")
    expect(init).toMatchObject({
      credentials: "include",
      headers: { "X-CSRF-Token": "csrf-token" },
      keepalive: true,
      method: "POST",
    })
    expect(init.body).toBeInstanceOf(FormData)
    const body = init.body as FormData
    expect(body.get("chapter_number")).toBe("4")
    expect(body.get("replace_existing")).toBe("true")
    expect(body.get("text")).toBe("Safe draft")
  })

  it("does not send an empty draft", () => {
    const fetchMock = vi.fn()
    vi.stubGlobal("fetch", fetchMock)

    expect(
      persistManuscriptDraftOnPageHide({
        activeChapterNumber: 1,
        bookId: "book-1",
        draft: { text: "   " },
      })
    ).toBe(false)
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it("does not surface a rejected best-effort request", async () => {
    const fetchMock = vi.fn().mockRejectedValue(new Error("page already closed"))
    vi.stubGlobal("fetch", fetchMock)

    expect(
      persistManuscriptDraftOnPageHide({
        activeChapterNumber: 1,
        bookId: "book-1",
        draft: { text: "Draft" },
      })
    ).toBe(true)
    await Promise.resolve()
  })
})
