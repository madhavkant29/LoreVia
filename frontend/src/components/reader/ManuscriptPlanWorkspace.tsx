"use client"

import { memo } from "react"
import type { EmotionalArcOverview, ReadabilityMetrics, WriterWorkspace, WritingTemplate } from "@/types/book"

type GoalField = "chapter_target" | "book_target" | "session_target"
type CorkboardLane = "ideas" | "drafting" | "revised"

const LANE_LABELS: Record<CorkboardLane, string> = {
  ideas: "Ideas",
  drafting: "Drafting",
  revised: "Revised",
}

type ManuscriptPlanWorkspaceProps = {
  isDark: boolean
  editorMode: "chapter" | "book"
  writerWorkspace: WriterWorkspace | null
  tighteningSelection: boolean
  onTightenSelectedText: () => void
  chapterWordCount: number
  fullBookWordCount: number
  chapterGoalProgress: number | null
  bookGoalProgress: number | null
  readabilityLoading: boolean
  readability: ReadabilityMetrics | null
  chapterApproxPages: number
  fullBookApproxPages: number
  chapterVersionsCount: number
  workspaceSaving: boolean
  onWordCountGoalChange: (field: GoalField, value: number | null) => void
  onSaveGoals: () => void
  onApplyTemplate: (template: WritingTemplate) => void
  newCorkboardTitle: string
  onNewCorkboardTitleChange: (value: string) => void
  onAddCorkboardCard: () => void
  onUpdateCardLane: (cardId: string, lane: CorkboardLane) => void
  emotionalArc: EmotionalArcOverview | null
}

export const ManuscriptPlanWorkspace = memo(function ManuscriptPlanWorkspace({
  isDark,
  editorMode,
  writerWorkspace,
  tighteningSelection,
  onTightenSelectedText,
  chapterWordCount,
  fullBookWordCount,
  chapterGoalProgress,
  bookGoalProgress,
  readabilityLoading,
  readability,
  chapterApproxPages,
  fullBookApproxPages,
  chapterVersionsCount,
  workspaceSaving,
  onWordCountGoalChange,
  onSaveGoals,
  onApplyTemplate,
  newCorkboardTitle,
  onNewCorkboardTitleChange,
  onAddCorkboardCard,
  onUpdateCardLane,
  emotionalArc,
}: ManuscriptPlanWorkspaceProps) {
  const arcChartCharacter = emotionalArc?.characters.find((character) => character.points.length > 0) ?? null

  return (
    <div className="mt-4 grid gap-4 xl:grid-cols-[0.95fr_1.05fr]">
      <section className={`rounded-lg border p-5 ${isDark ? "border-white/10 bg-[#0c1118]/92" : "border-stone-200 bg-white/90"}`}>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className={`text-3xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-emerald-300" : "text-emerald-700"}`}>Writer dashboard</p>
            <h2 className={`mt-2 text-2xl font-semibold tracking-tight ${isDark ? "text-white" : "text-stone-950"}`}>Goals, templates, and live readability</h2>
          </div>
          <button
            type="button"
            onClick={onTightenSelectedText}
            disabled={tighteningSelection}
            className="rounded-md bg-[#1f615d] px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
          >
            {tighteningSelection ? "Tightening..." : "Tighten selected text"}
          </button>
        </div>
        <p className={`mt-3 text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>
          {editorMode === "chapter"
            ? "Highlight a passage inside the active chapter editor to tighten or comment on only that selection. Ctrl/Cmd+S saves, Ctrl/Cmd+Shift+M comments, and local autosave keeps draft changes safe."
            : "Switch to chapter view to tighten or comment on a selected passage without touching the rest of the manuscript."}
        </p>
        <div className="mt-5 grid gap-4 md:grid-cols-3">
          <MetricCard
            label="Chapter goal"
            value={writerWorkspace?.word_count_goals.chapter_target ? `${chapterWordCount.toLocaleString()} / ${writerWorkspace.word_count_goals.chapter_target.toLocaleString()}` : `${chapterWordCount.toLocaleString()} words`}
            note={chapterGoalProgress !== null ? `${chapterGoalProgress}% of target` : "Set a chapter target below"}
            isDark={isDark}
          />
          <MetricCard
            label="Book goal"
            value={writerWorkspace?.word_count_goals.book_target ? `${fullBookWordCount.toLocaleString()} / ${writerWorkspace.word_count_goals.book_target.toLocaleString()}` : `${fullBookWordCount.toLocaleString()} words`}
            note={bookGoalProgress !== null ? `${bookGoalProgress}% of target` : "Set a manuscript target below"}
            isDark={isDark}
          />
          <MetricCard
            label="Readability"
            value={readabilityLoading ? "Scoring..." : readability ? `${readability.label} (${Math.round(readability.reading_ease)})` : "Waiting..."}
            note={readability ? `${readability.average_sentence_length} words/sentence - grade ${readability.grade_level}` : "Live score updates while you write"}
            isDark={isDark}
          />
        </div>
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          <ProgressStrip
            label="Chapter progress"
            progress={chapterGoalProgress}
            fallback={`${chapterApproxPages} page${chapterApproxPages === 1 ? "" : "s"} in the current chapter draft`}
            isDark={isDark}
          />
          <ProgressStrip
            label="Book progress"
            progress={bookGoalProgress}
            fallback={`${fullBookApproxPages.toLocaleString()} estimated manuscript pages`}
            isDark={isDark}
          />
        </div>
        <div className="mt-5 grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <div className={`rounded-md border p-4 ${isDark ? "border-white/10 bg-black/20" : "border-stone-200 bg-stone-50/80"}`}>
            <p className={`text-3xs font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-400" : "text-stone-400"}`}>Word count goals</p>
            <div className="mt-3 grid gap-3 md:grid-cols-3">
              <input
                type="number"
                value={writerWorkspace?.word_count_goals.chapter_target ?? ""}
                onChange={(event) => onWordCountGoalChange("chapter_target", Number(event.target.value) || null)}
                placeholder="Chapter"
                className={`rounded-md border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-black text-slate-100" : "border-stone-200 bg-white text-stone-900"}`}
              />
              <input
                type="number"
                value={writerWorkspace?.word_count_goals.book_target ?? ""}
                onChange={(event) => onWordCountGoalChange("book_target", Number(event.target.value) || null)}
                placeholder="Book"
                className={`rounded-md border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-black text-slate-100" : "border-stone-200 bg-white text-stone-900"}`}
              />
              <input
                type="number"
                value={writerWorkspace?.word_count_goals.session_target ?? ""}
                onChange={(event) => onWordCountGoalChange("session_target", Number(event.target.value) || null)}
                placeholder="Session"
                className={`rounded-md border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-black text-slate-100" : "border-stone-200 bg-white text-stone-900"}`}
              />
            </div>
            <button
              type="button"
              onClick={onSaveGoals}
              disabled={!writerWorkspace || workspaceSaving}
              className="mt-3 rounded-md bg-[#1f615d] px-4 py-2 text-xs font-semibold text-white disabled:opacity-50"
            >
              {workspaceSaving ? "Saving..." : "Save goals"}
            </button>
          </div>
          <div className={`rounded-md border p-4 ${isDark ? "border-white/10 bg-black/20" : "border-stone-200 bg-stone-50/80"}`}>
            <p className={`text-3xs font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-400" : "text-stone-400"}`}>Templates</p>
            <div className="mt-3 space-y-3">
              {(writerWorkspace?.templates ?? []).map((template) => (
                <article key={template.id} className={`rounded-md border p-3 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-white bg-white"}`}>
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>{template.title}</p>
                      <p className={`mt-1 text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>{template.kind} template</p>
                    </div>
                    <button onClick={() => onApplyTemplate(template)} className={`rounded-full px-3 py-1.5 text-xs font-semibold ${isDark ? "bg-emerald-500/10 text-emerald-200" : "bg-emerald-50 text-emerald-700"}`}>Insert</button>
                  </div>
                  <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-700"}`}>{template.description}</p>
                </article>
              ))}
              {(writerWorkspace?.templates ?? []).length === 0 ? <p className={`text-sm ${isDark ? "text-slate-500" : "text-stone-500"}`}>No writing templates are available yet.</p> : null}
              {chapterVersionsCount === 0 ? <p className={`text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>No chapter versions saved yet. Manual versions stay separate from local autosaves.</p> : null}
            </div>
          </div>
        </div>
      </section>

      <section className={`rounded-lg border p-5 ${isDark ? "border-white/10 bg-[#0c1118]/92" : "border-stone-200 bg-white/90"}`}>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className={`text-3xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-amber-300" : "text-amber-700"}`}>Planning board</p>
            <h2 className={`mt-2 text-2xl font-semibold tracking-tight ${isDark ? "text-white" : "text-stone-950"}`}>Corkboard and emotional arc</h2>
          </div>
        </div>
        <div className="mt-4 flex gap-2">
          <input
            value={newCorkboardTitle}
            onChange={(event) => onNewCorkboardTitleChange(event.target.value)}
            placeholder="New corkboard card"
            className={`flex-1 rounded-md border px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-amber-400/30 ${isDark ? "border-white/10 bg-black/30 text-slate-100 placeholder:text-slate-500" : "border-stone-200 bg-stone-50 text-stone-900 placeholder:text-stone-400"}`}
          />
          <button onClick={onAddCorkboardCard} disabled={!writerWorkspace || !newCorkboardTitle.trim()} className="rounded-md bg-[#1f615d] px-4 py-3 text-sm font-semibold text-white disabled:opacity-50">Add</button>
        </div>
        <div className="mt-4 grid gap-3 md:grid-cols-3">
          {(["ideas", "drafting", "revised"] as const).map((lane) => (
            <div key={lane} className={`min-h-[18rem] rounded-md border p-3 ${isDark ? "border-white/10 bg-black/20" : "border-stone-200 bg-stone-50/80"}`}>
              <div className="flex items-center justify-between gap-3">
                <p className={`text-3xs font-semibold uppercase tracking-[0.2em] ${isDark ? "text-slate-400" : "text-stone-400"}`}>{LANE_LABELS[lane]}</p>
                <span className={`rounded-full px-2 py-0.5 text-3xs font-semibold ${isDark ? "bg-white/10 text-slate-300" : "bg-white text-stone-600"}`}>
                  {(writerWorkspace?.corkboard_cards ?? []).filter((card) => card.lane === lane).length}
                </span>
              </div>
              <div className="mt-3 space-y-2">
                {(writerWorkspace?.corkboard_cards ?? []).filter((card) => card.lane === lane).map((card) => (
                  <article key={card.id} className={`rounded-md border p-3 transition-colors ${isDark ? "border-white/10 bg-white/[0.035] hover:border-white/15" : "border-white bg-white hover:border-stone-200"}`}>
                    <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>{card.title}</p>
                    {card.chapter_number ? <p className={`mt-1 text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>Chapter {card.chapter_number}</p> : null}
                    <div className="mt-3 flex gap-2">
                      {lane !== "ideas" ? <button onClick={() => onUpdateCardLane(card.id, "ideas")} className={`text-xs ${isDark ? "text-slate-300" : "text-stone-600"}`}>Ideas</button> : null}
                      {lane !== "drafting" ? <button onClick={() => onUpdateCardLane(card.id, "drafting")} className={`text-xs ${isDark ? "text-slate-300" : "text-stone-600"}`}>Drafting</button> : null}
                      {lane !== "revised" ? <button onClick={() => onUpdateCardLane(card.id, "revised")} className={`text-xs ${isDark ? "text-slate-300" : "text-stone-600"}`}>Revised</button> : null}
                    </div>
                  </article>
                ))}
                {(writerWorkspace?.corkboard_cards ?? []).filter((card) => card.lane === lane).length === 0 ? (
                  <div className={`rounded-md border border-dashed p-4 text-sm ${isDark ? "border-white/10 text-slate-500" : "border-stone-200 text-stone-500"}`}>
                    No {LANE_LABELS[lane].toLowerCase()} cards yet. Add a card above, then move it as the idea develops.
                  </div>
                ) : null}
              </div>
            </div>
          ))}
        </div>
        <div className={`mt-5 rounded-md border p-4 ${isDark ? "border-white/10 bg-black/20" : "border-stone-200 bg-stone-50/80"}`}>
          <p className={`text-3xs font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-400" : "text-stone-400"}`}>Emotional arc tracking</p>
          {arcChartCharacter ? <EmotionalArcMiniChart character={arcChartCharacter} isDark={isDark} /> : null}
          {emotionalArc?.characters.length ? (
            <div className="mt-3 space-y-3">
              {emotionalArc.characters.slice(0, 4).map((character) => (
                <article key={character.character_id} className={`rounded-md border p-3 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-white bg-white"}`}>
                  <div className="flex items-center justify-between gap-3">
                    <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>{character.character_name}</p>
                    <span className={`text-xs ${isDark ? "text-slate-400" : "text-stone-500"}`}>trajectory {character.trajectory_score > 0 ? "+" : ""}{character.trajectory_score}</span>
                  </div>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {character.points.slice(-4).map((point) => (
                      <span key={`${character.character_id}-${point.chapter_number}-${point.label}`} className={`rounded-full px-2.5 py-1 text-3xs font-semibold ${point.sentiment >= 0 ? isDark ? "bg-emerald-500/10 text-emerald-200" : "bg-emerald-50 text-emerald-700" : isDark ? "bg-rose-500/10 text-rose-200" : "bg-rose-50 text-rose-700"}`}>
                        Ch. {point.chapter_number}: {point.label}
                      </span>
                    ))}
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <p className={`mt-3 text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>Emotional arc tracking will populate as character growth events become available.</p>
          )}
        </div>
      </section>
    </div>
  )
})

function EmotionalArcMiniChart({
  character,
  isDark,
}: {
  character: EmotionalArcOverview["characters"][number]
  isDark: boolean
}) {
  const points = character.points.slice(-8)
  const width = 520
  const height = 150
  const chartPoints = points.map((point, index) => {
    const x = points.length <= 1 ? width / 2 : (index / (points.length - 1)) * width
    const normalized = Math.max(-1, Math.min(1, point.sentiment / 5))
    const y = height / 2 - normalized * 52
    return { ...point, x, y }
  })
  const path = chartPoints.map((point, index) => `${index === 0 ? "M" : "L"} ${point.x.toFixed(1)} ${point.y.toFixed(1)}`).join(" ")

  return (
    <div className={`mt-4 rounded-md border p-3 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-stone-200 bg-white"}`}>
      <div className="flex items-center justify-between gap-3">
        <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>{character.character_name}</p>
        <span className={`text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>trajectory {character.trajectory_score > 0 ? "+" : ""}{character.trajectory_score}</span>
      </div>
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${character.character_name} emotional arc`} className="mt-3 h-36 w-full overflow-visible">
        <defs>
          <linearGradient id={`arc-${character.character_id}`} x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="#2dd4bf" stopOpacity="0.28" />
            <stop offset="100%" stopColor="#2dd4bf" stopOpacity="0" />
          </linearGradient>
        </defs>
        <line x1="0" x2={width} y1={height / 2} y2={height / 2} stroke={isDark ? "rgba(255,255,255,0.12)" : "rgba(68,64,60,0.16)"} />
        {path ? (
          <>
            <path d={`${path} L ${width} ${height} L 0 ${height} Z`} fill={`url(#arc-${character.character_id})`} />
            <path d={path} fill="none" stroke="#2dd4bf" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
          </>
        ) : null}
        {chartPoints.map((point) => (
          <circle key={`${point.chapter_number}-${point.label}`} cx={point.x} cy={point.y} r="4.5" fill={point.sentiment >= 0 ? "#38bdf8" : "#fb7185"} />
        ))}
      </svg>
      <div className={`grid gap-2 text-3xs ${isDark ? "text-slate-500" : "text-stone-500"}`} style={{ gridTemplateColumns: `repeat(${Math.max(1, points.length)}, minmax(0, 1fr))` }}>
        {points.map((point) => (
          <span key={`${point.chapter_number}-${point.label}`} className="truncate">Ch. {point.chapter_number}</span>
        ))}
      </div>
    </div>
  )
}

function MetricCard({
  label,
  value,
  note,
  isDark,
}: {
  label: string
  value: string
  note: string
  isDark: boolean
}) {
  return (
    <div className={`rounded-md border px-4 py-4 ${isDark ? "border-white/10 bg-black/20" : "border-stone-200 bg-stone-50/80"}`}>
      <p className={`text-3xs font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>{label}</p>
      <p className={`mt-3 text-2xl font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>{value}</p>
      <p className={`mt-2 text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>{note}</p>
    </div>
  )
}

function ProgressStrip({
  label,
  progress,
  fallback,
  isDark,
}: {
  label: string
  progress: number | null
  fallback: string
  isDark: boolean
}) {
  const fill = Math.max(0, Math.min(100, progress ?? 0))

  return (
    <div className={`rounded-md border px-4 py-3 ${isDark ? "border-white/10 bg-black/20" : "border-stone-200 bg-stone-50/80"}`}>
      <div className="flex items-center justify-between gap-3">
        <p className={`text-3xs font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>{label}</p>
        <p className={`text-xs font-semibold ${isDark ? "text-slate-300" : "text-stone-600"}`}>{progress !== null ? `${fill}%` : "No target"}</p>
      </div>
      <div className={`mt-3 h-2 overflow-hidden rounded-full ${isDark ? "bg-white/10" : "bg-stone-200"}`}>
        <div
          className="h-full rounded-full bg-[#1f615d] transition-[width]"
          style={{ width: `${progress !== null ? fill : 18}%` }}
        />
      </div>
      <p className={`mt-2 text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>
        {progress !== null ? "You are moving toward the active target." : fallback}
      </p>
    </div>
  )
}
