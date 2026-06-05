"use client"

import { memo, useState, type KeyboardEvent, type MouseEvent } from "react"
import { useConfirmDialog } from "@/components/ui/ConfirmDialog"
import { booksApi } from "@/lib/api/books"
import { isPaidTier } from "@/lib/billing/plans"
import { CONFIDENCE_THRESHOLDS } from "@/lib/constants"
import { useAuthStore } from "@/lib/stores/authStore"
import type { Character } from "@/types/character"

function eventChapterLabel(event: NonNullable<Character["growth_events"]>[number]) {
  const chapter = event.chapter_number ?? event.chapter
  return typeof chapter === "number" ? `Chapter ${chapter}` : null
}

function eventTitle(event: NonNullable<Character["growth_events"]>[number]) {
  return event.event_title || event.event || "Untitled event"
}

function eventDescription(event: NonNullable<Character["growth_events"]>[number]) {
  return event.description || event.impact || null
}

interface Props {
  character: Character
  bookId?: string
  compact?: boolean
  editable?: boolean
  onUpdated?: (character: Character) => void
  onDeleted?: (characterId: string) => void
  theme?: "light" | "dark"
}

function clampText(text: string, maxChars: number) {
  const cleaned = text.replace(/\s+/g, " ").trim()
  if (!cleaned) return ""
  if (cleaned.length <= maxChars) return cleaned
  const sliced = cleaned.slice(0, maxChars - 1)
  const lastStop = Math.max(sliced.lastIndexOf("."), sliced.lastIndexOf(";"), sliced.lastIndexOf(","))
  const candidate = lastStop > maxChars * 0.6 ? sliced.slice(0, lastStop + 1) : sliced
  return `${candidate.trim()}...`
}

function firstSentence(text: string, fallbackMaxChars: number) {
  const cleaned = text.replace(/\s+/g, " ").trim()
  if (!cleaned) return ""
  const match = cleaned.match(/^(.{20,}?[\.\!\?])\s/)
  return match?.[1] ? match[1].trim() : clampText(cleaned, fallbackMaxChars)
}

function listToString(values: string[] | undefined) {
  return (values ?? []).join(", ")
}

function stringToList(value: string) {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean)
}

export const CharacterCard = memo(function CharacterCard({ character, bookId, compact = false, editable = false, onUpdated, onDeleted, theme = "light" }: Props) {
  const [expanded, setExpanded] = useState(false)
  const [advancedOpen, setAdvancedOpen] = useState(false)
  const [editing, setEditing] = useState(false)
  const [saving, setSaving] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [shareState, setShareState] = useState<"idle" | "copied" | "error">("idle")
  const [exporting, setExporting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [draft, setDraft] = useState({
    name: character.name,
    aliases: listToString(character.aliases),
    description: character.description ?? "",
    arcSummary: character.arc_summary ?? "",
    personalityTags: listToString(character.personality_tags),
    motivations: listToString(character.motivations),
    fears: listToString(character.fears),
  })
  const confirm = useConfirmDialog()

  const user = useAuthStore((state) => state.user)
  const traits = character.trait_state ?? {}
  const visible = Object.entries(traits).filter(([, t]) => t && t.confidence >= CONFIDENCE_THRESHOLDS.SHOW_IN_UI && t.value)
  const isDark = theme === "dark"
  const relationshipSummaries = character.relationship_summaries ?? []
  const growthEvents = [...(character.growth_events ?? [])]
  const isPaid = isPaidTier(user?.tier)
  const advancedTraits = visible.filter(([key]) => !["hair", "eyes", "face", "build", "age", "distinguishing", "manual_description"].includes(key))

  const toggleExpanded = () => setExpanded((value) => !value)
  const handleCardKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault()
      toggleExpanded()
    }
  }

  async function handleSave() {
    if (!bookId) return
    setSaving(true)
    setError(null)
    try {
      const updated = await booksApi.updateCharacter(bookId, character.id, {
        name: draft.name.trim(),
        aliases: stringToList(draft.aliases),
        description: draft.description.trim() || null,
        arcSummary: draft.arcSummary.trim() || null,
        personalityTags: stringToList(draft.personalityTags),
        motivations: stringToList(draft.motivations),
        fears: stringToList(draft.fears),
      })
      onUpdated?.(updated)
      setEditing(false)
    } catch {
      setError("Could not save character changes.")
    } finally {
      setSaving(false)
    }
  }

  async function handleShare(event: MouseEvent<HTMLButtonElement>) {
    event.stopPropagation()
    if (!bookId) return
    try {
      const response = await booksApi.shareCharacter(bookId, character.id)
      const shareUrl = `${window.location.origin}${response.share_url}`
      await navigator.clipboard.writeText(shareUrl)
      setShareState("copied")
      window.setTimeout(() => setShareState("idle"), 2200)
    } catch {
      setShareState("error")
      window.setTimeout(() => setShareState("idle"), 2200)
    }
  }

  async function handleExport(event: MouseEvent<HTMLButtonElement>, format: "pdf" | "docx" | "md") {
    event.stopPropagation()
    if (!bookId) return
    setExporting(true)
    try {
      const blob = await booksApi.exportCharacterCard(bookId, character.id, format)
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement("a")
      anchor.href = url
      anchor.download = `${character.name.replace(/\s+/g, "-").toLowerCase()}-character-card.${format}`
      anchor.click()
      URL.revokeObjectURL(url)
    } finally {
      setExporting(false)
    }
  }

  async function handleDelete() {
    if (!bookId) return
    const confirmed = await confirm({
      title: `Delete ${character.name}?`,
      body: `Delete ${character.name} from this book? This is best for false positives and cannot be undone.`,
      confirmLabel: "Delete character",
      tone: "danger",
    })
    if (!confirmed) return
    setDeleting(true)
    setError(null)
    try {
      await booksApi.deleteCharacter(bookId, character.id)
      setExpanded(false)
      onDeleted?.(character.id)
    } catch {
      setError("Could not delete this character.")
    } finally {
      setDeleting(false)
    }
  }

  return (
    <>
      <div
        role="button"
        tabIndex={0}
        onClick={toggleExpanded}
        onKeyDown={handleCardKeyDown}
        className={`relative flex flex-col h-full w-full text-left rounded-lg border p-5 transition ${
          isDark ? "border-slate-800 bg-slate-900 text-white hover:border-slate-700" : "border-slate-200 bg-white text-slate-900 hover:border-slate-300"
        }`}
      >
        <div className="flex items-start gap-3">
          <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-md border text-sm font-semibold ${
            isDark ? "border-slate-700 bg-slate-800 text-white" : "border-slate-200 bg-slate-100 text-slate-700"
          }`}>
            {String(character.name?.[0] ?? "?").toUpperCase()}
          </div>
          <div className="min-w-0">
            <h3 className={`font-semibold text-xl leading-tight break-words ${isDark ? "text-white" : "text-slate-900"}`}>{character.name}</h3>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <span className={`rounded-md px-2.5 py-1 text-3xs font-semibold uppercase tracking-[0.14em] ${
                isDark ? "bg-slate-800 text-slate-200" : "bg-slate-100 text-slate-700"
              }`}>
                {character.role || "character"}
              </span>
              <span className={`rounded-md px-2.5 py-1 text-3xs font-semibold uppercase tracking-[0.14em] ${
                isDark ? "bg-slate-800 text-slate-300" : "bg-slate-100 text-slate-600"
              }`}>
                {character.status ?? "alive"}
              </span>
            </div>
          </div>
        </div>

        <div className="mt-4 border-t pt-4 flex-grow border-slate-200 dark:border-slate-800">
          <p className={`line-clamp-3 text-sm leading-relaxed ${isDark ? "text-slate-300" : "text-slate-600"}`}>
            {character.description || "LoreVia is still building this profile from the text."}
          </p>
        </div>
      </div>

      {expanded && (
        <div 
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 sm:p-6"
          onClick={() => setExpanded(false)}
        >
          <div 
            className={`relative z-50 max-h-[90vh] w-full max-w-4xl overflow-y-auto rounded-lg p-6 md:p-8 ${
              isDark ? "border border-slate-800 bg-slate-900 text-white" : "border border-slate-200 bg-white text-slate-900"
            }`}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="absolute top-4 right-4 sm:top-6 sm:right-6">
               <button
                 onClick={() => setExpanded(false)}
                 className={`rounded-md px-3 py-1.5 text-xs font-medium transition ${isDark ? "bg-slate-800 text-slate-200 hover:bg-slate-700" : "bg-slate-100 text-slate-700 hover:bg-slate-200"}`}
               >
                 Close
               </button>
            </div>

            <div className="flex items-start justify-between gap-3 pr-20">
              <div className="min-w-0">
                <div className="flex items-start gap-3">
                  <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-md border text-sm font-semibold ${
                    isDark ? "border-slate-700 bg-slate-800 text-white" : "border-slate-200 bg-slate-100 text-slate-700"
                  }`}>
                    {String(character.name?.[0] ?? "?").toUpperCase()}
                  </div>
                  <div className="min-w-0">
                    <h3 className={`font-semibold text-3xl leading-tight break-words ${isDark ? "text-white" : "text-slate-900"}`}>{character.name}</h3>
                    <div className="mt-2 flex flex-wrap items-center gap-2">
                      <span className={`rounded-md px-2.5 py-1 text-3xs font-semibold uppercase tracking-[0.14em] ${
                        isDark ? "bg-slate-800 text-slate-200" : "bg-slate-100 text-slate-700"
                      }`}>
                        {character.role || "character"}
                      </span>
                      <span className={`rounded-md px-2.5 py-1 text-3xs font-semibold uppercase tracking-[0.14em] ${
                        isDark ? "bg-slate-800 text-slate-300" : "bg-slate-100 text-slate-600"
                      }`}>
                        {character.status ?? "alive"}
                      </span>
                      {typeof character.first_chapter === "number" ? (
                        <span className={`rounded-md px-2.5 py-1 text-3xs font-medium ${
                          isDark ? "bg-slate-800 text-slate-300" : "bg-slate-100 text-slate-600"
                        }`}>
                          ch. {character.first_chapter} debut
                        </span>
                      ) : null}
                    </div>
                  </div>
                </div>
                {character.aliases?.length ? (
                  <p className={`mt-3 text-xs ${isDark ? "text-slate-400" : "text-slate-500"}`}>
                    Also known as {character.aliases.join(", ")}
                  </p>
                ) : null}
              </div>

              <div className="flex shrink-0 items-center gap-2">
                {editable && bookId ? (
                  <>
                    <button
                      type="button"
                      onClick={(event) => {
                        event.stopPropagation()
                        setEditing((value) => !value)
                      }}
                      className={`rounded-md px-3 py-1.5 text-xs font-medium ${isDark ? "border border-slate-700 text-slate-200 hover:bg-slate-800" : "border border-slate-300 text-slate-700 hover:bg-slate-100"}`}
                    >
                      {editing ? "Close edit" : "Edit"}
                    </button>
                    <button
                      type="button"
                      onClick={handleShare}
                      className={`rounded-md px-3 py-1.5 text-xs font-medium ${isDark ? "border border-slate-700 text-slate-200 hover:bg-slate-800" : "border border-slate-300 text-slate-700 hover:bg-slate-100"}`}
                    >
                      {shareState === "copied" ? "Link copied" : shareState === "error" ? "Share failed" : "Share"}
                    </button>
                    <button
                      type="button"
                      onClick={(event) => {
                        event.stopPropagation()
                        void handleDelete()
                      }}
                      disabled={deleting}
                      className={`rounded-md px-3 py-1.5 text-xs font-medium ${isDark ? "border border-red-500/40 text-red-200 hover:bg-red-500/10 disabled:opacity-60" : "border border-red-300 text-red-700 hover:bg-red-50 disabled:opacity-60"}`}
                    >
                      {deleting ? "Deleting..." : "Delete"}
                    </button>
                  </>
                ) : null}
              </div>
            </div>

            {character.personality_tags?.length ? (
              <div className="mt-6 flex flex-wrap gap-2">
                {character.personality_tags.map((tag) => (
                  <span key={tag} className={`rounded-md px-2.5 py-1 text-xs ${isDark ? "bg-slate-800 text-slate-200" : "bg-slate-50 text-slate-700 border border-slate-200"}`}>
                    {tag}
                  </span>
                ))}
              </div>
            ) : null}

            <div className="mt-6">
              <p className={`text-3xs font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-slate-400"}`}>Overview</p>
              <p className={`mt-2 text-base leading-8 ${isDark ? "text-slate-200" : "text-slate-700"}`}>
                {character.description || "LoreVia is still building this profile from the text."}
              </p>
            </div>

            <div className="mt-6 grid gap-4 md:grid-cols-2">
              <div className={`rounded-lg border p-5 ${isDark ? "border-slate-800 bg-slate-900/50" : "border-slate-200 bg-slate-50"}`}>
                <p className={`text-3xs font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-slate-400"}`}>Snapshot</p>
                <div className="mt-4 space-y-3 text-sm">
                  {visible.slice(0, 5).map(([key, trait]) => trait ? (
                    <div key={key} className="flex items-start justify-between gap-4">
                      <span className={isDark ? "text-slate-400 capitalize" : "text-slate-500 capitalize"}>{key}</span>
                      <span className={isDark ? "text-slate-100 font-medium text-right" : "text-slate-900 font-medium text-right"}>{trait.value}</span>
                    </div>
                  ) : null)}
                  {visible.length === 0 ? <p className={isDark ? "text-sm text-slate-400" : "text-sm text-slate-500"}>Details emerging...</p> : null}
                </div>
              </div>

              <div className={`rounded-lg border p-5 ${isDark ? "border-slate-800 bg-slate-900/50" : "border-slate-200 bg-slate-50"}`}>
                <p className={`text-3xs font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-slate-400"}`}>Continuity</p>
                <div className="mt-4 space-y-4 text-sm">
                  <div className="flex items-start justify-between gap-4">
                    <span className={isDark ? "text-slate-400" : "text-slate-500"}>Last seen</span>
                    <span className={isDark ? "text-slate-100 font-medium" : "text-slate-900 font-medium"}>{character.last_seen_chapter ? `Chapter ${character.last_seen_chapter}` : "-"}</span>
                  </div>
                  <div className="flex items-start justify-between gap-4">
                    <span className={isDark ? "text-slate-400" : "text-slate-500"}>Mentions</span>
                    <span className={isDark ? "text-slate-100 font-medium" : "text-slate-900 font-medium"}>{character.mention_count ?? 0}</span>
                  </div>
                  <div>
                    <p className={isDark ? "text-slate-400" : "text-slate-500"}>Arc</p>
                    <p className={isDark ? "mt-1 text-slate-100" : "mt-1 text-slate-900"}>{character.arc_summary || "Still forming."}</p>
                  </div>
                </div>
              </div>
            </div>

            {editable && editing && bookId ? (
              <div
                className={`mt-6 rounded-lg border p-5 ${isDark ? "border-slate-800 bg-slate-900/50" : "border-slate-200 bg-slate-50"}`}
                onClick={(event) => event.stopPropagation()}
              >
                <div className="grid gap-4 md:grid-cols-2">
                  <label className="space-y-1">
                    <span className={`text-3xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-slate-400"}`}>Name</span>
                    <input value={draft.name} onChange={(event) => setDraft((value) => ({ ...value, name: event.target.value }))} className={`w-full rounded-md border px-3 py-2 text-sm ${isDark ? "border-slate-700 bg-slate-800 text-white" : "border-slate-300 bg-white text-slate-900"}`} />
                  </label>
                  <label className="space-y-1">
                    <span className={`text-3xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-slate-400"}`}>Aliases</span>
                    <input value={draft.aliases} onChange={(event) => setDraft((value) => ({ ...value, aliases: event.target.value }))} className={`w-full rounded-md border px-3 py-2 text-sm ${isDark ? "border-slate-700 bg-slate-800 text-white" : "border-slate-300 bg-white text-slate-900"}`} />
                    <span className={`block text-xs ${isDark ? "text-slate-500" : "text-slate-500"}`}>Separate multiple values with commas.</span>
                  </label>
                  <label className="space-y-1 md:col-span-2">
                    <span className={`text-3xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-slate-400"}`}>Description</span>
                    <textarea value={draft.description} onChange={(event) => setDraft((value) => ({ ...value, description: event.target.value }))} rows={4} className={`w-full rounded-md border px-3 py-2 text-sm ${isDark ? "border-slate-700 bg-slate-800 text-white" : "border-slate-300 bg-white text-slate-900"}`} />
                  </label>
                  <label className="space-y-1 md:col-span-2">
                    <span className={`text-3xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-slate-400"}`}>Arc summary</span>
                    <textarea value={draft.arcSummary} onChange={(event) => setDraft((value) => ({ ...value, arcSummary: event.target.value }))} rows={3} className={`w-full rounded-md border px-3 py-2 text-sm ${isDark ? "border-slate-700 bg-slate-800 text-white" : "border-slate-300 bg-white text-slate-900"}`} />
                  </label>
                  <label className="space-y-1">
                    <span className={`text-3xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-slate-400"}`}>Personality</span>
                    <input value={draft.personalityTags} onChange={(event) => setDraft((value) => ({ ...value, personalityTags: event.target.value }))} className={`w-full rounded-md border px-3 py-2 text-sm ${isDark ? "border-slate-700 bg-slate-800 text-white" : "border-slate-300 bg-white text-slate-900"}`} />
                    <span className={`block text-xs ${isDark ? "text-slate-500" : "text-slate-500"}`}>Separate multiple values with commas.</span>
                  </label>
                  <label className="space-y-1">
                    <span className={`text-3xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-slate-400"}`}>Motivations</span>
                    <input value={draft.motivations} onChange={(event) => setDraft((value) => ({ ...value, motivations: event.target.value }))} className={`w-full rounded-md border px-3 py-2 text-sm ${isDark ? "border-slate-700 bg-slate-800 text-white" : "border-slate-300 bg-white text-slate-900"}`} />
                    <span className={`block text-xs ${isDark ? "text-slate-500" : "text-slate-500"}`}>Separate multiple values with commas.</span>
                  </label>
                  <label className="space-y-1 md:col-span-2">
                    <span className={`text-3xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-slate-400"}`}>Fears</span>
                    <input value={draft.fears} onChange={(event) => setDraft((value) => ({ ...value, fears: event.target.value }))} className={`w-full rounded-md border px-3 py-2 text-sm ${isDark ? "border-slate-700 bg-slate-800 text-white" : "border-slate-300 bg-white text-slate-900"}`} />
                    <span className={`block text-xs ${isDark ? "text-slate-500" : "text-slate-500"}`}>Separate multiple values with commas.</span>
                  </label>
                </div>
                {error ? <p className="mt-3 text-sm text-red-500">{error}</p> : null}
                <div className="mt-5 flex flex-wrap gap-2">
                  <button type="button" disabled={saving} onClick={handleSave} className="rounded-md bg-slate-900 px-5 py-2 text-sm font-semibold text-white disabled:opacity-60">
                    {saving ? "Saving..." : "Save edits"}
                  </button>
                  <button
                    type="button"
                    disabled={exporting}
                    onClick={(event) => void handleExport(event, "pdf")}
                    className={`rounded-md px-4 py-2 text-sm font-medium ${isDark ? "border border-slate-700 text-slate-200 hover:bg-slate-800" : "border border-slate-300 text-slate-700 hover:bg-slate-50"}`}
                  >
                    Export PDF
                  </button>
                  <button
                    type="button"
                    disabled={exporting}
                    onClick={(event) => void handleExport(event, "docx")}
                    className={`rounded-md px-4 py-2 text-sm font-medium ${isDark ? "border border-slate-700 text-slate-200 hover:bg-slate-800" : "border border-slate-300 text-slate-700 hover:bg-slate-50"}`}
                  >
                    Export Word
                  </button>
                </div>
              </div>
            ) : null}

            <div className="mt-6 space-y-6">
              {relationshipSummaries.length > 0 ? (
                <div>
                  <p className={isDark ? "text-xs font-semibold uppercase tracking-[0.22em] text-slate-500" : "text-xs font-semibold uppercase tracking-[0.22em] text-slate-400"}>Relationships</p>
                  <div className="mt-3 space-y-2">
                    {relationshipSummaries.map((summary, index) => (
                      <p key={`${character.id}-rel-${index}`} className={`text-base leading-8 ${isDark ? "text-slate-200" : "text-slate-700"}`}>{summary}</p>
                    ))}
                  </div>
                </div>
              ) : null}
              {character.motivations.length > 0 ? <p className={isDark ? "text-base text-slate-200" : "text-base text-slate-700"}><span className="font-semibold uppercase text-xs tracking-widest text-slate-500 block mb-1">Motivations</span> {character.motivations.join(" • ")}</p> : null}
              {character.fears.length > 0 ? <p className={isDark ? "text-base text-slate-200" : "text-base text-slate-700"}><span className="font-semibold uppercase text-xs tracking-widest text-slate-500 block mb-1">Fears</span> {character.fears.join(" • ")}</p> : null}
              {character.arc_summary ? <p className={isDark ? "text-base leading-8 text-slate-200" : "text-base leading-8 text-slate-700"}><span className="font-semibold uppercase text-xs tracking-widest text-slate-500 block mb-2">Arc Summary</span> {character.arc_summary}</p> : null}

              {growthEvents.length > 0 ? (
                <div>
                  <p className={isDark ? "text-xs font-semibold uppercase tracking-[0.22em] text-slate-500" : "text-xs font-semibold uppercase tracking-[0.22em] text-slate-400"}>Key growth events</p>
                  <div className="mt-3 space-y-3">
                    {growthEvents
                      .slice()
                      .sort((left, right) => (right.chapter_number ?? right.chapter ?? 0) - (left.chapter_number ?? left.chapter ?? 0))
                      .map((event, index) => (
                        <div key={`${character.id}-growth-${index}`} className={`rounded-lg border px-5 py-4 text-base ${isDark ? "border-slate-800 bg-slate-900/50 text-slate-200" : "border-slate-200 bg-white text-slate-700"}`}>
                          <p className={isDark ? "font-medium text-white" : "font-medium text-slate-900"}>
                            {eventChapterLabel(event) ? `${eventChapterLabel(event)}: ` : ""}
                            {eventTitle(event)}
                          </p>
                        {eventDescription(event) ? <p className={isDark ? "mt-2 text-sm leading-relaxed text-slate-300" : "mt-2 text-sm leading-relaxed text-slate-600"}>{eventDescription(event)}</p> : null}
                        <div className="mt-3 flex flex-wrap gap-2 text-3xs">
                          {typeof event.impact_score === "number" ? (
                            <span className={`rounded-full px-2.5 py-1 ${isDark ? "bg-slate-800 text-slate-300" : "bg-slate-100 text-slate-600"}`}>
                              impact {event.impact_score}/10
                            </span>
                          ) : null}
                          {event.growth_direction ? (
                            <span className={`rounded-full px-2.5 py-1 capitalize ${isDark ? "bg-slate-800 text-slate-300" : "bg-slate-100 text-slate-600"}`}>
                              {event.growth_direction}
                            </span>
                          ) : null}
                          {typeof event.growth_magnitude === "number" ? (
                            <span className={`rounded-full px-2.5 py-1 ${isDark ? "bg-slate-800 text-slate-300" : "bg-slate-100 text-slate-600"}`}>
                              growth {event.growth_magnitude}/10
                            </span>
                          ) : null}
                          {event.is_major ? (
                            <span className={`rounded-full px-2.5 py-1 ${isDark ? "bg-amber-500/15 text-amber-300" : "bg-amber-100 text-amber-700"}`}>
                              major
                            </span>
                          ) : null}
                        </div>
                        {event.accomplishments?.length ? (
                          <p className={isDark ? "mt-3 text-xs leading-relaxed text-slate-400" : "mt-3 text-xs leading-relaxed text-slate-500"}>
                            Accomplishments: {event.accomplishments.join(", ")}
                          </p>
                        ) : null}
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}

              <div className={`rounded-lg border ${isDark ? "border-slate-800 bg-slate-900/50" : "border-slate-200 bg-slate-50"}`}>
                <button
                  type="button"
                  onClick={(event) => {
                    event.stopPropagation()
                    setAdvancedOpen((value) => !value)
                  }}
                  className="flex w-full items-center justify-between px-5 py-4 text-left"
                >
                  <div>
                    <p className={isDark ? "text-xs font-semibold uppercase tracking-[0.22em] text-slate-500" : "text-xs font-semibold uppercase tracking-[0.22em] text-slate-400"}>Advanced details</p>
                    <p className={isDark ? "mt-1 text-xs text-slate-400" : "mt-1 text-xs text-slate-500"}>
                      {isPaid ? "Expanded unique traits and profile detail." : "Upgrade to Author to unlock deeper character detail."}
                    </p>
                  </div>
                  <span className={isDark ? "text-sm text-slate-300 font-medium" : "text-sm text-slate-600 font-medium"}>{advancedOpen ? "Hide" : isPaid ? "Open" : "Preview"}</span>
                </button>
                {advancedOpen ? (
                  <div className={`border-t px-5 py-4 ${isDark ? "border-slate-800" : "border-slate-200"}`}>
                    {isPaid ? (
                      <div className="space-y-3">
                        {character.archetype ? <p className={isDark ? "text-sm text-slate-200" : "text-sm text-slate-700"}><span className="font-medium">Archetype:</span> {character.archetype}</p> : null}
                        {advancedTraits.length > 0 ? advancedTraits.map(([key, trait]) => trait ? (
                          <div key={`${character.id}-${key}`} className="flex items-start justify-between gap-3 text-sm">
                            <span className={isDark ? "text-slate-400 capitalize" : "text-slate-500 capitalize"}>{key}</span>
                            <span className={isDark ? "text-slate-100 text-right" : "text-slate-700 text-right"}>{trait.value}</span>
                          </div>
                        ) : null) : <p className={isDark ? "text-sm text-slate-400" : "text-sm text-slate-500"}>More advanced details will appear as the profile deepens.</p>}
                      </div>
                    ) : (
                      <p className={isDark ? "text-sm leading-relaxed text-slate-300" : "text-sm leading-relaxed text-slate-600"}>Premium character detail expands the profile with unique traits, aliases, and richer evolving context.</p>
                    )}
                  </div>
                ) : null}
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  )
})
