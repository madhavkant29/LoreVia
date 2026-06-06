// @vitest-environment jsdom

import { act } from "react"
import type { ReactNode } from "react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { createRoot } from "react-dom/client"
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest"

import { PublicUploadsPageClient } from "./PublicUploadsPageClient"

const listRankedCreatorUploadsMock = vi.fn()
const getUploadsAnalyticsMock = vi.fn()

vi.mock("next/link", () => ({
  default: ({ children, href, ...props }: { children: ReactNode; href: string }) => <a href={href} {...props}>{children}</a>,
}))

vi.mock("@/lib/stores/preferencesStore", () => ({
  usePreferencesStore: () => ({ theme: "light" }),
}))

vi.mock("@/lib/api/public", () => ({
  publicApi: {
    listRankedCreatorUploads: (...args: unknown[]) => listRankedCreatorUploadsMock(...args),
    getUploadsAnalytics: (...args: unknown[]) => getUploadsAnalyticsMock(...args),
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
  listRankedCreatorUploadsMock.mockReset()
  getUploadsAnalyticsMock.mockReset()
  document.body.innerHTML = ""
})

describe("PublicUploadsPageClient", () => {
  beforeAll(() => {
    ;(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
  })

  it("renders creator-only uploads and overview metrics", async () => {
    listRankedCreatorUploadsMock.mockResolvedValue({ items: [], total: 0, page: 1, limit: 24, has_more: false, ranking_key: "most_popular", time_window: "monthly", surface: "creator_uploads" })
    getUploadsAnalyticsMock.mockResolvedValue(null)

    const { container, unmount } = renderWithQuery(
      <PublicUploadsPageClient
        initialBooks={[
          {
            id: "book-1",
            title: "Ember Harbor",
            author: "A. Writer",
            author_username: "writer",
            genre: "Fantasy",
            description: "A creator upload",
            format: "manual",
            work_type: "novel",
            status: "ready",
            total_chapters: 4,
            public_slug: "ember-harbor",
            published_at: "2026-05-20T00:00:00Z",
            ranking: { surface: "creator_uploads", ranking_key: "most_popular", time_window: "monthly", position: 1, score: 90, label: "Most popular this month", supporting_note: "Weighted by recent reader activity, views, discussion, and interest.", primary_timestamp: "2026-05-20T00:00:00Z" },
          } as any,
        ]}
        initialRankingData={{
          items: [
            {
              id: "book-1",
              title: "Ember Harbor",
              author: "A. Writer",
              author_username: "writer",
              genre: "Fantasy",
              description: "A creator upload",
              format: "manual",
              work_type: "novel",
              status: "ready",
              total_chapters: 4,
              public_slug: "ember-harbor",
              published_at: "2026-05-20T00:00:00Z",
              ranking: { surface: "creator_uploads", ranking_key: "most_popular", time_window: "monthly", position: 1, score: 90, label: "Most popular this month", supporting_note: "Weighted by recent reader activity, views, discussion, and interest.", primary_timestamp: "2026-05-20T00:00:00Z" },
            } as any,
          ],
          total: 1,
          page: 1,
          limit: 24,
          has_more: false,
          ranking_key: "most_popular",
          time_window: "monthly",
          surface: "creator_uploads",
        }}
        initialOverview={{
          total_public_books: 3,
          total_authors: 2,
          total_visible_chapters: 12,
          total_visible_words: 45000,
          uploads_last_30_days: 1,
          genre_breakdown: [],
          work_type_breakdown: [],
          recent_uploads: [],
        }}
      />,
    )

    await act(async () => {
      await Promise.resolve()
    })

    expect(container.textContent).toContain("Browse creator-published books")
    expect(container.textContent).toContain("Ember Harbor")
    expect(container.textContent).toContain("Most popular this month")
    expect(container.textContent).toContain("45,000")
    expect(Array.from(container.querySelectorAll("a")).some((anchor) => anchor.getAttribute("href") === "/public/analytics")).toBe(true)
    unmount()
  })

  it("requests ranked uploads when the ranking controls change", async () => {
    listRankedCreatorUploadsMock.mockResolvedValue({ items: [], total: 0, page: 1, limit: 24, has_more: false, ranking_key: "most_popular", time_window: "monthly", surface: "creator_uploads" })
    getUploadsAnalyticsMock.mockResolvedValue(null)

    const { container, unmount } = renderWithQuery(<PublicUploadsPageClient initialBooks={[]} initialOverview={null} />)

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

    expect(listRankedCreatorUploadsMock).toHaveBeenLastCalledWith({
      ranking: "top_rated",
      timeWindow: "weekly",
      search: "",
      page: 1,
      limit: 24,
    })
    unmount()
  })
})
