import type { Metadata } from "next"
import Link from "next/link"

import { PublicContentHeader, ContentArrowIcon } from "@/components/marketing/PublicContentHeader"
import { Reveal } from "@/components/marketing/Reveal"
import { JsonLdScript } from "@/components/seo/JsonLdScript"
import { demoPages, getBlogArticleBySlug } from "@/lib/content"
import { DEFAULT_OG_IMAGE, SITE_NAME, SITE_URL, buildCollectionPageJsonLd } from "@/lib/seo"

export const metadata: Metadata = {
  title: "Demo",
  description:
    "Public-domain LoreVia demos showing how character tracking, relationship mapping, and timeline analysis support fiction authors.",
  keywords: [
    "public domain writing demos",
    "character tracking demo",
    "story timeline tracker demo",
    "relationship map for novelists",
  ],
  alternates: {
    canonical: "/demo",
  },
  openGraph: {
    title: `LoreVia Demo | ${SITE_NAME}`,
    description:
      "Public-domain LoreVia demos showing how character tracking, relationship mapping, and timeline analysis support fiction authors.",
    url: `${SITE_URL}/demo`,
    images: [
      {
        url: DEFAULT_OG_IMAGE,
        width: 1200,
        height: 630,
        alt: "LoreVia public-domain demos",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: `LoreVia Demo | ${SITE_NAME}`,
    description:
      "Public-domain LoreVia demos showing how character tracking, relationship mapping, and timeline analysis support fiction authors.",
    images: [DEFAULT_OG_IMAGE],
  },
}

export default function DemoIndexPage() {
  const jsonLd = buildCollectionPageJsonLd({
    name: "LoreVia Demo",
    description:
      "Public-domain LoreVia demos showing how character tracking, relationship mapping, and timeline analysis support fiction authors.",
    path: "/demo",
    about: [
      "public-domain fiction",
      "character tracking demo",
      "timeline analysis",
      "relationship mapping",
    ],
  })

  return (
    <main className="app-shell overflow-hidden">
      <div className="app-shell__mesh" />
      <div className="absolute inset-x-0 top-0 -z-10 h-[30rem] bg-[radial-gradient(circle_at_top,rgba(15,118,110,0.14),transparent_36%),radial-gradient(circle_at_80%_10%,rgba(180,83,9,0.14),transparent_24%)]" />
      <JsonLdScript id="demo-collection-jsonld" data={jsonLd} />

      <PublicContentHeader activeSection="demo" />

      <section className="app-container py-16 md:py-24">
        <div className="grid gap-10 lg:grid-cols-[1.05fr_0.95fr] lg:items-start">
          <Reveal>
            <div className="max-w-3xl">
              <span className="app-chip">Public-domain examples</span>
              <h1 className="app-title mt-7 max-w-4xl">
                Examples that show the workflow, not just the promise.
              </h1>
              <p className="app-copy mt-6 max-w-2xl text-lg md:text-xl">
                LoreVia&apos;s strongest SEO angle is manuscript intelligence for fiction authors. These demo pages use public-domain books to show how character tracking, relationship mapping, and continuity review become tangible.
              </p>

              <div className="mt-8 flex flex-col gap-3 sm:flex-row">
                <Link href={`/demo/${demoPages[0].slug}`} className="app-button-primary gap-2">
                  Open a demo
                  <ContentArrowIcon />
                </Link>
                <Link href="/blog" className="app-button-secondary">
                  Read the full guides
                </Link>
              </div>
            </div>
          </Reveal>

          <Reveal delay={100}>
            <div className="app-panel app-panel--strong rounded-[2rem] p-6 md:p-8">
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-muted-foreground">Why these pages matter</p>
              <ul className="mt-6 space-y-4 text-sm leading-7 text-foreground/85">
                <li className="flex gap-3">
                  <span className="mt-2 h-1.5 w-1.5 rounded-full bg-[rgb(var(--accent))]" />
                  <span>They turn abstract product claims into visible editorial workflows.</span>
                </li>
                <li className="flex gap-3">
                  <span className="mt-2 h-1.5 w-1.5 rounded-full bg-[rgb(var(--accent))]" />
                  <span>They give LoreVia pages original examples instead of template-style filler.</span>
                </li>
                <li className="flex gap-3">
                  <span className="mt-2 h-1.5 w-1.5 rounded-full bg-[rgb(var(--accent))]" />
                  <span>They create natural internal links between guides, answers, and product intent.</span>
                </li>
              </ul>
            </div>
          </Reveal>
        </div>
      </section>

      <section className="app-container pb-20 md:pb-24">
        <Reveal>
          <div className="app-panel rounded-[2rem] p-6 md:p-8 lg:p-10">
            <div className="max-w-2xl">
              <p className="app-eyebrow">All demos</p>
              <h2 className="mt-4 font-[var(--font-newsreader)] text-3xl tracking-[-0.04em] text-foreground md:text-4xl">
                Public-domain books used to illustrate real manuscript problems.
              </h2>
            </div>

            <div className="mt-10 grid gap-5 lg:grid-cols-3">
              {demoPages.map((demo, index) => {
                const article = getBlogArticleBySlug(demo.articleSlug)
                return (
                  <Reveal key={demo.slug} delay={index * 70}>
                    <article className="h-full rounded-[1.6rem] border border-[rgba(var(--border),0.76)] bg-white/58 p-6 dark:bg-white/[0.04]">
                      <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
                        {demo.sourceWork} by {demo.sourceAuthor}
                      </p>
                      <h3 className="mt-4 text-2xl font-semibold tracking-[-0.03em] text-foreground">
                        <Link href={`/demo/${demo.slug}`} className="hover:text-[rgb(var(--accent))]">
                          {demo.title}
                        </Link>
                      </h3>
                      <p className="app-copy mt-3 text-sm">{demo.featuredInsight}</p>
                      {article ? (
                        <p className="mt-4 text-sm font-medium text-muted-foreground">
                          Related guide: {article.title}
                        </p>
                      ) : null}
                    </article>
                  </Reveal>
                )
              })}
            </div>
          </div>
        </Reveal>
      </section>
    </main>
  )
}
