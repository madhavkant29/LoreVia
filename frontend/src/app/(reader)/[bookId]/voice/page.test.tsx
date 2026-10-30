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
const saveVoiceReviewDecisionMock = vi.hoisted(() => vi.fn())
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
    voiceConsistencyReviewStream: (...args: unknown[]) => {
      const handlers = args[3] as { onStage?: (message: string) => void } | undefined
      handlers?.onStage?.("Reviewing the full passage…")
      return voiceConsistencyReviewMock(...args.slice(0, 3))
    },
    saveVoiceReviewDecision: (...args: unknown[]) => saveVoiceReviewDecisionMock(...args),
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
  saveVoiceReviewDecisionMock.mockReset().mockResolvedValue({ finding_key: "a".repeat(64), decision: "intentional", note: null })
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
  it("explains the voice comparison when the info button is clicked", async () => {
    renderPage()
    await waitForContent("The Ember Gate")
    const info = container?.querySelector<HTMLButtonElement>('button[aria-label="How Voice Consistency works"]')
    expect(info?.getAttribute("aria-expanded")).toBe("false")
    await act(async () => { info?.click() })
    expect(info?.getAttribute("aria-expanded")).toBe("true")
    expect(container?.querySelector('[role="tooltip"]')?.textContent).toContain("source-backed samples")
    expect(container?.querySelector('[role="tooltip"]')?.textContent).toContain("too little evidence")
    await act(async () => { container?.querySelector<HTMLButtonElement>('button[aria-label="Close help"]')?.click() })
    expect(info?.getAttribute("aria-expanded")).toBe("false")
  })

  it("labels alternate-character similarity as evidence rather than identity proof", async () => {
    voiceConsistencyReviewMock.mockResolvedValueOnce({
      review: { status: "complete", overall_verdict: "No supported shift.", issues: [] },
      retrieved_passages: [],
      characters_reviewed: ["Gregor"],
      character_matches: [{
        character_name: "Gregor",
        match_score: 42,
        baseline_sample_size: 3,
        baseline_word_count: 80,
        sample_dialogue_count: 2,
        strongest_signals: [],
        closest_other_character: "Grete",
        closest_other_score: 86,
      }],
      warnings: [],
    })
    renderPage()
    await waitForContent("The Ember Gate")
    await act(async () => { await new Promise((resolve) => setTimeout(resolve, 20)) })
    await clickButton("Run voice review")
    await waitForContent("Closest alternate voice: Grete")
    expect(container?.textContent).toContain("86% stylistic similarity")
    expect(container?.textContent).toContain("supporting evidence, not proof of speaker identity")
  })

  it("records an intentional voice finding and keeps it out of active findings", async () => {
    const issue = {
      finding_key: "a".repeat(64), character_name: "Gregor", classification: "possible",
      severity: "moderate", title: "Register shift", description: "His diction has shifted.",
      submitted_excerpt: "I can still make this work.", baseline_excerpt: "I shall continue.",
      baseline_chapter_number: 2, confidence: 0.7, revision_direction: "Keep the urgency.",
      intentionality_prompt: "Is this deliberate?",
    }
    voiceConsistencyReviewMock.mockResolvedValueOnce({
      review: { status: "complete", overall_verdict: "One possible shift.", issues: [issue] },
      retrieved_passages: [], characters_reviewed: ["Gregor"], character_matches: [], warnings: [],
    })
    renderPage()
    await waitForContent("The Ember Gate")
    await act(async () => { await new Promise((resolve) => setTimeout(resolve, 20)) })
    await clickButton("Run voice review")
    await waitForContent("Register shift")

    await clickButton("Mark intentional")

    expect(saveVoiceReviewDecisionMock).toHaveBeenCalledWith("book-1", issue.finding_key, "intentional")
    expect(container?.textContent).toContain("Previously reviewed findings (1)")
    expect(container?.textContent).toContain("marked intentional")
    expect(container?.textContent).not.toContain("No supported character voice issues were found")
  })

  it("leaves a voice finding visible when saving its decision fails", async () => {
    saveVoiceReviewDecisionMock.mockRejectedValueOnce(new Error("offline"))
    voiceConsistencyReviewMock.mockResolvedValueOnce({
      review: { status: "complete", overall_verdict: "One possible shift.", issues: [{
        finding_key: "b".repeat(64), character_name: "Gregor", severity: "moderate",
        title: "Register shift", description: "His diction has shifted.", intentionality_prompt: "Intentional?",
      }] },
      retrieved_passages: [], characters_reviewed: ["Gregor"], character_matches: [], warnings: [],
    })
    renderPage()
    await waitForContent("The Ember Gate")
    await act(async () => { await new Promise((resolve) => setTimeout(resolve, 20)) })
    await clickButton("Run voice review")
    await waitForContent("Register shift")

    await clickButton("Mark incorrect")

    expect(container?.textContent).toContain("Could not save that decision")
    expect(container?.textContent).toContain("Register shift")
    expect(container?.textContent).toContain("Mark incorrect")
  })

  it("allows a selected narrator and sends scene context for first-person review", async () => {
    renderPage()
    await waitForContent("The Ember Gate")
    await act(async () => { await new Promise((resolve) => setTimeout(resolve, 20)) })
    const modeSelect = container?.querySelector("#voice-mode") as HTMLSelectElement
    const characterSelect = container?.querySelector("#voice-character") as HTMLSelectElement
    const runButton = Array.from(container?.querySelectorAll("button") ?? []).find((button) => button.textContent?.includes("Run voice review"))
    await act(async () => {
      modeSelect.value = "first_person_narration"
      modeSelect.dispatchEvent(new Event("change", { bubbles: true }))
    })
    expect(runButton?.disabled).toBe(false)
    await act(async () => {
      characterSelect.value = "char-gregor"
      characterSelect.dispatchEvent(new Event("change", { bubbles: true }))
    })
    const contextField = container?.querySelector("#voice-scene-context") as HTMLTextAreaElement
    await act(async () => {
      Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")!.set!.call(contextField, "He is frightened.")
      contextField.dispatchEvent(new Event("input", { bubbles: true }))
    })
    await act(async () => { runButton?.click(); await Promise.resolve() })
    expect(voiceConsistencyReviewMock).toHaveBeenCalledWith("book-1", expect.any(String), {
      chapterNum: 1, characterId: "char-gregor", voiceMode: "first_person_narration",
      sceneContext: "He is frightened.",
    })
  })

  it("submits first-person auto-detection without assigning a guessed narrator", async () => {
    renderPage()
    await waitForContent("The Ember Gate")
    await act(async () => { await new Promise((resolve) => setTimeout(resolve, 20)) })
    const modeSelect = container?.querySelector("#voice-mode") as HTMLSelectElement
    await act(async () => {
      modeSelect.value = "first_person_narration"
      modeSelect.dispatchEvent(new Event("change", { bubbles: true }))
    })
    expect(container?.textContent).toContain("We will not guess from “I” alone")
    await clickButton("Run voice review")
    expect(voiceConsistencyReviewMock).toHaveBeenCalledWith("book-1", expect.any(String), {
      chapterNum: 1, characterId: null, voiceMode: "first_person_narration",
    })
  })

  it("shows insufficient evidence without claiming a clean voice verdict", async () => {
    voiceConsistencyReviewMock.mockResolvedValueOnce({
      review: { status: "insufficient_evidence", overall_verdict: "More independent dialogue is needed.", issues: [] },
      retrieved_passages: [], characters_reviewed: [], characters_detected: ["Gregor"], character_matches: [],
      warnings: ["Gregor: only 1 attributed baseline excerpt outside this passage."],
      coverage: { processed_ranges: [], total_characters: 42 },
    })
    renderPage()
    await waitForContent("The Ember Gate")
    await act(async () => { await new Promise((resolve) => setTimeout(resolve, 20)) })
    const runButton = Array.from(container?.querySelectorAll("button") ?? []).find((button) => button.textContent?.includes("Run voice review"))
    await act(async () => { runButton?.click(); await Promise.resolve() })

    expect(container?.textContent).toContain("Insufficient voice evidence")
    expect(container?.textContent).toContain("No verdict was made")
    expect(container?.textContent).toContain("Voice baselines compared: 0 of 1 detected characters")
    expect(container?.textContent).toContain("no source sections reviewed")
    expect(container?.textContent).not.toContain("No supported character voice issues were found")
  })

  it("labels a pronoun-attributed partial review as uncertain rather than clean", async () => {
    voiceConsistencyReviewMock.mockResolvedValueOnce({
      review: { status: "partial_evidence", overall_verdict: "Speaker attribution is tentative.", issues: [] },
      retrieved_passages: [], characters_reviewed: ["Gregor"], characters_detected: ["Gregor", "Lina"], character_matches: [],
      baseline_evidence: [{ character_name: "Gregor", sample_count: 3, word_count: 75, chapters: [1, 2], baseline_attribution_confidence: "contextual", attribution_confidence: "contextual" }],
      warnings: ["Gregor: dialogue was linked through a nearby pronoun."],
      coverage: { processed_ranges: [{ start: 0, end: 20 }], unattributed_ranges: [{ start: 20, end: 42 }], compared_ranges: [{ start: 5, end: 15 }], not_compared_ranges: [{ start: 0, end: 5 }, { start: 15, end: 42 }], unattributed_quoted_ranges: [{ start: 20, end: 30 }], total_characters: 42 },
      coverage_by_character: [{ character_name: "Gregor", processed_ranges: [{ start: 0, end: 20 }], unattributed_ranges: [{ start: 20, end: 42 }], compared_ranges: [{ start: 5, end: 15 }], not_compared_ranges: [{ start: 0, end: 5 }, { start: 15, end: 42 }], total_characters: 42 }],
    })
    renderPage()
    await waitForContent("The Ember Gate")
    await act(async () => { await new Promise((resolve) => setTimeout(resolve, 20)) })
    const runButton = Array.from(container?.querySelectorAll("button") ?? []).find((button) => button.textContent?.includes("Run voice review"))
    await act(async () => { runButton?.click(); await Promise.resolve() })

    expect(container?.textContent).toContain("Partial voice review")
    expect(container?.textContent).toContain("Voice baselines compared: 1 of 2 detected characters")
    expect(container?.textContent).toContain("20 of 42 source characters were in reviewed sections")
    expect(container?.textContent).toContain("only attributed voice samples were compared")
    expect(container?.textContent).toContain("Exact voice comparison: 10 characters compared with the baseline; 32 source characters were not voice-compared")
    expect(container?.textContent).toContain("22 characters had no attributable voice")
    expect(container?.textContent).toContain("Gregor: 1 overlapping section(s) compared; 1 section(s) had no attributable voice and were not compared")
    expect(container?.textContent).toContain("10 attributed voice characters compared")
    expect(container?.textContent).toContain("10 quoted characters were not attributed to a reviewed voice")
    expect(container?.textContent).toContain("Baseline attribution: contextual")
    expect(container?.textContent).toContain("Current passage attribution: contextual")
    expect(container?.textContent).toContain("not a complete verdict")
    expect(container?.textContent).not.toContain("No supported character voice issues were found")
  })

  it("shows uncertain narrator baseline evidence without claiming a voice match", async () => {
    voiceConsistencyReviewMock.mockResolvedValueOnce({
      voice_mode: "first_person_narration",
      review: { status: "partial_evidence", overall_verdict: "Narrator attribution in the baseline is tentative.", issues: [] },
      retrieved_passages: [], characters_reviewed: ["Gregor"], character_matches: [],
      baseline_evidence: [{ character_name: "Gregor", sample_count: 3, word_count: 140, chapters: [1, 2], baseline_attribution_confidence: "unverified_narrator", attribution_confidence: "user_selected_narrator" }],
      warnings: ["Gregor: baseline chapters do not independently identify this narrator."],
      coverage: { processed_ranges: [{ start: 0, end: 42 }], total_characters: 42 },
    })
    renderPage()
    await waitForContent("The Ember Gate")
    await act(async () => { await new Promise((resolve) => setTimeout(resolve, 20)) })
    await clickButton("Run voice review")
    await waitForContent("Narrator attribution in the baseline is tentative")

    expect(container?.textContent).toContain("Partial voice review")
    expect(container?.textContent).toContain("Baseline attribution: unverified narrator")
    expect(container?.textContent).toContain("Current passage attribution: user selected narrator")
    expect(container?.textContent).toContain("No reliable match scores were available")
    expect(container?.textContent).not.toContain("% match")
  })

  it("explains that sparse current dialogue cannot support a match percentage", async () => {
    voiceConsistencyReviewMock.mockResolvedValueOnce({
      review: { status: "partial_evidence", overall_verdict: "Current passage evidence is too limited for a reliable voice match.", issues: [] },
      retrieved_passages: [], characters_reviewed: ["Gregor"], character_matches: [],
      warnings: ["Gregor: at least 2 dialogue excerpts and 20 words are needed for a reliable voice match."],
      coverage: { processed_ranges: [{ start: 0, end: 42 }], total_characters: 42 },
    })
    renderPage()
    await waitForContent("The Ember Gate")
    await act(async () => { await new Promise((resolve) => setTimeout(resolve, 20)) })
    await clickButton("Run voice review")
    await waitForContent("Current passage evidence is too limited")

    expect(container?.textContent).toContain("current passage evidence may be too limited")
    expect(container?.textContent).toContain("No reliable match scores were available")
    expect(container?.textContent).not.toContain("% match")
  })

  it("pairs submitted and baseline excerpts with source chapter", async () => {
    voiceConsistencyReviewMock.mockResolvedValueOnce({
      review: { status: "complete", overall_verdict: "One possible register shift.", issues: [{
        character_name: "Gregor", classification: "possible", severity: "moderate", title: "Register shift",
        description: "The newer line is more casual.", submitted_excerpt: "I can still make this work.",
        baseline_excerpt: "I shall continue tomorrow.", baseline_chapter_number: 2, confidence: 0.7,
        revision_direction: "Keep the urgency while checking diction.", intentionality_prompt: "Is this shift intentional?",
      }] },
      retrieved_passages: [], characters_reviewed: ["Gregor"], character_matches: [], warnings: [],
      coverage: { processed_ranges: [{ start: 0, end: 42 }], total_characters: 42 },
    })
    renderPage()
    await waitForContent("The Ember Gate")
    await act(async () => { await new Promise((resolve) => setTimeout(resolve, 20)) })
    const runButton = Array.from(container?.querySelectorAll("button") ?? []).find((button) => button.textContent?.includes("Run voice review"))
    await act(async () => { runButton?.click(); await Promise.resolve() })

    expect(container?.textContent).toContain("Submitted passage: I can still make this work.")
    expect(container?.textContent).toContain("Baseline, chapter 2: I shall continue tomorrow.")
    expect(container?.textContent).toContain("70% evidence strength")
  })

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
    expect(container?.textContent).toContain("Reviewing the full passage…")
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
