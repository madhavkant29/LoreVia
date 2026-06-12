"use client"

import Link from "next/link"
import type { Route } from "next"

type ContextualUpgradePromptProps = {
  featureName?: string
  body?: string
  compareHref?: Route | string
  onBack?: () => void
}

export function ContextualUpgradePrompt({
  featureName = "Author workspace",
  body = "Free includes reading existing projects, exporting manuscript files, and 1 Story Advisor turn each week.",
  compareHref = "/upgrade",
  onBack,
}: ContextualUpgradePromptProps) {
  return (
    <section className="rounded-md border border-amber-200 bg-amber-50 px-5 py-4 text-amber-950 dark:border-amber-400/25 dark:bg-amber-400/10 dark:text-amber-100">
      <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
        <div className="max-w-2xl">
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-amber-700 dark:text-amber-200">Author feature</p>
          <h2 className="mt-2 text-lg font-semibold tracking-[-0.01em]">{featureName} requires Author</h2>
          <p className="mt-2 text-sm leading-6 text-amber-900/85 dark:text-amber-100/85">{body}</p>
        </div>
        <div className="flex shrink-0 flex-wrap gap-2">
          <Link
            href="/upgrade?plan=author"
            className="inline-flex items-center justify-center rounded-sm border border-transparent bg-[#1f615d] px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-[#174c49]"
          >
            Upgrade to Author
          </Link>
          <Link
            href={compareHref as any}
            className="inline-flex items-center justify-center rounded-sm border border-amber-300 bg-white px-4 py-2.5 text-sm font-semibold text-amber-950 transition hover:bg-amber-100 dark:border-amber-300/30 dark:bg-transparent dark:text-amber-100 dark:hover:bg-amber-300/10"
          >
            Compare plans
          </Link>
          {onBack ? (
            <button
              type="button"
              onClick={onBack}
              className="inline-flex items-center justify-center rounded-sm border border-transparent px-4 py-2.5 text-sm font-semibold text-amber-900 transition hover:bg-amber-100 dark:text-amber-100 dark:hover:bg-amber-300/10"
            >
              Back
            </button>
          ) : null}
        </div>
      </div>
    </section>
  )
}
