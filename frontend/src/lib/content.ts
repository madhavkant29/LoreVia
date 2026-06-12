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
  readTime: string
  articleSlug: string
  demoSlug?: string
  intro: string
  shortAnswer: string
  quickSteps: string[]
  whyItMatters: string
  sections: ContentSection[]
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

export type PublicContentEntry = {
  path: string
  publishedAt: string
  type: "hub" | "blog" | "answer" | "demo"
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
      "scrivener vs LoreVia",
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
  {
    slug: "how-to-use-lorevia-during-a-revision-week",
    title: "How to Use LoreVia During a Real Revision Week",
    description:
      "A practical Monday-to-Friday revision workflow for authors who want continuity checks, grounded questions, notes, and export prep to support the same draft instead of becoming separate chores.",
    category: "Revision workflow",
    publishedAt: "2026-06-12",
    publishedLabel: "June 12, 2026",
    readTime: "9 min read",
    keywords: [
      "fiction revision workflow",
      "how to revise a novel with AI tools",
      "manuscript revision software",
      "LoreVia workflow",
    ],
    intro:
      "A revision week can disappear into good intentions. You open the draft, reread three chapters, fix a sentence, remember a continuity problem, chase a note from last month, and somehow never reach the scene that actually needed attention. LoreVia is most useful when it gives that week a rhythm: read, inspect, decide, revise, and verify.",
    highlights: [
      "Use the first pass to locate risk, not to fix every sentence.",
      "Turn grounded answers into decisions you can apply to specific chapters.",
      "End the week by checking whether the revision created new continuity debt.",
    ],
    sections: [
      {
        heading: "Start by choosing one revision question",
        body: [
          "The fastest way to waste a revision session is to ask the draft to improve in every direction at once. Pick one question for the week: is the central relationship moving cleanly, does the timeline still work, or did the midpoint rewrite break a later reveal?",
          "Once the question is specific, LoreVia can support it with manuscript evidence. You can inspect the relevant characters, ask chapter-grounded questions, and keep notes attached to the scenes that need decisions instead of creating a separate pile of reminders.",
        ],
      },
      {
        heading: "Use Monday for orientation, not rewriting",
        body: [
          "On the first day, resist the urge to polish. Upload or refresh the manuscript, review the extracted story memory, and look for the places where the system is unsure or where the draft looks noisier than your memory of it.",
          "That orientation pass gives you a working map. The value is not that every extracted detail is sacred. The value is that the manuscript is now visible as a set of characters, scenes, relationships, timeline claims, and open threads you can inspect.",
        ],
        bullets: [
          "Review character records that changed in the last draft.",
          "Check relationships with recent scene cuts or rewritten dialogue.",
          "Skim continuity signals before touching line edits.",
        ],
      },
      {
        heading: "Spend the middle of the week making decisions",
        body: [
          "Tuesday through Thursday should be decision time. Ask direct questions such as where a promise first appears, who knows a secret before Chapter 18, or whether an injury has enough recovery time. Then use the answers to choose a fix in the manuscript.",
          "This is where grounded answers matter. A vague summary can make you feel oriented while still hiding the scene that proves or contradicts the claim. Chapter evidence lets you move from suspicion to edit without rereading the whole book.",
        ],
        highlight:
          "Revision gets easier when every question ends in a manuscript decision: keep, cut, move, clarify, or mark for a later pass.",
      },
      {
        heading: "End with a verification pass",
        body: [
          "Friday is for checking the consequences. If you moved a reveal, refresh the related thread. If you rewrote a relationship scene, check whether the later emotional beat still lands. If you deleted a chapter, inspect what facts lost their first appearance.",
          "That final pass is the habit that keeps revisions from compounding hidden problems. LoreVia should not replace judgment; it should give your judgment a better list of places to look before the draft goes to readers or editors.",
        ],
      },
    ],
    supportingAnswerSlugs: [
      "how-should-i-use-lorevia-after-uploading-a-draft",
      "how-do-i-use-lorevia-in-a-weekly-revision-routine",
      "what-should-i-ask-a-manuscript-assistant",
      "how-do-i-turn-continuity-findings-into-edits",
    ],
    demoSlug: "dracula-story-timeline-tracker",
  },
  {
    slug: "why-chapter-grounded-answers-matter-for-fiction-revision",
    title: "Why Chapter-Grounded Answers Matter for Fiction Revision",
    description:
      "A guide to using cited manuscript answers during revision, especially when authors need to verify plot logic, character memory, and continuity without trusting unsupported summaries.",
    category: "Grounded answers",
    publishedAt: "2026-06-12",
    publishedLabel: "June 12, 2026",
    readTime: "8 min read",
    keywords: [
      "chapter grounded answers",
      "manuscript AI assistant",
      "fiction writing assistant with citations",
      "ask questions about my novel",
    ],
    intro:
      "The problem with many writing assistants is not that they answer badly. It is that they answer too confidently without showing you where the answer came from. Fiction revision needs a different standard. If a tool tells you a character already knows something, you need to see the chapter that proves it.",
    highlights: [
      "Grounded answers help authors verify claims instead of accepting a polished guess.",
      "Chapter references make revision faster because the next edit location is visible.",
      "Citations protect the author's voice by keeping the draft, not the assistant, in charge.",
    ],
    sections: [
      {
        heading: "A good answer should point back to the page",
        body: [
          "When you ask whether a reveal has been set up, the useful answer is not just yes or no. The useful answer names the scenes where the setup appears, tells you what is missing, and lets you decide whether the reader has enough information.",
          "That is why LoreVia's answer workflow is built around the manuscript. The assistant can help you move through the draft, but the draft remains the source of truth.",
        ],
      },
      {
        heading: "Grounding is especially important in long manuscripts",
        body: [
          "In a short story, an author can often remember every scene. In a ninety-thousand-word novel, memory gets unreliable. A sentence written six months ago may be doing more structural work than you realize, or a deleted exchange may have removed the only explanation for a later choice.",
          "Chapter-grounded answers reduce that uncertainty. They do not ask you to trust a broad summary. They help you reopen the relevant part of the manuscript and make a real editorial decision.",
        ],
        bullets: [
          "Who knows this secret before the reveal?",
          "Where does this object last appear?",
          "Which chapters changed this relationship?",
        ],
      },
      {
        heading: "Citations make collaboration cleaner",
        body: [
          "Editors, beta readers, and coauthors all benefit when a question has evidence attached. Instead of debating whether a detail is present, the conversation can move to whether the detail is clear enough, early enough, or emotionally convincing.",
          "That shift matters. Revision is not just finding facts. It is deciding what the reader can understand from the facts the book actually gives them.",
        ],
      },
      {
        heading: "Use answers as a starting point, not a verdict",
        body: [
          "No author should outsource the meaning of a scene. A grounded answer is most useful when it starts a sharper reread. It narrows the search, surfaces likely evidence, and gives you enough context to judge the prose yourself.",
          "That keeps the workflow practical and author-led. LoreVia can help find the trail; the writer still decides what the trail should become.",
        ],
        highlight:
          "The safest writing assistant is one that keeps sending you back to your own manuscript.",
      },
    ],
    supportingAnswerSlugs: [
      "why-do-chapter-citations-matter-for-writing-software",
      "what-should-i-ask-a-manuscript-assistant",
      "how-can-i-find-dropped-plot-threads-before-beta-readers",
    ],
    demoSlug: "dracula-story-timeline-tracker",
  },
  {
    slug: "how-relationship-tracking-changes-a-character-rewrite",
    title: "How Relationship Tracking Changes a Character Rewrite",
    description:
      "A revision guide for authors using relationship tracking to keep emotional logic, trust shifts, betrayals, alliances, and romantic pacing coherent after major rewrites.",
    category: "Character systems",
    publishedAt: "2026-06-12",
    publishedLabel: "June 12, 2026",
    readTime: "9 min read",
    keywords: [
      "relationship tracking for writers",
      "character rewrite workflow",
      "fiction relationship map",
      "track character relationships in a novel",
    ],
    intro:
      "A character rewrite rarely changes one character alone. If you make a protagonist less trusting, every scene with the mentor changes. If you soften a rival, the romantic subplot may suddenly move too quickly. Relationship tracking helps authors see those knock-on effects before the emotional logic of the book starts to blur.",
    highlights: [
      "Track the bond itself, not only the two character profiles.",
      "Use relationship changes to find scenes that need new dialogue or motivation.",
      "Recheck later payoff scenes after changing early trust, resentment, or attraction.",
    ],
    sections: [
      {
        heading: "The relationship is a revision object",
        body: [
          "Writers often keep separate character sheets and hope the relationship will stay obvious in memory. During a rewrite, that is risky. The bond between two people has its own history, pressure, and pace.",
          "LoreVia makes that relationship easier to inspect by treating it as something with scenes, turns, and evidence. That helps when the draft changes but the emotional payoff still needs to feel earned.",
        ],
      },
      {
        heading: "Rewrite the cause, then check the effect",
        body: [
          "If you change why two characters mistrust each other, you have probably changed the argument in Chapter 9, the apology in Chapter 16, and the alliance in Chapter 24. Relationship tracking gives you a shortlist of scenes where that cause-and-effect chain may need attention.",
          "This is not busywork. It is how you keep the reader from feeling that a betrayal, confession, or reconciliation arrived because the outline required it rather than because the relationship earned it.",
        ],
        bullets: [
          "First meaningful tension",
          "Scenes that raise or lower trust",
          "Payoff moments that depend on earlier movement",
        ],
      },
      {
        heading: "Watch for emotional shortcuts",
        body: [
          "Rewrites often leave behind emotional shortcuts. Two characters forgive each other too quickly because a conflict scene was cut. A romantic beat feels sudden because a quieter attraction scene moved later. A rival becomes helpful without the page showing the shift.",
          "A relationship map makes those gaps easier to notice. The goal is not to force every feeling into a chart; it is to notice when the chart exposes a missing bridge.",
        ],
      },
      {
        heading: "Use the tracker before beta readers see the draft",
        body: [
          "Beta readers are very good at sensing when a relationship feels rushed or inconsistent, but they may not know exactly where the problem started. Running a relationship pass first lets you send them a cleaner draft and better questions.",
          "Ask them about the moments that still concern you: whether the reconciliation lands, whether the distrust makes sense, or whether the midpoint argument changes enough afterward.",
        ],
        highlight:
          "Relationship tracking turns vague feedback like 'I did not buy this' into a more precise search for the missing emotional turn.",
      },
    ],
    supportingAnswerSlugs: [
      "how-do-i-track-relationship-changes-between-drafts",
      "how-do-i-track-character-relationships-in-a-novel",
      "how-do-i-track-character-arcs",
    ],
    demoSlug: "pride-and-prejudice-relationship-map",
  },
  {
    slug: "how-to-prepare-beta-reader-packets-with-lorevia",
    title: "How to Prepare Beta Reader Packets with LoreVia",
    description:
      "A grounded workflow for turning manuscript analysis, continuity cleanup, and author questions into beta reader packets that get clearer and more useful feedback.",
    category: "Beta readers",
    publishedAt: "2026-06-12",
    publishedLabel: "June 12, 2026",
    readTime: "8 min read",
    keywords: [
      "beta reader packet",
      "prepare manuscript for beta readers",
      "fiction beta reader workflow",
      "author feedback questions",
    ],
    intro:
      "A beta reader packet is not a press kit. It is a small working document that helps readers give useful feedback without being overloaded by the author's private process. LoreVia can help authors build that packet from the manuscript itself: what changed, what might confuse readers, and what questions matter most this round.",
    highlights: [
      "Clean obvious continuity issues before asking readers to evaluate story impact.",
      "Give readers a few targeted questions instead of a long homework sheet.",
      "Use LoreVia's story memory to prepare context without explaining the book away.",
    ],
    sections: [
      {
        heading: "Start with the reader's job",
        body: [
          "Before sending pages, decide what you want the reader to notice. Are you testing whether the mystery is fair, whether the romance builds at the right pace, or whether the ending feels earned?",
          "A clear packet keeps that job visible. It should include the manuscript, the feedback priorities, any content boundaries, and just enough context to prevent avoidable confusion.",
        ],
      },
      {
        heading: "Use analysis to remove avoidable friction",
        body: [
          "LoreVia's continuity and story-memory views are useful before the packet goes out. If the protagonist's name changed in one chapter, fix it. If a timeline claim contradicts the chapter order, decide whether to repair it now or explicitly ask readers whether it confused them.",
          "This lets beta readers spend less energy on errors you could have caught and more energy on the experience only a fresh reader can report.",
        ],
        bullets: [
          "Run a continuity pass for names, dates, and obvious thread gaps.",
          "Review character and relationship summaries for stale details.",
          "Mark unresolved questions you intentionally want readers to react to.",
        ],
      },
      {
        heading: "Write questions that invite useful reactions",
        body: [
          "Good beta questions are specific without steering the reader into your preferred answer. Instead of asking whether the book is good, ask where their attention dropped, which character choice felt unsupported, or what they expected after a key reveal.",
          "LoreVia helps by turning draft concerns into concrete prompts. If the relationship tracker shows a thin emotional bridge, ask readers whether that moment felt believable rather than asking for general relationship feedback.",
        ],
      },
      {
        heading: "Keep the packet light",
        body: [
          "Readers do not need your entire story bible. They need enough context to read the draft fairly. A short cast note, spoiler expectations, deadline, format instructions, and five to eight questions are usually more useful than a long explanation of every concern.",
          "The manuscript still has to stand on its own. The packet's job is to focus attention, not to defend the book in advance.",
        ],
        highlight:
          "The best beta packet feels like an invitation to respond, not a manual for how to read.",
      },
    ],
    supportingAnswerSlugs: [
      "what-should-go-in-a-beta-reader-packet",
      "how-do-i-prepare-a-manuscript-for-beta-readers",
      "how-can-i-find-dropped-plot-threads-before-beta-readers",
    ],
    demoSlug: "gregor-samsa-character-tracker",
  },
  {
    slug: "how-to-keep-a-series-bible-alive",
    title: "How to Keep a Series Bible Alive Without Becoming a Librarian",
    description:
      "A workflow for maintaining series canon, recurring characters, world rules, and cross-book continuity without turning the story bible into a second full-time project.",
    category: "Series continuity",
    publishedAt: "2026-06-12",
    publishedLabel: "June 12, 2026",
    readTime: "10 min read",
    keywords: [
      "series bible for authors",
      "series continuity software",
      "track canon across books",
      "multi book story bible",
    ],
    intro:
      "A series bible is supposed to make the next book easier. Too often it becomes a museum of half-updated facts. The trick is to stop treating it like an encyclopedia and start treating it like a continuity tool: what has the series made true, where was it established, and what future scenes depend on it?",
    highlights: [
      "Track canon by evidence and dependency, not by how interesting the lore feels.",
      "Refresh the bible after structural edits so stale facts do not travel into the next book.",
      "Use cross-book questions to check recurring characters, promises, and world rules.",
    ],
    sections: [
      {
        heading: "A living bible needs a maintenance rule",
        body: [
          "If every small detail has to be entered by hand, the bible will eventually stop matching the books. Authors need a maintenance rule that is simple enough to survive deadlines: update the bible when a fact creates future obligations.",
          "That means recurring character history, world rules, timeline anchors, vows, injuries, political changes, magical costs, and unresolved promises deserve attention. Decorative facts can wait unless they become structurally important.",
        ],
      },
      {
        heading: "Tie canon to the book that proved it",
        body: [
          "Series continuity fails when notes lose their source. If a city law, family secret, or character scar matters in Book 3, the bible should tell you where that fact appeared in Book 1 or Book 2.",
          "LoreVia's chapter-grounded workflow is useful here because it keeps the author close to evidence. You can ask where a rule was introduced, whether a character already knows it, and which later scenes depend on it.",
        ],
        bullets: [
          "First book and chapter where the fact appears",
          "Characters who know or misunderstand the fact",
          "Scenes in later books that depend on the fact remaining true",
        ],
      },
      {
        heading: "Use the bible during planning, not only cleanup",
        body: [
          "A series bible is not just a place to check mistakes after drafting. It can shape the next book before the first chapter is written. Reviewing open promises, damaged relationships, and unresolved rules can show which threads are ready for payoff.",
          "This is where a living system beats a static document. It lets the previous manuscript become useful pressure on the next one without forcing the author to reread everything from scratch.",
        ],
      },
      {
        heading: "Do a canon audit before release",
        body: [
          "Before a book goes out, run a focused audit on anything that crosses book boundaries. Check returning characters, old promises, world rules, travel assumptions, and timeline references. Then update the bible with the final decisions from the release draft.",
          "That last step protects the next project. It means the author's starting point is the published canon, not a memory of the draft that existed three revisions earlier.",
        ],
        highlight:
          "A good series bible is less about collecting lore and more about preventing old decisions from becoming new contradictions.",
      },
    ],
    supportingAnswerSlugs: [
      "how-do-i-use-continuity-tracking-across-a-series",
      "what-belongs-in-a-series-bible",
      "how-do-i-create-a-story-bible-automatically",
    ],
    demoSlug: "pride-and-prejudice-relationship-map",
  },
]

export const answerPages: AnswerPage[] = [
  {
    slug: "how-do-i-track-character-relationships-in-a-novel",
    question: "How do I track character relationships in a novel?",
    description: "A short system for tracking trust, conflict, history, and changing loyalties between characters.",
    publishedAt: "2026-05-14",
    publishedLabel: "May 14, 2026",
    readTime: "4 min read",
    articleSlug: "how-to-track-characters-in-a-novel",
    demoSlug: "pride-and-prejudice-relationship-map",
    intro:
      "When authors say they lose track of relationships, they usually do not mean they forgot who knows whom. They mean the emotional state between two characters has become blurry. The manuscript knows they are siblings, rivals, ex-lovers, or allies, but it no longer shows exactly when trust broke, when tension softened, or why a reaction now feels different from three chapters earlier.",
    shortAnswer:
      "Track the relationship itself, not just the two characters involved. Give each important bond a short record with current status, major shifts, scene references, and unresolved tension so you can see how it changes over the course of the book.",
    quickSteps: [
      "List the relationships that can change the plot or emotional stakes.",
      "Note the scene where the current status was last confirmed.",
      "Update the record whenever a betrayal, promise, confession, or alliance shift happens.",
    ],
    whyItMatters:
      "Relationship continuity is one of the fastest ways readers notice emotional inconsistency, especially in romance, family drama, and multi-POV fiction.",
    sections: [
      {
        heading: "Track movement, not labels",
        body: [
          "A label like enemies, friends, or in love is not enough for revision. What matters is movement. Record the current level of trust, the pressure currently acting on the bond, and the last event that changed how the characters read each other.",
          "That lets you spot scenes where the dialogue assumes warmth the story has not earned yet, or where a conflict should still be sharper because no real repair happened on the page.",
        ],
        bullets: [
          "Current status and the last scene that proved it",
          "What each person wants from the other right now",
          "What misunderstanding, resentment, or promise is still unresolved",
        ],
      },
      {
        heading: "Use scene evidence whenever the bond shifts",
        body: [
          "Relationship notes become useful when they point back to the manuscript. If a reconciliation happens in chapter twelve, record chapter twelve. If a secret changes the balance of power, note where that knowledge transfer actually happens.",
          "This keeps the tracker grounded. It also gives you a fast way to check whether later scenes are reacting to the relationship that exists on the page, not the one you remember from your outline.",
        ],
      },
    ],
  },
  {
    slug: "how-do-i-remember-small-details-in-a-long-manuscript",
    question: "How do I remember small details in a long manuscript?",
    description: "A practical answer for tracking details like injuries, clothing, objects, weather, and side promises.",
    publishedAt: "2026-05-14",
    publishedLabel: "May 14, 2026",
    readTime: "4 min read",
    articleSlug: "how-to-track-characters-in-a-novel",
    demoSlug: "gregor-samsa-character-tracker",
    intro:
      "The details authors forget are rarely the dramatic centerpiece of the story. They are the small facts that quietly build trust with the reader: who limps after the fight, which ring belonged to the mother, whether the rain already started, or what promise was made in passing two chapters ago. Those details feel minor until they contradict each other.",
    shortAnswer:
      "Do not rely on memory once the draft gets long. Put small details into a searchable canon with chapter references so you can verify them quickly instead of rereading half the book every time a detail comes back.",
    quickSteps: [
      "Capture details only when they can create contradictions later.",
      "Attach every note to the scene or chapter that established it.",
      "Review those notes after major rewrites so stale facts do not survive into later drafts.",
    ],
    whyItMatters:
      "Tiny details are often the first cracks readers notice because they signal that the larger story may also be unstable.",
    sections: [
      {
        heading: "Choose details by risk, not by volume",
        body: [
          "You do not need to log every cup of tea or every item in a room. Track the details that can break continuity later: visible injuries, heirlooms, passwords, weather conditions, missing objects, recurring clothing, or offhand promises that will matter if they disappear.",
          "This keeps the system lean enough to use. A good canon is selective. It stores the facts most likely to create reader confusion if they drift during revision.",
        ],
      },
      {
        heading: "Make retrieval faster than rereading",
        body: [
          "The tracker has to beat your fallback habit, which is usually opening old chapters and hunting by instinct. If a note includes the chapter, scene, and brief context, you can confirm the fact in seconds instead of losing momentum.",
          "That matters most during revision, because a long manuscript creates dozens of moments where a returning detail needs to be checked before the next scene can be trusted.",
        ],
        bullets: [
          "Store the fact in the words you would search later",
          "Keep the chapter or scene citation beside it",
          "Re-check detail notes after merges, cuts, and timeline changes",
        ],
      },
    ],
  },
  {
    slug: "how-do-i-avoid-plot-holes-in-my-story",
    question: "How do I avoid plot holes in my story?",
    description: "A concise workflow for catching missing cause-and-effect, broken setup/payoff, and unresolved story logic.",
    publishedAt: "2026-05-14",
    publishedLabel: "May 14, 2026",
    readTime: "4 min read",
    articleSlug: "how-to-avoid-continuity-errors-when-writing-a-novel",
    demoSlug: "dracula-story-timeline-tracker",
    intro:
      "Most plot holes are not giant conceptual disasters. They are ordinary logic gaps that opened during drafting or revision: a character acts on information they never received, a solution arrives before the setup exists, or a major event changes nothing afterward. The way to avoid them is to inspect cause, access, and consequence at every turning point.",
    shortAnswer:
      "Audit every major turning point for setup, consequence, and reader knowledge. Most plot holes appear when a story event happens without enough cause, without the right information being available, or without later consequences being acknowledged.",
    quickSteps: [
      "Check what made the event possible.",
      "Check who knew enough for the event to happen.",
      "Check what the event should change afterward.",
    ],
    whyItMatters:
      "A plot hole is usually a continuity problem with story logic rather than surface details.",
    sections: [
      {
        heading: "Interrogate the event from three angles",
        body: [
          "When a scene feels wrong, ask three direct questions. What caused this event? Who had the knowledge or access needed for it? What should this event change going forward? If one answer is thin, the problem is probably not style. It is structure.",
          "This method is practical because it applies to action scenes, mysteries, romance turns, reveals, and quieter emotional pivots. The genre changes, but cause-and-effect discipline does not.",
        ],
      },
      {
        heading: "Look for holes after revision, not only after drafting",
        body: [
          "Large edits create fresh logic problems. Delete a setup scene, move an explanation, soften a motivation, or shorten the travel time and you may open a new hole downstream without noticing it immediately.",
          "That is why plot-hole checking belongs inside revision passes. Treat every structural change as a reason to review the scenes that depend on it, especially revelations, reversals, and endings.",
        ],
        bullets: [
          "Turning points should have visible setup",
          "Characters should not act on missing knowledge",
          "Big events should leave consequences behind them",
        ],
      },
    ],
  },
  {
    slug: "how-do-authors-manage-timelines",
    question: "How do authors manage timelines?",
    description: "A short answer on tracking elapsed time, travel duration, flashbacks, and overlapping scenes.",
    publishedAt: "2026-05-14",
    publishedLabel: "May 14, 2026",
    readTime: "4 min read",
    articleSlug: "how-to-avoid-continuity-errors-when-writing-a-novel",
    demoSlug: "dracula-story-timeline-tracker",
    intro:
      "A manuscript can feel temporally correct while the actual math is broken. Characters seem to move naturally until you realize they crossed a country overnight, healed too quickly, or learned information before the relevant scene occurred. Authors manage timelines by externalizing time into something visible and checkable instead of keeping it in intuition alone.",
    shortAnswer:
      "Authors manage timelines by anchoring scenes to concrete markers: day counts, travel time, seasonal clues, holidays, injuries healing, and where each POV overlaps with the others. Once those anchors exist, timeline problems become visible instead of intuitive.",
    quickSteps: [
      "Create a scene-by-scene timeline with elapsed time.",
      "Mark travel duration and any events that must happen off page.",
      "Re-check the timeline every time a chapter moves or expands.",
    ],
    whyItMatters:
      "Timeline drift is one of the most common causes of accidental continuity errors in long fiction.",
    sections: [
      {
        heading: "Anchor scenes to observable markers",
        body: [
          "You do not need a complicated spreadsheet to start. You need anchors. That can be sunrise, a festival date, a bus ride, a wound healing over three days, or an email sent after midnight. Those anchors create real spacing between scenes.",
          "Once every major chapter has one or two markers, impossible sequences start revealing themselves. You can see whether the chronology supports the story instead of merely sounding plausible.",
        ],
      },
      {
        heading: "Track overlap when multiple threads run at once",
        body: [
          "Timelines get harder when several POVs, flashbacks, or epistolary documents interact. In those cases, the question is not only what happened when, but also what each character could know at that moment.",
          "A reliable timeline therefore tracks both elapsed time and knowledge transfer. That combination helps catch reveals that arrive too early and convergences that happen before the separate strands truly line up.",
        ],
        bullets: [
          "Elapsed time between scenes",
          "Travel and recovery duration",
          "Moments where knowledge moves from one thread to another",
        ],
      },
    ],
  },
  {
    slug: "what-is-manuscript-analysis",
    question: "What is manuscript analysis?",
    description: "A direct explanation of what manuscript analysis does for fiction authors and why it matters.",
    publishedAt: "2026-05-14",
    publishedLabel: "May 14, 2026",
    readTime: "4 min read",
    articleSlug: "what-is-a-story-bible-and-do-you-need-one",
    intro:
      "For fiction authors, manuscript analysis is not a vague AI promise. It is the practical act of turning the draft into information you can inspect. Instead of seeing only pages, you start seeing recurring characters, scene relationships, unresolved threads, timeline anchors, and continuity pressure points that can support revision decisions.",
    shortAnswer:
      "Manuscript analysis means turning the draft into something you can inspect, search, and reason about. For authors, that usually includes extracting characters, scenes, relationships, recurring facts, unresolved threads, and continuity risks from the manuscript itself.",
    quickSteps: [
      "Start with the manuscript, not a separate planning document.",
      "Extract the recurring facts that future chapters depend on.",
      "Use the analysis to support revision, continuity checks, and beta-reader prep.",
    ],
    whyItMatters:
      "Good manuscript analysis turns a long novel from a blur of pages into a workable editorial system.",
    sections: [
      {
        heading: "The point is inspection, not automation theater",
        body: [
          "A useful analysis layer gives you questions you can actually answer: where a character last appeared, which scenes moved a relationship, what promises still lack payoff, or whether a world rule is drifting. If the output cannot support those questions, it is not helping the manuscript.",
          "That is why grounded evidence matters. Authors need analysis tied back to chapters and scenes, not disconnected summaries that sound confident but cannot be verified.",
        ],
      },
      {
        heading: "It becomes most valuable during revision",
        body: [
          "Drafting is often about momentum. Revision is about remembering what the book has already committed to. Manuscript analysis is strongest in that second phase because it gives shape to a long draft that has become difficult to hold in working memory.",
          "Once the manuscript becomes searchable as story data, continuity review, story-bible upkeep, and beta-reader preparation all become faster and more defensible.",
        ],
      },
    ],
  },
  {
    slug: "what-is-a-continuity-checker-for-fiction",
    question: "What is a continuity checker for fiction?",
    description: "A quick definition of continuity checking for novels and how it differs from grammar tools.",
    publishedAt: "2026-05-14",
    publishedLabel: "May 14, 2026",
    readTime: "4 min read",
    articleSlug: "how-to-avoid-continuity-errors-when-writing-a-novel",
    demoSlug: "dracula-story-timeline-tracker",
    intro:
      "A continuity checker for fiction is not trying to improve your sentences. It is trying to protect the internal truth of the story. That means monitoring the facts, relationships, timing, and world rules the manuscript has already established so later scenes do not quietly contradict them.",
    shortAnswer:
      "A continuity checker for fiction looks for contradictions inside the story itself. Instead of fixing spelling or grammar, it helps authors catch broken facts, timeline conflicts, dropped promises, character inconsistencies, and world-rule drift.",
    quickSteps: [
      "Define the facts your story has already established.",
      "Compare new chapters against those facts.",
      "Review contradictions with scene references before revising.",
    ],
    whyItMatters:
      "Grammar tools improve sentences. Continuity tools protect the logic of the book.",
    sections: [
      {
        heading: "Continuity checking covers more than plot",
        body: [
          "Authors often hear continuity and think only of plot holes, but the scope is wider. It includes injuries, travel time, relationship memory, object placement, ages, weather, magical limits, and what each character knows at any given point.",
          "That wider view matters because readers usually experience continuity as trust. When small facts stop aligning, the story starts to feel less solid even before a major contradiction appears.",
        ],
      },
      {
        heading: "The best checker points back to scenes",
        body: [
          "A warning is only useful if you can verify it quickly. Good continuity support therefore pairs the possible conflict with the scenes that created the original fact and the scene that may now contradict it.",
          "That makes the tool editorially useful. It helps you decide whether the new chapter should change, whether the older canon should be revised, or whether the apparent contradiction is actually intentional.",
        ],
        bullets: [
          "Fact continuity",
          "Timeline continuity",
          "Relationship and knowledge continuity",
        ],
      },
    ],
  },
  {
    slug: "how-do-i-organize-chapters-and-scenes",
    question: "How do I organize chapters and scenes?",
    description: "A short guide for keeping chapters readable, searchable, and revision-friendly.",
    publishedAt: "2026-05-14",
    publishedLabel: "May 14, 2026",
    readTime: "4 min read",
    articleSlug: "what-is-a-story-bible-and-do-you-need-one",
    intro:
      "Chapter organization becomes a real editorial problem once a draft grows beyond a few clean acts. Authors stop needing a simple order list and start needing a way to understand what each scene is doing, what information it establishes, and what later chapters depend on it. Good organization makes revision possible at speed.",
    shortAnswer:
      "Organize chapters and scenes by function, not just order. Each scene should clearly show whose goal is active, what changes, and what information it establishes so later revision is easier to trace.",
    quickSteps: [
      "Label scenes with POV, location, and purpose.",
      "Track which scenes establish important facts or promises.",
      "Keep deleted or merged scene decisions visible during revision.",
    ],
    whyItMatters:
      "A clear scene structure makes it much easier to track continuity and prepare a manuscript for outside readers.",
    sections: [
      {
        heading: "Treat scenes as units of change",
        body: [
          "A scene should be easy to identify by what shifts inside it. That could be a decision, a revealed fact, a failed attempt, a relationship turn, or a new threat. When scenes are labeled only by chapter number, revision forces you to reread constantly.",
          "When they are labeled by POV, location, and narrative function, you can move through the manuscript with much more editorial clarity.",
        ],
      },
      {
        heading: "Preserve the history of structural edits",
        body: [
          "Organization also means remembering what changed. If chapter eight was split, if a bridge scene was cut, or if two conversations were merged, make that visible somewhere in your notes or tracker.",
          "Those decisions often explain later continuity problems. A scene system that remembers structural history is far more useful than one that only records the manuscript as it currently looks.",
        ],
        bullets: [
          "POV and location",
          "Purpose of the scene",
          "Facts, promises, or emotional changes established there",
        ],
      },
    ],
  },
  {
    slug: "how-do-i-track-character-arcs",
    question: "How do I track character arcs?",
    description: "A concise answer on tracking emotional and behavioral change across the draft.",
    publishedAt: "2026-05-14",
    publishedLabel: "May 14, 2026",
    readTime: "4 min read",
    articleSlug: "how-to-track-characters-in-a-novel",
    demoSlug: "gregor-samsa-character-tracker",
    intro:
      "A character arc becomes hard to manage when it exists only as a feeling. You know the protagonist is changing, but you cannot point to the precise scenes that challenged their belief, escalated the pressure, or earned the final transformation. Arc tracking fixes that by turning emotional development into a traceable sequence.",
    shortAnswer:
      "Track character arcs as a sequence of pressure points, not a summary paragraph. Note the belief or wound the character begins with, the scenes that challenge it, the choices that reveal change, and the final state they reach by the end.",
    quickSteps: [
      "Define the starting belief, flaw, or fear.",
      "Capture the scenes that force a visible change.",
      "Review whether the ending state is earned by those moments.",
    ],
    whyItMatters:
      "Arc tracking keeps emotional development from going flat or skipping steps between chapters.",
    sections: [
      {
        heading: "Map the pressure points that force change",
        body: [
          "An arc is easier to follow when you identify the scenes that actually apply pressure. These are not every scene the character appears in. They are the scenes that expose a flaw, test a belief, or force a choice that reveals a different self.",
          "If those moments are visible in sequence, you can tell whether the ending lands naturally or whether a transformation is being declared without enough narrative support.",
        ],
      },
      {
        heading: "Track internal change beside external events",
        body: [
          "Plots are noisy. Battles, arguments, mysteries, and twists can hide the emotional line if you only track external action. Arc notes should therefore record what the event did to the character's worldview, not only what happened on the surface.",
          "That is especially useful in revision, where an external scene may survive but its emotional effect may have shifted after neighboring scenes were cut or rewritten.",
        ],
        bullets: [
          "Starting belief or wound",
          "Scenes that challenge it",
          "Choice points that prove the change",
        ],
      },
    ],
  },
  {
    slug: "how-do-i-create-a-story-bible-automatically",
    question: "How do I create a story bible automatically?",
    description: "A practical answer about using manuscript analysis to generate and maintain a story bible.",
    publishedAt: "2026-05-14",
    publishedLabel: "May 14, 2026",
    readTime: "4 min read",
    articleSlug: "what-is-a-story-bible-and-do-you-need-one",
    demoSlug: "pride-and-prejudice-relationship-map",
    intro:
      "Automation only helps if it starts from the manuscript itself. A story bible generated from memory tends to reproduce the same gaps the author already has. A story bible generated from the draft can surface the canon that is actually on the page and make upkeep far less fragile during revision.",
    shortAnswer:
      "Start from the manuscript and extract the recurring facts that matter: characters, aliases, locations, relationships, timeline anchors, and unresolved threads. Then keep those entries linked back to the scenes that proved them so the bible stays grounded.",
    quickSteps: [
      "Import the draft into a system that can read it as story data.",
      "Generate entries from the text, not from memory alone.",
      "Update the bible whenever major revision changes the canon.",
    ],
    whyItMatters:
      "Automation matters because the hardest part of a story bible is keeping it current after the manuscript changes.",
    sections: [
      {
        heading: "Generate the entries authors usually abandon",
        body: [
          "The best automation targets the parts writers do not consistently maintain by hand: aliases, chapter references, relationship links, recurring locations, and unresolved threads. Those are the records that quietly go stale when the manuscript shifts.",
          "If the system can produce those entries from the draft, the bible stops being a second project and starts acting like living editorial infrastructure.",
        ],
      },
      {
        heading: "Keep the bible tied to evidence",
        body: [
          "A generated story bible still needs grounding. Each entry should be traceable back to the text that established it. Otherwise the author cannot tell whether a note reflects canon, inference, or a stale earlier draft.",
          "That scene-level grounding is what keeps automatic generation useful after multiple revisions. It lets authors refresh the bible without losing trust in it.",
        ],
        bullets: [
          "Characters and aliases",
          "Locations and world rules",
          "Timeline anchors and unresolved threads",
        ],
      },
    ],
  },
  {
    slug: "how-do-i-prepare-a-manuscript-for-beta-readers",
    question: "How do I prepare a manuscript for beta readers?",
    description: "A short answer on continuity cleanup, reader packets, and the notes authors should make before outside feedback starts.",
    publishedAt: "2026-05-14",
    publishedLabel: "May 14, 2026",
    readTime: "4 min read",
    articleSlug: "best-writing-software-for-fiction-authors",
    intro:
      "Beta readers are most helpful when they are reacting to the story you meant to show them, not tripping over fixable confusion you already suspected. Preparation is therefore less about polishing every sentence and more about removing avoidable friction, clarifying your questions, and making the manuscript easy to read as a draft in progress.",
    shortAnswer:
      "Do a continuity pass before sending the draft out, define the questions you most want answered, and prepare a light support packet with character names, context, and any boundaries around spoilers or unfinished arcs.",
    quickSteps: [
      "Fix the obvious contradictions first so beta readers are not doing cleanup work.",
      "Decide what kind of feedback you want on plot, pacing, or character clarity.",
      "Package the manuscript with enough context to reduce confusion without over-explaining.",
    ],
    whyItMatters:
      "A better-prepared manuscript gets more useful reader feedback and fewer avoidable continuity comments.",
    sections: [
      {
        heading: "Clean the draft before asking for reactions",
        body: [
          "Beta readers should not be spending their attention on the contradictions you already know how to fix. Run a quick continuity pass first, especially on names, timeline drift, missing setup, and obvious scene-order confusion.",
          "That pass does not need to be perfectionist. Its job is to remove the avoidable noise that would otherwise dilute the feedback you actually need.",
        ],
      },
      {
        heading: "Guide the feedback without scripting it",
        body: [
          "Readers give stronger notes when they know what kind of help you want. Tell them whether you are most concerned about pacing, motivation, confusion, emotional payoff, or the clarity of the ending.",
          "A light packet with character names, context, and response questions is usually enough. Too much explanation can flatten the authentic reader experience you are trying to test.",
        ],
        bullets: [
          "State the feedback priorities clearly",
          "Give only the context needed to read well",
          "Keep your own revision questions visible while responses come in",
        ],
      },
    ],
  },
  {
    slug: "how-should-i-use-lorevia-after-uploading-a-draft",
    question: "How should I use LoreVia after uploading a draft?",
    description: "A first-session workflow for turning an imported manuscript into useful revision context.",
    publishedAt: "2026-06-12",
    publishedLabel: "June 12, 2026",
    readTime: "4 min read",
    articleSlug: "how-to-use-lorevia-during-a-revision-week",
    intro:
      "The first session after uploading a draft should not be a frantic editing sprint. Treat it like opening a new set of editorial instruments. The goal is to learn what LoreVia can see clearly, what needs author correction, and which parts of the manuscript deserve the next focused pass.",
    shortAnswer:
      "Start by reviewing the extracted chapters, character records, relationships, and timeline signals. Correct obvious extraction mistakes, then choose one revision question and use grounded answers or continuity views to locate the scenes that need decisions.",
    quickSteps: [
      "Confirm the chapter structure and import boundaries look right.",
      "Review the highest-value story memory: main characters, relationships, and open threads.",
      "Ask one concrete question about the draft before making edits.",
    ],
    whyItMatters:
      "A calm first pass helps LoreVia become a working revision system instead of another place where notes pile up.",
    sections: [
      {
        heading: "Do not try to solve the whole book immediately",
        body: [
          "A manuscript import gives you a lot of surfaces at once. If you jump between every character, timeline event, note, and answer, the session can feel busy without becoming useful.",
          "Pick the area with the most revision pressure. If you are worried about continuity, start there. If the emotional arc is unstable, start with relationships and character history.",
        ],
      },
      {
        heading: "Make the system more trustworthy",
        body: [
          "Review the records that matter most and fix anything obviously stale or misread. The point is not to perfect the database on day one. It is to make the parts you plan to use this week accurate enough to support real decisions.",
          "Once the import looks reliable, ask a grounded question and follow the answer back to the manuscript. That closes the loop between analysis and editing.",
        ],
        bullets: [
          "Correct names and aliases for major characters.",
          "Check whether chapter labels match the manuscript.",
          "Turn one answer into one specific revision action.",
        ],
      },
    ],
  },
  {
    slug: "what-should-i-ask-a-manuscript-assistant",
    question: "What should I ask a manuscript assistant?",
    description: "Examples of useful revision questions that keep the author in control of the manuscript.",
    publishedAt: "2026-06-12",
    publishedLabel: "June 12, 2026",
    readTime: "4 min read",
    articleSlug: "why-chapter-grounded-answers-matter-for-fiction-revision",
    intro:
      "The best questions for a manuscript assistant are not vague requests to improve the book. They are questions that help you locate evidence, test a concern, or choose between revision options. A good question gives the assistant a narrow job and leaves the author with the decision.",
    shortAnswer:
      "Ask questions that point to scenes, causality, character knowledge, timeline order, relationship change, or unresolved promises. Avoid broad prompts that invite generic advice without proving anything from the draft.",
    quickSteps: [
      "Ask where a fact appears before asking whether it works.",
      "Ask who knows something at a specific chapter point.",
      "Ask which scenes support a payoff before rewriting the payoff.",
    ],
    whyItMatters:
      "Sharper questions create answers you can verify in the manuscript instead of advice that sounds plausible but cannot guide an edit.",
    sections: [
      {
        heading: "Ask for evidence before advice",
        body: [
          "A useful manuscript question often starts with where, when, or who. Where did I first establish the vault key? When does Mara learn about the betrayal? Who has enough information to suspect the killer before the midpoint?",
          "Those questions help you inspect the book you already wrote. Once you see the evidence, you can decide whether the setup needs more weight or the payoff needs less explanation.",
        ],
      },
      {
        heading: "Make the question match the revision stage",
        body: [
          "During structural revision, ask about causality, timeline, promises, and motivation. During a character pass, ask about relationships, wounds, voice, and knowledge. During final cleanup, ask about repeated facts, names, objects, and scene order.",
          "The assistant is most helpful when it supports the pass you are actually doing, not every possible pass at once.",
        ],
        bullets: [
          "Structural: what breaks if this scene moves?",
          "Character: which scenes change this relationship?",
          "Continuity: where does this detail contradict itself?",
        ],
      },
    ],
  },
  {
    slug: "why-do-chapter-citations-matter-for-writing-software",
    question: "Why do chapter citations matter for writing software?",
    description: "A clear explanation of why fiction revision tools should show where an answer came from.",
    publishedAt: "2026-06-12",
    publishedLabel: "June 12, 2026",
    readTime: "4 min read",
    articleSlug: "why-chapter-grounded-answers-matter-for-fiction-revision",
    demoSlug: "dracula-story-timeline-tracker",
    intro:
      "Chapter citations matter because fiction revision is evidence work. If software says a clue is present, a relationship has changed, or a timeline still works, the author needs to see the part of the manuscript behind that claim.",
    shortAnswer:
      "Citations make answers verifiable. They help authors reopen the relevant chapter, judge the scene themselves, and avoid making edits based on confident but unsupported summaries.",
    quickSteps: [
      "Prefer answers that name the chapter or scene behind the claim.",
      "Use citations to jump from analysis into the next edit location.",
      "Treat uncited answers as suggestions, not manuscript evidence.",
    ],
    whyItMatters:
      "Without citations, a writing assistant can sound helpful while quietly separating the author from the draft.",
    sections: [
      {
        heading: "A cited answer keeps the manuscript in charge",
        body: [
          "Fiction tools should not replace the author's memory with a new unsupported memory. They should improve the author's access to the manuscript. Chapter citations do that by showing where the answer came from.",
          "That is especially useful when a question is delicate: whether a secret is fairly planted, whether a character has enough motivation, or whether a later scene contradicts an earlier rule.",
        ],
      },
      {
        heading: "Citations make revision faster",
        body: [
          "The practical benefit is speed. If an answer tells you the relevant evidence lives in Chapters 7, 11, and 18, you can move directly to the scenes that matter instead of rereading the entire draft with a vague concern in mind.",
          "That does not make the edit automatic. It simply makes the next author decision easier to reach.",
        ],
        bullets: [
          "Verify setup before changing payoff.",
          "Find stale facts after moving chapters.",
          "Check reader knowledge at a specific point in the story.",
        ],
      },
    ],
  },
  {
    slug: "how-do-i-use-lorevia-in-a-weekly-revision-routine",
    question: "How do I use LoreVia in a weekly revision routine?",
    description: "A repeatable weekly rhythm for authors revising a novel with LoreVia.",
    publishedAt: "2026-06-12",
    publishedLabel: "June 12, 2026",
    readTime: "4 min read",
    articleSlug: "how-to-use-lorevia-during-a-revision-week",
    intro:
      "A weekly routine works better than occasional giant cleanup sessions. LoreVia fits that rhythm when you give each day a clear job: orient, inspect, revise, verify, and prepare the next pass.",
    shortAnswer:
      "Use the beginning of the week to review manuscript intelligence, the middle to make targeted edits, and the end to check whether those edits changed continuity, relationships, or open threads.",
    quickSteps: [
      "Monday: review story memory and choose the week's revision question.",
      "Tuesday to Thursday: edit the scenes connected to that question.",
      "Friday: refresh the related records and verify consequences.",
    ],
    whyItMatters:
      "A routine turns LoreVia from an occasional lookup tool into part of the author's actual revision cadence.",
    sections: [
      {
        heading: "Keep the week narrow",
        body: [
          "One week does not need to solve every weakness in the draft. Choose a pass: timeline, relationship, plot thread, character motivation, or beta-reader prep. Then use LoreVia around that pass.",
          "This prevents the tool from becoming another dashboard you glance at without acting on. The point is to turn analysis into a sequence of manuscript decisions.",
        ],
      },
      {
        heading: "Leave yourself a visible trail",
        body: [
          "When you find an issue, note the decision you made. If the fix is not immediate, keep it tied to the chapter or story record that exposed it. That makes the next session easier to resume.",
          "At the end of the week, review what changed. If the rewrite moved a reveal, altered a character's knowledge, or deleted the first mention of a detail, add that to the next pass.",
        ],
        bullets: [
          "Choose one revision pass.",
          "Ask evidence-based questions.",
          "Verify the downstream effects before moving on.",
        ],
      },
    ],
  },
  {
    slug: "how-do-i-track-relationship-changes-between-drafts",
    question: "How do I track relationship changes between drafts?",
    description: "A practical answer for preserving emotional continuity after rewriting scenes.",
    publishedAt: "2026-06-12",
    publishedLabel: "June 12, 2026",
    readTime: "4 min read",
    articleSlug: "how-relationship-tracking-changes-a-character-rewrite",
    demoSlug: "pride-and-prejudice-relationship-map",
    intro:
      "Relationships can change silently between drafts. A scene cut for pacing may remove the only apology. A softened argument may make a later reconciliation feel oversized. Tracking the bond between characters helps you see those effects before readers feel them.",
    shortAnswer:
      "Track the relationship as its own record: current status, scenes that changed it, unresolved tension, and later payoffs that depend on earlier movement. Recheck that record after major rewrites.",
    quickSteps: [
      "List the scenes that changed trust, attraction, rivalry, or loyalty.",
      "Compare the old emotional path with the new chapter order.",
      "Verify that later payoff scenes still have enough setup.",
    ],
    whyItMatters:
      "Emotional continuity is one of the first things readers notice when a rewrite removes the bridge between two beats.",
    sections: [
      {
        heading: "Track the turn, not only the characters",
        body: [
          "A character profile can tell you who someone is. A relationship record tells you what has happened between two people. During revision, that distinction matters because the bond may change even when both profiles stay mostly the same.",
          "For each important pair, note the scenes that shifted trust, fear, respect, attraction, debt, or resentment.",
        ],
      },
      {
        heading: "Audit payoff scenes after cuts",
        body: [
          "After deleting or moving scenes, check the moments where the relationship pays off. Does the apology still feel earned? Does the betrayal still hurt for the right reason? Does the alliance still make sense at that point in the book?",
          "If the answer is uncertain, the relationship tracker gives you the right area to repair instead of sending you through the whole manuscript.",
        ],
        bullets: [
          "First tension",
          "Turning point",
          "Payoff scene",
        ],
      },
    ],
  },
  {
    slug: "how-can-i-find-dropped-plot-threads-before-beta-readers",
    question: "How can I find dropped plot threads before beta readers?",
    description: "A focused workflow for finding setups that no longer receive payoffs.",
    publishedAt: "2026-06-12",
    publishedLabel: "June 12, 2026",
    readTime: "4 min read",
    articleSlug: "why-chapter-grounded-answers-matter-for-fiction-revision",
    intro:
      "Dropped plot threads are embarrassing because they often began as good ideas. The draft promised something, the revision moved on, and the thread stayed behind like a door the reader expects to open.",
    shortAnswer:
      "Build a list of setups, promises, mysteries, objects, relationship tensions, and world rules, then check whether each one has a payoff, an intentional deferral, or a clean removal before beta readers see the draft.",
    quickSteps: [
      "Collect visible promises from early and middle chapters.",
      "Mark each thread as paid off, deferred, revised, or removed.",
      "Ask grounded questions about any setup you cannot place.",
    ],
    whyItMatters:
      "Beta readers can tell you a thread disappeared, but it is better to catch obvious dropped promises before they spend attention on them.",
    sections: [
      {
        heading: "Look for promises, not just subplots",
        body: [
          "A plot thread can be a mystery, a vow, a suspicious object, a political rule, a romantic obstacle, or a repeated image that begins to feel meaningful. If the reader is likely to expect a return, it belongs on the thread list.",
          "LoreVia can help surface these patterns because the system is already reading characters, scenes, and recurring story material together.",
        ],
      },
      {
        heading: "Decide what each thread deserves",
        body: [
          "Not every thread needs a large payoff. Some need one sentence of closure. Some should be removed because the book no longer uses them. Others should be deliberately carried into the next book.",
          "The important step is making the decision visible. A thread that is intentionally deferred feels different from one the author forgot.",
        ],
        bullets: [
          "Pay off in this draft.",
          "Clarify as background texture.",
          "Remove the setup if it no longer serves the book.",
        ],
      },
    ],
  },
  {
    slug: "what-should-go-in-a-beta-reader-packet",
    question: "What should go in a beta reader packet?",
    description: "A concise checklist for preparing reader instructions, feedback questions, and manuscript context.",
    publishedAt: "2026-06-12",
    publishedLabel: "June 12, 2026",
    readTime: "4 min read",
    articleSlug: "how-to-prepare-beta-reader-packets-with-lorevia",
    intro:
      "A beta reader packet should make the reader's job easier without telling them what to think. It gives the practical details, the feedback priorities, and the boundaries around the draft while leaving the reading experience intact.",
    shortAnswer:
      "Include the manuscript, deadline, format instructions, content notes if needed, a short cast or context note, and a small set of focused feedback questions. Keep the packet short enough that readers actually use it.",
    quickSteps: [
      "State what kind of feedback you want this round.",
      "Give practical reading instructions and deadline expectations.",
      "Include five to eight questions tied to your current revision concerns.",
    ],
    whyItMatters:
      "A clear packet gets better feedback because readers know where to put their attention and how to respond.",
    sections: [
      {
        heading: "Separate context from persuasion",
        body: [
          "Context helps the reader understand the assignment. Persuasion tries to explain why the book works before they have reacted to it. Keep the packet on the context side.",
          "A short list of major names, draft status, and feedback priorities is usually enough. If a reader needs a long explanation to understand a plot turn, the manuscript probably needs the explanation on the page.",
        ],
      },
      {
        heading: "Ask questions you can act on",
        body: [
          "Avoid questions that invite vague approval. Ask where the reader felt confused, which relationship beat felt too sudden, whether the villain's plan seemed fair, or what they expected after a specific reveal.",
          "Those answers are easier to turn into revision work than a general note that the reader liked or disliked the draft.",
        ],
        bullets: [
          "Confusion points",
          "Pacing shifts",
          "Character motivation",
          "Ending payoff",
        ],
      },
    ],
  },
  {
    slug: "how-do-i-use-continuity-tracking-across-a-series",
    question: "How do I use continuity tracking across a series?",
    description: "A practical answer for keeping canon consistent across multiple books.",
    publishedAt: "2026-06-12",
    publishedLabel: "June 12, 2026",
    readTime: "4 min read",
    articleSlug: "how-to-keep-a-series-bible-alive",
    intro:
      "Series continuity is harder than single-book continuity because old decisions keep creating new obligations. A scar, promise, treaty, family secret, or magic rule may matter again long after the original scene was drafted.",
    shortAnswer:
      "Track recurring facts by source, affected characters, and future dependencies. Before drafting or releasing a new book, audit the facts that cross book boundaries and update the series bible with the final version.",
    quickSteps: [
      "Record where each important canon fact first appeared.",
      "Mark which future scenes or books depend on it.",
      "Audit recurring characters and world rules before release.",
    ],
    whyItMatters:
      "Readers remember series canon, and contradictions can weaken trust in the entire story world.",
    sections: [
      {
        heading: "Track facts that travel",
        body: [
          "Not every detail needs series-level attention. Focus on facts that travel from one book to another: relationships, injuries, laws, powers, locations, family history, open promises, and political changes.",
          "Those facts should have source references so the author can verify what the published story actually established.",
        ],
      },
      {
        heading: "Review before planning and before release",
        body: [
          "Use the continuity record before drafting the next book, then again before release. The first pass helps with planning. The second catches contradictions introduced during revision.",
          "That habit keeps the bible alive because it is attached to real manuscript moments rather than maintained as a separate archive.",
        ],
        bullets: [
          "Returning character status",
          "Open promises from earlier books",
          "World rules that limit the new plot",
        ],
      },
    ],
  },
  {
    slug: "what-belongs-in-a-series-bible",
    question: "What belongs in a series bible?",
    description: "A focused list of canon records that help authors maintain multi-book continuity.",
    publishedAt: "2026-06-12",
    publishedLabel: "June 12, 2026",
    readTime: "4 min read",
    articleSlug: "how-to-keep-a-series-bible-alive",
    demoSlug: "pride-and-prejudice-relationship-map",
    intro:
      "A series bible should not become a warehouse for every detail you have ever invented. It should hold the facts that future books may depend on and the evidence that proves those facts are canon.",
    shortAnswer:
      "Include recurring characters, aliases, relationship history, timeline anchors, world rules, locations, objects, unresolved promises, and book-by-book canon decisions. Tie important entries back to the chapter or book where they appeared.",
    quickSteps: [
      "Separate structural canon from decorative lore.",
      "Record source chapters for facts that affect future books.",
      "Update entries after the release draft, not only during planning.",
    ],
    whyItMatters:
      "A focused series bible reduces continuity errors without turning maintenance into a second manuscript.",
    sections: [
      {
        heading: "Store what creates obligations",
        body: [
          "The most important entries are facts that can create contradictions later. A character's age, injury, oath, secret knowledge, inherited object, or magical limit matters because later scenes may depend on it.",
          "Decorative lore can still be stored, but it should not crowd out the entries that protect the series from drift.",
        ],
      },
      {
        heading: "Keep book-level history visible",
        body: [
          "For each major entry, note which book established it and whether the fact changed later. That helps when a character's public role, private allegiance, or relationship status evolves across installments.",
          "A good series bible shows the shape of change, not only the final state.",
        ],
        bullets: [
          "Canon fact",
          "Source book and chapter",
          "Current status",
          "Future dependency",
        ],
      },
    ],
  },
  {
    slug: "how-do-i-turn-continuity-findings-into-edits",
    question: "How do I turn continuity findings into actual edits?",
    description: "A practical answer for moving from a continuity flag to a clear manuscript decision.",
    publishedAt: "2026-06-12",
    publishedLabel: "June 12, 2026",
    readTime: "4 min read",
    articleSlug: "how-to-use-lorevia-during-a-revision-week",
    intro:
      "A continuity finding is only useful if it changes the manuscript. Authors can lose time collecting flags without deciding what each one means for the page. The better workflow is to translate every finding into a small editorial choice.",
    shortAnswer:
      "For each finding, decide whether to keep, clarify, move, rewrite, or remove the conflicting material. Then make the smallest edit that restores the story logic without over-explaining the problem to the reader.",
    quickSteps: [
      "Open the chapter evidence behind the finding.",
      "Name the actual conflict in one sentence.",
      "Choose the edit type before rewriting prose.",
    ],
    whyItMatters:
      "Continuity review should reduce revision noise. A finding that never becomes a decision is just another note competing for attention.",
    sections: [
      {
        heading: "Separate the flag from the fix",
        body: [
          "A flag tells you that something may be wrong. It does not automatically tell you the right repair. If a character knows a secret too early, the fix could be moving the reveal, changing the dialogue, adding a missing scene, or deciding the early knowledge is intentional.",
          "That is why the first step is to restate the problem plainly. Once you know what the contradiction actually is, the edit gets smaller and less emotional.",
        ],
      },
      {
        heading: "Use the lightest edit that restores trust",
        body: [
          "Not every continuity issue needs a new scene. Sometimes a line of clarification is enough. Sometimes the cleanest fix is deleting a stray detail that no longer belongs to this draft.",
          "LoreVia helps by pointing back to the evidence, but the author still chooses the level of intervention. The best fix is the one that makes the story coherent without making the repair visible.",
        ],
        bullets: [
          "Clarify a line when the setup exists but is easy to miss.",
          "Move a reveal when reader knowledge arrives too early.",
          "Remove a detail when the draft no longer uses it.",
        ],
      },
    ],
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

export function getAllPublicContentEntries(): PublicContentEntry[] {
  const latestPublishedAt = getLatestContentPublishedAt()

  return [
    ...CONTENT_HUB_ROUTES.map((path) => ({
      path,
      publishedAt: latestPublishedAt,
      type: "hub" as const,
    })),
    ...blogArticles.map((article) => ({
      path: `/blog/${article.slug}`,
      publishedAt: article.publishedAt,
      type: "blog" as const,
    })),
    ...answerPages.map((answer) => ({
      path: `/answers/${answer.slug}`,
      publishedAt: answer.publishedAt,
      type: "answer" as const,
    })),
    ...demoPages.map((demo) => ({
      path: `/demo/${demo.slug}`,
      publishedAt: demo.publishedAt,
      type: "demo" as const,
    })),
  ]
}

export function getLatestContentPublishedAt(): string {
  return [...blogArticles, ...answerPages, ...demoPages]
    .map((entry) => entry.publishedAt)
    .sort((left, right) => right.localeCompare(left))[0]
}

function countWords(value: string): number {
  return value
    .trim()
    .split(/\s+/)
    .filter(Boolean).length
}

function countSectionWords(sections: ContentSection[]): number {
  return sections.reduce((total, section) => {
    const bodyWords = section.body.reduce((bodyTotal, paragraph) => bodyTotal + countWords(paragraph), 0)
    const bulletWords = (section.bullets ?? []).reduce((bulletTotal, bullet) => bulletTotal + countWords(bullet), 0)
    const highlightWords = section.highlight ? countWords(section.highlight) : 0

    return total + countWords(section.heading) + bodyWords + bulletWords + highlightWords
  }, 0)
}

export function getContentWordCount(entry: BlogArticle | AnswerPage | DemoPage): number {
  if ("question" in entry) {
    return (
      countWords(entry.question) +
      countWords(entry.description) +
      countWords(entry.intro) +
      countWords(entry.shortAnswer) +
      countWords(entry.whyItMatters) +
      entry.quickSteps.reduce((total, step) => total + countWords(step), 0) +
      countSectionWords(entry.sections)
    )
  }

  if ("sourceWork" in entry) {
    return (
      countWords(entry.title) +
      countWords(entry.description) +
      countWords(entry.intro) +
      countWords(entry.featuredInsight) +
      countSectionWords(entry.sections)
    )
  }

  return (
    countWords(entry.title) +
    countWords(entry.description) +
    countWords(entry.intro) +
    entry.highlights.reduce((total, highlight) => total + countWords(highlight), 0) +
    countSectionWords(entry.sections)
  )
}
