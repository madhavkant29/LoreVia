// @vitest-environment jsdom

import { act } from "react"
import type { ReactNode } from "react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { createRoot } from "react-dom/client"
import { afterEach, describe, expect, it, vi } from "vitest"

import { PublicUploadsPageClient } from "./PublicUploadsPageClient"

const listCreatorUploadsMock = vi.fn()
const getUploadsAnalyticsMock = vi.fn()

vi.mock("next/link", () => ({
  default: ({ children, href, ...props }: { children: ReactNode; href: string }) => <a href={href} {...props}>{children}</a>,
}))

vi.mock("@/lib/stores/preferencesStore", () => ({
  usePreferencesStore: () => ({ theme: "light" }),
}))

vi.mock("@/lib/api/public", () => ({
  publicApi: {
    listCreatorUploads: (...args: unknown[]) => listCreatorUploadsMock(...args),
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
      container.remove()
    },
  }
}

afterEach(() => {
  listCreatorUploadsMock.mockReset()
  getUploadsAnalyticsMock.mockReset()
  document.body.innerHTML = ""
})

describe("PublicUploadsPageClient", () => {
  it("renders creator-only uploads and overview metrics", async () => {
    listCreatorUploadsMock.mockResolvedValue([])
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
          } as any,
        ]}
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
    expect(container.textContent).toContain("45,000")
    expect(Array.from(container.querySelectorAll("a")).some((anchor) => anchor.getAttribute("href") === "/public/analytics")).toBe(true)
    unmount()
  })
})
