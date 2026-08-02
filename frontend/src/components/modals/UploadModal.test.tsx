import React, { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest"

const useQueryMock = vi.hoisted(() => vi.fn())
const uploadMock = vi.hoisted(() => vi.fn())
const setUsernameMock = vi.hoisted(() => vi.fn())
const captureMock = vi.hoisted(() => vi.fn())
const captureTimingMock = vi.hoisted(() => vi.fn())
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
    previewUpload: vi.fn(),
    createEmptyProject: vi.fn(),
    delete: vi.fn(),
    retryProcessing: vi.fn(),
  },
}))

vi.mock("@/lib/api/auth", () => ({
  authApi: {
    setUsername: setUsernameMock,
  },
}))

vi.mock("@/lib/api/intelligence", () => ({
  intelligenceApi: {
    advisorSuggestions: vi.fn(),
    continuityReport: vi.fn(),
    editorialReview: vi.fn(),
    synopsis: vi.fn(),
  },
}))

vi.mock("@/lib/api/reader", () => ({
  readerApi: {
    getChapter: vi.fn(),
    getPlotThreads: vi.fn(),
  },
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
  captureTiming: captureTimingMock,
}))

vi.mock("@/lib/query/cacheKeys", () => ({
  asQueryKey: (value: unknown) => value,
  bookCacheKey: (...parts: string[]) => parts.join(":"),
  booksListCacheKey: () => "books:list",
  booksSeriesCacheKey: () => "books:series",
  booksStatsCacheKey: () => "books:stats",
}))

import { UploadModal } from "./UploadModal"
import { booksApi } from "@/lib/api/books"
import { intelligenceApi } from "@/lib/api/intelligence"
import { readerApi } from "@/lib/api/reader"

let container: HTMLDivElement | null = null
let root: Root | null = null

describe("UploadModal", () => {
  beforeAll(() => {
    ;(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
  })

  beforeEach(() => {
    useQueryMock.mockReset()
    uploadMock.mockReset()
    vi.mocked(booksApi.importManuscript).mockReset()
    vi.mocked(booksApi.previewUpload).mockReset()
    vi.mocked(booksApi.createEmptyProject).mockReset()
    vi.mocked(booksApi.delete).mockReset()
    vi.mocked(intelligenceApi.advisorSuggestions).mockReset()
    vi.mocked(intelligenceApi.continuityReport).mockReset()
    vi.mocked(intelligenceApi.editorialReview).mockReset()
    vi.mocked(intelligenceApi.synopsis).mockReset()
    vi.mocked(readerApi.getChapter).mockReset()
    vi.mocked(readerApi.getPlotThreads).mockReset()
    setUsernameMock.mockReset()
    captureMock.mockReset()
    captureTimingMock.mockReset()
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
    vi.mocked(booksApi.previewUpload).mockResolvedValue(importPreviewFixture() as never)
    vi.mocked(booksApi.importManuscript).mockResolvedValue(importResponseFixture() as never)
    vi.mocked(booksApi.createEmptyProject).mockResolvedValue({ book_id: "empty-1" } as never)
    vi.mocked(booksApi.delete).mockResolvedValue({} as never)
    vi.mocked(intelligenceApi.editorialReview).mockResolvedValue({
      review: editorialReviewFixture(),
      retrieved_passages: [{ chapter_num: 2, chapter_title: "Gate", excerpt: "The oath appears." }],
    } as never)
    vi.mocked(intelligenceApi.advisorSuggestions).mockResolvedValue({
      suggestions: [{ id: "suggestion-1", title: "Clarify oath", description: "Add setup.", chapter_ref: 2 }],
    } as never)
    vi.mocked(intelligenceApi.synopsis).mockResolvedValue({ synopsis: "Spoiler-light synopsis.", focus_points: ["oath"] } as never)
    vi.mocked(intelligenceApi.continuityReport).mockResolvedValue(new Blob(["report"], { type: "application/pdf" }))
    vi.mocked(readerApi.getChapter).mockResolvedValue({ text_content: "Recovered chapter text." } as never)
    vi.mocked(readerApi.getPlotThreads).mockResolvedValue([{ id: "thread-1", title: "Oath thread", status: "developing", introduced_at: 1 }] as never)
    Object.defineProperty(URL, "createObjectURL", { configurable: true, value: vi.fn(() => "blob:report") })
    Object.defineProperty(URL, "revokeObjectURL", { configurable: true, value: vi.fn() })
    Object.defineProperty(HTMLAnchorElement.prototype, "click", { configurable: true, value: vi.fn() })
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

    const authorInput = view.querySelector('input[aria-label="Manuscript author or pen name"]') as HTMLInputElement | null
    expect(authorInput?.value).toBe("author")
  })

  it("does not repopulate the manuscript byline after the user clears it", async () => {
    const view = renderUploadModal({ initialMode: "author" })
    const authorInput = view.querySelector('input[aria-label="Manuscript author or pen name"]') as HTMLInputElement | undefined

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

    const titleInput = view.querySelector('input[aria-label="Title"]') as HTMLInputElement | null
    const authorInput = view.querySelector('input[aria-label="Manuscript author or pen name"]') as HTMLInputElement | undefined
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
    expect(captureMock).toHaveBeenCalledWith("upload_started", expect.objectContaining({ mode: "author", kind: "new_upload" }))
    expect(captureMock).toHaveBeenCalledWith("book_uploaded", expect.not.objectContaining({ manuscript_text: expect.anything() }))
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

  it("previews manuscript structure, edits sections, skips preview, and starts empty projects", async () => {
    useQueryMock.mockImplementation(({ queryKey }: { queryKey: unknown }) => {
      if (queryKey === "books:series") return { data: { items: [{ id: "series-1", name: "Gate Cycle" }] }, refetch: vi.fn() }
      if (queryKey === "books:stats") {
        return {
          data: { private: { upload_limit_unlimited: false, total_uploads: 2, upload_limit: 5, uploads_remaining: 3 } },
          refetch: vi.fn(),
        }
      }
      return { data: [], refetch: vi.fn() }
    })
    const view = renderUploadModal({ initialMode: "author", presentation: "inline" })

    await chooseFile(view, new File(["chapter"], "gate.pdf", { type: "application/pdf" }))
    await clickButton(view, "Preview structure")
    expect(view.textContent).toContain("Structure preview")
    expect(view.textContent).toContain("92% confident")
    expect(view.textContent).toContain("Chapter One")

    await clickButton(view, "Edit structure")
    expect(view.textContent).toContain("Edit section structure")
    await clickButton(view, "Save changes")
    await clickButton(view, "Start empty project")
    setInputValue(view, 'input[aria-label="Title"]', "Blank Gate")
    await clickButton(view, "Gate Cycle")
    await clickButton(view, "Start empty project", 1)

    expect(booksApi.createEmptyProject).toHaveBeenCalledWith(
      expect.objectContaining({
        title: "Blank Gate",
        series_ids: ["series-1"],
        work_type: "novel",
      }),
    )
  })

  it("imports pasted chapters into existing author books and renders post-import review", async () => {
    useQueryMock.mockImplementation(({ queryKey }: { queryKey: unknown }) => {
      if (queryKey === "books:list") {
        return {
          data: [
            {
              id: "book-1",
              title: "Gate Draft",
              mode: "author",
              hidden_at: null,
              total_chapters: 3,
              work_type: "novel",
            },
          ],
          refetch: vi.fn(),
        }
      }
      return { data: undefined, refetch: vi.fn() }
    })

    const view = renderUploadModal({ initialMode: "author", initialExistingBookId: "book-1", presentation: "inline" })
    expect(view.textContent).toContain("Add New Chapter")
    expect((view.querySelector('input[aria-label="Chapter number"]') as HTMLInputElement | null)?.value).toBe("4")

    setInputValue(view, 'input[aria-label="Chapter title"]', "The Oath")
    setTextareaValue(view, "textarea", "Mara repeats the gate oath.")
    await clickButton(view, "Add Chapter & Process")

    expect(booksApi.importManuscript).toHaveBeenCalledWith(
      "book-1",
      expect.objectContaining({
        text: "Mara repeats the gate oath.",
        title: "The Oath",
        chapterNumber: 4,
        replaceExisting: false,
        splitIntoChapters: true,
      }),
    )
    await waitForText(view, "Immediate continuity review")
    expect(view.textContent).toContain("Immediate continuity review")
    expect(view.textContent).toContain("Strong upload")
    expect(view.textContent).toContain("Oath thread")

    await clickButton(view, "Download continuity report")
    expect(intelligenceApi.continuityReport).toHaveBeenCalled()
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

async function clickButton(view: HTMLDivElement, label: string, index = 0) {
  const button = Array.from(view.querySelectorAll("button")).filter((candidate) => candidate.textContent?.includes(label))[index]
  if (!button) throw new Error(`Missing button ${label}\n${view.textContent ?? ""}`)
  await act(async () => {
    button.dispatchEvent(new MouseEvent("click", { bubbles: true }))
    await Promise.resolve()
    await new Promise((resolve) => setTimeout(resolve, 0))
  })
}

async function chooseFile(view: HTMLDivElement, file: File) {
  const fileInput = view.querySelector('input[type="file"]') as HTMLInputElement | null
  if (!fileInput) throw new Error("Missing file input")
  await act(async () => {
    Object.defineProperty(fileInput, "files", { configurable: true, value: [file] })
    fileInput.dispatchEvent(new Event("change", { bubbles: true }))
    await Promise.resolve()
  })
}

function setInputValue(view: HTMLDivElement, selector: string, value: string) {
  const input = view.querySelector(selector) as HTMLInputElement | null
  if (!input) throw new Error(`Missing input ${selector}`)
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set
  setter?.call(input, value)
  input.dispatchEvent(new Event("input", { bubbles: true }))
}

function setTextareaValue(view: HTMLDivElement, selector: string, value: string) {
  const input = view.querySelector(selector) as HTMLTextAreaElement | null
  if (!input) throw new Error(`Missing textarea ${selector}`)
  const setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")?.set
  setter?.call(input, value)
  input.dispatchEvent(new Event("input", { bubbles: true }))
}

async function waitForText(view: HTMLDivElement, expected: string) {
  for (let index = 0; index < 30; index += 1) {
    if (view.textContent?.includes(expected)) return
    await act(async () => {
      await Promise.resolve()
      await new Promise((resolve) => setTimeout(resolve, 0))
    })
  }
  throw new Error(`Missing text ${expected}\n${view.textContent ?? ""}`)
}

function importPreviewFixture() {
  return {
    confidence: 0.92,
    detected_language: "en",
    language_confidence: 0.98,
    chapter_count: 1,
    front_matter_count: 1,
    toc_detected: true,
    warnings: [{ severity: "warning", message: "Front matter detected." }],
    sections: [
      { id: "section-1", type: "chapter", title: "Chapter One", number: 1, confidence: 0.9, include_in_analysis: true },
      { id: "section-2", type: "toc", title: "Contents", number: 0, confidence: 0.8, include_in_analysis: false },
    ],
  }
}

function importResponseFixture() {
  return {
    book_id: "book-1",
    imported_chapters: [4],
    status: "processing",
    chapter_reports: [
      {
        book_id: "book-1",
        chapter_number: 4,
        chapter_title: "The Oath",
        summary: "Mara repeats the oath.",
        new_characters: [{ name: "Mara", role: "mc", arc_summary: "Keeps the gate oath." }],
        relationship_changes: ["Mara trusts Joren"],
        plot_threads_opened: ["Gate oath"],
        plot_threads_resolved: [],
        continuity_flags: ["Oath is introduced late"],
        warnings: [],
      },
    ],
  }
}

function editorialReviewFixture() {
  return {
    overall_verdict: "Strong upload with one oath continuity note.",
    thematic_fit: { score: "strong", notes: "Theme lands." },
    continuity_issues: [{ title: "Oath timing", severity: "moderate", type: "timeline", description: "The oath needs earlier setup.", suggestion: "Seed it in chapter two." }],
    grammar_issues: [],
    formatting_notes: [],
    insertion_opportunities: [{ title: "Seed oath", target_chapter: 2, target_chapter_title: "Gate", problem: "Late setup", what_to_add: "A short oath reference.", why_here: "This is where Mara learns the rule." }],
  }
}
