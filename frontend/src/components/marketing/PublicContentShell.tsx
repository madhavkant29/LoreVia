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
  const squareCorners = activeSection === "blog" || activeSection === "answers"

  return (
    <main className={cn("app-shell overflow-hidden content-library-shell", squareCorners && "content-library-square-corners", className)}>
      <PublicContentHeader activeSection={activeSection} />
      {children}
    </main>
  )
}
