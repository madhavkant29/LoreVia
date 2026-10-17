// @vitest-environment jsdom

import { act } from "react"
import type { ReactNode } from "react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const getBookMock = vi.hoisted(() => vi.fn())
const getCharactersMock = vi.hoisted(() => vi.fn())
const getWorkspaceTreeMock = vi.hoisted(() => vi.fn())
const getChapterListMock = vi.hoisted(() => vi.fn())
const getChapterMock = vi.hoisted(() => vi.fn())
const voiceConsistencyReviewMock = vi.hoisted(() => vi.fn())
const saveSceneMock = vi.hoisted(() => vi.fn())
const saveNoteMock = vi.hoisted(() => vi.fn())

vi.mock("next/dynamic", () => ({
  default: () => () => <div data-testid="author-tools-nav" />,
}))

vi.mock("next/link", () => ({
  default: ({ children, href, prefetch: _prefetch, ...props }: { children: ReactNode; href: string; prefetch?: boolean | null }) => <a href={href} {...props}>{children}</a>,
}))

vi.mock("next/navigation", () => ({
  useParams: () => ({ bookId: "book-1" }),
}))

vi.mock("@/lib/api/books", () => ({
  booksApi: {
    get: (...args: unknown[]) => getBookMock(...args),
    getCharacters: (...args: unknown[]) => getCharactersMock(...args),
    getWorkspaceTree: (...args: unknown[]) => getWorkspaceTreeMock(...args),
    saveScene: (...args: unknown[]) => saveSceneMock(...args),
  },
}))

vi.mock("@/lib/api/reader", () => ({
  readerApi: {
    getChapterList: (...args: unknown[]) => getChapterListMock(...args),
    getChapter: (...args: unknown[]) => getChapterMock(...args),
  },
}))

vi.mock("@/lib/api/intelligence", () => ({
  MAX_ADVISOR_PASSAGE_CHARS: 12_000,
  intelligenceApi: {
    voiceConsistencyReview: (...args: unknown[]) => voiceConsistencyReviewMock(...args),
  },
}))

vi.mock("@/lib/stores/preferencesStore", () => ({
  usePreferencesStore: () => ({ theme: "light" }),
}))

vi.mock("@/lib/utils/notes", () => ({
  saveContextualVaultNote: (...args: unknown[]) => saveNoteMock(...args),
}))

vi.mock("@/lib/utils/apiErrors", () => ({
  getApiErrorDetail: () => null,
}))

import VoiceConsistencyPage from "./page"

let container: HTMLDivElement | null = null
let root: Root | null = null
let queryClient: QueryClient | null = null

;(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

function renderPage() {
  container = document.createElement("div")
  document.body.appendChild(container)
  root = createRoot(container)
  const client = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  })
  queryClient = client

  act(() => {
    root?.render(
      <QueryClientProvider client={client}>
        <VoiceConsistencyPage />
      </QueryClientProvider>,
    )
  })

  return client
}

async function waitForContent(text: string, timeout = 2000) {
  const start = Date.now()
  while (Date.now() - start < timeout) {
    if (container?.textContent?.includes(text)) return
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 0))
    })
  }
  throw new Error(`Timed out waiting for "${text}"`)
}

beforeEach(() => {
  saveNoteMock.mockReset().mockResolvedValue({ path: "Voice/review.md" })
  getBookMock.mockReset()
  getCharactersMock.mockReset()
  getWorkspaceTreeMock.mockReset()
  getChapterListMock.mockReset()
  getChapterMock.mockReset()
  voiceConsistencyReviewMock.mockReset()
  saveSceneMock.mockReset()

  getBookMock.mockResolvedValue({
    id: "book-1",
    title: "Sky of Ash",
  })
  getCharactersMock.mockResolvedValue([
    {
      id: "char-gregor",
      name: "Gregor",
    },
    {
      id: "char-grete",
      name: "Grete",
    },
  ])
  getWorkspaceTreeMock.mockResolvedValue({
    scene_groups: [],
    note_paths: [],
  })
  getChapterListMock.mockResolvedValue({
    current_chapter: 1,
    chapters: [{ number: 1, title: "The Ember Gate" }],
  })
  getChapterMock.mockResolvedValue({
    chapter_title: "The Ember Gate",
    text_content: "Gregor said, \"I can still make this work.\"",
  })
  voiceConsistencyReviewMock.mockResolvedValue({
    review: {
      overall_verdict: "Gregor is mostly on voice.",
      issues: [],
    },
    retrieved_passages: [],
    characters_reviewed: ["Gregor"],
    character_matches: [],
    warnings: ["Dialogue could not be confidently attributed to Gregor; the review used the full submitted passage instead."],
  })
  saveSceneMock.mockResolvedValue({ path: "scenes/voice/chapter-1/voice-review.md" })
})

afterEach(() => {
  vi.restoreAllMocks()
  if (root) {
    act(() => {
      root?.unmount()
    })
  }
  queryClient?.clear()
  container?.remove()
  container = null
  root = null
  queryClient = null
  document.body.innerHTML = ""
})

describe("VoiceConsistencyPage", () => {
  it("defaults to auto-detect and sends the selected character when focused", async () => {
    renderPage()
    await waitForContent("The Ember Gate")
    await act(async () => { await new Promise((resolve) => setTimeout(resolve, 20)) })
    expect(getWorkspaceTreeMock).not.toHaveBeenCalled()

    const selects = container?.querySelectorAll("select")
    const characterSelect = selects?.[1] as HTMLSelectElement
    expect(characterSelect.value).toBe("")

    await act(async () => {
      characterSelect.value = "char-gregor"
      characterSelect.dispatchEvent(new Event("change", { bubbles: true }))
    })

    const runButton = Array.from(container?.querySelectorAll("button") ?? []).find((button) => button.textContent?.includes("Run voice review"))
    expect(runButton).toBeTruthy()

    await act(async () => {
      runButton?.dispatchEvent(new MouseEvent("click", { bubbles: true }))
      await Promise.resolve()
    })

    expect(voiceConsistencyReviewMock).toHaveBeenCalledWith("book-1", "Gregor said, \"I can still make this work.\"", {
      chapterNum: 1,
      characterId: "char-gregor",
    })
    await waitForContent("Focused review: Gregor")
    expect(container?.textContent).toContain("Dialogue could not be confidently attributed to Gregor; the review used the full submitted passage instead.")
    expect(getWorkspaceTreeMock).not.toHaveBeenCalled()

    const saveSnapshotButton = Array.from(container?.querySelectorAll("button") ?? []).find((button) => button.textContent?.includes("Save snapshot"))
    await act(async () => {
      saveSnapshotButton?.dispatchEvent(new MouseEvent("click", { bubbles: true }))
      await Promise.resolve()
    })
    expect(getWorkspaceTreeMock).toHaveBeenCalledTimes(1)
  })

  it("keeps edited chapter and custom drafts through selection changes and refetches", async () => {
    const client = renderPage()
    await waitForContent("The Ember Gate")
    await act(async () => { await new Promise((resolve) => setTimeout(resolve, 20)) })
    await editPassage("My chapter revision")
    await selectSource("")
    await editPassage("My custom dialogue")
    await act(async () => { await client.invalidateQueries() })
    expect(container?.querySelector("textarea")?.value).toBe("My custom dialogue")
    await selectSource("1")
    expect(container?.querySelector("textarea")?.value).toBe("My chapter revision")
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false)
    await clickButton("Discard passage edits")
    expect(container?.querySelector("textarea")?.value).toBe("My chapter revision")
    confirm.mockReturnValue(true)
    await clickButton("Discard passage edits")
    expect(container?.querySelector("textarea")?.value).toContain("I can still make this work")
  })

  it("prevents truncated reviews and duplicate requests while retaining the submitted snapshot", async () => {
    renderPage(); await waitForContent("The Ember Gate")
    await act(async () => { await new Promise((resolve) => setTimeout(resolve, 20)) })
    await editPassage("x".repeat(12001))
    expect(container?.querySelector("textarea")?.value).toHaveLength(12001)
    await clickButton("Run voice review")
    expect(voiceConsistencyReviewMock).not.toHaveBeenCalled()
    await editPassage("Reviewed dialogue")
    let resolve!: (value: unknown) => void
    voiceConsistencyReviewMock.mockImplementationOnce(() => new Promise((done) => { resolve = done }))
    await clickButton("Run voice review")
    await editPassage("Later revision")
    await act(async () => { resolve({ review: { overall_verdict: "Original review", issues: [] }, characters_reviewed: [], warnings: ["Limited evidence"], retrieved_passages: [] }) })
    await waitForContent("The editor or character focus has changed")
    await selectSource("")
    await editPassage("Different custom text")
    await clickButton("Save snapshot")
    expect(voiceConsistencyReviewMock).toHaveBeenCalledTimes(1)
    expect(saveSceneMock.mock.calls[0][1]).toMatchObject({ chapter_number: 1, body: expect.stringContaining("Reviewed dialogue") })
    expect(saveSceneMock.mock.calls[0][1].body).not.toContain("Later revision")
    expect(saveSceneMock.mock.calls[0][1].body).toContain("Limited evidence")
  })

  it("preserves the previous review on failure and recovers from note save errors", async () => {
    renderPage(); await waitForContent("The Ember Gate")
    await act(async () => { await new Promise((resolve) => setTimeout(resolve, 20)) })
    await clickButton("Run voice review")
    await waitForContent("Gregor is mostly on voice")
    voiceConsistencyReviewMock.mockRejectedValueOnce(new Error("offline"))
    await editPassage("Revised dialogue")
    await clickButton("Run voice review")
    await waitForContent("Could not run the voice review")
    expect(container?.textContent).toContain("Gregor is mostly on voice")
    saveNoteMock.mockRejectedValueOnce(new Error("offline"))
    await clickButton("Save review note")
    await waitForContent("Check Notes before trying again")
    await clickButton("Save review note")
    await waitForContent("Saved voice note")
    expect(saveNoteMock.mock.calls[1][0].content).toContain("Character focus: Auto-detect")
  })

  it("does not replace a custom draft when a delayed chapter list arrives", async () => {
    let resolve!: (value: unknown) => void
    getChapterListMock.mockImplementation(() => new Promise((done) => { resolve = done }))
    renderPage(); await waitForContent("Loading chapters")
    await editPassage("Dialogue typed while chapters load")
    await act(async () => { resolve({ current_chapter: 1, chapters: [{ number: 1, title: "The Ember Gate" }] }); await new Promise((done) => setTimeout(done, 0)) })
    expect(container?.querySelector("select")?.value).toBe("")
    expect(container?.querySelector("textarea")?.value).toBe("Dialogue typed while chapters load")
  })

  it("makes a removed chapter explicit and keeps its draft recoverable", async () => {
    const client = renderPage(); await waitForContent("The Ember Gate")
    await act(async () => { await new Promise((resolve) => setTimeout(resolve, 20)) })
    await editPassage("Preserve this orphaned chapter draft")
    getChapterListMock.mockResolvedValue({ current_chapter: null, chapters: [] })
    await act(async () => { await client.invalidateQueries(); await new Promise((resolve) => setTimeout(resolve, 0)) })
    await waitForContent("This chapter is no longer in the chapter list")
    expect(container?.querySelector("textarea")?.value).toBe("Preserve this orphaned chapter draft")
    await clickButton("Run voice review")
    expect(voiceConsistencyReviewMock).not.toHaveBeenCalled()
  })
})

async function editPassage(value: string) {
  await act(async () => {
    const input = container!.querySelector("textarea")!
    Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")!.set!.call(input, value)
    input.dispatchEvent(new Event("input", { bubbles: true }))
  })
}

async function selectSource(value: string) {
  await act(async () => {
    const select = container!.querySelector("select")!
    select.value = value; select.dispatchEvent(new Event("change", { bubbles: true }))
  })
}

async function clickButton(label: string) {
  await act(async () => {
    Array.from(container!.querySelectorAll("button")).find((button) => button.textContent === label)?.click()
    await new Promise((resolve) => setTimeout(resolve, 0))
  })
}
