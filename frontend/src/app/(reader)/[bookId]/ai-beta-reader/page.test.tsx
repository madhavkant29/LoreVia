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
  default: ({ children, href, ...props }: { children: ReactNode; href: string }) => <a href={href} {...props}>{children}</a>,
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

    await act(async () => button("Overused Language")?.click())
    expect(container?.textContent).toContain("silver moon")
    expect(container?.querySelector('a[href*="ai_beta_finding=term-1"]')).toBeTruthy()

    await act(async () => button("Character Voices")?.click())
    expect(container?.textContent).toContain("42%")
    expect(container?.textContent).toContain("high confidence")

    await act(async () => button("Revision Priorities")?.click())
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
    await waitForText("Run again")
    await act(async () => button("Run again")?.click())

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
})
