import { useCallback, useEffect, useRef, useState, type Dispatch, type MutableRefObject, type SetStateAction } from "react"
import { useRouter } from "next/navigation"
import type { Route } from "next"
import { booksApi } from "@/lib/api/books"
import type { VaultNote } from "@/types/book"

export function useVaultNotesAutosave({ bookId, notes, drafts, latestDraftRef, busy, setNotes, setDrafts }: {
  bookId: string
  notes: VaultNote[]
  drafts: Record<string, string>
  latestDraftRef: MutableRefObject<Record<string, string>>
  busy: boolean
  setNotes: Dispatch<SetStateAction<VaultNote[]>>
  setDrafts: Dispatch<SetStateAction<Record<string, string>>>
}) {
  const router = useRouter()
  const timers = useRef<Record<string, ReturnType<typeof setTimeout>>>({})
  const writes = useRef<Record<string, Promise<boolean>>>({})
  const saved = useRef<Record<string, string>>({})
  const [saving, setSaving] = useState<Record<string, boolean>>({})
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [leaving, setLeaving] = useState(false)
  const mounted = useRef(true)
  const navigationPending = useRef(false)
  const [recovered, setRecovered] = useState(false)
  const [backupUnavailable, setBackupUnavailable] = useState(false)
  const storageKey = `lorevia:note-drafts:${bookId}`
  for (const note of notes) saved.current[note.path] = note.content

  const backUpDrafts = useCallback(() => {
    try {
      const pending = Object.fromEntries(Object.entries(latestDraftRef.current).filter(([path, content]) => saved.current[path] !== content))
      if (Object.keys(pending).length) window.sessionStorage.setItem(storageKey, JSON.stringify(pending))
      else window.sessionStorage.removeItem(storageKey)
      if (mounted.current) setBackupUnavailable(false)
    } catch {
      if (mounted.current) setBackupUnavailable(true)
    }
  }, [latestDraftRef, storageKey])

  useEffect(() => {
    try {
      const value: unknown = JSON.parse(window.sessionStorage.getItem(storageKey) ?? "{}")
      if (!value || typeof value !== "object" || Array.isArray(value)) return
      const restored = Object.fromEntries(Object.entries(value).filter(([path, content]) => typeof content === "string" && path in saved.current && content !== saved.current[path])) as Record<string, string>
      if (!Object.keys(restored).length) return
      latestDraftRef.current = { ...restored, ...latestDraftRef.current }
      setDrafts((current) => ({ ...restored, ...current }))
      setRecovered(true)
    } catch { /* Invalid or unavailable tab storage must not prevent editing. */ }
  }, [latestDraftRef, setDrafts, storageKey])

  const cancelTimer = useCallback((path: string) => {
    clearTimeout(timers.current[path])
    delete timers.current[path]
  }, [])

  const saveNote = useCallback((path: string, content: string): Promise<boolean> => {
    cancelTimer(path)
    // Serialize writes per path so a slow older request cannot overwrite a newer draft.
    const previous = writes.current[path] ?? Promise.resolve(true)
    const write = previous.then(async () => {
      const current = latestDraftRef.current[path] ?? content
      if (saved.current[path] === current) {
        if (mounted.current) setErrors((value) => { const next = { ...value }; delete next[path]; return next })
        return true
      }
      if (mounted.current) setSaving((value) => ({ ...value, [path]: true }))
      try {
        const result = await booksApi.saveVaultNote(bookId, { path, content: current })
        saved.current[path] = result.content
        const stillCurrent = latestDraftRef.current[path] === current
        if (stillCurrent) latestDraftRef.current[path] = result.content
        backUpDrafts()
        if (mounted.current) {
          setNotes((value) => value.map((note) => note.path === path ? { ...note, content: result.content, updated_at: result.updated_at ?? note.updated_at } : note))
          setDrafts((value) => stillCurrent ? { ...value, [path]: result.content } : value)
          setErrors((value) => { const next = { ...value }; delete next[path]; return next })
        }
        return true
      } catch {
        if (mounted.current) setErrors((value) => ({ ...value, [path]: `Could not save ${path}. Your draft is still here.` }))
        return false
      } finally {
        if (mounted.current) setSaving((value) => ({ ...value, [path]: false }))
      }
    })
    writes.current[path] = write
    return write
  }, [backUpDrafts, bookId, cancelTimer, latestDraftRef, setDrafts, setNotes])

  const updateDraft = useCallback((path: string, content: string) => {
    latestDraftRef.current[path] = content
    backUpDrafts()
    setDrafts((value) => ({ ...value, [path]: content }))
    cancelTimer(path)
    timers.current[path] = setTimeout(() => void saveNote(path, content), 700)
  }, [backUpDrafts, cancelTimer, latestDraftRef, saveNote, setDrafts])

  // Wait for an in-flight write before a rename/delete, and cancel its pending autosave.
  const settlePath = useCallback(async (path: string) => {
    cancelTimer(path)
    await writes.current[path]
  }, [cancelTimer])

  const forgetPath = useCallback((path: string) => {
    cancelTimer(path)
    delete latestDraftRef.current[path]
    delete saved.current[path]
    delete writes.current[path]
    backUpDrafts()
    setErrors((value) => { const next = { ...value }; delete next[path]; return next })
  }, [backUpDrafts, cancelTimer, latestDraftRef])

  const flushAll = useCallback(async () => {
    const results = await Promise.all(Object.entries(latestDraftRef.current).map(([path, content]) => saveNote(path, content)))
    return results.every(Boolean)
  }, [latestDraftRef, saveNote])

  const dirty = notes.some((note) => drafts[note.path] !== undefined && drafts[note.path] !== note.content)
  const dirtyRef = useRef(dirty)
  dirtyRef.current = dirty
  const busyRef = useRef(busy)
  busyRef.current = busy
  useEffect(() => {
    mounted.current = true
    const activeTimers = timers.current
    function beforeUnload(event: BeforeUnloadEvent) {
      if (!dirtyRef.current && !busyRef.current) return
      event.preventDefault()
      event.returnValue = ""
    }
    window.addEventListener("beforeunload", beforeUnload)
    return () => {
      mounted.current = false
      Object.values(activeTimers).forEach(clearTimeout)
      window.removeEventListener("beforeunload", beforeUnload)
    }
  }, [])

  useEffect(() => {
    function guardLink(event: MouseEvent) {
      if ((!dirtyRef.current && !busy) || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return
      const link = event.target instanceof Element ? event.target.closest<HTMLAnchorElement>("a[href]") : null
      if (!link || link.target === "_blank" || link.hasAttribute("download") || link.getAttribute("href")?.startsWith("#")) return
      const destination = new URL(link.href, window.location.href)
      if (destination.href === window.location.href || destination.origin !== window.location.origin) return
      event.preventDefault()
      event.stopPropagation()
      if (busy || navigationPending.current) return
      navigationPending.current = true
      setLeaving(true)
      void flushAll().then((success) => {
        if (success) router.push(`${destination.pathname}${destination.search}${destination.hash}` as Route)
      }).finally(() => {
        navigationPending.current = false
        if (mounted.current) setLeaving(false)
      })
    }
    document.addEventListener("click", guardLink, true)
    return () => document.removeEventListener("click", guardLink, true)
  }, [busy, flushAll, router])

  return { saveNote, updateDraft, settlePath, forgetPath, flushAll, saving, errors, dirty, leaving, recovered, backupUnavailable }
}
