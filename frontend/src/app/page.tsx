import Link from "next/link"
import type { Metadata } from "next"
import type { Route } from "next"
import type { ReactNode } from "react"

import { AudienceSection } from "@/components/marketing/AudienceSection"
import { HomePricingSection } from "@/components/marketing/HomePricingSection"
import { MarketingHeader } from "@/components/marketing/MarketingHeader"
import { Reveal } from "@/components/marketing/Reveal"
import { JsonLdScript } from "@/components/seo/JsonLdScript"
import { homepageComparisonRows, comparisonIndexCards } from "@/lib/comparisons"
import { pricingTiers as billingPricingTiers } from "@/lib/billing/catalog"
import {
  DEFAULT_OG_IMAGE,
  SITE_NAME,
  SITE_URL,
  buildFaqPageJsonLd,
  toAbsoluteUrl,
} from "@/lib/seo"

export const metadata: Metadata = {
  title: "LoreVia | Write, revise, and remember every thread of your story",
  description:
    "Draft chapters, organize scenes, export manuscripts, and let LoreVia build editable story memory for characters, relationships, timelines, continuity issues, and grounded answers from your draft.",
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
    title: "LoreVia | Write, revise, and remember every thread of your story",
    description:
      "Draft chapters, organize scenes, export manuscripts, and let LoreVia build editable story memory for characters, relationships, timelines, continuity issues, and grounded answers from your draft.",
    url: SITE_URL,
    images: [DEFAULT_OG_IMAGE],
  },
  twitter: {
    card: "summary_large_image",
    title: "LoreVia | Write, revise, and remember every thread of your story",
    description:
      "Draft chapters, organize scenes, export manuscripts, and let LoreVia build editable story memory for characters, relationships, timelines, continuity issues, and grounded answers from your draft.",
    images: [DEFAULT_OG_IMAGE],
  },
}

const fileFormats = ["DOCX", "PDF", "EPUB", "Markdown", "TXT", "Obsidian"]

const featureStrip = [
  {
    title: "Chapter-grounded answers",
    body: "Ask what changed in Chapter 12 and get answers grounded in that chapter, not a generic manuscript recap.",
    icon: <QuestionIcon />,
  },
  {
    title: "Continuity review",
    body: "Catch contradictions, dropped details, and timeline mismatches before readers do.",
    icon: <CompassIcon />,
  },
  {
    title: "Character memory",
    body: "Keep editable character, relationship, and recurring-detail memory tied directly to the draft.",
    icon: <CharacterIcon />,
  },
  {
    title: "Timeline and threads",
    body: "See where plot threads begin, stall, and return so revision does not bury your story logic.",
    icon: <ThreadIcon />,
  },
  {
    title: "Export and compile",
    body: "Export clean manuscript files while keeping your working notes, scans, and story memory intact.",
    icon: <ExportIcon />,
  },
  {
    title: "Version control",
    body: "Track draft changes, compare revision passes, and restore earlier versions without losing context.",
    icon: <VersionIcon />,
  },
]

const workflowSteps = [
  {
    step: "Draft or import",
    body: "Write from scratch or bring in an existing manuscript. LoreVia keeps chapters, scenes, exports, and revisions in one place.",
  },
  {
    step: "LoreVia builds story memory",
    body: "Characters, relationships, locations, timelines, and callbacks become editable working data instead of scattered notes.",
  },
  {
    step: "Review continuity and drift",
    body: "Inspect contradictions, missing thread payoffs, and detail inconsistencies while the manuscript is still easy to correct.",
  },
  {
    step: "Ask grounded questions",
    body: "Query the draft without losing chapter context or relying on unsupported summaries.",
  },
  {
    step: "Export or keep revising",
    body: "Compile the manuscript, hand it to collaborators, or keep iterating with version history and spoiler-safe reading.",
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

function HeroProductMockup() {
  return (
    <div className="overflow-hidden rounded-[1.9rem] border border-white/10 bg-[linear-gradient(180deg,rgba(13,23,21,0.98),rgba(8,17,15,0.98))] shadow-[0_30px_90px_-52px_rgba(0,0,0,0.78)]">
      <div className="grid min-h-[36rem] lg:grid-cols-[12rem_1.25fr_14.5rem]">
        <aside className="border-b border-white/8 bg-[#0b1513] p-5 lg:border-b-0 lg:border-r">
          <div className="rounded-xl border border-white/8 bg-white/5 px-3 py-2 text-sm text-[#d9e0db]">
            Bloodline of Dawn
          </div>
          <div className="mt-6">
            <p className="text-[10px] uppercase tracking-[0.22em] text-[#6fae9f]">Manuscript</p>
            <div className="mt-3 space-y-2">
              {["Chapters", "Scenes", "Manuscript", "Outline", "Notes", "Bookmarks"].map((item, index) => (
                <div
                  key={item}
                  className={`rounded-xl px-3 py-2.5 text-sm ${
                    index === 0 ? "bg-[#11312d] text-[#85e1ce]" : "text-[#9fb0a8]"
                  }`}
                >
                  {item}
                </div>
              ))}
            </div>
          </div>
        </aside>

        <div className="border-b border-white/8 p-5 lg:border-b-0 lg:border-r lg:p-7">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-3">
                <h3 className="font-display text-3xl text-white">Chapter 12</h3>
                <span className="rounded-full border border-[#1e5a53] bg-[#102a27] px-3 py-1 text-xs font-semibold text-[#7fd7c5]">
                  Saved just now
                </span>
              </div>
              <div className="mt-4 flex gap-5 text-sm text-[#8fa19a]">
                {["Write", "Preview", "Stats"].map((tab, index) => (
                  <span key={tab} className={index === 0 ? "font-semibold text-white" : ""}>
                    {tab}
                  </span>
                ))}
              </div>
            </div>
            <div className="flex gap-2 text-xs text-[#8fa19a]">
              {["Normal", "B", "I", "H2", "List"].map((tool) => (
                <span key={tool} className="rounded-lg border border-white/8 bg-white/5 px-2.5 py-1.5">
                  {tool}
                </span>
              ))}
            </div>
          </div>

          <div className="mt-7 rounded-[1.35rem] border border-white/8 bg-[#0c1413] p-6">
            <h4 className="font-display text-3xl text-white">Chapter 12</h4>
            <div className="mt-5 space-y-4 text-sm leading-8 text-[#d9e0db]">
              <p>
                The convoy moved through the valley in uneasy silence. Kael kept his eyes forward, though every instinct told him they were being watched.
              </p>
              <p>
                Mira studied the ridgeline, tracking faint movements in the rock and shadow. The landscape always remembered what people tried to forget.
              </p>
              <p>
                Behind them, someone asked a question no one wanted to answer.
              </p>
              <p>&quot;Are we still following the right trail?&quot;</p>
            </div>
            <div className="mt-5 flex flex-wrap items-center justify-between gap-3 border-t border-white/8 pt-4 text-xs uppercase tracking-[0.18em] text-[#72827b]">
              <span>6,432 words</span>
              <span>Reading time: 34 min</span>
            </div>
          </div>
        </div>

        <aside className="bg-[#091310] p-5">
          <div className="flex items-center gap-2 text-xs text-[#8fa19a]">
            {["Context", "Advisor", "Notes"].map((tab, index) => (
              <span
                key={tab}
                className={`rounded-full px-3 py-1.5 ${index === 0 ? "border border-[#225a53] bg-[#102b27] text-[#86decd]" : "border border-transparent bg-transparent"}`}
              >
                {tab}
              </span>
            ))}
          </div>

          <div className="mt-6 rounded-[1.25rem] border border-white/8 bg-[#0d1715] p-4">
            <p className="text-[10px] uppercase tracking-[0.24em] text-[#6fae9f]">Continuity findings</p>
            <div className="mt-4 space-y-3">
              {[
                ["Character age", "Possible mismatch for Elira between ch. 7 and ch. 12"],
                ["Timeline gap", "Travel time between ch. 9 and ch. 10 is unusually short"],
                ["Unresolved thread", "The letter from Mara has not been addressed since ch. 7"],
              ].map(([title, body]) => (
                <div key={title} className="rounded-xl border border-white/8 bg-[#101a18] p-3">
                  <p className="text-sm font-semibold text-white">{title}</p>
                  <p className="mt-2 text-sm leading-6 text-[#9fb0a8]">{body}</p>
                </div>
              ))}
            </div>
          </div>

          <div className="mt-4 rounded-[1.25rem] border border-white/8 bg-[#0d1715] p-4">
            <p className="text-[10px] uppercase tracking-[0.24em] text-[#6fae9f]">Ask LoreVia</p>
            <div className="mt-3 rounded-xl border border-white/8 bg-[#101a18] px-3 py-3 text-sm text-[#d9e0db]">
              What are the stakes in this chapter?
            </div>
            <p className="mt-3 text-sm leading-6 text-[#9fb0a8]">
              Kael risks losing the old order lead, exposing Mira's deception, and breaking the fragile trust they have left with Elias.
            </p>
          </div>
        </aside>
      </div>
    </div>
  )
}

function WorkflowPanel() {
  return (
    <div className="rounded-[2rem] border border-white/8 bg-[linear-gradient(180deg,rgba(12,22,20,0.98),rgba(8,17,15,0.98))] p-6 md:p-8">
      <div className="grid gap-8 lg:grid-cols-[0.85fr_1.15fr]">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.32em] text-[#6fae9f]">Your writing workflow</p>
          <h2 className="mt-5 max-w-lg font-display text-4xl font-semibold leading-[1.02] text-white md:text-5xl">
            A workspace that guides your entire process
          </h2>
          <div className="mt-8 space-y-5">
            {workflowSteps.map((item, index) => (
              <div key={item.step} className="flex gap-4">
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-[#2a6f67] text-sm font-semibold text-[#86decd]">
                  {index + 1}
                </div>
                <div>
                  <h3 className="text-lg font-semibold text-white">{item.step}</h3>
                  <p className="mt-2 text-sm leading-7 text-[#aeb9b3]">{item.body}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="space-y-4">
          <div className="grid gap-4 md:grid-cols-3">
            {[
              ["Characters", "23", "Total characters"],
              ["Plot threads", "17", "Active threads"],
              ["Timeline events", "86", "Tracked events"],
            ].map(([label, value, note]) => (
              <div key={label} className="rounded-[1.3rem] border border-white/8 bg-[#0d1715] p-5">
                <p className="text-[10px] uppercase tracking-[0.22em] text-[#6fae9f]">{label}</p>
                <p className="mt-3 text-4xl font-semibold tracking-tight text-white">{value}</p>
                <p className="mt-2 text-sm text-[#8fa19a]">{note}</p>
              </div>
            ))}
          </div>

          <div className="grid gap-4 md:grid-cols-[0.8fr_1.2fr_0.7fr]">
            <div className="rounded-[1.3rem] border border-white/8 bg-[#0d1715] p-5">
              <p className="text-[10px] uppercase tracking-[0.22em] text-[#6fae9f]">Continuity score</p>
              <p className="mt-3 text-4xl font-semibold tracking-tight text-white">92%</p>
              <div className="mt-4 h-2 overflow-hidden rounded-full bg-white/8">
                <div className="h-full w-[92%] rounded-full bg-[#4fb6a3]" />
              </div>
              <p className="mt-3 text-sm text-[#8fa19a]">Good</p>
            </div>

            <div className="rounded-[1.3rem] border border-white/8 bg-[#0d1715] p-5">
              <p className="text-[10px] uppercase tracking-[0.22em] text-[#6fae9f]">Recent finding</p>
              <p className="mt-4 text-lg font-semibold text-white">Timeline gap</p>
              <p className="mt-2 text-sm leading-7 text-[#aeb9b3]">
                Travel time between ch. 9 and ch. 10 is unusually short for the route the manuscript establishes.
              </p>
              <div className="mt-4 inline-flex rounded-full border border-[#276a63] bg-[#11312d] px-3 py-1.5 text-xs font-semibold text-[#86decd]">
                Review finding
              </div>
            </div>

            <div className="rounded-[1.3rem] border border-white/8 bg-[#0d1715] p-5">
              <p className="text-[10px] uppercase tracking-[0.22em] text-[#6fae9f]">Chapters</p>
              <p className="mt-3 text-4xl font-semibold tracking-tight text-white">24</p>
              <p className="mt-2 text-sm text-[#8fa19a]">Total chapters</p>
            </div>
          </div>

          <div className="rounded-[1.35rem] border border-white/8 bg-[#0d1715] p-5">
            <p className="text-[10px] uppercase tracking-[0.22em] text-[#6fae9f]">Ask LoreVia about your manuscript</p>
            <div className="mt-4 rounded-xl border border-white/8 bg-[#0b1513] px-4 py-3 text-sm text-[#d9e0db]">
              What are the motivations driving Kael in the last three chapters?
            </div>
            <div className="mt-4 rounded-xl border border-[#20443f] bg-[#0e1d1b] p-4">
              <p className="text-sm leading-7 text-[#d9e0db]">
                In the last three chapters, Kael is driven by three core motivations:
              </p>
              <ul className="mt-3 space-y-2 text-sm leading-7 text-[#aeb9b3]">
                <li>- Protecting his sister at any cost</li>
                <li>- Finding the truth about the old order</li>
                <li>- Earning the trust of a reluctant ally</li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

function HomepageComparisonSection() {
  return (
    <Section id="compare" className="pt-8">
      <div className="grid gap-8 lg:grid-cols-[0.85fr_1.15fr] lg:items-start">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.32em] text-[#6fae9f]">Comparison</p>
          <h2 className="mt-5 max-w-lg font-display text-4xl font-semibold leading-[1.02] text-white md:text-5xl">
            A writing workspace that understands the manuscript.
          </h2>
          <p className="mt-5 max-w-xl text-lg leading-8 text-[#aeb9b3]">
            Traditional tools help you write and organize. LoreVia does that too, then automatically builds editable story memory, checks continuity, and answers grounded questions from your draft.
          </p>

          <div className="mt-7">
            <p className="text-sm font-semibold uppercase tracking-[0.22em] text-[#8fa19a]">
              Detailed comparisons
            </p>
            <div className="mt-4 grid gap-3">
              {comparisonIndexCards.map((item) => (
                <Link
                  key={item.slug}
                  href={`/compare/${item.slug}`}
                  className="rounded-[1.2rem] border border-white/8 bg-white/5 px-4 py-4 transition hover:border-white/16 hover:bg-white/8"
                >
                  <p className="text-base font-semibold text-white">LoreVia vs {item.name}</p>
                  <p className="mt-2 text-sm leading-7 text-[#9fb0a8]">{item.summary}</p>
                </Link>
              ))}
            </div>
          </div>

          <Link
            href="/compare"
            className="mt-5 inline-flex items-center gap-2 text-sm font-semibold text-[#86decd] transition hover:text-white"
          >
            See detailed comparisons
            <ArrowIcon />
          </Link>
        </div>

        <div className="overflow-hidden rounded-[1.75rem] border border-white/10 bg-[#0d1715] shadow-[0_24px_70px_-48px_rgba(0,0,0,0.72)]">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] border-separate border-spacing-0 text-left text-sm">
              <thead>
                <tr className="text-[#9fb0a8]">
                  {["Feature", "Scrivener", "Campfire", "Google Docs", "LoreVia"].map((heading) => (
                    <th
                      key={heading}
                      className={`border-b border-white/8 px-5 py-4 font-semibold ${
                        heading === "LoreVia" ? "bg-[#0f2320] text-[#7ad3c1]" : ""
                      }`}
                    >
                      {heading}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {homepageComparisonRows.map((row) => (
                  <tr key={row.feature} className="text-[#d9e0db]">
                    <td className="border-b border-white/6 px-5 py-4 font-medium text-white">{row.feature}</td>
                    <td className="border-b border-white/6 px-5 py-4 text-[#aeb9b3]">{row.scrivener}</td>
                    <td className="border-b border-white/6 px-5 py-4 text-[#aeb9b3]">{row.campfire}</td>
                    <td className="border-b border-white/6 px-5 py-4 text-[#aeb9b3]">{row.googleDocs}</td>
                    <td className="border-b border-[#14433d] bg-[#0f2320] px-5 py-4 font-semibold text-[#85e1ce]">
                      {row.lorevia}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
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
          <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(38,94,87,0.22),transparent_36%),radial-gradient(circle_at_top_right,rgba(20,54,49,0.18),transparent_28%)]" />
          <MarketingHeader />

          <Section className="relative pb-14 pt-12 md:pt-14">
            <div className="grid gap-10 lg:grid-cols-[0.85fr_1.25fr] lg:items-center">
              <Reveal>
                <div>
                  
                  <h1 className="mt-8 max-w-2xl font-display text-5xl font-semibold leading-[0.95] tracking-[-0.045em] text-white md:text-[5.5rem]">
                    Revise coherently.                  <br />
                     <span className="text-[#67c6b4]">LoreVia remembers every thread.</span>
                  </h1>
                  <p className="mt-6 max-w-xl text-lg leading-8 text-[#aeb9b3]">
                    Draft, organize, export, and let LoreVia track your story’s characters, timelines, relationships, and continuity.
                  </p>

                  <div className="mt-8 flex flex-col gap-3 sm:flex-row">
                    <Link
                      href={ctaHref}
                      className="inline-flex items-center justify-center rounded-xl bg-[#1f615d] px-6 py-3.5 text-base font-semibold text-white transition hover:bg-[#25756f]"
                    >
                      Start writing free
                    </Link>
                    <Link
                      href="/pricing"
                      className="inline-flex items-center justify-center rounded-xl border border-white/12 bg-white/5 px-6 py-3.5 text-base font-semibold text-white transition hover:bg-white/8"
                    >
                      View pricing
                    </Link>
                  </div>

                  <div className="mt-9">
                    <p className="text-sm text-[#8fa19a]">Works with your files</p>
                    <div className="mt-4 flex flex-wrap gap-3">
                      {fileFormats.map((format) => (
                        <span
                          key={format}
                          className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm font-medium text-[#d9e0db]"
                        >
                          {format}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              </Reveal>

              <Reveal delay={90}>
                <HeroProductMockup />
              </Reveal>
            </div>
          </Section>
        </div>

        <Section id="features" className="pb-18 pt-4">
          <SectionHeading
            title="Everything you need to write with clarity"
            align="center"
          />
          <div className="mt-8 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {featureStrip.map((item, index) => (
              <Reveal key={item.title} delay={index * 60}>
                <article className="h-full rounded-[1.5rem] border border-white/8 bg-[#0d1715] p-5 md:p-6">
                  <div className="inline-flex h-12 w-12 items-center justify-center rounded-full border border-white/10 bg-white/5 text-[#7fd7c5]">
                    {item.icon}
                  </div>
                  <h3 className="mt-5 text-2xl font-semibold text-white">{item.title}</h3>
                  <p className="mt-4 text-sm leading-7 text-[#aeb9b3]">{item.body}</p>
                </article>
              </Reveal>
            ))}
          </div>
        </Section>

        <Section id="workflow" className="pb-18 pt-8">
          <WorkflowPanel />
        </Section>

        <AudienceSection />
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
                className="group self-start rounded-[1.3rem] border border-white/8 bg-[#0d1715] p-5 open:border-[#235f57]"
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
          <div className="rounded-[2rem] border border-[#1e5a53] bg-[linear-gradient(180deg,rgba(18,50,46,0.98),rgba(10,24,21,0.98))] px-6 py-8 shadow-[0_24px_60px_-40px_rgba(13,58,53,0.6)] md:px-10 md:py-10">
            <div className="grid gap-6 lg:grid-cols-[1fr_auto] lg:items-center">
              <div>
                <h2 className="font-display text-4xl font-semibold leading-tight text-white md:text-5xl">
                  Start with the draft you already have.
                </h2>
                <p className="mt-4 max-w-2xl text-lg leading-8 text-[#aeb9b3]">
                  Import a manuscript, build story memory, and begin revising with continuity in view.
                </p>
              </div>
              <div className="flex flex-col gap-3 sm:flex-row lg:justify-end">
                <Link
                  href={ctaHref}
                  className="inline-flex items-center justify-center rounded-xl bg-[#1f615d] px-7 py-3.5 text-base font-semibold text-white transition hover:bg-[#25756f]"
                >
                  Start free
                </Link>
                <Link
                  href="/pricing"
                  className="inline-flex items-center justify-center rounded-xl border border-white/12 bg-white/5 px-7 py-3.5 text-base font-semibold text-white transition hover:bg-white/8"
                >
                  View pricing
                </Link>
              </div>
            </div>
          </div>
        </section>
      </main>
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

function QuestionIcon() {
  return (
    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M9.5 9a2.5 2.5 0 115 0c0 1.8-2.5 2.1-2.5 4" />
      <circle cx="12" cy="17.5" r="0.75" fill="currentColor" stroke="none" />
      <circle cx="12" cy="12" r="9" />
    </svg>
  )
}

function CompassIcon() {
  return (
    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
      <circle cx="12" cy="12" r="8.5" />
      <path strokeLinecap="round" strokeLinejoin="round" d="m14.9 9.1-2.8 5.8-5.8 2.8 2.8-5.8 5.8-2.8Z" />
    </svg>
  )
}

function CharacterIcon() {
  return (
    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
      <circle cx="12" cy="8.5" r="3.25" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M5.5 18.5c1.4-2.7 3.6-4 6.5-4s5.1 1.3 6.5 4" />
    </svg>
  )
}

function ThreadIcon() {
  return (
    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M7.5 8.5h9m-9 7h9" />
      <circle cx="7" cy="8.5" r="1.75" fill="none" />
      <circle cx="17" cy="15.5" r="1.75" fill="none" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M8.7 9.7 15.3 14.3" />
    </svg>
  )
}

function ExportIcon() {
  return (
    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v10" />
      <path strokeLinecap="round" strokeLinejoin="round" d="m8.5 10.5 3.5 3.5 3.5-3.5" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M5 18.5h14" />
    </svg>
  )
}

function VersionIcon() {
  return (
    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 6.5v5l3.5 2" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M5.5 12A6.5 6.5 0 1 0 8 7" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 7.5H8v3.5" />
    </svg>
  )
}
