import Link from "next/link"
import type { Route } from "next"

type ComparisonHeroProps = {
  title: string
  summary: string
}

export function ComparisonHero({ title, summary }: ComparisonHeroProps) {
  const ctaHref: Route = "/register"

  return (
    <section className="mx-auto max-w-7xl px-5 pb-12 pt-12 md:px-8 md:pb-16 md:pt-16">
      <div className="grid gap-8 lg:grid-cols-[0.9fr_1.1fr] lg:items-end">
        <div>
          <p className="text-3xs font-semibold uppercase tracking-[0.32em] text-[#79c8b8]">
            Comparison guide
          </p>
          <h1 className="mt-5 max-w-2xl font-display text-5xl font-semibold leading-[0.95] tracking-[-0.04em] text-white md:text-7xl">
            {title}
          </h1>
          <p className="mt-6 max-w-2xl text-lg leading-8 text-[#aeb9b3]">{summary}</p>
          <div className="mt-8 flex flex-col gap-3 sm:flex-row">
            <Link
              href={ctaHref}
              className="inline-flex items-center justify-center rounded-xl bg-[#1f615d] px-6 py-3.5 text-base font-semibold text-white transition hover:bg-[#25756f]"
            >
              Start free
            </Link>
            <Link
              href="/pricing"
              className="inline-flex items-center justify-center rounded-xl border border-white/12 bg-white/5 px-6 py-3.5 text-base font-semibold text-white transition hover:bg-white/8"
            >
              View pricing
            </Link>
          </div>
        </div>

        <div className="rounded-lg border border-white/10 bg-[linear-gradient(180deg,rgba(15,35,32,0.94),rgba(9,18,16,0.98))] p-6 shadow-[0_24px_70px_-48px_rgba(0,0,0,0.75)]">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="rounded-md border border-white/8 bg-[#0b1513] p-5">
              <p className="text-xs uppercase tracking-[0.22em] text-[#6fae9f]">What LoreVia emphasizes</p>
              <p className="mt-4 text-lg font-semibold text-white">Continuity, story memory, revision clarity</p>
            </div>
            <div className="rounded-md border border-white/8 bg-[#0b1513] p-5">
              <p className="text-xs uppercase tracking-[0.22em] text-[#6fae9f]">How to read this page</p>
              <p className="mt-4 text-lg font-semibold text-white">Choose the workflow that removes your bottleneck</p>
            </div>
          </div>
          <p className="mt-5 text-sm leading-7 text-[#8fa19a]">
            This comparison is designed to stay specific and practical. It focuses on writing workflow, continuity support, story memory, and revision needs rather than trying to claim one tool is universally better.
          </p>
        </div>
      </div>
    </section>
  )
}
