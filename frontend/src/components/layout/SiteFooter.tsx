"use client"

import Link from "next/link"
import type { Route } from "next"
import { usePathname } from "next/navigation"
import { BrandLockup } from "@/components/layout/BrandLockup"
import { SocialLinks } from "@/components/layout/SocialLinks"
import { LEGAL_EMAIL, SUPPORT_EMAIL } from "@/lib/constants/contact"
import { TRUST_RESOURCE_LINKS } from "@/lib/constants/trust"
import { shouldHideSiteFooter } from "@/lib/routes"
import { useAuthStore } from "@/lib/stores/authStore"

export function SiteFooter() {
  const pathname = usePathname()
  const { user, hydrated } = useAuthStore()

  if (shouldHideSiteFooter(pathname)) return null

  const footerLinkClass =
    "group flex items-center justify-between gap-6 rounded-[0.9rem] px-0 py-0.5 text-[1.05rem] text-stone-900 transition-colors hover:text-[#1f615d] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[rgba(var(--accent),0.45)] dark:text-[#f3ede4] dark:hover:text-[#69c6b1]"
  const pricingHref = hydrated && user ? "/upgrade" : "/pricing"
  const returnLink: { href: Route; label: string } = hydrated && user
    ? { href: "/library", label: "Return to library" }
    : { href: "/", label: "Return to landing page" }
  const footerDocs = TRUST_RESOURCE_LINKS.filter((link) => link.href !== "/status")
  const navigationLinks = [
    ...footerDocs.map((link) => ({ href: link.href, label: link.label, external: false as const })),
    { href: pricingHref, label: "Pricing", external: !(hydrated && user) },
    { href: "/blog", label: "Blog", external: false as const },
    { href: "/answers", label: "Answers", external: false as const },
    { href: "/demo", label: "Demo", external: false as const },
    { href: "/status", label: "Status", external: false as const },
  ]
  const navigationColumns = [navigationLinks.slice(0, 6), navigationLinks.slice(6)]

  return (
    <footer className="border-t border-slate-200 bg-[#f6f5f3] px-4 py-16 text-sm text-[rgb(var(--foreground))] transition-colors dark:border-slate-700/70 dark:bg-[#12171c] sm:px-6 lg:px-8">
      <div className="mx-auto max-w-7xl">
        <div className="grid gap-12 xl:grid-cols-[minmax(0,1.1fr)_minmax(0,1.25fr)_minmax(0,0.85fr)_220px]">
          <div className="min-w-0">
            <BrandLockup size="xl" />
            <p className="mt-6 text-[1.05rem] text-stone-600 dark:text-slate-300">LoreVia for authors</p>
            <p className="mt-8 max-w-[360px] text-[1.1rem] leading-[2.2rem] text-stone-600 dark:text-slate-300">
              Manuscript intelligence, continuity control, and a calmer revision workspace for fiction authors.
            </p>
          </div>

          <div className="min-w-0">
            <p className="text-[11px] font-semibold uppercase tracking-[0.28em] text-stone-500 dark:text-slate-400">Navigation</p>
            <div className="mt-8 grid gap-10 sm:grid-cols-2">
              {navigationColumns.map((column, index) => (
                <div key={index} className="space-y-5">
                  {column.map((link) =>
                    link.external ? (
                      <a key={link.label} href={link.href} className={footerLinkClass}>
                        <span>{link.label}</span>
                        <ArrowOutIcon />
                      </a>
                    ) : (
                      <Link key={link.label} href={link.href as Route} className={footerLinkClass}>
                        <span>{link.label}</span>
                        <ArrowOutIcon />
                      </Link>
                    )
                  )}
                </div>
              ))}
            </div>

            <div className="mt-8 border-t border-slate-200 pt-8 dark:border-slate-700/70">
              <Link href={returnLink.href} className="group inline-flex items-center gap-4 text-[1.05rem] text-stone-900 transition-colors hover:text-[#1f615d] dark:text-[#f3ede4] dark:hover:text-[#69c6b1]">
                <span className="flex h-10 w-10 items-center justify-center rounded-full border border-slate-200 bg-[#f0ece7] text-stone-700 transition-colors group-hover:border-[#76b4aa] group-hover:text-[#1f615d] dark:border-slate-700/70 dark:bg-[#182028] dark:text-slate-300 dark:group-hover:border-[#69c6b1] dark:group-hover:text-[#69c6b1]">
                  <CornerArrowIcon />
                </span>
                <span>{returnLink.label}</span>
              </Link>
            </div>
          </div>

          <div className="min-w-0">
            <p className="text-[11px] font-semibold uppercase tracking-[0.28em] text-stone-500 dark:text-slate-400">Contact</p>
            <div className="mt-8 space-y-8">
              <div className="flex items-start gap-4">
                <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full border border-slate-200 bg-[#f0ece7] text-stone-700 dark:border-slate-700/70 dark:bg-[#182028] dark:text-slate-300">
                  <MailIcon />
                </span>
                <div className="min-w-0">
                  <p className="text-[1.1rem] font-medium text-stone-950 dark:text-[#f3ede4]">Support</p>
                  <a
                    href={`mailto:${SUPPORT_EMAIL}`}
                    className="mt-1 inline-block break-all text-[1.05rem] text-stone-500 transition-colors hover:text-[#1f615d] dark:text-slate-300 dark:hover:text-[#69c6b1]"
                  >
                    {SUPPORT_EMAIL}
                  </a>
                </div>
              </div>

              <div className="border-t border-slate-200 pt-8 dark:border-slate-700/70">
                <div className="flex items-start gap-4">
                  <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full border border-slate-200 bg-[#f0ece7] text-stone-700 dark:border-slate-700/70 dark:bg-[#182028] dark:text-slate-300">
                    <ShieldIcon />
                  </span>
                  <div className="min-w-0">
                    <p className="text-[1.1rem] font-medium text-stone-950 dark:text-[#f3ede4]">Legal</p>
                    <a
                      href={`mailto:${LEGAL_EMAIL}`}
                      className="mt-1 inline-block break-all text-[1.05rem] text-stone-500 transition-colors hover:text-[#1f615d] dark:text-slate-300 dark:hover:text-[#69c6b1]"
                    >
                      {LEGAL_EMAIL}
                    </a>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div className="min-w-0">
            <p className="text-[11px] font-semibold uppercase tracking-[0.28em] text-stone-500 dark:text-slate-400">Connect</p>
            <SocialLinks
              className="mt-8 flex items-center gap-4"
              linkClassName="inline-flex h-14 w-14 items-center justify-center rounded-full border border-slate-300 text-stone-700 transition-colors hover:border-[#76b4aa] hover:text-[#1f615d] dark:border-slate-600 dark:text-slate-300 dark:hover:border-[#69c6b1] dark:hover:text-[#69c6b1]"
            />
          </div>
        </div>

        <div className="mt-14 border-t border-slate-200 pt-8 dark:border-slate-700/70">
          <p className="text-[1.05rem] text-stone-500 dark:text-slate-400">&copy; 2026 LoreVia</p>
        </div>
      </div>
    </footer>
  )
}

function ArrowOutIcon() {
  return (
    <svg className="h-5 w-5 shrink-0 text-stone-500 transition-colors group-hover:text-[#1f615d] dark:text-slate-400 dark:group-hover:text-[#69c6b1]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M6 12h12M13 5l7 7-7 7" />
    </svg>
  )
}

function CornerArrowIcon() {
  return (
    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M8 16V8h8M8 8l8 8" />
    </svg>
  )
}

function MailIcon() {
  return (
    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
      <rect x="3.75" y="5.5" width="16.5" height="13" rx="2.2" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 7l7.5 6 7.5-6" />
    </svg>
  )
}

function ShieldIcon() {
  return (
    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 4l6.5 2.8v4.6c0 4.1-2.4 7-6.5 8.6-4.1-1.6-6.5-4.5-6.5-8.6V6.8L12 4z" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v5" />
    </svg>
  )
}
