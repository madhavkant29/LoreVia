"use client"

import Link from "next/link"
import type { Route } from "next"
import { usePathname } from "next/navigation"
import { BrandLockup } from "@/components/layout/BrandLockup"
import { SocialLinks } from "@/components/layout/SocialLinks"
import { LEGAL_EMAIL, SUPPORT_EMAIL } from "@/lib/constants/contact"
import { TRUST_RESOURCE_LINKS } from "@/lib/constants/trust"
import { shouldHideSiteFooter, shouldOffsetSiteFooterForDashboardShell } from "@/lib/routes"
import { useAuthStore } from "@/lib/stores/authStore"

export function SiteFooter() {
  const pathname = usePathname()
  const { user, hydrated } = useAuthStore()

  if (shouldHideSiteFooter(pathname)) return null

  const isLandingPage = pathname === "/"
  const isEditorialMarketingSurface = pathname === "/" || pathname?.startsWith("/compare") === true
  const isDashboardShellSurface = shouldOffsetSiteFooterForDashboardShell(pathname)

  const footerLinkClass =
    `group inline-flex items-center gap-3 rounded-sm px-0 py-0.5 text-[1.02rem] transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[rgba(var(--accent),0.45)] ${
      isEditorialMarketingSurface
        ? "text-[#f3ede4] hover:text-[#69c6b1]"
        : "text-stone-900 hover:text-[#1f615d] dark:text-[#f3ede4] dark:hover:text-[#69c6b1]"
    }`
  const pricingHref = hydrated && user ? "/upgrade" : "/pricing"
  const returnLink: { href: Route; label: string } = hydrated && user
    ? { href: "/library", label: "Return to library" }
    : { href: "/", label: "Return to landing page" }
  const footerDocs = TRUST_RESOURCE_LINKS.filter((link) => link.href !== "/status")
  const navigationLinks = [
    ...footerDocs.map((link) => ({ href: link.href, label: link.label, external: false as const })),
    { href: pricingHref, label: "Pricing", external: !(hydrated && user) },
    { href: "/compare", label: "Compare", external: false as const },
    { href: "/blog", label: "Blog", external: false as const },
    { href: "/answers", label: "Answers", external: false as const },
    { href: "/demo", label: "Demo", external: false as const },
    { href: "/font-notice", label: "Font Notice", external: false as const },
    { href: "/status", label: "Status", external: false as const },
  ]
  const navigationColumns = [navigationLinks.slice(0, 6), navigationLinks.slice(6)]

  return (
    <footer
      className={`border-t px-4 py-16 text-sm transition-colors sm:px-6 lg:px-8 ${isDashboardShellSurface ? "lg:ml-[15rem]" : ""} ${
        isEditorialMarketingSurface
          ? "border-white/[0.08] bg-[#08110f] text-[#d9e0db]"
          : "border-slate-200 bg-[#f6f5f3] text-[rgb(var(--foreground))] dark:border-slate-700/70 dark:bg-[#12171c]"
      }`}
    >
      <div className="mx-auto max-w-7xl">
        <div className="grid gap-10 xl:grid-cols-[minmax(0,1.1fr)_minmax(0,1.15fr)_minmax(0,0.8fr)_180px]">
          <div className="min-w-0">
            <BrandLockup size="xl" tone={isEditorialMarketingSurface ? "dark" : "auto"} />
            <p className={`mt-6 text-[1.05rem] ${isEditorialMarketingSurface ? "text-[#9fb0a8]" : "text-stone-600 dark:text-slate-300"}`}>LoreVia for authors</p>
            <p className={`mt-6 max-w-[340px] text-[1.02rem] leading-8 ${isEditorialMarketingSurface ? "text-[#aeb9b3]" : "text-stone-600 dark:text-slate-300"}`}>
              Manuscript intelligence, continuity control, and a calmer revision workspace for fiction authors.
            </p>
          </div>

          <div className="min-w-0">
            <p className={`text-3xs font-semibold uppercase tracking-[0.28em] ${isEditorialMarketingSurface ? "text-[#6fae9f]" : "text-stone-500 dark:text-slate-400"}`}>Navigation</p>
            <div className="mt-6 grid gap-8 sm:grid-cols-2">
              {navigationColumns.map((column, index) => (
                <div key={index} className="flex flex-col items-start gap-4">
                  {column.map((link) =>
                    link.external ? (
                      <a key={link.label} href={link.href} className={footerLinkClass}>
                        <span>{link.label}</span>
                        {isEditorialMarketingSurface ? null : <ArrowOutIcon />}
                      </a>
                    ) : (
                      <Link key={link.label} href={link.href as Route} className={footerLinkClass}>
                        <span>{link.label}</span>
                        {isEditorialMarketingSurface ? null : <ArrowOutIcon />}
                      </Link>
                    )
                  )}
                </div>
              ))}
            </div>

            {!isLandingPage ? (
              <div className={`mt-8 border-t pt-8 ${isEditorialMarketingSurface ? "border-white/[0.08]" : "border-slate-200 dark:border-slate-700/70"}`}>
                <Link href={returnLink.href} className={`group inline-flex items-center gap-4 text-[1.05rem] transition-colors ${isEditorialMarketingSurface ? "text-[#f3ede4] hover:text-[#69c6b1]" : "text-stone-900 hover:text-[#1f615d] dark:text-[#f3ede4] dark:hover:text-[#69c6b1]"}`}>
                  <span className={`flex h-10 w-10 items-center justify-center rounded-full border transition-colors ${
                    isEditorialMarketingSurface
                      ? "border-white/10 bg-[#0e1715] text-[#c9d1cb] group-hover:border-[#69c6b1] group-hover:text-[#69c6b1]"
                      : "border-slate-200 bg-[#f0ece7] text-stone-700 group-hover:border-[#76b4aa] group-hover:text-[#1f615d] dark:border-slate-700/70 dark:bg-[#182028] dark:text-slate-300 dark:group-hover:border-[#69c6b1] dark:group-hover:text-[#69c6b1]"
                  }`}>
                    <CornerArrowIcon />
                  </span>
                  <span>{returnLink.label}</span>
                </Link>
              </div>
            ) : null}
          </div>

          <div className="min-w-0">
            <p className={`text-3xs font-semibold uppercase tracking-[0.28em] ${isEditorialMarketingSurface ? "text-[#6fae9f]" : "text-stone-500 dark:text-slate-400"}`}>Contact</p>
            <div className="mt-6 space-y-6">
              <div className="flex items-start gap-4">
                <span className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-full border ${
                  isEditorialMarketingSurface
                    ? "border-white/10 bg-[#0e1715] text-[#c9d1cb]"
                    : "border-slate-200 bg-[#f0ece7] text-stone-700 dark:border-slate-700/70 dark:bg-[#182028] dark:text-slate-300"
                }`}>
                  <MailIcon />
                </span>
                <div className="min-w-0">
                  <p className={`text-[1.1rem] font-medium ${isEditorialMarketingSurface ? "text-white" : "text-stone-950 dark:text-[#f3ede4]"}`}>Support</p>
                  <a
                    href={`mailto:${SUPPORT_EMAIL}`}
                    className={`mt-1 inline-block break-all text-[1.05rem] transition-colors ${
                      isEditorialMarketingSurface
                        ? "text-[#aeb9b3] hover:text-[#69c6b1]"
                        : "text-stone-500 hover:text-[#1f615d] dark:text-slate-300 dark:hover:text-[#69c6b1]"
                    }`}
                  >
                    {SUPPORT_EMAIL}
                  </a>
                </div>
              </div>

              <div className={`border-t pt-6 ${isEditorialMarketingSurface ? "border-white/[0.08]" : "border-slate-200 dark:border-slate-700/70"}`}>
                <div className="flex items-start gap-4">
                  <span className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-full border ${
                    isEditorialMarketingSurface
                      ? "border-white/10 bg-[#0e1715] text-[#c9d1cb]"
                      : "border-slate-200 bg-[#f0ece7] text-stone-700 dark:border-slate-700/70 dark:bg-[#182028] dark:text-slate-300"
                  }`}>
                    <ShieldIcon />
                  </span>
                  <div className="min-w-0">
                    <p className={`text-[1.1rem] font-medium ${isEditorialMarketingSurface ? "text-white" : "text-stone-950 dark:text-[#f3ede4]"}`}>Legal</p>
                    <a
                      href={`mailto:${LEGAL_EMAIL}`}
                      className={`mt-1 inline-block break-all text-[1.05rem] transition-colors ${
                        isEditorialMarketingSurface
                          ? "text-[#aeb9b3] hover:text-[#69c6b1]"
                          : "text-stone-500 hover:text-[#1f615d] dark:text-slate-300 dark:hover:text-[#69c6b1]"
                      }`}
                    >
                      {LEGAL_EMAIL}
                    </a>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div className="min-w-0">
            <p className={`text-3xs font-semibold uppercase tracking-[0.28em] ${isEditorialMarketingSurface ? "text-[#6fae9f]" : "text-stone-500 dark:text-slate-400"}`}>Connect</p>
            <SocialLinks
              className="mt-6 flex items-center gap-3"
              linkClassName={`inline-flex h-11 w-11 items-center justify-center rounded-full border transition-colors ${
                isEditorialMarketingSurface
                  ? "border-white/[0.12] text-[#c9d1cb] hover:border-[#69c6b1] hover:text-[#69c6b1]"
                  : "border-slate-300 text-stone-700 hover:border-[#76b4aa] hover:text-[#1f615d] dark:border-slate-600 dark:text-slate-300 dark:hover:border-[#69c6b1] dark:hover:text-[#69c6b1]"
              }`}
            />
          </div>
        </div>

        <div className={`mt-14 border-t pt-8 ${isEditorialMarketingSurface ? "border-white/[0.08]" : "border-slate-200 dark:border-slate-700/70"}`}>
          <p className={`text-[1.05rem] ${isEditorialMarketingSurface ? "text-[#8fa19a]" : "text-stone-500 dark:text-slate-400"}`}>&copy; 2026 LoreVia</p>
        </div>
      </div>
    </footer>
  )
}

function ArrowOutIcon() {
  return (
    <svg className="h-5 w-5 shrink-0 transition-colors group-hover:text-[#69c6b1] text-current" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
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
