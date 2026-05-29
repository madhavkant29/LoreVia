import Link from "next/link"
import type { Route } from "next"

type ComparisonCTAProps = {
  title?: string
  body?: string
}

export function ComparisonCTA({
  title = "Try LoreVia on your own manuscript.",
  body = "Bring in the draft you already have, keep continuity visible, and revise from a workspace that remembers the story with you.",
}: ComparisonCTAProps) {
  const ctaHref: Route = "/register"

  return (
    <section className="mx-auto max-w-7xl px-5 py-12 md:px-8 md:pb-20">
      <div className="rounded-lg border border-white/10 bg-[linear-gradient(180deg,rgba(15,35,32,0.94),rgba(8,17,15,0.98))] px-6 py-8 md:px-10 md:py-10">
        <div className="grid gap-6 lg:grid-cols-[1fr_auto] lg:items-center">
          <div>
            <h2 className="font-display text-4xl font-semibold leading-tight text-white md:text-5xl">{title}</h2>
            <p className="mt-4 max-w-2xl text-lg leading-8 text-[#aeb9b3]">{body}</p>
          </div>
          <div className="flex flex-col gap-3 sm:flex-row lg:justify-end">
            <Link
              href={ctaHref}
              className="inline-flex items-center justify-center rounded-xl bg-[#1f615d] px-7 py-3.5 text-base font-semibold text-white transition hover:bg-[#25756f]"
            >
              Start free
            </Link>
            <Link
              href="/compare"
              className="inline-flex items-center justify-center rounded-xl border border-white/12 bg-white/5 px-7 py-3.5 text-base font-semibold text-white transition hover:bg-white/8"
            >
              See all comparisons
            </Link>
          </div>
        </div>
      </div>
    </section>
  )
}
