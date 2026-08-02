"use client"

import Image from "next/image"
import { useEffect, useRef, useState } from "react"

import { LANDING_SHOWCASE_VISUALS } from "@/lib/marketing/landingShowcaseVisuals"

export { LANDING_SHOWCASE_VISUALS }

type ShowcaseStep = {
  id: string
  title: string
  body: string
  detail: string
  caption: string
  visuals: string[]
  proofPoints: string[]
}

const showcaseSteps: ShowcaseStep[] = [
  {
    id: "analysis",
    title: "Analyze the full manuscript",
    body: "Upload your draft and LoreVia maps characters, chapters, scenes, relationships, timelines, and continuity risks so you can revise with context instead of guesswork.",
    detail: "The manuscript view keeps draft text, chapter structure, active characters, unresolved threads, and advisor context visible together so each revision decision stays tied to evidence.",
    caption: "Manuscript analysis / continuity sidebar / chapter evidence",
    visuals: [
      "/landing/manuscript-analysis.png",
      "/landing/manuscript-analysis-with-advisor.png",
    ],
    proofPoints: [
      "Detects timeline conflicts",
      "Finds character continuity issues",
      "Surfaces unresolved story logic",
      "Works across long manuscripts",
    ],
  },
  {
    id: "characters",
    title: "Track character continuity",
    body: "LoreVia tracks who your characters are, what they know, how they change, and where inconsistencies appear across the manuscript.",
    detail: "Profiles collect aliases, last-seen chapters, relationship notes, evidence passages, and continuity flags, making character drift easier to catch before a rewrite moves forward.",
    caption: "Character Bible / aliases / relationships / continuity flags",
    visuals: ["/landing/character-continuity.png"],
    proofPoints: [
      "Editable character profiles",
      "Alias and duplicate review",
      "Relationship evidence",
      "Knowledge-state warnings",
    ],
  },
  {
    id: "timeline",
    title: "Map scenes and timelines",
    body: "See whether events, reveals, injuries, travel, memories, and cause-effect chains still make sense as the story grows.",
    detail: "Timeline checks show where the manuscript establishes an event, which later scenes depend on it, and where the story needs a cleaner bridge or explanation.",
    caption: "Timeline logic / scene sequence / conflict markers",
    visuals: ["/landing/timeline-logic.png"],
    proofPoints: [
      "Event order checks",
      "Travel and recovery gaps",
      "Reveal timing",
      "Chapter-level source links",
    ],
  },
  {
    id: "graph",
    title: "Visualize relationships",
    body: "Track friendships, rivalries, family bonds, power dynamics, romantic tension, betrayals, and hidden connections in one structured graph.",
    detail: "The graph turns scattered relationship beats into a visible network, with selected edges linking back to shared evidence instead of relying on memory.",
    caption: "Relationship graph / selected edge / shared facets",
    visuals: ["/landing/relationship-graph.png"],
    proofPoints: [
      "Character networks",
      "Relationship notes",
      "Hidden connection review",
      "Tension and trust shifts",
    ],
  },
  {
    id: "editorial",
    title: "Review story logic",
    body: "LoreVia gives structured editorial diagnostics so you know what to fix, where it appears, and why it matters.",
    detail: "Editorial review separates pacing, continuity, clarity, and unresolved-thread issues so each note becomes a concrete revision target rather than a vague summary.",
    caption: "Editorial review / continuity / pacing / unresolved threads",
    visuals: [
      "/landing/editorial-review.png",
      "/landing/editorial-review-2.png",
    ],
    proofPoints: [
      "Issue categories",
      "Revision targets",
      "Pacing and plot risks",
      "Actionable diagnostics",
    ],
  },
  {
    id: "notes",
    title: "Keep notes beside the draft",
    body: "Build notes for characters, worlds, locations, factions, rules, themes, and unresolved ideas without leaving the writing workspace.",
    detail: "Notes stay close to the manuscript and can be organized around the parts of the story they explain, from world rules to callbacks and open questions.",
    caption: "Notes workspace / backlinks / worldbuilding references",
    visuals: ["/landing/notes-workspace.png"],
    proofPoints: [
      "Linked story notes",
      "Worldbuilding rules",
      "Character references",
      "Draft-adjacent context",
    ],
  },
  {
    id: "export",
    title: "Export with structure",
    body: "Structure chapters, scenes, notes, and export-ready manuscript sections without losing the story context you built along the way.",
    detail: "Export keeps the working structure visible while you prepare clean output, front matter, collaborator files, or a manuscript package for the next stage.",
    caption: "Export studio / front matter / manuscript package",
    visuals: ["/landing/export-workflow.png"],
    proofPoints: [
      "DOCX and EPUB workflows",
      "Front matter controls",
      "Chapter structure",
      "Notes retained for revision",
    ],
  },
]

export function LandingShowcase() {
  const [activeStepId, setActiveStepId] = useState(showcaseSteps[0].id)
  const stepRefs = useRef<Record<string, HTMLElement | null>>({})

  useEffect(() => {
    if (typeof window === "undefined" || !("IntersectionObserver" in window)) return

    const reduceMotion = Boolean(
      window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches,
    )
    const observer = new IntersectionObserver(
      (entries) => {
        const visibleEntry = entries
          .filter((entry) => entry.isIntersecting)
          .sort((left, right) => right.intersectionRatio - left.intersectionRatio)[0]

        if (visibleEntry?.target instanceof HTMLElement) {
          setActiveStepId(visibleEntry.target.dataset.showcaseStep ?? showcaseSteps[0].id)
        }
      },
      {
        rootMargin: reduceMotion ? "0px 0px -30% 0px" : "-18% 0px -42% 0px",
        threshold: [0.2, 0.45, 0.7],
      },
    )

    for (const step of showcaseSteps) {
      const element = stepRefs.current[step.id]
      if (element) observer.observe(element)
    }

    return () => observer.disconnect()
  }, [])

  const activeStep = showcaseSteps.find((step) => step.id === activeStepId) ?? showcaseSteps[0]

  return (
    <section id="features" className="mx-auto max-w-[1600px] px-5 py-20 md:px-8">
      <span id="sample-finding" className="block scroll-mt-24" aria-hidden="true" />
      <div className="max-w-3xl">
        <p className="text-3xs font-semibold uppercase tracking-[0.28em] text-[#d6a84f]">
          Product walkthrough
        </p>
        <h2 className="mt-5 font-display text-4xl font-semibold leading-[1.02] text-[#f4f1ea] md:text-5xl">
          One manuscript. Every hidden inconsistency surfaced.
        </h2>
        <p className="mt-5 text-lg leading-8 text-[#a09a90]">
          LoreVia turns your draft into a structured story workspace: characters, scenes, relationships,
          timelines, notes, and editorial diagnostics connected in one place.
        </p>
      </div>

      <div className="mt-14 grid gap-10 lg:grid-cols-[minmax(0,1.2fr)_minmax(360px,0.8fr)] lg:gap-14 2xl:grid-cols-[minmax(720px,1.3fr)_minmax(440px,0.7fr)]">
        <div className="hidden lg:block">
          <div className="sticky top-24">
            <ProductFrame step={activeStep} />
          </div>
        </div>

        <div className="space-y-8 lg:space-y-0">
          {showcaseSteps.map((step) => (
            <article
              key={step.id}
              ref={(element) => {
                stepRefs.current[step.id] = element
              }}
              data-showcase-step={step.id}
              className="min-h-[auto] border-t border-white/[0.08] py-10 lg:min-h-[78vh] lg:py-16"
            >
              <div className="mb-7 lg:hidden">
                <ProductFrame step={step} />
              </div>
              <p className="text-3xs font-semibold uppercase tracking-[0.24em] text-[#d6a84f]">
                {step.caption}
              </p>
              <h3 className="mt-5 font-display text-3xl font-semibold leading-tight text-[#f4f1ea] md:text-4xl">
                {step.title}
              </h3>
              <p className="mt-5 max-w-2xl text-lg leading-8 text-[#a09a90]">{step.body}</p>
              <p className="mt-4 max-w-2xl text-base leading-7 text-[#bcb6ab]">{step.detail}</p>
              <div className="mt-8 grid gap-3 sm:grid-cols-2">
                {step.proofPoints.map((point) => (
                  <div
                    key={point}
                    className="rounded-md border border-white/[0.08] bg-[#121214] px-4 py-3 text-sm font-semibold text-[#f4f1ea]"
                  >
                    {point}
                  </div>
                ))}
              </div>
            </article>
          ))}
        </div>
      </div>
    </section>
  )
}

function ProductFrame({ step }: { step: ShowcaseStep }) {
  const hasPairedVisuals = step.visuals.length > 1
  const [activeVisualIndex, setActiveVisualIndex] = useState(0)
  const [isPreviewHovered, setIsPreviewHovered] = useState(false)
  const previewVisualIndex = activeVisualIndex === 0 ? 1 : 0

  useEffect(() => {
    setActiveVisualIndex(0)
    setIsPreviewHovered(false)
  }, [step.id])

  return (
    <figure
      className={`w-full ${
        hasPairedVisuals
          ? "overflow-visible"
          : "overflow-hidden rounded-lg border border-white/10 bg-[#121214] shadow-[0_28px_90px_rgba(0,0,0,0.35)]"
      }`}
    >
      {hasPairedVisuals ? (
        <figcaption className="sr-only">{step.caption}</figcaption>
      ) : (
        <div className="flex items-center justify-between border-b border-white/[0.08] px-4 py-3">
          <figcaption className="text-xs font-semibold uppercase tracking-[0.22em] text-[#d6a84f]">
            {step.caption}
          </figcaption>
          <span className="h-2 w-2 rounded-full bg-[#8fbc8f]" aria-hidden="true" />
        </div>
      )}
      {hasPairedVisuals ? (
        <div className="relative overflow-visible lg:pb-[12%]" onMouseLeave={() => setIsPreviewHovered(false)}>
          <div className="relative z-20 aspect-[2520/1380] overflow-hidden rounded-lg border border-white/10 bg-[#0c0c0d] shadow-[0_28px_90px_rgba(0,0,0,0.42)]">
            <div className="pointer-events-none absolute inset-x-0 top-0 z-20 flex items-center justify-between bg-[#121214]/86 px-4 py-3 backdrop-blur-sm">
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-[#d6a84f]">
                {step.caption}
              </p>
              <span className="h-2 w-2 rounded-full bg-[#8fbc8f]" aria-hidden="true" />
            </div>
            {step.visuals.map((visual, index) => (
              <Image
                key={visual}
                src={visual}
                alt={`${step.title} product screenshot ${index + 1}`}
                fill
                loading="lazy"
                sizes="(min-width: 1024px) 58vw, 100vw"
                className={`object-contain transition-opacity duration-[900ms] ease-[cubic-bezier(0.22,1,0.36,1)] ${
                  activeVisualIndex === index ? "opacity-100" : "opacity-0"
                }`}
              />
            ))}
          </div>

          <button
            type="button"
            className={`relative z-10 mx-auto mt-3 aspect-[2520/1380] w-[58%] max-w-[260px] cursor-pointer overflow-hidden rounded-lg border border-[#d6a84f]/28 bg-[#0c0c0d] shadow-[0_16px_38px_rgba(0,0,0,0.36),0_0_22px_rgba(214,168,79,0.08)] transition-[filter,opacity,box-shadow,border-color,transform] duration-[900ms] ease-[cubic-bezier(0.22,1,0.36,1)] sm:w-[48%] lg:absolute lg:left-1/2 lg:top-[88%] lg:mt-0 lg:w-[46%] lg:max-w-[520px] lg:-translate-x-1/2 lg:shadow-[0_22px_58px_rgba(0,0,0,0.4),0_0_30px_rgba(214,168,79,0.08)] xl:w-[42%] ${
              isPreviewHovered
                ? "-translate-y-1 border-[#d6a84f]/45 opacity-100 brightness-105 shadow-[0_22px_52px_rgba(0,0,0,0.42),0_0_34px_rgba(214,168,79,0.14)] lg:-translate-x-1/2 lg:-translate-y-2 lg:shadow-[0_28px_72px_rgba(0,0,0,0.46),0_0_42px_rgba(214,168,79,0.14)]"
                : "opacity-[0.9] brightness-90 lg:-translate-x-1/2"
            }`}
            aria-label={`Show ${step.title} screenshot ${previewVisualIndex + 1}`}
            onClick={() => setActiveVisualIndex(previewVisualIndex)}
            onMouseEnter={() => setIsPreviewHovered(true)}
            onFocus={() => setIsPreviewHovered(true)}
            onBlur={() => setIsPreviewHovered(false)}
          >
            <Image
              src={step.visuals[previewVisualIndex]}
              alt={`${step.title} product screenshot preview`}
              fill
              loading="lazy"
              sizes="(min-width: 1024px) 58vw, 100vw"
              className="object-contain"
            />
            <div className="pointer-events-none absolute inset-0 bg-gradient-to-b from-[#050806]/10 via-transparent to-[#050806]/30" />
          </button>
        </div>
      ) : (
        <div className="grid">
          {step.visuals.map((visual) => (
            <div key={visual} className="relative aspect-[2520/1380] bg-[#0c0c0d]">
              <Image
                src={visual}
                alt={`${step.title} product screenshot`}
                fill
                loading="lazy"
                sizes="(min-width: 1024px) 58vw, 100vw"
                className="object-contain"
              />
            </div>
          ))}
        </div>
      )}
    </figure>
  )
}
