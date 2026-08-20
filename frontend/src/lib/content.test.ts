import { describe, expect, it } from "vitest"

import {
  answerPages,
  blogArticles,
  demoPages,
  getAllPublicContentEntries,
  getAllPublicContentPaths,
  getAnswerPageBySlug,
  getAnswersByArticleSlug,
  getBlogArticleBySlug,
  getContentWordCount,
  getDemoPageBySlug,
  getLatestContentPublishedAt,
} from "./content"

describe("content helpers", () => {
  it("returns a blog article by slug", () => {
    expect(getBlogArticleBySlug("how-to-track-characters-in-a-novel")?.title).toBe(
      "How to Keep Track of Characters in a Novel"
    )
  })

  it("returns an answer page by slug", () => {
    expect(getAnswerPageBySlug("how-do-i-track-character-arcs")?.question).toBe(
      "How Do I Track Character Arcs?"
    )
  })

  it("returns a demo page by slug", () => {
    expect(getDemoPageBySlug("dracula-story-timeline-tracker")?.sourceWork).toBe("Dracula")
  })

  it("groups answers by their parent article", () => {
    const answers = getAnswersByArticleSlug("how-to-avoid-continuity-errors-when-writing-a-novel")

    expect(answers.map((answer) => answer.slug)).toEqual([
      "how-do-i-avoid-plot-holes-in-my-story",
      "how-do-authors-manage-timelines",
      "what-is-a-continuity-checker-for-fiction",
    ])
  })

  it("exposes public routes for all hubs and dynamic content pages", () => {
    const paths = getAllPublicContentPaths()

    expect(paths).toContain("/blog")
    expect(paths).toContain("/answers")
    expect(paths).toContain("/demo")
    expect(paths).toContain("/blog/how-to-track-characters-in-a-novel")
    expect(paths).toContain("/answers/how-do-i-track-character-arcs")
    expect(paths).toContain("/demo/pride-and-prejudice-relationship-map")
  })

  it("keeps the exported content inventories in sync with route generation", () => {
    const expectedCount = 3 + blogArticles.length + answerPages.length + demoPages.length

    expect(getAllPublicContentPaths()).toHaveLength(expectedCount)
  })

  it("exposes the complete public blog and answer inventory", () => {
    expect(blogArticles).toHaveLength(30)
    expect(answerPages).toHaveLength(20)
  })

  it("exposes public content entries with stable publish dates for sitemap generation", () => {
    const entries = getAllPublicContentEntries()

    expect(entries).toContainEqual(
      expect.objectContaining({
        path: "/blog/how-to-track-characters-in-a-novel",
        publishedAt: "2026-05-14",
        type: "blog",
      }),
    )
    expect(entries).toContainEqual(
      expect.objectContaining({
        path: "/answers/how-do-i-track-character-arcs",
        publishedAt: "2026-05-14",
        type: "answer",
      }),
    )
  })

  it("uses the newest public content date for hub pages", () => {
    expect(getLatestContentPublishedAt()).toBe("2026-08-09")
    expect(getAllPublicContentEntries()).toContainEqual(
      expect.objectContaining({
        path: "/blog",
        publishedAt: "2026-08-09",
        type: "hub",
      }),
    )
  })

  it("keeps every blog supporting answer link resolvable", () => {
    for (const article of blogArticles) {
      for (const slug of article.supportingAnswerSlugs) {
        expect(getAnswerPageBySlug(slug), `${article.slug} references ${slug}`).not.toBeNull()
      }
    }
  })

  it("keeps each public content entry above the editorial depth floor", () => {
    const allEntries = [...blogArticles, ...answerPages, ...demoPages]

    for (const entry of allEntries) {
      expect(getContentWordCount(entry)).toBeGreaterThanOrEqual(200)
    }
  })
})
