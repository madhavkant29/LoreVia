// @vitest-environment jsdom

import React, { act, type ReactElement } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const serverMock = vi.hoisted(() => ({
  listBooks: vi.fn(),
  listBooksPage: vi.fn(),
  getBook: vi.fn(),
  getProfile: vi.fn(),
  listNovels: vi.fn(),
  getPost: vi.fn(),
  listComments: vi.fn(),
  listCommentsPage: vi.fn(),
  listUploads: vi.fn(),
  getAnalytics: vi.fn(),
}))

vi.mock("next/dynamic", () => ({
  default: () => function DynamicPublicClient(props: Record<string, unknown>) {
    return <div data-testid="dynamic-public-client">Dynamic public client {JSON.stringify(Object.keys(props).sort())}</div>
  },
}))
vi.mock("@/components/seo/JsonLdScript", () => ({ JsonLdScript: ({ id }: { id: string }) => <script data-testid={id} /> }))
vi.mock("@/components/public/PublicBookPageClient", () => ({ PublicBookPageClient: (props: { bookId: string; initialBook: unknown }) => <div>Book client {props.bookId} {props.initialBook ? "loaded" : "empty"}</div> }))
vi.mock("@/components/public/PublicUploadsAnalyticsPageClient", () => ({ PublicUploadsAnalyticsPageClient: ({ overview }: { overview: { total_public_books: number } }) => <div>Analytics books {overview.total_public_books}</div> }))
vi.mock("@/lib/api/public.server", () => ({
  listPublicBooksServer: serverMock.listBooks,
  listPublicBooksPageServer: serverMock.listBooksPage,
  getPublicBookServer: serverMock.getBook,
  getPublicUserProfileServer: serverMock.getProfile,
  listRankedBetaNovelsServer: serverMock.listNovels,
  getPublicForumPostServer: serverMock.getPost,
  listPublicForumCommentsServer: serverMock.listComments,
  listPublicForumCommentsPageServer: serverMock.listCommentsPage,
  listRankedCreatorPublicUploadsServer: serverMock.listUploads,
  getPublicUploadsAnalyticsServer: serverMock.getAnalytics,
}))

import PublicLibraryPage, { metadata as libraryMetadata } from "./public/page"
import PublicBookPage, { generateMetadata as generateBookMetadata } from "./public/[bookId]/page"
import PublicWriterProfilePage, { generateMetadata as generateWriterMetadata } from "./public/writers/[username]/page"
import PublicForumPage, { metadata as forumMetadata } from "./public/forum/page"
import PublicForumPostPage, { generateMetadata as generatePostMetadata } from "./public/forum/[postId]/page"
import PublicUploadsPage, { metadata as uploadsMetadata } from "./public/uploads/page"
import PublicUploadsAnalyticsPage, { metadata as analyticsMetadata } from "./public/analytics/page"

let root: Root | null = null
let container: HTMLDivElement | null = null

beforeEach(() => {
  vi.stubEnv("NODE_ENV", "production")
  serverMock.listBooks.mockReset().mockResolvedValue([{ id: "book-1", public_slug: "gate", title: "Gate Draft" }])
  serverMock.listBooksPage.mockReset().mockResolvedValue({ items: [{ id: "book-1", public_slug: "gate", title: "Gate Draft" }], next_cursor: null, has_more: false })
  serverMock.getBook.mockReset().mockResolvedValue({ id: "book-1", public_slug: "gate", title: "Gate Draft", author: "Mara", creator_display_name: "Mara", description: null, genre: "Fantasy", total_chapters: 8 })
  serverMock.getProfile.mockReset().mockResolvedValue({ username: "mara" })
  serverMock.listNovels.mockReset().mockResolvedValue({ items: [{ id: "post-1", headline: "Read my gate draft" }] })
  serverMock.getPost.mockReset().mockResolvedValue({ id: "post-1", headline: "Read my gate draft", body: "A".repeat(220), created_at: "2026-01-01", updated_at: "2026-01-02", author_username: "mara" })
  serverMock.listComments.mockReset().mockResolvedValue([{ id: "comment-1" }])
  serverMock.listCommentsPage.mockReset().mockResolvedValue({
    items: [{ id: "comment-1" }],
    next_cursor: null,
    has_more: false,
  })
  serverMock.listUploads.mockReset().mockResolvedValue({ items: [{ id: "book-1" }], total: 1, page: 1, limit: 24, has_more: false, ranking_key: "most_popular", time_window: "monthly", surface: "creator_uploads" })
  serverMock.getAnalytics.mockReset().mockResolvedValue({ total_public_books: 1, total_authors: 1, total_visible_chapters: 8, total_visible_words: 1000, uploads_last_30_days: 1, genre_breakdown: [], work_type_breakdown: [], recent_uploads: [] })
})

afterEach(() => {
  if (root) act(() => root?.unmount())
  container?.remove()
  root = null
  container = null
  vi.unstubAllEnvs()
})

describe("public server page wrappers", () => {
  it("renders the public library, forum, uploads, and analytics pages with server data", async () => {
    expect(libraryMetadata.title).toBe("Public Library")
    await render(await PublicLibraryPage())
    expect(container?.textContent).toContain("Dynamic public client")
    expect(container?.querySelectorAll("script")).toHaveLength(2)

    await rerender(await PublicForumPage())
    expect(forumMetadata.title).toBe("Public Forum")
    expect(container?.querySelectorAll("script")).toHaveLength(2)

    await rerender(await PublicUploadsPage())
    expect(uploadsMetadata.title).toBe("Creator Public Uploads")
    expect(serverMock.listUploads).toHaveBeenCalled()

    await rerender(await PublicUploadsAnalyticsPage())
    expect(analyticsMetadata.title).toBe("Public Upload Analytics")
    expect(container?.textContent).toContain("Analytics books 1")
  })

  it("builds book, writer, and forum-post metadata plus structured page data", async () => {
    const bookMetadata = await generateBookMetadata({ params: Promise.resolve({ bookId: "gate" }) })
    expect(bookMetadata.title).toBe("Gate Draft")
    await render(await PublicBookPage({ params: Promise.resolve({ bookId: "gate" }) }))
    expect(container?.textContent).toContain("Book client book-1 loaded")
    expect(container?.querySelectorAll("script")).toHaveLength(2)

    const writerMetadata = await generateWriterMetadata({ params: Promise.resolve({ username: "mara" }) })
    expect(writerMetadata.title).toBe("@mara")
    await rerender(await PublicWriterProfilePage({ params: Promise.resolve({ username: "mara" }) }))
    expect(container?.querySelectorAll("script")).toHaveLength(1)

    const postMetadata = await generatePostMetadata({ params: Promise.resolve({ postId: "post-1" }) })
    expect(String(postMetadata.description)).toHaveLength(180)
    await rerender(await PublicForumPostPage({ params: Promise.resolve({ postId: "post-1" }) }))
    expect(container?.querySelectorAll("script")).toHaveLength(2)
  })

  it("returns empty metadata and fallback page payloads when public APIs fail", async () => {
    serverMock.getBook.mockRejectedValue(new Error("missing"))
    serverMock.getProfile.mockRejectedValue(new Error("missing"))
    serverMock.getPost.mockRejectedValue(new Error("missing"))
    serverMock.listComments.mockRejectedValue(new Error("missing"))
    serverMock.listCommentsPage.mockRejectedValue(new Error("missing"))
    serverMock.listUploads.mockRejectedValue(new Error("offline"))
    serverMock.getAnalytics.mockRejectedValue(new Error("offline"))

    expect(await generateBookMetadata({ params: Promise.resolve({ bookId: "missing" }) })).toEqual({})
    expect(await generateWriterMetadata({ params: Promise.resolve({ username: "missing" }) })).toEqual({})
    expect(await generatePostMetadata({ params: Promise.resolve({ postId: "missing" }) })).toEqual({})
    await render(await PublicBookPage({ params: Promise.resolve({ bookId: "missing" }) }))
    expect(container?.textContent).toContain("Book client missing empty")
    await rerender(await PublicForumPostPage({ params: Promise.resolve({ postId: "missing" }) }))
    expect(container?.querySelectorAll("script")).toHaveLength(0)
    await rerender(await PublicUploadsPage())
    await rerender(await PublicUploadsAnalyticsPage())
    expect(container?.textContent).toContain("Analytics books 0")
  })
})

async function render(element: ReactElement) {
  container = document.createElement("div")
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => {
    root?.render(element)
    await Promise.resolve()
  })
}

async function rerender(element: ReactElement) {
  if (!root) throw new Error("Root not initialized")
  await act(async () => {
    root?.render(element)
    await Promise.resolve()
  })
}
