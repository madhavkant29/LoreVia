import Link from "next/link"

import { comparisonIndexCards } from "@/lib/comparisons"

type CompareNavProps = {
  activeSlug?: string
}

export function CompareNav({ activeSlug }: CompareNavProps) {
  return (
    <nav aria-label="Other comparisons" className="grid border-y border-white/10 sm:grid-cols-2 lg:grid-cols-4">
      {comparisonIndexCards.map((item) => {
        const active = item.slug === activeSlug

        return (
          <Link
            key={item.slug}
            href={`/compare/${item.slug}`}
            aria-current={active ? "page" : undefined}
            className={`border-b border-white/[0.08] py-4 text-sm font-semibold transition sm:px-4 lg:border-b-0 lg:border-r lg:last:border-r-0 ${
              active
                ? "text-[#86decd]"
                : "text-[#aeb9b3] hover:bg-white/[0.025] hover:text-white"
            }`}
          >
            LoreVia vs {item.name}
          </Link>
        )
      })}
    </nav>
  )
}
