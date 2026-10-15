import { describe, expect, it } from "vitest"
import { metadataTextToList, normalizeSceneMetadata } from "./scenesPage.helpers"

describe("scene metadata input", () => {
  it("preserves an unfinished comma while typing another item", () => {
    expect(metadataTextToList("gate, ", true)).toEqual(["gate", ""])
    expect(metadataTextToList("gate, courier", true)).toEqual(["gate", "courier"])
    expect(metadataTextToList(" ", true)).toEqual([""])
  })
  it("removes blank entries when saving without dropping other metadata", () => {
    expect(normalizeSceneMetadata({ pov: "Nora", tags: [" gate ", "", "courier"], mood: ["tense", ""] })).toEqual({ pov: "Nora", tags: ["gate", "courier"], mood: ["tense"] })
    expect(normalizeSceneMetadata({})).toEqual({ tags: [], mood: [] })
    expect(metadataTextToList(", , ")).toEqual([])
  })
})
