import Link from "next/link"
import type { Metadata } from "next"
import type { Route } from "next"
import type { ReactNode } from "react"

import { AudienceSection } from "@/components/marketing/AudienceSection"
import { HomePricingSection } from "@/components/marketing/HomePricingSection"
import { Reveal } from "@/components/marketing/Reveal"
import { BrandLockup } from "@/components/layout/BrandLockup"
import { pricingTiers as billingPricingTiers } from "@/lib/billing/catalog"
import { JsonLdScript } from "@/components/seo/JsonLdScript"
import {
  DEFAULT_OG_IMAGE,
  SITE_NAME,
  SITE_URL,
  buildFaqPageJsonLd,
  toAbsoluteUrl,
} from "@/lib/seo"

export const metadata: Metadata = {
  title: "LoreVia | A calmer manuscript workspace for fiction authors",
  description:
    "LoreVia helps fiction authors keep a manuscript coherent while revising with grounded story memory, continuity review, and a calmer drafting workspace.",
  keywords: [
    "fiction writing software",
    "manuscript analysis tool",
    "continuity checker for fiction",
    "character tracking for writers",
    "story bible software",
    "novel revision software",
  ],
  alternates: {
    canonical: "/",
  },
  openGraph: {
    title: "LoreVia | A calmer manuscript workspace for fiction authors",
    description:
      "LoreVia helps fiction authors keep a manuscript coherent while revising with grounded story memory, continuity review, and a calmer drafting workspace.",
    url: SITE_URL,
    images: [DEFAULT_OG_IMAGE],
  },
  twitter: {
    card: "summary_large_image",
    title: "LoreVia | A calmer manuscript workspace for fiction authors",
    description:
      "LoreVia helps fiction authors keep a manuscript coherent while revising with grounded story memory, continuity review, and a calmer drafting workspace.",
    images: [DEFAULT_OG_IMAGE],
  },
}

const navItems = [
  { label: "Product", href: "#product" },
  { label: "Use cases", href: "#audiences" },
  { label: "Pricing", href: "#pricing" },
  { label: "FAQ", href: "#faq" },
]

const fileFormats = ["DOCX", "PDF", "EPUB", "MD", "TXT", "Obsidian"]

const workspaceModules = [
  {
    title: "Manuscript workspace",
    body: "Draft, revise, and leave yourself usable context without scattering the book across tools.",
  },
  {
    title: "Character memory",
    body: "Keep names, relationships, motives, and appearances attached to the draft they belong to.",
  },
  {
    title: "Continuity review",
    body: "Surface contradictions, dropped threads, and small drift before they become expensive to fix.",
  },
  {
    title: "Story advisor",
    body: "Ask the manuscript direct questions and get grounded answers you can check against the text.",
  },
]

const comparisonRows = [
  ["Manual story memory", "Required", "Required", "Required", "Reduced"],
  ["Automatic continuity scans", "No", "No", "No", "Yes"],
  ["Chapter-grounded answers", "No", "No", "No", "Yes"],
  ["Character relationship tracking", "Manual", "Partial", "No", "Automatic"],
  ["Series-aware recall", "No", "Partial", "No", "Yes"],
]

const faqItems = [
  {
    q: "Will LoreVia spoil future chapters?",
    a: "No. Shared access can stop at a chosen chapter so reader-facing views stay spoiler-safe.",
  },
  {
    q: "Can I use it before publication?",
    a: "Yes. LoreVia is built for private drafts, revision, and pre-publication manuscript work.",
  },
  {
    q: "What files can I import?",
    a: "DOCX, PDF, EPUB, Markdown, plain text, and Obsidian-style notes are all supported.",
  },
  {
    q: "Can I export my work?",
    a: "Yes. You can export manuscript and reference materials without locking the project inside LoreVia.",
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

function SectionHeader({
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
      <h2 className="font-display text-4xl font-semibold leading-tight text-stone-950 md:text-5xl">{title}</h2>
      {body ? <p className="mt-4 text-base leading-8 text-stone-600">{body}</p> : null}
    </div>
  )
}

function CheckIcon() {
  return (
    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="m5 13 4 4L19 7" />
    </svg>
  )
}

function ArrowIcon() {
  return (
    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M5 12h14m-6-6 6 6-6 6" />
    </svg>
  )
}

function HeroWorkspacePreview() {
  return (
    <div className="overflow-hidden rounded-[1.6rem] border border-[rgba(var(--border),0.9)] bg-[#f6f1e8] shadow-[0_24px_60px_-42px_rgba(58,49,37,0.18)]">
      <div className="grid min-h-[33rem] lg:grid-cols-[13rem_1fr]">
        <aside className="border-b border-[rgba(var(--border),0.8)] bg-[#ece5da] p-5 lg:border-b-0 lg:border-r">
          <BrandLockup size="sm" />
          <div className="mt-8 space-y-2">
            {["Overview", "Manuscript", "Story advisor", "Characters", "Notes"].map((item, index) => (
              <div
                key={item}
                className={`rounded-xl px-3 py-2.5 text-sm font-medium ${
                  index === 0 ? "bg-[#fbf8f2] text-stone-950 shadow-sm" : "text-stone-500"
                }`}
              >
                {item}
              </div>
            ))}
          </div>
        </aside>

        <div className="p-5 md:p-7">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <p className="text-sm text-stone-500">The Last Lighthouse</p>
              <h3 className="mt-1 font-display text-3xl text-stone-950">Overview</h3>
            </div>
            <div className="rounded-xl border border-[rgba(var(--border),0.9)] bg-[#fbf8f2] px-4 py-2 text-sm font-semibold text-teal-800">
              Open manuscript
            </div>
          </div>

          <div className="mt-6 grid gap-3 md:grid-cols-4">
            {[
              ["Manuscript status", "In progress"],
              ["Pacing", "Keep building"],
              ["Tension", "Rising"],
              ["Clarity", "Clear"],
            ].map(([label, value]) => (
              <div key={label} className="rounded-[1.1rem] border border-[rgba(var(--border),0.9)] bg-[#fbf8f2] p-4">
                <p className="text-xs uppercase tracking-[0.16em] text-stone-400">{label}</p>
                <p className="mt-3 text-sm font-semibold text-teal-800">{value}</p>
              </div>
            ))}
          </div>

          <div className="mt-6 grid gap-4 lg:grid-cols-[1.15fr_0.85fr]">
            <div className="rounded-[1.25rem] border border-[rgba(var(--border),0.9)] bg-[#fbf8f2] p-5">
              <div className="flex items-center justify-between gap-3">
                <h4 className="font-display text-2xl text-stone-950">Story structure</h4>
                <span className="text-sm text-stone-500">Chapter 4</span>
              </div>
              <div className="mt-5 space-y-3">
                {["The Call", "Crossing the Line", "Into the Unknown", "First Clash"].map((step, index) => (
                  <div key={step} className={`flex items-center justify-between rounded-xl px-3 py-2 ${index === 3 ? "bg-[#ece5da]" : ""}`}>
                    <span className="text-sm text-stone-700">{step}</span>
                    <span className={`h-2.5 w-2.5 rounded-full ${index < 3 ? "bg-teal-700/30" : "bg-teal-800"}`} />
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded-[1.25rem] border border-[rgba(var(--border),0.9)] bg-[#fbf8f2] p-5">
              <h4 className="font-display text-2xl text-stone-950">Story advisor</h4>
              <p className="mt-3 text-sm leading-7 text-stone-600">
                Chapter 4 lands the turn well. The pressure is there, but the middle could carry cleaner cause and effect.
              </p>
              <div className="mt-5 space-y-3">
                {[
                  "The midpoint setup is holding.",
                  "Nora's motive is still clear on the page.",
                  "The ending keeps the chapter moving forward.",
                ].map((item) => (
                  <div key={item} className="flex gap-3 rounded-xl bg-[#ece5da] px-3 py-3 text-sm text-stone-700">
                    <span className="mt-0.5 text-teal-800"><CheckIcon /></span>
                    <span>{item}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

function ProductProof() {
  return (
    <Section id="product" className="pt-8">
      <div className="grid gap-4 lg:grid-cols-3">
        {[
          {
            title: "Chapter-grounded answers",
            body: "Ask what happened, who knows what, or where a thread began and answer it against the draft instead of memory.",
          },
          {
            title: "Continuity review",
            body: "See contradictions, unresolved promises, duplicate naming, and weak recall while they are still easy to repair.",
          },
          {
            title: "Character memory",
            body: "Keep relationship shifts, aliases, motives, and appearances attached to the manuscript rather than buried in notes.",
          },
        ].map((item) => (
          <Reveal key={item.title}>
            <article className="h-full rounded-[1.4rem] border border-[rgba(var(--border),0.9)] bg-[#f6f1e8] p-6 shadow-[0_18px_44px_-38px_rgba(58,49,37,0.14)]">
              <p className="text-xs uppercase tracking-[0.16em] text-teal-800">LoreVia</p>
              <h3 className="mt-4 font-display text-3xl text-stone-950">{item.title}</h3>
              <p className="mt-4 text-sm leading-7 text-stone-600">{item.body}</p>
            </article>
          </Reveal>
        ))}
      </div>
    </Section>
  )
}

function WorkspaceSection() {
  return (
    <Section>
      <div className="grid gap-10 lg:grid-cols-[0.84fr_1.16fr] lg:items-start">
        <Reveal>
          <div>
            <SectionHeader
              title="One place to draft, remember, and revise."
              body="Upload the manuscript once, then return to a workspace that keeps the book legible to you across weeks, edits, and rewrites."
            />
            <div className="mt-8 grid gap-px overflow-hidden rounded-[1.4rem] border border-[rgba(var(--border),0.9)] bg-[rgba(var(--border),0.65)]">
              {workspaceModules.map((item) => (
                <div key={item.title} className="bg-[#f6f1e8] p-5">
                  <h3 className="text-lg font-semibold text-stone-950">{item.title}</h3>
                  <p className="mt-2 text-sm leading-7 text-stone-600">{item.body}</p>
                </div>
              ))}
            </div>
          </div>
        </Reveal>

        <Reveal delay={90}>
          <div className="rounded-[1.6rem] border border-[rgba(var(--border),0.9)] bg-[#f4eee4] p-5 shadow-[0_24px_60px_-42px_rgba(58,49,37,0.16)]">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-sm text-stone-500">Library</p>
                <h3 className="mt-1 font-display text-3xl text-stone-950">Return without rebuilding context.</h3>
              </div>
              <button type="button" className="rounded-xl bg-teal-800 px-4 py-2 text-sm font-semibold text-white">
                New manuscript
              </button>
            </div>

            <div className="mt-6 grid gap-4 md:grid-cols-3">
              {[
                ["The Last Lighthouse", "Fantasy - 82,000 words"],
                ["Beneath the Lake", "Mystery - 67,300 words"],
                ["Ashes of Tomorrow", "Sci-Fi - 91,200 words"],
              ].map(([title, meta], index) => (
                <div key={title} className="rounded-[1.1rem] border border-[rgba(var(--border),0.9)] bg-[#fbf8f2] p-4">
                  <div className={`aspect-[0.72] rounded-[0.9rem] ${index === 0 ? "bg-[#7b8a87]" : index === 1 ? "bg-[#b7ab94]" : "bg-[#d4c8b1]"}`} />
                  <h4 className="mt-4 text-base font-semibold text-stone-950">{title}</h4>
                  <p className="mt-1 text-sm text-stone-500">{meta}</p>
                </div>
              ))}
            </div>

            <div className="mt-6 rounded-[1.1rem] border border-[rgba(var(--border),0.9)] bg-[#fbf8f2] p-5">
              <p className="text-sm text-stone-500">Continue editing</p>
              <div className="mt-3 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <h4 className="text-lg font-semibold text-stone-950">The Last Lighthouse</h4>
                  <p className="mt-1 text-sm text-stone-600">Chapter 8 - Into the Storm</p>
                </div>
                <button type="button" className="inline-flex items-center gap-2 rounded-xl bg-teal-800 px-4 py-2 text-sm font-semibold text-white">
                  Open manuscript
                  <ArrowIcon />
                </button>
              </div>
            </div>
          </div>
        </Reveal>
      </div>
    </Section>
  )
}

function ComparisonSection() {
  return (
    <Section>
      <SectionHeader
        title="Most writing tools store the work. They do not hold the book together."
        body="LoreVia is for revision pressure: when character memory, continuity, and story recall start to matter more than file storage."
      />
      <Reveal>
        <div className="mt-8 overflow-hidden rounded-[1.5rem] border border-[rgba(var(--border),0.9)] bg-[#f6f1e8]">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[760px] border-separate border-spacing-0 text-left text-sm">
              <thead>
                <tr className="text-stone-500">
                  {["Feature", "Scrivener", "Campfire", "Google Docs", "LoreVia"].map((head) => (
                    <th
                      key={head}
                      className={`border-b border-[rgba(var(--border),0.9)] px-5 py-4 font-semibold ${
                        head === "LoreVia" ? "bg-teal-700/8 text-teal-900" : ""
                      }`}
                    >
                      {head}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {comparisonRows.map((row) => (
                  <tr key={row[0]} className="text-stone-700">
                    {row.map((cell, index) => (
                      <td
                        key={`${row[0]}-${index}`}
                        className={`border-b border-[rgba(var(--border),0.75)] px-5 py-4 ${
                          index === 0 ? "font-medium text-stone-950" : ""
                        } ${index === 4 ? "bg-teal-700/8 font-semibold text-teal-900" : ""}`}
                      >
                        {cell}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </Reveal>
    </Section>
  )
}

function FAQSection() {
  return (
    <Section id="faq">
      <SectionHeader title="Questions worth settling before you trust a draft to a new workspace." align="center" />
      <div className="mt-10 grid gap-4 md:grid-cols-2">
        {faqItems.map((item) => (
          <Reveal key={item.q}>
            <article className="h-full rounded-[1.35rem] border border-[rgba(var(--border),0.9)] bg-[#f6f1e8] p-6">
              <h3 className="text-lg font-semibold text-stone-950">{item.q}</h3>
              <p className="mt-3 text-sm leading-7 text-stone-600">{item.a}</p>
            </article>
          </Reveal>
        ))}
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
      "fiction writing software",
      "manuscript analysis",
      "continuity checker",
      "story bible",
    ],
    description:
      "LoreVia helps fiction authors keep a manuscript coherent while revising with grounded story memory, continuity review, and a calmer drafting workspace.",
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
      "Grounded story recall",
      "Continuity review",
      "Character memory",
      "Chapter-grounded questions",
      "Revision workspace",
      "Beta-reader collaboration",
    ],
  }

  return (
    <main className="min-h-screen bg-[#f1ece3] text-stone-950">
      <JsonLdScript id="home-faq-jsonld" data={faqJsonLd} />
      <JsonLdScript id="home-software-jsonld" data={softwareJsonLd} />

      <header className="sticky top-0 z-50 border-b border-[rgba(var(--border),0.9)] bg-[rgba(241,236,227,0.96)] backdrop-blur-sm">
        <div className="mx-auto flex h-[76px] max-w-7xl items-center justify-between px-5 md:px-8">
          <Link href="/" aria-label="LoreVia home">
            <BrandLockup size="md" />
          </Link>
          <nav className="hidden items-center gap-8 lg:flex">
            {navItems.map((item) => (
              <a
                key={item.label}
                href={item.href}
                className="text-[14px] font-medium text-stone-600 transition hover:text-stone-950"
              >
                {item.label}
              </a>
            ))}
          </nav>
          <div className="flex items-center gap-3">
            <Link href="/blog" className="hidden px-4 py-2 text-[14px] font-medium text-stone-600 transition hover:text-stone-950 sm:inline-flex">
              Blog
            </Link>
            <Link href="/login" className="hidden px-4 py-2 text-[14px] font-medium text-stone-600 transition hover:text-stone-950 sm:inline-flex">
              Sign in
            </Link>
            <Link
              href={ctaHref}
              className="rounded-xl bg-teal-800 px-4 py-2.5 text-[14px] font-semibold text-white transition hover:bg-teal-700"
            >
              Start free
            </Link>
          </div>
        </div>
      </header>

      <Section className="pb-10 pt-10 md:pt-14">
        <div className="grid gap-10 lg:grid-cols-[0.82fr_1.18fr] lg:items-center">
          <Reveal>
            <div>
              <h1 className="max-w-xl font-display text-5xl font-semibold leading-[0.96] text-stone-950 md:text-7xl">
                Keep the manuscript coherent while you revise.
              </h1>
              <p className="mt-6 max-w-xl text-lg leading-8 text-stone-600">
                LoreVia gives fiction authors a calmer workspace for story recall, continuity review, and revision decisions that stay tied to the draft.
              </p>
              <div className="mt-8 flex flex-col gap-3 sm:flex-row">
                <Link
                  href={ctaHref}
                  className="inline-flex items-center justify-center gap-2 rounded-xl bg-teal-800 px-6 py-3.5 text-base font-semibold text-white transition hover:bg-teal-700"
                >
                  Start free
                </Link>
                <a
                  href="#product"
                  className="inline-flex items-center justify-center gap-2 rounded-xl border border-[rgba(var(--border),0.9)] bg-[#fbf8f2] px-6 py-3.5 text-base font-semibold text-stone-900 transition hover:bg-[#f6f1e8]"
                >
                  See how it works
                </a>
              </div>

              <div className="mt-10">
                <p className="text-sm text-stone-500">Works with your files</p>
                <div className="mt-4 flex flex-wrap gap-3">
                  {fileFormats.map((format) => (
                    <span key={format} className="rounded-full border border-[rgba(var(--border),0.9)] bg-[#ece5da] px-4 py-2 text-sm font-medium text-stone-700">
                      {format}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          </Reveal>

          <Reveal delay={90}>
            <HeroWorkspacePreview />
          </Reveal>
        </div>
      </Section>

      <ProductProof />
      <WorkspaceSection />
      <AudienceSection />
      <ComparisonSection />
      <HomePricingSection ctaHref={ctaHref} />
      <FAQSection />

      <section className="border-t border-[rgba(var(--border),0.9)] bg-[#ece6dc]">
        <div className="mx-auto grid max-w-7xl gap-8 px-5 py-18 md:px-8 lg:grid-cols-[1fr_auto] lg:items-center">
          <div>
            <h2 className="font-display text-4xl font-semibold leading-tight text-stone-950 md:text-5xl">
              Start with the draft you already have.
            </h2>
            <p className="mt-4 max-w-2xl text-lg leading-8 text-stone-600">
              Bring in a manuscript, keep the book legible to yourself, and revise from firmer ground.
            </p>
          </div>
          <div className="flex flex-col gap-3 sm:flex-row lg:justify-end">
            <Link href={ctaHref} className="inline-flex items-center justify-center rounded-xl bg-teal-800 px-7 py-4 text-base font-semibold text-white transition hover:bg-teal-700">
              Start free
            </Link>
            <a href="#pricing" className="inline-flex items-center justify-center rounded-xl border border-[rgba(var(--border),0.9)] bg-[#fbf8f2] px-7 py-4 text-base font-semibold text-stone-900 transition hover:bg-[#f6f1e8]">
              View pricing
            </a>
          </div>
        </div>
      </section>
    </main>
  )
}
