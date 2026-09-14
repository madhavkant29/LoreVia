// @vitest-environment jsdom

import { act } from "react"
import type { ReactNode } from "react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const getBookMock = vi.hoisted(() => vi.fn())
const advisorGreetingMock = vi.hoisted(() => vi.fn())
const advisorSuggestionsMock = vi.hoisted(() => vi.fn())
const advisorSuggestionsScanMock = vi.hoisted(() => vi.fn())
const advisorSuggestionsJobStatusMock = vi.hoisted(() => vi.fn())
const advisorMessageStreamMock = vi.hoisted(() => vi.fn())
const saveContextualVaultNoteMock = vi.hoisted(() => vi.fn())

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
    advisorSuggestionsScan: (...args: unknown[]) => advisorSuggestionsScanMock(...args),
    advisorSuggestionsJobStatus: (...args: unknown[]) => advisorSuggestionsJobStatusMock(...args),
    advisorMessageStream: (...args: unknown[]) => advisorMessageStreamMock(...args),
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
  saveContextualVaultNote: (...args: unknown[]) => saveContextualVaultNoteMock(...args),
}))

import AdvisorPage from "./page"

let container: HTMLDivElement | null = null
let root: Root | null = null
let queryClient: QueryClient | null = null

;(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
Element.prototype.scrollIntoView = vi.fn()

const localStore: Record<string, string> = {}
const localStorageMock = {
  get length() {
    return Object.keys(localStore).length
  },
  clear: vi.fn(() => {
    Object.keys(localStore).forEach((key) => delete localStore[key])
  }),
  getItem: vi.fn((key: string) => localStore[key] ?? null),
  key: vi.fn((index: number) => Object.keys(localStore)[index] ?? null),
  removeItem: vi.fn((key: string) => {
    delete localStore[key]
  }),
  setItem: vi.fn((key: string, value: string) => {
    localStore[key] = value
  }),
}
vi.stubGlobal("localStorage", localStorageMock)

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

function clickByText(text: string, index = 0) {
  const matches = Array.from(container?.querySelectorAll("button, a") ?? []).filter((element) =>
    element.textContent?.includes(text)
  )
  const match = matches[index] as HTMLElement | undefined
  expect(match, `Expected ${text}`).toBeTruthy()
  act(() => {
    match?.click()
  })
  return match
}

function setFieldValue(field: HTMLTextAreaElement, value: string) {
  const descriptor = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")
  act(() => {
    descriptor?.set?.call(field, value)
    field.dispatchEvent(new Event("input", { bubbles: true }))
  })
}

function suggestionsMeta(overrides: Record<string, unknown> = {}) {
  return {
    character_count: 3,
    state_count: 2,
    open_thread_count: 1,
    clue_count: 4,
    relationship_count: 2,
    world_element_count: 5,
    heuristic_count: 4,
    fallback_applied: true,
    proactive_audit_applied: true,
    scan_basis: ["characters", "plot threads", "world elements"],
    data_gaps: ["timeline"],
    audit_summary: "Audit found several setup opportunities.",
    ...overrides,
  }
}

beforeEach(() => {
  getBookMock.mockReset()
  advisorGreetingMock.mockReset()
  advisorSuggestionsMock.mockReset()
  advisorSuggestionsScanMock.mockReset()
  advisorSuggestionsJobStatusMock.mockReset()
  advisorMessageStreamMock.mockReset()
  saveContextualVaultNoteMock.mockReset()
  window.localStorage.clear()

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
  advisorSuggestionsScanMock.mockResolvedValue({ job_id: "scan-job-1", cached: true })
  advisorSuggestionsJobStatusMock.mockResolvedValue({ status: "complete", result: null })
  advisorMessageStreamMock.mockImplementation(async (_bookId, _messages, callbacks) => {
    callbacks?.onDelta?.("Opportunity: ")
    callbacks?.onDelta?.("seed the lantern earlier.")
    return {
      reply: "Opportunity: seed the lantern earlier.\nOption A: make it a relic.",
      response_type: "opportunity",
      retrieved_passages: [
        {
          chapter_num: 2,
          chapter_title: "Ash Road",
          excerpt: "Mara hides the lantern under her coat.",
          relevance: 0.91,
        },
      ],
      world_analysis: {
        mode: "story_integration",
        answer: "The lantern can connect to the Aster Sea rule.",
        logic_alerts: [{ title: "Lantern rule", description: "Define the cost." }],
        suggestions: [{ title: "Seed a warning", description: "Mention the old sailor." }],
        citations: [{ title: "World Bible" }],
      },
    }
  })
  saveContextualVaultNoteMock.mockResolvedValue({})
})

afterEach(() => {
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

describe("AdvisorPage", () => {
  it("renders the accessible mode toggle and preserved notes link", async () => {
    advisorSuggestionsMock.mockResolvedValue({
      suggestions: [],
      total: 0,
      book_title: "The Ember Gate",
      meta: {
        character_count: 3,
        state_count: 0,
        open_thread_count: 0,
        clue_count: 0,
        relationship_count: 0,
        world_element_count: 0,
        heuristic_count: 0,
        fallback_applied: false,
        proactive_audit_applied: false,
        scan_basis: [],
        data_gaps: [],
        audit_summary: null,
      },
    })
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

  it("drives scan card actions, cached scan refresh, note saving, and advisor chat", async () => {
    advisorSuggestionsMock.mockResolvedValue({
      suggestions: [
        {
          id: "warn-1",
          type: "contradiction",
          severity: "warning",
          title: "Lantern timeline conflict",
          description: "The lantern is broken after it is used.",
          chapter_ref: 2,
          action_label: "Fix lantern conflict",
          ask_prompt: "How do I fix the lantern conflict?",
          source: "heuristic",
        },
        {
          id: "dir-1",
          type: "future_direction",
          severity: "direction",
          title: "Choose a betrayal direction",
          description: "The next arc needs a clearer cost.",
          chapter_ref: null,
          action_label: "Compare directions",
          ask_prompt: "Which betrayal direction fits?",
          source: "proactive_audit",
        },
        {
          id: "opp-1",
          type: "foreshadowing",
          severity: "opportunity",
          title: "Foreshadow the Aster Sea",
          description: "A sailor warning could pay off later.",
          chapter_ref: 4,
          action_label: "Plan foreshadowing",
          ask_prompt: "Plan the Aster Sea foreshadowing.",
          source: "fallback",
        },
        {
          id: "info-1",
          type: "info",
          severity: "info",
          title: "Track the oath",
          description: "The oath appears in two chapters.",
          chapter_ref: 1,
          action_label: "Explain the oath",
          ask_prompt: "Explain the oath thread.",
          source: "heuristic",
        },
      ],
      total: 4,
      book_title: "The Ember Gate",
      meta: suggestionsMeta(),
    })

    renderPage()
    await flushUi()
    await flushUi()

    expect(container?.textContent).toContain("Lantern timeline conflict")
    expect(container?.textContent).toContain("Proactive audit added")

    clickByText("Save note")
    await flushUi()
    expect(saveContextualVaultNoteMock).toHaveBeenCalledWith(expect.objectContaining({
      bookId: "book-1",
      context: "story_advisor",
      folderSegments: ["Chapter 2"],
    }))

    clickByText("Mark as intentional")
    await flushUi()
    expect(container?.textContent).toContain("Intentional choices")

    clickByText("Dismiss")
    await flushUi()
    expect(window.localStorage.getItem("lorevia-advisor-scan:book-1")).toContain("warn-1")

    clickByText("Plan foreshadowing")
    await flushUi()
    const checkerTab = container?.querySelector("#advisor-tab-chat")
    expect(checkerTab?.getAttribute("aria-selected")).toBe("true")
    const advisorInput = container?.querySelector('textarea[aria-label="Advisor question"]') as HTMLTextAreaElement
    expect(advisorInput.value).toBe("Plan the Aster Sea foreshadowing.")

    clickByText("Send")
    await flushUi()
    await flushUi()
    expect(advisorMessageStreamMock).toHaveBeenCalled()
    expect(container?.textContent).toContain("seed the lantern earlier")
    expect(container?.textContent).toContain("Mara hides the lantern")
    expect(container?.textContent).toContain("The lantern can connect")

    clickByText("Save to notes")
    await flushUi()
    expect(saveContextualVaultNoteMock).toHaveBeenCalledWith(expect.objectContaining({
      title: "Advisor insight",
      folderSegments: [],
    }))

    clickByText("Continuity Scan")
    clickByText("Check Story Health")
    await flushUi()
    expect(advisorSuggestionsScanMock).toHaveBeenCalledWith("book-1")
    expect(advisorSuggestionsMock).toHaveBeenCalled()

    setFieldValue(advisorInput, "A fresh question")
    expect(advisorInput.value).toBe("A fresh question")
  })
})
