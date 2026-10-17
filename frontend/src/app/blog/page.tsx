import type { Metadata } from "next"
import Image from "next/image"
import Link from "next/link"
import type { Route } from "next"

import { StoryCard } from "@/components/content/StoryCard"
import { PublicContentShell } from "@/components/marketing/PublicContentShell"
import { JsonLdScript } from "@/components/seo/JsonLdScript"
import { blogArticles } from "@/lib/content"
import { BLOG_RSS_PATH, SITE_NAME, SITE_URL, buildCollectionPageJsonLd, toAbsoluteUrl } from "@/lib/seo"

const publicationArticles = [...blogArticles].sort((left, right) => (
  right.publishedAt.localeCompare(left.publishedAt) || left.order - right.order
))
const featuredArticle = publicationArticles[0]
const BLOG_DESCRIPTION = "Calm, practical craft and revision guides for fiction authors, published by LoreVia Editorial."

export const metadata: Metadata = {
  title: "Blog",
  description: BLOG_DESCRIPTION,
  keywords: ["fiction craft", "novel revision", "character tracking", "story continuity", "story bible"],
  alternates: { canonical: "/blog", types: { "application/rss+xml": BLOG_RSS_PATH } },
  openGraph: {
    title: `LoreVia Editorial | ${SITE_NAME}`,
    description: BLOG_DESCRIPTION,
    url: `${SITE_URL}/blog`,
    images: [{
      url: featuredArticle.hero.src,
      width: featuredArticle.hero.width,
      height: featuredArticle.hero.height,
      alt: featuredArticle.hero.alt,
    }],
  },
  twitter: {
    card: "summary_large_image",
    title: `LoreVia Editorial | ${SITE_NAME}`,
    description: BLOG_DESCRIPTION,
    images: [featuredArticle.hero.src],
  },
}

export default function BlogPage() {
  const latest = publicationArticles.slice(1, 5)
  const archive = publicationArticles.slice(5)
  const topics = Array.from(new Set(archive.map((article) => article.category)))
  const collection = buildCollectionPageJsonLd({
    name: "LoreVia Editorial",
    description: BLOG_DESCRIPTION,
    path: "/blog",
    about: topics,
  })
  const itemList = {
    "@context": "https://schema.org",
    "@type": "ItemList",
    name: "LoreVia Editorial articles",
    numberOfItems: blogArticles.length,
    itemListElement: blogArticles.map((article, index) => ({
      "@type": "ListItem",
      position: index + 1,
      url: toAbsoluteUrl(`/blog/${article.slug}`),
      name: article.title,
    })),
  }

  return (
    <PublicContentShell activeSection="blog">
      <JsonLdScript id="blog-collection-jsonld" data={collection} />
      <JsonLdScript id="blog-item-list-jsonld" data={itemList} />

      <div className="editorial-hub">
        <header className="editorial-masthead">
          <p>LoreVia Editorial</p>
          <h1>Notes on the difficult work of keeping a story whole.</h1>
          <div>
            <span>Craft</span><span>Continuity</span><span>Revision</span><span>Writing practice</span>
          </div>
        </header>

        <section className="editorial-feature" aria-labelledby="featured-story-title">
          <Link href={`/blog/${featuredArticle.slug}` as Route} className="editorial-feature__image">
            <Image
              src={featuredArticle.hero.src}
              alt={featuredArticle.hero.alt}
              width={featuredArticle.hero.width}
              height={featuredArticle.hero.height}
              sizes="(max-width: 1024px) 100vw, 58vw"
              priority
            />
          </Link>
          <div>
            <p className="editorial-kicker">Featured · {featuredArticle.category}</p>
            <h2 id="featured-story-title"><Link href={`/blog/${featuredArticle.slug}` as Route}>{featuredArticle.title}</Link></h2>
            <p>{featuredArticle.description}</p>
            <p className="editorial-byline-small">LoreVia Editorial · {featuredArticle.publishedLabel} · {featuredArticle.readTime}</p>
            <Link href={`/blog/${featuredArticle.slug}` as Route} className="editorial-text-link">Read the story <span aria-hidden="true">→</span></Link>
          </div>
        </section>

        <section className="editorial-latest" aria-labelledby="latest-title">
          <div className="editorial-section-heading">
            <p className="editorial-kicker">From the desk</p>
            <h2 id="latest-title">Latest articles</h2>
          </div>
          <div className="editorial-latest-grid">
            {latest.map((article) => <StoryCard key={article.slug} story={article} />)}
          </div>
        </section>

        <section className="editorial-topics" aria-labelledby="topics-title">
          <div className="editorial-section-heading">
            <p className="editorial-kicker">Article archive</p>
            <h2 id="topics-title">Browse every guide</h2>
          </div>
          {topics.map((topic) => (
            <section key={topic} className="editorial-topic-row" aria-labelledby={`topic-${topic.replace(/\s+/g, "-").toLowerCase()}`}>
              <h3 id={`topic-${topic.replace(/\s+/g, "-").toLowerCase()}`}>{topic}</h3>
              <div className="editorial-archive-list">
                {archive.filter((article) => article.category === topic).map((article) => (
                  <Link key={article.slug} href={`/blog/${article.slug}` as Route}>
                    <span>{article.title}</span>
                    <span>{article.publishedLabel} · {article.readTime}</span>
                  </Link>
                ))}
              </div>
            </section>
          ))}
        </section>

        <div className="editorial-rss-link">
          <Link href={BLOG_RSS_PATH as Route}>Follow new essays via RSS</Link>
        </div>
      </div>
    </PublicContentShell>
  )
}
