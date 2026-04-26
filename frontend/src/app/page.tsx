"use client"

import Link from "next/link"
import { useEffect, useRef, useState } from "react"
import { useAuthStore } from "@/lib/stores/authStore"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"

// ─── Static data ──────────────────────────────────────────────────────────────

const trustStats = [
  { value: "EPUB & PDF", label: "supported formats" },
  { value: "Any length", label: "no chapter limit" },
  { value: "Zero edits", label: "your text is never changed" },
]

const painPoints = [
  "You forget when a character last appeared",
  "You contradict something from 100 chapters ago",
  "You waste hours searching your own text",
  "Readers catch your inconsistencies before you do",
]

const steps = [
  {
    num: "01",
    title: "Upload your manuscript",
    body: "Drop in your EPUB or PDF. Any length, any genre.",
  },
  {
    num: "02",
    title: "We structure your story",
    body: "Every character, relationship, and event — extracted and organised from your text.",
  },
  {
    num: "03",
    title: "Ask anything. Get cited answers.",
    body: "Every answer references the exact chapter it came from. No hallucinations.",
  },
]

const features = [
  {
    icon: "🔍",
    title: "Find anything instantly",
    body: "\"When did this character last appear?\" \"What's the relationship between X and Y?\"",
    checks: ["Instant answers", "With chapter references"],
  },
  {
    icon: "📖",
    title: "Your character bible—generated automatically",
    body: "Every character, their roles, and relationships — generated directly from your manuscript.",
    checks: ["Roles and arc summaries", "Relationship map"],
  },
  {
    icon: "🗂️",
    title: "Manage entire series without confusion",
    body: "Keep each book separate. Search stays scoped to the active book.",
    checks: ["Series stay isolated", "Book-scoped search"],
  },
  {
    icon: "⚠️",
    title: "Catch continuity errors early",
    body: "Catch inconsistencies before your readers do. Contradictions, dropped threads, missing appearances.",
    checks: ["Conflicting descriptions flagged", "Dropped threads surfaced"],
  },
]

const proofStats = [
  { value: "58", label: "characters detected" },
  { value: "3",  label: "unresolved threads" },
  { value: "1",  label: "continuity issue" },
]

const proofOutputs = [
  {
    severity: "warning",
    text: "Conflicting eye description: Aria",
    sub: "\"blue\" (Ch. 12) → \"green\" (Ch. 64) — no character state change recorded",
  },
  {
    severity: "warning",
    text: "Character hasn't appeared in 87 chapters",
    sub: "Last seen: Ch. 14 — \"The Northern Gate\" — 87 chapters of silence",
  },
  {
    severity: "info",
    text: "Unresolved plot thread introduced in Chapter 8",
    sub: "\"The sealed letter\" — mentioned 4 times, still open",
  },
]

const objections = [
  {
    q: "Will this rewrite my story?",
    a: "No. LoreVia only reads and analyses your text. It never changes a single word.",
  },
  {
    q: "Is my manuscript safe?",
    a: "Your content is private and never used for training or shared with anyone.",
  },
  {
    q: "How accurate is it?",
    a: "Every answer is grounded in your actual text with chapter references. If it's not in your manuscript, it won't appear here.",
  },
]

const demoQueries = [
  {
    q: "When did Arthur last appear?",
    chapter: "Chapter 42 — The Council Scene",
    excerpt: "\"Arthur stood at the back of the hall, his expression unreadable as the votes were cast...\"",
  },
  {
    q: "What's the relationship between Sara and Kai?",
    chapter: "Estranged siblings",
    excerpt: "First appeared together in Chapter 7. Relationship deteriorated by Ch. 31. No reconciliation recorded.",
  },
]

const targetAudiences = [
  "Novelists writing long-form fiction",
  "Fantasy & sci-fi authors managing complex worlds",
  "Writers working on multi-book series",
]

const heroHeadlineVariants = [
  {
    audience: "For readers",
    accent: "Remember every thread.",
    title: "Pick up any story.",
    body: "Character memory, clue recall, and spoiler-safe context whenever you return.",
  },
  {
    audience: "For authors",
    accent: "Catch every contradiction.",
    title: "Draft with full recall.",
    body: "Continuity, character memory, and story intelligence while you build the manuscript.",
  },
] as const

const comparisonCompetitors = [
  {
    name: "Fandom Wiki",
    icon: "📖",
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
    bestFor: "Readers of big-name series who just want a quick refresher (and don’t mind spoilers or gaps).",
    verdictType: "bad" as const,
  },
  {
    name: "Kindle X-Ray",
    icon: "📱",
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
    bestFor: "Kindle-only reading when you just need a lightweight “who’s this again?” lookup.",
    verdictType: "bad" as const,
  },
  {
    name: "Campfire Write",
    icon: "🏕️",
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
    bestFor: "Worldbuilding and planning when you prefer filling in structured templates by hand.",
    verdictType: "neutral" as const,
  },
  {
    name: "Scrivener",
    icon: "✍️",
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
    bestFor: "Drafting and revision workflows when you want a powerful writing studio (not auto-extracted story memory).",
    verdictType: "neutral" as const,
  },
  {
    name: "LoreVia",
    icon: null,
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
    bestFor: "Authors (and returning readers) who want spoiler-safe recall, auto-built character bibles, and continuity checks—grounded in the exact chapters.",
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
  "Works on any book": "Not just bestsellers or popular series",
  "Zero spoiler risk": "Never shows content past where you've read",
  "No manual data entry": "Extracts everything from your text automatically",
  "Tracks your reading position": "Knows exactly where you are in the story",
  "Automatic character extraction": "Reads the manuscript and builds profiles itself",
  "Finds plotholes": "Detects contradictions across hundreds of chapters",
  "Author writing tools": "Continuity checker, character bible, and story advisor",
  "Memory recall on return": "\"Previously on...\" when you come back after a break",
  "Relationship graph": "Visual map of every character connection",
  "Works on unpublished novels": "Your drafts, your WIPs, your private manuscripts",
}

// ─── useInView hook ───────────────────────────────────────────────────────────

function useInView(threshold = 0.12) {
  const ref = useRef<HTMLDivElement>(null)
  const [inView, setInView] = useState(false)

  useEffect(() => {
    const obs = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) setInView(true) },
      { threshold }
    )
    if (ref.current) obs.observe(ref.current)
    return () => obs.disconnect()
  }, [threshold])

  return { ref, inView }
}

// ─── AnimatedCard — scroll-triggered fade-up wrapper ─────────────────────────

function AnimatedCard({
  children,
  delay = 0,
  className = "",
}: {
  children: React.ReactNode
  delay?: number
  className?: string
}) {
  const { ref, inView } = useInView()
  return (
    <div
      ref={ref}
      style={{ transitionDelay: `${delay}ms` }}
      className={`transition-opacity duration-300 ease-out ${
        inView ? "opacity-100" : "opacity-0"
      } ${className}`}
    >
      {children}
    </div>
  )
}

// ─── Main page ────────────────────────────────────────────────────────────────

function ComparisonSection({
  ctaHref,
  isDark,
}: {
  ctaHref: "/library" | "/login"
  isDark: boolean
}) {
  const [activeTooltip, setActiveTooltip] = useState<string | null>(null)

  return (
    <Section id="comparison">
      <div className="mx-auto max-w-6xl">
        <div className="text-center">
          <p className={`text-xs font-bold uppercase tracking-[0.32em] ${isDark ? "text-red-400" : "text-red-600"}`}>
            Why LoreVia
          </p>
          <h2 className={`mt-4 font-semibold text-4xl leading-tight md:text-5xl ${isDark ? "text-white" : "text-slate-900"}`}>
            Every other tool makes you
            <br />
            do the work yourself.
          </h2>
          <p className={`mx-auto mt-5 max-w-2xl text-base leading-7 ${isDark ? "text-slate-400" : "text-slate-600"}`}>
            Wikis spoil you. Campfire makes you fill it in. Kindle X-Ray stays shallow. LoreVia reads your book so
            you don&apos;t have to remember everything.
          </p>
        </div>

        <AnimatedCard>
          <div
            className={`mt-14 overflow-hidden rounded-lg border ${
              isDark ? "border-slate-800 bg-slate-900" : "border-slate-200 bg-white"
            }`}
          >
            <div className="overflow-x-auto">
              <table className="w-full min-w-[980px] border-separate border-spacing-0">
                <thead>
                  <tr>
                    <th
                      className={`sticky left-0 z-10 border-b px-6 py-6 text-left align-bottom ${
                        isDark ? "border-slate-800 bg-slate-900" : "border-slate-200 bg-white"
                      }`}
                    >
                      <span className={`text-[11px] font-bold uppercase tracking-[0.26em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>
                        Features
                      </span>
                    </th>
                    {comparisonCompetitors.map((competitor) => {
                      const isLoreVia = competitor.verdictType === "lorevia"

                      return (
                        <th
                          key={competitor.name}
                          className={`relative border-b px-4 pb-5 pt-6 text-center align-bottom ${
                            isLoreVia
                              ? isDark
                                ? "border-slate-700 bg-slate-800"
                                : "border-slate-300 bg-slate-50"
                              : isDark
                                ? "border-slate-800"
                                : "border-slate-200"
                          }`}
                        >
                          {isLoreVia ? <div className="absolute inset-x-0 top-0 h-0.5 bg-red-600 dark:bg-red-400" /> : null}
                          <div className="flex flex-col items-center gap-3">
                            <div
                              className={`flex h-12 w-12 items-center justify-center rounded-lg border text-xl ${
                                isLoreVia
                                  ? "border-red-500/50 bg-red-500/10 dark:border-red-400/50 dark:bg-red-400/10"
                                  : isDark
                                    ? "border-slate-700 bg-slate-800"
                                    : "border-slate-200 bg-slate-50"
                              }`}
                              title={competitor.description}
                            >
                              {isLoreVia ? <LoreViaMark /> : competitor.icon}
                            </div>
                            <div>
                              <p className={`text-sm font-semibold ${isLoreVia ? "text-red-600 dark:text-red-400" : isDark ? "text-white" : "text-slate-900"}`}>
                                {competitor.name}
                              </p>
                              <p className={`mt-1 max-w-[11rem] text-[11px] leading-4 ${isDark ? "text-slate-500" : "text-stone-400"}`}>
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
                    <tr key={feature} className={isDark ? "hover:bg-slate-800/50" : "hover:bg-slate-50"}>
                      <td
                        className={`sticky left-0 z-[1] border-b px-6 py-4 text-left ${
                          isDark ? "border-slate-800 bg-slate-900" : "border-slate-200 bg-white"
                        }`}
                      >
                        <div
                          className="relative inline-flex items-center gap-2"
                          onMouseEnter={() => setActiveTooltip(feature)}
                          onMouseLeave={() => setActiveTooltip(null)}
                        >
                          <span className={`text-sm font-medium ${isDark ? "text-slate-200" : "text-stone-700"}`}>
                            {feature}
                          </span>
                          <button
                            type="button"
                            aria-label={`More about ${feature}`}
                            className={`flex h-5 w-5 items-center justify-center rounded-md text-[10px] font-bold transition-colors ${
                              isDark
                                ? "bg-slate-800 text-slate-400 hover:bg-slate-700 hover:text-slate-200"
                                : "bg-slate-100 text-slate-400 hover:bg-slate-200 hover:text-slate-600"
                            }`}
                            onFocus={() => setActiveTooltip(feature)}
                            onBlur={() => setActiveTooltip(null)}
                          >
                            ?
                          </button>
                          {activeTooltip === feature ? (
                            <div
                              className={`absolute left-0 bottom-full z-50 mb-2 max-w-xs rounded-lg px-3 py-2 text-xs leading-5 shadow-lg ${
                                isDark ? "bg-slate-800 text-slate-100 border border-slate-700" : "bg-slate-900 text-white border border-slate-700"
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
                            className={`border-b px-4 py-4 text-center ${
                              isLoreVia
                                ? isDark
                                  ? "border-red-500/30 bg-red-500/5"
                                  : "border-red-300 bg-red-50"
                                : isDark
                                  ? "border-slate-800"
                                  : "border-slate-200"
                            }`}
                          >
                            <div className="flex justify-center">
                              {competitor.features[feature] ? <ComparisonCheck /> : <ComparisonCross isDark={isDark} />}
                            </div>
                          </td>
                        )
                      })}
                    </tr>
                  ))}

                  <tr className={isDark ? "bg-slate-800/30" : "bg-slate-50"}>
                    <td
                      className={`sticky left-0 z-[1] border-b px-6 py-4 text-left ${
                        isDark ? "border-slate-800 bg-slate-800/50" : "border-slate-200 bg-slate-50"
                      }`}
                    >
                      <span className={`text-[11px] font-bold uppercase tracking-[0.26em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>
                        Best for
                      </span>
                    </td>
                    {comparisonCompetitors.map((competitor) => {
                      const isLoreVia = competitor.verdictType === "lorevia"
                      const badgeClass = isLoreVia
                        ? isDark
                          ? "bg-red-500/20 text-red-100"
                          : "bg-red-100 text-red-900"
                        : isDark
                          ? "bg-slate-800 text-slate-200"
                          : "bg-slate-100 text-slate-800"

                      return (
                        <td
                          key={`${competitor.name}-verdict`}
                          className={`border-b px-4 py-4 text-center align-top ${
                            isLoreVia
                              ? isDark
                                ? "border-red-500/30 bg-red-500/5"
                                : "border-red-300 bg-red-50"
                              : isDark
                                ? "border-slate-800"
                                : "border-slate-200"
                          }`}
                        >
                          <span className={`inline-block rounded-md px-3 py-2 text-left text-xs leading-5 ${badgeClass}`}>
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
        </AnimatedCard>

        <div className="mt-10 text-center">
          <Link
            href={ctaHref}
            className={`inline-flex items-center justify-center rounded-lg px-7 py-3 text-sm font-semibold transition-colors duration-150 ${
              isDark
                ? "bg-white text-slate-900 hover:bg-slate-100"
                : "bg-slate-900 text-white hover:bg-slate-800"
            }`}
          >
            Upload Manuscript
          </Link>
          <p className={`mt-3 text-xs font-medium ${isDark ? "text-slate-500" : "text-stone-400"}`}>
            Built for readers and authors working with real books, not prefilled templates.
          </p>
        </div>
      </div>
    </Section>
  )
}

function ComparisonCheck() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden="true">
      <circle cx="9" cy="9" r="9" fill="currentColor" fillOpacity="0.1" className="text-slate-900 dark:text-white" />
      <path d="M5 9.5L8 12.5L13 6.5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className="text-slate-900 dark:text-white" />
    </svg>
  )
}

function ComparisonCross({ isDark }: { isDark: boolean }) {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden="true">
      <circle cx="9" cy="9" r="9" fill="currentColor" fillOpacity="0.05" className={isDark ? "text-slate-400" : "text-slate-400"} />
      <path d="M6 6L12 12M12 6L6 12" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" className={isDark ? "text-slate-500" : "text-slate-400"} />
    </svg>
  )
}

function LoreViaMark() {
  return (
    <svg width="28" height="28" viewBox="0 0 28 28" fill="none" aria-hidden="true">
      <circle cx="14" cy="14" r="4" fill="white" />
      <circle cx="5" cy="8" r="2.5" fill="white" fillOpacity="0.7" />
      <circle cx="23" cy="8" r="2.5" fill="white" fillOpacity="0.7" />
      <circle cx="5" cy="20" r="2.5" fill="white" fillOpacity="0.7" />
      <circle cx="23" cy="20" r="2.5" fill="white" fillOpacity="0.7" />
      <circle cx="14" cy="3" r="2" fill="white" fillOpacity="0.5" />
      <circle cx="14" cy="25" r="2" fill="white" fillOpacity="0.5" />
      <line x1="14" y1="14" x2="5" y2="8" stroke="white" strokeWidth="1" strokeOpacity="0.6" />
      <line x1="14" y1="14" x2="23" y2="8" stroke="white" strokeWidth="1" strokeOpacity="0.6" />
      <line x1="14" y1="14" x2="5" y2="20" stroke="white" strokeWidth="1" strokeOpacity="0.6" />
      <line x1="14" y1="14" x2="23" y2="20" stroke="white" strokeWidth="1" strokeOpacity="0.6" />
      <line x1="14" y1="14" x2="14" y2="3" stroke="white" strokeWidth="1" strokeOpacity="0.4" />
      <line x1="14" y1="14" x2="14" y2="25" stroke="white" strokeWidth="1" strokeOpacity="0.4" />
    </svg>
  )
}

export default function HomePage() {
  const user = useAuthStore((s) => s.user)
  const { theme } = usePreferencesStore()
  const isDark = theme === "dark"
  const [activeDemo, setActiveDemo] = useState(0)
  const [activeHeroHeadline, setActiveHeroHeadline] = useState(0)
  const [heroHeadlineVisible, setHeroHeadlineVisible] = useState(true)
  const heroSwapTimeoutRef = useRef<number | null>(null)

  const ctaHref = user ? "/library" : "/login"

  useEffect(() => {
    const t = setInterval(() => setActiveDemo((p) => (p + 1) % demoQueries.length), 5200)
    return () => clearInterval(t)
  }, [])

  useEffect(() => {
    const interval = window.setInterval(() => {
      setHeroHeadlineVisible(false)
      heroSwapTimeoutRef.current = window.setTimeout(() => {
        setActiveHeroHeadline((current) => (current + 1) % heroHeadlineVariants.length)
        setHeroHeadlineVisible(true)
      }, 180)
    }, 4000)

    return () => {
      window.clearInterval(interval)
      if (heroSwapTimeoutRef.current !== null) {
        window.clearTimeout(heroSwapTimeoutRef.current)
      }
    }
  }, [])

  const currentHeroHeadline = heroHeadlineVariants[activeHeroHeadline]

  return (
    <main
      className={`min-h-screen transition-colors ${
        isDark
          ? "bg-[linear-gradient(180deg,#000000_0%,#050505_42%,#0b0b0b_100%)] text-slate-100"
          : "bg-white text-slate-900"
      }`}
    >

      {/* ══ NAVBAR ═══════════════════════════════════════════════════════════════ */}
      <nav
        className={`sticky top-0 z-50 border-b backdrop-blur-md ${
          isDark
            ? "border-white/[0.06] bg-black/75"
            : "border-slate-200 bg-white"
        }`}
      >
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4 lg:px-10">
          <img src="/logoandtext.png" alt="LoreVia" className="h-8 w-auto" />

          <div
            className={`hidden md:flex items-center gap-8 text-sm font-medium ${
              isDark ? "text-slate-400" : "text-slate-500"
            }`}
          >
            <a href="#how"      className={`transition-colors hover:${isDark ? "text-white" : "text-slate-900"}`}>How it works</a>
            <a href="#features" className={`transition-colors hover:${isDark ? "text-white" : "text-slate-900"}`}>Features</a>
            <a href="#faq"      className={`transition-colors hover:${isDark ? "text-white" : "text-slate-900"}`}>FAQ</a>
          </div>

          <Link
            href={ctaHref}
            className={`rounded-lg px-5 py-2 text-sm font-semibold transition-colors duration-150 ${
              isDark
                ? "bg-white text-slate-900 hover:bg-slate-100"
                : "bg-slate-900 text-white hover:bg-slate-800"
            }`}
          >
            Get started
          </Link>
        </div>
      </nav>

      {/* ══ 1. HERO ══════════════════════════════════════════════════════════════ */}
      <section className="relative mx-auto max-w-7xl px-6 pb-16 pt-20 lg:px-10 lg:pb-20 lg:pt-28">

        {/* Dramatic layered ambient glow with red */}
        <div className="pointer-events-none absolute inset-0 overflow-hidden">
          <div
            className={`absolute -top-40 left-1/2 -translate-x-1/2 h-[600px] w-[900px] rounded-full blur-[120px] ${
              isDark ? "opacity-[0.18] bg-red-600" : "opacity-[0.22] bg-red-300"
            }`}
          />
          <div
            className={`absolute -top-20 left-1/3 h-[400px] w-[500px] rounded-full blur-[100px] ${
              isDark ? "opacity-[0.10] bg-orange-400" : "opacity-[0.14] bg-orange-200"
            }`}
          />
        </div>

        <div className="relative grid gap-14 lg:grid-cols-2 lg:items-center">

          {/* Left — copy */}
          <div>
            <img src="/logoandtext.png" alt="LoreVia" className="mb-8 h-12 w-auto object-contain sm:h-14" />

            <div className="mb-6 flex flex-wrap items-center gap-4">
              <div
                className={`inline-flex min-w-[10rem] items-center justify-center rounded-md border px-4 py-1.5 text-[11px] font-bold uppercase tracking-[0.32em] ${
                  isDark
                    ? "border-white/10 bg-white/[0.04] text-red-400"
                    : "border-slate-200 bg-slate-100 text-slate-600"
                }`}
              >
                {currentHeroHeadline.audience}
              </div>
              <p className={`text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>
                {currentHeroHeadline.body}
              </p>
            </div>

            <div className="relative min-h-[10rem] sm:min-h-[12rem] md:min-h-[13.5rem]">
              <h1
                className={`font-semibold text-[3.2rem] leading-[1.2] tracking-tight transition-opacity duration-200 sm:text-[4.2rem] md:text-[4.8rem] ${
                  isDark ? "text-white" : "text-slate-900"
                } ${heroHeadlineVisible ? "opacity-100" : "opacity-0"}`}
              >
                {currentHeroHeadline.title}
                <br />
                <span className={isDark ? "text-red-400" : "text-slate-600"}>
                  {currentHeroHeadline.accent}
                </span>
              </h1>
            </div>

            <p
              className={`mt-6 max-w-[480px] text-base leading-7 ${
                isDark ? "text-slate-400" : "text-slate-600"
              }`}
            >
              Upload your manuscript and ask anything about your characters, relationships, or past
              events — with answers grounded in exact chapters and passages.
            </p>

            <div className="mt-8 flex flex-col gap-4 sm:flex-row sm:items-center">
              <Link
                href={ctaHref}
                className={`inline-flex items-center justify-center rounded-lg px-8 py-3 text-base font-semibold transition-colors duration-150 ${
                  isDark
                    ? "bg-white text-slate-900 hover:bg-slate-100"
                    : "bg-slate-900 text-white hover:bg-slate-800"
                }`}
              >
                Upload Manuscript
              </Link>
              <button
                onClick={() => document.getElementById("proof")?.scrollIntoView({ behavior: "smooth" })}
                className={`text-sm font-medium transition ${
                  isDark ? "text-slate-400 hover:text-slate-200" : "text-stone-500 hover:text-stone-800"
                }`}
              >
                See example report →
              </button>
            </div>

            <p className={`mt-4 text-xs font-medium ${isDark ? "text-slate-600" : "text-stone-400"}`}>
              Free • No credit card required
            </p>
          </div>

          {/* Right — demo card */}
          <div
            className={`rounded-lg border ${
              isDark
                ? "border-slate-800 bg-slate-900"
                : "border-slate-200 bg-white"
            }`}
          >
              {/* Window chrome */}
              <div
                className={`flex items-center gap-2 border-b px-5 py-3 ${
                  isDark ? "border-slate-800 bg-slate-800/50" : "border-slate-200 bg-slate-50"
                }`}
              >
                <span className="h-2.5 w-2.5 rounded-full bg-red-400" />
                <span className="h-2.5 w-2.5 rounded-full bg-amber-400" />
                <span className="h-2.5 w-2.5 rounded-full bg-emerald-400" />
                <span className={`ml-2 text-[11px] font-medium ${isDark ? "text-slate-400" : "text-slate-500"}`}>
                  manuscript.epub — workspace
                </span>
              </div>

              {/* "This is real" legitimacy signal */}
              <div className="px-6 pt-4 pb-1">
                <p className={`text-xs font-semibold uppercase tracking-[0.28em] ${
                  isDark ? "text-slate-500" : "text-slate-500"
                }`}>
                  Example output from a real manuscript
                </p>
              </div>

              {/* Demo queries */}
              <div className="space-y-5 p-6 pt-3">
                {demoQueries.map((demo, i) => (
                  <div
                    key={i}
                    className={`transition-opacity duration-300 ease-out ${
                      activeDemo === i ? "opacity-100" : "opacity-50"
                    }`}
                  >
                    <div className="mb-3 flex items-start gap-2.5">
                      <span className={`mt-px text-sm font-bold ${isDark ? "text-slate-400" : "text-slate-500"}`}>
                        ›
                      </span>
                      <p className={`text-sm font-medium ${isDark ? "text-slate-200" : "text-slate-800"}`}>
                        {demo.q}
                      </p>
                    </div>
                    <div
                      className={`ml-5 rounded-lg border px-4 py-4 ${
                        isDark ? "border-slate-800 bg-slate-800/50" : "border-slate-200 bg-slate-50"
                      }`}
                    >
                      <p className={`text-[11px] font-bold uppercase tracking-[0.26em] mb-2 ${
                        isDark ? "text-slate-400" : "text-slate-600"
                      }`}>
                        {demo.chapter}
                      </p>
                      <p className={`text-xs leading-5 ${isDark ? "text-slate-400" : "text-stone-500"}`}>
                        {demo.excerpt}
                      </p>
                    </div>
                  </div>
                ))}

                {/* Fake input bar — static cursor (no pulse) */}
                <div
                  className={`flex items-center gap-3 rounded-[0.9rem] border px-4 py-3 ${
                    isDark ? "border-white/[0.06] bg-white/[0.04]" : "border-stone-200 bg-stone-50"
                  }`}
                >
                  <span className={`flex-1 text-sm ${isDark ? "text-slate-600" : "text-stone-400"}`}>
                    Ask anything about your story…
                  </span>
                  <span className={`h-[14px] w-px ${isDark ? "bg-white/30" : "bg-red-300"}`} />
                </div>
              </div>

              {/* Pagination dots */}
              <div className="flex justify-center gap-1.5 pb-5">
                {demoQueries.map((_, i) => (
                  <button
                    key={i}
                    onClick={() => setActiveDemo(i)}
                    className={`h-1.5 rounded-full transition-all duration-300 ${
                      activeDemo === i
                        ? isDark ? "w-5 bg-white" : "w-5 bg-red-500"
                        : isDark ? "w-1.5 bg-white/20" : "w-1.5 bg-stone-300"
                    }`}
                  />
                ))}
              </div>
          </div>
        </div>
      </section>

      {/* ══ 2. TRUST STATS BAR ═══════════════════════════════════════════════════ */}
      <section
        className={`border-y py-10 ${
          isDark ? "border-white/[0.06] bg-white/[0.02]" : "border-stone-200 bg-stone-50"
        }`}
      >
        <div className="mx-auto max-w-5xl px-6 grid grid-cols-3 gap-8 text-center lg:px-10">
          {trustStats.map(({ value, label }, i) => (
            <AnimatedCard key={label} delay={i * 80}>
              <p className={`font-serif text-3xl font-semibold sm:text-4xl ${isDark ? "text-white" : "text-stone-950"}`}>
                {value}
              </p>
              <p className={`mt-1 text-sm ${isDark ? "text-slate-500" : "text-stone-500"}`}>
                {label}
              </p>
            </AnimatedCard>
          ))}
        </div>
      </section>

      {/* ══ 3. PAIN ══════════════════════════════════════════════════════════════ */}
      <section className={`py-20 ${isDark ? "bg-[#040404]" : "bg-stone-950"}`}>
        <div className="mx-auto max-w-5xl px-6 lg:px-10">
          <h2 className="font-serif text-3xl leading-tight text-white sm:text-4xl md:text-[2.8rem]">
            Long stories break your memory.
          </h2>

          <div className="mt-10 grid gap-3 sm:grid-cols-2">
            {painPoints.map((point, i) => (
              <AnimatedCard key={point} delay={i * 60}>
                <div className="flex items-start gap-3 rounded-[1.2rem] border border-white/[0.07] bg-white/[0.04] px-5 py-4">
                  <span className="mt-0.5 shrink-0 text-amber-400 text-sm">✗</span>
                  <p className="text-sm leading-6 text-slate-300">{point}</p>
                </div>
              </AnimatedCard>
            ))}
          </div>

          <p className="mt-9 text-base font-medium text-slate-500">
            You're solving this manually. You shouldn't have to.
          </p>
        </div>
      </section>

      {/* ══ 4. HOW IT WORKS ════════════════════════════════════════════════════════ */}
      <Section id="how">
        <SectionHeader eyebrow="How it works" title="Three steps. That's it." body="" isDark={isDark} />

        <div className="mt-12 grid gap-5 md:grid-cols-2 xl:grid-cols-4">
          {steps.map((step, i) => (
            <AnimatedCard key={step.num} delay={i * 80}>
              <article
                className={`rounded-[2rem] border p-7 h-full ${
                  isDark ? "border-white/10 bg-white/[0.04]" : "border-stone-200 bg-white"
                }`}
              >
                <span className={`block font-serif text-[3rem] leading-none ${isDark ? "text-white/20" : "text-violet-200"}`}>
                  {step.num}
                </span>
                <h3 className={`mt-5 text-lg font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>
                  {step.title}
                </h3>
                <p className={`mt-3 text-sm leading-7 ${isDark ? "text-slate-300" : "text-stone-600"}`}>
                  {step.body}
                </p>
              </article>
            </AnimatedCard>
          ))}
        </div>
      </Section>

      {/* ══ 5. FEATURES ══════════════════════════════════════════════════════════ */}
      <Section id="features">
        <SectionHeader eyebrow="Features" title="Four things. Done right." body="" isDark={isDark} />

        <div className="mt-12 grid gap-6 md:grid-cols-2 xl:grid-cols-4">
          {features.map((f, i) => (
            <AnimatedCard key={f.title} delay={i * 80}>
              <article
                className={`rounded-[2rem] border p-7 h-full ${
                  isDark ? "border-white/10 bg-white/[0.04]" : "border-stone-200 bg-white"
                }`}
              >
                <span className="text-2xl">{f.icon}</span>
                <h3 className={`mt-5 text-lg font-semibold leading-snug ${isDark ? "text-white" : "text-stone-950"}`}>
                  {f.title}
                </h3>
                <p className={`mt-3 text-sm leading-7 ${isDark ? "text-slate-400" : "text-stone-500"}`}>
                  {f.body}
                </p>
                <ul className="mt-5 space-y-2">
                  {f.checks.map((c) => (
                    <li key={c} className="flex items-center gap-2">
                      <span className={`text-xs font-extrabold ${isDark ? "text-teal-400" : "text-teal-600"}`}>✔</span>
                      <span className={`text-sm font-medium ${isDark ? "text-slate-200" : "text-stone-700"}`}>{c}</span>
                    </li>
                  ))}
                </ul>
              </article>
            </AnimatedCard>
          ))}
        </div>
      </Section>

      {/* ══ 6. PROOF ═════════════════════════════════════════════════════════════ */}
      <ComparisonSection ctaHref={ctaHref} isDark={isDark} />

      <Section id="proof">
        <div>
          <SectionHeader
            eyebrow="Example output"
            title="Here's what comes back from a 120-chapter manuscript."
            body=""
            isDark={isDark}
          />

          <AnimatedCard>
            <div
              className={`mt-12 overflow-hidden rounded-[2rem] border ${
                isDark ? "border-white/10 bg-[#080808]" : "border-stone-200 bg-white"
              }`}
            >
              {/* Scan header */}
              <div
                className={`flex flex-wrap items-center justify-between gap-5 border-b px-7 py-6 ${
                  isDark ? "border-white/[0.06] bg-white/[0.03]" : "border-stone-100 bg-stone-50"
                }`}
              >
                <div>
                  <p className={`text-[11px] font-bold uppercase tracking-[0.32em] ${isDark ? "text-neutral-300" : "text-violet-600"}`}>
                    Scan results
                  </p>
                  <p className={`mt-1 text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>
                    From a 120-chapter epic fantasy manuscript • processed in seconds
                  </p>
                </div>
                <div className="flex gap-3">
                  {proofStats.map(({ value, label }) => (
                    <div
                      key={label}
                      className={`rounded-[1rem] border px-4 py-3 text-center ${
                        isDark ? "border-white/[0.07] bg-white/[0.04]" : "border-stone-100 bg-stone-50"
                      }`}
                    >
                      <p className={`font-serif text-2xl font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>
                        {value}
                      </p>
                      <p className={`mt-0.5 text-[11px] ${isDark ? "text-slate-500" : "text-stone-400"}`}>
                        {label}
                      </p>
                    </div>
                  ))}
                </div>
              </div>

              {/* Output rows */}
              <div className="space-y-2.5 p-7">
                {proofOutputs.map(({ severity, text, sub }) => (
                  <div
                    key={text}
                    className={`flex items-start gap-4 rounded-[1.2rem] border px-5 py-4 ${
                      severity === "warning"
                        ? isDark ? "border-amber-500/25 bg-amber-500/[0.07]" : "border-amber-200 bg-amber-50"
                        : isDark ? "border-white/[0.06] bg-white/[0.03]" : "border-stone-100 bg-stone-50"
                    }`}
                  >
                    <span className="mt-0.5 shrink-0 text-base">
                      {severity === "warning" ? "⚠️" : "ℹ️"}
                    </span>
                    <div>
                      <p className={`text-sm font-medium ${isDark ? "text-slate-100" : "text-stone-800"}`}>
                        {text}
                      </p>
                      <p className={`mt-1 text-xs ${isDark ? "text-slate-500" : "text-stone-400"}`}>
                        {sub}
                      </p>
                    </div>
                  </div>
                ))}
                <p className={`pt-2 text-xs font-medium ${isDark ? "text-slate-600" : "text-stone-400"}`}>
                  Each finding links back to the exact chapter and passage.
                </p>
              </div>
            </div>
          </AnimatedCard>

          {/* Capacity note */}
          <AnimatedCard delay={100}>
            <blockquote
              className={`mt-8 rounded-[2rem] border p-8 ${
                isDark ? "border-white/10 bg-white/[0.03]" : "border-stone-200 bg-white"
              }`}
            >
              <p className={`font-serif text-xl leading-relaxed ${
                isDark ? "text-slate-200" : "text-stone-700"
              }`}>
                Built to handle long manuscripts, multi-book series, and chapter-linked answers without mixing contexts.
              </p>
              <footer className="mt-6 flex items-center gap-3">
                <div
                  className={`h-9 w-9 rounded-full flex items-center justify-center text-sm font-bold ${
                    isDark ? "bg-violet-500/30 text-violet-300" : "bg-violet-100 text-violet-600"
                  }`}
                >
                  12K
                </div>
                <div>
                  <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>
                    Scale-ready, not launch-padded
                  </p>
                  <p className={`text-xs ${isDark ? "text-slate-500" : "text-stone-400"}`}>
                    Designed for large libraries and series workflows
                  </p>
                </div>
              </footer>
            </blockquote>
          </AnimatedCard>
        </div>
      </Section>

      {/* ══ 7. BUILT FOR ═════════════════════════════════════════════════════════ */}
      <Section id="built-for">
        <SectionHeader eyebrow="Built for" title="Writers working with complex stories" body="" isDark={isDark} />

        <div className="mt-10 grid gap-4 md:grid-cols-3">
          {targetAudiences.map((item, i) => (
            <AnimatedCard key={item} delay={i * 80}>
              <div
                className={`rounded-[1.6rem] border px-6 py-5 ${
                  isDark ? "border-white/10 bg-white/[0.04]" : "border-stone-200 bg-white"
                }`}
              >
                <p className={`text-base font-medium leading-snug ${isDark ? "text-slate-100" : "text-stone-800"}`}>
                  {item}
                </p>
              </div>
            </AnimatedCard>
          ))}
        </div>
      </Section>

      {/* ══ 8. OBJECTIONS / FAQ ══════════════════════════════════════════════════ */}
      <Section id="faq">
        <SectionHeader eyebrow="Before you upload" title="Three questions authors always ask." body="" isDark={isDark} />

        <div className="mt-10 grid gap-5 md:grid-cols-3">
          {objections.map(({ q, a }, i) => (
            <AnimatedCard key={q} delay={i * 80}>
              <article
                className={`rounded-[2rem] border p-7 h-full ${
                  isDark ? "border-white/10 bg-white/[0.04]" : "border-stone-200 bg-white"
                }`}
              >
                <h3 className={`text-base font-semibold leading-snug ${isDark ? "text-white" : "text-stone-950"}`}>
                  "{q}"
                </h3>
                <p className={`mt-4 text-sm leading-7 ${isDark ? "text-slate-300" : "text-stone-600"}`}>
                  {a}
                </p>
              </article>
            </AnimatedCard>
          ))}
        </div>
      </Section>

      {/* ══ 9. FINAL CTA ═════════════════════════════════════════════════════════ */}
      <section className={`py-24 ${isDark ? "bg-[#040404]" : "bg-stone-950"}`}>
        <div className="mx-auto max-w-3xl px-6 text-center lg:px-10">
          <p className="text-[11px] font-bold uppercase tracking-[0.36em] text-indigo-400">
            Get started
          </p>
          <h2 className="mt-5 font-serif text-4xl leading-tight text-white sm:text-5xl">
            Stop rereading.
            <br />
            Start querying.
          </h2>
          <p className="mt-5 text-base text-slate-400">
            Upload your manuscript. Get answers in seconds.
          </p>
          <div className="mt-10 flex flex-col items-center gap-3">
            <Link
              href={ctaHref}
              className="inline-flex items-center justify-center rounded-[1.1rem] bg-white px-10 py-4 text-lg font-semibold text-black shadow-[0_20px_40px_-18px_rgba(255,255,255,0.3)] transition hover:bg-stone-100 hover:-translate-y-[1px] active:translate-y-0"
            >
              Upload Manuscript
            </Link>
            <p className="text-sm text-slate-600">Free • No credit card required</p>
          </div>
        </div>
      </section>

      

      {/* Footer is rendered globally via SiteFooter */}


    </main>
  )
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function Section({
  children,
  id,
  className = "",
}: {
  children: React.ReactNode
  id?: string
  className?: string
}) {
  return (
    <section id={id} className={`mx-auto max-w-7xl px-6 py-24 lg:px-10 lg:py-32 ${className}`}>
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
  body: string
  isDark: boolean
}) {
  return (
    <div className="max-w-3xl">
      <p className={`text-xs font-bold uppercase tracking-[0.32em] ${isDark ? "text-neutral-300" : "text-violet-600"}`}>
        {eyebrow}
      </p>
      <h2 className={`mt-4 font-serif text-4xl leading-tight md:text-5xl ${isDark ? "text-white" : "text-stone-950"}`}>
        {title}
      </h2>
      {body ? (
        <p className={`mt-5 max-w-xl text-base leading-7 ${isDark ? "text-slate-300" : "text-stone-600"}`}>
          {body}
        </p>
      ) : null}
    </div>
  )
}
