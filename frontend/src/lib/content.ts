export type ContentSection = {
  heading: string
  body: string[]
  bullets?: string[]
  highlight?: string
}

export type BlogArticle = {
  slug: string
  title: string
  description: string
  category: string
  publishedAt: string
  publishedLabel: string
  readTime: string
  keywords: string[]
  intro: string
  highlights: string[]
  sections: ContentSection[]
  supportingAnswerSlugs: string[]
  demoSlug: string
}

export type AnswerPage = {
  slug: string
  question: string
  description: string
  publishedAt: string
  publishedLabel: string
  articleSlug: string
  demoSlug?: string
  shortAnswer: string
  quickSteps: string[]
  whyItMatters: string
}

export type DemoPage = {
  slug: string
  title: string
  description: string
  publishedAt: string
  publishedLabel: string
  sourceWork: string
  sourceAuthor: string
  articleSlug: string
  answerSlugs: string[]
  featuredInsight: string
  sections: ContentSection[]
}

export const CONTENT_HUB_ROUTES = ["/blog", "/answers", "/demo"] as const

export const blogArticles: BlogArticle[] = [
  {
    slug: "how-to-track-characters-in-a-novel",
    title: "How to Keep Track of Characters in a Novel",
    description:
      "A practical system for tracking names, relationships, promises, physical details, and re-appearances across a growing manuscript.",
    category: "Character systems",
    publishedAt: "2026-05-14",
    publishedLabel: "May 14, 2026",
    readTime: "9 min read",
    keywords: [
      "character tracking for writers",
      "how to keep track of characters in a novel",
      "character bible for authors",
      "novel writing software for character tracking",
    ],
    intro:
      "Most character mistakes are not creative failures. They are memory failures. When a manuscript grows past a few chapters, authors start forgetting eye colors, side promises, old nicknames, relationship shifts, and the last scene where someone appeared. The fix is not more stress. The fix is a system.",
    highlights: [
      "Track every character by role, first appearance, and last confirmed fact.",
      "Keep a live relationship log so emotional changes are visible, not guessed.",
      "Store unresolved promises beside the character record so arcs do not quietly vanish.",
    ],
    sections: [
      {
        heading: "Start with a canon record, not a vague cast list",
        body: [
          "A cast list is only useful when it stores facts you can trust. For each important character, capture the spelling you have committed to, key aliases, physical markers, loyalties, open secrets, and the first chapter where the reader meets them.",
          "That gives you a stable reference point when revisions start moving scenes around. It also prevents a common long-draft problem where a character exists in your head more clearly than they exist on the page.",
        ],
        bullets: [
          "Name, alias, and role in the story",
          "First on-page appearance and last confirmed appearance",
          "Stable physical and emotional traits",
          "Open promises, wounds, and unresolved tensions",
        ],
      },
      {
        heading: "Track relationships as their own system",
        body: [
          "Authors often store relationship details inside individual character notes, but that hides the movement between people. Relationship tracking works better when the bond itself has a record: current status, last meaningful shift, scenes that changed it, and any contradiction still unresolved.",
          "If two siblings go from estranged to protective, that shift should be visible at a glance. The same is true for rivalries, mentor bonds, betrayals, and romantic threads.",
        ],
        highlight:
          "Relationship tracking is where continuity and character development meet. It is also where many reader complaints begin when the record is fuzzy.",
      },
      {
        heading: "Use chapter references for every important fact",
        body: [
          "The fastest way to stop arguing with your own memory is to cite the chapter where a fact appears. If a note says a scar came from a duel, add the chapter reference. If a side character knows a secret, add the scene where they learned it.",
          "This is the difference between a pleasant reference document and a dependable editorial system. LoreVia is strongest when every answer points back to the manuscript instead of asking you to trust an unsupported summary.",
        ],
      },
      {
        heading: "Review the character system during revision, not just after drafting",
        body: [
          "A character tracker is not a one-time setup. It becomes useful when you update it during major revisions, especially after deleted scenes, chapter merges, or POV shifts. Those are the moments when small facts go stale.",
          "A short continuity pass after each revision sprint keeps the tracker honest and stops errors from multiplying into later chapters.",
        ],
      },
    ],
    supportingAnswerSlugs: [
      "how-do-i-track-character-relationships-in-a-novel",
      "how-do-i-remember-small-details-in-a-long-manuscript",
      "how-do-i-track-character-arcs",
    ],
    demoSlug: "gregor-samsa-character-tracker",
  },
  {
    slug: "how-to-avoid-continuity-errors-when-writing-a-novel",
    title: "How to Avoid Continuity Errors When Writing a Novel",
    description:
      "A revision workflow for catching contradictions, dropped plot threads, timeline issues, and accidental fact changes before readers do.",
    category: "Continuity",
    publishedAt: "2026-05-14",
    publishedLabel: "May 14, 2026",
    readTime: "10 min read",
    keywords: [
      "novel continuity checker",
      "how to avoid continuity errors when writing a novel",
      "story timeline tracker",
      "plot hole checker for fiction writers",
    ],
    intro:
      "Continuity errors rarely come from one dramatic mistake. They come from dozens of tiny facts drifting apart over time: travel times, weather, injuries, promises, props, sibling ages, old lies that stop mattering, or world rules that bend without explanation.",
    highlights: [
      "Separate fact continuity from emotional continuity so you catch both kinds of breakage.",
      "Run continuity passes after structural edits, not just at the very end.",
      "Track promises, travel time, injuries, and knowledge transfer as explicit review categories.",
    ],
    sections: [
      {
        heading: "Continuity is more than plot holes",
        body: [
          "Plot holes are only one category. Continuity also includes timing, world rules, injuries, relationship memory, scene geography, and who knows what at a given point in the draft.",
          "When authors reduce continuity to plot alone, they miss the smaller contradictions that make a manuscript feel unstable even when the outline still works.",
        ],
      },
      {
        heading: "Build a repeatable continuity checklist",
        body: [
          "The easiest way to improve continuity is to review the same categories every time. That keeps you from checking only the errors you already expect to find.",
        ],
        bullets: [
          "Character facts: names, appearance, skills, fears, backstory details",
          "Timeline facts: dates, elapsed days, travel duration, season, time of day",
          "Relationship facts: loyalties, resentments, secrets, promises, betrayals",
          "World facts: magic costs, political rules, geography, technology limits",
          "Thread facts: setups, callbacks, unresolved questions, and payoffs",
        ],
      },
      {
        heading: "Audit what changed after every major revision",
        body: [
          "Big rewrites create continuity debt. If you delete a chapter, merge two scenes, or move a reveal, you also change downstream facts. Treat the edit itself as the start of a continuity review, not the end of one.",
          "A manuscript intelligence tool helps here because it can surface which characters, threads, and scenes are likely downstream of the change you just made.",
        ],
        highlight:
          "The real cost of a large revision is not the rewrite. It is the hidden continuity drift that follows if no one audits the consequences.",
      },
      {
        heading: "Keep your fixes visible",
        body: [
          "When you find a continuity problem, note both the error and the chosen fix. That prevents a second pass from reopening the same issue or solving it a different way in a later chapter.",
          "For authors working across multiple drafts or collaborators, visible fix notes also make editorial decisions easier to defend.",
        ],
      },
    ],
    supportingAnswerSlugs: [
      "how-do-i-avoid-plot-holes-in-my-story",
      "how-do-authors-manage-timelines",
      "what-is-a-continuity-checker-for-fiction",
    ],
    demoSlug: "dracula-story-timeline-tracker",
  },
  {
    slug: "what-is-a-story-bible-and-do-you-need-one",
    title: "What Is a Story Bible and Do You Actually Need One?",
    description:
      "A clear explanation of what belongs in a story bible, when it helps, and how authors can keep it useful instead of turning it into abandoned admin work.",
    category: "Story bibles",
    publishedAt: "2026-05-14",
    publishedLabel: "May 14, 2026",
    readTime: "8 min read",
    keywords: [
      "what is a story bible",
      "story bible for authors",
      "worldbuilding software for authors",
      "create a story bible automatically",
    ],
    intro:
      "A story bible is a living record of what your manuscript has already made true. It is not meant to impress anyone. It exists so your draft stops depending on fragile memory.",
    highlights: [
      "A story bible should serve the manuscript, not become a second writing project.",
      "The best entries are grounded in scenes, not abstract lore for its own sake.",
      "Automation matters because abandoned bibles usually fail from upkeep, not intent.",
    ],
    sections: [
      {
        heading: "What belongs in a story bible",
        body: [
          "At minimum, a useful story bible tracks characters, locations, timeline anchors, world rules, recurring objects, and unresolved threads. If a fact can create a contradiction later, it belongs in the system.",
          "For fiction authors, the most valuable entries are often the least glamorous ones: how a spell actually works, who knows an alias, how long it takes to cross a city, or what chapter established a family's history.",
        ],
      },
      {
        heading: "When you truly need one",
        body: [
          "You need a story bible as soon as the manuscript becomes harder to hold in working memory. That point arrives earlier than most authors expect, especially in mystery, fantasy, romance series, dual timelines, or any project with a large cast.",
          "Short standalone fiction may only need a light version. A long novel or series almost always benefits from something more structured.",
        ],
      },
      {
        heading: "Why manual bibles get abandoned",
        body: [
          "Manual systems fail when updating them feels separate from writing. If the only way to maintain the bible is to stop drafting and summarize everything by hand, it turns into guilt instead of support.",
          "That is why manuscript analysis and grounded extraction are so useful. The less admin authors must do just to keep their own facts visible, the more likely the system is to survive revision.",
        ],
        highlight:
          "A story bible should reduce cognitive load. If it keeps asking for extra labor, it is not doing its job.",
      },
      {
        heading: "Aim for a living reference, not a perfect encyclopedia",
        body: [
          "The goal is not to document everything. The goal is to capture what the book has already committed to and what future chapters depend on.",
          "That means a good story bible is selective, searchable, and connected to the text that proves each entry.",
        ],
      },
    ],
    supportingAnswerSlugs: [
      "what-is-manuscript-analysis",
      "how-do-i-create-a-story-bible-automatically",
      "how-do-i-organize-chapters-and-scenes",
    ],
    demoSlug: "pride-and-prejudice-relationship-map",
  },
  {
    slug: "best-writing-software-for-fiction-authors",
    title: "Best Writing Software for Fiction Authors",
    description:
      "A buyer-focused comparison of writing software categories, with special attention to continuity, revision workflow, character tracking, and story intelligence for novelists.",
    category: "Comparisons",
    publishedAt: "2026-05-14",
    publishedLabel: "May 14, 2026",
    readTime: "11 min read",
    keywords: [
      "best writing software for fiction authors",
      "writing software for novelists",
      "manuscript analysis tool",
      "author software comparison",
    ],
    intro:
      "The best writing software for fiction authors depends on the problem you are trying to solve. Some tools are excellent for drafting. Some are strong at worldbuilding. Far fewer are built to understand a manuscript well enough to help with continuity, character tracking, and chapter-grounded recall.",
    highlights: [
      "Choose software by workflow bottleneck, not by the longest feature list.",
      "Drafting, planning, and manuscript intelligence are different jobs.",
      "Authors revising long novels need stronger continuity support than most tools offer.",
    ],
    sections: [
      {
        heading: "Most fiction software falls into four buckets",
        body: [
          "The useful comparison is not app against app at first. It is category against category. Authors generally choose between clean drafting tools, planning databases, collaboration tools, and manuscript intelligence platforms.",
          "A drafting app helps you produce pages. A planning app helps you store references. A manuscript intelligence tool helps you understand what the draft is already doing and where it has drifted.",
        ],
      },
      {
        heading: "What serious novelists should compare",
        body: [
          "Once a manuscript gets long, compare tools against the editorial problems you actually face, not the marketing headline on the homepage.",
        ],
        bullets: [
          "Can it track characters and aliases without heavy manual upkeep?",
          "Can it show relationship and timeline changes over time?",
          "Can it help catch continuity mistakes before beta readers do?",
          "Can it answer questions with chapter-level evidence?",
          "Can it support private draft work without forcing public posting or gimmicky generation?",
        ],
      },
      {
        heading: "Why continuity and recall are now buying criteria",
        body: [
          "For many authors, the pain point is no longer getting words onto the page. It is keeping a sprawling manuscript coherent through multiple revisions. That changes the evaluation completely.",
          "A tool that is wonderful for first-draft momentum may still be weak once the project needs story memory, beta-reader prep, and contradiction checks.",
        ],
      },
      {
        heading: "Where LoreVia fits",
        body: [
          "LoreVia is strongest for authors who already have material and need help turning that draft into a searchable working system. It is built around manuscript analysis, continuity tracking, chapter-grounded questions, character memory, and revision awareness.",
          "That makes it a better fit for fiction authors dealing with complexity than for someone simply looking for a blank page and a word counter.",
        ],
        highlight:
          "If your core problem is losing track of the story you already wrote, evaluate tools by memory and continuity, not just drafting comfort.",
      },
    ],
    supportingAnswerSlugs: [
      "how-do-i-prepare-a-manuscript-for-beta-readers",
      "how-do-i-organize-chapters-and-scenes",
    ],
    demoSlug: "dracula-story-timeline-tracker",
  },
  {
    slug: "scrivener-vs-campfire-vs-lorevia-for-novel-planning",
    title: "Scrivener vs Campfire vs LoreVia: Which Is Better for Novel Planning?",
    description:
      "A comparison for authors deciding between drafting-first software, planning-first software, and a manuscript intelligence workflow built around continuity and story memory.",
    category: "Comparisons",
    publishedAt: "2026-05-14",
    publishedLabel: "May 14, 2026",
    readTime: "12 min read",
    keywords: [
      "scrivener vs lorevia",
      "campfire write alternative",
      "scrivener alternative for authors",
      "campfire write comparison",
    ],
    intro:
      "Scrivener, Campfire, and LoreVia solve different parts of the fiction workflow. The wrong comparison treats them as interchangeable. The better comparison is to ask where each tool is strongest: drafting, planning, or understanding the manuscript you already have.",
    highlights: [
      "Scrivener is strongest as a drafting and project-organization tool.",
      "Campfire is strongest as a planning and worldbuilding workspace.",
      "LoreVia is strongest when authors need continuity tracking and manuscript-grounded recall.",
    ],
    sections: [
      {
        heading: "Scrivener excels at drafting control",
        body: [
          "Scrivener gives authors strong control over long-form drafting, project structure, and manuscript assembly. If your main goal is a flexible writing environment with folders, notes, and compile options, it remains a strong choice.",
          "Its limitation is that much of the intelligence still lives in you. Scrivener stores material well, but it does not deeply analyze the story for contradictions or answer manuscript questions with citations.",
        ],
      },
      {
        heading: "Campfire excels at planning and worldbuilding",
        body: [
          "Campfire is strong when you want dedicated spaces for lore, maps, cultures, species, relationship graphs, and other planning objects before or alongside drafting.",
          "For authors with complex worldbuilding needs, that can be a better planning surface than a simple notes system. The tradeoff is that planning systems can drift away from the actual manuscript if they are not tightly grounded in it.",
        ],
      },
      {
        heading: "LoreVia is built for manuscript intelligence",
        body: [
          "LoreVia starts from the manuscript and turns it into a working story system. That means character tracking, timeline recall, thread visibility, chapter-aware answers, beta-reader prep, and continuity review become part of the same workflow.",
          "It is especially useful when the challenge is not inventing the world, but keeping the written draft coherent while it changes.",
        ],
      },
      {
        heading: "Choose based on where your pain lives",
        body: [
          "Authors who mostly need a drafting cockpit may prefer Scrivener. Authors who mainly need planning databases may prefer Campfire. Authors who are wrestling with revision complexity, continuity drift, and story memory will usually get the most leverage from LoreVia.",
        ],
        highlight:
          "The best tool is the one that removes the bottleneck currently slowing the manuscript down.",
      },
    ],
    supportingAnswerSlugs: [
      "what-is-a-continuity-checker-for-fiction",
      "how-do-i-prepare-a-manuscript-for-beta-readers",
    ],
    demoSlug: "gregor-samsa-character-tracker",
  },
]

export const answerPages: AnswerPage[] = [
  {
    slug: "how-do-i-track-character-relationships-in-a-novel",
    question: "How do I track character relationships in a novel?",
    description: "A short system for tracking trust, conflict, history, and changing loyalties between characters.",
    publishedAt: "2026-05-14",
    publishedLabel: "May 14, 2026",
    articleSlug: "how-to-track-characters-in-a-novel",
    demoSlug: "pride-and-prejudice-relationship-map",
    shortAnswer:
      "Track the relationship itself, not just the two characters involved. Give each important bond a short record with current status, major shifts, scene references, and unresolved tension so you can see how it changes over the course of the book.",
    quickSteps: [
      "List the relationships that can change the plot or emotional stakes.",
      "Note the scene where the current status was last confirmed.",
      "Update the record whenever a betrayal, promise, confession, or alliance shift happens.",
    ],
    whyItMatters:
      "Relationship continuity is one of the fastest ways readers notice emotional inconsistency, especially in romance, family drama, and multi-POV fiction.",
  },
  {
    slug: "how-do-i-remember-small-details-in-a-long-manuscript",
    question: "How do I remember small details in a long manuscript?",
    description: "A practical answer for tracking details like injuries, clothing, objects, weather, and side promises.",
    publishedAt: "2026-05-14",
    publishedLabel: "May 14, 2026",
    articleSlug: "how-to-track-characters-in-a-novel",
    demoSlug: "gregor-samsa-character-tracker",
    shortAnswer:
      "Do not rely on memory once the draft gets long. Put small details into a searchable canon with chapter references so you can verify them quickly instead of rereading half the book every time a detail comes back.",
    quickSteps: [
      "Capture details only when they can create contradictions later.",
      "Attach every note to the scene or chapter that established it.",
      "Review those notes after major rewrites so stale facts do not survive into later drafts.",
    ],
    whyItMatters:
      "Tiny details are often the first cracks readers notice because they signal that the larger story may also be unstable.",
  },
  {
    slug: "how-do-i-avoid-plot-holes-in-my-story",
    question: "How do I avoid plot holes in my story?",
    description: "A concise workflow for catching missing cause-and-effect, broken setup/payoff, and unresolved story logic.",
    publishedAt: "2026-05-14",
    publishedLabel: "May 14, 2026",
    articleSlug: "how-to-avoid-continuity-errors-when-writing-a-novel",
    demoSlug: "dracula-story-timeline-tracker",
    shortAnswer:
      "Audit every major turning point for setup, consequence, and reader knowledge. Most plot holes appear when a story event happens without enough cause, without the right information being available, or without later consequences being acknowledged.",
    quickSteps: [
      "Check what made the event possible.",
      "Check who knew enough for the event to happen.",
      "Check what the event should change afterward.",
    ],
    whyItMatters:
      "A plot hole is usually a continuity problem with story logic rather than surface details.",
  },
  {
    slug: "how-do-authors-manage-timelines",
    question: "How do authors manage timelines?",
    description: "A short answer on tracking elapsed time, travel duration, flashbacks, and overlapping scenes.",
    publishedAt: "2026-05-14",
    publishedLabel: "May 14, 2026",
    articleSlug: "how-to-avoid-continuity-errors-when-writing-a-novel",
    demoSlug: "dracula-story-timeline-tracker",
    shortAnswer:
      "Authors manage timelines by anchoring scenes to concrete markers: day counts, travel time, seasonal clues, holidays, injuries healing, and where each POV overlaps with the others. Once those anchors exist, timeline problems become visible instead of intuitive.",
    quickSteps: [
      "Create a scene-by-scene timeline with elapsed time.",
      "Mark travel duration and any events that must happen off page.",
      "Re-check the timeline every time a chapter moves or expands.",
    ],
    whyItMatters:
      "Timeline drift is one of the most common causes of accidental continuity errors in long fiction.",
  },
  {
    slug: "what-is-manuscript-analysis",
    question: "What is manuscript analysis?",
    description: "A direct explanation of what manuscript analysis does for fiction authors and why it matters.",
    publishedAt: "2026-05-14",
    publishedLabel: "May 14, 2026",
    articleSlug: "what-is-a-story-bible-and-do-you-need-one",
    shortAnswer:
      "Manuscript analysis means turning the draft into something you can inspect, search, and reason about. For authors, that usually includes extracting characters, scenes, relationships, recurring facts, unresolved threads, and continuity risks from the manuscript itself.",
    quickSteps: [
      "Start with the manuscript, not a separate planning document.",
      "Extract the recurring facts that future chapters depend on.",
      "Use the analysis to support revision, continuity checks, and beta-reader prep.",
    ],
    whyItMatters:
      "Good manuscript analysis turns a long novel from a blur of pages into a workable editorial system.",
  },
  {
    slug: "what-is-a-continuity-checker-for-fiction",
    question: "What is a continuity checker for fiction?",
    description: "A quick definition of continuity checking for novels and how it differs from grammar tools.",
    publishedAt: "2026-05-14",
    publishedLabel: "May 14, 2026",
    articleSlug: "how-to-avoid-continuity-errors-when-writing-a-novel",
    demoSlug: "dracula-story-timeline-tracker",
    shortAnswer:
      "A continuity checker for fiction looks for contradictions inside the story itself. Instead of fixing spelling or grammar, it helps authors catch broken facts, timeline conflicts, dropped promises, character inconsistencies, and world-rule drift.",
    quickSteps: [
      "Define the facts your story has already established.",
      "Compare new chapters against those facts.",
      "Review contradictions with scene references before revising.",
    ],
    whyItMatters:
      "Grammar tools improve sentences. Continuity tools protect the logic of the book.",
  },
  {
    slug: "how-do-i-organize-chapters-and-scenes",
    question: "How do I organize chapters and scenes?",
    description: "A short guide for keeping chapters readable, searchable, and revision-friendly.",
    publishedAt: "2026-05-14",
    publishedLabel: "May 14, 2026",
    articleSlug: "what-is-a-story-bible-and-do-you-need-one",
    shortAnswer:
      "Organize chapters and scenes by function, not just order. Each scene should clearly show whose goal is active, what changes, and what information it establishes so later revision is easier to trace.",
    quickSteps: [
      "Label scenes with POV, location, and purpose.",
      "Track which scenes establish important facts or promises.",
      "Keep deleted or merged scene decisions visible during revision.",
    ],
    whyItMatters:
      "A clear scene structure makes it much easier to track continuity and prepare a manuscript for outside readers.",
  },
  {
    slug: "how-do-i-track-character-arcs",
    question: "How do I track character arcs?",
    description: "A concise answer on tracking emotional and behavioral change across the draft.",
    publishedAt: "2026-05-14",
    publishedLabel: "May 14, 2026",
    articleSlug: "how-to-track-characters-in-a-novel",
    demoSlug: "gregor-samsa-character-tracker",
    shortAnswer:
      "Track character arcs as a sequence of pressure points, not a summary paragraph. Note the belief or wound the character begins with, the scenes that challenge it, the choices that reveal change, and the final state they reach by the end.",
    quickSteps: [
      "Define the starting belief, flaw, or fear.",
      "Capture the scenes that force a visible change.",
      "Review whether the ending state is earned by those moments.",
    ],
    whyItMatters:
      "Arc tracking keeps emotional development from going flat or skipping steps between chapters.",
  },
  {
    slug: "how-do-i-create-a-story-bible-automatically",
    question: "How do I create a story bible automatically?",
    description: "A practical answer about using manuscript analysis to generate and maintain a story bible.",
    publishedAt: "2026-05-14",
    publishedLabel: "May 14, 2026",
    articleSlug: "what-is-a-story-bible-and-do-you-need-one",
    demoSlug: "pride-and-prejudice-relationship-map",
    shortAnswer:
      "Start from the manuscript and extract the recurring facts that matter: characters, aliases, locations, relationships, timeline anchors, and unresolved threads. Then keep those entries linked back to the scenes that proved them so the bible stays grounded.",
    quickSteps: [
      "Import the draft into a system that can read it as story data.",
      "Generate entries from the text, not from memory alone.",
      "Update the bible whenever major revision changes the canon.",
    ],
    whyItMatters:
      "Automation matters because the hardest part of a story bible is keeping it current after the manuscript changes.",
  },
  {
    slug: "how-do-i-prepare-a-manuscript-for-beta-readers",
    question: "How do I prepare a manuscript for beta readers?",
    description: "A short answer on continuity cleanup, reader packets, and the notes authors should make before outside feedback starts.",
    publishedAt: "2026-05-14",
    publishedLabel: "May 14, 2026",
    articleSlug: "best-writing-software-for-fiction-authors",
    shortAnswer:
      "Do a continuity pass before sending the draft out, define the questions you most want answered, and prepare a light support packet with character names, context, and any boundaries around spoilers or unfinished arcs.",
    quickSteps: [
      "Fix the obvious contradictions first so beta readers are not doing cleanup work.",
      "Decide what kind of feedback you want on plot, pacing, or character clarity.",
      "Package the manuscript with enough context to reduce confusion without over-explaining.",
    ],
    whyItMatters:
      "A better-prepared manuscript gets more useful reader feedback and fewer avoidable continuity comments.",
  },
]

export const demoPages: DemoPage[] = [
  {
    slug: "gregor-samsa-character-tracker",
    title: "Demo: Tracking Gregor Samsa Across The Metamorphosis",
    description:
      "A public-domain workflow example showing how LoreVia-style character tracking can follow transformations, family tension, and identity drift scene by scene.",
    publishedAt: "2026-05-14",
    publishedLabel: "May 14, 2026",
    sourceWork: "The Metamorphosis",
    sourceAuthor: "Franz Kafka",
    articleSlug: "how-to-track-characters-in-a-novel",
    answerSlugs: [
      "how-do-i-remember-small-details-in-a-long-manuscript",
      "how-do-i-track-character-arcs",
    ],
    featuredInsight:
      "Gregor's transformation is not only physical. A tracking system also surfaces how his family's language, fear, and obligation change around him.",
    sections: [
      {
        heading: "What the character record captures",
        body: [
          "A strong character tracker would capture Gregor's physical change, his role as provider, his shrinking agency, and the exact points where family members stop relating to him as a son and begin responding to him as a problem.",
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
    ],
  },
  {
    slug: "dracula-story-timeline-tracker",
    title: "Demo: Using Dracula to Show a Story Timeline Tracker",
    description:
      "A public-domain example showing how LoreVia-style timeline tracking can organize travel, diary entries, letters, and overlapping events in a complex manuscript.",
    publishedAt: "2026-05-14",
    publishedLabel: "May 14, 2026",
    sourceWork: "Dracula",
    sourceAuthor: "Bram Stoker",
    articleSlug: "how-to-avoid-continuity-errors-when-writing-a-novel",
    answerSlugs: [
      "how-do-authors-manage-timelines",
      "what-is-a-continuity-checker-for-fiction",
    ],
    featuredInsight:
      "Dracula is a perfect timeline demo because its letters, journals, and travel windows force the reader to reconcile overlapping accounts across multiple narrators.",
    sections: [
      {
        heading: "What the timeline system surfaces",
        body: [
          "A timeline tracker can line up journal entries, train travel, off-page movement, and the moments when one narrator learns what another already knows. That quickly exposes impossible travel windows or delayed knowledge transfer.",
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
    ],
  },
  {
    slug: "pride-and-prejudice-relationship-map",
    title: "Demo: Mapping Relationships in Pride and Prejudice",
    description:
      "A public-domain example showing how LoreVia-style relationship tracking can map conflict, prejudice, reversals, and social pressure through a novel.",
    publishedAt: "2026-05-14",
    publishedLabel: "May 14, 2026",
    sourceWork: "Pride and Prejudice",
    sourceAuthor: "Jane Austen",
    articleSlug: "what-is-a-story-bible-and-do-you-need-one",
    answerSlugs: [
      "how-do-i-track-character-relationships-in-a-novel",
      "how-do-i-create-a-story-bible-automatically",
    ],
    featuredInsight:
      "A relationship map shows not just who is connected, but how misread motives, social status, and shifting respect change the emotional geometry of the novel.",
    sections: [
      {
        heading: "What the relationship map captures",
        body: [
          "A relationship graph for Pride and Prejudice would track courtship pressure, family expectations, social friction, and the major reversals that change how Elizabeth, Darcy, Jane, Bingley, and Lady Catherine interact.",
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
    ],
  },
]

export function getBlogArticleBySlug(slug: string): BlogArticle | null {
  return blogArticles.find((article) => article.slug === slug) ?? null
}

export function getAnswerPageBySlug(slug: string): AnswerPage | null {
  return answerPages.find((answer) => answer.slug === slug) ?? null
}

export function getDemoPageBySlug(slug: string): DemoPage | null {
  return demoPages.find((demo) => demo.slug === slug) ?? null
}

export function getAnswersByArticleSlug(articleSlug: string): AnswerPage[] {
  return answerPages.filter((answer) => answer.articleSlug === articleSlug)
}

export function getAnswerPagesBySlugs(slugs: string[]): AnswerPage[] {
  return slugs
    .map((slug) => getAnswerPageBySlug(slug))
    .filter((answer): answer is AnswerPage => answer !== null)
}

export function getAllPublicContentPaths(): string[] {
  return [
    ...CONTENT_HUB_ROUTES,
    ...blogArticles.map((article) => `/blog/${article.slug}`),
    ...answerPages.map((answer) => `/answers/${answer.slug}`),
    ...demoPages.map((demo) => `/demo/${demo.slug}`),
  ]
}
