import { renderToStaticMarkup } from "react-dom/server"
import { describe, expect, it } from "vitest"

import { PublicContextChrome } from "./PublicContextChrome"

describe("PublicContextChrome", () => {
  it("keeps public navigation distinct and provides a private workspace return", () => {
    const markup = renderToStaticMarkup(<PublicContextChrome />)

    expect(markup).toContain('aria-label="Public navigation"')
    expect(markup).toContain('/logoandtext.png')
    expect(markup).not.toContain("invert")
    expect(markup).toContain('alt="LoreVia"')
    expect(markup).toContain('href="/public/forum"')
    expect(markup).toContain('href="/library"')
    expect(markup).toContain('aria-label="Switch to dark mode"')
    expect(markup).not.toContain("Settings")
  })
})
