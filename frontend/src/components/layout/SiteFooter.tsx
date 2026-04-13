"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { LEGAL_EMAIL, SUPPORT_EMAIL } from "@/lib/constants/contact"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"

export function SiteFooter() {
  const pathname = usePathname()
  const { theme } = usePreferencesStore()
  const isDark = theme === "dark"

  if (pathname?.includes("/chapter/")) return null

  return (
    <footer
      className={`border-t px-4 py-4 text-xs transition-colors ${
        isDark ? "border-white/10 bg-black/40 text-gray-400" : "border-stone-200 bg-white/80 text-stone-500"
      }`}
    >
      <div className="mx-auto flex max-w-6xl flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <p>
          Support:{" "}
          <a href={`mailto:${SUPPORT_EMAIL}`} className={isDark ? "text-gray-200 hover:text-white" : "text-stone-700 hover:text-stone-950"}>
            {SUPPORT_EMAIL}
          </a>
        </p>
        <p className="flex flex-wrap items-center gap-3">
          <Link href="/contact" className={isDark ? "hover:text-white" : "hover:text-stone-950"}>
            Contact
          </Link>
          <Link href="/terms" className={isDark ? "hover:text-white" : "hover:text-stone-950"}>
            Terms &amp; Conditions
          </Link>
          <Link href="/compliance" className={isDark ? "hover:text-white" : "hover:text-stone-950"}>
            Compliance
          </Link>
          <Link href="/eula" className={isDark ? "hover:text-white" : "hover:text-stone-950"}>
            EULA
          </Link>
          <span>Legal and copyright: <a href={`mailto:${LEGAL_EMAIL}`} className={isDark ? "text-gray-200 hover:text-white" : "text-stone-700 hover:text-stone-950"}>{LEGAL_EMAIL}</a></span>
        </p>
      </div>
    </footer>
  )
}
