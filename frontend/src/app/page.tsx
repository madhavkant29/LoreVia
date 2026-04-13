"use client"

import Link from "next/link"
import { useMemo, useState } from "react"
import { useAuthStore } from "@/lib/stores/authStore"

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
  {
    name: "Studio",
    monthly: "$34",
    yearly: "$340",
    note: "for future advanced workflows",
    highlight: "Future tier",
    bullets: ["Editorial-grade workflows", "Cross-book intelligence systems", "Reserved for advanced premium tooling"],
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

const heroSignals = [
  "Dense fiction",
  "Classics",
  "Fantasy series",
  "Narrative nonfiction",
  "Long-form reading",
]

export default function HomePage() {
  const user = useAuthStore((state) => state.user)
  const [billingCycle, setBillingCycle] = useState<BillingCycle>("monthly")
  const primaryNav = [
    { href: "#difference", label: "Why LoreVia" },
    { href: "#features", label: "Features" },
    { href: "#workflow", label: "Workflow" },
    { href: "#pricing", label: "Pricing" },
    { href: "#faq", label: "FAQ" },
  ]

  const pricingHref = useMemo(() => (user ? "/pricing" : "#pricing"), [user])

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top,#efebe2_0%,rgba(239,235,226,0.88)_32%,rgba(244,240,234,0.98)_68%,#f7f3ed_100%)] text-slate-900">
      <section className="relative flex min-h-screen items-center justify-center overflow-hidden px-6 py-12 lg:px-10">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(193,186,255,0.22),transparent_22%),radial-gradient(circle_at_center,rgba(214,206,255,0.15),transparent_38%),radial-gradient(circle_at_bottom,rgba(255,248,240,0.9),transparent_60%)]" />
        <div className="relative z-10 mx-auto flex w-full max-w-6xl flex-col items-center justify-center text-center">
          <div className="mb-10 flex h-28 w-28 items-center justify-center rounded-[2rem] bg-white/92 shadow-[0_22px_50px_-30px_rgba(79,70,229,0.35)] md:h-24 md:w-24">
            <div className="text-5xl text-[rgb(71,56,230)] md:text-4xl">📖</div>
          </div>

          <h1 className="font-serif text-[5.4rem] leading-none tracking-[-0.04em] text-slate-950 sm:text-[6.6rem] md:text-[7rem]">
            LoreVia
          </h1>
          <p className="mt-10 max-w-2xl font-serif text-[1.9rem] italic leading-relaxed text-slate-600 sm:text-[2.1rem] md:mt-8 md:text-[2.4rem]">
            Your books, deeply understood.
          </p>

          <div className="mt-10 max-w-4xl text-center text-[0.86rem] font-medium uppercase tracking-[0.34em] text-slate-400 sm:text-[0.92rem] md:mt-8">
            <span className="inline">Characters.</span>{" "}
            <span className="inline">Relationships.</span>{" "}
            <span className="inline">Plot Threads.</span>{" "}
            <span className="inline">Memory.</span>{" "}
            <span className="inline">On Demand.</span>
          </div>

          <div className="mt-12 flex w-full max-w-md flex-col gap-4 sm:max-w-none sm:flex-row sm:items-center sm:justify-center md:mt-12">
            <Link
              href={user ? "/library" : "/register"}
              className="inline-flex min-w-[220px] items-center justify-center rounded-2xl bg-[linear-gradient(135deg,#4f46e5,#4338ca)] px-8 py-4 text-lg font-semibold text-white shadow-[0_20px_38px_-22px_rgba(79,70,229,0.65)] transition hover:brightness-105"
            >
              {user ? "Open app" : "Get started free"}
            </Link>
            <Link
              href={user ? "/library" : "/login"}
              className="inline-flex min-w-[170px] items-center justify-center rounded-2xl bg-white/95 px-8 py-4 text-lg font-semibold text-slate-800 shadow-[0_16px_34px_-26px_rgba(15,23,42,0.28)] transition hover:bg-white"
            >
              Sign in
            </Link>
          </div>

          <div className="mt-28 flex flex-col items-center gap-5 text-slate-400 md:mt-24">
            <p className="text-[0.92rem] font-medium uppercase tracking-[0.4em]">Designed for the digital curator</p>
            <div className="h-14 w-px bg-[linear-gradient(180deg,rgba(99,102,241,0.7),rgba(99,102,241,0))]" />
            <p className="text-[0.78rem] font-medium uppercase tracking-[0.36em]">Scroll to explore</p>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-6 pb-20 pt-8 lg:px-10 lg:pb-28 lg:pt-10">
        <div className="grid gap-14 lg:grid-cols-[1.02fr_0.98fr] lg:items-center">
          <div className="max-w-3xl">
            <p className="text-xs font-semibold uppercase tracking-[0.34em] text-sky-800">A serious reading workspace</p>
            <h2 className="mt-6 font-serif text-[3.15rem] leading-[0.98] text-slate-950 sm:text-5xl md:text-[5.2rem]">
              Stay with the story.
              <br />
              Keep every thread.
            </h2>
            <p className="mt-6 max-w-2xl text-lg leading-8 text-slate-600 md:mt-8 md:text-xl">
              LoreVia helps readers navigate complex books through spoiler-aware summaries, evolving character intelligence, relationship mapping, recall, thematic exploration, and grounded Q&amp;A shaped around reading progress.
            </p>

            <div className="mt-8 flex flex-wrap gap-4 md:mt-10">
              <Link href={user ? "/library" : "/register"} className="rounded-full bg-slate-950 px-7 py-3.5 text-sm font-semibold text-white transition hover:bg-slate-800">
                {user ? "Open your library" : "Create your workspace"}
              </Link>
              <Link href={pricingHref} className="rounded-full border border-slate-300 bg-white px-7 py-3.5 text-sm font-semibold text-slate-700 transition hover:bg-slate-50">
                View pricing
              </Link>
            </div>

            <div className="mt-12 flex flex-wrap gap-4">
              {heroSignals.map((signal) => (
                <span key={signal} className="rounded-full border border-white/80 bg-white/78 px-4 py-2 text-sm text-slate-600 shadow-[0_14px_35px_-28px_rgba(15,23,42,0.35)]">
                  {signal}
                </span>
              ))}
            </div>
          </div>

          <div className="rounded-[2.8rem] border border-white/80 bg-[linear-gradient(165deg,rgba(255,255,255,0.96),rgba(243,246,255,0.96)_55%,rgba(255,246,235,0.98))] p-5 shadow-[0_44px_140px_-60px_rgba(15,23,42,0.32)] lg:p-6">
            <div className="overflow-hidden rounded-[2.1rem] bg-[radial-gradient(circle_at_top_left,rgba(59,130,246,0.18),transparent_28%),radial-gradient(circle_at_92%_8%,rgba(250,204,21,0.2),transparent_24%),linear-gradient(180deg,#0f172a,#111827_55%,#172133)] p-6 text-white lg:p-7">
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
      </section>

      <section className="border-y border-slate-200/70 bg-white/55 py-5 backdrop-blur">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-center gap-x-10 gap-y-3 px-6 text-sm font-medium tracking-[0.18em] text-slate-500 uppercase lg:px-10">
          <span>Built for dense reading</span>
          <span>Continuity first</span>
          <span>Spoiler-aware</span>
          <span>Long-form narrative intelligence</span>
        </div>
      </section>

      <section id="difference" className="mx-auto max-w-7xl px-6 py-24 lg:px-10 lg:py-32">
        <div className="max-w-3xl">
          <p className="text-xs font-semibold uppercase tracking-[0.3em] text-rose-700">Why LoreVia</p>
          <h2 className="mt-4 font-serif text-4xl leading-tight text-slate-950 md:text-5xl">
            Not generic AI over documents.
            <br />
            A system built for reading continuity.
          </h2>
        </div>
        <div className="mt-12 grid gap-6 md:grid-cols-3">
          {differentiators.map((item) => (
            <article key={item.title} className="rounded-[2rem] border border-white/80 bg-white/88 p-7 shadow-[0_26px_70px_-54px_rgba(15,23,42,0.22)]">
              <h3 className="text-xl font-semibold text-slate-950">{item.title}</h3>
              <p className="mt-4 text-base leading-7 text-slate-600">{item.body}</p>
            </article>
          ))}
        </div>
      </section>

      <section id="features" className="mx-auto max-w-7xl px-6 py-24 lg:px-10 lg:py-32">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-3xl">
            <p className="text-xs font-semibold uppercase tracking-[0.3em] text-indigo-700">Features</p>
            <h2 className="mt-4 font-serif text-4xl leading-tight text-slate-950 md:text-5xl">
              Every tool is tied to a real reading job, not novelty for its own sake.
            </h2>
          </div>
          <p className="max-w-xl text-base leading-7 text-slate-600">
            Each feature is there to reduce rereading friction, improve comprehension, and keep readers oriented inside long books.
          </p>
        </div>
        <div className="mt-12 grid gap-5 md:grid-cols-2 xl:grid-cols-4">
          {features.map(([title, body]) => (
            <article key={title} className="rounded-[1.8rem] border border-white/80 bg-white/90 p-6 shadow-[0_18px_60px_-48px_rgba(15,23,42,0.18)]">
              <h3 className="text-lg font-semibold text-slate-950">{title}</h3>
              <p className="mt-3 text-sm leading-7 text-slate-600">{body}</p>
            </article>
          ))}
        </div>
      </section>

      <section id="workflow" className="mx-auto max-w-7xl px-6 py-24 lg:px-10 lg:py-32">
        <div className="max-w-3xl">
          <p className="text-xs font-semibold uppercase tracking-[0.3em] text-sky-800">Workflow</p>
          <h2 className="mt-4 font-serif text-4xl leading-tight text-slate-950 md:text-5xl">
            A cleaner path from raw book file to usable reading memory.
          </h2>
        </div>
        <div className="mt-12 grid gap-5 md:grid-cols-3">
          {workflow.map(([title, body], index) => (
            <article key={title} className="rounded-[1.9rem] border border-white/80 bg-white/92 p-7 shadow-[0_18px_60px_-48px_rgba(15,23,42,0.16)]">
              <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">Step {index + 1}</p>
              <h3 className="mt-4 text-2xl font-semibold text-slate-950">{title}</h3>
              <p className="mt-4 text-base leading-7 text-slate-600">{body}</p>
            </article>
          ))}
        </div>
      </section>

      <section id="pricing" className="mx-auto max-w-7xl px-6 py-24 lg:px-10 lg:py-32">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-2xl">
            <p className="text-xs font-semibold uppercase tracking-[0.3em] text-amber-700">Pricing</p>
            <h2 className="mt-4 font-serif text-4xl leading-tight text-slate-950 md:text-5xl">
              Start free now. Premium tiers are being opened carefully.
            </h2>
          </div>
          <div className="flex flex-col items-start gap-4 lg:items-end">
            <p className="max-w-xl text-base leading-7 text-slate-600">
              Starter is available today. Pro and Power are being staged with higher rate limits, cleaner controls, and a calmer rollout.
            </p>
            <div className="inline-flex rounded-full border border-slate-200 bg-slate-100 p-1">
              {(["monthly", "yearly"] as BillingCycle[]).map((cycle) => (
                <button
                  key={cycle}
                  onClick={() => setBillingCycle(cycle)}
                  className={`rounded-full px-4 py-2 text-sm font-medium transition ${
                    billingCycle === cycle ? "bg-white text-slate-950 shadow-sm" : "text-slate-600"
                  }`}
                >
                  {cycle === "monthly" ? "Monthly" : "Yearly"}
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="relative mt-12 overflow-hidden rounded-[2.5rem] border border-white/80 bg-[linear-gradient(180deg,rgba(255,255,255,0.95),rgba(247,248,250,0.95))] p-6 shadow-[0_34px_100px_-60px_rgba(15,23,42,0.28)] lg:p-8">
          <div className="grid gap-5 opacity-45 blur-[1px] lg:grid-cols-4">
            {plans.map((plan, index) => {
              const selectedPrice = billingCycle === "yearly" ? plan.yearly : plan.monthly
              const active = index === 1
              return (
                <article
                  key={plan.name}
                  className={`rounded-[2rem] border p-6 ${
                    active ? "border-slate-950 bg-slate-950 text-white" : "border-slate-200 bg-white/95 text-slate-900"
                  }`}
                >
                  <p className={`text-xs font-semibold uppercase tracking-[0.22em] ${active ? "text-amber-200" : "text-slate-500"}`}>{plan.highlight}</p>
                  <div className="mt-4 flex items-end gap-3">
                    <h3 className="font-serif text-4xl">{plan.name}</h3>
                    <p className={`pb-1 text-sm ${active ? "text-slate-300" : "text-slate-500"}`}>{selectedPrice}</p>
                  </div>
                  <p className={`mt-1 text-xs uppercase tracking-[0.18em] ${active ? "text-slate-400" : "text-slate-400"}`}>
                    {billingCycle === "yearly" ? "per year" : "per month"} - {plan.note}
                  </p>
                  <ul className="mt-6 space-y-3">
                    {plan.bullets.map((bullet) => (
                      <li key={bullet} className={`rounded-2xl px-4 py-3 text-sm ${active ? "bg-white/8 text-slate-100" : "bg-slate-100 text-slate-700"}`}>
                        {bullet}
                      </li>
                    ))}
                  </ul>
                  <div className={`mt-7 rounded-full border px-5 py-3 text-center text-sm font-semibold ${active ? "border-white/10 text-slate-200" : "border-slate-300 text-slate-600"}`}>
                    {plan.name === "Starter" ? "Available now" : "Coming soon"}
                  </div>
                </article>
              )
            })}
          </div>

          <div className="absolute inset-0 flex items-center justify-center bg-[linear-gradient(180deg,rgba(255,255,255,0.46),rgba(255,255,255,0.78))] backdrop-blur-sm">
            <div className="mx-6 max-w-2xl rounded-[2rem] border border-white/80 bg-white/82 px-8 py-10 text-center shadow-[0_30px_80px_-52px_rgba(15,23,42,0.28)]">
              <p className="text-xs font-semibold uppercase tracking-[0.34em] text-amber-700">Coming soon</p>
              <h3 className="mt-4 font-serif text-4xl leading-tight text-slate-950">Higher rate limits, cleaner paid tiers, and a more deliberate rollout.</h3>
              <p className="mt-4 text-base leading-7 text-slate-600">
                Starter stays open now. Pro and Power are being prepared with expanded capacity for search, summaries, grounded Q&amp;A, and long-book continuity.
              </p>
              <div className="mt-7 flex flex-wrap items-center justify-center gap-3">
                <span className="rounded-full bg-slate-950 px-4 py-2 text-sm font-medium text-white">Higher summary limits</span>
                <span className="rounded-full bg-slate-950 px-4 py-2 text-sm font-medium text-white">Higher search limits</span>
                <span className="rounded-full bg-slate-950 px-4 py-2 text-sm font-medium text-white">Longer reading sessions</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section id="faq" className="mx-auto max-w-7xl px-6 pb-28 pt-10 lg:px-10">
        <div className="grid gap-10 lg:grid-cols-[0.92fr_1.08fr]">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.3em] text-sky-800">FAQ</p>
            <h2 className="mt-4 font-serif text-4xl leading-tight text-slate-950 md:text-5xl">
              Questions readers usually ask before committing.
            </h2>
          </div>
          <div className="space-y-4">
            {faqs.map(([question, answer]) => (
              <article key={question} className="rounded-[1.8rem] border border-white/80 bg-white/92 p-6 shadow-[0_18px_60px_-48px_rgba(15,23,42,0.16)]">
                <h3 className="text-lg font-semibold text-slate-950">{question}</h3>
                <p className="mt-3 text-sm leading-7 text-slate-600">{answer}</p>
              </article>
            ))}
          </div>
        </div>
      </section>
    </main>
  )
}
