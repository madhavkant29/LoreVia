import Link from "next/link"
import type { Metadata } from "next"

import { MarketingHeader } from "@/components/marketing/MarketingHeader"
import { comparisonIndexCards } from "@/lib/comparisons"
import { JsonLdScript } from "@/components/seo/JsonLdScript"
import {
  DEFAULT_OG_IMAGE,
  SITE_NAME,
  SITE_URL,
  buildBreadcrumbJsonLd,
  buildCollectionPageJsonLd,
  buildItemListJsonLd,
} from "@/lib/seo"

export const metadata: Metadata = {
  title: "Compare LoreVia",
  description:
    "Compare LoreVia with Scrivener, Campfire, Novelcrafter, and Sudowrite for manuscript writing, continuity, and story memory workflows.",
  alternates: {
    canonical: "/compare",
  },
  openGraph: {
    title: `Compare LoreVia | ${SITE_NAME}`,
    description:
      "Compare LoreVia with Scrivener, Campfire, Novelcrafter, and Sudowrite for manuscript writing, continuity, and story memory workflows.",
    url: `${SITE_URL}/compare`,
    images: [DEFAULT_OG_IMAGE],
  },
  twitter: {
    card: "summary_large_image",
    title: `Compare LoreVia | ${SITE_NAME}`,
    description:
      "Compare LoreVia with Scrivener, Campfire, Novelcrafter, and Sudowrite for manuscript writing, continuity, and story memory workflows.",
    images: [DEFAULT_OG_IMAGE],
  },
}

export default function CompareIndexPage() {
  const breadcrumbJsonLd = buildBreadcrumbJsonLd([
    { name: "Home", path: "/" },
    { name: "Compare", path: "/compare" },
  ])
  const collectionJsonLd = buildCollectionPageJsonLd({
    name: "LoreVia comparison pages",
    description:
      "Comparison pages for authors evaluating LoreVia against other fiction writing tools.",
    path: "/compare",
    about: ["fiction writing software", "manuscript continuity", "story memory"],
  })
  const itemListJsonLd = buildItemListJsonLd({
    name: "LoreVia comparisons",
    path: "/compare",
    items: comparisonIndexCards.map((item) => ({
      name: `LoreVia vs ${item.name}`,
      path: `/compare/${item.slug}`,
    })),
  })

  return (
    <>
      <JsonLdScript id="compare-breadcrumb-jsonld" data={breadcrumbJsonLd} />
      <JsonLdScript id="compare-collection-jsonld" data={collectionJsonLd} />
      <JsonLdScript id="compare-itemlist-jsonld" data={itemListJsonLd} />

      <main className="min-h-screen bg-[#08110f] text-white">
        <MarketingHeader />

        <section className="mx-auto max-w-7xl px-5 pb-14 pt-14 md:px-8 md:pt-20">
          <p className="text-[11px] font-semibold uppercase tracking-[0.32em] text-[#6fae9f]">Compare LoreVia</p>
          <h1 className="mt-5 max-w-4xl font-display text-5xl font-semibold leading-[0.95] tracking-[-0.04em] text-white md:text-7xl">
            Pick the writing workspace that matches your real bottleneck.
          </h1>
          <p className="mt-6 max-w-3xl text-lg leading-8 text-[#aeb9b3]">
            These comparison pages focus on workflow fit: drafting, continuity, story memory, worldbuilding, and revision support. They are written to stay specific and respectful rather than overclaiming.
          </p>
        </section>

        <section className="mx-auto max-w-7xl px-5 pb-24 md:px-8">
          <div className="grid gap-5 lg:grid-cols-2">
            {comparisonIndexCards.map((item) => (
              <Link
                key={item.slug}
                href={`/compare/${item.slug}`}
                className="rounded-[1.7rem] border border-white/10 bg-[#0d1715] p-6 transition hover:border-white/18 hover:bg-[#101a18]"
              >
                <p className="text-[11px] font-semibold uppercase tracking-[0.28em] text-[#6fae9f]">Comparison page</p>
                <h2 className="mt-4 font-display text-4xl font-semibold text-white">LoreVia vs {item.name}</h2>
                <p className="mt-4 text-base leading-8 text-[#aeb9b3]">{item.summary}</p>
                <span className="mt-6 inline-flex items-center gap-2 text-sm font-semibold text-[#86decd]">
                  Open comparison
                  <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M5 12h14m-6-6 6 6-6 6" />
                  </svg>
                </span>
              </Link>
            ))}
          </div>
        </section>
      </main>
    </>
  )
}
