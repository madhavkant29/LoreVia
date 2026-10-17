import "server-only"

import { existsSync, readFileSync, readdirSync } from "node:fs"
import path from "node:path"

import matter from "gray-matter"
import { compileMDX } from "next-mdx-remote/rsc"
import remarkGfm from "remark-gfm"

import { editorialMdxComponents } from "@/components/content/EditorialMdxComponents"

import { SOURCES_HEADING_ID, SOURCES_HEADING_LABEL, headingText, slugifyHeading } from "./slug"
import type {
  AnswerSummary,
  BlogSummary,
  ContentDocument,
  ContentHero,
  ContentKind,
  ContentSource,
  ContentSummary,
  TableOfContentsItem,
} from "./types"

const CONTENT_ROOT = path.join(process.cwd(), "src", "content")
const WORDS_PER_MINUTE = 225
const DATE_FORMAT = /^\d{4}-\d{2}-\d{2}$/
const SLUG_FORMAT = /^[a-z0-9]+(?:-[a-z0-9]+)*$/

type ParsedContentFile = {
  summary: ContentSummary
  source: string
  body: string
  filePath: string
}

function requireString(value: unknown, field: string, filePath: string): string {
  if (typeof value !== "string" || !value.trim()) {
    throw new Error(`${filePath}: ${field} must be a non-empty string`)
  }
  return value.trim()
}

function requireDate(value: unknown, field: string, filePath: string): string {
  const date = requireString(value, field, filePath)
  if (!DATE_FORMAT.test(date)) {
    throw new Error(`${filePath}: ${field} must use YYYY-MM-DD`)
  }
  return date
}

function requireStringList(value: unknown, field: string, filePath: string): string[] {
  if (!Array.isArray(value) || value.some((item) => typeof item !== "string" || !item.trim())) {
    throw new Error(`${filePath}: ${field} must be an array of non-empty strings`)
  }
  return value.map((item) => String(item).trim())
}

function optionalString(value: unknown, field: string, filePath: string): string | undefined {
  if (value === undefined || value === null || value === "") return undefined
  return requireString(value, field, filePath)
}

function parseHero(value: unknown, filePath: string): ContentHero {
  if (!value || typeof value !== "object") {
    throw new Error(`${filePath}: hero must be an object`)
  }
  const hero = value as Record<string, unknown>
  const width = Number(hero.width)
  const height = Number(hero.height)
  if (!Number.isInteger(width) || width < 1200 || !Number.isInteger(height) || height < 630) {
    throw new Error(`${filePath}: hero dimensions must be integers of at least 1200x630`)
  }
  return {
    src: requireString(hero.src, "hero.src", filePath),
    alt: requireString(hero.alt, "hero.alt", filePath),
    width,
    height,
  }
}

function parseSources(value: unknown, filePath: string): ContentSource[] {
  if (!Array.isArray(value)) {
    throw new Error(`${filePath}: sources must be an array`)
  }
  return value.map((item, index) => {
    if (!item || typeof item !== "object") {
      throw new Error(`${filePath}: sources[${index}] must be an object`)
    }
    const source = item as Record<string, unknown>
    const url = requireString(source.url, `sources[${index}].url`, filePath)
    if (!url.startsWith("https://")) {
      throw new Error(`${filePath}: sources[${index}].url must be HTTPS`)
    }
    return {
      title: requireString(source.title, `sources[${index}].title`, filePath),
      publisher: requireString(source.publisher, `sources[${index}].publisher`, filePath),
      url,
      reviewedAt: requireDate(source.reviewedAt, `sources[${index}].reviewedAt`, filePath),
    }
  })
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("en-US", {
    month: "long",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(`${value}T00:00:00.000Z`))
}

export function countVisibleWords(markdownBody: string): number {
  const visibleText = markdownBody
    .replace(/```[\s\S]*?```/g, " ")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/<[^>]+>/g, " ")
    .replace(/!\[([^\]]*)\]\([^\)]+\)/g, "$1")
    .replace(/\[([^\]]+)\]\([^\)]+\)/g, "$1")
    .replace(/^#{1,6}\s+/gm, "")
    .replace(/^[-*+]\s+/gm, "")
    .replace(/^\d+\.\s+/gm, "")
    .replace(/[|>*_~]/g, " ")
    .replace(/&[a-z]+;/gi, " ")

  return visibleText.match(/[\p{L}\p{N}]+(?:[’'-][\p{L}\p{N}]+)*/gu)?.length ?? 0
}

export function estimateReadTimeMinutes(wordCount: number): number {
  return Math.max(1, Math.ceil(wordCount / WORDS_PER_MINUTE))
}

export function extractTableOfContents(markdownBody: string): TableOfContentsItem[] {
  const items = [...markdownBody.matchAll(/^##\s+(.+)$/gm)].map((match) => {
    const label = headingText(match[1])
    return { id: slugifyHeading(label), label }
  })
  const ids = items.map((item) => item.id)
  if (new Set(ids).size !== ids.length) {
    throw new Error("Article H2 headings must produce unique anchors")
  }
  return items
}

export function buildTableOfContents(markdownBody: string, includeSources: boolean): TableOfContentsItem[] {
  const items = extractTableOfContents(markdownBody)
  if (!includeSources) return items
  if (items.some((item) => item.id === SOURCES_HEADING_ID)) {
    throw new Error("Article body must not duplicate the generated sources section")
  }
  return [...items, { id: SOURCES_HEADING_ID, label: SOURCES_HEADING_LABEL }]
}

function parseContentFile(kind: ContentKind, filePath: string): ParsedContentFile {
  const source = readFileSync(filePath, "utf8")
  const parsed = matter(source)
  const data = parsed.data as Record<string, unknown>
  const fileSlug = path.basename(filePath, ".mdx")
  const parsedKind = requireString(data.kind, "kind", filePath)
  const slug = requireString(data.slug, "slug", filePath)

  if (parsedKind !== kind) throw new Error(`${filePath}: kind must be ${kind}`)
  if (!SLUG_FORMAT.test(slug) || slug !== fileSlug) {
    throw new Error(`${filePath}: slug must match the filename and use kebab-case`)
  }

  const order = Number(data.order)
  if (!Number.isInteger(order) || order < 0) {
    throw new Error(`${filePath}: order must be a non-negative integer`)
  }

  const publishedAt = requireDate(data.publishedAt, "publishedAt", filePath)
  const updatedAt = requireDate(data.updatedAt, "updatedAt", filePath)
  const wordCount = countVisibleWords(parsed.content)
  const readTimeMinutes = estimateReadTimeMinutes(wordCount)
  const common = {
    slug,
    title: requireString(data.title, "title", filePath),
    description: requireString(data.description, "description", filePath),
    category: requireString(data.category, "category", filePath),
    keywords: requireStringList(data.keywords, "keywords", filePath),
    publishedAt,
    updatedAt,
    publishedLabel: formatDate(publishedAt),
    updatedLabel: formatDate(updatedAt),
    authorId: requireString(data.authorId, "authorId", filePath) as "lorevia-editorial",
    hero: parseHero(data.hero, filePath),
    relatedSlugs: requireStringList(data.relatedSlugs, "relatedSlugs", filePath),
    sources: parseSources(data.sources, filePath),
    order,
    wordCount,
    readTimeMinutes,
    readTime: `${readTimeMinutes} min read`,
  }

  if (common.authorId !== "lorevia-editorial") {
    throw new Error(`${filePath}: authorId must be lorevia-editorial`)
  }

  const summary: ContentSummary = kind === "blog"
    ? {
        ...common,
        kind,
        supportingAnswerSlugs: requireStringList(data.supportingAnswerSlugs, "supportingAnswerSlugs", filePath),
        demoSlug: optionalString(data.demoSlug, "demoSlug", filePath),
      } satisfies BlogSummary
    : {
        ...common,
        kind,
        question: common.title,
        shortAnswer: requireString(data.shortAnswer, "shortAnswer", filePath),
        articleSlug: requireString(data.articleSlug, "articleSlug", filePath),
        demoSlug: optionalString(data.demoSlug, "demoSlug", filePath),
      } satisfies AnswerSummary

  return { summary, source, body: parsed.content, filePath }
}

function readKind(kind: ContentKind): ParsedContentFile[] {
  const directory = path.join(CONTENT_ROOT, kind === "blog" ? "blog" : "answers")
  if (!existsSync(directory)) return []
  return readdirSync(directory)
    .filter((name) => name.endsWith(".mdx"))
    .map((name) => parseContentFile(kind, path.join(directory, name)))
    .sort((left, right) => left.summary.order - right.summary.order)
}

let parsedContentCache: ParsedContentFile[] | null = null

function allParsedContent(): ParsedContentFile[] {
  if (!parsedContentCache) parsedContentCache = [...readKind("blog"), ...readKind("answer")]
  return parsedContentCache
}

export function clearContentCacheForTests(): void {
  parsedContentCache = null
}

export function getAllContentSummaries(): ContentSummary[] {
  return allParsedContent().map((entry) => entry.summary)
}

export function getBlogSummaries(): BlogSummary[] {
  return getAllContentSummaries().filter((entry): entry is BlogSummary => entry.kind === "blog")
}

export function getAnswerSummaries(): AnswerSummary[] {
  return getAllContentSummaries().filter((entry): entry is AnswerSummary => entry.kind === "answer")
}

export function getContentSummary(kind: ContentKind, slug: string): ContentSummary | null {
  return getAllContentSummaries().find((entry) => entry.kind === kind && entry.slug === slug) ?? null
}

export async function getContentDocument(kind: ContentKind, slug: string): Promise<ContentDocument | null> {
  const parsed = allParsedContent().find((entry) => entry.summary.kind === kind && entry.summary.slug === slug)
  if (!parsed) return null

  const { content } = await compileMDX({
    source: parsed.body,
    components: editorialMdxComponents,
    options: {
      blockJS: true,
      blockDangerousJS: true,
      mdxOptions: { remarkPlugins: [remarkGfm] },
    },
  })

  return {
    summary: parsed.summary,
    source: parsed.source,
    content,
    tableOfContents: buildTableOfContents(parsed.body, parsed.summary.sources.length > 0),
  }
}

export function getContentSource(kind: ContentKind, slug: string): string | null {
  return allParsedContent().find((entry) => entry.summary.kind === kind && entry.summary.slug === slug)?.source ?? null
}
