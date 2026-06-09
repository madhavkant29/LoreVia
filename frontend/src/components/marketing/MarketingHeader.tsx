"use client"

import Link from "next/link"
import type { Route } from "next"
import type { UrlObject } from "url"

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
  const ctaHref: Route = "/register"

  return (
    <header className="sticky top-0 z-50 border-b border-white/8 bg-[#08110f]">
      <div className="mx-auto flex h-[76px] max-w-7xl items-center justify-between px-5 md:px-8">
        <Link href="/" aria-label="LoreVia home" className="shrink-0">
          <BrandLockup size="md" tone="dark" />
        </Link>

        <nav className="hidden items-center gap-8 lg:flex">
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

        <div className="flex items-center gap-3">
          <AuthLink
            href="/login"
            className="hidden px-4 py-2 text-sm font-medium text-[#c9d1cb] transition hover:text-white sm:inline-flex"
          >
            Sign in
          </AuthLink>
          <AuthLink
            href="/register"
            className="inline-flex items-center justify-center rounded-md bg-[#1f615d] px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-[#25756f]"
          >
            Start free
          </AuthLink>
        </div>
      </div>
    </header>
  )
}
