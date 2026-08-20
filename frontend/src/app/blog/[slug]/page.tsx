import type { Metadata } from "next"
import { notFound } from "next/navigation"

import { ArticleShell } from "@/components/content/ArticleShell"
import { PublicContentShell } from "@/components/marketing/PublicContentShell"
import { JsonLdScript } from "@/components/seo/JsonLdScript"
import { getContentDocument } from "@/content/loader"
import { blogArticles, getBlogArticleBySlug } from "@/lib/content"
import { SITE_NAME, buildArticleJsonLd, buildBreadcrumbJsonLd, toAbsoluteUrl } from "@/lib/seo"

export const dynamicParams = false

export function generateStaticParams() {
  return blogArticles.map((article) => ({ slug: article.slug }))
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const { slug } = await params
  const article = getBlogArticleBySlug(slug)
  if (!article) return {}

  return {
    title: article.title,
    description: article.description,
    keywords: article.keywords,
    authors: [{ name: "LoreVia Editorial", url: toAbsoluteUrl("/blog") }],
    category: article.category,
    alternates: { canonical: `/blog/${article.slug}` },
    openGraph: {
      type: "article",
      title: `${article.title} | ${SITE_NAME}`,
      description: article.description,
      url: toAbsoluteUrl(`/blog/${article.slug}`),
      publishedTime: article.publishedAt,
      modifiedTime: article.updatedAt,
      authors: ["LoreVia Editorial"],
      images: [{
        url: article.hero.src,
        width: article.hero.width,
        height: article.hero.height,
        alt: article.hero.alt,
      }],
    },
    twitter: {
      card: "summary_large_image",
      title: `${article.title} | ${SITE_NAME}`,
      description: article.description,
      images: [article.hero.src],
    },
  }
}

export default async function BlogArticlePage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params
  const document = await getContentDocument("blog", slug)
  if (!document || document.summary.kind !== "blog") notFound()

  const article = document.summary
  const related = article.relatedSlugs
    .map((relatedSlug) => getBlogArticleBySlug(relatedSlug))
    .filter((item) => item !== null)

  const jsonLd = buildArticleJsonLd({
    type: "BlogPosting",
    title: article.title,
    description: article.description,
    path: `/blog/${article.slug}`,
    datePublished: article.publishedAt,
    dateModified: article.updatedAt,
    keywords: article.keywords,
    about: [article.category, "fiction writing", "manuscript revision"],
    image: article.hero.src,
    authorName: "LoreVia Editorial",
    wordCount: article.wordCount,
  })
  const breadcrumbs = buildBreadcrumbJsonLd([
    { name: "Home", path: "/" },
    { name: "Blog", path: "/blog" },
    { name: article.title, path: `/blog/${article.slug}` },
  ])

  return (
    <PublicContentShell activeSection="blog">
      <JsonLdScript id={`blog-jsonld-${article.slug}`} data={jsonLd} />
      <JsonLdScript id={`blog-breadcrumbs-jsonld-${article.slug}`} data={breadcrumbs} />
      <ArticleShell document={document} related={related} />
    </PublicContentShell>
  )
}
