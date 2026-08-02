// @vitest-environment jsdom

import { act, type ReactElement, type ReactNode } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, expect, vi } from "vitest"

const useQueryMock = vi.hoisted(() => vi.fn())
const routerMock = vi.hoisted(() => ({ push: vi.fn(), replace: vi.fn(), refresh: vi.fn() }))
const booksApiMock = vi.hoisted(() => ({
  acceptDuplicateSuggestion: vi.fn(),
  acceptRelationshipCandidate: vi.fn(),
  applyCharacterReprocess: vi.fn(),
  approveCharacter: vi.fn(),
  attachCharacterCandidate: vi.fn(),
  attachRelationshipCandidateA: vi.fn(),
  attachRelationshipCandidateB: vi.fn(),
  createCharacter: vi.fn(),
  createRelationship: vi.fn(),
  deleteCharacter: vi.fn(),
  demoteCharacter: vi.fn(),
  dismissDuplicateSuggestion: vi.fn(),
  exportCharacterBible: vi.fn(),
  exportCharacterCard: vi.fn(),
  getCharacterIdentityDiagnostics: vi.fn(),
  getCharacterReview: vi.fn(),
  getCharacters: vi.fn(),
  markCharacterCandidatePlace: vi.fn(),
  mergeCharacters: vi.fn(),
  partitionCharacter: vi.fn(),
  previewCharacterReprocess: vi.fn(),
  promoteCharacterCandidate: vi.fn(),
  rejectCharacter: vi.fn(),
  rejectCharacterCandidate: vi.fn(),
  rejectRelationshipCandidate: vi.fn(),
  repairRelationships: vi.fn(),
  resolveRelationshipCandidate: vi.fn(),
  shareCharacter: vi.fn(),
  undoCharacterIdentityAction: vi.fn(),
  updateCharacter: vi.fn(),
  updateCharacterCandidate: vi.fn(),
  updateCharacterGraphVisibility: vi.fn(),
  updateCharacterRelationshipCandidate: vi.fn(),
  updateCharacterReviewNote: vi.fn(),
}))
const readerApiMock = vi.hoisted(() => ({
  getChapterList: vi.fn(),
  getProgress: vi.fn(),
  getRelationships: vi.fn(),
  search: vi.fn(),
}))
const promptMock = vi.hoisted(() => vi.fn())

vi.mock("@tanstack/react-query", () => ({ useQuery: useQueryMock }))
vi.mock("next/dynamic", () => ({
  default: () => function MockRelationshipGraph() {
    return <div>Relationship graph rendered</div>
  },
}))
vi.mock("next/link", () => ({
  default: ({ children, href, ...props }: { children: ReactNode; href: string }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}))
vi.mock("next/navigation", () => ({
  useParams: () => ({ bookId: "book-1" }),
  useRouter: () => routerMock,
}))
vi.mock("@/lib/api/books", () => ({ booksApi: booksApiMock }))
vi.mock("@/lib/api/reader", () => ({ readerApi: readerApiMock }))
vi.mock("@/lib/hooks/useBookDetail", () => ({ useBookDetail: () => ({ data: bookFixture, isLoading: false }) }))
vi.mock("@/lib/query/cacheKeys", () => ({
  asQueryKey: (value: unknown) => value,
  bookCacheKey: (...parts: string[]) => parts.join(":"),
  readerCacheKey: (...parts: string[]) => parts.join(":"),
}))
vi.mock("@/lib/stores/preferencesStore", () => ({
  usePreferencesStore: (selector?: (state: { theme: string }) => unknown) => {
    const state = { theme: "light" }
    return selector ? selector(state) : state
  },
}))
vi.mock("@/lib/utils/notes", () => ({ saveContextualVaultNote: vi.fn().mockResolvedValue({}) }))
vi.mock("@/components/ui/ConfirmDialog", () => ({ useConfirmDialog: () => vi.fn().mockResolvedValue(true) }))
vi.mock("@/components/ui/PromptDialog", () => ({ usePromptDialog: () => promptMock }))
vi.mock("@/components/reader/CharacterEvidencePanel", () => ({
  CharacterEvidencePanel: ({ evidence, results }: { evidence?: unknown[]; results?: unknown[] }) => (
    <div>Evidence panel {(results ?? evidence ?? []).length}</div>
  ),
}))
vi.mock("@/components/reader/CharacterProfileRightRail", () => ({
  CharacterProfileRightRail: ({ character, activeTab, onTabChange }: { character: { name?: string } | null; activeTab: string; onTabChange: (tab: string) => void }) => (
    <aside>
      <p>Right rail {character?.name}</p>
      <button type="button" onClick={() => onTabChange(activeTab === "insights" ? "relationships" : "insights")}>Switch rail tab</button>
    </aside>
  ),
}))
vi.mock("@/components/reader/CharacterProfileTabs", () => ({
  CharacterProfileTabs: (props: { active?: string; activeTab?: string; onChange?: (tab: string) => void; onTabChange?: (tab: string) => void; onSelect?: (tab: string) => void }) => {
    const active = props.active ?? props.activeTab ?? "overview"
    const change = props.onSelect ?? props.onTabChange ?? props.onChange ?? (() => {})
    return (
      <nav>
        <button type="button" aria-pressed={active === "overview"} onClick={() => change("overview")}>Overview tab</button>
        <button type="button" aria-pressed={active === "relationships"} onClick={() => change("relationships")}>Relationships tab</button>
        <button type="button" aria-pressed={active === "arc"} onClick={() => change("arc")}>Arc tab</button>
      </nav>
    )
  },
}))
vi.mock("@/components/reader/CharacterWorkspaceHeader", () => ({
  CharacterWorkspaceHeader: ({
    actions,
    bookTitle,
    characterCount,
    stats,
  }: {
    actions?: ReactNode
    bookTitle?: string
    characterCount?: number
    stats?: ReactNode
  }) => (
    <header>
      <h1>Character workspace</h1>
      <p>{bookTitle} / {characterCount} characters</p>
      <div>{stats}</div>
      <div>{actions}</div>
    </header>
  ),
}))
vi.mock("@/components/reader/CharacterWorkspaceSidebarHeader", () => ({
  CharacterWorkspaceSidebarHeader: ({ title }: { title?: string }) => <div>Sidebar {title}</div>,
}))

import CharactersPage from "@/app/(reader)/[bookId]/characters/page"

let root: Root | null = null
let container: HTMLDivElement | null = null

const bookFixture = {
  id: "book-1",
  title: "Gate Draft",
  author: "Mira Vale",
  mode: "author",
  workspace_shell: "author",
  total_chapters: 12,
  progress_pct: 75,
  status: "ready",
}

const charactersFixture = [
  {
    id: "char-1",
    book_id: "book-1",
    name: "Mira",
    aliases: ["The Gatekeeper"],
    alias_records: [{ alias: "Gatekeeper", alias_kind: "epithet", confidence: 0.9, chapter_number: 2 }],
    role: "mc",
    first_chapter: 1,
    last_seen_chapter: 9,
    mention_count: 48,
    status: "alive",
    trait_state: {
      age: { value: "twenty-nine", confidence: 0.95, type: "objective" },
      distinguishing: { value: "silver key scar", confidence: 0.9, type: "objective" },
    },
    hair: "black",
    eyes: "gray",
    build: "lean",
    age_descriptor: "twenty-nine",
    distinguishing: "silver key scar",
    description: "Mira guards the ash gate and doubts the council.",
    personality_tags: ["guarded", "precise"],
    motivations: ["protect the gate"],
    fears: ["losing the city"],
    archetype: "guardian",
    arc_type: "truth",
    arc_summary: "Learns to trust Joren with the gate law.",
    goal: "seal the unstable gate",
    lie_they_believe: "trust invites betrayal",
    backstory_wound: "the first gate collapse",
    growth_events: [{ chapter_number: 5, event_title: "Trusts Joren", event: "lets him carry the key" }],
    relationship_summaries: ["Uneasy alliance with Joren."],
    arc_tracker: {
      goal: "seal the gate",
      lie_they_believe: "trust invites betrayal",
      wound_backstory: "gate collapse",
      arc_type: "positive",
      diagnostics: ["trust changes too abruptly"],
      voice_markers: ["measured commands"],
      relationship_changes: [{ counterpart_id: "char-2", chapter_number: 5, type: "ally", to_chapter: null, sentiment: 0.6, description: "Mira trusts Joren." }],
    },
    analysis_metadata: { user_curated: true },
    is_manual: false,
    tags: ["featured"],
    graph_visibility_override: null,
  },
  {
    id: "char-2",
    book_id: "book-1",
    name: "Joren",
    aliases: [],
    role: "sc",
    first_chapter: 2,
    last_seen_chapter: 8,
    mention_count: 28,
    status: "alive",
    trait_state: {},
    description: "Joren studies gate law.",
    personality_tags: ["curious"],
    motivations: ["prove the gate theory"],
    fears: [],
    archetype: null,
    arc_summary: null,
    growth_events: [],
    relationship_summaries: [],
    analysis_metadata: {},
    is_manual: false,
    tags: [],
    graph_visibility_override: "include",
  },
]

const reviewFixture = {
  candidates: [
    {
      id: "candidate-1",
      raw_name: "The Council",
      proposed_name: "Council",
      aliases: ["High Council"],
      cluster_names: ["Council"],
      status: "pending",
      adjudication_status: "needs_review",
      reason_codes: ["title_or_role"],
      confidence: 0.72,
      chapter_number: 4,
      evidence_count: 3,
    },
  ],
  duplicate_suggestions: [
    {
      id: "dup-1",
      primary_character_id: "char-1",
      secondary_character_id: "char-2",
      confidence: 82,
      reasons: ["shared gate scenes"],
      shared_cluster_keys: ["gate"],
      shared_chapters: [4, 5],
      embedding_similarity: 0.81,
      primary_is_protected: false,
      secondary_is_protected: false,
      primary_is_curated: true,
      secondary_is_curated: false,
      auto_dismissed: false,
      status: "pending",
    },
  ],
  relationship_candidates: [
    {
      id: "rel-candidate-1",
      raw_character_a: "Mira",
      raw_character_b: "Joren",
      rel_type: "ally",
      description: "They protect the gate together.",
      status: "pending",
      reason_codes: ["relationship_evidence"],
      confidence: 0.8,
      chapter_number: 5,
    },
  ],
  shadow_characters: [
    {
      id: "shadow-1",
      book_id: "book-1",
      name: "Ash Gate",
      aliases: [],
      role: "background",
      first_chapter: 1,
      last_seen_chapter: 8,
      mention_count: 12,
      is_manual: false,
      analysis_metadata: { hidden_reason: "place" },
    },
  ],
  decision_events: [{ id: "event-1", action: "promote", created_at: "2026-01-01T00:00:00Z" }],
  counts: {
    pending_candidates: 1,
    pending_duplicate_suggestions: 1,
    pending_relationship_candidates: 1,
  },
}

const graphFixture = {
  nodes: [
    { id: "char-1", name: "Mira", role: "mc" },
    { id: "char-2", name: "Joren", role: "sc" },
  ],
  edges: [
    { source: "char-1", target: "char-2", type: "ally", sentiment: 0.6, strength: 0.8, description: "Uneasy alliance", from_chapter: 5, to_chapter: null },
  ],
  hidden_nodes: [{
    id: "shadow-1",
    name: "Ash Gate",
    reason: "score_below_threshold",
    score: 0.2,
    visibility_score: 0.2,
    connected_relationship_count: 0,
    visibility_reasons: ["score_below_threshold", "profile_details"],
  }],
}

const progressFixture = { book_id: "book-1", current_chapter: 6, progress_pct: 50 }
const chapterListFixture = {
  chapters: [
    { number: 1, title: "The Gate Opens" },
    { number: 5, title: "The Key" },
  ],
}
const identityDiagnosticsFixture = {
  suppressed_count: 1,
  auto_merged_count: 2,
  auto_alias_count: 3,
  blocked_duplicate_count: 1,
  hidden_candidate_count: 4,
  suppression_reasons: { place: 2 },
  recent_identity_actions: [],
}
const repairPreviewFixture = {
  book_id: "book-1",
  dry_run: true,
  allow_merge_safe_pairs: true,
  allow_demote_obvious_noise: true,
  auto_merged: 1,
  auto_aliases: 1,
  auto_suppressed: 1,
  blocked_suggestions: 0,
  remaining_review_items: 2,
  planned_merges: [],
  planned_aliases: [],
  planned_demotions: [],
  planned_suppressions: [],
  blocked_duplicate_suggestions: [],
  skipped_protected_merge_pairs: [],
  skipped_protected_demotions: [],
  updated_first_chapters: {},
  updated_last_seen_chapters: {},
  character_labels: { "char-1": "Mira", "char-2": "Joren" },
  pending_duplicate_suggestions: 1,
  pending_relationship_candidates: 1,
  pending_character_candidates_suppressed: 0,
  pending_character_candidates_kept: 1,
  pending_relationship_candidates_suppressed: 0,
  pending_relationship_candidates_kept: 1,
  protected_manual_records_skipped: 0,
  unresolved_relationship_deltas: {},
}

async function renderPage(element: ReactElement) {
  container = document.createElement("div")
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => {
    root?.render(element)
    await flush()
  })
}

export async function flush() {
  await Promise.resolve()
  await new Promise((resolve) => window.setTimeout(resolve, 0))
  await Promise.resolve()
}

export async function waitForText(expected: string) {
  for (let index = 0; index < 40; index += 1) {
    if ((container?.textContent ?? "").includes(expected)) return
    await act(flush)
  }
  throw new Error(`Missing text: ${expected}\n${container?.textContent ?? ""}`)
}

export async function click(label: string, index = 0) {
  const matches = Array.from(container?.querySelectorAll("button") ?? []).filter((button) =>
    button.textContent?.includes(label) || button.getAttribute("aria-label") === label
  )
  const match = matches[index]
  if (!match) throw new Error(`Missing button: ${label}`)
  await act(async () => {
    match.dispatchEvent(new MouseEvent("click", { bubbles: true }))
    await flush()
  })
}

export function setFieldValue(field: HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement, value: string) {
  const prototype =
    field instanceof HTMLTextAreaElement
      ? HTMLTextAreaElement.prototype
      : field instanceof HTMLSelectElement
        ? HTMLSelectElement.prototype
        : HTMLInputElement.prototype
  Object.getOwnPropertyDescriptor(prototype, "value")?.set?.call(field, value)
  field.dispatchEvent(new Event(field instanceof HTMLSelectElement ? "change" : "input", { bubbles: true }))
}

export function firstField<T extends HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>(selector: string, index = 0) {
  const field = Array.from(container?.querySelectorAll(selector) ?? [])[index]
  if (!field) throw new Error(`Missing field: ${selector}\n${container?.textContent ?? ""}`)
  return field as T
}

beforeEach(() => {
  window.requestIdleCallback = ((callback: IdleRequestCallback) => {
    window.setTimeout(() => callback({ didTimeout: false, timeRemaining: () => 50 } as IdleDeadline), 0)
    return 1
  }) as typeof window.requestIdleCallback
  window.cancelIdleCallback = vi.fn()
  Object.values(booksApiMock).forEach((mock) => mock.mockReset())
  Object.values(readerApiMock).forEach((mock) => mock.mockReset())
  promptMock.mockReset()
  promptMock.mockResolvedValue("Mira\nAsh Mira")
  Object.defineProperty(navigator, "clipboard", {
    configurable: true,
    value: { writeText: vi.fn().mockResolvedValue(undefined) },
  })
  Object.defineProperty(URL, "createObjectURL", {
    configurable: true,
    value: vi.fn(() => "blob:character"),
  })
  Object.defineProperty(URL, "revokeObjectURL", {
    configurable: true,
    value: vi.fn(),
  })
  HTMLAnchorElement.prototype.click = vi.fn()
  booksApiMock.acceptDuplicateSuggestion.mockResolvedValue({ merged: "char-1" })
  booksApiMock.applyCharacterReprocess.mockResolvedValue({})
  booksApiMock.approveCharacter.mockResolvedValue({})
  booksApiMock.attachCharacterCandidate.mockResolvedValue({})
  booksApiMock.createCharacter.mockResolvedValue({ ...charactersFixture[1], id: "char-3", name: "Lina", role: "background" })
  booksApiMock.createRelationship.mockResolvedValue({})
  booksApiMock.deleteCharacter.mockResolvedValue({})
  booksApiMock.demoteCharacter.mockResolvedValue({ candidate_id: "candidate-demoted-1" })
  booksApiMock.dismissDuplicateSuggestion.mockResolvedValue({})
  booksApiMock.exportCharacterBible.mockResolvedValue(new Blob(["bible"], { type: "text/markdown" }))
  booksApiMock.exportCharacterCard.mockResolvedValue(new Blob(["card"], { type: "application/pdf" }))
  booksApiMock.getCharacters.mockResolvedValue(charactersFixture)
  booksApiMock.getCharacterReview.mockResolvedValue(reviewFixture)
  booksApiMock.getCharacterIdentityDiagnostics.mockResolvedValue(identityDiagnosticsFixture)
  booksApiMock.markCharacterCandidatePlace.mockResolvedValue({})
  booksApiMock.mergeCharacters.mockResolvedValue({ merged: "char-1" })
  booksApiMock.partitionCharacter.mockResolvedValue({ created: ["char-3"] })
  booksApiMock.previewCharacterReprocess.mockResolvedValue(repairPreviewFixture)
  booksApiMock.promoteCharacterCandidate.mockResolvedValue({ promoted: "char-1" })
  booksApiMock.rejectCharacter.mockResolvedValue({})
  booksApiMock.rejectCharacterCandidate.mockResolvedValue({})
  booksApiMock.repairRelationships.mockResolvedValue({
    pairs_repaired: 1,
    relationships_deleted: 0,
    relationships_remaining: 2,
    relationship_candidates_updated: 1,
  })
  booksApiMock.resolveRelationshipCandidate.mockResolvedValue({})
  booksApiMock.shareCharacter.mockResolvedValue({ share_url: "/public/characters/mira" })
  booksApiMock.undoCharacterIdentityAction.mockResolvedValue({})
  booksApiMock.updateCharacter.mockImplementation((_bookId, _characterId, payload) =>
    Promise.resolve({ ...charactersFixture[0], ...payload, id: "char-1", name: payload.name ?? "Mira" }),
  )
  booksApiMock.updateCharacterReviewNote.mockResolvedValue({})
  readerApiMock.getProgress.mockResolvedValue(progressFixture)
  readerApiMock.getChapterList.mockResolvedValue(chapterListFixture)
  readerApiMock.getRelationships.mockResolvedValue(graphFixture)
  readerApiMock.search.mockResolvedValue([
    { chapter_num: 5, chapter_title: "The Key", excerpt: "Mira gives Joren the key.", summary: "Mira gives Joren the key.", text: "Mira gives Joren the key.", score: 0.9 },
  ])
  useQueryMock.mockImplementation(({ queryKey, enabled }: { queryKey: string; enabled?: boolean }) => {
    const withRefetch = (data: unknown, extra: Record<string, unknown> = {}) => ({
      data,
      refetch: vi.fn().mockResolvedValue({ data }),
      isLoading: false,
      isFetching: false,
      ...extra,
    })
    if (queryKey === "book-1:progress") return withRefetch(progressFixture)
    if (queryKey === "book-1:chapters") return withRefetch(chapterListFixture)
    if (queryKey === "book-1:characters") return withRefetch(charactersFixture)
    if (queryKey === "book-1:character-review") return withRefetch(enabled === false ? reviewFixture : reviewFixture)
    if (String(queryKey).includes("character-identity-diagnostics")) return withRefetch(identityDiagnosticsFixture)
    if (String(queryKey).includes("character-review:reprocess")) return withRefetch(repairPreviewFixture)
    return withRefetch(null)
  })
})

afterEach(() => {
  if (root) {
    act(() => {
      root?.unmount()
    })
  }
  container?.remove()
  root = null
  container = null
  document.body.innerHTML = ""
  vi.clearAllMocks()
})

export async function renderCharactersPage() {
  await renderPage(<CharactersPage />)
}

export function getCharactersPageContainer() {
  return container
}

export { booksApiMock, readerApiMock }
