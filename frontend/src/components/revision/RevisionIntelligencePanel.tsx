"use client"

import { useMemo, useState } from "react"

import { booksApi } from "@/lib/api/books"
import { applyRevisionBoardState, buildRevisionTask, patchRevisionIntelligenceItem } from "@/lib/utils/revisionIntelligence"
import type { GoalCalendarItem, RevisionActionItem, RevisionIntelligence, WriterWorkspace } from "@/types/book"

type Props = {
  bookId: string
  revision: RevisionIntelligence
  writerWorkspace: WriterWorkspace | null
  isDark: boolean
  onRevisionChange: (revision: RevisionIntelligence) => void
  onWriterWorkspaceChange: (workspace: WriterWorkspace) => void
  variant?: "full" | "preview" | "story-map"
}

function statusBadgeClass(status: string, isDark: boolean) {
  if (status === "fixed") return isDark ? "bg-emerald-500/15 text-emerald-200" : "bg-emerald-50 text-emerald-700"
  if (status === "ignored") return isDark ? "bg-slate-500/15 text-slate-300" : "bg-slate-100 text-slate-600"
  if (status === "task_created") return isDark ? "bg-sky-500/15 text-sky-200" : "bg-sky-50 text-sky-700"
  return isDark ? "bg-amber-500/15 text-amber-200" : "bg-amber-50 text-amber-700"
}

function severityBadgeClass(severity: string, isDark: boolean) {
  if (severity === "high") return isDark ? "bg-rose-500/15 text-rose-200" : "bg-rose-50 text-rose-700"
  if (severity === "medium") return isDark ? "bg-amber-500/15 text-amber-200" : "bg-amber-50 text-amber-700"
  return isDark ? "bg-slate-500/15 text-slate-300" : "bg-slate-100 text-slate-600"
}

function panelClass(isDark: boolean) {
  return `rounded-md border shadow-[0_18px_42px_-32px_rgba(15,23,42,0.38)] ${isDark ? "border-white/[0.065] bg-[#0d141c]" : "border-slate-200/70 bg-white"}`
}

function todayDateValue() {
  const date = new Date()
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, "0")
  const day = String(date.getDate()).padStart(2, "0")
  return `${year}-${month}-${day}`
}

function mergeGoalCalendar(existing: GoalCalendarItem[], additions: GoalCalendarItem[]) {
  const seen = new Set(existing.map((item) => item.id))
  return [...existing, ...additions.filter((item) => !seen.has(item.id))]
}

function SectionFrame({ title, body, isDark, children }: { title: string; body: string; isDark: boolean; children: React.ReactNode }) {
  return (
    <section className={`rounded-md border p-5 ${isDark ? "border-white/[0.06] bg-white/[0.025]" : "border-slate-200/70 bg-slate-50/60"}`}>
      <p className={`text-3xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-500" : "text-slate-400"}`}>{title}</p>
      <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-300" : "text-slate-600"}`}>{body}</p>
      <div className="mt-4">{children}</div>
    </section>
  )
}

function RevisionItemCard({
  item,
  isDark,
  busy,
  onMarkFixed,
  onIgnore,
  onConvertToTask,
  onAssignVersion,
}: {
  item: RevisionActionItem
  isDark: boolean
  busy: boolean
  onMarkFixed: () => void
  onIgnore: () => void
  onConvertToTask: () => void
  onAssignVersion: () => void
}) {
  return (
    <div className={`rounded-md border p-4 ${isDark ? "border-white/[0.06] bg-[#101720]" : "border-slate-200 bg-white"}`}>
      <div className="flex flex-wrap items-center gap-2">
        <span className={`rounded-full px-2 py-1 text-3xs font-semibold uppercase tracking-[0.18em] ${severityBadgeClass(item.severity, isDark)}`}>{item.severity}</span>
        <span className={`rounded-full px-2 py-1 text-3xs font-semibold uppercase tracking-[0.18em] ${statusBadgeClass(item.status, isDark)}`}>{item.status.replace("_", " ")}</span>
        {item.chapter_ref ? <span className={isDark ? "text-xs text-slate-500" : "text-xs text-slate-400"}>{`Chapter ${item.chapter_ref}`}</span> : null}
      </div>
      <p className={`mt-3 text-sm font-semibold ${isDark ? "text-white" : "text-slate-900"}`}>{item.title}</p>
      <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-300" : "text-slate-600"}`}>{item.description}</p>
      {item.recommendation ? (
        <p className={`mt-2 text-xs leading-5 ${isDark ? "text-sky-300" : "text-sky-700"}`}>{item.recommendation}</p>
      ) : null}
      {item.assigned_version_id ? (
        <p className={`mt-2 text-xs ${isDark ? "text-violet-300" : "text-violet-700"}`}>Assigned to a draft snapshot for follow-up.</p>
      ) : null}
      <div className="mt-4 flex flex-wrap gap-2">
        <button
          type="button"
          disabled={busy || item.status === "fixed"}
          onClick={onMarkFixed}
          className={`rounded-full px-3 py-1.5 text-xs font-semibold transition disabled:opacity-50 ${isDark ? "bg-emerald-500/12 text-emerald-200 hover:bg-emerald-500/20" : "bg-emerald-50 text-emerald-700 hover:bg-emerald-100"}`}
        >
          Mark as fixed
        </button>
        <button
          type="button"
          disabled={busy || item.status === "ignored"}
          onClick={onIgnore}
          className={`rounded-full px-3 py-1.5 text-xs font-semibold transition disabled:opacity-50 ${isDark ? "bg-white/10 text-slate-200 hover:bg-white/15" : "bg-white text-slate-700 hover:bg-slate-50 border border-slate-200"}`}
        >
          Ignore
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={onConvertToTask}
          className={`rounded-full px-3 py-1.5 text-xs font-semibold transition disabled:opacity-50 ${isDark ? "bg-sky-500/12 text-sky-200 hover:bg-sky-500/20" : "bg-sky-50 text-sky-700 hover:bg-sky-100"}`}
        >
          Convert to task
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={onAssignVersion}
          className={`rounded-full px-3 py-1.5 text-xs font-semibold transition disabled:opacity-50 ${isDark ? "bg-violet-500/12 text-violet-200 hover:bg-violet-500/20" : "bg-violet-50 text-violet-700 hover:bg-violet-100"}`}
        >
          Assign to draft version
        </button>
      </div>
    </div>
  )
}

export function RevisionIntelligencePanel({
  bookId,
  revision,
  writerWorkspace,
  isDark,
  onRevisionChange,
  onWriterWorkspaceChange,
  variant = "full",
}: Props) {
  const [statusMessage, setStatusMessage] = useState<string | null>(null)
  const [busyItemId, setBusyItemId] = useState<string | null>(null)

  const board = writerWorkspace?.revision_board ?? { items: [], last_generated_at: null }
  const today = useMemo(() => todayDateValue(), [])

  const persistWorkspace = async (
    nextWorkspacePatch: Partial<WriterWorkspace>,
    nextRevision: RevisionIntelligence
  ) => {
    const updated = await booksApi.updateWriterWorkspace(bookId, nextWorkspacePatch)
    onWriterWorkspaceChange(updated)
    onRevisionChange(nextRevision)
  }

  const updateItemState = async (
    item: RevisionActionItem,
    patch: { status?: string; assigned_version_id?: string | null; task_id?: string | null },
    extraWorkspace?: Partial<WriterWorkspace>,
    message?: string
  ) => {
    const nextBoard = applyRevisionBoardState(board, item.id, {
      ...patch,
      updated_at: new Date().toISOString(),
    })
    const nextRevision = patchRevisionIntelligenceItem(revision, item.id, patch)
    setBusyItemId(item.id)
    try {
      await persistWorkspace(
        {
          ...extraWorkspace,
          revision_board: nextBoard,
        },
        nextRevision
      )
      setStatusMessage(message ?? `${item.title} updated.`)
    } catch {
      setStatusMessage("We could not save that revision action right now.")
    } finally {
      setBusyItemId(null)
    }
  }

  const convertItemToTask = async (item: RevisionActionItem) => {
    const currentCalendar = writerWorkspace?.goal_calendar ?? []
    const task = buildRevisionTask(item, today)
    await updateItemState(
      item,
      { status: "task_created", task_id: task.id },
      { goal_calendar: mergeGoalCalendar(currentCalendar, [task]) },
      `Added "${item.title}" to your revision checklist.`
    )
  }

  const assignItemToLatestVersion = async (item: RevisionActionItem) => {
    if (!item.chapter_ref) {
      setStatusMessage("This item is not tied to a specific chapter version yet.")
      return
    }
    setBusyItemId(item.id)
    try {
      let versions = await booksApi.getChapterVersions(bookId, item.chapter_ref, 6)
      if (versions.length === 0) {
        await booksApi.createChapterSnapshot(bookId, item.chapter_ref, `Auto snapshot for ${item.title}`)
        versions = await booksApi.getChapterVersions(bookId, item.chapter_ref, 6)
      }
      if (versions.length === 0) {
        setStatusMessage(`No saved draft snapshots exist yet for Chapter ${item.chapter_ref}.`)
        return
      }
      const latest = versions[0]
      await updateItemState(
        item,
        { assigned_version_id: latest.id },
        undefined,
        `Assigned "${item.title}" to the latest Chapter ${item.chapter_ref} snapshot.`
      )
    } catch {
      setStatusMessage("We could not load draft snapshots for that item.")
    } finally {
      setBusyItemId(null)
    }
  }

  const createChecklist = async () => {
    const planItems = revision.revision_plan.flatMap((revisionPass) => revisionPass.items)
    const actionable = planItems.filter((item, index, array) => array.findIndex((candidate) => candidate.id === item.id) === index)
    const pending = actionable.filter((item) => item.status !== "fixed" && item.status !== "ignored").slice(0, 5)
    if (pending.length === 0) {
      setStatusMessage("Everything currently actionable is already resolved or intentionally ignored.")
      return
    }

    const nextBoardItems = pending.reduce(
      (current, item) => applyRevisionBoardState(current, item.id, { status: "task_created", task_id: `revision-task:${item.id}`, updated_at: new Date().toISOString() }),
      board
    )
    const nextTasks = pending.map((item) => buildRevisionTask(item, today))
    const nextRevision = pending.reduce(
      (current, item) => patchRevisionIntelligenceItem(current, item.id, { status: "task_created", task_id: `revision-task:${item.id}` }),
      revision
    )

    try {
      await persistWorkspace(
        {
          goal_calendar: mergeGoalCalendar(writerWorkspace?.goal_calendar ?? [], nextTasks),
          revision_board: nextBoardItems,
        },
        nextRevision
      )
      setStatusMessage(`Created ${pending.length} revision checklist item${pending.length === 1 ? "" : "s"}.`)
    } catch {
      setStatusMessage("We could not create the revision checklist right now.")
    }
  }

  const renderActionList = (items: RevisionActionItem[], emptyText: string) => {
    if (items.length === 0) {
      return <p className={isDark ? "text-sm text-slate-500" : "text-sm text-slate-400"}>{emptyText}</p>
    }
    return (
      <div className="space-y-3">
        {items.map((item) => (
          <RevisionItemCard
            key={item.id}
            item={item}
            isDark={isDark}
            busy={busyItemId === item.id}
            onMarkFixed={() => void updateItemState(item, { status: "fixed" }, undefined, `Marked "${item.title}" as fixed.`)}
            onIgnore={() => void updateItemState(item, { status: "ignored" }, undefined, `Ignored "${item.title}".`)}
            onConvertToTask={() => void convertItemToTask(item)}
            onAssignVersion={() => void assignItemToLatestVersion(item)}
          />
        ))}
      </div>
    )
  }

  if (variant === "preview") {
    return (
      <section className={panelClass(isDark)}>
        <div className="border-b px-5 py-5">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className={`text-3xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-500" : "text-slate-400"}`}>Revision hub</p>
              <h2 className={`mt-2 text-xl font-semibold ${isDark ? "text-white" : "text-slate-900"}`}>Revision pressure at a glance.</h2>
              <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-300" : "text-slate-600"}`}>{revision.summary.hero_message}</p>
            </div>
            <button
              type="button"
              onClick={() => void createChecklist()}
              className={`rounded-full px-4 py-2 text-sm font-semibold transition ${isDark ? "bg-violet-500 text-white hover:bg-violet-400" : "bg-violet-600 text-white hover:bg-violet-500"}`}
            >
              Create checklist
            </button>
          </div>
        </div>

        <div className="px-5 py-5">
          <div className="grid gap-3 sm:grid-cols-3">
            {[
              { label: "Active items", value: revision.summary.active_item_count },
              { label: "High severity", value: revision.summary.high_severity_count },
              { label: "Task-ready", value: revision.summary.task_ready_count },
            ].map((stat) => (
              <div key={stat.label} className={`rounded-md border p-4 ${isDark ? "border-white/[0.06] bg-[#101720]" : "border-slate-200 bg-slate-50"}`}>
                <p className={isDark ? "text-xs uppercase tracking-[0.2em] text-slate-500" : "text-xs uppercase tracking-[0.2em] text-slate-400"}>{stat.label}</p>
                <p className={`mt-2 text-2xl font-semibold ${isDark ? "text-white" : "text-slate-900"}`}>{stat.value}</p>
              </div>
            ))}
          </div>

          {statusMessage ? <p className={`mt-4 text-sm ${isDark ? "text-violet-300" : "text-violet-700"}`}>{statusMessage}</p> : null}

          <div className="mt-5 space-y-3">
            {(revision.change_impacts.length > 0 ? revision.change_impacts : revision.scene_advice).slice(0, 2).map((item) => (
              <RevisionItemCard
                key={item.id}
                item={item}
                isDark={isDark}
                busy={busyItemId === item.id}
                onMarkFixed={() => void updateItemState(item, { status: "fixed" }, undefined, `Marked "${item.title}" as fixed.`)}
                onIgnore={() => void updateItemState(item, { status: "ignored" }, undefined, `Ignored "${item.title}".`)}
                onConvertToTask={() => void convertItemToTask(item)}
                onAssignVersion={() => void assignItemToLatestVersion(item)}
              />
            ))}
            {revision.change_impacts.length === 0 && revision.scene_advice.length === 0 ? (
              <p className={isDark ? "text-sm text-slate-500" : "text-sm text-slate-400"}>No active revision warnings are surfaced right now.</p>
            ) : null}
          </div>
        </div>
      </section>
    )
  }

  if (variant === "story-map") {
    return (
      <section className={panelClass(isDark)}>
        <div className="border-b px-5 py-5">
          <p className={`text-3xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-500" : "text-slate-400"}`}>Story map details</p>
          <h2 className={`mt-2 text-xl font-semibold ${isDark ? "text-white" : "text-slate-900"}`}>Knowledge state, timeline clarity, and reader friction.</h2>
        </div>

        <div className="px-5 py-5">
          <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
            <SectionFrame
              title="Knowledge state"
              body="What key story facts characters appear to know, including a chapter-by-chapter matrix across the current manuscript."
              isDark={isDark}
            >
              <div className="space-y-4">
                {revision.knowledge_matrix.map((fact) => (
                  <div key={fact.fact} className={`rounded-md border p-4 ${isDark ? "border-white/[0.06] bg-[#101720]" : "border-slate-200 bg-white"}`}>
                    <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-slate-900"}`}>{fact.fact}</p>
                    <div className="mt-3 space-y-2">
                      {fact.entries.map((entry) => (
                        <div key={`${fact.fact}-${entry.character_name}`} className={`grid grid-cols-[minmax(0,1fr)_auto] gap-3 text-sm ${isDark ? "text-slate-300" : "text-slate-600"}`}>
                          <div>
                            <p className={isDark ? "text-slate-200" : "text-slate-800"}>{entry.character_name}</p>
                            <p className={isDark ? "text-xs text-slate-500" : "text-xs text-slate-400"}>{entry.source}</p>
                          </div>
                          <span className={isDark ? "text-xs text-slate-500" : "text-xs text-slate-400"}>
                            {entry.chapter_learned ? `Chapter ${entry.chapter_learned}` : "Unknown"}
                          </span>
                        </div>
                      ))}
                    </div>
                    {fact.warning ? <p className={`mt-3 text-xs leading-5 ${isDark ? "text-amber-300" : "text-amber-700"}`}>{fact.warning}</p> : null}
                  </div>
                ))}
              </div>
            </SectionFrame>

            <SectionFrame
              title="Timeline clarity"
              body="A chapter-by-chapter view of when knowledge changes and where it may drift."
              isDark={isDark}
            >
              <div className="space-y-4">
                {revision.knowledge_timeline.map((fact) => (
                  <div key={`timeline-${fact.fact}`} className={`overflow-x-auto rounded-md border p-4 ${isDark ? "border-white/[0.06] bg-black/20" : "border-slate-200 bg-slate-50"}`}>
                    <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-slate-900"}`}>{fact.fact} timeline</p>
                    <table className="mt-3 min-w-full border-separate border-spacing-2 text-xs">
                      <thead>
                        <tr>
                          <th className={`text-left font-semibold ${isDark ? "text-slate-400" : "text-slate-500"}`}>Character</th>
                          {fact.rows[0]?.cells.map((cell) => (
                            <th key={`${fact.fact}-chapter-${cell.chapter_number}`} className={`text-left font-semibold ${isDark ? "text-slate-400" : "text-slate-500"}`}>Ch {cell.chapter_number}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {fact.rows.map((row) => (
                          <tr key={`${fact.fact}-${row.character_name}`}>
                            <td className={`pr-4 font-medium ${isDark ? "text-slate-200" : "text-slate-700"}`}>{row.character_name}</td>
                            {row.cells.map((cell) => (
                              <td key={`${fact.fact}-${row.character_name}-${cell.chapter_number}`}>
                                <span
                                  className={`inline-flex rounded-full px-2 py-1 font-semibold ${
                                    cell.state === "learned"
                                      ? isDark ? "bg-emerald-500/15 text-emerald-200" : "bg-emerald-50 text-emerald-700"
                                      : cell.state === "known"
                                        ? isDark ? "bg-sky-500/15 text-sky-200" : "bg-sky-50 text-sky-700"
                                        : isDark ? "bg-white/8 text-slate-400" : "bg-white text-slate-500 border border-slate-200"
                                  }`}
                                >
                                  {cell.state}
                                </span>
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    {fact.warning ? <p className={`mt-3 text-xs leading-5 ${isDark ? "text-amber-300" : "text-amber-700"}`}>{fact.warning}</p> : null}
                  </div>
                ))}
              </div>
            </SectionFrame>
          </div>

          <div className="mt-5 grid gap-5 xl:grid-cols-3">
            <SectionFrame
              title="Continuity findings"
              body="Downstream logic LoreVia thinks is most exposed right now."
              isDark={isDark}
            >
              {renderActionList(revision.change_impacts, "No active downstream impact warnings are surfaced right now.")}
            </SectionFrame>
            <SectionFrame
              title="Reader confusion map"
              body="Chapters where entity density, terminology, or anchoring may overwhelm the reader."
              isDark={isDark}
            >
              {renderActionList(revision.confusion_map, "Reader confusion risk is currently low across the sampled chapters.")}
            </SectionFrame>
            <SectionFrame
              title="Voice consistency checker"
              body="Dialogue or setting-language drift that may be carrying too much exposition or tonal mismatch."
              isDark={isDark}
            >
              {renderActionList(revision.voice_alerts, "No major voice drift is surfaced in the sampled chapters.")}
            </SectionFrame>
          </div>
        </div>
      </section>
    )
  }

  return (
    <section className={panelClass(isDark)}>
        <div className="flex flex-col gap-4 border-b px-5 py-5 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className={`text-3xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-500" : "text-slate-400"}`}>Revision command center</p>
          <h2 className={`mt-2 text-2xl font-semibold ${isDark ? "text-white" : "text-slate-900"}`}>Know what your edit breaks before your readers do.</h2>
          <p className={`mt-2 max-w-3xl text-sm leading-7 ${isDark ? "text-slate-300" : "text-slate-600"}`}>{revision.summary.hero_message}</p>
          {revision.summary.recent_edit_label ? (
            <p className={`mt-2 max-w-3xl text-sm leading-7 ${isDark ? "text-violet-300" : "text-violet-700"}`}>{revision.summary.recent_edit_label}</p>
          ) : null}
        </div>
        <button
          type="button"
          onClick={() => void createChecklist()}
          className={`rounded-full px-4 py-2 text-sm font-semibold transition ${isDark ? "bg-violet-500 text-white hover:bg-violet-400" : "bg-violet-600 text-white hover:bg-violet-500"}`}
        >
          Open revision board
        </button>
      </div>

      <div className="px-5 py-5">
        <div className="grid gap-3 sm:grid-cols-3">
          {[
            { label: "Active items", value: revision.summary.active_item_count },
            { label: "High severity", value: revision.summary.high_severity_count },
            { label: "Task-ready", value: revision.summary.task_ready_count },
          ].map((stat) => (
            <div key={stat.label} className={`rounded-md border p-4 ${isDark ? "border-white/[0.06] bg-[#101720]" : "border-slate-200 bg-slate-50"}`}>
              <p className={isDark ? "text-xs uppercase tracking-[0.2em] text-slate-500" : "text-xs uppercase tracking-[0.2em] text-slate-400"}>{stat.label}</p>
              <p className={`mt-2 text-2xl font-semibold ${isDark ? "text-white" : "text-slate-900"}`}>{stat.value}</p>
            </div>
          ))}
        </div>

        {statusMessage ? (
          <p className={`mt-4 text-sm ${isDark ? "text-violet-300" : "text-violet-700"}`}>{statusMessage}</p>
        ) : null}

        <div className="mt-6 grid gap-5 xl:grid-cols-[minmax(0,1.1fr)_minmax(0,0.9fr)]">
          <SectionFrame
            title="Change impact"
            body="Downstream story logic LoreVia thinks is most exposed right now."
            isDark={isDark}
          >
            {renderActionList(revision.change_impacts, "No active downstream impact warnings are surfaced right now.")}
          </SectionFrame>

          <SectionFrame
            title="Genre-specific intelligence"
            body="Checks weighted toward the expectations of this manuscript's genre."
            isDark={isDark}
          >
            <div className="space-y-3">
              {revision.genre_checks.map((genreCheck) => (
                <div key={genreCheck.label} className={`rounded-md border p-4 ${isDark ? "border-white/[0.06] bg-[#101720]" : "border-slate-200 bg-white"}`}>
                  <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-slate-900"}`}>{genreCheck.label}</p>
                  <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-300" : "text-slate-600"}`}>{genreCheck.rationale}</p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {genreCheck.checks.map((check) => (
                      <span key={check} className={`rounded-full px-3 py-1 text-3xs font-semibold ${isDark ? "bg-white/10 text-slate-200" : "bg-slate-100 text-slate-700"}`}>{check}</span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </SectionFrame>
        </div>

        <div className="mt-5 grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <SectionFrame
            title="Revision roadmap"
            body="A structured pass order so the draft gets cleaner with each revision cycle."
            isDark={isDark}
          >
            <div className="space-y-4">
              {revision.revision_plan.map((revisionPass) => (
                <div key={revisionPass.title} className={`rounded-md border p-4 ${isDark ? "border-white/[0.06] bg-[#101720]" : "border-slate-200 bg-white"}`}>
                  <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-slate-900"}`}>{revisionPass.title}</p>
                  <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-300" : "text-slate-600"}`}>{revisionPass.summary}</p>
                  <div className="mt-3 space-y-2">
                    {revisionPass.items.length > 0 ? revisionPass.items.map((item) => (
                      <div key={`${revisionPass.title}-${item.id}`} className={`rounded-md border px-3 py-3 ${isDark ? "border-white/[0.05] bg-black/20" : "border-slate-200 bg-slate-50"}`}>
                        <div className="flex items-center justify-between gap-3">
                          <p className={`text-sm font-medium ${isDark ? "text-slate-200" : "text-slate-700"}`}>{item.title}</p>
                          <span className={`rounded-full px-2 py-1 text-3xs font-semibold uppercase tracking-[0.16em] ${statusBadgeClass(item.status, isDark)}`}>{item.status.replace("_", " ")}</span>
                        </div>
                      </div>
                    )) : <p className={isDark ? "text-sm text-slate-500" : "text-sm text-slate-400"}>This pass is clear for now.</p>}
                  </div>
                </div>
              ))}
            </div>
          </SectionFrame>

          <SectionFrame
            title="Knowledge state"
            body="What key story facts characters appear to know, including a chapter-by-chapter matrix across the current manuscript."
            isDark={isDark}
          >
            <div className="space-y-4">
              {revision.knowledge_matrix.map((fact) => (
                <div key={fact.fact} className={`rounded-md border p-4 ${isDark ? "border-white/[0.06] bg-[#101720]" : "border-slate-200 bg-white"}`}>
                  <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-slate-900"}`}>{fact.fact}</p>
                  <div className="mt-3 space-y-2">
                    {fact.entries.map((entry) => (
                      <div key={`${fact.fact}-${entry.character_name}`} className={`grid grid-cols-[minmax(0,1fr)_auto] gap-3 text-sm ${isDark ? "text-slate-300" : "text-slate-600"}`}>
                        <div>
                          <p className={isDark ? "text-slate-200" : "text-slate-800"}>{entry.character_name}</p>
                          <p className={isDark ? "text-xs text-slate-500" : "text-xs text-slate-400"}>{entry.source}</p>
                        </div>
                        <span className={isDark ? "text-xs text-slate-500" : "text-xs text-slate-400"}>
                          {entry.chapter_learned ? `Chapter ${entry.chapter_learned}` : "Unknown"}
                        </span>
                      </div>
                    ))}
                  </div>
                  {fact.warning ? <p className={`mt-3 text-xs leading-5 ${isDark ? "text-amber-300" : "text-amber-700"}`}>{fact.warning}</p> : null}
                </div>
              ))}
              {revision.knowledge_timeline.map((fact) => (
                <div key={`timeline-${fact.fact}`} className={`overflow-x-auto rounded-md border p-4 ${isDark ? "border-white/[0.06] bg-black/20" : "border-slate-200 bg-slate-50"}`}>
                  <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-slate-900"}`}>{fact.fact} timeline</p>
                  <table className="mt-3 min-w-full border-separate border-spacing-2 text-xs">
                    <thead>
                      <tr>
                        <th className={`text-left font-semibold ${isDark ? "text-slate-400" : "text-slate-500"}`}>Character</th>
                        {fact.rows[0]?.cells.map((cell) => (
                          <th key={`${fact.fact}-chapter-${cell.chapter_number}`} className={`text-left font-semibold ${isDark ? "text-slate-400" : "text-slate-500"}`}>Ch {cell.chapter_number}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {fact.rows.map((row) => (
                        <tr key={`${fact.fact}-${row.character_name}`}>
                          <td className={`pr-4 font-medium ${isDark ? "text-slate-200" : "text-slate-700"}`}>{row.character_name}</td>
                          {row.cells.map((cell) => (
                            <td key={`${fact.fact}-${row.character_name}-${cell.chapter_number}`}>
                              <span
                                className={`inline-flex rounded-full px-2 py-1 font-semibold ${
                                  cell.state === "learned"
                                    ? isDark ? "bg-emerald-500/15 text-emerald-200" : "bg-emerald-50 text-emerald-700"
                                    : cell.state === "known"
                                      ? isDark ? "bg-sky-500/15 text-sky-200" : "bg-sky-50 text-sky-700"
                                      : isDark ? "bg-white/8 text-slate-400" : "bg-white text-slate-500 border border-slate-200"
                                }`}
                              >
                                {cell.state}
                              </span>
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {fact.warning ? <p className={`mt-3 text-xs leading-5 ${isDark ? "text-amber-300" : "text-amber-700"}`}>{fact.warning}</p> : null}
                </div>
              ))}
            </div>
          </SectionFrame>
        </div>

        <div className="mt-5 grid gap-5 xl:grid-cols-3">
          <SectionFrame
            title="Scene cut / merge advisor"
            body="Places where the manuscript may be doing duplicate work or carrying a low-impact scene."
            isDark={isDark}
          >
            {renderActionList(revision.scene_advice, "No obvious scene cuts or merge opportunities are surfaced right now.")}
          </SectionFrame>
          <SectionFrame
            title="Reader confusion map"
            body="Chapters where entity density, terminology, or anchoring may overwhelm the reader."
            isDark={isDark}
          >
            {renderActionList(revision.confusion_map, "Reader confusion risk is currently low across the sampled chapters.")}
          </SectionFrame>
          <SectionFrame
            title="Voice consistency checker"
            body="Dialogue or setting-language drift that may be carrying too much exposition or tonal mismatch."
            isDark={isDark}
          >
            {renderActionList(revision.voice_alerts, "No major voice drift is surfaced in the sampled chapters.")}
          </SectionFrame>
        </div>
      </div>
    </section>
  )
}
