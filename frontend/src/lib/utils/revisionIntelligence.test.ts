import { describe, expect, it } from "vitest"

import { applyRevisionBoardState, buildRevisionTask, patchRevisionIntelligenceItem } from "./revisionIntelligence"
import type { RevisionIntelligence } from "@/types/book"

describe("revision intelligence helpers", () => {
  it("applies and updates board item state", () => {
    const initial = { items: [], last_generated_at: null }

    const created = applyRevisionBoardState(initial, "rev-1", { status: "fixed", assigned_version_id: "version-1" })
    expect(created.items).toHaveLength(1)
    expect(created.items[0]).toMatchObject({
      item_id: "rev-1",
      status: "fixed",
      assigned_version_id: "version-1",
    })

    const updated = applyRevisionBoardState(created, "rev-1", { status: "ignored" })
    expect(updated.items[0]).toMatchObject({
      item_id: "rev-1",
      status: "ignored",
      assigned_version_id: "version-1",
    })
  })

  it("patches a revision item everywhere it appears", () => {
    const revision: RevisionIntelligence = {
      tagline: "Know what your edit breaks before your readers do.",
      summary: {
        hero_message: "2 risks need attention.",
        active_item_count: 2,
        high_severity_count: 1,
        task_ready_count: 2,
      },
      change_impacts: [
        {
          id: "rev-1",
          category: "impact",
          title: "Impact item",
          description: "Something breaks later.",
          severity: "high",
          status: "pending",
        },
      ],
      genre_checks: [
        {
          genre: "fantasy",
          label: "Fantasy",
          checks: ["magic system consistency"],
          rationale: "Lore-weighted checks.",
          findings: [
            {
              id: "rev-1",
              category: "impact",
              title: "Impact item",
              description: "Something breaks later.",
              severity: "high",
              status: "pending",
            },
          ],
        },
      ],
      revision_plan: [
        {
          title: "Pass 1",
          summary: "Story logic",
          items: [
            {
              id: "rev-1",
              category: "impact",
              title: "Impact item",
              description: "Something breaks later.",
              severity: "high",
              status: "pending",
            },
          ],
        },
      ],
      knowledge_matrix: [],
      knowledge_timeline: [],
      scene_advice: [],
      confusion_map: [],
      voice_alerts: [],
    }

    const patched = patchRevisionIntelligenceItem(revision, "rev-1", { status: "fixed" })

    expect(patched.change_impacts[0]?.status).toBe("fixed")
    expect(patched.genre_checks[0]?.findings[0]?.status).toBe("fixed")
    expect(patched.revision_plan[0]?.items[0]?.status).toBe("fixed")
    expect(patched.summary.active_item_count).toBe(0)
    expect(patched.summary.high_severity_count).toBe(0)
  })

  it("builds a planner task from a revision item", () => {
    const task = buildRevisionTask(
      {
        id: "rev-9",
        category: "scene",
        title: "Merge chapter scenes",
        description: "These scenes repeat the same beat.",
        severity: "medium",
        status: "pending",
      },
      "2026-05-11"
    )

    expect(task).toEqual({
      id: "revision-task:rev-9",
      title: "Merge chapter scenes",
      due_date: "2026-05-11",
      quota_value: 1,
      quota_unit: "tasks",
      completed: false,
    })
  })
})
