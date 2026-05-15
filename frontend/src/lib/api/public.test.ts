import { beforeEach, describe, expect, it, vi } from "vitest"

const { getMock, postMock, putMock } = vi.hoisted(() => ({
  getMock: vi.fn(),
  postMock: vi.fn(),
  putMock: vi.fn(),
}))

vi.mock("./client", () => ({
  apiClient: {
    get: getMock,
    post: postMock,
    put: putMock,
  },
}))

import { publicApi } from "./public"

describe("public api", () => {
  beforeEach(() => {
    getMock.mockReset()
    postMock.mockReset()
    putMock.mockReset()

    getMock.mockResolvedValue({ data: { ok: true, items: [] } })
    postMock.mockResolvedValue({ data: { ok: true } })
    putMock.mockResolvedValue({ data: { ok: true } })
  })

  it("lists forum posts with an optional search query", async () => {
    await publicApi.listForumPosts("  sky harbor  ")

    expect(getMock).toHaveBeenCalledWith("/public/forum/posts", {
      params: { q: "sky harbor" },
    })
  })

  it("loads public books through the public client", async () => {
    await publicApi.listBooks()

    expect(getMock).toHaveBeenCalledWith("/public/books")
  })

  it("loads public book details and chapters", async () => {
    await publicApi.getBook("book-1")
    await publicApi.getChapter("book-1", 2)

    expect(getMock).toHaveBeenCalledWith("/public/books/book-1")
    expect(getMock).toHaveBeenCalledWith("/public/books/book-1/chapter/2")
  })

  it("loads a forum post detail", async () => {
    await publicApi.getForumPost("post-1")

    expect(getMock).toHaveBeenCalledWith("/public/forum/posts/post-1")
  })

  it("loads forum comments for a post", async () => {
    await publicApi.listForumComments("post-1")

    expect(getMock).toHaveBeenCalledWith("/public/forum/posts/post-1/comments")
  })

  it("creates a forum comment", async () => {
    await publicApi.createForumComment("post-2", "Helpful note")

    expect(postMock).toHaveBeenCalledWith("/public/forum/posts/post-2/comments", {
      body: "Helpful note",
    })
  })

  it("reacts to a forum comment", async () => {
    await publicApi.reactToForumComment("comment-3", "dislike")

    expect(putMock).toHaveBeenCalledWith("/public/forum/comments/comment-3/reaction", {
      reaction: "dislike",
    })
  })

  it("loads a public user profile with encoded usernames", async () => {
    await publicApi.getUserProfile("writer name")

    expect(getMock).toHaveBeenCalledWith("/public/users/writer%20name")
  })
})
