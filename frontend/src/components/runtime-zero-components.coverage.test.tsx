// @vitest-environment jsdom

import { act, type ReactElement, type ReactNode } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

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
  listMessages: vi.fn(),
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

import { CharacterCard } from "@/components/characters/CharacterCard"
import { AddCharacterFromSelection } from "@/components/characters/AddCharacterFromSelection"
import { WhatsTheWordPanel } from "@/components/intelligence/WhatsTheWordPanel"
import { ChatsPanel } from "@/components/layout/ChatsPanel"
import { ContextPanel } from "@/components/reader/ContextPanel"

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

  socialApiMock.listConversations.mockResolvedValue({ items: [conversationFixture] })
  socialApiMock.listMessages.mockResolvedValue({
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

describe("zero-coverage runtime components", () => {
  it("drives context panel quote, character edit, recall, links, search, loading, empty, and drag paths", async () => {
    const onClose = vi.fn()
    await renderElement(
      <ContextPanel
        result={{ type: "character", character: characterFixture }}
        loading={false}
        onClose={onClose}
        mobileSheet
        theme="dark"
        selectedQuote="The lantern hummed when Mara lied."
        chapterNumber={3}
        chapterTitle="The Lock"
        characters={[{ name: "Mara Vale" }, { name: "Theo" }]}
      />
    )

    expect(text()).toContain("Mara Vale")
    setFieldValue(firstField<HTMLSelectElement>("select"), "Mara Vale")
    setFieldValue(firstField<HTMLTextAreaElement>('textarea[aria-label="Line bookmark note"]'), "Important lie.")
    await click("Save line bookmark")
    expect(readerApiMock.saveQuote).toHaveBeenCalledWith("book-1", expect.objectContaining({ character_name: "Mara Vale" }))

    await clickText("+1 more", "span")
    expect(text()).toContain("Show less")
    await click("Edit")
    setFieldValue(firstField<HTMLTextAreaElement>("textarea"), "Mara Bright")
    await click("Save Changes")
    expect(booksApiMock.updateCharacter).toHaveBeenCalledWith("book-1", "char-1", expect.objectContaining({ name: "Mara Vale" }))
    await click("Links")
    expect(text()).toContain("Relationship links")
    await click("Recall")
    expect(text()).toContain("Mara last appeared")

    root?.unmount()
    container?.remove()
    root = null
    container = null
    await renderElement(
      <ContextPanel
        result={{ type: "search", results: [{ chapter_num: 4, text: "Theo finds the spare key." }] }}
        loading={false}
        onClose={onClose}
        theme="light"
        selectedQuote={null}
        chapterNumber={4}
        chapterTitle={null}
        characters={[]}
      />
    )
    expect(text()).toContain("Theo finds the spare key")

    root?.unmount()
    container?.remove()
    root = null
    container = null
    await renderElement(
      <ContextPanel
        result={null}
        loading
        onClose={onClose}
        theme="light"
        selectedQuote={null}
        chapterNumber={1}
        chapterTitle={null}
        characters={[]}
      />
    )
    expect(text()).toContain("Loading character context")
  })

  it("expands character cards and exercises edit, share, export, delete, keyboard, and advanced paths", async () => {
    const onUpdated = vi.fn()
    const onDeleted = vi.fn()
    await renderElement(
      <CharacterCard
        character={characterFixture}
        bookId="book-1"
        editable
        onUpdated={onUpdated}
        onDeleted={onDeleted}
        theme="dark"
      />
    )

    const card = container?.querySelector('[role="button"]')
    if (!card) throw new Error("Missing character card")
    await act(async () => {
      card.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }))
      await flush()
    })
    expect(text()).toContain("Advanced details")
    await click("Edit")
    setFieldValue(firstField<HTMLInputElement>("input"), "Mara Bright")
    await click("Save edits")
    expect(onUpdated).toHaveBeenCalledWith(expect.objectContaining({ name: "Mara Bright" }))
    await click("Share")
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith(expect.stringContaining("/share/mara"))
    await click("Edit")
    await click("Export PDF")
    expect(URL.createObjectURL).toHaveBeenCalled()
    await click("Open")
    expect(text()).toContain("Archetype")
    await click("Delete")
    expect(confirmMock).toHaveBeenCalled()
    expect(onDeleted).toHaveBeenCalledWith("char-1")
  })

  it("creates characters from selected text and handles validation, cancel, and API errors", async () => {
    const onClose = vi.fn()
    const onCreated = vi.fn()
    await renderElement(
      <AddCharacterFromSelection
        bookId="book-1"
        selectedText={"  Mara   Vale  "}
        isDark
        firstChapter={4}
        open
        onClose={onClose}
        onCreated={onCreated}
      />
    )

    expect(text()).toContain("Add character from selection")
    expect(firstField<HTMLInputElement>("input").value).toBe("Mara Vale")
    setFieldValue(firstField<HTMLSelectElement>("select"), "sc")
    setFieldValue(firstField<HTMLTextAreaElement>("textarea"), "Gate keeper.")
    await click("Create character")
    expect(booksApiMock.createCharacter).toHaveBeenCalledWith("book-1", {
      name: "Mara Vale",
      firstChapter: 4,
      role: "sc",
      description: "Gate keeper.",
    })
    expect(onCreated).toHaveBeenCalledWith(expect.objectContaining({ id: "char-new" }))
    expect(onClose).toHaveBeenCalled()

    unmountCurrentRoot()
    onClose.mockClear()
    onCreated.mockClear()
    await renderElement(
      <AddCharacterFromSelection
        bookId="book-1"
        selectedText="Theo"
        isDark={false}
        open
        onClose={onClose}
        onCreated={onCreated}
      />
    )
    setFieldValue(firstField<HTMLInputElement>("input"), "")
    await act(async () => {
      firstField<HTMLInputElement>("input").dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }))
      await flush()
    })
    expect(text()).toContain("Character name is required.")

    setFieldValue(firstField<HTMLInputElement>("input"), "Theo")
    booksApiMock.createCharacter.mockRejectedValueOnce(new Error("duplicate"))
    await click("Create character")
    expect(text()).toContain("Could not create this character")

    await act(async () => {
      document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }))
      await flush()
    })
    expect(onClose).toHaveBeenCalled()

    unmountCurrentRoot()
    onClose.mockClear()
    await renderElement(
      <AddCharacterFromSelection
        bookId="book-1"
        selectedText="Lina"
        isDark={false}
        open
        onClose={onClose}
      />
    )
    await click("Cancel")
    expect(onClose).toHaveBeenCalled()

    unmountCurrentRoot()
    await renderElement(
      <AddCharacterFromSelection
        bookId="book-1"
        selectedText="Hidden"
        isDark={false}
        open={false}
        onClose={onClose}
      />
    )
    expect(text()).not.toContain("Hidden")
  })

  it("opens the word finder, requests suggestions, retries, and handles errors", async () => {
    await renderElement(<WhatsTheWordPanel bookId="book-1" isDark className="panel" />)

    expect(text()).toContain("What's the word")
    await click("What's the word")
    expect(text()).toContain("Word finder")
    expect(text()).toContain("0 /")
    expect((button("Find word") as HTMLButtonElement).disabled).toBe(true)

    setFieldValue(
      firstField<HTMLTextAreaElement>("textarea"),
      "a smile that hides contempt behind polished manners",
    )
    expect((button("Find word") as HTMLButtonElement).disabled).toBe(false)
    await click("Find word")
    expect(intelligenceApiMock.whatsTheWordStream).toHaveBeenCalledWith(
      "book-1",
      "a smile that hides contempt behind polished manners",
      null,
      expect.any(Object),
    )
    expect(text()).toContain("smirk")
    expect(text()).toContain("A smile with concealed contempt.")

    await click("Try again")
    expect(intelligenceApiMock.whatsTheWordStream).toHaveBeenLastCalledWith(
      "book-1",
      "a smile that hides contempt behind polished manners",
      "smirk",
      expect.any(Object),
    )

    intelligenceApiMock.whatsTheWordStream.mockRejectedValueOnce(new Error("provider down"))
    setFieldValue(firstField<HTMLTextAreaElement>("textarea"), "a voice that sounds bitter while staying calm")
    await click("Find word")
    expect(text()).toContain("Couldn't find the word right now")

    await click("Hide what's the word")
    expect(text()).not.toContain("Word finder")
  })

  it("renders chats, hydrates conversations, searches users, sends requests, and posts messages", async () => {
    searchParamsMock.set("username", "lina")
    await renderElement(<ChatsPanel mode="page" enabled />)

    expect(text()).toContain("Private chats")
    expect(text()).toContain("@theo")
    expect(socialApiMock.listConversations).toHaveBeenCalled()
    expect(socialApiMock.listMessages).toHaveBeenCalledWith("conversation-1")
    setFieldValue(firstField<HTMLTextAreaElement>('textarea[aria-label="Message"]'), "I can read it tonight.")
    await click("Send")
    expect(socialApiMock.sendMessage).toHaveBeenCalledWith("conversation-1", "I can read it tonight.")

    setFieldValue(firstField<HTMLInputElement>('input[aria-label="Search usernames"]'), "lina")
    await act(flush)
    expect(socialApiMock.searchUsers).toHaveBeenCalledWith("lina")

    root?.unmount()
    container?.remove()
    root = null
    container = null
    queryClientMock.getQueryData.mockImplementation((key: string[]) => key.includes("conversations") ? { items: [] } : null)
    socialApiMock.listConversations.mockResolvedValueOnce({ items: [] })
    await renderElement(<ChatsPanel mode="sidebar" enabled />)
    setFieldValue(firstField<HTMLInputElement>('input[aria-label="Search usernames"]'), "lina")
    await act(flush)
    await click("@lina")
    await click("Send friend request")
    expect(socialApiMock.sendFriendRequest).toHaveBeenCalledWith("user-3")
  })
})
