import type { BetaReadAssignment } from "@/types/reader"

const SHORT_DATE_FORMATTER = new Intl.DateTimeFormat("en-US", {
  month: "short",
  day: "numeric",
})

const TIME_FORMATTER = new Intl.DateTimeFormat("en-US", {
  hour: "numeric",
  minute: "2-digit",
})

function toDate(value: string) {
  return new Date(value)
}

function startOfDay(value: Date) {
  return new Date(value.getFullYear(), value.getMonth(), value.getDate())
}

function isSameDay(left: Date, right: Date) {
  return (
    left.getFullYear() === right.getFullYear()
    && left.getMonth() === right.getMonth()
    && left.getDate() === right.getDate()
  )
}

export function betaReadDeadlineLabel(expiresAt: string, now = new Date()) {
  const dueAt = toDate(expiresAt)
  if (Number.isNaN(dueAt.getTime())) return "Due soon"
  if (dueAt.getTime() < now.getTime()) return "Expired"
  if (isSameDay(dueAt, now)) return "Due today"

  const dayDiff = Math.ceil((startOfDay(dueAt).getTime() - startOfDay(now).getTime()) / 86400000)
  if (dayDiff <= 3) return `${dayDiff} day${dayDiff === 1 ? "" : "s"} left`
  return `Due ${SHORT_DATE_FORMATTER.format(dueAt)}`
}

export function betaReadDeadlineDetail(expiresAt: string, now = new Date()) {
  const dueAt = toDate(expiresAt)
  if (Number.isNaN(dueAt.getTime())) return "Deadline unavailable"
  if (isSameDay(dueAt, now)) return `Today, ${TIME_FORMATTER.format(dueAt)}`
  return `${SHORT_DATE_FORMATTER.format(dueAt)}, ${TIME_FORMATTER.format(dueAt)}`
}

export function betaReadHoursRemaining(expiresAt: string, now = new Date()) {
  const dueAt = toDate(expiresAt)
  if (Number.isNaN(dueAt.getTime())) return null
  return (dueAt.getTime() - now.getTime()) / 3600000
}

export function betaReadIsUrgent(expiresAt: string, now = new Date()) {
  const hoursRemaining = betaReadHoursRemaining(expiresAt, now)
  return hoursRemaining !== null && hoursRemaining >= 0 && hoursRemaining < 24
}

export function betaReadProgressLabel(assignment: BetaReadAssignment) {
  return `${Math.round(assignment.progress_pct)}% read`
}

export function betaReadRequirementLines(assignment: BetaReadAssignment) {
  const lines = [
    `Finish ${assignment.required_progress_pct}% of the assigned reading`,
  ]
  if (assignment.required_comment_count > 0) {
    lines.push(`Leave at least ${assignment.required_comment_count} comment${assignment.required_comment_count === 1 ? "" : "s"}`)
  }
  if (assignment.required_feedback_item_count > 0) {
    lines.push(`Add at least ${assignment.required_feedback_item_count} feedback item${assignment.required_feedback_item_count === 1 ? "" : "s"}`)
  }
  if (assignment.require_final_feedback) {
    lines.push("Submit final feedback")
  }
  return lines
}

export function betaReadPrimaryHref(assignment: BetaReadAssignment) {
  return `/${assignment.book_id}/chapter/${Math.max(1, assignment.current_chapter || assignment.chapter_start || 1)}`
}

export function betaReadMissedWarning(assignment: BetaReadAssignment) {
  if (assignment.view_bucket !== "missed") return null
  if (assignment.penalty_warning) return assignment.penalty_warning
  if (assignment.counted_toward_missed_streak) {
    return "This missed beta read counted toward your consecutive-miss streak."
  }
  return null
}
