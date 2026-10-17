// @vitest-environment jsdom

import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { act, type ReactNode } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import type { BetaReaderReport } from "@/types/intelligence"

const getBookMock = vi.hoisted(() => vi.fn())
const getCharactersMock = vi.hoisted(() => vi.fn())
const getChapterListMock = vi.hoisted(() => vi.fn())
const getReportsMock = vi.hoisted(() => vi.fn())
const runBetaReaderMock = vi.hoisted(() => vi.fn())
const getJobMock = vi.hoisted(() => vi.fn())
const createTaskMock = vi.hoisted(() => vi.fn())
const saveNoteMock = vi.hoisted(() => vi.fn())
const captureMock = vi.hoisted(() => vi.fn())

vi.mock("next/link", () => ({
  default: ({ children, href, prefetch: _prefetch, ...props }: { children: ReactNode; href: string; prefetch?: boolean | null }) => <a href={href} {...props}>{children}</a>,
}))

vi.mock("next/navigation", () => ({ useParams: () => ({ bookId: "book-1" }) }))
vi.mock("@/lib/api/books", () => ({
  booksApi: {
    get: (...args: unknown[]) => getBookMock(...args),
    getCharacters: (...args: unknown[]) => getCharactersMock(...args),
  },
}))
vi.mock("@/lib/api/reader", () => ({
  readerApi: { getChapterList: (...args: unknown[]) => getChapterListMock(...args) },
}))
vi.mock("@/lib/api/intelligence", () => ({
  intelligenceApi: {
    getBetaReaderReports: (...args: unknown[]) => getReportsMock(...args),
    runBetaReader: (...args: unknown[]) => runBetaReaderMock(...args),
    getBetaReaderJob: (...args: unknown[]) => getJobMock(...args),
    createBetaReaderRevisionTask: (...args: unknown[]) => createTaskMock(...args),
  },
}))
vi.mock("@/lib/utils/notes", () => ({
  saveContextualVaultNote: (...args: unknown[]) => saveNoteMock(...args),
}))
vi.mock("@/lib/analytics/posthog", () => ({ capture: (...args: unknown[]) => captureMock(...args) }))
vi.mock("@/lib/stores/authStore", () => ({
  useAuthStore: (selector: (state: { user: { tier: string } }) => unknown) => selector({ user: { tier: "author" } }),
}))
vi.mock("@/lib/stores/preferencesStore", () => ({ usePreferencesStore: () => ({ theme: "light" }) }))

import AiBetaReaderPage from "./page"

const report: BetaReaderReport = {
  report_id: "report-1",
  scope: "chapter",
  request_hash: "request",
  source_fingerprint: "source",
  created_at: "2026-08-30T10:00:00Z",
  is_stale: true,
  checks: ["repetition", "voice", "reader_feedback"],
  coverage: {
    requested_chapters: [1],
    analyzed_chapters: [1],
    missing_chapters: [],
    word_count: 900,
    character_count: 2,
  },
  overall_impression: "The opening creates immediate tension.",
  reader_vibe: "Gothic mystery with a tense, intimate opening.",
  story_understanding: "Mara is deciding whether to enter a locked house that already knows her.",
  strengths: ["Strong setting"],
  reader_questions: ["Who locked the gate?"],
  prioritized_revisions: ["Vary the threshold image."],
  overused_terms: [{
    id: "term-1",
    term: "silver moon",
    kind: "phrase",
    count: 4,
    rate_per_1000: 4.44,
    narration_count: 3,
    dialogue_count: 1,
    burst_detected: true,
    chapter_counts: { "1": 4 },
    evidence: [{ chapter_number: 1, excerpt: "The silver moon crossed the gate." }],
  }],
  character_voices: [{
    id: "voice-1",
    character_id: "char-1",
    character_name: "Mara",
    distinctness_score: 42,
    confidence: "high",
    sample_dialogue_count: 18,
    sample_word_count: 360,
    closest_character_id: "char-2",
    closest_character_name: "Ivo",
    similarity_score: 58,
    signals: { avg_sentence_length: 12 },
    shared_signals: ["sentence length", "formality"],
    shared_phrases: ["all right"],
  }],
  findings: [{
    id: "finding-1",
    category: "pacing",
    severity: "high",
    title: "The reveal pauses",
    description: "The reader waits too long for the door to open.",
    chapter_number: 1,
    evidence: [{ chapter_number: 1, excerpt: "She waited at the gate." }],
    recommendation: "Compress the exchange.",
    reader_question: "What is Mara waiting for?",
  }],
  revision_candidates: [{
    id: "candidate-1",
    source_item_id: "finding-1",
    category: "pacing",
    severity: "high",
    title: "Compress the gate exchange",
    description: "The reveal loses momentum.",
    recommendation: "Move the reaction before the explanation.",
    chapter_number: 1,
    evidence: [{ chapter_number: 1, excerpt: "She waited at the gate." }],
  }],
  warnings: ["One chapter excerpt was unavailable."],
}

let container: HTMLDivElement | null = null
let root: Root | null = null
let queryClient: QueryClient | null = null

;(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

function renderPage() {
  container = document.createElement("div")
  document.body.appendChild(container)
  root = createRoot(container)
  queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  act(() => {
    root?.render(<QueryClientProvider client={queryClient as QueryClient}><AiBetaReaderPage /></QueryClientProvider>)
  })
}

async function waitForText(text: string, timeout = 2000) {
  const start = Date.now()
  while (Date.now() - start < timeout) {
    if (container?.textContent?.includes(text)) return
    await act(async () => { await new Promise((resolve) => setTimeout(resolve, 0)) })
  }
  throw new Error(`Timed out waiting for ${text}`)
}

function button(label: string) {
  return Array.from(container?.querySelectorAll("button") ?? []).find(
    (item) => item.textContent?.trim() === label,
  ) as HTMLButtonElement | undefined
}

beforeEach(() => {
  sessionStorage.clear()
  for (const mock of [getBookMock, getCharactersMock, getChapterListMock, getReportsMock, runBetaReaderMock, getJobMock, createTaskMock, saveNoteMock, captureMock]) mock.mockReset()
  getBookMock.mockResolvedValue({
    id: "book-1",
    title: "The Echo House",
    status: "ready",
    access_class: "owner",
    collaboration_permissions: null,
  })
  getCharactersMock.mockResolvedValue([{ id: "char-1", name: "Mara" }, { id: "char-2", name: "Ivo" }])
  getChapterListMock.mockResolvedValue({ current_chapter: 1, chapters: [{ number: 1, title: "The Gate" }] })
  getReportsMock.mockResolvedValue({ reports: [report] })
  runBetaReaderMock.mockResolvedValue({ status: "complete", task_id: null, cached: true, report })
  createTaskMock.mockResolvedValue({ task_id: "task-1", candidate_id: "candidate-1", created: true })
  saveNoteMock.mockResolvedValue({ path: "AI Beta Reader/Chapter 1/Finding.md" })
})

afterEach(() => {
  act(() => root?.unmount())
  queryClient?.clear()
  container?.remove()
  root = null
  queryClient = null
  container = null
  document.body.innerHTML = ""
})

describe("AiBetaReaderPage", () => {
  it("shows stale reports, repetition evidence, voice confidence, and revision actions", async () => {
    renderPage()
    await waitForText("This report is from an earlier manuscript version")
    expect(container?.textContent).toContain("Gothic mystery")
    expect(container?.textContent).toContain("Mara is deciding")
    expect(container?.textContent).toContain("Vary the threshold image.")

    await act(async () => button("Overused language")?.click())
    expect(container?.textContent).toContain("silver moon")
    expect(container?.querySelector('a[href*="ai_beta_finding=term-1"]')).toBeTruthy()

    await act(async () => button("Character voices")?.click())
    expect(container?.textContent).toContain("42%")
    expect(container?.textContent).toContain("high confidence")

    await act(async () => button("Revision priorities")?.click())
    await act(async () => button("Save note")?.click())
    expect(saveNoteMock).toHaveBeenCalledWith(expect.objectContaining({
      explicitFolder: "AI Beta Reader/Chapter 1",
    }))
    await act(async () => button("Create revision task")?.click())
    expect(createTaskMock).toHaveBeenCalledWith("book-1", "report-1", "candidate-1")
    await waitForText("Revision task created")
  })

  it("runs all checks for the selected chapter and uses an exact cached report", async () => {
    renderPage()
    await waitForText("Reader report")
    expect(getChapterListMock).not.toHaveBeenCalled()
    expect(getCharactersMock).not.toHaveBeenCalled()

    await act(async () => button("New run")?.click())
    await waitForText("The Gate")
    expect(getChapterListMock).toHaveBeenCalledTimes(1)
    expect(getCharactersMock).toHaveBeenCalledTimes(1)
    await act(async () => button("Run reader pass")?.click())

    expect(runBetaReaderMock).toHaveBeenCalledWith("book-1", expect.objectContaining({
      scope: "chapter",
      chapter_number: 1,
      checks: ["repetition", "voice", "reader_feedback"],
    }))
    await waitForText("already analyzed")
    expect(captureMock).toHaveBeenCalledWith("ai_beta_reader_completed", expect.objectContaining({ cached: true }))
  })

  it("keeps human beta readers permission locked without an AI scan grant", async () => {
    getBookMock.mockResolvedValue({
      id: "book-1",
      title: "The Echo House",
      status: "ready",
      access_class: "reader_collaborator",
      collaboration_permissions: { can_run_ai_scans: false, can_edit_manuscript: false },
    })
    renderPage()
    await waitForText("AI scans are not enabled")
    expect(container?.textContent).toContain("Human beta readers do not receive AI access automatically")
    expect(getReportsMock).not.toHaveBeenCalled()
  })
  it("shows a report-load failure instead of a false empty state and retries", async () => {
    getReportsMock.mockRejectedValueOnce(new Error("Offline"))
    renderPage()
    await waitForText("Could not load saved reports")
    expect(container?.textContent).not.toContain("No saved reports yet")
    expect(container?.textContent).not.toContain("No reader report yet")
    await act(async () => button("Retry saved reports")?.click())
    await waitForText("The opening creates immediate tension")
  })

  it("does not interpret unavailable book data as denied permission", async () => {
    getBookMock.mockRejectedValueOnce(new Error("Offline"))
    renderPage()
    await waitForText("Could not load manuscript access")
    expect(container?.textContent).not.toContain("Permission required")
    await act(async () => button("Retry manuscript")?.click())
    await waitForText("Reader report")
  })

  it("keeps a queued job recoverable across transient polling errors", async () => {
    sessionStorage.setItem("lorevia:beta-reader-job:book-1", JSON.stringify({ taskId: "job-1", scope: "full_book" }))
    getJobMock.mockRejectedValueOnce(new Error("Offline")).mockResolvedValue({ status: "complete", report })
    renderPage()
    await waitForText("Could not check progress")
    expect(container?.textContent).not.toContain("Configure a reader pass")
    expect(button("Run reader pass")).toBeUndefined()
    await act(async () => button("Check progress now")?.click())
    await waitForText("Reader report")
    expect(runBetaReaderMock).not.toHaveBeenCalled()
    expect(sessionStorage.getItem("lorevia:beta-reader-job:book-1")).toBeNull()
  })

  it("recovers a missing saved job without repeatedly polling it", async () => {
    sessionStorage.setItem("lorevia:beta-reader-job:book-1", JSON.stringify({ taskId: "missing-job", scope: "chapter" }))
    getJobMock.mockRejectedValue({ isAxiosError: true, response: { status: 404 } })
    renderPage()
    await waitForText("This reader pass could no longer be found")
    expect(button("New run")).toBeTruthy()
    expect(sessionStorage.getItem("lorevia:beta-reader-job:book-1")).toBeNull()
  })

  it("ignores malformed stored jobs and handles a completed job with no report", async () => {
    sessionStorage.setItem("lorevia:beta-reader-job:book-1", "{broken")
    runBetaReaderMock.mockResolvedValue({ status: "queued", task_id: "job-1", report: null })
    getJobMock.mockResolvedValue({ status: "complete", report: null })
    renderPage()
    await waitForText("Reader report")
    await act(async () => button("New run")?.click())
    await waitForText("The Gate")
    await act(async () => button("Run reader pass")?.click())
    await waitForText("finished without returning a report")
    expect(sessionStorage.getItem("lorevia:beta-reader-job:book-1")).toBeNull()
  })

  it("adds a cached report to history while keeping earlier reports reachable", async () => {
    runBetaReaderMock.mockResolvedValue({ status: "complete", task_id: null, report: { ...report, report_id: "second", scope: "full_book", overall_impression: "A new full report." } })
    renderPage()
    await waitForText("Reader report")
    await act(async () => button("New run")?.click())
    await waitForText("The Gate")
    await act(async () => button("Run reader pass")?.click())
    await waitForText("A new full report.")
    expect(container?.querySelectorAll('aside button[aria-pressed]').length).toBe(2)
  })

  it("clears incompatible finding types when switching report tabs", async () => {
    renderPage()
    await waitForText("Reader report")
    const type = Array.from(container!.querySelectorAll("label")).find((item) => item.textContent?.includes("Finding type"))!.querySelector("select")!
    await act(async () => { type.value = "pacing"; type.dispatchEvent(new Event("change", { bubbles: true })) })
    await act(async () => button("Overused language")?.click())
    expect(container?.textContent).toContain("silver moon")
    expect(container?.querySelector('[role="tabpanel"]')?.getAttribute("aria-labelledby")).toBe(button("Overused language")?.id)
  })

  it("deduplicates save requests and restores controls after failure", async () => {
    let fail!: (error: Error) => void
    saveNoteMock.mockImplementationOnce(() => new Promise((_, reject) => { fail = reject }))
    renderPage()
    await waitForText("Reader report")
    await act(async () => { button("Save to notes")?.click(); button("Save to notes")?.click() })
    expect(saveNoteMock).toHaveBeenCalledTimes(1)
    expect(button("Save finding")?.disabled).toBe(true)
    await act(async () => { fail(new Error("Offline")); await Promise.resolve() })
    await waitForText("Could not save this report")
    expect(button("Save to notes")?.disabled).toBe(false)
    await act(async () => button("Save finding")?.click())
    await waitForText("Saved finding")
    expect(container?.textContent).not.toContain("Could not save this report")
  })

  it("caps optional voice selection at twenty characters without blocking deselection", async () => {
    getCharactersMock.mockResolvedValue(Array.from({ length: 21 }, (_, index) => ({ id: `character-${index}`, name: `Character ${index}` })))
    renderPage()
    await waitForText("Reader report")
    await act(async () => button("New run")?.click())
    await waitForText("Character 20")
    const choices = Array.from(container!.querySelectorAll<HTMLInputElement>('details input[type="checkbox"]'))
    for (const choice of choices.slice(0, 20)) await act(async () => choice.click())
    expect(choices[20].disabled).toBe(true)
    expect(container?.textContent).toContain("20 of 20 selected")
    await act(async () => choices[0].click())
    expect(choices[20].disabled).toBe(false)
  })

})
