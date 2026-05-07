import Link from "next/link"
import type { Route } from "next"

import { TRUST_RESOURCE_LINKS } from "@/lib/constants/trust"

type TrustFact = {
  label: string
  value: string
  detail: string
}

type TrustSection = {
  title: string
  paragraphs: ReadonlyArray<string>
  bullets?: ReadonlyArray<string>
}

type TrustContact = {
  title: string
  description: string
  ctaLabel: string
  ctaHref: string
}

type TrustPageProps = {
  currentPath: Route
  eyebrow: string
  title: string
  description: string
  effectiveDate?: string
  intro: ReadonlyArray<string>
  facts: ReadonlyArray<TrustFact>
  sections: ReadonlyArray<TrustSection>
  contacts?: ReadonlyArray<TrustContact>
}

export function TrustPage({
  currentPath,
  eyebrow,
  title,
  description,
  effectiveDate,
  intro,
  facts,
  sections,
  contacts = [],
}: TrustPageProps) {
  const relatedLinks = TRUST_RESOURCE_LINKS.filter((link) => link.href !== currentPath)

  return (
    <main className="min-h-screen overflow-hidden bg-[radial-gradient(circle_at_top,rgba(56,189,248,0.12),transparent_26%),linear-gradient(180deg,#030711_0%,#07111d_32%,#081522_64%,#0a1725_100%)] px-4 py-12 text-white sm:px-6 lg:px-8">
      <div className="mx-auto max-w-6xl">
        <section className="relative overflow-hidden rounded-[2rem] border border-white/10 bg-[linear-gradient(145deg,rgba(8,15,28,0.94),rgba(11,24,39,0.9)_55%,rgba(34,211,238,0.08))] p-8 shadow-[0_36px_110px_-60px_rgba(8,47,73,0.75)] backdrop-blur">
          <div className="absolute inset-y-0 right-0 w-64 bg-[radial-gradient(circle_at_center,rgba(34,211,238,0.12),transparent_62%)]" />
          <div className="relative grid gap-8 lg:grid-cols-[1.35fr_0.65fr]">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.28em] text-cyan-200/80">{eyebrow}</p>
              <h1 className="mt-4 max-w-3xl font-serif text-4xl leading-tight text-white sm:text-5xl">{title}</h1>
              <p className="mt-4 max-w-3xl text-base leading-8 text-slate-300">{description}</p>
              {effectiveDate ? <p className="mt-4 text-sm text-slate-400">Effective date: {effectiveDate}</p> : null}
              <div className="mt-8 space-y-4 text-sm leading-7 text-slate-300">
                {intro.map((paragraph) => (
                  <p key={paragraph}>{paragraph}</p>
                ))}
              </div>
            </div>

            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-1">
              {facts.map((fact) => (
                <article
                  key={fact.label}
                  className="rounded-[1.5rem] border border-white/10 bg-white/[0.05] p-5 shadow-sm shadow-black/20"
                >
                  <p className="text-[11px] font-semibold uppercase tracking-[0.26em] text-cyan-200/70">{fact.label}</p>
                  <p className="mt-3 text-lg font-semibold text-white">{fact.value}</p>
                  <p className="mt-2 text-sm leading-6 text-slate-300">{fact.detail}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <div className="mt-8 grid gap-6 xl:grid-cols-[minmax(0,1fr)_19rem]">
          <div className="space-y-6">
            {sections.map((section) => (
              <section
                key={section.title}
                className="rounded-[1.75rem] border border-white/10 bg-white/[0.04] p-6 shadow-sm shadow-black/20 backdrop-blur"
              >
                <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400">{eyebrow}</p>
                <h2 className="mt-3 font-serif text-3xl text-white">{section.title}</h2>
                <div className="mt-4 space-y-4 text-sm leading-7 text-slate-300">
                  {section.paragraphs.map((paragraph) => (
                    <p key={paragraph}>{paragraph}</p>
                  ))}
                </div>
                {section.bullets?.length ? (
                  <ul className="mt-5 space-y-3 text-sm leading-7 text-slate-300">
                    {section.bullets.map((bullet) => (
                      <li key={bullet} className="flex gap-3">
                        <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-cyan-300" />
                        <span>{bullet}</span>
                      </li>
                    ))}
                  </ul>
                ) : null}
              </section>
            ))}
          </div>

          <aside className="space-y-6">
            {contacts.length ? (
              <section className="rounded-[1.75rem] border border-cyan-300/20 bg-cyan-300/[0.08] p-6 shadow-sm shadow-black/20 backdrop-blur">
                <p className="text-xs font-semibold uppercase tracking-[0.24em] text-cyan-200/80">Reach LoreVia</p>
                <div className="mt-4 space-y-4">
                  {contacts.map((contact) => (
                    <article key={contact.title} className="rounded-2xl border border-white/10 bg-black/20 p-4">
                      <h3 className="text-base font-semibold text-white">{contact.title}</h3>
                      <p className="mt-2 text-sm leading-6 text-slate-300">{contact.description}</p>
                      <a
                        className="mt-4 inline-flex rounded-full border border-white/15 px-4 py-2 text-sm font-semibold text-white transition hover:border-white/35 hover:bg-white/8"
                        href={contact.ctaHref}
                      >
                        {contact.ctaLabel}
                      </a>
                    </article>
                  ))}
                </div>
              </section>
            ) : null}

            <section className="rounded-[1.75rem] border border-white/10 bg-white/[0.04] p-6 shadow-sm shadow-black/20 backdrop-blur">
              <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400">Footer resources</p>
              <div className="mt-4 space-y-3">
                {relatedLinks.map((link) => (
                  <Link
                    key={link.href}
                    href={link.href}
                    className="block rounded-2xl border border-white/10 bg-black/20 p-4 transition hover:border-white/20 hover:bg-white/[0.04]"
                  >
                    <p className="text-sm font-semibold text-white">{link.title}</p>
                    <p className="mt-2 text-sm leading-6 text-slate-300">{link.description}</p>
                  </Link>
                ))}
              </div>
            </section>
          </aside>
        </div>
      </div>
    </main>
  )
}
