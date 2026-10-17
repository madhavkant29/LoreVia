import React, { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, describe, expect, it, vi } from "vitest"

import type { Book, BookNote, SavedQuote } from "@/types/book"
import type { ChapterListResponse, ReadingProgress, SummaryCollectionResponse } from "@/types/reader"

const recallHookMock = vi.hoisted(() => vi.fn())

vi.mock("@/lib/hooks/useRecall", () => ({
  useRecall: recallHookMock,
}))

vi.mock("@/components/intelligence/RecallCard", () => ({
  RecallCard: ({
    recall,
    lastChapter,
    onDismiss,
    onContinue,
  }: {
    recall: string
    lastChapter: number | null
    onDismiss: () => void
    onContinue: () => void
  }) => (
    <section data-testid="story-so-far-card">
      <h2>Story So Far</h2>
      <p>{recall}</p>
      <p>Last active chapter: {lastChapter ?? "syncing"}</p>
      <button onClick={onContinue}>Continue Reading</button>
      <button onClick={onDismiss}>Dismiss</button>
    </section>
  ),
}))

import { ReaderOverview } from "./ReaderOverview"

let container: HTMLDivElement | null = null
let root: Root | null = null

describe("ReaderOverview", () => {
  afterEach(() => {
    if (root) {
      act(() => {
        root?.unmount()
      })
    }
    if (container) {
      container.remove()
    }
    recallHookMock.mockReset()
    container = null
    root = null
  })

  it("shows the story so far card when recall is available", () => {
    const dismiss = vi.fn()
    const onContinueReading = vi.fn()

    recallHookMock.mockReturnValue({
      recall: "Nora makes it through the Ember Gate and starts to suspect the archivist.",
      lastChapter: 4,
      show: true,
      dismiss,
    })

    const view = renderReaderOverview({ onContinueReading })

    expect(view.textContent).toContain("Story So Far")
    expect(view.textContent).toContain("Nora makes it through the Ember Gate")
    expect(view.textContent).toContain("Last active chapter: 4")

    const dismissButton = Array.from(view.querySelectorAll("button")).find((button) => button.textContent?.trim() === "Dismiss")
    expect(dismissButton).not.toBeNull()

    act(() => {
      dismissButton?.dispatchEvent(new MouseEvent("click", { bubbles: true }))
    })

    expect(dismiss).toHaveBeenCalledOnce()

    const continueButton = Array.from(view.querySelectorAll("button")).find((button) => button.textContent?.trim() === "Continue Reading")
    expect(continueButton).not.toBeNull()

    act(() => {
      continueButton?.dispatchEvent(new MouseEvent("click", { bubbles: true }))
    })

    expect(onContinueReading).toHaveBeenCalledOnce()
  })

  it("does not render the story so far card when recall is unavailable", () => {
    recallHookMock.mockReturnValue({
      recall: null,
      lastChapter: null,
      show: false,
      dismiss: vi.fn(),
    })

    const view = renderReaderOverview()

    expect(view.textContent).not.toContain("Story So Far")
  })

  it("shows measured story-memory coverage without invented pulse scores", () => {
    recallHookMock.mockReturnValue({
      recall: null,
      lastChapter: null,
      show: false,
      dismiss: vi.fn(),
    })

    const view = renderReaderOverview()

    expect(view.textContent).toContain("Story Memory")
    expect(view.textContent).toContain("1 ready")
    expect(view.textContent).toContain("Not opened yet")
    expect(view.querySelector("details")?.hasAttribute("open")).toBe(true)
    expect(view.textContent).not.toContain("Story Pulse")
  })
  it("offers one chapter list and a labelled search that trims and encodes the query", () => {
    recallHookMock.mockReturnValue({ recall: null, show: false, dismiss: vi.fn() })
    const onNavigate = vi.fn()
    const view = renderReaderOverview({ onNavigate })
    expect(view.querySelectorAll("h1")).toHaveLength(1)
    expect(Array.from(view.querySelectorAll("button")).filter((button) => button.textContent?.includes("Chapter 4"))).toHaveLength(1)
    const input = view.querySelector<HTMLInputElement>("#overview-book-search")!
    act(() => {
      Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set?.call(input, "  Nora & Tarin  ")
      input.dispatchEvent(new Event("input", { bubbles: true }))
    })
    act(() => { view.querySelector("form")?.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true })) })
    expect(onNavigate).toHaveBeenCalledWith("/book-1/search?q=Nora%20%26%20Tarin")
  })

  it("disables reading when there are no chapters and explains the empty state", () => {
    recallHookMock.mockReturnValue({ recall: null, show: false, dismiss: vi.fn() })
    const view = renderReaderOverview({ chapterList: { chapters: [], current_chapter: 1, read_upto: 0 } })
    const action = Array.from(view.querySelectorAll("button")).find((button) => button.textContent?.trim() === "Continue Reading")
    expect(action?.disabled).toBe(true)
    expect(view.textContent).toContain("no chapters yet")
  })

})

function renderReaderOverview({
  onContinueReading = vi.fn(),
  onNavigate = vi.fn(),
  progress,
  chapterList,
  summaryCollection,
  bookNotes = [],
  savedQuotes = [],
}: {
  onContinueReading?: () => void
  onNavigate?: (href: string) => void
  progress?: ReadingProgress | null
  chapterList?: ChapterListResponse | null
  summaryCollection?: SummaryCollectionResponse | null
  bookNotes?: BookNote[]
  savedQuotes?: SavedQuote[]
} = {}) {
  container = document.createElement("div")
  document.body.appendChild(container)
  root = createRoot(container)

  act(() => {
    root?.render(
      <ReaderOverview
        bookId="book-1"
        book={buildBook()}
        activeBookMode="reader"
        progress={progress ?? buildProgress()}
        chapterList={chapterList ?? buildChapterList()}
        summaryCollection={summaryCollection ?? buildSummaryCollection()}
        bookNotes={bookNotes}
        savedQuotes={savedQuotes}
        bookmark={null}
        isDark={false}
        modeSaving={false}
        canUseAuthorMode={true}
        onModeChange={() => {}}
        onToggleTheme={() => {}}
        onNavigate={onNavigate}
        onContinueReading={onContinueReading}
      />
    )
  })

  return container
}

function buildBook(): Book {
  return {
    id: "book-1",
    title: "The Ember Gate",
    status: "ready",
    author: "A. Writer",
    genre: "Fantasy",
    work_type: "novel",
    public_description: "A fantasy novel about secrets and thresholds.",
    created_at: "2026-05-01T00:00:00.000Z",
    progress_pct: 42,
    total_chapters: 12,
    total_words: 84000,
    total_tokens: null,
    format: "epub",
    cover_url: null,
  } as Book
}

function buildProgress(): ReadingProgress {
  return {
    current_chapter: 4,
    scroll_pct: 0.4,
    chapters_read_count: 4,
    percent_complete: 42,
    chapters_left: 8,
  }
}

function buildChapterList(): ChapterListResponse {
  return {
    read_upto: 4,
    current_chapter: 4,
    chapters: Array.from({ length: 8 }, (_, index) => ({
      number: index + 1,
      title: `Chapter ${index + 1}`,
      processed: true,
      read: index < 4,
    })),
  }
}

function buildSummaryCollection(): SummaryCollectionResponse {
  return {
    read_upto: 4,
    summaries: [
      {
        chapter_number: 1,
        chapter_title: "Chapter 1",
        read: true,
        available: true,
        content: "Summary",
        key_events: [{ event: "Nora meets the archivist.", importance: 1 }],
      },
    ],
  }
}
