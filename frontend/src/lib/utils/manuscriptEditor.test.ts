import { describe, expect, it } from "vitest"

import {
  buildCommentNoteBody,
  buildCommentNoteTitle,
  buildManuscriptAutosaveKey,
  buildSceneAutosaveKey,
  buildSceneOutline,
  countWords,
  formatReadingTimeLabel,
  isCommentNoteTitle,
  parseAutosaveDraft,
  parseSceneAutosaveDraft,
  serializeAutosaveDraft,
  serializeSceneAutosaveDraft,
} from "./manuscriptEditor"

describe("manuscript editor utilities", () => {
  it("counts words and formats reading time labels", () => {
    expect(countWords("LoreVia keeps the draft moving")).toBe(5)
    expect(formatReadingTimeLabel(0)).toBe("0 min read")
    expect(formatReadingTimeLabel(7)).toBe("7 min read")
    expect(formatReadingTimeLabel(75)).toBe("1 hr 15 min read")
  })

  it("builds a scene outline from scene breaks", () => {
    const scenes = buildSceneOutline([
      "The storm rolled in over the harbor.",
      "",
      "* * *",
      "",
      "Mara found the key under the sink.",
      "",
      "---",
      "",
      "They opened the cellar door together.",
    ].join("\n"))

    expect(scenes).toHaveLength(3)
    expect(scenes.map((scene) => scene.title)).toEqual(["Scene 1", "Scene 2", "Scene 3"])
    expect(scenes[0]?.excerpt).toContain("The storm rolled in")
    expect(scenes[1]?.wordCount).toBeGreaterThan(0)
  })

  it("serializes and parses autosave drafts safely", () => {
    const raw = serializeAutosaveDraft({
      title: "Chapter 7",
      text: "Saved locally",
      html: "<p>Saved locally</p>",
      updatedAt: "2026-05-14T10:00:00.000Z",
    })

    expect(parseAutosaveDraft(raw)).toEqual({
      title: "Chapter 7",
      text: "Saved locally",
      html: "<p>Saved locally</p>",
      updatedAt: "2026-05-14T10:00:00.000Z",
    })
    expect(parseAutosaveDraft("{bad json")).toBeNull()
    expect(buildManuscriptAutosaveKey("book-1", 9)).toBe("lorevia:manuscript-autosave:book-1:chapter:9")
  })

  it("serializes and parses scene autosave drafts safely", () => {
    const raw = serializeSceneAutosaveDraft({
      title: "Rooftop Meeting",
      description: "A rain-soaked confrontation.",
      body: "The city hissed under the rain.",
      chapterNumber: 3,
      updatedAt: "2026-05-14T10:05:00.000Z",
    })

    expect(parseSceneAutosaveDraft(raw)).toEqual({
      title: "Rooftop Meeting",
      description: "A rain-soaked confrontation.",
      body: "The city hissed under the rain.",
      chapterNumber: 3,
      updatedAt: "2026-05-14T10:05:00.000Z",
    })
    expect(parseSceneAutosaveDraft("{bad json")).toBeNull()
    expect(buildSceneAutosaveKey("book-1", "scene-7")).toBe("lorevia:scene-autosave:book-1:scene:scene-7")
  })

  it("formats comment notes so they can be separated from regular notes", () => {
    const title = buildCommentNoteTitle("A longer selected passage from the manuscript that should be trimmed down.")
    const body = buildCommentNoteBody("A tense exchange at the harbor.", "Flag the motivation shift here.")

    expect(title).toMatch(/^Comment:/)
    expect(isCommentNoteTitle(title)).toBe(true)
    expect(isCommentNoteTitle("Research note")).toBe(false)
    expect(body).toContain("<blockquote>A tense exchange at the harbor.</blockquote>")
    expect(body).toContain("Flag the motivation shift here.")
  })
})
