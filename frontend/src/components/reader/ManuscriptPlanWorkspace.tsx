"use client"

import { memo, useState } from "react"

import { Tooltip } from "@/components/ui/Tooltip"
import type { EmotionalArcOverview, ReadabilityMetrics, WriterWorkspace, WritingTemplate } from "@/types/book"

type GoalField = "chapter_target" | "book_target" | "session_target"
type CorkboardLane = "ideas" | "drafting" | "revised"
export type TemplateDestination = "chapter_note" | "corkboard" | "manuscript_outline"

const LANE_LABELS: Record<CorkboardLane, string> = {
  ideas: "Ideas",
  drafting: "Drafting",
  revised: "Revised",
}

const LANE_HELP: Record<CorkboardLane, string> = {
  ideas: "Loose ideas that are not ready to draft yet.",
  drafting: "Cards you are actively turning into manuscript material.",
  revised: "Cards that have been written or incorporated into the draft.",
}

const TEMPLATE_HELP: Record<string, string> = {
  chapter: "Inserts a chapter-level scaffold into the active chapter draft.",
  scene: "Inserts a scene structure prompt where you can shape goal, conflict, and outcome.",
  story: "Inserts a larger story-structure scaffold for act turns and major pivots.",
}

const WORD_GOAL_FIELDS: Array<{
  field: GoalField
  label: string
  help: string
}> = [
  {
    field: "chapter_target",
    label: "Chapter target",
    help: "Target word count for the active chapter. This drives the chapter progress card above.",
  },
  {
    field: "book_target",
    label: "Book target",
    help: "Target word count for the whole manuscript. This drives the book progress card above.",
  },
  {
    field: "session_target",
    label: "Session target",
    help: "Target word count for a writing session. This is stored with your planning settings.",
  },
]

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
  onApplyTemplate: (template: WritingTemplate, destination: TemplateDestination) => Promise<void> | void
  onSaveTemplates: (templates: WritingTemplate[]) => Promise<void> | void
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
  onSaveTemplates,
  newCorkboardTitle,
  onNewCorkboardTitleChange,
  onAddCorkboardCard,
  onUpdateCardLane,
  emotionalArc,
}: ManuscriptPlanWorkspaceProps) {
  const arcChartCharacter = emotionalArc?.characters.find((character) => character.points.length > 0) ?? null
  const wordCountGoals = writerWorkspace?.word_count_goals ?? {}
  const templates = writerWorkspace?.templates ?? []
  const [templateEditorOpen, setTemplateEditorOpen] = useState(false)
  const [editingTemplateId, setEditingTemplateId] = useState<string | null>(null)
  const [templateDestination, setTemplateDestination] = useState<TemplateDestination>("chapter_note")
  const [templateTitle, setTemplateTitle] = useState("")
  const [templateKind, setTemplateKind] = useState("chapter")
  const [templateDescription, setTemplateDescription] = useState("")
  const [templateContent, setTemplateContent] = useState("")
  const [templateSaving, setTemplateSaving] = useState(false)

  const selectedTemplate: WritingTemplate | null = editingTemplateId
    ? templates.find((template) => template.id === editingTemplateId) ?? null
    : null

  function openTemplateEditor(template?: WritingTemplate) {
    setEditingTemplateId(template?.id ?? null)
    setTemplateDestination("chapter_note")
    setTemplateTitle(template?.title ?? "")
    setTemplateKind(template?.kind ?? "chapter")
    setTemplateDescription(template?.description ?? "")
    setTemplateContent(template?.content ?? "")
    setTemplateEditorOpen(true)
  }

  async function saveTemplateDraft() {
    if (!writerWorkspace || !templateTitle.trim() || !templateContent.trim()) return
    setTemplateSaving(true)
    try {
      const nextTemplate: WritingTemplate = {
        id: selectedTemplate?.id ?? `template-${Date.now()}`,
        title: templateTitle.trim(),
        kind: templateKind.trim() || "chapter",
        description: templateDescription.trim(),
        content: templateContent.trim(),
      }
      const nextTemplates = selectedTemplate
        ? templates.map((template) => template.id === selectedTemplate.id ? nextTemplate : template)
        : [...templates, nextTemplate]
      await onSaveTemplates(nextTemplates)
      setEditingTemplateId(nextTemplate.id)
    } finally {
      setTemplateSaving(false)
    }
  }

  async function applyTemplateDraft() {
    if (!templateTitle.trim() || !templateContent.trim()) return
    const nextTemplate: WritingTemplate = {
      id: selectedTemplate?.id ?? `template-preview-${Date.now()}`,
      title: templateTitle.trim(),
      kind: templateKind.trim() || "chapter",
      description: templateDescription.trim(),
      content: templateContent.trim(),
    }
    await onApplyTemplate(nextTemplate, templateDestination)
    setTemplateEditorOpen(false)
  }

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
            title="Rewrite only the selected manuscript text into tighter prose."
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
            help="Compares the active chapter's current word count against the saved chapter target."
            isDark={isDark}
          />
          <MetricCard
            label="Book goal"
            value={writerWorkspace?.word_count_goals.book_target ? `${fullBookWordCount.toLocaleString()} / ${writerWorkspace.word_count_goals.book_target.toLocaleString()}` : `${fullBookWordCount.toLocaleString()} words`}
            note={bookGoalProgress !== null ? `${bookGoalProgress}% of target` : "Set a manuscript target below"}
            help="Compares total manuscript words against the saved full-book target."
            isDark={isDark}
          />
          <MetricCard
            label="Readability"
            value={readabilityLoading ? "Scoring..." : readability ? `${readability.label} (${Math.round(readability.reading_ease)})` : "Waiting..."}
            note={readability ? `${readability.average_sentence_length} words/sentence - grade ${readability.grade_level}` : "Live score updates while you write"}
            help="Shows a live readability estimate for the active draft when scoring data is available."
            isDark={isDark}
          />
        </div>
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          <ProgressStrip
            label="Chapter progress"
            progress={chapterGoalProgress}
            fallback={`${chapterApproxPages} page${chapterApproxPages === 1 ? "" : "s"} in the current chapter draft`}
            help="Progress toward the saved chapter word target."
            isDark={isDark}
          />
          <ProgressStrip
            label="Book progress"
            progress={bookGoalProgress}
            fallback={`${fullBookApproxPages.toLocaleString()} estimated manuscript pages`}
            help="Progress toward the saved full-book word target."
            isDark={isDark}
          />
        </div>
        <div className="mt-5 grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <div className={`rounded-md border p-4 ${isDark ? "border-white/10 bg-black/20" : "border-stone-200 bg-stone-50/80"}`}>
            <SectionLabel isDark={isDark} label="Word count goals" help="Set word-count targets in words. These values update the goal and progress cards above." />
            <div className="mt-3 grid gap-3 md:grid-cols-3">
              {WORD_GOAL_FIELDS.map((item) => (
                <label key={item.field} className="block">
                  <span className={`flex items-center gap-1.5 text-3xs font-semibold uppercase tracking-[0.16em] ${isDark ? "text-slate-400" : "text-stone-500"}`}>
                    {item.label}
                    <HelpTooltip content={item.help} />
                  </span>
                  <input
                    type="number"
                    min={0}
                    step={100}
                    inputMode="numeric"
                    value={wordCountGoals[item.field] ?? ""}
                    onChange={(event) => onWordCountGoalChange(item.field, Number(event.target.value) || null)}
                    aria-label={`${item.label} words`}
                    title={item.help}
                    className={`mt-1 w-full rounded-md border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-black text-slate-100" : "border-stone-200 bg-white text-stone-900"}`}
                  />
                  <span className={`mt-1 block text-3xs ${isDark ? "text-slate-500" : "text-stone-400"}`}>words</span>
                </label>
              ))}
            </div>
            <button
              type="button"
              onClick={onSaveGoals}
              disabled={!writerWorkspace || workspaceSaving}
              title="Save these word-count targets to the writer workspace."
              className="mt-3 rounded-md bg-[#1f615d] px-4 py-2 text-xs font-semibold text-white disabled:opacity-50"
            >
              {workspaceSaving ? "Saving..." : "Save goals"}
            </button>
          </div>
          <div className={`rounded-md border p-4 ${isDark ? "border-white/10 bg-black/20" : "border-stone-200 bg-stone-50/80"}`}>
            <SectionLabel isDark={isDark} label="Templates" help="Templates insert reusable structure into the draft. They add scaffold text; they do not replace existing manuscript text." />
            <div className="mt-3 space-y-3">
              <button
                type="button"
                onClick={() => openTemplateEditor()}
                disabled={!writerWorkspace}
                title="Create a reusable author template."
                className={`w-full rounded-md border border-dashed px-3 py-2 text-left text-xs font-semibold ${isDark ? "border-white/10 text-slate-300 hover:bg-white/[0.04]" : "border-stone-200 text-stone-600 hover:bg-white"}`}
              >
                New custom template
              </button>
              {templates.map((template) => (
                <article key={template.id} className={`rounded-md border p-3 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-white bg-white"}`}>
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className={`flex items-center gap-1.5 text-sm font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>
                        {template.title}
                        <HelpTooltip content={TEMPLATE_HELP[template.kind] ?? "Inserts this reusable writing scaffold into the active draft."} />
                      </p>
                      <p className={`mt-1 text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>{formatTemplateKind(template.kind)} template</p>
                    </div>
                    <button
                      onClick={() => openTemplateEditor(template)}
                      title={`Preview and choose where to use ${template.title}.`}
                      className={`rounded-full px-3 py-1.5 text-xs font-semibold ${isDark ? "bg-emerald-500/10 text-emerald-200" : "bg-emerald-50 text-emerald-700"}`}
                    >
                      Use template
                    </button>
                  </div>
                  <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-700"}`}>{template.description}</p>
                </article>
              ))}
              {templates.length === 0 ? <p className={`text-sm ${isDark ? "text-slate-500" : "text-stone-500"}`}>No writing templates are available yet.</p> : null}
              {chapterVersionsCount === 0 ? <p className={`text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>No manual chapter snapshots yet. Save a chapter, then create a snapshot in version history when you want a restore point.</p> : null}
            </div>
          </div>
        </div>
      </section>

      <section className={`rounded-lg border p-5 ${isDark ? "border-white/10 bg-[#0c1118]/92" : "border-stone-200 bg-white/90"}`}>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className={`text-3xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-amber-300" : "text-amber-700"}`}>Planning board</p>
            <h2 className={`mt-2 flex items-center gap-2 text-2xl font-semibold tracking-tight ${isDark ? "text-white" : "text-stone-950"}`}>
              Corkboard and emotional arc
              <HelpTooltip content="Use the corkboard for planning cards and the emotional arc to scan extracted character trajectory signals." />
            </h2>
          </div>
        </div>
        <div className="mt-4 flex gap-2">
          <label className="min-w-0 flex-1">
            <span className={`mb-1 flex items-center gap-1.5 text-3xs font-semibold uppercase tracking-[0.16em] ${isDark ? "text-slate-400" : "text-stone-500"}`}>
              New corkboard card
              <HelpTooltip content="A short planning card title. Add it to Ideas first, then move it as it becomes draft material." />
            </span>
            <input
              value={newCorkboardTitle}
              onChange={(event) => onNewCorkboardTitleChange(event.target.value)}
              aria-label="New corkboard card title"
              title="Short title for a new planning card."
              className={`w-full rounded-md border px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-amber-400/30 ${isDark ? "border-white/10 bg-black/30 text-slate-100 placeholder:text-slate-500" : "border-stone-200 bg-stone-50 text-stone-900 placeholder:text-stone-400"}`}
            />
          </label>
          <button onClick={onAddCorkboardCard} disabled={!writerWorkspace || !newCorkboardTitle.trim()} title="Add this card to the Ideas lane." className="mt-5 rounded-md bg-[#1f615d] px-4 py-3 text-sm font-semibold text-white disabled:opacity-50">Add</button>
        </div>
        <div className="mt-4 grid gap-3 md:grid-cols-3">
          {(["ideas", "drafting", "revised"] as const).map((lane) => (
            <div key={lane} className={`min-h-[18rem] rounded-md border p-3 ${isDark ? "border-white/10 bg-black/20" : "border-stone-200 bg-stone-50/80"}`}>
              <div className="flex items-center justify-between gap-3">
                <p className={`flex items-center gap-1.5 text-3xs font-semibold uppercase tracking-[0.2em] ${isDark ? "text-slate-400" : "text-stone-400"}`}>
                  {LANE_LABELS[lane]}
                  <HelpTooltip content={LANE_HELP[lane]} />
                </p>
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
                      {lane !== "ideas" ? <button onClick={() => onUpdateCardLane(card.id, "ideas")} title="Move this card back to Ideas." className={`text-xs ${isDark ? "text-slate-300" : "text-stone-600"}`}>Ideas</button> : null}
                      {lane !== "drafting" ? <button onClick={() => onUpdateCardLane(card.id, "drafting")} title="Move this card to Drafting." className={`text-xs ${isDark ? "text-slate-300" : "text-stone-600"}`}>Drafting</button> : null}
                      {lane !== "revised" ? <button onClick={() => onUpdateCardLane(card.id, "revised")} title="Move this card to Revised." className={`text-xs ${isDark ? "text-slate-300" : "text-stone-600"}`}>Revised</button> : null}
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
          <SectionLabel isDark={isDark} label="Emotional arc tracking" help="Shows extracted character growth or sentiment points by chapter. Positive trajectory means the recent extracted points trend upward." />
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
      {templateEditorOpen ? (
        <TemplateEditorPanel
          isDark={isDark}
          title={templateTitle}
          kind={templateKind}
          description={templateDescription}
          content={templateContent}
          destination={templateDestination}
          templateSaving={templateSaving}
          canSave={Boolean(writerWorkspace && templateTitle.trim() && templateContent.trim())}
          onTitleChange={setTemplateTitle}
          onKindChange={setTemplateKind}
          onDescriptionChange={setTemplateDescription}
          onContentChange={setTemplateContent}
          onDestinationChange={setTemplateDestination}
          onSaveTemplate={() => void saveTemplateDraft()}
          onApply={() => void applyTemplateDraft()}
          onClose={() => setTemplateEditorOpen(false)}
        />
      ) : null}
    </div>
  )
})

function TemplateEditorPanel({
  isDark,
  title,
  kind,
  description,
  content,
  destination,
  templateSaving,
  canSave,
  onTitleChange,
  onKindChange,
  onDescriptionChange,
  onContentChange,
  onDestinationChange,
  onSaveTemplate,
  onApply,
  onClose,
}: {
  isDark: boolean
  title: string
  kind: string
  description: string
  content: string
  destination: TemplateDestination
  templateSaving: boolean
  canSave: boolean
  onTitleChange: (value: string) => void
  onKindChange: (value: string) => void
  onDescriptionChange: (value: string) => void
  onContentChange: (value: string) => void
  onDestinationChange: (value: TemplateDestination) => void
  onSaveTemplate: () => void
  onApply: () => void
  onClose: () => void
}) {
  const destinationOptions: Array<{ value: TemplateDestination; label: string; help: string }> = [
    {
      value: "chapter_note",
      label: "Chapter note",
      help: "Save this scaffold as a note for the active chapter. This keeps it out of manuscript prose.",
    },
    {
      value: "corkboard",
      label: "Corkboard card",
      help: "Create an Ideas card from this scaffold so it can move through the planning board.",
    },
    {
      value: "manuscript_outline",
      label: "Draft outline block",
      help: "Append a labeled outline block to the manuscript body. Use only when you want it inside the draft.",
    },
  ]

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/55 p-4">
      <section className={`grid max-h-[92vh] w-full max-w-5xl overflow-hidden rounded-lg border shadow-2xl lg:grid-cols-[0.95fr_1.05fr] ${isDark ? "border-white/10 bg-[#0c1118] text-slate-100" : "border-stone-200 bg-white text-stone-950"}`}>
        <div className={`space-y-4 overflow-y-auto border-r p-5 ${isDark ? "border-white/10" : "border-stone-200"}`}>
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className={`text-3xs font-semibold uppercase tracking-[0.22em] ${isDark ? "text-emerald-300" : "text-emerald-700"}`}>Template preview</p>
              <h3 className="mt-2 text-2xl font-semibold">Use or customize template</h3>
            </div>
            <button
              type="button"
              onClick={onClose}
              className={`rounded-sm border px-3 py-2 text-xs font-semibold ${isDark ? "border-white/10 text-slate-200 hover:bg-white/10" : "border-stone-200 text-stone-700 hover:bg-stone-50"}`}
            >
              Close
            </button>
          </div>

          <label className="block">
            <span className={`text-3xs font-semibold uppercase tracking-[0.16em] ${isDark ? "text-slate-400" : "text-stone-500"}`}>Template title</span>
            <input
              value={title}
              onChange={(event) => onTitleChange(event.target.value)}
              className={`mt-1 w-full rounded-md border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-black text-slate-100" : "border-stone-200 bg-white text-stone-900"}`}
            />
          </label>

          <label className="block">
            <span className={`text-3xs font-semibold uppercase tracking-[0.16em] ${isDark ? "text-slate-400" : "text-stone-500"}`}>Template type</span>
            <select
              value={kind}
              onChange={(event) => onKindChange(event.target.value)}
              className={`mt-1 w-full rounded-md border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-black text-slate-100" : "border-stone-200 bg-white text-stone-900"}`}
            >
              <option value="chapter">Chapter</option>
              <option value="scene">Scene</option>
              <option value="story">Story</option>
            </select>
          </label>

          <label className="block">
            <span className={`text-3xs font-semibold uppercase tracking-[0.16em] ${isDark ? "text-slate-400" : "text-stone-500"}`}>Short description</span>
            <textarea
              rows={3}
              value={description}
              onChange={(event) => onDescriptionChange(event.target.value)}
              className={`mt-1 w-full resize-none rounded-md border px-3 py-2 text-sm leading-6 ${isDark ? "border-white/10 bg-black text-slate-100" : "border-stone-200 bg-white text-stone-900"}`}
            />
          </label>

          <label className="block">
            <span className={`text-3xs font-semibold uppercase tracking-[0.16em] ${isDark ? "text-slate-400" : "text-stone-500"}`}>Scaffold content</span>
            <textarea
              rows={10}
              value={content}
              onChange={(event) => onContentChange(event.target.value)}
              className={`mt-1 w-full resize-y rounded-md border px-3 py-2 font-mono text-sm leading-6 ${isDark ? "border-white/10 bg-black text-slate-100" : "border-stone-200 bg-white text-stone-900"}`}
            />
          </label>
        </div>

        <div className="space-y-5 overflow-y-auto p-5">
          <div>
            <SectionLabel isDark={isDark} label="Send to" help="Choose where this scaffold should go. Chapter note is the default because it keeps structure outside prose." />
            <div className="mt-3 grid gap-2">
              {destinationOptions.map((option) => (
                <label
                  key={option.value}
                  className={`flex cursor-pointer items-start gap-3 rounded-md border p-3 text-sm ${destination === option.value ? isDark ? "border-teal-300 bg-teal-400/10" : "border-teal-500 bg-teal-50" : isDark ? "border-white/10 bg-white/[0.03]" : "border-stone-200 bg-stone-50"}`}
                >
                  <input
                    type="radio"
                    name="template-destination"
                    value={option.value}
                    checked={destination === option.value}
                    onChange={() => onDestinationChange(option.value)}
                    className="mt-1"
                  />
                  <span>
                    <span className={`block font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>{option.label}</span>
                    <span className={`mt-1 block text-xs leading-5 ${isDark ? "text-slate-400" : "text-stone-500"}`}>{option.help}</span>
                  </span>
                </label>
              ))}
            </div>
          </div>

          <div className={`rounded-md border p-4 ${isDark ? "border-white/10 bg-black/20" : "border-stone-200 bg-stone-50"}`}>
            <SectionLabel isDark={isDark} label="Preview" help="This is the exact scaffold text that will be saved or inserted." />
            <pre className={`mt-3 max-h-80 overflow-auto whitespace-pre-wrap rounded-md border p-3 text-sm leading-6 ${isDark ? "border-white/10 bg-black text-slate-200" : "border-stone-200 bg-white text-stone-800"}`}>
              {content.trim() || "Add scaffold content to preview it here."}
            </pre>
          </div>

          <div className="flex flex-wrap justify-end gap-3">
            <button
              type="button"
              onClick={onSaveTemplate}
              disabled={!canSave || templateSaving}
              className={`rounded-md border px-4 py-2 text-sm font-semibold disabled:opacity-50 ${isDark ? "border-white/10 text-slate-200 hover:bg-white/10" : "border-stone-200 text-stone-700 hover:bg-stone-50"}`}
            >
              {templateSaving ? "Saving..." : "Save template changes"}
            </button>
            <button
              type="button"
              onClick={onApply}
              disabled={!title.trim() || !content.trim()}
              className="rounded-md bg-[#1f615d] px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
            >
              Use in selected destination
            </button>
          </div>
        </div>
      </section>
    </div>
  )
}

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

function SectionLabel({ isDark, label, help }: { isDark: boolean; label: string; help: string }) {
  return (
    <p className={`flex items-center gap-1.5 text-3xs font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-400" : "text-stone-400"}`}>
      {label}
      <HelpTooltip content={help} />
    </p>
  )
}

function HelpTooltip({ content }: { content: string }) {
  return (
    <Tooltip content={content} align="start">
      <span
        tabIndex={0}
        aria-label={content}
        role="img"
        className="inline-flex h-4 w-4 items-center justify-center rounded-full border border-current/30 text-[10px] font-semibold leading-none opacity-80 transition hover:opacity-100 focus:outline-none focus:ring-2 focus:ring-teal-300/40"
      >
        ?
      </span>
    </Tooltip>
  )
}

function formatTemplateKind(kind: string) {
  if (kind === "chapter") return "Chapter"
  if (kind === "scene") return "Scene"
  if (kind === "story") return "Story"
  return `${kind.slice(0, 1).toUpperCase()}${kind.slice(1)}`
}

function MetricCard({
  label,
  value,
  note,
  help,
  isDark,
}: {
  label: string
  value: string
  note: string
  help: string
  isDark: boolean
}) {
  return (
    <div className={`rounded-md border px-4 py-4 ${isDark ? "border-white/10 bg-black/20" : "border-stone-200 bg-stone-50/80"}`}>
      <p className={`flex items-center gap-1.5 text-3xs font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>
        {label}
        <HelpTooltip content={help} />
      </p>
      <p className={`mt-3 text-2xl font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>{value}</p>
      <p className={`mt-2 text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>{note}</p>
    </div>
  )
}

function ProgressStrip({
  label,
  progress,
  fallback,
  help,
  isDark,
}: {
  label: string
  progress: number | null
  fallback: string
  help: string
  isDark: boolean
}) {
  const fill = Math.max(0, Math.min(100, progress ?? 0))

  return (
    <div className={`rounded-md border px-4 py-3 ${isDark ? "border-white/10 bg-black/20" : "border-stone-200 bg-stone-50/80"}`}>
      <div className="flex items-center justify-between gap-3">
        <p className={`flex items-center gap-1.5 text-3xs font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>
          {label}
          <HelpTooltip content={help} />
        </p>
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
