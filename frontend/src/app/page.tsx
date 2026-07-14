import Link from "next/link"
import type { Metadata } from "next"
import type { Route } from "next"
import type { ReactNode } from "react"
import Image from "next/image"
import dynamic from "next/dynamic"

import { SiteFooter } from "@/components/layout/SiteFooter"
import { HomePricingSection } from "@/components/marketing/HomePricingSection"
import { MarketingHeader } from "@/components/marketing/MarketingHeader"
import { Reveal } from "@/components/marketing/Reveal"
import { JsonLdScript } from "@/components/seo/JsonLdScript"
import { pricingTiers as billingPricingTiers } from "@/lib/billing/catalog"
import {
  DEFAULT_OG_IMAGE,
  SITE_NAME,
  SITE_URL,
  buildFaqPageJsonLd,
  toAbsoluteUrl,
} from "@/lib/seo"

export const metadata: Metadata = {
  title: "LoreVia | Find plot holes before your readers do",
  description:
    "Analyze manuscripts for continuity issues, timeline conflicts, character inconsistencies, unresolved story logic, and grounded revision context without losing your voice.",
  keywords: [
    "fiction writing workspace",
    "manuscript continuity software",
    "story memory for authors",
    "chapter grounded writing assistant",
    "revision software for fiction authors",
    "LoreVia",
  ],
  alternates: {
    canonical: "/",
  },
  openGraph: {
    title: "LoreVia | Find plot holes before your readers do",
    description:
      "Analyze manuscripts for continuity issues, timeline conflicts, character inconsistencies, unresolved story logic, and grounded revision context without losing your voice.",
    url: SITE_URL,
    images: [DEFAULT_OG_IMAGE],
  },
  twitter: {
    card: "summary_large_image",
    title: "LoreVia | Find plot holes before your readers do",
    description:
      "Analyze manuscripts for continuity issues, timeline conflicts, character inconsistencies, unresolved story logic, and grounded revision context without losing your voice.",
    images: [DEFAULT_OG_IMAGE],
  },
}

const fileFormats = ["DOCX", "PDF", "EPUB", "Markdown", "TXT", "Vault"]

const LandingShowcase = dynamic(
  () => import("@/components/marketing/LandingShowcase").then((module) => module.LandingShowcase),
  {
    loading: () => (
      <section className="mx-auto min-h-[32rem] max-w-[1600px] px-5 py-20 md:px-8" aria-label="Loading product example" />
    ),
  },
)

const workflowSteps = [
  {
    step: "Upload the draft",
    body: "Start with the manuscript you already have: DOCX, PDF, EPUB, Markdown, TXT, or vault notes.",
  },
  {
    step: "Build story memory",
    body: "Characters, relationships, locations, timelines, and callbacks become editable working data.",
  },
  {
    step: "Fix the conflicts",
    body: "Review contradictions, dropped threads, timeline drift, and grounded answers while the draft is still easy to change.",
  },
]

const faqItems = [
  {
    q: "Is LoreVia a Scrivener replacement?",
    a: "LoreVia can cover manuscript writing, chapter organization, export, and revision work, but its main difference is built-in story memory, grounded answers, and continuity review tied to the draft.",
  },
  {
    q: "Is LoreVia mainly for generating prose?",
    a: "No. LoreVia is positioned as a writing and revision workspace for complex fiction manuscripts. It focuses on continuity, recall, story memory, grounded answers, and keeping the draft coherent.",
  },
  {
    q: "Can I import an existing manuscript?",
    a: "Yes. LoreVia is designed to work with drafts you already have, including common manuscript and notes formats.",
  },
  {
    q: "Is my manuscript private?",
    a: "Yes. LoreVia is built for private draft work, revision, and author-controlled sharing rather than public posting.",
  },
  {
    q: "Can LoreVia help with continuity?",
    a: "Yes. Continuity review is one of the core workflows: relationship drift, thread follow-through, detail consistency, and timeline issues can all be surfaced from the manuscript.",
  },
  {
    q: "Can I export my manuscript?",
    a: "Yes. LoreVia includes export and compile workflows so you can keep publishing progress moving without locking the book inside the platform.",
  },
]

function Section({
  id,
  className = "",
  children,
}: {
  id?: string
  className?: string
  children: ReactNode
}) {
  return (
    <section id={id} className={`mx-auto max-w-7xl px-5 py-20 md:px-8 ${className}`}>
      {children}
    </section>
  )
}

function SectionHeading({
  title,
  body,
  align = "left",
}: {
  title: string
  body?: string
  align?: "left" | "center"
}) {
  return (
    <div className={align === "center" ? "mx-auto max-w-3xl text-center" : "max-w-3xl"}>
      <h2 className="font-display text-4xl font-semibold leading-[1.02] text-white md:text-5xl">{title}</h2>
      {body ? <p className="mt-5 text-lg leading-8 text-[#aeb9b3]">{body}</p> : null}
    </div>
  )
}

function WorkflowPanel() {
  return (
    <div className="rounded-lg border border-white/[0.08] bg-[#121214] p-6 md:p-8">
      <div className="grid gap-10 lg:grid-cols-[0.8fr_1.2fr] lg:items-center">
        <div>
          <p className="text-3xs font-semibold uppercase tracking-[0.32em] text-[#d6a84f]">Revision workflow</p>
          <h2 className="mt-5 max-w-lg font-display text-4xl font-semibold leading-[1.02] text-[#f4f1ea] md:text-5xl">
            Move from memory-based revision to manuscript evidence.
          </h2>
          <p className="mt-5 max-w-xl text-lg leading-8 text-[#a09a90]">
            Import the draft, let LoreVia build the story map, then work through the conflicts with chapter evidence beside you.
          </p>
        </div>

        <div className="grid gap-4 md:grid-cols-3">
          {workflowSteps.map((item, index) => (
            <div key={item.step} className="rounded-md border border-white/[0.08] bg-[#0c0c0d] p-5">
              <div className="flex h-8 w-8 items-center justify-center rounded-md border border-[#665128] text-sm font-semibold text-[#d6a84f]">
                {index + 1}
              </div>
              <h3 className="mt-5 text-lg font-semibold text-[#f4f1ea]">{item.step}</h3>
              <p className="mt-2 text-sm leading-7 text-[#a09a90]">{item.body}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function HeroWorkspaceSummary() {
  return (
    <aside className="overflow-hidden rounded-lg border border-white/10 bg-[#121214] shadow-[0_28px_90px_rgba(0,0,0,0.35)]">
      <div className="flex items-center justify-between border-b border-white/[0.08] px-4 py-3">
        <p className="text-3xs font-semibold uppercase tracking-[0.24em] text-[#d6a84f]">Live manuscript scan</p>
        <span className="text-xs text-[#a09a90]">Sky of Ash / demo draft</span>
      </div>
      <div className="relative aspect-[2503/1389] bg-[#0c0c0d]">
        <Image
          src="/landing/manuscript-analysis.png"
          alt="LoreVia manuscript editor showing continuity issues beside a draft"
          fill
          priority
          fetchPriority="high"
          sizes="(min-width: 1024px) 62vw, 100vw"
          className="object-contain"
        />
      </div>
    </aside>
  )
}

function HomepageComparisonSection() {
  return (
    <Section id="compare" className="py-10">
      <div className="rounded-lg border border-white/[0.08] bg-[#0d1715] px-6 py-8 md:px-10">
        <div className="grid gap-6 lg:grid-cols-[1fr_auto] lg:items-center">
          <div>
            <p className="text-3xs font-semibold uppercase tracking-[0.32em] text-[#6fae9f]">Compare workflows</p>
            <h2 className="mt-4 max-w-2xl font-display text-3xl font-semibold leading-tight text-white md:text-4xl">
              Already comparing writing tools?
            </h2>
            <p className="mt-4 max-w-2xl text-base leading-7 text-[#aeb9b3]">
              Keep the homepage focused on trying LoreVia. Detailed Scrivener, Campfire, Google Docs, Novelcrafter, and Sudowrite comparisons live on the comparison hub.
            </p>
          </div>
          <Link
            href="/compare"
            className="inline-flex items-center justify-center gap-2 rounded-md border border-white/[0.12] bg-white/5 px-6 py-3.5 text-base font-semibold text-[#f4f1ea] transition hover:bg-white/[0.08]"
          >
            See detailed comparisons
            <ArrowIcon />
          </Link>
        </div>
      </div>
    </Section>
  )
}

export default function HomePage() {
  const ctaHref: Route = "/register"
  const faqJsonLd = buildFaqPageJsonLd(
    faqItems.map((item) => ({
      question: item.q,
      answer: item.a,
    })),
  )
  const softwareJsonLd = {
    "@context": "https://schema.org",
    "@type": "SoftwareApplication",
    name: SITE_NAME,
    applicationCategory: "BusinessApplication",
    operatingSystem: "Web",
    url: toAbsoluteUrl("/"),
    keywords: [
      "fiction writing workspace",
      "manuscript continuity software",
      "story memory for authors",
      "revision software",
    ],
    description:
      "LoreVia helps authors write, organize, revise, and audit complex stories in one workspace with built-in story memory, continuity intelligence, and grounded manuscript answers.",
    offers: billingPricingTiers
      .filter((tier) => tier.priceMonthly >= 0)
      .map((tier) => ({
        "@type": "Offer",
        price: tier.priceMonthly.toString(),
        priceCurrency: "USD",
        name: tier.name,
        url: toAbsoluteUrl("/pricing"),
      })),
    featureList: [
      "Manuscript writing and editing",
      "Chapter-grounded answers",
      "Automatic continuity review",
      "Editable story memory",
      "Spoiler-aware reader mode",
      "Multi-book continuity support",
    ],
  }

  return (
    <>
      <JsonLdScript id="home-faq-jsonld" data={faqJsonLd} />
      <JsonLdScript id="home-software-jsonld" data={softwareJsonLd} />

      <main className="min-h-screen bg-[#08110f] text-white">
        <div className="relative overflow-hidden">
          <MarketingHeader />

          <Section className="relative max-w-[1760px] pb-16 pt-10 md:pt-14">
            <div className="grid gap-10 lg:grid-cols-[minmax(0,1.35fr)_minmax(420px,0.85fr)] lg:items-center lg:gap-12 2xl:grid-cols-[minmax(820px,1.4fr)_minmax(500px,0.8fr)]">
              <Reveal className="lg:order-2">
                <div>
                  
                  <h1 className="max-w-2xl font-display text-5xl font-semibold leading-[0.95] tracking-[-0.025em] text-[#f4f1ea] md:text-[4.15rem] xl:text-[4.7rem]">
                    Find plot holes before your readers do.
                  </h1>
                  <p className="mt-6 max-w-xl text-lg leading-8 text-[#a09a90]">
                    LoreVia analyzes your manuscript for continuity issues, timeline conflicts, character inconsistencies, and unresolved story logic without changing your voice.
                  </p>

                  <div className="mt-8 flex flex-col gap-3 sm:flex-row">
                    <Link
                      href={ctaHref}
                      className="inline-flex items-center justify-center rounded-md bg-[#d6a84f] px-6 py-3.5 text-base font-semibold text-[#15120b] transition hover:bg-[#e4bb67]"
                    >
                      Analyze my manuscript
                    </Link>
                    <Link
                      href="/demo/workspace"
                      className="inline-flex items-center justify-center rounded-md border border-white/[0.12] bg-white/5 px-6 py-3.5 text-base font-semibold text-[#f4f1ea] transition hover:bg-white/[0.08]"
                    >
                      See a sample finding
                    </Link>
                  </div>
                  <p className="mt-3 text-sm text-[#a09a90]">
                    Includes a 10-day Author trial. No payment required.
                  </p>

                  <div className="mt-9">
                    <p className="text-sm text-[#a09a90]">Built for fiction writers, novelists, beta readers, and editors.</p>
                    <div className="mt-4 flex flex-wrap gap-3">
                      {fileFormats.map((format) => (
                        <span
                          key={format}
                          className="rounded-md border border-white/10 bg-white/5 px-4 py-2 text-sm font-medium text-[#f4f1ea]"
                        >
                          {format}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              </Reveal>

              <Reveal delay={90} className="lg:order-1">
                <HeroWorkspaceSummary />
              </Reveal>
            </div>
          </Section>
        </div>

        <LandingShowcase />

        <Section id="workflow" className="pb-18 pt-8">
          <WorkflowPanel />
        </Section>

        <HomepageComparisonSection />
        <HomePricingSection ctaHref={ctaHref} />

        <Section id="faq" className="pb-18 pt-6">
          <SectionHeading
            title="Questions worth settling before you start."
            align="center"
          />
          <div className="mx-auto mt-8 grid max-w-5xl items-start gap-4 md:grid-cols-2">
            {faqItems.map((item) => (
              <details
                key={item.q}
                className="group self-start rounded-lg border border-white/[0.08] bg-[#0d1715] p-5 open:border-[#235f57]"
              >
                <summary className="flex cursor-pointer list-none items-center justify-between gap-4 text-lg font-semibold text-white">
                  <span>{item.q}</span>
                  <span className="text-[#86decd] transition group-open:rotate-45">+</span>
                </summary>
                <p className="mt-4 text-sm leading-7 text-[#aeb9b3]">{item.a}</p>
              </details>
            ))}
          </div>
        </Section>

        <section className="mx-auto max-w-7xl px-5 pb-22 pt-6 md:px-8">
          <div className="rounded-lg border border-[#665128] bg-[#171719] px-6 py-8 md:px-10 md:py-10">
            <div className="grid gap-6 lg:grid-cols-[1fr_auto] lg:items-center">
              <div>
                <h2 className="font-display text-4xl font-semibold leading-tight text-[#f4f1ea] md:text-5xl">
                  Your manuscript already contains the answers. LoreVia helps you see where they conflict.
                </h2>
                <p className="mt-4 max-w-2xl text-lg leading-8 text-[#a09a90]">
                  Import a manuscript, build story memory, and begin revising with continuity in view.
                </p>
              </div>
              <div className="flex flex-col gap-3 sm:flex-row lg:justify-end">
                <Link
                  href={ctaHref}
                  className="inline-flex items-center justify-center rounded-md bg-[#d6a84f] px-7 py-3.5 text-base font-semibold text-[#15120b] transition hover:bg-[#e4bb67]"
                >
                  Analyze my manuscript
                </Link>
                <Link
                  href="/pricing"
                  className="inline-flex items-center justify-center rounded-md border border-white/[0.12] bg-white/5 px-7 py-3.5 text-base font-semibold text-[#f4f1ea] transition hover:bg-white/[0.08]"
                >
                  View pricing
                </Link>
              </div>
              <p className="text-sm text-[#a09a90] lg:col-start-2 lg:text-right">
                Includes a 10-day Author trial. No payment required.
              </p>
            </div>
          </div>
        </section>
      </main>
      <SiteFooter />
    </>
  )
}

function ArrowIcon() {
  return (
    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M5 12h14m-6-6 6 6-6 6" />
    </svg>
  )
}
