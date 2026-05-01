"use client"

import { startTransition, useDeferredValue, useEffect, useMemo, useRef, useState, type ReactNode } from "react"

import { booksApi } from "@/lib/api/books"
import type { ObsidianGraph, ObsidianNoteRelations, ObsidianVaultNote } from "@/types/book"
import { FolderTree } from "./FolderTree"
import { GraphViewer } from "./GraphViewer"
import { MarkdownPreview } from "./MarkdownPreview"

function noteTitle(path: string) {
  return path.split("/").pop()?.replace(/\.md$/i, "") || path
}

function matchesReference(path: string, reference: string) {
  const cleanedReference = reference.replace(/\.md$/i, "").trim().toLowerCase()
  const cleanedPath = path.toLowerCase()
  return cleanedPath === reference.toLowerCase() || noteTitle(path).toLowerCase() === cleanedReference
}

function fileWordCount(value: string) {
  const trimmed = value.trim()
  return trimmed ? trimmed.split(/\s+/).length : 0
}

export function ObsidianNotesEditor({
  bookId,
  bookTitle,
  initialNotes,
  initialGraph,
  isDark,
}: {
  bookId: string
  bookTitle: string
  initialNotes: ObsidianVaultNote[]
  initialGraph: ObsidianGraph
  isDark: boolean
}) {
  const [notes, setNotes] = useState<ObsidianVaultNote[]>(initialNotes)
  const [graph, setGraph] = useState<ObsidianGraph>(initialGraph)
  const [relations, setRelations] = useState<ObsidianNoteRelations | null>(null)
  const [selectedPath, setSelectedPath] = useState<string | null>(initialNotes[0]?.path ?? null)
  const [drafts, setDrafts] = useState<Record<string, string>>({})
  const [query, setQuery] = useState("")
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({})
  const [mode, setMode] = useState<"edit" | "preview">("edit")
  const [status, setStatus] = useState<string | null>(null)
  const [newFolder, setNewFolder] = useState("Characters")
  const [newTitle, setNewTitle] = useState("")
  const [busy, setBusy] = useState(false)
  const [graphExpanded, setGraphExpanded] = useState(false)
  const deferredQuery = useDeferredValue(query)
  const saveTimersRef = useRef<Record<string, number>>({})
  const latestDraftRef = useRef<Record<string, string>>({})
  const importInputRef = useRef<HTMLInputElement | null>(null)

  useEffect(() => {
    return () => {
      for (const timer of Object.values(saveTimersRef.current)) {
        window.clearTimeout(timer)
      }
    }
  }, [])

  useEffect(() => {
    if (!graphExpanded) return
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setGraphExpanded(false)
      }
    }
    window.addEventListener("keydown", onKeyDown)
    return () => window.removeEventListener("keydown", onKeyDown)
  }, [graphExpanded])

  const noteMap = useMemo(() => new Map(notes.map((note) => [note.path, note])), [notes])
  const selectedNote = selectedPath ? noteMap.get(selectedPath) ?? null : null
  const selectedContent = selectedNote ? drafts[selectedNote.path] ?? selectedNote.content : ""

  const filteredPaths = useMemo(() => {
    const term = deferredQuery.trim().toLowerCase()
    const source = notes.map((note) => ({
      path: note.path,
      title: noteTitle(note.path).toLowerCase(),
      content: (drafts[note.path] ?? note.content).toLowerCase(),
    }))
    if (!term) return source.map((item) => item.path)
    return source
      .filter((item) => item.path.toLowerCase().includes(term) || item.title.includes(term) || item.content.includes(term))
      .map((item) => item.path)
  }, [deferredQuery, drafts, notes])

  useEffect(() => {
    if (!selectedPath && filteredPaths[0]) {
      setSelectedPath(filteredPaths[0])
      return
    }
    if (selectedPath && filteredPaths.length > 0 && !filteredPaths.includes(selectedPath)) {
      setSelectedPath(filteredPaths[0])
    }
  }, [filteredPaths, selectedPath])

  useEffect(() => {
    if (!selectedNote) {
      setRelations(null)
      return
    }

    let cancelled = false
    setRelations(null)
    void booksApi.getObsidianNoteRelations(bookId, selectedNote.path)
      .then((value) => {
        if (!cancelled) setRelations(value)
      })
      .catch(() => {
        if (!cancelled) setRelations(null)
      })
    return () => {
      cancelled = true
    }
  }, [bookId, selectedNote?.path])

  const refreshGraph = async () => {
    const nextGraph = await booksApi.getObsidianGraph(bookId)
    setGraph(nextGraph)
  }

  const saveNote = async (path: string, content: string) => {
    latestDraftRef.current[path] = content
    try {
      const result = await booksApi.saveObsidianNote(bookId, { path, content })
      if (latestDraftRef.current[path] !== result.content) return
      setNotes((current) =>
        current
          .map((note) =>
            note.path === path ? { ...note, content: result.content, updated_at: result.updated_at ?? note.updated_at } : note
          )
          .sort((a, b) => a.path.localeCompare(b.path))
      )
      setDrafts((current) => ({ ...current, [path]: result.content }))
      setStatus(`Saved ${path}`)
      void refreshGraph()
      if (selectedPath === path) {
        void booksApi.getObsidianNoteRelations(bookId, path).then((value) => setRelations(value))
      }
    } catch {
      setStatus(`Could not save ${path}`)
    }
  }

  useEffect(() => {
    if (!selectedNote) return
    const nextValue = drafts[selectedNote.path]
    if (nextValue === undefined || nextValue === selectedNote.content) return
    const existingTimer = saveTimersRef.current[selectedNote.path]
    if (existingTimer) window.clearTimeout(existingTimer)
    saveTimersRef.current[selectedNote.path] = window.setTimeout(() => {
      delete saveTimersRef.current[selectedNote.path]
      void saveNote(selectedNote.path, latestDraftRef.current[selectedNote.path] ?? nextValue)
    }, 700)
  }, [drafts, selectedNote])

  const openNote = (reference: string) => {
    const match = notes.find((note) => matchesReference(note.path, reference))
    if (!match) return
    startTransition(() => setSelectedPath(match.path))
  }

  const createNote = async () => {
    const trimmedTitle = newTitle.trim()
    if (!trimmedTitle) return
    const cleanFolder = newFolder.trim().replace(/^\/+|\/+$/g, "")
    const filename = `${trimmedTitle.replace(/[<>:"|?*]+/g, "").trim() || "Untitled"}.md`
    const path = cleanFolder ? `${cleanFolder}/${filename}` : filename
    setBusy(true)
    try {
      const result = await booksApi.saveObsidianNote(bookId, { path, content: `# ${trimmedTitle}\n\n` })
      setNotes((current) =>
        [...current, {
          id: `${result.path}:${Date.now()}`,
          book_id: bookId,
          source: result.source,
          path: result.path,
          content: result.content,
          created_at: result.created_at ?? new Date().toISOString(),
          updated_at: result.updated_at ?? new Date().toISOString(),
        }].sort((a, b) => a.path.localeCompare(b.path))
      )
      setDrafts((current) => ({ ...current, [result.path]: result.content }))
      setSelectedPath(result.path)
      setNewTitle("")
      setStatus(`Created ${result.path}`)
      await refreshGraph()
    } finally {
      setBusy(false)
    }
  }

  const deleteCurrent = async () => {
    if (!selectedNote) return
    const proceed = window.confirm(`Delete ${selectedNote.path}?`)
    if (!proceed) return
    setBusy(true)
    try {
      await booksApi.deleteObsidianNote(bookId, selectedNote.path)
      setNotes((current) => current.filter((note) => note.path !== selectedNote.path))
      setDrafts((current) => {
        const next = { ...current }
        delete next[selectedNote.path]
        return next
      })
      setSelectedPath((current) => {
        const remaining = notes.filter((note) => note.path !== selectedNote.path)
        return remaining[0]?.path ?? null
      })
      setStatus(`Deleted ${selectedNote.path}`)
      await refreshGraph()
    } finally {
      setBusy(false)
    }
  }

  const exportNotes = async () => {
    const blob = await booksApi.exportObsidianNotes(bookId)
    const url = window.URL.createObjectURL(blob)
    const anchor = document.createElement("a")
    anchor.href = url
    anchor.download = `${bookTitle.replace(/[^\w\s-]/g, "").trim().replace(/\s+/g, "-") || "book"}-notes.zip`
    document.body.appendChild(anchor)
    anchor.click()
    anchor.remove()
    window.URL.revokeObjectURL(url)
    setStatus("Downloaded notes ZIP")
  }

  const importNotes = async (file: File) => {
    setBusy(true)
    try {
      await booksApi.importObsidianNotes(bookId, file)
      const [nextNotes, nextGraph] = await Promise.all([booksApi.listObsidianNotes(bookId), booksApi.getObsidianGraph(bookId)])
      setNotes(nextNotes)
      setGraph(nextGraph)
      setSelectedPath(nextNotes[0]?.path ?? null)
      setStatus(`Imported ${file.name}`)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className={`rounded-[2rem] border p-5 shadow-[0_30px_90px_-50px_rgba(15,23,42,0.85)] ${isDark ? "border-white/10 bg-[linear-gradient(180deg,rgba(8,10,20,0.96),rgba(14,23,38,0.9))]" : "border-stone-200 bg-[linear-gradient(180deg,rgba(255,255,255,0.96),rgba(244,247,245,0.92))]"}`}>
      <div className="flex flex-col gap-5 border-b border-white/10 pb-5 xl:flex-row xl:items-end xl:justify-between">
        <div className="max-w-3xl">
          <p className={`text-[11px] font-semibold uppercase tracking-[0.34em] ${isDark ? "text-emerald-300" : "text-emerald-600"}`}>Per-book vault</p>
          <h2 className={`mt-2 font-serif text-4xl tracking-tight ${isDark ? "text-white" : "text-stone-950"}`}>Obsidian-style notes workspace</h2>
          <p className={`mt-3 text-sm leading-7 ${isDark ? "text-slate-300" : "text-stone-600"}`}>
            Organize notes in folders, write in markdown, jump through wiki-links, and export the vault as a ZIP whenever you want.
          </p>
        </div>

        <div className="flex flex-wrap gap-2">
          <button type="button" onClick={() => importInputRef.current?.click()} disabled={busy} className={`rounded-full border px-4 py-2 text-sm font-medium ${isDark ? "border-white/10 bg-white/5 text-slate-200" : "border-stone-200 bg-white text-stone-700"}`}>Import ZIP</button>
          <button type="button" onClick={exportNotes} disabled={busy} className="rounded-full bg-[linear-gradient(135deg,#0f766e,#2563eb)] px-4 py-2 text-sm font-semibold text-white">Export ZIP</button>
          <input
            ref={importInputRef}
            type="file"
            accept=".zip,application/zip"
            className="hidden"
            onChange={(event) => {
              const file = event.target.files?.[0]
              if (file) void importNotes(file)
              event.currentTarget.value = ""
            }}
          />
        </div>
      </div>

      <div className="mt-5 grid gap-5 xl:grid-cols-[20rem_minmax(0,1fr)_20rem]">
        <aside className={`rounded-[1.4rem] border p-4 ${isDark ? "border-white/10 bg-black/20" : "border-stone-200 bg-white/80"}`}>
          <div className="space-y-3">
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search notes or content"
              className={`w-full rounded-[1rem] border px-3 py-2 text-sm outline-none ${isDark ? "border-white/10 bg-white/5 text-slate-100" : "border-stone-200 bg-white text-stone-900"}`}
            />
            <div className={`rounded-[1rem] border p-3 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-stone-200 bg-stone-50"}`}>
              <p className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>New note</p>
              <input
                value={newFolder}
                onChange={(event) => setNewFolder(event.target.value)}
                placeholder="Folder"
                className={`mt-3 w-full rounded-xl border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-[#07111f] text-slate-100" : "border-stone-200 bg-white text-stone-900"}`}
              />
              <input
                value={newTitle}
                onChange={(event) => setNewTitle(event.target.value)}
                placeholder="Note title"
                className={`mt-2 w-full rounded-xl border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-[#07111f] text-slate-100" : "border-stone-200 bg-white text-stone-900"}`}
              />
              <button type="button" onClick={() => void createNote()} disabled={busy || !newTitle.trim()} className="mt-3 w-full rounded-xl bg-[linear-gradient(135deg,#059669,#0f766e)] px-4 py-2 text-sm font-semibold text-white disabled:opacity-60">
                Create note
              </button>
            </div>
          </div>

          <div className="mt-4 max-h-[40rem] overflow-auto pr-1">
            {filteredPaths.length === 0 ? (
              <div className={`rounded-[1rem] border border-dashed px-4 py-8 text-center text-sm ${isDark ? "border-white/10 text-slate-400" : "border-stone-300 text-stone-500"}`}>No notes match that search.</div>
            ) : (
              <FolderTree
                paths={filteredPaths}
                activePath={selectedPath}
                collapsed={collapsed}
                onToggleFolder={(path) => setCollapsed((current) => ({ ...current, [path]: !current[path] }))}
                onSelect={(path) => setSelectedPath(path)}
                isDark={isDark}
              />
            )}
          </div>
        </aside>

        <section className={`rounded-[1.4rem] border p-4 ${isDark ? "border-white/10 bg-black/25" : "border-stone-200 bg-white"}`}>
          {selectedNote ? (
            <>
              <div className="flex flex-col gap-3 border-b border-white/10 pb-4 lg:flex-row lg:items-end lg:justify-between">
                <div>
                  <p className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Editing</p>
                  <h3 className={`mt-2 text-2xl font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>{noteTitle(selectedNote.path)}</h3>
                  <p className={`mt-1 text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>{selectedNote.path}</p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <button type="button" onClick={() => setMode("edit")} className={`rounded-full px-4 py-2 text-sm font-medium ${mode === "edit" ? "bg-emerald-600 text-white" : isDark ? "bg-white/5 text-slate-200" : "bg-stone-100 text-stone-700"}`}>Edit</button>
                  <button type="button" onClick={() => setMode("preview")} className={`rounded-full px-4 py-2 text-sm font-medium ${mode === "preview" ? "bg-emerald-600 text-white" : isDark ? "bg-white/5 text-slate-200" : "bg-stone-100 text-stone-700"}`}>Preview</button>
                  <button type="button" onClick={() => void saveNote(selectedNote.path, selectedContent)} className={`rounded-full px-4 py-2 text-sm font-medium ${isDark ? "bg-white/10 text-white" : "bg-stone-900 text-white"}`}>Save now</button>
                  <button type="button" onClick={() => void deleteCurrent()} disabled={busy} className={`rounded-full px-4 py-2 text-sm font-medium ${isDark ? "bg-rose-500/15 text-rose-200" : "bg-rose-50 text-rose-700"}`}>Delete</button>
                </div>
              </div>

              <div className="mt-4">
                {mode === "edit" ? (
                  <textarea
                    value={selectedContent}
                    onChange={(event) => {
                      const value = event.target.value
                      latestDraftRef.current[selectedNote.path] = value
                      setDrafts((current) => ({ ...current, [selectedNote.path]: value }))
                      setStatus(null)
                    }}
                    spellCheck={false}
                    className={`min-h-[34rem] w-full resize-y rounded-[1.2rem] border px-4 py-4 font-mono text-sm leading-7 outline-none ${isDark ? "border-white/10 bg-[#050816] text-slate-100" : "border-stone-200 bg-white text-stone-900"}`}
                  />
                ) : (
                  <MarkdownPreview content={selectedContent} isDark={isDark} notes={notes} currentPath={selectedNote.path} onOpenNote={openNote} />
                )}
              </div>
            </>
          ) : (
            <div className={`flex min-h-[30rem] items-center justify-center rounded-[1.2rem] border border-dashed ${isDark ? "border-white/10 text-slate-400" : "border-stone-300 text-stone-500"}`}>Create or select a note to begin.</div>
          )}
        </section>

        <aside className="space-y-4">
          <div className={`rounded-[1.4rem] border p-4 ${isDark ? "border-white/10 bg-black/20" : "border-stone-200 bg-white/80"}`}>
            <p className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Current note</p>
            <div className="mt-3 space-y-2 text-sm">
              <InfoRow label="Folder" value={selectedNote ? selectedNote.path.split("/").slice(0, -1).join("/") || "Root" : "-"} isDark={isDark} />
              <InfoRow label="Words" value={String(fileWordCount(selectedContent))} isDark={isDark} />
              <InfoRow label="Links" value={String(graph.edges.filter((edge) => edge.source === selectedPath).length)} isDark={isDark} />
            </div>
            {relations ? (
              <div className="mt-4 space-y-3">
                <RelationGroup label="Tags" isDark={isDark}>
                  {relations.tags.length ? (
                    <div className="flex flex-wrap gap-2">
                      {relations.tags.map((tag) => (
                        <span
                          key={tag.id}
                          className={`rounded-full px-3 py-1 text-xs font-medium ${isDark ? "bg-emerald-500/15 text-emerald-200" : "bg-emerald-50 text-emerald-700"}`}
                        >
                          #{tag.tag_name}
                        </span>
                      ))}
                    </div>
                  ) : (
                    <p className={`text-xs ${isDark ? "text-slate-500" : "text-stone-400"}`}>No tags found.</p>
                  )}
                </RelationGroup>

                <RelationGroup label="Links" isDark={isDark}>
                  <RelationList
                    items={relations.links.map((link) => ({ id: link.id, label: link.target_note_path, secondary: link.target_label ?? link.link_type }))}
                    isDark={isDark}
                    onOpen={openNote}
                    emptyLabel="No outgoing links."
                  />
                </RelationGroup>

                <RelationGroup label="Backlinks" isDark={isDark}>
                  <RelationList
                    items={relations.backlinks.map((link) => ({ id: link.id, label: link.source_note_path, secondary: link.link_type }))}
                    isDark={isDark}
                    onOpen={openNote}
                    emptyLabel="No backlinks yet."
                  />
                </RelationGroup>

                <RelationGroup label="Series Links" isDark={isDark}>
                  <RelationList
                    items={relations.series_links.map((link) => ({ id: link.id, label: link.target_note_path, secondary: link.link_type }))}
                    isDark={isDark}
                    onOpen={openNote}
                    emptyLabel="No series links."
                  />
                </RelationGroup>
              </div>
            ) : null}
            {status ? <p className={`mt-4 text-sm ${isDark ? "text-emerald-300" : "text-emerald-700"}`}>{status}</p> : null}
          </div>

          <div className={`rounded-[1.4rem] border p-4 ${isDark ? "border-white/10 bg-black/20" : "border-stone-200 bg-white/80"}`}>
            <div className="flex items-center justify-between gap-3">
              <p className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Graph viewer</p>
              <button
                type="button"
                onClick={() => setGraphExpanded(true)}
                className={`rounded-full border px-3 py-1.5 text-xs font-semibold transition ${isDark ? "border-white/10 bg-white/5 text-slate-200 hover:bg-white/10" : "border-stone-200 bg-white text-stone-700 hover:bg-stone-50"}`}
              >
                Open graph view
              </button>
            </div>
            <div className="mt-3">
              <GraphViewer
                graph={graph}
                selectedPath={selectedPath}
                onOpenNote={(path) => setSelectedPath(path)}
                isDark={isDark}
                heightClassName="min-h-[23rem]"
              />
            </div>
          </div>
        </aside>
      </div>

      {graphExpanded ? (
        <div className="fixed inset-0 z-[70] flex items-stretch justify-center bg-black/70 p-3 backdrop-blur-sm sm:p-5">
          <div className={`flex h-full w-full max-w-[96rem] flex-col overflow-hidden rounded-[1.8rem] border shadow-[0_40px_140px_-50px_rgba(2,6,23,0.95)] ${isDark ? "border-white/10 bg-[#08111d]" : "border-stone-200 bg-[#f4f7fb]"}`}>
            <div className={`flex flex-col gap-3 border-b px-5 py-4 sm:flex-row sm:items-center sm:justify-between ${isDark ? "border-white/10 bg-black/20" : "border-stone-200 bg-white/70"}`}>
              <div>
                <p className={`text-[11px] font-semibold uppercase tracking-[0.24em] ${isDark ? "text-emerald-300" : "text-emerald-700"}`}>Obsidian graph</p>
                <h3 className={`mt-1 text-2xl font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>Vault graph view</h3>
                <p className={`mt-1 text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>
                  Pan, zoom, drag nodes, and open linked notes directly from the site.
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                {selectedNote ? (
                  <div className={`rounded-full border px-4 py-2 text-sm ${isDark ? "border-white/10 bg-white/5 text-slate-200" : "border-stone-200 bg-white text-stone-700"}`}>
                    Current: {noteTitle(selectedNote.path)}
                  </div>
                ) : null}
                <button
                  type="button"
                  onClick={() => setGraphExpanded(false)}
                  className={`rounded-full px-4 py-2 text-sm font-semibold ${isDark ? "bg-white text-slate-950" : "bg-stone-900 text-white"}`}
                >
                  Close
                </button>
              </div>
            </div>

            <div className="grid min-h-0 flex-1 gap-0 lg:grid-cols-[minmax(0,1fr)_22rem]">
              <div className="min-h-0 p-4">
                <GraphViewer
                  graph={graph}
                  selectedPath={selectedPath}
                  onOpenNote={(path) => {
                    setSelectedPath(path)
                    setGraphExpanded(false)
                  }}
                  isDark={isDark}
                  heightClassName="h-[calc(100vh-13rem)] min-h-[34rem]"
                />
              </div>

              <aside className={`border-l p-5 ${isDark ? "border-white/10 bg-black/20" : "border-stone-200 bg-white/65"}`}>
                <p className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>How it works</p>
                <div className={`mt-4 space-y-3 text-sm leading-7 ${isDark ? "text-slate-300" : "text-stone-600"}`}>
                  <p>Drag nodes to shape the map. Your layout stays saved in the browser.</p>
                  <p>Use <span className="font-semibold">Local</span> to focus on the current note’s neighborhood, or switch back to the full vault.</p>
                  <p>Labels fade out when you zoom far away, then return as you zoom back in, closer to Obsidian’s graph behavior.</p>
                  <p>Click a node to jump straight into that note.</p>
                </div>

                {selectedNote ? (
                  <div className={`mt-6 rounded-[1.2rem] border p-4 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-stone-200 bg-stone-50"}`}>
                    <p className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Selected note</p>
                    <h4 className={`mt-2 text-lg font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{noteTitle(selectedNote.path)}</h4>
                    <p className={`mt-1 text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>{selectedNote.path}</p>
                    <button
                      type="button"
                      onClick={() => setGraphExpanded(false)}
                      className={`mt-4 inline-flex items-center justify-center rounded-full px-4 py-2 text-sm font-medium ${isDark ? "bg-white/10 text-slate-100" : "bg-stone-900 text-white"}`}
                    >
                      Open in editor
                    </button>
                  </div>
                ) : null}
              </aside>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )
}

function InfoRow({ label, value, isDark }: { label: string; value: string; isDark: boolean }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className={`text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>{label}</span>
      <span className={`text-xs ${isDark ? "text-slate-200" : "text-stone-700"}`}>{value}</span>
    </div>
  )
}

function RelationGroup({
  label,
  isDark,
  children,
}: {
  label: string
  isDark: boolean
  children: ReactNode
}) {
  return (
    <div className={`rounded-[1rem] border p-3 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-stone-200 bg-stone-50"}`}>
      <p className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>{label}</p>
      <div className="mt-2">{children}</div>
    </div>
  )
}

function RelationList({
  items,
  emptyLabel,
  onOpen,
  isDark,
}: {
  items: { id: string; label: string; secondary?: string | null }[]
  emptyLabel: string
  onOpen: (reference: string) => void
  isDark: boolean
}) {
  if (!items.length) {
    return <p className={`text-xs ${isDark ? "text-slate-500" : "text-stone-400"}`}>{emptyLabel}</p>
  }

  return (
    <div className="space-y-2">
      {items.map((item) => (
        <button
          key={item.id}
          type="button"
          onClick={() => onOpen(item.label)}
          className={`flex w-full items-center justify-between gap-3 rounded-xl border px-3 py-2 text-left text-sm transition ${
            isDark ? "border-white/10 bg-black/20 text-slate-100 hover:bg-white/5" : "border-stone-200 bg-white text-stone-800 hover:bg-stone-50"
          }`}
        >
          <span className="min-w-0 truncate">{item.label}</span>
          {item.secondary ? <span className={`shrink-0 text-[11px] uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>{item.secondary}</span> : null}
        </button>
      ))}
    </div>
  )
}
