import { describe, expect, it } from "vitest"

import {
  applyVoiceFindingDecision,
  buildVoiceIssueNote,
  buildVoiceReviewNote,
  buildVoiceReviewSceneDraft,
  countVoiceSourceCharacters,
  defaultVoiceSceneFolder,
  voiceReviewErrorMessage,
} from "./voiceWorkspace"
import type { VoiceConsistencyResponse } from "@/types/intelligence"

describe("voice workspace utilities", () => {
  it("counts Unicode source characters like the backend passage limit", () => {
    expect(countVoiceSourceCharacters("")).toBe(0)
    expect(countVoiceSourceCharacters("A😀B")).toBe(3)
    expect(countVoiceSourceCharacters("😀".repeat(12_000))).toBe(12_000)
  })
  it("shows public stream errors and explains incomplete responses", () => {
    expect(voiceReviewErrorMessage(new Error("503: Advisor stream failed — Review temporarily unavailable."))).toBe("Review temporarily unavailable.")
    expect(voiceReviewErrorMessage(new Error("Advisor stream ended before a final response arrived"))).toContain("full result")
    expect(voiceReviewErrorMessage(null)).toContain("Could not run")
  })
  it("builds voice issue note content", () => {
    const note = buildVoiceIssueNote({
      character_name: "Iris",
      title: "Too formal",
      description: "Her dialogue reads colder than usual.",
      severity: "moderate",
      evidence: "She switches into legal language mid-scene.",
      suggestion: "Bring back the clipped humor from earlier chapters.",
      submitted_excerpt: "That clause is void.",
      baseline_excerpt: "Come on, we can fix it.",
      baseline_chapter_number: 2,
      confidence: 0.82,
      revision_direction: "Keep her clipped humor while expressing the contract point.",
      intentionality_prompt: "Is the formal register deliberate here?",
    })

    expect(note.title).toBe("Voice: Iris - Too formal")
    expect(note.body).toContain("**Submitted excerpt:** That clause is void.")
    expect(note.body).toContain("**Baseline excerpt (chapter 2):** Come on, we can fix it.")
    expect(note.body).toContain("**Evidence strength:** 82%")
    expect(note.body).toContain("**Revision direction:** Keep her clipped humor")
    expect(note.body).toContain("**Intentionality question:** Is the formal register deliberate here?")
  })

  it("builds a summary note for a full voice review", () => {
    const note = buildVoiceReviewNote({
      chapterNumber: 7,
      chapterTitle: "Crossing the bridge",
      overallVerdict: "Mostly consistent with one drift point.",
      charactersReviewed: ["Iris", "Milo"],
      matches: [
        {
          character_name: "Iris",
          match_score: 81,
          strongest_signals: ["clipped cadence"],
          closest_other_character: "Milo",
          closest_other_score: 56,
        },
      ],
      issues: [{ character_name: "Iris", title: "Register shift", description: "The diction is unusually formal.", severity: "moderate", submitted_excerpt: "That clause is void.", baseline_excerpt: "Come on, we can fix it.", baseline_chapter_number: 2 }],
    })

    expect(note.title).toBe("Voice Review - Chapter 7: Crossing the bridge")
    expect(note.body).toContain("**Reviewed characters:** Iris, Milo")
    expect(note.body).toContain("- Iris: 81% match | signals clipped cadence | closest alternate Milo (56%)")
    expect(note.body).toContain("**Baseline excerpt (chapter 2):** Come on, we can fix it.")
  })

  it("builds unique scene drafts inside the voice workspace", () => {
    const draft = buildVoiceReviewSceneDraft({
      chapterNumber: 4,
      chapterTitle: "The warning",
      overallVerdict: "Voice drift detected.",
      sourceText: "A short passage.",
      issues: [
        {
          character_name: "Ava",
          title: "Missing sarcasm",
          description: "The line loses her bite.",
          severity: "minor",
          suggestion: "Sharpen the comeback.",
          submitted_excerpt: "I disagree.",
          baseline_excerpt: "Try me again, if you dare.",
          baseline_chapter_number: 1,
        },
      ],
      existingPaths: ["scenes/voice/chapter-04/Chapter 4 Voice Review - The warning.md"],
    })

    expect(defaultVoiceSceneFolder(4)).toBe("scenes/voice/chapter-04")
    expect(draft.path).toBe("scenes/voice/chapter-04/Chapter 4 Voice Review - The warning 2.md")
    expect(draft.body).toContain("Unresolved findings:")
    expect(draft.body).toContain("**Submitted excerpt:** I disagree.")
    expect(draft.body).toContain("**Baseline excerpt (chapter 1):** Try me again, if you dare.")
  })

  it("updates the verdict immediately after a saved decision without claiming a clean review", () => {
    const issue = { finding_key: "a".repeat(64), character_name: "Iris", title: "Register shift", description: "A possible shift.", severity: "moderate" as const, intentionality_prompt: "Deliberate?" }
    const result: VoiceConsistencyResponse = { review: { status: "partial_evidence", overall_verdict: "One possible shift.", issues: [issue] }, retrieved_passages: [], characters_reviewed: ["Iris"], warnings: [] }

    const decided = applyVoiceFindingDecision(result, issue.finding_key, "intentional")

    expect(decided.review.issues).toEqual([])
    expect(decided.suppressed_findings?.[0]).toMatchObject({ finding_key: issue.finding_key, decision: "intentional" })
    expect(decided.review.overall_verdict).toContain("listed separately")
    expect(decided.review.overall_verdict).toContain("review remains limited by the available evidence")
    expect(result.review.issues).toEqual([issue])
    expect(applyVoiceFindingDecision(decided, "missing", "incorrect")).toBe(decided)
  })

  it("keeps recorded decisions and their paired evidence in saved reviews", () => {
    const decidedIssue = { character_name: "Iris", title: "Register shift", description: "The line sounds more formal.", severity: "moderate" as const, decision: "intentional" as const, submitted_excerpt: "That clause is void.", baseline_excerpt: "Come on, we can fix it.", baseline_chapter_number: 2 }
    const note = buildVoiceReviewNote({ overallVerdict: "All findings have recorded decisions.", charactersReviewed: ["Iris"], issues: [], suppressedFindings: [decidedIssue], reviewStatus: "partial_evidence", matches: [] })
    const scene = buildVoiceReviewSceneDraft({ overallVerdict: "All findings have recorded decisions.", sourceText: "That clause is void.", issues: [], suppressedFindings: [decidedIssue], reviewStatus: "partial_evidence", existingPaths: [] })

    for (const body of [note.body, scene.body]) {
      expect(body).toContain("Review decision:** intentional")
      expect(body).toContain("**Submitted excerpt:** That clause is void.")
      expect(body).toContain("**Baseline excerpt (chapter 2):** Come on, we can fix it.")
      expect(body).not.toContain("No voice issues were flagged")
    }
    expect(note.body).toContain("No new unresolved voice findings")
    expect(scene.body).toContain("Unresolved findings: none; recorded decisions follow.")
  })
})
