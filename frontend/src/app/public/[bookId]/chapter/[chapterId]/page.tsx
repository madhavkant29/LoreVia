import type { Metadata } from "next"
import Script from "next/script"

import { PublicChapterPageClient } from "@/components/public/PublicChapterPageClient"
import { getPublicBookServer, getPublicChapterServer } from "@/lib/api/public.server"
import {
  DEFAULT_OG_IMAGE,
  SITE_NAME,
  buildArticleJsonLd,
  buildBreadcrumbJsonLd,
} from "@/lib/seo"

export async function generateMetadata({
  params,
}: {
  params: Promise<{ bookId: string; chapterId: string }>
}): Promise<Metadata> {
  const { bookId, chapterId } = await params
  const chapterNumber = Number.parseInt(chapterId, 10)

  if (!Number.isFinite(chapterNumber) || chapterNumber <= 0) {
    return {}
  }

  const [book, chapter] = await Promise.all([
    getPublicBookServer(bookId).catch(() => null),
    getPublicChapterServer(bookId, chapterNumber).catch(() => null),
  ])

  if (!book || !chapter) {
    return {}
  }

  const routeId = book.public_slug || book.id
  const chapterTitle = chapter.chapter_title || `Chapter ${chapter.chapter_number}`
  const description = chapter.chapter_description
    ?? `Read ${chapterTitle} from ${book.title} on LoreVia.`

  return {
    title: `${chapterTitle} - ${book.title}`,
    description,
    alternates: {
      canonical: `/public/${routeId}/chapter/${chapter.chapter_number}`,
    },
    openGraph: {
      title: `${chapterTitle} | ${book.title} | ${SITE_NAME}`,
      description,
      url: `https://getlorevia.com/public/${routeId}/chapter/${chapter.chapter_number}`,
      images: [DEFAULT_OG_IMAGE],
    },
    twitter: {
      card: "summary_large_image",
      title: `${chapterTitle} | ${book.title} | ${SITE_NAME}`,
      description,
      images: [DEFAULT_OG_IMAGE],
    },
  }
}

export default async function PublicChapterPage({
  params,
}: {
  params: Promise<{ bookId: string; chapterId: string }>
}) {
  const { bookId, chapterId } = await params
  const chapterNumber = Number.parseInt(chapterId, 10)
  const [book, chapter] = await Promise.all([
    getPublicBookServer(bookId),
    getPublicChapterServer(bookId, chapterNumber),
  ])
  const routeId = book.public_slug || book.id
  const chapterTitle = chapter.chapter_title || `Chapter ${chapter.chapter_number}`
  const articleJsonLd = buildArticleJsonLd({
    title: `${chapterTitle} - ${book.title}`,
    description: chapter.chapter_description ?? `Read ${chapterTitle} from ${book.title} on LoreVia.`,
    path: `/public/${routeId}/chapter/${chapter.chapter_number}`,
    datePublished: book.created_at ?? new Date().toISOString(),
    about: [book.title, chapterTitle, "public manuscript sample"],
  })
  const breadcrumbJsonLd = buildBreadcrumbJsonLd([
    { name: "Home", path: "/" },
    { name: "Public Library", path: "/public" },
    { name: book.title, path: `/public/${routeId}` },
    { name: chapterTitle, path: `/public/${routeId}/chapter/${chapter.chapter_number}` },
  ])

  return (
    <>
      <Script id={`public-chapter-jsonld-${routeId}-${chapter.chapter_number}`} type="application/ld+json" strategy="beforeInteractive">
        {JSON.stringify(articleJsonLd).replace(/</g, "\\u003c")}
      </Script>
      <Script id={`public-chapter-breadcrumbs-jsonld-${routeId}-${chapter.chapter_number}`} type="application/ld+json" strategy="beforeInteractive">
        {JSON.stringify(breadcrumbJsonLd).replace(/</g, "\\u003c")}
      </Script>
      <PublicChapterPageClient bookId={routeId} chapterId={chapterId} initialChapter={chapter} />
    </>
  )
}
