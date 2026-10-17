import { describe, expect, it, vi } from "vitest"

vi.mock("@/lib/api/public.server", () => ({
  listPublicBooksServer: vi.fn(async () => []),
  listPublicForumPostsServer: vi.fn(async () => ({ items: [] })),
}))

import sitemap from "./sitemap"

describe("sitemap", () => {
  it("uses content modification dates for dynamic editorial pages", async () => {
    const entries = await sitemap()

    expect(entries).toContainEqual(
      expect.objectContaining({
        url: "https://getlorevia.com/blog/how-to-track-characters-in-a-novel",
        lastModified: new Date("2026-08-09T00:00:00.000Z"),
        changeFrequency: "monthly",
        priority: 0.85,
      }),
    )
    expect(entries).toContainEqual(
      expect.objectContaining({
        url: "https://getlorevia.com/answers/how-do-i-track-character-arcs",
        lastModified: new Date("2026-08-09T00:00:00.000Z"),
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
