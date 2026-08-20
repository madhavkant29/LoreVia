import type { ReactElement } from "react"

export type ContentKind = "blog" | "answer"

export type EditorialAuthor = {
  id: "lorevia-editorial"
  name: "LoreVia Editorial"
  avatar: "/image.png"
  bio: string
}

export const LOREVIA_EDITORIAL: EditorialAuthor = {
  id: "lorevia-editorial",
  name: "LoreVia Editorial",
  avatar: "/image.png",
  bio: "Practical craft and revision guidance for fiction authors, grounded in the manuscript rather than generic advice.",
}

export type ContentHero = {
  src: string
  alt: string
  width: number
  height: number
}

export type ContentSource = {
  title: string
  publisher: string
  url: string
  reviewedAt: string
}

type ContentSummaryBase = {
  kind: ContentKind
  slug: string
  title: string
  description: string
  category: string
  keywords: string[]
  publishedAt: string
  updatedAt: string
  publishedLabel: string
  updatedLabel: string
  authorId: EditorialAuthor["id"]
  hero: ContentHero
  relatedSlugs: string[]
  sources: ContentSource[]
  order: number
  wordCount: number
  readTimeMinutes: number
  readTime: string
}

export type BlogSummary = ContentSummaryBase & {
  kind: "blog"
  supportingAnswerSlugs: string[]
  demoSlug?: string
}

export type AnswerSummary = ContentSummaryBase & {
  kind: "answer"
  question: string
  shortAnswer: string
  articleSlug: string
  demoSlug?: string
}

export type ContentSummary = BlogSummary | AnswerSummary

export type TableOfContentsItem = {
  id: string
  label: string
}

export type ContentDocument<TSummary extends ContentSummary = ContentSummary> = {
  summary: TSummary
  source: string
  content: ReactElement
  tableOfContents: TableOfContentsItem[]
}
