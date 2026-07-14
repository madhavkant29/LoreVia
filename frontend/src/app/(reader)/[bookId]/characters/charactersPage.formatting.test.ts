import { afterEach, describe, expect, it, vi } from "vitest"

import {
  characterInitial,
  downloadBlob,
  formatChapterAppearanceText,
  formatChapterRange,
  formatPercent,
  formatRelationshipType,
  formatResolverStatus,
  formatRole,
  formatRoleFilterLabel,
  formatStatus,
  formatTraitLabel,
  listToString,
  normalizeText,
  parsePartitionTargets,
  parsePositiveInteger,
  slugify,
  stringToList,
} from "./charactersPage.helpers"

describe("characters page formatting helpers", () => {
  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it("normalizes comma lists and partition target rows", () => {
    expect(listToString(["Mira", "Jon"])).toBe("Mira, Jon")
    expect(listToString(undefined)).toBe("")
    expect(stringToList(" Mira, Jon,, Sefa ")).toEqual(["Mira", "Jon", "Sefa"])
    expect(parsePartitionTargets("Mira | M, Mir\n\nJon")).toEqual([
      { name: "Mira", aliases: ["M", "Mir"] },
      { name: "Jon", aliases: [] },
    ])
  })

  it("parses positive integers and falls back for invalid input", () => {
    expect(parsePositiveInteger("4")).toBe(4)
    expect(parsePositiveInteger("0", 7)).toBe(7)
    expect(parsePositiveInteger("not-a-number", 2)).toBe(2)
  })

  it("formats display text consistently", () => {
    expect(normalizeText(" Mira ")).toBe("mira")
    expect(slugify("Mira & Jon!")).toBe("mira-jon")
    expect(characterInitial("")).toBe("?")
    expect(characterInitial(" mira")).toBe("M")
    expect(formatPercent(0.876)).toBe("88%")
    expect(formatPercent(null)).toBe("Unknown")
    expect(formatResolverStatus(null)).toBe("needs review")
    expect(formatResolverStatus("pending_review")).toBe("pending review")
    expect(formatRole("mc")).toBe("Primary character")
    expect(formatRole("sc")).toBe("Supporting character")
    expect(formatRole("background")).toBe("Minor character")
    expect(formatRole(null)).toBe("Character")
    expect(formatRoleFilterLabel("mc")).toBe("main")
    expect(formatRoleFilterLabel("sc")).toBe("supporting")
    expect(formatRoleFilterLabel("background")).toBe("minor")
    expect(formatRoleFilterLabel(null)).toBe("unclassified")
    expect(formatTraitLabel("hair_color")).toBe("Hair Color")
    expect(formatStatus("deceased")).toBe("Deceased")
    expect(formatStatus("alive")).toBe("Active")
    expect(formatRelationshipType("political_ally")).toBe("Political Ally")
    expect(formatRelationshipType(null)).toBe("Connection")
    expect(formatChapterRange(null, null)).toBe("Chapter range unknown")
    expect(formatChapterRange(2, null)).toBe("Ch. 2")
    expect(formatChapterRange(2, 5)).toBe("Ch. 2-5")
    expect(formatChapterAppearanceText(2, new Map([[2, "Storm Front"]]))).toBe("Chapter 2 / Storm Front")
    expect(formatChapterAppearanceText(3, new Map([[2, "Storm Front"]]))).toBe("Chapter 3")
    expect(formatChapterAppearanceText(null, new Map())).toBe("Chapter unknown")
  })

  it("downloads blobs through a temporary object URL", () => {
    const click = vi.fn()
    const anchor = { href: "", download: "", click } as unknown as HTMLAnchorElement
    const createObjectURL = vi.fn(() => "blob:character-card")
    const revokeObjectURL = vi.fn()
    vi.stubGlobal("URL", { ...URL, createObjectURL, revokeObjectURL })
    vi.spyOn(document, "createElement").mockReturnValue(anchor)

    const blob = new Blob(["card"])
    downloadBlob(blob, "mira-card.pdf")

    expect(createObjectURL).toHaveBeenCalledWith(blob)
    expect(anchor.href).toBe("blob:character-card")
    expect(anchor.download).toBe("mira-card.pdf")
    expect(click).toHaveBeenCalledTimes(1)
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:character-card")
  })
})
