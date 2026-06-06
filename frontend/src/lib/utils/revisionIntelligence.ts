import type { GoalCalendarItem, RevisionActionItem, RevisionBoard, RevisionIntelligence } from "@/types/book"

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
      findings: genreCheck.findings.map(patchItem),
    })),
    revision_plan: revision.revision_plan.map((revisionPass) => ({
      ...revisionPass,
      items: revisionPass.items.map(patchItem),
    })),
    scene_advice: revision.scene_advice.map(patchItem),
    confusion_map: revision.confusion_map.map(patchItem),
    voice_alerts: revision.voice_alerts.map(patchItem),
  }
  const uniqueItems = new Map<string, RevisionActionItem>()
  for (const item of [
    ...nextRevision.change_impacts,
    ...nextRevision.scene_advice,
    ...nextRevision.confusion_map,
    ...nextRevision.voice_alerts,
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
