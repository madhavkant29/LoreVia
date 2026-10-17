"use client"

import Link from "next/link"
import type { Route } from "next"
import type { UrlObject } from "url"
import { useRef, useState } from "react"

import { AuthLink } from "@/components/auth/AuthLink"
import { BrandLockup } from "@/components/layout/BrandLockup"

const navItems: Array<{ label: string; href: Route | UrlObject }> = [
  { label: "Features", href: { pathname: "/", hash: "features" } },
  { label: "How it works", href: { pathname: "/", hash: "workflow" } },
  { label: "Compare", href: "/compare" },
  { label: "Pricing", href: { pathname: "/", hash: "pricing" } },
  { label: "Resources", href: "/blog" },
]

export function MarketingHeader() {
  const [mobileNavOpen, setMobileNavOpen] = useState(false)
  const mobileNavButtonRef = useRef<HTMLButtonElement>(null)

  return (
    <header
      className="sticky top-0 z-50 border-b border-white/[0.08] bg-[#08110f]"
      onKeyDown={(event) => {
        if (event.key === "Escape" && mobileNavOpen) {
          setMobileNavOpen(false)
          mobileNavButtonRef.current?.focus()
        }
      }}
    >
      <div className="mx-auto flex h-[76px] max-w-7xl items-center justify-between gap-3 px-4 sm:px-5 md:px-8">
        <Link href="/" aria-label="LoreVia home" className="shrink-0">
          <BrandLockup size="md" tone="dark" />
        </Link>

        <nav aria-label="Primary navigation" className="hidden items-center gap-8 lg:flex">
          {navItems.map((item) => (
            <Link
              key={item.label}
              href={item.href}
              className="text-sm font-medium text-[#c9d1cb] transition hover:text-white"
            >
              {item.label}
            </Link>
          ))}
        </nav>

        <div className="flex shrink-0 items-center gap-2 sm:gap-3">
          <button
            ref={mobileNavButtonRef}
            type="button"
            className="inline-flex h-10 w-10 items-center justify-center border border-white/[0.12] text-[#f4f1ea] transition hover:bg-white/[0.06] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#86decd] lg:hidden"
            aria-label={mobileNavOpen ? "Close navigation menu" : "Open navigation menu"}
            aria-expanded={mobileNavOpen}
            aria-controls="marketing-mobile-navigation"
            onClick={() => setMobileNavOpen((open) => !open)}
          >
            <svg aria-hidden="true" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
              {mobileNavOpen ? <path strokeLinecap="round" d="M6 6l12 12M18 6 6 18" /> : <path strokeLinecap="round" d="M4 7h16M4 12h16M4 17h16" />}
            </svg>
          </button>
          <AuthLink
            href="/login"
            className="inline-flex px-1 py-2 text-sm font-medium text-[#c9d1cb] transition hover:text-white sm:px-4"
          >
            Sign in
          </AuthLink>
          <AuthLink
            href="/register"
            className="inline-flex items-center justify-center rounded-md bg-[#1f615d] px-3 py-2.5 text-sm font-semibold text-white transition hover:bg-[#25756f] sm:px-4"
          >
            <span className="sm:hidden">Start free</span>
            <span className="hidden sm:inline">Analyze my manuscript</span>
          </AuthLink>
        </div>
      </div>
      <nav
        id="marketing-mobile-navigation"
        aria-label="Mobile primary navigation"
        className="border-t border-white/[0.08] lg:hidden"
        hidden={!mobileNavOpen}
      >
        <div className="mx-auto grid max-w-7xl px-4 sm:px-5 md:px-8">
          {navItems.map((item) => (
            <Link
              key={item.label}
              href={item.href}
              className="border-b border-white/[0.08] py-3.5 text-sm font-medium text-[#d7ddd8] transition hover:text-white last:border-b-0"
              onClick={() => setMobileNavOpen(false)}
            >
              {item.label}
            </Link>
          ))}
        </div>
      </nav>
    </header>
  )
}
