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
  "Series Authors": [
    "Cross-book continuity checks for recurring casts and lore",
    "Timeline recall that follows reveals across volumes",
    "Relationship tracking that survives major revisions",
    "Story-bible support grounded in the manuscript, not memory",
    "Multi-book scans before contradictions spread downstream",
  ],
  Collaborators: [
    "Invite-only beta reading windows",
    "Author-scoped access for beta readers and editors",
    "Guided questions, comments, and reactions for draft review",
    "Spoiler-bounded reading context for collaborators",
    "Author-controlled collaboration without turning LoreVia into a public reader app",
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
      <h2 className="font-display text-4xl font-semibold leading-[1.04] text-stone-950 md:text-5xl">{title}</h2>
      {body ? <p className="mt-5 text-base leading-8 text-stone-600 md:text-lg">{body}</p> : null}
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
              body="LoreVia stays centered on drafting, revision, continuity, and story memory. Collaboration exists to support author work, not distract from it."
            />
            <div className="mt-8 inline-flex rounded-full border border-[rgba(var(--border),0.9)] bg-[rgba(255,252,247,0.9)] p-1">
              {(Object.keys(audienceTabs) as Array<keyof typeof audienceTabs>).map((tab) => (
                <button
                  key={tab}
                  type="button"
                  onClick={() => setActiveAudience(tab)}
                  className={`rounded px-4 py-2 text-sm font-semibold transition ${
                    activeAudience === tab ? "bg-teal-800 text-white" : "text-stone-500 hover:text-stone-950"
                  }`}
                >
                  {tab}
                </button>
              ))}
            </div>
          </div>
        </Reveal>

        <Reveal delay={100}>
          <div className="relative isolate overflow-hidden rounded-[1.5rem] border border-[rgba(var(--border),0.9)] bg-[rgba(255,252,247,0.95)] p-6 md:p-8">
            <div className="relative z-10 grid gap-10 lg:grid-cols-[1fr_0.85fr] lg:gap-8">
              <div>
                <p className="text-sm font-semibold uppercase tracking-[0.2em] text-teal-800">{activeAudience}</p>
                <h3 className="mt-4 font-display text-3xl font-semibold text-stone-950">Concrete manuscript tools, not vague writing magic.</h3>
                <div className="mt-7 space-y-4">
                  {items.map((item) => (
                    <div key={item} className="flex gap-4 rounded-[1rem] border border-[rgba(var(--border),0.9)] bg-white p-4">
                      <span className="mt-1 h-2 w-2 rounded-full bg-teal-800" />
                      <p className="text-sm leading-6 text-stone-700">{item}</p>
                    </div>
                  ))}
                </div>
              </div>

              <div className="relative mx-auto min-h-[220px] w-full max-w-[280px] overflow-hidden rounded-[1.4rem] bg-[rgba(var(--muted),0.35)] lg:min-h-[320px] lg:max-w-none">
                <svg viewBox="0 0 320 320" className="h-full w-full text-teal-800/55" aria-hidden>
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
                      <circle cx={cx as number} cy={cy as number} r="26" fill="#fffaf4" stroke="rgba(33,97,94,0.35)" />
                      <text x={cx as number} y={(cy as number) + 4} textAnchor="middle" fill="#3b3a36" fontSize="12">
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
