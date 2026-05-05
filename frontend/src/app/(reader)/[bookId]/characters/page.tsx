"use client"

import { useEffect, useMemo, useState } from "react"
import { useParams, useRouter } from "next/navigation"

import RelationshipGraph from "@/components/intelligence/RelationshipGraph"
import { CONFIDENCE_THRESHOLDS } from "@/lib/constants"
import { booksApi } from "@/lib/api/books"
import { intelligenceApi } from "@/lib/api/intelligence"
import { readerApi } from "@/lib/api/reader"
import type { Book } from "@/types/book"
import type { Character, RelationshipGraph as RelationshipGraphData } from "@/types/character"
import type { ChatMessage } from "@/types/intelligence"
import type { ReadingProgress } from "@/types/reader"

type EditDraft = {
  name: string
  aliases: string
  description: string
  arcSummary: string
  personalityTags: string
  motivations: string
  fears: string
}

type CharacterTab = "overview" | "relationships" | "motivation" | "continuity" | "evidence"
type CastFilter = "all" | "main" | "minor" | "needs-review"

function formatRole(role: Character["role"]) {
  if (role === "mc") return "Main character"
  if (role === "sc") return "Supporting character"
  if (role === "background") return "Background character"
  return "Character"
}

function formatRoleMeta(role: Character["role"]) {
  if (role === "mc") return "main"
  if (role === "sc") return "major"
  if (role === "background") return "minor"
  return "unclassified"
}

function formatStatus(status: Character["status"]) {
  return status === "deceased" ? "deceased" : "active"
}

function formatRelationshipType(type: string | null | undefined) {
  return (type || "connection")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (part) => part.toUpperCase())
}

function normalizeText(value: string | null | undefined) {
  return (value ?? "").trim().toLowerCase()
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

function characterInitial(name: string) {
  return (name.trim()[0] || "?").toUpperCase()
}

function buildDraft(character: Character | null): EditDraft {
  return {
    name: character?.name ?? "",
    aliases: listToString(character?.aliases),
    description: character?.description ?? "",
    arcSummary: character?.arc_summary ?? "",
    personalityTags: listToString(character?.personality_tags),
    motivations: listToString(character?.motivations),
    fears: listToString(character?.fears),
  }
}

function visibleTraitEntries(character: Character | null) {
  if (!character) return []
  return Object.entries(character.trait_state ?? {}).filter(([, trait]) => (
    trait && trait.confidence >= CONFIDENCE_THRESHOLDS.SHOW_IN_UI && trait.value
  ))
}

function sentimentLabel(value: number | null | undefined) {
  if (typeof value !== "number" || Number.isNaN(value)) return "Neutral"
  if (value >= 0.4) return "Positive"
  if (value <= -0.4) return "Tense"
  return "Neutral"
}

function growthTitle(event: NonNullable<Character["growth_events"]>[number]) {
  return event.event_title || event.event || "Untitled event"
}

function growthChapter(event: NonNullable<Character["growth_events"]>[number]) {
  return event.chapter_number ?? event.chapter ?? null
}

function buildMergeSuggestionIds(chars: Character[]) {
  const ids = new Set<string>()
  const names = chars.map((char) => ({
    id: char.id,
    name: normalizeText(char.name),
    aliases: (char.aliases ?? []).map((alias) => normalizeText(alias)).filter(Boolean),
  }))

  for (let index = 0; index < names.length; index += 1) {
    for (let inner = index + 1; inner < names.length; inner += 1) {
      const left = names[index]
      const right = names[inner]
      const overlap = left.name === right.name
        || left.aliases.includes(right.name)
        || right.aliases.includes(left.name)
        || left.aliases.some((alias) => right.aliases.includes(alias))
      if (overlap) {
        ids.add(left.id)
        ids.add(right.id)
      }
    }
  }

  return ids
}

function qualityFlags(character: Character, mergeSuggestionIds: Set<string>) {
  const traits = visibleTraitEntries(character)
  const continuityKeys = new Set(traits.map(([key]) => key))
  const flags: string[] = []

  if (mergeSuggestionIds.has(character.id)) flags.push("Needs merge")
  if (!character.description && traits.length < 2) flags.push("Low confidence")
  if (!continuityKeys.has("age") || !continuityKeys.has("build") || !continuityKeys.has("distinguishing")) {
    flags.push("Missing traits")
  }

  return Array.from(new Set(flags))
}

function topStats(
  characterCount: number,
  relationshipCount: number,
  chapter: number,
  mergeSuggestionCount: number,
) {
  return [
    { label: "Characters", value: String(characterCount) },
    { label: "Relationships", value: String(relationshipCount) },
    { label: "Chapter", value: String(chapter) },
    { label: "Merge Suggestions", value: String(mergeSuggestionCount) },
  ]
}

function tabButtonClasses(isDark: boolean, active: boolean) {
  if (active) {
    return isDark
      ? "border-violet-400/40 bg-violet-500/15 text-violet-100"
      : "border-violet-300 bg-violet-50 text-violet-700"
  }
  return isDark
    ? "border-transparent bg-transparent text-slate-400 hover:border-white/10 hover:bg-white/[0.04] hover:text-slate-200"
    : "border-transparent bg-transparent text-stone-500 hover:border-stone-200 hover:bg-stone-50 hover:text-stone-700"
}

function flagClasses(isDark: boolean, flag: string) {
  if (flag === "Needs merge") {
    return isDark ? "bg-amber-500/12 text-amber-200" : "bg-amber-50 text-amber-700"
  }
  if (flag === "Low confidence") {
    return isDark ? "bg-rose-500/12 text-rose-200" : "bg-rose-50 text-rose-700"
  }
  return isDark ? "bg-sky-500/12 text-sky-200" : "bg-sky-50 text-sky-700"
}

function buildSelectedCharacterSummary(
  character: Character | null,
  connections: Array<{ counterpartName: string; type: string; sentiment: number | null }> = [],
) {
  if (!character) return ""

  const traits = visibleTraitEntries(character)
  const age = traits.find(([key]) => key === "age")?.[1]?.value
  const distinguishing = traits.find(([key]) => key === "distinguishing")?.[1]?.value
  const disposition = character.personality_tags.slice(0, 3).join(", ")
  const wants = character.motivations.slice(0, 2).join(", ")
  const relationshipNotes = connections
    .slice(0, 2)
    .map((edge) => `${formatRelationshipType(edge.type)} connection with ${edge.counterpartName}.`)
    .join(" ")

  const parts = [
    character.description || `${character.name} is a ${formatRole(character.role).toLowerCase()}.`,
    age ? `${character.name} appears to be ${age}.` : null,
    distinguishing ? `Notable for ${distinguishing}.` : null,
    disposition ? `Disposition: ${disposition}.` : null,
    wants ? `Wants: ${wants}.` : null,
    relationshipNotes || null,
  ].filter(Boolean)

  return parts.join(" ")
}

export default function CharactersPage() {
  const { bookId } = useParams<{ bookId: string }>()
  const router = useRouter()

  const [book, setBook] = useState<Book | null>(null)
  const [progress, setProgress] = useState<ReadingProgress | null>(null)
  const [chars, setChars] = useState<Character[]>([])
  const [graphData, setGraphData] = useState<RelationshipGraphData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [theme, setTheme] = useState<"light" | "dark">("light")
  const [search, setSearch] = useState("")
  const [selectedId, setSelectedId] = useState("")
  const [activeTab, setActiveTab] = useState<CharacterTab>("overview")
  const [castFilter, setCastFilter] = useState<CastFilter>("all")
  const [primaryMergeId, setPrimaryMergeId] = useState("")
  const [secondaryMergeId, setSecondaryMergeId] = useState("")
  const [mergeBusy, setMergeBusy] = useState(false)
  const [mergeError, setMergeError] = useState<string | null>(null)
  const [editing, setEditing] = useState(false)
  const [saving, setSaving] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [shareState, setShareState] = useState<"idle" | "copied" | "error">("idle")
  const [exporting, setExporting] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)
  const [draft, setDraft] = useState<EditDraft>(buildDraft(null))
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([])
  const [chatInput, setChatInput] = useState("")
  const [chatLoading, setChatLoading] = useState(false)
  const [chatHint, setChatHint] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    setLoading(true)
    setError(null)

    Promise.all([
      booksApi.get(bookId),
      booksApi.getCharacters(bookId),
      readerApi.getProgress(bookId).catch(() => null),
    ])
      .then(([bookData, characterData, progressData]) => {
        if (!active) return
        setBook(bookData)
        setChars(characterData)
        setProgress(progressData)
        setSelectedId((current) => current || characterData[0]?.id || "")
      })
      .catch(() => {
        if (!active) return
        setError("Could not load the character workspace yet.")
      })
      .finally(() => {
        if (active) setLoading(false)
      })

    return () => {
      active = false
    }
  }, [bookId])

  useEffect(() => {
    const stored = window.localStorage.getItem("reader-theme")
    if (stored === "dark" || stored === "light") setTheme(stored)
  }, [])

  const relationshipChapter = book?.mode === "author"
    ? Math.max(book?.total_chapters ?? 1, progress?.current_chapter ?? 1)
    : Math.max(progress?.current_chapter ?? 1, 1)

  useEffect(() => {
    if (!book) return

    let active = true
    readerApi.getRelationships(bookId, relationshipChapter)
      .then((data) => {
        if (active) setGraphData(data)
      })
      .catch(() => {
        if (active) setGraphData(null)
      })

    return () => {
      active = false
    }
  }, [book, bookId, relationshipChapter])

  const isDark = theme === "dark"
  const isAuthorMode = book?.mode === "author"
  const normalizedSearch = search.trim().toLowerCase()
  const mergeSuggestionIds = useMemo(() => buildMergeSuggestionIds(chars), [chars])

  const relationshipCounts = useMemo(() => {
    const counts = new Map<string, number>()
    for (const edge of graphData?.edges ?? []) {
      counts.set(edge.source, (counts.get(edge.source) ?? 0) + 1)
      counts.set(edge.target, (counts.get(edge.target) ?? 0) + 1)
    }
    return counts
  }, [graphData])

  const filteredChars = chars.filter((char) => {
    const flags = qualityFlags(char, mergeSuggestionIds)
    const passesSearch = !normalizedSearch || [
      char.name,
      ...(char.aliases ?? []),
      char.description ?? "",
      char.arc_summary ?? "",
      ...(char.personality_tags ?? []),
      ...flags,
    ].join(" ").toLowerCase().includes(normalizedSearch)

    if (!passesSearch) return false
    if (castFilter === "all") return true
    if (castFilter === "main") return char.role === "mc" || char.role === "sc"
    if (castFilter === "minor") return char.role === "background" || !char.role
    return flags.length > 0
  })

  useEffect(() => {
    if (filteredChars.length === 0) {
      setSelectedId("")
      return
    }
    if (filteredChars.some((char) => char.id === selectedId)) return
    setSelectedId(filteredChars[0].id)
  }, [filteredChars, selectedId])

  const selectedCharacter = filteredChars.find((char) => char.id === selectedId)
    ?? chars.find((char) => char.id === selectedId)
    ?? filteredChars[0]
    ?? chars[0]
    ?? null

  useEffect(() => {
    if (!editing) {
      setDraft(buildDraft(selectedCharacter))
      setActionError(null)
    }
  }, [editing, selectedCharacter])

  useEffect(() => {
    setChatMessages([])
    setChatInput("")
    setChatHint(null)
  }, [selectedCharacter?.id])

  const nodeLookup = new Map((graphData?.nodes ?? []).map((node) => [node.id, node.name]))
  const selectedConnections = selectedCharacter
    ? (graphData?.edges ?? [])
        .filter((edge) => edge.source === selectedCharacter.id || edge.target === selectedCharacter.id)
        .map((edge) => {
          const counterpartId = edge.source === selectedCharacter.id ? edge.target : edge.source
          return {
            ...edge,
            counterpartId,
            counterpartName: nodeLookup.get(counterpartId) || "Unknown character",
          }
        })
        .sort((left, right) => (right.from_chapter ?? 0) - (left.from_chapter ?? 0))
    : []

  const stats = topStats(chars.length, graphData?.edges.length ?? 0, relationshipChapter, mergeSuggestionIds.size)
  const selectedFlags = selectedCharacter ? qualityFlags(selectedCharacter, mergeSuggestionIds) : []
  const overviewTraits = selectedCharacter ? visibleTraitEntries(selectedCharacter).slice(0, 4) : []
  const continuityTraits = selectedCharacter ? visibleTraitEntries(selectedCharacter).filter(([key]) => (
    ["age", "build", "distinguishing", "eyes", "hair", "face"].includes(key)
  )) : []
  const selectedCharacterSummary = buildSelectedCharacterSummary(selectedCharacter, selectedConnections)
  const growthEvents = (selectedCharacter?.growth_events ?? [])
    .slice()
    .sort((left, right) => (right.chapter_number ?? right.chapter ?? 0) - (left.chapter_number ?? left.chapter ?? 0))

  async function refreshCharacters() {
    const refreshed = await booksApi.getCharacters(bookId)
    setChars(refreshed)
    return refreshed
  }

  async function handleMergeCharacters() {
    if (!primaryMergeId || !secondaryMergeId || primaryMergeId === secondaryMergeId) {
      setMergeError("Choose two different characters to merge.")
      return
    }
    setMergeBusy(true)
    setMergeError(null)
    try {
      const response = await booksApi.mergeCharacters(bookId, {
        primaryId: primaryMergeId,
        secondaryId: secondaryMergeId,
      })
      const refreshed = await refreshCharacters()
      setPrimaryMergeId(response.merged)
      setSecondaryMergeId("")
      setSelectedId(response.merged || refreshed[0]?.id || "")
    } catch {
      setMergeError("Could not merge those characters.")
    } finally {
      setMergeBusy(false)
    }
  }

  async function handleSaveCharacter() {
    if (!selectedCharacter) return
    setSaving(true)
    setActionError(null)
    try {
      const updated = await booksApi.updateCharacter(bookId, selectedCharacter.id, {
        name: draft.name.trim(),
        aliases: stringToList(draft.aliases),
        description: draft.description.trim() || null,
        arcSummary: draft.arcSummary.trim() || null,
        personalityTags: stringToList(draft.personalityTags),
        motivations: stringToList(draft.motivations),
        fears: stringToList(draft.fears),
      })
      setChars((current) => current.map((item) => item.id === updated.id ? updated : item))
      setSelectedId(updated.id)
      setEditing(false)
    } catch {
      setActionError("Could not save character changes.")
    } finally {
      setSaving(false)
    }
  }

  async function handleShareCharacter() {
    if (!selectedCharacter) return
    try {
      const response = await booksApi.shareCharacter(bookId, selectedCharacter.id)
      const shareUrl = `${window.location.origin}${response.share_url}`
      await navigator.clipboard.writeText(shareUrl)
      setShareState("copied")
      window.setTimeout(() => setShareState("idle"), 2200)
    } catch {
      setShareState("error")
      window.setTimeout(() => setShareState("idle"), 2200)
    }
  }

  async function handleExportCharacter() {
    if (!selectedCharacter) return
    setExporting(true)
    try {
      const blob = await booksApi.exportCharacterCard(bookId, selectedCharacter.id, "pdf")
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement("a")
      anchor.href = url
      anchor.download = `${selectedCharacter.name.replace(/\s+/g, "-").toLowerCase()}-character-card.pdf`
      anchor.click()
      URL.revokeObjectURL(url)
    } finally {
      setExporting(false)
    }
  }

  async function handleDeleteCharacter() {
    if (!selectedCharacter) return
    const confirmed = window.confirm(`Delete ${selectedCharacter.name} from this book? This is best for false positives and cannot be undone.`)
    if (!confirmed) return

    setDeleting(true)
    setActionError(null)
    try {
      await booksApi.deleteCharacter(bookId, selectedCharacter.id)
      const remaining = chars.filter((char) => char.id !== selectedCharacter.id)
      setChars(remaining)
      setSelectedId(remaining[0]?.id || "")
      setEditing(false)
    } catch {
      setActionError("Could not delete this character.")
    } finally {
      setDeleting(false)
    }
  }

  async function handleCharacterChat() {
    if (!selectedCharacter || !chatInput.trim()) return
    const nextMessages: ChatMessage[] = [...chatMessages, { role: "user", content: chatInput.trim() }]
    setChatMessages(nextMessages)
    setChatInput("")
    setChatLoading(true)
    setChatHint(null)
    try {
      const response = await intelligenceApi.chat(
        bookId,
        selectedCharacter.id,
        nextMessages,
        relationshipChapter,
        selectedCharacterSummary
      )
      setChatMessages([...nextMessages, { role: "assistant", content: response.reply }])
      setChatHint(response.grounded_hint ?? null)
    } catch {
      setChatMessages([...nextMessages, { role: "assistant", content: "I cannot answer that right now." }])
    } finally {
      setChatLoading(false)
    }
  }

  const atmosphere = isDark
    ? "bg-[radial-gradient(circle_at_top_left,rgba(124,58,237,0.16),transparent_28%),radial-gradient(circle_at_top_right,rgba(59,130,246,0.10),transparent_26%),linear-gradient(180deg,#040507_0%,#090a0f_44%,#0e1016_100%)] text-slate-100"
    : "bg-[radial-gradient(circle_at_top_left,rgba(124,58,237,0.08),transparent_26%),radial-gradient(circle_at_top_right,rgba(244,114,182,0.07),transparent_24%),linear-gradient(180deg,#fbf8f3_0%,#f7f1e8_46%,#f4ede4_100%)] text-stone-950"

  if (loading) {
    return (
      <div className={`min-h-screen ${atmosphere}`}>
        <div className="mx-auto max-w-[1600px] px-4 py-8 sm:px-6 lg:px-8">
          <div className={`rounded-[1.4rem] border p-6 text-sm ${isDark ? "border-white/10 bg-black/20 text-slate-300" : "border-stone-200 bg-white/85 text-stone-600"}`}>
            Loading the character workspace...
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className={`min-h-screen transition-colors ${atmosphere}`}>
      <div className="mx-auto max-w-[1600px] px-4 pb-16 pt-5 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between gap-3">
          <button
            onClick={() => router.back()}
            className={`text-sm font-medium transition ${isDark ? "text-violet-200 hover:text-white" : "text-violet-700 hover:text-violet-800"}`}
          >
            {"<- Back"}
          </button>
        </div>

        <div className="mt-4 flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
          <div>
            <p className={`text-[11px] font-semibold uppercase tracking-[0.32em] ${isDark ? "text-violet-300" : "text-violet-500"}`}>Character workspace</p>
            <h1 className={`mt-2 text-3xl font-semibold tracking-tight ${isDark ? "text-white" : "text-stone-950"}`}>Characters</h1>
            <p className={`mt-2 max-w-3xl text-sm leading-7 ${isDark ? "text-slate-300" : "text-stone-600"}`}>
              Manage cast profiles, aliases, relationships, and continuity.
            </p>
          </div>

          <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
            {stats.map((stat) => (
              <div key={stat.label} className={`min-w-[110px] rounded-[1.1rem] border px-4 py-3 ${isDark ? "border-white/10 bg-black/20" : "border-stone-200 bg-white/88"}`}>
                <p className={`text-[10px] font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>{stat.label}</p>
                <p className={`mt-1 text-lg font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{stat.value}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="mt-5 grid gap-3 xl:grid-cols-[minmax(0,1fr)_auto]">
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search characters, aliases, traits..."
            className={`w-full rounded-[1rem] border px-4 py-3 text-sm ${isDark ? "border-white/10 bg-black/20 text-slate-100 placeholder:text-slate-500" : "border-stone-200 bg-white text-stone-900 placeholder:text-stone-400"}`}
          />

          {isAuthorMode ? (
            <div className="grid gap-2 sm:grid-cols-[180px_180px_auto]">
              <select
                value={primaryMergeId}
                onChange={(event) => setPrimaryMergeId(event.target.value)}
                className={`rounded-[1rem] border px-4 py-3 text-sm ${isDark ? "border-white/10 bg-black/20 text-slate-100" : "border-stone-200 bg-white text-stone-900"}`}
              >
                <option value="">Primary character</option>
                {chars.map((char) => (
                  <option key={char.id} value={char.id}>{char.name}</option>
                ))}
              </select>
              <select
                value={secondaryMergeId}
                onChange={(event) => setSecondaryMergeId(event.target.value)}
                className={`rounded-[1rem] border px-4 py-3 text-sm ${isDark ? "border-white/10 bg-black/20 text-slate-100" : "border-stone-200 bg-white text-stone-900"}`}
              >
                <option value="">Duplicate character</option>
                {chars.map((char) => (
                  <option key={char.id} value={char.id}>{char.name}</option>
                ))}
              </select>
              <button
                type="button"
                onClick={() => void handleMergeCharacters()}
                disabled={mergeBusy}
                className="rounded-[1rem] bg-[linear-gradient(135deg,#8b5cf6,#6d28d9)] px-5 py-3 text-sm font-semibold text-white shadow-[0_15px_35px_rgba(109,40,217,0.22)] transition hover:translate-y-[-1px] disabled:opacity-60"
              >
                {mergeBusy ? "Merging..." : "Merge"}
              </button>
            </div>
          ) : null}
        </div>

        {mergeError ? <p className="mt-2 text-sm text-red-500">{mergeError}</p> : null}
        {error ? <p className="mt-3 text-sm text-red-500">{error}</p> : null}

        {!error && chars.length > 0 ? (
          <div className={`mt-5 overflow-hidden rounded-[1.8rem] border shadow-[0_24px_70px_rgba(0,0,0,0.18)] ${isDark ? "border-white/10 bg-[#090b10]" : "border-stone-200 bg-white/92"}`}>
            <div className="grid xl:grid-cols-[280px_minmax(0,1fr)_380px] 2xl:grid-cols-[280px_minmax(0,1fr)_420px]">
              <aside className={`min-h-[calc(100vh-16rem)] overflow-y-auto border-r ${isDark ? "border-white/8" : "border-stone-200"}`}>
                <div className={`sticky top-0 z-10 border-b px-4 py-4 backdrop-blur ${isDark ? "border-white/8 bg-[#090b10]/95" : "border-stone-200 bg-white/95"}`}>
                  <div className="flex items-center justify-between gap-2">
                    <div>
                      <p className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Cast list</p>
                      <p className={`mt-1 text-sm ${isDark ? "text-slate-300" : "text-stone-600"}`}>{filteredChars.length} visible</p>
                    </div>
                    <div className={`rounded-full border px-2.5 py-1 text-[10px] font-semibold ${isDark ? "border-white/10 bg-white/[0.03] text-slate-300" : "border-stone-200 bg-stone-50 text-stone-600"}`}>
                      Sticky
                    </div>
                  </div>

                  <div className="mt-3 flex flex-wrap gap-2">
                    {([
                      ["all", "All"],
                      ["main", "Main"],
                      ["minor", "Minor"],
                      ["needs-review", "Needs Review"],
                    ] as Array<[CastFilter, string]>).map(([value, label]) => (
                      <button
                        key={value}
                        type="button"
                        onClick={() => setCastFilter(value)}
                        className={`rounded-full border px-3 py-1.5 text-xs font-medium ${castFilter === value
                          ? isDark ? "border-violet-400/30 bg-violet-500/15 text-violet-100" : "border-violet-300 bg-violet-50 text-violet-700"
                          : isDark ? "border-white/10 text-slate-300 hover:bg-white/[0.05]" : "border-stone-200 text-stone-600 hover:bg-stone-50"
                        }`}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="p-3">
                  {filteredChars.map((char) => {
                    const isActive = selectedCharacter?.id === char.id
                    const flags = qualityFlags(char, mergeSuggestionIds)
                    return (
                      <button
                        key={char.id}
                        type="button"
                        onClick={() => {
                          setSelectedId(char.id)
                          setEditing(false)
                        }}
                        className={`mb-2 w-full rounded-[1rem] border px-3 py-3 text-left transition ${isActive
                          ? isDark
                            ? "border-violet-400/40 bg-violet-500/12 shadow-[inset_0_0_0_1px_rgba(167,139,250,0.15)]"
                            : "border-violet-300 bg-violet-50"
                          : isDark
                            ? "border-white/8 bg-white/[0.02] hover:bg-white/[0.04]"
                            : "border-stone-200 bg-white hover:bg-stone-50"
                        }`}
                      >
                        <div className="flex items-start gap-3">
                          <div className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-sm font-semibold ${isActive
                            ? isDark ? "bg-violet-500/18 text-violet-100" : "bg-violet-100 text-violet-700"
                            : isDark ? "bg-white/[0.05] text-slate-200" : "bg-stone-100 text-stone-700"
                          }`}>
                            {characterInitial(char.name)}
                          </div>
                          <div className="min-w-0 flex-1">
                            <div className="flex items-center justify-between gap-3">
                              <p className={`truncate text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{char.name}</p>
                              <span className={`shrink-0 text-xs font-medium ${isDark ? "text-slate-400" : "text-stone-500"}`}>{relationshipCounts.get(char.id) ?? 0} ties</span>
                            </div>
                            <p className={`mt-1 truncate text-xs ${isDark ? "text-slate-400" : "text-stone-500"}`}>
                              {formatRoleMeta(char.role)} • {formatStatus(char.status)} • ch. {char.first_chapter}{char.last_seen_chapter ? `-${char.last_seen_chapter}` : ""}
                            </p>
                            {flags.length > 0 ? (
                              <div className="mt-2 flex flex-wrap gap-1.5">
                                {flags.map((flag) => (
                                  <span key={flag} className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${flagClasses(isDark, flag)}`}>
                                    {flag}
                                  </span>
                                ))}
                              </div>
                            ) : null}
                          </div>
                        </div>
                      </button>
                    )
                  })}
                </div>
              </aside>

              <section className={`min-h-[calc(100vh-16rem)] overflow-y-auto border-r ${isDark ? "border-white/8" : "border-stone-200"}`}>
                {selectedCharacter ? (
                  <div className="p-5">
                    <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <h2 className={`text-3xl font-semibold tracking-tight ${isDark ? "text-white" : "text-stone-950"}`}>{selectedCharacter.name}</h2>
                        </div>
                        <p className={`mt-2 text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>
                          {formatRole(selectedCharacter.role)} • {formatStatus(selectedCharacter.status)} • {selectedCharacter.mention_count ?? 0} mentions • {relationshipCounts.get(selectedCharacter.id) ?? 0} ties
                        </p>
                        {selectedFlags.length > 0 ? (
                          <div className="mt-3 flex flex-wrap gap-2">
                            {selectedFlags.map((flag) => (
                              <span key={flag} className={`rounded-full px-2.5 py-1 text-xs font-medium ${flagClasses(isDark, flag)}`}>
                                {flag}
                              </span>
                            ))}
                          </div>
                        ) : null}
                      </div>

                      <div className="flex flex-wrap gap-2">
                        {isAuthorMode ? (
                          <button
                            type="button"
                            onClick={() => setEditing((current) => !current)}
                            className={`rounded-full border px-4 py-2 text-sm font-medium ${isDark ? "border-white/10 bg-white/[0.04] text-slate-200 hover:bg-white/[0.08]" : "border-stone-200 bg-white text-stone-700 hover:bg-stone-50"}`}
                          >
                            {editing ? "Close edit" : "Edit"}
                          </button>
                        ) : null}
                        <button
                          type="button"
                          onClick={() => void handleShareCharacter()}
                          className={`rounded-full border px-4 py-2 text-sm font-medium ${isDark ? "border-white/10 bg-white/[0.04] text-slate-200 hover:bg-white/[0.08]" : "border-stone-200 bg-white text-stone-700 hover:bg-stone-50"}`}
                        >
                          {shareState === "copied" ? "Link copied" : shareState === "error" ? "Share failed" : "Share"}
                        </button>
                        <button
                          type="button"
                          onClick={() => void handleExportCharacter()}
                          disabled={exporting}
                          className="rounded-full bg-[linear-gradient(135deg,#8b5cf6,#6d28d9)] px-4 py-2 text-sm font-semibold text-white shadow-[0_12px_28px_rgba(109,40,217,0.22)] transition hover:translate-y-[-1px] disabled:opacity-60"
                        >
                          {exporting ? "Preparing..." : "Export PDF"}
                        </button>
                        {isAuthorMode ? (
                          <button
                            type="button"
                            onClick={() => void handleDeleteCharacter()}
                            disabled={deleting}
                            className={`rounded-full border px-4 py-2 text-sm font-medium ${isDark ? "border-red-500/30 bg-red-500/10 text-red-100 hover:bg-red-500/15" : "border-red-200 bg-red-50 text-red-700 hover:bg-red-100"} disabled:opacity-60`}
                          >
                            {deleting ? "Deleting..." : "Delete"}
                          </button>
                        ) : null}
                      </div>
                    </div>

                    <div className={`mt-5 flex flex-wrap gap-2 border-b pb-4 ${isDark ? "border-white/8" : "border-stone-200"}`}>
                      {([
                        ["overview", "Overview"],
                        ["relationships", "Relationships"],
                        ["motivation", "Motivation"],
                        ["continuity", "Continuity"],
                        ["evidence", "Evidence"],
                      ] as Array<[CharacterTab, string]>).map(([value, label]) => (
                        <button
                          key={value}
                          type="button"
                          onClick={() => setActiveTab(value)}
                          className={`rounded-full border px-3 py-1.5 text-sm font-medium ${tabButtonClasses(isDark, activeTab === value)}`}
                        >
                          {label}
                        </button>
                      ))}
                    </div>

                    {activeTab === "overview" ? (
                      <div className="mt-5 space-y-5">
                        <section className={`rounded-[1rem] border px-4 py-4 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-stone-200 bg-stone-50/70"}`}>
                          <p className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Selected character</p>
                          <h3 className={`mt-2 text-xl font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{selectedCharacter.name}</h3>
                          <p className={`mt-3 text-sm leading-7 ${isDark ? "text-slate-300" : "text-stone-600"}`}>
                            {selectedCharacterSummary}
                          </p>
                        </section>

                        {selectedCharacter.aliases.length > 0 ? (
                          <section>
                            <p className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Aliases</p>
                            <p className={`mt-2 text-sm leading-7 ${isDark ? "text-slate-300" : "text-stone-600"}`}>{selectedCharacter.aliases.join(", ")}</p>
                          </section>
                        ) : null}

                        <section>
                          <p className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Summary</p>
                          <p className={`mt-2 text-sm leading-7 ${isDark ? "text-slate-300" : "text-stone-600"}`}>
                            {selectedCharacter.description || "LoreVia is still building a concise grounded profile from the text."}
                          </p>
                        </section>

                        <section>
                          <p className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Core traits</p>
                          <div className="mt-3 flex flex-wrap gap-2">
                            {selectedCharacter.personality_tags.length > 0
                              ? selectedCharacter.personality_tags.map((tag) => (
                                  <span key={tag} className={`rounded-full px-3 py-1.5 text-xs ${isDark ? "bg-white/[0.05] text-slate-200" : "bg-stone-100 text-stone-700"}`}>
                                    {tag}
                                  </span>
                                ))
                              : overviewTraits.map(([key, trait]) => trait ? (
                                  <span key={key} className={`rounded-full px-3 py-1.5 text-xs ${isDark ? "bg-white/[0.05] text-slate-200" : "bg-stone-100 text-stone-700"}`}>
                                    {trait.value}
                                  </span>
                                ) : null)}
                            {selectedCharacter.personality_tags.length === 0 && overviewTraits.length === 0 ? (
                              <span className={isDark ? "text-sm text-slate-400" : "text-sm text-stone-500"}>No core traits captured yet.</span>
                            ) : null}
                          </div>
                        </section>

                        <section>
                          <p className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Arc</p>
                          <p className={`mt-2 text-sm leading-7 ${isDark ? "text-slate-300" : "text-stone-600"}`}>
                            {selectedCharacter.arc_summary || "Current role and progression are still being inferred from the manuscript."}
                          </p>
                        </section>

                        {isAuthorMode && editing ? (
                          <section className={`rounded-[1.2rem] border p-4 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-stone-200 bg-stone-50/80"}`}>
                            <div className="grid gap-4 md:grid-cols-2">
                              <label className="space-y-1">
                                <span className={`text-[11px] font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Name</span>
                                <input value={draft.name} onChange={(event) => setDraft((value) => ({ ...value, name: event.target.value }))} className={`w-full rounded-xl border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-black/20 text-white" : "border-stone-200 bg-white text-stone-900"}`} />
                              </label>
                              <label className="space-y-1">
                                <span className={`text-[11px] font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Aliases</span>
                                <input value={draft.aliases} onChange={(event) => setDraft((value) => ({ ...value, aliases: event.target.value }))} className={`w-full rounded-xl border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-black/20 text-white" : "border-stone-200 bg-white text-stone-900"}`} />
                              </label>
                              <label className="space-y-1 md:col-span-2">
                                <span className={`text-[11px] font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Description</span>
                                <textarea value={draft.description} onChange={(event) => setDraft((value) => ({ ...value, description: event.target.value }))} rows={4} className={`w-full rounded-xl border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-black/20 text-white" : "border-stone-200 bg-white text-stone-900"}`} />
                              </label>
                              <label className="space-y-1 md:col-span-2">
                                <span className={`text-[11px] font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Arc summary</span>
                                <textarea value={draft.arcSummary} onChange={(event) => setDraft((value) => ({ ...value, arcSummary: event.target.value }))} rows={3} className={`w-full rounded-xl border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-black/20 text-white" : "border-stone-200 bg-white text-stone-900"}`} />
                              </label>
                              <label className="space-y-1">
                                <span className={`text-[11px] font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Personality tags</span>
                                <input value={draft.personalityTags} onChange={(event) => setDraft((value) => ({ ...value, personalityTags: event.target.value }))} className={`w-full rounded-xl border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-black/20 text-white" : "border-stone-200 bg-white text-stone-900"}`} />
                              </label>
                              <label className="space-y-1">
                                <span className={`text-[11px] font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Motivations</span>
                                <input value={draft.motivations} onChange={(event) => setDraft((value) => ({ ...value, motivations: event.target.value }))} className={`w-full rounded-xl border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-black/20 text-white" : "border-stone-200 bg-white text-stone-900"}`} />
                              </label>
                              <label className="space-y-1 md:col-span-2">
                                <span className={`text-[11px] font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Fears</span>
                                <input value={draft.fears} onChange={(event) => setDraft((value) => ({ ...value, fears: event.target.value }))} className={`w-full rounded-xl border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-black/20 text-white" : "border-stone-200 bg-white text-stone-900"}`} />
                              </label>
                            </div>
                            {actionError ? <p className="mt-3 text-sm text-red-500">{actionError}</p> : null}
                            <div className="mt-4 flex flex-wrap gap-2">
                              <button type="button" disabled={saving} onClick={() => void handleSaveCharacter()} className="rounded-full bg-[linear-gradient(135deg,#8b5cf6,#6d28d9)] px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-60">
                                {saving ? "Saving..." : "Save changes"}
                              </button>
                              <button
                                type="button"
                                onClick={() => {
                                  setEditing(false)
                                  setDraft(buildDraft(selectedCharacter))
                                }}
                                className={`rounded-full border px-4 py-2.5 text-sm font-medium ${isDark ? "border-white/10 text-slate-300 hover:bg-white/[0.05]" : "border-stone-200 text-stone-700 hover:bg-white"}`}
                              >
                                Cancel
                              </button>
                            </div>
                          </section>
                        ) : null}
                      </div>
                    ) : null}

                    {activeTab === "relationships" ? (
                      <div className="mt-5 space-y-3">
                        {selectedConnections.length > 0 ? selectedConnections.map((edge, index) => (
                          <div key={`${edge.source}-${edge.target}-${edge.type}-${index}`} className={`rounded-[1rem] border px-4 py-3 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-stone-200 bg-stone-50/70"}`}>
                            <div className="flex flex-wrap items-center gap-2">
                              <span className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{edge.counterpartName}</span>
                              <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.16em] ${isDark ? "bg-violet-500/15 text-violet-100" : "bg-violet-100 text-violet-700"}`}>
                                {formatRelationshipType(edge.type)}
                              </span>
                              <span className={`rounded-full px-2 py-0.5 text-[10px] ${isDark ? "bg-white/[0.05] text-slate-300" : "bg-white text-stone-600 border border-stone-200"}`}>
                                {sentimentLabel(edge.sentiment)}
                              </span>
                              {typeof edge.from_chapter === "number" ? (
                                <span className={`rounded-full px-2 py-0.5 text-[10px] ${isDark ? "bg-white/[0.05] text-slate-300" : "bg-white text-stone-600 border border-stone-200"}`}>
                                  Ch. {edge.from_chapter}
                                </span>
                              ) : null}
                            </div>
                            <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-600"}`}>
                              {edge.description || `${selectedCharacter.name} has a tracked ${formatRelationshipType(edge.type).toLowerCase()} relationship with ${edge.counterpartName}.`}
                            </p>
                          </div>
                        )) : (
                          <p className={isDark ? "text-sm text-slate-400" : "text-sm text-stone-500"}>No relationship links are visible for this character yet.</p>
                        )}
                      </div>
                    ) : null}

                    {activeTab === "motivation" ? (
                      <div className="mt-5 space-y-5">
                        <section>
                          <p className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Motivations</p>
                          <div className="mt-3 flex flex-wrap gap-2">
                            {selectedCharacter.motivations.length > 0 ? selectedCharacter.motivations.map((item) => (
                              <span key={item} className={`rounded-full px-3 py-1.5 text-xs ${isDark ? "bg-emerald-500/12 text-emerald-200" : "bg-emerald-50 text-emerald-700"}`}>{item}</span>
                            )) : <span className={isDark ? "text-sm text-slate-400" : "text-sm text-stone-500"}>No motivations captured yet.</span>}
                          </div>
                        </section>

                        <section>
                          <p className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Fears</p>
                          <div className="mt-3 flex flex-wrap gap-2">
                            {selectedCharacter.fears.length > 0 ? selectedCharacter.fears.map((item) => (
                              <span key={item} className={`rounded-full px-3 py-1.5 text-xs ${isDark ? "bg-rose-500/12 text-rose-200" : "bg-rose-50 text-rose-700"}`}>{item}</span>
                            )) : <span className={isDark ? "text-sm text-slate-400" : "text-sm text-stone-500"}>No fears captured yet.</span>}
                          </div>
                        </section>

                        <section>
                          <p className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Disposition</p>
                          <div className="mt-3 flex flex-wrap gap-2">
                            {selectedCharacter.personality_tags.length > 0 ? selectedCharacter.personality_tags.map((item) => (
                              <span key={item} className={`rounded-full px-3 py-1.5 text-xs ${isDark ? "bg-white/[0.05] text-slate-200" : "bg-stone-100 text-stone-700"}`}>{item}</span>
                            )) : <span className={isDark ? "text-sm text-slate-400" : "text-sm text-stone-500"}>No disposition tags captured yet.</span>}
                          </div>
                        </section>
                      </div>
                    ) : null}

                    {activeTab === "continuity" ? (
                      <div className="mt-5 grid gap-3 md:grid-cols-2">
                        {continuityTraits.map(([key, trait]) => trait ? (
                          <div key={key} className={`rounded-[1rem] border px-4 py-3 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-stone-200 bg-stone-50/70"}`}>
                            <p className={`text-[11px] font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>{key}</p>
                            <p className={`mt-2 text-sm ${isDark ? "text-white" : "text-stone-900"}`}>{trait.value}</p>
                          </div>
                        ) : null)}
                        {continuityTraits.length === 0 ? (
                          <p className={isDark ? "text-sm text-slate-400" : "text-sm text-stone-500"}>No continuity traits are confirmed yet.</p>
                        ) : null}
                        <div className={`rounded-[1rem] border px-4 py-3 md:col-span-2 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-stone-200 bg-stone-50/70"}`}>
                          <p className={`text-[11px] font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Arc context</p>
                          <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-600"}`}>
                            {selectedCharacter.arc_summary || "No arc progression has been captured yet."}
                          </p>
                        </div>
                      </div>
                    ) : null}

                    {activeTab === "evidence" ? (
                      <div className="mt-5 space-y-4">
                        {growthEvents.map((event, index) => (
                          <div key={`${selectedCharacter.id}-growth-${index}`} className={`rounded-[1rem] border px-4 py-3 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-stone-200 bg-stone-50/70"}`}>
                            <div className="flex flex-wrap items-center gap-2">
                              {growthChapter(event) ? (
                                <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.16em] ${isDark ? "bg-violet-500/15 text-violet-100" : "bg-violet-100 text-violet-700"}`}>
                                  Chapter {growthChapter(event)}
                                </span>
                              ) : null}
                              {event.is_major ? (
                                <span className={`rounded-full px-2 py-0.5 text-[10px] ${isDark ? "bg-amber-500/12 text-amber-200" : "bg-amber-50 text-amber-700"}`}>
                                  major
                                </span>
                              ) : null}
                            </div>
                            <p className={`mt-2 text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{growthTitle(event)}</p>
                            {event.description || event.impact ? (
                              <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-600"}`}>
                                {event.description || event.impact}
                              </p>
                            ) : null}
                          </div>
                        ))}
                        {growthEvents.length === 0 && selectedCharacter.relationship_summaries?.length ? selectedCharacter.relationship_summaries.map((summary, index) => (
                          <div key={`${selectedCharacter.id}-summary-${index}`} className={`rounded-[1rem] border px-4 py-3 text-sm leading-6 ${isDark ? "border-white/10 bg-white/[0.03] text-slate-300" : "border-stone-200 bg-stone-50/70 text-stone-600"}`}>
                            {summary}
                          </div>
                        )) : null}
                        {growthEvents.length === 0 && !(selectedCharacter.relationship_summaries?.length) ? (
                          <p className={isDark ? "text-sm text-slate-400" : "text-sm text-stone-500"}>No evidence cards are available yet.</p>
                        ) : null}
                      </div>
                    ) : null}

                    {actionError && !editing ? <p className="mt-4 text-sm text-red-500">{actionError}</p> : null}
                  </div>
                ) : (
                  <div className="p-5">
                    <p className={isDark ? "text-sm text-slate-400" : "text-sm text-stone-500"}>No characters match the current filters.</p>
                  </div>
                )}
              </section>

              <aside className="min-h-[calc(100vh-16rem)] overflow-y-auto">
                <div className="p-4">
                  <RelationshipGraph
                    bookId={bookId}
                    upToChapter={relationshipChapter}
                    authorMode={isAuthorMode}
                    theme={theme}
                    compact
                    focusCharacterId={selectedCharacter?.id ?? null}
                    onSelectCharacterId={(characterId) => {
                      if (characterId) {
                        setSelectedId(characterId)
                        setEditing(false)
                      }
                    }}
                  />

                  {selectedCharacter ? (
                    <div className={`mt-4 rounded-[1.2rem] border p-4 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-stone-200 bg-stone-50/75"}`}>
                      <p className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Selected character</p>
                      <h3 className={`mt-2 text-2xl font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{selectedCharacter.name}</h3>
                      <p className={`mt-3 text-sm leading-7 ${isDark ? "text-slate-300" : "text-stone-600"}`}>
                        {selectedCharacterSummary}
                      </p>
                      <div className={`mt-4 flex items-center justify-between rounded-xl border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-black/20 text-slate-300" : "border-stone-200 bg-white text-stone-600"}`}>
                        <span>Connections in view</span>
                        <span className="font-semibold">{selectedConnections.length}</span>
                      </div>
                    </div>
                  ) : null}

                  {selectedCharacter ? (
                    <div className={`mt-4 rounded-[1.2rem] border p-4 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-stone-200 bg-stone-50/75"}`}>
                      <p className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-violet-300" : "text-violet-700"}`}>In-character chat</p>
                      <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-400" : "text-stone-500"}`}>
                        Replies use the extracted personality, motivations, fears, relationships, and growth evidence from the manuscript up to chapter {relationshipChapter}.
                      </p>
                      <div className={`mt-3 max-h-72 space-y-2 overflow-y-auto rounded-[1rem] border p-3 ${isDark ? "border-white/10 bg-black/20" : "border-stone-200 bg-white"}`}>
                        {chatMessages.length === 0 ? (
                          <p className={`text-sm ${isDark ? "text-slate-500" : "text-stone-500"}`}>Ask {selectedCharacter.name} something in their own voice.</p>
                        ) : null}
                        {chatMessages.map((message, index) => (
                          <div
                            key={`${message.role}-${index}`}
                            className={`rounded-xl px-3 py-2 text-sm leading-6 ${message.role === "user"
                              ? isDark ? "bg-violet-500/15 text-violet-100" : "bg-violet-50 text-violet-800"
                              : isDark ? "bg-white/[0.05] text-slate-200" : "bg-stone-50 text-stone-700"
                            }`}
                          >
                            {message.content}
                          </div>
                        ))}
                        {chatLoading ? <p className={`text-sm ${isDark ? "text-slate-500" : "text-stone-500"}`}>{selectedCharacter.name} is answering...</p> : null}
                      </div>
                      {chatHint ? <p className={`mt-2 text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>{chatHint}</p> : null}
                      <div className="mt-3 flex gap-2">
                        <input
                          value={chatInput}
                          onChange={(event) => setChatInput(event.target.value)}
                          onKeyDown={(event) => {
                            if (event.key === "Enter") void handleCharacterChat()
                          }}
                          placeholder={`Ask ${selectedCharacter.name}...`}
                          className={`min-w-0 flex-1 rounded-xl border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-black/20 text-white placeholder:text-slate-500" : "border-stone-200 bg-white text-stone-900 placeholder:text-stone-400"}`}
                        />
                        <button
                          type="button"
                          onClick={() => void handleCharacterChat()}
                          disabled={chatLoading || !chatInput.trim()}
                          className="rounded-xl bg-[linear-gradient(135deg,#8b5cf6,#6d28d9)] px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
                        >
                          Send
                        </button>
                      </div>
                    </div>
                  ) : null}

                  <div className={`mt-4 rounded-[1.2rem] border p-4 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-stone-200 bg-stone-50/75"}`}>
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <p className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Relationship map</p>
                        <p className={`mt-1 text-sm ${isDark ? "text-slate-300" : "text-stone-600"}`}>{selectedCharacter?.name || "Select a character"}</p>
                      </div>
                      <span className={`rounded-full px-2.5 py-1 text-[10px] font-semibold ${isDark ? "bg-white/[0.05] text-slate-300" : "bg-white text-stone-600 border border-stone-200"}`}>
                        {selectedConnections.length} links
                      </span>
                    </div>

                    <div className="mt-4 space-y-2">
                      {selectedConnections.length > 0 ? selectedConnections.map((edge, index) => (
                        <button
                          key={`${edge.source}-${edge.target}-${edge.type}-${index}`}
                          type="button"
                          onClick={() => {
                            setSelectedId(edge.counterpartId)
                            setActiveTab("relationships")
                          }}
                          className={`w-full rounded-[0.95rem] border px-3 py-3 text-left transition ${isDark ? "border-white/8 bg-black/20 hover:bg-white/[0.04]" : "border-stone-200 bg-white hover:bg-stone-50"}`}
                        >
                          <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{edge.counterpartName}</p>
                          <p className={`mt-1 text-xs ${isDark ? "text-slate-400" : "text-stone-500"}`}>
                            {formatRelationshipType(edge.type)} • {sentimentLabel(edge.sentiment)}{typeof edge.from_chapter === "number" ? ` • Ch. ${edge.from_chapter}` : ""}
                          </p>
                        </button>
                      )) : (
                        <p className={isDark ? "text-sm text-slate-400" : "text-sm text-stone-500"}>No relationship links are visible for the selected character yet.</p>
                      )}
                    </div>
                  </div>
                </div>
              </aside>
            </div>
          </div>
        ) : !error ? (
          <div className={`mt-5 rounded-[1.4rem] border p-6 text-sm ${isDark ? "border-white/10 bg-black/20 text-slate-300" : "border-stone-200 bg-white/85 text-stone-600"}`}>
            No character profiles are ready yet. Processing continues in the background after upload.
          </div>
        ) : null}
      </div>
    </div>
  )
}
