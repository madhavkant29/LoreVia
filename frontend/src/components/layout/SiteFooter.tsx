"use client"

import Link from "next/link"
import type { Route } from "next"
import { usePathname } from "next/navigation"
import { SocialLinks } from "@/components/layout/SocialLinks"
import { LEGAL_EMAIL, SUPPORT_EMAIL } from "@/lib/constants/contact"
import { useAuthStore } from "@/lib/stores/authStore"

export function SiteFooter() {
  const pathname = usePathname()
  const { user, hydrated } = useAuthStore()

  if (pathname?.includes("/chapter/")) return null

  const footerLinkClass =
    "rounded-full px-3 py-1.5 -mx-1 -my-1.5 text-sm transition-all hover:bg-white/10 hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white/40"
  const returnLink: { href: Route; label: string } = hydrated && user
    ? { href: "/library", label: "Return to library" }
    : { href: "/", label: "Return to landing page" }

  return (
    <footer className="border-t border-white/10 bg-[#050814] px-4 py-14 text-sm text-white transition-colors">
      <div className="mx-auto flex max-w-7xl flex-col gap-8 lg:flex-row lg:items-end lg:justify-between">
        <div className="max-w-xl">
          <div className="flex items-center gap-3">
            <img src="/image.png" alt="LoreVia" className="h-11 w-11 rounded-2xl object-cover" />
            <div>
              <p className="text-sm font-semibold tracking-[0.3em]">LOREVIA</p>
              <p className="text-sm text-white/60">Manuscript intelligence for readers and authors</p>
            </div>
          </div>
          <p className="mt-5 max-w-lg text-base leading-7 text-white/70">
            Built for long books, real continuity work, and people who want a calmer way to work through a story.
          </p>
        </div>

        <div className="flex flex-col gap-6">
          <div className="flex flex-wrap gap-3">
            <Link href="/contact" className={footerLinkClass}>
              Contact
            </Link>
            <Link href="/terms" className={footerLinkClass}>
              Terms
            </Link>
            <Link href="/privacy" className={footerLinkClass}>
              Privacy
            </Link>
            <Link href="/pricing" className={footerLinkClass}>
              Pricing
            </Link>
            <Link href="/status" className={footerLinkClass}>
              Status
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
            <Link href={returnLink.href} className={footerLinkClass}>
              {returnLink.label}
            </Link>
          </div>

          <div className="flex flex-wrap items-center gap-5">
            <p className="text-white/70">
              Support:{" "}
              <a href={`mailto:${SUPPORT_EMAIL}`} className={footerLinkClass}>
                {SUPPORT_EMAIL}
              </a>
            </p>
            <p className="text-white/70">
              Legal:{" "}
              <a href={`mailto:${LEGAL_EMAIL}`} className={footerLinkClass}>
                {LEGAL_EMAIL}
              </a>
            </p>
            <SocialLinks
              className="flex items-center gap-2"
              linkClassName="inline-flex h-10 w-10 items-center justify-center rounded-full border border-white/15 text-white transition-colors hover:border-white/40 hover:text-white"
            />
          </div>

          <p className="text-sm text-white/50">&copy; {new Date().getFullYear()} LoreVia</p>
        </div>
      </div>
    </footer>
  )
}
