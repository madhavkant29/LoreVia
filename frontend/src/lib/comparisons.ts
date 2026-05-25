export type HomeComparisonRow = {
  feature: string
  scrivener: string
  campfire: string
  googleDocs: string
  lorevia: string
}

export type CompetitorComparisonRow = {
  feature: string
  competitor: string
  lorevia: string
}

export type CompetitorPage = {
  slug: "sudowrite" | "novelcrafter" | "campfire" | "scrivener"
  competitorName: string
  title: string
  description: string
  heroSummary: string
  competitorBestFor: string
  loreviaBestFor: string
  differentiators: Array<{
    title: string
    body: string
  }>
  chooseLoreVia: string[]
  chooseCompetitor: string[]
  rows: CompetitorComparisonRow[]
}

export const homepageComparisonRows: HomeComparisonRow[] = [
  {
    feature: "Manuscript writing/editing",
    scrivener: "Yes",
    campfire: "Yes",
    googleDocs: "Yes",
    lorevia: "Yes",
  },
  {
    feature: "Chapter/scene organization",
    scrivener: "Yes",
    campfire: "Yes",
    googleDocs: "Limited",
    lorevia: "Yes",
  },
  {
    feature: "Compile/export for publishing",
    scrivener: "Yes",
    campfire: "Limited",
    googleDocs: "Basic",
    lorevia: "Yes",
  },
  {
    feature: "Character database",
    scrivener: "Manual",
    campfire: "Manual",
    googleDocs: "No",
    lorevia: "Automatic + editable",
  },
  {
    feature: "Relationship tracking",
    scrivener: "Manual",
    campfire: "Manual",
    googleDocs: "No",
    lorevia: "Automatic + editable",
  },
  {
    feature: "AI story understanding",
    scrivener: "No",
    campfire: "Limited",
    googleDocs: "No",
    lorevia: "Yes",
  },
  {
    feature: "Automatic continuity scans",
    scrivener: "No",
    campfire: "No",
    googleDocs: "No",
    lorevia: "Yes",
  },
  {
    feature: "Chapter-grounded answers",
    scrivener: "No",
    campfire: "No",
    googleDocs: "No",
    lorevia: "Yes",
  },
  {
    feature: "Multi-book continuity analysis",
    scrivener: "Manual",
    campfire: "Limited",
    googleDocs: "No",
    lorevia: "Higher tiers",
  },
]

export const comparisonIndexCards = [
  {
    slug: "scrivener",
    name: "Scrivener",
    summary: "Drafting-first software compared with LoreVia's continuity-aware manuscript workspace.",
  },
  {
    slug: "campfire",
    name: "Campfire",
    summary: "Manual worldbuilding databases compared with LoreVia's manuscript-generated story memory.",
  },
  {
    slug: "novelcrafter",
    name: "Novelcrafter",
    summary: "An AI writing cockpit compared with LoreVia's continuity-first revision workflow.",
  },
  {
    slug: "sudowrite",
    name: "Sudowrite",
    summary: "A prose-generation tool compared with LoreVia's manuscript management and audit focus.",
  },
] as const

export const competitorPages: CompetitorPage[] = [
  {
    slug: "scrivener",
    competitorName: "Scrivener",
    title: "LoreVia vs Scrivener",
    description:
      "Compare LoreVia and Scrivener for manuscript writing, continuity review, story memory, and revision support.",
    heroSummary:
      "Scrivener is excellent for drafting, structuring, and compiling manuscripts. LoreVia adds automatic story memory, continuity scans, grounded manuscript answers, and revision workflows built around the draft itself.",
    competitorBestFor:
      "Authors who want a mature drafting tool with strong project organization and compile options.",
    loreviaBestFor:
      "Authors who want to write in one place and also keep continuity, characters, threads, and revision memory connected to the manuscript.",
    differentiators: [
      {
        title: "Draft-first versus manuscript-aware",
        body:
          "Scrivener is a flexible drafting environment. LoreVia is a drafting and revision workspace that also interprets what the manuscript is doing so authors can audit continuity without building every reference surface by hand.",
      },
      {
        title: "Manual records versus editable extraction",
        body:
          "Scrivener can store notes, research, and snapshots well. LoreVia focuses on turning the written draft into editable character, relationship, timeline, and thread records that stay tied to chapters.",
      },
      {
        title: "Revision support",
        body:
          "LoreVia is designed for the stage where a large manuscript needs memory, grounded answers, and continuity checks, not just a place to keep documents organized.",
      },
    ],
    chooseLoreVia: [
      "You want automatic continuity review alongside writing and revision.",
      "You want chapter-grounded answers instead of searching scattered notes.",
      "You want character, relationship, and timeline memory generated from the draft and still editable.",
      "You are working on a manuscript that is becoming hard to hold in memory.",
    ],
    chooseCompetitor: [
      "You mainly want a mature drafting environment and compile workflow.",
      "You are comfortable managing story memory manually.",
      "Offline project structure matters more to you than built-in manuscript intelligence.",
    ],
    rows: [
      { feature: "Manuscript writing/editing", competitor: "Yes", lorevia: "Yes" },
      { feature: "Chapter/scene organization", competitor: "Yes", lorevia: "Yes" },
      { feature: "Compile/export", competitor: "Yes", lorevia: "Yes" },
      { feature: "Version / snapshot history", competitor: "Yes", lorevia: "Yes" },
      { feature: "Character database", competitor: "Manual", lorevia: "Automatic + editable" },
      { feature: "Relationship tracking", competitor: "Manual", lorevia: "Automatic + editable" },
      { feature: "Timeline / story memory", competitor: "Manual", lorevia: "Automatic + editable" },
      { feature: "Continuity scans", competitor: "Manual", lorevia: "Automatic" },
      { feature: "Chapter-grounded Q&A", competitor: "No", lorevia: "Yes" },
      { feature: "Dropped plot thread detection", competitor: "Manual", lorevia: "Yes" },
      { feature: "AI story understanding", competitor: "No", lorevia: "Yes" },
      { feature: "Multi-book continuity", competitor: "Manual", lorevia: "Higher tiers" },
    ],
  },
  {
    slug: "campfire",
    competitorName: "Campfire",
    title: "LoreVia vs Campfire",
    description:
      "Compare LoreVia and Campfire for worldbuilding, manuscript writing, continuity review, and editable story memory.",
    heroSummary:
      "Campfire is strong for manual worldbuilding and planning systems. LoreVia is stronger when the manuscript itself should generate editable character, relationship, thread, and continuity intelligence.",
    competitorBestFor:
      "Authors who want dedicated worldbuilding databases, lore organization, and manual planning surfaces.",
    loreviaBestFor:
      "Authors who want the manuscript to drive story memory, continuity work, grounded answers, and revision support.",
    differentiators: [
      {
        title: "Planning-first versus draft-first",
        body:
          "Campfire shines when you want to design your world and manage lore manually. LoreVia starts from the manuscript and works backward into editable memory, which is especially useful once a draft already exists.",
      },
      {
        title: "Manual upkeep versus assisted upkeep",
        body:
          "Campfire gives authors rich places to store information. LoreVia focuses on reducing the manual upkeep by extracting and organizing story information from the written work itself.",
      },
      {
        title: "Continuity as a workflow",
        body:
          "LoreVia treats continuity review, thread tracking, and grounded questions as core revision workflows rather than optional side notes.",
      },
    ],
    chooseLoreVia: [
      "You want editable extracted data from the manuscript instead of a fully manual database.",
      "You want grounded Q&A, continuity scans, and plot-thread visibility in the same workspace.",
      "You want to revise complex drafts without rebuilding your story memory from scratch.",
    ],
    chooseCompetitor: [
      "You mainly want manual worldbuilding and lore design tools.",
      "You prefer planning systems that are separate from the draft.",
      "You are comfortable maintaining databases by hand.",
    ],
    rows: [
      { feature: "Manuscript editor", competitor: "Yes", lorevia: "Yes" },
      { feature: "Character database", competitor: "Manual", lorevia: "Automatic + editable" },
      { feature: "Relationship tracking", competitor: "Manual", lorevia: "Automatic + editable" },
      { feature: "Timeline tools", competitor: "Manual", lorevia: "Automatic + editable" },
      { feature: "Worldbuilding workspace", competitor: "Yes", lorevia: "Yes" },
      { feature: "Editable extracted data", competitor: "No", lorevia: "Yes" },
      { feature: "Version control / draft history", competitor: "Limited", lorevia: "Yes" },
      { feature: "AI continuity scans", competitor: "No", lorevia: "Yes" },
      { feature: "Dropped plot thread detection", competitor: "Manual", lorevia: "Yes" },
      { feature: "Chapter-grounded Q&A", competitor: "No", lorevia: "Yes" },
    ],
  },
  {
    slug: "novelcrafter",
    competitorName: "Novelcrafter",
    title: "LoreVia vs Novelcrafter",
    description:
      "Compare LoreVia and Novelcrafter for manuscript editing, continuity-first writing workflows, and story memory built from the draft.",
    heroSummary:
      "Novelcrafter is a capable AI writing cockpit. LoreVia is better suited for authors who want continuity, spoiler-aware story memory, grounded answers, and revision support built directly into the writing workspace.",
    competitorBestFor:
      "Authors who want a flexible AI-assisted writing environment with strong cockpit-style workflows.",
    loreviaBestFor:
      "Authors who want a continuity-first workspace that writes, revises, tracks, and audits the manuscript in one place.",
    differentiators: [
      {
        title: "AI cockpit versus continuity-first workspace",
        body:
          "Novelcrafter is strong when the author wants a broad AI writing cockpit. LoreVia is organized around keeping the manuscript coherent across revisions, scenes, characters, and plot threads.",
      },
      {
        title: "Reader and author surfaces",
        body:
          "LoreVia pairs author tooling with spoiler-aware reading and collaboration flows, which makes it useful when the manuscript needs both revision control and guided outside feedback.",
      },
      {
        title: "Editable story memory",
        body:
          "LoreVia emphasizes extracted story memory that authors can review and correct, keeping the draft and the reference layer synchronized.",
      },
    ],
    chooseLoreVia: [
      "You want continuity review to be a core workflow, not an afterthought.",
      "You want spoiler-aware reader mode and author collaboration around the same manuscript.",
      "You want grounded answers, editable extraction, and story memory attached to chapters and scenes.",
    ],
    chooseCompetitor: [
      "You want a more cockpit-like AI writing environment.",
      "You care more about broad AI workflow flexibility than continuity-first revision tooling.",
    ],
    rows: [
      { feature: "Manuscript editor", competitor: "Yes", lorevia: "Yes" },
      { feature: "Chapter/scene organization", competitor: "Yes", lorevia: "Yes" },
      { feature: "Compile/export", competitor: "Yes", lorevia: "Yes" },
      { feature: "Story bible / codex", competitor: "Yes", lorevia: "Yes" },
      { feature: "Automatic extraction", competitor: "Limited", lorevia: "Yes" },
      { feature: "Editable extracted data", competitor: "Limited", lorevia: "Yes" },
      { feature: "Version control", competitor: "Limited", lorevia: "Yes" },
      { feature: "Continuity review as core workflow", competitor: "Limited", lorevia: "Yes" },
      { feature: "Spoiler-safe reader mode", competitor: "No", lorevia: "Yes" },
      { feature: "Reader + author modes", competitor: "No", lorevia: "Yes" },
      { feature: "Multi-book continuity", competitor: "Limited", lorevia: "Higher tiers" },
    ],
  },
  {
    slug: "sudowrite",
    competitorName: "Sudowrite",
    title: "LoreVia vs Sudowrite",
    description:
      "Compare LoreVia and Sudowrite for prose generation, manuscript organization, continuity review, and grounded story memory.",
    heroSummary:
      "Sudowrite is stronger for AI-assisted prose generation. LoreVia is stronger for managing, revising, organizing, and auditing complex manuscripts once continuity and story memory start to matter.",
    competitorBestFor:
      "Authors who mainly want AI support for generating, expanding, or rewriting prose.",
    loreviaBestFor:
      "Authors who want a manuscript workspace for drafting, revision, continuity, grounded answers, and spoiler-aware story memory.",
    differentiators: [
      {
        title: "Generation versus management",
        body:
          "Sudowrite is well suited to ideation and prose assistance. LoreVia is built around helping authors manage the structure, history, and continuity of a manuscript that already has many moving parts.",
      },
      {
        title: "Revision intelligence",
        body:
          "LoreVia focuses on questions authors ask late in the process: what changed, who knows what, which details drifted, and where a thread went missing.",
      },
      {
        title: "Story memory grounded in the draft",
        body:
          "LoreVia's differentiator is not replacing the author with generated prose. It is keeping the existing story legible while the book grows and changes.",
      },
    ],
    chooseLoreVia: [
      "You want a serious manuscript workspace rather than a generation-first interface.",
      "You need continuity scans, plot-thread visibility, and grounded answers from your own draft.",
      "You want spoiler-safe reading and structured story memory alongside writing and revision.",
    ],
    chooseCompetitor: [
      "You mainly want AI help generating, expanding, or rewriting prose.",
      "You care more about ideation assistance than continuity, structure, and manuscript audit tooling.",
    ],
    rows: [
      { feature: "AI prose generation", competitor: "Strong", lorevia: "Not core" },
      { feature: "Rewrite / expand / describe", competitor: "Strong", lorevia: "Limited" },
      { feature: "Manuscript editor", competitor: "Limited", lorevia: "Yes" },
      { feature: "Chapter/scene organization", competitor: "Limited", lorevia: "Yes" },
      { feature: "Story bible", competitor: "Limited", lorevia: "Yes" },
      { feature: "Version control", competitor: "No", lorevia: "Yes" },
      { feature: "Compile/export", competitor: "Limited", lorevia: "Yes" },
      { feature: "Continuity scan", competitor: "No", lorevia: "Yes" },
      { feature: "Plot thread detection", competitor: "No", lorevia: "Yes" },
      { feature: "Grounded manuscript Q&A", competitor: "No", lorevia: "Yes" },
      { feature: "Spoiler-safe story memory", competitor: "No", lorevia: "Yes" },
    ],
  },
]

export function getCompetitorPage(slug: string) {
  return competitorPages.find((page) => page.slug === slug)
}
