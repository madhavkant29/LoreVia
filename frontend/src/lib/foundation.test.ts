import { afterEach, beforeEach, describe, expect, it } from "vitest"

import { canUseAuthorFeatures, isPaidTier, tierLabel } from "./billing/plans"
import { LEGAL_EMAIL, SUPPORT_EMAIL } from "./constants/contact"
import { TRUST_EFFECTIVE_DATE, TRUST_RESOURCE_LINKS } from "./constants/trust"
import { shouldSkipAuthBootstrap } from "./routes"
import {
  DEFAULT_OG_IMAGE,
  INDEXNOW_KEY_PATH,
  SITE_DESCRIPTION,
  SITE_NAME,
  SITE_URL,
  STATIC_PUBLIC_ROUTES,
  getIndexNowKey,
  getIndexNowKeyLocation,
  organizationJsonLd,
  toAbsoluteUrl,
  websiteJsonLd,
} from "./seo"
import { cn, highlightQuery, truncate } from "./utils/text"

describe("foundation utilities", () => {
  const originalIndexNowKey = process.env.INDEXNOW_KEY

  beforeEach(() => {
    process.env.INDEXNOW_KEY = originalIndexNowKey
  })

  afterEach(() => {
    process.env.INDEXNOW_KEY = originalIndexNowKey
  })

  it("merges tailwind class conflicts with cn", () => {
    expect(cn("px-2 py-1", "px-4")).toBe("py-1 px-4")
  })

  it("keeps non-conflicting classes with cn", () => {
    expect(cn("flex", "items-center", "gap-2")).toBe("flex items-center gap-2")
  })

  it("returns the original text when truncate is not needed", () => {
    expect(truncate("LoreVia", 20)).toBe("LoreVia")
  })

  it("returns the original text when truncate length matches exactly", () => {
    expect(truncate("LoreVia", 8)).toBe("LoreVia")
  })

  it("adds an ellipsis when truncate shortens text", () => {
    expect(truncate("LoreVia keeps long notes readable", 12)).toBe("LoreVia k...")
  })

  it("returns the original string when highlightQuery has no query", () => {
    expect(highlightQuery("Reader workspace", "")).toBe("Reader workspace")
  })

  it("wraps matches with mark tags in highlightQuery", () => {
    expect(highlightQuery("Reader workspace reader", "reader")).toBe("<mark>Reader</mark> workspace <mark>reader</mark>")
  })

  it("escapes regex characters in highlightQuery", () => {
    expect(highlightQuery("Use C++ for speed", "C++")).toBe("Use <mark>C++</mark> for speed")
  })

  it("preserves surrounding content in highlightQuery", () => {
    expect(highlightQuery("plot-thread planner", "thread")).toBe("plot-<mark>thread</mark> planner")
  })

  it("does not skip auth bootstrap for null pathnames", () => {
    expect(shouldSkipAuthBootstrap(null)).toBe(false)
  })

  it("skips auth bootstrap for static public pages", () => {
    expect(shouldSkipAuthBootstrap("/pricing")).toBe(true)
  })

  it("skips auth bootstrap for the Paddle checkout landing page", () => {
    expect(shouldSkipAuthBootstrap("/checkout")).toBe(true)
  })

  it("skips auth bootstrap for nested Paddle checkout routes", () => {
    expect(shouldSkipAuthBootstrap("/checkout/success")).toBe(true)
  })

  it("skips auth bootstrap for the public blog page", () => {
    expect(shouldSkipAuthBootstrap("/blog")).toBe(true)
  })

  it("skips auth bootstrap for public blog articles", () => {
    expect(shouldSkipAuthBootstrap("/blog/how-to-track-characters-in-a-novel")).toBe(true)
  })

  it("skips auth bootstrap for the answers hub and nested answer pages", () => {
    expect(shouldSkipAuthBootstrap("/answers")).toBe(true)
    expect(shouldSkipAuthBootstrap("/answers/how-do-i-track-character-arcs")).toBe(true)
  })

  it("skips auth bootstrap for the demo hub and nested demo pages", () => {
    expect(shouldSkipAuthBootstrap("/demo")).toBe(true)
    expect(shouldSkipAuthBootstrap("/demo/gregor-samsa-character-tracker")).toBe(true)
  })

  it("skips auth bootstrap for exact auth-excluded routes", () => {
    expect(shouldSkipAuthBootstrap("/login")).toBe(true)
  })

  it("skips auth bootstrap for nested auth-excluded routes", () => {
    expect(shouldSkipAuthBootstrap("/verify-email/success")).toBe(true)
  })

  it("does not skip auth bootstrap for authenticated app routes", () => {
    expect(shouldSkipAuthBootstrap("/library")).toBe(false)
  })

  it("resolves root-relative paths with toAbsoluteUrl", () => {
    expect(toAbsoluteUrl("/pricing")).toBe("https://getlorevia.com/pricing")
  })

  it("resolves relative paths with toAbsoluteUrl", () => {
    expect(toAbsoluteUrl("status")).toBe("https://getlorevia.com/status")
  })

  it("returns a trimmed indexnow key when configured", () => {
    process.env.INDEXNOW_KEY = "  lorevia-key  "
    expect(getIndexNowKey()).toBe("lorevia-key")
  })

  it("returns null for blank indexnow keys", () => {
    process.env.INDEXNOW_KEY = "   "
    expect(getIndexNowKey()).toBeNull()
  })

  it("builds the canonical indexnow key location", () => {
    expect(getIndexNowKeyLocation()).toBe("https://getlorevia.com/indexnow-key.txt")
  })

  it("exposes the expected site constants", () => {
    expect(SITE_URL).toBe("https://getlorevia.com")
    expect(SITE_NAME).toBe("LoreVia")
    expect(DEFAULT_OG_IMAGE).toBe("/og-image.png")
  })

  it("includes a stable site description", () => {
    expect(SITE_DESCRIPTION).toContain("story workspace")
  })

  it("includes public marketing routes in static public routes", () => {
    expect(STATIC_PUBLIC_ROUTES).toContain("/")
    expect(STATIC_PUBLIC_ROUTES).toContain("/blog")
    expect(STATIC_PUBLIC_ROUTES).toContain("/answers")
    expect(STATIC_PUBLIC_ROUTES).toContain("/demo")
    expect(STATIC_PUBLIC_ROUTES).toContain("/pricing")
  })

  it("exposes the indexnow key path constant", () => {
    expect(INDEXNOW_KEY_PATH).toBe("/indexnow-key.txt")
  })

  it("builds website json-ld with the publisher logo", () => {
    expect(websiteJsonLd.publisher.logo).toBe("https://getlorevia.com/logoandtext.png")
  })

  it("builds website json-ld with the site name", () => {
    expect(websiteJsonLd.name).toBe("LoreVia")
  })

  it("builds organization json-ld with the canonical logo", () => {
    expect(organizationJsonLd.logo).toBe("https://getlorevia.com/logoandtext.png")
  })

  it("marks author tiers as able to use author features", () => {
    expect(canUseAuthorFeatures("author")).toBe(true)
  })

  it("marks admin tiers as able to use author features", () => {
    expect(canUseAuthorFeatures("admin")).toBe(true)
  })

  it("does not mark invited beta-reader tiers as able to use author features", () => {
    expect(canUseAuthorFeatures("collaborator")).toBe(false)
  })

  it("does not treat invited beta-reader access as a paid tier", () => {
    expect(isPaidTier("collaborator")).toBe(false)
  })

  it("does not treat free as a paid tier", () => {
    expect(isPaidTier("free")).toBe(false)
  })

  it("returns an invited beta reader label", () => {
    expect(tierLabel("collaborator")).toBe("Invited beta reader")
  })

  it("returns an Author label", () => {
    expect(tierLabel("author")).toBe("Author")
  })

  it("returns an Architect label", () => {
    expect(tierLabel("architect")).toBe("Architect")
  })

  it("returns an Admin label", () => {
    expect(tierLabel("admin")).toBe("Admin")
  })

  it("returns a Free label by default", () => {
    expect(tierLabel(undefined)).toBe("Free")
  })

  it("exposes the support email constant", () => {
    expect(SUPPORT_EMAIL).toBe("support@getlorevia.com")
  })

  it("exposes the legal email constant", () => {
    expect(LEGAL_EMAIL).toBe("legal@getlorevia.com")
  })

  it("exposes the trust effective date", () => {
    expect(TRUST_EFFECTIVE_DATE).toBe("May 6, 2026")
  })

  it("includes the security resource link in the trust resources", () => {
    expect(TRUST_RESOURCE_LINKS.some((link) => link.href === "/compliance" && link.label === "Security")).toBe(true)
  })
})
