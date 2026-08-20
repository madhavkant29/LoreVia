// @vitest-environment jsdom

import { act } from "react"
import { createRoot } from "react-dom/client"
import { afterEach, describe, expect, it, vi } from "vitest"

import type { BlogSummary } from "@/content/types"

import { StoryCard } from "./StoryCard"

vi.mock("next/image", () => ({
  default: (props: React.ImgHTMLAttributes<HTMLImageElement>) => <img alt={props.alt ?? ""} {...props} />,
}))
vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: React.AnchorHTMLAttributes<HTMLAnchorElement>) => (
    <a href={String(href)} {...props}>{children}</a>
  ),
}))

const story: BlogSummary = {
  kind: "blog",
  slug: "scene-list",
  title: "Build a scene list",
  description: "A practical scene-list guide.",
  category: "Revision craft",
  keywords: ["scene list"],
  publishedAt: "2026-08-09",
  updatedAt: "2026-08-11",
  publishedLabel: "August 9, 2026",
  updatedLabel: "August 11, 2026",
  authorId: "lorevia-editorial",
  hero: { src: "/blog/heroes/scene-list.webp", alt: "Editorial scene cards", width: 1600, height: 900 },
  relatedSlugs: [],
  sources: [],
  order: 1,
  wordCount: 1800,
  readTimeMinutes: 8,
  readTime: "8 min read",
  supportingAnswerSlugs: [],
}

afterEach(() => {
  document.body.innerHTML = ""
})

describe("StoryCard", () => {
  it("tags both related-story links with the editorial destination", async () => {
    const container = document.createElement("div")
    document.body.appendChild(container)
    const root = createRoot(container)

    await act(async () => {
      root.render(<StoryCard story={story} trackingEvent="editorial_related_opened" />)
    })

    const links = [...container.querySelectorAll("a")]
    expect(links).toHaveLength(2)
    for (const link of links) {
      expect(link.dataset.editorialEvent).toBe("editorial_related_opened")
      expect(link.dataset.editorialDestination).toBe("/blog/scene-list")
    }

    act(() => root.unmount())
  })
})
