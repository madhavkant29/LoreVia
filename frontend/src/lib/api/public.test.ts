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
      params: { q: "sky harbor", page: 1, page_size: 20 },
    })
  })

  it("passes pagination params for forum post listing", async () => {
    await publicApi.listForumPosts(undefined, 3, 50)

    expect(getMock).toHaveBeenCalledWith("/public/forum/posts", {
      params: { page: 3, page_size: 50 },
    })
  })

  it("loads public books through the public client", async () => {
    await publicApi.listBooks()

    expect(getMock).toHaveBeenCalledWith("/public/books", { params: {} })
  })

  it("passes creator-upload filters and search params for public books", async () => {
    await publicApi.listBooks({ catalog: "creator_uploads", search: " moon harbor " })

    expect(getMock).toHaveBeenCalledWith("/public/books", {
      params: { catalog: "creator_uploads", search: "moon harbor" },
    })
  })

  it("loads creator uploads and public upload analytics", async () => {
    await publicApi.listCreatorUploads({ search: " ember " })
    await publicApi.getUploadsAnalytics()

    expect(getMock).toHaveBeenCalledWith("/public/uploads", {
      params: { search: "ember" },
    })
    expect(getMock).toHaveBeenCalledWith("/public/analytics")
  })

  it("loads public book details and chapters", async () => {
    await publicApi.getBook("book-1")
    await publicApi.getChapter("book-1", 2)

    expect(getMock).toHaveBeenCalledWith("/public/books/book-1")
    expect(getMock).toHaveBeenCalledWith("/public/books/book-1/chapter/2")
  })

  it("tracks book analytics views", async () => {
    await publicApi.trackView("book-1", { eventType: "chapter_view", chapterNumber: 2 })

    expect(postMock).toHaveBeenCalledWith("/public/books/book-1/analytics/view", {
      event_type: "chapter_view",
      chapter_number: 2,
    })
  })

  it("tracks public book and chapter views", async () => {
    await publicApi.trackView("book-1", { eventType: "book_view" })
    await publicApi.trackView("book-1", { eventType: "chapter_view", chapterNumber: 3 })

    expect(postMock).toHaveBeenCalledWith("/public/books/book-1/analytics/view", {
      event_type: "book_view",
    })
    expect(postMock).toHaveBeenCalledWith("/public/books/book-1/analytics/view", {
      event_type: "chapter_view",
      chapter_number: 3,
    })
  })

  it("loads a forum post detail", async () => {
    await publicApi.getForumPost("post-1")

    expect(getMock).toHaveBeenCalledWith("/public/forum/posts/post-1")
  })

  it("loads the signed-in author's forum posts", async () => {
    await publicApi.listMyForumPosts()

    expect(getMock).toHaveBeenCalledWith("/public/forum/my-posts")
  })

  it("creates a public forum post", async () => {
    await publicApi.createForumPost({
      threadType: "novel",
      bookId: "book-1",
      headline: "Need mystery beta readers",
      body: "Looking for readers who can flag continuity gaps and pacing issues.",
      desiredBetaReaderCount: 4,
      allowContactRequests: true,
    })

    expect(postMock).toHaveBeenCalledWith("/public/forum/posts", {
      thread_type: "novel",
      book_id: "book-1",
      headline: "Need mystery beta readers",
      body: "Looking for readers who can flag continuity gaps and pacing issues.",
      desired_beta_reader_count: 4,
      allow_contact_requests: true,
    })
  })

  it("creates a general forum post without a book id", async () => {
    await publicApi.createForumPost({
      threadType: "general",
      headline: "How do you handle midpoint sag?",
      body: "I want practical advice on keeping the second act tense without speeding through character work.",
    })

    expect(postMock).toHaveBeenCalledWith("/public/forum/posts", {
      thread_type: "general",
      headline: "How do you handle midpoint sag?",
      body: "I want practical advice on keeping the second act tense without speeding through character work.",
      desired_beta_reader_count: null,
      allow_contact_requests: true,
    })
  })

  it("updates a public forum post", async () => {
    await publicApi.updateForumPost("post-9", {
      threadType: "novel",
      headline: "Updated headline",
      body: "Updated forum body with more detail for collaborators.",
      desiredBetaReaderCount: 6,
      allowContactRequests: false,
      status: "closed",
    })

    expect(putMock).toHaveBeenCalledWith("/public/forum/posts/post-9", {
      thread_type: "novel",
      headline: "Updated headline",
      body: "Updated forum body with more detail for collaborators.",
      desired_beta_reader_count: 6,
      allow_contact_requests: false,
      status: "closed",
    })
  })

  it("preserves backend default status when no explicit status is supplied", async () => {
    await publicApi.updateForumPost("post-10", {
      threadType: "novel",
      headline: "Keep this open",
      body: "Still looking for continuity and pacing feedback from collaborators.",
      desiredBetaReaderCount: 2,
      allowContactRequests: true,
    })

    expect(putMock).toHaveBeenCalledWith("/public/forum/posts/post-10", {
      thread_type: "novel",
      headline: "Keep this open",
      body: "Still looking for continuity and pacing feedback from collaborators.",
      desired_beta_reader_count: 2,
      allow_contact_requests: true,
    })
  })

  it("loads forum comments for a post", async () => {
    await publicApi.listForumComments("post-1")

    expect(getMock).toHaveBeenCalledWith("/public/forum/posts/post-1/comments")
  })

  it("loads forum interests for a post", async () => {
    await publicApi.listForumInterests("post-1")

    expect(getMock).toHaveBeenCalledWith("/public/forum/posts/post-1/interests")
  })

  it("creates a forum interest message", async () => {
    await publicApi.createForumInterest("post-3", "I would love to beta read this.")

    expect(postMock).toHaveBeenCalledWith("/public/forum/posts/post-3/interests", {
      message: "I would love to beta read this.",
    })
  })

  it("creates a forum comment", async () => {
    await publicApi.createForumComment("post-2", "Helpful note")

    expect(postMock).toHaveBeenCalledWith("/public/forum/posts/post-2/comments", {
      body: "Helpful note",
    })
  })

  it("reacts to a forum post", async () => {
    await publicApi.reactToForumPost("post-2", "like")

    expect(putMock).toHaveBeenCalledWith("/public/forum/posts/post-2/reaction", {
      reaction: "like",
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
