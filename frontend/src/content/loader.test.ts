import { existsSync } from "node:fs"
import path from "node:path"

import { describe, expect, it } from "vitest"

import { demoPages } from "@/content/demoContent"
import {
  buildTableOfContents,
  estimateReadTimeMinutes,
  getAllContentSummaries,
  getAnswerSummaries,
  getBlogSummaries,
  getContentSource,
} from "@/content/loader"

const blogs = getBlogSummaries()
const answers = getAnswerSummaries()
const allContent = getAllContentSummaries()
const editorialHeroSystem = new Set([
  "/blog/editorial/character-voice-relationships.webp",
  "/blog/editorial/continuity-timeline-canon.webp",
  "/blog/editorial/revision-feedback.webp",
  "/blog/editorial/scene-structure-pacing.webp",
  "/blog/editorial/story-bible-worldbuilding.webp",
  "/blog/editorial/writing-tools-workflows.webp",
])
const publicPaths = new Set([
  "/blog",
  "/answers",
  "/demo",
  ...blogs.map((entry) => `/blog/${entry.slug}`),
  ...answers.map((entry) => `/answers/${entry.slug}`),
  ...demoPages.map((entry) => `/demo/${entry.slug}`),
])

describe("editorial content catalogue", () => {
  it("contains exactly thirty blogs and twenty answers with unique matching slugs", () => {
    expect(blogs).toHaveLength(30)
    expect(answers).toHaveLength(20)
    expect(new Set(allContent.map((entry) => entry.slug)).size).toBe(50)
    for (const entry of allContent) {
      expect(entry.slug).toMatch(/^[a-z0-9]+(?:-[a-z0-9]+)*$/)
    }
  })

  it("validates editorial depth and derives reading time at 225 words per minute", () => {
    for (const article of blogs) {
      expect(article.wordCount, article.slug).toBeGreaterThanOrEqual(1800)
      expect(article.wordCount, article.slug).toBeLessThanOrEqual(2500)
    }
    for (const answer of answers) {
      expect(answer.wordCount, answer.slug).toBeGreaterThanOrEqual(800)
      expect(answer.wordCount, answer.slug).toBeLessThanOrEqual(1200)
    }
    for (const entry of allContent) {
      expect(entry.readTimeMinutes).toBe(estimateReadTimeMinutes(entry.wordCount))
      expect(entry.readTime).toBe(`${entry.readTimeMinutes} min read`)
    }
  })

  it("requires dated updates, descriptive hero assets, and reviewed HTTPS sources", () => {
    for (const entry of allContent) {
      expect(entry.updatedAt).toMatch(/^\d{4}-\d{2}-\d{2}$/)
      expect(entry.updatedAt.localeCompare(entry.publishedAt)).toBeGreaterThanOrEqual(0)
      expect(entry.hero.alt.length).toBeGreaterThan(20)
      expect(entry.hero.width).toBe(1600)
      expect(entry.hero.height).toBe(900)
      expect(existsSync(path.join(process.cwd(), "public", entry.hero.src))).toBe(true)
      for (const source of entry.sources) {
        expect(source.url).toMatch(/^https:\/\//)
        expect(source.title).toBeTruthy()
        expect(source.publisher).toBeTruthy()
        expect(source.reviewedAt).toMatch(/^\d{4}-\d{2}-\d{2}$/)
      }
    }
  })

  it("resolves parents, related stories, demos, supporting answers, and inline internal links", () => {
    const blogSlugs = new Set(blogs.map((entry) => entry.slug))
    const answerSlugs = new Set(answers.map((entry) => entry.slug))
    const demoSlugs = new Set(demoPages.map((entry) => entry.slug))

    for (const blog of blogs) {
      blog.relatedSlugs.forEach((slug) => expect(blogSlugs.has(slug), `${blog.slug} -> ${slug}`).toBe(true))
      blog.supportingAnswerSlugs.forEach((slug) => expect(answerSlugs.has(slug), `${blog.slug} -> ${slug}`).toBe(true))
      if (blog.demoSlug) expect(demoSlugs.has(blog.demoSlug)).toBe(true)
    }
    for (const answer of answers) {
      expect(blogSlugs.has(answer.articleSlug), `${answer.slug} -> ${answer.articleSlug}`).toBe(true)
      answer.relatedSlugs.forEach((slug) => expect(answerSlugs.has(slug), `${answer.slug} -> ${slug}`).toBe(true))
      if (answer.demoSlug) expect(demoSlugs.has(answer.demoSlug), `${answer.slug} -> ${answer.demoSlug}`).toBe(true)
    }

    for (const entry of allContent) {
      const source = getContentSource(entry.kind, entry.slug) ?? ""
      for (const match of source.matchAll(/\]\((\/(?:blog|answers|demo)(?:\/[^)#?\s]+)?)\)/g)) {
        expect(publicPaths.has(match[1]), `${entry.slug} has unresolved link ${match[1]}`).toBe(true)
      }
    }
  })

  it("keeps rendered H2 anchors unique and aligned with the table of contents", () => {
    for (const entry of allContent) {
      const source = getContentSource(entry.kind, entry.slug) ?? ""
      const body = source.replace(/^---[\s\S]*?---\s*/, "")
      const toc = buildTableOfContents(body, entry.sources.length > 0)
      expect(toc.length, entry.slug).toBeGreaterThan(2)
      expect(new Set(toc.map((item) => item.id)).size).toBe(toc.length)
      expect(toc.every((item) => item.id && item.label)).toBe(true)
      if (entry.sources.length > 0) {
        expect(toc.at(-1)).toEqual({ id: "sources-and-further-reading", label: "Sources and further reading" })
      }
    }
  })

  it("rejects a hand-written sources heading when the shared source list is present", () => {
    expect(() => buildTableOfContents("## Sources and further reading", true)).toThrow(
      "Article body must not duplicate the generated sources section",
    )
  })

  it("keeps every blog's editorial identity and long-form passages distinct", () => {
    expect(new Set(blogs.map((entry) => entry.title)).size).toBe(blogs.length)
    expect(new Set(blogs.map((entry) => entry.description)).size).toBe(blogs.length)
    expect(new Set(blogs.map((entry) => entry.keywords[0])).size).toBe(blogs.length)
    expect(new Set(blogs.map((entry) => entry.hero.src))).toEqual(editorialHeroSystem)
    expect(allContent.every((entry) => editorialHeroSystem.has(entry.hero.src))).toBe(true)

    const paragraphOwners = new Map<string, string>()
    for (const article of blogs) {
      const source = getContentSource(article.kind, article.slug) ?? ""
      const body = source.replace(/^---[\s\S]*?---\s*/, "")
      const paragraphs = body
        .split(/\n{2,}/)
        .map((paragraph) => paragraph.replace(/\s+/g, " ").trim().toLowerCase())
        .filter((paragraph) => paragraph.length >= 180 && !paragraph.startsWith("|"))

      for (const paragraph of paragraphs) {
        expect(paragraphOwners.get(paragraph), `${article.slug} duplicates ${paragraphOwners.get(paragraph)}`).toBeUndefined()
        paragraphOwners.set(paragraph, article.slug)
      }
    }
  })

  it("keeps internal marketing language out of public copy", () => {
    const forbidden = ["SEO hub", "built for search intent", "supporting pages"]
    for (const entry of allContent) {
      const source = getContentSource(entry.kind, entry.slug) ?? ""
      forbidden.forEach((phrase) => expect(source.toLowerCase()).not.toContain(phrase.toLowerCase()))
    }
  })
})
