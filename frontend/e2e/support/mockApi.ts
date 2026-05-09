import type { Page, Route } from "@playwright/test"

type SessionMode = "authenticated" | "guest"
type LoginMode = "success" | "unauthorized"

type MockOptions = {
  session?: SessionMode
  login?: LoginMode
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
    "Nora crossed the ember gate with ash on her sleeves. The city bells rang beyond the bridge.",
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
  processing: book.processing,
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

  await page.route("**/api/v1/**", async (route) => {
    const url = new URL(route.request().url())
    const path = url.pathname
      .replace("/api/v1/books/sky-of-ash--book-1", "/api/v1/books/book-1")
      .replace("/api/v1/reader/sky-of-ash--book-1", "/api/v1/reader/book-1")
      .replace("/api/v1/intelligence/sky-of-ash--book-1", "/api/v1/intelligence/book-1")
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

    if (path === "/api/v1/books" && method === "GET") {
      return json(route, [book])
    }

    if (path === "/api/v1/books/book-1" && method === "GET") {
      return json(route, book)
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
      return json(route, writerWorkspace)
    }

    if (path === "/api/v1/books/book-1/emotional-arc" && method === "GET") {
      return json(route, emotionalArc)
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

    if (path === "/api/v1/reader/book-1/chapter/2" && method === "GET") {
      return json(route, chapter)
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
