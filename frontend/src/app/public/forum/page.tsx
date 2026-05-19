import type { Metadata } from "next"
import Script from "next/script"

import { PublicForumPageClient } from "@/components/public/PublicForumPageClient"
import { listPublicForumPostsServer } from "@/lib/api/public.server"
import {
  DEFAULT_OG_IMAGE,
  SITE_NAME,
  SITE_URL,
  buildCollectionPageJsonLd,
  buildItemListJsonLd,
} from "@/lib/seo"

export const metadata: Metadata = {
  title: "Public Forum",
  description:
    "Browse LoreVia public beta-reading threads, author requests, and discussion signals around fiction manuscripts without exposing private drafts.",
  alternates: {
    canonical: "/public/forum",
  },
  openGraph: {
    title: `LoreVia Public Forum | ${SITE_NAME}`,
    description:
      "Browse LoreVia public beta-reading threads, author requests, and discussion signals around fiction manuscripts without exposing private drafts.",
    url: `${SITE_URL}/public/forum`,
    images: [DEFAULT_OG_IMAGE],
  },
  twitter: {
    card: "summary_large_image",
    title: `LoreVia Public Forum | ${SITE_NAME}`,
    description:
      "Browse LoreVia public beta-reading threads, author requests, and discussion signals around fiction manuscripts without exposing private drafts.",
    images: [DEFAULT_OG_IMAGE],
  },
}

export default async function PublicForumPage() {
  const initialData = await listPublicForumPostsServer().catch(() => ({
    items: [],
    total: 0,
    page: 1,
    page_size: 20,
    has_more: false,
  }))
  const collectionJsonLd = buildCollectionPageJsonLd({
    name: "LoreVia Public Forum",
    description:
      "A public discussion feed for beta-reading requests, manuscript feedback threads, and surfaced author asks inside LoreVia.",
    path: "/public/forum",
    about: ["beta reading", "fiction critique", "manuscript feedback"],
  })
  const itemListJsonLd = buildItemListJsonLd({
    name: "LoreVia public forum threads",
    path: "/public/forum",
    items: initialData.items.slice(0, 12).map((post) => ({
      name: post.headline,
      path: `/public/forum/${post.id}`,
    })),
  })

  return (
    <>
      <Script id="public-forum-jsonld" type="application/ld+json" strategy="beforeInteractive">
        {JSON.stringify(collectionJsonLd).replace(/</g, "\\u003c")}
      </Script>
      <Script id="public-forum-itemlist-jsonld" type="application/ld+json" strategy="beforeInteractive">
        {JSON.stringify(itemListJsonLd).replace(/</g, "\\u003c")}
      </Script>
      <PublicForumPageClient initialData={initialData} />
    </>
  )
}
