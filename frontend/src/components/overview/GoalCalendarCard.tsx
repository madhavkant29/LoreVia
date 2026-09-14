"use client"

import { useEffect, useMemo, useState } from "react"

import type { GoalCalendarItem, WriterWorkspace } from "@/types/book"

import { Icon } from "./Icon"
import { PanelTitle } from "./PanelTitle"
import type { WorkspaceSaveState } from "./types"
import {
  buildCalendarDays,
  createCalendarItemId,
  formatPlannerDate,
  formatPlannerMonth,
  formatQuotaLabel,
  monthValueFromDate,
  panelClass,
  shiftMonthValue,
  todayDateValue,
} from "./utils"

export function GoalCalendarCard({
  isDark,
  writerWorkspace,
  saveState,
  saveMessage,
  onSaveGoalCalendar,
  onOpenManuscript,
}: {
  isDark: boolean
  writerWorkspace: WriterWorkspace | null
  saveState: WorkspaceSaveState
  saveMessage: string | null
  onSaveGoalCalendar: (goalCalendar: GoalCalendarItem[]) => Promise<boolean>
  onOpenManuscript: () => void
}) {
  const editable = Boolean(writerWorkspace)
  const [selectedDate, setSelectedDate] = useState(() => todayDateValue())
  const [visibleMonth, setVisibleMonth] = useState(() => todayDateValue().slice(0, 7))
  const [draftTitle, setDraftTitle] = useState("")
  const [draftQuotaValue, setDraftQuotaValue] = useState("")
  const [draftQuotaUnit, setDraftQuotaUnit] = useState("words")
  const today = todayDateValue()
  const goalCalendar = useMemo(
    () => writerWorkspace?.goal_calendar ?? [],
    [writerWorkspace?.goal_calendar],
  )
  const calendarDays = useMemo(() => buildCalendarDays(visibleMonth), [visibleMonth])
  const itemsByDate = useMemo(() => {
    const map = new Map<string, GoalCalendarItem[]>()
    for (const item of goalCalendar) {
      const current = map.get(item.due_date) ?? []
      current.push(item)
      map.set(item.due_date, current)
    }

    for (const items of map.values()) {
      items.sort((left, right) => {
        if (left.completed !== right.completed) return left.completed ? 1 : -1
        return left.title.localeCompare(right.title)
      })
    }

    return map
  }, [goalCalendar])
  const selectedItems = itemsByDate.get(selectedDate) ?? []
  const selectedQuotaTotal = selectedItems.reduce((sum, item) => sum + (item.quota_value ?? 0), 0)
  const monthItemCount = goalCalendar.filter((item) => item.due_date.startsWith(visibleMonth)).length
  const monthCompletedCount = goalCalendar.filter((item) => item.due_date.startsWith(visibleMonth) && item.completed).length
  const goalChips = [
    { label: "Book goal", value: writerWorkspace?.word_count_goals.book_target, unit: "words" },
    { label: "Chapter goal", value: writerWorkspace?.word_count_goals.chapter_target, unit: "words" },
    { label: "Session quota", value: writerWorkspace?.word_count_goals.session_target, unit: "words" },
  ]

  useEffect(() => {
    if (selectedDate.startsWith(visibleMonth)) return
    setVisibleMonth(monthValueFromDate(selectedDate))
  }, [selectedDate, visibleMonth])

  const addCalendarItem = async () => {
    const title = draftTitle.trim()
    if (!title || !writerWorkspace || !editable) return

    const parsedQuota = Number(draftQuotaValue)
    const nextItems = [
      ...goalCalendar,
      {
        id: createCalendarItemId(),
        title,
        due_date: selectedDate,
        quota_value: Number.isFinite(parsedQuota) && parsedQuota > 0 ? Math.round(parsedQuota) : null,
        quota_unit: Number.isFinite(parsedQuota) && parsedQuota > 0 ? draftQuotaUnit : null,
        completed: false,
      },
    ]

    const saved = await onSaveGoalCalendar(nextItems)
    if (!saved) return
    setDraftTitle("")
    setDraftQuotaValue("")
  }

  const toggleCalendarItem = async (itemId: string) => {
    if (!editable) return
    const nextItems = goalCalendar.map((item) => (item.id === itemId ? { ...item, completed: !item.completed } : item))
    await onSaveGoalCalendar(nextItems)
  }

  const removeCalendarItem = async (itemId: string) => {
    if (!editable) return
    await onSaveGoalCalendar(goalCalendar.filter((item) => item.id !== itemId))
  }

  return (
    <section className={panelClass(isDark, "p-4 sm:p-5")}>
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <PanelTitle isDark={isDark}>Goal Calendar</PanelTitle>
            <span className={`inline-flex items-center rounded-full px-2 py-1 text-3xs font-semibold ${isDark ? "bg-white/[0.05] text-slate-400" : "bg-slate-100 text-slate-500"}`}>
              {monthCompletedCount}/{monthItemCount || 0} done this month
            </span>
          </div>
          <p className={`mt-2 text-sm ${isDark ? "text-slate-400" : "text-slate-500"}`}>
            Plan writing goals, track quotas, and keep each milestone attached to a day on the board.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {goalChips.map((goal) => (
            <div key={goal.label} className={`rounded-md border px-3 py-2 text-xs ${isDark ? "border-white/[0.08] bg-white/[0.03]" : "border-slate-200 bg-slate-50"}`}>
              <p className={isDark ? "text-slate-500" : "text-slate-400"}>{goal.label}</p>
              <p className={`mt-1 font-semibold ${isDark ? "text-slate-200" : "text-slate-700"}`}>
                {typeof goal.value === "number" && goal.value > 0 ? `${goal.value.toLocaleString()} ${goal.unit}` : "Not set"}
              </p>
            </div>
          ))}
        </div>
      </div>

      <div className="mt-6 grid gap-5 xl:grid-cols-[minmax(0,1.45fr)_minmax(20rem,0.95fr)]">
        <div className={`rounded-md border p-4 ${isDark ? "border-white/[0.06] bg-white/[0.025]" : "border-slate-200/70 bg-slate-50/60"}`}>
          <div className="flex items-center justify-between gap-3">
            <button
              onClick={() => setVisibleMonth((current) => shiftMonthValue(current, -1))}
              aria-label="Show previous month"
              className={`flex h-9 w-9 items-center justify-center rounded-md border transition ${isDark ? "border-white/[0.08] bg-[#101720] text-slate-300 hover:bg-[#17212d]" : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50"}`}
            >
              <Icon name="chevron" className="h-4 w-4 rotate-180" />
            </button>
            <div className="text-center">
              <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-slate-900"}`}>{formatPlannerMonth(visibleMonth)}</p>
              <p className={`mt-1 text-xs ${isDark ? "text-slate-500" : "text-slate-400"}`}>Select a day to review the plan.</p>
            </div>
            <button
              onClick={() => setVisibleMonth((current) => shiftMonthValue(current, 1))}
              aria-label="Show next month"
              className={`flex h-9 w-9 items-center justify-center rounded-md border transition ${isDark ? "border-white/[0.08] bg-[#101720] text-slate-300 hover:bg-[#17212d]" : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50"}`}
            >
              <Icon name="chevron" className="h-4 w-4" />
            </button>
          </div>

          <div className="mt-4 grid grid-cols-7 gap-2">
            {["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map((label) => (
              <div key={label} className={`px-1 text-center text-3xs font-semibold ${isDark ? "text-slate-500" : "text-slate-400"}`}>
                {label}
              </div>
            ))}
            {calendarDays.map((day) => {
              const dayItems = itemsByDate.get(day.value) ?? []
              const completedCount = dayItems.filter((item) => item.completed).length
              const quotaTotal = dayItems.reduce((sum, item) => sum + (item.quota_value ?? 0), 0)
              const selected = day.value === selectedDate
              const isToday = day.value === today

              return (
                <button
                  key={day.value}
                  onClick={() => setSelectedDate(day.value)}
                  className={`min-h-[5.7rem] rounded-md border p-2 text-left transition ${
                    selected
                      ? isDark
                        ? "border-teal-800/25 bg-teal-800/10"
                        : "border-teal-300 bg-teal-50"
                      : isDark
                        ? "border-white/[0.05] bg-[#101720] hover:bg-[#16202b]"
                        : "border-slate-200 bg-white hover:bg-slate-50"
                  } ${!day.inMonth ? (isDark ? "text-slate-600" : "text-slate-300") : ""}`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className={`text-sm font-semibold ${selected ? "text-teal-800" : day.inMonth ? (isDark ? "text-slate-200" : "text-slate-700") : ""}`}>{day.label}</span>
                    {isToday ? <span className="rounded-full bg-teal-800 px-1.5 py-0.5 text-3xs font-semibold text-white">Today</span> : null}
                  </div>
                  <div className="mt-3 space-y-1">
                    {dayItems.length > 0 ? (
                      <>
                        <p className={`text-3xs font-medium ${isDark ? "text-slate-300" : "text-slate-600"}`}>{dayItems.length} item{dayItems.length === 1 ? "" : "s"}</p>
                        <p className={`text-3xs ${isDark ? "text-slate-500" : "text-slate-400"}`}>{completedCount}/{dayItems.length} complete</p>
                        {quotaTotal > 0 ? <p className="text-3xs font-semibold text-teal-800">{quotaTotal.toLocaleString()} quota</p> : null}
                      </>
                    ) : (
                      <p className={`text-3xs ${isDark ? "text-slate-600" : "text-slate-300"}`}>Open</p>
                    )}
                  </div>
                </button>
              )
            })}
          </div>
        </div>

        <div className={`rounded-md border p-4 ${isDark ? "border-white/[0.06] bg-white/[0.025]" : "border-slate-200/70 bg-slate-50/60"}`}>
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-slate-900"}`}>{formatPlannerDate(selectedDate)}</p>
              <p className={`mt-1 text-xs ${isDark ? "text-slate-500" : "text-slate-400"}`}>
                {selectedItems.length > 0 ? `${selectedItems.length} scheduled item${selectedItems.length === 1 ? "" : "s"}` : "No goals scheduled yet."}
              </p>
            </div>
            <div className="text-right">
              <p className={`text-3xs ${isDark ? "text-slate-500" : "text-slate-400"}`}>Selected quota</p>
              <p className={`mt-1 text-sm font-semibold ${isDark ? "text-slate-200" : "text-slate-700"}`}>{selectedQuotaTotal > 0 ? selectedQuotaTotal.toLocaleString() : "-"}</p>
            </div>
          </div>

          <div className="mt-4 space-y-3">
            {selectedItems.length > 0 ? selectedItems.map((item) => {
              const quotaLabel = formatQuotaLabel(item.quota_value, item.quota_unit)
              const overdue = item.due_date < today && !item.completed
              return (
                <div key={item.id} className={`rounded-md border p-3 ${isDark ? "border-white/[0.06] bg-[#101720]" : "border-slate-200 bg-white"}`}>
                  <div className="flex items-start gap-3">
                    <input
                      type="checkbox"
                      checked={item.completed}
                      disabled={!editable || saveState === "saving"}
                      onChange={() => void toggleCalendarItem(item.id)}
                      className="mt-1 h-4 w-4 rounded border-slate-300 text-teal-800 focus:ring-teal-700"
                    />
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className={`text-sm font-semibold ${item.completed ? (isDark ? "text-slate-500 line-through" : "text-slate-400 line-through") : isDark ? "text-slate-200" : "text-slate-700"}`}>
                          {item.title}
                        </p>
                        {quotaLabel ? <span className={`rounded-full px-2 py-1 text-3xs font-semibold ${isDark ? "bg-teal-800/10 text-teal-200" : "bg-teal-50 text-teal-800"}`}>{quotaLabel}</span> : null}
                        {overdue ? <span className={`rounded-full px-2 py-1 text-3xs font-semibold ${isDark ? "bg-amber-500/12 text-amber-300" : "bg-amber-50 text-amber-700"}`}>Overdue</span> : null}
                      </div>
                      <p className={`mt-1 text-xs ${isDark ? "text-slate-500" : "text-slate-400"}`}>{item.completed ? "Completed" : "Planned"} for {formatPlannerDate(item.due_date)}</p>
                    </div>
                    <button
                      onClick={() => void removeCalendarItem(item.id)}
                      disabled={!editable || saveState === "saving"}
                      className={`text-xs font-semibold ${isDark ? "text-slate-500 hover:text-rose-300 disabled:text-slate-700" : "text-slate-400 hover:text-rose-600 disabled:text-slate-300"}`}
                    >
                      Remove
                    </button>
                  </div>
                </div>
              )
            }) : (
              <div className={`rounded-md border border-dashed p-4 text-sm ${isDark ? "border-white/[0.08] text-slate-500" : "border-slate-200 text-slate-400"}`}>
                Nothing is scheduled for this day yet.
              </div>
            )}
          </div>

          <div className={`mt-5 rounded-md border p-4 ${isDark ? "border-white/[0.06] bg-[#0d141c]" : "border-slate-200 bg-white"}`}>
            <div className="flex items-center justify-between gap-3">
              <p className={`text-sm font-semibold ${isDark ? "text-slate-200" : "text-slate-700"}`}>Add planning item</p>
              <button
                onClick={() => {
                  setSelectedDate(today)
                  setVisibleMonth(monthValueFromDate(today))
                }}
                className={`text-xs font-semibold ${isDark ? "text-teal-200" : "text-teal-800"}`}
              >
                Jump to today
              </button>
            </div>

            <div className="mt-4 grid gap-3 sm:grid-cols-[minmax(0,1.2fr)_9rem]">
              <input
                value={draftTitle}
                onChange={(event) => setDraftTitle(event.target.value)}
                disabled={!editable || saveState === "saving"}
                aria-label="Planning item"
                className={`h-11 rounded-md border px-3 text-sm outline-none transition ${isDark ? "border-white/[0.08] bg-[#101720] text-slate-100 focus:border-teal-700" : "border-slate-200 bg-white text-slate-900 focus:border-teal-700"}`}
              />
              <input
                type="date"
                value={selectedDate}
                onChange={(event) => setSelectedDate(event.target.value)}
                disabled={!editable || saveState === "saving"}
                className={`h-11 rounded-md border px-3 text-sm outline-none transition ${isDark ? "border-white/[0.08] bg-[#101720] text-slate-100 focus:border-teal-700" : "border-slate-200 bg-white text-slate-900 focus:border-teal-700"}`}
              />
            </div>

            <div className="mt-3 grid gap-3 sm:grid-cols-[minmax(0,0.65fr)_minmax(0,0.65fr)_auto]">
              <input
                type="number"
                min="0"
                step="1"
                value={draftQuotaValue}
                onChange={(event) => setDraftQuotaValue(event.target.value)}
                disabled={!editable || saveState === "saving"}
                aria-label="Planning quota"
                className={`h-11 rounded-md border px-3 text-sm outline-none transition ${isDark ? "border-white/[0.08] bg-[#101720] text-slate-100 focus:border-teal-700" : "border-slate-200 bg-white text-slate-900 focus:border-teal-700"}`}
              />
              <select
                value={draftQuotaUnit}
                onChange={(event) => setDraftQuotaUnit(event.target.value)}
                disabled={!editable || saveState === "saving"}
                className={`h-11 rounded-md border px-3 text-sm outline-none transition ${isDark ? "border-white/[0.08] bg-[#101720] text-slate-100 focus:border-teal-700" : "border-slate-200 bg-white text-slate-900 focus:border-teal-700"}`}
              >
                {["words", "chapters", "scenes", "pages", "tasks"].map((unit) => (
                  <option key={unit} value={unit}>{unit}</option>
                ))}
              </select>
              <button
                onClick={() => void addCalendarItem()}
                disabled={!editable || saveState === "saving" || !draftTitle.trim()}
                className={`inline-flex h-11 items-center justify-center rounded-md px-4 text-sm font-semibold transition ${isDark ? "bg-teal-800 text-white hover:bg-teal-700 disabled:bg-teal-800/35" : "bg-teal-800 text-white hover:bg-teal-800 disabled:bg-teal-300"}`}
              >
                Add item
              </button>
            </div>

            <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <span className={`inline-flex h-2 w-2 rounded-full ${
                  saveState === "error"
                    ? "bg-rose-400"
                    : saveState === "saved"
                      ? "bg-emerald-400"
                      : saveState === "saving"
                        ? "bg-amber-400"
                        : isDark
                          ? "bg-slate-600"
                          : "bg-slate-300"
                }`} />
                <p className={`text-xs ${saveState === "error" ? "text-rose-400" : isDark ? "text-slate-500" : "text-slate-400"}`}>
                  {saveMessage || (editable ? "Changes save back into this book workspace." : "Loading planner...")}
                </p>
              </div>
              <button type="button" onClick={onOpenManuscript} className="text-xs font-semibold text-teal-800">
                Adjust word goals
              </button>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
