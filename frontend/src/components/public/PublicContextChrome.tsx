"use client"

import { ArrowLeft, BookOpen, MessageCircle, Moon, Sun } from "lucide-react"
import Image from "next/image"
import Link from "next/link"

import { usePreferencesStore } from "@/lib/stores/preferencesStore"

export function PublicContextChrome() {
  const theme = usePreferencesStore((state) => state.theme)
  const toggleTheme = usePreferencesStore((state) => state.toggleTheme)

  return (
    <header className="border-b border-[rgba(var(--border),0.75)] bg-[rgb(var(--background))]">
      <nav aria-label="Public navigation" className="mx-auto flex min-h-16 max-w-[1240px] items-center gap-3 px-4 md:px-8 lg:px-10">
        <Link href="/public" className="mr-auto inline-flex min-h-11 items-center" aria-label="LoreVia public library">
          <Image src="/image.png" alt="LoreVia" width={44} height={44} className="h-10 w-10 object-contain invert dark:invert-0 sm:hidden" priority />
          <Image src="/logoandtext.png" alt="" width={164} height={44} className="hidden h-11 w-auto object-contain invert dark:invert-0 sm:block" priority />
        </Link>
        <div className="hidden items-center gap-1 sm:flex">
          <Link href="/public" className="inline-flex min-h-11 items-center gap-2 px-3 text-sm font-semibold text-[rgb(var(--muted-foreground))] hover:text-[rgb(var(--foreground))]">
            <BookOpen className="h-4 w-4" aria-hidden="true" />
            Library
          </Link>
          <Link href="/public/forum" className="inline-flex min-h-11 items-center gap-2 px-3 text-sm font-semibold text-[rgb(var(--muted-foreground))] hover:text-[rgb(var(--foreground))]">
            <MessageCircle className="h-4 w-4" aria-hidden="true" />
            Book discussions
          </Link>
        </div>
        <button
          type="button"
          onClick={toggleTheme}
          className="inline-flex h-11 w-11 shrink-0 items-center justify-center text-[rgb(var(--muted-foreground))] hover:text-[rgb(var(--foreground))] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[rgb(var(--accent))]"
          aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
        >
          {theme === "dark" ? <Sun className="h-5 w-5" aria-hidden="true" /> : <Moon className="h-5 w-5" aria-hidden="true" />}
        </button>
        <Link href="/library" className="inline-flex min-h-11 shrink-0 items-center gap-2 text-sm font-semibold text-[rgb(var(--foreground))] hover:text-[rgb(var(--accent))]">
          <ArrowLeft className="h-4 w-4" aria-hidden="true" />
          <span className="hidden sm:inline">Private workspace</span>
          <span className="sm:hidden">Workspace</span>
        </Link>
      </nav>
    </header>
  )
}
