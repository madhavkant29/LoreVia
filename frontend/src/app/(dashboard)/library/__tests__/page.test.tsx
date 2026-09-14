// @vitest-environment jsdom

import type { ReactNode } from "react"
import { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import type { Book } from "@/types/book"

const mockRefetch = vi.fn()
const mockPush = vi.fn()
const mockPrefetch = vi.fn()
const mockArchive = vi.fn()
const mockHide = vi.fn()
const mockPublishPublicly = vi.fn()
const mockUnpublishPublicly = vi.fn()
const mockRetryProcessing = vi.fn()
const mockDeletePermanently = vi.fn()
const mockGetReaderBootstrap = vi.fn()
const mockConfirm = vi.fn()
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
  useQueryClient: () => ({ prefetchQuery: mockPrefetch }),
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
    const Component = ({ onClose, initialMode, initialExistingBookId }: { onClose?: () => void; initialMode?: string; initialExistingBookId?: string }) => (
      <section>
        <p>Upload modal inline</p>
        {initialMode ? <p>Mode {initialMode}</p> : null}
        {initialExistingBookId ? <p>Book {initialExistingBookId}</p> : null}
        <button type="button" onClick={onClose}>Close upload</button>
      </section>
    )
    Component.displayName = "DynamicMock"
    return Component
  },
}))

vi.mock("@/lib/api/books", () => ({
  booksApi: {
    list: vi.fn(),
    listPage: vi.fn(),
    archive: (...args: unknown[]) => mockArchive(...args),
    hide: (...args: unknown[]) => mockHide(...args),
    publishPublicly: (...args: unknown[]) => mockPublishPublicly(...args),
    unpublishPublicly: (...args: unknown[]) => mockUnpublishPublicly(...args),
    retryProcessing: (...args: unknown[]) => mockRetryProcessing(...args),
    deletePermanently: (...args: unknown[]) => mockDeletePermanently(...args),
    getReaderBootstrap: (...args: unknown[]) => mockGetReaderBootstrap(...args),
  },
}))

vi.mock("@/components/ui/ConfirmDialog", () => ({
  useConfirmDialog: () => mockConfirm,
}))

vi.mock("@/lib/query/cacheKeys", () => ({
  asQueryKey: (key: string) => key,
  booksPageCacheKey: () => "books-page",
}))

vi.mock("@/lib/stores/authStore", () => ({
  useAuthStore: (selector?: ((s: { user: { id: string; tier: string; trial_active: boolean }; hydrated: boolean }) => unknown) | undefined) => {
    const state = { user: { id: "test-user", tier: "author", trial_active: false }, hydrated: true }
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
  mockRefetch.mockResolvedValue({})
  mockArchive.mockResolvedValue({})
  mockHide.mockResolvedValue({})
  mockPublishPublicly.mockResolvedValue({})
  mockUnpublishPublicly.mockResolvedValue({})
  mockRetryProcessing.mockResolvedValue({})
  mockDeletePermanently.mockResolvedValue({})
  mockGetReaderBootstrap.mockResolvedValue({})
  mockConfirm.mockResolvedValue(true)
  mockBooks = []
  mockIsLoading = false
  mockIsError = true
})

afterEach(() => {
  mockRefetch.mockClear()
  mockPush.mockClear()
  mockPrefetch.mockClear()
  mockArchive.mockClear()
  mockHide.mockClear()
  mockPublishPublicly.mockClear()
  mockUnpublishPublicly.mockClear()
  mockRetryProcessing.mockClear()
  mockDeletePermanently.mockClear()
  mockGetReaderBootstrap.mockClear()
  mockConfirm.mockClear()
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

async function flushUi(times = 3) {
  for (let index = 0; index < times; index += 1) {
    await act(async () => {
      await Promise.resolve()
    })
  }
}

function clickByText(text: string, index = 0) {
  const matches = Array.from(document.body.querySelectorAll("button, a")).filter((element) =>
    element.textContent?.includes(text) || element.getAttribute("aria-label")?.includes(text)
  )
  const match = matches[index] as HTMLElement | undefined
  expect(match, `Expected ${text}`).toBeTruthy()
  act(() => {
    match?.click()
  })
  return match
}

function clickExactButton(text: string, index = 0) {
  const matches = Array.from(document.body.querySelectorAll("button")).filter((element) =>
    element.textContent?.trim() === text
  )
  const match = matches[index] as HTMLElement | undefined
  expect(match, `Expected exact button ${text}`).toBeTruthy()
  act(() => {
    match?.click()
  })
  return match
}

function setValue(field: HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement, value: string) {
  const prototype = field instanceof HTMLTextAreaElement
    ? HTMLTextAreaElement.prototype
    : field instanceof HTMLSelectElement
      ? HTMLSelectElement.prototype
      : HTMLInputElement.prototype
  const descriptor = Object.getOwnPropertyDescriptor(prototype, "value")
  act(() => {
    descriptor?.set?.call(field, value)
    field.dispatchEvent(new Event("input", { bubbles: true }))
    field.dispatchEvent(new Event("change", { bubbles: true }))
  })
}

function buildBook(overrides: Partial<Book> & Pick<Book, "id" | "title">): Book {
  return {
    author: "A. Writer",
    genre: "Fantasy",
    format: "pdf",
    work_type: "novel",
    status: "ready",
    mode: "author",
    workspace_shell: "author",
    access_class: "owner",
    can_switch_workspace_mode: true,
    total_chapters: 10,
    chapters_read_count: 2,
    progress_pct: 30,
    total_tokens: 24000,
    created_at: "2026-06-01T00:00:00Z",
    processing: {
      status: "ready",
      stage: "ready",
      label: "Ready",
      progress_pct: 100,
      retryAvailable: false,
      updated_at: "2026-06-05T00:00:00Z",
    },
    ...overrides,
  } as Book
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
  it("shows the first-manuscript hero for eligible zero-project users and opens author upload", async () => {
    mockIsError = false
    mockBooks = []

    render()
    await flushUi()

    expect(container?.textContent).toContain("Upload your manuscript for a first read")
    expect(container?.textContent).toContain("LoreVia begins with what is working")
    expect(container?.textContent).not.toContain("Total projects")

    clickExactButton("Upload manuscript")

    expect(container?.textContent).toContain("Upload modal inline")
    expect(container?.textContent).toContain("Mode author")
  })

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

  it("drives filters, project menus, publish, upload, and navigation actions", async () => {
    mockIsError = false
    mockBooks = [
      buildBook({
        id: "book-ready",
        title: "Aster Draft",
        public_status: "draft",
        public_slug: null,
        public_description: null,
      }),
      buildBook({
        id: "book-processing",
        title: "Processing Draft",
        status: "processing",
        progress_pct: 12,
        processing: {
          status: "processing",
          stage: "extracting",
          progress_pct: 34,
          retry_available: true,
          updated_at: "2026-06-06T00:00:00Z",
        },
      }),
      buildBook({
        id: "book-public",
        title: "Public Draft",
        is_public: true,
        public_status: "published",
        public_slug: "public-draft",
      }),
      buildBook({
        id: "book-archived",
        title: "Archived Draft",
        archived_at: "2026-06-02T00:00:00Z",
      }),
    ]

    render()
    await flushUi()

    expect(container?.textContent).toContain("Aster Draft")
    expect(container?.textContent).not.toContain("Archived Draft")

    const search = container?.querySelector('input[aria-label="Search projects"]') as HTMLInputElement
    setValue(search, "processing")
    expect(container?.textContent).toContain("Processing Draft")

    clickByText("Filter")
    clickByText("Author Workspace")
    clickByText("Processing")
    const showArchived = container?.querySelector('button[aria-label="Show archived projects"]') as HTMLButtonElement
    act(() => showArchived.click())
    expect(showArchived.getAttribute("aria-pressed")).toBe("true")

    const sort = container?.querySelector('select[aria-label="Sort projects"]') as HTMLSelectElement
    setValue(sort, "title")
    clickByText("List view")
    expect(container?.querySelector('[aria-label="List view"]')?.getAttribute("aria-pressed")).toBe("true")

    setValue(search, "")
    clickByText("Any")
    clickByText("Open actions for Aster Draft")
    clickExactButton("Pin project")
    expect(localStorageStore["library-pinned-projects:v1"]).toBeDefined()

    clickByText("Open actions for Aster Draft")
    clickExactButton("Add chapter")
    expect(mockPush).toHaveBeenCalledWith("/library/add-chapter?book=book-ready")

    clickExactButton("Archive")
    await flushUi()
    expect(mockArchive).toHaveBeenCalledWith("book-ready", true)

    clickByText("Open actions for Aster Draft")
    clickExactButton("Remove")
    await flushUi()
    expect(mockConfirm).toHaveBeenCalled()
    expect(mockHide).toHaveBeenCalledWith("book-ready", true)

    clickByText("Open actions for Aster Draft")
    clickExactButton("Delete permanently")
    await flushUi()
    expect(document.body.textContent).toContain("Delete Aster Draft permanently?")
    const inputs = Array.from(document.body.querySelectorAll("input")) as HTMLInputElement[]
    const deleteInput = inputs[inputs.length - 1]
    setValue(deleteInput, "DELETE BOOK")
    clickExactButton("Delete permanently", 1)
    await flushUi()
    expect(mockDeletePermanently).toHaveBeenCalledWith("book-ready", "DELETE BOOK")

    clickByText("Open actions for Aster Draft")
    clickExactButton("Publish publicly")
    expect(document.body.textContent).toContain("Publish your own original work")
    const publishInputs = Array.from(document.body.querySelectorAll("input"))
    const rightsCheckbox = publishInputs.find((input) => input.type === "checkbox") as HTMLInputElement
    act(() => rightsCheckbox.click())
    await flushUi()
    clickExactButton("Publish publicly", 1)
    await flushUi()
    expect(mockPublishPublicly).toHaveBeenCalledWith("book-ready", {
      publicSlug: "aster-draft",
      rightsConfirmation: true,
      description: null,
    })

    clickByText("Open actions for Public Draft")
    clickExactButton("Unpublish public book")
    await flushUi()
    expect(mockUnpublishPublicly).toHaveBeenCalledWith("book-public")

    clickExactButton("Retry")
    await flushUi()
    expect(mockRetryProcessing).toHaveBeenCalledWith("book-processing")

    clickByText("Create new project")
    expect(container?.textContent).toContain("Upload modal inline")
    clickByText("Close upload")
    await flushUi()
    expect(mockRefetch).toHaveBeenCalled()

    const asterLink = container?.querySelector<HTMLAnchorElement>('a[aria-label="Open Aster Draft"]')
    expect(asterLink).toBeTruthy()
    act(() => {
      asterLink?.click()
    })
    expect(mockPush).toHaveBeenLastCalledWith("/book-1")
  })
})
