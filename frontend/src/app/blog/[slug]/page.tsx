import type { Metadata } from "next"
import Link from "next/link"
import { notFound } from "next/navigation"

import { ContentArrowIcon } from "@/components/marketing/PublicContentHeader"
import { PublicContentShell } from "@/components/marketing/PublicContentShell"
import { JsonLdScript } from "@/components/seo/JsonLdScript"
import {
  blogArticles,
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
  return blogArticles.map((article) => ({ slug: article.slug }))
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const { slug } = await params
  const article = getBlogArticleBySlug(slug)

  if (!article) {
    return {}
  }

  return {
    title: article.title,
    description: article.description,
    keywords: article.keywords,
    authors: [{ name: SITE_NAME, url: toAbsoluteUrl("/") }],
    category: article.category,
    alternates: {
      canonical: `/blog/${article.slug}`,
    },
    openGraph: {
      type: "article",
      title: `${article.title} | ${SITE_NAME}`,
      description: article.description,
      url: toAbsoluteUrl(`/blog/${article.slug}`),
      publishedTime: article.publishedAt,
      images: [
        {
          url: DEFAULT_OG_IMAGE,
          width: 1200,
          height: 630,
          alt: article.title,
        },
      ],
    },
    twitter: {
      card: "summary_large_image",
      title: `${article.title} | ${SITE_NAME}`,
      description: article.description,
      images: [DEFAULT_OG_IMAGE],
    },
  }
}

export default async function BlogArticlePage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params
  const article = getBlogArticleBySlug(slug)

  if (!article) {
    notFound()
  }

  const supportingAnswers = getAnswerPagesBySlugs(article.supportingAnswerSlugs)
  const demoPage = getDemoPageBySlug(article.demoSlug)

  const jsonLd = buildArticleJsonLd({
    type: "BlogPosting",
    title: article.title,
    description: article.description,
    path: `/blog/${article.slug}`,
    datePublished: article.publishedAt,
    keywords: article.keywords,
    about: [article.category, "fiction writing", "manuscript revision"],
  })
  const breadcrumbJsonLd = buildBreadcrumbJsonLd([
    { name: "Home", path: "/" },
    { name: "Blog", path: "/blog" },
    { name: article.title, path: `/blog/${article.slug}` },
  ])

  return (
    <PublicContentShell activeSection="blog">
      <JsonLdScript id={`blog-jsonld-${article.slug}`} data={jsonLd} />
      <JsonLdScript id={`blog-breadcrumbs-jsonld-${article.slug}`} data={breadcrumbJsonLd} />

      <section className="app-container py-10 md:py-14">
        <div className="app-panel app-panel--strong rounded-lg p-6 md:p-8 lg:p-10">
          <div className="flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
            <Link href="/blog" className="hover:text-foreground">
              Blog
            </Link>
            <span>/</span>
            <span>{article.category}</span>
          </div>

          <div className="mt-8 grid gap-8 lg:grid-cols-[1.18fr_0.82fr] lg:items-start">
            <div className="max-w-4xl">
              <span className="app-chip">{article.category}</span>
              <h1 className="mt-7 max-w-5xl font-display text-[3rem] leading-[0.94] tracking-[-0.04em] text-foreground sm:text-[3.5rem]">{article.title}</h1>
              <p className="mt-6 max-w-3xl text-base leading-8 text-muted-foreground sm:text-[1.1rem]">{article.intro}</p>
            </div>

            <div className="grid gap-4 sm:grid-cols-3 lg:grid-cols-1">
              <div className="app-stat app-stat--accent">
                <p className="app-stat__label">Published</p>
                <p className="mt-3 text-lg font-semibold text-foreground">{article.publishedLabel}</p>
                <p className="app-stat__note">Fresh editorial copy built for author search intent.</p>
              </div>
              <div className="app-stat">
                <p className="app-stat__label">Read time</p>
                <p className="mt-3 text-lg font-semibold text-foreground">{article.readTime}</p>
                <p className="app-stat__note">Long-form guidance rather than a landing-page summary.</p>
              </div>
              <div className="app-stat app-stat--success">
                <p className="app-stat__label">Key points</p>
                <p className="app-stat__value">{article.highlights.length}</p>
                <p className="app-stat__note">Practical takeaways tied to revision workflow.</p>
              </div>
            </div>
          </div>
        </div>
        
        <div className="mt-8 grid gap-8 lg:grid-cols-[0.75fr_1.25fr]">
          <aside className="space-y-6 lg:sticky lg:top-28">
            <div className="app-panel app-panel--strong rounded-lg p-6 md:p-8">
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-muted-foreground">Key takeaways</p>
              <ul className="mt-5 space-y-4 text-sm leading-7 text-foreground/85">
                {article.highlights.map((highlight) => (
                  <li key={highlight} className="flex gap-3">
                    <span className="mt-2 h-1.5 w-1.5 rounded-full bg-[rgb(var(--accent))]" />
                    <span>{highlight}</span>
                  </li>
                ))}
              </ul>
            </div>

            <div className="app-panel rounded-lg p-6 md:p-8">
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-muted-foreground">Why this guide exists</p>
              <p className="mt-4 text-sm leading-7 text-muted-foreground">{article.description}</p>
            </div>

            {demoPage ? (
              <div className="app-panel rounded-lg p-6 md:p-8">
                <p className="text-xs font-semibold uppercase tracking-[0.22em] text-muted-foreground">See it in action</p>
                <h2 className="mt-3 text-xl font-semibold tracking-[-0.02em] text-foreground">{demoPage.title}</h2>
                <p className="mt-3 text-sm leading-7 text-muted-foreground">{demoPage.featuredInsight}</p>
                <Link href={`/demo/${demoPage.slug}`} className="mt-4 inline-flex items-center gap-2 font-semibold text-[rgb(var(--accent))]">
                  Open demo
                  <ContentArrowIcon />
                </Link>
              </div>
            ) : null}
          </aside>

          <article className="space-y-6">
            {article.sections.map((section) => (
              <section key={section.heading} className="app-panel rounded-lg p-6 md:p-8">
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

                {section.highlight ? (
                  <div className="mt-6 rounded-lg border border-[rgba(var(--border),0.8)] bg-[rgba(31,97,93,0.08)] p-5 text-sm leading-7 text-foreground/85 dark:bg-[rgba(105,180,173,0.08)]">
                    {section.highlight}
                  </div>
                ) : null}
              </section>
            ))}
          </article>
        </div>
      </section>

      <section className="app-container pb-8">
        <div className="app-panel app-panel--subtle rounded-lg p-6 md:p-8 lg:p-10">
          <div className="max-w-2xl">
            <p className="app-eyebrow">Related answers</p>
            <h2 className="mt-4 text-3xl font-semibold tracking-[-0.03em] text-foreground md:text-4xl">
              Smaller question pages that reinforce this topic cluster.
            </h2>
          </div>

          <div className="mt-8 grid gap-5 lg:grid-cols-3">
            {supportingAnswers.map((answer) => (
              <article key={answer.slug} className="h-full rounded-lg border border-[rgba(var(--border),0.76)] bg-white/70 p-6 dark:bg-white/[0.04]">
                <h3 className="text-xl font-semibold tracking-[-0.03em] text-foreground">
                  <Link href={`/answers/${answer.slug}`} className="hover:text-[rgb(var(--accent))]">
                    {answer.question}
                  </Link>
                </h3>
                <p className="mt-3 text-sm leading-7 text-muted-foreground">{answer.description}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="app-container pb-20 pt-8 md:pb-24">
        <div className="app-panel app-panel--strong rounded-lg p-7 md:p-10">
          <div className="max-w-3xl">
            <p className="app-eyebrow">Try LoreVia</p>
            <h2 className="mt-4 text-3xl font-semibold tracking-[-0.03em] text-foreground md:text-4xl">
              Build a searchable manuscript workspace instead of keeping your story in your head.
            </h2>
            <p className="mt-4 text-base leading-8 text-muted-foreground md:text-lg">
              LoreVia helps fiction authors track characters, check continuity, inspect timelines, and ask grounded questions that stay tied to the actual draft.
            </p>
          </div>
          <div className="mt-7 flex flex-col gap-3 sm:flex-row">
            <Link href="/register" className="app-button-primary gap-2">
              Start free
              <ContentArrowIcon />
            </Link>
            <Link href="/answers" className="app-button-secondary">
              Explore more questions
            </Link>
          </div>
        </div>
      </section>
    </PublicContentShell>
  )
}
