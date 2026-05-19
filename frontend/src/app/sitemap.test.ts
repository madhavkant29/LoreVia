import { describe, expect, it } from "vitest"

import sitemap from "./sitemap"

describe("sitemap", () => {
  it("uses content publish dates for dynamic seo pages", async () => {
    const entries = await sitemap()

    expect(entries).toContainEqual(
      expect.objectContaining({
        url: "https://getlorevia.com/blog/how-to-track-characters-in-a-novel",
        lastModified: new Date("2026-05-14T00:00:00.000Z"),
        changeFrequency: "monthly",
        priority: 0.85,
      }),
    )
    expect(entries).toContainEqual(
      expect.objectContaining({
        url: "https://getlorevia.com/answers/how-do-i-track-character-arcs",
        lastModified: new Date("2026-05-14T00:00:00.000Z"),
        changeFrequency: "monthly",
        priority: 0.72,
      }),
    )
  })

  it("includes public discovery hubs in the sitemap", async () => {
    const entries = await sitemap()

    expect(entries).toContainEqual(
      expect.objectContaining({
        url: "https://getlorevia.com/public",
      }),
    )
    expect(entries).toContainEqual(
      expect.objectContaining({
        url: "https://getlorevia.com/public/forum",
      }),
    )
  })
})
