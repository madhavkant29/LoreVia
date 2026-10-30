"use client"

import { useEffect, useRef, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { booksApi } from "@/lib/api/books"
import { readerApi } from "@/lib/api/reader"
import { intelligenceApi, MAX_ADVISOR_PASSAGE_CHARS } from "@/lib/api/intelligence"
import { asQueryKey, bookCacheKey, readerCacheKey } from "@/lib/query/cacheKeys"
import { getApiErrorDetail } from "@/lib/utils/apiErrors"
import { saveContextualVaultNote } from "@/lib/utils/notes"
import { applyVoiceFindingDecision, buildVoiceIssueNote, buildVoiceReviewNote, buildVoiceReviewSceneDraft, countVoiceSourceCharacters, voiceReviewErrorMessage } from "@/lib/utils/voiceWorkspace"
import type { Character } from "@/types/character"
import type { VoiceConsistencyIssue, VoiceConsistencyResponse, VoiceReviewDecision } from "@/types/intelligence"

type Draft = { text: string; original: string; title: string }
export type VoiceResult = VoiceConsistencyResponse & {
  source: { text: string; chapterNumber: number | null; chapterTitle: string; characterId: string | null; characterName: string; sceneContext: string; voiceMode: "dialogue" | "first_person_narration" }
}

export function useVoiceWorkspace(bookId: string) {
  const [selectedChapter, setSelectedChapter] = useState<number | null>(null)
  const [selectedCharacterId, setSelectedCharacterId] = useState<string | null>(null)
  const [sceneContext, setSceneContext] = useState("")
  const [voiceMode, setVoiceMode] = useState<"dialogue" | "first_person_narration">("dialogue")
  const [drafts, setDrafts] = useState<Record<string, Draft>>({ custom: { text: "", original: "", title: "Custom passage" } })
  const [result, setResult] = useState<VoiceResult | null>(null)
  const [reviewLoading, setReviewLoading] = useState(false)
  const [reviewStage, setReviewStage] = useState<string | null>(null)
  const [reviewError, setReviewError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [saveStatus, setSaveStatus] = useState<string | null>(null)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [decisionSavingKey, setDecisionSavingKey] = useState<string | null>(null)
  const [decisionError, setDecisionError] = useState<string | null>(null)
  const initialized = useRef(false)
  const mounted = useRef(true)
  const reviewLock = useRef(false)
  const reviewController = useRef<AbortController | null>(null)
  const saveLock = useRef(false)
  const decisionLock = useRef(false)
  const dirty = Object.values(drafts).some((draft) => draft.text !== draft.original)
  const leaving = useRef(false)
  leaving.current = dirty || !!result || reviewLoading || saving

  useEffect(() => {
    mounted.current = true
    const unload = (event: BeforeUnloadEvent) => { if (leaving.current) { event.preventDefault(); event.returnValue = "" } }
    const click = (event: MouseEvent) => {
      const link = event.target instanceof Element ? event.target.closest("a[href]") : null
      if (!leaving.current || !(link instanceof HTMLAnchorElement) || link.target === "_blank" || link.hasAttribute("download") || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return
      const target = new URL(link.href, location.href)
      if (target.pathname === location.pathname && target.search === location.search) return
      if (!window.confirm("Leave voice review? Passage edits and this review are kept only on this page. Save a snapshot before leaving if you need a copy.")) { event.preventDefault(); event.stopPropagation() }
    }
    window.addEventListener("beforeunload", unload); document.addEventListener("click", click, true)
    return () => { mounted.current = false; reviewController.current?.abort(); window.removeEventListener("beforeunload", unload); document.removeEventListener("click", click, true) }
  }, [])

  const bookQuery = useQuery({ queryKey: asQueryKey(bookCacheKey(bookId, "detail")), queryFn: () => booksApi.get(bookId), retry: false })
  const chaptersQuery = useQuery({ queryKey: asQueryKey(readerCacheKey(bookId, "chapters")), queryFn: () => readerApi.getChapterList(bookId), retry: false })
  const charactersQuery = useQuery({ queryKey: asQueryKey(bookCacheKey(bookId, "characters:navigation")), queryFn: () => booksApi.getCharacters<Pick<Character, "id" | "name">>(bookId, { fields: ["id", "name"] }), retry: false })
  const chapterQuery = useQuery({
    queryKey: selectedChapter !== null ? asQueryKey(readerCacheKey(bookId, `chapter:${selectedChapter}`)) : ["voice:chapter:none", bookId],
    queryFn: () => readerApi.getChapter(bookId, selectedChapter as number), enabled: selectedChapter !== null, retry: false,
  })
  const sourceKey = selectedChapter === null ? "custom" : String(selectedChapter)
  const draft = drafts[sourceKey]
  const text = draft?.text ?? ""
  const chapterTitle = draft?.title ?? `Chapter ${selectedChapter}`
  const characters = charactersQuery.data ?? []
  const selectedCharacter = characters.find((character) => character.id === selectedCharacterId)

  useEffect(() => {
    if (initialized.current || !chaptersQuery.data) return
    initialized.current = true
    const chapters = chaptersQuery.data.chapters
    const preferred = chaptersQuery.data.current_chapter
    setSelectedChapter(chapters.some((chapter) => chapter.number === preferred) ? preferred ?? null : chapters.at(-1)?.number ?? null)
  }, [chaptersQuery.data])

  useEffect(() => {
    if (selectedChapter === null || !chapterQuery.data) return
    const chapter = chapterQuery.data
    setDrafts((current) => current[sourceKey] ? current : { ...current, [sourceKey]: {
      text: chapter.text_content || "", original: chapter.text_content || "",
      title: chapter.chapter_title || chaptersQuery.data?.chapters.find((item) => item.number === selectedChapter)?.title || `Chapter ${selectedChapter}`,
    } })
  }, [chapterQuery.data, chaptersQuery.data, selectedChapter, sourceKey])

  const selectChapter = (chapter: number | null) => { initialized.current = true; setSelectedChapter(chapter) }
  const setText = (value: string) => {
    initialized.current = true
    setDrafts((current) => current[sourceKey] ? { ...current, [sourceKey]: { ...current[sourceKey], text: value } } : current)
  }
  const resetDraft = () => {
    if (!draft || !window.confirm("Discard edits to this passage and restore its original text?")) return
    setText(draft.original)
  }
  const overLimit = countVoiceSourceCharacters(text) > MAX_ADVISOR_PASSAGE_CHARS
  const contextChanged = !!result && (result.source.text !== text || result.source.chapterNumber !== selectedChapter || result.source.characterId !== selectedCharacterId || result.source.sceneContext !== sceneContext.trim() || result.source.voiceMode !== voiceMode)
  const chapterAvailable = selectedChapter === null || !!chaptersQuery.data?.chapters.some((chapter) => chapter.number === selectedChapter)
  const canReview = !!bookQuery.data && !bookQuery.isError && chapterAvailable && !!draft && !!text.trim() && !overLimit && (!selectedCharacterId || !!selectedCharacter)

  const runReview = async () => {
    if (reviewLock.current || saveLock.current || !canReview) return
    reviewLock.current = true; setReviewLoading(true); setReviewStage("Connecting to voice review…"); setReviewError(null); setSaveStatus(null); setSaveError(null)
    const controller = new AbortController()
    reviewController.current = controller
    const source = { text, chapterNumber: selectedChapter, chapterTitle, characterId: selectedCharacterId, characterName: selectedCharacter?.name ?? "Auto-detect", sceneContext: sceneContext.trim(), voiceMode }
    try {
      const response = await intelligenceApi.voiceConsistencyReviewStream(bookQuery.data!.id, source.text, { chapterNum: source.chapterNumber ?? undefined, characterId: source.characterId, ...(source.sceneContext ? { sceneContext: source.sceneContext } : {}), ...(source.voiceMode === "first_person_narration" ? { voiceMode: source.voiceMode } : {}) }, { signal: controller.signal, onStage: (message) => { if (mounted.current) setReviewStage(message) } })
      if (mounted.current) setResult({ ...response, source })
    } catch (error) {
      if (mounted.current) setReviewError(voiceReviewErrorMessage(error))
    } finally {
      reviewLock.current = false
      if (reviewController.current === controller) reviewController.current = null
      if (mounted.current) { setReviewLoading(false); setReviewStage(null) }
    }
  }

  const save = async (kind: "issue" | "review" | "snapshot", issue?: VoiceConsistencyIssue) => {
    if (!result || saveLock.current || reviewLock.current) return
    saveLock.current = true; setSaving(true); setSaveStatus(null); setSaveError(null)
    const { source, review } = result
    const limitations = result.warnings?.length ? `\n\nReview limitations:\n${result.warnings.map((warning) => `- ${warning}`).join("\n")}` : ""
    try {
      let path: string
      if (kind === "snapshot") {
        const tree = await booksApi.getWorkspaceTree(bookId)
        const scene = buildVoiceReviewSceneDraft({ ...source, sourceText: source.text, overallVerdict: review.overall_verdict, issues: review.issues, suppressedFindings: result.suppressed_findings, reviewStatus: review.status, existingPaths: (tree?.scene_groups ?? []).flatMap((group) => group.scenes.map((item) => item.path)) })
        path = (await booksApi.saveScene(bookId, { ...scene, body: `${scene.body}\n\nCharacter focus: ${source.characterName}${limitations}` })).path
      } else {
        const note = kind === "issue" && issue ? buildVoiceIssueNote(issue) : buildVoiceReviewNote({ ...source, overallVerdict: review.overall_verdict, charactersReviewed: result.characters_reviewed, issues: review.issues, suppressedFindings: result.suppressed_findings, reviewStatus: review.status, matches: result.character_matches ?? [] })
        const context = `${source.chapterNumber === null ? "Custom passage" : `Chapter ${source.chapterNumber}: ${source.chapterTitle}`}\nCharacter focus: ${source.characterName}`
        path = (await saveContextualVaultNote({ bookId, title: note.title, content: `${context}\n\n${note.body}${limitations}`, context: "story_advisor", folderSegments: source.chapterNumber !== null ? ["Voice", `Chapter ${source.chapterNumber}`] : ["Voice"] })).path
      }
      if (mounted.current) setSaveStatus(`Saved ${kind === "snapshot" ? "review scene" : "voice note"} to ${path}`)
    } catch (error) {
      if (mounted.current) setSaveError(`${getApiErrorDetail(error) ?? "Could not confirm the save."} Your review is still here. Check ${kind === "snapshot" ? "Scenes" : "Notes"} before trying again to avoid a duplicate.`)
    } finally {
      saveLock.current = false
      if (mounted.current) setSaving(false)
    }
  }

  const decideFinding = async (issue: VoiceConsistencyIssue, decision: VoiceReviewDecision) => {
    if (!issue.finding_key || decisionLock.current || reviewLock.current || !result) return
    decisionLock.current = true
    setDecisionSavingKey(issue.finding_key)
    setDecisionError(null)
    try {
      await intelligenceApi.saveVoiceReviewDecision(bookQuery.data!.id, issue.finding_key, decision)
      if (mounted.current) setResult((current) => current ? applyVoiceFindingDecision(current, issue.finding_key!, decision) : current)
    } catch (error) {
      if (mounted.current) setDecisionError(getApiErrorDetail(error) ?? "Could not save that decision. The finding remains available; please retry.")
    } finally {
      decisionLock.current = false
      if (mounted.current) setDecisionSavingKey(null)
    }
  }

  return { bookQuery, chaptersQuery, charactersQuery, chapterQuery, selectedChapter, selectChapter, selectedCharacterId, setSelectedCharacterId, selectedCharacter, characters, sceneContext, setSceneContext, voiceMode, setVoiceMode,
    text, setText, chapterTitle, chapterAvailable, draft, resetDraft, dirty, result, contextChanged, overLimit, canReview, runReview, reviewLoading, reviewStage, reviewError, saving, saveStatus, saveError, save, decideFinding, decisionSavingKey, decisionError }
}
