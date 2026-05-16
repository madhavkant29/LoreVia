import type { BetaReadAssignment, BetaReadAssignmentDetail } from "@/types/betaRead"
import type { Book, ChapterConsistencyReport, RevisionActionItem, RevisionBoard, RevisionIntelligence, StoryHealth, WriterWorkspace } from "@/types/book"
import type { Character } from "@/types/character"

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
  const storyScore = params.storyHealth?.score ?? 0

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
      tone: storyScore >= 75 ? "ready" : storyScore >= 55 ? "working" : "attention",
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
