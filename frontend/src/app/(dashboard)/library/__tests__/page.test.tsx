// @vitest-environment jsdom

import type { ReactNode } from "react"
import { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import type { Book } from "@/types/book"

const mockRefetch = vi.fn()
const mockPush = vi.fn()
let mockBooks: Book[] = []
let mockIsLoading = false
let mockIsError = true

const localStorageStore: Record<string, string> = {}
const localStorageMock = {
  getItem: vi.fn((key: string) => localStorageStore[key] ?? null),
  setItem: vi.fn((key: string, value: string) => {
    localStorageStore[key] = value
  }),
  removeItem: vi.fn((key: string) => {
    delete localStorageStore[key]
  }),
  clear: vi.fn(() => {
    Object.keys(localStorageStore).forEach((key) => delete localStorageStore[key])
  }),
}

vi.stubGlobal("localStorage", localStorageMock)

vi.mock("@tanstack/react-query", () => ({
  useQuery: () => ({
    data: mockBooks,
    isLoading: mockIsLoading,
    isError: mockIsError,
    refetch: mockRefetch,
  }),
  useQueryClient: () => ({}),
}))

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
  useParams: () => ({}),
}))

vi.mock("next/link", () => ({
  default: ({ children, href, ...props }: { children: ReactNode; href: string }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}))

vi.mock("next/dynamic", () => ({
  default: () => {
    const Component = () => null
    Component.displayName = "DynamicMock"
    return Component
  },
}))

vi.mock("@/lib/api/books", () => ({
  booksApi: {
    list: vi.fn(),
    archive: vi.fn(),
    hide: vi.fn(),
    publishPublicly: vi.fn(),
    unpublishPublicly: vi.fn(),
  },
}))

vi.mock("@/lib/query/cacheKeys", () => ({
  asQueryKey: (key: string) => key,
  booksListCacheKey: () => "books-list",
}))

vi.mock("@/lib/stores/authStore", () => ({
  useAuthStore: (selector?: ((s: { user: { id: string }; hydrated: boolean }) => unknown) | undefined) => {
    const state = { user: { id: "test-user" }, hydrated: true }
    return typeof selector === "function" ? selector(state) : state
  },
}))

vi.mock("@/lib/stores/preferencesStore", () => ({
  usePreferencesStore: () => ({ theme: "dark" }),
}))

vi.mock("@/lib/utils/bookRoutes", () => ({
  getBookHref: () => "/book-1",
}))

import { LibraryClient } from "../LibraryClient"

let container: HTMLDivElement | null = null
let root: Root | null = null

beforeEach(() => {
  localStorageMock.clear()
  mockBooks = []
  mockIsLoading = false
  mockIsError = true
})

afterEach(() => {
  mockRefetch.mockClear()
  mockPush.mockClear()
  if (root) {
    act(() => {
      root?.unmount()
    })
  }
  container?.remove()
  container = null
  root = null
  document.body.innerHTML = ""
})

function render() {
  container = document.createElement("div")
  document.body.appendChild(container)
  root = createRoot(container)

  act(() => {
    root?.render(<LibraryClient />)
  })
}

describe("LibraryPage error state", () => {
  it("renders error card when books query fails", () => {
    render()

    expect(container?.textContent).toContain("Failed to load library")
    expect(container?.textContent).toContain(
      "Something went wrong while loading your library. Check your connection and try again.",
    )
  })

  it("renders a retry button that calls refetch", () => {
    render()

    const retryButton = container?.querySelector("button")
    expect(retryButton).toBeTruthy()
    expect(retryButton?.textContent).toContain("Try again")

    act(() => {
      retryButton?.click()
    })

    expect(mockRefetch).toHaveBeenCalledTimes(1)
  })

  it("does not render library content when in error state", () => {
    render()

    expect(container?.textContent).not.toContain("Pinned projects")
    expect(container?.textContent).not.toContain("All projects")
    expect(container?.textContent).not.toContain("New Project")
  })

  it("renders the error icon in the error card", () => {
    render()

    const svg = container?.querySelector("svg")
    expect(svg).toBeTruthy()
  })
})

describe("LibraryPage shared-book filtering", () => {
  it("hides reader-collaborator beta shares from the library list", () => {
    mockIsError = false
    mockBooks = [
      {
        id: "book-owner",
        title: "Owned project",
        author: null,
        genre: null,
        format: "pdf",
        work_type: "novel",
        status: "ready",
        mode: "author",
        workspace_shell: "author",
        access_class: "owner",
        can_switch_workspace_mode: true,
        total_chapters: 12,
        created_at: "2026-06-06T00:00:00Z",
      },
      {
        id: "book-share",
        title: "Shared beta project",
        author: null,
        genre: null,
        format: "pdf",
        work_type: "novel",
        status: "ready",
        mode: "reader",
        workspace_shell: "reader",
        access_class: "reader_collaborator",
        can_switch_workspace_mode: false,
        total_chapters: 8,
        created_at: "2026-06-06T00:00:00Z",
      },
    ] as Book[]

    render()

    expect(container?.textContent).toContain("Owned project")
    expect(container?.textContent).not.toContain("Shared beta project")
  })
})
