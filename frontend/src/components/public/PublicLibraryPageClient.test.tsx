// @vitest-environment jsdom

import { act, type ReactElement, type ReactNode } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const { listBooksMock, queryState, themeState, useQueryMock } = vi.hoisted(() => ({
  listBooksMock: vi.fn(),
  queryState: { data: undefined as unknown, isLoading: false },
  themeState: { theme: "light" },
  useQueryMock: vi.fn(),
}))

vi.mock("next/link", () => ({
  default: ({ children, href, ...props }: { children: ReactNode; href: string }) => <a href={href} {...props}>{children}</a>,
}))
vi.mock("@tanstack/react-query", () => ({ useQuery: useQueryMock }))
vi.mock("@/lib/api/public", () => ({ publicApi: { listBooks: listBooksMock } }))
vi.mock("@/lib/stores/preferencesStore", () => ({ usePreferencesStore: () => themeState }))

import { PublicLibraryPageClient } from "./PublicLibraryPageClient"

let root: Root | null = null
let container: HTMLDivElement | null = null

async function renderElement(element: ReactElement) {
  container = document.createElement("div")
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => {
    root?.render(element)
    await Promise.resolve()
  })
  return container
}

describe("PublicLibraryPageClient", () => {
  beforeEach(() => {
    listBooksMock.mockReset().mockResolvedValue([])
    useQueryMock.mockReset().mockImplementation(() => queryState)
    queryState.data = undefined
    queryState.isLoading = false
    themeState.theme = "light"
  })

  afterEach(async () => {
    await act(async () => root?.unmount())
    container?.remove()
    root = null
    container = null
  })

  it("renders creator and public-domain books with their available actions", async () => {
    themeState.theme = "dark"
    queryState.data = [
      { id: "book-1", title: "Atlas Rising", author_username: "nora", content_source_type: "creator_original", genre: "Fantasy", description: "A gate opens at dawn.", total_chapters: 12, status: "ready", public_slug: "atlas-rising", active_forum_post_id: "post-1", analytics: { book_view_count: 1234 } },
      { id: "book-2", title: "The Old Voyage", author: "A. Sailor", content_source_type: "public_domain", genre: null, description: null, total_chapters: null, status: "ready", public_slug: null, active_forum_post_id: null, analytics: null },
    ]

    const view = await renderElement(<PublicLibraryPageClient />)
    expect(view.textContent).toContain("Published work for focused reading.")
    expect(view.textContent).toContain("Creator-published original / Fantasy")
    expect(view.textContent).toContain("Public-domain demo")
    expect(view.textContent).toContain("by A. Sailor")
    expect(view.textContent).toContain("1,234 views")
    expect(view.textContent).toContain("? chapters")
    expect(view.querySelector('a[href="/public/writers/nora"]')?.textContent).toBe("@nora")
    expect(view.querySelector('a[href="/public/atlas-rising"]')).not.toBeNull()
    expect(view.querySelector('a[href="/public/book-2"]')).not.toBeNull()
    expect(view.querySelector('a[href="/public/forum/post-1"]')?.textContent).toContain("Discussion")
    expect(view.querySelector("main")?.className).toContain("bg-[#0a0f14]")

    await useQueryMock.mock.calls[0][0].queryFn()
    expect(listBooksMock).toHaveBeenCalledOnce()
  })

  it("renders loading state and supplies initial books to React Query", async () => {
    queryState.isLoading = true
    const view = await renderElement(<PublicLibraryPageClient initialBooks={[{ id: "seed" }] as never} />)
    expect(view.textContent).toContain("Loading public books...")
    expect(useQueryMock.mock.calls[0][0]).toEqual(expect.objectContaining({
      queryKey: ["public:books"], staleTime: 60_000, initialData: [{ id: "seed" }],
    }))
  })

  it("renders the empty public library state", async () => {
    queryState.data = []
    const view = await renderElement(<PublicLibraryPageClient />)
    expect(view.textContent).toContain("No public showcase books are available yet.")
    expect(view.querySelector('a[href="/public/forum"]')).not.toBeNull()
    expect(view.querySelector('a[href="/register"]')).not.toBeNull()
  })
})
