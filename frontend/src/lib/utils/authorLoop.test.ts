import { describe, expect, it } from "vitest"

import { buildAuthorLoopIssueCards, buildAuthorLoopSteps, buildCharacterReviewStats, buildProjectNextActions } from "./authorLoop"

describe("authorLoop utils", () => {
  it("builds cited issue cards from revision intelligence and chapter reports", () => {
    const cards = buildAuthorLoopIssueCards(
      {
        tagline: "tag",
        summary: {
          hero_message: "Watch continuity",
          active_item_count: 1,
          high_severity_count: 1,
          task_ready_count: 1,
        },
        change_impacts: [
          {
            id: "issue-1",
            category: "continuity",
            title: "Lantern voice changed",
            description: "The lantern sounds like a different entity in chapter 6.",
            severity: "high",
            chapter_ref: 6,
            source_label: "Lantern scene",
            recommendation: "Align the voice cues or add a reveal explaining the shift.",
            status: "pending",
          },
        ],
        genre_checks: [],
        revision_plan: [],
        knowledge_matrix: [],
        knowledge_timeline: [],
        scene_advice: [],
        confusion_map: [],
        voice_alerts: [],
      },
      [
        {
          chapter_number: 7,
          chapter_title: "The Crossing",
          summary: "A follow-up scene introduces a continuity wobble.",
          new_characters: [],
          relationship_changes: [],
          plot_threads_opened: [],
          plot_threads_resolved: [],
          continuity_flags: ["Bridge injury appears healed too early."],
        },
      ],
      {
        revision_board: {
          items: [{ item_id: "issue-1", status: "task_created", task_id: "revision-task:1" }],
        },
      } as never
    )

    expect(cards).toHaveLength(2)
    expect(cards[0]).toMatchObject({
      id: "issue-1",
      severity: "high",
      citation: "Chapter 6",
      status: "task_created",
    })
    expect(cards[1]).toMatchObject({
      severity: "medium",
      citation: "Chapter 7",
    })
  })

  it("counts duplicate and thin character profiles", () => {
    const stats = buildCharacterReviewStats([
      { id: "a", name: "Nora", description: "Lead", aliases: ["N"], motivations: [], fears: [] },
      { id: "b", name: "Nora", description: "", aliases: [], motivations: [], fears: [] },
    ] as never)

    expect(stats.totalCharacters).toBe(2)
    expect(stats.duplicateCount).toBe(2)
    expect(stats.needsReviewCount).toBe(1)
  })

  it("marks feedback triage as attention when open beta feedback exists", () => {
    const steps = buildAuthorLoopSteps({
      book: { status: "ready" } as never,
      characters: [],
      storyHealth: { score: 82, summary: "Healthy", status: "healthy", metrics: [] },
      issueCards: [],
      assignments: [{ id: "assignment-1", view_bucket: "active" }] as never,
      selectedAssignment: {
        feedback_items: [
          { id: "feedback-1", author_status: "open" },
          { id: "feedback-2", author_status: "resolved" },
        ],
      } as never,
    })

    expect(steps.find((step) => step.id === "feedback")).toMatchObject({
      tone: "attention",
    })
    expect(steps.find((step) => step.id === "invite")).toMatchObject({
      tone: "ready",
    })
  })

  it("prioritizes severe findings and then fresh beta feedback", () => {
    const actions = buildProjectNextActions({
      book: { status: "ready", total_chapters: 12 } as never,
      bookId: "river-ash--book-1",
      issues: [{ id: "finding-1", title: "Timeline contradiction", severity: "high", citation: "Chapter 8", suggestedFix: "Reconcile the date", status: "pending" }] as never,
      consensus: { summary: { reader_count: 2, submitted_reader_count: 1, feedback_item_count: 4, open_feedback_count: 3, hotspot_count: 1, disagreement_count: 0 } } as never,
      assignmentCount: 2,
    })

    expect(actions.map((action) => action.priority)).toEqual(["severe_finding", "fresh_beta_feedback"])
    expect(actions[0].fingerprint).toContain("finding-1")
  })

  it("routes failed projects back to their overview", () => {
    const actions = buildProjectNextActions({
      book: { status: "failed", processing: { last_error: "Timed out" } } as never,
      bookId: "river-ash--book-1",
      issues: [],
      consensus: null,
      assignmentCount: 0,
    })

    expect(actions[0]).toMatchObject({
      priority: "failed_processing",
      href: "/river-ash--book-1/overview",
    })
  })

  it("keeps the share-ready action ahead of generic drafting for a clean project", () => {
    const actions = buildProjectNextActions({
      book: { status: "ready", total_chapters: 12 } as never,
      bookId: "river-ash--book-1",
      issues: [],
      consensus: {
        summary: {
          reader_count: 0,
          submitted_reader_count: 0,
          feedback_item_count: 0,
          open_feedback_count: 0,
          hotspot_count: 0,
          disagreement_count: 0,
        },
      } as never,
      assignmentCount: 0,
    })

    expect(actions.map((action) => action.priority)).toEqual([
      "export_share_ready",
      "fallback",
    ])
  })

  it("includes advisor and reader signals in the unified issue queue", () => {
    const cards = buildAuthorLoopIssueCards({
      tagline: "tag",
      summary: { hero_message: "Review", active_item_count: 1, high_severity_count: 0, task_ready_count: 1 },
      change_impacts: [], genre_checks: [], revision_plan: [], knowledge_matrix: [], knowledge_timeline: [], scene_advice: [], confusion_map: [], voice_alerts: [],
      external_signals: [{ id: "beta-1", category: "beta_consensus", title: "Reader hotspot", description: "Two readers paused here", severity: "medium", chapter_ref: 4, status: "pending" }],
    }, [], null)

    expect(cards).toHaveLength(1)
    expect(cards[0]).toMatchObject({ id: "beta-1", citation: "Chapter 4", sourceLabel: "beta consensus" })
  })
})
