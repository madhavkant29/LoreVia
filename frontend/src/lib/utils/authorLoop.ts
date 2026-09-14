import type { BetaReadAssignment, BetaReadAssignmentDetail, BetaReadConsensus } from "@/types/betaRead"
import type { Book, ChapterConsistencyReport, RevisionActionItem, RevisionBoard, RevisionIntelligence, StoryHealth, WriterWorkspace } from "@/types/book"
import type { Character } from "@/types/character"
import type { NextBestActionCandidate } from "@/lib/workspace/nextBestActionResolver"
import type { Route } from "next"

export type AuthorLoopStepTone = "ready" | "working" | "attention"

export type AuthorLoopStep = {
  id: "upload" | "bible" | "continuity" | "issues" | "invite" | "feedback"
  label: string
  detail: string
  tone: AuthorLoopStepTone
}

export type AuthorLoopIssueCard = {
  id: string
  title: string
  severity: "high" | "medium" | "low"
  affected: string[]
  citation: string
  explanation: string
  suggestedFix: string
  confidence: string
  status: string
  sourceLabel: string
}

function severityRank(severity: string) {
  if (severity === "high") return 3
  if (severity === "medium") return 2
  return 1
}

function normalizeIssueSeverity(severity: string | null | undefined): "high" | "medium" | "low" {
  const normalized = (severity ?? "").trim().toLowerCase()
  if (normalized === "critical" || normalized === "high") return "high"
  if (normalized === "moderate" || normalized === "medium") return "medium"
  return "low"
}

function normalizeBoardStatus(board: RevisionBoard | null | undefined, itemId: string) {
  return board?.items.find((item) => item.item_id === itemId)?.status ?? "pending"
}

function buildIssueCardFromRevisionItem(item: RevisionActionItem, board: RevisionBoard | null | undefined): AuthorLoopIssueCard {
  const severity = normalizeIssueSeverity(item.severity)
  const affected = [item.source_label, item.chapter_ref ? `Chapter ${item.chapter_ref}` : null].filter(Boolean) as string[]
  return {
    id: item.id,
    title: item.title,
    severity,
    affected,
    citation: item.chapter_ref ? `Chapter ${item.chapter_ref}` : "Cross-manuscript signal",
    explanation: item.description,
    suggestedFix: item.recommendation || "Review the cited passage and decide whether this needs a manuscript update.",
    confidence: severity === "high" ? "High priority" : severity === "medium" ? "Worth a focused pass" : "Keep on radar",
    status: normalizeBoardStatus(board, item.id),
    sourceLabel: item.category.replace(/_/g, " "),
  }
}

function buildIssueCardFromChapterReport(report: ChapterConsistencyReport, index: number): AuthorLoopIssueCard[] {
  return report.continuity_flags.map((flag, flagIndex) => ({
    id: `chapter-report:${report.chapter_number}:${index}:${flagIndex}`,
    title: flag,
    severity: "medium",
    affected: [report.chapter_title ? `Chapter ${report.chapter_number}: ${report.chapter_title}` : `Chapter ${report.chapter_number}`],
    citation: `Chapter ${report.chapter_number}`,
    explanation: report.summary,
    suggestedFix: "Open the cited chapter report and verify whether the flagged detail needs a continuity note or a direct revision.",
    confidence: "Chapter-level signal",
    status: "pending",
    sourceLabel: "chapter report",
  }))
}

export function buildAuthorLoopIssueCards(
  revision: RevisionIntelligence | null | undefined,
  reports: ChapterConsistencyReport[],
  workspace: WriterWorkspace | null | undefined
): AuthorLoopIssueCard[] {
  const board = workspace?.revision_board
  const revisionItems = [
    ...(revision?.change_impacts ?? []),
    ...(revision?.scene_advice ?? []),
    ...(revision?.confusion_map ?? []),
    ...(revision?.voice_alerts ?? []),
    ...(revision?.external_signals ?? []),
    ...(revision?.revision_plan.flatMap((revisionPass) => revisionPass.items) ?? []),
  ]
  const uniqueItems = new Map<string, RevisionActionItem>()
  for (const item of revisionItems) {
    if (!uniqueItems.has(item.id)) uniqueItems.set(item.id, item)
  }
  const cards = [...uniqueItems.values()].map((item) => buildIssueCardFromRevisionItem(item, board))
  reports.forEach((report, index) => {
    cards.push(...buildIssueCardFromChapterReport(report, index))
  })
  return cards
    .filter((card) => card.status !== "fixed" && card.status !== "ignored")
    .sort((left, right) => severityRank(right.severity) - severityRank(left.severity))
}

export function buildProjectNextActions(params: {
  book: Book | null
  bookId: string
  issues: AuthorLoopIssueCard[]
  consensus: BetaReadConsensus | null
  assignmentCount: number
}): NextBestActionCandidate[] {
  const { book, bookId, issues, consensus, assignmentCount } = params
  const candidates: NextBestActionCandidate[] = []
  const bookRoute = (path: string) => `/${bookId}${path}` as Route
  const isShareReady = book?.status === "ready"
    && issues.length === 0
    && (consensus?.summary.open_feedback_count ?? 0) === 0
  if (book?.status === "failed") {
    candidates.push({
      id: `project:${bookId}:processing`,
      label: "Resume manuscript processing",
      description: "Processing stopped before the review workspace was ready.",
      href: bookRoute("/overview"),
      tone: "danger",
      priority: "failed_processing",
      fingerprint: `failed:${book.processing?.last_error ?? "unknown"}`,
    })
  }
  const severe = issues.find((issue) => issue.severity === "high")
  if (severe) {
    candidates.push({
      id: `project:${bookId}:severe-finding`,
      label: `Review: ${severe.title}`,
      description: `${severe.citation} · ${severe.suggestedFix}`,
      href: bookRoute("/author-loop#revision-control"),
      tone: "primary",
      priority: "severe_finding",
      fingerprint: `${severe.id}:${severe.status}`,
    })
  }
  if ((consensus?.summary.open_feedback_count ?? 0) > 0) {
    candidates.push({
      id: `project:${bookId}:beta-feedback`,
      label: "Triage fresh reader feedback",
      description: `${consensus?.summary.open_feedback_count} open signal(s) across ${consensus?.summary.hotspot_count} chapter hotspot(s).`,
      href: bookRoute("/author-loop#beta-consensus"),
      tone: "primary",
      priority: "fresh_beta_feedback",
      fingerprint: `${consensus?.summary.feedback_item_count}:${consensus?.summary.open_feedback_count}`,
    })
  }
  if (isShareReady) {
    candidates.push({
      id: `project:${bookId}:export`,
      label: "Create a share-ready draft",
      description: "No active review blockers are waiting. Capture a revision round, then export.",
      href: bookRoute("/export"),
      tone: "primary",
      priority: "export_share_ready",
      fingerprint: `ready:${book.total_chapters ?? 0}:${assignmentCount}`,
    })
  }
  if (!severe && (consensus?.summary.open_feedback_count ?? 0) === 0) {
    candidates.push({
      id: `project:${bookId}:manuscript`,
      label: "Continue the manuscript",
      description: "Return to the last active chapter and keep drafting.",
      href: bookRoute("/manuscript"),
      tone: "secondary",
      priority: book?.status === "ready" && !isShareReady ? "active_drafting" : "fallback",
      fingerprint: `draft:${book?.status ?? "pending"}:${book?.total_chapters ?? 0}`,
    })
  }
  return candidates
}

export function buildCharacterReviewStats(characters: Character[]) {
  const duplicateGroups = new Set<string>()
  let needsReviewCount = 0
  const names = new Map<string, string>()
  for (const character of characters) {
    const normalized = character.name.trim().toLowerCase()
    if (!normalized) continue
    const existing = names.get(normalized)
    if (existing && existing !== character.id) {
      duplicateGroups.add(existing)
      duplicateGroups.add(character.id)
    } else {
      names.set(normalized, character.id)
    }
    if (!character.description || (character.aliases?.length ?? 0) === 0) {
      needsReviewCount += 1
    }
  }
  return {
    totalCharacters: characters.length,
    duplicateCount: duplicateGroups.size,
    needsReviewCount,
  }
}

export function buildAuthorLoopSteps(params: {
  book: Book | null
  characters: Character[]
  storyHealth: StoryHealth | null
  issueCards: AuthorLoopIssueCard[]
  assignments: BetaReadAssignment[]
  selectedAssignment: BetaReadAssignmentDetail | null
}): AuthorLoopStep[] {
  const characterStats = buildCharacterReviewStats(params.characters)
  const activeAssignments = params.assignments.filter((assignment) => assignment.view_bucket === "active" || assignment.view_bucket === "scheduled")
  const feedbackCount = params.selectedAssignment?.feedback_items.length ?? 0
  const openFeedbackCount = params.selectedAssignment?.feedback_items.filter((item) => item.author_status === "open").length ?? 0
  const storyScore = params.storyHealth && params.storyHealth.available !== false
    ? params.storyHealth.score
    : null

  return [
    {
      id: "upload",
      label: "Upload manuscript",
      detail: params.book?.processing?.status && params.book.status !== "ready"
        ? "Upload complete. LoreVia is still processing the manuscript."
        : "Private upload with processing status and no public sharing in this step.",
      tone: params.book?.status === "ready" ? "ready" : "working",
    },
    {
      id: "bible",
      label: "Build character bible",
      detail: `${characterStats.totalCharacters} profiles, ${characterStats.duplicateCount} possible duplicates, ${characterStats.needsReviewCount} needing review.`,
      tone: characterStats.totalCharacters > 0 ? (characterStats.duplicateCount > 0 || characterStats.needsReviewCount > 0 ? "working" : "ready") : "attention",
    },
    {
      id: "continuity",
      label: "Run continuity scan",
      detail: params.storyHealth ? `${params.storyHealth.summary}` : "Scan ready once the manuscript finishes processing.",
      tone: storyScore === null ? "working" : storyScore >= 75 ? "ready" : storyScore >= 55 ? "working" : "attention",
    },
    {
      id: "issues",
      label: "Show cited contradictions/gaps",
      detail: `${params.issueCards.length} active issue${params.issueCards.length === 1 ? "" : "s"} with chapter citations and suggested fixes.`,
      tone: params.issueCards.length === 0 ? "working" : params.issueCards.some((card) => card.severity === "high") ? "attention" : "ready",
    },
    {
      id: "invite",
      label: "Invite beta reader",
      detail: activeAssignments.length > 0 ? `${activeAssignments.length} scoped beta invite${activeAssignments.length === 1 ? "" : "s"} active.` : "Set a full-book or chapter-range invite with a deadline.",
      tone: activeAssignments.length > 0 ? "ready" : "working",
    },
    {
      id: "feedback",
      label: "Collect scoped feedback",
      detail: feedbackCount > 0 ? `${feedbackCount} feedback item${feedbackCount === 1 ? "" : "s"}, ${openFeedbackCount} still open for author triage.` : "Reader comments, prompts, and confusing sections land in one scoped inbox.",
      tone: feedbackCount === 0 ? "working" : openFeedbackCount > 0 ? "attention" : "ready",
    },
  ]
}
