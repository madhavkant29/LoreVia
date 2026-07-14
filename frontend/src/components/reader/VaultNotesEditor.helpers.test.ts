// @vitest-environment jsdom

import { beforeEach, describe, expect, it, vi } from "vitest"

import {
  FAVORITES_STORAGE_KEY,
  FOLDERS_STORAGE_KEY_PREFIX,
  buildFolderTree,
  buildNoteMap,
  buildUniqueNotePath,
  countMarkdownHeadings,
  countWikiLinks,
  fileCharacterCount,
  fileWordCount,
  filterVaultNotes,
  getAvailableNotePaths,
  getDisplayedVaultNotes,
  getFavoriteVaultNotes,
  getSelectedNoteContent,
  getSelectedOutgoingLinks,
  getSelectedVaultNote,
  formatRelativeTime,
  inferNoteType,
  insertTextSnippet,
  loadCustomFolders,
  loadFavoriteMap,
  matchesReference,
  noteFolder,
  noteTitle,
  parseNotesDragItem,
  prefixSelectedTextLines,
  wrapSelectedText,
} from "./VaultNotesEditor.helpers"
import type { VaultNote } from "@/types/book"

const notes: VaultNote[] = [
  {
    id: "note-1",
    book_id: "book-1",
    path: "Characters/Mira.md",
    source: "user_notes",
    content: "# Mira\n\nMira trusts [[Plot Threads/Ash Gate]].",
    created_at: "2026-06-01T00:00:00Z",
    updated_at: "2026-06-15T00:00:00Z",
  },
  {
    id: "note-2",
    book_id: "book-1",
    path: "Characters/Mira 2.md",
    source: "user_notes",
    content: "Second note",
    created_at: "2026-06-02T00:00:00Z",
    updated_at: "2026-06-14T00:00:00Z",
  },
]

beforeEach(() => {
  const store = new Map<string, string>()
  Object.defineProperty(window, "localStorage", {
    configurable: true,
    value: {
      get length() {
        return store.size
      },
      clear: () => store.clear(),
      getItem: (key: string) => store.get(key) ?? null,
      key: (index: number) => Array.from(store.keys())[index] ?? null,
      removeItem: (key: string) => {
        store.delete(key)
      },
      setItem: (key: string, value: string) => {
        store.set(key, value)
      },
    } satisfies Storage,
  })
  vi.useRealTimers()
})

describe("VaultNotesEditor helpers", () => {
  it("normalizes note title, folder, references, and unique paths", () => {
    expect(noteTitle("Characters/Mira.md")).toBe("Mira")
    expect(noteFolder("Characters/Mira.md")).toBe("Characters")
    expect(matchesReference("Characters/Mira.md", "Mira")).toBe(true)
    expect(matchesReference("Characters/Mira.md", "Characters/Mira.md")).toBe(true)
    expect(matchesReference("Characters/Mira.md", "Ash Gate")).toBe(false)
    expect(buildUniqueNotePath(notes, "Characters", "Mira")).toBe("Characters/Mira 3.md")
  })

  it("counts note metrics without treating whitespace as content", () => {
    const content = "# Title\n\nTwo words [[Target]].\n\n## Section"

    expect(fileWordCount(content)).toBe(7)
    expect(fileWordCount("   ")).toBe(0)
    expect(fileCharacterCount("  text  ")).toBe(4)
    expect(countMarkdownHeadings(content)).toBe(2)
    expect(countWikiLinks(content)).toBe(1)
  })

  it("loads favorites and custom folders defensively from localStorage", () => {
    window.localStorage.setItem(FAVORITES_STORAGE_KEY, JSON.stringify({ "Characters/Mira.md": true }))
    window.localStorage.setItem(
      `${FOLDERS_STORAGE_KEY_PREFIX}book-1`,
      JSON.stringify([" Custom/Scenes ", "", "Worldbuilding"])
    )

    expect(loadFavoriteMap()).toEqual({ "Characters/Mira.md": true })
    expect(loadCustomFolders("book-1")).toEqual(["Custom/Scenes", "Worldbuilding"])

    window.localStorage.setItem(FAVORITES_STORAGE_KEY, "{")
    window.localStorage.setItem(`${FOLDERS_STORAGE_KEY_PREFIX}book-1`, "{")

    expect(loadFavoriteMap()).toEqual({})
    expect(loadCustomFolders("book-1")).toEqual([])
  })

  it("parses note drag payloads and rejects malformed drag data", () => {
    const validDataTransfer = {
      getData: () => JSON.stringify({ kind: "note", path: "Characters/Mira.md" }),
    } as unknown as DataTransfer
    const invalidDataTransfer = {
      getData: () => "{",
    } as unknown as DataTransfer

    expect(parseNotesDragItem({ dataTransfer: validDataTransfer })).toEqual({
      kind: "note",
      path: "Characters/Mira.md",
    })
    expect(parseNotesDragItem({ dataTransfer: invalidDataTransfer })).toBeNull()
    expect(parseNotesDragItem({ dataTransfer: null })).toBeNull()
  })

  it("formats relative time and note type summaries", () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date("2026-06-15T12:00:00Z"))

    expect(formatRelativeTime("2026-06-15T11:45:00Z")).toBe("15m ago")
    expect(formatRelativeTime("not-a-date")).toBe("Unknown")
    expect(inferNoteType("Worldbuilding/Kingdoms.md")).toBe("World")
    expect(inferNoteType("Templates/Scene.md")).toBe("Template")
  })

  it("builds a folder tree with seeded folders", () => {
    const tree = buildFolderTree(["Characters/Mira.md"], ["Worldbuilding"])

    expect(tree.name).toBe("All notes")
    expect(tree.folders.has("Characters")).toBe(true)
    expect(tree.folders.has("Worldbuilding")).toBe(true)
  })

  it("derives selected note, selected content, outgoing links, and available paths", () => {
    const noteMap = buildNoteMap(notes)
    const selectedNote = getSelectedVaultNote(noteMap, "Characters/Mira.md")

    expect(selectedNote?.id).toBe("note-1")
    expect(getSelectedVaultNote(noteMap, null)).toBeNull()
    expect(getSelectedNoteContent(selectedNote, { "Characters/Mira.md": "Draft content" })).toBe("Draft content")
    expect(getSelectedNoteContent(selectedNote, {})).toBe(notes[0].content)
    expect(
      getSelectedOutgoingLinks(
        [
          { source: "Characters/Mira.md", target: "Plot Threads/Ash Gate.md" },
          { source: "Characters/Mira 2.md", target: "Characters/Mira.md" },
        ],
        "Characters/Mira.md"
      )
    ).toEqual([{ source: "Characters/Mira.md", target: "Plot Threads/Ash Gate.md" }])
    expect(getAvailableNotePaths(notes)).toEqual(["Characters/Mira.md", "Characters/Mira 2.md"])
  })

  it("filters, sorts, favorites, and selects displayed notes", () => {
    const worldNote = {
      id: "note-3",
      book_id: "book-1",
      path: "Worldbuilding/Ash Gate.md",
      source: "user_notes",
      content: "Ancient gate",
      created_at: "2026-06-03T00:00:00Z",
      updated_at: "2026-06-16T00:00:00Z",
    }
    const allNotes = [...notes, worldNote]

    expect(filterVaultNotes(allNotes, {}, "Characters", "").map((note) => note.path)).toEqual([
      "Characters/Mira.md",
      "Characters/Mira 2.md",
    ])
    expect(filterVaultNotes(allNotes, { "Characters/Mira 2.md": "Hidden Ash clue" }, null, "ash").map((note) => note.path)).toEqual([
      "Worldbuilding/Ash Gate.md",
      "Characters/Mira.md",
      "Characters/Mira 2.md",
    ])
    expect(getFavoriteVaultNotes(allNotes, { "Worldbuilding/Ash Gate.md": true }).map((note) => note.path)).toEqual([
      "Worldbuilding/Ash Gate.md",
    ])
    expect(getDisplayedVaultNotes("favorites", allNotes, [worldNote])).toEqual([worldNote])
    expect(getDisplayedVaultNotes("recent", allNotes, [worldNote])).toEqual(allNotes)
  })

  it("calculates markdown text edits and next selection ranges", () => {
    expect(wrapSelectedText("alpha beta", { start: 6, end: 10 }, "**")).toEqual({
      value: "alpha **beta**",
      start: 8,
      end: 12,
    })
    expect(wrapSelectedText("alpha ", { start: 6, end: 6 }, "[[", "]]", "Target")).toEqual({
      value: "alpha [[Target]]",
      start: 8,
      end: 14,
    })
    expect(prefixSelectedTextLines("one\ntwo", { start: 0, end: 7 }, "- ", "fallback")).toEqual({
      value: "- one\n- two",
      start: 0,
      end: 11,
    })
    expect(insertTextSnippet("alpha omega", { start: 6, end: 11 }, "***")).toEqual({
      value: "alpha ***",
      start: 9,
      end: 9,
    })
  })
})
