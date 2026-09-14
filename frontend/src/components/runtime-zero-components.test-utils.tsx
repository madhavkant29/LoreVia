// @vitest-environment jsdom

import { act, type ReactElement, type ReactNode } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, vi } from "vitest"

const booksApiMock = vi.hoisted(() => ({
  createCharacter: vi.fn(),
  deleteCharacter: vi.fn(),
  exportCharacterCard: vi.fn(),
  shareCharacter: vi.fn(),
  updateCharacter: vi.fn(),
}))
const readerApiMock = vi.hoisted(() => ({
  getRecall: vi.fn(),
  saveQuote: vi.fn(),
}))
const intelligenceApiMock = vi.hoisted(() => ({
  whatsTheWordStream: vi.fn(),
}))
const socialApiMock = vi.hoisted(() => ({
  listConversations: vi.fn(),
  listConversationsPage: vi.fn(),
  listMessages: vi.fn(),
  listMessagesPage: vi.fn(),
  listRelationships: vi.fn(),
  markConversationRead: vi.fn(),
  openDirectConversation: vi.fn(),
  searchUsers: vi.fn(),
  sendFriendRequest: vi.fn(),
  sendMessage: vi.fn(),
}))
const confirmMock = vi.hoisted(() => vi.fn())
const emitChatsChangedMock = vi.hoisted(() => vi.fn())
const queryClientMock = vi.hoisted(() => ({
  fetchQuery: vi.fn(),
  getQueryData: vi.fn(),
  invalidateQueries: vi.fn(),
}))
const searchParamsMock = vi.hoisted(() => new URLSearchParams())
const authStateMock = vi.hoisted(() => ({ hydrated: true, user: { id: "user-1", tier: "architect" } }))
const preferencesStateMock = vi.hoisted(() => ({ theme: "dark" }))

vi.mock("next/link", () => ({
  default: ({ children, href, onClick, ...props }: { children: ReactNode; href: string; onClick?: () => void }) => (
    <a href={href} onClick={onClick} {...props}>{children}</a>
  ),
}))
vi.mock("next/navigation", () => ({
  useParams: () => ({ bookId: "book-1" }),
  useSearchParams: () => searchParamsMock,
}))
vi.mock("@tanstack/react-query", () => ({ useQueryClient: () => queryClientMock }))
vi.mock("@/components/ui/ConfirmDialog", () => ({ useConfirmDialog: () => confirmMock }))
vi.mock("@/components/ui/Skeleton", () => ({ Skeleton: ({ className = "" }: { className?: string }) => <div className={className}>Loading row</div> }))
vi.mock("@/lib/api/books", () => ({ booksApi: booksApiMock }))
vi.mock("@/lib/api/intelligence", () => ({ intelligenceApi: intelligenceApiMock }))
vi.mock("@/lib/api/reader", () => ({ readerApi: readerApiMock }))
vi.mock("@/lib/api/social", () => ({ socialApi: socialApiMock }))
vi.mock("@/lib/hooks/useChatUnreadCount", () => ({ emitChatsChanged: emitChatsChangedMock }))
vi.mock("@/lib/stores/authStore", () => ({
  useAuthStore: (selector?: (state: { user: { id: string; tier: string } | null; hydrated: boolean }) => unknown) => {
    return typeof selector === "function" ? selector(authStateMock) : authStateMock
  },
}))
vi.mock("@/lib/stores/preferencesStore", () => ({
  usePreferencesStore: () => preferencesStateMock,
}))
vi.mock("@/lib/query/sidebarPrefetch", () => ({
  SOCIAL_CONVERSATIONS_QUERY_KEY: ["social", "conversations"],
  SOCIAL_RELATIONSHIPS_QUERY_KEY: ["social", "relationships"],
}))


let root: Root | null = null
let container: HTMLDivElement | null = null

const characterFixture = {
  id: "char-1",
  name: "Mara Vale",
  role: "keeper",
  status: "alive",
  aliases: ["The Lantern"],
  description: "Mara guards the lantern gate and tracks every broken lock.",
  arc_summary: "She moves from secrecy to trust.",
  archetype: "guardian",
  first_chapter: 1,
  last_seen_chapter: 9,
  mention_count: 44,
  personality_tags: ["patient", "watchful", "ruthless", "loyal"],
  motivations: ["protect the city"],
  fears: ["losing the lantern"],
  relationship_summaries: ["Mara distrusts Theo but protects him."],
  trait_state: {
    hair: { value: "silver", confidence: 0.94 },
    eyes: { value: "green", confidence: 0.9 },
    oath: { value: "never abandon the gate", confidence: 0.92 },
  },
  growth_events: [
    {
      chapter_number: 8,
      event_title: "Mara reveals the oath",
      description: "She chooses honesty.",
      impact_score: 8,
      growth_direction: "positive",
      growth_magnitude: 7,
      is_major: true,
      accomplishments: ["saves Theo"],
    },
  ],
}

const conversationFixture = {
  id: "conversation-1",
  other_user: {
    id: "user-2",
    username: "theo",
    display_name: "Theo",
    messaging_permission: "friends_only",
  },
  last_message_preview: "Can you read chapter two?",
  unread_count: 2,
}

async function renderElement(element: ReactElement) {
  container = document.createElement("div")
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => {
    root?.render(element)
    await flush()
  })
}

function unmountCurrentRoot() {
  if (root) {
    act(() => {
      root?.unmount()
    })
  }
  container?.remove()
  root = null
  container = null
}

async function flush() {
  await Promise.resolve()
  await new Promise((resolve) => window.setTimeout(resolve, 0))
  await Promise.resolve()
}

function text() {
  return container?.textContent ?? ""
}

function button(label: string, index = 0) {
  const matches = Array.from(container?.querySelectorAll("button") ?? []).filter((item) => item.textContent?.includes(label))
  const target = matches[index]
  if (!target) throw new Error(`Missing button: ${label}\n${text()}`)
  return target
}

async function click(label: string, index = 0) {
  await act(async () => {
    button(label, index).dispatchEvent(new MouseEvent("click", { bubbles: true }))
    await flush()
  })
}

async function clickText(label: string, selector = "*", index = 0) {
  const matches = Array.from(container?.querySelectorAll(selector) ?? []).filter((item) => item.textContent?.includes(label))
  const target = matches[index]
  if (!target) throw new Error(`Missing text target: ${label}\n${text()}`)
  await act(async () => {
    target.dispatchEvent(new MouseEvent("click", { bubbles: true }))
    await flush()
  })
}

function setFieldValue(field: HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement, value: string) {
  const prototype =
    field instanceof HTMLTextAreaElement
      ? HTMLTextAreaElement.prototype
      : field instanceof HTMLSelectElement
        ? HTMLSelectElement.prototype
        : HTMLInputElement.prototype
  Object.getOwnPropertyDescriptor(prototype, "value")?.set?.call(field, value)
  field.dispatchEvent(new Event(field instanceof HTMLSelectElement ? "change" : "input", { bubbles: true }))
}

function firstField<T extends HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>(selector: string) {
  const field = container?.querySelector(selector)
  if (!field) throw new Error(`Missing field: ${selector}\n${text()}`)
  return field as T
}

beforeEach(() => {
  Object.values(booksApiMock).forEach((mock) => mock.mockReset())
  Object.values(intelligenceApiMock).forEach((mock) => mock.mockReset())
  Object.values(readerApiMock).forEach((mock) => mock.mockReset())
  Object.values(socialApiMock).forEach((mock) => mock.mockReset())
  queryClientMock.fetchQuery.mockReset()
  queryClientMock.getQueryData.mockReset()
  queryClientMock.invalidateQueries.mockReset()
  confirmMock.mockReset()
  emitChatsChangedMock.mockReset()
  searchParamsMock.delete("username")

  booksApiMock.createCharacter.mockResolvedValue({ ...characterFixture, id: "char-new", name: "Mara Vale", role: "sc" })
  booksApiMock.updateCharacter.mockResolvedValue({ ...characterFixture, name: "Mara Bright" })
  booksApiMock.shareCharacter.mockResolvedValue({ share_url: "/share/mara" })
  booksApiMock.exportCharacterCard.mockResolvedValue(new Blob(["card"], { type: "application/pdf" }))
  booksApiMock.deleteCharacter.mockResolvedValue({})
  readerApiMock.getRecall.mockResolvedValue({ recall: "Mara last appeared at the gate with Theo." })
  readerApiMock.saveQuote.mockResolvedValue({})
  intelligenceApiMock.whatsTheWordStream.mockImplementation(async (_bookId, _description, _previousWord, options) => {
    options?.onStage?.("Scanning diction...")
    return { word: "smirk", gloss: "A smile with concealed contempt." }
  })
  confirmMock.mockResolvedValue(true)

  socialApiMock.listConversationsPage.mockResolvedValue({
    items: [conversationFixture],
    next_cursor: null,
    has_more: false,
  })
  socialApiMock.listMessagesPage.mockResolvedValue({
    items: [
      {
        id: "message-1",
        conversation_id: "conversation-1",
        sender_user_id: "user-2",
        recipient_user_id: "user-1",
        body: "Can you read chapter two?",
        created_at: "2026-01-01T00:00:00Z",
        recipient_read_at: null,
      },
    ],
    next_cursor: null,
    has_more: false,
  })
  socialApiMock.listRelationships.mockResolvedValue({
    incoming_requests: [{ id: "rel-1", requester_username: "lina" }],
    outgoing_requests: [],
    friends: [],
  })
  socialApiMock.searchUsers.mockResolvedValue({
    items: [
      {
        id: "user-3",
        username: "lina",
        display_name: "Lina",
        messaging_permission: "friends_only",
        friend_state: "none",
        can_message: false,
      },
    ],
  })
  socialApiMock.openDirectConversation.mockResolvedValue({ items: [{ ...conversationFixture, id: "conversation-2" }] })
  socialApiMock.sendFriendRequest.mockResolvedValue({})
  socialApiMock.sendMessage.mockResolvedValue({
    id: "message-2",
    conversation_id: "conversation-1",
    sender_user_id: "user-1",
    recipient_user_id: "user-2",
    body: "I can read it tonight.",
    created_at: "2026-01-01T00:01:00Z",
    recipient_read_at: null,
  })
  socialApiMock.markConversationRead.mockResolvedValue({})
  queryClientMock.getQueryData.mockReturnValue(null)
  queryClientMock.fetchQuery.mockImplementation(({ queryFn }: { queryFn: () => Promise<unknown> }) => queryFn())
  window.setInterval = vi.fn(() => 1) as unknown as typeof window.setInterval
  window.clearInterval = vi.fn() as unknown as typeof window.clearInterval

  Object.defineProperty(navigator, "clipboard", {
    configurable: true,
    value: { writeText: vi.fn().mockResolvedValue(undefined) },
  })
  URL.createObjectURL = vi.fn(() => "blob:character")
  URL.revokeObjectURL = vi.fn()
  HTMLAnchorElement.prototype.click = vi.fn()
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
})


function getContainer() {
  return container
}

export {
  booksApiMock,
  button,
  characterFixture,
  click,
  clickText,
  confirmMock,
  firstField,
  flush,
  getContainer,
  intelligenceApiMock,
  queryClientMock,
  readerApiMock,
  renderElement,
  searchParamsMock,
  setFieldValue,
  socialApiMock,
  text,
  unmountCurrentRoot,
}
