// @vitest-environment jsdom

import React from "react"
import { act } from "react"
import type { ReactNode } from "react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { createRoot } from "react-dom/client"
import { afterEach, describe, expect, it, vi } from "vitest"

import { PublicBookPageClient } from "./PublicBookPageClient"
import { PublicUploadsAnalyticsPageClient } from "./PublicUploadsAnalyticsPageClient"
import { PublicWriterProfilePageClient } from "./PublicWriterProfilePageClient"

const trackViewMock = vi.fn()
const getBookMock = vi.fn()
const getUserProfileMock = vi.fn()
const createContentReportMock = vi.fn()

vi.mock("next/link", () => ({
  default: ({ children, href, ...props }: { children: ReactNode; href: string }) => <a href={href} {...props}>{children}</a>,
}))

vi.mock("@/lib/stores/preferencesStore", () => ({
  usePreferencesStore: () => ({ theme: "light" }),
}))

vi.mock("@/lib/api/public", () => ({
  publicApi: {
    getBook: (...args: unknown[]) => getBookMock(...args),
    getUserProfile: (...args: unknown[]) => getUserProfileMock(...args),
    createContentReport: (...args: unknown[]) => createContentReportMock(...args),
    trackView: (...args: unknown[]) => trackViewMock(...args),
  },
}))

function renderWithQuery(ui: React.ReactNode) {
  const container = document.createElement("div")
  document.body.appendChild(container)
  const root = createRoot(container)
  const queryClient = new QueryClient()
  act(() => {
    root.render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>)
  })
  return {
    container,
    unmount: () => {
      act(() => {
        root.unmount()
      })
      queryClient.clear()
      container.remove()
    },
  }
}

afterEach(() => {
  trackViewMock.mockReset()
  getBookMock.mockReset()
  getUserProfileMock.mockReset()
  createContentReportMock.mockReset()
  document.body.innerHTML = ""
})

describe("public analytics surfaces", () => {
  it("renders public book analytics and tracks a book view", async () => {
    const initialBook = {
      id: "book-1",
      public_slug: "book-1",
      title: "Public Sample",
      author: "A. Writer",
      author_username: "writer",
      creator_display_name: "writer",
      genre: "Fantasy",
      description: "A visible sample.",
      format: "manual",
      work_type: "novel",
      status: "ready",
      total_chapters: 3,
      chapters: [{ number: 1, title: "One", description: null }],
      analytics: {
        book_view_count: 12,
        unique_reader_count_30d: 5,
        chapter_view_count: 18,
        published_at: null,
        chapter_count: 3,
        total_words: 1200,
        has_open_discussion: false,
        open_discussion_count: 0,
        discussion_comment_count: 0,
        discussion_interest_count: 0,
      },
    }
    getBookMock.mockResolvedValue(initialBook)

    const { container, unmount } = renderWithQuery(<PublicBookPageClient bookId="book-1" initialBook={initialBook as any} />)
    await act(async () => {
      await Promise.resolve()
    })

    expect(container.textContent).toContain("12")
    expect(container.textContent).toContain("5")
    expect(container.textContent).toContain("18")
    expect(container.querySelector('a[href="/public"]')?.textContent).toContain("Back to public library")
    expect(trackViewMock).toHaveBeenCalledWith("book-1", { eventType: "book_view" })
    unmount()
  })

  it("renders public writer analytics rollups", async () => {
    const initialProfile = {
      user_id: "user-1",
      username: "writer",
      reputation_score: 14,
      reputation_likes_received: 4,
      reputation_dislikes_received: 1,
      trust_level: "Trusted",
      forum_post_count: 2,
      forum_comment_count: 3,
      current_project: null,
      public_books_count: 1,
      public_books: [
        {
          id: "book-1",
          title: "Public Sample",
          author: "A. Writer",
          author_username: "writer",
          genre: "Fantasy",
          description: "Visible sample",
          format: "manual",
          work_type: "novel",
          status: "ready",
          total_chapters: 3,
          public_slug: "public-sample",
          analytics: { book_view_count: 42 },
        },
      ],
      public_analytics: {
        total_book_views: 42,
        total_unique_readers_30d: 9,
        total_chapter_views: 84,
        total_public_books: 1,
        total_chapters: 3,
        total_words: 1200,
        latest_published_at: null,
        open_forum_discussions_count: 0,
      },
      posts: [],
      comments: [],
      created_at: "2026-05-20T00:00:00Z",
    }
    getUserProfileMock.mockResolvedValue(initialProfile)

    const { container, unmount } = renderWithQuery(<PublicWriterProfilePageClient username="writer" initialProfile={initialProfile as any} />)
    await act(async () => {
      await Promise.resolve()
    })

    expect(container.textContent).toContain("42")
    expect(container.textContent).toContain("9")
    expect(container.textContent).toContain("1.2k words")
    expect(container.textContent).toContain("Published books")
    expect(container.textContent).toContain("Public Sample")
    expect(container.querySelector('a[href="/public"]')?.textContent).toContain("Back to public library")
    unmount()
  })

  it("renders the writer layout with empty states when the profile has no public activity yet", async () => {
    getUserProfileMock.mockRejectedValue(new Error("Not Found"))

    const { container, unmount } = renderWithQuery(<PublicWriterProfilePageClient username="mell" initialProfile={null} />)
    await act(async () => {
      await Promise.resolve()
    })
    await act(async () => {
      await Promise.resolve()
    })

    expect(container.textContent).toContain("@mell")
    expect(container.textContent).toContain("0 visible uploads")
    expect(container.textContent).toContain("No public posts are visible for this writer yet.")
    expect(container.textContent).toContain("This writer has not surfaced any visible creator-published public books yet.")
    expect(container.textContent).not.toContain("Could not load this writer profile.")
    unmount()
  })

  it("renders useful empty states when public upload analytics are unavailable", () => {
    const { container, unmount } = renderWithQuery(
      <PublicUploadsAnalyticsPageClient
        overview={{
          total_public_books: 0,
          total_authors: 0,
          total_visible_chapters: 0,
          total_visible_words: 0,
          uploads_last_30_days: 0,
          genre_breakdown: [],
          work_type_breakdown: [],
          recent_uploads: [],
        }}
      />,
    )

    expect(container.textContent).toContain("Genre metrics will appear")
    expect(container.textContent).toContain("Work type metrics will appear")
    expect(container.textContent).toContain("Recent creator uploads will appear")
    unmount()
  })
})
