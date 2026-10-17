import { describe, expect, it } from "vitest"

import { applyRevisionBoardState, buildGoalCalendarSavePatch, buildRevisionTask, findRevisionTaskSource, patchRevisionIntelligenceItem } from "./revisionIntelligence"
import type { RevisionIntelligence, WriterWorkspace } from "@/types/book"

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

  it("can convert a revision item when older genre checks omit findings", () => {
    const item = { id: "rev-legacy", category: "impact", title: "Clarify the reveal", description: "Missing setup", severity: "high", status: "pending" }
    const revision = {
      summary: { hero_message: "One risk", active_item_count: 1, high_severity_count: 1, task_ready_count: 1 },
      change_impacts: [item],
      genre_checks: [{ genre: "fantasy", label: "Fantasy", checks: [], rationale: "", findings: undefined }],
      revision_plan: [{ title: "Pass 1", summary: "", items: undefined }],
      scene_advice: [], confusion_map: [], voice_alerts: [], knowledge_matrix: [], knowledge_timeline: [],
    } as unknown as RevisionIntelligence

    const patched = patchRevisionIntelligenceItem(revision, item.id, { status: "task_created" })

    expect(patched.change_impacts[0].status).toBe("task_created")
    expect(patched.genre_checks[0].findings).toEqual([])
    expect(patched.revision_plan[0].items).toEqual([])
    expect(patched.summary.task_ready_count).toBe(0)
  })

  it("finds the saved task's source finding across revision sections", () => {
    const source = { id: "scene-1", category: "scene", title: "Repair the scene", description: "The scene repeats a reveal.", severity: "medium", status: "task_created", task_id: "saved-task-1" }
    const revision = {
      change_impacts: [], scene_advice: [source], confusion_map: [], voice_alerts: [],
      genre_checks: [{ findings: undefined }], revision_plan: [{ items: undefined }],
    } as unknown as RevisionIntelligence

    expect(findRevisionTaskSource(revision, "saved-task-1")).toBe(source)
    expect(findRevisionTaskSource(revision, "revision-task:scene-1")).toBe(source)
    expect(findRevisionTaskSource(revision, "other-task")).toBeNull()
    expect(findRevisionTaskSource(null, "saved-task-1")).toBeNull()
  })

  it("deletes only selected tasks and clears their revision links without removing findings", () => {
    const task = { id: "revision-task:rev-1", title: "Repair scene", due_date: "2026-05-21", quota_unit: "tasks", completed: false }
    const otherTask = { ...task, id: "revision-task:rev-2", title: "Keep this task" }
    const workspace = {
      goal_calendar: [task, otherTask],
      revision_board: {
        items: [
          { item_id: "rev-1", status: "task_created", task_id: task.id },
          { item_id: "rev-2", status: "fixed", task_id: otherTask.id },
        ],
      },
    } as WriterWorkspace

    const { patch, removedTaskIds } = buildGoalCalendarSavePatch(workspace, [otherTask])
    expect(removedTaskIds).toEqual([task.id])
    expect(patch.goal_calendar).toEqual([otherTask])
    expect(patch.revision_board?.items).toEqual([
      { item_id: "rev-1", status: "pending", task_id: null },
      { item_id: "rev-2", status: "fixed", task_id: otherTask.id },
    ])
    expect(workspace.revision_board.items[0].status).toBe("task_created")
    expect(buildGoalCalendarSavePatch(workspace, workspace.goal_calendar).patch).toEqual({ goal_calendar: workspace.goal_calendar })
  })
})
