"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { SocialLinks } from "@/components/layout/SocialLinks"
import { LEGAL_EMAIL, SUPPORT_EMAIL } from "@/lib/constants/contact"

export function SiteFooter() {
  const pathname = usePathname()

  if (pathname?.includes("/chapter/")) return null

  const footerLinkClass =
    "rounded-md px-2 py-1 -mx-2 -my-1 transition-all hover:bg-white/10 hover:text-white hover:underline underline-offset-4 decoration-white/35 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white/40"

  return (
    <footer className="border-t border-zinc-800 bg-zinc-900 px-4 py-10 text-[11px] font-medium tracking-tight text-white transition-colors">
      <div className="mx-auto flex max-w-7xl flex-col items-center gap-6 text-center sm:flex-row sm:items-start sm:justify-between sm:text-left">
        <div className="flex flex-col items-center gap-4 sm:items-start">
          <div className="flex flex-col items-center gap-4 sm:flex-row sm:items-start">
            <p className="flex items-center gap-2">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-brand-500" />
              Support:{" "}
              <a
                href={`mailto:${SUPPORT_EMAIL}`}
                className={footerLinkClass}
              >
                {SUPPORT_EMAIL}
              </a>
            </p>
            <p className="flex items-center gap-2">
              Legal:{" "}
              <a
                href={`mailto:${LEGAL_EMAIL}`}
                className={footerLinkClass}
              >
                {LEGAL_EMAIL}
              </a>
            </p>
          </div>
        </div>
        <SocialLinks
          className="flex items-center gap-2"
          linkClassName="inline-flex h-8 w-8 items-center justify-center rounded-full border border-white/15 text-white transition-colors hover:border-white/40 hover:text-white"
        />
        <div className="flex flex-col items-center gap-3 sm:flex-row sm:items-center sm:gap-x-6">
          <div className="flex flex-wrap justify-center gap-x-4 gap-y-2">
            <Link href="/contact" className={footerLinkClass}>
              Contact
            </Link>
            <Link href="/terms" className={footerLinkClass}>
              Terms
            </Link>
            <Link href="/privacy" className={footerLinkClass}>
              Privacy
            </Link>
            <Link href="/compliance" className={footerLinkClass}>
              Compliance
            </Link>
            <Link href="/refund" className={footerLinkClass}>
              Refund
            </Link>
            <Link href="/eula" className={footerLinkClass}>
              EULA
            </Link>
          </div>
          <p className="text-white/60">
            © {new Date().getFullYear()} LoreVia
          </p>
        </div>
      </div>
    </footer>
  )
}
