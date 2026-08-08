import type { NextBestAction } from "@/types/ux"

export type RecommendationPriority =
  | "failed_processing"
  | "active_drafting"
  | "severe_finding"
  | "fresh_beta_feedback"
  | "export_share_ready"
  | "fallback"

export type NextBestActionCandidate = NextBestAction & {
  priority: RecommendationPriority
  fingerprint: string
}
type StoredRecommendationState = {
  fingerprint?: string
  snoozed_until?: string
  dismissed_at?: string
}

const PRIORITY_RANK: Record<RecommendationPriority, number> = {
  failed_processing: 0,
  active_drafting: 1,
  severe_finding: 2,
  fresh_beta_feedback: 3,
  export_share_ready: 4,
  fallback: 5,
}

function storedState(value: unknown): StoredRecommendationState | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null
  return value as StoredRecommendationState
}

export function recommendationIsSuppressed(
  candidate: NextBestActionCandidate,
  stored: Record<string, unknown>,
  now = new Date(),
) {
  const state = storedState(stored[candidate.id])
  if (!state || state.fingerprint !== candidate.fingerprint) return false
  if (state.dismissed_at) return true
  if (!state.snoozed_until) return false
  const snoozedUntil = new Date(state.snoozed_until).getTime()
  return Number.isFinite(snoozedUntil) && snoozedUntil > now.getTime()
}

export function resolveNextBestActions(
  candidates: NextBestActionCandidate[],
  stored: Record<string, unknown> = {},
  now = new Date(),
) {
  return candidates
    .map((candidate, index) => ({ candidate, index }))
    .filter(({ candidate }) => !recommendationIsSuppressed(candidate, stored, now))
    .sort((left, right) => (
      PRIORITY_RANK[left.candidate.priority] - PRIORITY_RANK[right.candidate.priority]
      || left.index - right.index
    ))
    .map(({ candidate }) => candidate)
}
