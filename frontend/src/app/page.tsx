"use client"

import Link from "next/link"
import { useMemo, useState } from "react"
import { billingApi } from "@/lib/api/billing"
import { useAuthStore } from "@/lib/stores/authStore"

type BillingCycle = "monthly" | "yearly"
type PaidPlanCode = "pro_monthly" | "pro_annual" | "power_monthly" | "power_annual"

const productPillars = [
  {
    title: "Character Engine",
    label: "Micro view",
    body: "Track who people are, how they change, which roles they play, and how their motives evolve as the story unfolds.",
  },
  {
    title: "Event / Plot Tracker",
    label: "Meso view",
    body: "Follow turning points, unresolved threads, foreshadowing signals, and relationship shifts without losing your place in the story.",
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
    body: "LoreVia is designed around long-form reading, not generic document chat. The product thinks in chapters, characters, arcs, and read progress.",
  },
  {
    title: "Spoiler-safe by product design",
    body: "Progress-aware recall, summaries, and relationship tools are part of the core architecture rather than an afterthought.",
  },
  {
    title: "A reading workspace, not a PDF wrapper",
    body: "Upload, organize, search, revisit, quote, and reason across the book from a single structured environment.",
  },
]

const plans = [
  {
    name: "Starter",
    monthly: "$0",
    yearly: "$0",
    note: "for exploration",
    monthlyCode: null,
    yearlyCode: null,
    comingSoon: false,
    highlight: "Best for trying the experience",
    bullets: ["Core spoiler-safe reading workspace", "Chapter memory and smart retrieval", "A polished first step into LoreVia"],
  },
  {
    name: "Pro",
    monthly: "$9",
    yearly: "$90",
    note: "for serious readers",
    monthlyCode: "pro_monthly" as PaidPlanCode,
    yearlyCode: "pro_annual" as PaidPlanCode,
    comingSoon: false,
    highlight: "Best for serious readers",
    bullets: ["Expanded reading workspace", "More summaries, search, and grounded Q&A", "Premium character detail and richer continuity"],
  },
  {
    name: "Power",
    monthly: "$17",
    yearly: "$170",
    note: "for dense books and long libraries",
    monthlyCode: "power_monthly" as PaidPlanCode,
    yearlyCode: "power_annual" as PaidPlanCode,
    comingSoon: false,
    highlight: "Best for dense books and long libraries",
    bullets: ["Highest depth and capacity", "Maximum continuity headroom", "Best fit for classics, series, and research-heavy reading"],
  },
  {
    name: "Studio",
    monthly: "$34",
    yearly: "$340",
    note: "for future advanced workflows",
    monthlyCode: null,
    yearlyCode: null,
    comingSoon: true,
    highlight: "Reserved for richer premium workflows",
    bullets: ["High-touch future tier", "Best home for advanced series workflows", "Coming soon"],
  },
]

const faqs = [
  ["What makes LoreVia different?", "LoreVia is built around spoiler-safe reading continuity. It treats books as evolving worlds, not just static files to summarize."],
  ["Does it replace reading?", "No. It supports reading by helping you recover context, track people and events, and return to the exact thread you were following."],
  ["Who is it best for?", "Readers of dense fiction, classics, fantasy series, and long-form narrative nonfiction benefit the most."],
  ["Why upgrade?", "Paid plans open a larger, deeper workspace for readers who want more continuity, more interaction, and more room for long projects."],
]

const workflow = [
  ["Upload the book", "Bring in a PDF or EPUB and turn it into a structured reading workspace."],
  ["Read with context", "Track characters, summaries, events, and recall without losing your place."],
  ["Explore what matters", "Use timelines, thematic search, grounded Q&A, and saved quotes to revisit the book intelligently."],
]

export default function HomePage() {
  const user = useAuthStore((state) => state.user)
  const [busyPlan, setBusyPlan] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [hovered, setHovered] = useState("Pro")
  const [billingCycle, setBillingCycle] = useState<BillingCycle>("monthly")

  const pricingHref = useMemo(() => (user ? "/pricing" : "#pricing"), [user])

  async function handlePlanClick(planCode: PaidPlanCode | null) {
    if (!planCode) {
      window.location.href = user ? "/library" : "/register"
      return
    }
    if (!user) {
      window.location.href = "/register"
      return
    }

    setBusyPlan(planCode)
    setMessage(null)
    try {
      const result = await billingApi.checkout(planCode)
      if (!result.billing_enabled || !result.checkout_url) {
        setMessage(result.message ?? "Billing is not configured in this environment yet.")
        return
      }
      window.location.href = result.checkout_url
    } catch {
      setMessage("We could not start checkout right now. Please try again in a moment.")
    } finally {
      setBusyPlan(null)
    }
  }

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top_left,#dce8ff,transparent_22%),radial-gradient(circle_at_88%_8%,#fde7cc,transparent_26%),linear-gradient(180deg,#f4f6fb_0%,#fbfaf7_52%,#eef2f9_100%)] text-slate-900">
      <header className="sticky top-0 z-30 border-b border-slate-200/70 bg-white/75 backdrop-blur-xl">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4 lg:px-10">
          <Link href="/" className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-slate-950 text-sm font-semibold text-white">LV</div>
            <div>
              <p className="font-serif text-2xl tracking-tight text-slate-950">LoreVia</p>
              <p className="text-xs text-slate-500">Reading intelligence, made elegant</p>
            </div>
          </Link>
          <nav className="hidden items-center gap-2 md:flex">
            <a href="#features" className="rounded-full px-4 py-2 text-sm text-slate-600 transition hover:bg-white hover:text-slate-950">Features</a>
            <a href="#difference" className="rounded-full px-4 py-2 text-sm text-slate-600 transition hover:bg-white hover:text-slate-950">Why LoreVia</a>
            <a href="#faq" className="rounded-full px-4 py-2 text-sm text-slate-600 transition hover:bg-white hover:text-slate-950">FAQ</a>
            <Link href={pricingHref} className="rounded-full px-4 py-2 text-sm text-slate-600 transition hover:bg-white hover:text-slate-950">Pricing</Link>
          </nav>
          <div className="flex items-center gap-3">
            <Link href={user ? "/library" : "/login"} className="rounded-full border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50">
              {user ? "Open app" : "Sign in"}
            </Link>
            <Link href={user ? "/pricing" : "/register"} className="rounded-full bg-slate-950 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-slate-800">
              {user ? "Upgrade" : "Start free"}
            </Link>
          </div>
        </div>
      </header>

      <section className="mx-auto max-w-7xl px-6 pb-20 pt-12 lg:px-10 lg:pt-16">
        <div className="grid gap-8 lg:grid-cols-[1.1fr_0.9fr] lg:items-center">
          <div className="max-w-3xl">
            <p className="text-xs font-semibold uppercase tracking-[0.34em] text-sky-800">A serious reading workspace</p>
            <h1 className="mt-4 font-serif text-5xl leading-[1.02] text-slate-950 md:text-7xl">
              Follow the story,
              <br />
              keep the thread,
              <br />
              remember more.
            </h1>
            <p className="mt-6 max-w-2xl text-lg leading-8 text-slate-600">
              LoreVia helps readers navigate complex books through spoiler-aware summaries, evolving character intelligence, relationship mapping, recall, thematic exploration, and grounded Q&amp;A built around reading progress.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link href={user ? "/library" : "/register"} className="rounded-full bg-slate-950 px-6 py-3 text-sm font-semibold text-white transition hover:bg-slate-800">
                {user ? "Go to your library" : "Create your workspace"}
              </Link>
              <Link href={pricingHref} className="rounded-full border border-slate-300 bg-white px-6 py-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-50">
                View pricing
              </Link>
            </div>
          </div>

          <div className="rounded-[2.4rem] border border-white/80 bg-[linear-gradient(160deg,rgba(255,255,255,0.96),rgba(239,244,255,0.96)_55%,rgba(255,245,232,0.98))] p-6 shadow-[0_40px_140px_-55px_rgba(15,23,42,0.28)]">
            <div className="rounded-[1.9rem] bg-[radial-gradient(circle_at_top_left,rgba(59,130,246,0.18),transparent_26%),radial-gradient(circle_at_85%_10%,rgba(251,191,36,0.18),transparent_26%),linear-gradient(180deg,#0f172a,#111827_55%,#162033)] p-6 text-white">
              <p className="text-xs font-semibold uppercase tracking-[0.28em] text-slate-300">Inside LoreVia</p>
              <h2 className="mt-3 font-serif text-3xl leading-tight">A book becomes an explorable memory layer.</h2>
              <div className="mt-6 grid gap-3 sm:grid-cols-2">
                {productPillars.map((item) => (
                  <div key={item.title} className="rounded-2xl border border-white/10 bg-white/5 p-4">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-amber-200">{item.label}</p>
                    <p className="mt-2 text-sm font-semibold text-white">{item.title}</p>
                    <p className="mt-2 text-xs leading-6 text-slate-300">{item.body}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>

      <section id="difference" className="mx-auto max-w-7xl px-6 py-18 lg:px-10">
        <div className="max-w-3xl">
          <p className="text-xs font-semibold uppercase tracking-[0.3em] text-rose-700">What makes LoreVia unique</p>
          <h2 className="mt-3 font-serif text-4xl text-slate-950">Not generic AI over documents. A dedicated system for reading continuity.</h2>
        </div>
        <div className="mt-8 grid gap-5 md:grid-cols-3">
          {differentiators.map((item) => (
            <article key={item.title} className="rounded-[1.9rem] border border-slate-200 bg-white/92 p-6 shadow-[0_24px_70px_-52px_rgba(15,23,42,0.2)]">
              <h3 className="text-xl font-semibold text-slate-950">{item.title}</h3>
              <p className="mt-3 text-sm leading-7 text-slate-600">{item.body}</p>
            </article>
          ))}
        </div>
      </section>

      <section id="features" className="mx-auto max-w-7xl px-6 py-18 lg:px-10">
        <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
          <div className="max-w-3xl">
            <p className="text-xs font-semibold uppercase tracking-[0.3em] text-indigo-700">Features</p>
            <h2 className="mt-3 font-serif text-4xl text-slate-950">Everything the app provides, with each tool tied to a reading job.</h2>
          </div>
          <p className="max-w-xl text-sm leading-7 text-slate-600">
            Each feature is designed to reduce rereading friction, improve comprehension, and help readers stay oriented inside long books.
          </p>
        </div>
        <div className="mt-8 grid gap-5 md:grid-cols-2 xl:grid-cols-4">
          {features.map(([title, body]) => (
            <article key={title} className="rounded-[1.7rem] border border-slate-200 bg-white/95 p-5 shadow-[0_18px_60px_-48px_rgba(15,23,42,0.18)]">
              <h3 className="text-lg font-semibold text-slate-950">{title}</h3>
              <p className="mt-2 text-sm leading-6 text-slate-600">{body}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-6 py-18 lg:px-10">
        <div className="max-w-3xl">
          <p className="text-xs font-semibold uppercase tracking-[0.3em] text-sky-800">How it works</p>
          <h2 className="mt-3 font-serif text-4xl text-slate-950">A cleaner path from raw book file to usable reading memory.</h2>
        </div>
        <div className="mt-8 grid gap-5 md:grid-cols-3">
          {workflow.map(([title, body], index) => (
            <article key={title} className="rounded-[1.8rem] border border-slate-200 bg-white/95 p-6 shadow-[0_18px_60px_-48px_rgba(15,23,42,0.16)]">
              <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">Step {index + 1}</p>
              <h3 className="mt-3 text-xl font-semibold text-slate-950">{title}</h3>
              <p className="mt-3 text-sm leading-7 text-slate-600">{body}</p>
            </article>
          ))}
        </div>
      </section>

      <section id="pricing" className="mx-auto max-w-7xl px-6 py-18 lg:px-10">
        <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
          <div className="max-w-2xl">
            <p className="text-xs font-semibold uppercase tracking-[0.3em] text-amber-700">Pricing</p>
            <h2 className="mt-3 font-serif text-4xl text-slate-950">Start free, expand your reading workspace when you want more depth.</h2>
          </div>
          <div className="flex flex-col items-start gap-4 md:items-end">
            <p className="max-w-xl text-sm leading-7 text-slate-600">
              Starter gives the core experience. Pro and Power are for readers who want more continuity, more interaction, and more room for long projects.
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
        {message ? <div className="mt-6 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">{message}</div> : null}
        <div className="mt-8 grid gap-5 lg:grid-cols-4">
          {plans.map((plan) => {
            const active = hovered === plan.name
            const selectedPrice = billingCycle === "yearly" ? plan.yearly : plan.monthly
            const selectedPlanCode = billingCycle === "yearly" ? plan.yearlyCode : plan.monthlyCode
            return (
              <article
                key={plan.name}
                onMouseEnter={() => setHovered(plan.name)}
                className={`rounded-[2rem] border p-6 transition-all duration-300 ${
                  active
                    ? "translate-y-[-8px] border-slate-950 bg-slate-950 text-white shadow-[0_32px_110px_-56px_rgba(15,23,42,0.48)]"
                    : "border-slate-200 bg-white/95 text-slate-900 shadow-[0_18px_70px_-55px_rgba(15,23,42,0.2)] hover:translate-y-[-8px]"
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
                {selectedPlanCode ? (
                  <button
                    onClick={() => handlePlanClick(selectedPlanCode)}
                    disabled={busyPlan === selectedPlanCode}
                    className={`mt-7 w-full rounded-full px-5 py-3 text-sm font-semibold transition ${
                      active ? "bg-amber-300 text-slate-950 hover:bg-amber-200" : "border border-slate-300 bg-white text-slate-900 hover:bg-slate-50"
                    } disabled:opacity-60`}
                  >
                    {busyPlan === selectedPlanCode ? "Opening checkout..." : `Choose ${plan.name}`}
                  </button>
                ) : (
                  <div className={`mt-7 rounded-full border px-5 py-3 text-center text-sm font-semibold ${
                    active ? "border-white/10 text-slate-200" : "border-slate-300 text-slate-600"
                  }`}>
                    {plan.comingSoon ? "Coming soon" : "Start with Starter"}
                  </div>
                )}
              </article>
            )
          })}
        </div>
      </section>

      <section id="faq" className="mx-auto max-w-7xl px-6 pb-24 pt-10 lg:px-10">
        <div className="grid gap-8 lg:grid-cols-[0.9fr_1.1fr]">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.3em] text-sky-800">FAQ</p>
            <h2 className="mt-3 font-serif text-4xl text-slate-950">Questions readers usually ask before committing.</h2>
          </div>
          <div className="space-y-4">
            {faqs.map(([question, answer]) => (
              <article key={question} className="rounded-[1.8rem] border border-slate-200 bg-white/95 p-6 shadow-[0_18px_60px_-48px_rgba(15,23,42,0.16)]">
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
