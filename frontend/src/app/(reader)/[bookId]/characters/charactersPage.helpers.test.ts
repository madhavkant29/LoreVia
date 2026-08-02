import { describe, expect, it } from "vitest"

import type {
  Character,
  CharacterCandidate,
  CharacterRelationshipCandidate,
  CharacterReviewResponse,
  CharacterShadowRecord,
} from "@/types/character"
import {
  bookCoverageLabel,
  buildCharacterFlagsById,
  buildCharacterHealthById,
  buildCharacterLookup,
  buildConnectionsByCharacter,
  buildDashboardStats,
  buildMergeSuggestionIds,
  buildMergeSuggestions,
  buildShadowCharacters,
  buildTopStats,
  buildCharacterHealth,
  buildCandidateEvidenceQuery,
  buildCharacterEvidenceQuery,
  buildCreateDraft,
  buildDraft,
  buildRelationshipDraft,
  buildSelectedCharacterSummary,
  characterFromShadow,
  characterLabelForId,
  chapterAppearanceLabel,
  chapterSpanCount,
  flagClasses,
  filterCharacters,
  filterMergeSuggestions,
  filterPendingCharacterCandidates,
  filterPendingRelationshipCandidates,
  formatStatus,
  graphVisibilityLabel,
  graphVisibilityReasonCopy,
  getPendingCharacterCandidates,
  getPendingRelationshipCandidates,
  groupAliasRecordsByKind,
  growthChapter,
  growthTitle,
  isCuratedCharacter,
  isFlaggedCharacter,
  isProtectedCharacter,
  isReviewedCharacter,
  knownFacts,
  missingTraitLabels,
  openQuestionsForCharacter,
  qualityFlags,
  relationshipChangeKey,
  relationshipStrengthColor,
  reviewStatusLabel,
  sentimentLabel,
  sortedMergeableCharacters,
  sortedRelationshipCounterpartOptions,
  sortGrowthEvents,
  strengthValue,
  visibleTraitEntries,
  buildRelationshipCounts,
  type MergeSuggestion,
} from "./charactersPage.helpers"
import { character } from "./charactersPage.testData"

describe("characters page helpers", () => {
  it("builds top dashboard stats with safe percentages", () => {
    expect(buildTopStats({
      characterCount: 10,
      reviewedCount: 6,
      flaggedCount: 2,
      duplicateCount: 1,
      unresolvedCount: 4,
    })).toEqual([
      { label: "Total characters", value: "10", tone: "default", icon: "characters" },
      { label: "Reviewed", value: "6", detail: "60%", tone: "teal", icon: "review" },
      { label: "Flagged", value: "2", detail: "20%", tone: "amber", icon: "chapter" },
      { label: "Potential duplicates", value: "1", detail: "10%", tone: "violet", icon: "merge" },
      { label: "Unresolved items", value: "4", detail: "View", tone: "rose", icon: "review" },
    ])

    expect(buildTopStats({
      characterCount: 0,
      reviewedCount: 0,
      flaggedCount: 0,
      duplicateCount: 0,
      unresolvedCount: 0,
    })[1].detail).toBe("0%")
  })

  it("builds relationship maps and character lookup maps", () => {
    const graph = {
      nodes: [
        { id: "character-1", name: "Mira", role: "mc", first_chapter: 1 },
        { id: "character-2", name: "Jon", role: "sc", first_chapter: 2 },
        { id: "character-3", name: "Sefa", role: "sc", first_chapter: 3 },
      ],
      edges: [
        {
          source: "character-1",
          target: "character-2",
          type: "ally",
          sentiment: 0.6,
          description: "Trusts him",
          from_chapter: 2,
        },
        {
          source: "character-3",
          target: "character-1",
          type: "rival",
          sentiment: -0.4,
          description: "Challenges her",
          from_chapter: 7,
        },
      ],
    }

    const connections = buildConnectionsByCharacter(graph)
    expect(connections.get("character-1")?.map((connection) => connection.counterpartName)).toEqual(["Sefa", "Jon"])
    expect(buildRelationshipCounts(graph).get("character-1")).toBe(2)

    const shadow = character({ id: "shadow-1", name: "Shadow" })
    const visible = character({ id: "character-1", name: "Visible" })
    expect(Array.from(buildCharacterLookup([visible], [shadow]).keys())).toEqual(["shadow-1", "character-1"])
  })

  it("derives flags, health, filtered characters, and dashboard stats", () => {
    const mira = character({
      id: "character-1",
      name: "Mira",
      aliases: ["Captain"],
      role: "mc",
      approval_state: "approved",
      description: "Lead scout",
      motivations: ["protect the crew"],
      trait_state: { hair: { value: "black", confidence: 0.9, type: "objective" } },
    })
    const jon = character({
      id: "character-2",
      name: "Jon",
      role: "background",
      description: null,
      analysis_metadata: { needs_review: true },
    })
    const connections = new Map([["character-2", [{ counterpartName: "Mira" } as Parameters<typeof buildCharacterHealth>[2][number]]]])
    const mergeIds = new Set(["character-2"])
    const flagsByCharacter = buildCharacterFlagsById([mira, jon], mergeIds, connections)
    const healthByCharacter = buildCharacterHealthById([mira, jon], mergeIds, connections)

    expect(flagsByCharacter.get("character-2")).toContain("Needs merge")
    expect(healthByCharacter.get("character-2")?.tone).toBe("attention")
    expect(filterCharacters([mira, jon], {
      deferredSearch: "captain",
      statusFilter: "all",
      roleFilter: "all",
      castFilter: "all",
      flagsByCharacter,
      mergeSuggestionIds: mergeIds,
    }).map((item) => item.id)).toEqual(["character-1"])
    expect(filterCharacters([mira, jon], {
      deferredSearch: "",
      statusFilter: "flagged",
      roleFilter: "all",
      castFilter: "duplicates",
      flagsByCharacter,
      mergeSuggestionIds: mergeIds,
    }).map((item) => item.id)).toEqual(["character-2"])
    expect(buildDashboardStats([mira, jon], flagsByCharacter, 1, 3)).toEqual([
      { label: "Total characters", value: "2", tone: "default", icon: "characters" },
      { label: "Reviewed", value: "1", detail: "50%", tone: "teal", icon: "review" },
      { label: "Flagged", value: "2", detail: "100%", tone: "amber", icon: "chapter" },
      { label: "Potential duplicates", value: "1", detail: "50%", tone: "violet", icon: "merge" },
      { label: "Unresolved items", value: "3", detail: "View", tone: "rose", icon: "review" },
    ])
  })

  it("filters merge and review queues by search text", () => {
    const charById = buildCharacterLookup([
      character({ id: "character-1", name: "Mira", aliases: ["Captain"] }),
      character({ id: "character-2", name: "Jon", aliases: [] }),
    ], [])
    const mergeSuggestions: MergeSuggestion[] = [
      {
        key: "merge-1",
        primaryId: "character-1",
        secondaryId: "character-2",
        confidence: 90,
        reasons: ["shared chapter"],
        sharedClusterKeys: [],
        sharedChapters: [],
        primaryIsProtected: false,
        secondaryIsProtected: false,
        primaryIsCurated: false,
        secondaryIsCurated: false,
      },
    ]

    expect(filterMergeSuggestions(mergeSuggestions, charById, "captain")).toHaveLength(1)
    expect(filterMergeSuggestions(mergeSuggestions, charById, "missing")).toHaveLength(0)
    expect(filterPendingCharacterCandidates([
      {
        proposed_name: "Sefa",
        raw_name: "Sefa",
        aliases: ["Navigator"],
        reason_codes: ["low_confidence"],
      } as CharacterCandidate,
    ], "navigator")).toHaveLength(1)
    expect(filterPendingRelationshipCandidates([
      {
        raw_character_a: "Mira",
        raw_character_b: "Jon",
        rel_type: "ally",
        description: "Trust improves",
        reason_codes: ["relationship_unresolved"],
      } as CharacterRelationshipCandidate,
    ], "trust")).toHaveLength(1)
  })

  it("derives pending review queues and normalized merge suggestions", () => {
    const reviewData = {
      candidates: [
        { id: "candidate-1", status: "pending", proposed_name: "Mira" },
        { id: "candidate-2", status: "suppressed", adjudication_status: "place", proposed_name: "River" },
        { id: "candidate-3", status: "suppressed", adjudication_status: "not_a_character", proposed_name: "Noise" },
      ],
      relationship_candidates: [
        { id: "relationship-1", status: "pending", raw_character_a: "Mira", raw_character_b: "Jon" },
        { id: "relationship-2", status: "accepted", raw_character_a: "Mira", raw_character_b: "Sefa" },
      ],
      duplicate_suggestions: [
        {
          id: "duplicate-1",
          status: "pending",
          confidence: 80,
          auto_dismissed: false,
          primary_character_id: "character-1",
          secondary_character_id: "character-2",
          reasons: ["same alias"],
          shared_cluster_keys: ["mira"],
          shared_chapters: [2],
          embedding_similarity: 0.91,
          primary_is_protected: false,
          secondary_is_protected: true,
          primary_is_curated: true,
          secondary_is_curated: false,
        },
        {
          id: "duplicate-2",
          status: "pending",
          confidence: 70,
          auto_dismissed: false,
          primary_character_id: "character-3",
          secondary_character_id: "character-4",
          reasons: [],
          primary_is_protected: false,
          secondary_is_protected: false,
          primary_is_curated: false,
          secondary_is_curated: false,
        },
      ],
      shadow_characters: [
        {
          id: "shadow-1",
          book_id: "book-1",
          name: "Shadow Mira",
          role: "sc",
          first_chapter: 3,
          analysis_metadata: {},
        },
      ],
    } as unknown as CharacterReviewResponse

    expect(getPendingCharacterCandidates(reviewData).map((candidate) => candidate.id)).toEqual(["candidate-1", "candidate-2"])
    expect(getPendingRelationshipCandidates(reviewData).map((candidate) => candidate.id)).toEqual(["relationship-1"])
    expect(buildMergeSuggestions(reviewData, []).map((suggestion) => suggestion.key)).toEqual(["duplicate-1"])
    expect(buildMergeSuggestions(reviewData, ["duplicate-1"])).toEqual([])
    expect(Array.from(buildMergeSuggestionIds(buildMergeSuggestions(reviewData, [])))).toEqual(["character-1", "character-2"])
    expect(buildShadowCharacters(reviewData)[0]).toMatchObject({
      id: "shadow-1",
      name: "Shadow Mira",
      aliases: [],
      status: "alive",
    })
  })

  it("labels characters, groups aliases, and sorts growth/options", () => {
    const mira = character({
      id: "character-1",
      name: "Mira",
      alias_records: [
        {
          id: "alias-1",
          book_id: "book-1",
          character_id: "character-1",
          alias_text: "Captain",
          normalized_alias: "captain",
          alias_kind: "title",
          source: "test",
          confidence: 0.9,
          created_at: "2026-01-01T00:00:00Z",
        },
        {
          id: "alias-2",
          book_id: "book-1",
          character_id: "character-1",
          alias_text: "M",
          normalized_alias: "m",
          alias_kind: "",
          source: "test",
          confidence: 0.9,
          created_at: "2026-01-01T00:00:00Z",
        },
      ] as Character["alias_records"],
      growth_events: [
        { event: "Early doubt", chapter_number: 2 },
        { event: "Late resolve", chapter: 7 },
      ] as Character["growth_events"],
    })
    const jon = character({ id: "character-2", name: "Jon" })
    const sefa = character({ id: "character-3", name: "Sefa" })
    const charById = buildCharacterLookup([mira, jon], [])

    expect(characterLabelForId("character-1", charById, {})).toBe("Mira")
    expect(characterLabelForId("missing", charById, { missing: "Fallback" })).toBe("Fallback")
    expect(groupAliasRecordsByKind(mira).map(([kind, aliases]) => [kind, aliases.map((alias) => alias.alias_text)])).toEqual([
      ["title", ["Captain"]],
      ["unspecified", ["M"]],
    ])
    expect(sortGrowthEvents(mira).map((event) => event.event)).toEqual(["Late resolve", "Early doubt"])
    expect(sortedRelationshipCounterpartOptions([sefa, mira, jon], "character-1").map((item) => item.name)).toEqual(["Jon", "Sefa"])
    expect(sortedMergeableCharacters([sefa, mira, jon]).map((item) => item.name)).toEqual(["Jon", "Mira", "Sefa"])
  })

  it("builds stable evidence search queries from unique trimmed names", () => {
    expect(buildCharacterEvidenceQuery(character({ name: "Mira", aliases: ["Mira", " Mir ", "Captain", "Storm", "Extra"] }))).toBe(
      "Mira Mir Captain Storm",
    )

    const candidate = {
      proposed_name: "Mira",
      raw_name: " Mira ",
      aliases: ["Mir", "Captain"],
      cluster_names: ["Storm", "Extra"],
    } as CharacterCandidate

    expect(buildCandidateEvidenceQuery(candidate)).toBe("Mira Mir Captain Storm Extra")
  })

  it("maps shadow records into displayable character records", () => {
    const mapped = characterFromShadow({
      id: "shadow-1",
      book_id: "book-1",
      name: "Shadow Mira",
      aliases: undefined as unknown as string[],
      role: "sc",
      first_chapter: 3,
      last_seen_chapter: undefined,
      mention_count: undefined,
      analysis_metadata: { trust_tier: "review_only" },
      is_manual: undefined,
    } as CharacterShadowRecord)

    expect(mapped).toMatchObject({
      id: "shadow-1",
      name: "Shadow Mira",
      aliases: [],
      role: "sc",
      first_chapter: 3,
      last_seen_chapter: null,
      mention_count: 0,
      status: "alive",
      is_manual: false,
      tags: [],
      graph_visibility_override: null,
    })
  })

  it("creates stable keys for relationship change rows", () => {
    const key = relationshipChangeKey(
      {
        counterpart_id: "character-2",
        counterpart_name: "Jon",
        chapter_number: 4,
        type: "ally",
        to_chapter: null,
        sentiment: undefined,
        description: "Trust improves",
      },
      2,
    )

    expect(key).toBe("character-2:4:ally:open:neutral:Trust improves:2")
  })

  it("builds draft defaults and relationship composer state", () => {
    const mira = character({
      aliases: ["Captain"],
      goal: "Find the gate",
      personality_tags: ["guarded"],
      motivations: ["protect Sefa"],
      fears: ["betrayal"],
    })

    expect(buildDraft(mira)).toMatchObject({
      name: "Mira",
      aliases: "Captain",
      goal: "Find the gate",
      personalityTags: "guarded",
      motivations: "protect Sefa",
      fears: "betrayal",
    })
    expect(buildCreateDraft(0)).toMatchObject({ role: "", firstChapter: "1" })
    expect(buildRelationshipDraft(4, "character-2")).toMatchObject({
      counterpartId: "character-2",
      relType: "neutral",
      fromChapter: "4",
    })
  })

  it("formats graph visibility, sentiment, strength, chapters, and growth event labels", () => {
    expect(graphVisibilityLabel("include")).toBe("Forced into graph")
    expect(graphVisibilityLabel("exclude")).toBe("Excluded from graph")
    expect(graphVisibilityLabel(null)).toBe("Auto visibility")
    expect(graphVisibilityReasonCopy("author_override_include")).toContain("keeps this character visible")
    expect(graphVisibilityReasonCopy("custom_reason")).toBe("custom reason")
    expect(sentimentLabel(0.6)).toBe("Positive")
    expect(sentimentLabel(-0.6)).toBe("Tense")
    expect(sentimentLabel(undefined)).toBe("Neutral")
    expect(strengthValue(-2)).toBe(18)
    expect(strengthValue(2)).toBe(100)
    expect(relationshipStrengthColor(null, true)).toBe("bg-slate-500")
    expect(relationshipStrengthColor(0.8, false)).toBe("bg-teal-600")
    expect(chapterAppearanceLabel(null)).toBe("Chapter unknown")
    expect(chapterAppearanceLabel(3)).toBe("Chapter 3")
    expect(growthTitle({ event: "Learns the truth", chapter: 4 } as NonNullable<Character["growth_events"]>[number])).toBe("Learns the truth")
    expect(growthChapter({ chapter_number: 5 } as NonNullable<Character["growth_events"]>[number])).toBe(5)
  })

  it("derives character traits, health, flags, facts, and review status", () => {
    const mira = character({
      id: "character-1",
      description: null,
      trait_state: {
        hair: { value: "black", confidence: 0.9, type: "objective" },
        hidden: { value: "secret", confidence: 0.1, type: "objective" },
      },
      build: "athletic",
      last_seen_chapter: 5,
      growth_events: [],
      motivations: [],
      arc_tracker: { diagnostics: ["changes too abruptly"] } as Character["arc_tracker"],
      analysis_metadata: { needs_review: true },
    })
    const connections = [
      { counterpartName: "Jon", type: "ally", description: "", from_chapter: null },
    ] as unknown as Parameters<typeof qualityFlags>[2]
    const mergeIds = new Set(["character-1"])

    expect(visibleTraitEntries(mira).map(([key]) => key)).toEqual(["hair", "build"])
    expect(missingTraitLabels(mira)).toEqual(["age", "distinguishing details"])
    expect(qualityFlags(mira, mergeIds, connections)).toEqual([
      "Needs merge",
      "Missing traits",
      "Needs evidence",
      "Arc stale",
    ])
    expect(buildCharacterHealth(mira, mergeIds, connections)).toMatchObject({
      tone: "attention",
      issues: expect.arrayContaining(["Age is not grounded", "Duplicate candidate found"]),
    })
    expect(flagClasses(false, "Needs merge")).toContain("amber")
    expect(buildSelectedCharacterSummary(mira, connections)).toContain("Ally connection with Jon")
    expect(isCuratedCharacter(character({ analysis_metadata: { user_curated: true } }))).toBe(true)
    expect(isProtectedCharacter(character({ is_manual: true }))).toBe(true)
    expect(isReviewedCharacter(character({ approval_state: "approved" }))).toBe(true)
    expect(isFlaggedCharacter(mira, [])).toBe(true)
    expect(reviewStatusLabel(mira, [])).toBe("Flagged")
    expect(chapterSpanCount(mira)).toBe(5)
    expect(bookCoverageLabel(mira, 10)).toBe("50% of book")
    expect(knownFacts(character({ trait_state: { eyes: { value: "gray", confidence: 0.9, type: "objective" } }, goal: "Open the gate" }), [])).toContain("eyes: gray")
    expect(openQuestionsForCharacter(character({ goal: null, arc_summary: null }), [])).toEqual([
      "What does Mira want most clearly?",
      "Which scene proves the motivation?",
      "Which relationship should be linked first?",
    ])
  })
})
