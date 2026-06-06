"use client"

import Link from "next/link"
import type { Route } from "next"
import { Children } from "react"
import type { ReactNode } from "react"

import { BrandLockup } from "@/components/layout/BrandLockup"
import { LEGAL_EMAIL, SUPPORT_EMAIL } from "@/lib/constants/contact"
import { useAuthStore } from "@/lib/stores/authStore"

export type LegalSectionContent = {
  id?: string
  title: string
  paragraphs?: ReadonlyArray<string>
  body?: string
  bullets?: ReadonlyArray<string>
}

export type LegalRailItem = {
  label: string
  value: string
  detail?: string
  href?: string
}

type LegalPageShellProps = {
  eyebrow: string
  title: string
  description: string
  effectiveDate?: string
  notice?: string
  sections?: ReadonlyArray<LegalSectionContent>
  tableOfContents?: boolean
  rightRail?: ReactNode
  contactBlock?: ReactNode
  maxWidth?: "document" | "wide"
  children?: ReactNode
}

const legalAccent = "text-teal-800"
const legalLink =
  "text-teal-800 underline-offset-4 transition hover:text-teal-700 hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-teal-800/40"

function sectionId(section: LegalSectionContent, index: number) {
  return section.id ?? `section-${index + 1}`
}

export function LegalTopBar() {
  const { user, hydrated } = useAuthStore()
  const isLoggedIn = hydrated && Boolean(user)

  return (
    <header className="border-b border-[rgba(var(--border),0.9)] bg-[#f8f4ee]">
      <nav className="mx-auto flex h-16 max-w-7xl items-center justify-between px-5 sm:px-8 lg:px-10">
        <Link
          href={(isLoggedIn ? "/library" : "/") as Route}
          className="transition hover:opacity-80 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-teal-800/30"
        >
          <BrandLockup size="sm" />
        </Link>

        {isLoggedIn ? (
          <Link href="/library" className="text-sm text-stone-600 transition hover:text-stone-950">
            Return to library
          </Link>
        ) : (
          <div className="flex items-center gap-6 text-sm text-stone-600">
            <Link href="/login" className="transition hover:text-stone-950">
              Login
            </Link>
            <Link href="/" className="transition hover:text-stone-950">
              Home
            </Link>
          </div>
        )}
      </nav>
    </header>
  )
}

export function LegalHero({
  eyebrow,
  title,
  description,
  effectiveDate,
  notice,
}: Pick<LegalPageShellProps, "eyebrow" | "title" | "description" | "effectiveDate" | "notice">) {
  return (
    <section className="py-14 sm:py-18">
      <p className={`text-3xs font-semibold uppercase tracking-[0.32em] ${legalAccent}`}>{eyebrow}</p>
      <h1 className="mt-5 max-w-4xl text-[2.55rem] font-semibold leading-[1.02] tracking-[-0.045em] text-stone-950 sm:text-[3.45rem] lg:text-[3.75rem]">
        {title}
      </h1>
      {effectiveDate ? (
        <p className="mt-6 text-sm leading-7 text-stone-500">Effective date: {effectiveDate}</p>
      ) : null}
      <p className="mt-6 max-w-3xl text-[1.02rem] leading-8 text-stone-600">{description}</p>
      {notice ? <LegalNotice>{notice}</LegalNotice> : null}
    </section>
  )
}

export function LegalNotice({ children }: { children: ReactNode }) {
  return (
    <div className="mt-8 max-w-3xl rounded-xl border border-[rgba(var(--border),0.9)] bg-[rgba(255,252,247,0.94)] px-5 py-4 text-sm leading-7 text-stone-700">
      {children}
    </div>
  )
}

export function LegalTableOfContents({ sections }: { sections: ReadonlyArray<LegalSectionContent> }) {
  return (
    <nav aria-labelledby="legal-toc" className="border-t border-[rgba(var(--border),0.9)] py-8">
      <h2 id="legal-toc" className="text-3xs font-semibold uppercase tracking-[0.32em] text-stone-500">
        Table of contents
      </h2>
      <ol className="mt-6 grid gap-x-12 gap-y-4 md:grid-cols-2">
        {sections.map((section, index) => {
          const id = sectionId(section, index)
          const number = String(index + 1).padStart(2, "0")

          return (
            <li key={`toc-${id}`}>
              <a
                href={`#${id}`}
                className="group grid grid-cols-[2.5rem_1fr] gap-4 text-base leading-7 text-stone-600 transition hover:text-stone-950"
              >
                <span className={legalAccent}>{number}</span>
                <span>{section.title}</span>
              </a>
            </li>
          )
        })}
      </ol>
    </nav>
  )
}

export function LegalSection({ section, index }: { section: LegalSectionContent; index: number }) {
  const number = String(index + 1).padStart(2, "0")
  const paragraphs = section.paragraphs ?? (section.body ? [section.body] : [])

  return (
    <section id={sectionId(section, index)} className="scroll-mt-20 border-t border-[rgba(var(--border),0.9)] py-10">
      <div className="grid gap-4 md:grid-cols-[56px_1fr]">
        <div className={`text-sm md:text-xl ${legalAccent}`}>{number}</div>
        <div>
          <h2 className="text-2xl font-semibold leading-tight tracking-[-0.02em] text-stone-950 sm:text-[1.7rem]">
            {section.title}
          </h2>
          <div className="mt-5 space-y-4 text-[15.5px] leading-8 text-stone-600">
            {paragraphs.map((paragraph, paragraphIndex) => (
              <p key={`paragraph-${index}-${paragraphIndex}`}>{paragraph}</p>
            ))}
          </div>
          {section.bullets?.length ? (
            <ul className="mt-6 space-y-3 text-[15.5px] leading-8 text-stone-600">
              {section.bullets.map((bullet, bulletIndex) => (
                <li key={`bullet-${index}-${bulletIndex}`} className="flex gap-3">
                  <span className={`mt-0.5 ${legalAccent}`} aria-hidden="true">
                    -
                  </span>
                  <span>{bullet}</span>
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      </div>
    </section>
  )
}

export function LegalRightRail({ items }: { items: ReadonlyArray<LegalRailItem> }) {
  return (
    <aside className="rounded-xl border border-[rgba(var(--border),0.9)] bg-[rgba(255,252,247,0.94)] px-5 py-2 lg:sticky lg:top-6">
      {items.map((item, index) => {
        const content = (
          <>
            <p className="text-3xs font-semibold uppercase tracking-[0.28em] text-stone-500">{item.label}</p>
            <p className="mt-3 break-words text-base font-medium text-stone-950">{item.value}</p>
            {item.detail ? <p className="mt-2 text-sm leading-6 text-stone-600">{item.detail}</p> : null}
          </>
        )

        return (
          <div key={`rail-item-${index}-${item.label}`} className="border-b border-[rgba(var(--border),0.9)] py-5 last:border-b-0">
            {item.href ? (
              <a href={item.href} className="block rounded-md outline-none transition hover:text-stone-950 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-teal-800/40">
                {content}
              </a>
            ) : (
              content
            )}
          </div>
        )
      })}
    </aside>
  )
}

export function LegalContactBlock({
  title = "Need help?",
  description = "If you have questions about this page, your account, or LoreVia policies, contact us.",
  supportEmail = SUPPORT_EMAIL,
  legalEmail = LEGAL_EMAIL,
}: {
  title?: string
  description?: string
  supportEmail?: string
  legalEmail?: string
}) {
  return (
    <section className="mt-4 border-t border-[rgba(var(--border),0.9)] py-10">
      <div className="rounded-xl border border-[rgba(var(--border),0.9)] bg-[rgba(255,252,247,0.94)] px-5 py-6 sm:px-6">
        <h2 className="text-xl font-semibold text-stone-950">{title}</h2>
        <p className="mt-3 max-w-2xl text-[15.5px] leading-8 text-stone-600">{description}</p>
        <div className="mt-5 flex flex-wrap gap-x-6 gap-y-3 text-sm">
          <a href={`mailto:${supportEmail}`} className={legalLink}>
            {supportEmail}
          </a>
          <a href={`mailto:${legalEmail}`} className={legalLink}>
            {legalEmail}
          </a>
        </div>
      </div>
    </section>
  )
}

export function LegalPageShell({
  eyebrow,
  title,
  description,
  effectiveDate,
  notice,
  sections = [],
  tableOfContents = true,
  rightRail,
  contactBlock,
  maxWidth = "document",
  children,
}: LegalPageShellProps) {
  const hasRail = Boolean(rightRail)
  const normalizedChildren = Children.toArray(children)
  const normalizedRightRail = Children.toArray(rightRail)
  const normalizedContactBlock = Children.toArray(contactBlock ?? <LegalContactBlock />)
  const widthClassName = maxWidth === "wide" || hasRail ? "max-w-6xl" : "max-w-[900px]"

  return (
    <main className="min-h-screen bg-[#f8f4ee] text-stone-950">
      <LegalTopBar />
      <div className={`mx-auto ${widthClassName} px-5 pb-16 sm:px-8 lg:px-10`}>
        <LegalHero
          eyebrow={eyebrow}
          title={title}
          description={description}
          effectiveDate={effectiveDate}
          notice={notice}
        />

        {normalizedChildren.length > 0 ? (
          <div className={hasRail ? "grid gap-12 lg:grid-cols-[minmax(0,1fr)_300px] lg:items-start" : undefined}>
            <div>{normalizedChildren}</div>
            {normalizedRightRail}
          </div>
        ) : (
          <div className={hasRail ? "grid gap-12 lg:grid-cols-[minmax(0,1fr)_300px] lg:items-start" : undefined}>
            <div>
              {tableOfContents && sections.length > 3 ? <LegalTableOfContents sections={sections} /> : null}
              {sections.map((section, index) => {
                const id = sectionId(section, index)

                return <LegalSection key={`section-${id}`} section={section} index={index} />
              })}
              {normalizedContactBlock}
            </div>
            {normalizedRightRail}
          </div>
        )}
      </div>
    </main>
  )
}
