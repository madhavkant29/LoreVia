"use client"

import { useState, type KeyboardEvent, type MouseEvent } from "react"
import { booksApi } from "@/lib/api/books"
import { CONFIDENCE_THRESHOLDS } from "@/lib/constants"
import { useAuthStore } from "@/lib/stores/authStore"
import type { Character } from "@/types/character"

interface Props {
  character: Character
  bookId?: string
  compact?: boolean
  editable?: boolean
  onUpdated?: (character: Character) => void
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

export function CharacterCard({ character, bookId, compact = false, editable = false, onUpdated, theme = "light" }: Props) {
  const [expanded, setExpanded] = useState(false)
  const [advancedOpen, setAdvancedOpen] = useState(false)
  const [editing, setEditing] = useState(false)
  const [saving, setSaving] = useState(false)
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

  const user = useAuthStore((state) => state.user)
  const traits = character.trait_state ?? {}
  const visible = Object.entries(traits).filter(([, t]) => t && t.confidence >= CONFIDENCE_THRESHOLDS.SHOW_IN_UI && t.value)
  const isDark = theme === "dark"
  const relationshipSummaries = character.relationship_summaries ?? []
  const growthEvents = character.growth_events ?? []
  const isPaid = user?.tier === "pro" || user?.tier === "power" || user?.tier === "admin"
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

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={toggleExpanded}
      onKeyDown={handleCardKeyDown}
      className={`w-full text-left rounded-[1.2rem] border p-5 ${compact ? "" : "transition hover:-translate-y-0.5 hover:shadow-[0_20px_60px_-50px_rgba(15,23,42,0.45)]"} ${
        isDark ? "border-white/10 bg-white/[0.04] text-white" : "border-stone-200/80 bg-[linear-gradient(180deg,rgba(255,255,255,0.96),rgba(248,245,240,0.96))] text-stone-950"
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-start gap-3">
            <div className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-[0.95rem] border text-sm font-semibold ${
              isDark ? "border-white/10 bg-white/8 text-white" : "border-stone-200 bg-stone-100 text-stone-700"
            }`}>
              {String(character.name?.[0] ?? "?").toUpperCase()}
            </div>
            <div className="min-w-0">
              <h3 className={`truncate font-serif text-[1.75rem] leading-none ${isDark ? "text-white" : "text-stone-950"}`}>{character.name}</h3>
              <div className="mt-2 flex flex-wrap items-center gap-2">
                <span className={`rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] ${
                  isDark ? "bg-white/10 text-slate-200" : "bg-stone-100 text-stone-700"
                }`}>
                  {character.role || "character"}
                </span>
                <span className={`rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] ${
                  isDark ? "bg-white/10 text-slate-300" : "bg-stone-100 text-stone-600"
                }`}>
                  {character.status ?? "alive"}
                </span>
                {typeof character.first_chapter === "number" ? (
                  <span className={`rounded-full px-3 py-1 text-[11px] font-medium ${
                    isDark ? "bg-white/10 text-slate-300" : "bg-stone-100 text-stone-600"
                  }`}>
                    ch. {character.first_chapter} debut
                  </span>
                ) : null}
              </div>
            </div>
          </div>
          {character.aliases?.length ? (
            <p className={`mt-3 text-xs ${isDark ? "text-slate-400" : "text-stone-500"}`}>
              Also known as {character.aliases.slice(0, 3).join(", ")}
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
                  setExpanded(true)
                }}
                className={`rounded-full px-3 py-1.5 text-xs font-medium ${isDark ? "border border-white/10 text-slate-200 hover:bg-white/8" : "border border-stone-300 text-stone-700 hover:bg-stone-100"}`}
              >
                {editing ? "Close edit" : "Edit"}
              </button>
              <button
                type="button"
                onClick={handleShare}
                className={`rounded-full px-3 py-1.5 text-xs font-medium ${isDark ? "border border-white/10 text-slate-200 hover:bg-white/8" : "border border-stone-300 text-stone-700 hover:bg-stone-100"}`}
              >
                {shareState === "copied" ? "Link copied" : shareState === "error" ? "Share failed" : "Share"}
              </button>
            </>
          ) : null}
          {!compact ? <span className={isDark ? "text-xs text-slate-400" : "text-xs text-stone-500"}>{expanded ? "Collapse" : "Open"}</span> : null}
        </div>
      </div>

      {character.personality_tags?.length ? (
        <div className="mt-4 flex flex-wrap gap-2">
          {character.personality_tags.slice(0, expanded ? 6 : 4).map((tag) => (
            <span key={tag} className={`rounded-full px-3 py-1 text-xs ${isDark ? "bg-white/10 text-slate-200" : "bg-white text-stone-700 border border-stone-200/70"}`}>
              {tag}
            </span>
          ))}
        </div>
      ) : null}

      {!compact ? (
        <div className="mt-4">
          <p className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Overview</p>
          <p className={`mt-2 text-sm leading-7 ${isDark ? "text-slate-200" : "text-stone-700"}`}>
            {character.description
              ? (expanded ? clampText(character.description, 520) : firstSentence(character.description, 240))
              : "LoreVia is still building this profile from the text."}
          </p>
        </div>
      ) : null}

      {!compact && (
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          <div className={`rounded-[1rem] border p-4 ${isDark ? "border-white/10 bg-black/15" : "border-stone-200/80 bg-stone-50/90"}`}>
            <p className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Snapshot</p>
            <div className="mt-3 space-y-2 text-sm">
              {visible.slice(0, 5).map(([key, trait]) => trait ? (
                <div key={key} className="flex items-start justify-between gap-4">
                  <span className={isDark ? "text-slate-400 capitalize" : "text-stone-500 capitalize"}>{key}</span>
                  <span className={isDark ? "text-slate-100 font-medium text-right" : "text-stone-900 font-medium text-right"}>{trait.value}</span>
                </div>
              ) : null)}
              {visible.length === 0 ? <p className={isDark ? "text-sm text-slate-400" : "text-sm text-stone-500"}>Details emerging...</p> : null}
            </div>
          </div>

          <div className={`rounded-[1rem] border p-4 ${isDark ? "border-white/10 bg-black/15" : "border-stone-200/80 bg-stone-50/90"}`}>
            <p className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Continuity</p>
            <div className="mt-3 space-y-3 text-sm">
              <div className="flex items-start justify-between gap-4">
                <span className={isDark ? "text-slate-400" : "text-stone-500"}>Last seen</span>
                <span className={isDark ? "text-slate-100" : "text-stone-900"}>{character.last_seen_chapter ? `Chapter ${character.last_seen_chapter}` : "-"}</span>
              </div>
              <div className="flex items-start justify-between gap-4">
                <span className={isDark ? "text-slate-400" : "text-stone-500"}>Mentions</span>
                <span className={isDark ? "text-slate-100" : "text-stone-900"}>{character.mention_count ?? 0}</span>
              </div>
              <div>
                <p className={isDark ? "text-slate-400" : "text-stone-500"}>Arc</p>
                <p className={isDark ? "text-slate-100" : "text-stone-900"}>{character.arc_summary ? clampText(character.arc_summary, 160) : "Still forming."}</p>
              </div>
            </div>
          </div>
        </div>
      )}

      {!compact && expanded ? (
        <div className={`mt-5 border-t pt-5 ${isDark ? "border-white/10" : "border-stone-200"}`}>
          {editable && editing && bookId ? (
            <div
              className={`mb-5 rounded-[1rem] border p-4 ${isDark ? "border-white/10 bg-black/15" : "border-stone-200 bg-stone-50/90"}`}
              onClick={(event) => event.stopPropagation()}
            >
              <div className="grid gap-3 md:grid-cols-2">
                <label className="space-y-1">
                  <span className={`text-[11px] font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Name</span>
                  <input value={draft.name} onChange={(event) => setDraft((value) => ({ ...value, name: event.target.value }))} className={`w-full rounded-xl border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-black/20 text-white" : "border-stone-300 bg-white text-stone-900"}`} />
                </label>
                <label className="space-y-1">
                  <span className={`text-[11px] font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Aliases</span>
                  <input value={draft.aliases} onChange={(event) => setDraft((value) => ({ ...value, aliases: event.target.value }))} placeholder="Comma separated" className={`w-full rounded-xl border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-black/20 text-white" : "border-stone-300 bg-white text-stone-900"}`} />
                </label>
                <label className="space-y-1 md:col-span-2">
                  <span className={`text-[11px] font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Description</span>
                  <textarea value={draft.description} onChange={(event) => setDraft((value) => ({ ...value, description: event.target.value }))} rows={4} className={`w-full rounded-xl border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-black/20 text-white" : "border-stone-300 bg-white text-stone-900"}`} />
                </label>
                <label className="space-y-1 md:col-span-2">
                  <span className={`text-[11px] font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Arc summary</span>
                  <textarea value={draft.arcSummary} onChange={(event) => setDraft((value) => ({ ...value, arcSummary: event.target.value }))} rows={3} className={`w-full rounded-xl border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-black/20 text-white" : "border-stone-300 bg-white text-stone-900"}`} />
                </label>
                <label className="space-y-1">
                  <span className={`text-[11px] font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Personality</span>
                  <input value={draft.personalityTags} onChange={(event) => setDraft((value) => ({ ...value, personalityTags: event.target.value }))} placeholder="Comma separated" className={`w-full rounded-xl border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-black/20 text-white" : "border-stone-300 bg-white text-stone-900"}`} />
                </label>
                <label className="space-y-1">
                  <span className={`text-[11px] font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Motivations</span>
                  <input value={draft.motivations} onChange={(event) => setDraft((value) => ({ ...value, motivations: event.target.value }))} placeholder="Comma separated" className={`w-full rounded-xl border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-black/20 text-white" : "border-stone-300 bg-white text-stone-900"}`} />
                </label>
                <label className="space-y-1 md:col-span-2">
                  <span className={`text-[11px] font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Fears</span>
                  <input value={draft.fears} onChange={(event) => setDraft((value) => ({ ...value, fears: event.target.value }))} placeholder="Comma separated" className={`w-full rounded-xl border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-black/20 text-white" : "border-stone-300 bg-white text-stone-900"}`} />
                </label>
              </div>
              {error ? <p className="mt-3 text-sm text-red-500">{error}</p> : null}
              <div className="mt-4 flex flex-wrap gap-2">
                <button type="button" disabled={saving} onClick={handleSave} className="rounded-full bg-slate-900 px-4 py-2 text-xs font-semibold text-white disabled:opacity-60">
                  {saving ? "Saving..." : "Save edits"}
                </button>
                <button
                  type="button"
                  disabled={exporting}
                  onClick={(event) => void handleExport(event, "pdf")}
                  className={`rounded-full px-4 py-2 text-xs font-medium ${isDark ? "border border-white/10 text-slate-200 hover:bg-white/8" : "border border-stone-300 text-stone-700 hover:bg-white"}`}
                >
                  Export PDF
                </button>
                <button
                  type="button"
                  disabled={exporting}
                  onClick={(event) => void handleExport(event, "docx")}
                  className={`rounded-full px-4 py-2 text-xs font-medium ${isDark ? "border border-white/10 text-slate-200 hover:bg-white/8" : "border border-stone-300 text-stone-700 hover:bg-white"}`}
                >
                  Export Word
                </button>
              </div>
            </div>
          ) : null}

          <div className="space-y-4">
            {relationshipSummaries.length > 0 ? (
              <div>
                <p className={isDark ? "text-xs font-semibold uppercase tracking-[0.22em] text-slate-500" : "text-xs font-semibold uppercase tracking-[0.22em] text-stone-400"}>Relationships</p>
                <div className="mt-2 space-y-2">
                  {relationshipSummaries.map((summary, index) => (
                    <p key={`${character.id}-rel-${index}`} className={`text-sm leading-7 ${isDark ? "text-slate-200" : "text-stone-700"}`}>{summary}</p>
                  ))}
                </div>
              </div>
            ) : null}
            {character.motivations.length > 0 ? <p className={isDark ? "text-sm text-slate-200" : "text-sm text-stone-700"}><span className="font-medium">Motivations:</span> {character.motivations.slice(0, 8).join(" • ")}</p> : null}
            {character.fears.length > 0 ? <p className={isDark ? "text-sm text-slate-200" : "text-sm text-stone-700"}><span className="font-medium">Fears:</span> {character.fears.slice(0, 8).join(" • ")}</p> : null}
            {character.arc_summary ? <p className={isDark ? "text-sm text-slate-200" : "text-sm text-stone-700"}><span className="font-medium">Arc:</span> {character.arc_summary}</p> : null}

            {growthEvents.length > 0 ? (
              <div>
                <p className={isDark ? "text-xs font-semibold uppercase tracking-[0.22em] text-slate-500" : "text-xs font-semibold uppercase tracking-[0.22em] text-stone-400"}>Key growth events</p>
                <div className="mt-2 space-y-2">
                  {growthEvents.slice(-4).reverse().map((event, index) => (
                    <div key={`${character.id}-growth-${index}`} className={`rounded-[0.95rem] border px-4 py-3 text-sm ${isDark ? "border-white/10 bg-white/[0.04] text-slate-200" : "border-stone-200/70 bg-white text-stone-700"}`}>
                      <p className={isDark ? "font-medium text-white" : "font-medium text-stone-900"}>
                        {typeof event.chapter === "number" ? `Chapter ${event.chapter}: ` : ""}
                        {event.event}
                      </p>
                      {event.impact ? <p className={isDark ? "mt-1 text-slate-300" : "mt-1 text-stone-600"}>{event.impact}</p> : null}
                    </div>
                  ))}
                </div>
              </div>
            ) : null}

            <div className={`rounded-xl border ${isDark ? "border-white/10 bg-white/5" : "border-stone-200 bg-stone-50/80"}`}>
              <button
                type="button"
                onClick={(event) => {
                  event.stopPropagation()
                  setAdvancedOpen((value) => !value)
                }}
                className="flex w-full items-center justify-between px-3 py-2 text-left"
              >
                <div>
                  <p className={isDark ? "text-xs font-semibold uppercase tracking-[0.22em] text-slate-500" : "text-xs font-semibold uppercase tracking-[0.22em] text-stone-400"}>Advanced details</p>
                  <p className={isDark ? "text-[11px] text-slate-400" : "text-[11px] text-stone-500"}>
                    {isPaid ? "Expanded unique traits and profile detail." : "Upgrade to Pro to unlock deeper character detail."}
                  </p>
                </div>
                <span className={isDark ? "text-xs text-slate-300" : "text-xs text-stone-600"}>{advancedOpen ? "Hide" : isPaid ? "Open" : "Preview"}</span>
              </button>
              {advancedOpen ? (
                <div className={`border-t px-3 py-3 ${isDark ? "border-white/10" : "border-stone-200"}`}>
                  {isPaid ? (
                    <div className="space-y-2">
                      {character.archetype ? <p className={isDark ? "text-xs text-slate-200" : "text-xs text-stone-700"}><span className="font-medium">Archetype:</span> {character.archetype}</p> : null}
                      {advancedTraits.length > 0 ? advancedTraits.map(([key, trait]) => trait ? (
                        <div key={`${character.id}-${key}`} className="flex items-start justify-between gap-3 text-xs">
                          <span className={isDark ? "text-slate-400 capitalize" : "text-stone-500 capitalize"}>{key}</span>
                          <span className={isDark ? "text-slate-100 text-right" : "text-stone-700 text-right"}>{trait.value}</span>
                        </div>
                      ) : null) : <p className={isDark ? "text-xs text-slate-400" : "text-xs text-stone-500"}>More advanced details will appear as the profile deepens.</p>}
                    </div>
                  ) : (
                    <p className={isDark ? "text-xs text-slate-300" : "text-xs text-stone-600"}>Premium character detail expands the profile with unique traits, aliases, and richer evolving context.</p>
                  )}
                </div>
              ) : null}
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )
}
