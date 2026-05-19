import { describe, expect, it } from "vitest"

import { resolveReaderFontStack } from "./readerTypography"

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
})
