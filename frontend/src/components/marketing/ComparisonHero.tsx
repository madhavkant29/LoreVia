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
      <div className="max-w-5xl">
        <Link href="/compare" className="text-sm font-semibold text-[#79c8b8] transition hover:text-white">
          Comparisons
        </Link>
        <h1 className="mt-4 font-display text-5xl font-semibold leading-[0.98] tracking-[-0.04em] text-white md:text-7xl">
          {title}
        </h1>
        <p className="mt-6 max-w-3xl text-lg leading-8 text-[#aeb9b3]">{summary}</p>
        <div className="mt-8 flex flex-col gap-3 sm:flex-row">
          <Link
            href={ctaHref}
            className="inline-flex items-center justify-center rounded-md bg-[#1f615d] px-6 py-3.5 text-base font-semibold text-white transition hover:bg-[#25756f]"
          >
            Start free
          </Link>
          <Link
            href="/pricing"
            className="inline-flex items-center justify-center rounded-md border border-white/[0.12] bg-white/5 px-6 py-3.5 text-base font-semibold text-white transition hover:bg-white/[0.08]"
          >
            View pricing
          </Link>
        </div>
        <div className="mt-10 max-w-3xl border-l-2 border-[#276a63] pl-5">
          <p className="text-sm leading-7 text-[#8fa19a]">
            This guide compares writing workflow, continuity support, story memory, and revision needs. It does not assume one tool is the right fit for every author.
          </p>
        </div>
      </div>
    </section>
  )
}
