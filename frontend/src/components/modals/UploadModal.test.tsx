import React, { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest"

const useQueryMock = vi.hoisted(() => vi.fn())
const uploadMock = vi.hoisted(() => vi.fn())
const setUsernameMock = vi.hoisted(() => vi.fn())
const captureMock = vi.hoisted(() => vi.fn())
const setUserMock = vi.hoisted(() => vi.fn())
const setBookModeMock = vi.hoisted(() => vi.fn())
const authState = vi.hoisted(() => ({
  user: {
    id: "user-1",
    email: "author@getlorevia.com",
    username: "author",
    tier: "author",
  },
}))

vi.mock("@tanstack/react-query", () => ({
  useQuery: useQueryMock,
}))

vi.mock("@/lib/api/books", () => ({
  booksApi: {
    listSeries: vi.fn(),
    list: vi.fn(),
    getStats: vi.fn(),
    get: vi.fn(),
    upload: uploadMock,
    importManuscript: vi.fn(),
  },
}))

vi.mock("@/lib/api/auth", () => ({
  authApi: {
    setUsername: setUsernameMock,
  },
}))

vi.mock("@/lib/api/intelligence", () => ({
  intelligenceApi: {},
}))

vi.mock("@/lib/api/reader", () => ({
  readerApi: {},
}))

vi.mock("@/lib/billing/plans", () => ({
  canUseAuthorFeatures: () => true,
}))

vi.mock("@/lib/stores/preferencesStore", () => ({
  usePreferencesStore: () => ({
    theme: "light",
  }),
}))

vi.mock("@/lib/stores/authStore", () => ({
  useAuthStore: (selector?: (state: { user: typeof authState.user; setUser: typeof setUserMock }) => unknown) => {
    const state = {
      user: authState.user,
      setUser: setUserMock,
    }
    return selector ? selector(state) : state
  },
}))

vi.mock("@/lib/stores/bookModeStore", () => ({
  useBookModeStore: (selector?: (state: { setMode: typeof setBookModeMock }) => unknown) => {
    const state = { setMode: setBookModeMock }
    return selector ? selector(state) : state
  },
}))

vi.mock("@/lib/analytics/posthog", () => ({
  capture: captureMock,
}))

vi.mock("@/lib/query/cacheKeys", () => ({
  asQueryKey: (value: unknown) => value,
  bookCacheKey: (...parts: string[]) => parts.join(":"),
  booksListCacheKey: () => "books:list",
  booksSeriesCacheKey: () => "books:series",
  booksStatsCacheKey: () => "books:stats",
}))

import { UploadModal } from "./UploadModal"

let container: HTMLDivElement | null = null
let root: Root | null = null

describe("UploadModal", () => {
  beforeAll(() => {
    ;(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
  })

  beforeEach(() => {
    useQueryMock.mockReset()
    uploadMock.mockReset()
    setUsernameMock.mockReset()
    captureMock.mockReset()
    setUserMock.mockReset()
    setBookModeMock.mockReset()
    authState.user = {
      id: "user-1",
      email: "author@getlorevia.com",
      username: "author",
      tier: "author",
    }

    useQueryMock.mockReturnValue({ data: undefined, refetch: vi.fn() })
    uploadMock.mockResolvedValue({ book_id: "book-99" })
  })

  afterEach(() => {
    if (root) {
      act(() => {
        root?.unmount()
      })
    }
    if (container) {
      container.remove()
    }
    container = null
    root = null
  })

  it("prefills author mode uploads from the account username and explains the manuscript-only byline", async () => {
    const view = renderUploadModal({ initialMode: "author" })

    expect(view.textContent).toContain("This name appears on this manuscript only.")
    expect(view.textContent).toContain("different pen name or byline")

    const textInputs = Array.from(view.querySelectorAll('input[type="text"]')) as HTMLInputElement[]
    const authorInput = textInputs.find((input) => input.placeholder === "Manuscript author or pen name")
    expect(authorInput?.value).toBe("author")
  })

  it("does not repopulate the manuscript byline after the user clears it", async () => {
    const view = renderUploadModal({ initialMode: "author" })
    const authorInput = Array.from(view.querySelectorAll('input[type="text"]')).find((input) => (input as HTMLInputElement).placeholder === "Manuscript author or pen name") as HTMLInputElement | undefined

    await act(async () => {
      if (authorInput) {
        authorInput.value = ""
        authorInput.dispatchEvent(new Event("input", { bubbles: true }))
      }
    })

    expect(authorInput?.value).toBe("")
  })

  it("submits an overridden manuscript author without changing the account username", async () => {
    const view = renderUploadModal({ initialMode: "author" })

    const titleInput = view.querySelector('input[placeholder="Title"]') as HTMLInputElement | null
    const authorInput = Array.from(view.querySelectorAll('input[type="text"]')).find((input) => (input as HTMLInputElement).placeholder === "Manuscript author or pen name") as HTMLInputElement | undefined
    const fileInput = view.querySelector('input[type="file"]') as HTMLInputElement | null
    const submitButton = view.querySelector('button[type="submit"]') as HTMLButtonElement | null

    await act(async () => {
      if (titleInput) {
        titleInput.value = "Ash Draft"
        titleInput.dispatchEvent(new Event("input", { bubbles: true }))
      }
      if (authorInput) {
        authorInput.value = "M. Vale"
        authorInput.dispatchEvent(new Event("input", { bubbles: true }))
      }
    })

    const file = new File(["chapter one"], "ash-draft.docx", { type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document" })
    await act(async () => {
      if (fileInput) {
        Object.defineProperty(fileInput, "files", {
          configurable: true,
          value: [file],
        })
        fileInput.dispatchEvent(new Event("change", { bubbles: true }))
      }
    })

    await act(async () => {
      submitButton?.dispatchEvent(new MouseEvent("click", { bubbles: true }))
      await Promise.resolve()
    })

    expect(uploadMock).toHaveBeenCalledWith(
      expect.any(File),
      "Ash Draft",
      undefined,
      "M. Vale",
      expect.objectContaining({ mode: "author" }),
    )
    expect(authState.user.username).toBe("author")
  })

  it("removes the private workspace notice and renders author upload options with explicit colors", async () => {
    useQueryMock.mockImplementation(({ queryKey }: { queryKey: unknown }) => {
      if (queryKey === "books:list") {
        return {
          data: [
            {
              id: "book-1",
              title: "metamorphosis",
              mode: "author",
              hidden_at: null,
              work_type: "novel",
            },
          ],
          refetch: vi.fn(),
        }
      }
      return { data: undefined, refetch: vi.fn() }
    })

    const view = renderUploadModal({ initialMode: "author" })

    expect(view.textContent).not.toContain("Private by default")
    expect(view.textContent).not.toContain("This upload stays in your workspace.")
    expect(view.textContent).not.toContain("Public sharing is not part of this step.")

    const toggleButton = findButton(view, "Create a new upload")
    await act(async () => {
      toggleButton?.dispatchEvent(new MouseEvent("click", { bubbles: true }))
    })

    const optionButton = findButton(view, "metamorphosis")
    expect(optionButton?.getAttribute("style")).toContain("background-color: rgb(255, 255, 255)")
    expect(optionButton?.getAttribute("style")).toContain("color: rgb(0, 0, 0)")
  })
})

function renderUploadModal(props?: Partial<React.ComponentProps<typeof UploadModal>>) {
  container = document.createElement("div")
  document.body.appendChild(container)
  root = createRoot(container)

  act(() => {
    root?.render(<UploadModal onClose={() => {}} {...props} />)
  })

  return container
}

function findButton(view: HTMLDivElement, label: string) {
  return Array.from(view.querySelectorAll("button")).find((button) => button.textContent?.includes(label))
}
