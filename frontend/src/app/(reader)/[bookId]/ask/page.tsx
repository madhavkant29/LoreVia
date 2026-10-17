"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { useParams, useRouter } from "next/navigation"
import Link from "next/link"
import { booksApi } from "@/lib/api/books"
import { intelligenceApi } from "@/lib/api/intelligence"
import { readerApi } from "@/lib/api/reader"
import { asQueryKey, bookCacheKey, readerCacheKey } from "@/lib/query/cacheKeys"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import { normalizeBookRouteId } from "@/lib/utils/bookRoutes"
import { capture } from "@/lib/analytics/posthog"
import { AskLoreViaWorkspace } from "@/components/reader/AskLoreViaWorkspace"
import { getAskFailureMessage, getAskLoreViaScopeLabel, isAskChapter, parseRecentQuestions, type AskEntry } from "@/lib/utils/askLoreVia"

const QUICK_PROMPTS = ["When did this character last appear?", "How has the relationship between these characters changed?", "Has this character used this ability before?", "Where was this plot thread introduced?"]
const SAVED_QUESTIONS_KEY_PREFIX = "lorevia-ask-recent-questions:v1:"

export default function AskPage() {
  const { bookId } = useParams<{ bookId: string }>()
  return <AskWorkspace key={bookId} bookId={bookId} />
}

function AskWorkspace({ bookId }: { bookId: string }) {
  const router = useRouter()
  const { theme } = usePreferencesStore()
  const [input, setInput] = useState("")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [history, setHistory] = useState<AskEntry[]>([])
  const [savedQuestions, setSavedQuestions] = useState<string[]>([])
  const [storageError, setStorageError] = useState(false)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  const activeRequest = useRef<AbortController | null>(null)
  const storageKey = `${SAVED_QUESTIONS_KEY_PREFIX}${normalizeBookRouteId(bookId)}`
  const book = useQuery({ queryKey: asQueryKey(bookCacheKey(bookId, "detail")), queryFn: () => booksApi.get(bookId), staleTime: 20_000 })
  const progress = useQuery({ queryKey: asQueryKey(readerCacheKey(bookId, "progress")), queryFn: () => readerApi.getProgress(bookId), staleTime: 12_000, enabled: book.data?.mode === "reader" })
  const currentChapter = isAskChapter(progress.data?.current_chapter) ? progress.data!.current_chapter : 0
  const ready = book.data?.mode === "reader" && !!progress.data && currentChapter > 0 && !book.isError && !progress.isError
  const scopeLabel = ready ? getAskLoreViaScopeLabel(book.data?.mode, currentChapter) : "Chapter context unavailable"

  useEffect(() => {
    try { setSavedQuestions(parseRecentQuestions(window.localStorage.getItem(storageKey) ?? window.localStorage.getItem(`${SAVED_QUESTIONS_KEY_PREFIX}${bookId}`))) }
    catch { setStorageError(true) }
  }, [storageKey, bookId])
  useEffect(() => () => { activeRequest.current?.abort(); activeRequest.current = null }, [])
  useEffect(() => {
    if (!input.trim() && !loading) return
    const unload = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = "" }
    const navigate = (event: MouseEvent) => {
      if (event.target instanceof Element && event.target.closest("a[href]") && !window.confirm("Leave this question workspace? Your draft and any unfinished answer will be lost.")) { event.preventDefault(); event.stopPropagation() }
    }
    window.addEventListener("beforeunload", unload)
    document.addEventListener("click", navigate, true)
    return () => { window.removeEventListener("beforeunload", unload); document.removeEventListener("click", navigate, true) }
  }, [input, loading])
  useEffect(() => { if (book.data?.mode === "author") router.replace(`/${bookId}/advisor?mode=ask`) }, [book.data?.mode, bookId, router])

  const ask = useCallback(async (text: string) => {
    const question = text.trim()
    if (!question || activeRequest.current || !ready) return
    if (input.trim() && input.trim() !== question && !window.confirm("Replace the question you are drafting with this retry?")) return
    const controller = new AbortController()
    activeRequest.current = controller
    setInput(""); setError(null); setLoading(true)
    setHistory((previous) => [...previous, { question, answer: "", citations: [], chapter: currentChapter, status: "streaming" }])
    capture("ask_submitted", { book_id: bookId, chapter: currentChapter, question_len: question.length, mode: "reader" })
    const update = (changes: Partial<AskEntry>, delta?: string) => {
      if (activeRequest.current !== controller) return
      setHistory((previous) => previous.map((entry, index) => index === previous.length - 1 ? { ...entry, ...changes, ...(delta ? { answer: entry.answer + delta } : {}) } : entry))
    }
    try {
      const response = await intelligenceApi.answerStream(bookId, question, currentChapter, { signal: controller.signal, onDelta: (content) => { if (!controller.signal.aborted) update({}, content) } })
      if (controller.signal.aborted) throw new Error("Stopped")
      if (!response.answer?.trim()) throw new Error("Empty answer")
      update({ answer: response.answer, citations: response.citations ?? [], status: "complete" })
      if (activeRequest.current === controller) setSavedQuestions((current) => {
        const next = [question, ...current.filter((item) => item !== question)].slice(0, 6)
        try { window.localStorage.setItem(storageKey, JSON.stringify(next)) } catch { setStorageError(true) }
        return next
      })
    } catch (err: unknown) {
      if (activeRequest.current !== controller) return
      const failure = getAskFailureMessage(err, controller.signal.aborted)
      update({ status: controller.signal.aborted ? "stopped" : "failed", error: failure })
      setInput(question); setError(failure)
    } finally {
      if (activeRequest.current === controller) { activeRequest.current = null; setLoading(false) }
    }
  }, [bookId, currentChapter, ready, storageKey, input])

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); void ask(input) }
  }
  const clearRecent = () => {
    try { window.localStorage.removeItem(storageKey); window.localStorage.removeItem(`${SAVED_QUESTIONS_KEY_PREFIX}${bookId}`); setSavedQuestions([]); setStorageError(false) }
    catch { setStorageError(true) }
  }
  if (book.data?.mode === "author") return <main className="grid min-h-[50vh] place-items-center px-6" role="status"><p className="text-sm">Opening the manuscript question view in Story Advisor…</p></main>

  const contextNotice = !book.data ? book.isError ? <div role="alert">Manuscript details could not be loaded. <button type="button" className="underline" disabled={book.isFetching} onClick={() => void book.refetch()}>Retry manuscript</button></div> : <p role="status">Loading manuscript context…</p> : book.isError ? <div role="alert">Manuscript access could not be refreshed. <button type="button" className="underline" disabled={book.isFetching} onClick={() => void book.refetch()}>Retry manuscript</button></div> : progress.isError ? <div role="alert">Reading progress could not be loaded. <button type="button" className="underline" disabled={progress.isFetching} onClick={() => void progress.refetch()}>Retry reading progress</button></div> : !progress.data ? <p role="status">Loading reading progress…</p> : !currentChapter ? <p>No reading chapter is available yet. <Link className="underline" href={`/${bookId}/chapters`}>Choose a chapter</Link> to establish your question context.</p> : null
  return <AskLoreViaWorkspace bookId={bookId} bookTitle={book.data?.title} mode={book.data?.mode} currentChapter={currentChapter} scopeLabel={scopeLabel} history={history} input={input} loading={loading} error={error} isDark={theme === "dark"} inputRef={inputRef} bottomRef={bottomRef} onInputChange={setInput} onSubmit={ask} onKeyDown={handleKeyDown} quickPrompts={QUICK_PROMPTS} recentQuestions={savedQuestions} onClearRecent={clearRecent} storageError={storageError} contextNotice={contextNotice} disabled={!ready} onStop={() => activeRequest.current?.abort()} />
}
