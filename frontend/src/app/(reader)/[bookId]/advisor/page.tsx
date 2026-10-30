"use client"

import { useEffect, useRef, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import Link from "next/link"
import { useParams } from "next/navigation"
import { WorkspaceFamilyHeader } from "@/components/reader/WorkspaceFamilyHeader"
import { SUPPORT_HELP_EVENT } from "@/components/ui/ShortcutHelp"
import { booksApi } from "@/lib/api/books"
import { intelligenceApi } from "@/lib/api/intelligence"
import { canUseAuthorFeatures } from "@/lib/billing/plans"
import { useAuthStore } from "@/lib/stores/authStore"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import { capture } from "@/lib/analytics/posthog"
import { saveContextualVaultNote } from "@/lib/utils/notes"
import { AdvisorConversation } from "./advisorPage.conversation"
import { AdvisorChecks } from "./advisorPage.checks"
import type { AdvisorNote } from "./advisorPage.helpers"

export default function AdvisorPage() {
  const { bookId } = useParams<{ bookId: string }>()
  const user = useAuthStore((state) => state.user)
  const hydrated = useAuthStore((state) => state.hydrated)
  const { theme } = usePreferencesStore()
  if (!hydrated) return <p role="status" className="p-6">Loading your account…</p>
  if (!user) return <p role="alert" className="p-6">Sign in to use Story Advisor.</p>
  return <AdvisorWorkspace key={`${user.id}:${bookId}`} bookId={bookId} userId={user.id} paid={canUseAuthorFeatures(user.tier)} isDark={theme === "dark"} />
}

function AdvisorWorkspace({ bookId, userId, paid, isDark }: { bookId: string; userId: string; paid: boolean; isDark: boolean }) {
  const [tab, setTab] = useState<"chat" | "scan">("chat")
  const [input, setInput] = useState("")
  const [busy, setBusy] = useState(false)
  const [saving, setSaving] = useState(false)
  const [noteStatus, setNoteStatus] = useState("")
  const [failedNote, setFailedNote] = useState<AdvisorNote | null>(null)
  const mounted = useRef(true)
  const savingRef = useRef(false)
  const guard = useRef({ dirty: false, busy: false })
  guard.current = { dirty: !!input.trim(), busy: busy || saving }
  const book = useQuery({ queryKey: ["advisor-context", userId, bookId], queryFn: () => booksApi.get(bookId), retry: false, refetchOnWindowFocus: false, refetchOnReconnect: false })
  const greeting = useQuery({ queryKey: ["advisor-greeting", userId, bookId], queryFn: () => intelligenceApi.advisorGreeting(bookId), enabled: !!book.data, retry: false, refetchOnWindowFocus: false, refetchOnReconnect: false })

  useEffect(() => {
    if (paid && new URLSearchParams(window.location.search).get("tab") === "scan") setTab("scan")
  }, [paid])

  useEffect(() => {
    mounted.current = true
    capture("author_advisor_opened", { book_id: bookId })
    const unload = (event: BeforeUnloadEvent) => { if (guard.current.dirty || guard.current.busy) { event.preventDefault(); event.returnValue = "" } }
    const click = (event: MouseEvent) => {
      const anchor = event.target instanceof Element ? event.target.closest<HTMLAnchorElement>("a[href]") : null
      if (!anchor || anchor.target === "_blank" || anchor.hasAttribute("download") || /^(#|mailto:|tel:)/.test(anchor.getAttribute("href") ?? "")) return
      if ((guard.current.dirty || guard.current.busy) && !window.confirm("Leave Story Advisor? Unsaved questions and answers stay only on this page. An unfinished answer will stop waiting.")) { event.preventDefault(); event.stopPropagation() }
    }
    window.addEventListener("beforeunload", unload); document.addEventListener("click", click, true)
    return () => { mounted.current = false; window.removeEventListener("beforeunload", unload); document.removeEventListener("click", click, true) }
  }, [bookId])

  async function saveNote(note: AdvisorNote) {
    if (savingRef.current || !paid) return
    savingRef.current = true; setSaving(true); setNoteStatus("Saving advisor note…"); setFailedNote(null)
    try {
      await saveContextualVaultNote({ bookId, title: note.title?.trim() || "Advisor note", content: note.body, context: "story_advisor", folderSegments: note.chapterNumber ? [`Chapter ${note.chapterNumber}`] : [] })
      if (mounted.current) setNoteStatus(`Saved to Story Advisor${note.chapterNumber ? ` / Chapter ${note.chapterNumber}` : ""}.`)
    } catch { if (mounted.current) { setNoteStatus("Note saving could not be confirmed. Check your notes before retrying to avoid a duplicate."); setFailedNote(note) } }
    finally { savingRef.current = false; if (mounted.current) setSaving(false) }
  }

  function askFromCheck(prompt: string) {
    if (busy) { setNoteStatus("Wait for the current answer or stop waiting before choosing another question."); return }
    if (input.trim() && input !== prompt && !window.confirm("Replace your current question draft with this check?")) return
    setInput(prompt); setTab("chat")
    requestAnimationFrame(() => document.getElementById("advisor-input")?.focus())
  }

  return <div data-advisor-workspace className="min-h-screen bg-[rgb(var(--background))] text-[rgb(var(--foreground))] [overflow-wrap:anywhere]"><div className="mx-auto max-w-[84rem] space-y-6 px-4 py-6 pb-16 sm:px-6 lg:px-8">
    <WorkspaceFamilyHeader active="advisor" bookId={bookId} family="review-center" title="Story advisor" description="Ask grounded questions about the manuscript or review checks drawn from extracted story evidence." actions={<button type="button" className="app-button-secondary" onClick={() => window.dispatchEvent(new CustomEvent(SUPPORT_HELP_EVENT))}>Help</button>} />
    {!paid ? <p className="border-l-2 border-[rgb(var(--border))] pl-4 text-sm leading-6">Free accounts include one Story Advisor turn per week. Scans and saved advisor notes require an active trial, Author, or Architect plan. <Link className="underline" href="/upgrade">View plans</Link></p> : null}
    {book.isLoading ? <p role="status">Loading project context…</p> : null}
    {book.isError ? <div role="alert" className="text-sm leading-7"><p>Project context could not be loaded. Check your access or try again.</p><button type="button" className="app-button-secondary mt-2" onClick={() => void book.refetch()}>Retry project context</button></div> : !book.isLoading && !book.data ? <p role="alert">This project is unavailable. Return to your library to choose a project.</p> : null}
    {!book.isLoading && !book.data ? <Link href="/library" className="app-button-secondary">Open library</Link> : null}
    {noteStatus ? <div className="border-l-2 border-[rgb(var(--border))] pl-4 text-sm leading-7"><p role={failedNote ? "alert" : "status"}>{noteStatus}</p><div className="flex flex-wrap gap-3">{failedNote ? <button type="button" disabled={saving} className="min-h-11 underline" onClick={() => void saveNote(failedNote)}>Retry saving note</button> : null}<Link className="inline-flex min-h-11 items-center underline" href={`/${bookId}/notes`}>Open notes</Link></div></div> : null}
    {book.data ? <>
      <div role="tablist" aria-label="Story Advisor mode" className="flex flex-wrap gap-2 border-b border-[rgb(var(--border))]" onKeyDown={(event) => { if (!paid || !["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return; event.preventDefault(); const next = event.key === "Home" ? "chat" : event.key === "End" ? "scan" : tab === "chat" ? "scan" : "chat"; setTab(next); document.getElementById(`advisor-tab-${next}`)?.focus() }}>
        {[{ id: "chat", label: "Ask advisor" }, ...(paid ? [{ id: "scan", label: "Recommended checks" }] : [])].map((item) => <button key={item.id} type="button" role="tab" id={`advisor-tab-${item.id}`} aria-controls={`advisor-${item.id}-panel`} aria-selected={tab === item.id} tabIndex={tab === item.id ? 0 : -1} className={`min-h-11 border-b-2 px-4 py-3 text-sm font-semibold ${tab === item.id ? "border-[rgb(var(--accent))]" : "advisor-muted border-transparent"}`} onClick={() => setTab(item.id as "chat" | "scan")}>{item.label}{item.id === "chat" && busy ? " · Answering…" : ""}</button>)}
      </div>
      <div hidden={tab !== "chat"} id="advisor-chat-panel" role="tabpanel" aria-labelledby="advisor-tab-chat"><AdvisorConversation bookId={bookId} author={book.data.mode === "author"} paid={paid} isDark={isDark} input={input} setInput={setInput} busy={busy} setBusy={setBusy} onSave={(note) => void saveNote(note)} saving={saving} ready={!book.isError} greeting={greeting.data?.message} /></div>
      {paid ? <div hidden={tab !== "scan"} id="advisor-scan-panel" role="tabpanel" aria-labelledby="advisor-tab-scan"><AdvisorChecks bookId={bookId} userId={userId} isDark={isDark} onAsk={askFromCheck} onSave={(note) => void saveNote(note)} saving={saving} /></div> : null}
    </> : null}
  </div></div>
}
