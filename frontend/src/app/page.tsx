"use client"

import Link from "next/link"
import { useEffect, useRef, useState, type ReactNode } from "react"
import { useAuthStore } from "@/lib/stores/authStore"

const trustStats = [
  { value: "EPUB + PDF", label: "supported formats" },
  { value: "Any length", label: "built for long manuscripts" },
  { value: "Zero edits", label: "your text is never changed" },
]

const painPoints = [
  "You forget when a character last appeared",
  "You contradict something from 100 chapters ago",
  "You waste hours searching your own text",
  "Readers catch inconsistencies before you do",
]

const workflowSteps = [
  {
    num: "01",
    title: "Upload the manuscript",
    body: "Drop in an EPUB or PDF. LoreVia reads the story structure without asking you to format it first.",
  },
  {
    num: "02",
    title: "Build the story map",
    body: "Characters, relationships, chapters, and threads are organized into a usable reference layer.",
  },
  {
    num: "03",
    title: "Ask and verify",
    body: "Every answer comes back with chapter-linked context, so you can trust the result and trace it fast.",
  },
]

const featureCards = [
  {
    title: "Instant recall",
    body: "Find where a person appeared, what changed, and which chapter contains the source.",
  },
  {
    title: "Character bible",
    body: "Profiles, roles, relationships, and arc notes generated from the text itself.",
  },
  {
    title: "Series-safe structure",
    body: "Keep books isolated so a large series stays organized instead of blending together.",
  },
  {
    title: "Continuity checks",
    body: "Surface contradictions, missing returns, and loose threads before readers do.",
  },
]

const audienceCards = [
  {
    title: "Screenwriters",
    body: "Track scenes, dialogue beats, and character continuity across script drafts.",
  },
  {
    title: "Authors",
    body: "Keep character arcs, timelines, and references consistent across long manuscripts.",
  },
  {
    title: "Webnovel writers",
    body: "Upload chapter by chapter and keep the story memory intact as the series grows.",
  },
  {
    title: "Book series",
    body: "Separate each book while still comparing recurring characters and story threads.",
  },
]

const proofItems = [
  {
    tone: "warning",
    title: "Conflicting eye color for Aria",
    body: '"blue" in Chapter 12, "green" in Chapter 64. No state change recorded.',
  },
  {
    tone: "warning",
    title: "A character disappeared for 87 chapters",
    body: "Last seen in Chapter 14. The gap is now visible instead of hidden.",
  },
  {
    tone: "info",
    title: "An unresolved thread stays open",
    body: "The sealed letter is mentioned repeatedly, but never closed out.",
  },
]

const comparisonCompetitors = [
  {
    name: "Fandom Wiki",
    description: "Community-maintained wikis for popular series",
    features: {
      "Works on any book": false,
      "Zero spoiler risk": false,
      "No manual data entry": true,
      "Tracks your reading position": false,
      "Automatic character extraction": false,
      "Finds plotholes": false,
      "Author writing tools": false,
      "Memory recall on return": false,
      "Relationship graph": true,
      "Works on unpublished novels": false,
    },
    bestFor: "Readers of big-name series who want a quick refresher.",
    verdictType: "bad" as const,
  },
  {
    name: "Kindle X-Ray",
    description: "Amazon's built-in character lookup feature",
    features: {
      "Works on any book": false,
      "Zero spoiler risk": false,
      "No manual data entry": true,
      "Tracks your reading position": true,
      "Automatic character extraction": false,
      "Finds plotholes": false,
      "Author writing tools": false,
      "Memory recall on return": false,
      "Relationship graph": false,
      "Works on unpublished novels": false,
    },
    bestFor: "Kindle-only reading when you need a lightweight lookup.",
    verdictType: "bad" as const,
  },
  {
    name: "Campfire Write",
    description: "Modular writing tool for authors",
    features: {
      "Works on any book": true,
      "Zero spoiler risk": true,
      "No manual data entry": false,
      "Tracks your reading position": false,
      "Automatic character extraction": false,
      "Finds plotholes": false,
      "Author writing tools": true,
      "Memory recall on return": false,
      "Relationship graph": true,
      "Works on unpublished novels": true,
    },
    bestFor: "Worldbuilding and planning with manual templates.",
    verdictType: "neutral" as const,
  },
  {
    name: "Scrivener",
    description: "Professional manuscript editor for authors",
    features: {
      "Works on any book": true,
      "Zero spoiler risk": true,
      "No manual data entry": false,
      "Tracks your reading position": false,
      "Automatic character extraction": false,
      "Finds plotholes": false,
      "Author writing tools": true,
      "Memory recall on return": false,
      "Relationship graph": false,
      "Works on unpublished novels": true,
    },
    bestFor: "Drafting and revision workflows for serious writers.",
    verdictType: "neutral" as const,
  },
  {
    name: "LoreVia",
    description: "AI that reads your book so you don't have to remember everything",
    features: {
      "Works on any book": true,
      "Zero spoiler risk": true,
      "No manual data entry": true,
      "Tracks your reading position": true,
      "Automatic character extraction": true,
      "Finds plotholes": true,
      "Author writing tools": true,
      "Memory recall on return": true,
      "Relationship graph": true,
      "Works on unpublished novels": true,
    },
    bestFor: "Readers and authors who want spoiler-safe recall and continuity checks.",
    verdictType: "lorevia" as const,
  },
]

const comparisonFeatureList = [
  "Works on any book",
  "Zero spoiler risk",
  "No manual data entry",
  "Tracks your reading position",
  "Automatic character extraction",
  "Finds plotholes",
  "Author writing tools",
  "Memory recall on return",
  "Relationship graph",
  "Works on unpublished novels",
] as const

const comparisonFeatureDescriptions: Record<(typeof comparisonFeatureList)[number], string> = {
  "Works on any book": "Not limited to popular titles or public wikis",
  "Zero spoiler risk": "Never shows content beyond your reading position",
  "No manual data entry": "Extracts the story automatically from the text",
  "Tracks your reading position": "Keeps the context anchored to where you are",
  "Automatic character extraction": "Reads the manuscript and builds profiles",
  "Finds plotholes": "Flags contradictions and missing story threads",
  "Author writing tools": "Character bible, feedback, and continuity help",
  "Memory recall on return": "Brings you back up to speed after a break",
  "Relationship graph": "Visual map of how characters connect",
  "Works on unpublished novels": "Works on drafts and private work in progress",
}

const pricingTiers = [
  {
    name: "Starter",
    priceMonthly: 0,
    priceAnnual: 0,
    subtitle: "For trying the product on a small library.",
    bullets: [
      "Track up to 2 books",
      "Basic summaries and recall",
      "Tap character names for context",
      "A lightweight way to explore the product",
    ],
    highlight: false,
    cta: "Start free",
  },
  {
    name: "Reader",
    priceMonthly: 12,
    priceAnnual: 120,
    subtitle: "For dedicated readers who come back to long books.",
    bullets: [
      "Everything in Starter, plus",
      "Unlimited books",
      "Multi-mode story summaries",
      "Ask unlimited questions about your story",
    ],
    highlight: false,
    cta: "Go Reader",
  },
  {
    name: "Author",
    priceMonthly: 24,
    priceAnnual: 240,
    subtitle: "For manuscript builders who need continuity support.",
    bullets: [
      "Everything in Reader, plus",
      "Catch continuity errors automatically",
      "Chapter and manuscript feedback",
      "Auto-generated character reference sheets",
      "Visual relationship maps",
    ],
    highlight: true,
    cta: "Start drafting",
  },
  {
    name: "Architect",
    priceMonthly: 36,
    priceAnnual: 360,
    subtitle: "For series and world-builders at scale.",
    bullets: [
      "Everything in Author, plus",
      "Faster processing for large files",
      "Deeper continuity analysis",
      "Analyze multiple books together",
      "Early access to new features",
    ],
    highlight: false,
    cta: "Build your world",
  },
]

const faqItems = [
  {
    q: "Does it rewrite my manuscript?",
    a: "No. LoreVia analyzes the text and leaves the source untouched.",
  },
  {
    q: "Will it work on long books?",
    a: "Yes. The page is designed around long-form manuscripts and series workflows.",
  },
  {
    q: "Is the answer grounded in my book?",
    a: "Yes. Results are tied back to chapter and passage context so you can verify them quickly.",
  },
]

function useInView(threshold = 0.12) {
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
    <section id={id} className={`mx-auto max-w-7xl px-6 py-20 md:px-8 md:py-28 ${className}`}>
      {children}
    </section>
  )
}

function SectionHeader({
  eyebrow,
  title,
  body,
  isDark,
}: {
  eyebrow: string
  title: string
  body?: string
  isDark: boolean
}) {
  return (
    <div className="max-w-3xl">
      <p className={`text-xs font-semibold uppercase tracking-[0.34em] ${isDark ? "text-cyan-300" : "text-cyan-700"}`}>
        {eyebrow}
      </p>
      <h2 className={`mt-4 text-3xl font-semibold tracking-tight md:text-5xl ${isDark ? "text-white" : "text-slate-950"}`}>
        {title}
      </h2>
      {body ? (
        <p className={`mt-5 max-w-2xl text-base leading-8 md:text-lg ${isDark ? "text-slate-300" : "text-slate-600"}`}>
          {body}
        </p>
      ) : null}
    </div>
  )
}

function LogoMark() {
  return (
    <div className="flex items-center gap-3">
      <img src="/image.png" alt="LoreVia" className="h-12 w-12 rounded-2xl object-cover shadow-[0_18px_40px_-20px_rgba(15,23,42,0.6)]" />
      <div>
        <p className="text-sm font-semibold tracking-[0.3em]">LOREVIA</p>
        <p className="text-xs text-slate-500">Manuscript intelligence</p>
      </div>
    </div>
  )
}

function getButtonClass(isDark: boolean, variant: "primary" | "secondary" = "primary") {
  if (variant === "primary") {
    return isDark
      ? "inline-flex items-center justify-center rounded-full bg-white px-7 py-4 text-base font-semibold text-slate-950 shadow-[0_20px_55px_-25px_rgba(255,255,255,0.45)] transition hover:-translate-y-0.5 hover:bg-slate-100"
      : "inline-flex items-center justify-center rounded-full bg-slate-950 px-7 py-4 text-base font-semibold text-white shadow-[0_20px_55px_-25px_rgba(15,23,42,0.45)] transition hover:-translate-y-0.5 hover:bg-slate-800"
  }

  return isDark
    ? "inline-flex items-center justify-center rounded-full border border-white/12 bg-white/6 px-7 py-4 text-base font-semibold text-white transition hover:border-white/20 hover:bg-white/10"
  : "inline-flex items-center justify-center rounded-full border border-slate-200 bg-white px-7 py-4 text-base font-semibold text-slate-900 transition hover:border-slate-300 hover:bg-slate-50"
}

function ComparisonCheck({ isDark }: { isDark: boolean }) {
  return (
    <span className={`inline-flex h-8 w-8 items-center justify-center rounded-full text-sm font-bold ${
      isDark ? "bg-emerald-400/15 text-emerald-300" : "bg-emerald-50 text-emerald-700"
    }`}>
      +
    </span>
  )
}

function ComparisonCross({ isDark }: { isDark: boolean }) {
  return (
    <span className={`inline-flex h-8 w-8 items-center justify-center rounded-full text-sm font-bold ${
      isDark ? "bg-white/6 text-slate-500" : "bg-slate-100 text-slate-400"
    }`}>
      -
    </span>
  )
}

function ComparisonSection({ ctaHref, isDark }: { ctaHref: "/library" | "/login"; isDark: boolean }) {
  const [activeTooltip, setActiveTooltip] = useState<string | null>(null)

  return (
    <Section id="comparison">
        <div className="mx-auto max-w-6xl">
          <div className="text-center">
            <p className={`text-xs font-semibold uppercase tracking-[0.34em] ${isDark ? "text-cyan-300" : "text-cyan-700"}`}>
              Why LoreVia
            </p>
            <h2 className={`mt-4 text-3xl font-semibold tracking-tight md:text-5xl ${isDark ? "text-white" : "text-slate-950"}`}>
              Other tools still make you
              <br />
              do the work yourself.
            </h2>
            <p className={`mx-auto mt-5 max-w-2xl text-base leading-8 ${isDark ? "text-slate-300" : "text-slate-600"}`}>
            Wikis help if the story already has a page. Campfire and Scrivener help you build. LoreVia reads the
            manuscript and keeps the recall, continuity, and relationships in one place.
          </p>
        </div>

        <Reveal>
          <div
            className={`mt-12 overflow-hidden rounded-[2rem] border shadow-[0_24px_70px_-35px_rgba(15,23,42,0.4)] ${
              isDark ? "border-white/10 bg-white/[0.03]" : "border-slate-200 bg-white"
            }`}
          >
            <div className="overflow-x-auto">
              <table className="w-full min-w-[920px] border-separate border-spacing-0">
                <thead>
                  <tr>
                    <th
                      className={`sticky left-0 z-10 border-b px-8 py-7 text-left align-bottom ${
                        isDark ? "border-white/10 bg-[#060b14]" : "border-slate-100 bg-white"
                      }`}
                    >
                      <span className={`text-[11px] font-semibold uppercase tracking-[0.32em] ${isDark ? "text-slate-500" : "text-slate-400"}`}>
                        Feature
                      </span>
                    </th>
                    {comparisonCompetitors.map((competitor) => {
                      const isLoreVia = competitor.verdictType === "lorevia"
                      return (
                        <th
                          key={competitor.name}
                          className={`relative border-b px-4 pb-6 pt-7 text-center align-bottom ${
                            isLoreVia
                              ? isDark
                                ? "border-cyan-300/20 bg-cyan-400/[0.06]"
                                : "border-cyan-100 bg-cyan-50/70"
                              : isDark
                                ? "border-white/10"
                                : "border-slate-100"
                          }`}
                          >
                            {isLoreVia ? <div className="absolute inset-x-0 top-0 h-1 bg-cyan-400" /> : null}
                            <div className="flex flex-col items-center gap-3">
                              <div
                                className={`flex h-12 w-12 items-center justify-center rounded-2xl border text-sm font-semibold tracking-[0.14em] ${
                                  isLoreVia
                                    ? "border-cyan-300/40 bg-cyan-400/15"
                                    : isDark
                                      ? "border-white/10 bg-white/[0.04]"
                                      : "border-slate-200 bg-slate-50"
                                }`}
                                title={competitor.description}
                              >
                                {isLoreVia ? "LV" : competitor.name === "Campfire Write" ? "CW" : competitor.name === "Scrivener" ? "SC" : competitor.name === "Kindle X-Ray" ? "KX" : "FW"}
                              </div>
                              <div>
                                <p className={`text-sm font-semibold ${isLoreVia ? "text-cyan-700 dark:text-cyan-200" : isDark ? "text-white" : "text-slate-900"}`}>
                                  {competitor.name}
                                </p>
                                <p className={`mt-1 max-w-[11rem] text-[11px] leading-5 ${isDark ? "text-slate-500" : "text-slate-400"}`}>
                                  {competitor.description}
                                </p>
                              </div>
                            </div>
                        </th>
                      )
                    })}
                  </tr>
                </thead>
                <tbody>
                  {comparisonFeatureList.map((feature) => (
                    <tr key={feature} className={isDark ? "hover:bg-white/[0.025]" : "hover:bg-slate-50/80"}>
                      <td
                        className={`sticky left-0 z-[1] border-b px-8 py-5 text-left ${
                          isDark ? "border-white/10 bg-[#060b14]" : "border-slate-100 bg-white"
                        }`}
                      >
                        <div
                          className="relative inline-flex max-w-[14rem] items-start gap-3"
                          onMouseEnter={() => setActiveTooltip(feature)}
                          onMouseLeave={() => setActiveTooltip(null)}
                        >
                          <div>
                            <p className={`text-sm font-medium leading-6 ${isDark ? "text-slate-100" : "text-slate-800"}`}>
                              {feature}
                            </p>
                            <p className={`mt-1 text-[11px] leading-5 ${isDark ? "text-slate-500" : "text-slate-400"}`}>
                              {comparisonFeatureDescriptions[feature]}
                            </p>
                          </div>
                          {activeTooltip === feature ? (
                            <div
                              className={`absolute left-0 bottom-full z-50 mb-2 max-w-xs rounded-xl px-3 py-2 text-xs leading-5 shadow-xl ${
                                isDark ? "bg-white text-slate-950" : "bg-slate-950 text-white"
                              }`}
                            >
                              {comparisonFeatureDescriptions[feature]}
                            </div>
                          ) : null}
                        </div>
                      </td>
                      {comparisonCompetitors.map((competitor) => {
                        const isLoreVia = competitor.verdictType === "lorevia"
                        return (
                          <td
                            key={`${competitor.name}-${feature}`}
                            className={`border-b px-4 py-5 text-center ${
                              isLoreVia
                                ? isDark
                                  ? "border-cyan-300/20 bg-cyan-400/[0.04]"
                                  : "border-cyan-100 bg-cyan-50/50"
                                : isDark
                                  ? "border-white/10"
                                  : "border-slate-100"
                            }`}
                          >
                            <div className="flex justify-center">
                              {competitor.features[feature] ? <ComparisonCheck isDark={isDark} /> : <ComparisonCross isDark={isDark} />}
                            </div>
                          </td>
                        )
                      })}
                    </tr>
                  ))}
                  <tr className={isDark ? "bg-white/[0.02]" : "bg-slate-50/70"}>
                    <td
                      className={`sticky left-0 z-[1] border-b px-8 py-5 text-left ${
                        isDark ? "border-white/10 bg-[#090f19]" : "border-slate-100 bg-slate-50/70"
                      }`}
                    >
                      <span className={`text-[11px] font-semibold uppercase tracking-[0.28em] ${isDark ? "text-slate-500" : "text-slate-400"}`}>
                        Best for
                      </span>
                    </td>
                    {comparisonCompetitors.map((competitor) => {
                      const isLoreVia = competitor.verdictType === "lorevia"
                      return (
                        <td
                          key={`${competitor.name}-bestfor`}
                          className={`border-b px-4 py-5 text-center align-top ${
                            isLoreVia
                              ? isDark
                                ? "border-cyan-300/20 bg-cyan-400/[0.06]"
                                : "border-cyan-100 bg-cyan-50/70"
                              : isDark
                                ? "border-white/10"
                                : "border-slate-100"
                          }`}
                        >
                          <span
                            className={`inline-flex min-h-[4.5rem] items-center rounded-2xl px-3 py-2 text-left text-xs leading-5 ${
                              isLoreVia
                                ? isDark
                                  ? "bg-cyan-400/15 text-cyan-100"
                                  : "bg-cyan-100 text-cyan-900"
                                : isDark
                                  ? "bg-white/[0.05] text-slate-200"
                                  : "bg-slate-100 text-slate-700"
                            }`}
                          >
                            {competitor.bestFor}
                          </span>
                        </td>
                      )
                    })}
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </Reveal>

        <div className="mt-10 text-center">
          <Link
            href={ctaHref}
            className={`inline-flex items-center justify-center rounded-full px-7 py-4 text-sm font-semibold transition hover:-translate-y-[1px] ${
              isDark
                ? "bg-white text-slate-950 hover:bg-slate-100"
                : "bg-slate-950 text-white hover:bg-slate-800"
            }`}
          >
            Upload manuscript
          </Link>
          <p className={`mt-3 text-xs font-medium ${isDark ? "text-slate-500" : "text-slate-400"}`}>
            Built for readers and authors working with real books, not prefilled templates.
          </p>
        </div>
      </div>
    </Section>
  )
}

export default function LandingPage() {
  const { user } = useAuthStore()
  const isDark = true
  const [billingCycle, setBillingCycle] = useState<"monthly" | "annual">("monthly")

  const ctaHref = user ? "/library" : "/login"
  const secondaryCtaHref = user ? "/pricing" : "/login"

  const shellClass = isDark
    ? "min-h-screen bg-[#040814] text-white"
    : "min-h-screen bg-[#f7f3ee] text-slate-950"

  return (
    <main className={`relative overflow-hidden ${shellClass}`}>
      <div
        className={`pointer-events-none absolute inset-0 ${
          isDark
            ? "bg-[radial-gradient(circle_at_top_left,rgba(56,189,248,0.14),transparent_38%),radial-gradient(circle_at_top_right,rgba(168,85,247,0.12),transparent_35%),linear-gradient(to_bottom,rgba(255,255,255,0.03),transparent_24%)]"
            : "bg-[radial-gradient(circle_at_top_left,rgba(56,189,248,0.14),transparent_36%),radial-gradient(circle_at_top_right,rgba(15,23,42,0.06),transparent_28%),linear-gradient(to_bottom,rgba(255,255,255,0.55),transparent_28%)]"
        }`}
      />
      <div className="pointer-events-none absolute left-1/2 top-32 h-[32rem] w-[32rem] -translate-x-1/2 rounded-full bg-cyan-400/10 blur-3xl" />
      <div className="pointer-events-none absolute -right-32 top-[22rem] h-[28rem] w-[28rem] rounded-full bg-indigo-500/10 blur-3xl" />

      <header className="relative z-10">
        <nav className="mx-auto flex max-w-7xl items-center justify-between px-6 py-6 md:px-8 md:py-8">
          <LogoMark />
          <div className="hidden items-center gap-8 lg:flex">
            <a href="#product" className={`text-sm font-medium transition ${isDark ? "text-slate-300 hover:text-white" : "text-slate-600 hover:text-slate-950"}`}>
              Product
            </a>
            <a href="#workflow" className={`text-sm font-medium transition ${isDark ? "text-slate-300 hover:text-white" : "text-slate-600 hover:text-slate-950"}`}>
              How it works
            </a>
            <a href="#pricing" className={`text-sm font-medium transition ${isDark ? "text-slate-300 hover:text-white" : "text-slate-600 hover:text-slate-950"}`}>
              Pricing
            </a>
            <a href="#faq" className={`text-sm font-medium transition ${isDark ? "text-slate-300 hover:text-white" : "text-slate-600 hover:text-slate-950"}`}>
              FAQ
            </a>
          </div>
          <Link href={ctaHref} className={getButtonClass(isDark, "primary")}>
            {user ? "Open library" : "Get started"}
          </Link>
        </nav>
      </header>

      <section className="relative z-10">
        <div className="mx-auto grid max-w-7xl gap-10 px-6 pb-16 pt-6 md:px-8 md:pb-24 lg:grid-cols-[1.05fr_0.95fr] lg:items-center lg:gap-16 lg:pt-10">
          <div>
            <Reveal>
              <div className={`inline-flex items-center rounded-full border px-4 py-2 text-xs font-semibold tracking-[0.26em] ${isDark ? "border-white/10 bg-white/6 text-cyan-200" : "border-slate-200 bg-white text-cyan-800"}`}>
                FOR READERS AND AUTHORS
              </div>
            </Reveal>

            <Reveal delay={60}>
              <h1 className={`mt-6 max-w-3xl text-5xl font-semibold leading-[0.95] tracking-tight md:text-7xl ${isDark ? "text-white" : "text-slate-950"}`}>
                Pick up any story.
                <span className={`block ${isDark ? "text-slate-300" : "text-slate-600"}`}>
                  Remember every thread.
                </span>
              </h1>
            </Reveal>

            <Reveal delay={120}>
              <p className={`mt-6 max-w-2xl text-lg leading-8 md:text-xl ${isDark ? "text-slate-300" : "text-slate-600"}`}>
                LoreVia reads your manuscript and turns it into a structured reference layer, so you can ask about
                characters, relationships, and past events without hunting through the text yourself.
              </p>
            </Reveal>

            <Reveal delay={180}>
              <div className="mt-8 flex flex-wrap gap-4">
                <Link href={ctaHref} className={getButtonClass(isDark, "primary")}>
                  Upload manuscript
                </Link>
                <Link href={secondaryCtaHref} className={getButtonClass(isDark, "secondary")}>
                  View pricing
                </Link>
              </div>
            </Reveal>

            <Reveal delay={240}>
              <div className="mt-8 flex flex-wrap gap-3">
                {trustStats.map((item) => (
                  <div
                    key={item.label}
                    className={`rounded-2xl border px-4 py-3 ${isDark ? "border-white/10 bg-white/6" : "border-slate-200 bg-white"} `}
                  >
                    <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-slate-950"}`}>{item.value}</p>
                    <p className={`text-xs ${isDark ? "text-slate-400" : "text-slate-500"}`}>{item.label}</p>
                  </div>
                ))}
              </div>
            </Reveal>
          </div>

          <Reveal delay={120} className="relative">
            <div
              className={`relative overflow-hidden rounded-[2rem] border p-5 shadow-[0_30px_120px_-40px_rgba(15,23,42,0.5)] md:p-7 ${
                isDark ? "border-white/10 bg-white/5" : "border-slate-200 bg-white"
              }`}
            >
              <div className={`absolute inset-0 ${isDark ? "bg-[linear-gradient(135deg,rgba(255,255,255,0.04),transparent_36%)]" : "bg-[linear-gradient(135deg,rgba(15,23,42,0.02),transparent_36%)]"}`} />
              <div className="relative">
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <p className={`text-[11px] font-semibold uppercase tracking-[0.32em] ${isDark ? "text-cyan-200" : "text-cyan-700"}`}>
                      Manuscript workspace
                    </p>
                    <p className={`mt-2 text-base ${isDark ? "text-slate-300" : "text-slate-600"}`}>
                      A cleaner view into a 120-chapter story
                    </p>
                  </div>
                  <div className={`rounded-full px-4 py-2 text-sm font-semibold ${isDark ? "bg-cyan-400/15 text-cyan-200" : "bg-cyan-50 text-cyan-800"}`}>
                    Live analysis
                  </div>
                </div>

                <div className="mt-6 grid items-start gap-4 md:grid-cols-[1.1fr_0.9fr]">
                  <div className={`rounded-[1.6rem] border p-5 ${isDark ? "border-white/10 bg-slate-950/30" : "border-slate-200 bg-slate-50"}`}>
                    <p className={`text-xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-400" : "text-slate-500"}`}>
                      Ask anything
                    </p>
                    <div className="mt-4 space-y-4">
                      <div className={`rounded-2xl border px-4 py-4 ${isDark ? "border-white/10 bg-white/6" : "border-slate-200 bg-white"}`}>
                        <p className={`text-sm font-medium ${isDark ? "text-white" : "text-slate-950"}`}>
                          Which clue ties the sealed letter to the council vote, and where does the timeline break?
                        </p>
                        <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-300" : "text-slate-600"}`}>
                          LoreVia traces every mention of the letter, connects it to the vote, and flags the gap before the
                          reveal in Chapter 42.
                        </p>
                      </div>
                      <div className={`rounded-2xl border px-4 py-4 ${isDark ? "border-white/10 bg-white/6" : "border-slate-200 bg-white"}`}>
                        <p className={`text-sm font-medium ${isDark ? "text-white" : "text-slate-950"}`}>
                          Where does the rebellion arc actually turn from alliance into distrust?
                        </p>
                        <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-300" : "text-slate-600"}`}>
                          It spots the exact chapters where the relationship shifts, then links the turning points back to the
                          scenes that caused them.
                        </p>
                      </div>
                    </div>
                  </div>

                  <div className="grid gap-4">
                      <div className={`rounded-[1.6rem] border p-5 ${isDark ? "border-white/10 bg-white/6" : "border-slate-200 bg-white"}`}>
                        <p className={`text-xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-400" : "text-slate-500"}`}>
                          Story health
                        </p>
                        <div className="mt-5 space-y-3">
                          {[
                            ["58", "characters detected"],
                            ["3", "open threads"],
                            ["1", "continuity issue"],
                          ].map(([value, label]) => (
                            <div
                              key={label}
                              className={`flex items-center justify-between rounded-2xl border px-4 py-3 ${
                                isDark ? "border-white/10 bg-slate-950/30" : "border-slate-200 bg-slate-50"
                              }`}
                            >
                              <div>
                                <p className={`text-2xl font-semibold ${isDark ? "text-white" : "text-slate-950"}`}>{value}</p>
                                <p className={`mt-1 text-[11px] uppercase tracking-[0.2em] ${isDark ? "text-slate-400" : "text-slate-500"}`}>
                                  {label}
                                </p>
                              </div>
                              <span className={`rounded-full px-3 py-1 text-xs font-semibold ${
                                isDark ? "bg-white/10 text-slate-200" : "bg-white text-slate-700"
                              }`}>
                                live
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>

                    <div className={`rounded-[1.6rem] border p-5 ${isDark ? "border-cyan-400/20 bg-cyan-400/8" : "border-cyan-200 bg-cyan-50"}`}>
                      <p className={`text-xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-cyan-200" : "text-cyan-800"}`}>
                        Answer quality
                      </p>
                      <p className={`mt-3 text-sm leading-7 ${isDark ? "text-slate-200" : "text-slate-700"}`}>
                        Chapter-linked answers, character context, and continuity checks are presented together instead
                        of as separate tiny widgets.
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </Reveal>
        </div>
      </section>

      <Section id="product">
        <SectionHeader
          eyebrow="Why it feels different"
          title="Built like a real workspace, not a thin marketing page."
          body="The visual language is intentionally larger, calmer, and more substantial so the product feels credible at first glance."
          isDark={isDark}
        />

        <div className="mt-10 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {featureCards.map((card, index) => (
            <Reveal key={card.title} delay={index * 70}>
              <article
                className={`h-full rounded-[1.8rem] border p-6 shadow-[0_18px_60px_-40px_rgba(15,23,42,0.45)] ${
                  isDark ? "border-white/10 bg-white/5" : "border-slate-200 bg-white"
                }`}
              >
                <div className={`inline-flex h-12 w-12 items-center justify-center rounded-2xl text-base font-semibold ${
                  isDark ? "bg-cyan-400/15 text-cyan-200" : "bg-cyan-50 text-cyan-800"
                }`}>
                  {String(index + 1).padStart(2, "0")}
                </div>
                <h3 className={`mt-5 text-xl font-semibold ${isDark ? "text-white" : "text-slate-950"}`}>{card.title}</h3>
                <p className={`mt-3 text-base leading-7 ${isDark ? "text-slate-300" : "text-slate-600"}`}>{card.body}</p>
              </article>
            </Reveal>
          ))}
        </div>

        <div className="mt-10 grid gap-4 lg:grid-cols-[1fr_1fr]">
          <Reveal>
            <div className={`rounded-[2rem] border p-7 ${isDark ? "border-white/10 bg-white/5" : "border-slate-200 bg-white"}`}>
              <p className={`text-sm font-semibold uppercase tracking-[0.28em] ${isDark ? "text-cyan-300" : "text-cyan-700"}`}>
                The problem
              </p>
              <div className="mt-6 space-y-4">
                {painPoints.map((item) => (
                  <div key={item} className={`rounded-2xl border px-5 py-4 ${isDark ? "border-white/10 bg-slate-950/30" : "border-slate-200 bg-slate-50"}`}>
                    <p className={`text-base leading-7 ${isDark ? "text-slate-200" : "text-slate-700"}`}>{item}</p>
                  </div>
                ))}
              </div>
            </div>
          </Reveal>

          <Reveal delay={90}>
            <div className={`rounded-[2rem] border p-7 ${isDark ? "border-cyan-400/20 bg-cyan-400/8" : "border-cyan-200 bg-cyan-50"}`}>
              <p className={`text-sm font-semibold uppercase tracking-[0.28em] ${isDark ? "text-cyan-200" : "text-cyan-800"}`}>
                The fix
              </p>
              <h3 className={`mt-6 text-2xl font-semibold ${isDark ? "text-white" : "text-slate-950"}`}>
                Give the story a memory layer.
              </h3>
              <p className={`mt-4 text-base leading-8 ${isDark ? "text-slate-200" : "text-slate-700"}`}>
                LoreVia turns raw chapters into a cleaner reference system: larger surfaces, clearer hierarchy, and
                enough visual weight to feel like software built for serious manuscript work.
              </p>
              <div className="mt-8 flex flex-wrap gap-3">
                <span className={`rounded-full border px-4 py-2 text-sm font-medium ${isDark ? "border-white/10 bg-white/10 text-white" : "border-slate-200 bg-white text-slate-700"}`}>
                  chapter-linked answers
                </span>
                <span className={`rounded-full border px-4 py-2 text-sm font-medium ${isDark ? "border-white/10 bg-white/10 text-white" : "border-slate-200 bg-white text-slate-700"}`}>
                  character bible
                </span>
                <span className={`rounded-full border px-4 py-2 text-sm font-medium ${isDark ? "border-white/10 bg-white/10 text-white" : "border-slate-200 bg-white text-slate-700"}`}>
                  continuity checks
                </span>
              </div>
            </div>
          </Reveal>
        </div>
      </Section>

      <Section id="workflow">
        <SectionHeader
          eyebrow="How it works"
          title="Three steps, but the experience feels much larger."
          body="The interface should feel like a real product, so the workflow panels are intentionally broad and readable."
          isDark={isDark}
        />

        <div className="mt-10 grid gap-5 lg:grid-cols-3">
          {workflowSteps.map((step, index) => (
            <Reveal key={step.num} delay={index * 80}>
              <article
                className={`h-full rounded-[2rem] border p-7 ${isDark ? "border-white/10 bg-white/5" : "border-slate-200 bg-white"}`}
              >
                <p className={`text-sm font-semibold uppercase tracking-[0.32em] ${isDark ? "text-cyan-300" : "text-cyan-700"}`}>
                  {step.num}
                </p>
                <h3 className={`mt-5 text-2xl font-semibold ${isDark ? "text-white" : "text-slate-950"}`}>{step.title}</h3>
                <p className={`mt-4 text-base leading-8 ${isDark ? "text-slate-300" : "text-slate-600"}`}>{step.body}</p>
              </article>
            </Reveal>
          ))}
        </div>
        </Section>

      <Section>
        <SectionHeader
          eyebrow="Who it's for"
          title="Built for screenwriters and authors working across formats."
          body="Scripts, novels, chapter-wise webnovels, and book series all need different kinds of memory. LoreVia keeps them organized without forcing a single workflow."
          isDark={isDark}
        />

        <div className="mt-10 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {audienceCards.map((card, index) => (
            <Reveal key={card.title} delay={index * 70}>
              <article
                className={`h-full rounded-[1.8rem] border p-6 shadow-[0_18px_60px_-40px_rgba(15,23,42,0.45)] ${
                  isDark ? "border-white/10 bg-white/5" : "border-slate-200 bg-white"
                }`}
              >
                <p className={`text-[11px] font-semibold uppercase tracking-[0.28em] ${isDark ? "text-cyan-300" : "text-cyan-700"}`}>
                  {String(index + 1).padStart(2, "0")}
                </p>
                <h3 className={`mt-4 text-xl font-semibold ${isDark ? "text-white" : "text-slate-950"}`}>{card.title}</h3>
                <p className={`mt-3 text-base leading-7 ${isDark ? "text-slate-300" : "text-slate-600"}`}>{card.body}</p>
              </article>
            </Reveal>
          ))}
        </div>
      </Section>

        <ComparisonSection ctaHref={ctaHref} isDark={isDark} />

        <Section>
        <SectionHeader
          eyebrow="Example output"
          title="What a real scan looks like."
          body="The goal is to make the result feel concrete, legible, and worth trusting."
          isDark={isDark}
        />

        <div className="mt-10 grid gap-6 lg:grid-cols-[1.05fr_0.95fr]">
          <Reveal>
            <div className={`rounded-[2rem] border p-7 ${isDark ? "border-white/10 bg-white/5" : "border-slate-200 bg-white"}`}>
              <div className="flex items-center justify-between gap-4">
                <div>
                  <p className={`text-xs font-semibold uppercase tracking-[0.28em] ${isDark ? "text-cyan-300" : "text-cyan-700"}`}>
                    Scan results
                  </p>
                  <p className={`mt-2 text-base ${isDark ? "text-slate-300" : "text-slate-600"}`}>
                    A 120-chapter epic fantasy manuscript processed in seconds.
                  </p>
                </div>
                <div className={`rounded-full border px-4 py-2 text-sm font-semibold ${isDark ? "border-white/10 bg-white/8 text-white" : "border-slate-200 bg-slate-50 text-slate-800"}`}>
                  Ready to review
                </div>
              </div>

              <div className="mt-6 space-y-4">
                {proofItems.map((item) => (
                  <div
                    key={item.title}
                    className={`rounded-2xl border px-5 py-4 ${
                      item.tone === "warning"
                        ? isDark
                          ? "border-amber-400/20 bg-amber-400/8"
                          : "border-amber-200 bg-amber-50"
                        : isDark
                          ? "border-white/10 bg-white/6"
                          : "border-slate-200 bg-slate-50"
                    }`}
                  >
                    <p className={`text-base font-semibold ${isDark ? "text-white" : "text-slate-950"}`}>{item.title}</p>
                    <p className={`mt-2 text-sm leading-7 ${isDark ? "text-slate-300" : "text-slate-600"}`}>{item.body}</p>
                  </div>
                ))}
              </div>
            </div>
          </Reveal>

          <Reveal delay={100}>
            <div className={`rounded-[2rem] border p-7 ${isDark ? "border-white/10 bg-white/5" : "border-slate-200 bg-white"}`}>
              <p className={`text-xs font-semibold uppercase tracking-[0.28em] ${isDark ? "text-cyan-300" : "text-cyan-700"}`}>
                Output summary
              </p>
              <div className="mt-6 grid gap-4 sm:grid-cols-3">
                {[
                  ["58", "characters detected"],
                  ["3", "open threads"],
                  ["1", "issue flagged"],
                ].map(([value, label]) => (
                  <div key={label} className={`rounded-2xl border p-4 text-center ${isDark ? "border-white/10 bg-slate-950/30" : "border-slate-200 bg-slate-50"}`}>
                    <p className={`text-3xl font-semibold ${isDark ? "text-white" : "text-slate-950"}`}>{value}</p>
                    <p className={`mt-2 text-xs uppercase tracking-[0.2em] ${isDark ? "text-slate-400" : "text-slate-500"}`}>{label}</p>
                  </div>
                ))}
              </div>

              <blockquote className={`mt-6 rounded-2xl border-l-4 px-5 py-5 ${isDark ? "border-cyan-300 bg-cyan-400/8 text-slate-200" : "border-cyan-600 bg-cyan-50 text-slate-700"}`}>
                Built to handle long manuscripts, multi-book series, and chapter-linked answers without mixing contexts.
              </blockquote>
            </div>
          </Reveal>
        </div>
      </Section>

      <Section id="pricing">
        <div className="flex flex-col gap-10 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-2xl">
            <SectionHeader
              eyebrow="Pricing"
              title="Pick a tier that matches your pace."
              body="Monthly billing is shown by default. Every signup gets a short trial window so people can explore the workspace before committing."
              isDark={isDark}
            />
          </div>

          <div className={`relative inline-flex items-center rounded-full p-1 ${isDark ? "bg-white/10" : "bg-slate-950"}`}>
            <div
              className="absolute left-1 top-1 h-[calc(100%-8px)] w-[calc(50%-4px)] rounded-full bg-white transition-transform duration-300 ease-out"
              style={{ transform: billingCycle === "annual" ? "translateX(100%)" : "translateX(0)" }}
            />
            <button
              type="button"
              onClick={() => setBillingCycle("monthly")}
              className={`relative z-10 rounded-full px-5 py-2.5 text-sm font-semibold transition-colors duration-200 ${
                billingCycle === "monthly"
                  ? "text-slate-950"
                  : isDark
                    ? "text-slate-300 hover:text-white"
                    : "text-slate-300 hover:text-slate-100"
              }`}
            >
              Monthly
            </button>
            <button
              type="button"
              onClick={() => setBillingCycle("annual")}
              className={`relative z-10 rounded-full px-5 py-2.5 text-sm font-semibold transition-colors duration-200 ${
                billingCycle === "annual"
                  ? "text-slate-950"
                  : isDark
                    ? "text-slate-300 hover:text-white"
                    : "text-slate-300 hover:text-slate-100"
              }`}
            >
              Annual
            </button>
          </div>
        </div>

        <div className="mt-14 grid gap-5 md:grid-cols-2 lg:grid-cols-4">
          {pricingTiers.map((tier, index) => {
            const price = billingCycle === "annual" ? tier.priceAnnual : tier.priceMonthly
            const suffix = tier.name === "Starter" ? "" : billingCycle === "annual" ? "/yr" : "/mo"

            return (
              <Reveal key={tier.name} delay={index * 70} className="h-full">
                <article
                  className={`group relative flex h-full flex-col rounded-[2rem] p-8 transition-all duration-300 hover:-translate-y-1 ${
                    tier.highlight
                      ? isDark
                        ? "border border-cyan-300/20 bg-cyan-400/[0.08] shadow-[0_24px_70px_-35px_rgba(34,211,238,0.22)]"
                        : "border border-cyan-200 bg-cyan-50/80 shadow-[0_24px_70px_-35px_rgba(14,165,233,0.18)]"
                      : isDark
                        ? "border border-white/10 bg-white/[0.04]"
                        : "border border-slate-200 bg-white"
                  }`}
                >
                  <div className="mb-8 flex items-center justify-between">
                    <span className={`text-[10px] font-semibold uppercase tracking-[0.24em] ${
                      tier.highlight
                        ? isDark
                          ? "text-cyan-200"
                          : "text-cyan-700"
                        : isDark
                          ? "text-slate-500"
                          : "text-slate-400"
                    }`}>
                      {tier.name}
                    </span>
                    {tier.highlight ? (
                      <div className={`h-2 w-2 rounded-full ${isDark ? "bg-cyan-300" : "bg-cyan-600"}`} />
                    ) : null}
                  </div>

                  <div className="flex items-baseline gap-1">
                    <span className={`text-5xl font-semibold tracking-tight ${isDark ? "text-white" : "text-slate-950"}`}>
                      {tier.name === "Starter" ? "$0" : `$${price}`}
                    </span>
                    <span className={`text-sm ${isDark ? "text-slate-400" : "text-slate-500"}`}>{suffix}</span>
                  </div>

                  <p className={`mt-3 text-sm ${isDark ? "text-slate-300" : "text-slate-600"}`}>{tier.subtitle}</p>

                  <ul className="mb-8 mt-8 space-y-4">
                    {tier.bullets.map((bullet) => (
                      <li key={bullet} className="flex items-start gap-3 text-sm leading-relaxed">
                        <span
                          className={`mt-0.5 text-base font-bold ${
                            tier.highlight
                              ? isDark
                                ? "text-cyan-200"
                                : "text-cyan-700"
                              : isDark
                                ? "text-slate-500"
                                : "text-slate-400"
                          }`}
                        >
                          •
                        </span>
                        <span className={isDark ? "text-slate-200" : "text-slate-700"}>{bullet}</span>
                      </li>
                    ))}
                  </ul>

                  <div className="mt-auto">
                    <Link
                      href={ctaHref}
                      className={`inline-flex w-full items-center justify-center rounded-full py-3.5 text-sm font-semibold transition-all duration-200 ${
                        tier.highlight
                          ? isDark
                            ? "bg-white text-slate-950 hover:bg-slate-100"
                            : "bg-slate-950 text-white hover:bg-slate-800"
                          : isDark
                            ? "border border-white/10 bg-white/[0.04] text-slate-200 hover:border-white/20 hover:bg-white/10"
                            : "border border-slate-200 bg-white text-slate-700 hover:border-slate-300 hover:text-slate-900"
                      }`}
                    >
                      {tier.cta}
                    </Link>
                  </div>
                </article>
              </Reveal>
            )
          })}
        </div>
      </Section>

      <Section id="faq">
        <SectionHeader
          eyebrow="FAQ"
          title="The common questions, answered plainly."
          isDark={isDark}
        />

        <div className="mt-10 grid gap-5 md:grid-cols-3">
          {faqItems.map((item, index) => (
            <Reveal key={item.q} delay={index * 80}>
              <article className={`h-full rounded-[1.8rem] border p-7 ${isDark ? "border-white/10 bg-white/5" : "border-slate-200 bg-white"}`}>
                <h3 className={`text-xl font-semibold ${isDark ? "text-white" : "text-slate-950"}`}>{item.q}</h3>
                <p className={`mt-4 text-base leading-8 ${isDark ? "text-slate-300" : "text-slate-600"}`}>{item.a}</p>
              </article>
            </Reveal>
          ))}
        </div>
      </Section>

      <section className={`relative z-10 border-t ${isDark ? "border-white/10 bg-[#02050d]" : "border-slate-200 bg-slate-950"}`}>
        <div className="mx-auto max-w-7xl px-6 py-20 md:px-8 md:py-24">
          <div className="grid gap-8 lg:grid-cols-[1.05fr_0.95fr] lg:items-center">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.34em] text-cyan-300">
                Ready when you are
              </p>
              <h2 className="mt-5 text-4xl font-semibold tracking-tight text-white md:text-6xl">
                Stop rereading.
                <span className="block text-slate-300">Start querying.</span>
              </h2>
              <p className="mt-5 max-w-2xl text-lg leading-8 text-slate-400">
                Upload your manuscript and get a clearer, more professional way to work with the story.
              </p>
            </div>

            <div className="flex flex-col gap-4 sm:flex-row sm:justify-end">
              <Link href={ctaHref} className="inline-flex items-center justify-center rounded-full bg-white px-8 py-4 text-base font-semibold text-slate-950 transition hover:bg-slate-100">
                Upload manuscript
              </Link>
              <Link href={secondaryCtaHref} className="inline-flex items-center justify-center rounded-full border border-white/15 px-8 py-4 text-base font-semibold text-white transition hover:border-white/30 hover:bg-white/8">
                Explore pricing
              </Link>
            </div>
          </div>
        </div>
      </section>
    </main>
  )
}
