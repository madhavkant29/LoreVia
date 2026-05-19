import type { Metadata } from "next"
import Link from "next/link"
import { notFound } from "next/navigation"

import { PublicContentHeader, ContentArrowIcon } from "@/components/marketing/PublicContentHeader"
import { Reveal } from "@/components/marketing/Reveal"
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
    <main className="app-shell overflow-hidden">
      <div className="app-shell__mesh" />
      <div className="absolute inset-x-0 top-0 -z-10 h-[30rem] bg-[radial-gradient(circle_at_top,rgba(15,118,110,0.15),transparent_38%),radial-gradient(circle_at_80%_12%,rgba(180,83,9,0.14),transparent_24%)]" />
      <JsonLdScript id={`blog-jsonld-${article.slug}`} data={jsonLd} />
      <JsonLdScript id={`blog-breadcrumbs-jsonld-${article.slug}`} data={breadcrumbJsonLd} />

      <PublicContentHeader activeSection="blog" />

      <section className="app-container py-14 md:py-20">
        <Reveal>
          <div className="max-w-4xl">
            <div className="flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
              <Link href="/blog" className="hover:text-foreground">
                Blog
              </Link>
              <span>/</span>
              <span>{article.category}</span>
            </div>
            <span className="app-chip mt-6">{article.category}</span>
            <h1 className="app-title mt-7 max-w-5xl">{article.title}</h1>
            <p className="app-copy mt-6 max-w-3xl text-lg md:text-xl">{article.intro}</p>

            <div className="mt-8 flex flex-wrap gap-3 text-sm text-muted-foreground">
              <span className="app-chip px-4 py-2">{article.publishedLabel}</span>
              <span className="app-chip px-4 py-2">{article.readTime}</span>
              <span className="app-chip px-4 py-2">For fiction authors</span>
            </div>
          </div>
        </Reveal>

        <div className="mt-12 grid gap-8 lg:grid-cols-[0.75fr_1.25fr]">
          <Reveal>
            <aside className="app-panel app-panel--strong rounded-[2rem] p-6 md:p-8">
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-muted-foreground">Key takeaways</p>
              <ul className="mt-5 space-y-4 text-sm leading-7 text-foreground/85">
                {article.highlights.map((highlight) => (
                  <li key={highlight} className="flex gap-3">
                    <span className="mt-2 h-1.5 w-1.5 rounded-full bg-[rgb(var(--accent))]" />
                    <span>{highlight}</span>
                  </li>
                ))}
              </ul>

              {demoPage ? (
                <div className="mt-8 rounded-[1.4rem] border border-[rgba(var(--border),0.76)] bg-white/55 p-5 dark:bg-white/[0.04]">
                  <p className="text-xs font-semibold uppercase tracking-[0.22em] text-muted-foreground">See it in action</p>
                  <h2 className="mt-3 text-xl font-semibold tracking-[-0.02em] text-foreground">{demoPage.title}</h2>
                  <p className="app-copy mt-3 text-sm">{demoPage.featuredInsight}</p>
                  <Link href={`/demo/${demoPage.slug}`} className="mt-4 inline-flex items-center gap-2 font-semibold text-[rgb(var(--accent))]">
                    Open demo
                    <ContentArrowIcon />
                  </Link>
                </div>
              ) : null}
            </aside>
          </Reveal>

          <Reveal delay={100}>
            <article className="space-y-8">
              {article.sections.map((section) => (
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

                  {section.highlight ? (
                    <div className="mt-6 rounded-[1.4rem] border border-[rgba(var(--border),0.8)] bg-[rgba(15,118,110,0.08)] p-5 text-sm leading-7 text-foreground/85 dark:bg-[rgba(45,212,191,0.08)]">
                      {section.highlight}
                    </div>
                  ) : null}
                </section>
              ))}
            </article>
          </Reveal>
        </div>
      </section>

      <section className="app-container pb-8">
        <Reveal>
          <div className="app-panel app-panel--subtle rounded-[2rem] p-6 md:p-8 lg:p-10">
            <div className="max-w-2xl">
              <p className="app-eyebrow">Related answers</p>
              <h2 className="mt-4 font-[var(--font-newsreader)] text-3xl tracking-[-0.04em] text-foreground md:text-4xl">
                Smaller question pages that reinforce this topic cluster.
              </h2>
            </div>

            <div className="mt-8 grid gap-5 lg:grid-cols-3">
              {supportingAnswers.map((answer, index) => (
                <Reveal key={answer.slug} delay={index * 70}>
                  <article className="h-full rounded-[1.6rem] border border-[rgba(var(--border),0.76)] bg-white/58 p-6 dark:bg-white/[0.04]">
                    <h3 className="text-xl font-semibold tracking-[-0.03em] text-foreground">
                      <Link href={`/answers/${answer.slug}`} className="hover:text-[rgb(var(--accent))]">
                        {answer.question}
                      </Link>
                    </h3>
                    <p className="app-copy mt-3 text-sm">{answer.description}</p>
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
                Build a searchable manuscript workspace instead of keeping your story in your head.
              </h2>
              <p className="app-copy mt-4 text-base md:text-lg">
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
        </Reveal>
      </section>
    </main>
  )
}
