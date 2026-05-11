import type { Page, Route } from "@playwright/test"

type SessionMode = "authenticated" | "guest"
type LoginMode = "success" | "unauthorized"

type MockOptions = {
  session?: SessionMode
  login?: LoginMode
}

function normalizeMockApiPath(pathname: string) {
  return pathname
    .replace(/^\/api\/v1\/books\/[^/]+--([^/]+)(?=\/|$)/, "/api/v1/books/$1")
    .replace(/^\/api\/v1\/reader\/[^/]+--([^/]+)(?=\/|$)/, "/api/v1/reader/$1")
    .replace(/^\/api\/v1\/intelligence\/[^/]+--([^/]+)(?=\/|$)/, "/api/v1/intelligence/$1")
}

const user = {
  id: "user-1",
  email: "author@getlorevia.com",
  username: "author",
  tier: "author",
  plan_tier: "author",
  tier_label: "Author",
  trial_active: false,
  trial_ends_at: null,
  reading_mode: "analyst",
  daily_word_goal: 1200,
  today_word_count: 450,
  last_login_at: "2026-05-08T10:00:00Z",
  login_streak_days: 7,
  longest_login_streak_days: 12,
  login_activity_dates: ["2026-05-05", "2026-05-06", "2026-05-07", "2026-05-08"],
  email_verified: true,
  created_at: "2026-04-01T09:00:00Z",
}

const book = {
  id: "book-1",
  title: "Sky of Ash",
  author: "M. Vale",
  genre: "Epic Fantasy",
  format: "docx",
  work_type: "novel",
  status: "ready",
  mode: "author",
  source_kind: "upload",
  preserve_chapter_numbers: true,
  cover_url: null,
  total_chapters: 3,
  total_tokens: 42000,
  total_words: 31500,
  is_truncated: false,
  primary_series_id: null,
  series_name: "Ash Cycle",
  series_order: 1,
  is_public: false,
  public_description: null,
  copyright_warning: false,
  archived_at: null,
  hidden_at: null,
  created_at: "2026-05-07T12:00:00Z",
  progress_pct: 64,
  chapters_read_count: 2,
  chapters_left: 1,
  marked_complete_in_series: false,
  processing: {
    status: "ready",
    stage: "ready",
    progress_pct: 100,
    chapters_completed: 3,
    chapters_total: 3,
    eta_seconds: 0,
    last_chapter_number: 2,
    last_chapter_title: "The Ember Gate",
    started_at: "2026-05-07T12:00:00Z",
    updated_at: "2026-05-08T11:45:00Z",
    last_error: null,
  },
}

const chapterList = {
  read_upto: 2,
  current_chapter: 2,
  chapters: [
    { number: 1, title: "Ashfall", processed: true, intelligence_available: true, read: true },
    { number: 2, title: "The Ember Gate", processed: true, intelligence_available: true, read: true },
    { number: 3, title: "River of Glass", processed: false, intelligence_available: false, read: false },
  ],
}

const chapter = {
  chapter_number: 2,
  chapter_title: "The Ember Gate",
  total_chapters: 3,
  intelligence_available: true,
  text_url: null,
  text_content:
    [
      "Nora crossed the ember gate with ash on her sleeves. The city bells rang beyond the bridge.",
      "The courier behind her whispered that the old road remembered every footstep.",
      "* * *",
      "Morning came with a hard white sun and the smell of metal in the rain.",
      "RADIO: All westbound gates remain closed until the ashfall advisory is lifted.",
      "> CITY BULLETIN\n> Curfew begins at ninth bell. Keep identification papers ready.",
    ].join("\n\n"),
  html_content:
    "<p>Nora crossed the ember gate with ash on her sleeves.</p><p>The city bells rang beyond the bridge.</p>",
  media: [],
  characters: [
    {
      id: "char-1",
      name: "Nora Vale",
      aliases: ["Nora"],
      role: "mc",
      first_chapter: 1,
      description: "A determined courier.",
      personality_tags: ["determined", "curious"],
    },
  ],
}

const chaptersByNumber = {
  1: {
    chapter_number: 1,
    chapter_title: "Ashfall",
    total_chapters: 3,
    intelligence_available: true,
    text_url: null,
    text_content:
      "Nora leaves the outer district with a sealed message and no time to second-guess the mission.",
    html_content:
      "<p>Nora leaves the outer district with a sealed message and no time to second-guess the mission.</p>",
    media: [],
    characters: chapter.characters,
  },
  2: chapter,
  3: {
    chapter_number: 3,
    chapter_title: "River of Glass",
    total_chapters: 3,
    intelligence_available: false,
    text_url: null,
    text_content: "",
    html_content: "<p></p>",
    media: [],
    characters: chapter.characters,
  },
} as const

const storyHealth = {
  score: 82,
  status: "Stable",
  summary: "Character arcs and plot continuity are holding together in the current draft.",
  metrics: [
    { label: "Characters", score: 88 },
    { label: "World Coherence", score: 80 },
    { label: "Plot Consistency", score: 79 },
    { label: "Pacing", score: 76 },
  ],
}

const writerWorkspace = {
  word_count_goals: {
    chapter_target: 2500,
    book_target: 90000,
    session_target: 800,
  },
  goal_calendar: [],
  corkboard_cards: [],
  templates: [
    {
      id: "template-1",
      kind: "scene",
      title: "Scene Starter",
      description: "A quick outline for a new scene.",
      content: "Goal:\nConflict:\nTurn:",
    },
  ],
  publishing: {
    active_preset: "standard_manuscript",
    trim_size: "6x9",
    include_title_page: true,
    mirror_margins: false,
  },
  manuscript_front_matter: {
    author_name: "M. Vale",
    pen_name: "",
    contact_email: "author@getlorevia.com",
    contact_phone: "",
    contact_address: "",
    title: "Sky of Ash",
    subtitle: "",
    header_last_name: "Vale",
    header_title: "Sky of Ash",
    approximate_word_count_override: null,
    dedication: "",
    acknowledgments: "",
    epigraph: "",
    prologue: "",
    include_dedication: false,
    include_acknowledgments: false,
    include_epigraph: false,
    include_prologue: false,
  },
  revision_board: {
    items: [],
    last_generated_at: null,
  },
  processing: book.processing,
}

const revisionIntelligence = {
  tagline: "Know what your edit breaks before your readers do.",
  summary: {
    hero_message: "2 downstream logic risks need attention first.",
    active_item_count: 5,
    high_severity_count: 2,
    task_ready_count: 5,
  },
  change_impacts: [
    {
      id: "rev-impact-1",
      category: "impact",
      title: "Chapter 2 assumption may break later payoff",
      description: "Chapter 3 still assumes Nora and Kael already understand the silver gate blood rule.",
      severity: "high",
      chapter_ref: 2,
      source_label: "The Ember Gate",
      recommendation: "Restore the setup or revise the later dialogue so the reveal still tracks.",
      status: "pending",
      assigned_version_id: null,
      task_id: null,
    },
  ],
  genre_checks: [
    {
      genre: "epic fantasy",
      label: "Fantasy",
      checks: ["magic system consistency", "faction politics", "invented terms", "worldbuilding contradictions"],
      rationale: "LoreVia is weighting revision checks toward the story promises and failure modes that usually matter most in fantasy manuscripts.",
    },
  ],
  revision_plan: [
    {
      title: "Pass 1: Fix story logic",
      summary: "Resolve the items most likely to create downstream contradictions or broken assumptions.",
      items: [
        {
          id: "rev-impact-1",
          category: "impact",
          title: "Chapter 2 assumption may break later payoff",
          description: "Chapter 3 still assumes Nora and Kael already understand the silver gate blood rule.",
          severity: "high",
          chapter_ref: 2,
          status: "pending",
          assigned_version_id: null,
          task_id: null,
        },
      ],
    },
  ],
  knowledge_matrix: [
    {
      fact: "Silver gate blood rule",
      chapter_ref: 2,
      entries: [
        { character_name: "Nora", chapter_learned: 2, source: "Tracked through the silver gate thread" },
        { character_name: "Kael", chapter_learned: 2, source: "Tracked through the silver gate thread" },
        { character_name: "Mira", chapter_learned: null, source: "No earlier evidence surfaced yet" },
      ],
      warning: "LoreVia has no clear evidence yet that Mira learned this before later story beats could depend on it.",
    },
  ],
  scene_advice: [
    {
      id: "rev-scene-1",
      category: "scene",
      title: "Scenes in Chapters 2 and 3 may be doing duplicate work",
      description: "Both scenes repeat the gate warning and delay the same reveal beat.",
      severity: "medium",
      chapter_ref: 3,
      status: "pending",
      assigned_version_id: null,
      task_id: null,
    },
  ],
  confusion_map: [
    {
      id: "rev-confusion-1",
      category: "confusion",
      title: "Reader confusion risk in Chapter 1",
      description: "4 named characters arrive here; 3 lore terms appear here.",
      severity: "medium",
      chapter_ref: 1,
      status: "pending",
      assigned_version_id: null,
      task_id: null,
    },
  ],
  voice_alerts: [
    {
      id: "rev-voice-1",
      category: "voice",
      title: "Nora's voice drifts in Chapter 3",
      description: "The dialogue turns unusually formal and exposition-heavy for Nora's baseline.",
      severity: "medium",
      chapter_ref: 3,
      status: "pending",
      assigned_version_id: null,
      task_id: null,
    },
  ],
}

const workspaceTree = {
  chapters: [
    { chapter_number: 1, title: "Ashfall", scene_count: 1 },
    { chapter_number: 2, title: "The Ember Gate", scene_count: 1 },
  ],
  scene_groups: [
    {
      id: "chapter-2",
      label: "Chapter 2",
      chapter_number: 2,
      collapsed_by_default: false,
      scenes: [
        {
          id: "scene-1",
          book_id: "book-1",
          chapter_id: null,
          chapter_number: 2,
          title: "Gate Crossing",
          description: "Nora reaches the city gate.",
          body: "Nora crosses into the city.",
          html_body: "<p>Nora crosses into the city.</p>",
          metadata: {},
          path: "Scenes/Chapter 2/Gate Crossing.md",
          status: "assigned",
          sort_order: 1,
          source: "manual",
          origin_chapter_number: 2,
          created_at: "2026-05-08T10:00:00Z",
          updated_at: "2026-05-08T10:10:00Z",
        },
      ],
    },
  ],
  note_paths: ["Notes/Chapter 2/Bridge notes.md"],
}

const preWritingCheck = {
  upcoming_chapter: 3,
  active_characters: [
    {
      character_id: "char-1",
      character_name: "Nora Vale",
      role: "mc",
      active_goal: "Reach the archive before dawn.",
    },
  ],
  unresolved_threads: [
    {
      id: "thread-1",
      title: "Who opened the gate?",
      status: "open",
      last_updated_chapter: 2,
      note: "Still unresolved after the bridge sequence.",
    },
  ],
  recent_events: [
    {
      chapter_number: 2,
      chapter_title: "The Ember Gate",
      summary: "Nora enters the city and hears the bells.",
    },
  ],
  alerts: [],
}

const emotionalArc = {
  focus_character_count: 1,
  latest_turning_points: ["Nora commits to reaching the archive."],
  characters: [
    {
      character_id: "char-1",
      character_name: "Nora Vale",
      role: "mc",
      arc_summary: "Nora is leaning into responsibility.",
      trajectory_score: 0.78,
      points: [
        {
          chapter_number: 1,
          label: "Departure",
          sentiment: 0.2,
          impact_score: 0.5,
          growth_direction: "up",
        },
      ],
    },
  ],
}

const synopsis = {
  spoiler_level: "minimal",
  synopsis:
    "Nora is carrying dangerous knowledge into the city while the political stakes around the ember gate continue rising.",
  focus_points: ["Nora's mission", "The ember gate", "Unresolved political tension"],
  coverage_chapters: [1, 2],
}

const notifications = {
  items: [],
  unread_count: 0,
}

const pointsBalance = {
  balance: 18,
}

const pointsLedger = [
  {
    id: "ledger-1",
    entry_type: "grant",
    source_type: "rewarded_ad",
    source_id: "ad-session-1",
    points_delta: 3,
    expires_at: null,
    metadata_json: {},
    created_at: "2026-05-08T13:00:00Z",
  },
  {
    id: "ledger-2",
    entry_type: "spend",
    source_type: "overflow_search",
    source_id: "spend-1",
    points_delta: -3,
    expires_at: null,
    metadata_json: {},
    created_at: "2026-05-08T14:00:00Z",
  },
]

const referralSummary = {
  referral_code: "LOREAUTHOR",
  referral_url: "https://getlorevia.com/register?ref=LOREAUTHOR",
  points_balance: 18,
  rewards: [],
}

const pointOffers = {
  offers: [
    {
      code: "search_pack_5",
      action: "search",
      title: "Search pack",
      description: "Add five same-day semantic searches.",
      points_cost: 3,
      units: 5,
      eligible: true,
      reason: null,
    },
  ],
}

const rewardedAdStatus = {
  enabled: true,
  provider: "google_publisher_tag",
  reward_points: 3,
  daily_cap: 3,
  claims_used_today: 1,
  claims_remaining_today: 2,
  session_ttl_seconds: 900,
  min_grant_seconds: 0,
  reason: null,
}

const notes = [
  {
    id: "note-1",
    book_id: "book-1",
    book_title: "Sky of Ash",
    chapter_number: 2,
    chapter_title: "The Ember Gate",
    title: "Gate imagery",
    body: "Revisit the bell motif.",
    created_at: "2026-05-08T10:00:00Z",
    updated_at: "2026-05-08T10:00:00Z",
  },
]

const collaborators = [
  {
    id: "collab-1",
    book_id: "book-1",
    email: "beta@example.com",
    display_name: "Beta Reader",
    role: "beta_reader",
    scope: {
      chapter_start: 1,
      chapter_end: 10,
      character_bible: true,
      continuity_report: true,
      reader_confusion_report: true,
    },
    invite_status: "active",
    invited_at: "2026-05-08T10:00:00Z",
    updated_at: "2026-05-08T10:00:00Z",
  },
]

function json(route: Route, body: unknown, status = 200) {
  return route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  })
}

function notFound(route: Route) {
  return json(route, { detail: "Not found" }, 404)
}

export async function installMockApi(page: Page, options: MockOptions = {}) {
  const session = options.session ?? "authenticated"
  const login = options.login ?? "success"
  let mockWriterWorkspace = JSON.parse(JSON.stringify(writerWorkspace))

  await page.route("**/api/v1/**", async (route) => {
    const url = new URL(route.request().url())
    const path = normalizeMockApiPath(url.pathname)
    const method = route.request().method()

    if (path === "/api/v1/auth/me" && method === "GET") {
      return session === "authenticated" ? json(route, user) : json(route, { detail: "Unauthorized" }, 401)
    }

    if (path === "/api/v1/auth/refresh" && method === "POST") {
      return session === "authenticated" ? json(route, user) : json(route, { detail: "Unauthorized" }, 401)
    }

    if (path === "/api/v1/auth/login" && method === "POST") {
      return login === "success" ? json(route, user) : json(route, { detail: "Invalid credentials" }, 401)
    }

    if (path === "/api/v1/auth/logout" && method === "POST") {
      return json(route, { ok: true })
    }

    if (path === "/api/v1/notifications" && method === "GET") {
      return json(route, notifications)
    }

    if (path === "/api/v1/monetization/points" && method === "GET") {
      return json(route, pointsBalance)
    }

    if (path === "/api/v1/monetization/points/ledger" && method === "GET") {
      return json(route, pointsLedger)
    }

    if (path === "/api/v1/monetization/referrals" && method === "GET") {
      return json(route, referralSummary)
    }

    if (path === "/api/v1/monetization/offers" && method === "GET") {
      return json(route, pointOffers)
    }

    if (path === "/api/v1/monetization/rewarded-ads/status" && method === "GET") {
      return json(route, rewardedAdStatus)
    }

    if (path === "/api/v1/books" && method === "GET") {
      return json(route, [book])
    }

    if (path === "/api/v1/books/book-1" && method === "GET") {
      return json(route, book)
    }

    if (path === "/api/v1/books/book-1/collaborators" && method === "GET") {
      return json(route, collaborators)
    }

    if (path === "/api/v1/books/book-1/collaborators" && method === "POST") {
      const payload = JSON.parse(route.request().postData() || "{}")
      return json(route, {
        id: "collab-2",
        book_id: "book-1",
        email: payload.email,
        display_name: payload.display_name,
        role: payload.role,
        scope: payload.scope,
        invite_status: "active",
        invited_at: "2026-05-11T10:00:00Z",
        updated_at: "2026-05-11T10:00:00Z",
      }, 201)
    }

    if (path === "/api/v1/books/book-1/characters" && method === "GET") {
      return json(route, chapter.characters)
    }

    if (path === "/api/v1/books/book-1/chapter-reports" && method === "GET") {
      return json(route, [])
    }

    if (path === "/api/v1/books/book-1/pre-writing-check" && method === "GET") {
      return json(route, preWritingCheck)
    }

    if (path === "/api/v1/books/book-1/story-health" && method === "GET") {
      return json(route, storyHealth)
    }

    if (path === "/api/v1/books/book-1/writer-workspace" && method === "GET") {
      return json(route, mockWriterWorkspace)
    }

    if (path === "/api/v1/books/book-1/writer-workspace" && method === "PUT") {
      const body = route.request().postDataJSON() as Record<string, unknown> | null
      mockWriterWorkspace = {
        ...mockWriterWorkspace,
        ...(body ?? {}),
      }
      return json(route, mockWriterWorkspace)
    }

    if (path === "/api/v1/books/book-1/emotional-arc" && method === "GET") {
      return json(route, emotionalArc)
    }

    if (path === "/api/v1/books/book-1/revision-intelligence" && method === "GET") {
      return json(route, revisionIntelligence)
    }

    if (path === "/api/v1/books/book-1/workspace/tree" && method === "GET") {
      return json(route, workspaceTree)
    }

    if (path === "/api/v1/books/book-1/chapter-versions" && method === "GET") {
      return json(route, [])
    }

    if (path === "/api/v1/books/book-1/notes" && method === "GET") {
      return json(route, notes)
    }

    if (path === "/api/v1/reader/book-1/progress" && method === "GET") {
      return json(route, {
        current_chapter: 2,
        scroll_pct: 35,
        chapters_read_count: 2,
        percent_complete: 64,
        chapters_left: 1,
      })
    }

    if (path === "/api/v1/reader/book-1/chapters" && method === "GET") {
      return json(route, chapterList)
    }

    const chapterMatch = path.match(/^\/api\/v1\/reader\/book-1\/chapter\/(\d+)$/)
    if (chapterMatch && method === "GET") {
      const chapterNumber = Number.parseInt(chapterMatch[1] ?? "", 10)
      const chapterData = chaptersByNumber[chapterNumber as keyof typeof chaptersByNumber]
      return chapterData ? json(route, chapterData) : notFound(route)
    }

    if (path === "/api/v1/reader/book-1/plot-threads" && method === "GET") {
      return json(route, [])
    }

    if (path === "/api/v1/intelligence/book-1/advisor/synopsis" && method === "GET") {
      return json(route, synopsis)
    }

    if (path === "/api/v1/intelligence/book-1/advisor/suggestions" && method === "GET") {
      return json(route, { suggestions: [], total: 0, book_title: book.title })
    }

    if (path.startsWith("/api/v1/")) {
      return notFound(route)
    }

    return route.continue()
  })
}
