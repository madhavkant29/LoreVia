import type { Metadata } from "next"
import dynamic from "next/dynamic"

import { JsonLdScript } from "@/components/seo/JsonLdScript"
import { listPublicBooksServer } from "@/lib/api/public.server"
import {
  DEFAULT_OG_IMAGE,
  SITE_NAME,
  SITE_URL,
  buildCollectionPageJsonLd,
  buildItemListJsonLd,
} from "@/lib/seo"

const PublicLibraryPageClient = dynamic(
  () => import("@/components/public/PublicLibraryPageClient").then((module) => module.PublicLibraryPageClient)
)

export const metadata: Metadata = {
  title: "Public Library",
  description:
    "Browse LoreVia public-domain demos and creator-published samples with crawlable book pages, chapter navigation, and public author profiles.",
  alternates: {
    canonical: "/public",
  },
  openGraph: {
    title: `LoreVia Public Library | ${SITE_NAME}`,
    description:
      "Browse LoreVia public-domain demos and creator-published samples with crawlable book pages, chapter navigation, and public author profiles.",
    url: `${SITE_URL}/public`,
    images: [
      {
        url: DEFAULT_OG_IMAGE,
        width: 1200,
        height: 630,
        alt: "LoreVia public library",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: `LoreVia Public Library | ${SITE_NAME}`,
    description:
      "Browse LoreVia public-domain demos and creator-published samples with crawlable book pages, chapter navigation, and public author profiles.",
    images: [DEFAULT_OG_IMAGE],
  },
}

export default async function PublicLibraryPage() {
  const books = await listPublicBooksServer().catch(() => [])
  const collectionJsonLd = buildCollectionPageJsonLd({
    name: "LoreVia Public Library",
    description:
      "A public library of LoreVia demos and creator-published book samples for fiction readers, beta readers, and authors researching manuscript workflows.",
    path: "/public",
    about: ["public-domain fiction", "beta reading", "fiction manuscripts"],
  })
  const itemListJsonLd = buildItemListJsonLd({
    name: "LoreVia public books",
    path: "/public",
    items: books.slice(0, 12).map((book) => ({
      name: book.title,
      path: `/public/${book.public_slug || book.id}`,
    })),
  })

  return (
    <>
      <JsonLdScript id="public-library-jsonld" data={collectionJsonLd} />
      <JsonLdScript id="public-library-itemlist-jsonld" data={itemListJsonLd} />
      <div className="sr-only">
        LoreVia public library for fiction authors, beta readers, and readers exploring public-domain manuscript demos, author profiles, and surfaced public samples.
      </div>
      <PublicLibraryPageClient initialBooks={books} />
    </>
  )
}
