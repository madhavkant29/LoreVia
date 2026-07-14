import { describe, expect, it } from "vitest"
import { renderToStaticMarkup } from "react-dom/server"

import { ProjectGlyph, SearchIcon } from "./LibraryClient.icons"

describe("LibraryClient icons", () => {
  it("renders accessible svg markup for shared library icons", () => {
    expect(renderToStaticMarkup(<SearchIcon className="text-test" />)).toContain("text-test")
    expect(renderToStaticMarkup(<ProjectGlyph glyph="moon" />)).toContain("viewBox=\"0 0 24 24\"")
    expect(renderToStaticMarkup(<ProjectGlyph glyph="star" />)).toContain("M12 4")
  })
})
