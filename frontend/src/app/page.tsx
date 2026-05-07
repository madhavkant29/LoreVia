"use client"

import Link from "next/link"
import type { Route } from "next"
import { useEffect, useRef, useState, type ReactNode } from "react"
import { useAuthStore } from "@/lib/stores/authStore"

const navItems = [
  { label: "Product", href: "#product" },
  { label: "Authors", href: "#audiences" },
  { label: "Readers", href: "#audiences" },
  { label: "Pricing", href: "#pricing" },
  { label: "About", href: "#faq" },
]

const fileFormats = ["DOCX", "PDF", "EPUB", "MD", "TXT", "Obsidian"]

const workspaceNav = [
  "Ask LoreVia",
  "Manuscript",
  "Characters",
  "Places",
  "Plot Threads",
  "Timeline",
  "Continuity Scan",
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
    title: "Manuscript",
    body: "Chapter text stays beside references, notes, and issue markers.",
  },
  {
    title: "Character Bible",
    body: "Profiles update from the draft instead of depending on manual cards.",
  },
  {
    title: "Story Advisor",
    body: "Ask grounded questions with chapter-aware limits and citations.",
  },
  {
    title: "Continuity Scan",
    body: "Contradictions, dropped promises, and duplicate names surface together.",
  },
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
    body: "Get spoiler-safe answers, continuity flags, and chapter references you can verify fast.",
  },
]

const audienceTabs = {
  Authors: [
    "Character bible built from the manuscript",
    "Continuity scan for late-draft revisions",
    "Plot thread tracker with first and latest mention",
    "Voice and detail inconsistency detection",
    "Worldbuilding gaps before beta readers find them",
  ],
  Screenwriters: [
    "Scene continuity across drafts",
    "Motivation tracking by character and beat",
    "Dialogue voice checks",
    "Location and prop consistency",
    "Beat references for rewrites",
  ],
  Readers: [
    "Spoiler-safe recap up to your chapter",
    "Ask what happened without future reveals",
    "Character reminders after long breaks",
    "Relationship maps for dense casts",
    "Reader-safe public-domain story scans",
  ],
}

const comparisonRows = [
  ["Automatic character extraction", "-", "Limited", "-", "Yes"],
  ["Spoiler-aware answers", "-", "-", "-", "Yes"],
  ["Continuity contradiction detection", "-", "-", "-", "Yes"],
  ["Chapter-grounded references", "-", "Limited", "Mixed", "Yes"],
  ["Author revision workspace", "Yes", "-", "-", "Yes"],
  ["Works before publishing", "Yes", "-", "-", "Yes"],
  ["Reader-safe recap", "-", "Limited", "-", "Yes"],
]

const pricingTiers = [
  {
    name: "Free",
    price: 0,
    subtitle: "For testing one book and trying story recall.",
    bullets: [
      "2 active books",
      "Smart Tap, character profiles, and recall",
      "Short summaries only",
      "5 semantic searches/day and 3 prediction queries/day",
    ],
    cta: "Start free",
    highlighted: false,
  },
  {
    name: "Reader",
    price: 12,
    subtitle: "For dedicated readers returning to long books.",
    bullets: [
      "Everything in Free, plus",
      "Unlimited books",
      "Multi-mode story summaries",
      "Reader-only access with no authoring tools",
      "10 prediction queries/day",
    ],
    cta: "Go Reader",
    highlighted: false,
  },
  {
    name: "Author",
    price: 24,
    subtitle: "For drafting, revising, and managing an active manuscript.",
    bullets: [
      "Everything in Reader, plus",
      "Catch continuity errors automatically",
      "Chapter and manuscript feedback",
      "Auto-generated character reference sheets",
      "Visual relationship maps",
      "Marketed as unlimited with a 30/day fair-use cap",
    ],
    cta: "Start drafting",
    highlighted: true,
  },
  {
    name: "Lore Architect",
    price: 36,
    subtitle: "For heavy usage, large manuscripts, and series work.",
    bullets: [
      "Everything in Author, plus",
      "Priority processing planned for launch rollout",
      "Deeper continuity analysis",
      "Analyze multiple books together",
      "Early access to new features",
      "Marketed as unlimited with a 60/day fair-use cap",
    ],
    cta: "Build your world",
    highlighted: false,
  },
]

const faqItems = [
  {
    q: "Will LoreVia spoil future chapters?",
    a: "Reader mode can stay bounded to a chapter, so answers avoid events past the point you choose.",
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

function useInView(threshold = 0.14) {
  const ref = useRef<HTMLDivElement>(null)
  const [inView, setInView] = useState(false)

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) setInView(true)
      },
      { threshold }
    )

    if (ref.current) observer.observe(ref.current)

    return () => observer.disconnect()
  }, [threshold])

  return { ref, inView }
}

function Reveal({
  children,
  delay = 0,
  className = "",
}: {
  children: ReactNode
  delay?: number
  className?: string
}) {
  const { ref, inView } = useInView()

  return (
    <div
      ref={ref}
      style={{ transitionDelay: `${delay}ms` }}
      className={`transform-gpu transition-all duration-700 ease-out ${
        inView ? "translate-y-0 opacity-100" : "translate-y-6 opacity-0"
      } ${className}`}
    >
      {children}
    </div>
  )
}

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
    <div className="flex items-center gap-3">
      <img src="/image.png" alt="LoreVia" className={compact ? "h-9 w-9 rounded-xl object-cover" : "h-12 w-12 rounded-2xl object-cover"} />
      <span className={compact ? "text-lg font-semibold text-white" : "text-2xl font-semibold text-white"}>LoreVia</span>
    </div>
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
  return (
    <Section id="product">
      <div className="grid gap-10 lg:grid-cols-[0.8fr_1.2fr] lg:items-center">
        <Reveal>
          <div>
            <SectionHeader
              title="One workspace for the entire story."
              body="Instead of another row of feature cards, LoreVia gives the manuscript a working surface: text, characters, threads, scans, and grounded answers in one place."
            />
            <div className="mt-8 grid gap-4 sm:grid-cols-2">
              {workspaceModules.map((item) => (
                <div key={item.title} className="border-l border-white/15 pl-5">
                  <h3 className="text-lg font-semibold text-white">{item.title}</h3>
                  <p className="mt-2 text-sm leading-6 text-slate-400">{item.body}</p>
                </div>
              ))}
            </div>
          </div>
        </Reveal>

        <Reveal delay={100}>
          <div className="overflow-hidden rounded-2xl border border-white/10 bg-[#080d18]">
            <div className="grid lg:grid-cols-[190px_1fr_210px]">
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

              <div className="p-5 md:p-6">
                <div className="flex flex-wrap items-center justify-between gap-4">
                  <h3 className="text-2xl font-semibold text-white">Manuscripts</h3>
                  <button type="button" className="rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white">
                    + New Manuscript
                  </button>
                </div>
                <div className="mt-6 overflow-x-auto">
                  <table className="w-full min-w-[560px] text-left text-sm">
                    <thead className="text-slate-500">
                      <tr>
                        <th className="pb-3 font-medium">Title</th>
                        <th className="pb-3 font-medium">Status</th>
                        <th className="pb-3 font-medium">Chapters</th>
                        <th className="pb-3 font-medium">Last Scan</th>
                        <th className="pb-3 font-medium">Score</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-white/10 text-slate-200">
                      {[
                        ["The Ashen Crown", "In Progress", "24", "Apr 21", "94%"],
                        ["Forsaken Empire", "Draft", "18", "Apr 18", "91%"],
                        ["Winds of Verdania", "In Progress", "31", "Apr 17", "93%"],
                        ["Shadows of Elaris", "Draft", "14", "Apr 10", "89%"],
                        ["Dawn of the Fifth", "Outlining", "10", "Apr 5", "84%"],
                      ].map((row) => (
                        <tr key={row[0]}>
                          <td className="py-3 font-medium text-white">{row[0]}</td>
                          <td className="py-3">
                            <span className="rounded bg-white/8 px-2 py-1 text-xs">{row[1]}</span>
                          </td>
                          <td className="py-3">{row[2]}</td>
                          <td className="py-3">{row[3]}</td>
                          <td className="py-3 font-semibold text-emerald-300">{row[4]}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
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
                <div className="mt-7 grid grid-cols-2 gap-4 text-sm">
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
        body="The process is simple, but the output is useful enough for real revision: import, extract, then ask or scan with evidence."
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

function AudienceSection() {
  const [activeAudience, setActiveAudience] = useState<keyof typeof audienceTabs>("Authors")
  const items = audienceTabs[activeAudience]

  return (
    <Section id="audiences">
      <div className="grid gap-10 lg:grid-cols-[0.8fr_1.2fr] lg:items-start">
        <Reveal>
          <div>
            <SectionHeader
              title="Built for the way different story people work."
              body="Authors, screenwriters, and serious readers need different memory boundaries. The same story engine can serve each without making the interface feel generic."
            />
            <div className="mt-8 inline-flex rounded-md border border-white/10 bg-white/[0.04] p-1">
              {(Object.keys(audienceTabs) as Array<keyof typeof audienceTabs>).map((tab) => (
                <button
                  key={tab}
                  type="button"
                  onClick={() => setActiveAudience(tab)}
                  className={`rounded px-4 py-2 text-sm font-semibold transition ${
                    activeAudience === tab ? "bg-white text-slate-950" : "text-slate-400 hover:text-white"
                  }`}
                >
                  {tab}
                </button>
              ))}
            </div>
          </div>
        </Reveal>

        <Reveal delay={100}>
          <div className="relative overflow-hidden rounded-2xl border border-white/10 bg-[#080d18] p-6 md:p-8">
            <div className="absolute inset-y-0 right-0 w-1/2 bg-[radial-gradient(circle_at_center,rgba(125,211,252,0.12),transparent_55%)]" />
            <div className="relative grid gap-8 md:grid-cols-[1fr_0.85fr]">
              <div>
                <p className="text-sm font-semibold uppercase tracking-[0.2em] text-cyan-300">{activeAudience}</p>
                <h3 className="mt-4 text-3xl font-semibold text-white">Concrete tools, not vague writing magic.</h3>
                <div className="mt-7 space-y-4">
                  {items.map((item) => (
                    <div key={item} className="flex gap-4 rounded-xl border border-white/10 bg-white/[0.03] p-4">
                      <span className="mt-1 h-2 w-2 rounded-full bg-cyan-300" />
                      <p className="text-sm leading-6 text-slate-200">{item}</p>
                    </div>
                  ))}
                </div>
              </div>

              <div className="relative min-h-[320px]">
                <svg viewBox="0 0 320 320" className="h-full w-full text-cyan-200/70" aria-hidden>
                  <path d="M82 90 C140 34 223 52 250 112" stroke="currentColor" strokeWidth="1.4" fill="none" opacity="0.5" />
                  <path d="M77 96 C100 185 170 235 242 222" stroke="currentColor" strokeWidth="1.4" fill="none" opacity="0.35" />
                  <path d="M251 119 C213 152 201 188 241 219" stroke="currentColor" strokeWidth="1.4" fill="none" opacity="0.5" />
                  {[
                    [78, 94, "Mira"],
                    [252, 116, "Vael"],
                    [242, 224, "Joren"],
                    [118, 212, "Amulet"],
                    [178, 68, "Bridge"],
                  ].map(([cx, cy, label]) => (
                    <g key={label as string}>
                      <circle cx={cx as number} cy={cy as number} r="26" fill="#0f172a" stroke="rgba(125,211,252,0.45)" />
                      <text x={cx as number} y={(cy as number) + 4} textAnchor="middle" fill="#f8fafc" fontSize="12">
                        {label}
                      </text>
                    </g>
                  ))}
                </svg>
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
    <Section id="comparison">
      <SectionHeader
        title="Why authors choose LoreVia."
        body="A compact look at where LoreVia is different: it reads the story, keeps chapter evidence, and works before a book is public."
      />
      <Reveal>
        <div className="mt-10 overflow-hidden rounded-2xl border border-white/10 bg-[#080d18]">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[820px] border-separate border-spacing-0 text-left text-sm">
              <thead>
                <tr className="text-slate-400">
                  {["Feature", "Campfire", "Kindle X-Ray", "Wiki", "LoreVia"].map((head) => (
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

function PricingSection({ ctaHref }: { ctaHref: Route }) {
  return (
    <Section id="pricing">
      <SectionHeader
        title="Simple pricing for different story loads."
        body="Start free, then choose the plan that matches how many books, chapters, and scans you need. The Author plan is the best fit for most manuscript work."
        align="center"
      />
      <div className="mt-12 grid gap-5 md:grid-cols-2 lg:grid-cols-4">
        {pricingTiers.map((tier, index) => (
          <Reveal key={tier.name} delay={index * 70} className="h-full">
            <article
              className={`relative flex h-full flex-col rounded-2xl p-6 transition hover:-translate-y-1 ${
                tier.highlighted
                  ? "border border-cyan-300/50 bg-[#121b30] shadow-[0_24px_70px_-45px_rgba(125,211,252,0.8)]"
                  : "border border-white/10 bg-[#080d18]"
              }`}
            >
              {tier.highlighted ? (
                <div className="absolute -top-3 left-6 rounded-md bg-cyan-300 px-3 py-1 text-xs font-semibold uppercase tracking-[0.14em] text-slate-950">
                  Best value
                </div>
              ) : null}
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h3 className="text-xl font-semibold text-white">{tier.name}</h3>
                  <p className="mt-2 text-sm leading-6 text-slate-400">{tier.subtitle}</p>
                </div>
              </div>
              <div className="mt-8 flex items-baseline gap-1">
                <span className="text-5xl font-semibold tracking-tight text-white">${tier.price}</span>
                {tier.price > 0 ? <span className="text-sm text-slate-500">/mo</span> : null}
              </div>
              <ul className="mt-8 space-y-4">
                {tier.bullets.map((bullet) => (
                  <li key={bullet} className="flex gap-3 text-sm leading-6 text-slate-300">
                    <span className={tier.highlighted ? "text-cyan-200" : "text-slate-500"}>+</span>
                    <span>{bullet}</span>
                  </li>
                ))}
              </ul>
              <Link
                href={ctaHref}
                className={`mt-auto inline-flex w-full items-center justify-center rounded-md px-4 py-3.5 text-sm font-semibold transition ${
                  tier.highlighted
                    ? "bg-white text-slate-950 hover:bg-slate-200"
                    : "border border-white/10 text-white hover:border-white/25 hover:bg-white/8"
                }`}
              >
                {tier.cta}
              </Link>
            </article>
          </Reveal>
        ))}
      </div>
    </Section>
  )
}

function FAQSection() {
  return (
    <Section id="faq">
      <SectionHeader title="Questions authors ask before uploading." align="center" />
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
  const { user, hydrated } = useAuthStore()
  const ctaHref: Route = hydrated && user ? "/library" : "/login"

  return (
    <main className="min-h-screen overflow-hidden bg-[#050814] text-white">
      <div className="pointer-events-none fixed inset-0 -z-10 bg-[radial-gradient(circle_at_20%_0%,rgba(125,211,252,0.09),transparent_28%),radial-gradient(circle_at_80%_12%,rgba(196,181,253,0.08),transparent_24%),linear-gradient(180deg,#050814_0%,#070b14_42%,#0b1020_100%)]" />

      <header className="sticky top-0 z-50 border-b border-white/10 bg-[#050814]/88 backdrop-blur-xl">
        <div className="mx-auto flex h-20 max-w-7xl items-center justify-between px-5 md:px-8">
          <Link href="/" aria-label="LoreVia home">
            <LogoMark />
          </Link>
          <nav className="hidden items-center gap-9 lg:flex">
            {navItems.map((item) => (
              <a key={item.label} href={item.href} className="text-sm font-medium text-slate-300 transition hover:text-white">
                {item.label}
              </a>
            ))}
          </nav>
          <div className="flex items-center gap-3">
            <Link href="/login" className="hidden rounded-md px-4 py-2 text-sm font-semibold text-slate-300 transition hover:text-white sm:inline-flex">
              Sign in
            </Link>
            <Link href={ctaHref} className="rounded-md bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-blue-500">
              Start free
            </Link>
          </div>
        </div>
      </header>

      <section className="relative mx-auto grid min-h-[88vh] max-w-7xl gap-12 px-5 pb-16 pt-14 md:px-8 lg:grid-cols-[0.82fr_1.18fr] lg:items-center">
        <Reveal>
          <div>
            <p className="inline-flex rounded-full border border-white/10 px-4 py-2 text-xs font-semibold uppercase tracking-[0.2em] text-slate-300">
              For fiction authors and serious readers
            </p>
            <h1 className="mt-8 font-display text-6xl font-semibold leading-[0.96] tracking-normal text-white md:text-7xl xl:text-[5.4rem]">
              Never lose track of your story again.
            </h1>
            <p className="mt-7 max-w-2xl text-lg leading-9 text-slate-300 md:text-xl">
              LoreVia remembers every character, relationship, plot thread, contradiction, and chapter detail, so you can write, revise, or reread without digging through hundreds of pages.
            </p>
            <div className="mt-9 flex flex-col gap-4 xl:flex-row">
              <Link
                href={ctaHref}
                className="inline-flex items-center justify-center gap-3 rounded-lg bg-white px-7 py-4 text-base font-semibold text-slate-950 transition hover:bg-slate-200"
              >
                Start analyzing your story
                <Icon name="arrow" className="h-5 w-5" />
              </Link>
              <a
                href="#scan"
                className="inline-flex items-center justify-center rounded-lg border border-white/15 px-7 py-4 text-base font-semibold text-white transition hover:border-white/30 hover:bg-white/8"
              >
                See example scan
              </a>
            </div>

            <div className="mt-10 grid gap-4 border-t border-white/10 pt-7 sm:grid-cols-4">
              {[
                ["Spoiler-aware", "shield"],
                ["Chapter-grounded", "book"],
                ["Private by design", "shield"],
                ["Author-first", "scan"],
              ].map(([label, icon]) => (
                <div key={label} className="flex items-center gap-2 text-sm text-slate-400">
                  <Icon name={icon} className="h-4 w-4 text-slate-500" />
                  <span>{label}</span>
                </div>
              ))}
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
      <PricingSection ctaHref={ctaHref} />
      <FAQSection />

      <section className="border-t border-white/10 bg-[#030711]">
        <div className="mx-auto grid max-w-7xl gap-8 px-5 py-20 md:px-8 lg:grid-cols-[1fr_auto] lg:items-center">
          <div>
            <h2 className="font-display text-4xl font-semibold leading-tight text-white md:text-6xl">
              Start with one chapter. See what LoreVia remembers.
            </h2>
            <p className="mt-5 max-w-2xl text-lg leading-8 text-slate-400">
              Upload a manuscript and get your first continuity scan, character map, and grounded story memory.
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
