import Image from "next/image"
import Link from "next/link"
import type { Route } from "next"

import { SOURCES_HEADING_ID } from "@/content/slug"
import { LOREVIA_EDITORIAL, type ContentDocument, type ContentSummary } from "@/content/types"

import { ReaderTools } from "./ReaderTools"
import { StoryCard } from "./StoryCard"

export function ArticleShell({
  document,
  related,
  parent,
}: {
  document: ContentDocument
  related: ContentSummary[]
  parent?: ContentSummary | null
}) {
  const { summary, content, tableOfContents } = document
  const isUpdated = summary.updatedAt !== summary.publishedAt

  return (
    <article className={`editorial-article editorial-article--${summary.kind}`}>
      <ReaderTools kind={summary.kind} slug={summary.slug} title={summary.title} tableOfContents={tableOfContents} />

      <header className="editorial-article-header">
        <p className="editorial-kicker">{summary.category}</p>
        <h1>{summary.title}</h1>
        <p className="editorial-deck">{summary.description}</p>

        <div className="editorial-author-row">
          <Image src={LOREVIA_EDITORIAL.avatar} alt="" width={44} height={44} className="editorial-author-row__avatar" />
          <div>
            <p className="editorial-author-row__name">{LOREVIA_EDITORIAL.name}</p>
            <p className="editorial-author-row__meta">
              Published {summary.publishedLabel}
              {isUpdated ? ` · Updated ${summary.updatedLabel}` : ""}
              {` · ${summary.readTime}`}
            </p>
          </div>
        </div>

        <div className="editorial-hero">
          <Image
            src={summary.hero.src}
            alt={summary.hero.alt}
            width={summary.hero.width}
            height={summary.hero.height}
            sizes="(max-width: 1024px) 100vw, 1120px"
            priority
          />
        </div>
      </header>

      <div className="editorial-article-layout">
        <aside className="editorial-desktop-toc">
          <p>In this article</p>
          <nav aria-label="Article sections">
            {tableOfContents.map((item) => <a key={item.id} href={`#${item.id}`}>{item.label}</a>)}
          </nav>
        </aside>

        <main className="editorial-prose" data-editorial-body>
          {summary.kind === "answer" ? (
            <section className="editorial-short-answer" aria-labelledby="short-answer-title">
              <p id="short-answer-title">Short answer</p>
              <div>{summary.shortAnswer}</div>
            </section>
          ) : null}

          {content}

          {summary.sources.length ? (
            <section className="editorial-sources" aria-labelledby={SOURCES_HEADING_ID}>
              <h2 id={SOURCES_HEADING_ID}>Sources and further reading</h2>
              <ul>
                {summary.sources.map((source) => (
                  <li key={source.url}>
                    <a href={source.url} target="_blank" rel="noreferrer">{source.title}</a>
                    <span>{source.publisher} · Reviewed {source.reviewedAt}</span>
                  </li>
                ))}
              </ul>
            </section>
          ) : null}

          {summary.kind === "answer" && parent ? (
            <p className="editorial-parent-link">
              Broader guide: <Link href={`/blog/${parent.slug}` as Route}>{parent.title}</Link>
            </p>
          ) : null}
        </main>
      </div>

      <section className="editorial-related" aria-labelledby="related-reading-title">
        <div className="editorial-section-heading">
          <p className="editorial-kicker">Continue reading</p>
          <h2 id="related-reading-title">Related stories</h2>
        </div>
        <div className="editorial-related-grid">
          {related.map((story) => (
            <StoryCard
              key={`${story.kind}-${story.slug}`}
              story={story}
              trackingEvent="editorial_related_opened"
            />
          ))}
        </div>
      </section>

      <aside className="editorial-cta">
        <div>
          <p className="editorial-kicker">Bring the method to your manuscript</p>
          <h2>Keep story evidence close while you revise.</h2>
          <p>LoreVia helps fiction authors trace characters, continuity, relationships, and chapter-grounded answers across a draft.</p>
        </div>
        <Link
          href="/register"
          className="editorial-cta__link"
          data-editorial-event="editorial_cta_opened"
          data-editorial-destination="/register"
        >
          Start free
        </Link>
      </aside>
    </article>
  )
}
