// @vitest-environment jsdom

import { act, type ReactElement, type ReactNode } from "react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const pushMock = vi.hoisted(() => vi.fn())
const booksApiMock = vi.hoisted(() => ({
  get: vi.fn(),
  getChapterReports: vi.fn(),
}))
const readerApiMock = vi.hoisted(() => ({
  getForeshadowing: vi.fn(),
  getSummaryCollection: vi.fn(),
  getUpcomingBetaReads: vi.fn(),
  startBetaRead: vi.fn(),
}))
const publicApiMock = vi.hoisted(() => ({
  getChapter: vi.fn(),
  trackView: vi.fn(),
}))
const captureMock = vi.hoisted(() => vi.fn())

vi.mock("next/link", () => ({
  default: ({ children, href, ...props }: { children: ReactNode; href: string }) => <a href={href} {...props}>{children}</a>,
}))

vi.mock("next/navigation", () => ({
  useParams: () => ({ bookId: "book-1" }),
  useRouter: () => ({ push: pushMock }),
}))

vi.mock("@/lib/api/books", () => ({ booksApi: booksApiMock }))
vi.mock("@/lib/api/reader", () => ({ readerApi: readerApiMock }))
vi.mock("@/lib/api/public", () => ({ publicApi: publicApiMock }))
vi.mock("@/lib/analytics/posthog", () => ({ capture: captureMock }))
vi.mock("@/lib/stores/authStore", () => ({
  useAuthStore: (selector: (state: { user: { id: string } }) => unknown) => selector({ user: { id: "user-1" } }),
}))
vi.mock("@/lib/stores/preferencesStore", () => ({
  usePreferencesStore: (selector?: (state: { theme: "dark" }) => unknown) => {
    const state = { theme: "dark" as const }
    return typeof selector === "function" ? selector(state) : state
  },
}))

import ChapterReportsPage from "@/app/(reader)/[bookId]/reports/page"
import SummariesPage from "@/app/(reader)/[bookId]/summaries/page"
import ForeshadowingPage from "@/app/(reader)/[bookId]/foreshadowing/page"
import { UpcomingBetaReadsCard } from "@/components/library/UpcomingBetaReadsCard"
import { DailyCapPrompt } from "@/components/limits/DailyCapPrompt"
import { ChaptersPageHeader } from "@/components/reader/ChaptersPageHeader"
import { ReaderQuickRail } from "@/components/reader/ReaderQuickRail"
import { PublicChapterPageClient } from "@/components/public/PublicChapterPageClient"
import { DAILY_CAP_EVENT } from "@/lib/limits/dailyCap"

let root: Root | null = null
let container: HTMLDivElement | null = null
let queryClient: QueryClient | null = null

;(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

beforeEach(() => {
  pushMock.mockReset()
  captureMock.mockReset()
  Object.values(booksApiMock).forEach((mock) => mock.mockReset())
  Object.values(readerApiMock).forEach((mock) => mock.mockReset())
  Object.values(publicApiMock).forEach((mock) => mock.mockReset())
  readerApiMock.startBetaRead.mockResolvedValue({})
  publicApiMock.trackView.mockResolvedValue({})
})

afterEach(() => {
  cleanupRenderedTree()
})

describe("previously uncovered runtime surfaces", () => {
  it("renders chapter reports with populated and empty report groups", async () => {
    booksApiMock.getChapterReports.mockResolvedValue([
      {
        chapter_number: 3,
        chapter_title: "The Gate",
        summary: "Mara opens the gate and changes her alliance.",
        new_characters: [{ name: "Theo" }],
        relationship_changes: ["Mara now trusts Theo"],
        plot_threads_opened: ["The brass key"],
        plot_threads_resolved: [],
        continuity_flags: ["The key changed color"],
      },
    ])

    await renderElement(<ChapterReportsPage />)
    await flushAsync()

    expect(container?.textContent).toContain("Chapter reports")
    expect(container?.textContent).toContain("Mara now trusts Theo")
    expect(container?.textContent).toContain("No threads resolved")
    expect(container?.textContent).toContain("The key changed color")
    expect(captureMock).toHaveBeenCalledWith("author_reports_opened", { book_id: "book-1" })
  })

  it("renders author summaries with available and pending chapter states", async () => {
    booksApiMock.get.mockResolvedValue({ id: "book-1", mode: "author" })
    readerApiMock.getSummaryCollection.mockResolvedValue({
      read_upto: 4,
      summaries: [
        { chapter_number: 3, chapter_title: "The Gate", available: true, content: "Mara opens the gate." },
        { chapter_number: 4, chapter_title: null, available: false, content: null },
      ],
    })

    await renderElement(<SummariesPage />)
    await flushAsync()

    expect(container?.textContent).toContain("Chapter summaries")
    expect(container?.textContent).toContain("Available")
    expect(container?.textContent).toContain("Pending")
    expect(container?.textContent).toContain("Summary not available yet for this processed chapter")
  })

  it("renders foreshadowing clues with described and sparse follow-through", async () => {
    readerApiMock.getForeshadowing.mockResolvedValue({
      items: [
        { chapter_number: 1, chapter_title: "Ash", clue: "A brass key", foreshadows: "The locked gate." },
        { chapter_number: 2, chapter_title: null, clue: "A broken sigil", foreshadows: null },
      ],
    })

    await renderElement(<ForeshadowingPage />)
    await flushAsync()

    expect(container?.textContent).toContain("Foreshadowing signals")
    expect(container?.textContent).toContain("The locked gate")
    expect(container?.textContent).toContain("follow-through description is still sparse")
  })

  it("starts an upcoming beta read and reports the loaded assignment count", async () => {
    const onCountChange = vi.fn()
    readerApiMock.getUpcomingBetaReads.mockResolvedValue([
      {
        id: "assignment-1",
        book_id: "book-1",
        task_label: "Read the opening",
        author_name: "Ada",
        primary_action: "Start",
        expires_at: "2099-01-01T00:00:00Z",
        progress_pct: 0,
        current_chapter: 2,
        chapter_start: 1,
      },
    ])

    await renderElement(<UpcomingBetaReadsCard isDark onCountChange={onCountChange} />)
    await flushAsync()
    await clickButton("Start")

    expect(container?.textContent).toContain("Read the opening - Ada")
    expect(readerApiMock.startBetaRead).toHaveBeenCalledWith("assignment-1")
    expect(pushMock).toHaveBeenCalledWith("/book-1/chapter/2")
    expect(onCountChange).toHaveBeenCalledWith(1, true)
    await clickButton("View all beta reads")
    expect(pushMock).toHaveBeenCalledWith("/beta-reads")
  })

  it("opens and closes daily-cap prompts and navigates to pricing", async () => {
    await renderElement(<DailyCapPrompt />)

    await act(async () => {
      window.dispatchEvent(new CustomEvent(DAILY_CAP_EVENT, { detail: { action: "search" } }))
      await Promise.resolve()
    })
    expect(container?.textContent).toContain("today's search cap")
    await clickButton("Continue later")
    expect(container?.textContent).not.toContain("Daily cap reached")

    await act(async () => {
      window.dispatchEvent(new CustomEvent(DAILY_CAP_EVENT, { detail: { action: "high_cost_authoring" } }))
      await Promise.resolve()
    })
    expect(container?.textContent).toContain("today's authoring cap")
    await clickButton("View pricing")
    expect(pushMock).toHaveBeenCalledWith("/upgrade")
  })

  it("renders quick-reader and chapter-header controls", async () => {
    const onSummary = vi.fn()
    const onBack = vi.fn()
    const onPrimaryAction = vi.fn()

    await renderElement(
      <>
        <ReaderQuickRail bookId="book-1" chapterNum={5} theme="dark" onSummary={onSummary} />
        <ChaptersPageHeader
          title="The Ember Gate"
          subtitle="Manage the manuscript chapters."
          processedCount={4}
          totalCount={6}
          isDark
          backLabel="Back to library"
          primaryActionLabel="Process chapters"
          primaryActionBusyLabel="Processing"
          primaryActionBusy={false}
          onBack={onBack}
          onPrimaryAction={onPrimaryAction}
        />
      </>,
    )

    expect(container?.textContent).toContain("Chapter 5")
    expect(container?.textContent).toContain("4 / 6")
    expect(container?.querySelector('a[aria-label="Graph"]')?.getAttribute("href")).toBe("/book-1/graph")
    await clickButton("Open summary", true)
    await clickButton("Back to library")
    await clickButton("Process chapters")
    expect(onSummary).toHaveBeenCalled()
    expect(onBack).toHaveBeenCalled()
    expect(onPrimaryAction).toHaveBeenCalled()
  })

  it("renders public chapter content, navigation, tracking, and unavailable states", async () => {
    const chapter = {
      book_id: "book-1",
      chapter_number: 2,
      chapter_title: "The Gate",
      chapter_description: "Mara reaches the sealed gate.",
      html_content: "<p>The brass key turned.</p>",
      text_content: null,
      text_url: null,
      total_chapters: 4,
    }
    publicApiMock.getChapter.mockResolvedValue(chapter)

    await renderElement(<PublicChapterPageClient bookId="book-1" chapterId="2" initialChapter={chapter as never} />)
    await flushAsync()

    expect(container?.textContent).toContain("The Gate")
    expect(container?.textContent).toContain("The brass key turned")
    expect(container?.textContent).toContain("Previous chapter")
    expect(container?.textContent).toContain("Next chapter")
    expect(publicApiMock.trackView).toHaveBeenCalledWith("book-1", { eventType: "chapter_view", chapterNumber: 2 })

    cleanupRenderedTree()
    await renderElement(<PublicChapterPageClient bookId="book-1" chapterId="bad" />)
    await flushAsync()
    expect(container?.textContent).toContain("This chapter is not available")
  })
})

async function renderElement(element: ReactElement) {
  container = document.createElement("div")
  document.body.appendChild(container)
  root = createRoot(container)
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  queryClient = client
  await act(async () => {
    root?.render(<QueryClientProvider client={client}>{element}</QueryClientProvider>)
    await Promise.resolve()
  })
}

function cleanupRenderedTree() {
  if (root) {
    act(() => {
      root?.unmount()
    })
  }
  queryClient?.clear()
  container?.remove()
  document.body.innerHTML = ""
  root = null
  container = null
  queryClient = null
}

async function flushAsync() {
  await act(async () => {
    await Promise.resolve()
    await Promise.resolve()
    await new Promise((resolve) => window.setTimeout(resolve, 0))
  })
}

async function clickButton(text: string, useAriaLabel = false) {
  const button = Array.from(container?.querySelectorAll("button") ?? []).find((node) =>
    useAriaLabel ? node.getAttribute("aria-label") === text : node.textContent?.includes(text),
  )
  expect(button, `button containing ${text}`).toBeTruthy()
  await act(async () => {
    button?.dispatchEvent(new MouseEvent("click", { bubbles: true }))
    await Promise.resolve()
  })
}
