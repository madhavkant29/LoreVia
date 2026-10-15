// @vitest-environment jsdom

import { act, type ReactElement, type ReactNode } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const authApiMock = vi.hoisted(() => ({
  me: vi.fn(),
}))
const publicApiMock = vi.hoisted(() => ({
  createForumComment: vi.fn(),
  createForumInterest: vi.fn(),
  getForumPost: vi.fn(),
  listForumComments: vi.fn(),
  listForumCommentsPage: vi.fn(),
  listForumInterests: vi.fn(),
  listForumInterestsPage: vi.fn(),
  reactToForumComment: vi.fn(),
  reactToForumPost: vi.fn(),
  updateForumPost: vi.fn(),
}))

vi.mock("next/link", () => ({
  default: ({ children, href, ...props }: { children: ReactNode; href: string }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}))
vi.mock("@/lib/api/auth", () => ({ authApi: authApiMock }))
vi.mock("@/lib/api/public", () => ({ publicApi: publicApiMock }))
vi.mock("@/lib/billing/plans", () => ({ canUseAuthorFeatures: (tier?: string | null) => tier === "author" || tier === "architect" }))
vi.mock("@/lib/stores/preferencesStore", () => ({ usePreferencesStore: () => ({ theme: "light" }) }))
vi.mock("@/lib/utils/assetUrls", () => ({ resolveAssetUrl: (value?: string | null) => value ?? "" }))
vi.mock("@/lib/utils/publicForum", () => ({ formatReputationScore: (value: number) => `${value} pts` }))

import { PublicForumPostPageClient } from "@/components/public/PublicForumPostPageClient"

let root: Root | null = null
let container: HTMLDivElement | null = null

const authorViewer = { id: "author-1", username: "mira", email: "mira@example.com", tier: "architect" }
const readerViewer = { id: "reader-1", username: "reader", email: "reader@example.com", tier: "reader" }

const basePost = {
  id: "post-1",
  thread_type: "novel",
  book_id: "book-1",
  author_user_id: "author-1",
  author_username: "mira",
  author_reputation_score: 42,
  author_trust_level: "trusted",
  title: "Gate Draft",
  author: "Mira Vale",
  genre: "Fantasy",
  description: "A portal mystery.",
  work_type: "novel",
  headline: "Need beta readers for the gate chapter",
  body: "The middle act needs sharper stakes.",
  image_url: "https://cdn.example/forum.png",
  image_filename: "forum.png",
  image_content_type: "image/png",
  desired_beta_reader_count: 3,
  allow_contact_requests: true,
  status: "open",
  viewer_interest_status: null,
  reaction: null,
  interest_count: 1,
  comment_count: 1,
  like_count: 4,
  dislike_count: 1,
  rating_summary: {
    average_rating: 4.2,
    rating_count: 5,
    positive_rating_count: 4,
    neutral_rating_count: 1,
    negative_rating_count: 0,
  },
  discoverability_score: 87,
  ranking: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
}

const baseComment = {
  id: "comment-1",
  post_id: "post-1",
  book_id: "book-1",
  parent_comment_id: null,
  author_user_id: "reader-1",
  author_username: "reader",
  author_reputation_score: 7,
  author_trust_level: "new",
  body: "The gate reveal worked.",
  image_url: null,
  image_filename: null,
  image_content_type: null,
  like_count: 2,
  dislike_count: 0,
  reaction: null,
  can_edit: false,
  replies: [
    {
      id: "reply-1",
      post_id: "post-1",
      book_id: "book-1",
      parent_comment_id: "comment-1",
      author_user_id: "author-1",
      author_username: "mira",
      author_reputation_score: 42,
      author_trust_level: "trusted",
      body: "That is helpful.",
      image_url: null,
      image_filename: null,
      image_content_type: null,
      like_count: 1,
      dislike_count: 0,
      reaction: null,
      can_edit: true,
      replies: [],
      created_at: "2026-01-01T01:00:00Z",
      updated_at: "2026-01-01T01:00:00Z",
    },
  ],
  created_at: "2026-01-01T00:30:00Z",
  updated_at: "2026-01-01T00:30:00Z",
}

async function renderClient(element: ReactElement) {
  container = document.createElement("div")
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => {
    root?.render(element)
    await flush()
  })
}

async function flush() {
  await Promise.resolve()
  await new Promise((resolve) => window.setTimeout(resolve, 0))
  await Promise.resolve()
}

async function waitForText(expected: string) {
  for (let index = 0; index < 50; index += 1) {
    if ((container?.textContent ?? "").includes(expected)) return
    await act(flush)
  }
  throw new Error(`Missing text: ${expected}\n${container?.textContent ?? ""}`)
}

function setFieldValue(field: HTMLInputElement | HTMLTextAreaElement, value: string) {
  const prototype = field instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype
  const setter = Object.getOwnPropertyDescriptor(prototype, "value")?.set
  setter?.call(field, value)
  field.dispatchEvent(new Event("input", { bubbles: true }))
}

function button(label: string, index = 0) {
  const matches = Array.from(container?.querySelectorAll("button") ?? []).filter((item) =>
    item.textContent?.includes(label)
  )
  const match = matches[index]
  if (!match) throw new Error(`Missing button: ${label}`)
  return match
}

function clickElement(element: Element) {
  element.dispatchEvent(new MouseEvent("click", { bubbles: true }))
}

async function click(label: string, index = 0) {
  await act(async () => {
    clickElement(button(label, index))
    await flush()
  })
}

beforeEach(() => {
  vi.setSystemTime(new Date("2026-01-02T00:00:00Z"))
  window.requestIdleCallback = ((callback: IdleRequestCallback) => {
    window.setTimeout(() => callback({ didTimeout: false, timeRemaining: () => 50 } as IdleDeadline), 0)
    return 1
  }) as typeof window.requestIdleCallback
  window.cancelIdleCallback = vi.fn()
  authApiMock.me.mockResolvedValue(readerViewer)
  publicApiMock.getForumPost.mockResolvedValue(basePost)
  publicApiMock.listForumComments.mockResolvedValue([baseComment])
  publicApiMock.listForumCommentsPage.mockResolvedValue({
    items: [baseComment],
    next_cursor: null,
    has_more: false,
  })
  publicApiMock.listForumInterests.mockResolvedValue([
    {
      id: "interest-1",
      post_id: "post-1",
      book_id: "book-1",
      author_user_id: "author-1",
      interested_user_id: "reader-1",
      interested_username: "reader",
      interested_email: "reader@example.com",
      message: "I can beta read this week.",
      status: "pending",
      created_at: "2026-01-01T02:00:00Z",
      updated_at: "2026-01-01T02:00:00Z",
    },
  ])
  publicApiMock.listForumInterestsPage.mockResolvedValue({
    items: [{
      id: "interest-1",
      post_id: "post-1",
      book_id: "book-1",
      author_user_id: "author-1",
      interested_user_id: "reader-1",
      interested_username: "reader",
      interested_email: "reader@example.com",
      message: "I can beta read this week.",
      status: "pending",
      created_at: "2026-01-01T02:00:00Z",
      updated_at: "2026-01-01T02:00:00Z",
    }],
    next_cursor: null,
    has_more: false,
  })
  publicApiMock.createForumComment.mockImplementation(async (_postId, body, parentCommentId) => ({
    ...baseComment,
    id: parentCommentId ? "reply-new" : "comment-new",
    parent_comment_id: parentCommentId ?? null,
    body,
    replies: [],
  }))
  publicApiMock.reactToForumComment.mockResolvedValue({ ...baseComment, like_count: 3, reaction: "like" })
  publicApiMock.reactToForumPost.mockResolvedValue({ ...basePost, like_count: 5, reaction: "like" })
  publicApiMock.createForumInterest.mockResolvedValue({
    id: "interest-new",
    post_id: "post-1",
    book_id: "book-1",
    author_user_id: "author-1",
    interested_user_id: "reader-1",
    interested_username: "reader",
    interested_email: "reader@example.com",
    message: "I can read it.",
    status: "pending",
    created_at: "2026-01-01T03:00:00Z",
    updated_at: "2026-01-01T03:00:00Z",
  })
  publicApiMock.updateForumPost.mockImplementation(async (_postId, payload) => ({
    ...basePost,
    headline: payload.headline,
    body: payload.body,
    status: payload.status,
    desired_beta_reader_count: payload.desiredBetaReaderCount,
    allow_contact_requests: payload.allowContactRequests,
  }))
})

afterEach(() => {
  if (root) {
    act(() => {
      root?.unmount()
    })
  }
  root = null
  container?.remove()
  container = null
  document.body.innerHTML = ""
  vi.useRealTimers()
  vi.clearAllMocks()
})

describe("PublicForumPostPageClient", () => {
  it("renders author controls, interest notes, editing, reply, and comment reactions", async () => {
    authApiMock.me.mockResolvedValue(authorViewer)
    await renderClient(<PublicForumPostPageClient postId="post-1" initialPost={basePost} initialComments={[baseComment]} />)
    await waitForText("Reader interest")
    await waitForText("I can beta read this week.")
    expect(container?.querySelector("[data-testid='forum-comment-thread']")).not.toBeNull()
    expect(container?.querySelector("[data-testid='forum-comment-thread']")?.className).not.toContain("rounded-lg")

    await click("Edit discussion")
    setFieldValue(container?.querySelector("[aria-label='Discussion headline']") as HTMLInputElement, "Sharper gate chapter")
    setFieldValue(container?.querySelector("[aria-label='Discussion body']") as HTMLTextAreaElement, "Please test the reveal.")
    setFieldValue(container?.querySelector("[aria-label='Desired beta readers']") as HTMLInputElement, "4")
    await click("Save discussion")
    expect(publicApiMock.updateForumPost).toHaveBeenCalledWith("post-1", expect.objectContaining({
      headline: "Sharper gate chapter",
      body: "Please test the reveal.",
      desiredBetaReaderCount: 4,
    }))

    await click("Reply")
    setFieldValue(container?.querySelector("[aria-label='Reply to @reader']") as HTMLTextAreaElement, "I will clarify that beat.")
    await click("Post reply")
    expect(publicApiMock.createForumComment).toHaveBeenCalledWith("post-1", "I will clarify that beat.", "comment-1", null)

    await click("2", 0)
    expect(publicApiMock.reactToForumComment).toHaveBeenCalledWith("comment-1", "like")

    await click("Close discussion")
    expect(publicApiMock.updateForumPost).toHaveBeenCalledWith("post-1", expect.objectContaining({ status: "closed" }))
  })

  it("renders reader controls and submits post reactions, comments, and collaborator notes", async () => {
    authApiMock.me.mockResolvedValue(readerViewer)
    await renderClient(<PublicForumPostPageClient postId="post-1" initialPost={basePost} initialComments={[]} />)
    await waitForText("Offer to beta read")
    await waitForText("Signed in as @reader")

    await act(async () => {
      clickElement(container?.querySelector("article button") as HTMLButtonElement)
      await flush()
    })
    expect(publicApiMock.reactToForumPost).toHaveBeenCalledWith("post-1", "like")

    setFieldValue(container?.querySelector("[aria-label='Public comment']") as HTMLTextAreaElement, "The premise is clear.")
    await click("Post comment")
    expect(publicApiMock.createForumComment).toHaveBeenCalledWith("post-1", "The premise is clear.", null, null)

    setFieldValue(container?.querySelector("[aria-label='Collaborator note']") as HTMLTextAreaElement, "I can read this weekend.")
    await click("Send collaborator note")
    expect(publicApiMock.createForumInterest).toHaveBeenCalledWith("post-1", "I can read this weekend.")
    await waitForText("Your collaborator interest note was sent to the author.")
  })

  it("loads subsequent comment and author-interest cursor pages", async () => {
    const nextComment = {
      ...baseComment,
      id: "comment-2",
      body: "The second page is visible.",
      replies: [],
      created_at: "2026-01-01T03:00:00Z",
      updated_at: "2026-01-01T03:00:00Z",
    }
    publicApiMock.listForumCommentsPage.mockResolvedValueOnce({
      items: [nextComment],
      next_cursor: null,
      has_more: false,
    })
    publicApiMock.listForumInterestsPage.mockResolvedValue({
      items: [{
        id: "interest-1",
        post_id: "post-1",
        book_id: "book-1",
        author_user_id: "author-1",
        interested_user_id: "reader-1",
        interested_username: "reader",
        interested_email: "reader@example.com",
        message: "I can beta read this week.",
        status: "pending",
        created_at: "2026-01-01T02:00:00Z",
        updated_at: "2026-01-01T02:00:00Z",
      }],
      next_cursor: "interest-page-2",
      has_more: true,
    })
    authApiMock.me.mockResolvedValue(authorViewer)

    await renderClient(
      <PublicForumPostPageClient
        postId="post-1"
        initialPost={basePost}
        initialComments={[baseComment]}
        initialCommentCursor="comment-page-2"
      />,
    )
    await waitForText("Load more comments")
    await click("Load more comments")
    await waitForText("The second page is visible.")
    expect(publicApiMock.listForumCommentsPage).toHaveBeenCalledWith(
      "post-1",
      "comment-page-2",
    )

    await waitForText("Load more requests")
    publicApiMock.listForumInterestsPage.mockResolvedValueOnce({
        items: [{
          id: "interest-2",
          post_id: "post-1",
          book_id: "book-1",
          author_user_id: "author-1",
          interested_user_id: "reader-2",
          interested_username: "second-reader",
          interested_email: "second@example.com",
          message: "I can review the full draft.",
          status: "pending",
          created_at: "2026-01-01T04:00:00Z",
          updated_at: "2026-01-01T04:00:00Z",
        }],
        next_cursor: null,
        has_more: false,
      })
    await click("Load more requests")
    await waitForText("I can review the full draft.")
    expect(publicApiMock.listForumInterestsPage).toHaveBeenCalledWith(
      "post-1",
      "interest-page-2",
    )
  })

  it("shows the load failure state when no initial shell is available", async () => {
    publicApiMock.getForumPost.mockRejectedValueOnce(new Error("missing"))
    await renderClient(<PublicForumPostPageClient postId="missing" />)
    await waitForText("Could not load this surfaced discussion.")
  })
})
