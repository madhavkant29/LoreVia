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

vi.mock("next/dynamic", () => ({
  default: () => () => <div data-testid="author-tools-nav" />,
}))

vi.mock("next/link", () => ({
  default: ({ children, href, ...props }: { children: ReactNode; href: string }) => <a href={href} {...props}>{children}</a>,
}))

vi.mock("next/navigation", () => ({
  useParams: () => ({ bookId: "book-1" }),
}))

vi.mock("@/lib/api/books", () => ({
  booksApi: {
    get: (...args: unknown[]) => getBookMock(...args),
    getCharacters: (...args: unknown[]) => getCharactersMock(...args),
    getWorkspaceTree: (...args: unknown[]) => getWorkspaceTreeMock(...args),
    saveScene: vi.fn(),
  },
}))

vi.mock("@/lib/api/reader", () => ({
  readerApi: {
    getChapterList: (...args: unknown[]) => getChapterListMock(...args),
    getChapter: (...args: unknown[]) => getChapterMock(...args),
  },
}))

vi.mock("@/lib/api/intelligence", () => ({
  intelligenceApi: {
    voiceConsistencyReview: (...args: unknown[]) => voiceConsistencyReviewMock(...args),
  },
}))

vi.mock("@/lib/stores/preferencesStore", () => ({
  usePreferencesStore: () => ({ theme: "light" }),
}))

vi.mock("@/lib/utils/notes", () => ({
  saveContextualVaultNote: vi.fn(),
}))

vi.mock("@/lib/utils/apiErrors", () => ({
  getApiErrorDetail: () => null,
}))

import VoiceConsistencyPage from "./page"

let container: HTMLDivElement | null = null
let root: Root | null = null

;(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

function renderPage() {
  container = document.createElement("div")
  document.body.appendChild(container)
  root = createRoot(container)
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  })

  act(() => {
    root?.render(
      <QueryClientProvider client={queryClient}>
        <VoiceConsistencyPage />
      </QueryClientProvider>,
    )
  })

  return queryClient
}

async function flushUi() {
  await act(async () => {
    await Promise.resolve()
    await Promise.resolve()
    await Promise.resolve()
  })
}

beforeEach(() => {
  getBookMock.mockReset()
  getCharactersMock.mockReset()
  getWorkspaceTreeMock.mockReset()
  getChapterListMock.mockReset()
  getChapterMock.mockReset()
  voiceConsistencyReviewMock.mockReset()

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
})

afterEach(() => {
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

describe("VoiceConsistencyPage", () => {
  it("defaults to auto-detect and sends the selected character when focused", async () => {
    renderPage()
    await flushUi()
    await flushUi()

    expect(container?.textContent).toContain("Auto-detect from passage")

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
    expect(container?.textContent).toContain("Focused review: Gregor")
    expect(container?.textContent).toContain("Dialogue could not be confidently attributed to Gregor; the review used the full submitted passage instead.")
  })
})
