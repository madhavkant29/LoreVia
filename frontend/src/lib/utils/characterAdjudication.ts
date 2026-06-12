import type { CharacterCandidate } from "@/types/character"

export function candidateAdjudicationBadges(candidate: CharacterCandidate): string[] {
  const badges: string[] = []
  const add = (label: string) => {
    if (!badges.includes(label)) {
      badges.push(label)
    }
  }
  const status = (candidate.adjudication_status ?? "").toLowerCase()
  const entityType = (candidate.entity_type ?? "").toLowerCase()
  const reasons = [
    ...(candidate.reason_codes ?? []),
    ...(candidate.resolver_reasons ?? []),
    candidate.rejection_reason ?? "",
  ].map((item) => item.toLowerCase())
  const hasReason = (needle: string) => reasons.some((item) => item.includes(needle))

  if (status === "place" || entityType === "place" || hasReason("place")) {
    add("likely place")
  }
  if (status === "title_or_role" || entityType === "title_or_role" || hasReason("role") || hasReason("title")) {
    add("title/role")
  }
  if (entityType === "junk" || hasReason("junk") || hasReason("fragment") || hasReason("single_letter")) {
    add("junk fragment")
  }
  if (status === "merged_alias" || entityType === "alias_candidate" || hasReason("alias") || hasReason("merge")) {
    add("possible alias")
  }
  if (
    status === "quarantined"
    || hasReason("low_evidence")
    || hasReason("thin_evidence")
    || Number(candidate.character_score ?? 0) < 60
  ) {
    add("low evidence")
  }
  if (badges.length === 0 || status === "candidate" || status === "unknown") {
    add("needs review")
  }

  return badges.slice(0, 5)
}
