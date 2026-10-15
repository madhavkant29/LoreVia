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
  visual: string
  proofPoints: string[]
}

const showcaseSteps: ShowcaseStep[] = [
  {
    id: "evidence",
    title: "See the conflict beside the manuscript",
    body: "LoreVia finds timeline, character, and story-logic conflicts, then keeps the relevant chapter evidence next to the finding.",
    detail: "You can judge the actual passage before deciding whether the issue needs a rewrite, a clarification, or no change at all.",
    caption: "Manuscript finding with cited context",
    visual: "/landing/manuscript-analysis-with-advisor.webp",
    proofPoints: [
      "Chapter-linked evidence",
      "Continuity and timeline findings",
      "Grounded answers about the draft",
    ],
  },
  {
    id: "memory",
    title: "Follow what changed, who knows it, and when",
    body: "Character profiles connect aliases, relationships, knowledge, appearances, and continuity warnings across the draft.",
    detail: "Instead of another disconnected summary, the story bible becomes an editable record you can check while revising later chapters.",
    caption: "Selected character with continuity evidence",
    visual: "/landing/character-continuity.webp",
    proofPoints: [
      "Editable story memory",
      "Alias and duplicate review",
      "Relationship and knowledge history",
    ],
  },
  {
    id: "revision",
    title: "Turn a finding into a revision decision",
    body: "Review issues by category, compare them with the manuscript, and keep only the changes that strengthen the story.",
    detail: "The workflow stays focused on evidence, severity, and the next editorial action—not generating replacement prose or filling a dashboard with scores.",
    caption: "Evidence-to-decision review",
    visual: "/landing/editorial-review-2.webp",
    proofPoints: [
      "Specific revision targets",
      "Accept, dismiss, or revisit",
      "Author-controlled decisions",
    ],
  },
]

export function LandingShowcase() {
  const [activeStepId, setActiveStepId] = useState(showcaseSteps[0].id)
  const stepRefs = useRef<Record<string, HTMLElement | null>>({})

  useEffect(() => {
    if (typeof window === "undefined" || !("IntersectionObserver" in window)) return

    const observer = new IntersectionObserver(
      (entries) => {
        const visibleEntry = entries
          .filter((entry) => entry.isIntersecting)
          .sort((left, right) => right.intersectionRatio - left.intersectionRatio)[0]

        if (visibleEntry?.target instanceof HTMLElement) {
          setActiveStepId(visibleEntry.target.dataset.showcaseStep ?? showcaseSteps[0].id)
        }
      },
      { rootMargin: "-18% 0px -42% 0px", threshold: [0.2, 0.45, 0.7] },
    )

    for (const step of showcaseSteps) {
      const element = stepRefs.current[step.id]
      if (element) observer.observe(element)
    }

    return () => observer.disconnect()
  }, [])

  const activeStep = showcaseSteps.find((step) => step.id === activeStepId) ?? showcaseSteps[0]

  return (
    <section id="features" className="mx-auto max-w-[1500px] px-5 py-20 md:px-8">
      <span id="sample-finding" className="block scroll-mt-24" aria-hidden="true" />
      <div className="max-w-3xl border-l border-[#d6a84f]/45 pl-5">
        <p className="text-sm font-semibold text-[#d6a84f]">Three proof points</p>
        <h2 className="mt-4 font-display text-4xl font-semibold leading-[1.02] text-[#f4f1ea] md:text-5xl">
          From manuscript evidence to a revision decision.
        </h2>
        <p className="mt-5 text-lg leading-8 text-[#a09a90]">
          LoreVia connects a finding to the story memory behind it and the passage you can actually revise.
        </p>
      </div>

      <div className="mt-14 grid gap-10 lg:grid-cols-[minmax(0,1.2fr)_minmax(360px,0.8fr)] lg:gap-14 2xl:grid-cols-[minmax(720px,1.3fr)_minmax(440px,0.7fr)]">
        <div className="hidden lg:block">
          <div className="sticky top-24">
            <ProductFrame step={activeStep} />
          </div>
        </div>

        <div>
          {showcaseSteps.map((step, index) => (
            <article
              key={step.id}
              ref={(element) => {
                stepRefs.current[step.id] = element
              }}
              data-showcase-step={step.id}
              className="border-t border-white/[0.1] py-10 lg:min-h-[62vh] lg:py-16"
            >
              <div className="mb-7 lg:hidden">
                <ProductFrame step={step} />
              </div>
              <p className="text-sm font-semibold text-[#d6a84f]">0{index + 1} · {step.caption}</p>
              <h3 className="mt-4 font-display text-3xl font-semibold leading-tight text-[#f4f1ea] md:text-4xl">
                {step.title}
              </h3>
              <p className="mt-5 max-w-2xl text-lg leading-8 text-[#a09a90]">{step.body}</p>
              <p className="mt-4 max-w-2xl text-base leading-7 text-[#bcb6ab]">{step.detail}</p>
              <ul className="mt-7 divide-y divide-white/[0.08] border-y border-white/[0.08]">
                {step.proofPoints.map((point) => (
                  <li key={point} className="flex items-center gap-3 py-3 text-sm font-medium text-[#f4f1ea]">
                    <span className="text-[#86decd]" aria-hidden="true">✓</span>
                    {point}
                  </li>
                ))}
              </ul>
            </article>
          ))}
        </div>
      </div>
    </section>
  )
}

function ProductFrame({ step }: { step: ShowcaseStep }) {
  return (
    <figure className="overflow-hidden border border-white/10 bg-[#121214] shadow-[0_22px_65px_rgba(0,0,0,0.3)]">
      <figcaption className="flex items-center justify-between border-b border-white/[0.08] px-4 py-3 text-sm font-medium text-[#d6a84f]">
        {step.caption}
        <span className="text-xs font-normal text-[#8f9993]">Product view</span>
      </figcaption>
      <div className="relative aspect-video bg-[#0c0c0d]">
        <Image
          src={step.visual}
          alt={`${step.title} product screenshot`}
          fill
          loading="lazy"
          sizes="(min-width: 1024px) 58vw, 100vw"
          className="object-contain"
        />
      </div>
    </figure>
  )
}
