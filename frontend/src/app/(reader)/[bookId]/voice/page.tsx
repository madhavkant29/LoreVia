"use client"

import { useQuery } from "@tanstack/react-query"
import dynamic from "next/dynamic"
import { useEffect, useMemo, useState } from "react"
import Link from "next/link"
import { useParams } from "next/navigation"

import { booksApi } from "@/lib/api/books"
import { intelligenceApi } from "@/lib/api/intelligence"
import { asQueryKey, bookCacheKey, readerCacheKey } from "@/lib/query/cacheKeys"
import { readerApi } from "@/lib/api/reader"
import { saveContextualVaultNote } from "@/lib/utils/notes"
import { getApiErrorDetail } from "@/lib/utils/apiErrors"
import {
  buildVoiceIssueNote,
  buildVoiceReviewNote,
  buildVoiceReviewSceneDraft,
  defaultVoiceSceneFolder,
} from "@/lib/utils/voiceWorkspace"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import type { Book, ManuscriptWorkspaceTree } from "@/types/book"
import type { VoiceConsistencyIssue, VoiceConsistencyMatch, VoiceConsistencyReview } from "@/types/intelligence"
import type { ChapterListResponse } from "@/types/reader"

const EMPTY_CHAPTERS: ChapterListResponse["chapters"] = []

const AuthorToolsNav = dynamic(
  () => import("@/components/layout/AuthorToolsNav").then((module) => module.AuthorToolsNav),
  {
    ssr: false,
    loading: () => <div className="rounded-[1.8rem] border border-dashed p-8" />,
  }
)

export default function VoiceConsistencyPage() {
  const { bookId } = useParams<{ bookId: string }>()
  const { theme } = usePreferencesStore()
  const isDark = theme === "dark"

  const [selectedChapter, setSelectedChapter] = useState<number | null>(null)
  const [chapterTitle, setChapterTitle] = useState("")
  const [text, setText] = useState("")
  const [reviewLoading, setReviewLoading] = useState(false)
  const [saveStatus, setSaveStatus] = useState<string | null>(null)
  const [reviewError, setReviewError] = useState<string | null>(null)
  const [review, setReview] = useState<VoiceConsistencyReview | null>(null)
  const [voiceCharacters, setVoiceCharacters] = useState<string[]>([])
  const [voiceMatches, setVoiceMatches] = useState<VoiceConsistencyMatch[]>([])

  const { data: book = null, isLoading: bookLoading } = useQuery<Book | null>({
    queryKey: asQueryKey(bookCacheKey(bookId, "detail")),
    queryFn: () => booksApi.get(bookId),
  })
  const { data: chapterList = null, isLoading: chapterListLoading } = useQuery<ChapterListResponse | null>({
    queryKey: asQueryKey(readerCacheKey(bookId, "chapters")),
    queryFn: () => readerApi.getChapterList(bookId),
  })
  const {
    data: workspaceTree = null,
    isLoading: workspaceTreeLoading,
    refetch: refetchWorkspaceTree,
  } = useQuery<ManuscriptWorkspaceTree | null>({
    queryKey: asQueryKey(bookCacheKey(bookId, "workspace-tree")),
    queryFn: () => booksApi.getWorkspaceTree(bookId),
  })
  const { data: chapterData = null, isLoading: chapterLoading } = useQuery({
    queryKey: selectedChapter !== null ? asQueryKey(readerCacheKey(bookId, `chapter:${selectedChapter}`)) : ["voice:chapter:none"],
    queryFn: () => readerApi.getChapter(bookId, selectedChapter as number),
    enabled: selectedChapter !== null,
  })
  const loading = bookLoading || chapterListLoading || workspaceTreeLoading

  const chapterOptions = useMemo(() => chapterList?.chapters ?? EMPTY_CHAPTERS, [chapterList?.chapters])
  const existingScenePaths = useMemo(
    () => (workspaceTree?.scene_groups ?? []).flatMap((group) => group.scenes.map((scene) => scene.path)),
    [workspaceTree]
  )
  const savedVoiceSceneCount = useMemo(
    () => existingScenePaths.filter((path) => path.startsWith("scenes/voice/")).length,
    [existingScenePaths]
  )
  const existingVoiceNotes = useMemo(
    () => (workspaceTree?.note_paths ?? []).filter((path) => path.toLowerCase().includes("/voice/") || path.toLowerCase().startsWith("story advisor/voice")),
    [workspaceTree]
  )

  useEffect(() => {
    const preferredChapter = chapterList?.current_chapter
      ?? chapterList?.chapters[chapterList.chapters.length - 1]?.number
      ?? null
    if (preferredChapter === null) {
      setSelectedChapter(null)
      return
    }
    setSelectedChapter((current) => {
      if (current && chapterOptions.some((chapter) => chapter.number === current)) return current
      return preferredChapter
    })
  }, [chapterList, chapterOptions])

  useEffect(() => {
    if (selectedChapter === null) {
      setChapterTitle("")
      setText("")
      setReview(null)
      setReviewError(null)
      setVoiceCharacters([])
      setVoiceMatches([])
      return
    }

    const chapterMeta = chapterOptions.find((item) => item.number === selectedChapter)
    if (chapterData) {
      setChapterTitle(chapterData.chapter_title || chapterMeta?.title || `Chapter ${selectedChapter}`)
      setText(chapterData.text_content || "")
    } else if (!chapterLoading) {
      setChapterTitle(chapterMeta?.title || `Chapter ${selectedChapter}`)
      setText("")
    }

    setReview(null)
    setReviewError(null)
    setVoiceCharacters([])
    setVoiceMatches([])
    setSaveStatus(null)
  }, [chapterData, chapterLoading, chapterOptions, selectedChapter])

  const runReview = async () => {
    const trimmed = text.trim()
    if (!trimmed) return
    setReviewLoading(true)
    setSaveStatus(null)
    setReviewError(null)
    try {
      const result = await intelligenceApi.voiceConsistencyReview(bookId, trimmed, selectedChapter ?? undefined)
      setReview(result.review)
      setVoiceCharacters(result.characters_reviewed)
      setVoiceMatches(result.character_matches ?? [])
    } catch (error) {
      setReview(null)
      setVoiceCharacters([])
      setVoiceMatches([])
      setReviewError(getApiErrorDetail(error) ?? "Could not run the voice review right now. Please try again.")
    } finally {
      setReviewLoading(false)
    }
  }

  const saveIssueNote = async (issue: VoiceConsistencyIssue) => {
    const note = buildVoiceIssueNote(issue)
    const saved = await saveContextualVaultNote({
      bookId,
      title: note.title,
      content: note.body,
      context: "story_advisor",
      folderSegments: selectedChapter ? ["Voice", `Chapter ${selectedChapter}`] : ["Voice"],
    })
    setSaveStatus(`Saved voice note to ${saved.path}`)
    await refetchWorkspaceTree()
  }

  const saveReviewNote = async () => {
    if (!review) return
    const note = buildVoiceReviewNote({
      chapterNumber: selectedChapter,
      chapterTitle,
      overallVerdict: review.overall_verdict,
      charactersReviewed: voiceCharacters,
      issues: review.issues,
      matches: voiceMatches,
    })
    const saved = await saveContextualVaultNote({
      bookId,
      title: note.title,
      content: note.body,
      context: "story_advisor",
      folderSegments: selectedChapter ? ["Voice", `Chapter ${selectedChapter}`] : ["Voice"],
    })
    setSaveStatus(`Saved full review to ${saved.path}`)
    await refetchWorkspaceTree()
  }

  const saveReviewScene = async () => {
    if (!review) return
    const sceneDraft = buildVoiceReviewSceneDraft({
      chapterNumber: selectedChapter,
      chapterTitle,
      overallVerdict: review.overall_verdict,
      sourceText: text,
      issues: review.issues,
      existingPaths: existingScenePaths,
    })
    const saved = await booksApi.saveScene(bookId, sceneDraft)
    setSaveStatus(`Saved review scene to ${saved.path}`)
    await refetchWorkspaceTree()
  }

  if (loading) {
    return <div className={`min-h-screen px-6 py-20 ${isDark ? "bg-black text-slate-400" : "bg-stone-50 text-stone-500"}`}>Loading voice workspace...</div>
  }

  return (
    <div className={`min-h-screen ${isDark ? "bg-[linear-gradient(180deg,#05030a_0%,#0a0f18_55%,#111827_100%)] text-slate-100" : "bg-[linear-gradient(180deg,#f9f1ea_0%,#f5f2fb_45%,#eef5fb_100%)] text-stone-950"}`}>
      <div className="mx-auto max-w-[108rem] px-4 pb-20 pt-6 sm:px-6 lg:px-8">
        <div className="grid gap-6 xl:grid-cols-[17rem_minmax(0,1fr)]">
          <AuthorToolsNav
            bookId={bookId}
            active="voice"
            isDark={isDark}
            bookData={book}
            title="Voice consistency"
            description="Run a dedicated voice pass, then save the results back into your shared notes and scene workspaces."
          />

          <div className="space-y-6">
            <section className={`rounded-[1.8rem] border p-6 ${isDark ? "border-white/10 bg-white/[0.04]" : "border-white/70 bg-white/88"}`}>
              <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
                <div className="max-w-3xl">
                  <p className={`text-[11px] font-semibold uppercase tracking-[0.28em] ${isDark ? "text-rose-300" : "text-rose-700"}`}>Voice workspace</p>
                  <h1 className={`mt-2 font-serif text-4xl ${isDark ? "text-white" : "text-stone-950"}`}>{book?.title || "Book"} voice consistency</h1>
                  <p className={`mt-3 text-sm leading-7 ${isDark ? "text-slate-300" : "text-stone-600"}`}>
                    Review one chapter or passage at a time, save issues into your vault notes, and push snapshots into the scenes tree so the rest of the workspace can reuse them.
                  </p>
                </div>
                <div className="flex flex-wrap gap-3">
                  <Link href={`/${bookId}/notes`} className={`rounded-full px-4 py-2 text-sm font-semibold ${isDark ? "bg-white/10 text-slate-100" : "bg-white text-stone-800"}`}>
                    Open notes
                  </Link>
                  <Link href={`/${bookId}/scenes`} className={`rounded-full px-4 py-2 text-sm font-semibold ${isDark ? "bg-white/10 text-slate-100" : "bg-white text-stone-800"}`}>
                    Open scenes
                  </Link>
                  <Link href={`/${bookId}/manuscript`} className={`rounded-full px-4 py-2 text-sm font-semibold ${isDark ? "bg-rose-500 text-white" : "bg-stone-900 text-white"}`}>
                    Open manuscript
                  </Link>
                </div>
              </div>

              <div className="mt-6 grid gap-4 lg:grid-cols-[18rem_minmax(0,1fr)]">
                <div className={`rounded-[1.3rem] border p-4 ${isDark ? "border-white/10 bg-black/20" : "border-stone-200 bg-stone-50/80"}`}>
                  <label className="block text-sm">
                    <span className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-500"}`}>Chapter</span>
                    <select
                      value={selectedChapter ?? ""}
                      onChange={(event) => setSelectedChapter(event.target.value ? Number(event.target.value) : null)}
                      className={`mt-3 w-full rounded-[0.95rem] border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-[#0b1220] text-slate-100" : "border-stone-200 bg-white text-stone-900"}`}
                    >
                      <option value="">Paste custom passage</option>
                      {chapterOptions.map((chapter) => (
                        <option key={chapter.number} value={chapter.number}>
                          Chapter {chapter.number}{chapter.title ? ` - ${chapter.title}` : ""}
                        </option>
                      ))}
                    </select>
                  </label>

                  <div className="mt-5 space-y-3">
                    <div className={`rounded-[1rem] border px-4 py-3 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-stone-200 bg-white"}`}>
                      <p className={`text-[11px] font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Shared outputs</p>
                      <p className="mt-2 text-sm">{existingVoiceNotes.length} saved voice note{existingVoiceNotes.length === 1 ? "" : "s"}</p>
                      <p className="mt-1 text-sm">{savedVoiceSceneCount} voice scene snapshot{savedVoiceSceneCount === 1 ? "" : "s"}</p>
                      <p className={`mt-2 text-xs leading-5 ${isDark ? "text-slate-500" : "text-stone-500"}`}>These counts update when you save a review note or scene snapshot.</p>
                    </div>
                    <div className={`rounded-[1rem] border px-4 py-3 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-stone-200 bg-white"}`}>
                      <p className={`text-[11px] font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Latest review</p>
                      {review ? (
                        <>
                          <p className="mt-2 text-sm">{review.issues.length} flagged issue{review.issues.length === 1 ? "" : "s"}</p>
                          <p className="mt-1 text-sm">{voiceCharacters.length} character baseline{voiceCharacters.length === 1 ? "" : "s"} reviewed</p>
                        </>
                      ) : (
                        <p className={`mt-2 text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>Run a voice review to compare this passage against your manuscript baselines.</p>
                      )}
                    </div>
                    <div className={`rounded-[1rem] border px-4 py-3 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-stone-200 bg-white"}`}>
                      <p className={`text-[11px] font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Scene folder</p>
                      <p className="mt-2 text-sm">{defaultVoiceSceneFolder(selectedChapter)}</p>
                    </div>
                  </div>
                </div>

                <div className={`rounded-[1.3rem] border p-4 ${isDark ? "border-white/10 bg-black/20" : "border-stone-200 bg-white/90"}`}>
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Source passage</p>
                      <h2 className={`mt-2 text-2xl font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>{chapterTitle || "Custom passage"}</h2>
                    </div>
                    <button
                      type="button"
                      onClick={() => void runReview()}
                      disabled={reviewLoading || !text.trim()}
                      className="rounded-full bg-[linear-gradient(135deg,#f43f5e,#e11d48)] px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
                    >
                      {reviewLoading ? "Running..." : "Run voice review"}
                    </button>
                  </div>

                  <textarea
                    value={text}
                    onChange={(event) => setText(event.target.value)}
                    placeholder="Paste dialogue or load a chapter to review its voice consistency."
                    className={`mt-4 min-h-[18rem] w-full rounded-[1rem] border px-4 py-3 text-sm leading-7 outline-none ${isDark ? "border-white/10 bg-[#0b1220] text-slate-100" : "border-stone-200 bg-white text-stone-900"}`}
                  />
                  {reviewError ? (
                    <p className={`mt-3 rounded-[0.95rem] border px-3 py-2 text-sm ${isDark ? "border-rose-500/30 bg-rose-500/10 text-rose-200" : "border-rose-200 bg-rose-50 text-rose-700"}`}>
                      {reviewError}
                    </p>
                  ) : null}
                  {saveStatus ? <p className={`mt-3 text-sm ${isDark ? "text-emerald-300" : "text-emerald-700"}`}>{saveStatus}</p> : null}
                </div>
              </div>
            </section>

            <section className="grid gap-5 xl:grid-cols-[minmax(0,1.25fr)_minmax(20rem,0.9fr)]">
              <div className={`rounded-[1.8rem] border p-5 ${isDark ? "border-white/10 bg-white/[0.04]" : "border-white/70 bg-white/86"}`}>
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className={`text-[11px] font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Review result</p>
                    <h2 className={`mt-2 text-2xl font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>Character voice consistency</h2>
                  </div>
                  {review ? (
                    <div className="flex flex-wrap gap-2">
                      <button type="button" onClick={() => void saveReviewNote()} className={`rounded-full px-4 py-2 text-sm font-semibold ${isDark ? "bg-white/10 text-slate-100" : "bg-stone-100 text-stone-800"}`}>
                        Save review note
                      </button>
                      <button type="button" onClick={() => void saveReviewScene()} className={`rounded-full px-4 py-2 text-sm font-semibold ${isDark ? "bg-rose-500 text-white" : "bg-rose-600 text-white"}`}>
                        Save as scene
                      </button>
                    </div>
                  ) : null}
                </div>

                {!review ? (
                  <p className={`mt-4 text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>Run a review to compare chapter dialogue against established character voice baselines.</p>
                ) : (
                  <div className="mt-4 space-y-4">
                    <div className={`rounded-[1.2rem] border p-4 ${isDark ? "border-white/10 bg-black/20" : "border-stone-200 bg-stone-50/80"}`}>
                      <p className={`text-sm font-medium ${isDark ? "text-white" : "text-stone-900"}`}>{review.overall_verdict}</p>
                      {voiceCharacters.length > 0 ? (
                        <p className={`mt-2 text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>Reviewed: {voiceCharacters.join(", ")}</p>
                      ) : null}
                    </div>

                    {review.issues.length > 0 ? review.issues.map((issue, index) => (
                      <div key={`${issue.character_name}-${issue.title}-${index}`} className={`rounded-[1.2rem] border p-4 ${isDark ? "border-rose-500/20 bg-rose-500/10" : "border-rose-200 bg-rose-50"}`}>
                        <div className="flex flex-wrap items-start justify-between gap-3">
                          <div className="flex-1">
                            <div className="flex flex-wrap items-center gap-2">
                              <p className="text-sm font-semibold">{issue.character_name}: {issue.title}</p>
                              <span className={`rounded-full px-2 py-1 text-[10px] uppercase tracking-[0.16em] ${isDark ? "bg-white/10 text-slate-300" : "bg-white text-stone-600"}`}>{issue.severity}</span>
                            </div>
                            <p className="mt-2 text-sm leading-6">{issue.description}</p>
                            {issue.evidence ? <p className="mt-2 text-xs opacity-80">Evidence: {issue.evidence}</p> : null}
                            {issue.suggestion ? <p className="mt-2 text-xs opacity-90">Suggestion: {issue.suggestion}</p> : null}
                          </div>
                          <button
                            type="button"
                            onClick={() => void saveIssueNote(issue)}
                            className={`rounded-full px-3 py-1.5 text-[11px] font-semibold transition ${isDark ? "bg-white/10 text-slate-200 hover:bg-white/20" : "bg-white text-stone-700 hover:bg-stone-100"}`}
                          >
                            Save note
                          </button>
                        </div>
                      </div>
                    )) : (
                      <p className={`rounded-[1.2rem] border px-4 py-4 text-sm ${isDark ? "border-emerald-500/20 bg-emerald-500/10 text-emerald-200" : "border-emerald-200 bg-emerald-50 text-emerald-700"}`}>
                        No character voice issues were flagged in this pass.
                      </p>
                    )}
                  </div>
                )}
              </div>

              <div className="space-y-5">
                <section className={`rounded-[1.8rem] border p-5 ${isDark ? "border-white/10 bg-white/[0.04]" : "border-white/70 bg-white/86"}`}>
                  <p className={`text-[11px] font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Match scores</p>
                  {!voiceMatches.length ? (
                    <p className={`mt-4 text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>Scores appear here after a review runs.</p>
                  ) : (
                    <div className="mt-4 space-y-3">
                      {voiceMatches.map((match) => (
                        <div key={match.character_name} className={`rounded-[1rem] border px-4 py-3 text-sm ${match.match_score >= 70 ? isDark ? "border-emerald-500/20 bg-emerald-500/10" : "border-emerald-200 bg-emerald-50" : isDark ? "border-amber-500/20 bg-amber-500/10" : "border-amber-200 bg-amber-50"}`}>
                          <div className="flex items-center justify-between gap-3">
                            <p className="font-semibold">{match.character_name}</p>
                            <span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${isDark ? "bg-white/10 text-slate-200" : "bg-white text-stone-700"}`}>{match.match_score}% match</span>
                          </div>
                          <p className="mt-2 text-xs opacity-80">Baseline {match.baseline_sample_size} samples | current passage {match.sample_dialogue_count} excerpts</p>
                          {match.strongest_signals.length > 0 ? <p className="mt-2 text-xs opacity-90">{match.strongest_signals.join(". ")}.</p> : null}
                          {match.closest_other_character ? <p className="mt-2 text-xs opacity-80">Closest alternate voice: {match.closest_other_character}{typeof match.closest_other_score === "number" ? ` (${match.closest_other_score}% match)` : ""}</p> : null}
                        </div>
                      ))}
                    </div>
                  )}
                </section>

                <section className={`rounded-[1.8rem] border p-5 ${isDark ? "border-white/10 bg-white/[0.04]" : "border-white/70 bg-white/86"}`}>
                  <p className={`text-[11px] font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Workspace links</p>
                  <div className="mt-4 space-y-3 text-sm">
                    <Link href={`/${bookId}/notes`} className={`block rounded-[1rem] border px-4 py-3 ${isDark ? "border-white/10 bg-black/20 hover:bg-white/[0.06]" : "border-stone-200 bg-stone-50 hover:bg-white"}`}>
                      Voice notes open in the shared notes workspace.
                    </Link>
                    <Link href={`/${bookId}/scenes`} className={`block rounded-[1rem] border px-4 py-3 ${isDark ? "border-white/10 bg-black/20 hover:bg-white/[0.06]" : "border-stone-200 bg-stone-50 hover:bg-white"}`}>
                      Voice review snapshots live in the scenes tree under <span className="font-semibold">{defaultVoiceSceneFolder(selectedChapter)}</span>.
                    </Link>
                  </div>
                </section>
              </div>
            </section>
          </div>
        </div>
      </div>
    </div>
  )
}
