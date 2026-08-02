import { CONFIDENCE_THRESHOLDS } from "@/lib/constants"
import type { CharacterHealth, ConnectedRelationship } from "@/components/reader/CharacterProfileRightRail"
import type { CharacterBibleStat } from "./charactersPage.components"
import type {
  Character,
  CharacterCandidate,
  CharacterRelationshipCandidate,
  CharacterReviewResponse,
  CharacterShadowRecord,
  RelationshipGraph as RelationshipGraphData,
} from "@/types/character"

export type EditDraft = {
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

export type CreateDraft = EditDraft & {
  role: "" | "mc" | "sc" | "background"
  firstChapter: string
}

export type RelationshipComposerType = "ally" | "enemy" | "family" | "mentor" | "neutral" | "political" | "romantic" | "rival"

export type RelationshipComposerDraft = {
  counterpartId: string
  relType: RelationshipComposerType
  sentiment: string
  description: string
  fromChapter: string
  toChapter: string
}

export type MergeSuggestion = {
  key: string
  suggestionId?: string
  primaryId: string
  secondaryId: string
  confidence: number
  reasons: string[]
  sharedClusterKeys: string[]
  sharedChapters: number[]
  embeddingSimilarity?: number | null
  primaryIsProtected: boolean
  secondaryIsProtected: boolean
  primaryIsCurated: boolean
  secondaryIsCurated: boolean
}

export const RELATIONSHIP_TYPE_OPTIONS: RelationshipComposerType[] = ["ally", "enemy", "family", "mentor", "neutral", "political", "romantic", "rival"]

export function relationshipChangeKey(
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

export function listToString(values: string[] | undefined) {
  return (values ?? []).join(", ")
}

export function stringToList(value: string) {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean)
}

export function parsePositiveInteger(value: string, fallback = 1) {
  const parsed = Number.parseInt(value.trim(), 10)
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback
}

export function parsePartitionTargets(value: string) {
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

export function normalizeText(value: string | null | undefined) {
  return (value ?? "").trim().toLowerCase()
}

export function slugify(value: string) {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
}

export function characterInitial(name: string) {
  return (name.trim()[0] || "?").toUpperCase()
}

export function formatPercent(value: number | null | undefined) {
  if (typeof value !== "number" || Number.isNaN(value)) return "Unknown"
  return `${Math.round(value * 100)}%`
}

export function buildCharacterEvidenceQuery(character: Character) {
  const terms = Array.from(new Set([character.name, ...(character.aliases ?? [])].map((value) => value.trim()).filter(Boolean)))
  return terms.slice(0, 4).join(" ")
}

export function buildCandidateEvidenceQuery(candidate: CharacterCandidate) {
  const terms = Array.from(new Set([
    candidate.proposed_name,
    candidate.raw_name,
    ...(candidate.aliases ?? []),
    ...(candidate.cluster_names ?? []),
  ].map((value) => value.trim()).filter(Boolean)))
  return terms.slice(0, 5).join(" ")
}

export function characterFromShadow(character: CharacterShadowRecord): Character {
  return {
    id: character.id,
    book_id: character.book_id,
    name: character.name,
    aliases: character.aliases ?? [],
    role: character.role,
    first_chapter: character.first_chapter,
    last_seen_chapter: character.last_seen_chapter ?? null,
    mention_count: character.mention_count ?? 0,
    status: "alive",
    trait_state: {},
    description: null,
    personality_tags: [],
    motivations: [],
    fears: [],
    archetype: null,
    arc_summary: null,
    analysis_metadata: character.analysis_metadata,
    growth_events: [],
    relationship_summaries: [],
    is_manual: character.is_manual ?? false,
    tags: [],
    graph_visibility_override: null,
  }
}

export function formatResolverStatus(value: string | null | undefined) {
  return (value || "needs_review").replaceAll("_", " ")
}

export function formatRole(role: Character["role"]) {
  if (role === "mc") return "Primary character"
  if (role === "sc") return "Supporting character"
  if (role === "background") return "Minor character"
  return "Character"
}

export function formatRoleFilterLabel(role: Character["role"]) {
  if (role === "mc") return "main"
  if (role === "sc") return "supporting"
  if (role === "background") return "minor"
  return "unclassified"
}

export function formatTraitLabel(key: string) {
  if (key === "age") return "Age"
  return key.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase())
}

export function formatStatus(status: Character["status"]) {
  return status === "deceased" ? "Deceased" : "Active"
}

export function formatRelationshipType(type: string | null | undefined) {
  return (type || "connection")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (part) => part.toUpperCase())
}

export function formatChapterRange(first: number | null | undefined, last: number | null | undefined) {
  if (typeof first !== "number") return "Chapter range unknown"
  if (typeof last === "number" && last > first) return `Ch. ${first}-${last}`
  return `Ch. ${first}`
}

export function formatChapterAppearanceText(
  chapter: number | null | undefined,
  chapterTitleByNumber: ReadonlyMap<number, string>,
) {
  const label = chapterAppearanceLabel(chapter)
  if (typeof chapter !== "number") return label
  const title = chapterTitleByNumber.get(chapter)
  return title ? `${label} / ${title}` : label
}

export function buildTopStats({
  characterCount,
  reviewedCount,
  flaggedCount,
  duplicateCount,
  unresolvedCount,
}: {
  characterCount: number
  reviewedCount: number
  flaggedCount: number
  duplicateCount: number
  unresolvedCount: number
}): CharacterBibleStat[] {
  const percent = (value: number) => characterCount > 0 ? `${Math.round((value / characterCount) * 100)}%` : "0%"
  return [
    { label: "Total characters", value: String(characterCount), tone: "default", icon: "characters" },
    { label: "Reviewed", value: String(reviewedCount), detail: percent(reviewedCount), tone: "teal", icon: "review" },
    { label: "Flagged", value: String(flaggedCount), detail: percent(flaggedCount), tone: "amber", icon: "chapter" },
    { label: "Potential duplicates", value: String(duplicateCount), detail: percent(duplicateCount), tone: "violet", icon: "merge" },
    { label: "Unresolved items", value: String(unresolvedCount), detail: "View", tone: "rose", icon: "review" },
  ]
}

export function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement("a")
  anchor.href = url
  anchor.download = filename
  anchor.click()
  URL.revokeObjectURL(url)
}

export function buildNodeLookup(graphData: RelationshipGraphData | null | undefined) {
  return new Map((graphData?.nodes ?? []).map((node) => [node.id, node.name]))
}

export function buildConnectionsByCharacter(
  graphData: RelationshipGraphData | null | undefined,
): Map<string, ConnectedRelationship[]> {
  const nodeLookup = buildNodeLookup(graphData)
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
}

export function buildRelationshipCounts(
  graphData: RelationshipGraphData | null | undefined,
): Map<string, number> {
  const counts = new Map<string, number>()
  for (const edge of graphData?.edges ?? []) {
    counts.set(edge.source, (counts.get(edge.source) ?? 0) + 1)
    counts.set(edge.target, (counts.get(edge.target) ?? 0) + 1)
  }
  return counts
}

export function buildCharacterLookup(chars: Character[], shadowChars: Character[]) {
  const entries = [...shadowChars, ...chars].map((character) => [character.id, character] as const)
  return new Map(entries)
}

export function buildCharacterFlagsById(
  chars: Character[],
  mergeSuggestionIds: Set<string>,
  connectionsByCharacter: Map<string, ConnectedRelationship[]>,
) {
  const map = new Map<string, string[]>()
  for (const character of chars) {
    map.set(character.id, qualityFlags(character, mergeSuggestionIds, connectionsByCharacter.get(character.id) ?? []))
  }
  return map
}

export function buildCharacterHealthById(
  chars: Character[],
  mergeSuggestionIds: Set<string>,
  connectionsByCharacter: Map<string, ConnectedRelationship[]>,
) {
  const map = new Map<string, CharacterHealth>()
  for (const character of chars) {
    map.set(character.id, buildCharacterHealth(character, mergeSuggestionIds, connectionsByCharacter.get(character.id) ?? []))
  }
  return map
}

export function filterCharacters(
  chars: Character[],
  {
    deferredSearch,
    statusFilter,
    roleFilter,
    castFilter,
    flagsByCharacter,
    mergeSuggestionIds,
  }: {
    deferredSearch: string
    statusFilter: string
    roleFilter: string
    castFilter: "all" | "main" | "minor" | "needs-review" | "duplicates"
    flagsByCharacter: Map<string, string[]>
    mergeSuggestionIds: Set<string>
  },
) {
  return chars.filter((char) => {
    const flags = flagsByCharacter.get(char.id) ?? []
    const statusLabel = reviewStatusLabel(char, flags).toLowerCase()
    const haystack = [
      char.name,
      ...(char.aliases ?? []),
      char.description ?? "",
      char.arc_summary ?? "",
      ...(char.personality_tags ?? []),
      statusLabel,
      formatRoleFilterLabel(char.role),
      ...flags,
    ]
      .join(" ")
      .toLowerCase()

    if (deferredSearch && !haystack.includes(deferredSearch)) return false
    if (statusFilter === "reviewed" && !isReviewedCharacter(char)) return false
    if (statusFilter === "flagged" && !isFlaggedCharacter(char, flags)) return false
    if (statusFilter === "unresolved" && (isReviewedCharacter(char) || isFlaggedCharacter(char, flags))) return false
    if (roleFilter !== "all" && char.role !== roleFilter) return false
    if (castFilter === "all") return true
    if (castFilter === "main") return char.role === "mc" || char.role === "sc"
    if (castFilter === "minor") return char.role === "background" || !char.role
    if (castFilter === "duplicates") return mergeSuggestionIds.has(char.id)
    return flags.length > 0
  })
}

export function filterMergeSuggestions(
  mergeSuggestions: MergeSuggestion[],
  charById: Map<string, Character>,
  deferredSearch: string,
) {
  return mergeSuggestions.filter((suggestion) => {
    if (!deferredSearch) return true
    const primary = charById.get(suggestion.primaryId)
    const secondary = charById.get(suggestion.secondaryId)
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
  })
}

export function filterPendingCharacterCandidates(
  pendingCandidates: CharacterCandidate[],
  deferredSearch: string,
) {
  return pendingCandidates.filter((candidate) => {
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
  })
}

export function filterPendingRelationshipCandidates(
  pendingRelationshipCandidates: CharacterRelationshipCandidate[],
  deferredSearch: string,
) {
  return pendingRelationshipCandidates.filter((candidate) => {
    if (!deferredSearch) return true
    return [
      candidate.raw_character_a,
      candidate.raw_character_b,
      candidate.rel_type ?? "",
      candidate.description ?? "",
      ...(candidate.reason_codes ?? []),
    ]
      .join(" ")
      .toLowerCase()
      .includes(deferredSearch)
  })
}

export function buildDashboardStats(
  chars: Character[],
  flagsByCharacter: Map<string, string[]>,
  mergeSuggestionCount: number,
  pendingReviewItemCount: number,
) {
  let reviewedCount = 0
  let flaggedCount = 0
  for (const character of chars) {
    const flags = flagsByCharacter.get(character.id) ?? []
    if (isReviewedCharacter(character)) reviewedCount += 1
    if (isFlaggedCharacter(character, flags)) flaggedCount += 1
  }
  return buildTopStats({
    characterCount: chars.length,
    reviewedCount,
    flaggedCount,
    duplicateCount: mergeSuggestionCount,
    unresolvedCount: pendingReviewItemCount,
  })
}

export function getPendingCharacterCandidates(reviewData: CharacterReviewResponse) {
  return (reviewData.candidates ?? []).filter((candidate) => (
    candidate.status === "pending"
    || (
      candidate.status === "suppressed"
      && ["place", "organization", "object", "title_or_role"].includes(candidate.adjudication_status ?? "")
    )
  ))
}

export function getPendingRelationshipCandidates(reviewData: CharacterReviewResponse) {
  return (reviewData.relationship_candidates ?? []).filter((candidate) => candidate.status === "pending")
}

export function buildMergeSuggestions(
  reviewData: CharacterReviewResponse,
  dismissedMergeKeys: string[],
): MergeSuggestion[] {
  return (reviewData.duplicate_suggestions ?? [])
    .filter((suggestion) => (
      suggestion.status === "pending"
      && suggestion.confidence >= 75
      && !suggestion.auto_dismissed
      && !dismissedMergeKeys.includes(suggestion.id)
    ))
    .map((suggestion) => ({
      key: suggestion.id,
      suggestionId: suggestion.id,
      primaryId: suggestion.primary_character_id,
      secondaryId: suggestion.secondary_character_id,
      confidence: suggestion.confidence,
      reasons: suggestion.reasons,
      sharedClusterKeys: suggestion.shared_cluster_keys ?? [],
      sharedChapters: suggestion.shared_chapters ?? [],
      embeddingSimilarity: suggestion.embedding_similarity ?? null,
      primaryIsProtected: suggestion.primary_is_protected,
      secondaryIsProtected: suggestion.secondary_is_protected,
      primaryIsCurated: suggestion.primary_is_curated,
      secondaryIsCurated: suggestion.secondary_is_curated,
    }))
}

export function buildMergeSuggestionIds(mergeSuggestions: MergeSuggestion[]) {
  return new Set(mergeSuggestions.flatMap((suggestion) => [suggestion.primaryId, suggestion.secondaryId]))
}

export function buildShadowCharacters(reviewData: CharacterReviewResponse) {
  return (reviewData.shadow_characters ?? []).map(characterFromShadow)
}

export function characterLabelForId(
  characterId: string,
  charById: Map<string, Character>,
  fallbackLabels: Record<string, string>,
) {
  return charById.get(characterId)?.name ?? fallbackLabels[characterId] ?? characterId
}

export function groupAliasRecordsByKind(character: Character | null | undefined) {
  const groups = new Map<string, NonNullable<Character["alias_records"]>>()
  for (const alias of character?.alias_records ?? []) {
    const key = alias.alias_kind || "unspecified"
    groups.set(key, [...(groups.get(key) ?? []), alias])
  }
  return Array.from(groups.entries()).sort(([left], [right]) => left.localeCompare(right))
}

export function sortGrowthEvents(character: Character | null | undefined) {
  return (character?.growth_events ?? [])
    .slice()
    .sort((left, right) => (right.chapter_number ?? right.chapter ?? 0) - (left.chapter_number ?? left.chapter ?? 0))
}

export function sortedRelationshipCounterpartOptions(
  chars: Character[],
  selectedCharacterId: string | null | undefined,
) {
  return chars
    .filter((char) => char.id !== selectedCharacterId)
    .slice()
    .sort((left, right) => left.name.localeCompare(right.name))
}

export function sortedMergeableCharacters(chars: Character[]) {
  return chars.slice().sort((left, right) => left.name.localeCompare(right.name))
}

export function isCuratedCharacter(character: Character | null | undefined) {
  return Boolean(character?.analysis_metadata?.user_curated)
}

export function isProtectedCharacter(character: Character | null | undefined) {
  return Boolean(character?.is_manual || character?.analysis_metadata?.protected_from_repair)
}

export function buildDraft(character: Character | null): EditDraft {
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

export function buildCreateDraft(firstChapter = 1): CreateDraft {
  return {
    ...buildDraft(null),
    role: "",
    firstChapter: String(Math.max(1, firstChapter)),
  }
}

export function buildRelationshipDraft(chapter = 1, counterpartId = ""): RelationshipComposerDraft {
  return {
    counterpartId,
    relType: "neutral",
    sentiment: "0",
    description: "",
    fromChapter: String(Math.max(1, chapter)),
    toChapter: "",
  }
}

export function graphVisibilityLabel(value: Character["graph_visibility_override"]) {
  if (value === "include") return "Forced into graph"
  if (value === "exclude") return "Excluded from graph"
  return "Auto visibility"
}

export function graphVisibilityReasonCopy(reason: string) {
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

export function visibleTraitEntries(character: Character | null) {
  if (!character) return []
  const entries = Object.entries(character.trait_state ?? {}).filter(([, trait]) => (
    trait && trait.confidence >= CONFIDENCE_THRESHOLDS.SHOW_IN_UI && trait.value
  ))
  const seen = new Set(entries.map(([key]) => key))
  const addLegacyTrait = (key: string, value: string | null | undefined) => {
    const trimmed = value?.trim()
    if (!trimmed || seen.has(key)) return
    entries.push([key, { value: trimmed, confidence: 1, type: "objective" }])
    seen.add(key)
  }
  addLegacyTrait("hair", character.hair)
  addLegacyTrait("eyes", character.eyes)
  addLegacyTrait("build", character.build)
  addLegacyTrait("age", character.age_descriptor)
  addLegacyTrait("distinguishing", character.distinguishing)
  return entries
}

export function missingTraitLabels(character: Character) {
  const traits = new Set(visibleTraitEntries(character).map(([key]) => key))
  const missing: string[] = []
  if (!traits.has("age")) missing.push("age")
  if (!traits.has("build")) missing.push("physical description")
  if (!traits.has("distinguishing")) missing.push("distinguishing details")
  return missing
}

export function sentimentLabel(value: number | null | undefined) {
  if (typeof value !== "number" || Number.isNaN(value)) return "Neutral"
  if (value >= 0.4) return "Positive"
  if (value <= -0.4) return "Tense"
  return "Neutral"
}

export function strengthValue(value: number | null | undefined) {
  if (typeof value !== "number" || Number.isNaN(value)) return 32
  return Math.max(18, Math.min(100, Math.round((value + 1) * 50)))
}

export function relationshipStrengthColor(value: number | null | undefined, isDark: boolean) {
  if (typeof value !== "number" || Number.isNaN(value)) return isDark ? "bg-slate-500" : "bg-stone-400"
  if (value >= 0.4) return "bg-teal-600"
  if (value <= -0.4) return "bg-rose-500"
  return isDark ? "bg-slate-500" : "bg-stone-400"
}

export function growthTitle(event: NonNullable<Character["growth_events"]>[number]) {
  return event.event_title || event.event || "Untitled event"
}

export function growthChapter(event: NonNullable<Character["growth_events"]>[number]) {
  return event.chapter_number ?? event.chapter ?? null
}

export function qualityFlags(character: Character, mergeSuggestionIds: Set<string>, connections: ConnectedRelationship[]) {
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

export function healthTone(score: number): CharacterHealth["tone"] {
  if (score >= 80) return "strong"
  if (score >= 60) return "moderate"
  return "attention"
}

export function buildCharacterHealth(character: Character, mergeSuggestionIds: Set<string>, connections: ConnectedRelationship[]): CharacterHealth {
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

export function flagClasses(isDark: boolean, flag: string) {
  if (flag === "Needs merge") {
    return isDark ? "bg-amber-500/12 text-amber-200" : "bg-amber-50 text-amber-700"
  }
  if (flag === "Low confidence" || flag === "Arc stale") {
    return isDark ? "bg-rose-500/12 text-rose-200" : "bg-rose-50 text-rose-700"
  }
  return isDark ? "bg-sky-500/12 text-sky-200" : "bg-sky-50 text-sky-700"
}

export function buildSelectedCharacterSummary(character: Character | null, connections: ConnectedRelationship[]) {
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

export function isReviewedCharacter(character: Character) {
  return Boolean(
    character.approval_state === "approved"
    || character.approval_state === "protected"
    || character.analysis_metadata?.user_curated
    || character.is_manual,
  )
}

export function isFlaggedCharacter(character: Character, flags: string[]) {
  return Boolean(
    flags.length > 0
    || character.approval_state === "pending_review"
    || character.analysis_metadata?.needs_review
    || (character.analysis_metadata?.quality_flags?.length ?? 0) > 0,
  )
}

export function reviewStatusLabel(character: Character, flags: string[]) {
  if (isFlaggedCharacter(character, flags)) return "Flagged"
  if (isReviewedCharacter(character)) return "Reviewed"
  return "Unresolved"
}

export function chapterSpanCount(character: Character) {
  const first = character.first_chapter || 1
  const last = character.last_seen_chapter ?? first
  return Math.max(1, last - first + 1)
}

export function bookCoverageLabel(character: Character, totalChapters: number | null | undefined) {
  if (!totalChapters || totalChapters < 1) return "Coverage unknown"
  return `${Math.min(100, Math.round((chapterSpanCount(character) / totalChapters) * 100))}% of book`
}

export function chapterAppearanceLabel(chapter: number | null | undefined) {
  if (typeof chapter !== "number" || chapter < 1) return "Chapter unknown"
  return `Chapter ${chapter}`
}

export function knownFacts(character: Character, connections: ConnectedRelationship[]) {
  const facts: string[] = []
  for (const [key, trait] of Object.entries(character.trait_state ?? {})) {
    if (trait?.value && trait.confidence >= CONFIDENCE_THRESHOLDS.SHOW_IN_UI) {
      facts.push(`${key.replaceAll("_", " ")}: ${trait.value}`)
    }
  }
  if (character.goal) facts.push(`Goal: ${character.goal}`)
  if (character.arc_type) facts.push(`Arc: ${character.arc_type}`)
  if (connections.length > 0) facts.push(`${connections.length} relationship ${connections.length === 1 ? "link" : "links"} tracked`)
  return facts.slice(0, 5)
}

export function openQuestionsForCharacter(character: Character, connections: ConnectedRelationship[]) {
  const questions: string[] = []
  if (!character.goal && !character.arc_tracker?.goal) questions.push(`What does ${character.name} want most clearly?`)
  if ((character.motivations ?? []).length === 0) questions.push("Which scene proves the motivation?")
  if (connections.length === 0) questions.push("Which relationship should be linked first?")
  if (!character.arc_summary) questions.push("What is the long-term arc summary?")
  return questions.slice(0, 3)
}
