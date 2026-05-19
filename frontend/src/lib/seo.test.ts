import { describe, expect, it } from "vitest"

import {
  buildBookJsonLd,
  buildFaqPageJsonLd,
  buildForumThreadJsonLd,
  buildProfilePageJsonLd,
} from "./seo"

describe("seo helpers", () => {
  it("builds faq structured data with question-answer pairs", () => {
    expect(
      buildFaqPageJsonLd([
        {
          question: "How do I track character arcs?",
          answer: "Track turning points, not summaries.",
        },
      ]),
    ).toMatchObject({
      "@type": "FAQPage",
      mainEntity: [
        expect.objectContaining({
          "@type": "Question",
          name: "How do I track character arcs?",
          acceptedAnswer: expect.objectContaining({
            "@type": "Answer",
            text: "Track turning points, not summaries.",
          }),
        }),
      ],
    })
  })

  it("builds profile pages for public writer surfaces", () => {
    expect(
      buildProfilePageJsonLd({
        username: "maya",
        description: "Public writer profile",
        path: "/public/writers/maya",
      }),
    ).toMatchObject({
      "@type": "ProfilePage",
      url: "https://getlorevia.com/public/writers/maya",
      mainEntity: expect.objectContaining({
        "@type": "Person",
        alternateName: "@maya",
      }),
    })
  })

  it("builds book schema for public samples", () => {
    expect(
      buildBookJsonLd({
        title: "Ashen Reign",
        author: "Maya Vale",
        description: "Public sample",
        path: "/public/ashen-reign",
        genre: "Fantasy",
        chapterCount: 12,
      }),
    ).toMatchObject({
      "@type": "Book",
      name: "Ashen Reign",
      url: "https://getlorevia.com/public/ashen-reign",
      author: expect.objectContaining({
        "@type": "Person",
        name: "Maya Vale",
      }),
      numberOfPages: 12,
    })
  })

  it("builds discussion schema for public forum threads", () => {
    expect(
      buildForumThreadJsonLd({
        title: "Need pacing feedback for act two",
        body: "Looking for readers who can flag drag in the middle act.",
        path: "/public/forum/thread-1",
        createdAt: "2026-05-19T00:00:00.000Z",
        authorName: "maya",
      }),
    ).toMatchObject({
      "@type": "DiscussionForumPosting",
      url: "https://getlorevia.com/public/forum/thread-1",
      author: expect.objectContaining({
        name: "maya",
      }),
    })
  })
})
