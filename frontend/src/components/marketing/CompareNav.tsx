import Link from "next/link"

import { comparisonIndexCards } from "@/lib/comparisons"

type CompareNavProps = {
  activeSlug?: string
}

export function CompareNav({ activeSlug }: CompareNavProps) {
  return (
    <div className="flex flex-wrap gap-3">
      {comparisonIndexCards.map((item) => {
        const active = item.slug === activeSlug

        return (
          <Link
            key={item.slug}
            href={`/compare/${item.slug}`}
            className={`inline-flex items-center rounded-full border px-4 py-2 text-sm font-semibold transition ${
              active
                ? "border-[#276a63] bg-[#11312d] text-[#86decd]"
                : "border-white/10 bg-white/5 text-[#c9d1cb] hover:border-white/20 hover:bg-white/8 hover:text-white"
            }`}
          >
            LoreVia vs {item.name}
          </Link>
        )
      })}
    </div>
  )
}
