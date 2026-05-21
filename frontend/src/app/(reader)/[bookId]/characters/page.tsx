"use client"

import { useQuery } from "@tanstack/react-query"
import { useDeferredValue, useEffect, useMemo, useState, type ReactNode } from "react"
import Link from "next/link"
import { useParams, useRouter } from "next/navigation"

import RelationshipGraph from "@/components/intelligence/RelationshipGraph"
import { booksApi } from "@/lib/api/books"
import { CONFIDENCE_THRESHOLDS } from "@/lib/constants"
import { intelligenceApi } from "@/lib/api/intelligence"
import { asQueryKey, bookCacheKey, readerCacheKey } from "@/lib/query/cacheKeys"
import { readerApi } from "@/lib/api/reader"
import { saveContextualVaultNote } from "@/lib/utils/notes"
import type { Book } from "@/types/book"
import type {
  Character,
  CharacterCandidate,
  CharacterReviewResponse,
  RelationshipGraph as RelationshipGraphData,
} from "@/types/character"
import type { ChatMessage } from "@/types/intelligence"
import type { ReadingProgress, SearchResult } from "@/types/reader"

type EditDraft = {
  name: string
  aliases: string
  description: string
  goal: string
  lieTheyBelieve: string
  backstoryWound: string
  arcType: string
  arcSummary: string
  personalityTags: string
  motivations: string
  fears: string
}

type CreateDraft = EditDraft & {
  role: "" | "mc" | "sc" | "background"
  firstChapter: string
}

type RelationshipComposerDraft = {
  counterpartId: string
  relType: "ally" | "enemy" | "family" | "mentor" | "neutral" | "political" | "romantic" | "rival"
  sentiment: string
  description: string
  fromChapter: string
  toChapter: string
}

type CharacterTab = "overview" | "relationships" | "arc" | "evidence" | "continuity" | "notes"
type SidebarTab = "insights" | "evidence" | "ask"
type CastFilter = "all" | "main" | "minor" | "needs-review" | "duplicates"
type WorkspaceMode = "profile" | "duplicates"

type MergeSuggestion = {
  key: string
  suggestionId?: string
  primaryId: string
  secondaryId: string
  confidence: number
  reasons: string[]
}

type ConnectedRelationship = RelationshipGraphData["edges"][number] & {
  counterpartId: string
  counterpartName: string
}

type CharacterHealth = {
  score: number
  tone: "strong" | "moderate" | "attention"
  summary: string
  issues: string[]
}

type MenuAction = {
  label: string
  onClick: () => void
  danger?: boolean
  disabled?: boolean
  dividerBefore?: boolean
}

type EvidenceCacheEntry = {
  chapter: number
  results: SearchResult[]
}

const RELATIONSHIP_TYPE_OPTIONS: RelationshipComposerDraft["relType"][] = ["ally", "enemy", "family", "mentor", "neutral", "political", "romantic", "rival"]

function relationshipChangeKey(
  item: NonNullable<NonNullable<Character["arc_tracker"]>["relationship_changes"]>[number],
  index: number,
) {
  return [
    item.counterpart_id,
    item.chapter_number,
    item.type,
    item.to_chapter ?? "open",
    item.sentiment ?? "neutral",
    item.description ?? "",
    index,
  ].join(":")
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

function parsePositiveInteger(value: string, fallback = 1) {
  const parsed = Number.parseInt(value.trim(), 10)
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback
}

function parsePartitionTargets(value: string) {
  return value
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const [rawName, rawAliases] = line.split("|")
      return {
        name: rawName.trim(),
        aliases: (rawAliases ?? "")
          .split(",")
          .map((item) => item.trim())
          .filter(Boolean),
      }
    })
    .filter((item) => item.name)
}

function normalizeText(value: string | null | undefined) {
  return (value ?? "").trim().toLowerCase()
}

function slugify(value: string) {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
}

function characterInitial(name: string) {
  return (name.trim()[0] || "?").toUpperCase()
}

function formatRole(role: Character["role"]) {
  if (role === "mc") return "Primary character"
  if (role === "sc") return "Supporting character"
  if (role === "background") return "Minor character"
  return "Character"
}

function formatRoleFilterLabel(role: Character["role"]) {
  if (role === "mc") return "main"
  if (role === "sc") return "supporting"
  if (role === "background") return "minor"
  return "unclassified"
}

function formatStatus(status: Character["status"]) {
  return status === "deceased" ? "Deceased" : "Active"
}

function formatRelationshipType(type: string | null | undefined) {
  return (type || "connection")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (part) => part.toUpperCase())
}

function formatChapterRange(first: number | null | undefined, last: number | null | undefined) {
  if (typeof first !== "number") return "Chapter range unknown"
  if (typeof last === "number" && last > first) return `Ch. ${first}-${last}`
  return `Ch. ${first}`
}

function buildDraft(character: Character | null): EditDraft {
  return {
    name: character?.name ?? "",
    aliases: listToString(character?.aliases),
    description: character?.description ?? "",
    goal: character?.goal ?? character?.arc_tracker?.goal ?? "",
    lieTheyBelieve: character?.lie_they_believe ?? character?.arc_tracker?.lie_they_believe ?? "",
    backstoryWound: character?.backstory_wound ?? character?.arc_tracker?.wound_backstory ?? "",
    arcType: character?.arc_type ?? character?.arc_tracker?.arc_type ?? "",
    arcSummary: character?.arc_summary ?? "",
    personalityTags: listToString(character?.personality_tags),
    motivations: listToString(character?.motivations),
    fears: listToString(character?.fears),
  }
}

function buildCreateDraft(firstChapter = 1): CreateDraft {
  return {
    ...buildDraft(null),
    role: "",
    firstChapter: String(Math.max(1, firstChapter)),
  }
}

function buildRelationshipDraft(chapter = 1, counterpartId = ""): RelationshipComposerDraft {
  return {
    counterpartId,
    relType: "neutral",
    sentiment: "0",
    description: "",
    fromChapter: String(Math.max(1, chapter)),
    toChapter: "",
  }
}

function graphVisibilityLabel(value: Character["graph_visibility_override"]) {
  if (value === "include") return "Forced into graph"
  if (value === "exclude") return "Excluded from graph"
  return "Auto visibility"
}

function graphVisibilityReasonCopy(reason: string) {
  switch (reason) {
    case "author_override_include":
      return "Author override keeps this character visible."
    case "author_override_exclude":
      return "Author override hides this character."
    case "manual_character":
      return "Manual character entries count as cast members."
    case "relationship_evidence":
      return "Relationship history supports character visibility."
    case "repeat_mentions":
      return "Repeated mentions strengthen confidence."
    case "has_aliases":
      return "Alias evidence supports this identity."
    case "has_arc_summary":
      return "Arc summary gives stronger story evidence."
    case "profile_details":
      return "Profile details make this more likely to be a real character."
    case "score_meets_threshold":
      return "The current extraction score passes the graph threshold."
    case "score_below_threshold":
      return "The current extraction score falls below the graph threshold."
    case "possessive_name_shape":
      return "The name currently looks like a possessive phrase, not a person."
    case "lowercase_single_word":
      return "The name currently looks like a lowercase common word."
    case "missing_name":
      return "The character has no usable display name yet."
    case "no_name_tokens":
      return "The name does not currently parse into person-like tokens."
    default:
      return reason.replaceAll("_", " ")
  }
}

function visibleTraitEntries(character: Character | null) {
  if (!character) return []
  return Object.entries(character.trait_state ?? {}).filter(([, trait]) => (
    trait && trait.confidence >= CONFIDENCE_THRESHOLDS.SHOW_IN_UI && trait.value
  ))
}

function missingTraitLabels(character: Character) {
  const traits = new Set(visibleTraitEntries(character).map(([key]) => key))
  const missing: string[] = []
  if (!traits.has("age")) missing.push("age")
  if (!traits.has("build")) missing.push("physical description")
  if (!traits.has("distinguishing")) missing.push("distinguishing details")
  return missing
}

function sentimentLabel(value: number | null | undefined) {
  if (typeof value !== "number" || Number.isNaN(value)) return "Neutral"
  if (value >= 0.4) return "Positive"
  if (value <= -0.4) return "Tense"
  return "Neutral"
}

function strengthValue(value: number | null | undefined) {
  if (typeof value !== "number" || Number.isNaN(value)) return 32
  return Math.max(18, Math.min(100, Math.round((value + 1) * 50)))
}

function growthTitle(event: NonNullable<Character["growth_events"]>[number]) {
  return event.event_title || event.event || "Untitled event"
}

function growthChapter(event: NonNullable<Character["growth_events"]>[number]) {
  return event.chapter_number ?? event.chapter ?? null
}

function qualityFlags(character: Character, mergeSuggestionIds: Set<string>, connections: ConnectedRelationship[]) {
  const flags: string[] = []
  const missingTraits = missingTraitLabels(character)
  const lastSeenChapter = character.last_seen_chapter ?? character.first_chapter ?? null

  if (mergeSuggestionIds.has(character.id)) flags.push("Needs merge")
  if (missingTraits.length > 0) flags.push("Missing traits")
  if (!character.description && visibleTraitEntries(character).length < 2) flags.push("Low confidence")
  if (connections.some((connection) => !connection.description || typeof connection.from_chapter !== "number")) {
    flags.push("Needs evidence")
  }
  if (typeof lastSeenChapter === "number" && lastSeenChapter > character.first_chapter && (character.growth_events?.length ?? 0) === 0) {
    flags.push("Arc stale")
  }

  return Array.from(new Set(flags))
}

function healthTone(score: number): CharacterHealth["tone"] {
  if (score >= 80) return "strong"
  if (score >= 60) return "moderate"
  return "attention"
}

function buildCharacterHealth(character: Character, mergeSuggestionIds: Set<string>, connections: ConnectedRelationship[]): CharacterHealth {
  let score = 100
  const issues: string[] = []
  const missingTraits = missingTraitLabels(character)
  const lastSeenChapter = character.last_seen_chapter ?? character.first_chapter ?? null

  if (missingTraits.includes("physical description")) {
    score -= 16
    issues.push("Missing physical description")
  }
  if (missingTraits.includes("age")) {
    score -= 8
    issues.push("Age is not grounded")
  }
  if (!character.description) {
    score -= 14
    issues.push("Profile summary is still thin")
  }
  if (character.motivations.length === 0) {
    score -= 12
    issues.push("Motivation evidence is missing")
  }
  if (mergeSuggestionIds.has(character.id)) {
    score -= 16
    issues.push("Duplicate candidate found")
  }
  if (connections.some((connection) => !connection.description || typeof connection.from_chapter !== "number")) {
    score -= 12
    issues.push("Relationship evidence incomplete")
  }
  if (typeof lastSeenChapter === "number" && lastSeenChapter > character.first_chapter && (character.growth_events?.length ?? 0) === 0) {
    score -= 10
    issues.push(`Arc has no update after chapter ${lastSeenChapter}`)
  }
  for (const diagnostic of character.arc_tracker?.diagnostics ?? []) {
    score -= diagnostic.includes("too abruptly") ? 12 : 8
    issues.push(diagnostic)
  }
  if (!(character.arc_tracker?.voice_markers?.length ?? 0)) {
    score -= 6
    issues.push("Voice markers are not grounded yet")
  }
  if (!(character.goal ?? character.arc_tracker?.goal)) {
    score -= 8
    issues.push("Goal is missing")
  }
  if (visibleTraitEntries(character).length < 2) {
    score -= 10
  }

  const normalizedScore = Math.max(24, Math.min(issues.length > 0 ? 86 : 94, Math.round(score)))
  const tone = healthTone(normalizedScore)
  const summary = tone === "strong"
    ? "Well-grounded across traits, continuity, and relationships."
    : tone === "moderate"
      ? "Some continuity gaps and missing data need attention."
      : "Important profile gaps are weakening this character record."

  return {
    score: normalizedScore,
    tone,
    summary,
    issues: issues.slice(0, 4),
  }
}

function flagClasses(isDark: boolean, flag: string) {
  if (flag === "Needs merge") {
    return isDark ? "bg-amber-500/12 text-amber-200" : "bg-amber-50 text-amber-700"
  }
  if (flag === "Low confidence" || flag === "Arc stale") {
    return isDark ? "bg-rose-500/12 text-rose-200" : "bg-rose-50 text-rose-700"
  }
  return isDark ? "bg-sky-500/12 text-sky-200" : "bg-sky-50 text-sky-700"
}

function sidebarTabClasses(isDark: boolean, active: boolean) {
  if (active) {
    return isDark
      ? "border-b border-violet-400 text-white"
      : "border-b border-violet-500 text-violet-700"
  }
  return isDark ? "border-b border-transparent text-slate-400 hover:text-slate-200" : "border-b border-transparent text-stone-500 hover:text-stone-800"
}

function workspaceTabClasses(isDark: boolean, active: boolean) {
  if (active) {
    return isDark
      ? "border-b-2 border-violet-400 text-white"
      : "border-b-2 border-violet-500 text-violet-700"
  }
  return isDark ? "border-b-2 border-transparent text-slate-400 hover:text-slate-200" : "border-b-2 border-transparent text-stone-500 hover:text-stone-800"
}

function filterChipClasses(isDark: boolean, active: boolean) {
  if (active) {
    return isDark
      ? "border-violet-400/40 bg-violet-500/14 text-violet-100"
      : "border-violet-300 bg-violet-50 text-violet-700"
  }
  return isDark ? "border-white/10 text-slate-300 hover:bg-white/[0.04]" : "border-stone-200 text-stone-600 hover:bg-stone-50"
}

function buildSelectedCharacterSummary(character: Character | null, connections: ConnectedRelationship[]) {
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

  return [
    character.description || `${character.name} is a ${formatRole(character.role).toLowerCase()}.`,
    age ? `${character.name} appears to be ${age}.` : null,
    distinguishing ? `Notable for ${distinguishing}.` : null,
    disposition ? `Disposition: ${disposition}.` : null,
    wants ? `Wants: ${wants}.` : null,
    relationshipNotes || null,
  ]
    .filter(Boolean)
    .join(" ")
}

function topStats(characterCount: number, relationshipCount: number, chapter: number, mergeSuggestionCount: number) {
  return [
    { label: "characters", value: String(characterCount) },
    { label: "relationships", value: String(relationshipCount) },
    { label: "chapter", value: String(chapter) },
    { label: "merge suggestions", value: String(mergeSuggestionCount) },
  ]
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement("a")
  anchor.href = url
  anchor.download = filename
  anchor.click()
  URL.revokeObjectURL(url)
}

function iconButtonClasses(isDark: boolean) {
  return `inline-flex h-10 w-10 items-center justify-center rounded-xl border transition ${
    isDark ? "border-white/10 bg-white/[0.04] text-slate-200 hover:bg-white/[0.08]" : "border-stone-200 bg-white text-stone-700 hover:bg-stone-50"
  }`
}

function actionButtonClasses(isDark: boolean) {
  return `inline-flex items-center rounded-xl border px-4 py-2.5 text-sm font-medium transition ${
    isDark ? "border-white/10 bg-white/[0.04] text-slate-100 hover:bg-white/[0.08]" : "border-stone-200 bg-white text-stone-700 hover:bg-stone-50"
  }`
}

function menuPanelClasses(isDark: boolean) {
  return `absolute right-0 top-full z-30 mt-2 w-60 overflow-hidden rounded-2xl border p-1 shadow-2xl ${
    isDark ? "border-white/10 bg-[#0d1016]" : "border-stone-200 bg-white"
  }`
}

function StatCard({ label, value, isDark }: { label: string; value: string; isDark: boolean }) {
  return (
    <div className={`min-h-[88px] rounded-[1rem] border px-4 py-3 ${isDark ? "border-white/10 bg-[#0d1118]" : "border-stone-200 bg-white/92"}`}>
      <p className={`text-[1.75rem] font-semibold leading-none tracking-tight ${isDark ? "text-white" : "text-stone-950"}`}>{value}</p>
      <p className={`mt-3 text-[10px] font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-400" : "text-stone-400"}`}>{label}</p>
    </div>
  )
}

function SurfaceCard({
  title,
  children,
  isDark,
  className = "",
}: {
  title: string
  children: ReactNode
  isDark: boolean
  className?: string
}) {
  return (
    <section className={`rounded-[1.15rem] border px-4 py-4 ${isDark ? "border-white/8 bg-[#10141d]/88 shadow-[0_12px_28px_rgba(0,0,0,0.12)]" : "border-stone-200 bg-stone-50/80"} ${className}`}>
      <p className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>{title}</p>
      <div className="mt-4">{children}</div>
    </section>
  )
}

function HealthRing({ score, tone, isDark }: { score: number; tone: CharacterHealth["tone"]; isDark: boolean }) {
  const accent = tone === "strong" ? "#22c55e" : tone === "moderate" ? "#8b5cf6" : "#f59e0b"

  return (
    <div
      className="relative flex h-24 w-24 items-center justify-center rounded-full"
      style={{
        background: `conic-gradient(${accent} ${score}%, ${isDark ? "rgba(255,255,255,0.09)" : "rgba(148,163,184,0.2)"} ${score}% 100%)`,
      }}
    >
      <div className={`flex h-[74px] w-[74px] items-center justify-center rounded-full text-2xl font-semibold ${isDark ? "bg-[#0d1016] text-white" : "bg-white text-stone-950"}`}>
        {score}%
      </div>
    </div>
  )
}

function OverflowMenu({
  isDark,
  open,
  onToggle,
  actions,
}: {
  isDark: boolean
  open: boolean
  onToggle: () => void
  actions: MenuAction[]
}) {
  return (
    <div className="relative">
      <button type="button" onClick={onToggle} className={iconButtonClasses(isDark)} aria-label="Open menu">
        <svg className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
          <path d="M10 4.75a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3ZM10 11.5a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3ZM10 18.25a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3Z" />
        </svg>
      </button>

      {open ? (
        <div className={menuPanelClasses(isDark)}>
          {actions.map((action, index) => (
            <div key={`${action.label}-${index}`} className={action.dividerBefore ? `mt-1 border-t pt-1 ${isDark ? "border-white/10" : "border-stone-200"}` : ""}>
              <button
                type="button"
                disabled={action.disabled}
                onClick={action.onClick}
                className={`block w-full rounded-xl px-4 py-2.5 text-left text-sm transition disabled:cursor-not-allowed disabled:opacity-50 ${
                  action.danger
                    ? isDark ? "text-rose-300 hover:bg-rose-500/12" : "text-rose-700 hover:bg-rose-50"
                    : isDark ? "text-slate-200 hover:bg-white/[0.06]" : "text-stone-700 hover:bg-stone-50"
                }`}
              >
                {action.label}
              </button>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  )
}

function QuickActionTile({
  isDark,
  title,
  description,
  onClick,
}: {
  isDark: boolean
  title: string
  description: string
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-[1rem] border p-3 text-left transition ${isDark ? "border-white/10 bg-[#0d1118] hover:bg-white/[0.05]" : "border-stone-200 bg-white hover:bg-stone-50"}`}
    >
      <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{title}</p>
      <p className={`mt-1 text-xs leading-5 ${isDark ? "text-slate-400" : "text-stone-500"}`}>{description}</p>
    </button>
  )
}

export default function CharactersPage() {
  const { bookId } = useParams<{ bookId: string }>()
  const router = useRouter()

  const { data: bookData = null, isLoading: bookLoading } = useQuery<Book | null>({
    queryKey: asQueryKey(bookCacheKey(bookId, "detail")),
    queryFn: () => booksApi.get(bookId),
  })
  const { data: progressData = null } = useQuery<ReadingProgress | null>({
    queryKey: asQueryKey(readerCacheKey(bookId, "progress")),
    queryFn: () => readerApi.getProgress(bookId).catch(() => null),
  })
  const {
    data: charactersData = [],
    refetch: refetchCharacters,
    isLoading: charactersLoading,
  } = useQuery<Character[]>({
    queryKey: asQueryKey(bookCacheKey(bookId, "characters")),
    queryFn: () => booksApi.getCharacters(bookId),
  })
  const emptyReview = useMemo<CharacterReviewResponse>(() => ({
    candidates: [],
    duplicate_suggestions: [],
    counts: {
      pending_candidates: 0,
      pending_duplicate_suggestions: 0,
    },
  }), [])
  const {
    data: reviewData = emptyReview,
    refetch: refetchCharacterReview,
  } = useQuery<CharacterReviewResponse>({
    queryKey: asQueryKey(bookCacheKey(bookId, "character-review")),
    queryFn: () => booksApi.getCharacterReview(bookId).catch(() => emptyReview),
  })
  const [book, setBook] = useState<Book | null>(null)
  const [progress, setProgress] = useState<ReadingProgress | null>(null)
  const [chars, setChars] = useState<Character[]>([])
  const [graphData, setGraphData] = useState<RelationshipGraphData | null>(null)
  const loading = bookLoading || charactersLoading
  const error: string | null = null
  const [theme, setTheme] = useState<"light" | "dark">("light")
  const [search, setSearch] = useState("")
  const [selectedId, setSelectedId] = useState("")
  const [selectedMergeKey, setSelectedMergeKey] = useState("")
  const [manualMergePrimaryId, setManualMergePrimaryId] = useState("")
  const [manualMergeSecondaryId, setManualMergeSecondaryId] = useState("")
  const [activeTab, setActiveTab] = useState<CharacterTab>("overview")
  const [sidebarTab, setSidebarTab] = useState<SidebarTab>("insights")
  const [castFilter, setCastFilter] = useState<CastFilter>("all")
  const [workspaceMode, setWorkspaceMode] = useState<WorkspaceMode>("profile")
  const [showAllCast, setShowAllCast] = useState(false)
  const [dismissedMergeKeys, setDismissedMergeKeys] = useState<string[]>([])
  const [mergeBusy, setMergeBusy] = useState(false)
  const [mergeError, setMergeError] = useState<string | null>(null)
  const [creating, setCreating] = useState(false)
  const [createBusy, setCreateBusy] = useState(false)
  const [editing, setEditing] = useState(false)
  const [saving, setSaving] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [partitioning, setPartitioning] = useState(false)
  const [shareState, setShareState] = useState<"idle" | "copied" | "error">("idle")
  const [exporting, setExporting] = useState<false | "character" | "bible">()
  const [refreshingGraph, setRefreshingGraph] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)
  const [noteToast, setNoteToast] = useState<string | null>(null)
  const [draft, setDraft] = useState<EditDraft>(buildDraft(null))
  const [createDraft, setCreateDraft] = useState<CreateDraft>(buildCreateDraft(1))
  const [relationshipDraft, setRelationshipDraft] = useState<RelationshipComposerDraft>(buildRelationshipDraft(1))
  const [createRelationshipBusy, setCreateRelationshipBusy] = useState(false)
  const [graphOverrideBusy, setGraphOverrideBusy] = useState(false)
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([])
  const [chatInput, setChatInput] = useState("")
  const [chatLoading, setChatLoading] = useState(false)
  const [chatHint, setChatHint] = useState<string | null>(null)
  const [evidenceCache, setEvidenceCache] = useState<Record<string, EvidenceCacheEntry>>({})
  const [evidenceLoadingId, setEvidenceLoadingId] = useState<string | null>(null)
  const [evidenceError, setEvidenceError] = useState<string | null>(null)
  const [pageMenuOpen, setPageMenuOpen] = useState(false)
  const [characterMenuOpen, setCharacterMenuOpen] = useState(false)
  const [candidateActionId, setCandidateActionId] = useState<string | null>(null)

  useEffect(() => {
    setBook(bookData)
  }, [bookData])

  useEffect(() => {
    setChars(charactersData)
    setSelectedId((current) => current || charactersData[0]?.id || "")
  }, [charactersData])

  useEffect(() => {
    setProgress(progressData)
  }, [progressData])

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
    readerApi.getRelationships(bookId, relationshipChapter, { includeInactive: book.mode === "author" })
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
  const deferredSearch = useDeferredValue(search.trim().toLowerCase())

  const pendingCandidates = useMemo(
    () => (reviewData.candidates ?? []).filter((candidate) => candidate.status === "pending"),
    [reviewData.candidates],
  )

  const mergeSuggestions = useMemo(
    () => (reviewData.duplicate_suggestions ?? [])
      .filter((suggestion) => suggestion.status === "pending" && !dismissedMergeKeys.includes(suggestion.id))
      .map((suggestion) => ({
        key: suggestion.id,
        suggestionId: suggestion.id,
        primaryId: suggestion.primary_character_id,
        secondaryId: suggestion.secondary_character_id,
        confidence: suggestion.confidence,
        reasons: suggestion.reasons,
      })),
    [dismissedMergeKeys, reviewData.duplicate_suggestions],
  )

  const mergeSuggestionIds = useMemo(
    () => new Set(mergeSuggestions.flatMap((suggestion) => [suggestion.primaryId, suggestion.secondaryId])),
    [mergeSuggestions],
  )

  const nodeLookup = useMemo(
    () => new Map((graphData?.nodes ?? []).map((node) => [node.id, node.name])),
    [graphData],
  )

  const connectionsByCharacter = useMemo(() => {
    const map = new Map<string, ConnectedRelationship[]>()

    for (const edge of graphData?.edges ?? []) {
      const leftCounterpart = {
        ...edge,
        counterpartId: edge.target,
        counterpartName: nodeLookup.get(edge.target) || "Unknown character",
      }
      const rightCounterpart = {
        ...edge,
        counterpartId: edge.source,
        counterpartName: nodeLookup.get(edge.source) || "Unknown character",
      }

      map.set(edge.source, [...(map.get(edge.source) ?? []), leftCounterpart])
      map.set(edge.target, [...(map.get(edge.target) ?? []), rightCounterpart])
    }

    for (const [key, value] of map.entries()) {
      map.set(
        key,
        value.slice().sort((left, right) => (right.from_chapter ?? 0) - (left.from_chapter ?? 0)),
      )
    }

    return map
  }, [graphData, nodeLookup])

  const relationshipCounts = useMemo(() => {
    const counts = new Map<string, number>()
    for (const edge of graphData?.edges ?? []) {
      counts.set(edge.source, (counts.get(edge.source) ?? 0) + 1)
      counts.set(edge.target, (counts.get(edge.target) ?? 0) + 1)
    }
    return counts
  }, [graphData])

  const healthByCharacter = useMemo(() => {
    const map = new Map<string, CharacterHealth>()
    for (const character of chars) {
      map.set(character.id, buildCharacterHealth(character, mergeSuggestionIds, connectionsByCharacter.get(character.id) ?? []))
    }
    return map
  }, [chars, connectionsByCharacter, mergeSuggestionIds])

  const filteredChars = useMemo(() => chars.filter((char) => {
    const flags = qualityFlags(char, mergeSuggestionIds, connectionsByCharacter.get(char.id) ?? [])
    const haystack = [
      char.name,
      ...(char.aliases ?? []),
      char.description ?? "",
      char.arc_summary ?? "",
      ...(char.personality_tags ?? []),
      ...flags,
    ]
      .join(" ")
      .toLowerCase()

    if (deferredSearch && !haystack.includes(deferredSearch)) return false
    if (castFilter === "all") return true
    if (castFilter === "main") return char.role === "mc" || char.role === "sc"
    if (castFilter === "minor") return char.role === "background" || !char.role
    if (castFilter === "duplicates") return mergeSuggestionIds.has(char.id)
    return flags.length > 0
  }), [castFilter, chars, connectionsByCharacter, deferredSearch, mergeSuggestionIds])

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

  const filteredMergeSuggestions = useMemo(() => mergeSuggestions.filter((suggestion) => {
    if (!deferredSearch) return true
    const primary = chars.find((char) => char.id === suggestion.primaryId)
    const secondary = chars.find((char) => char.id === suggestion.secondaryId)
    return [
      primary?.name ?? "",
      secondary?.name ?? "",
      ...(primary?.aliases ?? []),
      ...(secondary?.aliases ?? []),
      ...suggestion.reasons,
    ]
      .join(" ")
      .toLowerCase()
      .includes(deferredSearch)
  }), [chars, deferredSearch, mergeSuggestions])

  const filteredPendingCandidates = useMemo(() => pendingCandidates.filter((candidate) => {
    if (!deferredSearch) return true
    return [
      candidate.proposed_name,
      candidate.raw_name,
      ...(candidate.aliases ?? []),
      ...(candidate.reason_codes ?? []),
    ]
      .join(" ")
      .toLowerCase()
      .includes(deferredSearch)
  }), [deferredSearch, pendingCandidates])

  useEffect(() => {
    if (filteredMergeSuggestions.length === 0) {
      setSelectedMergeKey("")
      return
    }
    if (filteredMergeSuggestions.some((suggestion) => suggestion.key === selectedMergeKey)) return
    setSelectedMergeKey(filteredMergeSuggestions[0].key)
  }, [filteredMergeSuggestions, selectedMergeKey])

  const selectedMergeSuggestion = filteredMergeSuggestions.find((suggestion) => suggestion.key === selectedMergeKey)
    ?? filteredMergeSuggestions[0]
    ?? null

  const visibleCastChars = showAllCast ? filteredChars : filteredChars.slice(0, 8)

  const selectedConnections = selectedCharacter ? connectionsByCharacter.get(selectedCharacter.id) ?? [] : []
  const hiddenGraphNodes = graphData?.hidden_nodes ?? []
  const selectedHiddenGraphRecord = selectedCharacter ? hiddenGraphNodes.find((node) => node.id === selectedCharacter.id) ?? null : null
  const selectedFlags = selectedCharacter ? qualityFlags(selectedCharacter, mergeSuggestionIds, selectedConnections) : []
  const selectedHealth = selectedCharacter ? healthByCharacter.get(selectedCharacter.id) ?? null : null
  const selectedCharacterSummary = buildSelectedCharacterSummary(selectedCharacter, selectedConnections)
  const selectedEvidence = selectedCharacter ? evidenceCache[selectedCharacter.id]?.results ?? [] : []
  const selectedArcTracker = selectedCharacter?.arc_tracker ?? null
  const selectedGrowthEvents = (selectedCharacter?.growth_events ?? [])
    .slice()
    .sort((left, right) => (right.chapter_number ?? right.chapter ?? 0) - (left.chapter_number ?? left.chapter ?? 0))
  const relationshipCounterpartOptions = useMemo(
    () => chars.filter((char) => char.id !== selectedCharacter?.id).sort((left, right) => left.name.localeCompare(right.name)),
    [chars, selectedCharacter?.id],
  )

  const mergeableCharacters = useMemo(
    () => chars.slice().sort((left, right) => left.name.localeCompare(right.name)),
    [chars],
  )
  const manualMergePrimary = manualMergePrimaryId ? chars.find((char) => char.id === manualMergePrimaryId) ?? null : null
  const manualMergeSecondary = manualMergeSecondaryId ? chars.find((char) => char.id === manualMergeSecondaryId) ?? null : null
  const isManualMerge = Boolean(manualMergePrimary && manualMergeSecondary)
  const selectedMergePrimary = isManualMerge
    ? manualMergePrimary
    : selectedMergeSuggestion ? chars.find((char) => char.id === selectedMergeSuggestion.primaryId) ?? null : null
  const selectedMergeSecondary = isManualMerge
    ? manualMergeSecondary
    : selectedMergeSuggestion ? chars.find((char) => char.id === selectedMergeSuggestion.secondaryId) ?? null : null
  const selectedMergePrimaryEvidence = selectedMergePrimary ? evidenceCache[selectedMergePrimary.id]?.results ?? [] : []
  const selectedMergeSecondaryEvidence = selectedMergeSecondary ? evidenceCache[selectedMergeSecondary.id]?.results ?? [] : []

  useEffect(() => {
    if (!editing) {
      setDraft(buildDraft(selectedCharacter))
      setActionError(null)
    }
  }, [editing, selectedCharacter])

  useEffect(() => {
    const fallbackCounterpart = chars.find((char) => char.id !== selectedCharacter?.id)?.id ?? ""
    setRelationshipDraft(buildRelationshipDraft(relationshipChapter, fallbackCounterpart))
  }, [chars, relationshipChapter, selectedCharacter?.id])

  useEffect(() => {
    setChatMessages([])
    setChatInput("")
    setChatHint(null)
  }, [selectedCharacter?.id])

  useEffect(() => {
    setCharacterMenuOpen(false)
    setPageMenuOpen(false)
  }, [selectedId, selectedMergeKey, workspaceMode])

  useEffect(() => {
    if (workspaceMode !== "duplicates" || !manualMergePrimaryId) return
    if (!chars.some((char) => char.id === manualMergePrimaryId)) {
      setManualMergePrimaryId("")
    }
  }, [chars, manualMergePrimaryId, workspaceMode])

  useEffect(() => {
    if (workspaceMode !== "duplicates" || !manualMergeSecondaryId) return
    if (!chars.some((char) => char.id === manualMergeSecondaryId)) {
      setManualMergeSecondaryId("")
    }
  }, [chars, manualMergeSecondaryId, workspaceMode])

  function openCreateCharacter() {
    setWorkspaceMode("profile")
    setCreating(true)
    setEditing(false)
    setActiveTab("overview")
    setSidebarTab("insights")
    setCharacterMenuOpen(false)
    setPageMenuOpen(false)
    setActionError(null)
    setCreateDraft(buildCreateDraft(progress?.current_chapter ?? 1))
  }

  async function loadCharacterEvidence(character: Character, force = false) {
    const cached = evidenceCache[character.id]
    if (!force && cached && cached.chapter === relationshipChapter) return cached.results

    setEvidenceLoadingId(character.id)
    setEvidenceError(null)
    try {
      const query = [character.name, character.aliases[0]].filter(Boolean).join(" ")
      const results = await readerApi.search(bookId, query || character.name, relationshipChapter)
      setEvidenceCache((current) => ({
        ...current,
        [character.id]: {
          chapter: relationshipChapter,
          results: results.slice(0, 8),
        },
      }))
      return results
    } catch {
      setEvidenceError("Could not pull grounded evidence right now.")
      return []
    } finally {
      setEvidenceLoadingId((current) => current === character.id ? null : current)
    }
  }

  useEffect(() => {
    if (!selectedCharacter || workspaceMode !== "profile") return
    if (activeTab !== "evidence" && sidebarTab !== "evidence") return
    void loadCharacterEvidence(selectedCharacter)
  }, [activeTab, sidebarTab, selectedCharacter, workspaceMode])

  useEffect(() => {
    if (workspaceMode !== "duplicates" || !selectedMergePrimary || !selectedMergeSecondary) return
    void loadCharacterEvidence(selectedMergePrimary)
    void loadCharacterEvidence(selectedMergeSecondary)
  }, [selectedMergePrimary, selectedMergeSecondary, workspaceMode])

  async function refreshCharacters() {
    const { data: refreshed = [] } = await refetchCharacters()
    await refetchCharacterReview()
    setChars(refreshed)
    return refreshed
  }

  async function refreshGraph() {
    setRefreshingGraph(true)
    try {
      const refreshed = await readerApi.getRelationships(bookId, relationshipChapter, { includeInactive: isAuthorMode })
      setGraphData(refreshed)
    } catch {
      setActionError("Could not rebuild the relationship graph.")
    } finally {
      setRefreshingGraph(false)
    }
  }

  async function handleMergeCharacters(primaryId: string, secondaryId: string, suggestionId?: string) {
    if (!primaryId || !secondaryId || primaryId === secondaryId) {
      setMergeError("Choose two different characters to merge.")
      return
    }
    setMergeBusy(true)
    setMergeError(null)
    try {
      const response = suggestionId
        ? await booksApi.acceptDuplicateSuggestion(bookId, suggestionId)
        : await booksApi.mergeCharacters(bookId, { primaryId, secondaryId })
      const refreshed = await refreshCharacters()
      await refreshGraph()
      setWorkspaceMode("profile")
      setSelectedId(response.merged || refreshed[0]?.id || "")
      setActiveTab("overview")
      setSidebarTab("insights")
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
        goal: draft.goal.trim() || null,
        lieTheyBelieve: draft.lieTheyBelieve.trim() || null,
        backstoryWound: draft.backstoryWound.trim() || null,
        arcType: draft.arcType.trim() || null,
        arcSummary: draft.arcSummary.trim() || null,
        personalityTags: stringToList(draft.personalityTags),
        motivations: stringToList(draft.motivations),
        fears: stringToList(draft.fears),
      })
      setChars((current) => current.map((item) => item.id === updated.id ? updated : item))
      setSelectedId(updated.id)
      await refetchCharacterReview()
      await refreshGraph()
      setEditing(false)
    } catch {
      setActionError("Could not save character changes.")
    } finally {
      setSaving(false)
    }
  }

  async function handleGraphVisibilityOverride(override: "include" | "exclude" | null) {
    if (!selectedCharacter) return
    setGraphOverrideBusy(true)
    setActionError(null)
    try {
      const updated = await booksApi.updateCharacter(bookId, selectedCharacter.id, {
        graphVisibility: override,
      })
      setChars((current) => current.map((item) => item.id === updated.id ? updated : item))
      await refetchCharacterReview()
      await refreshGraph()
    } catch {
      setActionError("Could not update graph visibility for this character.")
    } finally {
      setGraphOverrideBusy(false)
    }
  }

  async function handleCreateCharacter() {
    setCreateBusy(true)
    setActionError(null)
    try {
      const created = await booksApi.createCharacter(bookId, {
        name: createDraft.name.trim(),
        firstChapter: parsePositiveInteger(createDraft.firstChapter, progress?.current_chapter ?? 1),
        aliases: stringToList(createDraft.aliases),
        role: createDraft.role || null,
        description: createDraft.description.trim() || null,
        goal: createDraft.goal.trim() || null,
        lieTheyBelieve: createDraft.lieTheyBelieve.trim() || null,
        backstoryWound: createDraft.backstoryWound.trim() || null,
        arcType: createDraft.arcType.trim() || null,
        arcSummary: createDraft.arcSummary.trim() || null,
        personalityTags: stringToList(createDraft.personalityTags),
        motivations: stringToList(createDraft.motivations),
        fears: stringToList(createDraft.fears),
      })
      setChars((current) => [...current, created])
      setSelectedId(created.id)
      await refetchCharacterReview()
      await refreshGraph()
      setCreating(false)
      setCastFilter("all")
      setSearch("")
    } catch {
      setActionError("Could not create this character.")
    } finally {
      setCreateBusy(false)
    }
  }

  async function handleCreateRelationship() {
    if (!selectedCharacter || !relationshipDraft.counterpartId) {
      setActionError("Choose a counterpart before creating a relationship.")
      return
    }
    setCreateRelationshipBusy(true)
    setActionError(null)
    try {
      await booksApi.createRelationship(bookId, {
        characterAId: selectedCharacter.id,
        characterBId: relationshipDraft.counterpartId,
        relType: relationshipDraft.relType,
        description: relationshipDraft.description.trim() || null,
        sentiment: relationshipDraft.sentiment === "" ? null : Number(relationshipDraft.sentiment),
        fromChapter: parsePositiveInteger(relationshipDraft.fromChapter, relationshipChapter),
        toChapter: relationshipDraft.toChapter === "" ? null : parsePositiveInteger(relationshipDraft.toChapter, relationshipChapter),
      })
      await refreshGraph()
      setRelationshipDraft(buildRelationshipDraft(relationshipChapter, relationshipDraft.counterpartId))
      setActiveTab("relationships")
    } catch {
      setActionError("Could not create the relationship.")
    } finally {
      setCreateRelationshipBusy(false)
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

  async function handleExportCharacter(format: "pdf" | "md" | "docx" = "pdf") {
    if (!selectedCharacter) return
    setExporting("character")
    try {
      const blob = await booksApi.exportCharacterCard(bookId, selectedCharacter.id, format)
      const bookBase = slugify(book?.title ?? "lorevia") || "lorevia"
      const characterBase = slugify(selectedCharacter.name) || "character"
      downloadBlob(blob, `${bookBase}-${characterBase}-character-card.${format}`)
      setCharacterMenuOpen(false)
    } finally {
      setExporting(false)
    }
  }

  async function handleExportCharacterBible(format: "pdf" | "md" | "docx" = "md") {
    setExporting("bible")
    try {
      const blob = await booksApi.exportCharacterBible(bookId, format)
      downloadBlob(blob, `${slugify(book?.title ?? "lorevia") || "lorevia"}-character-bible.${format}`)
      setPageMenuOpen(false)
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
      await refetchCharacterReview()
      await refreshGraph()
      setEditing(false)
      setCharacterMenuOpen(false)
    } catch {
      setActionError("Could not delete this character.")
    } finally {
      setDeleting(false)
    }
  }

  async function handlePartitionCharacter() {
    if (!selectedCharacter) return
    const suggestedTargets = selectedCharacter.aliases.length >= 2
      ? selectedCharacter.aliases.slice(0, 4).join("\n")
      : [selectedCharacter.name, ...selectedCharacter.aliases].filter(Boolean).join("\n")
    const input = window.prompt(
      "Split this character into separate cards.\nEnter one character per line.\nOptional aliases: Name | alias one, alias two",
      suggestedTargets,
    )
    if (!input) return

    const partitions = parsePartitionTargets(input)
    if (partitions.length < 2) {
      setActionError("Enter at least two distinct character names to split this card.")
      return
    }

    setPartitioning(true)
    setActionError(null)
    try {
      const response = await booksApi.partitionCharacter(bookId, selectedCharacter.id, { partitions })
      const refreshed = await booksApi.getCharacters(bookId)
      setChars(refreshed)
      setSelectedId(response.created[0] ?? refreshed[0]?.id ?? "")
      await refetchCharacterReview()
      setEditing(false)
      setWorkspaceMode("profile")
      setCharacterMenuOpen(false)
    } catch {
      setActionError("Could not split this character card.")
    } finally {
      setPartitioning(false)
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
        selectedCharacterSummary,
      )
      setChatMessages([...nextMessages, { role: "assistant", content: response.reply }])
      setChatHint(response.grounded_hint ?? null)
    } catch {
      setChatMessages([...nextMessages, { role: "assistant", content: "I cannot answer that right now." }])
    } finally {
      setChatLoading(false)
    }
  }

  function openCharacterEvidence() {
    if (!selectedCharacter) return
    setWorkspaceMode("profile")
    setActiveTab("evidence")
    setSidebarTab("evidence")
    void loadCharacterEvidence(selectedCharacter)
  }

  async function saveCharacterWorkspaceNote() {
    if (!selectedCharacter) return
    setActionError(null)
    try {
      const summary = buildSelectedCharacterSummary(selectedCharacter, selectedConnections)
      const bodyParts = [
        summary,
        selectedCharacter.arc_summary ? `## Arc summary\n\n${selectedCharacter.arc_summary}` : "",
        selectedCharacter.personality_tags.length ? `## Personality tags\n\n- ${selectedCharacter.personality_tags.join("\n- ")}` : "",
        selectedCharacter.motivations.length ? `## Motivations\n\n- ${selectedCharacter.motivations.join("\n- ")}` : "",
        selectedConnections.length
          ? `## Key relationships\n\n${selectedConnections
              .slice(0, 4)
              .map((edge) => `- ${edge.counterpartName}: ${formatRelationshipType(edge.type)}${edge.description ? ` - ${edge.description}` : ""}`)
              .join("\n")}`
          : "",
      ].filter(Boolean)

      await saveContextualVaultNote({
        bookId,
        title: selectedCharacter.name,
        content: bodyParts.join("\n\n"),
        context: "characters",
        folderSegments: [selectedCharacter.name],
      })
      setNoteToast(`Saved ${selectedCharacter.name} to Characters.`)
      window.setTimeout(() => setNoteToast(null), 2400)
    } catch {
      setActionError("Could not save this character to the notes workspace.")
    }
  }

  function openCharacterChat() {
    setWorkspaceMode("profile")
    setSidebarTab("ask")
  }

  function openRelationships() {
    setWorkspaceMode("profile")
    setActiveTab("relationships")
  }

  function openDuplicateReview(targetCharacterId?: string) {
    setCreating(false)
    setWorkspaceMode("duplicates")
    setManualMergePrimaryId("")
    setManualMergeSecondaryId("")
    if (targetCharacterId) {
      const preferred = filteredMergeSuggestions.find((suggestion) => suggestion.primaryId === targetCharacterId || suggestion.secondaryId === targetCharacterId)
      if (preferred) {
        setSelectedMergeKey(preferred.key)
        return
      }
      const fallbackSecondary = chars.find((char) => char.id !== targetCharacterId)?.id ?? ""
      setManualMergePrimaryId(targetCharacterId)
      setManualMergeSecondaryId(fallbackSecondary)
    }
  }

  function openManualMerge(primaryId?: string, secondaryId?: string) {
    setCreating(false)
    const primary = primaryId || selectedCharacter?.id || chars[0]?.id || ""
    const fallbackSecondary = chars.find((char) => char.id !== primary)?.id ?? ""
    setWorkspaceMode("duplicates")
    setManualMergePrimaryId(primary)
    setManualMergeSecondaryId(secondaryId && secondaryId !== primary ? secondaryId : fallbackSecondary)
    setSelectedMergeKey("")
  }

  function resetFilters() {
    setSearch("")
    setCastFilter("all")
    setWorkspaceMode("profile")
    setPageMenuOpen(false)
  }

  function dismissMergeSuggestion(key: string) {
    setDismissedMergeKeys((current) => current.includes(key) ? current : [...current, key])
    setMergeError(null)
  }

  async function handlePromoteCandidate(candidate: CharacterCandidate) {
    setCandidateActionId(candidate.id)
    setActionError(null)
    try {
      const response = await booksApi.promoteCharacterCandidate(bookId, candidate.id)
      const refreshed = await refreshCharacters()
      setWorkspaceMode("profile")
      setSelectedId(response.promoted || refreshed[0]?.id || "")
      await refreshGraph()
    } catch {
      setActionError("Could not promote this candidate into the cast.")
    } finally {
      setCandidateActionId(null)
    }
  }

  async function handleAttachCandidate(candidate: CharacterCandidate) {
    if (!selectedCharacter) {
      setActionError("Select a character profile first, then attach this candidate.")
      return
    }
    setCandidateActionId(candidate.id)
    setActionError(null)
    try {
      await booksApi.attachCharacterCandidate(bookId, candidate.id, selectedCharacter.id)
      await refreshCharacters()
      await refreshGraph()
    } catch {
      setActionError("Could not attach this candidate to the selected character.")
    } finally {
      setCandidateActionId(null)
    }
  }

  async function handleRejectCandidate(candidate: CharacterCandidate) {
    setCandidateActionId(candidate.id)
    setActionError(null)
    try {
      await booksApi.rejectCharacterCandidate(bookId, candidate.id)
      await refetchCharacterReview()
    } catch {
      setActionError("Could not reject this candidate.")
    } finally {
      setCandidateActionId(null)
    }
  }

  async function dismissDuplicateSuggestion(suggestion: MergeSuggestion) {
    if (!suggestion.suggestionId) {
      dismissMergeSuggestion(suggestion.key)
      return
    }
    setMergeBusy(true)
    setMergeError(null)
    try {
      await booksApi.dismissDuplicateSuggestion(bookId, suggestion.suggestionId)
      setDismissedMergeKeys((current) => current.includes(suggestion.key) ? current : [...current, suggestion.key])
      await refetchCharacterReview()
    } catch {
      setMergeError("Could not dismiss this duplicate suggestion.")
    } finally {
      setMergeBusy(false)
    }
  }

  const pageMenuActions: MenuAction[] = [
    ...(isAuthorMode ? [{ label: "Add character", onClick: () => { openCreateCharacter(); setPageMenuOpen(false) } }] : []),
    { label: exporting === "bible" ? "Exporting bible..." : "Export character bible", onClick: () => void handleExportCharacterBible("md"), disabled: exporting === "bible" },
    { label: exporting === "bible" ? "Exporting PDF..." : "Export as PDF", onClick: () => void handleExportCharacterBible("pdf"), disabled: exporting === "bible" },
    { label: "Review duplicate suggestions", onClick: () => { openDuplicateReview(); setPageMenuOpen(false) } },
    { label: "Start manual merge", onClick: () => { openManualMerge(); setPageMenuOpen(false) } },
    { label: refreshingGraph ? "Rebuilding graph..." : "Rebuild relationship graph", onClick: () => void refreshGraph(), disabled: refreshingGraph },
    { label: "Reset filters", onClick: resetFilters },
  ]

  const characterMenuActions: MenuAction[] = selectedCharacter ? [
    {
      label: editing ? "Close edit details" : "Edit details",
      onClick: () => {
        setEditing((current) => !current)
        setCharacterMenuOpen(false)
      },
    },
    {
      label: "Add alias",
      onClick: () => {
        setEditing(true)
        setCharacterMenuOpen(false)
      },
    },
    {
      label: "Find mentions",
      onClick: () => {
        openCharacterEvidence()
        setCharacterMenuOpen(false)
      },
    },
    {
      label: "Find evidence",
      onClick: () => {
        openCharacterEvidence()
        setCharacterMenuOpen(false)
      },
    },
    {
      label: "Review duplicate candidates",
      onClick: () => {
        openDuplicateReview(selectedCharacter.id)
        setCharacterMenuOpen(false)
      },
    },
    {
      label: "Merge with another character",
      onClick: () => {
        openManualMerge(selectedCharacter.id)
        setCharacterMenuOpen(false)
      },
    },
    {
      label: partitioning ? "Splitting character..." : "Split character card",
      onClick: () => void handlePartitionCharacter(),
      disabled: partitioning || !isAuthorMode,
    },
    {
      label: exporting === "character" ? "Exporting character..." : "Export character PDF",
      onClick: () => void handleExportCharacter("pdf"),
      disabled: exporting === "character",
    },
    {
      label: deleting ? "Deleting..." : "Delete character",
      onClick: () => void handleDeleteCharacter(),
      danger: true,
      dividerBefore: true,
      disabled: deleting || !isAuthorMode,
    },
  ] : []

  const stats = topStats(chars.length, graphData?.edges.length ?? 0, relationshipChapter, mergeSuggestions.length)

  const atmosphere = isDark
    ? "bg-[radial-gradient(circle_at_top_left,rgba(124,58,237,0.16),transparent_28%),radial-gradient(circle_at_top_right,rgba(59,130,246,0.10),transparent_26%),linear-gradient(180deg,#040507_0%,#090a0f_44%,#0e1016_100%)] text-slate-100"
    : "bg-[radial-gradient(circle_at_top_left,rgba(124,58,237,0.08),transparent_26%),radial-gradient(circle_at_top_right,rgba(244,114,182,0.07),transparent_24%),linear-gradient(180deg,#fbf8f3_0%,#f7f1e8_46%,#f4ede4_100%)] text-stone-950"

  if (loading) {
    return (
      <div className={`min-h-screen ${atmosphere}`}>
        <div className="mx-auto max-w-[1680px] px-4 py-8 sm:px-6 lg:px-8">
          <div className={`rounded-[1.5rem] border p-6 text-sm ${isDark ? "border-white/10 bg-black/20 text-slate-300" : "border-stone-200 bg-white/85 text-stone-600"}`}>
            Loading the Character Bible...
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className={`min-h-screen transition-colors ${atmosphere}`}>
      <div className="mx-auto max-w-[1680px] px-4 pb-8 pt-5 sm:px-6 lg:px-8">
        <button
          onClick={() => router.back()}
          className={`inline-flex items-center gap-2 text-sm font-medium transition ${isDark ? "text-slate-300 hover:text-white" : "text-stone-600 hover:text-stone-950"}`}
        >
          <svg className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
            <path fillRule="evenodd" d="M11.78 4.22a.75.75 0 0 1 0 1.06L8.06 9h8.19a.75.75 0 0 1 0 1.5H8.06l3.72 3.72a.75.75 0 1 1-1.06 1.06l-5-5a.75.75 0 0 1 0-1.06l5-5a.75.75 0 0 1 1.06 0Z" clipRule="evenodd" />
          </svg>
          Back
        </button>

        <div className="mt-4 flex flex-col gap-5 xl:flex-row xl:items-start xl:justify-between">
          <div className="min-w-0">
            <h1 className={`text-[2.55rem] font-semibold tracking-tight ${isDark ? "text-white" : "text-stone-950"}`}>Character Bible</h1>
            <p className={`mt-1.5 max-w-3xl text-sm leading-7 ${isDark ? "text-slate-300" : "text-stone-600"}`}>
              Manage cast, aliases, relationships, continuity, and duplicate review.
            </p>
          </div>

          <div className="flex flex-col gap-3 xl:min-w-[860px]">
            <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
              {stats.map((stat) => (
                <StatCard key={stat.label} label={stat.label} value={stat.value} isDark={isDark} />
              ))}
            </div>

            <div className="flex items-center justify-end gap-3">
              {isAuthorMode ? (
                <button
                  type="button"
                  onClick={openCreateCharacter}
                  className={`rounded-[1rem] border px-5 py-3 text-sm font-semibold transition ${isDark ? "border-white/10 bg-white/[0.05] text-white hover:bg-white/[0.08]" : "border-stone-200 bg-white text-stone-900 hover:bg-stone-50"}`}
                >
                  Add character
                </button>
              ) : null}
              <button
                type="button"
                onClick={() => setWorkspaceMode((current) => current === "duplicates" ? "profile" : "duplicates")}
                className="rounded-[1rem] bg-[linear-gradient(135deg,#8b5cf6,#6d28d9)] px-5 py-3 text-sm font-semibold text-white shadow-[0_15px_35px_rgba(109,40,217,0.22)] transition hover:translate-y-[-1px]"
              >
                {workspaceMode === "duplicates" ? "Back to bible" : "Review duplicates"}
              </button>
              <OverflowMenu isDark={isDark} open={pageMenuOpen} onToggle={() => setPageMenuOpen((current) => !current)} actions={pageMenuActions} />
            </div>
          </div>
        </div>

        {mergeError ? <p className="mt-3 text-sm text-amber-400">{mergeError}</p> : null}
        {error ? <p className="mt-3 text-sm text-rose-400">{error}</p> : null}

        {!error && (chars.length > 0 || creating) ? (
          <div className={`mt-5 overflow-hidden rounded-[1.9rem] border shadow-[0_24px_70px_rgba(0,0,0,0.18)] ${isDark ? "border-white/10 bg-[#090b10]" : "border-stone-200 bg-white/94"}`}>
            <div className="grid xl:h-[calc(100vh-13.25rem)] xl:grid-cols-[420px_minmax(0,1fr)_390px] 2xl:grid-cols-[430px_minmax(0,1fr)_400px]">
              <aside className={`border-b xl:min-h-0 xl:overflow-y-auto xl:border-b-0 xl:border-r ${isDark ? "border-white/8" : "border-stone-200"}`}>
                <div className={`sticky top-0 z-10 border-b px-4 py-4 backdrop-blur ${isDark ? "border-white/8 bg-[#090b10]/96" : "border-stone-200 bg-white/96"}`}>
                  <p className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>
                    {workspaceMode === "duplicates" ? "Duplicate review" : "Cast"}
                  </p>
                  <p className={`mt-1 text-sm ${isDark ? "text-slate-300" : "text-stone-600"}`}>
                    {workspaceMode === "duplicates"
                      ? `${filteredMergeSuggestions.length} suggestions${isManualMerge ? " · manual pair selected" : ""}`
                      : `${filteredChars.length} characters`}
                  </p>

                  <div className={`mt-4 flex items-center gap-3 rounded-[1rem] border px-3 py-3 ${isDark ? "border-white/10 bg-black/20" : "border-stone-200 bg-stone-50"}`}>
                    <svg className={`h-4 w-4 ${isDark ? "text-slate-500" : "text-stone-400"}`} viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
                      <path fillRule="evenodd" d="M8.5 3a5.5 5.5 0 1 0 3.473 9.765l3.63 3.631a.75.75 0 1 0 1.06-1.06l-3.63-3.63A5.5 5.5 0 0 0 8.5 3ZM4.5 8.5a4 4 0 1 1 8 0 4 4 0 0 1-8 0Z" clipRule="evenodd" />
                    </svg>
                    <input
                      value={search}
                      onChange={(event) => setSearch(event.target.value)}
                      placeholder={workspaceMode === "duplicates" ? "Search merge suggestions..." : "Search characters, aliases, traits..."}
                      className={`min-w-0 flex-1 bg-transparent text-sm outline-none ${isDark ? "text-slate-100 placeholder:text-slate-500" : "text-stone-900 placeholder:text-stone-400"}`}
                    />
                    <span className={`rounded-md border px-1.5 py-0.5 text-[10px] font-medium ${isDark ? "border-white/10 bg-white/[0.03] text-slate-500" : "border-stone-200 bg-white text-stone-400"}`}>
                      Ctrl K
                    </span>
                  </div>

                  {workspaceMode === "profile" ? (
                    <div className="mt-4 flex flex-wrap gap-2">
                      {([
                        ["all", "All"],
                        ["main", "Main"],
                        ["minor", "Minor"],
                        ["needs-review", "Needs review"],
                        ["duplicates", "Duplicates"],
                      ] as Array<[CastFilter, string]>).map(([value, label]) => (
                        <button
                          key={value}
                          type="button"
                          onClick={() => setCastFilter(value)}
                          className={`rounded-full border px-3 py-1.5 text-xs font-medium transition ${filterChipClasses(isDark, castFilter === value)}`}
                        >
                          {label}
                        </button>
                      ))}
                    </div>
                  ) : null}
                </div>

                {workspaceMode === "profile" ? (
                  <div className="px-3 py-2">
                    <p className={`px-3 pb-2 pt-1 text-xs ${isDark ? "text-slate-400" : "text-stone-500"}`}>{filteredChars.length} characters</p>
                    {visibleCastChars.map((char) => {
                      const isActive = selectedCharacter?.id === char.id
                      const flags = qualityFlags(char, mergeSuggestionIds, connectionsByCharacter.get(char.id) ?? [])
                      const health = healthByCharacter.get(char.id)
                      return (
                        <button
                          key={char.id}
                          type="button"
                          onClick={() => {
                            setSelectedId(char.id)
                            setCreating(false)
                            setEditing(false)
                            setWorkspaceMode("profile")
                          }}
                          className={`mb-1 w-full px-3 py-3 text-left transition ${isActive
                            ? isDark ? "rounded-[1rem] border border-violet-400/40 bg-violet-500/12 shadow-[inset_0_0_0_1px_rgba(167,139,250,0.16)]" : "rounded-[1rem] border border-violet-300 bg-violet-50"
                            : isDark ? "border-b border-white/8 hover:bg-white/[0.03]" : "border-b border-stone-200 hover:bg-stone-50/80"
                          }`}
                        >
                          <div className="flex items-start gap-3">
                            <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-[0.8rem] text-sm font-semibold ${isActive
                              ? isDark ? "bg-violet-500/20 text-violet-100" : "bg-violet-100 text-violet-700"
                              : isDark ? "bg-white/[0.06] text-slate-200" : "bg-stone-100 text-stone-700"
                            }`}>
                              {characterInitial(char.name)}
                            </div>
                            <div className="min-w-0 flex-1">
                              <div className="flex items-start justify-between gap-3">
                                <div className="min-w-0">
                                  <div className="flex items-center gap-2">
                                    <p className={`truncate text-[15px] font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{char.name}</p>
                                    {char.is_manual ? (
                                      <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.14em] ${isDark ? "bg-violet-500/15 text-violet-100" : "bg-violet-100 text-violet-700"}`}>
                                        Manual
                                      </span>
                                    ) : null}
                                  </div>
                                  <p className={`mt-1 text-xs ${isDark ? "text-slate-400" : "text-stone-500"}`}>{relationshipCounts.get(char.id) ?? 0} ties</p>
                                </div>
                                <div className="flex items-center gap-2">
                                  <span className={`text-xs font-semibold ${isDark ? "text-slate-300" : "text-stone-700"}`}>{health?.score ?? 0}%</span>
                                  <span
                                    className="inline-flex h-3.5 w-3.5 rounded-full border-2"
                                    style={{
                                      borderColor: health?.tone === "strong" ? "#22c55e" : health?.tone === "moderate" ? "#8b5cf6" : "#f59e0b",
                                      backgroundColor: "transparent",
                                    }}
                                  />
                                </div>
                              </div>
                              <p className={`mt-1 text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>
                                {flags.length > 0 ? flags.slice(0, 2).join(" / ") : `${formatRoleFilterLabel(char.role)} / ${formatChapterRange(char.first_chapter, char.last_seen_chapter ?? null)}`}
                              </p>
                            </div>
                          </div>
                        </button>
                      )
                    })}

                    {filteredChars.length === 0 ? (
                      <div className="px-3 py-6">
                        <p className={isDark ? "text-sm text-slate-400" : "text-sm text-stone-500"}>
                          {chars.length === 0 ? "No characters yet. Add one manually to start the bible." : "No characters match the current filters."}
                        </p>
                        {chars.length === 0 && isAuthorMode ? (
                          <button
                            type="button"
                            onClick={openCreateCharacter}
                            className="mt-3 rounded-[0.9rem] bg-[linear-gradient(135deg,#8b5cf6,#6d28d9)] px-4 py-2.5 text-sm font-semibold text-white"
                          >
                            Add character
                          </button>
                        ) : null}
                      </div>
                    ) : null}
                    {filteredChars.length > 8 ? (
                      <div className="px-3 py-4 text-center">
                        <button
                          type="button"
                          onClick={() => setShowAllCast((current) => !current)}
                          className={`text-sm font-medium ${isDark ? "text-slate-400 hover:text-white" : "text-stone-600 hover:text-stone-950"}`}
                        >
                          {showAllCast ? "Show less" : "Show more"}
                        </button>
                      </div>
                    ) : null}
                  </div>
                ) : (
                  <div className="px-3 py-2">
                    {filteredMergeSuggestions.map((suggestion) => {
                      const primary = chars.find((char) => char.id === suggestion.primaryId)
                      const secondary = chars.find((char) => char.id === suggestion.secondaryId)
                      const active = selectedMergeSuggestion?.key === suggestion.key
                      if (!primary || !secondary) return null
                      return (
                        <button
                          key={suggestion.key}
                          type="button"
                          onClick={() => setSelectedMergeKey(suggestion.key)}
                          className={`w-full rounded-[1rem] border px-3 py-3 text-left transition ${active
                            ? isDark ? "border-violet-400/40 bg-violet-500/12" : "border-violet-300 bg-violet-50"
                            : isDark ? "border-white/8 bg-white/[0.02] hover:bg-white/[0.04]" : "border-stone-200 bg-white hover:bg-stone-50"
                          }`}
                        >
                          <div className="flex items-start justify-between gap-3">
                            <div className="min-w-0">
                              <p className={`truncate text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{primary.name}</p>
                              <p className={`mt-1 truncate text-xs ${isDark ? "text-slate-400" : "text-stone-500"}`}>Possible duplicate: {secondary.name}</p>
                              <p className={`mt-2 text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>{suggestion.reasons[0]}</p>
                            </div>
                            <span className={`rounded-full px-2 py-1 text-xs font-semibold ${isDark ? "bg-amber-500/12 text-amber-200" : "bg-amber-50 text-amber-700"}`}>
                              {suggestion.confidence}%
                            </span>
                          </div>
                        </button>
                      )
                    })}

                    {filteredMergeSuggestions.length === 0 ? (
                      <div className="px-3 py-6">
                        <p className={isDark ? "text-sm text-slate-400" : "text-sm text-stone-500"}>No duplicate suggestions match the current search. Use the manual merge tools in the main panel to compare any two records directly.</p>
                      </div>
                    ) : null}

                    {filteredPendingCandidates.length > 0 ? (
                      <div className={`mt-5 border-t px-3 pt-4 ${isDark ? "border-white/8" : "border-stone-200"}`}>
                        <p className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Quarantine queue</p>
                        <p className={`mt-1 text-xs ${isDark ? "text-slate-400" : "text-stone-500"}`}>{filteredPendingCandidates.length} candidates waiting for review</p>
                        <div className="mt-3 space-y-3">
                          {filteredPendingCandidates.slice(0, 8).map((candidate) => (
                            <div key={candidate.id} className={`rounded-[1rem] border px-3 py-3 ${isDark ? "border-white/8 bg-white/[0.02]" : "border-stone-200 bg-white"}`}>
                              <p className={`truncate text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{candidate.proposed_name}</p>
                              <p className={`mt-1 text-xs ${isDark ? "text-slate-400" : "text-stone-500"}`}>Chapter {candidate.chapter_number} • {candidate.confidence}%</p>
                              <p className={`mt-2 text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>{candidate.reason_codes[0] ?? "Needs review"}</p>
                              <div className="mt-3 flex flex-wrap gap-2">
                                <button
                                  type="button"
                                  disabled={candidateActionId === candidate.id}
                                  onClick={() => void handlePromoteCandidate(candidate)}
                                  className={actionButtonClasses(isDark)}
                                >
                                  {candidateActionId === candidate.id ? "Working..." : "Promote"}
                                </button>
                                <button
                                  type="button"
                                  disabled={candidateActionId === candidate.id || !selectedCharacter}
                                  onClick={() => void handleAttachCandidate(candidate)}
                                  className={actionButtonClasses(isDark)}
                                >
                                  Attach to selected
                                </button>
                                <button
                                  type="button"
                                  disabled={candidateActionId === candidate.id}
                                  onClick={() => void handleRejectCandidate(candidate)}
                                  className={actionButtonClasses(isDark)}
                                >
                                  Reject
                                </button>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    ) : null}
                  </div>
                )}
              </aside>

              <section className={`border-b xl:min-h-0 xl:overflow-y-auto xl:border-b-0 xl:border-r ${isDark ? "border-white/8" : "border-stone-200"}`}>
                {workspaceMode === "profile" && creating ? (
                  <div className="p-5">
                    <div>
                      <p className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-violet-300" : "text-violet-600"}`}>Manual profile</p>
                      <h2 className={`mt-2 text-3xl font-semibold tracking-tight ${isDark ? "text-white" : "text-stone-950"}`}>New character</h2>
                      <p className={`mt-2 max-w-2xl text-sm leading-7 ${isDark ? "text-slate-400" : "text-stone-500"}`}>
                        Add a character LoreVia did not extract yet. This creates a real backend character record and makes it available across the Character Bible and other author tools.
                      </p>
                    </div>

                    <SurfaceCard title="Add character" isDark={isDark} className="mt-5">
                      <div className="grid gap-4 md:grid-cols-2">
                        <label className="space-y-1">
                          <span className={`text-[11px] font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Name</span>
                          <input value={createDraft.name} onChange={(event) => setCreateDraft((value) => ({ ...value, name: event.target.value }))} className={`w-full rounded-xl border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-black/20 text-white" : "border-stone-200 bg-white text-stone-900"}`} />
                        </label>
                        <label className="space-y-1">
                          <span className={`text-[11px] font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Role</span>
                          <select value={createDraft.role} onChange={(event) => setCreateDraft((value) => ({ ...value, role: event.target.value as CreateDraft["role"] }))} className={`w-full rounded-xl border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-black/20 text-white" : "border-stone-200 bg-white text-stone-900"}`}>
                            <option value="">Unclassified</option>
                            <option value="mc">Primary character</option>
                            <option value="sc">Supporting character</option>
                            <option value="background">Minor character</option>
                          </select>
                        </label>
                        <label className="space-y-1">
                          <span className={`text-[11px] font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>First chapter</span>
                          <input value={createDraft.firstChapter} onChange={(event) => setCreateDraft((value) => ({ ...value, firstChapter: event.target.value }))} inputMode="numeric" className={`w-full rounded-xl border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-black/20 text-white" : "border-stone-200 bg-white text-stone-900"}`} />
                        </label>
                        <label className="space-y-1">
                          <span className={`text-[11px] font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Aliases</span>
                          <input value={createDraft.aliases} onChange={(event) => setCreateDraft((value) => ({ ...value, aliases: event.target.value }))} className={`w-full rounded-xl border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-black/20 text-white" : "border-stone-200 bg-white text-stone-900"}`} />
                        </label>
                        <label className="space-y-1 md:col-span-2">
                          <span className={`text-[11px] font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Description</span>
                          <textarea value={createDraft.description} onChange={(event) => setCreateDraft((value) => ({ ...value, description: event.target.value }))} rows={4} className={`w-full rounded-xl border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-black/20 text-white" : "border-stone-200 bg-white text-stone-900"}`} />
                        </label>
                        <label className="space-y-1">
                          <span className={`text-[11px] font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Goal</span>
                          <input value={createDraft.goal} onChange={(event) => setCreateDraft((value) => ({ ...value, goal: event.target.value }))} className={`w-full rounded-xl border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-black/20 text-white" : "border-stone-200 bg-white text-stone-900"}`} />
                        </label>
                        <label className="space-y-1">
                          <span className={`text-[11px] font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Arc type</span>
                          <input value={createDraft.arcType} onChange={(event) => setCreateDraft((value) => ({ ...value, arcType: event.target.value }))} className={`w-full rounded-xl border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-black/20 text-white" : "border-stone-200 bg-white text-stone-900"}`} />
                        </label>
                        <label className="space-y-1 md:col-span-2">
                          <span className={`text-[11px] font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Lie they believe</span>
                          <textarea value={createDraft.lieTheyBelieve} onChange={(event) => setCreateDraft((value) => ({ ...value, lieTheyBelieve: event.target.value }))} rows={2} className={`w-full rounded-xl border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-black/20 text-white" : "border-stone-200 bg-white text-stone-900"}`} />
                        </label>
                        <label className="space-y-1 md:col-span-2">
                          <span className={`text-[11px] font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Wound / backstory</span>
                          <textarea value={createDraft.backstoryWound} onChange={(event) => setCreateDraft((value) => ({ ...value, backstoryWound: event.target.value }))} rows={3} className={`w-full rounded-xl border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-black/20 text-white" : "border-stone-200 bg-white text-stone-900"}`} />
                        </label>
                        <label className="space-y-1 md:col-span-2">
                          <span className={`text-[11px] font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Arc summary</span>
                          <textarea value={createDraft.arcSummary} onChange={(event) => setCreateDraft((value) => ({ ...value, arcSummary: event.target.value }))} rows={3} className={`w-full rounded-xl border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-black/20 text-white" : "border-stone-200 bg-white text-stone-900"}`} />
                        </label>
                        <label className="space-y-1">
                          <span className={`text-[11px] font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Personality tags</span>
                          <input value={createDraft.personalityTags} onChange={(event) => setCreateDraft((value) => ({ ...value, personalityTags: event.target.value }))} className={`w-full rounded-xl border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-black/20 text-white" : "border-stone-200 bg-white text-stone-900"}`} />
                        </label>
                        <label className="space-y-1">
                          <span className={`text-[11px] font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Motivations</span>
                          <input value={createDraft.motivations} onChange={(event) => setCreateDraft((value) => ({ ...value, motivations: event.target.value }))} className={`w-full rounded-xl border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-black/20 text-white" : "border-stone-200 bg-white text-stone-900"}`} />
                        </label>
                        <label className="space-y-1 md:col-span-2">
                          <span className={`text-[11px] font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Fears</span>
                          <input value={createDraft.fears} onChange={(event) => setCreateDraft((value) => ({ ...value, fears: event.target.value }))} className={`w-full rounded-xl border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-black/20 text-white" : "border-stone-200 bg-white text-stone-900"}`} />
                        </label>
                      </div>
                      {actionError ? <p className="mt-3 text-sm text-rose-400">{actionError}</p> : null}
                      <div className="mt-4 flex flex-wrap gap-2">
                        <button type="button" disabled={createBusy} onClick={() => void handleCreateCharacter()} className="rounded-full bg-[linear-gradient(135deg,#8b5cf6,#6d28d9)] px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-60">
                          {createBusy ? "Creating..." : "Create character"}
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            setCreating(false)
                            setCreateDraft(buildCreateDraft(progress?.current_chapter ?? 1))
                            setActionError(null)
                          }}
                          className={`rounded-full border px-4 py-2.5 text-sm font-medium ${isDark ? "border-white/10 text-slate-300 hover:bg-white/[0.05]" : "border-stone-200 text-stone-700 hover:bg-white"}`}
                        >
                          Cancel
                        </button>
                      </div>
                    </SurfaceCard>
                  </div>
                ) : null}

                {workspaceMode === "profile" && selectedCharacter && !creating ? (
                  <div className="p-5">
                    <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-3">
                          <h2 className={`text-[2.4rem] font-semibold tracking-tight ${isDark ? "text-white" : "text-stone-950"}`}>{selectedCharacter.name}</h2>
                          {selectedCharacter.is_manual ? (
                            <span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] ${isDark ? "bg-violet-500/15 text-violet-100" : "bg-violet-100 text-violet-700"}`}>
                              Manual profile
                            </span>
                          ) : null}
                        </div>
                        <p className={`mt-2 text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>
                          {formatRole(selectedCharacter.role)} / {formatStatus(selectedCharacter.status)} / {formatChapterRange(selectedCharacter.first_chapter, selectedCharacter.last_seen_chapter ?? null)} / {selectedCharacter.mention_count ?? 0} mentions / {selectedConnections.length} relationships
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
                        <button type="button" onClick={() => void handleShareCharacter()} className={actionButtonClasses(isDark)}>
                          <span className="mr-2 inline-flex h-4 w-4 items-center justify-center">
                            <svg className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
                              <path d="M15 8a3 3 0 1 0-2.83-4H12a3 3 0 0 0 .17 1L7.91 7.14a3 3 0 0 0-3.55.34A3 3 0 1 0 5 13.05l4.36 2.18a3 3 0 1 0 .64-1.28L5.63 11.8a3 3 0 0 0 0-1.6l4.37-2.16A3 3 0 0 0 15 8Z" />
                            </svg>
                          </span>
                          {shareState === "copied" ? "Link copied" : shareState === "error" ? "Share failed" : "Share"}
                        </button>
                        <OverflowMenu isDark={isDark} open={characterMenuOpen} onToggle={() => setCharacterMenuOpen((current) => !current)} actions={characterMenuActions} />
                      </div>
                    </div>

                    <div className={`mt-6 flex flex-wrap gap-8 border-b ${isDark ? "border-white/8" : "border-stone-200"}`}>
                      {([
                        ["overview", "Overview"],
                        ["relationships", "Relationships"],
                        ["arc", "Arc"],
                        ["evidence", "Evidence"],
                        ["continuity", "Continuity"],
                        ["notes", "Notes"],
                      ] as Array<[CharacterTab, string]>).map(([value, label]) => (
                        <button
                          key={value}
                          type="button"
                          onClick={() => setActiveTab(value)}
                          className={`pb-3 text-sm font-medium transition ${workspaceTabClasses(isDark, activeTab === value)}`}
                        >
                          {label}
                        </button>
                      ))}
                    </div>

                    {activeTab === "overview" ? (
                      <div className="mt-5 grid gap-4 xl:grid-cols-2">
                        <SurfaceCard title="Profile summary" isDark={isDark}>
                          <p className={`text-sm leading-7 ${isDark ? "text-slate-300" : "text-stone-600"}`}>
                            {selectedCharacterSummary || "LoreVia is still building a concise grounded profile from the manuscript."}
                          </p>
                          <div className={`mt-4 flex items-center justify-between rounded-xl border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-black/20 text-slate-300" : "border-stone-200 bg-white text-stone-600"}`}>
                            <span>Grounded in {selectedEvidence.length > 0 ? selectedEvidence.length : selectedGrowthEvents.length} passages</span>
                            <button type="button" onClick={openCharacterEvidence} className={`rounded-full px-3 py-1.5 text-xs font-semibold ${isDark ? "bg-white/[0.06] text-white" : "bg-stone-100 text-stone-800"}`}>
                              View evidence
                            </button>
                          </div>
                        </SurfaceCard>

                        <SurfaceCard title="Identity" isDark={isDark}>
                          <dl className="grid gap-4 text-sm">
                            <div className="grid grid-cols-[120px_minmax(0,1fr)] gap-3">
                              <dt className={isDark ? "text-slate-500" : "text-stone-500"}>Aliases</dt>
                              <dd className={isDark ? "text-white" : "text-stone-900"}>{selectedCharacter.aliases.length > 0 ? selectedCharacter.aliases.join(", ") : "None recorded"}</dd>
                            </div>
                            <div className="grid grid-cols-[120px_minmax(0,1fr)] gap-3">
                              <dt className={isDark ? "text-slate-500" : "text-stone-500"}>Role</dt>
                              <dd className={isDark ? "text-white" : "text-stone-900"}>{formatRole(selectedCharacter.role)}</dd>
                            </div>
                            <div className="grid grid-cols-[120px_minmax(0,1fr)] gap-3">
                              <dt className={isDark ? "text-slate-500" : "text-stone-500"}>First seen</dt>
                              <dd className={isDark ? "text-white" : "text-stone-900"}>Chapter {selectedCharacter.first_chapter}</dd>
                            </div>
                            <div className="grid grid-cols-[120px_minmax(0,1fr)] gap-3">
                              <dt className={isDark ? "text-slate-500" : "text-stone-500"}>Latest chapter</dt>
                              <dd className={isDark ? "text-white" : "text-stone-900"}>{selectedCharacter.last_seen_chapter ? `Chapter ${selectedCharacter.last_seen_chapter}` : `Chapter ${selectedCharacter.first_chapter}`}</dd>
                            </div>
                            <div className="grid grid-cols-[120px_minmax(0,1fr)] gap-3">
                              <dt className={isDark ? "text-slate-500" : "text-stone-500"}>Status</dt>
                              <dd className={isDark ? "text-white" : "text-stone-900"}>{formatStatus(selectedCharacter.status)}</dd>
                            </div>
                          </dl>
                        </SurfaceCard>

                        <SurfaceCard title="Graph visibility" isDark={isDark}>
                          <div className="space-y-3">
                            <div className={`rounded-xl border px-3 py-3 text-sm ${isDark ? "border-white/8 bg-black/20 text-slate-300" : "border-stone-200 bg-white text-stone-600"}`}>
                              <p className={`font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{graphVisibilityLabel(selectedCharacter.graph_visibility_override ?? null)}</p>
                              <p className="mt-1">
                                {selectedHiddenGraphRecord
                                  ? `${selectedCharacter.name} is currently hidden from the graph.`
                                  : `${selectedCharacter.name} is currently visible in the graph.`}
                              </p>
                              {selectedHiddenGraphRecord ? (
                                <p className={`mt-2 text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>
                                  Score {selectedHiddenGraphRecord.visibility_score}. {selectedHiddenGraphRecord.connected_relationship_count} relationship signals.
                                </p>
                              ) : null}
                            </div>
                            {selectedHiddenGraphRecord?.visibility_reasons?.length ? (
                              <div className="flex flex-wrap gap-2">
                                {selectedHiddenGraphRecord.visibility_reasons.map((reason) => (
                                  <span key={reason} className={`rounded-full px-3 py-1.5 text-xs ${isDark ? "bg-white/[0.05] text-slate-200" : "border border-stone-200 bg-white text-stone-700"}`}>
                                    {graphVisibilityReasonCopy(reason)}
                                  </span>
                                ))}
                              </div>
                            ) : null}
                            {isAuthorMode ? (
                              <div className="flex flex-wrap gap-2">
                                <button type="button" disabled={graphOverrideBusy} onClick={() => void handleGraphVisibilityOverride("include")} className="rounded-full bg-[linear-gradient(135deg,#0f766e,#0d9488)] px-4 py-2 text-xs font-semibold text-white disabled:opacity-60">
                                  Include in graph
                                </button>
                                <button type="button" disabled={graphOverrideBusy} onClick={() => void handleGraphVisibilityOverride("exclude")} className={`rounded-full px-4 py-2 text-xs font-semibold disabled:opacity-60 ${isDark ? "border border-white/10 text-slate-200 hover:bg-white/[0.05]" : "border border-stone-200 text-stone-700 hover:bg-white"}`}>
                                  Exclude from graph
                                </button>
                                <button type="button" disabled={graphOverrideBusy} onClick={() => void handleGraphVisibilityOverride(null)} className={`rounded-full px-4 py-2 text-xs font-semibold disabled:opacity-60 ${isDark ? "border border-white/10 text-slate-200 hover:bg-white/[0.05]" : "border border-stone-200 text-stone-700 hover:bg-white"}`}>
                                  Return to auto
                                </button>
                              </div>
                            ) : null}
                          </div>
                        </SurfaceCard>

                        <SurfaceCard title="Traits" isDark={isDark}>
                          <div className="flex flex-wrap gap-2">
                            {selectedCharacter.personality_tags.length > 0
                              ? selectedCharacter.personality_tags.map((tag) => (
                                  <span key={tag} className={`rounded-full px-3 py-1.5 text-xs ${isDark ? "bg-white/[0.05] text-slate-200" : "bg-white text-stone-700 border border-stone-200"}`}>
                                    {tag}
                                  </span>
                                ))
                              : visibleTraitEntries(selectedCharacter).map(([key, trait]) => trait ? (
                                  <span key={key} className={`rounded-full px-3 py-1.5 text-xs ${isDark ? "bg-white/[0.05] text-slate-200" : "bg-white text-stone-700 border border-stone-200"}`}>
                                    {trait.value}
                                  </span>
                                ) : null)}
                            {selectedCharacter.personality_tags.length === 0 && visibleTraitEntries(selectedCharacter).length === 0 ? (
                              <span className={isDark ? "text-sm text-slate-400" : "text-sm text-stone-500"}>No trait profile has been captured yet.</span>
                            ) : null}
                          </div>
                        </SurfaceCard>

                        <SurfaceCard title="Motivations" isDark={isDark}>
                          {selectedCharacter.motivations.length > 0 ? (
                            <ul className={`space-y-2 text-sm leading-7 ${isDark ? "text-slate-300" : "text-stone-600"}`}>
                              {selectedCharacter.motivations.map((motivation) => (
                                <li key={motivation} className="flex gap-3">
                                  <span className={`mt-2 h-1.5 w-1.5 rounded-full ${isDark ? "bg-violet-300" : "bg-violet-500"}`} />
                                  <span>{motivation}</span>
                                </li>
                              ))}
                            </ul>
                          ) : (
                            <p className={isDark ? "text-sm text-slate-400" : "text-sm text-stone-500"}>No grounded motivations are available yet.</p>
                          )}
                        </SurfaceCard>

                        <SurfaceCard title="Arc" isDark={isDark} className="xl:col-span-2">
                          <p className={`text-sm leading-7 ${isDark ? "text-slate-300" : "text-stone-600"}`}>
                            {selectedCharacter.arc_summary || "Illness, grief, and pressure points are still being inferred from the manuscript."}
                          </p>
                          {selectedHealth?.issues.find((issue) => issue.startsWith("Arc has no update")) ? (
                            <div className={`mt-4 flex items-center justify-between rounded-xl border px-3 py-3 ${isDark ? "border-amber-500/20 bg-amber-500/10 text-amber-200" : "border-amber-200 bg-amber-50 text-amber-700"}`}>
                              <span>{selectedHealth.issues.find((issue) => issue.startsWith("Arc has no update"))}</span>
                              <button type="button" onClick={() => setActiveTab("arc")} className={`rounded-full px-3 py-1.5 text-xs font-semibold ${isDark ? "bg-black/30 text-amber-100" : "bg-white text-amber-700"}`}>
                                Review arc
                              </button>
                            </div>
                          ) : null}
                        </SurfaceCard>

                        {isAuthorMode && editing ? (
                          <SurfaceCard title="Edit profile" isDark={isDark} className="xl:col-span-2">
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
                              <label className="space-y-1">
                                <span className={`text-[11px] font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Goal</span>
                                <input value={draft.goal} onChange={(event) => setDraft((value) => ({ ...value, goal: event.target.value }))} className={`w-full rounded-xl border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-black/20 text-white" : "border-stone-200 bg-white text-stone-900"}`} />
                              </label>
                              <label className="space-y-1">
                                <span className={`text-[11px] font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Arc type</span>
                                <input value={draft.arcType} onChange={(event) => setDraft((value) => ({ ...value, arcType: event.target.value }))} className={`w-full rounded-xl border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-black/20 text-white" : "border-stone-200 bg-white text-stone-900"}`} />
                              </label>
                              <label className="space-y-1 md:col-span-2">
                                <span className={`text-[11px] font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Lie they believe</span>
                                <textarea value={draft.lieTheyBelieve} onChange={(event) => setDraft((value) => ({ ...value, lieTheyBelieve: event.target.value }))} rows={2} className={`w-full rounded-xl border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-black/20 text-white" : "border-stone-200 bg-white text-stone-900"}`} />
                              </label>
                              <label className="space-y-1 md:col-span-2">
                                <span className={`text-[11px] font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Wound / backstory</span>
                                <textarea value={draft.backstoryWound} onChange={(event) => setDraft((value) => ({ ...value, backstoryWound: event.target.value }))} rows={3} className={`w-full rounded-xl border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-black/20 text-white" : "border-stone-200 bg-white text-stone-900"}`} />
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
                            {actionError ? <p className="mt-3 text-sm text-rose-400">{actionError}</p> : null}
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
                          </SurfaceCard>
                        ) : null}
                      </div>
                    ) : null}

                    {activeTab === "relationships" ? (
                      <div className="mt-5 space-y-5">
                        <RelationshipGraph
                          bookId={bookId}
                          upToChapter={relationshipChapter}
                          authorMode={isAuthorMode}
                          includeInactive={isAuthorMode}
                          theme={theme}
                          focusCharacterId={selectedCharacter.id}
                          onGraphDataChange={setGraphData}
                          onSelectCharacterId={(characterId) => {
                            if (characterId) {
                              setSelectedId(characterId)
                              setActiveTab("relationships")
                            }
                          }}
                        />

                        {isAuthorMode ? (
                          <div className="grid gap-4 xl:grid-cols-2">
                            <SurfaceCard title="Create relationship" isDark={isDark}>
                              <div className="grid gap-3 md:grid-cols-2">
                                <label className="space-y-1 md:col-span-2">
                                  <span className={`text-[11px] font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Counterpart</span>
                                  <select
                                    value={relationshipDraft.counterpartId}
                                    onChange={(event) => setRelationshipDraft((value) => ({ ...value, counterpartId: event.target.value }))}
                                    className={`w-full rounded-xl border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-black/20 text-white" : "border-stone-200 bg-white text-stone-900"}`}
                                  >
                                    <option value="">Choose a character</option>
                                    {relationshipCounterpartOptions.map((character) => (
                                      <option key={character.id} value={character.id}>{character.name}</option>
                                    ))}
                                  </select>
                                </label>
                                <label className="space-y-1">
                                  <span className={`text-[11px] font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Type</span>
                                  <select
                                    value={relationshipDraft.relType}
                                    onChange={(event) => setRelationshipDraft((value) => ({ ...value, relType: event.target.value as RelationshipComposerDraft["relType"] }))}
                                    className={`w-full rounded-xl border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-black/20 text-white" : "border-stone-200 bg-white text-stone-900"}`}
                                  >
                                    {RELATIONSHIP_TYPE_OPTIONS.map((type) => (
                                      <option key={type} value={type}>{formatRelationshipType(type)}</option>
                                    ))}
                                  </select>
                                </label>
                                <label className="space-y-1">
                                  <span className={`text-[11px] font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Sentiment</span>
                                  <input
                                    type="number"
                                    min={-1}
                                    max={1}
                                    step={0.1}
                                    value={relationshipDraft.sentiment}
                                    onChange={(event) => setRelationshipDraft((value) => ({ ...value, sentiment: event.target.value }))}
                                    className={`w-full rounded-xl border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-black/20 text-white" : "border-stone-200 bg-white text-stone-900"}`}
                                  />
                                </label>
                                <label className="space-y-1">
                                  <span className={`text-[11px] font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>From chapter</span>
                                  <input
                                    value={relationshipDraft.fromChapter}
                                    onChange={(event) => setRelationshipDraft((value) => ({ ...value, fromChapter: event.target.value }))}
                                    inputMode="numeric"
                                    className={`w-full rounded-xl border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-black/20 text-white" : "border-stone-200 bg-white text-stone-900"}`}
                                  />
                                </label>
                                <label className="space-y-1">
                                  <span className={`text-[11px] font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Ends chapter</span>
                                  <input
                                    value={relationshipDraft.toChapter}
                                    onChange={(event) => setRelationshipDraft((value) => ({ ...value, toChapter: event.target.value }))}
                                    inputMode="numeric"
                                    placeholder="Optional"
                                    className={`w-full rounded-xl border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-black/20 text-white" : "border-stone-200 bg-white text-stone-900"}`}
                                  />
                                </label>
                                <label className="space-y-1 md:col-span-2">
                                  <span className={`text-[11px] font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Relationship note</span>
                                  <textarea
                                    value={relationshipDraft.description}
                                    onChange={(event) => setRelationshipDraft((value) => ({ ...value, description: event.target.value }))}
                                    rows={3}
                                    className={`w-full rounded-xl border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-black/20 text-white" : "border-stone-200 bg-white text-stone-900"}`}
                                  />
                                </label>
                              </div>
                              <div className="mt-4 flex flex-wrap gap-2">
                                <button type="button" disabled={createRelationshipBusy} onClick={() => void handleCreateRelationship()} className="rounded-full bg-[linear-gradient(135deg,#8b5cf6,#6d28d9)] px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-60">
                                  {createRelationshipBusy ? "Saving..." : "Create relationship"}
                                </button>
                              </div>
                            </SurfaceCard>

                            <SurfaceCard title="Hidden from graph" isDark={isDark}>
                              {hiddenGraphNodes.length > 0 ? (
                                <div className="space-y-3">
                                  {hiddenGraphNodes.slice(0, 8).map((node) => (
                                    <div key={node.id} className={`rounded-xl border px-4 py-3 ${isDark ? "border-white/8 bg-black/20" : "border-stone-200 bg-white"}`}>
                                      <div className="flex items-start justify-between gap-3">
                                        <div>
                                          <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{node.name}</p>
                                          <p className={`mt-1 text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>Score {node.visibility_score} • {node.connected_relationship_count} relationship signals</p>
                                        </div>
                                        <button type="button" onClick={() => { setSelectedId(node.id); setActiveTab("overview") }} className={`rounded-full px-3 py-1.5 text-xs font-semibold ${isDark ? "bg-white/[0.06] text-white" : "bg-stone-100 text-stone-800"}`}>
                                          Review
                                        </button>
                                      </div>
                                      <div className="mt-3 flex flex-wrap gap-2">
                                        {node.visibility_reasons.map((reason) => (
                                          <span key={`${node.id}-${reason}`} className={`rounded-full px-3 py-1 text-[11px] ${isDark ? "bg-white/[0.05] text-slate-300" : "border border-stone-200 bg-stone-50 text-stone-600"}`}>
                                            {graphVisibilityReasonCopy(reason)}
                                          </span>
                                        ))}
                                      </div>
                                    </div>
                                  ))}
                                </div>
                              ) : (
                                <p className={isDark ? "text-sm text-slate-400" : "text-sm text-stone-500"}>No cast members are currently being filtered out of the graph.</p>
                              )}
                            </SurfaceCard>
                          </div>
                        ) : null}

                        <SurfaceCard title="Relationship table" isDark={isDark}>
                          {selectedConnections.length > 0 ? (
                            <div className="space-y-3">
                              {selectedConnections.map((edge, index) => (
                                <div key={`${edge.source}-${edge.target}-${edge.type}-${index}`} className={`grid gap-2 rounded-xl border px-3 py-3 md:grid-cols-[minmax(0,1fr)_120px_120px_90px] ${isDark ? "border-white/8 bg-black/20" : "border-stone-200 bg-white"}`}>
                                  <div className="min-w-0">
                                    <p className={`truncate text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{edge.counterpartName}</p>
                                    <p className={`mt-1 text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>{edge.description || "Relationship evidence is still being summarized."}</p>
                                  </div>
                                  <div className={`text-sm ${isDark ? "text-slate-300" : "text-stone-600"}`}>{formatRelationshipType(edge.type)}</div>
                                  <div className={`text-sm ${isDark ? "text-slate-300" : "text-stone-600"}`}>{sentimentLabel(edge.sentiment)}</div>
                                  <div className={`text-sm ${isDark ? "text-slate-300" : "text-stone-600"}`}>{typeof edge.from_chapter === "number" ? `Ch. ${edge.from_chapter}` : "No ch."}{edge.status === "ended" ? " • ended" : ""}</div>
                                </div>
                              ))}
                            </div>
                          ) : (
                            <p className={isDark ? "text-sm text-slate-400" : "text-sm text-stone-500"}>No relationship links are visible for this character yet.</p>
                          )}
                        </SurfaceCard>
                      </div>
                    ) : null}

                    {activeTab === "arc" ? (
                      <div className="mt-5 space-y-4">
                        <SurfaceCard title="Arc summary" isDark={isDark}>
                          <p className={`text-sm leading-7 ${isDark ? "text-slate-300" : "text-stone-600"}`}>
                            {selectedArcTracker?.summary || selectedCharacter.arc_summary || "Current role and progression are still being inferred from the manuscript."}
                          </p>
                        </SurfaceCard>

                        <div className="grid gap-4 xl:grid-cols-2">
                          <SurfaceCard title="Core arc profile" isDark={isDark}>
                            <dl className="grid gap-3 text-sm">
                              <div className="grid grid-cols-[132px_minmax(0,1fr)] gap-3">
                                <dt className={isDark ? "text-slate-500" : "text-stone-500"}>Goal</dt>
                                <dd className={isDark ? "text-white" : "text-stone-900"}>{selectedArcTracker?.goal || selectedCharacter.goal || "Not grounded yet"}</dd>
                              </div>
                              <div className="grid grid-cols-[132px_minmax(0,1fr)] gap-3">
                                <dt className={isDark ? "text-slate-500" : "text-stone-500"}>Motivation</dt>
                                <dd className={isDark ? "text-white" : "text-stone-900"}>{selectedArcTracker?.motivation || "Not grounded yet"}</dd>
                              </div>
                              <div className="grid grid-cols-[132px_minmax(0,1fr)] gap-3">
                                <dt className={isDark ? "text-slate-500" : "text-stone-500"}>Fear</dt>
                                <dd className={isDark ? "text-white" : "text-stone-900"}>{selectedArcTracker?.fear || "Not grounded yet"}</dd>
                              </div>
                              <div className="grid grid-cols-[132px_minmax(0,1fr)] gap-3">
                                <dt className={isDark ? "text-slate-500" : "text-stone-500"}>Lie</dt>
                                <dd className={isDark ? "text-white" : "text-stone-900"}>{selectedArcTracker?.lie_they_believe || selectedCharacter.lie_they_believe || "Not grounded yet"}</dd>
                              </div>
                              <div className="grid grid-cols-[132px_minmax(0,1fr)] gap-3">
                                <dt className={isDark ? "text-slate-500" : "text-stone-500"}>Wound</dt>
                                <dd className={isDark ? "text-white" : "text-stone-900"}>{selectedArcTracker?.wound_backstory || selectedCharacter.backstory_wound || "Not grounded yet"}</dd>
                              </div>
                              <div className="grid grid-cols-[132px_minmax(0,1fr)] gap-3">
                                <dt className={isDark ? "text-slate-500" : "text-stone-500"}>Arc type</dt>
                                <dd className={isDark ? "text-white" : "text-stone-900"}>{selectedArcTracker?.arc_type || selectedCharacter.arc_type || selectedCharacter.archetype || "Still inferring"}</dd>
                              </div>
                            </dl>
                          </SurfaceCard>

                          <SurfaceCard title="Voice markers" isDark={isDark}>
                            {(selectedArcTracker?.voice_markers?.length ?? 0) > 0 ? (
                              <div className="space-y-2">
                                {selectedArcTracker?.voice_markers?.map((marker) => (
                                  <div key={marker} className={`rounded-xl border px-3 py-2 text-sm ${isDark ? "border-white/8 bg-black/20 text-slate-200" : "border-stone-200 bg-white text-stone-700"}`}>
                                    {marker}
                                  </div>
                                ))}
                              </div>
                            ) : (
                              <p className={isDark ? "text-sm text-slate-400" : "text-sm text-stone-500"}>No voice markers are grounded yet.</p>
                            )}
                          </SurfaceCard>
                        </div>

                        <SurfaceCard title="Arc timeline" isDark={isDark}>
                          {(selectedArcTracker?.arc_timeline?.length ?? 0) > 0 ? (
                            <div className="space-y-3">
                              {selectedArcTracker?.arc_timeline?.map((line) => (
                                <div key={line} className={`rounded-xl border px-4 py-3 text-sm leading-6 ${isDark ? "border-white/8 bg-black/20 text-slate-200" : "border-stone-200 bg-white text-stone-700"}`}>
                                  {line}
                                </div>
                              ))}
                            </div>
                          ) : (
                            <p className={isDark ? "text-sm text-slate-400" : "text-sm text-stone-500"}>No chapter-by-chapter arc timeline has been captured yet.</p>
                          )}
                        </SurfaceCard>

                        <SurfaceCard title="Arc checkpoints" isDark={isDark}>
                          {(selectedArcTracker?.major_turning_points?.length ?? selectedGrowthEvents.length) > 0 ? (
                            <div className="space-y-3">
                              {(selectedArcTracker?.major_turning_points?.length ? selectedArcTracker.major_turning_points : selectedGrowthEvents).map((event, index) => (
                                <div key={`${selectedCharacter.id}-growth-${index}`} className={`rounded-xl border px-4 py-3 ${isDark ? "border-white/8 bg-black/20" : "border-stone-200 bg-white"}`}>
                                  <div className="flex flex-wrap items-center gap-2">
                                    {("chapter_number" in event ? event.chapter_number : growthChapter(event)) ? (
                                      <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.16em] ${isDark ? "bg-violet-500/15 text-violet-100" : "bg-violet-100 text-violet-700"}`}>
                                        Chapter {"chapter_number" in event ? event.chapter_number : growthChapter(event)}
                                      </span>
                                    ) : null}
                                    {event.is_major ? (
                                      <span className={`rounded-full px-2 py-0.5 text-[10px] ${isDark ? "bg-amber-500/12 text-amber-200" : "bg-amber-50 text-amber-700"}`}>
                                        major shift
                                      </span>
                                    ) : null}
                                  </div>
                                  <p className={`mt-2 text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{"title" in event ? event.title : growthTitle(event)}</p>
                                  {(event.description || ("impact" in event ? event.impact : null)) ? (
                                    <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-600"}`}>
                                      {event.description || ("impact" in event ? event.impact : null)}
                                    </p>
                                  ) : null}
                                </div>
                              ))}
                            </div>
                          ) : (
                            <p className={isDark ? "text-sm text-slate-400" : "text-sm text-stone-500"}>No explicit arc checkpoints have been captured yet.</p>
                          )}
                        </SurfaceCard>

                        <div className="grid gap-4 xl:grid-cols-2">
                          <SurfaceCard title="Relationship changes" isDark={isDark}>
                            {(selectedArcTracker?.relationship_changes?.length ?? 0) > 0 ? (
                              <div className="space-y-3">
                                {selectedArcTracker?.relationship_changes?.map((item, index) => (
                                  <div key={relationshipChangeKey(item, index)} className={`rounded-xl border px-4 py-3 ${isDark ? "border-white/8 bg-black/20" : "border-stone-200 bg-white"}`}>
                                    <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>Chapter {item.chapter_number}: {item.counterpart_name}</p>
                                    <p className={`mt-1 text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>{formatRelationshipType(item.type)} / {sentimentLabel(item.sentiment)}</p>
                                    {item.description ? <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-600"}`}>{item.description}</p> : null}
                                  </div>
                                ))}
                              </div>
                            ) : (
                              <p className={isDark ? "text-sm text-slate-400" : "text-sm text-stone-500"}>No explicit relationship shifts are tracked yet.</p>
                            )}
                          </SurfaceCard>

                          <SurfaceCard title="Physical description history" isDark={isDark}>
                            {(selectedArcTracker?.physical_description_history?.length ?? 0) > 0 ? (
                              <div className="space-y-3">
                                {selectedArcTracker?.physical_description_history?.map((item) => (
                                  <div key={`${item.chapter_number}-${item.trait}-${item.value}`} className={`rounded-xl border px-4 py-3 text-sm ${isDark ? "border-white/8 bg-black/20 text-slate-200" : "border-stone-200 bg-white text-stone-700"}`}>
                                    <span className={`text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>Chapter {item.chapter_number}</span>
                                    <p className={`mt-1 font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{item.label}</p>
                                    <p className="mt-1">{item.previous_value ? `${item.previous_value} -> ${item.value}` : item.value}</p>
                                  </div>
                                ))}
                              </div>
                            ) : (
                              <p className={isDark ? "text-sm text-slate-400" : "text-sm text-stone-500"}>No description history has been tracked yet.</p>
                            )}
                          </SurfaceCard>
                        </div>
                      </div>
                    ) : null}

                    {activeTab === "evidence" ? (
                      <div className="mt-5 space-y-4">
                        <SurfaceCard title="Passage evidence" isDark={isDark}>
                          {evidenceLoadingId === selectedCharacter.id ? (
                            <p className={isDark ? "text-sm text-slate-400" : "text-sm text-stone-500"}>Finding grounded passages...</p>
                          ) : null}
                          {selectedEvidence.length > 0 ? (
                            <div className="space-y-3">
                              {selectedEvidence.map((result, index) => (
                                <div key={`${selectedCharacter.id}-evidence-${index}`} className={`rounded-xl border px-4 py-3 ${isDark ? "border-white/8 bg-black/20" : "border-stone-200 bg-white"}`}>
                                  <div className="flex flex-wrap items-center gap-2">
                                    <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.16em] ${isDark ? "bg-violet-500/15 text-violet-100" : "bg-violet-100 text-violet-700"}`}>
                                      Chapter {result.chapter_num}
                                    </span>
                                    {result.chapter_title ? (
                                      <span className={`text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>{result.chapter_title}</span>
                                    ) : null}
                                  </div>
                                  <p className={`mt-2 text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{result.summary}</p>
                                  <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-600"}`}>{result.text}</p>
                                </div>
                              ))}
                            </div>
                          ) : evidenceLoadingId !== selectedCharacter.id ? (
                            <p className={isDark ? "text-sm text-slate-400" : "text-sm text-stone-500"}>No chapter-grounded evidence cards are available yet.</p>
                          ) : null}
                          {evidenceError ? <p className="mt-3 text-sm text-rose-400">{evidenceError}</p> : null}
                        </SurfaceCard>

                        <SurfaceCard title="Relationship evidence" isDark={isDark}>
                          {selectedConnections.length > 0 ? (
                            <div className="space-y-3">
                              {selectedConnections.map((edge, index) => (
                                <div key={`${selectedCharacter.id}-relationship-evidence-${index}`} className={`rounded-xl border px-4 py-3 ${isDark ? "border-white/8 bg-black/20" : "border-stone-200 bg-white"}`}>
                                  <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>
                                    {selectedCharacter.name} to {edge.counterpartName}
                                  </p>
                                  <p className={`mt-1 text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>
                                    {formatRelationshipType(edge.type)} / {sentimentLabel(edge.sentiment)}{typeof edge.from_chapter === "number" ? ` / Chapter ${edge.from_chapter}` : ""}
                                  </p>
                                  <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-600"}`}>
                                    {edge.description || "This relationship still needs a grounded description and chapter reference."}
                                  </p>
                                </div>
                              ))}
                            </div>
                          ) : (
                            <p className={isDark ? "text-sm text-slate-400" : "text-sm text-stone-500"}>No relationship evidence has been captured yet.</p>
                          )}
                        </SurfaceCard>
                      </div>
                    ) : null}

                    {activeTab === "continuity" ? (
                      <div className="mt-5 grid gap-4 xl:grid-cols-2">
                        <SurfaceCard title="Continuity traits" isDark={isDark}>
                          {visibleTraitEntries(selectedCharacter).length > 0 ? (
                            <div className="grid gap-3">
                              {visibleTraitEntries(selectedCharacter).map(([key, trait]) => trait ? (
                                <div key={key} className={`grid grid-cols-[120px_minmax(0,1fr)] gap-3 rounded-xl border px-3 py-3 ${isDark ? "border-white/8 bg-black/20" : "border-stone-200 bg-white"}`}>
                                  <span className={isDark ? "text-slate-500" : "text-stone-500"}>{key}</span>
                                  <span className={isDark ? "text-white" : "text-stone-900"}>{trait.value}</span>
                                </div>
                              ) : null)}
                            </div>
                          ) : (
                            <p className={isDark ? "text-sm text-slate-400" : "text-sm text-stone-500"}>No continuity traits are confirmed yet.</p>
                          )}
                        </SurfaceCard>

                        <SurfaceCard title="Continuity checklist" isDark={isDark}>
                          {(selectedHealth?.issues.length || selectedArcTracker?.diagnostics?.length) ? (
                            <div className="space-y-3">
                            {[...(selectedHealth?.issues ?? []), ...(selectedArcTracker?.diagnostics ?? [])].map((issue, index) => (
                              <div key={`${issue}-${index}`} className={`flex items-start justify-between gap-3 rounded-xl border px-3 py-3 ${isDark ? "border-white/8 bg-black/20 text-slate-200" : "border-stone-200 bg-white text-stone-700"}`}>
                                <span>{issue}</span>
                                <span className={isDark ? "text-slate-500" : "text-stone-400"}>{">"}</span>
                              </div>
                            ))}
                            </div>
                          ) : (
                            <p className={isDark ? "text-sm text-slate-400" : "text-sm text-stone-500"}>No hard continuity breaks are tracked yet, but this profile still benefits from a fresh pass on motive drift, scene-to-scene state, and relationship evidence.</p>
                          )}
                        </SurfaceCard>

                        <SurfaceCard title="Contradictions" isDark={isDark} className="xl:col-span-2">
                          {(selectedArcTracker?.contradictions?.length ?? 0) > 0 ? (
                            <div className="space-y-3">
                              {selectedArcTracker?.contradictions?.map((item, index) => (
                                <div key={`${item}-${index}`} className={`rounded-xl border px-4 py-3 text-sm leading-6 ${isDark ? "border-white/8 bg-black/20 text-slate-200" : "border-stone-200 bg-white text-stone-700"}`}>
                                  {item}
                                </div>
                              ))}
                            </div>
                          ) : (
                            <p className={isDark ? "text-sm text-slate-400" : "text-sm text-stone-500"}>No explicit contradiction is tracked yet, so the next useful check is pressure-testing this character&apos;s role labels, family aliases, and late-chapter motivation shifts.</p>
                          )}
                        </SurfaceCard>
                      </div>
                    ) : null}

                    {activeTab === "notes" ? (
                      <div className="mt-5 space-y-4">
                        <div className="flex flex-wrap items-center gap-2">
                          <button
                            type="button"
                            onClick={() => void saveCharacterWorkspaceNote()}
                            className={`rounded-full px-4 py-2 text-sm font-semibold ${isDark ? "bg-white text-slate-950" : "bg-stone-900 text-white"}`}
                          >
                            Save character note
                          </button>
                          <Link
                            href={`/${bookId}/notes`}
                            className={`rounded-full px-4 py-2 text-sm font-medium ${isDark ? "bg-white/8 text-slate-200" : "bg-stone-100 text-stone-700"}`}
                          >
                            Open notes workspace
                          </Link>
                          {noteToast ? <span className={`text-sm ${isDark ? "text-emerald-300" : "text-emerald-700"}`}>{noteToast}</span> : null}
                        </div>

                        <SurfaceCard title="Related notes" isDark={isDark}>
                          {(selectedCharacter.relationship_summaries?.length ?? 0) > 0 ? (
                            <div className="space-y-3">
                              {selectedCharacter.relationship_summaries?.map((summary, index) => (
                                <div key={`${selectedCharacter.id}-note-${index}`} className={`rounded-xl border px-4 py-3 text-sm leading-6 ${isDark ? "border-white/8 bg-black/20 text-slate-300" : "border-stone-200 bg-white text-stone-600"}`}>
                                  {summary}
                                </div>
                              ))}
                            </div>
                          ) : (
                            <p className={isDark ? "text-sm text-slate-400" : "text-sm text-stone-500"}>No linked notes yet. Use the Notes workspace to connect scene or research notes to this character.</p>
                          )}
                        </SurfaceCard>
                      </div>
                    ) : null}

                    {actionError && !editing ? <p className="mt-4 text-sm text-rose-400">{actionError}</p> : null}
                  </div>
                ) : null}

                {workspaceMode === "profile" && !selectedCharacter && !creating ? (
                  <div className="p-5">
                    <p className={isDark ? "text-sm text-slate-400" : "text-sm text-stone-500"}>
                      {chars.length === 0 ? "No character profiles are ready yet." : "No characters match the current filters."}
                    </p>
                    {chars.length === 0 && isAuthorMode ? (
                      <button
                        type="button"
                        onClick={openCreateCharacter}
                        className="mt-4 rounded-[1rem] bg-[linear-gradient(135deg,#8b5cf6,#6d28d9)] px-5 py-3 text-sm font-semibold text-white shadow-[0_15px_35px_rgba(109,40,217,0.22)] transition hover:translate-y-[-1px]"
                      >
                        Add character
                      </button>
                    ) : null}
                  </div>
                ) : null}

                {workspaceMode === "duplicates" ? (
                  <div className="p-5">
                    {selectedMergePrimary && selectedMergeSecondary ? (
                      <div className="space-y-5">
                        <div>
                          <p className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-violet-300" : "text-violet-600"}`}>Duplicate review</p>
                          <h2 className={`mt-2 text-3xl font-semibold tracking-tight ${isDark ? "text-white" : "text-stone-950"}`}>{isManualMerge ? "Manual merge" : "Merge suggestion"}</h2>
                          <p className={`mt-2 text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>
                            Compare evidence before merging duplicate character records.
                          </p>
                        </div>

                        <SurfaceCard title="Manual pair" isDark={isDark}>
                          <div className="grid gap-3 xl:grid-cols-2">
                            <label className="text-sm">
                              <span className={`text-[11px] font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Primary record</span>
                              <select
                                value={selectedMergePrimary.id}
                                onChange={(event) => {
                                  const nextPrimaryId = event.target.value
                                  setManualMergePrimaryId(nextPrimaryId)
                                  if (nextPrimaryId === selectedMergeSecondary.id) {
                                    const fallbackSecondary = mergeableCharacters.find((char) => char.id !== nextPrimaryId)?.id ?? ""
                                    setManualMergeSecondaryId(fallbackSecondary)
                                  }
                                }}
                                className={`mt-2 w-full rounded-[0.9rem] border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-[#0b1220] text-slate-100" : "border-stone-200 bg-white text-stone-900"}`}
                              >
                                {mergeableCharacters.map((character) => (
                                  <option key={`manual-primary-${character.id}`} value={character.id}>{character.name}</option>
                                ))}
                              </select>
                            </label>
                            <label className="text-sm">
                              <span className={`text-[11px] font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Merge into primary</span>
                              <select
                                value={selectedMergeSecondary.id}
                                onChange={(event) => setManualMergeSecondaryId(event.target.value)}
                                className={`mt-2 w-full rounded-[0.9rem] border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-[#0b1220] text-slate-100" : "border-stone-200 bg-white text-stone-900"}`}
                              >
                                {mergeableCharacters.filter((character) => character.id !== selectedMergePrimary.id).map((character) => (
                                  <option key={`manual-secondary-${character.id}`} value={character.id}>{character.name}</option>
                                ))}
                              </select>
                            </label>
                          </div>
                          <div className="mt-3 flex flex-wrap gap-2">
                            <button type="button" onClick={() => openManualMerge(selectedMergePrimary.id, selectedMergeSecondary.id)} className={actionButtonClasses(isDark)}>
                              Use manual pair
                            </button>
                            <button
                              type="button"
                              onClick={() => {
                                setManualMergePrimaryId("")
                                setManualMergeSecondaryId("")
                              }}
                              className={actionButtonClasses(isDark)}
                            >
                              Return to suggestions
                            </button>
                          </div>
                        </SurfaceCard>

                        <div className="grid gap-4 xl:grid-cols-2">
                          {[selectedMergePrimary, selectedMergeSecondary].map((character, index) => {
                            const evidence = index === 0 ? selectedMergePrimaryEvidence : selectedMergeSecondaryEvidence
                            const connections = connectionsByCharacter.get(character.id) ?? []
                            const flags = qualityFlags(character, mergeSuggestionIds, connections)
                            return (
                              <SurfaceCard
                                key={character.id}
                                title={index === 0 ? "Primary" : "Candidate"}
                                isDark={isDark}
                              >
                                <div className="flex items-start gap-3">
                                  <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl text-sm font-semibold ${isDark ? "bg-violet-500/18 text-violet-100" : "bg-violet-100 text-violet-700"}`}>
                                    {characterInitial(character.name)}
                                  </div>
                                  <div className="min-w-0">
                                    <h3 className={`text-xl font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{character.name}</h3>
                                    <p className={`mt-1 text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>
                                      {formatRole(character.role)} / {formatStatus(character.status)} / {formatChapterRange(character.first_chapter, character.last_seen_chapter ?? null)}
                                    </p>
                                  </div>
                                </div>

                                {flags.length > 0 ? (
                                  <div className="mt-3 flex flex-wrap gap-2">
                                    {flags.map((flag) => (
                                      <span key={flag} className={`rounded-full px-2.5 py-1 text-xs font-medium ${flagClasses(isDark, flag)}`}>
                                        {flag}
                                      </span>
                                    ))}
                                  </div>
                                ) : null}

                                <p className={`mt-4 text-sm leading-7 ${isDark ? "text-slate-300" : "text-stone-600"}`}>
                                  {character.description || "No concise profile summary is stored yet."}
                                </p>

                                <div className="mt-4">
                                  <p className={`text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Aliases</p>
                                  <p className={`mt-2 text-sm ${isDark ? "text-slate-300" : "text-stone-600"}`}>{character.aliases.length > 0 ? character.aliases.join(", ") : "No aliases recorded"}</p>
                                </div>

                                <div className="mt-4">
                                  <p className={`text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Traits</p>
                                  <div className="mt-2 flex flex-wrap gap-2">
                                    {character.personality_tags.length > 0 ? character.personality_tags.slice(0, 6).map((tag) => (
                                      <span key={tag} className={`rounded-full px-3 py-1.5 text-xs ${isDark ? "bg-white/[0.05] text-slate-200" : "bg-white text-stone-700 border border-stone-200"}`}>
                                        {tag}
                                      </span>
                                    )) : <span className={isDark ? "text-sm text-slate-400" : "text-sm text-stone-500"}>No trait tags yet.</span>}
                                  </div>
                                </div>

                                <div className="mt-4">
                                  <p className={`text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Evidence</p>
                                  <div className="mt-2 space-y-2">
                                    {evidence.slice(0, 2).map((result, evidenceIndex) => (
                                      <div key={`${character.id}-evidence-compare-${evidenceIndex}`} className={`rounded-xl border px-3 py-3 ${isDark ? "border-white/8 bg-black/20" : "border-stone-200 bg-white"}`}>
                                        <p className={`text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>Chapter {result.chapter_num}</p>
                                        <p className={`mt-1 text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{result.summary}</p>
                                      </div>
                                    ))}
                                    {evidence.length === 0 ? (
                                      <p className={isDark ? "text-sm text-slate-400" : "text-sm text-stone-500"}>No evidence preview loaded yet.</p>
                                    ) : null}
                                  </div>
                                </div>
                              </SurfaceCard>
                            )
                          })}
                        </div>

                        <SurfaceCard title="Differences" isDark={isDark}>
                          <div className="grid gap-3 md:grid-cols-2">
                            <div className={`rounded-xl border px-4 py-3 ${isDark ? "border-white/8 bg-black/20" : "border-stone-200 bg-white"}`}>
                              <p className={`text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Primary record</p>
                              <p className={`mt-2 text-sm ${isDark ? "text-slate-300" : "text-stone-600"}`}>{selectedMergePrimary.name} / {selectedMergePrimary.mention_count ?? 0} mentions / {relationshipCounts.get(selectedMergePrimary.id) ?? 0} ties</p>
                            </div>
                            <div className={`rounded-xl border px-4 py-3 ${isDark ? "border-white/8 bg-black/20" : "border-stone-200 bg-white"}`}>
                              <p className={`text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Candidate record</p>
                              <p className={`mt-2 text-sm ${isDark ? "text-slate-300" : "text-stone-600"}`}>{selectedMergeSecondary.name} / {selectedMergeSecondary.mention_count ?? 0} mentions / {relationshipCounts.get(selectedMergeSecondary.id) ?? 0} ties</p>
                            </div>
                          </div>

                          <div className="mt-4 flex flex-wrap gap-2">
                            <button
                              type="button"
                              onClick={() => {
                                setWorkspaceMode("profile")
                                setSelectedId(selectedMergePrimary.id)
                                setActiveTab("evidence")
                                setSidebarTab("evidence")
                              }}
                              className={actionButtonClasses(isDark)}
                            >
                              Compare evidence
                            </button>
                            <button
                              type="button"
                              onClick={() => void handleMergeCharacters(selectedMergePrimary.id, selectedMergeSecondary.id, selectedMergeSuggestion?.suggestionId)}
                              disabled={mergeBusy}
                              className="rounded-[1rem] bg-[linear-gradient(135deg,#8b5cf6,#6d28d9)] px-5 py-3 text-sm font-semibold text-white shadow-[0_15px_35px_rgba(109,40,217,0.22)] transition hover:translate-y-[-1px] disabled:opacity-60"
                            >
                              {mergeBusy ? "Merging..." : "Merge"}
                            </button>
                            {selectedMergeSuggestion && !isManualMerge ? (
                              <>
                                <button
                                  type="button"
                                  onClick={() => void dismissDuplicateSuggestion(selectedMergeSuggestion)}
                                  className={actionButtonClasses(isDark)}
                                >
                                  Keep separate
                                </button>
                                <button
                                  type="button"
                                  onClick={() => void dismissDuplicateSuggestion(selectedMergeSuggestion)}
                                  className={actionButtonClasses(isDark)}
                                >
                                  Dismiss
                                </button>
                              </>
                            ) : null}
                          </div>
                        </SurfaceCard>
                      </div>
                    ) : (
                      <div className="space-y-4">
                        <p className={isDark ? "text-sm text-slate-400" : "text-sm text-stone-500"}>No duplicate suggestion is selected right now. Start with a manual pair and compare any two character records directly.</p>
                        {chars.length >= 2 ? (
                          <button
                            type="button"
                            onClick={() => openManualMerge()}
                            className="rounded-[1rem] bg-[linear-gradient(135deg,#8b5cf6,#6d28d9)] px-5 py-3 text-sm font-semibold text-white shadow-[0_15px_35px_rgba(109,40,217,0.22)] transition hover:translate-y-[-1px]"
                          >
                            Start manual merge
                          </button>
                        ) : null}
                      </div>
                    )}
                  </div>
                ) : null}
              </section>

              <aside className="xl:min-h-0 xl:overflow-y-auto">
                {workspaceMode === "profile" && creating ? (
                  <div className="p-4">
                    <div className="space-y-4">
                      <section className={`rounded-[1.2rem] border p-4 ${isDark ? "border-white/10 bg-[#10141d]/88" : "border-stone-200 bg-stone-50/75"}`}>
                        <p className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Manual add</p>
                        <p className={`mt-3 text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-600"}`}>
                          Use this for characters LoreVia missed, off-page characters you still want tracked, or deliberate naming choices you do not want to wait for extraction to infer.
                        </p>
                      </section>

                      <section className={`rounded-[1.2rem] border p-4 ${isDark ? "border-white/10 bg-[#10141d]/88" : "border-stone-200 bg-stone-50/75"}`}>
                        <p className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Tips</p>
                        <div className="mt-4 space-y-3 text-sm leading-6">
                          <p className={isDark ? "text-slate-300" : "text-stone-600"}>Add a short description if you want the new profile to read well immediately.</p>
                          <p className={isDark ? "text-slate-300" : "text-stone-600"}>Set the first chapter to where this character truly enters the story so timeline tools stay grounded.</p>
                          <p className={isDark ? "text-slate-300" : "text-stone-600"}>Aliases help duplicate review later if the manuscript uses family-role labels or nicknames.</p>
                        </div>
                      </section>
                    </div>
                  </div>
                ) : null}

                {workspaceMode === "profile" && selectedCharacter && selectedHealth ? (
                  <div className="p-4">
                    <div className="flex gap-6 border-b px-1 pb-3">
                      {([
                        ["insights", "Insights"],
                        ["evidence", "Evidence"],
                        ["ask", "Ask Character"],
                      ] as Array<[SidebarTab, string]>).map(([value, label]) => (
                        <button
                          key={value}
                          type="button"
                          onClick={() => {
                            setSidebarTab(value)
                            if (value === "evidence") openCharacterEvidence()
                          }}
                          className={`pb-2 text-sm font-medium transition ${sidebarTabClasses(isDark, sidebarTab === value)}`}
                        >
                          {label}
                        </button>
                      ))}
                    </div>

                    {sidebarTab === "insights" ? (
                      <div className="mt-4 space-y-4">
                        <section className={`rounded-[1.2rem] border p-4 ${isDark ? "border-white/10 bg-[#10141d]/88" : "border-stone-200 bg-stone-50/75"}`}>
                          <p className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Character health</p>
                          <div className="mt-4 flex items-center gap-4">
                            <HealthRing score={selectedHealth.score} tone={selectedHealth.tone} isDark={isDark} />
                            <div>
                              <p className={`text-lg font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>
                                {selectedHealth.tone === "strong" ? "Strong" : selectedHealth.tone === "moderate" ? "Moderate" : "Needs attention"}
                              </p>
                              <p className={`mt-1 text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-600"}`}>{selectedHealth.summary}</p>
                            </div>
                          </div>

                          <div className="mt-4 space-y-2">
                            {selectedHealth.issues.map((issue, index) => (
                              <div key={`${issue}-${index}`} className={`flex items-center justify-between rounded-xl border px-3 py-2.5 ${isDark ? "border-white/8 bg-black/20 text-slate-200" : "border-stone-200 bg-white text-stone-700"}`}>
                                <span className="text-sm">{issue}</span>
                                <span className={isDark ? "text-slate-500" : "text-stone-400"}>{">"}</span>
                              </div>
                            ))}
                          </div>
                        </section>

                        <section className={`rounded-[1.2rem] border p-4 ${isDark ? "border-white/10 bg-[#10141d]/88" : "border-stone-200 bg-stone-50/75"}`}>
                          <p className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Quick actions</p>
                          <div className="mt-4 grid gap-3 sm:grid-cols-2">
                            <QuickActionTile isDark={isDark} title="Find evidence" description="Search scenes and grounded passages." onClick={openCharacterEvidence} />
                            <QuickActionTile isDark={isDark} title="Open relationships" description="View the full relationship graph." onClick={openRelationships} />
                            <QuickActionTile isDark={isDark} title="Review duplicates" description={mergeSuggestions.length > 0 ? `${mergeSuggestions.length} suggestions ready for review.` : "No suggestion yet? Start a manual merge for this character."} onClick={() => openDuplicateReview(selectedCharacter.id)} />
                            <QuickActionTile isDark={isDark} title="Manual merge" description="Choose another record and merge it yourself." onClick={() => openManualMerge(selectedCharacter.id)} />
                            <QuickActionTile isDark={isDark} title={partitioning ? "Splitting..." : "Split card"} description="Break one merged record into separate character cards and keep the new profiles." onClick={() => void handlePartitionCharacter()} />
                            <QuickActionTile isDark={isDark} title="Ask as character" description="Simulate a grounded reply in voice." onClick={openCharacterChat} />
                          </div>
                        </section>

                        <section className={`rounded-[1.2rem] border p-4 ${isDark ? "border-white/10 bg-[#10141d]/88" : "border-stone-200 bg-stone-50/75"}`}>
                          <div className="flex items-center justify-between gap-3">
                            <div>
                              <p className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Relationship summary</p>
                              <p className={`mt-1 text-sm ${isDark ? "text-slate-300" : "text-stone-600"}`}>{selectedConnections.length} relationships</p>
                            </div>
                          </div>

                          <div className="mt-4 space-y-3">
                            {selectedConnections.slice(0, 4).map((edge, index) => (
                              <div key={`${selectedCharacter.id}-summary-edge-${index}`} className="grid grid-cols-[36px_minmax(0,1fr)_88px] items-center gap-3">
                                <div className={`flex h-9 w-9 items-center justify-center rounded-xl text-xs font-semibold ${isDark ? "bg-violet-500/16 text-violet-100" : "bg-violet-100 text-violet-700"}`}>
                                  {characterInitial(edge.counterpartName)}
                                </div>
                                <div className="min-w-0">
                                  <p className={`truncate text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{edge.counterpartName}</p>
                                  <p className={`mt-1 text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>
                                    {formatRelationshipType(edge.type)} / {sentimentLabel(edge.sentiment)}
                                  </p>
                                </div>
                                <div className="space-y-1">
                                  <div className={`h-1.5 rounded-full ${isDark ? "bg-white/8" : "bg-stone-200"}`}>
                                    <div className="h-1.5 rounded-full" style={{ width: `${strengthValue(edge.sentiment)}%`, backgroundColor: typeof edge.sentiment === "number" && edge.sentiment >= 0.2 ? "#75d565" : typeof edge.sentiment === "number" && edge.sentiment <= -0.2 ? "#e0a63f" : "#7b8496" }} />
                                  </div>
                                  <p className={`text-right text-[11px] ${isDark ? "text-slate-400" : "text-stone-500"}`}>
                                    {strengthValue(edge.sentiment) >= 70 ? "Strong" : strengthValue(edge.sentiment) >= 45 ? "Moderate" : "Low"}
                                  </p>
                                </div>
                              </div>
                            ))}

                            {selectedConnections.length > 4 ? (
                              <button type="button" onClick={openRelationships} className={`text-sm font-medium ${isDark ? "text-slate-300 hover:text-white" : "text-stone-700 hover:text-stone-950"}`}>
                                +{selectedConnections.length - 4} more relationships
                              </button>
                            ) : null}
                          </div>
                        </section>

                        <section className={`rounded-[1.2rem] border p-4 ${isDark ? "border-white/10 bg-[#10141d]/88" : "border-stone-200 bg-stone-50/75"}`}>
                          <p className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Related notes</p>
                          <p className={`mt-3 text-sm ${isDark ? "text-slate-300" : "text-stone-600"}`}>
                            {(selectedCharacter.relationship_summaries?.length ?? 0) > 0
                              ? `${selectedCharacter.relationship_summaries?.length ?? 0} notes linked`
                              : "No linked notes yet"}
                          </p>
                        </section>
                      </div>
                    ) : null}

                    {sidebarTab === "evidence" ? (
                      <div className="mt-4 space-y-4">
                        <section className={`rounded-[1.2rem] border p-4 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-stone-200 bg-stone-50/75"}`}>
                          <div className="flex items-center justify-between gap-3">
                            <div>
                              <p className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Evidence</p>
                              <p className={`mt-1 text-sm ${isDark ? "text-slate-300" : "text-stone-600"}`}>{selectedCharacter.name}</p>
                            </div>
                            <button type="button" onClick={() => void loadCharacterEvidence(selectedCharacter, true)} className={actionButtonClasses(isDark)}>
                              Refresh
                            </button>
                          </div>

                          <div className="mt-4 space-y-3">
                            {evidenceLoadingId === selectedCharacter.id ? (
                              <p className={isDark ? "text-sm text-slate-400" : "text-sm text-stone-500"}>Searching passages...</p>
                            ) : null}
                            {selectedEvidence.slice(0, 5).map((result, index) => (
                              <div key={`${selectedCharacter.id}-sidebar-evidence-${index}`} className={`rounded-xl border px-3 py-3 ${isDark ? "border-white/8 bg-black/20" : "border-stone-200 bg-white"}`}>
                                <p className={`text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>Chapter {result.chapter_num}</p>
                                <p className={`mt-1 text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{result.summary}</p>
                                <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-600"}`}>{result.text}</p>
                              </div>
                            ))}
                            {selectedEvidence.length === 0 && evidenceLoadingId !== selectedCharacter.id ? (
                              <p className={isDark ? "text-sm text-slate-400" : "text-sm text-stone-500"}>No evidence cards are loaded yet.</p>
                            ) : null}
                            {evidenceError ? <p className="text-sm text-rose-400">{evidenceError}</p> : null}
                          </div>
                        </section>
                      </div>
                    ) : null}

                    {sidebarTab === "ask" ? (
                      <div className="mt-4 space-y-4">
                        <section className={`rounded-[1.2rem] border p-4 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-stone-200 bg-stone-50/75"}`}>
                          <p className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-violet-300" : "text-violet-700"}`}>Ask Character</p>
                          <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-400" : "text-stone-500"}`}>
                            Replies use extracted personality, motivations, fears, relationships, and growth evidence up to chapter {relationshipChapter}.
                          </p>

                          <div className={`mt-4 max-h-[340px] space-y-2 overflow-y-auto rounded-[1rem] border p-3 ${isDark ? "border-white/10 bg-black/20" : "border-stone-200 bg-white"}`}>
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
                        </section>
                      </div>
                    ) : null}
                  </div>
                ) : null}

                {workspaceMode === "duplicates" ? (
                  <div className="p-4">
                    {selectedMergePrimary && selectedMergeSecondary ? (
                      <div className="space-y-4">
                        <section className={`rounded-[1.2rem] border p-4 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-stone-200 bg-stone-50/75"}`}>
                          <p className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>{isManualMerge ? "Manual merge" : "Merge suggestion"}</p>
                          <p className={`mt-3 text-2xl font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{selectedMergeSuggestion && !isManualMerge ? `${selectedMergeSuggestion.confidence}%` : "Manual review"}</p>
                          <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-600"}`}>{selectedMergeSuggestion && !isManualMerge ? "Confidence based on name overlap, alias collisions, and shared chapter context." : "Use this when a family-role alias or late rename was missed by automatic duplicate suggestions."}</p>
                          {selectedMergeSuggestion && !isManualMerge ? (
                            <div className="mt-4 space-y-2">
                              {selectedMergeSuggestion.reasons.map((reason) => (
                                <div key={reason} className={`rounded-xl border px-3 py-2.5 text-sm ${isDark ? "border-white/8 bg-black/20 text-slate-200" : "border-stone-200 bg-white text-stone-700"}`}>
                                  {reason}
                                </div>
                              ))}
                            </div>
                          ) : null}
                        </section>

                        <section className={`rounded-[1.2rem] border p-4 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-stone-200 bg-stone-50/75"}`}>
                          <p className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Quick actions</p>
                          <div className="mt-4 space-y-3">
                            <QuickActionTile
                              isDark={isDark}
                              title="Compare evidence"
                              description={`Open ${selectedMergePrimary.name}'s evidence tab.`}
                              onClick={() => {
                                setWorkspaceMode("profile")
                                setSelectedId(selectedMergePrimary.id)
                                setActiveTab("evidence")
                                setSidebarTab("evidence")
                              }}
                            />
                            <QuickActionTile
                              isDark={isDark}
                              title={mergeBusy ? "Merging..." : "Merge records"}
                              description={`${selectedMergeSecondary.name} will merge into ${selectedMergePrimary.name}.`}
                              onClick={() => void handleMergeCharacters(selectedMergePrimary.id, selectedMergeSecondary.id, selectedMergeSuggestion?.suggestionId)}
                            />
                            <QuickActionTile
                              isDark={isDark}
                              title="Keep separate"
                              description="Dismiss this suggestion and leave both records untouched."
                              onClick={() => {
                                if (selectedMergeSuggestion && !isManualMerge) {
                                  void dismissDuplicateSuggestion(selectedMergeSuggestion)
                                  return
                                }
                                setManualMergePrimaryId("")
                                setManualMergeSecondaryId("")
                              }}
                            />
                          </div>
                        </section>
                      </div>
                    ) : (
                      <div className="space-y-4">
                        <p className={isDark ? "text-sm text-slate-400" : "text-sm text-stone-500"}>Choose a suggestion or start a manual merge to compare records the detector did not catch yet.</p>
                        {chars.length >= 2 ? (
                          <button
                            type="button"
                            onClick={() => openManualMerge()}
                            className="w-full rounded-[1rem] bg-[linear-gradient(135deg,#8b5cf6,#6d28d9)] px-5 py-3 text-sm font-semibold text-white shadow-[0_15px_35px_rgba(109,40,217,0.22)] transition hover:translate-y-[-1px]"
                          >
                            Begin manual merge
                          </button>
                        ) : null}
                      </div>
                    )}
                  </div>
                ) : null}
              </aside>
            </div>
          </div>
        ) : !error ? (
          <div className={`mt-5 rounded-[1.4rem] border p-6 text-sm ${isDark ? "border-white/10 bg-black/20 text-slate-300" : "border-stone-200 bg-white/85 text-stone-600"}`}>
            <p>No character profiles are ready yet. Processing continues in the background after upload.</p>
            {isAuthorMode ? (
              <button
                type="button"
                onClick={openCreateCharacter}
                className="mt-4 rounded-[1rem] bg-[linear-gradient(135deg,#8b5cf6,#6d28d9)] px-5 py-3 text-sm font-semibold text-white shadow-[0_15px_35px_rgba(109,40,217,0.22)] transition hover:translate-y-[-1px]"
              >
                Add character manually
              </button>
            ) : null}
          </div>
        ) : null}
      </div>
    </div>
  )
}

