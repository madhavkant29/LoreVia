import Image from "next/image"
import Link from "next/link"
import type { Route } from "next"

import type { ContentSummary } from "@/content/types"

export function StoryCard({
  story,
  compact = false,
  trackingEvent,
}: {
  story: ContentSummary
  compact?: boolean
  trackingEvent?: string
}) {
  const href = `/${story.kind === "blog" ? "blog" : "answers"}/${story.slug}` as Route
  const trackingAttributes = trackingEvent
    ? {
        "data-editorial-event": trackingEvent,
        "data-editorial-destination": href,
      }
    : {}
  return (
    <article className={compact ? "editorial-story-card editorial-story-card--compact" : "editorial-story-card"}>
      <Link href={href} className="editorial-story-card__image" aria-label={story.title} {...trackingAttributes}>
        <Image
          src={story.hero.src}
          alt=""
          width={story.hero.width}
          height={story.hero.height}
          sizes={compact ? "(max-width: 768px) 100vw, 280px" : "(max-width: 768px) 100vw, 420px"}
        />
      </Link>
      <div>
        <p className="editorial-kicker">{story.category}</p>
        <h3><Link href={href} {...trackingAttributes}>{story.title}</Link></h3>
        {!compact ? <p className="editorial-story-card__deck">{story.description}</p> : null}
        <p className="editorial-byline-small">LoreVia Editorial · {story.publishedLabel} · {story.readTime}</p>
      </div>
    </article>
  )
}
