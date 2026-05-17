import type { Metadata } from "next"
import Link from "next/link"
import Script from "next/script"
import { notFound } from "next/navigation"

import { PublicContentHeader, ContentArrowIcon } from "@/components/marketing/PublicContentHeader"
import { Reveal } from "@/components/marketing/Reveal"
import {
  demoPages,
  getAnswerPagesBySlugs,
  getBlogArticleBySlug,
  getDemoPageBySlug,
} from "@/lib/content"
import { DEFAULT_OG_IMAGE, SITE_NAME, buildBreadcrumbJsonLd, toAbsoluteUrl } from "@/lib/seo"

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

  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "Article",
    headline: demo.title,
    description: demo.description,
    datePublished: demo.publishedAt,
    dateModified: demo.publishedAt,
    author: {
      "@type": "Organization",
      name: SITE_NAME,
    },
    mainEntityOfPage: toAbsoluteUrl(`/demo/${demo.slug}`),
  }
  const breadcrumbJsonLd = buildBreadcrumbJsonLd([
    { name: "Home", path: "/" },
    { name: "Demo", path: "/demo" },
    { name: demo.title, path: `/demo/${demo.slug}` },
  ])

  return (
    <main className="app-shell overflow-hidden">
      <div className="app-shell__mesh" />
      <div className="absolute inset-x-0 top-0 -z-10 h-[28rem] bg-[radial-gradient(circle_at_top,rgba(15,118,110,0.14),transparent_36%),radial-gradient(circle_at_85%_10%,rgba(180,83,9,0.12),transparent_24%)]" />
      <Script id={`demo-jsonld-${demo.slug}`} type="application/ld+json" strategy="beforeInteractive">
        {JSON.stringify(jsonLd).replace(/</g, "\\u003c")}
      </Script>
      <Script id={`demo-breadcrumbs-jsonld-${demo.slug}`} type="application/ld+json" strategy="beforeInteractive">
        {JSON.stringify(breadcrumbJsonLd).replace(/</g, "\\u003c")}
      </Script>

      <PublicContentHeader activeSection="demo" />

      <section className="app-container py-14 md:py-20">
        <Reveal>
          <div className="max-w-4xl">
            <div className="flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
              <Link href="/demo" className="hover:text-foreground">
                Demo
              </Link>
              <span>/</span>
              <span>{demo.sourceWork}</span>
            </div>
            <span className="app-chip mt-6">
              {demo.sourceWork} by {demo.sourceAuthor}
            </span>
            <h1 className="app-title mt-7 max-w-5xl">{demo.title}</h1>
            <p className="app-copy mt-6 max-w-3xl text-lg md:text-xl">{demo.featuredInsight}</p>
          </div>
        </Reveal>

        <div className="mt-12 grid gap-8 lg:grid-cols-[1.2fr_0.8fr]">
          <Reveal>
            <article className="space-y-8">
              {demo.sections.map((section) => (
                <section key={section.heading} className="app-panel rounded-[2rem] p-6 md:p-8">
                  <h2 className="font-[var(--font-newsreader)] text-3xl tracking-[-0.04em] text-foreground md:text-4xl">
                    {section.heading}
                  </h2>
                  <div className="mt-5 space-y-4">
                    {section.body.map((paragraph) => (
                      <p key={paragraph} className="app-copy text-base md:text-lg">
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
          </Reveal>

          <Reveal delay={100}>
            <aside className="space-y-6">
              <div className="app-panel app-panel--strong rounded-[2rem] p-6 md:p-8">
                <p className="text-xs font-semibold uppercase tracking-[0.22em] text-muted-foreground">Why this page exists</p>
                <p className="app-copy mt-4 text-sm">{demo.description}</p>
              </div>

              {article ? (
                <div className="app-panel rounded-[2rem] p-6 md:p-8">
                  <p className="text-xs font-semibold uppercase tracking-[0.22em] text-muted-foreground">Related guide</p>
                  <h2 className="mt-4 text-2xl font-semibold tracking-[-0.03em] text-foreground">{article.title}</h2>
                  <p className="app-copy mt-3 text-sm">{article.description}</p>
                  <Link href={`/blog/${article.slug}`} className="mt-5 inline-flex items-center gap-2 font-semibold text-[rgb(var(--accent))]">
                    Open guide
                    <ContentArrowIcon />
                  </Link>
                </div>
              ) : null}
            </aside>
          </Reveal>
        </div>
      </section>

      <section className="app-container pb-8">
        <Reveal>
          <div className="app-panel app-panel--subtle rounded-[2rem] p-6 md:p-8 lg:p-10">
            <div className="max-w-2xl">
              <p className="app-eyebrow">Related questions</p>
              <h2 className="mt-4 font-[var(--font-newsreader)] text-3xl tracking-[-0.04em] text-foreground md:text-4xl">
                Supporting search questions tied to the same workflow.
              </h2>
            </div>

            <div className="mt-8 grid gap-5 lg:grid-cols-2">
              {relatedAnswers.map((answer, index) => (
                <Reveal key={answer.slug} delay={index * 70}>
                  <article className="h-full rounded-[1.6rem] border border-[rgba(var(--border),0.76)] bg-white/58 p-6 dark:bg-white/[0.04]">
                    <h3 className="text-xl font-semibold tracking-[-0.03em] text-foreground">
                      <Link href={`/answers/${answer.slug}`} className="hover:text-[rgb(var(--accent))]">
                        {answer.question}
                      </Link>
                    </h3>
                    <p className="app-copy mt-3 text-sm">{answer.shortAnswer}</p>
                  </article>
                </Reveal>
              ))}
            </div>
          </div>
        </Reveal>
      </section>

      <section className="app-container pb-20 pt-8 md:pb-24">
        <Reveal>
          <div className="rounded-[2rem] border border-[rgba(var(--border),0.8)] bg-[linear-gradient(135deg,rgba(15,118,110,0.12),rgba(255,255,255,0.72),rgba(180,83,9,0.12))] p-7 md:p-10 dark:bg-[linear-gradient(135deg,rgba(45,212,191,0.08),rgba(255,255,255,0.03),rgba(251,146,60,0.08))]">
            <div className="max-w-3xl">
              <p className="app-eyebrow">Try LoreVia</p>
              <h2 className="mt-4 font-[var(--font-newsreader)] text-3xl tracking-[-0.04em] text-foreground md:text-4xl">
                Apply the same workflow to your own manuscript.
              </h2>
              <p className="app-copy mt-4 text-base md:text-lg">
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
        </Reveal>
      </section>
    </main>
  )
}
