// @vitest-environment jsdom

import { act } from "react"
import type { ReactNode } from "react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const getBookMock = vi.hoisted(() => vi.fn())
const advisorGreetingMock = vi.hoisted(() => vi.fn())
const advisorSuggestionsMock = vi.hoisted(() => vi.fn())

vi.mock("next/link", () => ({
  default: ({ children, href, ...props }: { children: ReactNode; href: string }) => <a href={href} {...props}>{children}</a>,
}))

vi.mock("next/dynamic", () => ({
  default: () => () => <div data-testid="editorial-panel" />,
}))

vi.mock("next/navigation", () => ({
  useParams: () => ({ bookId: "book-1" }),
}))

vi.mock("@/lib/api/books", () => ({
  booksApi: {
    get: (...args: unknown[]) => getBookMock(...args),
  },
}))

vi.mock("@/lib/api/intelligence", () => ({
  intelligenceApi: {
    advisorGreeting: (...args: unknown[]) => advisorGreetingMock(...args),
    advisorSuggestions: (...args: unknown[]) => advisorSuggestionsMock(...args),
  },
}))

vi.mock("@/lib/stores/preferencesStore", () => ({
  usePreferencesStore: () => ({ theme: "dark" }),
}))

vi.mock("@/lib/stores/authStore", () => ({
  useAuthStore: (selector: (state: { user: { tier: string } | null }) => unknown) => selector({ user: { tier: "pro" } }),
}))

vi.mock("@/lib/billing/plans", () => ({
  canUseAuthorFeatures: () => true,
}))

vi.mock("@/lib/analytics/posthog", () => ({
  capture: vi.fn(),
}))

vi.mock("@/lib/utils/notes", () => ({
  saveContextualVaultNote: vi.fn(),
}))

import AdvisorPage from "./page"

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
        <AdvisorPage />
      </QueryClientProvider>,
    )
  })
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
  advisorGreetingMock.mockReset()
  advisorSuggestionsMock.mockReset()

  getBookMock.mockResolvedValue({
    id: "book-1",
    title: "The Ember Gate",
    mode: "author",
  })

  advisorGreetingMock.mockResolvedValue({
    message: "What aspect of your story feels unsolved right now?",
    book_title: "The Ember Gate",
    stats: {
      characters: 3,
      plot_threads: 0,
      total_chapters: 3,
    },
  })

  advisorSuggestionsMock.mockResolvedValue({
    suggestions: [
      {
        id: "scan-1",
        type: "editorial_focus",
        severity: "opportunity",
        title: "Editorial focus pass",
        description: "A focused pass can surface weak setup and underused foreshadowing.",
        chapter_ref: 3,
        action_label: "Find the best pressure point",
        ask_prompt: "Find the best pressure point",
        source: "fallback",
      },
    ],
    total: 1,
    book_title: "The Ember Gate",
    meta: {
      character_count: 3,
      state_count: 0,
      open_thread_count: 0,
      clue_count: 0,
      relationship_count: 0,
      world_element_count: 0,
      heuristic_count: 1,
      fallback_applied: true,
      proactive_audit_applied: false,
      scan_basis: ["characters", "plot threads"],
      data_gaps: [],
      audit_summary: null,
    },
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

describe("AdvisorPage", () => {
  it("renders the accessible mode toggle and preserved notes link", async () => {
    renderPage()
    await flushUi()
    await flushUi()

    const tabs = container?.querySelectorAll('[role="tab"]') ?? []
    expect(tabs).toHaveLength(2)

    const checkerTab = container?.querySelector("#advisor-tab-chat")
    const scanTab = container?.querySelector("#advisor-tab-scan")
    expect(checkerTab?.getAttribute("aria-selected")).toBe("true")
    expect(scanTab?.getAttribute("aria-selected")).toBe("false")

    const notesLink = Array.from(container?.querySelectorAll("a") ?? []).find((link) => link.textContent?.includes("Open notes workspace"))
    expect(notesLink?.getAttribute("href")).toBe("/book-1/notes")
  })

  it("switches to continuity scan and renders heuristic summary data", async () => {
    renderPage()
    await flushUi()
    await flushUi()

    const scanTab = container?.querySelector("#advisor-tab-scan")
    expect(scanTab).toBeTruthy()

    await act(async () => {
      scanTab?.dispatchEvent(new MouseEvent("click", { bubbles: true }))
      await Promise.resolve()
    })

    expect(container?.textContent).toContain("Heuristic Summary")
    expect(container?.textContent).toContain("Fallback Cards")
    expect(container?.textContent).toContain("Editorial focus pass")
    expect(container?.textContent).toContain("Find the best pressure point")
  })
})
