import Link from "next/link"
import type { Route } from "next"
import type { ReactNode } from "react"

import { BrandLockup } from "@/components/layout/BrandLockup"
import { LEGAL_EMAIL, SUPPORT_EMAIL } from "@/lib/constants/contact"
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

type IconProps = {
  className?: string
}

const primaryLinkOrder = ["/contact", "/terms", "/privacy", "/compliance", "/status"] as const
const primaryLinks = primaryLinkOrder
  .map((href) => TRUST_RESOURCE_LINKS.find((link) => link.href === href))
  .filter((link): link is (typeof TRUST_RESOURCE_LINKS)[number] => Boolean(link))

const surfaceClassName =
  "border border-white/10 bg-[linear-gradient(180deg,rgba(11,22,36,0.72),rgba(6,14,25,0.74))] shadow-[0_24px_70px_-54px_rgba(20,83,145,0.85)] backdrop-blur"

const iconClassName =
  "flex h-12 w-12 shrink-0 items-center justify-center rounded-full border border-[#4787d8]/35 bg-[#071522] text-[#7fb0ff]"

function BrandMark() {
  return <BrandLockup size="sm" iconClassName="h-8 w-8 rounded-lg" />
}

function ArrowIcon({ className = "h-4 w-4" }: IconProps) {
  return (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.8" className={className} aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" d="M3 8h10" />
      <path strokeLinecap="round" strokeLinejoin="round" d="m9 4 4 4-4 4" />
    </svg>
  )
}

function ShieldIcon({ className = "h-6 w-6" }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" className={className} aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 3.5 5.8 6v5.5c0 4.2 2.5 7.5 6.2 8.4 3.7-.9 6.2-4.2 6.2-8.4V6L12 3.5Z" />
    </svg>
  )
}

function PulseIcon({ className = "h-6 w-6" }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" className={className} aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" d="M3 12h4l2.4-4.4L13.3 17l2.4-5H21" />
    </svg>
  )
}

function QuestionIcon({ className = "h-6 w-6" }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" className={className} aria-hidden="true">
      <circle cx="12" cy="12" r="8.5" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M9.7 9.4A2.4 2.4 0 0 1 12 7.8c1.5 0 2.7 1 2.7 2.3 0 1.1-.7 1.8-1.8 2.4-.8.5-1.1.9-1.1 1.7" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 17h.01" />
    </svg>
  )
}

function DocumentIcon({ className = "h-6 w-6" }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" className={className} aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" d="M7 4.5h6.4L17 8.1v11.4H7z" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M13.2 4.7V8.3h3.5" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M9.6 13h4.8M9.6 16h3" />
    </svg>
  )
}

function DatabaseIcon({ className = "h-6 w-6" }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" className={className} aria-hidden="true">
      <ellipse cx="12" cy="6.5" rx="6" ry="2.7" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M6 6.5v5c0 1.5 2.7 2.7 6 2.7s6-1.2 6-2.7v-5" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M6 11.5v5c0 1.5 2.7 2.7 6 2.7s6-1.2 6-2.7v-5" />
    </svg>
  )
}

function SparkIcon({ className = "h-6 w-6" }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" className={className} aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" d="m12 3.8 1.9 5 5 1.9-5 1.9-1.9 5-1.9-5-5-1.9 5-1.9z" />
    </svg>
  )
}

function DotsIcon({ className = "h-6 w-6" }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" className={className} aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" d="M7 8h.01M16.5 5.5h.01M17 15h.01M9.2 17.5h.01" />
      <path strokeLinecap="round" strokeLinejoin="round" d="m10 8 3.8-2M9.8 16.5l4.7-1.2M16.2 7.8l.5 4.9" />
    </svg>
  )
}

function UsersIcon({ className = "h-6 w-6" }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" className={className} aria-hidden="true">
      <circle cx="9" cy="8.5" r="2.8" />
      <circle cx="16.5" cy="9.5" r="2.2" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 18.5c.5-2.8 2.1-4.4 4.5-4.4s4 1.6 4.5 4.4" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M13.8 15.2c1.9.2 3.2 1.3 3.7 3.3" />
    </svg>
  )
}

function ClockIcon({ className = "h-6 w-6" }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" className={className} aria-hidden="true">
      <circle cx="12" cy="12" r="8.2" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 7.5v5l3.2 1.8" />
    </svg>
  )
}

function LockIcon({ className = "h-6 w-6" }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" className={className} aria-hidden="true">
      <rect x="5" y="10" width="14" height="10" rx="2.4" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M8 10V7.9A4 4 0 0 1 12 4a4 4 0 0 1 4 3.9V10" />
    </svg>
  )
}

function SupportIcon({ className = "h-6 w-6" }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" className={className} aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" d="M4 13.5A8 8 0 0 1 12 5a8 8 0 0 1 8 8.5" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M5.5 13H4a1 1 0 0 0-1 1v3a1 1 0 0 0 1 1h1.5A1.5 1.5 0 0 0 7 16.5v-2A1.5 1.5 0 0 0 5.5 13Zm13 0H20a1 1 0 0 1 1 1v3a1 1 0 0 1-1 1h-1.5a1.5 1.5 0 0 1-1.5-1.5v-2a1.5 1.5 0 0 1 1.5-1.5Z" />
    </svg>
  )
}

function SectionIcon({ index }: { index: number }) {
  const icons = [
    <DocumentIcon key="document" />,
    <DatabaseIcon key="database" />,
    <PulseIcon key="pulse" />,
    <SparkIcon key="spark" />,
    <DotsIcon key="dots" />,
    <UsersIcon key="users" />,
    <ClockIcon key="clock" />,
    <ShieldIcon key="shield" />,
    <QuestionIcon key="question" />,
  ]

  return icons[index % icons.length]
}

function SummaryIcon({ index }: { index: number }) {
  const icons = [
    <ShieldIcon key="shield" />,
    <PulseIcon key="pulse" />,
    <QuestionIcon key="question" />,
  ]

  return icons[index % icons.length]
}

function Header({ currentPath }: { currentPath: Route }) {
  return (
    <header className="border-b border-white/[0.07] bg-[#030812]/86">
      <div className="mx-auto flex max-w-[76.5rem] flex-col gap-5 px-5 py-5 sm:px-8 lg:flex-row lg:items-center lg:justify-between">
        <Link href="/" className="w-fit">
          <BrandMark />
        </Link>

        <nav className="flex flex-wrap items-center gap-5 text-sm text-slate-300 sm:gap-8">
          {primaryLinks.map((link) => {
            const active = link.href === currentPath

            return (
              <Link key={link.href} href={link.href} className={`relative pb-3 transition ${active ? "text-white" : "hover:text-white"}`}>
                {link.label}
                {active ? <span className="absolute bottom-0 left-1/2 h-1.5 w-1.5 -translate-x-1/2 rounded-full bg-[#72a6ff]" /> : null}
              </Link>
            )
          })}
        </nav>
      </div>
    </header>
  )
}

function SummaryCard({ fact, index }: { fact: TrustFact; index: number }) {
  return (
    <article className={`${surfaceClassName} overflow-hidden rounded-lg p-5`}>
      <div className="flex flex-col gap-4 sm:flex-row">
        <div className={iconClassName}>
          <SummaryIcon index={index} />
        </div>
        <div className="min-w-0">
          <h3 className="font-serif text-lg leading-7 text-white">{fact.label}</h3>
          <p className="mt-2 break-words text-sm leading-6 text-slate-300/82">{fact.detail}</p>
          <a href={fact.value} className="mt-5 inline-flex items-center gap-2 text-sm font-semibold text-[#8fb7ff] transition hover:translate-x-0.5">
            <span>{index === 2 ? "See options" : "See details"}</span>
            <ArrowIcon />
          </a>
        </div>
      </div>
    </article>
  )
}

function PolicySection({ section, index }: { section: TrustSection; index: number }) {
  return (
    <section id={`section-${index + 1}`} className={`${surfaceClassName} overflow-hidden rounded-lg px-5 py-5 sm:px-6`}>
      <div className="grid gap-5 sm:grid-cols-[3.75rem_minmax(0,1fr)]">
        <div className={iconClassName}>
          <SectionIcon index={index} />
        </div>
        <div className="min-w-0">
          <h2 className="break-words font-serif text-2xl leading-8 text-white">
            {index + 1}. {section.title}
          </h2>
          <div className="mt-3 space-y-3 break-words text-sm leading-6 text-slate-300/84">
            {section.paragraphs.map((paragraph) => (
              <p key={paragraph}>{paragraph}</p>
            ))}
          </div>
          {section.bullets?.length ? (
            <ul className="mt-4 list-disc space-y-1.5 pl-5 text-sm leading-6 text-slate-300/84">
              {section.bullets.map((bullet) => (
                <li key={bullet}>{bullet}</li>
              ))}
            </ul>
          ) : null}
        </div>
      </div>
    </section>
  )
}

function SideCard({
  title,
  description,
  ctaLabel,
  ctaHref,
  icon,
  links,
}: {
  title: string
  description: string
  ctaLabel: string
  ctaHref: string
  icon: ReactNode
  links: ReadonlyArray<string>
}) {
  const isExternal = ctaHref.startsWith("https://")

  return (
    <article className={`${surfaceClassName} rounded-lg p-6`}>
      <div className="flex gap-5">
        <div className={iconClassName}>{icon}</div>
        <div className="min-w-0">
          <h3 className="font-serif text-lg leading-7 text-white">{title}</h3>
          <p className="mt-5 text-sm leading-6 text-slate-300/82">{description}</p>
          <a
            href={ctaHref}
            target={isExternal ? "_blank" : undefined}
            rel={isExternal ? "noreferrer" : undefined}
            className="mt-6 inline-flex items-center gap-3 text-sm font-semibold text-[#8fb7ff] transition hover:translate-x-0.5"
          >
            <span>{ctaLabel}</span>
            <ArrowIcon />
          </a>
        </div>
      </div>
      <div className="mt-6 border-t border-white/10 pt-5">
        <ul className="space-y-3 text-sm text-slate-300/82">
          {links.map((link) => (
            <li key={link}>{link}</li>
          ))}
        </ul>
      </div>
    </article>
  )
}

function ResourceCard({ relatedLinks }: { relatedLinks: ReturnType<typeof TRUST_RESOURCE_LINKS.filter> }) {
  const resourceLinks = relatedLinks.filter((link) => ["/terms", "/compliance", "/refund"].includes(link.href))

  return (
    <section className={`${surfaceClassName} rounded-lg p-6`}>
      <p className="text-[11px] font-semibold uppercase tracking-[0.34em] text-[#9fbfff]/80">Resources</p>
      <div className="mt-5 divide-y divide-white/10">
        {resourceLinks.map((link) => (
          <Link key={link.href} href={link.href} className="flex items-center justify-between gap-5 py-5 first:pt-0 last:pb-0">
            <span>
              <span className="block text-sm font-semibold text-white">{link.title}</span>
              <span className="mt-2 block text-sm leading-6 text-slate-300/78">{link.description}</span>
            </span>
            <ArrowIcon className="h-5 w-5 shrink-0 text-[#8fb7ff]" />
          </Link>
        ))}
      </div>
    </section>
  )
}

function SecurityCallout() {
  return (
    <section className="mt-4 rounded-lg border border-[#2f7fd1]/55 bg-[linear-gradient(180deg,rgba(9,23,39,0.8),rgba(7,16,28,0.78))] px-5 py-5 shadow-[0_24px_70px_-54px_rgba(20,83,145,0.9)] backdrop-blur sm:px-6">
      <div className="flex flex-col gap-5 md:flex-row md:items-center md:justify-between">
        <div className="flex gap-5">
          <div className={`${iconClassName} border-[#3f89e4]/60 text-[#8fb7ff]`}>
            <LockIcon />
          </div>
          <div>
            <h2 className="font-serif text-2xl leading-8 text-white">Report security issues responsibly</h2>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-300/84">
              If you believe you've found a security vulnerability, please report it privately to us. Do not disclose it publicly.
            </p>
          </div>
        </div>
        <a href={`mailto:${LEGAL_EMAIL}`} className="inline-flex items-center gap-3 self-start text-sm font-semibold text-[#8fb7ff] transition hover:translate-x-0.5 md:self-center">
          <span>security@getlorevia.com</span>
          <ArrowIcon />
        </a>
      </div>
    </section>
  )
}

export function TrustPage({
  currentPath,
  eyebrow,
  title,
  description,
  facts,
  sections,
  contacts = [],
}: TrustPageProps) {
  const relatedLinks = TRUST_RESOURCE_LINKS.filter((link) => link.href !== currentPath)
  const supportContact = contacts[0] ?? {
    title: "Privacy and account support",
    description: "Questions about your account, data, or privacy choices.",
    ctaLabel: SUPPORT_EMAIL,
    ctaHref: `mailto:${SUPPORT_EMAIL}`,
  }
  const legalContact = contacts[1] ?? {
    title: "Formal legal requests",
    description: "For legal inquiries, takedowns, subpoenas, or other formal requests.",
    ctaLabel: LEGAL_EMAIL,
    ctaHref: `mailto:${LEGAL_EMAIL}`,
  }

  return (
    <main className="min-h-screen overflow-hidden bg-[radial-gradient(circle_at_50%_8%,rgba(50,99,164,0.22),transparent_29%),radial-gradient(circle_at_50%_40%,rgba(17,42,74,0.28),transparent_36%),linear-gradient(180deg,#020711_0%,#06111d_34%,#06101c_100%)] text-white">
      <Header currentPath={currentPath} />

      <section className="px-5 py-16 sm:px-8 sm:py-20 lg:px-12">
        <div className="mx-auto max-w-4xl text-center">
          <p className="text-xs font-semibold uppercase tracking-[0.42em] text-[#8fb7ff]/82">{eyebrow}</p>
          <h1 className="mx-auto mt-7 max-w-[20rem] break-words font-serif text-[2.15rem] leading-[1.08] tracking-[-0.03em] text-white sm:max-w-3xl sm:text-[3.75rem] sm:leading-[0.98] lg:text-[4.05rem]">
            {title}
          </h1>
          <p className="mx-auto mt-7 max-w-2xl break-words text-base leading-8 text-slate-300/86 sm:text-lg">{description}</p>
        </div>
      </section>

      <div className="mx-auto max-w-[76.5rem] px-5 pb-10 sm:px-8 lg:px-0">
        <section>
          <h2 className="font-serif text-xl text-white">Quick summary</h2>
          <div className="mt-5 grid gap-4 lg:grid-cols-3">
            {facts.slice(0, 3).map((fact, index) => (
              <SummaryCard key={fact.label} fact={fact} index={index} />
            ))}
          </div>
        </section>

        <div className="mt-6 grid gap-8 lg:grid-cols-[minmax(0,1fr)_21rem] lg:items-start">
          <div>
            <div className="space-y-1">
              {sections.map((section, index) => (
                <PolicySection key={section.title} section={section} index={index} />
              ))}
            </div>
          </div>

          <aside className="space-y-5 lg:sticky lg:top-6">
            <SideCard
              title={supportContact.title}
              description={supportContact.description}
              ctaLabel={supportContact.ctaLabel}
              ctaHref={supportContact.ctaHref}
              icon={<SupportIcon />}
              links={["Account access & login", "Billing & subscriptions", "Data & privacy requests", "General product support"]}
            />
            <SideCard
              title={legalContact.title}
              description={legalContact.description}
              ctaLabel={legalContact.ctaLabel}
              ctaHref={legalContact.ctaHref}
              icon={<ShieldIcon />}
              links={["Copyright & takedown", "Privacy & data requests", "Terms & agreements"]}
            />
            <SideCard
              title="Service status"
              description="Live status, incidents, and maintenance updates."
              ctaLabel="View status page"
              ctaHref="/status"
              icon={<PulseIcon />}
              links={["Service availability", "Incident updates", "Scheduled maintenance", "Uptime history"]}
            />
            <ResourceCard relatedLinks={relatedLinks} />
          </aside>
        </div>

        <SecurityCallout />
      </div>
    </main>
  )
}
