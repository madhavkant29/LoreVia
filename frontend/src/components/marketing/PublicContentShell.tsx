import type { ReactNode } from "react"

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
    <main className={`editorial-shell ${className ?? ""}`}>
      <PublicContentHeader activeSection={activeSection} />
      {children}
    </main>
  )
}
