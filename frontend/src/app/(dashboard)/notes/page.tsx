"use client"

import { useMemo, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import Link from "next/link"

import {
  WorkspaceEmptyState,
  WorkspaceHeader,
  WorkspaceMetric,
  WorkspacePage,
  WorkspacePanel,
} from "@/components/ui/Workspace"
import { booksApi } from "@/lib/api/books"
import { asQueryKey, booksNotesCacheKey } from "@/lib/query/cacheKeys"
import { renderRichTextHtml } from "@/lib/utils/richText"
import type { BookNote } from "@/types/book"

export default function NotesPage() {
  const [query, setQuery] = useState("")
  const { data: notes = [], isLoading: loading } = useQuery<BookNote[]>({
    queryKey: asQueryKey(booksNotesCacheKey()),
    queryFn: () => booksApi.listNotes(),
    staleTime: 30_000,
  })

  const filteredNotes = useMemo(() => {
    const trimmed = query.trim().toLowerCase()
    if (!trimmed) return notes

    return notes.filter((note) =>
      [note.book_title, note.chapter_title, note.title, note.body]
        .filter(Boolean)
        .some((value) => value!.toLowerCase().includes(trimmed))
    )
  }, [notes, query])

  const booksRepresented = useMemo(
    () => new Set(notes.map((note) => note.book_title).filter(Boolean)).size,
    [notes]
  )

  return (
    <WorkspacePage className="min-h-0 bg-transparent">
      <div className="space-y-8 pb-12">
        <WorkspacePanel tone="strong" className="p-6 sm:p-8">
          <WorkspaceHeader
            eyebrow="Story notes"
            title="Keep manuscript notes visible without digging through each workspace."
            description="This page now behaves more like a proper notes inbox: you can scan what changed, search across books, and jump back to the right editing surface fast."
            meta={
              <div className="flex flex-wrap justify-end gap-3">
                <div className="app-chip">{notes.length} saved notes</div>
                <div className="app-chip">{booksRepresented} books represented</div>
              </div>
            }
          />

          <div className="mt-6">
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search notes, chapter names, or book titles"
              className="app-input"
            />
          </div>
        </WorkspacePanel>

        <section className="grid gap-4 sm:grid-cols-3">
          <WorkspaceMetric
            label="Visible notes"
            value={filteredNotes.length.toLocaleString()}
            note={query.trim() ? "Current filtered result set" : "All saved note cards"}
            accent="accent"
          />
          <WorkspaceMetric
            label="Books covered"
            value={booksRepresented.toLocaleString()}
            note="Unique manuscripts with notes"
          />
          <WorkspaceMetric
            label="Search mode"
            value={query.trim() ? "Filtered" : "All notes"}
            note={query.trim() ? `Query: ${query}` : "No active filter"}
            accent="success"
          />
        </section>

        {loading ? (
          <WorkspaceEmptyState
            title="Loading notes"
            body="LoreVia is collecting your chapter-linked notes and workspace annotations."
          />
        ) : filteredNotes.length === 0 ? (
          <WorkspaceEmptyState
            title={notes.length === 0 ? "No notes saved yet" : "No notes match that search"}
            body={
              notes.length === 0
                ? "Notes from your manuscript and reading workspaces will appear here once you start capturing them."
                : "Try a broader search term to pull notes from more books or chapters."
            }
          />
        ) : (
          <div className="grid gap-5 xl:grid-cols-2">
            {filteredNotes.map((note) => (
              <WorkspacePanel key={note.id} className="p-5">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="app-eyebrow">{note.book_title}</p>
                    <h2 className="mt-3 text-xl font-semibold text-[rgb(var(--foreground))]">
                      {note.title || "Untitled note"}
                    </h2>
                    <p className="mt-2 text-sm text-[rgb(var(--muted-foreground))]">
                      {note.chapter_number
                        ? `Chapter ${note.chapter_number}${note.chapter_title ? ` - ${note.chapter_title}` : ""}`
                        : "General manuscript note"}
                    </p>
                  </div>

                  <span className="app-chip whitespace-nowrap">
                    {new Date(note.updated_at).toLocaleDateString()}
                  </span>
                </div>

                <div
                  className="note-rich-content mt-5 text-sm leading-7 text-[rgb(var(--foreground))]"
                  dangerouslySetInnerHTML={{ __html: renderRichTextHtml(note.body) }}
                />

                <div className="mt-6 flex flex-wrap gap-3">
                  <Link href={`/${note.book_id}/manuscript`} className="app-button-primary">
                    Open manuscript
                  </Link>
                  <Link href={`/${note.book_id}/notes`} className="app-button-secondary">
                    Open notes vault
                  </Link>
                  {note.chapter_number ? (
                    <Link href={`/${note.book_id}/chapter/${note.chapter_number}`} className="app-button-secondary">
                      Open chapter
                    </Link>
                  ) : null}
                </div>
              </WorkspacePanel>
            ))}
          </div>
        )}
      </div>
    </WorkspacePage>
  )
}
