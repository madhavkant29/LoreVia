"use client"

import { useState } from "react"

import { Reveal } from "@/components/marketing/Reveal"

const audienceTabs = {
  Authors: {
    title: "For authors who want to finish strong.",
    body:
      "Stay organized, protect your story's consistency, and write with confidence from first draft to final polish.",
    bullets: [
      "Never lose a plot thread after a major revision.",
      "Keep character facts and relationship shifts consistent.",
      "Audit continuity before beta readers find the drift.",
      "Revise with chapter-grounded answers instead of guesswork.",
    ],
    nodes: [
      { name: "Mira", role: "Ally", trait: "Strategic, observant", x: "45%", y: "20%" },
      { name: "Kael", role: "Lead", trait: "Driven, conflicted", x: "20%", y: "56%" },
      { name: "The Old Order", role: "Antagonist", trait: "Watching the harbor", x: "86%", y: "35%" },
      { name: "Elias", role: "Brother", trait: "Impulsive, loyal", x: "76%", y: "73%" },
    ],
  },
  "Beta readers": {
    title: "For beta readers who need context without spoilers.",
    body:
      "Invite collaborators into a controlled reading experience with chapter boundaries, guided prompts, and shared manuscript context that does not overshare future reveals.",
    bullets: [
      "Open reading windows at a specific chapter boundary.",
      "Collect notes and reactions without exposing future twists.",
      "Keep author context and reader context separate.",
      "Review reader feedback beside the manuscript it refers to.",
    ],
    nodes: [
      { name: "Reader view", role: "Bounded", trait: "Stops at chapter 12", x: "19%", y: "18%" },
      { name: "Prompt set", role: "Guided", trait: "Pacing, clarity, payoff", x: "65%", y: "18%" },
      { name: "Spoiler gate", role: "Protected", trait: "Blocks future facts", x: "32%", y: "62%" },
      { name: "Feedback panel", role: "Linked", trait: "Anchored to the draft", x: "72%", y: "64%" },
    ],
  },
  "Series authors": {
    title: "For series writers and worldbuilders keeping many books aligned.",
    body:
      "Track recurring cast members, lore, timeline facts, and cross-book contradictions without rebuilding the series bible by hand after every rewrite.",
    bullets: [
      "Carry canon details across books without manual re-entry.",
      "Spot continuity conflicts before they spread downstream.",
      "Track recurring relationship arcs and timeline references.",
      "Keep high-volume projects readable as the series expands.",
    ],
    nodes: [
      { name: "Book I", role: "Origin", trait: "First appearance data", x: "15%", y: "22%" },
      { name: "Book II", role: "Bridge", trait: "Continuity checks", x: "46%", y: "52%" },
      { name: "Book III", role: "Current", trait: "Active revision pass", x: "73%", y: "16%" },
      { name: "Series wiki", role: "Shared", trait: "Editable canon memory", x: "74%", y: "70%" },
    ],
  },
  "Revision-focused": {
    title: "For revision-heavy writers who need the manuscript to stay legible.",
    body:
      "LoreVia is strongest when scenes move, reveals change, and continuity debt starts to accumulate faster than memory can keep up.",
    bullets: [
      "Run continuity scans after structural edits.",
      "Check who knows what before moving reveals.",
      "Find broken timeline gaps and dropped callbacks.",
      "Keep draft history and exports in the same workspace.",
    ],
    nodes: [
      { name: "Continuity", role: "92%", trait: "Tracked revision score", x: "18%", y: "18%" },
      { name: "Timeline gap", role: "Flagged", trait: "Between ch. 9 and 10", x: "70%", y: "18%" },
      { name: "Advisor", role: "Grounded", trait: "Answers from the text", x: "28%", y: "64%" },
      { name: "Snapshots", role: "Versioned", trait: "Restore past passes", x: "72%", y: "66%" },
    ],
  },
} as const

export function AudienceSection() {
  const [activeAudience, setActiveAudience] = useState<keyof typeof audienceTabs>("Authors")
  const active = audienceTabs[activeAudience]

  return (
    <section id="audiences" className="mx-auto max-w-7xl px-5 py-20 md:px-8">
      <div className="rounded-lg border border-white/[0.08] bg-[#0d1715] p-6 md:p-8">
        <div className="border-b border-white/[0.08] pb-6">
          <p className="text-3xs font-semibold uppercase tracking-[0.32em] text-[#6fae9f]">
            Built for every kind of author
          </p>
          <div className="mt-5 flex flex-wrap gap-3">
            {(Object.keys(audienceTabs) as Array<keyof typeof audienceTabs>).map((tab) => (
              <button
                key={tab}
                type="button"
                onClick={() => setActiveAudience(tab)}
                className={`inline-flex items-center rounded-md border px-4 py-2 text-sm font-semibold transition ${
                  activeAudience === tab
                    ? "border-[#276a63] bg-[#11312d] text-[#86decd]"
                    : "border-white/10 bg-white/5 text-[#c9d1cb] hover:border-white/20 hover:bg-white/[0.08] hover:text-white"
                }`}
              >
                {tab}
              </button>
            ))}
          </div>
        </div>

        <div className="grid gap-8 pt-7 lg:grid-cols-[0.84fr_1.16fr]">
          <Reveal>
            <div>
              <h2 className="max-w-xl font-display text-4xl font-semibold leading-[1.02] text-white md:text-5xl">
                {active.title}
              </h2>
              <p className="mt-5 max-w-xl text-lg leading-8 text-[#aeb9b3]">{active.body}</p>
              <div className="mt-8 space-y-3">
                {active.bullets.map((item) => (
                  <div key={item} className="flex items-start gap-3">
                    <span className="mt-1.5 h-2.5 w-2.5 rounded-full bg-[#55b8a5]" />
                    <p className="text-base leading-7 text-[#d9e0db]">{item}</p>
                  </div>
                ))}
              </div>
            </div>
          </Reveal>

          <Reveal delay={90}>
            <div className="relative min-h-[420px] overflow-hidden rounded-lg border border-white/10 bg-[#0d1715] p-6 xl:min-h-[360px]">
              <div className="absolute inset-x-12 top-14 h-px border-t border-dashed border-[#20443f]" />
              <div className="absolute left-1/2 top-16 h-[58%] w-px -translate-x-1/2 border-l border-dashed border-[#20443f]" />
              <div className="absolute inset-x-16 bottom-24 h-px border-t border-dashed border-[#20443f]" />

              {active.nodes.map((node) => (
                <article
                  key={node.name}
                  className="absolute w-[min(10.75rem,calc(100%-2rem))] rounded-md border border-white/[0.08] bg-[#111d1a] p-4 xl:w-[min(11.5rem,calc(100%-2rem))]"
                  style={{ left: node.x, top: node.y, transform: "translate(-50%, -50%)" }}
                >
                  <p className="text-sm font-semibold text-white">{node.name}</p>
                  <p className="mt-1 text-xs uppercase tracking-[0.18em] text-[#73c6b4]">{node.role}</p>
                  <p className="mt-3 text-sm leading-6 text-[#9fb0a8]">{node.trait}</p>
                </article>
              ))}
            </div>
          </Reveal>
        </div>
      </div>
    </section>
  )
}
