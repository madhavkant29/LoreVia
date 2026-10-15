"use client"

import type { ReactNode } from "react"

import { AuthorToolsNav } from "@/components/layout/AuthorToolsNav"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"

type WorkspaceFamily = "story-bible" | "review-center" | "publish-export"

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
  const theme = usePreferencesStore((state) => state.theme)

  return (
    <div className="space-y-5">
      <AuthorToolsNav
        active={active}
        bookId={bookId}
        isDark={theme === "dark"}
        title={title}
        variant="bar"
      />

      <header className="flex flex-col gap-4 border-b border-[rgba(var(--border),0.72)] pb-5 lg:flex-row lg:items-end lg:justify-between">
        <div className="max-w-3xl">
          <p className="app-eyebrow">{familyLabel(family)}</p>
          <h1 className="mt-2 text-3xl font-semibold tracking-[-0.02em] text-[rgb(var(--foreground))] sm:text-4xl">
            {title}
          </h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-[rgb(var(--muted-foreground))]">{description}</p>
        </div>
        {actions ? <div className="flex flex-wrap gap-2">{actions}</div> : null}
      </header>
    </div>
  )
}

function familyLabel(family: WorkspaceFamily) {
  switch (family) {
    case "story-bible":
      return "Story Bible"
    case "review-center":
      return "Review"
    case "publish-export":
      return "Share"
  }
}
