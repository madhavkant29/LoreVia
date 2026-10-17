import type { GoalCalendarItem, RevisionActionItem, RevisionBoard, RevisionIntelligence, WriterWorkspace } from "@/types/book"

export function todayDateKey(date = new Date()) {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, "0")
  const day = String(date.getDate()).padStart(2, "0")
  return `${year}-${month}-${day}`
}

export function applyRevisionBoardState(
  board: RevisionBoard,
  itemId: string,
  patch: Partial<RevisionBoard["items"][number]>
): RevisionBoard {
  const existingIndex = board.items.findIndex((item) => item.item_id === itemId)
  const nextItem = {
    item_id: itemId,
    status: patch.status ?? "pending",
    assigned_version_id: patch.assigned_version_id ?? null,
    task_id: patch.task_id ?? null,
    updated_at: patch.updated_at ?? null,
    ...(existingIndex >= 0 ? board.items[existingIndex] : {}),
    ...patch,
  }
  const nextItems =
    existingIndex >= 0
      ? board.items.map((item, index) => (index === existingIndex ? nextItem : item))
      : [...board.items, nextItem]

  return {
    ...board,
    items: nextItems,
  }
}

export function patchRevisionIntelligenceItem(
  revision: RevisionIntelligence,
  itemId: string,
  patch: Partial<RevisionActionItem>
): RevisionIntelligence {
  const patchItem = (item: RevisionActionItem) => (item.id === itemId ? { ...item, ...patch } : item)
  const nextRevision = {
    ...revision,
    change_impacts: revision.change_impacts.map(patchItem),
    genre_checks: revision.genre_checks.map((genreCheck) => ({
      ...genreCheck,
      findings: (genreCheck.findings ?? []).map(patchItem),
    })),
    revision_plan: revision.revision_plan.map((revisionPass) => ({
      ...revisionPass,
      items: (revisionPass.items ?? []).map(patchItem),
    })),
    scene_advice: revision.scene_advice.map(patchItem),
    confusion_map: revision.confusion_map.map(patchItem),
    voice_alerts: revision.voice_alerts.map(patchItem),
    external_signals: revision.external_signals?.map(patchItem),
    priority_findings: revision.priority_findings?.map(patchItem),
  }
  const uniqueItems = new Map<string, RevisionActionItem>()
  for (const item of [
    ...nextRevision.change_impacts,
    ...nextRevision.scene_advice,
    ...nextRevision.confusion_map,
    ...nextRevision.voice_alerts,
    ...(nextRevision.external_signals ?? []),
    ...(nextRevision.priority_findings ?? []),
    ...nextRevision.genre_checks.flatMap((genreCheck) => genreCheck.findings),
    ...nextRevision.revision_plan.flatMap((revisionPass) => revisionPass.items),
  ]) {
    uniqueItems.set(item.id, item)
  }
  const activeItems = [...uniqueItems.values()].filter((item) => item.status !== "fixed" && item.status !== "ignored")
  const highSeverityCount = activeItems.filter((item) => item.severity === "high").length
  return {
    ...nextRevision,
    summary: {
      ...nextRevision.summary,
      active_item_count: activeItems.length,
      high_severity_count: highSeverityCount,
      task_ready_count: activeItems.filter((item) => item.status !== "task_created").length,
      hero_message:
        highSeverityCount > 0
          ? `${highSeverityCount} downstream logic risk${highSeverityCount === 1 ? "" : "s"} need attention first.`
          : `${activeItems.length} revision item${activeItems.length === 1 ? "" : "s"} are worth a structured pass.`,
    },
  }
}

export function buildRevisionTask(item: RevisionActionItem, dueDate = todayDateKey()): GoalCalendarItem {
  return {
    id: `revision-task:${item.id}`,
    title: item.title,
    due_date: dueDate,
    quota_value: 1,
    quota_unit: "tasks",
    completed: false,
  }
}

export function findRevisionTaskSource(
  revision: RevisionIntelligence | null,
  taskId: string,
): RevisionActionItem | null {
  if (!revision || !taskId) return null
  const findings = [
    ...(revision.change_impacts ?? []),
    ...(revision.scene_advice ?? []),
    ...(revision.confusion_map ?? []),
    ...(revision.voice_alerts ?? []),
    ...(revision.external_signals ?? []),
    ...(revision.priority_findings ?? []),
    ...(revision.genre_checks ?? []).flatMap((check) => check.findings ?? []),
    ...(revision.revision_plan ?? []).flatMap((pass) => pass.items ?? []),
  ]
  return findings.find((item) => item.task_id === taskId || `revision-task:${item.id}` === taskId) ?? null
}

export function buildGoalCalendarSavePatch(
  workspace: WriterWorkspace,
  goalCalendar: GoalCalendarItem[],
): { patch: Partial<WriterWorkspace>; removedTaskIds: string[] } {
  const nextIds = new Set(goalCalendar.map((item) => item.id))
  const removedTaskIds = workspace.goal_calendar
    .filter((item) => item.quota_unit === "tasks" && !nextIds.has(item.id))
    .map((item) => item.id)
  if (removedTaskIds.length === 0) return { patch: { goal_calendar: goalCalendar }, removedTaskIds }

  const removedIds = new Set(removedTaskIds)
  return {
    patch: {
      goal_calendar: goalCalendar,
      revision_board: {
        ...workspace.revision_board,
        items: (workspace.revision_board?.items ?? []).map((item) => {
          const linkedTaskId = item.task_id ?? `revision-task:${item.item_id}`
          if (!removedIds.has(linkedTaskId)) return item
          return {
            ...item,
            task_id: null,
            status: item.status === "task_created" ? "pending" : item.status,
          }
        }),
      },
    },
    removedTaskIds,
  }
}
