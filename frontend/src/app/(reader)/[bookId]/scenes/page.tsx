"use client"

import { useQuery } from "@tanstack/react-query"
import { startTransition, useDeferredValue, useEffect, useMemo, useRef, useState } from "react"
import { useParams } from "next/navigation"

import { booksApi } from "@/lib/api/books"
import { useBookDetail } from "@/lib/hooks/useBookDetail"
import { asQueryKey, bookCacheKey } from "@/lib/query/cacheKeys"
import { countWords, estimateReadingTimeMinutes, formatReadingTimeLabel } from "@/lib/utils/manuscriptEditor"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import {
  buildSceneChapterOptions,
  extractChapterNumberFromSceneFolder,
  findWorkspaceStructurePath,
} from "@/lib/utils/sceneWorkspace"
import {
  buildUniqueWorkspacePathFromCandidate,
  buildWorkspaceFolderTree,
  normalizeWorkspaceFolderPath,
} from "@/lib/utils/workspacePaths"
import type { Book, ManuscriptWorkspaceTree, NovelScene, SceneMetadata } from "@/types/book"
import type { Character } from "@/types/character"
import { AddCharacterFromSelection } from "@/components/characters/AddCharacterFromSelection"
import { usePromptDialog } from "@/components/ui/PromptDialog"
import {
  ActionButton,
  MetadataPreviewPanel,
  MobilePanelToggles,
  SceneBrowserPanel,
  SceneEditorPanel,
  SceneMetadataForm,
  WorkspaceHeader,
  WorkspaceStateCard,
  WritingToolsPanel,
  type BrowserView,
} from "./scenesPage.components"
import {
  buildScenePath,
  defaultSceneFolder,
  emptySceneMetadata,
  loadSceneFolders,
  saveSceneFolders,
  sceneFolder,
} from "./scenesPage.helpers"

export default function ScenesPage() {
  const { bookId } = useParams<{ bookId: string }>()
  const { theme } = usePreferencesStore()
  const isDark = theme === "dark"
  const [selectedSceneId, setSelectedSceneId] = useState<string | null>(null)
  const [selectedFolder, setSelectedFolder] = useState<string | null>(null)
  const [customFolders, setCustomFolders] = useState<string[]>([])
  const [dropTargetFolder, setDropTargetFolder] = useState<string | null>(null)
  const [search, setSearch] = useState("")
  const [title, setTitle] = useState("")
  const [description, setDescription] = useState("")
  const [body, setBody] = useState("")
  const [htmlBody, setHtmlBody] = useState("<p></p>")
  const [chapterNumber, setChapterNumber] = useState<number | null>(null)
  const [sceneMetadata, setSceneMetadata] = useState<SceneMetadata>(emptySceneMetadata())
  const [sceneFolderDraft, setSceneFolderDraft] = useState(defaultSceneFolder(null))
  const [saving, setSaving] = useState(false)
  const [status, setStatus] = useState<string | null>(null)
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({})
  const [browserView, setBrowserView] = useState<BrowserView>("folders")
  const [showBrowserOnMobile, setShowBrowserOnMobile] = useState(true)
  const [showInspectorOnMobile, setShowInspectorOnMobile] = useState(false)
  const [showWritingTools, setShowWritingTools] = useState(false)
  const [firstLineIndent, setFirstLineIndent] = useState(false)
  const [selectionMenu, setSelectionMenu] = useState<{ text: string; top: number; left: number } | null>(null)
  const [addCharacterOpen, setAddCharacterOpen] = useState(false)
  const [addCharacterText, setAddCharacterText] = useState("")
  const selectionRef = useRef<string>("")
  const prompt = usePromptDialog()

  const { data: book = null } = useBookDetail(bookId)
  const {
    data: tree = null,
    isLoading: treeLoading,
    isError: treeError,
    refetch: refetchTree,
  } = useQuery<ManuscriptWorkspaceTree | null>({
    queryKey: asQueryKey(bookCacheKey(bookId, "workspace-tree")),
    queryFn: () => booksApi.getWorkspaceTree(bookId),
  })

  const scenes = useMemo(
    () => (tree?.scene_groups ?? []).flatMap((group) => group.scenes).sort((a, b) => a.path.localeCompare(b.path)),
    [tree]
  )
  const sceneMap = useMemo(() => new Map(scenes.map((scene) => [scene.id, scene])), [scenes])
  const selectedScene = selectedSceneId ? sceneMap.get(selectedSceneId) ?? null : null

  const sceneFolders = useMemo(() => {
    const chapterFolders = (tree?.chapters ?? []).map((chapter) => defaultSceneFolder(chapter.chapter_number))
    return [...new Set([...chapterFolders, ...customFolders])]
  }, [customFolders, tree])
  const chapterOptions = useMemo(
    () => buildSceneChapterOptions(tree?.chapters ?? [], [...sceneFolders, ...scenes.map((scene) => scene.path)]),
    [sceneFolders, scenes, tree]
  )
  const folderTree = useMemo(
    () => buildWorkspaceFolderTree(scenes.map((scene) => scene.path), sceneFolders),
    [sceneFolders, scenes]
  )

  const deferredSearch = useDeferredValue(search)

  const filteredScenes = useMemo(() => {
    const term = deferredSearch.trim().toLowerCase()
    return scenes.filter((scene) => {
      const folderMatches = !selectedFolder || sceneFolder(scene.path) === selectedFolder || sceneFolder(scene.path).startsWith(`${selectedFolder}/`)
      if (!folderMatches) return false
      if (!term) return true
      return [scene.title, scene.description ?? "", scene.body, scene.path].some((value) => value.toLowerCase().includes(term))
    })
  }, [deferredSearch, scenes, selectedFolder])

  const metadataRows = useMemo(() => {
    const metadata = selectedScene?.metadata ?? sceneMetadata ?? {}
    return Object.entries(metadata).filter(([, value]) => {
      if (Array.isArray(value)) return value.length > 0
      return value !== null && value !== undefined && String(value).trim() !== ""
    })
  }, [sceneMetadata, selectedScene])
  const sceneWordCount = useMemo(() => countWords(body), [body])
  const sceneReadingTime = useMemo(() => formatReadingTimeLabel(estimateReadingTimeMinutes(sceneWordCount)), [sceneWordCount])
  const currentScenePath = title.trim() ? buildScenePath(sceneFolderDraft, title.trim()) : null
  const selectedTagList = sceneMetadata.tags ?? []
  const selectedMoodList = sceneMetadata.mood ?? []

  const rememberFolder = (folderPath: string | null | undefined) => {
    const normalized = normalizeWorkspaceFolderPath(folderPath)
    if (!normalized) return
    setCustomFolders((current) => [...new Set([...current, normalized])].sort())
  }

  const syncWorkspaceSelection = (treeData: ManuscriptWorkspaceTree | null, preferredSceneId?: string | null) => {
    const availableScenes = treeData?.scene_groups.flatMap((group) => group.scenes) ?? []
    const nextSceneId = preferredSceneId ?? selectedSceneId
    const matchedScene = nextSceneId ? availableScenes.find((scene) => scene.id === nextSceneId) ?? null : null
    const fallbackScene = matchedScene ?? availableScenes[0] ?? null
    if (fallbackScene) {
      selectScene(fallbackScene)
      return
    }
    setSelectedSceneId(null)
  }

  useEffect(() => {
    setCustomFolders(loadSceneFolders(bookId))
  }, [bookId])

  useEffect(() => saveSceneFolders(bookId, customFolders), [bookId, customFolders])

  useEffect(() => {
    syncWorkspaceSelection(tree)
  }, [tree])

  useEffect(() => {
    const syncSelectionMenu = () => {
      const selection = window.getSelection()
      const selectedText = selection?.toString().trim() ?? ""
      const editor = document.querySelector<HTMLElement>(`[data-editor-key="scene-workspace-editor"]`)
      const anchorNode = selection?.anchorNode

      if (!selection || !selectedText || !editor || !anchorNode || !editor.contains(anchorNode) || selection.rangeCount === 0) {
        setSelectionMenu(null)
        return
      }

      const rect = selection.getRangeAt(0).getBoundingClientRect()
      if (!rect.width && !rect.height) {
        setSelectionMenu(null)
        return
      }

      selectionRef.current = selectedText
      setSelectionMenu({
        text: selectedText.slice(0, 100),
        top: rect.top + window.scrollY - 48,
        left: rect.left + window.scrollX + (rect.width / 2),
      })
    }

    document.addEventListener("selectionchange", syncSelectionMenu)
    window.addEventListener("resize", syncSelectionMenu)
    window.addEventListener("scroll", syncSelectionMenu, true)
    return () => {
      document.removeEventListener("selectionchange", syncSelectionMenu)
      window.removeEventListener("resize", syncSelectionMenu)
      window.removeEventListener("scroll", syncSelectionMenu, true)
    }
  }, [])

  const openAddCharacterFromSelection = () => {
    const text = selectionRef.current.trim()
    if (!text) {
      setStatus("Select a character name in the scene first.")
      return
    }
    setAddCharacterText(text)
    setAddCharacterOpen(true)
    setSelectionMenu(null)
  }

  const handleCharacterCreated = (character: Character) => {
    setStatus(`Character "${character.name}" added to the story bible.`)
  }

  function selectScene(scene: NovelScene) {
    const inferredChapterNumber = scene.chapter_number ?? extractChapterNumberFromSceneFolder(scene.path)
    const folderPath = sceneFolder(scene.path) || defaultSceneFolder(inferredChapterNumber)
    setSelectedSceneId(scene.id)
    setSelectedFolder(sceneFolder(scene.path) || null)
    setTitle(scene.title)
    setDescription(scene.description ?? "")
    setBody(scene.body)
    setHtmlBody(scene.html_body ?? `<p>${scene.body.replace(/\n/g, "<br>")}</p>`)
    setChapterNumber(inferredChapterNumber)
    setSceneMetadata({ ...emptySceneMetadata(), ...(scene.metadata ?? {}) })
    setSceneFolderDraft(folderPath)
    setStatus(null)
    setShowBrowserOnMobile(false)
  }

  function newScene(folderOverride?: string | null) {
    const destinationFolder = normalizeWorkspaceFolderPath(folderOverride ?? selectedFolder) || defaultSceneFolder(chapterNumber)
    const inferredChapterNumber = extractChapterNumberFromSceneFolder(destinationFolder)
    rememberFolder(destinationFolder)
    setSelectedSceneId(null)
    setTitle("")
    setDescription("")
    setBody("")
    setHtmlBody("<p></p>")
    setChapterNumber(inferredChapterNumber ?? chapterOptions[0] ?? null)
    setSceneMetadata(emptySceneMetadata())
    setSceneFolderDraft(destinationFolder)
    setStatus(null)
    setShowBrowserOnMobile(false)
  }

  const createFolder = async (parentFolder?: string | null) => {
    const base = normalizeWorkspaceFolderPath(parentFolder ?? selectedFolder) || "scenes"
    const requestedFolder = await prompt({
      title: "Create scene folder",
      body: "Use / to nest folders inside the scene workspace.",
      label: "Folder path",
      initialValue: `${base}/New Folder`,
      confirmLabel: "Create folder",
      validate: (value) => normalizeWorkspaceFolderPath(value) ? null : "Folder path cannot be empty.",
    })
    if (requestedFolder === null) return
    const cleanFolder = normalizeWorkspaceFolderPath(requestedFolder)
    if (!cleanFolder) {
      setStatus("Folder path cannot be empty")
      return
    }
    rememberFolder(cleanFolder)
    setSelectedFolder(cleanFolder)
    setChapterNumber((current) => extractChapterNumberFromSceneFolder(cleanFolder) ?? current)
    setSceneFolderDraft(cleanFolder)
    setCollapsed((current) => ({ ...current, [cleanFolder]: false }))
    setStatus(`Created folder ${cleanFolder}`)
  }

  const saveScene = async () => {
    if (!title.trim() || !body.trim()) return
    setSaving(true)
    try {
      const destinationFolder = normalizeWorkspaceFolderPath(sceneFolderDraft) || defaultSceneFolder(chapterNumber)
      rememberFolder(destinationFolder)
      const saved = await booksApi.saveScene(bookId, {
        id: selectedScene?.id,
        title: title.trim(),
        description: description.trim() || null,
        body,
        html_body: htmlBody,
        metadata: sceneMetadata,
        path: buildScenePath(destinationFolder, title.trim()),
        chapter_number: chapterNumber,
        status: chapterNumber ? "assigned" : "unassigned",
        sort_order: selectedScene?.sort_order ?? 1,
      })
      setStatus("Scene saved. Metadata refreshed from the scene text.")
      const { data: nextTree } = await refetchTree()
      syncWorkspaceSelection(nextTree ?? null, saved.id)
    } finally {
      setSaving(false)
    }
  }

  const moveSceneToFolder = async (sceneId: string, destinationFolder: string | null) => {
    const scene = sceneMap.get(sceneId)
    if (!scene) return
    const cleanFolder = normalizeWorkspaceFolderPath(destinationFolder) || "scenes"
    const nextPath = buildUniqueWorkspacePathFromCandidate(
      scenes.filter((item) => item.id !== scene.id).map((item) => item.path),
      buildScenePath(cleanFolder, scene.title)
    )
    if (nextPath === scene.path) {
      setStatus("That scene is already in this folder")
      return
    }

    setSaving(true)
    try {
      rememberFolder(cleanFolder)
      await booksApi.saveScene(bookId, {
        id: scene.id,
        title: scene.title,
        description: scene.description,
        body: scene.body,
        metadata: scene.metadata,
        html_body: scene.html_body,
        path: nextPath,
        chapter_number: scene.chapter_number,
        status: scene.status,
        sort_order: scene.sort_order,
      })
      setStatus(`Moved scene to ${nextPath}`)
      const { data: nextTree } = await refetchTree()
      syncWorkspaceSelection(nextTree ?? null, scene.id)
    } catch {
      setStatus("Could not move this scene")
    } finally {
      setSaving(false)
      setDropTargetFolder(null)
    }
  }

  const deleteScene = async () => {
    if (!selectedScene) return
    await booksApi.deleteScene(bookId, selectedScene.id)
    newScene(selectedFolder)
    setStatus("Scene deleted.")
    const { data: nextTree } = await refetchTree()
    syncWorkspaceSelection(nextTree ?? null)
  }

  return (
    <div className={`min-h-screen ${isDark ? "bg-[#071211] text-slate-100" : "bg-stone-50 text-stone-950"}`}>
      <div className="w-full px-4 pb-12 pt-0 sm:px-5 lg:px-6">
        <main className="min-w-0 space-y-6">
            <WorkspaceHeader
              bookId={bookId}
              book={book}
              isDark={isDark}
              onNewScene={() => newScene()}
              onNewFolder={() => void createFolder()}
            />

            <MobilePanelToggles
              isDark={isDark}
              showBrowser={showBrowserOnMobile}
              showInspector={showInspectorOnMobile}
              onToggleBrowser={() => setShowBrowserOnMobile((current) => !current)}
              onToggleInspector={() => setShowInspectorOnMobile((current) => !current)}
            />

            <section className={`overflow-hidden rounded-md border ${isDark ? "border-white/10 bg-[#09121f]/92" : "border-white/70 bg-white/90"}`}>
              {treeLoading && !tree ? (
                <WorkspaceStateCard
                  isDark={isDark}
                  title="Loading scene workspace"
                  body="Fetching scene files, folders, and structure for this manuscript."
                />
              ) : treeError ? (
                <WorkspaceStateCard
                  isDark={isDark}
                  title="Scene workspace unavailable"
                  body="We couldn't load the current scene workspace. Try again to refresh the folder tree and scene list."
                  action={<ActionButton type="button" variant="secondary" isDark={isDark} onClick={() => void refetchTree()}>Retry</ActionButton>}
                />
              ) : (
                <div className="grid gap-0 xl:min-h-[44rem] xl:grid-cols-[24rem_minmax(0,1fr)_21rem]">
                  <div className={`${showBrowserOnMobile ? "block" : "hidden"} min-w-0 xl:block`}>
                    <SceneBrowserPanel
                      isDark={isDark}
                      browserView={browserView}
                      onBrowserViewChange={setBrowserView}
                      search={search}
                      onSearchChange={setSearch}
                      scenes={scenes}
                      filteredScenes={filteredScenes}
                      selectedFolder={selectedFolder}
                      selectedSceneId={selectedSceneId}
                      folderTree={folderTree}
                      collapsed={collapsed}
                      onToggleFolder={(path) => setCollapsed((current) => ({ ...current, [path]: !current[path] }))}
                      onSelectFolder={setSelectedFolder}
                      onCreateFolder={(path) => void createFolder(path)}
                      onDropScene={(sceneId, folderPath) => void moveSceneToFolder(sceneId, folderPath)}
                      dropTargetFolder={dropTargetFolder}
                      onDropTargetChange={setDropTargetFolder}
                      onSelectScene={selectScene}
                      onCreateScene={() => newScene(selectedFolder)}
                    />
                  </div>

                  <div className="min-w-0 border-y xl:border-x xl:border-y-0" style={{ borderColor: isDark ? "rgba(255,255,255,0.08)" : "rgba(216, 216, 216, 0.9)" }}>
                    <div className="min-w-0 p-4 sm:p-5 xl:p-8">
                      <div className="grid gap-5">
                        <SceneMetadataForm
                          isDark={isDark}
                          title={title}
                          description={description}
                          chapterNumber={chapterNumber}
                          chapterOptions={chapterOptions}
                          sceneFolderDraft={sceneFolderDraft}
                          sceneMetadata={sceneMetadata}
                          selectedTagList={selectedTagList}
                          selectedMoodList={selectedMoodList}
                          onTitleChange={setTitle}
                          onDescriptionChange={setDescription}
                          onChapterNumberChange={setChapterNumber}
                          onSceneFolderDraftChange={setSceneFolderDraft}
                          onSceneMetadataChange={setSceneMetadata}
                        />

                        <WritingToolsPanel
                          isDark={isDark}
                          visible={showWritingTools}
                          onOpen={() => startTransition(() => setShowWritingTools(true))}
                          bookId={bookId}
                        />

                        <SceneEditorPanel
                          isDark={isDark}
                          htmlBody={htmlBody}
                          wordCount={sceneWordCount}
                          readingTime={sceneReadingTime}
                          status={status}
                          saving={saving}
                          canSave={Boolean(title.trim() && body.trim())}
                          hasSelectedScene={Boolean(selectedScene)}
                          firstLineIndent={firstLineIndent}
                          onToggleFirstLineIndent={() => setFirstLineIndent((value) => !value)}
                          onHtmlChange={(nextHtml, nextText) => {
                            setHtmlBody(nextHtml)
                            setBody(nextText)
                          }}
                          onDelete={() => void deleteScene()}
                          onSave={() => void saveScene()}
                        />
                      </div>
                    </div>
                  </div>

                  <div className={`${showInspectorOnMobile ? "block" : "hidden"} min-w-0 xl:block`}>
                    <MetadataPreviewPanel
                      isDark={isDark}
                      metadataRows={metadataRows}
                      sceneTitle={title.trim() || "Untitled scene"}
                      sceneDescription={description.trim()}
                      chapterNumber={chapterNumber}
                      wordCount={sceneWordCount}
                      readingTime={sceneReadingTime}
                      currentScenePath={currentScenePath}
                      selectedSceneId={selectedSceneId}
                      structureTree={tree?.structure_tree ?? []}
                    />
                  </div>
                </div>
              )}
            </section>
        </main>

        {selectionMenu ? (
          <div
            className="pointer-events-none fixed z-50 hidden -translate-x-1/2 xl:block"
            style={{ top: selectionMenu.top, left: selectionMenu.left }}
          >
            <div className={`pointer-events-auto flex items-center gap-2 rounded-full border px-2 py-2 ${isDark ? "border-white/10 bg-[#0f1117]" : "border-stone-200 bg-white"}`}>
              <button
                type="button"
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => openAddCharacterFromSelection()}
                className={`rounded-full px-3 py-1.5 text-xs font-medium ${isDark ? "bg-violet-700/30 text-violet-200" : "bg-violet-100 text-violet-800"}`}
              >
                Add as character
              </button>
            </div>
          </div>
        ) : null}

        <AddCharacterFromSelection
          bookId={bookId}
          selectedText={addCharacterText}
          isDark={isDark}
          firstChapter={chapterNumber ?? undefined}
          open={addCharacterOpen}
          onClose={() => setAddCharacterOpen(false)}
          onCreated={handleCharacterCreated}
        />
      </div>
    </div>
  )
}
