// @vitest-environment jsdom

import { act } from "react"
import type { ReactNode } from "react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { createRoot } from "react-dom/client"
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest"
import type { Book } from "@/types/book"
import type { PublicForumPost } from "@/types/public"

import { PublicForumPageClient } from "./PublicForumPageClient"

const pushMock = vi.hoisted(() => vi.fn())
const meMock = vi.hoisted(() => vi.fn())
const listBooksMock = vi.hoisted(() => vi.fn())
const updateForumMetadataMock = vi.hoisted(() => vi.fn())
const listRankedBetaNovelsMock = vi.hoisted(() => vi.fn())
const listForumPostsMock = vi.hoisted(() => vi.fn())
const listMyForumPostsMock = vi.hoisted(() => vi.fn())
const createForumPostMock = vi.hoisted(() => vi.fn())
const eligibleBooksMock = vi.hoisted(() => vi.fn((_books: Book[], _posts: PublicForumPost[]) => [] as Book[]))

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
  getEligibleForumAuthorBooks: (books: Book[], posts: PublicForumPost[]) => eligibleBooksMock(books, posts),
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
    listForumPosts: (...args: unknown[]) => listForumPostsMock(...args),
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
    listForumPostsMock.mockReset()
    listMyForumPostsMock.mockReset()
    createForumPostMock.mockReset()
    eligibleBooksMock.mockReset().mockReturnValue([])
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

  it("switches to the general feed and renders general discussion results", async () => {
    meMock.mockResolvedValue(null)
    listRankedBetaNovelsMock.mockResolvedValue(emptyFeed("most_popular", "monthly"))
    listForumPostsMock.mockResolvedValue({
      ...emptyFeed("most_popular", "monthly"),
      items: [buildForumPost({ id: "general-1", thread_type: "general", headline: "How do you revise openings?", allow_contact_requests: false })],
      total: 1,
    })
    const { container, unmount } = renderWithQuery(<PublicForumPageClient initialData={emptyFeed("most_popular", "monthly")} />)
    await flushUi()

    await clickButton(container, "General")
    await flushUi()
    expect(listForumPostsMock).toHaveBeenCalledWith(undefined, 1, 20, "general")
    expect(container.textContent).toContain("General writing discussions.")
    expect(container.textContent).toContain("How do you revise openings?")
    expect(container.textContent).toContain("General threads are for broader craft and community discussion.")
    unmount()
  })

  it("loads signed-in viewer context, validates, and creates a general thread", async () => {
    meMock.mockResolvedValue({ id: "user-1", username: "mira", tier: "author" })
    listBooksMock.mockResolvedValue([{ id: "book-1", title: "Atlas", mode: "author" }])
    listMyForumPostsMock.mockResolvedValue([])
    eligibleBooksMock.mockReturnValue([{ id: "book-1", title: "Atlas", genre: "Fantasy", public_description: "A gate story." }] as unknown as Book[])
    listRankedBetaNovelsMock.mockResolvedValue(emptyFeed("most_popular", "monthly"))
    listForumPostsMock.mockResolvedValue(emptyFeed("most_popular", "monthly"))
    createForumPostMock.mockResolvedValue({ id: "created-general" })
    const { container, unmount } = renderWithQuery(<PublicForumPageClient initialData={emptyFeed("most_popular", "monthly")} />)
    await flushUi()
    await flushUi()
    expect(container.textContent).toContain("Open a new thread")
    expect(container.textContent).toContain("@mira")

    await clickButton(container, "General discussion")
    await clickButton(container, "Open general thread")
    expect(container.textContent).toContain("Add a headline and body")

    const headline = container.querySelector('[aria-label="General discussion headline"]') as HTMLInputElement
    const body = container.querySelector('[aria-label="Discussion body"]') as HTMLTextAreaElement
    await act(async () => {
      setFieldValue(headline, "Opening chapters")
      setFieldValue(body, "How do you decide whether an opening chapter starts too slowly?")
      await Promise.resolve()
    })
    await clickButton(container, "Open general thread")
    await flushUi()
    expect(createForumPostMock).toHaveBeenCalledWith(expect.objectContaining({
      threadType: "general",
      bookId: null,
      headline: "Opening chapters",
      allowContactRequests: false,
    }))
    expect(pushMock).toHaveBeenCalledWith("/public/forum/created-general")
    unmount()
  })
})

function emptyFeed(rankingKey: string, timeWindow: string) {
  return { items: [], total: 0, page: 1, page_size: 20, has_more: false, ranking_key: rankingKey, time_window: timeWindow, surface: "beta_novels" }
}

function buildForumPost(overrides: Record<string, unknown> = {}) {
  return {
    id: "post-1", thread_type: "novel", book_id: "book-1", author_user_id: "user-1", author_username: "writer",
    author_reputation_score: 14, author_trust_level: "Trusted", title: "Atlas", author: "A. Writer", genre: "Fantasy",
    description: "A ranked thread.", work_type: "novel", headline: "Need readers", body: "A sufficiently detailed forum body.",
    desired_beta_reader_count: 3, allow_contact_requests: true, status: "open", viewer_interest_status: null, reaction: null,
    interest_count: 2, comment_count: 4, like_count: 5, dislike_count: 1,
    rating_summary: { average_rating: 4.2, rating_count: 5, positive_rating_count: 4, neutral_rating_count: 1, negative_rating_count: 0 },
    discoverability_score: 80, ranking: null, created_at: new Date().toISOString(), updated_at: new Date().toISOString(),
    ...overrides,
  }
}

async function flushUi() {
  await act(async () => {
    await Promise.resolve()
    await Promise.resolve()
    await new Promise((resolve) => setTimeout(resolve, 0))
  })
}

async function clickButton(container: HTMLElement, label: string) {
  const button = Array.from(container.querySelectorAll("button")).find((item) => item.textContent?.trim() === label)
  expect(button, `button ${label}`).toBeTruthy()
  await act(async () => {
    button?.dispatchEvent(new MouseEvent("click", { bubbles: true }))
    await Promise.resolve()
  })
}

function setFieldValue(field: HTMLInputElement | HTMLTextAreaElement, value: string) {
  const prototype = field instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype
  Object.getOwnPropertyDescriptor(prototype, "value")?.set?.call(field, value)
  field.dispatchEvent(new Event("input", { bubbles: true }))
}
