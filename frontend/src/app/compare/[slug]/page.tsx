import type { Metadata } from "next"
import Link from "next/link"
import { notFound } from "next/navigation"

import { ComparisonCTA } from "@/components/marketing/ComparisonCTA"
import { CompareNav } from "@/components/marketing/CompareNav"
import { ComparisonHero } from "@/components/marketing/ComparisonHero"
import { ComparisonTable } from "@/components/marketing/ComparisonTable"
import { CompetitorVerdict } from "@/components/marketing/CompetitorVerdict"
import { MarketingHeader } from "@/components/marketing/MarketingHeader"
import { JsonLdScript } from "@/components/seo/JsonLdScript"
import { competitorPages, getCompetitorPage } from "@/lib/comparisons"
import {
  DEFAULT_OG_IMAGE,
  SITE_NAME,
  SITE_URL,
  buildBreadcrumbJsonLd,
} from "@/lib/seo"

type ComparisonPageProps = {
  params: Promise<{ slug: string }>
}

export async function generateStaticParams() {
  return competitorPages.map((page) => ({ slug: page.slug }))
}

export async function generateMetadata({ params }: ComparisonPageProps): Promise<Metadata> {
  const { slug } = await params
  const page = getCompetitorPage(slug)

  if (!page) {
    return {}
  }

  return {
    title: page.title,
    description: page.description,
    alternates: {
      canonical: `/compare/${page.slug}`,
    },
    openGraph: {
      title: `${page.title} | ${SITE_NAME}`,
      description: page.description,
      url: `${SITE_URL}/compare/${page.slug}`,
      images: [DEFAULT_OG_IMAGE],
    },
    twitter: {
      card: "summary_large_image",
      title: `${page.title} | ${SITE_NAME}`,
      description: page.description,
      images: [DEFAULT_OG_IMAGE],
    },
  }
}

export default async function CompetitorComparisonPage({ params }: ComparisonPageProps) {
  const { slug } = await params
  const page = getCompetitorPage(slug)

  if (!page) {
    notFound()
  }

  const breadcrumbJsonLd = buildBreadcrumbJsonLd([
    { name: "Home", path: "/" },
    { name: "Compare", path: "/compare" },
    { name: page.title, path: `/compare/${page.slug}` },
  ])

  return (
    <>
      <JsonLdScript id={`compare-${page.slug}-breadcrumb-jsonld`} data={breadcrumbJsonLd} />

      <main className="min-h-screen bg-[#08110f] text-white">
        <MarketingHeader />
        <ComparisonHero title={page.title} summary={page.heroSummary} />
        <CompetitorVerdict
          competitorName={page.competitorName}
          competitorBestFor={page.competitorBestFor}
          loreviaBestFor={page.loreviaBestFor}
        />

        <section className="mx-auto max-w-7xl px-5 py-12 md:px-8">
          <div className="grid gap-10 lg:grid-cols-[0.82fr_1.18fr]">
            <div className="min-w-0">
              <p className="text-sm font-semibold text-[#79c8b8]">
                Where LoreVia is different
              </p>
              <div data-testid="comparison-differentiators" className="mt-5 border-y border-white/10">
                {page.differentiators.map((item) => (
                  <article key={item.title} className="border-b border-white/[0.08] py-5 last:border-b-0">
                    <h2 className="text-xl font-semibold text-white">{item.title}</h2>
                    <p className="mt-3 text-base leading-8 text-[#aeb9b3]">{item.body}</p>
                  </article>
                ))}
              </div>
            </div>

            <div className="min-w-0">
              <ComparisonTable competitorName={page.competitorName} rows={page.rows} />
            </div>
          </div>
        </section>

        <section className="mx-auto max-w-7xl px-5 py-12 md:px-8">
          <div className="grid border-y border-white/10 lg:grid-cols-2">
            <article className="py-6 lg:pr-8">
              <p className="text-sm font-semibold text-[#7ad3c1]">Choose LoreVia if...</p>
              <ul className="mt-5 divide-y divide-white/[0.07] text-base leading-7 text-[#d9e0db]">
                {page.chooseLoreVia.map((item) => (
                  <li key={item} className="py-3 first:pt-0 last:pb-0">{item}</li>
                ))}
              </ul>
            </article>
            <article className="border-t border-white/10 py-6 lg:border-l lg:border-t-0 lg:pl-8">
              <p className="text-sm font-semibold text-[#8fa19a]">
                Choose {page.competitorName} if...
              </p>
              <ul className="mt-5 divide-y divide-white/[0.07] text-base leading-7 text-[#d9e0db]">
                {page.chooseCompetitor.map((item) => (
                  <li key={item} className="py-3 first:pt-0 last:pb-0">{item}</li>
                ))}
              </ul>
            </article>
          </div>
        </section>

        <section className="mx-auto max-w-7xl px-5 py-12 md:px-8">
          <div>
            <p className="text-sm font-semibold text-[#79c8b8]">More comparisons</p>
            <div className="mt-5">
              <CompareNav activeSlug={page.slug} />
            </div>
            <div className="mt-6">
              <Link
                href="/compare"
                className="inline-flex items-center gap-2 text-sm font-semibold text-[#86decd] transition hover:text-white"
              >
                Back to all comparison pages
                <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M5 12h14m-6-6 6 6-6 6" />
                </svg>
              </Link>
            </div>
          </div>
        </section>

        <ComparisonCTA />
      </main>
    </>
  )
}
