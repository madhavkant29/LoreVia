import { describe, expect, it } from "vitest"

import { buildAuthorLoopIssueCards, buildAuthorLoopSteps, buildCharacterReviewStats } from "./authorLoop"

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
})
