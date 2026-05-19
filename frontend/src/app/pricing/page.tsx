import type { Metadata } from "next"
import { headers } from "next/headers"

import { PricingPlans } from "@/components/billing/PricingPlans"
import { LegalPageShell } from "@/components/legal/LegalPageShell"
import { JsonLdScript } from "@/components/seo/JsonLdScript"
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
    offers: [
      {
        "@type": "Offer",
        name: "Free",
        price: "0",
        priceCurrency: "USD",
        url: `${SITE_URL}/pricing`,
      },
      {
        "@type": "Offer",
        name: "Author",
        priceCurrency: "USD",
        url: `${SITE_URL}/pricing`,
      },
      {
        "@type": "Offer",
        name: "Architect",
        priceCurrency: "USD",
        url: `${SITE_URL}/pricing`,
      },
    ],
  }
  const breadcrumbJsonLd = buildBreadcrumbJsonLd([
    { name: "Home", path: "/" },
    { name: "Pricing", path: "/pricing" },
  ])

  return (
    <>
      <JsonLdScript id="pricing-software-jsonld" data={softwareJsonLd} />
      <JsonLdScript id="pricing-breadcrumbs-jsonld" data={breadcrumbJsonLd} />
      <LegalPageShell
        eyebrow="Pricing"
        title="Pricing for fiction authors doing serious manuscript work"
        description="See exactly what is included in Free, what happens after the 10-day Author trial, and how Author and Architect compare before you create an account."
        effectiveDate="May 8, 2026"
        notice="Every new signup gets 10 days of Author access with no credit card required, then falls back to Free unless you choose a paid plan."
        maxWidth="wide"
      >
        <PricingPlans surface="public" nonce={nonce} />
      </LegalPageShell>
    </>
  )
}
