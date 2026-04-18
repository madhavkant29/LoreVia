"use client"

import Link from "next/link"
import { useMemo, useState } from "react"
import { useAuthStore } from "@/lib/stores/authStore"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"

type BillingCycle = "monthly" | "yearly"

const productPillars = [
  {
    title: "Character Engine",
    label: "Micro view",
    body: "Track who people are, how they change, which roles they play, and how their motives evolve as the story unfolds.",
  },
  {
    title: "Event / Plot Tracker",
    label: "Meso view",
    body: "Follow turning points, unresolved threads, foreshadowing signals, and relationship shifts without losing your place.",
  },
  {
    title: "Thematic / Cross-Book Analysis",
    label: "Macro view",
    body: "Surface recurring ideas, patterns, and continuity across long books and eventually across entire series.",
  },
]

const features = [
  ["Spoiler-aware summaries", "Recaps stay aligned with your read progress instead of exposing future chapters."],
  ["Smart character cards", "Profiles merge aliases, motivations, roles, and evolving traits into one cleaner view."],
  ["Relationship graph", "Explore who is tied to whom with guardrails before graph-heavy spoiler surfaces open."],
  ["Foreshadowing highlights", "Spot early clues and signals that gain significance within your current reading window."],
  ["Timeline view", "Review major events, entrances, and plot movement chapter by chapter."],
  ["Thematic search", "Search for motifs, tensions, or patterns, not just exact words."],
  ["Grounded Q&A", "Ask the book questions and get answers based only on what the text has already revealed."],
  ["Saved quotes", "Keep important passages with book, chapter, and optional character context attached."],
]

const differentiators = [
  {
    title: "Built for narrative continuity",
    body: "LoreVia thinks in chapters, characters, arcs, and read progress instead of treating books like flat files.",
  },
  {
    title: "Spoiler-safe by product design",
    body: "Summaries, recall, and relationship tools are shaped around the reader's progress from the start.",
  },
  {
    title: "A reading workspace, not a file wrapper",
    body: "Upload, organize, search, revisit, quote, and reason across the book from one structured environment.",
  },
]

const plans = [
  {
    name: "Starter",
    monthly: "$0",
    yearly: "$0",
    note: "for exploration",
    highlight: "Available now",
    bullets: ["Core spoiler-safe reading workspace", "Chapter memory and smart retrieval", "A polished first step into LoreVia"],
  },
  {
    name: "Pro",
    monthly: "$9",
    yearly: "$90",
    note: "for serious readers",
    highlight: "Coming next",
    bullets: ["Higher search and summary limits", "Expanded reading workspace", "Richer continuity across longer books"],
  },
  {
    name: "Power",
    monthly: "$17",
    yearly: "$170",
    note: "for dense books and long libraries",
    highlight: "Coming next",
    bullets: ["Highest rate limits", "Maximum continuity headroom", "Best fit for classics, series, and rereads"],
  },
]

const faqs = [
  ["What makes LoreVia different?", "LoreVia is built around spoiler-safe reading continuity. It treats books as evolving worlds, not static files to summarize."],
  ["Does it replace reading?", "No. It supports reading by helping you recover context, track people and events, and return to the exact thread you were following."],
  ["Who is it best for?", "Readers of dense fiction, classics, fantasy series, and long-form narrative nonfiction benefit the most."],
  ["Why are paid plans marked coming soon?", "The premium tiers are being opened carefully with higher rate limits, cleaner controls, and a more deliberate rollout."],
]

const workflow = [
  ["Upload the book", "Bring in a PDF or EPUB and turn it into a structured reading workspace."],
  ["Read with context", "Track characters, summaries, events, and recall without losing your place."],
  ["Explore what matters", "Use timelines, thematic search, grounded Q&A, and saved quotes to revisit the book intelligently."],
]

const compareRows = [
  ["Spoiler-aware by chapter progress", "Yes", "No", "No"],
  ["Character memory and relationship recall", "Yes", "Limited", "No"],
  ["Grounded Q&A over the book", "Yes", "No", "Partial"],
  ["Series-level continuity direction", "Planned", "No", "No"],
  ["Reading workspace instead of only highlights", "Yes", "Partial", "No"],
]

export default function HomePage() {
  const user = useAuthStore((state) => state.user)
  const { theme } = usePreferencesStore()
  const isDark = theme === "dark"
  const [billingCycle, setBillingCycle] = useState<BillingCycle>("monthly")
  const [audienceTab, setAudienceTab] = useState<"readers" | "authors">("readers")
  const pricingHref = useMemo(() => (user ? "/pricing" : "#pricing"), [user])

  return (
    <main
      className={`min-h-screen transition-colors ${
        isDark
          ? "bg-[linear-gradient(180deg,#06101f_0%,#09162a_42%,#0d1d38_100%)] text-slate-100"
          : "bg-[linear-gradient(180deg,#fbf7ef_0%,#f7f2eb_48%,#f3efe9_100%)] text-stone-950"
      }`}
    >
      <section className="relative flex min-h-screen items-center justify-center overflow-hidden px-6 py-16 lg:px-10">
        <div
          className={`absolute inset-0 ${
            isDark
              ? "bg-[radial-gradient(circle_at_center,rgba(76,114,255,0.16),transparent_18%),radial-gradient(circle_at_center,rgba(56,89,194,0.12),transparent_34%)]"
              : "bg-[radial-gradient(circle_at_center,rgba(193,186,255,0.16),transparent_18%),radial-gradient(circle_at_center,rgba(214,206,255,0.1),transparent_34%)]"
          }`}
        />

        <div className="relative z-10 mx-auto flex w-full max-w-6xl flex-col items-center justify-center text-center">
          <div
            className={`mb-10 flex h-24 w-24 items-center justify-center rounded-[2rem] border shadow-[0_22px_50px_-30px_rgba(79,70,229,0.35)] md:h-24 md:w-24 ${
              isDark ? "border-white/10 bg-white/6 text-indigo-200" : "border-white/80 bg-white/92 text-[rgb(71,56,230)]"
            }`}
          >
            <span className="text-4xl">▦</span>
          </div>

          <h1 className={`font-serif text-[4.9rem] leading-none tracking-[-0.04em] sm:text-[6.5rem] md:text-[7rem] ${isDark ? "text-white" : "text-stone-950"}`}>
            LoreVia
          </h1>
          <p className={`mt-9 max-w-2xl font-serif text-[2.1rem] leading-[1.2] tracking-[-0.02em] sm:text-[2.4rem] md:text-[2.6rem] ${isDark ? "text-slate-200" : "text-stone-800"}`}>
            Never lose the thread.
          </p>
          <p className={`mt-5 max-w-3xl text-base leading-8 sm:text-lg ${isDark ? "text-slate-300" : "text-stone-600"}`}>
            LoreVia extracts every character, relationship, and plot thread from your novel. Tap any name while reading. Track every arc while writing.
          </p>

          <div className={`mt-9 max-w-4xl text-center text-[0.86rem] font-medium uppercase tracking-[0.34em] sm:text-[0.92rem] ${isDark ? "text-slate-400" : "text-stone-400"}`}>
            <span>Characters.</span>{" "}
            <span>Relationships.</span>{" "}
            <span>Plot Threads.</span>{" "}
            <span>Memory.</span>{" "}
            <span>On Demand.</span>
          </div>

          <div className="mt-12 flex w-full max-w-md flex-col gap-4 sm:max-w-none sm:flex-row sm:items-center sm:justify-center">
            <Link
              href={user ? "/library" : "/register"}
              className="inline-flex min-w-[220px] items-center justify-center rounded-2xl bg-[linear-gradient(135deg,#4f46e5,#4338ca)] px-8 py-4 text-lg font-semibold text-white shadow-[0_20px_38px_-22px_rgba(79,70,229,0.65)] transition hover:brightness-105"
            >
              {user ? "Open app" : "Get started free"}
            </Link>
            <Link
              href={user ? "/library" : "/login"}
              className={`inline-flex min-w-[170px] items-center justify-center rounded-2xl px-8 py-4 text-lg font-semibold transition ${
                isDark ? "border border-white/10 bg-white/6 text-white hover:bg-white/10" : "bg-white/95 text-stone-800 hover:bg-white"
              }`}
            >
              Sign in
            </Link>
          </div>

          <div className={`mt-28 flex flex-col items-center gap-5 md:mt-24 ${isDark ? "text-slate-500" : "text-stone-400"}`}>
            <p className="text-[0.92rem] font-medium uppercase tracking-[0.4em]">Designed for the digital curator</p>
            <div className="h-14 w-px bg-[linear-gradient(180deg,rgba(99,102,241,0.7),rgba(99,102,241,0))]" />
            <p className="text-[0.78rem] font-medium uppercase tracking-[0.36em]">Scroll to explore</p>
          </div>
        </div>
      </section>

      <Section className="pt-4">
        <div className="grid gap-14 lg:grid-cols-[1.02fr_0.98fr] lg:items-center">
          <div className="max-w-3xl">
            <p className={`text-xs font-semibold uppercase tracking-[0.34em] ${isDark ? "text-sky-300" : "text-sky-800"}`}>The intelligence layer for long-form fiction</p>
            <h2 className={`mt-6 font-serif text-[3.15rem] leading-[0.98] sm:text-5xl md:text-[5rem] ${isDark ? "text-white" : "text-stone-950"}`}>
              Stay with the story.
              <br />
              Keep every thread.
            </h2>
            <p className={`mt-7 max-w-2xl text-lg leading-8 ${isDark ? "text-slate-300" : "text-stone-600"}`}>
              For readers who get lost. For authors who need to remember. LoreVia turns a single upload into a navigable continuity layer: characters, relationships, arcs, and plot threads — always anchored to the text.
            </p>

            <div className="mt-8 flex flex-wrap gap-4">
              <Link href={user ? "/library" : "/register"} className={`rounded-full px-7 py-3.5 text-sm font-semibold transition ${isDark ? "bg-white text-slate-950 hover:bg-slate-100" : "bg-stone-950 text-white hover:bg-stone-800"}`}>
                {user ? "Open your library" : "Create your workspace"}
              </Link>
              <Link href={pricingHref} className={`rounded-full border px-7 py-3.5 text-sm font-semibold transition ${isDark ? "border-white/10 bg-white/5 text-slate-200 hover:bg-white/10" : "border-stone-300 bg-white text-stone-700 hover:bg-stone-50"}`}>
                View pricing
              </Link>
            </div>

            <div className={`mt-10 overflow-hidden rounded-[2rem] border shadow-[0_28px_80px_-60px_rgba(79,70,229,0.28)] ${isDark ? "border-white/10 bg-white/5" : "border-white/80 bg-white/92"}`}>
              <div className={`flex items-center gap-2 p-2 ${isDark ? "bg-white/[0.04]" : "bg-stone-50"}`}>
                <button
                  onClick={() => setAudienceTab("readers")}
                  className={`flex-1 rounded-[1.2rem] px-5 py-3 text-left text-sm font-semibold transition ${
                    audienceTab === "readers"
                      ? isDark ? "bg-white text-slate-950" : "bg-white text-stone-950 shadow-sm"
                      : isDark ? "text-slate-300 hover:bg-white/10" : "text-stone-600 hover:bg-white"
                  }`}
                >
                  For Readers
                </button>
                <button
                  onClick={() => setAudienceTab("authors")}
                  className={`flex-1 rounded-[1.2rem] px-5 py-3 text-left text-sm font-semibold transition ${
                    audienceTab === "authors"
                      ? isDark ? "bg-white text-slate-950" : "bg-white text-stone-950 shadow-sm"
                      : isDark ? "text-slate-300 hover:bg-white/10" : "text-stone-600 hover:bg-white"
                  }`}
                >
                  For Authors
                </button>
              </div>
              <div className="p-7">
                {audienceTab === "readers" ? (
                  <>
                    <p className={`text-xs font-semibold uppercase tracking-[0.28em] ${isDark ? "text-indigo-300" : "text-violet-600"}`}>Reader workflow</p>
                    <h3 className={`mt-4 font-serif text-3xl leading-tight ${isDark ? "text-white" : "text-stone-950"}`}>Tap any name. Recover context instantly.</h3>
                    <p className={`mt-4 text-base leading-8 ${isDark ? "text-slate-300" : "text-stone-600"}`}>
                      Smart character cards, spoiler-aware summaries, relationship recall, and grounded Q&A — all constrained to what you’ve actually read.
                    </p>
                    <div className="mt-5 grid gap-3 sm:grid-cols-2">
                      {[
                        ["Smart Tap", "Open character profiles directly from the page without breaking flow."],
                        ["Spoiler-safe profiles", "Descriptions adapt to your reading progress, not the full book."],
                        ["Memory recall", "Return to the exact thread you were following — fast."],
                        ["Relationship guardrails", "Explore connections without stepping into future chapters."],
                      ].map(([title, body]) => (
                        <div key={title} className={`rounded-[1.4rem] border p-4 ${isDark ? "border-white/10 bg-white/[0.04]" : "border-stone-200/80 bg-stone-50"}`}>
                          <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>{title}</p>
                          <p className={`mt-2 text-sm leading-7 ${isDark ? "text-slate-300" : "text-stone-600"}`}>{body}</p>
                        </div>
                      ))}
                    </div>
                  </>
                ) : (
                  <>
                    <p className={`text-xs font-semibold uppercase tracking-[0.28em] ${isDark ? "text-indigo-300" : "text-violet-600"}`}>Author workflow</p>
                    <h3 className={`mt-4 font-serif text-3xl leading-tight ${isDark ? "text-white" : "text-stone-950"}`}>Upload one EPUB. Get your story’s continuity map.</h3>
                    <p className={`mt-4 text-base leading-8 ${isDark ? "text-slate-300" : "text-stone-600"}`}>
                      LoreVia is a companion tool: character bible, relationship map, and plot thread tracking — built from your own manuscript export.
                    </p>
                    <div className="mt-5 grid gap-3 sm:grid-cols-2">
                      {[
                        ["Character bible export", "Download a clean reference document (Markdown today; PDF can follow)."],
                        ["Relationship map", "See connections and shifts without scanning dozens of chapters."],
                        ["Plot threads", "Track unresolved threads and turning points across the series."],
                        ["Continuity support", "Coming next: flag contradictions before you publish a new chapter."],
                      ].map(([title, body]) => (
                        <div key={title} className={`rounded-[1.4rem] border p-4 ${isDark ? "border-white/10 bg-white/[0.04]" : "border-stone-200/80 bg-stone-50"}`}>
                          <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>{title}</p>
                          <p className={`mt-2 text-sm leading-7 ${isDark ? "text-slate-300" : "text-stone-600"}`}>{body}</p>
                        </div>
                      ))}
                    </div>
                  </>
                )}
              </div>
            </div>
          </div>

          <div className={`rounded-[2.6rem] border p-5 shadow-[0_44px_140px_-60px_rgba(15,23,42,0.24)] ${isDark ? "border-white/10 bg-[#0c1830]" : "border-white/80 bg-[linear-gradient(165deg,rgba(255,255,255,0.96),rgba(243,246,255,0.96)_55%,rgba(255,246,235,0.98))]"}`}>
            <div className="overflow-hidden rounded-[2rem] bg-[radial-gradient(circle_at_top_left,rgba(59,130,246,0.18),transparent_28%),radial-gradient(circle_at_92%_8%,rgba(250,204,21,0.2),transparent_24%),linear-gradient(180deg,#0f172a,#111827_55%,#172133)] p-6 text-white lg:p-7">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-[0.28em] text-slate-300">Reader console</p>
                  <h2 className="mt-3 font-serif text-3xl leading-tight">A book becomes an explorable memory layer.</h2>
                </div>
                <div className="rounded-full border border-white/10 bg-white/6 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.22em] text-amber-200">
                  Progress-aware
                </div>
              </div>

              <div className="mt-7 grid gap-3 sm:grid-cols-2">
                {productPillars.map((item) => (
                  <div key={item.title} className="rounded-[1.4rem] border border-white/10 bg-white/6 p-4">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-amber-200">{item.label}</p>
                    <p className="mt-2 text-sm font-semibold text-white">{item.title}</p>
                    <p className="mt-2 text-sm leading-6 text-slate-300">{item.body}</p>
                  </div>
                ))}
                <div className="rounded-[1.4rem] border border-white/10 bg-[linear-gradient(180deg,rgba(255,255,255,0.08),rgba(255,255,255,0.03))] p-4">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-400">Live reading state</p>
                  <div className="mt-4 space-y-3">
                    <div className="rounded-2xl bg-white/7 p-3">
                      <p className="text-xs text-slate-400">Current chapter</p>
                      <p className="mt-1 text-sm font-medium text-white">Context stays aligned with what you already know.</p>
                    </div>
                    <div className="rounded-2xl bg-white/7 p-3">
                      <p className="text-xs text-slate-400">Character continuity</p>
                      <p className="mt-1 text-sm font-medium text-white">Aliases, motives, and relationships stay gathered instead of scattered.</p>
                    </div>
                    <div className="rounded-2xl bg-white/7 p-3">
                      <p className="text-xs text-slate-400">Recall</p>
                      <p className="mt-1 text-sm font-medium text-white">Return to the thread you were following without re-reading half the book.</p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </Section>

      <Section className="py-8">
        <div className={`rounded-full border px-6 py-4 ${isDark ? "border-white/10 bg-white/5" : "border-white/80 bg-white/72"}`}>
          <div className={`mx-auto flex max-w-7xl flex-wrap items-center justify-center gap-x-10 gap-y-3 text-sm font-medium uppercase tracking-[0.18em] ${isDark ? "text-slate-400" : "text-stone-500"}`}>
            <span>Built for dense reading</span>
            <span>Continuity first</span>
            <span>Spoiler-aware</span>
            <span>Long-form narrative intelligence</span>
          </div>
        </div>
      </Section>

      <Section id="difference">
        <SectionHeader eyebrow="Why LoreVia" title="Not generic AI over documents. A system built for reading continuity." body="" isDark={isDark} />
        <div className="mt-12 grid gap-6 md:grid-cols-3">
          {differentiators.map((item) => (
            <article key={item.title} className={`rounded-[2rem] border p-7 ${isDark ? "border-white/10 bg-white/5" : "border-white/80 bg-white/88"}`}>
              <h3 className={`text-xl font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>{item.title}</h3>
              <p className={`mt-4 text-base leading-7 ${isDark ? "text-slate-300" : "text-stone-600"}`}>{item.body}</p>
            </article>
          ))}
        </div>
      </Section>

      <Section id="features">
        <SectionHeader eyebrow="Features" title="Every tool is tied to a real reading job." body="Each feature is there to reduce rereading friction, improve comprehension, and keep readers oriented inside long books." isDark={isDark} />
        <div className="mt-12 grid gap-5 md:grid-cols-2 xl:grid-cols-4">
          {features.map(([title, body]) => (
            <article key={title} className={`rounded-[1.8rem] border p-6 ${isDark ? "border-white/10 bg-white/5" : "border-white/80 bg-white/90"}`}>
              <h3 className={`text-lg font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>{title}</h3>
              <p className={`mt-3 text-sm leading-7 ${isDark ? "text-slate-300" : "text-stone-600"}`}>{body}</p>
            </article>
          ))}
        </div>
      </Section>

      <Section id="workflow">
        <SectionHeader eyebrow="Workflow" title="A cleaner path from raw book file to usable reading memory." body="" isDark={isDark} />
        <div className="mt-12 grid gap-5 md:grid-cols-3">
          {workflow.map(([title, body], index) => (
            <article key={title} className={`rounded-[1.9rem] border p-7 ${isDark ? "border-white/10 bg-white/5" : "border-white/80 bg-white/92"}`}>
              <p className={`text-xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-400" : "text-stone-500"}`}>Step {index + 1}</p>
              <h3 className={`mt-4 text-2xl font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>{title}</h3>
              <p className={`mt-4 text-base leading-7 ${isDark ? "text-slate-300" : "text-stone-600"}`}>{body}</p>
            </article>
          ))}
        </div>
      </Section>

      <Section id="pricing">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <SectionHeader eyebrow="Pricing" title="Start free now. Premium tiers are being opened carefully." body="Starter is available today. Pro and Power are being staged with higher rate limits, cleaner controls, and a calmer rollout." isDark={isDark} />
          <div className={`inline-flex rounded-full p-1 ${isDark ? "border border-white/10 bg-white/5" : "border border-stone-200 bg-stone-100"}`}>
            {(["monthly", "yearly"] as BillingCycle[]).map((cycle) => (
              <button
                key={cycle}
                onClick={() => setBillingCycle(cycle)}
                className={`rounded-full px-4 py-2 text-sm font-medium transition ${
                  billingCycle === cycle
                    ? isDark ? "bg-white text-slate-950" : "bg-white text-stone-950 shadow-sm"
                    : isDark ? "text-slate-300" : "text-stone-600"
                }`}
              >
                {cycle === "monthly" ? "Monthly" : "Yearly"}
              </button>
            ))}
          </div>
        </div>

        <div className={`mt-12 rounded-[2.5rem] border p-6 lg:p-8 ${isDark ? "border-white/10 bg-[#09172d]" : "border-white/80 bg-[linear-gradient(180deg,rgba(255,255,255,0.95),rgba(247,248,250,0.95))]"}`}>
          <div className="grid gap-5 lg:grid-cols-3">
            {plans.map((plan) => {
              const selectedPrice = billingCycle === "yearly" ? plan.yearly : plan.monthly
              return (
                <article key={plan.name} className={`rounded-[2rem] border p-6 ${isDark ? "border-white/10 bg-white/5" : "border-stone-200 bg-white/95"}`}>
                  <p className={`text-xs font-semibold uppercase tracking-[0.22em] ${isDark ? "text-indigo-300" : "text-violet-600"}`}>{plan.highlight}</p>
                  <div className="mt-4 flex items-end gap-3">
                    <h3 className={`font-serif text-4xl ${isDark ? "text-white" : "text-stone-950"}`}>{plan.name}</h3>
                    <p className={isDark ? "pb-1 text-sm text-slate-400" : "pb-1 text-sm text-stone-500"}>{selectedPrice}</p>
                  </div>
                  <p className={`mt-1 text-xs uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>
                    {billingCycle === "yearly" ? "per year" : "per month"} - {plan.note}
                  </p>
                  <ul className="mt-6 space-y-3">
                    {plan.bullets.map((bullet) => (
                      <li key={bullet} className={`rounded-2xl px-4 py-3 text-sm ${isDark ? "bg-white/6 text-slate-200" : "bg-stone-100 text-stone-700"}`}>
                        {bullet}
                      </li>
                    ))}
                  </ul>
                </article>
              )
            })}
          </div>
        </div>
      </Section>

      <Section id="compare">
        <div className={`rounded-[2.5rem] border p-6 shadow-[0_28px_80px_-60px_rgba(15,23,42,0.2)] lg:p-8 ${isDark ? "border-white/10 bg-[#0a1730]" : "border-white/80 bg-white/86"}`}>
          <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-3xl">
              <p className={`text-xs font-semibold uppercase tracking-[0.3em] ${isDark ? "text-indigo-300" : "text-violet-600"}`}>Compare</p>
              <h2 className={`mt-4 font-serif text-4xl leading-tight md:text-5xl ${isDark ? "text-white" : "text-stone-950"}`}>
                Where LoreVia fits against Royal Road, Kindle, and generic AI.
              </h2>
            </div>
            <div className={`flex items-center gap-3 text-sm ${isDark ? "text-slate-300" : "text-stone-600"}`}>
              <span className="text-base">≋</span>
              Built around continuity, not just file access.
            </div>
          </div>

          <div className="mt-8 overflow-hidden rounded-[1.8rem] border border-white/10">
            <div className={`grid grid-cols-[1.4fr_repeat(3,1fr)] text-sm ${isDark ? "bg-white/6 text-slate-200" : "bg-stone-100 text-stone-700"}`}>
              <div className="px-4 py-4 font-semibold">Capability</div>
              <div className="px-4 py-4 font-semibold">LoreVia</div>
              <div className="px-4 py-4 font-semibold">Royal Road</div>
              <div className="px-4 py-4 font-semibold">Generic AI</div>
            </div>
            {compareRows.map(([capability, lorevia, kindle, generic]) => (
              <div key={capability} className={`grid grid-cols-[1.4fr_repeat(3,1fr)] border-t text-sm ${isDark ? "border-white/10 bg-[#0d1d39]" : "border-stone-200 bg-white"}`}>
                <div className={`px-4 py-4 ${isDark ? "text-slate-100" : "text-stone-900"}`}>{capability}</div>
                <div className="px-4 py-4 text-emerald-600">{lorevia}</div>
                <div className={`px-4 py-4 ${isDark ? "text-slate-400" : "text-stone-500"}`}>{kindle}</div>
                <div className={`px-4 py-4 ${isDark ? "text-slate-400" : "text-stone-500"}`}>{generic}</div>
              </div>
            ))}
          </div>
        </div>
      </Section>

      <Section id="faq" className="pb-28">
        <div className="grid gap-10 lg:grid-cols-[0.92fr_1.08fr]">
          <div>
            <p className={`text-xs font-semibold uppercase tracking-[0.3em] ${isDark ? "text-sky-300" : "text-sky-800"}`}>FAQ</p>
            <h2 className={`mt-4 font-serif text-4xl leading-tight md:text-5xl ${isDark ? "text-white" : "text-stone-950"}`}>
              Questions readers usually ask before committing.
            </h2>
          </div>
          <div className="space-y-4">
            {faqs.map(([question, answer]) => (
              <article key={question} className={`rounded-[1.8rem] border p-6 ${isDark ? "border-white/10 bg-white/5" : "border-white/80 bg-white/92"}`}>
                <h3 className={`text-lg font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>{question}</h3>
                <p className={`mt-3 text-sm leading-7 ${isDark ? "text-slate-300" : "text-stone-600"}`}>{answer}</p>
              </article>
            ))}
          </div>
        </div>

        <div className={`mt-12 flex items-center justify-center gap-8 ${isDark ? "text-slate-500" : "text-stone-400"}`}>
          <span className="text-xl">▤</span>
          <span className="text-xl">▦</span>
          <span className="text-xl">✦</span>
        </div>
      </Section>
    </main>
  )
}

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
    <section id={id} className={`mx-auto max-w-7xl px-6 py-28 lg:px-10 lg:py-32 ${className}`}>
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
      <p className={`text-xs font-semibold uppercase tracking-[0.3em] ${isDark ? "text-indigo-300" : "text-violet-600"}`}>{eyebrow}</p>
      <h2 className={`mt-4 font-serif text-4xl leading-tight md:text-5xl ${isDark ? "text-white" : "text-stone-950"}`}>{title}</h2>
      {body ? <p className={`mt-5 max-w-xl text-base leading-7 ${isDark ? "text-slate-300" : "text-stone-600"}`}>{body}</p> : null}
    </div>
  )
}
