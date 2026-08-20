import Link from "next/link"
import { ThemeBrandImage } from "@/components/layout/ThemeBrandImage"
import { PublicThemeToggle } from "./PublicThemeToggle"

function ArrowIcon() {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="h-4 w-4"
    >
      <path d="M5 12h14" />
      <path d="m13 6 6 6-6 6" />
    </svg>
  )
}

export function PublicContentHeader({
  activeSection,
}: {
  activeSection: "blog" | "answers" | "demo"
}) {
  const navItems = [
    { href: "/blog", label: "Blog", key: "blog" },
    { href: "/answers", label: "Answers", key: "answers" },
    { href: "/demo", label: "Demo", key: "demo" },
    { href: "/pricing", label: "Pricing", key: "pricing" },
  ] as const

  return (
    <header className="editorial-site-header">
      <div className="editorial-site-header__inner">
        <Link href="/" aria-label="LoreVia home" className="transition hover:opacity-90">
          <ThemeBrandImage variant="lockup" alt="LoreVia" className="h-8 w-auto sm:h-9" priority />
        </Link>

        <nav className="editorial-site-nav" aria-label="Editorial navigation">
          {navItems.map((item) => {
            const isActive = item.key === activeSection
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`${item.key === "demo" || item.key === "pricing" ? "hidden md:inline-flex" : "inline-flex"} editorial-site-nav__link ${
                  isActive
                    ? "editorial-site-nav__link--active"
                    : ""
                }`}
              >
                {item.label}
              </Link>
            )
          })}
        </nav>

        <div className="flex items-center gap-2 sm:gap-3">
          <PublicThemeToggle />
          <Link href="/login" className="hidden text-sm font-medium text-foreground/70 transition hover:text-foreground sm:inline-flex">
            Sign in
          </Link>
          <Link href="/register" className="editorial-header-cta">
            Start free
            <span className="hidden sm:inline"><ArrowIcon /></span>
          </Link>
        </div>
      </div>
    </header>
  )
}

export function ContentArrowIcon() {
  return <ArrowIcon />
}
