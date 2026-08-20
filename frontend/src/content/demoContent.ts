export type ContentSection = {
  heading: string
  body: string[]
  bullets?: string[]
  highlight?: string
}

export type DemoPage = {
  slug: string
  title: string
  description: string
  publishedAt: string
  publishedLabel: string
  readTime: string
  sourceWork: string
  sourceAuthor: string
  articleSlug: string
  answerSlugs: string[]
  intro: string
  featuredInsight: string
  sections: ContentSection[]
}

export const demoPages: DemoPage[] = [
  {
    slug: "gregor-samsa-character-tracker",
    title: "Demo: Tracking Gregor Samsa Across The Metamorphosis",
    description:
      "A public-domain workflow example showing how LoreVia-style character tracking can follow transformations, family tension, and identity drift scene by scene.",
    publishedAt: "2026-05-14",
    publishedLabel: "May 14, 2026",
    readTime: "5 min read",
    sourceWork: "The Metamorphosis",
    sourceAuthor: "Franz Kafka",
    articleSlug: "how-to-track-characters-in-a-novel",
    answerSlugs: [
      "how-do-i-remember-small-details-in-a-long-manuscript",
      "how-do-i-track-character-arcs",
    ],
    intro:
      "This demo is useful because Gregor Samsa changes so dramatically that a flat character sheet would fail almost immediately. A real tracker has to preserve both the visible facts of his transformation and the emotional facts surrounding it: who still treats him as family, who shifts into duty, who shifts into disgust, and how Gregor's own sense of self collapses under those reactions.",
    featuredInsight:
      "Gregor's transformation is not only physical. A tracking system also surfaces how his family's language, fear, and obligation change around him.",
    sections: [
      {
        heading: "What the character record captures",
        body: [
          "A strong character tracker would capture Gregor's physical change, his role as provider, his shrinking agency, and the exact points where family members stop relating to him as a son and begin responding to him as a problem.",
          "That matters because the novella's tragedy is not only the event of transformation. It is the steady revision of Gregor's social identity. A useful record would show when care becomes management, when embarrassment becomes hostility, and when Gregor's own internal language can no longer protect his earlier self-image.",
        ],
        bullets: [
          "First transformation event",
          "Changes in mobility and dependence",
          "Shifts in how Grete, the father, and the mother respond to him",
          "Moments where Gregor's internal identity no longer matches how others frame him",
        ],
      },
      {
        heading: "Why this example matters for novelists",
        body: [
          "Public-domain examples are useful because they show that character tracking is not just for fantasy encyclopedias or giant casts. Even a tight novella can benefit when changes in status, identity, and relationships are tracked with care.",
          "This is the same reason authors should track injuries, grief responses, or escalating resentment in their own drafts. Emotional continuity often lives in repeated small changes.",
        ],
      },
      {
        heading: "What LoreVia-style analysis would surface",
        body: [
          "A manuscript intelligence workflow could flag the clustered scenes where Gregor loses agency, track the vocabulary different family members use for him, and connect those moments to the broader arc of obligation inside the household. That turns a famous literary effect into something inspectable instead of purely intuitive.",
          "For working authors, the value is practical: once that pattern is visible in a demo, it becomes easier to imagine doing the same kind of tracking inside an original manuscript with less obvious but equally important emotional drift.",
        ],
      },
    ],
  },
  {
    slug: "dracula-story-timeline-tracker",
    title: "Demo: Using Dracula to Show a Story Timeline Tracker",
    description:
      "A public-domain example showing how LoreVia-style timeline tracking can organize travel, diary entries, letters, and overlapping events in a complex manuscript.",
    publishedAt: "2026-05-14",
    publishedLabel: "May 14, 2026",
    readTime: "5 min read",
    sourceWork: "Dracula",
    sourceAuthor: "Bram Stoker",
    articleSlug: "how-to-avoid-continuity-errors-when-writing-a-novel",
    answerSlugs: [
      "how-do-authors-manage-timelines",
      "what-is-a-continuity-checker-for-fiction",
    ],
    intro:
      "Dracula works well as a public demo because the book already behaves like a continuity stress test. Its journals, letters, newspaper clippings, and travel sequences force the reader to align separate records into one coherent chronology. That makes it a near-perfect example of why timeline tracking is a real editorial tool rather than administrative decoration.",
    featuredInsight:
      "Dracula is a perfect timeline demo because its letters, journals, and travel windows force the reader to reconcile overlapping accounts across multiple narrators.",
    sections: [
      {
        heading: "What the timeline system surfaces",
        body: [
          "A timeline tracker can line up journal entries, train travel, off-page movement, and the moments when one narrator learns what another already knows. That quickly exposes impossible travel windows or delayed knowledge transfer.",
          "Because Dracula uses distributed records, the timeline is doing double duty. It has to manage elapsed time and narrative perspective at once. A good system would therefore show both when something happened and who could responsibly know it at that moment.",
        ],
        bullets: [
          "Date and time anchors from diaries and letters",
          "Travel durations between major locations",
          "Knowledge handoffs between narrators",
          "Overlap between parallel events",
        ],
      },
      {
        heading: "Why this example matters for fiction authors",
        body: [
          "Many modern novels use dual timelines, multiple POVs, or epistolary fragments. Dracula shows why timeline clarity matters whenever a story depends on separate records converging into one readable sequence.",
          "If your own draft includes flashbacks, travel, or staggered reveals, a timeline tracker is not optional admin. It is structural support.",
        ],
      },
      {
        heading: "How the demo translates to modern revision work",
        body: [
          "In a LoreVia-style demo, the point is not to summarize Dracula for the sake of summary. It is to show the editorial view an author would want: dated events arranged in order, travel assumptions made explicit, and points of contradiction or ambiguity made easy to inspect.",
          "Once authors see that view on a familiar text, the workflow becomes concrete. The same timeline logic can support thrillers, romances with staggered timelines, fantasy quests, or any manuscript where chronology quietly controls plausibility.",
        ],
      },
    ],
  },
  {
    slug: "pride-and-prejudice-relationship-map",
    title: "Demo: Mapping Relationships in Pride and Prejudice",
    description:
      "A public-domain example showing how LoreVia-style relationship tracking can map conflict, prejudice, reversals, and social pressure through a novel.",
    publishedAt: "2026-05-14",
    publishedLabel: "May 14, 2026",
    readTime: "5 min read",
    sourceWork: "Pride and Prejudice",
    sourceAuthor: "Jane Austen",
    articleSlug: "what-is-a-story-bible-and-do-you-need-one",
    answerSlugs: [
      "how-do-i-track-character-relationships-in-a-novel",
      "how-do-i-create-a-story-bible-automatically",
    ],
    intro:
      "Pride and Prejudice is an excellent relationship demo because nearly every major turn depends on revised perception. Affection, embarrassment, pride, social ambition, and family pressure all change the meaning of earlier scenes. A relationship map lets those shifts stay visible instead of dissolving into a general memory that the book is \"about\" Elizabeth and Darcy.",
    featuredInsight:
      "A relationship map shows not just who is connected, but how misread motives, social status, and shifting respect change the emotional geometry of the novel.",
    sections: [
      {
        heading: "What the relationship map captures",
        body: [
          "A relationship graph for Pride and Prejudice would track courtship pressure, family expectations, social friction, and the major reversals that change how Elizabeth, Darcy, Jane, Bingley, and Lady Catherine interact.",
          "The key value is not simply knowing who is linked. It is preserving the shape of those links over time. The map should show when misunderstanding is dominant, when respect begins to replace irritation, and when external social pressure alters what a character can safely do.",
        ],
        bullets: [
          "Current relationship status",
          "Last scene that changed the bond",
          "Misunderstandings still driving behavior",
          "External pressures shaping the relationship",
        ],
      },
      {
        heading: "Why this example matters for authors",
        body: [
          "Relationship-rich novels depend on momentum between people, not just events. When that momentum is not tracked, revisions can accidentally flatten or rush the emotional logic that makes the book satisfying.",
          "This is why a story bible should contain relationship movement, not only static world facts.",
        ],
      },
      {
        heading: "What an author can borrow from this demo",
        body: [
          "The practical lesson is that relationship tracking is not limited to romance classics. Any manuscript with family tension, rivalry, shifting alliances, or social pressure can benefit from the same method. What matters is that the bond itself receives an editable record.",
          "That kind of record becomes especially valuable during revision, when a cut scene or softened exchange can accidentally change how fast a relationship develops without the author noticing until readers point it out.",
        ],
      },
    ],
  },
]
