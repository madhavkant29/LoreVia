import { describe, expect, it } from "vitest"

import {
  answerPages,
  blogArticles,
  demoPages,
  getAllPublicContentPaths,
  getAnswerPageBySlug,
  getAnswersByArticleSlug,
  getBlogArticleBySlug,
  getDemoPageBySlug,
} from "./content"

describe("content helpers", () => {
  it("returns a blog article by slug", () => {
    expect(getBlogArticleBySlug("how-to-track-characters-in-a-novel")?.title).toBe(
      "How to Keep Track of Characters in a Novel"
    )
  })

  it("returns an answer page by slug", () => {
    expect(getAnswerPageBySlug("how-do-i-track-character-arcs")?.question).toBe(
      "How do I track character arcs?"
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
})
