import { describe, expect, it } from "vitest"

import type { CharacterCandidate } from "@/types/character"
import { candidateAdjudicationBadges } from "./characterAdjudication"

function candidate(overrides: Partial<CharacterCandidate>): CharacterCandidate {
  return {
    id: "candidate-1",
    book_id: "book-1",
    chapter_number: 1,
    raw_name: "Port Stowe",
    proposed_name: "Port Stowe",
    normalized_name: "port stowe",
    aliases: [],
    status: "pending",
    confidence: 42,
    reason_codes: [],
    evidence: {},
    cluster_names: [],
    cluster_size: 1,
    cluster_mention_count: 1,
    resolver_reasons: [],
    snippets: [],
    source_batch_key: null,
    created_at: "2026-06-11T00:00:00Z",
    updated_at: "2026-06-11T00:00:00Z",
    ...overrides,
  }
}

describe("candidateAdjudicationBadges", () => {
  it("labels place candidates", () => {
    expect(candidateAdjudicationBadges(candidate({ adjudication_status: "place", entity_type: "place" }))).toContain("likely place")
  })

  it("labels aliases and low-evidence candidates", () => {
    const badges = candidateAdjudicationBadges(candidate({
      adjudication_status: "merged_alias",
      entity_type: "alias_candidate",
      character_score: 35,
    }))

    expect(badges).toContain("possible alias")
    expect(badges).toContain("low evidence")
  })

  it("falls back to needs review", () => {
    expect(candidateAdjudicationBadges(candidate({ character_score: 88 }))).toEqual(["needs review"])
  })
})
