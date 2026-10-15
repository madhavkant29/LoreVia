import type { Metadata } from "next"
import Link from "next/link"

import { MarketingFooterLayout } from "@/components/layout/MarketingFooterLayout"
import { PublicContentShell } from "@/components/marketing/PublicContentShell"
import { JsonLdScript } from "@/components/seo/JsonLdScript"
import { demoPages, getBlogArticleBySlug } from "@/lib/content"
import { DEFAULT_OG_IMAGE, SITE_NAME, SITE_URL, buildCollectionPageJsonLd } from "@/lib/seo"

export const metadata: Metadata = {
  title: "Demo",
  description:
    "Public-domain LoreVia demos showing how character tracking, relationship mapping, and timeline analysis support fiction authors.",
  keywords: [
    "public domain writing demos",
    "character tracking demo",
    "story timeline tracker demo",
    "relationship map for novelists",
  ],
  alternates: {
    canonical: "/demo",
  },
  openGraph: {
    title: `LoreVia Demo | ${SITE_NAME}`,
    description:
      "Public-domain LoreVia demos showing how character tracking, relationship mapping, and timeline analysis support fiction authors.",
    url: `${SITE_URL}/demo`,
    images: [
      {
        url: DEFAULT_OG_IMAGE,
        width: 1200,
        height: 630,
        alt: "LoreVia public-domain demos",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: `LoreVia Demo | ${SITE_NAME}`,
    description:
      "Public-domain LoreVia demos showing how character tracking, relationship mapping, and timeline analysis support fiction authors.",
    images: [DEFAULT_OG_IMAGE],
  },
}

export default function DemoIndexPage() {
  const jsonLd = buildCollectionPageJsonLd({
    name: "LoreVia Demo",
    description:
      "Public-domain LoreVia demos showing how character tracking, relationship mapping, and timeline analysis support fiction authors.",
    path: "/demo",
    about: [
      "public-domain fiction",
      "character tracking demo",
      "timeline analysis",
      "relationship mapping",
    ],
  })

  return (
    <MarketingFooterLayout>
      <PublicContentShell activeSection="demo">
        <JsonLdScript id="demo-collection-jsonld" data={jsonLd} />

      <section className="app-container py-12 md:py-16">
        <div className="max-w-4xl border-b border-[rgba(var(--border),0.72)] pb-12 md:pb-16">
          <p className="text-sm font-semibold text-[rgb(var(--accent))]">Public-domain workflow examples</p>
          <h1 className="mt-4 max-w-4xl font-display text-[3rem] leading-[0.96] tracking-[-0.04em] text-foreground sm:text-[4rem]">
            See how manuscript evidence becomes an editorial decision.
          </h1>
          <p className="mt-6 max-w-3xl text-base leading-8 text-muted-foreground sm:text-[1.1rem]">
            Follow character, timeline, and relationship analysis through familiar public-domain novels. Each case study starts with the source text and ends with a practical revision question.
          </p>
          <div className="mt-8 flex flex-col gap-3 sm:flex-row">
            <Link href="/demo/workspace" className="app-button-primary">
              Review a sample finding
            </Link>
            <Link href={`/demo/${demoPages[0].slug}`} className="app-button-secondary">
              Read the first case study
            </Link>
          </div>
        </div>
      </section>

      <section className="app-container pb-20 md:pb-24">
        <div className="max-w-3xl">
          <p className="text-sm font-semibold text-[rgb(var(--accent))]">Case-study library</p>
          <h2 className="mt-3 text-3xl font-semibold tracking-[-0.03em] text-foreground md:text-4xl">
            Three manuscripts, three editorial problems.
          </h2>
        </div>

        <div data-testid="demo-index-list" className="mt-8 border-y border-[rgba(var(--border),0.72)]">
          {demoPages.map((demo) => {
            const article = getBlogArticleBySlug(demo.articleSlug)
            return (
              <article key={demo.slug} className="grid gap-4 border-b border-[rgba(var(--border),0.64)] py-7 last:border-b-0 md:grid-cols-[minmax(0,0.85fr)_minmax(0,1.15fr)_auto] md:items-start md:gap-8">
                <div>
                  <p className="text-sm font-medium text-muted-foreground">
                    {demo.sourceWork} by {demo.sourceAuthor}
                  </p>
                  <h3 className="mt-2 text-2xl font-semibold tracking-[-0.03em] text-foreground">
                    <Link href={`/demo/${demo.slug}`} className="transition hover:text-[rgb(var(--accent))]">
                      {demo.title.replace(/^Demo:\s*/, "")}
                    </Link>
                  </h3>
                </div>
                <div>
                  <p className="text-sm leading-7 text-muted-foreground">{demo.featuredInsight}</p>
                  {article ? (
                    <Link href={`/blog/${article.slug}`} className="mt-3 inline-flex text-sm font-medium text-foreground/70 transition hover:text-[rgb(var(--accent))]">
                      Supporting guide: {article.title}
                    </Link>
                  ) : null}
                </div>
                <Link href={`/demo/${demo.slug}`} className="text-sm font-semibold text-[rgb(var(--accent))] md:justify-self-end">
                  Read case study →
                </Link>
              </article>
            )
          })}
        </div>
      </section>
      </PublicContentShell>
    </MarketingFooterLayout>
  )
}
