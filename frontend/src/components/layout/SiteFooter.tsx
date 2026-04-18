"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { LEGAL_EMAIL, SUPPORT_EMAIL } from "@/lib/constants/contact"

export function SiteFooter() {
  const pathname = usePathname()

  if (pathname?.includes("/chapter/")) return null

  return (
    <footer className="border-t border-border bg-background/50 px-4 py-8 text-[11px] font-medium tracking-tight text-muted-foreground transition-colors">
      <div className="mx-auto flex max-w-7xl flex-col gap-6 sm:flex-row sm:items-center sm:justify-between">
        <p className="flex items-center gap-2">
          <span className="h-1.5 w-1.5 rounded-full bg-brand-500 animate-pulse" />
          Support:{" "}
          <a href={`mailto:${SUPPORT_EMAIL}`} className="text-foreground hover:text-brand-500 transition-colors">
            {SUPPORT_EMAIL}
          </a>
        </p>
        <div className="flex flex-wrap items-center gap-y-2 gap-x-6">
          <Link href="/contact" className="hover:text-foreground transition-colors">
            Contact
          </Link>
          <Link href="/terms" className="hover:text-foreground transition-colors">
            Terms
          </Link>
          <Link href="/compliance" className="hover:text-foreground transition-colors">
            Compliance
          </Link>
          <Link href="/eula" className="hover:text-foreground transition-colors">
            EULA
          </Link>
          <p className="sm:ml-4">
            Legal: <a href={`mailto:${LEGAL_EMAIL}`} className="text-foreground hover:text-brand-500 transition-colors">{LEGAL_EMAIL}</a>
          </p>
        </div>
      </div>
    </footer>
  )
}
