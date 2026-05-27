import type { Metadata } from "next"
import Link from "next/link"
import { notFound } from "next/navigation"

import { ContentArrowIcon } from "@/components/marketing/PublicContentHeader"
import { PublicContentShell } from "@/components/marketing/PublicContentShell"
import { JsonLdScript } from "@/components/seo/JsonLdScript"
import {
  answerPages,
  getAnswerPageBySlug,
  getBlogArticleBySlug,
  getDemoPageBySlug,
} from "@/lib/content"
import {
  DEFAULT_OG_IMAGE,
  SITE_NAME,
  buildBreadcrumbJsonLd,
  buildFaqPageJsonLd,
  toAbsoluteUrl,
} from "@/lib/seo"

export function generateStaticParams() {
  return answerPages.map((answer) => ({ slug: answer.slug }))
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const { slug } = await params
  const answer = getAnswerPageBySlug(slug)

  if (!answer) {
    return {}
  }

  return {
    title: answer.question,
    description: answer.description,
    authors: [{ name: SITE_NAME, url: toAbsoluteUrl("/") }],
    alternates: {
      canonical: `/answers/${answer.slug}`,
    },
    openGraph: {
      type: "article",
      title: `${answer.question} | ${SITE_NAME}`,
      description: answer.description,
      url: toAbsoluteUrl(`/answers/${answer.slug}`),
      images: [
        {
          url: DEFAULT_OG_IMAGE,
          width: 1200,
          height: 630,
          alt: answer.question,
        },
      ],
    },
    twitter: {
      card: "summary_large_image",
      title: `${answer.question} | ${SITE_NAME}`,
      description: answer.description,
      images: [DEFAULT_OG_IMAGE],
    },
  }
}

export default async function AnswerPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params
  const answer = getAnswerPageBySlug(slug)

  if (!answer) {
    notFound()
  }

  const article = getBlogArticleBySlug(answer.articleSlug)
  const demoPage = answer.demoSlug ? getDemoPageBySlug(answer.demoSlug) : null

  const jsonLd = buildFaqPageJsonLd([
    {
      question: answer.question,
      answer: answer.shortAnswer,
    },
  ])
  const breadcrumbJsonLd = buildBreadcrumbJsonLd([
    { name: "Home", path: "/" },
    { name: "Answers", path: "/answers" },
    { name: answer.question, path: `/answers/${answer.slug}` },
  ])

  return (
    <PublicContentShell activeSection="answers">
      <JsonLdScript id={`answers-jsonld-${answer.slug}`} data={jsonLd} />
      <JsonLdScript id={`answers-breadcrumbs-jsonld-${answer.slug}`} data={breadcrumbJsonLd} />

      <section className="app-container py-10 md:py-14">
        <div className="app-panel app-panel--strong rounded-[2rem] p-6 md:p-8 lg:p-10">
          <div className="flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
            <Link href="/answers" className="hover:text-foreground">
              Answers
            </Link>
            <span>/</span>
            <span>{answer.publishedLabel}</span>
          </div>

          <div className="mt-8 grid gap-8 lg:grid-cols-[1.12fr_0.88fr] lg:items-start">
            <div className="max-w-4xl">
              <span className="app-chip">Author question</span>
              <h1 className="mt-7 max-w-5xl font-display text-[3rem] leading-[0.94] tracking-[-0.04em] text-foreground sm:text-[3.5rem]">{answer.question}</h1>
              <p className="mt-6 max-w-3xl text-base leading-8 text-muted-foreground sm:text-[1.1rem]">{answer.intro}</p>
            </div>

            <div className="grid gap-4 sm:grid-cols-3 lg:grid-cols-1">
              <div className="app-stat app-stat--accent">
                <p className="app-stat__label">Read time</p>
                <p className="mt-3 text-lg font-semibold text-foreground">{answer.readTime}</p>
                <p className="app-stat__note">Built to answer one real author problem clearly.</p>
              </div>
              <div className="app-stat app-stat--warning">
                <p className="app-stat__label">Quick steps</p>
                <p className="app-stat__value">{answer.quickSteps.length}</p>
                <p className="app-stat__note">A concise workflow you can apply during revision.</p>
              </div>
              <div className="app-stat">
                <p className="app-stat__label">Linked guide</p>
                <p className="mt-3 text-lg font-semibold text-foreground">{article?.title ?? "LoreVia guide"}</p>
                <p className="app-stat__note">Connects this short answer back to a deeper workflow page.</p>
              </div>
            </div>
          </div>
        </div>
        
        <div className="mt-8 grid gap-8 lg:grid-cols-[1.15fr_0.85fr]">
          <article className="space-y-6">
            <section className="app-panel app-panel--strong rounded-[2rem] p-6 md:p-8">
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-muted-foreground">Direct answer</p>
              <p className="mt-4 text-base leading-8 text-muted-foreground md:text-lg">{answer.shortAnswer}</p>
              <div className="mt-6 rounded-[1.4rem] border border-[rgba(var(--border),0.78)] bg-white/70 p-5 dark:bg-white/[0.03]">
                <p className="text-xs font-semibold uppercase tracking-[0.22em] text-muted-foreground">Why it matters</p>
                <p className="mt-3 text-sm leading-7 text-muted-foreground md:text-base">{answer.whyItMatters}</p>
              </div>
            </section>

            <section className="app-panel rounded-[2rem] p-6 md:p-8">
              <h2 className="text-3xl font-semibold tracking-[-0.03em] text-foreground">
                A simple way to handle it
              </h2>
              <ul className="mt-6 space-y-4 text-sm leading-7 text-foreground/85 md:text-base">
                {answer.quickSteps.map((step) => (
                  <li key={step} className="flex gap-3">
                    <span className="mt-2 h-1.5 w-1.5 rounded-full bg-[rgb(var(--accent))]" />
                    <span>{step}</span>
                  </li>
                ))}
              </ul>
            </section>

            {answer.sections.map((section) => (
              <section key={section.heading} className="app-panel rounded-[2rem] p-6 md:p-8">
                <h2 className="text-[2rem] font-semibold tracking-[-0.03em] text-foreground md:text-[2.2rem]">
                  {section.heading}
                </h2>
                <div className="mt-5 space-y-4">
                  {section.body.map((paragraph) => (
                    <p key={paragraph} className="text-base leading-8 text-muted-foreground md:text-lg">
                      {paragraph}
                    </p>
                  ))}
                </div>

                {section.bullets?.length ? (
                  <ul className="mt-6 space-y-3 text-sm leading-7 text-foreground/85 md:text-base">
                    {section.bullets.map((bullet) => (
                      <li key={bullet} className="flex gap-3">
                        <span className="mt-2 h-1.5 w-1.5 rounded-full bg-[rgb(var(--accent))]" />
                        <span>{bullet}</span>
                      </li>
                    ))}
                  </ul>
                ) : null}
              </section>
            ))}
          </article>

          <aside className="space-y-6 lg:sticky lg:top-28">
            {article ? (
              <div className="app-panel app-panel--strong rounded-[2rem] p-6 md:p-8">
                <p className="text-xs font-semibold uppercase tracking-[0.22em] text-muted-foreground">Read the main guide</p>
                <h2 className="mt-4 text-2xl font-semibold tracking-[-0.03em] text-foreground">{article.title}</h2>
                <p className="mt-3 text-sm leading-7 text-muted-foreground">{article.description}</p>
                <Link href={`/blog/${article.slug}`} className="mt-5 inline-flex items-center gap-2 font-semibold text-[rgb(var(--accent))]">
                  {article.title}
                  <ContentArrowIcon />
                </Link>
              </div>
            ) : null}

            {demoPage ? (
              <div className="app-panel rounded-[2rem] p-6 md:p-8">
                <p className="text-xs font-semibold uppercase tracking-[0.22em] text-muted-foreground">See a public-domain example</p>
                <h2 className="mt-4 text-2xl font-semibold tracking-[-0.03em] text-foreground">{demoPage.title}</h2>
                <p className="mt-3 text-sm leading-7 text-muted-foreground">{demoPage.featuredInsight}</p>
                <Link href={`/demo/${demoPage.slug}`} className="mt-5 inline-flex items-center gap-2 font-semibold text-[rgb(var(--accent))]">
                  Open demo
                  <ContentArrowIcon />
                </Link>
              </div>
            ) : null}

            <div className="app-panel rounded-[2rem] p-6 md:p-8">
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-muted-foreground">Editorial use</p>
              <p className="mt-4 text-sm leading-7 text-muted-foreground">
                These answer pages are designed to give authors a direct response while still preserving enough context to support real revision decisions, internal linking, and follow-up reading.
              </p>
            </div>
          </aside>
        </div>
      </section>

      <section className="app-container pb-20 pt-8 md:pb-24">
        <div className="app-panel app-panel--strong rounded-[2rem] p-7 md:p-10">
          <div className="max-w-3xl">
            <p className="app-eyebrow">Try LoreVia</p>
            <h2 className="mt-4 text-3xl font-semibold tracking-[-0.03em] text-foreground md:text-4xl">
              Turn these answers into a repeatable manuscript workflow.
            </h2>
            <p className="mt-4 text-base leading-8 text-muted-foreground md:text-lg">
              LoreVia helps authors move from scattered notes to a chapter-grounded story system for continuity, character memory, and revision decisions.
            </p>
          </div>
          <div className="mt-7 flex flex-col gap-3 sm:flex-row">
            <Link href="/register" className="app-button-primary gap-2">
              Start free
              <ContentArrowIcon />
            </Link>
            <Link href="/blog" className="app-button-secondary">
              Browse longer guides
            </Link>
          </div>
        </div>
      </section>
    </PublicContentShell>
  )
}
