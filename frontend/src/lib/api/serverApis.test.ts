import { beforeEach, describe, expect, it, vi } from "vitest"

vi.mock("next/navigation", () => ({ notFound: () => { throw new Error("NEXT_NOT_FOUND") } }))

import {
  getPublicBookServer,
  getPublicChapterServer,
  getPublicForumPostServer,
  getPublicUploadsAnalyticsServer,
  getPublicUserProfileServer,
  listCreatorPublicUploadsServer,
  listPublicBooksServer,
  listPublicForumCommentsServer,
  listPublicForumPostsServer,
  listRankedBetaNovelsServer,
  listRankedCreatorPublicUploadsServer,
} from "./public.server"
import { serverApi } from "./server"

const fetchMock = vi.fn()

beforeEach(() => {
  fetchMock.mockReset().mockResolvedValue(response({ ok: true }))
  vi.stubGlobal("fetch", fetchMock)
})

describe("server API wrappers", () => {
  it("builds every public server endpoint and query variant", async () => {
    fetchMock
      .mockResolvedValueOnce(response([]))
      .mockResolvedValueOnce(response([]))
      .mockResolvedValueOnce(response([]))
      .mockResolvedValueOnce(response({ items: [] }))
      .mockResolvedValueOnce(response({ id: "book-1" }))
      .mockResolvedValueOnce(response({ total_public_books: 1 }))
      .mockResolvedValueOnce(response({ chapter_number: 2 }))
      .mockResolvedValueOnce(response({ items: [] }))
      .mockResolvedValueOnce(response({ items: [] }))
      .mockResolvedValueOnce(response({ id: "post-1" }))
      .mockResolvedValueOnce(response({ items: [{ id: "comment-1" }] }))
      .mockResolvedValueOnce(response({ username: "mara" }))

    await listPublicBooksServer()
    await listCreatorPublicUploadsServer()
    await listCreatorPublicUploadsServer(" gate draft ")
    await listRankedCreatorPublicUploadsServer({ ranking: "newest", timeWindow: "weekly", query: " gate ", page: 2, limit: 10 })
    await getPublicBookServer("gate/draft")
    await getPublicUploadsAnalyticsServer()
    await getPublicChapterServer("gate/draft", 2)
    await listPublicForumPostsServer(" beta read ")
    await listRankedBetaNovelsServer({ ranking: "newest", timeWindow: "weekly", query: " gate ", page: 3, pageSize: 5 })
    await getPublicForumPostServer("post/1")
    expect(await listPublicForumCommentsServer("post/1")).toEqual([{ id: "comment-1" }])
    await getPublicUserProfileServer("mara vale")

    const urls = fetchMock.mock.calls.map(([url]) => String(url))
    expect(urls[0]).toContain("/api/v1/public/books")
    expect(urls[1]).toMatch(/\/uploads$/)
    expect(urls[2]).toContain("/uploads?search=gate+draft")
    expect(urls[3]).toContain("ranking=newest")
    expect(urls[3]).toContain("page=2")
    expect(urls[4]).toContain("/books/gate%2Fdraft")
    expect(urls[7]).toContain("q=beta+read")
    expect(urls[8]).toContain("page_size=5")
    expect(urls[9]).toContain("post%2F1")
    expect(urls[11]).toContain("mara%20vale")
    expect(fetchMock.mock.calls[3]?.[1]).toEqual({ next: { revalidate: 120 } })
  })

  it("handles public not-found and provider errors", async () => {
    fetchMock.mockResolvedValueOnce(response({}, 404))
    await expect(getPublicBookServer("missing")).rejects.toThrow("NEXT_NOT_FOUND")

    fetchMock.mockResolvedValueOnce(response({}, 503))
    await expect(listPublicBooksServer()).rejects.toThrow("status 503")
  })

  it("builds authenticated reader and books requests and returns null for auth and network failures", async () => {
    fetchMock
      .mockResolvedValueOnce(response({ chapter_num: 4 }))
      .mockResolvedValueOnce(response([{ id: "book-1" }]))
      .mockResolvedValueOnce(response({}, 401))
      .mockResolvedValueOnce(response({}, 403))
      .mockResolvedValueOnce(response({}, 500))
      .mockRejectedValueOnce(new Error("network"))

    expect(await serverApi.getChapter("book 1", 4, "session=abc")).toEqual({ chapter_num: 4 })
    expect(await serverApi.listBooks(true, null)).toEqual([{ id: "book-1" }])
    expect(await serverApi.listBooks(false, null)).toBeNull()
    expect(await serverApi.getChapter("book-1", 1, null)).toBeNull()
    expect(await serverApi.listBooks(false, null)).toBeNull()
    expect(await serverApi.listBooks(false, null)).toBeNull()

    expect(String(fetchMock.mock.calls[0]?.[0])).toContain("/reader/book 1/chapter/4")
    expect(fetchMock.mock.calls[0]?.[1]).toEqual(expect.objectContaining({ cache: "no-store", headers: { cookie: "session=abc" } }))
    expect(fetchMock.mock.calls[1]?.[1]).toEqual(expect.objectContaining({ headers: undefined }))
  })
})

function response(payload: unknown, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: vi.fn().mockResolvedValue(payload),
  }
}
