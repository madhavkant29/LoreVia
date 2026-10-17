// @vitest-environment jsdom

import { act, type ReactElement, type ReactNode } from "react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const pushMock = vi.hoisted(() => vi.fn())
const replaceMock = vi.hoisted(() => vi.fn())
const booksApiMock = vi.hoisted(() => ({
  get: vi.fn(),
  getChapterReports: vi.fn(),
}))
const readerApiMock = vi.hoisted(() => ({
  getForeshadowing: vi.fn(),
  getChapterList: vi.fn(),
  getSummaryCollection: vi.fn(),
  getUpcomingBetaReads: vi.fn(),
  startBetaRead: vi.fn(),
}))
const captureMock = vi.hoisted(() => vi.fn())

vi.mock("next/link", () => ({
  default: ({
    children,
    href,
    prefetch: _prefetch,
    replace: _replace,
    scroll: _scroll,
    shallow: _shallow,
    locale: _locale,
    ...props
  }: {
    children: ReactNode
    href: string
    prefetch?: boolean | null
    replace?: boolean
    scroll?: boolean
    shallow?: boolean
    locale?: string | false
  }) => <a href={href} {...props}>{children}</a>,
}))

vi.mock("next/navigation", () => ({
  useParams: () => ({ bookId: "book-1" }),
  useRouter: () => ({ push: pushMock, replace: replaceMock }),
}))

vi.mock("@/lib/api/books", () => ({ booksApi: booksApiMock }))
vi.mock("@/lib/api/reader", () => ({ readerApi: readerApiMock }))
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
import { DAILY_CAP_EVENT } from "@/lib/limits/dailyCap"

let root: Root | null = null
let container: HTMLDivElement | null = null
let queryClient: QueryClient | null = null

;(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

beforeEach(() => {
  pushMock.mockReset()
  replaceMock.mockReset()
  captureMock.mockReset()
  Object.values(booksApiMock).forEach((mock) => mock.mockReset())
  Object.values(readerApiMock).forEach((mock) => mock.mockReset())
  readerApiMock.startBetaRead.mockResolvedValue({})
})

afterEach(() => {
  cleanupRenderedTree()
})

describe("previously uncovered runtime surfaces", () => {
  it("redirects the legacy chapter reports route into the Findings chapter view", async () => {
    await renderElement(<ChapterReportsPage />)
    await flushAsync()

    expect(container?.textContent).toContain("Opening chapter reports in Findings")
    expect(replaceMock).toHaveBeenCalledWith("/book-1/analysis?view=chapters")
  })

  it("redirects the legacy summaries route to the overview recap", async () => {
    await renderElement(<SummariesPage />)
    await flushAsync()

    expect(container?.textContent).toContain("Opening the overview recap")
    expect(replaceMock).toHaveBeenCalledWith("/book-1")
  })

  it("renders foreshadowing clues with described and sparse follow-through", async () => {
    readerApiMock.getChapterList.mockResolvedValue({ chapters: [{ number: 1 }, { number: 2 }] })
    readerApiMock.getForeshadowing.mockResolvedValue({
      items: [
        { chapter_number: 1, chapter_title: "Ash", clue: "A brass key", foreshadows: "The locked gate." },
        { chapter_number: 2, chapter_title: null, clue: "A broken sigil", foreshadows: null },
      ],
    })

    await renderElement(<ForeshadowingPage />)
    await flushAsync()

    expect(container?.textContent).toContain("Setup and payoff")
    expect(container?.textContent).toContain("The locked gate")
    expect(container?.textContent).toContain("No linked payoff yet")
  })

  it("retries setup failures without showing an empty ledger", async () => {
    readerApiMock.getForeshadowing.mockRejectedValueOnce(new Error("offline")).mockResolvedValue({ items: [] })
    await renderElement(<ForeshadowingPage />)
    await flushAsync()
    expect(container?.textContent).toContain("signals could not be loaded")
    expect(container?.textContent).not.toContain("No setup signals yet")
    await clickButton("Retry signals")
    await flushAsync()
    expect(container?.textContent).toContain("No setup signals yet")
    expect(container?.querySelector('a[href="/book-1/chapters"]')).not.toBeNull()
  })

  it("filters unlinked clues without confusing them with resolved outcomes", async () => {
    readerApiMock.getForeshadowing.mockResolvedValue({ items: [
      { chapter_number: 1, chapter_title: null, clue: "The key", foreshadows: "Gate" },
      { chapter_number: 0, chapter_title: null, clue: "The bell", foreshadows: " " },
    ] })
    readerApiMock.getChapterList.mockResolvedValue({ chapters: [{ number: 1 }] })
    await renderElement(<ForeshadowingPage />)
    await flushAsync()
    await clickButton("Unlinked")
    expect(container?.textContent).toContain("The bell")
    expect(container?.textContent).not.toContain("The key")
    expect(container?.textContent).toContain("Chapter not located")
    await clickButton("Clear filters")
    expect(container?.textContent).toContain("The key")
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
    await clickButton("Continue later")

    await act(async () => {
      window.dispatchEvent(
        new CustomEvent(DAILY_CAP_EVENT, {
          detail: {
            action: "high_cost_authoring",
            detail:
              "You've reached your daily limit of 60 Story Advisor turns. It refreshes tomorrow.",
          },
        }),
      )
      await Promise.resolve()
    })
    expect(container?.textContent).toContain("daily limit of 60 Story Advisor turns")
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
