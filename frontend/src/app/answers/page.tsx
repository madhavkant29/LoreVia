import type { Metadata } from "next"
import Link from "next/link"

import { ContentArrowIcon } from "@/components/marketing/PublicContentHeader"
import { PublicContentShell } from "@/components/marketing/PublicContentShell"
import { JsonLdScript } from "@/components/seo/JsonLdScript"
import { answerPages, blogArticles, getBlogArticleBySlug } from "@/lib/content"
import { DEFAULT_OG_IMAGE, SITE_NAME, SITE_URL, buildCollectionPageJsonLd } from "@/lib/seo"

export const metadata: Metadata = {
  title: "Answers",
  description:
    "Short, useful question pages for fiction authors on character tracking, continuity, manuscript analysis, story bibles, timelines, and beta-reader prep.",
  keywords: [
    "fiction writing answers",
    "how do authors avoid continuity errors",
    "what is a story bible",
    "how do I track character arcs",
  ],
  alternates: {
    canonical: "/answers",
  },
  openGraph: {
    title: `LoreVia Answers | ${SITE_NAME}`,
    description:
      "Short, useful question pages for fiction authors on character tracking, continuity, manuscript analysis, story bibles, timelines, and beta-reader prep.",
    url: `${SITE_URL}/answers`,
    images: [
      {
        url: DEFAULT_OG_IMAGE,
        width: 1200,
        height: 630,
        alt: "LoreVia answers for fiction authors",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: `LoreVia Answers | ${SITE_NAME}`,
    description:
      "Short, useful question pages for fiction authors on character tracking, continuity, manuscript analysis, story bibles, timelines, and beta-reader prep.",
    images: [DEFAULT_OG_IMAGE],
  },
}

export default function AnswersPage() {
  const jsonLd = buildCollectionPageJsonLd({
    name: "LoreVia Answers",
    description:
      "Short, useful question pages for fiction authors on character tracking, continuity, manuscript analysis, story bibles, timelines, and beta-reader prep.",
    path: "/answers",
    about: [
      "fiction writing questions",
      "character tracking",
      "continuity checking",
      "story bibles",
    ],
  })

  return (
    <PublicContentShell activeSection="answers">
      <JsonLdScript id="answers-collection-jsonld" data={jsonLd} />

      <section className="app-container py-10 md:py-14">
        <div className="app-panel app-panel--strong rounded-[2rem] p-6 md:p-8 lg:p-10">
          <div className="grid gap-10 lg:grid-cols-[1.05fr_0.95fr] lg:items-start">
            <div className="max-w-3xl">
              <span className="app-chip">Question pages</span>
              <h1 className="mt-7 max-w-4xl font-display text-[3rem] leading-[0.94] tracking-[-0.04em] text-foreground sm:text-[3.5rem]">
                Fast answers for fiction-author questions that still lead somewhere useful.
              </h1>
              <p className="mt-6 max-w-2xl text-base leading-8 text-muted-foreground sm:text-[1.1rem]">
                Each page answers a specific search query clearly, links back to a stronger guide, and keeps the language focused on author workflow, manuscript intelligence, and continuity control.
              </p>

              <div className="mt-8 flex flex-col gap-3 sm:flex-row">
                <Link href={`/answers/${answerPages[0].slug}`} className="app-button-primary gap-2">
                  Read an answer page
                  <ContentArrowIcon />
                </Link>
                <Link href="/blog" className="app-button-secondary">
                  View main guides
                </Link>
              </div>
            </div>

            <div className="rounded-[1.8rem] border border-[rgba(var(--border),0.76)] bg-white/72 p-6 dark:bg-white/[0.04] md:p-8">
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-muted-foreground">Topic clusters</p>
              <div className="mt-6 grid gap-4 sm:grid-cols-2">
                {blogArticles.slice(0, 4).map((article) => {
                  const linkedCount = answerPages.filter((answer) => answer.articleSlug === article.slug).length
                  return (
                    <div key={article.slug} className="rounded-[1.4rem] border border-[rgba(var(--border),0.76)] bg-white/75 p-5 dark:bg-white/[0.04]">
                      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                        {linkedCount} supporting pages
                      </p>
                      <h2 className="mt-3 text-xl font-semibold tracking-[-0.03em] text-foreground">{article.title}</h2>
                    </div>
                  )
                })}
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="app-container pb-20 md:pb-24">
        <div className="app-panel rounded-[2rem] p-6 md:p-8 lg:p-10">
          <div className="max-w-2xl">
            <p className="app-eyebrow">All questions</p>
            <h2 className="mt-4 text-3xl font-semibold tracking-[-0.03em] text-foreground md:text-4xl">
              Specific problems authors search for during drafting and revision.
            </h2>
          </div>

          <div className="mt-10 grid gap-5 lg:grid-cols-2">
            {answerPages.map((answer) => {
              const article = getBlogArticleBySlug(answer.articleSlug)
              return (
                <article key={answer.slug} className="h-full rounded-[1.6rem] border border-[rgba(var(--border),0.76)] bg-white/66 p-6 dark:bg-white/[0.04]">
                  <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
                    Linked guide: {article?.title ?? "LoreVia guide"}
                  </p>
                  <h3 className="mt-4 text-2xl font-semibold tracking-[-0.03em] text-foreground">
                    <Link href={`/answers/${answer.slug}`} className="hover:text-[rgb(var(--accent))]">
                      {answer.question}
                    </Link>
                  </h3>
                  <p className="mt-3 text-sm leading-7 text-muted-foreground">{answer.shortAnswer}</p>
                </article>
              )
            })}
          </div>
        </div>
      </section>
    </PublicContentShell>
  )
}
