"use client"

import { useMemo, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import Link from "next/link"
import { WorkspaceHeader, WorkspacePage } from "@/components/ui/Workspace"
import { SUPPORT_HELP_EVENT } from "@/components/ui/ShortcutHelp"
import { booksApi } from "@/lib/api/books"
import { canUseAuthorFeatures } from "@/lib/billing/plans"
import { asQueryKey, booksNotesCacheKey } from "@/lib/query/cacheKeys"
import { useAuthStore } from "@/lib/stores/authStore"
import { renderRichTextHtml } from "@/lib/utils/richText"
import type { BookNote } from "@/types/book"
import { filterNotes, indexNotes, noteBooks, noteChapterHref, noteUpdatedDate } from "./notesPage.helpers"

const EMPTY_NOTES: BookNote[] = []
const PAGE_SIZE = 25

export default function NotesPage() {
  const userTier = useAuthStore((state) => state.user?.tier)
  const authHydrated = useAuthStore((state) => state.hydrated)
  const permitted = canUseAuthorFeatures(userTier)
  const [query, setQuery] = useState("")
  const [bookId, setBookId] = useState("")
  const [visible, setVisible] = useState(PAGE_SIZE)
  const result = useQuery<BookNote[]>({
    queryKey: asQueryKey(booksNotesCacheKey()),
    queryFn: () => booksApi.listNotes(),
    enabled: authHydrated && permitted,
    staleTime: 30_000,
  })
  const notes = result.data ?? EMPTY_NOTES
  const indexed = useMemo(() => indexNotes(notes), [notes])
  const books = useMemo(() => noteBooks(notes), [notes])
  const filtered = useMemo(() => filterNotes(indexed, query, bookId), [indexed, query, bookId])
  const filtering = !!query.trim() || !!bookId
  const clear = () => { setQuery(""); setBookId(""); setVisible(PAGE_SIZE) }

  return <WorkspacePage className="min-h-0 bg-transparent">
    <div data-account-notes className="min-w-0 space-y-6 pb-12 [overflow-wrap:anywhere]">
      <header className="border-b border-[rgb(var(--border))] pb-6">
        <WorkspaceHeader eyebrow="Story notes" title="Notes" description="Search notes from every manuscript and read them here. These are your saved manuscript notes; vault notes stay in each book’s notes workspace." actions={<button type="button" className="app-button-secondary self-start" onClick={() => window.dispatchEvent(new CustomEvent(SUPPORT_HELP_EVENT))}>Help</button>} />
      </header>
      {!authHydrated ? <p role="status" className="py-6 text-sm">Loading notes… Preparing your notes index.</p> : !permitted ? <section className="border-b border-[rgb(var(--border))] py-6"><h2 className="text-xl font-semibold">Notes require an active trial or paid plan.</h2><p className="mt-3 text-sm leading-6">View plans to access your saved manuscript notes.</p><div className="mt-4 flex flex-wrap gap-3"><Link href="/pricing" className="app-button-secondary">View plans</Link><Link href="/library" className="app-button-secondary">Return to library</Link></div></section> : <>
        <div className="flex flex-wrap items-end gap-4">
          <label htmlFor="notes-search" className="min-w-0 flex-1 basis-72 text-sm font-medium">Search notes<input type="search" id="notes-search" value={query} onChange={(event) => { setQuery(event.target.value); setVisible(PAGE_SIZE) }} placeholder="Note text, title, chapter, book, or tag" className="app-input mt-2" /></label>
          <label className="min-w-0 flex-1 basis-52 text-sm font-medium">Manuscript<select aria-label="Manuscript" value={bookId} onChange={(event) => { setBookId(event.target.value); setVisible(PAGE_SIZE) }} className="app-input mt-2"><option value="">All manuscripts</option>{books.map((book) => <option key={book.id} value={book.id}>{book.title}{books.filter((other) => other.title === book.title).length > 1 ? ` · ${book.id.slice(0, 8)}` : ""}</option>)}</select></label>
          {filtering ? <button type="button" className="app-button-secondary" onClick={clear}>Clear filters</button> : null}
          <button type="button" className="app-button-secondary" disabled={result.isFetching} onClick={() => void result.refetch()}>{result.isFetching ? "Refreshing…" : "Refresh notes"}</button>
        </div>
        {result.isLoading ? <p role="status" className="border-y border-[rgb(var(--border))] py-8 text-sm">Loading saved manuscript notes…</p> : null}
        {result.isError ? <div role="alert" className="border-l-2 border-amber-600 pl-4 text-sm leading-6"><p>{result.data ? "Notes could not be refreshed. Previously loaded notes are still shown." : "Your notes could not be loaded. Check your access or try again."}</p><button type="button" disabled={result.isFetching} onClick={() => void result.refetch()} className="mt-2 min-h-11 underline underline-offset-4">Retry notes</button></div> : null}
        {result.data ? <>
          <p role="status" className="text-sm text-[rgb(var(--muted-foreground))]">{filtering ? `${filtered.length} of ${notes.length} notes match` : `${notes.length} saved ${notes.length === 1 ? "note" : "notes"} across ${books.length} ${books.length === 1 ? "manuscript" : "manuscripts"}`} · Most recently updated first</p>
          {!notes.length ? <section className="border-y border-[rgb(var(--border))] py-8"><h2 className="text-xl font-semibold">No notes saved yet</h2><p className="mt-3 max-w-2xl text-sm leading-6">Save a note while reading a manuscript. You can then search and read it here. Vault notes are kept separately in each book.</p><Link href="/library" className="app-button-secondary mt-4">Choose a manuscript</Link></section> : !filtered.length ? <section className="border-y border-[rgb(var(--border))] py-8"><h2 className="text-xl font-semibold">No notes match that search</h2><p className="mt-3 text-sm">Try another phrase or clear the manuscript filter.</p><button type="button" className="app-button-secondary mt-4" onClick={clear}>Show all notes</button></section> : <>
            <div className="border-t border-[rgb(var(--border))]">{filtered.slice(0, visible).map(({ note, plainText }) => <NoteRow key={note.id} note={note} preview={plainText} />)}</div>
            {filtered.length > visible ? <div className="flex flex-wrap items-center gap-4 text-sm"><p>Showing {visible} of {filtered.length} matching notes.</p><button type="button" className="app-button-secondary" onClick={() => setVisible((count) => count + PAGE_SIZE)}>Show {Math.min(PAGE_SIZE, filtered.length - visible)} more notes</button></div> : null}
          </>}
        </> : null}
      </>}
    </div>
  </WorkspacePage>
}

function NoteRow({ note, preview }: { note: BookNote; preview: string }) {
  const [expanded, setExpanded] = useState(false)
  const updated = noteUpdatedDate(note.updated_at)
  const chapterHref = noteChapterHref(note)
  return <article className="min-w-0 border-b border-[rgb(var(--border))] py-5">
    <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-2 text-sm text-[rgb(var(--muted-foreground))]"><p>{note.book_title || "Untitled manuscript"}</p>{updated ? <time dateTime={updated.iso}>Updated {updated.label}</time> : <span>Update date unavailable</span>}</div>
    <h2 className="mt-2 text-lg font-semibold">{note.title?.trim() || "Untitled note"}</h2>
    <p className="mt-1 text-sm text-[rgb(var(--muted-foreground))]">{chapterHref ? `Chapter ${note.chapter_number}${note.chapter_title ? ` · ${note.chapter_title}` : ""}` : "General manuscript note"}</p>
    {expanded ? <div id={`note-body-${note.id}`} className="note-rich-content mt-4 max-w-prose text-base leading-7" dangerouslySetInnerHTML={{ __html: renderRichTextHtml(note.body ?? "") }} /> : <p id={`note-body-${note.id}`} className="mt-3 max-w-prose text-sm leading-6">{preview ? `${preview.slice(0, 240)}${preview.length > 240 ? "…" : ""}` : "No text in this note."}</p>}
    {note.tags?.length ? <p className="mt-3 text-sm text-[rgb(var(--muted-foreground))]">Tags: {note.tags.join(", ")}</p> : null}
    <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-2 text-sm">
      {note.body?.trim() ? <button type="button" aria-label={`${expanded ? "Close note" : "Read note"}: ${note.title || "Untitled note"}`} aria-expanded={expanded} aria-controls={`note-body-${note.id}`} className="min-h-11 font-semibold underline underline-offset-4" onClick={() => setExpanded((value) => !value)}>{expanded ? "Close note" : "Read note"}</button> : null}
      {chapterHref ? <Link href={chapterHref} className="inline-flex min-h-11 items-center underline underline-offset-4">Open chapter {note.chapter_number}</Link> : null}
      <Link href={`/${encodeURIComponent(note.book_id)}/notes`} className="inline-flex min-h-11 items-center underline underline-offset-4">Book notes workspace</Link>
    </div>
  </article>
}
