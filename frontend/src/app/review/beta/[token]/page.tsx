"use client"

import Image from "next/image"
import { useParams } from "next/navigation"
import { useEffect, useRef, useState } from "react"
import { BookOpen, CheckCircle2, ChevronLeft, ChevronRight, Heart, MessageSquare, Send, TriangleAlert } from "lucide-react"

import { betaReadsApi } from "@/lib/api/betaReads"
import type { BetaReadGuestReview } from "@/types/betaRead"

export default function GuestBetaReviewPage() {
  const params = useParams<{ token: string }>()
  const token = params.token
  const [review, setReview] = useState<BetaReadGuestReview | null>(null)
  const [error, setError] = useState("")
  const [busy, setBusy] = useState(false)
  const [comment, setComment] = useState("")
  const [chapterNumber, setChapterNumber] = useState<number | null>(null)
  const [finalFeedback, setFinalFeedback] = useState("")
  const [rating, setRating] = useState(4)
  const [submitted, setSubmitted] = useState(false)
  const [questionAnswers, setQuestionAnswers] = useState<Record<string, string>>({})
  const markedChapters = useRef(new Set<number>())

  useEffect(() => {
    if (!token) return
    betaReadsApi.getGuestReview(token).then((payload) => {
      setReview(payload)
      setChapterNumber(payload.chapters[0]?.number ?? null)
    }).catch(() => setError("This review link is invalid, expired, or was revoked."))
  }, [token])

  useEffect(() => {
    if (!review || !chapterNumber || markedChapters.current.has(chapterNumber)) return
    markedChapters.current.add(chapterNumber)
    void betaReadsApi.markGuestChapterRead(token, chapterNumber).catch(() => {
      markedChapters.current.delete(chapterNumber)
    })
  }, [chapterNumber, review, token])

  const addSignal = async (kind: string, body?: string, explicitChapterNumber?: number) => {
    const targetChapter = explicitChapterNumber ?? chapterNumber
    if (!review || !targetChapter) return
    setBusy(true)
    setError("")
    try {
      const payload = await betaReadsApi.createGuestFeedbackItem(token, {
        kind,
        chapterNumber: targetChapter,
        body: body || `${kind} moment in Chapter ${targetChapter}`,
        anchorText: kind === "chapter_comment" ? null : body || `${kind} moment`,
      })
      setReview((current) => current ? { ...current, ...payload } : current)
      setComment("")
    } catch {
      setError("That note could not be saved. Check your connection and try again.")
    } finally {
      setBusy(false)
    }
  }

  const submit = async () => {
    if (finalFeedback.trim().length < 3) return
    setBusy(true)
    setError("")
    try {
      await betaReadsApi.submitGuestReview(token, finalFeedback, rating)
      setSubmitted(true)
    } catch {
      setError("Finish the requested notes before submitting, then try again.")
    } finally {
      setBusy(false)
    }
  }

  const saveQuestionAnswer = async (questionId: string) => {
    const answer = questionAnswers[questionId]?.trim()
    if (!answer) return
    setBusy(true)
    setError("")
    try {
      const payload = await betaReadsApi.createGuestFeedbackItem(token, {
        kind: "answer",
        questionId,
        body: answer,
      })
      setReview((current) => current ? { ...current, ...payload } : current)
      setQuestionAnswers((current) => ({ ...current, [questionId]: "" }))
    } catch {
      setError("That answer could not be saved. Check your connection and try again.")
    } finally {
      setBusy(false)
    }
  }

  const selectedIndex = review?.chapters.findIndex((chapter) => chapter.number === chapterNumber) ?? -1
  const selectedChapter = selectedIndex >= 0 ? review?.chapters[selectedIndex] : review?.chapters[0]

  if (error && !review) {
    return <main className="mx-auto flex min-h-screen max-w-xl items-center px-6"><div className="rounded-3xl border border-amber-200 bg-amber-50 p-8 text-amber-950"><TriangleAlert className="mb-4 h-7 w-7" /><h1 className="text-2xl font-semibold">Review unavailable</h1><p className="mt-2 text-sm">{error}</p></div></main>
  }
  if (!review) return <main className="grid min-h-screen place-items-center text-sm text-gray-500">Opening your review copy…</main>
  if (submitted) return <main className="mx-auto flex min-h-screen max-w-xl items-center px-6"><div className="w-full rounded-3xl border border-emerald-200 bg-emerald-50 p-8 text-center"><CheckCircle2 className="mx-auto mb-4 h-10 w-10 text-emerald-600" /><h1 className="text-2xl font-semibold">Feedback delivered</h1><p className="mt-2 text-sm text-emerald-900">Thank you. The author can now fold your notes into their revision plan.</p></div></main>

  return (
    <main className="min-h-screen bg-stone-50 text-gray-950">
      <header className="sticky top-0 z-10 border-b border-gray-200 bg-white/95 px-4 py-3 backdrop-blur">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-4">
          <Image src="/logoandtext.png" alt="LoreVia" width={146} height={40} className="h-8 w-auto" />
          <span className="text-xs font-medium text-gray-500">Private review copy · expires {new Date(review.assignment.expires_at).toLocaleDateString()}</span>
        </div>
      </header>
      <div className="mx-auto grid max-w-5xl gap-6 px-4 py-8 lg:grid-cols-[minmax(0,1fr)_320px]">
        <section>
          <div className="mb-5"><p className="text-xs font-semibold uppercase tracking-[0.2em] text-violet-700">Beta review</p><h1 className="mt-1 text-3xl font-semibold">{review.assignment.book_title}</h1><p className="mt-2 text-sm text-gray-600">Read at your pace. Use the quick signals as moments happen; they save immediately.</p></div>
          {selectedChapter ? <div className="space-y-4">
            <article className="rounded-3xl border border-gray-200 bg-white p-6 shadow-sm">
              <div className="mb-5 flex items-center gap-2"><BookOpen className="h-4 w-4 text-violet-600" /><h2 className="text-xl font-semibold">{selectedChapter.title}</h2></div>
              <div className="whitespace-pre-wrap font-serif text-[17px] leading-8 text-gray-800">{selectedChapter.text}</div>
              <div className="mt-6 flex flex-wrap gap-2">
                <button disabled={busy} onClick={() => void addSignal("confusing", undefined, selectedChapter.number)} className="rounded-full border px-3 py-1.5 text-xs font-medium hover:bg-amber-50">Confusing</button>
                <button disabled={busy} onClick={() => void addSignal("boring", undefined, selectedChapter.number)} className="rounded-full border px-3 py-1.5 text-xs font-medium hover:bg-blue-50">Slow</button>
                <button disabled={busy} onClick={() => void addSignal("favorite", undefined, selectedChapter.number)} className="inline-flex items-center gap-1 rounded-full border px-3 py-1.5 text-xs font-medium hover:bg-rose-50"><Heart className="h-3 w-3" /> Favorite</button>
              </div>
            </article>
            <nav className="flex items-center justify-between" aria-label="Review chapters">
              <button type="button" disabled={selectedIndex <= 0} onClick={() => setChapterNumber(review.chapters[selectedIndex - 1].number)} className="inline-flex items-center gap-1 rounded-xl border bg-white px-3 py-2 text-sm font-medium disabled:opacity-30"><ChevronLeft className="h-4 w-4" /> Previous</button>
              <span className="text-xs font-medium text-gray-500">{selectedIndex + 1} of {review.chapters.length}</span>
              <button type="button" disabled={selectedIndex >= review.chapters.length - 1} onClick={() => setChapterNumber(review.chapters[selectedIndex + 1].number)} className="inline-flex items-center gap-1 rounded-xl border bg-white px-3 py-2 text-sm font-medium disabled:opacity-30">Next <ChevronRight className="h-4 w-4" /></button>
            </nav>
          </div> : null}
        </section>
        <aside className="space-y-4 lg:sticky lg:top-20 lg:self-start">
          <div className="rounded-3xl border border-gray-200 bg-white p-5 shadow-sm">
            <h2 className="flex items-center gap-2 font-semibold"><MessageSquare className="h-4 w-4" /> Add a note</h2>
            <p className="mt-1 text-xs text-gray-500">Chapter {chapterNumber ?? "—"}</p>
            <textarea value={comment} onChange={(event) => setComment(event.target.value)} rows={4} placeholder="What worked, what did not, or what you expected…" className="mt-3 w-full rounded-2xl border border-gray-200 p-3 text-sm outline-none focus:border-violet-400" />
            <button disabled={busy || !comment.trim()} onClick={() => void addSignal("chapter_comment", comment)} className="mt-2 w-full rounded-xl bg-gray-950 px-4 py-2 text-sm font-semibold text-white disabled:opacity-40">Save note</button>
          </div>
          {review.author_questions.length > 0 && <div className="rounded-3xl border border-gray-200 bg-white p-5 shadow-sm"><h2 className="font-semibold">Author questions</h2><div className="mt-3 space-y-4">{review.author_questions.map((question) => <div key={question.id}><label className="text-sm font-medium text-gray-700" htmlFor={`question-${question.id}`}>{question.prompt}</label><textarea id={`question-${question.id}`} value={questionAnswers[question.id] ?? ""} onChange={(event) => setQuestionAnswers((current) => ({ ...current, [question.id]: event.target.value }))} rows={3} className="mt-2 w-full rounded-xl border border-gray-200 p-3 text-sm" /><button type="button" disabled={busy || !(questionAnswers[question.id] ?? "").trim()} onClick={() => void saveQuestionAnswer(question.id)} className="mt-2 rounded-xl border px-3 py-2 text-xs font-semibold disabled:opacity-40">Save answer</button></div>)}</div></div>}
          <div className="rounded-3xl border border-violet-200 bg-violet-50 p-5">
            <h2 className="font-semibold">Finish review</h2>
            <textarea value={finalFeedback} onChange={(event) => setFinalFeedback(event.target.value)} rows={5} placeholder="Your overall reaction…" className="mt-3 w-full rounded-2xl border border-violet-200 bg-white p-3 text-sm outline-none" />
            <label className="mt-3 block text-xs font-medium">Overall rating</label>
            <select value={rating} onChange={(event) => setRating(Number(event.target.value))} className="mt-1 w-full rounded-xl border border-violet-200 bg-white p-2 text-sm">{[5, 4, 3, 2, 1].map((value) => <option key={value} value={value}>{value} / 5</option>)}</select>
            <button disabled={busy || finalFeedback.trim().length < 3} onClick={() => void submit()} className="mt-3 inline-flex w-full items-center justify-center gap-2 rounded-xl bg-violet-700 px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-40"><Send className="h-4 w-4" /> Submit feedback</button>
            {error && <p className="mt-2 text-xs text-red-700">{error}</p>}
          </div>
        </aside>
      </div>
    </main>
  )
}
