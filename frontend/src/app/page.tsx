import Link from "next/link"
import Script from "next/script"
import type { Metadata } from "next"
import type { Route } from "next"
import type { ReactNode } from "react"
import { AudienceSection } from "@/components/marketing/AudienceSection"
import { HomePricingSection } from "@/components/marketing/HomePricingSection"
import { Reveal } from "@/components/marketing/Reveal"
import { BrandLockup } from "@/components/layout/BrandLockup"
import { pricingTiers as billingPricingTiers } from "@/lib/billing/catalog"
import {
  DEFAULT_OG_IMAGE,
  SITE_NAME,
  SITE_URL,
  buildFaqPageJsonLd,
  toAbsoluteUrl,
} from "@/lib/seo"

export const metadata: Metadata = {
  title: "Fiction Writing Software for Manuscript Intelligence",
  description:
    "LoreVia helps fiction authors analyze manuscripts, track characters, catch continuity errors, build story bibles, and ask chapter-grounded questions during revision.",
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
    title: "LoreVia | Fiction Writing Software for Manuscript Intelligence",
    description:
      "LoreVia helps fiction authors analyze manuscripts, track characters, catch continuity errors, build story bibles, and ask chapter-grounded questions during revision.",
    url: SITE_URL,
    images: [DEFAULT_OG_IMAGE],
  },
  twitter: {
    card: "summary_large_image",
    title: "LoreVia | Fiction Writing Software for Manuscript Intelligence",
    description:
      "LoreVia helps fiction authors analyze manuscripts, track characters, catch continuity errors, build story bibles, and ask chapter-grounded questions during revision.",
    images: [DEFAULT_OG_IMAGE],
  },
}

const navItems = [
  { label: "Product", href: "#product" },
  { label: "For Authors", href: "#audiences" },
  { label: "Continuity", href: "#scan" },
  { label: "Pricing", href: "#pricing" },
  { label: "FAQ", href: "#faq" },
]

const fileFormats = ["DOCX", "PDF", "EPUB", "MD", "TXT", "Obsidian"]

const workspaceNav = [
  "Workspace",
  "Manuscript",
  "Characters",
  "Continuity",
  "Timeline",
  "Story Advisor",
  "Notes",
]

const scanSummary = [
  "147 story facts checked",
  "5 inconsistencies found",
  "23 details to double-check",
  "2 naming conflicts",
  "18 continuity gaps",
]

const workspaceModules = [
  {
    title: "Manuscript Editor",
    body: "Write chapters with notes, references, and issue markers beside the draft.",
  },
  {
    title: "Character Bible",
    body: "Automatically track characters, aliases, traits, relationships, and appearances.",
  },
  {
    title: "Continuity Scan",
    body: "Catch contradictions, duplicate names, dropped plot threads, and unresolved promises.",
  },
  {
    title: "Story Advisor",
    body: "Ask grounded questions with chapter-aware citations and collaborator-safe sharing limits.",
  },
]

const workspaceShowcaseTabs = ["Manuscript Editor", "Character Bible", "Continuity Scan", "Story Advisor"]

const manuscriptHighlights = [
  "Chapter 18 now mirrors the river crossing setup from Chapter 7.",
  "Mira's oath to return the amulet is still open in the current draft.",
  "Joren's alias appears in three scenes before the formal reveal.",
]

const characterSnapshot = [
  ["Aliases", "3 tracked"],
  ["Relationships", "12 linked"],
  ["Last appearance", "Chapter 18"],
]

const advisorCitations = [
  "Chapter 7: Mira reaches Vael with the northern caravan.",
  "Chapter 11: The alias 'Glassbird' is first used in council notes.",
]

const processSteps = [
  {
    number: "01",
    title: "Import your story",
    body: "Upload DOCX, PDF, EPUB, Markdown, text files, or an Obsidian vault.",
  },
  {
    number: "02",
    title: "Build story memory",
    body: "LoreVia extracts characters, places, relationships, scenes, timelines, and unresolved threads.",
  },
  {
    number: "03",
    title: "Ask, revise, detect",
    body: "Get grounded answers, continuity flags, and chapter references you can verify fast.",
  },
]

const comparisonRows = [
  ["Manuscript editor", "Yes", "Yes", "Yes", "Yes"],
  ["Character database", "Manual", "Manual", "No", "Automatic"],
  ["Relationship tracking", "Manual", "Yes", "No", "Automatic"],
  ["Timeline tools", "Manual", "Yes", "No", "Yes"],
  ["Worldbuilding workspace", "Limited", "Yes", "No", "Yes"],
  ["AI story understanding", "No", "No", "No", "Yes"],
  ["Automatic continuity scans", "No", "No", "No", "Yes"],
  ["Chapter-grounded answers", "No", "No", "No", "Yes"],
  ["Spoiler-aware story memory", "No", "No", "No", "Yes"],
  ["Multi-book analysis", "No", "Partial", "No", "Yes"],
  ["Detect dropped plot threads", "No", "No", "No", "Yes"],
  ["Character voice consistency checks", "No", "No", "No", "Yes"],
]

const faqItems = [
  {
    q: "Will LoreVia spoil future chapters?",
    a: "Collaborator access can stay bounded to a chapter, so shared answers avoid events past the point you choose.",
  },
  {
    q: "Can I use it before my book is published?",
    a: "Yes. The workspace is designed for private drafts, revisions, and unpublished manuscripts.",
  },
  {
    q: "Do you train AI models on my manuscript?",
    a: "Your manuscript is treated as private project content, not public training material.",
  },
  {
    q: "What file formats are supported?",
    a: "LoreVia is built around DOCX, PDF, EPUB, Markdown, plain text, and Obsidian-style notes.",
  },
  {
    q: "Can I export my character bible?",
    a: "Author workflows include generated reference material you can use outside the app.",
  },
  {
    q: "Does it work for long series?",
    a: "Yes. Higher tiers are shaped around larger manuscripts, multiple books, and recurring casts.",
  },
]

function Section({
  id,
  children,
  className = "",
}: {
  id?: string
  children: ReactNode
  className?: string
}) {
  return (
    <section id={id} className={`relative mx-auto max-w-7xl px-5 py-24 md:px-8 md:py-30 ${className}`}>
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
      <h2 className="font-display text-4xl font-semibold leading-[1.02] text-white md:text-6xl">{title}</h2>
      {body ? <p className="mt-5 text-base leading-8 text-slate-400 md:text-lg">{body}</p> : null}
    </div>
  )
}

function LogoMark({ compact = false }: { compact?: boolean }) {
  return (
    <BrandLockup
      size={compact ? "sm" : "md"}
      textClassName={compact ? "" : "text-[0.82rem] sm:text-[0.88rem] tracking-[0.3em]"}
      iconClassName={compact ? "" : "h-10 w-10 rounded-xl"}
    />
  )
}

function Icon({ name, className = "h-5 w-5" }: { name: string; className?: string }) {
  const common = {
    className,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.8,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    "aria-hidden": true,
  }

  if (name === "arrow") {
    return (
      <svg {...common}>
        <path d="M5 12h14" />
        <path d="m13 6 6 6-6 6" />
      </svg>
    )
  }

  if (name === "book") {
    return (
      <svg {...common}>
        <path d="M5 4.5h8a4 4 0 0 1 4 4v11H9a4 4 0 0 0-4 0z" />
        <path d="M17 8.5h2a2 2 0 0 1 2 2v9a4 4 0 0 0-4 0" />
      </svg>
    )
  }

  if (name === "scan") {
    return (
      <svg {...common}>
        <path d="M7 3H5a2 2 0 0 0-2 2v2" />
        <path d="M17 3h2a2 2 0 0 1 2 2v2" />
        <path d="M21 17v2a2 2 0 0 1-2 2h-2" />
        <path d="M7 21H5a2 2 0 0 1-2-2v-2" />
        <path d="M7 12h10" />
        <path d="M9 8h6" />
        <path d="M9 16h4" />
      </svg>
    )
  }

  if (name === "graph") {
    return (
      <svg {...common}>
        <circle cx="6" cy="7" r="2.5" />
        <circle cx="18" cy="8" r="2.5" />
        <circle cx="12" cy="18" r="2.5" />
        <path d="m8.2 8 7.6.5" />
        <path d="m7.3 9.1 3.4 6.7" />
        <path d="m16.7 10.2-3.4 5.6" />
      </svg>
    )
  }

  if (name === "shield") {
    return (
      <svg {...common}>
        <path d="M12 3 20 6v5c0 5-3.4 8.4-8 10-4.6-1.6-8-5-8-10V6z" />
        <path d="m9 12 2 2 4-5" />
      </svg>
    )
  }

  return (
    <svg {...common}>
      <path d="M12 5v14" />
      <path d="M5 12h14" />
    </svg>
  )
}

function HeroMockup() {
  return (
    <div className="relative">
      <div className="absolute -left-10 top-12 h-52 w-52 rounded-full bg-cyan-300/10 blur-3xl" />
      <div className="absolute -right-8 bottom-12 h-52 w-52 rounded-full bg-violet-300/10 blur-3xl" />
      <div className="relative overflow-hidden rounded-2xl border border-white/10 bg-[#0b1020] shadow-[0_30px_110px_-60px_rgba(125,211,252,0.42)]">
        <div className="grid min-h-[520px] lg:grid-cols-[220px_1fr]">
          <aside className="hidden border-r border-white/10 bg-[#080d18] p-5 lg:block">
            <LogoMark compact />
            <nav className="mt-8 space-y-2">
              {workspaceNav.map((item) => (
                <div
                  key={item}
                  className={`flex items-center gap-3 rounded-md px-3 py-3 text-sm ${
                    item === "Ask LoreVia" ? "bg-white/10 text-white" : "text-slate-400"
                  }`}
                >
                  <span className="h-1.5 w-1.5 rounded-full bg-current" />
                  {item}
                </div>
              ))}
            </nav>
            <div className="mt-12 border-t border-white/10 pt-5">
              <p className="text-xs uppercase tracking-[0.18em] text-slate-500">Project</p>
              <p className="mt-2 font-semibold text-white">Ashen Reign</p>
            </div>
          </aside>

          <div className="p-5 sm:p-7">
            <div className="flex items-start justify-between gap-5">
              <div>
                <h3 className="text-2xl font-semibold text-white">Ask LoreVia</h3>
                <p className="mt-1 text-sm text-slate-400">Grounded answers from your story.</p>
              </div>
              <span className="rounded-md border border-emerald-300/20 bg-emerald-300/10 px-3 py-1.5 text-xs font-semibold text-emerald-200">
                Spoiler-safe
              </span>
            </div>

            <div className="mt-7 rounded-xl border border-white/10 bg-[#111827]/80 p-4">
              <p className="text-xs text-slate-500">You</p>
              <p className="mt-2 text-sm leading-6 text-white">Has Mira ever been to Vael before Chapter 20?</p>
            </div>

            <div className="mt-4 rounded-xl border border-white/10 bg-[#111827]/80 p-4">
              <p className="text-xs font-semibold text-white">LoreVia</p>
              <p className="mt-2 text-sm leading-6 text-slate-200">
                Yes. In Chapter 7, Mira travels to Vael with the northern caravan and stays for three days.
              </p>
              <div className="mt-4 inline-flex rounded-md border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-slate-300">
                Chapter 7: The Northern Road
              </div>
            </div>

            <div className="mt-4 grid gap-4">
              <div className="rounded-xl border border-amber-300/20 bg-amber-300/8 p-4">
                <div className="flex items-start gap-3">
                  <Icon name="scan" className="mt-0.5 h-5 w-5 text-amber-200" />
                  <div>
                    <p className="font-semibold text-white">Character inconsistency detected</p>
                    <p className="mt-1 text-sm leading-6 text-slate-300">
                      In Chapter 4, Mira says she has never been to Vael. This contradicts Chapter 7.
                    </p>
                    <p className="mt-3 text-xs text-amber-100">References: Ch. 4, Ch. 7</p>
                  </div>
                </div>
              </div>

              <div className="rounded-xl border border-cyan-300/20 bg-cyan-300/8 p-4">
                <div className="flex items-start gap-3">
                  <Icon name="graph" className="mt-0.5 h-5 w-5 text-cyan-200" />
                  <div>
                    <p className="font-semibold text-white">Unresolved plot thread</p>
                    <p className="mt-1 text-sm leading-6 text-slate-300">
                      Joren promised to return the amulet to Mira. The promise has no closure yet.
                    </p>
                    <p className="mt-3 text-xs text-cyan-100">First mentioned in Ch. 9</p>
                  </div>
                </div>
              </div>
            </div>

            <div className="mt-4 flex items-center gap-3 rounded-xl border border-white/10 bg-[#070b14] p-3 text-sm text-slate-500">
              <span className="flex-1">Ask anything about your story...</span>
              <button
                type="button"
                className="inline-flex h-10 w-10 items-center justify-center rounded-lg bg-white text-slate-950 transition hover:bg-slate-200"
                aria-label="Send sample question"
              >
                <Icon name="arrow" className="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

function ScanProof({ ctaHref }: { ctaHref: Route }) {
  return (
    <Section id="scan" className="pt-10">
      <div className="grid gap-6 lg:grid-cols-[1.7fr_0.9fr]">
        <Reveal>
          <div className="h-full rounded-2xl border border-white/10 bg-[#080d18] p-6 md:p-8">
            <p className="text-sm font-semibold uppercase tracking-[0.22em] text-cyan-300">What LoreVia finds</p>
            <h2 className="mt-6 font-display text-4xl font-semibold leading-tight text-white md:text-5xl">
              Inconsistent fact: the eastern bridge
            </h2>
            <p className="mt-5 max-w-3xl text-lg leading-8 text-slate-300">
              In Chapter 3, Arin says the eastern bridge collapsed ten years ago. In Chapter 18, the same bridge is used during the escape.
            </p>

            <div className="mt-8 grid gap-4 md:grid-cols-2">
              <div className="rounded-xl border border-white/10 bg-white/[0.03] p-5">
                <p className="text-sm font-semibold text-white">Chapter 3, paragraph 12</p>
                <p className="mt-3 font-reading text-base italic leading-7 text-slate-300">
                  The eastern bridge fell before Arin was born, and no mason had touched it since.
                </p>
              </div>
              <div className="rounded-xl border border-white/10 bg-white/[0.03] p-5">
                <p className="text-sm font-semibold text-white">Chapter 18, paragraph 4</p>
                <p className="mt-3 font-reading text-base italic leading-7 text-slate-300">
                  Arin pulled the riders across the eastern bridge before the watch horns sounded.
                </p>
              </div>
            </div>

            <div className="mt-8 rounded-xl border border-amber-300/20 bg-amber-300/8 p-5">
              <p className="text-sm font-semibold uppercase tracking-[0.18em] text-amber-100">Possible fixes</p>
              <div className="mt-4 grid gap-3 text-sm leading-6 text-slate-200 md:grid-cols-3">
                <p>Change Chapter 18 to the western bridge.</p>
                <p>Explain that the bridge was rebuilt.</p>
                <p>Make the contradiction intentional and reveal it later.</p>
              </div>
            </div>
          </div>
        </Reveal>

        <Reveal delay={100}>
          <aside className="h-full rounded-2xl border border-white/10 bg-[#0b1020] p-6 md:p-8">
            <p className="text-sm font-semibold uppercase tracking-[0.2em] text-white">Scan summary</p>
            <div className="mt-7 space-y-5">
              {scanSummary.map((item) => (
                <div key={item} className="flex items-center gap-4 text-slate-200">
                  <span className="inline-flex h-7 w-7 items-center justify-center rounded-full bg-cyan-300/10 text-cyan-200">+</span>
                  <span>{item}</span>
                </div>
              ))}
            </div>
            <Link
              href={ctaHref}
              className="mt-9 inline-flex w-full items-center justify-center rounded-md border border-white/15 px-5 py-3.5 text-sm font-semibold text-white transition hover:border-white/30 hover:bg-white/8"
            >
              View full report
            </Link>
          </aside>
        </Reveal>
      </div>
    </Section>
  )
}

function WorkspacePreview() {
  const manuscriptRows = [
    ["The Ashen Crown", "In Progress", "24", "94%"],
    ["Forsaken Empire", "Draft", "18", "91%"],
    ["Winds of Verdania", "In Progress", "31", "93%"],
    ["Shadows of Elaris", "Draft", "14", "89%"],
    ["Dawn of the Fifth", "Outlining", "10", "84%"],
  ] as const

  return (
    <Section id="product">
      <div className="grid gap-12">
        <Reveal>
          <div className="max-w-3xl">
            <SectionHeader
              title="Everything your story needs, in one workspace."
              body="Upload a manuscript and LoreVia turns it into an author workspace for chapters, characters, continuity checks, notes, timelines, and grounded story questions."
            />
            <div className="mt-10 grid gap-px overflow-hidden rounded-2xl border border-white/10 bg-white/10 sm:grid-cols-2">
              {workspaceModules.map((item) => (
                <div key={item.title} className="h-full bg-[#080d18]/88 p-5 md:p-6">
                  <h3 className="text-lg font-semibold text-white">{item.title}</h3>
                  <p className="mt-2 text-sm leading-6 text-slate-400">{item.body}</p>
                </div>
              ))}
            </div>
          </div>
        </Reveal>

        <Reveal delay={100} className="min-w-0">
          <div className="min-w-0 overflow-hidden rounded-2xl border border-white/10 bg-[#080d18]">
            <div className="grid min-w-0 lg:grid-cols-[190px_minmax(0,1fr)_220px]">
              <aside className="hidden border-r border-white/10 p-4 lg:block">
                {["Manuscripts", "Scans", "Characters", "Locations", "World Bible", "Timelines", "Notes"].map((item, index) => (
                  <div
                    key={item}
                    className={`mb-2 rounded-md px-3 py-3 text-sm ${
                      index === 0 ? "bg-blue-500/20 text-white" : "text-slate-400"
                    }`}
                  >
                    {item}
                  </div>
                ))}
              </aside>

              <div className="min-w-0 p-5 md:p-6 lg:p-7">
                <div className="flex flex-col items-start justify-between gap-4 sm:flex-row sm:items-center">
                  <h3 className="text-2xl font-semibold text-white">Manuscripts</h3>
                  <button
                    type="button"
                    className="w-full rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white sm:w-auto"
                  >
                    + New Manuscript
                  </button>
                </div>
                <div className="mt-6">
                  <div className="-mx-2 overflow-x-auto px-2 pb-2 [scrollbar-width:thin] [scrollbar-color:rgba(148,163,184,0.45)_transparent]">
                    <table className="w-full min-w-[34rem] border-separate border-spacing-y-3 text-left text-sm sm:min-w-[38rem]">
                      <colgroup>
                        <col className="w-[44%]" />
                        <col className="w-[22%]" />
                        <col className="w-[16%]" />
                        <col className="w-[18%]" />
                      </colgroup>
                      <thead className="text-slate-500">
                        <tr>
                          <th className="pb-3 pr-8 font-medium">Title</th>
                          <th className="pb-3 pr-8 font-medium">Status</th>
                          <th className="pb-3 pr-8 font-medium">Chapters</th>
                          <th className="pb-3 pr-2 font-medium">Score</th>
                        </tr>
                      </thead>
                      <tbody className="text-slate-200">
                        {manuscriptRows.map((row) => (
                          <tr key={row[0]}>
                            <td className="border-y border-white/10 py-4 pr-8 font-medium leading-8 text-white">{row[0]}</td>
                            <td className="border-y border-white/10 py-4 pr-8">
                              <span className="inline-flex rounded bg-white/8 px-2 py-1 text-xs">{row[1]}</span>
                            </td>
                            <td className="border-y border-white/10 py-4 pr-8 text-base">{row[2]}</td>
                            <td className="border-y border-white/10 py-4 pr-2 text-base font-semibold text-emerald-300">{row[3]}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>

              <aside className="border-t border-white/10 p-5 lg:border-l lg:border-t-0">
                <p className="text-sm font-semibold uppercase tracking-[0.18em] text-white">Overall summary</p>
                <div className="mx-auto mt-7 flex h-36 w-36 items-center justify-center rounded-full border-[10px] border-blue-500/80">
                  <div className="text-center">
                    <p className="text-3xl font-semibold text-white">94%</p>
                    <p className="text-xs text-slate-400">Excellent</p>
                  </div>
                </div>
                <div className="mt-7 grid grid-cols-2 gap-4 text-sm sm:grid-cols-4 lg:grid-cols-2">
                  <div>
                    <p className="text-slate-500">Total Scans</p>
                    <p className="mt-1 font-semibold text-white">27</p>
                  </div>
                  <div>
                    <p className="text-slate-500">Issues</p>
                    <p className="mt-1 font-semibold text-white">68</p>
                  </div>
                  <div>
                    <p className="text-slate-500">Open</p>
                    <p className="mt-1 font-semibold text-white">7</p>
                  </div>
                  <div>
                    <p className="text-slate-500">Resolved</p>
                    <p className="mt-1 font-semibold text-white">61</p>
                  </div>
                </div>
              </aside>
            </div>
          </div>
        </Reveal>
      </div>
    </Section>
  )
}

function ProcessSection() {
  return (
    <Section>
      <SectionHeader
        title="Three steps to a stronger story memory."
        body="The process is simple, but the output is built for real author revision: import, extract, then ask or scan with evidence."
        align="center"
      />
      <div className="relative mt-14 grid gap-6 lg:grid-cols-3">
        <div className="absolute left-[12%] right-[12%] top-9 hidden h-px bg-gradient-to-r from-cyan-300/0 via-cyan-300/40 to-cyan-300/0 lg:block" />
        {processSteps.map((step, index) => (
          <Reveal key={step.number} delay={index * 80}>
            <article className="relative h-full rounded-2xl border border-white/10 bg-[#080d18] p-7">
              <div className="inline-flex h-16 w-16 items-center justify-center rounded-full border border-cyan-300/30 bg-cyan-300/10 text-lg font-semibold text-cyan-100">
                {step.number}
              </div>
              <h3 className="mt-8 text-2xl font-semibold text-white">{step.title}</h3>
              <p className="mt-4 text-base leading-8 text-slate-400">{step.body}</p>
            </article>
          </Reveal>
        ))}
      </div>
    </Section>
  )
}

function ComparisonSection() {
  return (
    <Section id="comparison">
      <SectionHeader
        title="Where traditional writing tools stop."
        body="Traditional writing tools help organize stories. LoreVia gives authors searchable story memory and continuity intelligence."
      />
      <Reveal>
        <div className="mt-10 overflow-hidden rounded-2xl border border-white/10 bg-[#080d18]">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[820px] border-separate border-spacing-0 text-left text-sm">
              <thead>
                <tr className="text-slate-400">
                  {["Feature", "Scrivener", "Campfire", "Google Docs", "LoreVia"].map((head) => (
                    <th
                      key={head}
                      className={`border-b border-white/10 px-5 py-5 font-semibold ${
                        head === "LoreVia" ? "bg-cyan-300/10 text-cyan-100" : ""
                      }`}
                    >
                      {head}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {comparisonRows.map((row) => (
                  <tr key={row[0]} className="text-slate-300">
                    {row.map((cell, index) => (
                      <td
                        key={`${row[0]}-${index}`}
                        className={`border-b border-white/10 px-5 py-4 ${
                          index === 0 ? "font-medium text-white" : ""
                        } ${index === 4 ? "bg-cyan-300/[0.06] font-semibold text-cyan-100" : ""}`}
                      >
                        {cell === "" || cell === "No" ? (
                          <span className="text-slate-600">&times;</span>
                        ) : cell}
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
      <SectionHeader title="Questions authors ask before trusting a manuscript workspace." align="center" />
      <div className="mt-12 grid gap-px overflow-hidden rounded-2xl border border-white/10 bg-white/10 md:grid-cols-2">
        {faqItems.map((item) => (
          <Reveal key={item.q}>
            <article className="h-full bg-[#080d18] p-6 md:p-8">
              <h3 className="text-lg font-semibold text-white">{item.q}</h3>
              <p className="mt-4 text-sm leading-7 text-slate-400">{item.a}</p>
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
      "LoreVia helps fiction authors analyze manuscripts, track characters, manage continuity, and build a searchable story workspace.",
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
      "Character tracking",
      "Continuity scans",
      "Timeline review",
      "Story bible generation",
      "Chapter-grounded story questions",
      "Beta-reader collaboration",
    ],
  }

  return (
    <main className="min-h-screen overflow-hidden bg-[#050814] text-white">
      <Script id="home-faq-jsonld" type="application/ld+json" strategy="beforeInteractive">
        {JSON.stringify(faqJsonLd).replace(/</g, "\\u003c")}
      </Script>
      <Script id="home-software-jsonld" type="application/ld+json" strategy="beforeInteractive">
        {JSON.stringify(softwareJsonLd).replace(/</g, "\\u003c")}
      </Script>
      <div className="pointer-events-none fixed inset-0 -z-10 bg-[radial-gradient(circle_at_20%_0%,rgba(125,211,252,0.09),transparent_28%),radial-gradient(circle_at_80%_12%,rgba(196,181,253,0.08),transparent_24%),linear-gradient(180deg,#050814_0%,#070b14_42%,#0b1020_100%)]" />

      <header className="sticky top-0 z-50 border-b border-white/10 bg-[#050814]/88 backdrop-blur-xl">
        <div className="mx-auto flex h-[76px] max-w-7xl items-center justify-between px-5 md:px-8">
          <Link href="/" aria-label="LoreVia home">
            <LogoMark />
          </Link>
          <nav className="hidden items-center gap-8 lg:flex">
            {navItems.map((item) => (
              <a
                key={item.label}
                href={item.href}
                className="text-[14px] font-medium tracking-[0.01em] text-white/70 transition hover:text-white"
              >
                {item.label}
              </a>
            ))}
          </nav>
          <div className="flex items-center gap-3">
            <Link
              href="/blog"
              className="hidden px-4 py-2 text-[14px] font-medium tracking-[0.01em] text-white/70 transition hover:text-white sm:inline-flex"
            >
              Blog
            </Link>
            <Link
              href="/login"
              className="hidden px-4 py-2 text-[14px] font-medium tracking-[0.01em] text-white/70 transition hover:text-white sm:inline-flex"
            >
              Sign in
            </Link>
            <Link
              href={ctaHref}
              className="rounded-[10px] bg-[#f4f4f5] px-4 py-2.5 text-[14px] font-semibold text-[#09090b] transition hover:bg-[#e7e9f8] focus-visible:outline-indigo-300"
            >
              Start free
            </Link>
          </div>
        </div>
      </header>

      <section className="relative mx-auto grid max-w-7xl gap-10 px-5 pb-14 pt-10 md:gap-12 md:px-8 md:pb-16 md:pt-12 lg:grid-cols-[0.82fr_1.18fr] lg:items-start lg:pt-16">
        <Reveal>
          <div>
            <p className="inline-flex rounded-full border border-white/10 px-4 py-2 text-xs font-semibold uppercase tracking-[0.2em] text-slate-300">
              Fiction authors only
            </p>
            <h1
              className="mt-7 text-5xl font-[600] leading-[0.98] tracking-[-0.04em] text-white md:text-7xl xl:text-[4.15rem]"
              style={{ fontFamily: '"Inter", "Geist", "Satoshi", var(--font-ui), sans-serif' }}
            >
              LoreVia for authors who need story memory, sharper revisions, and continuity control.
            </h1>
            <p className="mt-6 max-w-2xl text-lg leading-9 text-slate-300 md:text-xl">
              LoreVia turns your manuscript into an author workspace with character tracking, manuscript intelligence, relationship memory, grounded story questions, and continuity scans that stay tied to the draft.
            </p>
            <div className="mt-8 flex flex-col gap-4 xl:flex-row">
              <Link
                href={ctaHref}
                className="inline-flex items-center justify-center gap-3 rounded-[10px] bg-[#f4f4f5] px-7 py-4 text-base font-semibold text-[#09090b] transition hover:bg-[#e7e9f8] focus-visible:outline-indigo-300"
              >
                Analyze your manuscript
                <Icon name="arrow" className="h-5 w-5" />
              </Link>
              <a
                href="#scan"
                className="inline-flex items-center justify-center rounded-[10px] border border-white/15 px-7 py-4 text-base font-semibold text-white transition hover:border-white/30 hover:bg-[#161c2e]"
              >
                See example scan
              </a>
            </div>

            <div className="mt-10">
              <p className="text-sm text-slate-500">Works with your files</p>
              <div className="mt-4 flex flex-wrap gap-3">
                {fileFormats.map((format) => (
                  <span key={format} className="rounded-md border border-white/10 bg-white/[0.03] px-4 py-3 text-sm font-semibold text-slate-300">
                    {format}
                  </span>
                ))}
              </div>
            </div>
          </div>
        </Reveal>

        <Reveal delay={100}>
          <HeroMockup />
        </Reveal>
      </section>

      <ScanProof ctaHref={ctaHref} />
      <WorkspacePreview />
      <ProcessSection />
      <AudienceSection />
      <ComparisonSection />
      <HomePricingSection ctaHref={ctaHref} />
      <FAQSection />

      <section className="border-t border-white/10 bg-[#030711]">
        <div className="mx-auto grid max-w-7xl gap-8 px-5 py-20 md:px-8 lg:grid-cols-[1fr_auto] lg:items-center">
          <div>
            <h2 className="font-display text-4xl font-semibold leading-tight text-white md:text-6xl">
              Start with one chapter. See what LoreVia remembers.
            </h2>
            <p className="mt-5 max-w-2xl text-lg leading-8 text-slate-400">
              Upload a manuscript and get your first author-facing continuity scan, character map, and grounded story memory.
            </p>
          </div>
          <div className="flex flex-col gap-4 sm:flex-row lg:justify-end">
            <Link href={ctaHref} className="inline-flex items-center justify-center rounded-lg bg-white px-7 py-4 text-base font-semibold text-slate-950 transition hover:bg-slate-200">
              Start free
            </Link>
            <a href="#pricing" className="inline-flex items-center justify-center rounded-lg border border-white/15 px-7 py-4 text-base font-semibold text-white transition hover:border-white/30 hover:bg-white/8">
              View pricing
            </a>
          </div>
        </div>
      </section>
    </main>
  )
}
