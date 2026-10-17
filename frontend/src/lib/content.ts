import {
  getAllContentSummaries,
  getAnswerSummaries,
  getBlogSummaries,
  getContentSummary,
} from "@/content/loader"
import { demoPages, type ContentSection, type DemoPage } from "@/content/demoContent"
import type { AnswerSummary, BlogSummary, ContentSummary } from "@/content/types"

export type { AnswerSummary as AnswerPage, BlogSummary as BlogArticle, ContentSection, DemoPage }

export type PublicContentEntry = {
  path: string
  publishedAt: string
  updatedAt: string
  type: "hub" | "blog" | "answer" | "demo"
}

export const CONTENT_HUB_ROUTES = ["/blog", "/answers", "/demo"] as const

export const blogArticles = getBlogSummaries()
export const answerPages = getAnswerSummaries()
export { demoPages }

export function getBlogArticleBySlug(slug: string): BlogSummary | null {
  const summary = getContentSummary("blog", slug)
  return summary?.kind === "blog" ? summary : null
}

export function getAnswerPageBySlug(slug: string): AnswerSummary | null {
  const summary = getContentSummary("answer", slug)
  return summary?.kind === "answer" ? summary : null
}

export function getDemoPageBySlug(slug: string): DemoPage | null {
  return demoPages.find((demo) => demo.slug === slug) ?? null
}

export function getAnswersByArticleSlug(articleSlug: string): AnswerSummary[] {
  return answerPages.filter((answer) => answer.articleSlug === articleSlug)
}

export function getAnswerPagesBySlugs(slugs: string[]): AnswerSummary[] {
  return slugs
    .map((slug) => getAnswerPageBySlug(slug))
    .filter((answer): answer is AnswerSummary => answer !== null)
}

export function getAllPublicContentPaths(): string[] {
  return [
    ...CONTENT_HUB_ROUTES,
    ...blogArticles.map((article) => `/blog/${article.slug}`),
    ...answerPages.map((answer) => `/answers/${answer.slug}`),
    ...demoPages.map((demo) => `/demo/${demo.slug}`),
  ]
}

export function getAllPublicContentEntries(): PublicContentEntry[] {
  const latestUpdatedAt = getLatestContentPublishedAt()

  return [
    ...CONTENT_HUB_ROUTES.map((path) => ({
      path,
      publishedAt: latestUpdatedAt,
      updatedAt: latestUpdatedAt,
      type: "hub" as const,
    })),
    ...getAllContentSummaries().map((document) => ({
      path: `/${document.kind === "blog" ? "blog" : "answers"}/${document.slug}`,
      publishedAt: document.publishedAt,
      updatedAt: document.updatedAt,
      type: document.kind,
    })),
    ...demoPages.map((demo) => ({
      path: `/demo/${demo.slug}`,
      publishedAt: demo.publishedAt,
      updatedAt: demo.publishedAt,
      type: "demo" as const,
    })),
  ]
}

export function getLatestContentPublishedAt(): string {
  return [
    ...getAllContentSummaries().map((entry) => entry.updatedAt),
    ...demoPages.map((entry) => entry.publishedAt),
  ].sort((left, right) => right.localeCompare(left))[0]
}

function countWords(value: string): number {
  return value.trim().split(/\s+/).filter(Boolean).length
}

function countSectionWords(sections: ContentSection[]): number {
  return sections.reduce((total, section) => {
    const bodyWords = section.body.reduce((sum, paragraph) => sum + countWords(paragraph), 0)
    const bulletWords = (section.bullets ?? []).reduce((sum, bullet) => sum + countWords(bullet), 0)
    return total + countWords(section.heading) + bodyWords + bulletWords + countWords(section.highlight ?? "")
  }, 0)
}

export function getContentWordCount(entry: ContentSummary | DemoPage): number {
  if ("wordCount" in entry) return entry.wordCount
  return (
    countWords(entry.title) +
    countWords(entry.description) +
    countWords(entry.intro) +
    countWords(entry.featuredInsight) +
    countSectionWords(entry.sections)
  )
}
