import type { Metadata } from "next"
import Link from "next/link"

import { PublicContentHeader, ContentArrowIcon } from "@/components/marketing/PublicContentHeader"
import { Reveal } from "@/components/marketing/Reveal"
import { JsonLdScript } from "@/components/seo/JsonLdScript"
import { blogArticles, demoPages, getAnswersByArticleSlug } from "@/lib/content"
import { BLOG_RSS_PATH, DEFAULT_OG_IMAGE, SITE_NAME, SITE_URL, buildCollectionPageJsonLd } from "@/lib/seo"

const featuredArticle = blogArticles[0]

export const metadata: Metadata = {
  title: "Blog",
  description:
    "Long-form LoreVia guides for fiction authors on character tracking, continuity, story bibles, writing software, and revision workflows.",
  keywords: [
    "fiction author blog",
    "novel continuity checker",
    "character tracking for writers",
    "writing software for novelists",
    "story bible for authors",
  ],
  alternates: {
    canonical: "/blog",
    types: {
      "application/rss+xml": BLOG_RSS_PATH,
    },
  },
  openGraph: {
    title: `LoreVia Blog | ${SITE_NAME}`,
    description:
      "Long-form LoreVia guides for fiction authors on character tracking, continuity, story bibles, writing software, and revision workflows.",
    url: `${SITE_URL}/blog`,
    images: [
      {
        url: DEFAULT_OG_IMAGE,
        width: 1200,
        height: 630,
        alt: "LoreVia blog for fiction authors",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: `LoreVia Blog | ${SITE_NAME}`,
    description:
      "Long-form LoreVia guides for fiction authors on character tracking, continuity, story bibles, writing software, and revision workflows.",
    images: [DEFAULT_OG_IMAGE],
  },
}

export default function BlogPage() {
  const jsonLd = buildCollectionPageJsonLd({
    name: "LoreVia Blog",
    description:
      "Long-form LoreVia guides for fiction authors on character tracking, continuity, story bibles, writing software, and revision workflows.",
    path: "/blog",
    about: [
      "fiction author guides",
      "character tracking",
      "continuity checking",
      "revision workflow",
    ],
  })

  return (
    <main className="app-shell overflow-hidden">
      <div className="app-shell__mesh" />
      <div className="absolute inset-x-0 top-0 -z-10 h-[34rem] bg-[radial-gradient(circle_at_top,rgba(15,118,110,0.16),transparent_40%),radial-gradient(circle_at_82%_10%,rgba(180,83,9,0.16),transparent_24%)]" />
      <JsonLdScript id="blog-collection-jsonld" data={jsonLd} />

      <PublicContentHeader activeSection="blog" />

      <section className="app-container py-16 md:py-24">
        <div className="grid gap-10 lg:grid-cols-[1.12fr_0.88fr] lg:items-start">
          <Reveal>
            <div className="max-w-3xl">
              <span className="app-chip">Author-focused SEO hub</span>
              <h1 className="app-title mt-7 max-w-4xl">
                Practical guides for fiction authors, not generic AI fluff.
              </h1>
              <p className="app-copy mt-6 max-w-2xl text-lg md:text-xl">
                LoreVia&apos;s blog is structured around the manuscript problems authors actually search for:
                character tracking, continuity control, story bibles, revision workflow, and software comparisons grounded in fiction writing.
              </p>

              <div className="mt-8 flex flex-col gap-3 sm:flex-row">
                <Link href={`/blog/${featuredArticle.slug}`} className="app-button-primary gap-2">
                  Read the featured guide
                  <ContentArrowIcon />
                </Link>
                <Link href="/answers" className="app-button-secondary">
                  Browse short answers
                </Link>
              </div>

              <div className="mt-10 grid gap-4 sm:grid-cols-3">
                <div className="app-stat app-stat--accent">
                  <p className="app-stat__label">Main guides</p>
                  <p className="app-stat__value">{blogArticles.length}</p>
                  <p className="app-stat__note">Long-form pages targeting high-intent author keywords.</p>
                </div>
                <div className="app-stat app-stat--warning">
                  <p className="app-stat__label">Q&A pages</p>
                  <p className="app-stat__value">10</p>
                  <p className="app-stat__note">Question pages that support topic clusters and internal linking.</p>
                </div>
                <div className="app-stat app-stat--success">
                  <p className="app-stat__label">Public demos</p>
                  <p className="app-stat__value">{demoPages.length}</p>
                  <p className="app-stat__note">Public-domain examples that make the workflow concrete.</p>
                </div>
              </div>
            </div>
          </Reveal>

          <Reveal delay={120}>
            <article className="app-panel app-panel--strong rounded-[2rem] p-6 md:p-8">
              <div className="flex items-center justify-between gap-3">
                <span className="app-chip bg-[rgba(15,118,110,0.12)] text-[rgb(var(--accent))]">
                  Featured guide
                </span>
                <span className="text-xs font-semibold uppercase tracking-[0.24em] text-muted-foreground">
                  {featuredArticle.publishedLabel}
                </span>
              </div>

              <p className="mt-6 text-sm font-semibold uppercase tracking-[0.24em] text-[rgb(var(--accent))]">
                {featuredArticle.category}
              </p>
              <h2 className="mt-4 font-[var(--font-newsreader)] text-4xl leading-tight tracking-[-0.04em] text-foreground md:text-5xl">
                {featuredArticle.title}
              </h2>
              <p className="app-copy mt-5 text-base md:text-lg">{featuredArticle.description}</p>

              <div className="mt-8 rounded-[1.5rem] border border-[rgba(var(--border),0.8)] bg-white/55 p-5 dark:bg-white/5">
                <p className="text-xs font-semibold uppercase tracking-[0.22em] text-muted-foreground">What this page covers</p>
                <ul className="mt-4 space-y-3 text-sm leading-7 text-foreground/80">
                  {featuredArticle.highlights.map((item) => (
                    <li key={item} className="flex gap-3">
                      <span className="mt-2 h-1.5 w-1.5 rounded-full bg-[rgb(var(--accent))]" />
                      <span>{item}</span>
                    </li>
                  ))}
                </ul>
              </div>

              <div className="mt-6 flex items-center justify-between gap-4 border-t border-[rgba(var(--border),0.7)] pt-5 text-sm text-muted-foreground">
                <span>{featuredArticle.readTime}</span>
                <Link href={`/blog/${featuredArticle.slug}`} className="font-semibold text-[rgb(var(--accent))]">
                  Open article
                </Link>
              </div>
            </article>
          </Reveal>
        </div>
      </section>

      <section className="app-container pb-8">
        <Reveal>
          <div className="app-panel rounded-[2rem] p-6 md:p-8 lg:p-10">
            <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
              <div className="max-w-2xl">
                <p className="app-eyebrow">Main SEO articles</p>
                <h2 className="mt-4 font-[var(--font-newsreader)] text-3xl tracking-[-0.04em] text-foreground md:text-4xl">
                  Long guides built around author intent.
                </h2>
                <p className="app-copy mt-4">
                  These are the pages meant to rank for the core manuscript problems LoreVia solves, with clear internal links out to answers and demos.
                </p>
              </div>
              <Link href="/demo" className="app-button-secondary">
                See public demos
              </Link>
            </div>

            <div className="mt-10 grid gap-5 lg:grid-cols-2">
              {blogArticles.map((article, index) => (
                <Reveal key={article.slug} delay={index * 70}>
                  <article className="h-full rounded-[1.6rem] border border-[rgba(var(--border),0.76)] bg-white/58 p-6 dark:bg-white/[0.04]">
                    <div className="flex flex-wrap items-center gap-3 text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                      <span>{article.category}</span>
                      <span>{article.readTime}</span>
                    </div>
                    <h3 className="mt-4 text-2xl font-semibold tracking-[-0.03em] text-foreground">
                      <Link href={`/blog/${article.slug}`} className="hover:text-[rgb(var(--accent))]">
                        {article.title}
                      </Link>
                    </h3>
                    <p className="app-copy mt-3 text-sm">{article.description}</p>
                    <div className="mt-5 flex flex-wrap gap-2">
                      {article.keywords.slice(0, 2).map((keyword) => (
                        <span key={keyword} className="app-chip px-3 py-2 text-xs">
                          {keyword}
                        </span>
                      ))}
                    </div>
                  </article>
                </Reveal>
              ))}
            </div>
          </div>
        </Reveal>
      </section>

      <section className="app-container pb-8 pt-8">
        <Reveal>
          <div className="app-panel app-panel--subtle rounded-[2rem] p-6 md:p-8 lg:p-10">
            <div className="max-w-2xl">
              <p className="app-eyebrow">Question clusters</p>
              <h2 className="mt-4 font-[var(--font-newsreader)] text-3xl tracking-[-0.04em] text-foreground md:text-4xl">
                Short answer pages that point readers into deeper guides.
              </h2>
              <p className="app-copy mt-4">
                Each answer page targets a focused search question, gives a useful direct answer, and links back to the stronger guide page for the topic.
              </p>
            </div>

            <div className="mt-10 grid gap-5 lg:grid-cols-3">
              {blogArticles.slice(0, 3).map((article, index) => {
                const answerPages = getAnswersByArticleSlug(article.slug)
                return (
                  <Reveal key={article.slug} delay={index * 80}>
                    <article className="h-full rounded-[1.6rem] border border-[rgba(var(--border),0.76)] bg-white/58 p-6 dark:bg-white/[0.04]">
                      <p className="text-xs font-semibold uppercase tracking-[0.22em] text-muted-foreground">
                        Supports {article.title}
                      </p>
                      <ul className="mt-5 space-y-4 text-sm leading-7 text-foreground/85">
                        {answerPages.slice(0, 3).map((answer) => (
                          <li key={answer.slug}>
                            <Link href={`/answers/${answer.slug}`} className="font-medium hover:text-[rgb(var(--accent))]">
                              {answer.question}
                            </Link>
                          </li>
                        ))}
                      </ul>
                    </article>
                  </Reveal>
                )
              })}
            </div>
          </div>
        </Reveal>
      </section>

      <section className="app-container pb-20 pt-8 md:pb-24">
        <Reveal>
          <div className="rounded-[2rem] border border-[rgba(var(--border),0.8)] bg-[linear-gradient(135deg,rgba(15,118,110,0.12),rgba(255,255,255,0.72),rgba(180,83,9,0.12))] p-7 md:p-10 dark:bg-[linear-gradient(135deg,rgba(45,212,191,0.08),rgba(255,255,255,0.03),rgba(251,146,60,0.08))]">
            <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
              <div className="max-w-3xl">
                <p className="app-eyebrow">Public-domain examples</p>
                <h2 className="mt-4 font-[var(--font-newsreader)] text-3xl tracking-[-0.04em] text-foreground md:text-4xl">
                  Demonstrations that show what LoreVia-style manuscript intelligence looks like in practice.
                </h2>
                <p className="app-copy mt-4 text-base md:text-lg">
                  Instead of generic SEO filler, these pages use public-domain books to show how character tracking, timeline logic, and relationship mapping become visible inside real fiction.
                </p>
              </div>
              <Link href="/answers" className="app-button-secondary">
                Browse all answers
              </Link>
            </div>

            <div className="mt-8 grid gap-5 lg:grid-cols-3">
              {demoPages.map((demo, index) => (
                <Reveal key={demo.slug} delay={index * 70}>
                  <article className="h-full rounded-[1.6rem] border border-[rgba(var(--border),0.76)] bg-white/58 p-6 dark:bg-white/[0.04]">
                    <p className="text-xs font-semibold uppercase tracking-[0.22em] text-muted-foreground">
                      {demo.sourceWork} by {demo.sourceAuthor}
                    </p>
                    <h3 className="mt-4 text-2xl font-semibold tracking-[-0.03em] text-foreground">
                      <Link href={`/demo/${demo.slug}`} className="hover:text-[rgb(var(--accent))]">
                        {demo.title}
                      </Link>
                    </h3>
                    <p className="app-copy mt-3 text-sm">{demo.featuredInsight}</p>
                  </article>
                </Reveal>
              ))}
            </div>
          </div>
        </Reveal>
      </section>
    </main>
  )
}
