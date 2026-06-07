import type { BetaReadAssignment } from "@/types/betaRead"
import { normalizeBookRouteId } from "@/lib/utils/bookRoutes"

export function parseQuestionLines(value: string): string[] {
  return value
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
}

export function formatFeedbackKindLabel(kind: string): string {
  return kind
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase())
}

export function selectPrimaryAssignment(assignments: BetaReadAssignment[], bookId: string): BetaReadAssignment | null {
  const normalizedBookId = normalizeBookRouteId(bookId)
  const filtered = assignments.filter((assignment) => assignment.book_id === normalizedBookId)
  if (filtered.length === 0) return null
  return (
    filtered.find((assignment) => assignment.view_bucket === "active")
    ?? filtered.find((assignment) => assignment.view_bucket === "scheduled")
    ?? filtered[0]
    ?? null
  )
}
