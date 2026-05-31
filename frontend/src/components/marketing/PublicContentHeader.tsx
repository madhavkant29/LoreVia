import Link from "next/link"
import { ThemeBrandImage } from "@/components/layout/ThemeBrandImage"

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
    <header className="sticky top-0 z-30 border-b border-[rgba(var(--border),0.82)] bg-[rgba(243,244,246,0.9)] backdrop-blur-xl dark:bg-[rgba(23,27,29,0.88)]">
      <div className="app-container flex h-[78px] items-center justify-between gap-4">
        <Link href="/" aria-label="LoreVia home" className="transition hover:opacity-90">
          <ThemeBrandImage variant="lockup" alt="LoreVia" className="h-10 w-auto" priority />
        </Link>

        <nav className="hidden items-center gap-3 md:flex">
          {navItems.map((item) => {
            const isActive = item.key === activeSection
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`rounded-full px-4 py-2 text-sm font-medium transition ${
                  isActive
                    ? "border border-[rgba(var(--border),0.84)] bg-white text-foreground shadow-[0_10px_24px_-22px_rgba(15,23,42,0.4)] dark:bg-white/10"
                    : "text-foreground/70 hover:bg-white/70 hover:text-foreground dark:hover:bg-white/5"
                }`}
              >
                {item.label}
              </Link>
            )
          })}
        </nav>

        <div className="flex items-center gap-3">
          <Link href="/login" className="hidden text-sm font-medium text-foreground/70 transition hover:text-foreground sm:inline-flex">
            Sign in
          </Link>
          <Link href="/register" className="app-button-primary gap-2 px-4 py-2.5 text-sm">
            Start free
            <ArrowIcon />
          </Link>
        </div>
      </div>
    </header>
  )
}

export function ContentArrowIcon() {
  return <ArrowIcon />
}
