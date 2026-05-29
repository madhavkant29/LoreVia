"use client"

import { useMemo, useRef, useState, useEffect } from "react"
import { useParams } from "next/navigation"
import Link from "next/link"

import { readerApi } from "@/lib/api/reader"
import { booksApi } from "@/lib/api/books"
import type { ChapterCharacter, ContextResult } from "@/types/reader"

interface Props {
  result: ContextResult | null
  loading: boolean
  onClose: () => void
  mobileSheet?: boolean
  theme: "light" | "dark"
  selectedQuote: string | null
  chapterNumber: number
  chapterTitle: string | null
  characters: ChapterCharacter[]
}

export function ContextPanel({
  result,
  loading,
  onClose,
  mobileSheet = false,
  theme,
  selectedQuote,
  chapterNumber,
  chapterTitle,
  characters,
}: Props) {
  const { bookId } = useParams<{ bookId: string }>()
  const [savingQuote, setSavingQuote] = useState(false)
  const [quoteCharacter, setQuoteCharacter] = useState("")
  const [quoteNote, setQuoteNote] = useState("")
  const [dragOffset, setDragOffset] = useState(0)
  const dragStartRef = useRef<number | null>(null)
  const panelRef = useRef<HTMLDivElement | null>(null)
  const activeCharacter = result?.type === "character" ? result.character : null
  const isDark = theme === "dark"
  
  // Edit state
  const [editing, setEditing] = useState(false)
  const [saving, setSaving] = useState(false)
  const [editError, setEditError] = useState<string | null>(null)
  const [showBiography, setShowBiography] = useState(false)
  const [showLinks, setShowLinks] = useState(false)
  const [showRecall, setShowRecall] = useState(false)
  const [recallLoading, setRecallLoading] = useState(false)
  const [recallText, setRecallText] = useState<string | null>(null)
  const [traitsExpanded, setTraitsExpanded] = useState(false)
  const [draft, setDraft] = useState({
    name: activeCharacter?.name || "",
    aliases: activeCharacter?.aliases?.join(", ") || "",
    description: activeCharacter?.description || "",
    personalityTags: activeCharacter?.personality_tags?.join(", ") || "",
    motivations: activeCharacter?.motivations?.join(", ") || "",
    fears: activeCharacter?.fears?.join(", ") || "",
  })

  const shell = isDark
    ? {
        container: "border-white/5 bg-[#000000] text-white",
        sticky: "border-white/5 bg-[#000000]",
        tabActive: "bg-white/10 text-white",
        tab: "text-stone-500 hover:text-stone-300",
        card: "border-white/5 bg-white/[0.02]",
        subCard: "border-white/5 bg-white/[0.03]",
        muted: "text-stone-500",
        body: "text-stone-400",
        input: "border-white/10 bg-white/5 text-white placeholder:text-stone-600",
        button: "bg-white text-black hover:bg-white/90",
        line: "bg-white/10",
        title: "text-white",
        heading: "text-white",
        chip: "bg-white/5 text-stone-400",
        icon: "bg-white/5 text-stone-400",
        accent: "text-stone-400",
      }
    : {
        container: "border-stone-200/80 bg-white text-stone-950",
        sticky: "border-stone-200/60 bg-white",
        tabActive: "bg-stone-100 text-stone-900",
        tab: "text-stone-400 hover:text-stone-600",
        card: "border-stone-200/60 bg-stone-50/50",
        subCard: "border-stone-200/60 bg-white",
        muted: "text-stone-400",
        body: "text-stone-600",
        input: "border-stone-200 bg-white text-stone-900 placeholder:text-stone-400",
        button: "bg-stone-900 text-white hover:bg-stone-800",
        line: "bg-stone-200",
        title: "text-stone-900",
        heading: "text-stone-900",
        chip: "bg-stone-100 text-stone-600",
        icon: "bg-stone-100 text-stone-600",
        accent: "text-stone-600",
      }

  const characterOptions = useMemo(
    () => Array.from(new Set((characters ?? []).map((character) => character.name).filter(Boolean))).sort(),
    [characters]
  )

  // Update draft when activeCharacter changes
  useMemo(() => {
    if (activeCharacter) {
      setDraft({
        name: activeCharacter.name || "",
        aliases: activeCharacter.aliases?.join(", ") || "",
        description: activeCharacter.description || "",
        personalityTags: activeCharacter.personality_tags?.join(", ") || "",
        motivations: activeCharacter.motivations?.join(", ") || "",
        fears: activeCharacter.fears?.join(", ") || "",
      })
    }
  }, [activeCharacter])

  // Click outside to close
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (panelRef.current && !panelRef.current.contains(event.target as Node)) {
        onClose()
      }
    }

    document.addEventListener("mousedown", handleClickOutside)
    return () => {
      document.removeEventListener("mousedown", handleClickOutside)
    }
  }, [onClose])

  async function handleSaveEdit() {
    if (!bookId || !activeCharacter) return
    setSaving(true)
    setEditError(null)
    try {
      await booksApi.updateCharacter(bookId, activeCharacter.id, {
        name: draft.name.trim(),
        aliases: draft.aliases.split(",").map((s: string) => s.trim()).filter(Boolean),
        description: draft.description.trim() || null,
        personalityTags: draft.personalityTags.split(",").map((s: string) => s.trim()).filter(Boolean),
        motivations: draft.motivations.split(",").map((s: string) => s.trim()).filter(Boolean),
        fears: draft.fears.split(",").map((s: string) => s.trim()).filter(Boolean),
      })
      setEditing(false)
    } catch {
      setEditError("Could not save character changes.")
    } finally {
      setSaving(false)
    }
  }

  async function handleRecall() {
    if (!bookId || !activeCharacter) return
    setRecallLoading(true)
    setShowRecall(true)
    try {
      const response = await readerApi.getRecall(bookId)
      setRecallText(response.recall)
    } catch {
      setRecallText("Could not load recall.")
    } finally {
      setRecallLoading(false)
    }
  }

  const saveSelectedQuote = async () => {
    if (!selectedQuote?.trim()) return
    setSavingQuote(true)
    try {
      await readerApi.saveQuote(bookId, {
        quote_text: selectedQuote,
        chapter_number: chapterNumber,
        character_name: quoteCharacter || null,
        note: quoteNote || null,
      })
      setQuoteCharacter("")
      setQuoteNote("")
    } finally {
      setSavingQuote(false)
    }
  }

  const startDrag = (clientY: number) => {
    if (!mobileSheet) return
    dragStartRef.current = clientY
  }

  const moveDrag = (clientY: number) => {
    if (!mobileSheet || dragStartRef.current === null) return
    setDragOffset(Math.max(0, clientY - dragStartRef.current))
  }

  const endDrag = () => {
    if (!mobileSheet) return
    if (dragOffset > 120) {
      onClose()
    }
    dragStartRef.current = null
    setDragOffset(0)
  }

  return (
    <aside
      ref={panelRef}
      className={`fixed inset-x-0 bottom-0 z-40 flex h-[78dvh] flex-col overflow-hidden rounded-t-[1.9rem] border shadow-[0_-24px_60px_-30px_rgba(15,23,42,0.28)] md:static md:inset-auto md:h-auto md:max-h-none md:w-[23rem] md:rounded-none md:border-l md:border-t-0 md:shadow-[-24px_0_64px_-48px_rgba(79,70,229,0.3)] xl:w-[25rem] ${shell.container}`}
      style={{
        transform: mobileSheet ? `translateY(${dragOffset}px)` : undefined,
        transition: dragStartRef.current === null ? "transform 180ms ease-out" : undefined,
      }}
    >
      <div
        className={`shrink-0 border-b backdrop-blur ${shell.sticky}`}
        onTouchStart={(event) => startDrag(event.touches[0]?.clientY ?? 0)}
        onTouchMove={(event) => moveDrag(event.touches[0]?.clientY ?? 0)}
        onTouchEnd={endDrag}
      >
        <div className="flex justify-center pt-3 md:hidden">
          <span className={`h-1.5 w-12 rounded-full ${shell.line}`} />
        </div>
        <div className="px-5 py-3 md:py-4">
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className={`text-3xs font-medium uppercase tracking-[0.2em] ${shell.muted}`}>Character</p>
              <h2 className={`mt-1 text-2xl font-medium leading-tight ${shell.title}`} style={{ fontFamily: "var(--reader-display)" }}>
                Details
              </h2>
            </div>
            <button
              onClick={onClose}
              aria-label="Close context panel"
              className={`rounded-lg px-2 py-1.5 text-xs transition ${shell.tab}`}
            >
              ✕
            </button>
          </div>
        </div>
      </div>

      <div className="reader-scrollbar app-scroll min-h-0 flex-1 overflow-y-auto px-5 pb-[max(env(safe-area-inset-bottom),1rem)] pt-4 md:pt-5">
        {selectedQuote?.trim() ? (
          <div className={`mb-5 rounded-lg border p-4 ${shell.card}`}>
            <p className={`text-3xs font-semibold uppercase tracking-[0.24em] ${shell.accent}`}>Selected passage</p>
            <p className={`mt-3 whitespace-pre-wrap text-sm leading-7 ${shell.body}`}>{selectedQuote.trim()}</p>
            <div className="mt-4 space-y-3">
              <div className={`rounded-md border px-3 py-2 text-xs ${shell.card}`}>
                <span className="font-medium">Chapter:</span> {chapterTitle ? `${chapterNumber} - ${chapterTitle}` : `Chapter ${chapterNumber}`}
              </div>
              <select
                value={quoteCharacter}
                onChange={(event) => setQuoteCharacter(event.target.value)}
                className={`w-full rounded-md border px-3 py-2 text-sm ${shell.input}`}
              >
                <option value="">Who said it? (optional)</option>
                {characterOptions.map((name) => (
                  <option key={name} value={name}>
                    {name}
                  </option>
                ))}
              </select>
              <textarea
                value={quoteNote}
                onChange={(event) => setQuoteNote(event.target.value)}
                placeholder="Why does this line matter?"
                rows={3}
                className={`w-full rounded-md border px-3 py-2 text-sm ${shell.input}`}
              />
              <button onClick={saveSelectedQuote} className={`w-full rounded-md px-4 py-3 text-sm font-semibold transition ${shell.button}`}>
                {savingQuote ? "Saving..." : "Save line bookmark"}
              </button>
            </div>
          </div>
        ) : null}

        {loading ? <div className={`py-8 text-center text-sm ${shell.muted}`}>Loading...</div> : null}

        {!loading && activeCharacter ? (
          <div className={`rounded-xl border p-5 ${shell.card}`}>
            {editing ? (
              <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
                <div className={`relative w-full max-w-2xl max-h-[90vh] overflow-y-auto rounded-2xl p-6 md:p-8 ${
                  isDark ? "bg-[#000000] text-white border border-white/10" : "bg-white text-stone-900 border border-stone-200"
                }`}>
                  <div className="absolute top-4 right-4">
                    <button
                      onClick={() => setEditing(false)}
                      className={`rounded-lg px-3 py-1.5 text-xs font-medium transition ${shell.tab}`}
                    >
                      ✕
                    </button>
                  </div>
                  
                  <h3 className={`text-2xl font-medium mb-6 ${shell.heading}`}>Edit Character</h3>
                  
                  <div className="space-y-4">
                    <div>
                      <label className={`block text-xs font-medium uppercase tracking-[0.15em] ${shell.muted} mb-2`}>Name</label>
                      <textarea
                        value={draft.name}
                        onChange={(e) => setDraft({ ...draft, name: e.target.value })}
                        rows={4}
                        className={`w-full rounded-lg px-3 py-2 text-sm ${shell.input}`}
                      />
                    </div>
                    <div>
                      <label className={`block text-xs font-medium uppercase tracking-[0.15em] ${shell.muted} mb-2`}>Aliases (comma separated)</label>
                      <textarea
                        value={draft.aliases}
                        onChange={(e) => setDraft({ ...draft, aliases: e.target.value })}
                        rows={4}
                        className={`w-full rounded-lg px-3 py-2 text-sm ${shell.input}`}
                      />
                    </div>
                    <div>
                      <label className={`block text-xs font-medium uppercase tracking-[0.15em] ${shell.muted} mb-2`}>Description</label>
                      <textarea
                        value={draft.description}
                        onChange={(e) => setDraft({ ...draft, description: e.target.value })}
                        rows={12}
                        className={`w-full rounded-lg px-3 py-2 text-sm ${shell.input}`}
                      />
                    </div>
                    <div>
                      <label className={`block text-xs font-medium uppercase tracking-[0.15em] ${shell.muted} mb-2`}>Personality Tags (comma separated)</label>
                      <textarea
                        value={draft.personalityTags}
                        onChange={(e) => setDraft({ ...draft, personalityTags: e.target.value })}
                        rows={4}
                        className={`w-full rounded-lg px-3 py-2 text-sm ${shell.input}`}
                      />
                    </div>
                    <div>
                      <label className={`block text-xs font-medium uppercase tracking-[0.15em] ${shell.muted} mb-2`}>Motivations (comma separated)</label>
                      <textarea
                        value={draft.motivations}
                        onChange={(e) => setDraft({ ...draft, motivations: e.target.value })}
                        rows={4}
                        className={`w-full rounded-lg px-3 py-2 text-sm ${shell.input}`}
                      />
                    </div>
                    <div>
                      <label className={`block text-xs font-medium uppercase tracking-[0.15em] ${shell.muted} mb-2`}>Fears (comma separated)</label>
                      <textarea
                        value={draft.fears}
                        onChange={(e) => setDraft({ ...draft, fears: e.target.value })}
                        rows={4}
                        className={`w-full rounded-lg px-3 py-2 text-sm ${shell.input}`}
                      />
                    </div>
                    {editError && <p className="text-sm text-red-500">{editError}</p>}
                    <div className="flex gap-2 pt-4">
                      <button
                        onClick={handleSaveEdit}
                        disabled={saving}
                        className={`flex-1 rounded-lg px-4 py-3 text-sm font-medium transition ${shell.button} disabled:opacity-60`}
                      >
                        {saving ? "Saving..." : "Save Changes"}
                      </button>
                      <button
                        onClick={() => setEditing(false)}
                        className={`rounded-lg px-4 py-3 text-sm font-medium transition ${shell.tab}`}
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <>
                <div className="flex items-start gap-4">
                  <div className={`flex h-14 w-14 shrink-0 items-center justify-center rounded-lg ${isDark ? "bg-white/5" : "bg-stone-100"} text-xl font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>
                    {String(activeCharacter.name?.[0] ?? "?").toUpperCase()}
                  </div>
                  <div className="min-w-0 flex-1">
                    <h3 className={`text-xl font-medium leading-tight ${shell.heading}`} style={{ fontFamily: "var(--reader-display)" }}>
                      {activeCharacter.name}
                    </h3>
                    {activeCharacter.role ? <p className={`mt-1 text-xs uppercase tracking-[0.1em] ${shell.muted}`}>{activeCharacter.role}</p> : null}
                    {activeCharacter.aliases?.length ? (
                      <p className={`mt-1 text-xs truncate ${shell.muted}`}>Also known as {activeCharacter.aliases.join(", ")}</p>
                    ) : null}
                  </div>
                </div>

                <div className="mt-6">
                  <p className={`text-xs font-medium uppercase tracking-[0.15em] ${shell.muted}`}>Overview</p>
                  <p className={`mt-2 text-sm leading-6 ${shell.body}`}>
                    {activeCharacter.description || "LoreVia is still building this character profile from the text around this passage."}
                  </p>
                </div>

                {activeCharacter.personality_tags?.length ? (
                  <div className="mt-6">
                    <p className={`text-xs font-medium uppercase tracking-[0.15em] ${shell.muted}`}>Traits</p>
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {(traitsExpanded ? activeCharacter.personality_tags : activeCharacter.personality_tags.slice(0, 3)).map((tag: string) => (
                        <span key={tag} className={`rounded-md px-2 py-0.5 text-3xs capitalize ${shell.chip}`}>
                          {tag}
                        </span>
                      ))}
                      {activeCharacter.personality_tags.length > 3 && !traitsExpanded ? (
                        <span 
                          onClick={() => setTraitsExpanded(true)}
                          className={`rounded-md px-2 py-0.5 text-3xs cursor-pointer ${shell.muted} hover:underline`}
                        >
                          +{activeCharacter.personality_tags.length - 3} more
                        </span>
                      ) : null}
                      {traitsExpanded && activeCharacter.personality_tags.length > 3 ? (
                        <span 
                          onClick={() => setTraitsExpanded(false)}
                          className={`rounded-md px-2 py-0.5 text-3xs cursor-pointer ${shell.muted} hover:underline`}
                        >
                          Show less
                        </span>
                      ) : null}
                    </div>
                  </div>
                ) : null}

                {activeCharacter.motivations?.length ? (
                  <div className="mt-6">
                    <p className={`text-xs font-medium uppercase tracking-[0.15em] ${shell.muted}`}>Motivations</p>
                    <p className={`mt-2 text-sm leading-6 ${shell.body}`}>
                      {activeCharacter.motivations.join(" • ")}
                    </p>
                  </div>
                ) : null}

                {activeCharacter.fears?.length ? (
                  <div className="mt-6">
                    <p className={`text-xs font-medium uppercase tracking-[0.15em] ${shell.muted}`}>Fears</p>
                    <p className={`mt-2 text-sm leading-6 ${shell.body}`}>
                      {activeCharacter.fears.join(" • ")}
                    </p>
                  </div>
                ) : null}

                <div className="mt-6">
                  <p className={`text-xs font-medium uppercase tracking-[0.15em] ${shell.muted}`}>Actions</p>
                  <div className="mt-2 flex gap-2">
                    <button 
                      onClick={() => setEditing(true)} 
                      className={`rounded-md px-3 py-1.5 text-xs font-medium transition ${isDark ? "bg-white/10 text-white hover:bg-white/20" : "bg-stone-100 text-stone-900 hover:bg-stone-200"}`}
                    >
                      Edit
                    </button>
                    <button 
                      onClick={() => setShowLinks(!showLinks)} 
                      className={`rounded-md px-3 py-1.5 text-xs font-medium transition ${isDark ? "bg-white/10 text-white hover:bg-white/20" : "bg-stone-100 text-stone-900 hover:bg-stone-200"}`}
                    >
                      Links
                    </button>
                    <button 
                      onClick={() => {
                        if (showRecall) {
                          setShowRecall(false)
                        } else {
                          handleRecall()
                        }
                      }} 
                      className={`rounded-md px-3 py-1.5 text-xs font-medium transition ${isDark ? "bg-white/10 text-white hover:bg-white/20" : "bg-stone-100 text-stone-900 hover:bg-stone-200"}`}
                    >
                      Recall
                    </button>
                  </div>
                </div>

                {showLinks && (
                  <div className="mt-4">
                    <p className={`text-xs font-medium uppercase tracking-[0.15em] ${shell.muted}`}>Character Links</p>
                    <p className={`mt-2 text-sm ${shell.body}`}>
                      Relationship links will appear here when character has established connections.
                    </p>
                  </div>
                )}

                {showRecall && (
                  <div className="mt-4">
                    <p className={`text-xs font-medium uppercase tracking-[0.15em] ${shell.muted}`}>Recall</p>
                    {recallLoading ? (
                      <p className={`mt-2 text-sm ${shell.muted}`}>Loading...</p>
                    ) : recallText ? (
                      <p className={`mt-2 text-sm leading-6 ${shell.body}`}>
                        {recallText}
                      </p>
                    ) : null}
                  </div>
                )}

                <Link
                  href={`/${bookId}/characters`}
                  onClick={onClose}
                  className={`mt-6 block w-full rounded-lg px-4 py-2.5 text-center text-sm font-medium transition ${shell.button}`}
                >
                  Open Lore Entry
                </Link>
              </>
            )}
          </div>
        ) : null}

        {!loading && result?.type === "search" ? (
          <div className="flex flex-col gap-3">
            {(result.results ?? []).length === 0 ? <p className={`text-sm ${shell.muted}`}>No relevant passages found.</p> : null}
            {(result.results ?? []).map((searchResult, index) => (
              <div key={index} className={`rounded-lg border p-4 ${shell.card}`}>
                <div className="mb-1 flex items-center justify-between gap-3">
                  <p className={`text-xs font-semibold uppercase tracking-[0.16em] ${shell.accent}`}>Chapter {searchResult.chapter_num}</p>
                </div>
                <p className={`text-sm leading-7 ${shell.body}`}>{searchResult.text}</p>
              </div>
            ))}
          </div>
        ) : null}

        {!loading && !selectedQuote && !activeCharacter && result?.type !== "search" ? (
          <div className={`rounded-lg border p-5 ${shell.card}`}>
            <p className={`text-sm leading-7 ${shell.body}`}>
              Tap a highlighted character name to open a profile here. On mobile, this panel opens as a clean bottom sheet so the reading page stays visible behind it without collapsing the content.
            </p>
          </div>
        ) : null}
      </div>
    </aside>
  )
}
