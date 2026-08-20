import type { Metadata } from "next"
import { notFound } from "next/navigation"

import { ArticleShell } from "@/components/content/ArticleShell"
import { PublicContentShell } from "@/components/marketing/PublicContentShell"
import { JsonLdScript } from "@/components/seo/JsonLdScript"
import { getContentDocument } from "@/content/loader"
import { answerPages, getAnswerPageBySlug, getBlogArticleBySlug } from "@/lib/content"
import { SITE_NAME, buildArticleJsonLd, buildBreadcrumbJsonLd, toAbsoluteUrl } from "@/lib/seo"

export const dynamicParams = false

export function generateStaticParams() {
  return answerPages.map((answer) => ({ slug: answer.slug }))
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const { slug } = await params
  const answer = getAnswerPageBySlug(slug)
  if (!answer) return {}

  return {
    title: answer.title,
    description: answer.description,
    keywords: answer.keywords,
    authors: [{ name: "LoreVia Editorial", url: toAbsoluteUrl("/answers") }],
    category: answer.category,
    alternates: { canonical: `/answers/${answer.slug}` },
    openGraph: {
      type: "article",
      title: `${answer.title} | ${SITE_NAME}`,
      description: answer.description,
      url: toAbsoluteUrl(`/answers/${answer.slug}`),
      publishedTime: answer.publishedAt,
      modifiedTime: answer.updatedAt,
      authors: ["LoreVia Editorial"],
      images: [{
        url: `/answers/${answer.slug}/opengraph-image`,
        width: 1200,
        height: 630,
        alt: answer.title,
      }],
    },
    twitter: {
      card: "summary_large_image",
      title: `${answer.title} | ${SITE_NAME}`,
      description: answer.description,
      images: [`/answers/${answer.slug}/opengraph-image`],
    },
  }
}

export default async function AnswerPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params
  const document = await getContentDocument("answer", slug)
  if (!document || document.summary.kind !== "answer") notFound()

  const answer = document.summary
  const parent = getBlogArticleBySlug(answer.articleSlug)
  const related = answer.relatedSlugs
    .map((relatedSlug) => getAnswerPageBySlug(relatedSlug))
    .filter((item) => item !== null)

  const jsonLd = buildArticleJsonLd({
    type: "Article",
    title: answer.title,
    description: answer.description,
    path: `/answers/${answer.slug}`,
    datePublished: answer.publishedAt,
    dateModified: answer.updatedAt,
    keywords: answer.keywords,
    about: [answer.category, "fiction writing", "manuscript revision"],
    image: answer.hero.src,
    authorName: "LoreVia Editorial",
    wordCount: answer.wordCount,
  })
  const breadcrumbs = buildBreadcrumbJsonLd([
    { name: "Home", path: "/" },
    { name: "Answers", path: "/answers" },
    { name: answer.title, path: `/answers/${answer.slug}` },
  ])

  return (
    <PublicContentShell activeSection="answers">
      <JsonLdScript id={`answer-jsonld-${answer.slug}`} data={jsonLd} />
      <JsonLdScript id={`answer-breadcrumbs-jsonld-${answer.slug}`} data={breadcrumbs} />
      <ArticleShell document={document} related={related} parent={parent} />
    </PublicContentShell>
  )
}
