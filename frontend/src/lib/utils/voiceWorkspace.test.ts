import { describe, expect, it } from "vitest"

import {
  buildVoiceIssueNote,
  buildVoiceReviewNote,
  buildVoiceReviewSceneDraft,
  defaultVoiceSceneFolder,
} from "./voiceWorkspace"

describe("voice workspace utilities", () => {
  it("builds voice issue note content", () => {
    const note = buildVoiceIssueNote({
      character_name: "Iris",
      title: "Too formal",
      description: "Her dialogue reads colder than usual.",
      severity: "moderate",
      evidence: "She switches into legal language mid-scene.",
      suggestion: "Bring back the clipped humor from earlier chapters.",
    })

    expect(note.title).toBe("Voice: Iris - Too formal")
    expect(note.body).toContain("**Evidence:** She switches into legal language mid-scene.")
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
      issues: [],
    })

    expect(note.title).toBe("Voice Review - Chapter 7: Crossing the bridge")
    expect(note.body).toContain("**Reviewed characters:** Iris, Milo")
    expect(note.body).toContain("- Iris: 81% match | signals clipped cadence | closest alternate Milo (56%)")
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
        },
      ],
      existingPaths: ["scenes/voice/chapter-04/Chapter 4 Voice Review - The warning.md"],
    })

    expect(defaultVoiceSceneFolder(4)).toBe("scenes/voice/chapter-04")
    expect(draft.path).toBe("scenes/voice/chapter-04/Chapter 4 Voice Review - The warning 2.md")
    expect(draft.body).toContain("Detected issues:")
  })
})
