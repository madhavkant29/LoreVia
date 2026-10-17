import type { Metadata } from "next"
import { headers } from "next/headers"

import { QueryProvider } from "@/components/app/QueryProvider"
import { PricingPageIntro, PricingPlans } from "@/components/billing/PricingPlans"
import { MarketingHeader } from "@/components/marketing/MarketingHeader"
import { JsonLdScript } from "@/components/seo/JsonLdScript"
import { buildPricingOffersJsonLd } from "@/lib/billing/catalog"
import { DEFAULT_OG_IMAGE, SITE_NAME, SITE_URL, buildBreadcrumbJsonLd } from "@/lib/seo"

export const metadata: Metadata = {
  title: "Pricing",
  description: "Compare LoreVia plans for fiction authors doing manuscript intelligence, revision, continuity work, and invited beta-reader collaboration.",
  keywords: [
    "fiction writing software pricing",
    "manuscript analysis pricing",
    "continuity checker pricing",
    "story bible software pricing",
  ],
  alternates: {
    canonical: "/pricing",
  },
  openGraph: {
    title: `LoreVia Pricing | ${SITE_NAME}`,
    description: "Compare LoreVia plans for fiction authors doing manuscript intelligence, revision, continuity work, and invited beta-reader collaboration.",
    url: `${SITE_URL}/pricing`,
    images: [DEFAULT_OG_IMAGE],
  },
  twitter: {
    card: "summary_large_image",
    title: `LoreVia Pricing | ${SITE_NAME}`,
    description: "Compare LoreVia plans for fiction authors doing manuscript intelligence, revision, continuity work, and invited beta-reader collaboration.",
    images: [DEFAULT_OG_IMAGE],
  },
}

export default async function PricingPage() {
  const nonce = (await headers()).get("x-nonce") ?? undefined
  const softwareJsonLd = {
    "@context": "https://schema.org",
    "@type": "SoftwareApplication",
    name: SITE_NAME,
    applicationCategory: "BusinessApplication",
    operatingSystem: "Web",
    url: `${SITE_URL}/pricing`,
    description:
      "Pricing for LoreVia, the fiction-author workspace for manuscript analysis, continuity checks, character tracking, and revision support.",
    offers: buildPricingOffersJsonLd(`${SITE_URL}/pricing`),
  }
  const breadcrumbJsonLd = buildBreadcrumbJsonLd([
    { name: "Home", path: "/" },
    { name: "Pricing", path: "/pricing" },
  ])

  return (
    <>
      <JsonLdScript id="pricing-software-jsonld" data={softwareJsonLd} />
      <JsonLdScript id="pricing-breadcrumbs-jsonld" data={breadcrumbJsonLd} />
      <QueryProvider>
        <main className="app-shell min-h-screen">
          <MarketingHeader />
          <section className="app-container relative max-w-[1160px] px-4 pb-16 pt-10 sm:px-6 lg:px-8 lg:pt-14">
            <PricingPageIntro />

            <div className="mt-8">
              <PricingPlans surface="public" nonce={nonce} />
            </div>
          </section>
        </main>
      </QueryProvider>
    </>
  )
}
