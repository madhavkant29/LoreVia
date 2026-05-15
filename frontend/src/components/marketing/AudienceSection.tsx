"use client"

import { useState } from "react"
import { Reveal } from "@/components/marketing/Reveal"

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
  Collaboration: [
    "Invite-only beta reading windows",
    "Read-only manuscript access for feedback partners",
    "Guided questions, comments, and reactions for draft review",
    "Spoiler-bounded reading context for collaborators",
    "Author-controlled collaboration without exposing drafting tools",
  ],
} as const

function Section({
  id,
  children,
  className = "",
}: {
  id?: string
  children: React.ReactNode
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
}: {
  title: string
  body?: string
}) {
  return (
    <div className="max-w-3xl">
      <h2 className="font-display text-4xl font-semibold leading-[1.02] text-white md:text-6xl">{title}</h2>
      {body ? <p className="mt-5 text-base leading-8 text-slate-400 md:text-lg">{body}</p> : null}
    </div>
  )
}

export function AudienceSection() {
  const [activeAudience, setActiveAudience] = useState<keyof typeof audienceTabs>("Authors")
  const items = audienceTabs[activeAudience]

  return (
    <Section id="audiences">
      <div className="grid gap-10 lg:grid-cols-[0.8fr_1.2fr] lg:items-start">
        <Reveal>
          <div>
            <SectionHeader
              title="Built for authors first, flexible for the rest of the story team."
              body="LoreVia is positioned around author workflows: drafting, revision, continuity, and story memory. Collaboration features exist to support beta reading, review, and manuscript feedback without turning the product into a separate reader app."
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
          <div className="relative isolate overflow-hidden rounded-2xl border border-white/10 bg-[#080d18] p-6 md:p-8">
            <div className="pointer-events-none absolute inset-y-0 right-0 z-0 hidden w-[46%] bg-[radial-gradient(circle_at_center,rgba(125,211,252,0.12),transparent_55%)] lg:block" />
            <div className="relative z-10 grid gap-10 lg:grid-cols-[1fr_0.85fr] lg:gap-8">
              <div>
                <p className="text-sm font-semibold uppercase tracking-[0.2em] text-cyan-300">{activeAudience}</p>
                <h3 className="mt-4 text-3xl font-semibold text-white">Concrete manuscript tools, not vague writing magic.</h3>
                <div className="mt-7 space-y-4">
                  {items.map((item) => (
                    <div key={item} className="flex gap-4 rounded-xl border border-white/10 bg-white/[0.03] p-4">
                      <span className="mt-1 h-2 w-2 rounded-full bg-cyan-300" />
                      <p className="text-sm leading-6 text-slate-200">{item}</p>
                    </div>
                  ))}
                </div>
              </div>

              <div className="relative mx-auto min-h-[220px] w-full max-w-[280px] overflow-hidden rounded-2xl bg-[linear-gradient(180deg,rgba(125,211,252,0.04),transparent)] lg:min-h-[320px] lg:max-w-none lg:bg-transparent">
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
