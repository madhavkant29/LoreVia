import type { Metadata } from "next"
import Link from "next/link"
import { notFound } from "next/navigation"

import { MarketingFooterLayout } from "@/components/layout/MarketingFooterLayout"
import { ContentArrowIcon } from "@/components/marketing/PublicContentHeader"
import { PublicContentShell } from "@/components/marketing/PublicContentShell"
import { JsonLdScript } from "@/components/seo/JsonLdScript"
import {
  demoPages,
  getAnswerPagesBySlugs,
  getBlogArticleBySlug,
  getDemoPageBySlug,
} from "@/lib/content"
import {
  DEFAULT_OG_IMAGE,
  SITE_NAME,
  buildArticleJsonLd,
  buildBreadcrumbJsonLd,
  toAbsoluteUrl,
} from "@/lib/seo"

export function generateStaticParams() {
  return demoPages.map((demo) => ({ slug: demo.slug }))
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const { slug } = await params
  const demo = getDemoPageBySlug(slug)

  if (!demo) {
    return {}
  }

  return {
    title: demo.title,
    description: demo.description,
    authors: [{ name: SITE_NAME, url: toAbsoluteUrl("/") }],
    alternates: {
      canonical: `/demo/${demo.slug}`,
    },
    openGraph: {
      type: "article",
      title: `${demo.title} | ${SITE_NAME}`,
      description: demo.description,
      url: toAbsoluteUrl(`/demo/${demo.slug}`),
      images: [
        {
          url: DEFAULT_OG_IMAGE,
          width: 1200,
          height: 630,
          alt: demo.title,
        },
      ],
    },
    twitter: {
      card: "summary_large_image",
      title: `${demo.title} | ${SITE_NAME}`,
      description: demo.description,
      images: [DEFAULT_OG_IMAGE],
    },
  }
}

export default async function DemoPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params
  const demo = getDemoPageBySlug(slug)

  if (!demo) {
    notFound()
  }

  const article = getBlogArticleBySlug(demo.articleSlug)
  const relatedAnswers = getAnswerPagesBySlugs(demo.answerSlugs)
  const displayTitle = demo.title.replace(/^Demo:\s*/, "")

  const jsonLd = buildArticleJsonLd({
    title: demo.title,
    description: demo.description,
    path: `/demo/${demo.slug}`,
    datePublished: demo.publishedAt,
    about: [demo.sourceWork, demo.sourceAuthor, "fiction analysis demo"],
  })
  const breadcrumbJsonLd = buildBreadcrumbJsonLd([
    { name: "Home", path: "/" },
    { name: "Demo", path: "/demo" },
    { name: demo.title, path: `/demo/${demo.slug}` },
  ])

  return (
    <MarketingFooterLayout>
      <PublicContentShell activeSection="demo">
        <JsonLdScript id={`demo-jsonld-${demo.slug}`} data={jsonLd} />
        <JsonLdScript id={`demo-breadcrumbs-jsonld-${demo.slug}`} data={breadcrumbJsonLd} />

      <section className="app-container py-10 md:py-14">
        <div className="flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
          <Link href="/demo" className="transition hover:text-foreground">Demo library</Link>
          <span aria-hidden="true">/</span>
          <span>{demo.sourceWork}</span>
        </div>

        <header className="mt-8 max-w-4xl border-b border-[rgba(var(--border),0.72)] pb-10 md:pb-14">
          <p className="text-sm font-semibold text-[rgb(var(--accent))]">
            {demo.sourceWork} · {demo.sourceAuthor} · {demo.readTime}
          </p>
          <h1 className="mt-4 max-w-4xl font-display text-[3rem] leading-[0.96] tracking-[-0.04em] text-foreground sm:text-[3.75rem]">
            {displayTitle}
          </h1>
          <p className="mt-6 max-w-3xl text-base leading-8 text-muted-foreground sm:text-[1.1rem]">{demo.intro}</p>
        </header>

        <article data-testid="demo-case-study" className="max-w-4xl">
          <blockquote className="my-10 border-l-2 border-[rgb(var(--accent))] pl-5 text-xl font-medium leading-9 text-foreground md:my-12 md:text-2xl">
            {demo.featuredInsight}
          </blockquote>

          {demo.sections.map((section) => (
            <section key={section.heading} className="border-t border-[rgba(var(--border),0.64)] py-9 md:py-11">
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
                <ul className="mt-7 divide-y divide-[rgba(var(--border),0.56)] border-y border-[rgba(var(--border),0.56)] text-sm leading-7 text-foreground/85 md:text-base">
                  {section.bullets.map((bullet) => (
                    <li key={bullet} className="py-3">{bullet}</li>
                  ))}
                </ul>
              ) : null}
            </section>
          ))}
        </article>

        <section className="grid max-w-5xl border-y border-[rgba(var(--border),0.72)] lg:grid-cols-[0.95fr_1.05fr]">
          {article ? (
            <div className="py-8 lg:pr-10">
              <p className="text-sm font-semibold text-[rgb(var(--accent))]">Continue with the craft guide</p>
              <h2 className="mt-3 text-2xl font-semibold tracking-[-0.03em] text-foreground">{article.title}</h2>
              <p className="mt-3 text-sm leading-7 text-muted-foreground">{article.description}</p>
              <Link href={`/blog/${article.slug}`} className="mt-5 inline-flex items-center gap-2 font-semibold text-[rgb(var(--accent))]">
                Read the guide <ContentArrowIcon />
              </Link>
            </div>
          ) : null}
          <div className="border-t border-[rgba(var(--border),0.72)] py-8 lg:border-l lg:border-t-0 lg:pl-10">
            <p className="text-sm font-semibold text-[rgb(var(--accent))]">Related questions</p>
            <div className="mt-4 divide-y divide-[rgba(var(--border),0.56)]">
              {relatedAnswers.map((answer) => (
                <Link key={answer.slug} href={`/answers/${answer.slug}`} className="block py-4 first:pt-0 last:pb-0">
                  <span className="font-semibold text-foreground transition hover:text-[rgb(var(--accent))]">{answer.question}</span>
                  <span className="mt-1 block text-sm leading-6 text-muted-foreground">{answer.shortAnswer}</span>
                </Link>
              ))}
            </div>
          </div>
        </section>

        <section className="max-w-5xl py-14 md:py-16">
          <div className="grid gap-6 border-b border-[rgba(var(--border),0.72)] pb-10 md:grid-cols-[1fr_auto] md:items-end">
            <div className="max-w-3xl">
              <h2 className="text-3xl font-semibold tracking-[-0.03em] text-foreground md:text-4xl">
                Apply the same review to your manuscript.
              </h2>
              <p className="mt-4 text-base leading-8 text-muted-foreground md:text-lg">
                Import a draft, inspect the cited evidence, and decide which findings belong in your revision plan.
              </p>
            </div>
            <div className="flex flex-col gap-3 sm:flex-row">
              <Link href="/demo/workspace" className="app-button-secondary">Review a sample finding</Link>
              <Link href="/register" className="app-button-primary">Start free</Link>
            </div>
          </div>
        </section>
      </section>
      </PublicContentShell>
    </MarketingFooterLayout>
  )
}
