import { describe, expect, it } from "vitest"

import { isReaderFontFamily, resolveReaderFontStack } from "./readerTypography"

describe("reader typography", () => {
  it("keeps the classic serif stack for published reading", () => {
    expect(resolveReaderFontStack("serif", "published")).toContain("Georgia")
  })

  it("preserves the selected sans stack in published reading", () => {
    expect(resolveReaderFontStack("sans", "published")).toContain("Space Grotesk")
  })

  it("preserves the selected mono stack in published reading", () => {
    expect(resolveReaderFontStack("mono", "published")).toContain("SFMono-Regular")
  })

  it("uses the relaxed serif stack outside published mode", () => {
    expect(resolveReaderFontStack("serif", "relaxed")).toContain("Newsreader")
  })

  it("includes Monotype Italian Old Style Pro in the reader font stack", () => {
    expect(resolveReaderFontStack("italian-old-style", "published")).toContain("Monotype Italian Old Style Pro Regular")
  })

  it("includes EB Garamond in the reader font stack", () => {
    expect(resolveReaderFontStack("eb-garamond", "published")).toContain("EB Garamond")
  })

  it("validates supported reader font values", () => {
    expect(isReaderFontFamily("eb-garamond")).toBe(true)
    expect(isReaderFontFamily("comic-sans")).toBe(false)
  })
})
