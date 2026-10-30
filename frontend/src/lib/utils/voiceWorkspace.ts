import type { VoiceConsistencyIssue, VoiceConsistencyMatch, VoiceConsistencyResponse, VoiceReviewDecision } from "@/types/intelligence"

import { getApiErrorDetail } from "./apiErrors"
import { buildUniqueWorkspacePathFromCandidate, sanitizeWorkspaceTitle } from "./workspacePaths"

export function countVoiceSourceCharacters(text: string): number {
  return Array.from(text).length
}

export function voiceReviewErrorMessage(error: unknown): string {
  const detail = getApiErrorDetail(error)
  if (detail) return detail
  if (error instanceof Error) {
    const streamFailure = error.message.match(/^\d{3}: Advisor stream failed(?: — (.+))?$/)
    if (streamFailure?.[1]) return streamFailure[1]
    if (error.message === "Advisor stream ended before a final response arrived") {
      return "Voice review ended before the full result arrived. Please try again."
    }
    if (error.message === "Advisor stream is unavailable in this browser") {
      return "Live voice review is unavailable in this browser. Please try another browser."
    }
  }
  return "Could not run the voice review right now. Please try again."
}

export function defaultVoiceSceneFolder(chapterNumber: number | null | undefined) {
  if (typeof chapterNumber === "number" && chapterNumber > 0) {
    return `scenes/voice/chapter-${String(chapterNumber).padStart(2, "0")}`
  }
  return "scenes/voice/unassigned"
}

type VoiceNoteIssue = Pick<VoiceConsistencyIssue, "character_name" | "title" | "description" | "severity"> & Partial<Pick<VoiceConsistencyIssue,
  "classification" | "submitted_excerpt" | "baseline_excerpt" | "baseline_chapter_number" | "confidence" | "revision_direction" | "intentionality_prompt" | "evidence" | "suggestion" | "decision">>

function voiceIssueEvidenceLines(issue: VoiceNoteIssue): string[] {
  return [
    issue.classification ? `**Classification:** ${issue.classification.replace(/_/g, " ")}` : null,
    issue.decision ? `**Review decision:** ${issue.decision}` : null,
    issue.submitted_excerpt ? `**Submitted excerpt:** ${issue.submitted_excerpt}` : null,
    issue.baseline_excerpt ? `**Baseline excerpt${typeof issue.baseline_chapter_number === "number" ? ` (chapter ${issue.baseline_chapter_number})` : ""}:** ${issue.baseline_excerpt}` : null,
    typeof issue.confidence === "number" ? `**Evidence strength:** ${Math.round(issue.confidence * 100)}%` : null,
    issue.revision_direction ? `**Revision direction:** ${issue.revision_direction}` : null,
    issue.intentionality_prompt ? `**Intentionality question:** ${issue.intentionality_prompt}` : null,
    issue.evidence && !issue.submitted_excerpt ? `**Evidence:** ${issue.evidence}` : null,
    issue.suggestion && !issue.revision_direction ? `**Suggestion:** ${issue.suggestion}` : null,
  ].filter((line): line is string => !!line)
}

export function applyVoiceFindingDecision<T extends VoiceConsistencyResponse>(result: T, findingKey: string, decision: VoiceReviewDecision): T {
  const issue = result.review.issues.find((item) => item.finding_key === findingKey)
  if (!issue) return result
  const issues = result.review.issues.filter((item) => item.finding_key !== findingKey)
  const suppressed = [...(result.suppressed_findings ?? []), { ...issue, decision }]
  const overallVerdict = issues.length
    ? `New voice findings to review: ${issues.length}. Previously reviewed findings shown below: ${suppressed.length}.`
    : result.review.status === "partial_evidence"
      ? "No new unresolved voice findings. Previously reviewed findings are listed separately, but the review remains limited by the available evidence."
      : "No new unresolved voice findings. All supported findings in this review have recorded decisions."
  return { ...result, review: { ...result.review, issues, overall_verdict: overallVerdict }, suppressed_findings: suppressed }
}

export function buildVoiceIssueNote(issue: VoiceNoteIssue) {
  return {
    title: `Voice: ${issue.character_name} - ${issue.title}`,
    body: [
      `**Voice Issue: ${issue.character_name} - ${issue.title}**`,
      "",
      issue.description,
      ...voiceIssueEvidenceLines(issue),
      issue.severity ? `**Severity:** ${issue.severity}` : null,
    ].filter(Boolean).join("\n\n"),
  }
}

export function buildVoiceReviewNote(options: {
  chapterNumber?: number | null
  chapterTitle?: string | null
  overallVerdict: string
  charactersReviewed: string[]
  issues: VoiceNoteIssue[]
  suppressedFindings?: VoiceNoteIssue[]
  reviewStatus?: VoiceConsistencyResponse["review"]["status"]
  matches: Array<Pick<VoiceConsistencyMatch, "character_name" | "match_score" | "strongest_signals" | "closest_other_character" | "closest_other_score">>
}) {
  const heading = typeof options.chapterNumber === "number"
    ? `Voice Review - Chapter ${options.chapterNumber}`
    : "Voice Review"
  const title = options.chapterTitle?.trim() ? `${heading}: ${options.chapterTitle.trim()}` : heading

  const lines = [
    `**Overall verdict:** ${options.overallVerdict}`,
    options.charactersReviewed.length ? `**Reviewed characters:** ${options.charactersReviewed.join(", ")}` : null,
  ].filter(Boolean)

  if (options.matches.length) {
    lines.push("**Voice matches**")
    for (const match of options.matches) {
      lines.push(
        [
          `- ${match.character_name}: ${match.match_score}% match`,
          match.strongest_signals.length ? `signals ${match.strongest_signals.join(", ")}` : null,
          match.closest_other_character
            ? `closest alternate ${match.closest_other_character}${typeof match.closest_other_score === "number" ? ` (${match.closest_other_score}%)` : ""}`
            : null,
        ].filter(Boolean).join(" | ")
      )
    }
  }

  if (options.issues.length) {
    lines.push("**Issues**")
    for (const issue of options.issues) {
      lines.push(`- ${issue.character_name}: ${issue.title} (${issue.severity})`)
      lines.push(`  ${issue.description}`)
      lines.push(...voiceIssueEvidenceLines(issue).map((line) => `  ${line}`))
    }
  } else {
    lines.push(options.suppressedFindings?.length
      ? "No new unresolved voice findings; recorded decisions are listed below."
      : options.reviewStatus === "partial_evidence" || options.reviewStatus === "insufficient_evidence"
        ? "No complete voice verdict was made; review the limitations before drawing a conclusion."
        : "No supported character voice issues were found in the reviewed passage.")
  }

  if (options.suppressedFindings?.length) {
    lines.push("**Previously reviewed findings**")
    for (const issue of options.suppressedFindings) {
      lines.push(`- ${issue.character_name}: ${issue.title} (${issue.severity})`)
      lines.push(`  ${issue.description}`)
      lines.push(...voiceIssueEvidenceLines(issue).map((line) => `  ${line}`))
    }
  }

  return {
    title,
    body: lines.join("\n"),
  }
}

export function buildVoiceReviewSceneDraft(options: {
  chapterNumber?: number | null
  chapterTitle?: string | null
  overallVerdict: string
  sourceText: string
  issues: VoiceNoteIssue[]
  suppressedFindings?: VoiceNoteIssue[]
  reviewStatus?: VoiceConsistencyResponse["review"]["status"]
  existingPaths: string[]
}) {
  const chapterLabel = typeof options.chapterNumber === "number" ? `Chapter ${options.chapterNumber}` : "Voice Review"
  const titleBase = options.chapterTitle?.trim()
    ? `${chapterLabel} Voice Review - ${options.chapterTitle.trim()}`
    : `${chapterLabel} Voice Review`
  const title = sanitizeWorkspaceTitle(titleBase, "Voice Review")
  const folder = defaultVoiceSceneFolder(options.chapterNumber ?? null)
  const candidatePath = `${folder}/${title}.md`
  const path = buildUniqueWorkspacePathFromCandidate(options.existingPaths, candidatePath)
  const body = [
    `# ${title}`,
    "",
    `Overall verdict: ${options.overallVerdict}`,
    "",
    "Source passage:",
    options.sourceText.trim(),
    "",
    options.issues.length ? "Unresolved findings:" : options.suppressedFindings?.length ? "Unresolved findings: none; recorded decisions follow." : options.reviewStatus === "partial_evidence" || options.reviewStatus === "insufficient_evidence" ? "No complete voice verdict; review the limitations before drawing a conclusion." : "No supported findings in the reviewed passage.",
    ...options.issues.flatMap((issue) => [
      `- ${issue.character_name}: ${issue.title} (${issue.severity})`,
      `  ${issue.description}`,
      ...voiceIssueEvidenceLines(issue).map((line) => `  ${line}`),
    ]),
    ...(options.suppressedFindings?.length ? ["", "Previously reviewed findings:", ...options.suppressedFindings.flatMap((issue) => [
      `- ${issue.character_name}: ${issue.title} (${issue.severity})`,
      `  ${issue.description}`,
      ...voiceIssueEvidenceLines(issue).map((line) => `  ${line}`),
    ])] : []),
  ].join("\n")

  return {
    title,
    description: "Voice consistency review snapshot saved from the dedicated voice workspace.",
    body,
    path,
    chapter_number: options.chapterNumber ?? null,
    status: options.chapterNumber ? "assigned" : "unassigned",
  }
}
