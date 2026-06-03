import type { ReactNode } from "react"

import { cn } from "@/lib/utils/text"

import { PublicContentHeader } from "./PublicContentHeader"

export function PublicContentShell({
  activeSection,
  children,
  className,
}: {
  activeSection: "blog" | "answers" | "demo"
  children: ReactNode
  className?: string
}) {
  return (
    <main className={cn("app-shell overflow-hidden content-library-shell", className)}>
      <PublicContentHeader activeSection={activeSection} />
      {children}
    </main>
  )
}
