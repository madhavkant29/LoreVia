import type { ReactNode } from "react"
import type { Route } from "next"
import Link from "next/link"

import { cn } from "@/lib/utils/text"

type WorkspaceFamily = "story-bible" | "review-center" | "publish-export"

type FamilyItem = {
  id: string
  label: string
  href: (bookId: string) => Route
}

const FAMILY_ITEMS: Record<WorkspaceFamily, FamilyItem[]> = {
  "story-bible": [
    { id: "characters", label: "Characters", href: (bookId) => `/${bookId}/characters` as Route },
    { id: "relationships", label: "Relationships", href: (bookId) => `/${bookId}/graph` as Route },
    { id: "timeline", label: "Timeline", href: (bookId) => `/${bookId}/timeline` as Route },
    { id: "plot-threads", label: "Plot threads", href: (bookId) => `/${bookId}/plot-threads` as Route },
    { id: "foreshadowing", label: "Foreshadowing", href: (bookId) => `/${bookId}/foreshadowing` as Route },
    { id: "world-gap", label: "World gaps", href: (bookId) => `/${bookId}/world-gap` as Route },
    { id: "cross-book-wiki", label: "Series wiki", href: (bookId) => `/${bookId}/cross-book-wiki` as Route },
  ],
  "review-center": [
    { id: "advisor", label: "Story advisor", href: (bookId) => `/${bookId}/advisor` as Route },
    { id: "editorial-review", label: "Editorial review", href: (bookId) => `/${bookId}/editorial-review` as Route },
    { id: "voice", label: "Voice", href: (bookId) => `/${bookId}/voice` as Route },
    { id: "analysis", label: "Analysis", href: (bookId) => `/${bookId}/analysis` as Route },
    { id: "reports", label: "Chapter reports", href: (bookId) => `/${bookId}/reports` as Route },
    { id: "beta-feedback", label: "Beta feedback", href: (bookId) => `/${bookId}/beta-feedback` as Route },
    { id: "summaries", label: "Summaries", href: (bookId) => `/${bookId}/summaries` as Route },
    { id: "author-loop", label: "Author loop", href: (bookId) => `/${bookId}/author-loop` as Route },
  ],
  "publish-export": [
    { id: "export", label: "Import & export", href: (bookId) => `/${bookId}/export` as Route },
    { id: "collaboration", label: "Collaborators", href: (bookId) => `/${bookId}/collaboration` as Route },
    { id: "visibility", label: "Visibility", href: (bookId) => `/${bookId}/visibility` as Route },
  ],
}

export function WorkspaceFamilyHeader({
  active,
  actions,
  bookId,
  description,
  family,
  title,
}: {
  active: string
  actions?: ReactNode
  bookId: string
  description: string
  family: WorkspaceFamily
  title: string
}) {
  const items = FAMILY_ITEMS[family]

  return (
    <header className="app-panel app-panel--strong overflow-hidden">
      <div className="flex flex-col gap-5 px-5 py-6 sm:px-6 lg:flex-row lg:items-end lg:justify-between">
        <div className="max-w-3xl">
          <p className="app-eyebrow">{familyLabel(family)}</p>
          <h1 className="mt-3 font-display text-4xl leading-none tracking-normal text-[rgb(var(--foreground))] sm:text-5xl">
            {title}
          </h1>
          <p className="app-copy mt-3 max-w-2xl">{description}</p>
        </div>
        {actions ? <div className="flex flex-wrap gap-2">{actions}</div> : null}
      </div>

      <nav
        aria-label={`${familyLabel(family)} navigation`}
        className="app-family-tabs app-scroll border-t border-[rgba(var(--border),0.72)]"
      >
        {items.map((item) => (
          <Link
            key={item.id}
            href={item.href(bookId)}
            className={cn("app-family-tab", active === item.id && "app-family-tab--active")}
          >
            {item.label}
          </Link>
        ))}
      </nav>
    </header>
  )
}

function familyLabel(family: WorkspaceFamily) {
  switch (family) {
    case "story-bible":
      return "Story Bible"
    case "review-center":
      return "Review Center"
    case "publish-export":
      return "Publish & Export"
  }
}
