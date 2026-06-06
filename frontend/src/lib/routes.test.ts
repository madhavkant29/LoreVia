import { describe, expect, it } from "vitest"

import { resolveSafeAuthNextPath, shouldHideSiteFooter, shouldSkipAuthBootstrap } from "./routes"

describe("route helpers", () => {
  it("keeps auth bootstrap disabled on public and auth-entry pages", () => {
    expect(shouldSkipAuthBootstrap("/login")).toBe(true)
    expect(shouldSkipAuthBootstrap("/blog/how-to-revise")).toBe(true)
    expect(shouldSkipAuthBootstrap("/public/forum")).toBe(true)
    expect(shouldSkipAuthBootstrap("/library")).toBe(false)
  })

  it("hides the site footer for book workspace routes", () => {
    expect(shouldHideSiteFooter("/sky-of-ash--book-1")).toBe(true)
    expect(shouldHideSiteFooter("/sky-of-ash--book-1/manuscript")).toBe(true)
    expect(shouldHideSiteFooter("/pricing")).toBe(false)
  })

  it("resolves safe private auth next paths", () => {
    expect(resolveSafeAuthNextPath("/library")).toBe("/library")
    expect(resolveSafeAuthNextPath("/library?sort=recent")).toBe("/library?sort=recent")
    expect(resolveSafeAuthNextPath("/complete-username")).toBe("/complete-username")
    expect(resolveSafeAuthNextPath("/sky-of-ash--book-1/manuscript#draft")).toBe(
      "/sky-of-ash--book-1/manuscript#draft"
    )
  })

  it("rejects external, auth-entry, and public auth next paths", () => {
    expect(resolveSafeAuthNextPath("https://evil.example/library")).toBe("/library")
    expect(resolveSafeAuthNextPath("//evil.example/library")).toBe("/library")
    expect(resolveSafeAuthNextPath("/login")).toBe("/library")
    expect(resolveSafeAuthNextPath("/blog/how-to-revise")).toBe("/library")
    expect(resolveSafeAuthNextPath("/checkout/success")).toBe("/library")
    expect(resolveSafeAuthNextPath("/copyright")).toBe("/library")
    expect(resolveSafeAuthNextPath("/public/forum")).toBe("/library")
    expect(resolveSafeAuthNextPath(null)).toBe("/library")
  })
})
