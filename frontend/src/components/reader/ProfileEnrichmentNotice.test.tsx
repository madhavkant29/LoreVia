import { describe, expect, it } from "vitest"
import { renderToStaticMarkup } from "react-dom/server"

import { ProfileEnrichmentNotice } from "./ProfileEnrichmentNotice"

describe("ProfileEnrichmentNotice", () => {
  const processing = { parser_diagnostics: { character_extraction: { totals: { invalid_profile_batches: 2 } } } }

  it("warns about incomplete profiles after a run and links to the Character Bible", () => {
    const markup = renderToStaticMarkup(<ProfileEnrichmentNotice processing={processing} bookId="book-1" isDark={false} />)
    expect(markup).toContain("Some character profiles are incomplete")
    expect(markup).toContain("2 profile evidence batches")
    expect(markup).toContain('href="/book-1/characters"')
    expect(markup).toContain("text-amber-950")
  })

  it("shows the warning in dark mode and hides it when all profiles were verified", () => {
    expect(renderToStaticMarkup(<ProfileEnrichmentNotice processing={processing} bookId="book-1" isDark />)).toContain("text-amber-100")
    expect(renderToStaticMarkup(<ProfileEnrichmentNotice processing={{}} bookId="book-1" isDark={false} />)).toBe("")
  })
})
