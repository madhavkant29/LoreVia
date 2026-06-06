// @vitest-environment jsdom

import { act } from "react"
import type { ReactNode } from "react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { createRoot } from "react-dom/client"
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest"

import { PublicForumPageClient } from "./PublicForumPageClient"

const pushMock = vi.hoisted(() => vi.fn())
const meMock = vi.hoisted(() => vi.fn())
const listBooksMock = vi.hoisted(() => vi.fn())
const updateForumMetadataMock = vi.hoisted(() => vi.fn())
const listRankedBetaNovelsMock = vi.hoisted(() => vi.fn())
const listMyForumPostsMock = vi.hoisted(() => vi.fn())
const createForumPostMock = vi.hoisted(() => vi.fn())

vi.mock("next/link", () => ({
  default: ({ children, href, ...props }: { children: ReactNode; href: string }) => <a href={href} {...props}>{children}</a>,
}))

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock }),
}))

vi.mock("@/lib/stores/preferencesStore", () => ({
  usePreferencesStore: () => ({ theme: "light" }),
}))

vi.mock("@/lib/billing/plans", () => ({
  canUseAuthorFeatures: () => true,
}))

vi.mock("@/lib/utils/publicForum", () => ({
  formatReputationScore: (score: number) => String(score),
  getEligibleForumAuthorBooks: () => [],
}))

vi.mock("@/lib/api/auth", () => ({
  authApi: {
    me: (...args: unknown[]) => meMock(...args),
  },
}))

vi.mock("@/lib/api/books", () => ({
  booksApi: {
    list: (...args: unknown[]) => listBooksMock(...args),
    updateForumMetadata: (...args: unknown[]) => updateForumMetadataMock(...args),
  },
}))

vi.mock("@/lib/api/public", () => ({
  publicApi: {
    listRankedBetaNovels: (...args: unknown[]) => listRankedBetaNovelsMock(...args),
    listMyForumPosts: (...args: unknown[]) => listMyForumPostsMock(...args),
    createForumPost: (...args: unknown[]) => createForumPostMock(...args),
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

describe("PublicForumPageClient", () => {
  beforeAll(() => {
    ;(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
  })

  beforeEach(() => {
    ;(window as typeof window & {
      requestIdleCallback?: (callback: IdleRequestCallback) => number
      cancelIdleCallback?: (handle: number) => void
    }).requestIdleCallback = (callback) => {
      callback({ didTimeout: false, timeRemaining: () => 0 } as IdleDeadline)
      return 1
    }
    ;(window as typeof window & {
      cancelIdleCallback?: (handle: number) => void
    }).cancelIdleCallback = () => {}
  })

  afterEach(() => {
    pushMock.mockReset()
    meMock.mockReset()
    listBooksMock.mockReset()
    updateForumMetadataMock.mockReset()
    listRankedBetaNovelsMock.mockReset()
    listMyForumPostsMock.mockReset()
    createForumPostMock.mockReset()
    document.body.innerHTML = ""
  })

  it("renders ranked beta novel badges and supporting notes", async () => {
    meMock.mockResolvedValue(null)
    listBooksMock.mockResolvedValue([])
    listMyForumPostsMock.mockResolvedValue([])
    listRankedBetaNovelsMock.mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      page_size: 20,
      has_more: false,
      ranking_key: "most_popular",
      time_window: "monthly",
      surface: "beta_novels",
    })

    const { container, unmount } = renderWithQuery(
      <PublicForumPageClient
        initialData={{
          items: [
            {
              id: "post-1",
              thread_type: "novel",
              book_id: "book-1",
              author_user_id: "user-1",
              author_username: "writer",
              author_reputation_score: 14,
              author_trust_level: "Trusted",
              title: "Sky Citadel",
              author: "A. Writer",
              genre: "Fantasy",
              description: "A ranked beta thread.",
              work_type: "novel",
              headline: "Need beta readers for Sky Citadel",
              body: "Looking for pacing and continuity feedback on a fantasy manuscript.",
              desired_beta_reader_count: 5,
              allow_contact_requests: true,
              status: "open",
              viewer_interest_status: null,
              reaction: null,
              interest_count: 3,
              comment_count: 7,
              like_count: 9,
              dislike_count: 1,
              rating_summary: {
                average_rating: 4.7,
                rating_count: 9,
                positive_rating_count: 8,
                neutral_rating_count: 1,
                negative_rating_count: 0,
              },
              discoverability_score: 88,
              ranking: {
                surface: "beta_novels",
                ranking_key: "most_popular",
                time_window: "monthly",
                position: 1,
                score: 88,
                label: "Most popular this month",
                supporting_note: "Weighted by recent reader activity, views, discussion, and interest.",
                primary_timestamp: "2026-05-20T00:00:00Z",
              },
              created_at: "2026-05-20T00:00:00Z",
              updated_at: "2026-05-21T00:00:00Z",
            },
          ],
          total: 1,
          page: 1,
          page_size: 20,
          has_more: false,
          ranking_key: "most_popular",
          time_window: "monthly",
          surface: "beta_novels",
        }}
      />,
    )

    await act(async () => {
      await Promise.resolve()
    })

    expect(container.textContent).toContain("Beta novel rankings worth opening.")
    expect(container.textContent).toContain("Most popular this month")
    expect(container.textContent).toContain("Weighted by recent reader activity, views, discussion, and interest.")
    expect(container.textContent).toContain("Need beta readers for Sky Citadel")
    expect(container.querySelector('a[href="/public"]')?.textContent).toContain("Back to public library")
    unmount()
  })

  it("requests ranked beta novels with the selected ranking window and resets paging", async () => {
    meMock.mockResolvedValue(null)
    listBooksMock.mockResolvedValue([])
    listMyForumPostsMock.mockResolvedValue([])
    listRankedBetaNovelsMock.mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      page_size: 20,
      has_more: false,
      ranking_key: "most_popular",
      time_window: "monthly",
      surface: "beta_novels",
    })

    const { container, unmount } = renderWithQuery(
      <PublicForumPageClient
        initialData={{
          items: [],
          total: 24,
          page: 2,
          page_size: 20,
          has_more: true,
          ranking_key: "most_popular",
          time_window: "monthly",
          surface: "beta_novels",
        }}
      />,
    )

    await act(async () => {
      await Promise.resolve()
    })

    const selects = container.querySelectorAll("select")
    const rankingSelect = selects[0] as HTMLSelectElement
    const windowSelect = selects[1] as HTMLSelectElement

    await act(async () => {
      rankingSelect.value = "top_rated"
      rankingSelect.dispatchEvent(new Event("change", { bubbles: true }))
      windowSelect.value = "weekly"
      windowSelect.dispatchEvent(new Event("change", { bubbles: true }))
      await Promise.resolve()
    })

    expect(listRankedBetaNovelsMock).toHaveBeenLastCalledWith({
      ranking: "top_rated",
      timeWindow: "weekly",
      query: "",
      page: 1,
      pageSize: 20,
    })
    unmount()
  })
})
