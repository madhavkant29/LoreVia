"use client"

import Link from "next/link"
import type { Route } from "next"
import { usePathname } from "next/navigation"
import { BrandLockup } from "@/components/layout/BrandLockup"
import { SocialLinks } from "@/components/layout/SocialLinks"
import { LEGAL_EMAIL, SUPPORT_EMAIL } from "@/lib/constants/contact"
import { TRUST_RESOURCE_LINKS } from "@/lib/constants/trust"
import { useAuthStore } from "@/lib/stores/authStore"

export function SiteFooter() {
  const pathname = usePathname()
  const { user, hydrated } = useAuthStore()

  if (pathname?.includes("/chapter/")) return null

  const footerLinkClass =
    "rounded-full px-3 py-1.5 -mx-1 -my-1.5 text-sm transition-all hover:bg-white/10 hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white/40"
  const pricingHref = hydrated && user ? "/upgrade" : "/pricing"
  const returnLink: { href: Route; label: string } = hydrated && user
    ? { href: "/library", label: "Return to library" }
    : { href: "/", label: "Return to landing page" }
  const footerDocs = TRUST_RESOURCE_LINKS.filter((link) => link.href !== "/status")

  return (
    <footer className="border-t border-white/10 bg-[#050814] px-4 py-14 text-sm text-white transition-colors">
      <div className="mx-auto flex max-w-7xl flex-col gap-8 lg:flex-row lg:items-end lg:justify-between">
        <div className="max-w-xl">
          <div>
            <BrandLockup size="md" iconClassName="h-11 w-11 rounded-2xl" />
            <p className="mt-2 text-sm text-white/60">LoreVia for authors</p>
          </div>
          <p className="mt-5 max-w-lg text-base leading-7 text-white/70">
            Built for manuscript drafting, revision, continuity control, and the authors who need a dependable memory for every story detail.
          </p>
        </div>

        <div className="flex flex-col gap-6">
          <div className="flex flex-wrap gap-3">
            {footerDocs.map((link) => (
              <Link key={link.href} href={link.href} className={footerLinkClass}>
                {link.label}
              </Link>
            ))}
            {hydrated && user ? (
              <Link href={pricingHref as Route} className={footerLinkClass}>
                Pricing
              </Link>
            ) : (
              <a href={pricingHref} className={footerLinkClass}>
                Pricing
              </a>
            )}
            <Link href="/blog" className={footerLinkClass}>
              Blog
            </Link>
            <Link href="/answers" className={footerLinkClass}>
              Answers
            </Link>
            <Link href="/demo" className={footerLinkClass}>
              Demo
            </Link>
            <Link href="/status" className={footerLinkClass}>
              Status
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
