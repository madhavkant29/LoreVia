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
  default: ({ children, href, prefetch: _prefetch, ...props }: { children: ReactNode; href: string; prefetch?: boolean | null }) => <a href={href} {...props}>{children}</a>,
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
  useAuthStore: (selector: (state: { hydrated: boolean; user: { id: string; tier: string } | null }) => unknown) => selector({ hydrated: true, user: { id: "user-1", tier: "pro" } }),
}))

vi.mock("@/lib/api/reader", () => ({ readerApi: { getChapterList: async () => ({ chapters: [{ number: 2, title: "Ash Road" }] }) } }))

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
    await new Promise((resolve) => setTimeout(resolve, 0))
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
  window.history.replaceState({}, "", "/")
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
  it("opens recommended checks from a project overview deep link", async () => {
    window.history.replaceState({}, "", "/book-1/advisor?tab=scan")
    renderPage()
    await flushUi()
    await flushUi()

    expect(container?.querySelector("#advisor-tab-scan")?.getAttribute("aria-selected")).toBe("true")
    expect(container?.querySelector("#advisor-scan-panel")?.hasAttribute("hidden")).toBe(false)
  })
  it("preserves existing hidden checks when adopting account-specific storage", async () => {
    localStorage.setItem("lorevia-advisor-scan:book-1", JSON.stringify({ dismissed: ["scan-1"], intentional: [] }))
    renderPage()
    await flushUi(); await flushUi()
    clickByText("Recommended checks")
    await flushUi()
    expect(container?.textContent).toContain("All current checks are hidden")
    expect(JSON.parse(localStorage.getItem("lorevia-advisor-scan:user-1:book-1") || "{}").dismissed).toEqual(["scan-1"])
    clickByText("Restore all hidden checks")
    await flushUi()
    expect(JSON.parse(localStorage.getItem("lorevia-advisor-scan:user-1:book-1") || "{}").dismissed).toEqual([])
  })
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

    expect(container?.textContent).toContain("Ask advisor")
    expect(container?.textContent).toContain("Recommended checks")
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

    expect(container?.textContent).toContain("heuristic finding")
    expect(container?.textContent).toContain("Fallback analysis")
    expect(container?.textContent).toContain("Editorial focus pass")
    expect(container?.textContent).toContain("Find the best pressure point")
  })

  it("shows verified scan evidence and partial AI audit coverage", async () => {
    advisorSuggestionsMock.mockResolvedValue({
      suggestions: [{
        id: "proactive-1", type: "event_conflict", severity: "warning",
        title: "Bridge timing", description: "Check the bridge sequence.",
        evidence_excerpt: "The bridge remained open until dawn.",
        chapter_ref: 2, action_label: "Trace bridge", ask_prompt: "When did it close?",
        source: "proactive_audit",
      }],
      total: 1, book_title: "The Ember Gate",
      meta: {
        character_count: 3, state_count: 0, open_thread_count: 1,
        clue_count: 0, relationship_count: 0, world_element_count: 0,
        heuristic_count: 0, fallback_applied: false, proactive_audit_applied: true,
        scan_basis: ["plot threads"], data_gaps: [],
        audit_summary: "AI audit completed 2 of 3 evidence groups.",
        audit_failure_category: "invalid_ai_response",
        audit_groups_total: 3, audit_groups_completed: 2,
      },
    })

    renderPage()
    await flushUi()
    await flushUi()
    clickByText("Recommended checks")
    await flushUi()

    expect(container?.textContent).toContain("The bridge remained open until dawn.")
    expect(container?.textContent).toContain("AI evidence groups reviewed: 2/3")
    expect(container?.textContent).toContain("incomplete or unverified evidence")
  })

  it("shows legacy checks with unsupported priorities instead of silently hiding them", async () => {
    advisorSuggestionsMock.mockResolvedValue({
      suggestions: [
        {
          id: "legacy-1", type: "event_conflict", severity: "high",
          title: "Legacy bridge check", description: "The bridge timing needs review.",
          chapter_ref: 2, action_label: "Trace bridge", ask_prompt: "When did it close?",
          source: "proactive_audit",
        },
        {
          id: "current-1", type: "event_conflict", severity: "warning",
          title: "Current bridge check", description: "The bridge is still open.",
          chapter_ref: 2, action_label: "Trace bridge", ask_prompt: "Is it open?",
          source: "proactive_audit",
        },
      ],
      total: 2, book_title: "The Ember Gate", meta: suggestionsMeta(),
    })

    renderPage()
    await flushUi()
    await flushUi()
    clickByText("Recommended checks")
    await flushUi()

    expect(container?.textContent).toContain("Legacy bridge check")
    expect(container?.textContent).toContain("Current bridge check")
    expect(container?.textContent).toContain("unrecognized priority from an earlier scan")
  })

  it.each([
    [null, true, "No supported checks were found in the reviewed evidence"],
    ["ai_unavailable", false, "The AI audit did not finish"],
    [null, false, "No supported checks are available from the extracted evidence yet"],
  ] as const)("distinguishes empty recommended-check states", async (failure, applied, expected) => {
    advisorSuggestionsMock.mockResolvedValue({
      suggestions: [], total: 0, book_title: "The Ember Gate",
      meta: {
        character_count: 0, state_count: 0, open_thread_count: 0,
        clue_count: 0, relationship_count: 0, world_element_count: 0,
        heuristic_count: 0, fallback_applied: false, proactive_audit_applied: applied,
        scan_basis: [], data_gaps: ["characters"], audit_summary: null,
        audit_failure_category: failure, audit_groups_total: failure || applied ? 1 : 0,
        audit_groups_completed: applied ? 1 : 0,
      },
    })

    renderPage()
    await flushUi()
    await flushUi()
    clickByText("Recommended checks")
    await flushUi()

    expect(container?.textContent).toContain(expected)
  })

  it.each([
    ["budget_exhausted", "Monthly AI budget reached", "monthly reset"],
    ["capacity_busy", "AI processing slots are temporarily busy", "Refresh checks shortly"],
  ] as const)("shows actionable Advisor audit status for %s", async (failure, label, nextStep) => {
    advisorSuggestionsMock.mockResolvedValue({
      suggestions: [], total: 0, book_title: "The Ember Gate",
      meta: {
        character_count: 0, state_count: 0, open_thread_count: 0,
        clue_count: 0, relationship_count: 0, world_element_count: 0,
        heuristic_count: 0, fallback_applied: false, proactive_audit_applied: false,
        scan_basis: [], data_gaps: [], audit_summary: null,
        audit_failure_category: failure, audit_groups_total: 1, audit_groups_completed: 0,
      },
    })

    renderPage()
    await flushUi()
    await flushUi()
    clickByText("Recommended checks")
    await flushUi()

    expect(container?.textContent).toContain(label)
    expect(container?.textContent).toContain(nextStep)
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

    clickByText("Recommended checks")
    await flushUi()
    expect(container?.textContent).toContain("Lantern timeline conflict")
    expect(container?.textContent).toContain("Proactive audit included")

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
    expect(window.localStorage.getItem("lorevia-advisor-scan:user-1:book-1")).toContain("warn-1")

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

    clickByText("Recommended checks")
    clickByText("Refresh checks")
    await flushUi()
    expect(advisorSuggestionsScanMock).toHaveBeenCalledWith("book-1")
    expect(advisorSuggestionsMock).toHaveBeenCalled()

    setFieldValue(advisorInput, "A fresh question")
    expect(advisorInput.value).toBe("A fresh question")
  })
})
