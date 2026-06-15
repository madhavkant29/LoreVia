import { describe, expect, it } from "vitest"

import { chapterKindLabel, chapterKindShortLabel, formatIndex } from "./chapterLabels"

describe("chapter label utils", () => {
  it("formats chapter numbers in supported index styles", () => {
    expect(formatIndex(12)).toBe("12")
    expect(formatIndex(14, "roman-upper")).toBe("XIV")
    expect(formatIndex(14, "roman-lower")).toBe("xiv")
    expect(formatIndex(28, "alpha-upper")).toBe("AB")
    expect(formatIndex(28, "alpha-lower")).toBe("ab")
  })

  it("falls back to plain numbers for unsupported or out-of-range indexes", () => {
    expect(formatIndex(0, "roman-upper")).toBe("0")
    expect(formatIndex(4000, "roman-lower")).toBe("4000")
    expect(formatIndex(-1, "alpha-upper")).toBe("-1")
    expect(formatIndex(7, "unknown")).toBe("7")
  })

  it("builds long and short chapter labels with custom unit text", () => {
    expect(chapterKindLabel("chapter", 3, "Part", "roman-upper")).toBe("Part III")
    expect(chapterKindShortLabel(undefined, 27, "Pt.", "alpha-lower")).toBe("Pt. aa")
  })

  it("returns canonical labels for front and back matter", () => {
    expect(chapterKindLabel("title_page", null)).toBe("Title Page")
    expect(chapterKindShortLabel("toc", 1)).toBe("Table of Contents")
  })

  it("humanizes unknown chapter kinds defensively", () => {
    expect(chapterKindLabel("bonus_scene" as never, null)).toBe("Bonus Scene")
    expect(chapterKindShortLabel("author_note" as never, null)).toBe("Author Note")
  })
})
