import type { Metadata } from "next"
import Link from "next/link"
import Script from "next/script"
import { notFound } from "next/navigation"

import { PublicContentHeader, ContentArrowIcon } from "@/components/marketing/PublicContentHeader"
import { Reveal } from "@/components/marketing/Reveal"
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
    <main className="app-shell overflow-hidden">
      <div className="app-shell__mesh" />
      <div className="absolute inset-x-0 top-0 -z-10 h-[28rem] bg-[radial-gradient(circle_at_top,rgba(15,118,110,0.14),transparent_36%),radial-gradient(circle_at_85%_10%,rgba(180,83,9,0.12),transparent_24%)]" />
      <Script id={`answers-jsonld-${answer.slug}`} type="application/ld+json" strategy="beforeInteractive">
        {JSON.stringify(jsonLd).replace(/</g, "\\u003c")}
      </Script>
      <Script id={`answers-breadcrumbs-jsonld-${answer.slug}`} type="application/ld+json" strategy="beforeInteractive">
        {JSON.stringify(breadcrumbJsonLd).replace(/</g, "\\u003c")}
      </Script>

      <PublicContentHeader activeSection="answers" />

      <section className="app-container py-14 md:py-20">
        <Reveal>
          <div className="max-w-4xl">
            <div className="flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
              <Link href="/answers" className="hover:text-foreground">
                Answers
              </Link>
              <span>/</span>
              <span>{answer.publishedLabel}</span>
            </div>
            <span className="app-chip mt-6">Author question</span>
            <h1 className="app-title mt-7 max-w-5xl">{answer.question}</h1>
            <p className="app-copy mt-6 max-w-3xl text-lg md:text-xl">{answer.shortAnswer}</p>
          </div>
        </Reveal>

        <div className="mt-12 grid gap-8 lg:grid-cols-[1.15fr_0.85fr]">
          <Reveal>
            <article className="app-panel rounded-[2rem] p-6 md:p-8">
              <p className="app-copy text-base md:text-lg">{answer.whyItMatters}</p>
              <h2 className="mt-8 font-[var(--font-newsreader)] text-3xl tracking-[-0.04em] text-foreground">
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
            </article>
          </Reveal>

          <Reveal delay={100}>
            <aside className="space-y-6">
              {article ? (
                <div className="app-panel app-panel--strong rounded-[2rem] p-6 md:p-8">
                  <p className="text-xs font-semibold uppercase tracking-[0.22em] text-muted-foreground">Read the main guide</p>
                  <h2 className="mt-4 text-2xl font-semibold tracking-[-0.03em] text-foreground">{article.title}</h2>
                  <p className="app-copy mt-3 text-sm">{article.description}</p>
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
                  <p className="app-copy mt-3 text-sm">{demoPage.featuredInsight}</p>
                  <Link href={`/demo/${demoPage.slug}`} className="mt-5 inline-flex items-center gap-2 font-semibold text-[rgb(var(--accent))]">
                    Open demo
                    <ContentArrowIcon />
                  </Link>
                </div>
              ) : null}
            </aside>
          </Reveal>
        </div>
      </section>

      <section className="app-container pb-20 pt-8 md:pb-24">
        <Reveal>
          <div className="rounded-[2rem] border border-[rgba(var(--border),0.8)] bg-[linear-gradient(135deg,rgba(15,118,110,0.12),rgba(255,255,255,0.72),rgba(180,83,9,0.12))] p-7 md:p-10 dark:bg-[linear-gradient(135deg,rgba(45,212,191,0.08),rgba(255,255,255,0.03),rgba(251,146,60,0.08))]">
            <div className="max-w-3xl">
              <p className="app-eyebrow">Try LoreVia</p>
              <h2 className="mt-4 font-[var(--font-newsreader)] text-3xl tracking-[-0.04em] text-foreground md:text-4xl">
                Turn these answers into a repeatable manuscript workflow.
              </h2>
              <p className="app-copy mt-4 text-base md:text-lg">
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
        </Reveal>
      </section>
    </main>
  )
}
