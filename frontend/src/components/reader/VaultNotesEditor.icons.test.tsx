import { describe, expect, it } from "vitest"
import { renderToStaticMarkup } from "react-dom/server"

import { IconChevron, IconDocument, IconSearch, IconStar, IconUpload } from "./VaultNotesEditor.icons"

describe("VaultNotesEditor icons", () => {
  it("renders shared note editor icons with configurable state", () => {
    expect(renderToStaticMarkup(<IconSearch />)).toContain("viewBox=\"0 0 24 24\"")
    expect(renderToStaticMarkup(<IconUpload className="rotate-180" />)).toContain("rotate-180")
    expect(renderToStaticMarkup(<IconDocument small />)).toContain("shrink-0")
    expect(renderToStaticMarkup(<IconChevron open />)).toContain("rotate-90")
    expect(renderToStaticMarkup(<IconStar filled />)).toContain("currentColor")
  })
})
