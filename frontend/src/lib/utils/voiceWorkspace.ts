import type { VoiceConsistencyIssue, VoiceConsistencyMatch } from "@/types/intelligence"

import { buildUniqueWorkspacePathFromCandidate, sanitizeWorkspaceTitle } from "./workspacePaths"

export function defaultVoiceSceneFolder(chapterNumber: number | null | undefined) {
  if (typeof chapterNumber === "number" && chapterNumber > 0) {
    return `scenes/voice/chapter-${String(chapterNumber).padStart(2, "0")}`
  }
  return "scenes/voice/unassigned"
}

export function buildVoiceIssueNote(issue: Pick<VoiceConsistencyIssue, "character_name" | "title" | "description" | "severity" | "evidence" | "suggestion">) {
  return {
    title: `Voice: ${issue.character_name} - ${issue.title}`,
    body: [
      `**Voice Issue: ${issue.character_name} - ${issue.title}**`,
      "",
      issue.description,
      issue.evidence ? `**Evidence:** ${issue.evidence}` : null,
      issue.suggestion ? `**Suggestion:** ${issue.suggestion}` : null,
      issue.severity ? `**Severity:** ${issue.severity}` : null,
    ].filter(Boolean).join("\n\n"),
  }
}

export function buildVoiceReviewNote(options: {
  chapterNumber?: number | null
  chapterTitle?: string | null
  overallVerdict: string
  charactersReviewed: string[]
  issues: Array<Pick<VoiceConsistencyIssue, "character_name" | "title" | "description" | "severity" | "evidence" | "suggestion">>
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
      if (issue.evidence) lines.push(`  Evidence: ${issue.evidence}`)
      if (issue.suggestion) lines.push(`  Suggestion: ${issue.suggestion}`)
    }
  } else {
    lines.push("No voice issues were flagged in this review.")
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
  issues: Array<Pick<VoiceConsistencyIssue, "character_name" | "title" | "description" | "severity" | "suggestion">>
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
    options.issues.length ? "Detected issues:" : "Detected issues: none",
    ...options.issues.map((issue) =>
      `- ${issue.character_name}: ${issue.title} (${issue.severity})${issue.suggestion ? ` - ${issue.suggestion}` : ""}`
    ),
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
