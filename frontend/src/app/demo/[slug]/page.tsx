import type { Metadata } from "next"
import Link from "next/link"
import { notFound } from "next/navigation"

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
    <PublicContentShell activeSection="demo">
      <JsonLdScript id={`demo-jsonld-${demo.slug}`} data={jsonLd} />
      <JsonLdScript id={`demo-breadcrumbs-jsonld-${demo.slug}`} data={breadcrumbJsonLd} />

      <section className="app-container py-10 md:py-14">
        <div className="app-panel app-panel--strong rounded-[2rem] p-6 md:p-8 lg:p-10">
          <div className="flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
            <Link href="/demo" className="hover:text-foreground">
              Demo
            </Link>
            <span>/</span>
            <span>{demo.sourceWork}</span>
          </div>

          <div className="mt-8 grid gap-8 lg:grid-cols-[1.15fr_0.85fr] lg:items-start">
            <div className="max-w-4xl">
              <span className="app-chip">
                {demo.sourceWork} by {demo.sourceAuthor}
              </span>
              <h1 className="mt-7 max-w-5xl font-display text-[3rem] leading-[0.94] tracking-[-0.04em] text-foreground sm:text-[3.5rem]">{demo.title}</h1>
              <p className="mt-6 max-w-3xl text-base leading-8 text-muted-foreground sm:text-[1.1rem]">{demo.intro}</p>
            </div>

            <div className="grid gap-4 sm:grid-cols-3 lg:grid-cols-1">
              <div className="app-stat app-stat--accent">
                <p className="app-stat__label">Read time</p>
                <p className="mt-3 text-lg font-semibold text-foreground">{demo.readTime}</p>
                <p className="app-stat__note">A concrete public-domain example rather than abstract product copy.</p>
              </div>
              <div className="app-stat app-stat--success">
                <p className="app-stat__label">Source text</p>
                <p className="mt-3 text-lg font-semibold text-foreground">{demo.sourceWork}</p>
                <p className="app-stat__note">Chosen because the workflow is visible on the page.</p>
              </div>
              <div className="app-stat">
                <p className="app-stat__label">Related answers</p>
                <p className="app-stat__value">{relatedAnswers.length}</p>
                <p className="app-stat__note">Connected search-intent pages tied to the same workflow.</p>
              </div>
            </div>
          </div>
        </div>

        <div className="mt-8 grid gap-8 lg:grid-cols-[1.2fr_0.8fr]">
          <article className="space-y-6">
            <section className="app-panel rounded-[2rem] p-6 md:p-8">
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-muted-foreground">Featured insight</p>
              <p className="mt-4 text-base leading-8 text-muted-foreground md:text-lg">{demo.featuredInsight}</p>
            </section>

            {demo.sections.map((section) => (
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
            <div className="app-panel app-panel--strong rounded-[2rem] p-6 md:p-8">
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-muted-foreground">Why this page exists</p>
              <p className="mt-4 text-sm leading-7 text-muted-foreground">{demo.description}</p>
            </div>

            {article ? (
              <div className="app-panel rounded-[2rem] p-6 md:p-8">
                <p className="text-xs font-semibold uppercase tracking-[0.22em] text-muted-foreground">Related guide</p>
                <h2 className="mt-4 text-2xl font-semibold tracking-[-0.03em] text-foreground">{article.title}</h2>
                <p className="mt-3 text-sm leading-7 text-muted-foreground">{article.description}</p>
                <Link href={`/blog/${article.slug}`} className="mt-5 inline-flex items-center gap-2 font-semibold text-[rgb(var(--accent))]">
                  Open guide
                  <ContentArrowIcon />
                </Link>
              </div>
            ) : null}

            <div className="app-panel rounded-[2rem] p-6 md:p-8">
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-muted-foreground">Why demos work</p>
              <p className="mt-4 text-sm leading-7 text-muted-foreground">
                Public-domain examples make the product promise testable. Instead of talking abstractly about continuity or character memory, the page shows how those workflows would read against a recognizable manuscript.
              </p>
            </div>
          </aside>
        </div>
      </section>

      <section className="app-container pb-8">
        <div className="app-panel app-panel--subtle rounded-[2rem] p-6 md:p-8 lg:p-10">
          <div className="max-w-2xl">
            <p className="app-eyebrow">Related questions</p>
            <h2 className="mt-4 text-3xl font-semibold tracking-[-0.03em] text-foreground md:text-4xl">
              Supporting search questions tied to the same workflow.
            </h2>
          </div>

          <div className="mt-8 grid gap-5 lg:grid-cols-2">
            {relatedAnswers.map((answer) => (
              <article key={answer.slug} className="h-full rounded-[1.6rem] border border-[rgba(var(--border),0.76)] bg-white/70 p-6 dark:bg-white/[0.04]">
                <h3 className="text-xl font-semibold tracking-[-0.03em] text-foreground">
                  <Link href={`/answers/${answer.slug}`} className="hover:text-[rgb(var(--accent))]">
                    {answer.question}
                  </Link>
                </h3>
                <p className="mt-3 text-sm leading-7 text-muted-foreground">{answer.shortAnswer}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="app-container pb-20 pt-8 md:pb-24">
        <div className="app-panel app-panel--strong rounded-[2rem] p-7 md:p-10">
          <div className="max-w-3xl">
            <p className="app-eyebrow">Try LoreVia</p>
            <h2 className="mt-4 text-3xl font-semibold tracking-[-0.03em] text-foreground md:text-4xl">
              Apply the same workflow to your own manuscript.
            </h2>
            <p className="mt-4 text-base leading-8 text-muted-foreground md:text-lg">
              LoreVia helps authors turn drafts into searchable working systems for continuity, character memory, revision planning, and beta-reader preparation.
            </p>
          </div>
          <div className="mt-7 flex flex-col gap-3 sm:flex-row">
            <Link href="/register" className="app-button-primary gap-2">
              Start free
              <ContentArrowIcon />
            </Link>
            <Link href="/blog" className="app-button-secondary">
              Read the main guides
            </Link>
          </div>
        </div>
      </section>
    </PublicContentShell>
  )
}
