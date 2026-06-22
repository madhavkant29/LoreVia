import React, { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest"

import type { Book, PreWritingCheck, RevisionIntelligence, StoryHealth, UserStats, WriterWorkspace } from "@/types/book"
import type { ChapterListResponse } from "@/types/reader"

vi.mock("@/components/revision/RevisionIntelligencePanel", () => ({
  RevisionIntelligencePanel: ({ variant }: { variant?: "full" | "preview" | "story-map" }) => (
    <div data-testid={`revision-panel-${variant ?? "full"}`}>
      {variant === "preview" ? "Revision preview" : variant === "story-map" ? "Story map details" : "Revision hub full"}
    </div>
  ),
}))

import { AuthorWorkspaceDashboard } from "./AuthorWorkspaceDashboard"

let container: HTMLDivElement | null = null
let root: Root | null = null

describe("AuthorWorkspaceDashboard", () => {
  beforeAll(() => {
    ;(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
  })

  afterEach(() => {
    if (root) {
      act(() => {
        root?.unmount()
      })
    }
    if (container) {
      container.remove()
    }
    container = null
    root = null
  })

  it("renders the hero, compact story pulse, and author overview by default", () => {
    const view = renderDashboard()

    expect(view.textContent).toContain("Current project")
    expect(view.textContent).toContain("Story pulse")
    expect(view.textContent).toContain("Revision preview")
    expect(view.textContent).toContain("Your author command center")
    expect(view.textContent).not.toContain("Add planning item")
  })

  it("switches between planning, story map, and workspace stats tabs", async () => {
    const view = renderDashboard()

    await clickButton(view, "Planning")
    expect(view.textContent).toContain("Add planning item")

    await clickButton(view, "Story Map")
    expect(view.textContent).toContain("Memory map")
    expect(view.textContent).toContain("Story map details")

    await clickButton(view, "Workspace Stats")
    expect(view.textContent).toContain("Workspace stats")
    expect(view.textContent).toContain("Writing streak")
    expect(view.textContent).toContain("Daily goal")
  })

  it("renders all workspace stat metrics in the stats tab", async () => {
    const view = renderDashboard()

    await clickButton(view, "Workspace Stats")

    expect(view.textContent).toContain("Total words")
    expect(view.textContent).toContain("62,000")
    expect(view.textContent).toContain("Chapters")
    expect(view.textContent).toContain("8")
    expect(view.textContent).toContain("Characters")
    expect(view.textContent).toContain("3")
    expect(view.textContent).toContain("World items")
    expect(view.textContent).toContain("1")
  })

  it("keeps the full report link and hero CTAs wired to existing handlers", async () => {
    const onOpenManuscript = vi.fn()
    const onNavigate = vi.fn()
    const onOpenRelationships = vi.fn()
    const view = renderDashboard({ onOpenManuscript, onNavigate, onOpenRelationships })

    const reportLink = Array.from(view.querySelectorAll("a")).find((link) => link.textContent?.includes("View full report"))
    expect(reportLink?.getAttribute("href")).toBe("/book-1/analysis")

    await clickButton(view, "Open Manuscript Editor")
    expect(onOpenManuscript).toHaveBeenCalledOnce()

    await clickButton(view, "Open relationship map")
    expect(onOpenRelationships).toHaveBeenCalledOnce()

    await clickButton(view, "Open summaries")
    expect(onNavigate).toHaveBeenCalledWith("/book-1/summaries")
  })

  it("opens revision focus findings when a focus card is clicked", async () => {
    const view = renderDashboard()

    await clickButton(view, "Revision")
    await clickButton(view, "Continuity & logic")

    expect(view.textContent).toContain("Selected findings")
    expect(view.textContent).toContain("Fix archive key sequence")

    await clickButton(view, "Fix archive key sequence")
    expect(view.textContent).toContain("What LoreVia found")
    expect(view.textContent).toContain("Status: pending")
    expect(view.textContent).toContain("Category: continuity")
  })

  it("opens chapter findings and respects the severity filter", async () => {
    const view = renderDashboard()

    await clickButton(view, "Revision")
    await clickButton(view, "High")
    await act(async () => {
      const chapterButtons = Array.from(view.querySelectorAll("button")).filter((node) => node.textContent?.includes("Chapter 8"))
      chapterButtons.at(-1)?.dispatchEvent(new MouseEvent("click", { bubbles: true }))
      await Promise.resolve()
    })

    expect(view.textContent).toContain("Chapter findings")
    expect(view.textContent).toContain("Archive key timing")
    expect(view.textContent).not.toContain("Lore terms need re-anchoring")
  })

  it("makes story pulse metrics and readiness severity rows clickable", async () => {
    const onNavigate = vi.fn()
    const view = renderDashboard({ onNavigate })

    await clickButton(view, "Continuity")
    expect(view.textContent).toContain("Continuity: 82%")
    expect(view.textContent).toContain("Good continuity")
    expect(onNavigate).not.toHaveBeenCalled()

    await clickButton(view, "Revision")
    await clickButton(view, "Medium severity")

    const chapterButtons = Array.from(view.querySelectorAll("button"))
    const chapterEightButton = chapterButtons.filter((node) => node.textContent?.includes("Chapter 8")).at(-1)
    const chapterSevenButton = chapterButtons.filter((node) => node.textContent?.includes("Chapter 7")).at(-1)
    const bookWideButton = chapterButtons.filter((node) => node.textContent?.includes("Book-wide findings")).at(-1)

    expect(chapterEightButton?.textContent).toContain("0 issues")
    expect(chapterSevenButton?.textContent).toContain("1 issue")
    expect(bookWideButton?.textContent).toContain("1 issue")
  })
})

function renderDashboard({
  onOpenManuscript = vi.fn(),
  onNavigate = vi.fn(),
  onOpenRelationships = vi.fn(),
}: {
  onOpenManuscript?: () => void
  onNavigate?: (href: string) => void
  onOpenRelationships?: () => void
} = {}) {
  container = document.createElement("div")
  document.body.appendChild(container)
  root = createRoot(container)

  act(() => {
    root?.render(
      <AuthorWorkspaceDashboard
        bookId="book-1"
        book={buildBook()}
        isDark={true}
        activeBookMode="author"
        canUseAuthorMode={true}
        modeSaving={false}
        greetingName="Madhav"
        canOpenManuscript={true}
        currentWords={62000}
        targetWords={95000}
        percentComplete={65}
        chapters={buildChapters().chapters}
        unitTitle="Chapter"
        unitPrefix="Ch."
        storyHealth={buildStoryHealth()}
        preWritingCheck={buildPreWritingCheck()}
        revisionIntelligence={buildRevisionIntelligence()}
        writerWorkspace={buildWorkspace()}
        continuityIssueCount={3}
        worldGapCount={2}
        timelineIssueCount={1}
        processingSummary="draft is syncing"
        chapterCount={12}
        characterCount={18}
        worldArticleCount={9}
        loginStreakDays={4}
        weeklyLoginActivity={[true, false, true, true, false, false, true]}
        dailyWords={1200}
        dailyTarget={1500}
        userStats={buildUserStats()}
        saveState="idle"
        saveMessage={null}
        onModeChange={() => {}}
        onToggleTheme={() => {}}
        onNavigate={onNavigate}
        onOpenManuscript={onOpenManuscript}
        onOpenRelationships={onOpenRelationships}
        onSaveGoalCalendar={async () => true}
        onRevisionChange={() => {}}
        onWriterWorkspaceChange={() => {}}
      />
    )
  })

  return container
}

async function clickButton(view: HTMLDivElement, label: string) {
  const button = Array.from(view.querySelectorAll("button")).find((node) => node.textContent?.includes(label))
  expect(button).toBeTruthy()

  await act(async () => {
    button?.dispatchEvent(new MouseEvent("click", { bubbles: true }))
    await Promise.resolve()
  })
}

function buildBook(): Book {
  return {
    id: "book-1",
    title: "The Ember Gate",
    genre: "Fantasy",
    work_type: "novel",
    cover_url: null,
    status: "ready",
    created_at: "2026-05-10T00:00:00.000Z",
  } as Book
}

function buildChapters(): ChapterListResponse {
  return {
    read_upto: 8,
    current_chapter: 8,
    chapters: Array.from({ length: 10 }, (_, index) => ({
      number: index + 1,
      title: `Chapter ${index + 1}`,
      word_count: 3000 + index * 100,
      processed: true,
      read: index < 8,
    })),
  }
}

function buildUserStats(): UserStats {
  return {
    public: {
      total_books_read: 2,
      total_words_read: 120000,
    },
    private: {
      total_uploads: 4,
      total_token_consumption: 0,
      total_chapters_tracked: 12,
      saved_quotes: 3,
      active_analyzed_words: 120000,
      active_word_limit: 2000000,
      active_words_remaining: 1880000,
      monthly_processed_words: 120000,
      monthly_processed_word_limit: 1000000,
      monthly_processed_words_remaining: 880000,
      source_storage_bytes: 1024,
      source_storage_limit_bytes: 5368709120,
      source_storage_remaining_bytes: 5368708096,
      allowances_enforced: false,
    },
    writing: {
      today: { words: 1200, target_words: 1500, progress_pct: 80 },
      this_week: { words: 6400, target_words: 10500, progress_pct: 61 },
      this_month: { words: 18000, target_words: null, progress_pct: null },
      this_year: { words: 62000, target_words: null, progress_pct: null },
      last_24_hours: { words: 1200, target_words: null, progress_pct: null },
      last_7_days: { words: 6400, target_words: null, progress_pct: null },
      last_30_days: { words: 18000, target_words: null, progress_pct: null },
      last_year: { words: 62000, target_words: null, progress_pct: null },
      heatmap: [
        { date: "2026-05-14", words: 900 },
        { date: "2026-05-15", words: 0 },
        { date: "2026-05-16", words: 1400 },
        { date: "2026-05-17", words: 1200 },
        { date: "2026-05-18", words: 800 },
        { date: "2026-05-19", words: 900 },
        { date: "2026-05-20", words: 1200 },
      ],
      entries_today: [{ book_id: "book-1", chapter_number: 10, title: "Chapter 10", words: 1200 }],
    },
  }
}

function buildStoryHealth(): StoryHealth {
  return {
    score: 78,
    status: "steady",
    summary: "Continuity is holding, but a few plot threads need attention.",
    metrics: [
      { label: "Continuity", score: 82, detail: "Good continuity" },
      { label: "Timeline clarity", score: 74, detail: "Minor drift" },
      { label: "Pacing", score: 69, detail: "A few slow scenes" },
    ],
  }
}

function buildPreWritingCheck(): PreWritingCheck {
  return {
    upcoming_chapter: 9,
    active_characters: [
      { id: "c1", name: "Nora", role: "Lead", last_seen_chapter: 8, arc_summary: null },
      { id: "c2", name: "Tarin", role: "Rival", last_seen_chapter: 7, arc_summary: null },
    ],
    unresolved_threads: [
      { id: "t1", title: "Broken gate sigil", status: "open", introduced_at: 3, note: null },
    ],
    recent_events: [
      { chapter_number: 8, chapter_title: "Crossing", detail: "Nora enters the archive." },
    ],
    alerts: [
      { kind: "continuity", title: "Archive key timing", body: "The key appears before Nora receives it.", chapter_ref: 8 },
    ],
  }
}

function buildRevisionIntelligence(): RevisionIntelligence {
  return {
    tagline: "Focus revision where the manuscript is most exposed.",
    summary: {
      hero_message: "Two chapters carry the most revision pressure.",
      active_item_count: 4,
      high_severity_count: 1,
      task_ready_count: 3,
      recent_edit_label: "Last edit touched Chapters 7 and 8.",
    },
    change_impacts: [
      {
        id: "r1",
        category: "continuity",
        title: "Fix archive key sequence",
        description: "Align the handoff with Chapter 8.",
        severity: "high",
        chapter_ref: 8,
        source_label: "Archive key timing",
        status: "pending",
      },
    ],
    genre_checks: [
      {
        genre: "fantasy",
        label: "Fantasy promises",
        checks: ["Lore clarity"],
        rationale: "Readers need clear stakes.",
        findings: [
          {
            id: "genre-1",
            category: "confusion",
            title: "Lore terms need re-anchoring",
            description: "Too many archive terms arrive at once.",
            severity: "medium",
            status: "pending",
          },
        ],
      },
    ],
    revision_plan: [
      { title: "Pass 1", summary: "Repair contradictions first.", items: [] },
    ],
    knowledge_matrix: [
      { fact: "Knows the sigil meaning", entries: [{ character_name: "Nora", source: "Chapter 8", chapter_learned: 8 }], warning: null },
    ],
    knowledge_timeline: [
      {
        fact: "Sigil knowledge",
        rows: [{ character_name: "Nora", chapter_learned: 8, source: "Chapter 8", cells: [{ chapter_number: 8, state: "learned" }] }],
        warning: null,
      },
    ],
    scene_advice: [],
    confusion_map: [
      {
        id: "r3",
        category: "confusion",
        title: "Magic terms need a glossary pass",
        description: "The terminology warning applies across the current draft.",
        severity: "medium",
        source_label: "Reader confusion map",
        status: "pending",
      },
    ],
    voice_alerts: [
      {
        id: "r2",
        category: "voice",
        title: "Nora sounds too detached",
        description: "The internal narration flattens her fear response.",
        severity: "medium",
        chapter_ref: 7,
        source_label: "Voice consistency checker",
        status: "pending",
      },
    ],
  } as RevisionIntelligence
}

function buildWorkspace(): WriterWorkspace {
  return {
    word_count_goals: {
      book_target: 95000,
      chapter_target: 3500,
      session_target: 1200,
    },
    goal_calendar: [
      { id: "g1", title: "Revise Chapter 8", due_date: "2026-05-20", quota_value: 1200, quota_unit: "words", completed: false },
    ],
    corkboard_cards: [],
    templates: [],
    publishing: {
      active_preset: "standard_manuscript",
      trim_size: "6x9",
      include_title_page: true,
      mirror_margins: false,
    },
    manuscript_front_matter: {
      author_name: "A. Writer",
      pen_name: "",
      contact_email: "",
      contact_phone: "",
      contact_address: "",
      title: "The Ember Gate",
      subtitle: "",
      header_last_name: "Writer",
      header_title: "The Ember Gate",
      dedication: "",
      acknowledgments: "",
      epigraph: "",
      prologue: "",
      include_dedication: false,
      include_acknowledgments: false,
      include_epigraph: false,
      include_prologue: false,
    },
    novel_preface: "",
    revision_board: {
      items: [],
      last_generated_at: null,
    },
  } as WriterWorkspace
}
