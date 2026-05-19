import type { Metadata } from "next"
import Script from "next/script"

import { PublicBookPageClient } from "@/components/public/PublicBookPageClient"
import { getPublicBookServer } from "@/lib/api/public.server"
import {
  DEFAULT_OG_IMAGE,
  SITE_NAME,
  buildBookJsonLd,
  buildBreadcrumbJsonLd,
} from "@/lib/seo"

export async function generateMetadata({ params }: { params: Promise<{ bookId: string }> }): Promise<Metadata> {
  const { bookId } = await params
  const book = await getPublicBookServer(bookId).catch(() => null)

  if (!book) {
    return {}
  }

  const description = book.description
    ?? `Read ${book.title} on LoreVia with public chapter navigation, public author context, and searchable public sample metadata.`

  return {
    title: book.title,
    description,
    alternates: {
      canonical: `/public/${book.public_slug || book.id}`,
    },
    openGraph: {
      title: `${book.title} | ${SITE_NAME}`,
      description,
      url: `https://getlorevia.com/public/${book.public_slug || book.id}`,
      images: [DEFAULT_OG_IMAGE],
    },
    twitter: {
      card: "summary_large_image",
      title: `${book.title} | ${SITE_NAME}`,
      description,
      images: [DEFAULT_OG_IMAGE],
    },
  }
}

export default async function PublicBookPage({ params }: { params: Promise<{ bookId: string }> }) {
  const { bookId } = await params
  const book = await getPublicBookServer(bookId)
  const routeId = book.public_slug || book.id
  const bookJsonLd = buildBookJsonLd({
    title: book.title,
    author: book.author || book.creator_display_name,
    description: book.description,
    path: `/public/${routeId}`,
    genre: book.genre,
    chapterCount: book.total_chapters,
  })
  const breadcrumbJsonLd = buildBreadcrumbJsonLd([
    { name: "Home", path: "/" },
    { name: "Public Library", path: "/public" },
    { name: book.title, path: `/public/${routeId}` },
  ])

  return (
    <>
      <Script id={`public-book-jsonld-${routeId}`} type="application/ld+json" strategy="beforeInteractive">
        {JSON.stringify(bookJsonLd).replace(/</g, "\\u003c")}
      </Script>
      <Script id={`public-book-breadcrumbs-jsonld-${routeId}`} type="application/ld+json" strategy="beforeInteractive">
        {JSON.stringify(breadcrumbJsonLd).replace(/</g, "\\u003c")}
      </Script>
      <PublicBookPageClient bookId={bookId} initialBook={book} />
    </>
  )
}
