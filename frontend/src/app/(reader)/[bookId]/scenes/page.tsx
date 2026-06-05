"use client"

import { useQuery } from "@tanstack/react-query"
import { startTransition, useDeferredValue, useEffect, useMemo, useRef, useState, type DragEvent as ReactDragEvent, type ReactNode } from "react"
import dynamic from "next/dynamic"
import type { Route } from "next"
import Link from "next/link"
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
  parseStoredSceneFolders,
  SCENE_FOLDER_STORAGE_KEY_PREFIX,
} from "@/lib/utils/sceneWorkspace"
import {
  buildUniqueWorkspacePathFromCandidate,
  buildWorkspaceFolderTree,
  normalizeWorkspaceFolderPath,
  sanitizeWorkspaceTitle,
  workspaceFolderFromPath,
  type WorkspaceFolderNode,
} from "@/lib/utils/workspacePaths"
import type { Book, ManuscriptWorkspaceTree, NovelScene, SceneMetadata } from "@/types/book"
import type { Character } from "@/types/character"
import { AddCharacterFromSelection } from "@/components/characters/AddCharacterFromSelection"

type FolderNode = WorkspaceFolderNode
type StructureNode = NonNullable<ManuscriptWorkspaceTree["structure_tree"]>[number]
type SceneDragItem = { kind: "scene"; id: string }
type BrowserView = "folders" | "scenes"

const EditorToolbar = dynamic(
  () => import("@/components/editor/SharedRichTextEditor").then((module) => module.EditorToolbar),
  { ssr: false }
)

const RichTextEditor = dynamic(
  () => import("@/components/editor/SharedRichTextEditor").then((module) => module.RichTextEditor),
  {
    ssr: false,
    loading: () => <div className="min-h-[32rem] animate-pulse bg-black/20" />,
  }
)

const WhatsTheWordPanel = dynamic(
  () => import("@/components/intelligence/WhatsTheWordPanel").then((module) => module.WhatsTheWordPanel),
  { ssr: false }
)

function sceneFolder(path: string) {
  return workspaceFolderFromPath(path)
}

function sceneSlug(value: string) {
  return sanitizeWorkspaceTitle(value, "untitled-scene").toLowerCase().replace(/\s+/g, "-")
}

function buildScenePath(folderPath: string | null, title: string) {
  const normalizedFolder = normalizeWorkspaceFolderPath(folderPath)
  const filename = `${sceneSlug(title)}.md`
  return normalizedFolder ? `${normalizedFolder}/${filename}` : filename
}

function defaultSceneFolder(chapterNumber: number | null) {
  if (typeof chapterNumber === "number" && chapterNumber > 0) {
    return `scenes/chapter-${String(chapterNumber).padStart(2, "0")}`
  }
  return "scenes/unassigned"
}

function loadSceneFolders(bookId: string) {
  if (typeof window === "undefined") return [] as string[]
  return parseStoredSceneFolders(window.localStorage.getItem(`${SCENE_FOLDER_STORAGE_KEY_PREFIX}${bookId}`))
}

function parseSceneDragItem(event: Pick<DragEvent, "dataTransfer"> | Pick<ReactDragEvent, "dataTransfer">) {
  const raw = event.dataTransfer?.getData("application/lorevia-scene-item")
  if (!raw) return null
  try {
    const value = JSON.parse(raw) as SceneDragItem
    return value.kind === "scene" && value.id ? value : null
  } catch {
    return null
  }
}

function emptySceneMetadata(): SceneMetadata {
  return {
    pov: null,
    timeline: null,
    location: null,
    tags: [],
    mood: [],
    status_note: null,
    anchors: [],
    bookmarks: [],
  }
}

function metadataTextToList(value: string) {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean)
}

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
  const [selectionMenu, setSelectionMenu] = useState<{ text: string; top: number; left: number } | null>(null)
  const [addCharacterOpen, setAddCharacterOpen] = useState(false)
  const [addCharacterText, setAddCharacterText] = useState("")
  const selectionRef = useRef<string>("")

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

  useEffect(() => {
    if (typeof window === "undefined") return
    window.localStorage.setItem(
      `${SCENE_FOLDER_STORAGE_KEY_PREFIX}${bookId}`,
      JSON.stringify([...new Set(customFolders.map((folder) => normalizeWorkspaceFolderPath(folder)).filter(Boolean))].sort())
    )
  }, [bookId, customFolders])

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

  const createFolder = (parentFolder?: string | null) => {
    if (typeof window === "undefined") return
    const base = normalizeWorkspaceFolderPath(parentFolder ?? selectedFolder) || "scenes"
    const requestedFolder = window.prompt("Create a scene folder path. Use / to nest folders.", `${base}/New Folder`)
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
              onNewFolder={() => createFolder()}
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
                      onCreateFolder={createFolder}
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

function WorkspaceHeader({
  bookId,
  book,
  isDark,
  onNewScene,
  onNewFolder,
}: {
  bookId: string
  book: Book | null
  isDark: boolean
  onNewScene: () => void
  onNewFolder: () => void
}) {
  const headerSecondaryClass = isDark
    ? "!border-white/10 !bg-[#0d1917] !text-slate-100 hover:!border-white/15 hover:!bg-[#14231f]"
    : undefined

  return (
    <section className={`flex min-h-[16.25rem] rounded-lg border px-5 py-6 sm:px-8 sm:py-6 ${isDark ? "border-white/10 bg-[#08111d]/84" : "border-white/70 bg-white/88"}`}>
      <div className="flex w-full flex-col gap-5 xl:flex-row xl:items-start xl:justify-between">
        <div className="min-w-0 xl:pt-6">
          <p className={`text-3xs font-semibold uppercase tracking-[0.28em] ${isDark ? "text-teal-300" : "text-teal-700"}`}>Scene workspace</p>
          <h1 className="mt-3 font-serif text-4xl leading-none sm:text-[3.85rem]">{book?.title || "Manuscript"} scenes</h1>
          <p className={`mt-4 max-w-5xl text-sm leading-8 sm:text-base ${isDark ? "text-slate-300" : "text-stone-600"}`}>
            Organize scenes with nested folders, move them between planning buckets, and keep metadata attached when you import them into the manuscript.
          </p>
        </div>

        <div className="grid gap-2 sm:grid-cols-2 xl:w-[31rem] xl:grid-cols-2">
          <ActionButton type="button" isDark={isDark} onClick={onNewScene}><IconSparkPlus />New scene</ActionButton>
          <ActionButton type="button" variant="secondary" isDark={isDark} onClick={onNewFolder} className={headerSecondaryClass}><IconFolderPlus />New folder</ActionButton>
          <ActionLink href={`/${bookId}/notes`} isDark={isDark} className={headerSecondaryClass}><IconNote />Open notes</ActionLink>
          <ActionLink href={`/${bookId}/voice` as Route} isDark={isDark} className={headerSecondaryClass}><IconMic />Open voice workspace</ActionLink>
          <ActionLink href={`/${bookId}/manuscript`} variant="secondary" isDark={isDark} className={`sm:col-span-2 ${headerSecondaryClass ?? ""}`}><IconBook />Open manuscript</ActionLink>
        </div>
      </div>
    </section>
  )
}

function MobilePanelToggles({
  isDark,
  showBrowser,
  showInspector,
  onToggleBrowser,
  onToggleInspector,
}: {
  isDark: boolean
  showBrowser: boolean
  showInspector: boolean
  onToggleBrowser: () => void
  onToggleInspector: () => void
}) {
  return (
    <div className="flex flex-wrap gap-2 xl:hidden">
      <ActionButton type="button" variant={showBrowser ? "secondary" : "ghost"} isDark={isDark} onClick={onToggleBrowser}>
        {showBrowser ? "Hide scene browser" : "Show scene browser"}
      </ActionButton>
      <ActionButton type="button" variant={showInspector ? "secondary" : "ghost"} isDark={isDark} onClick={onToggleInspector}>
        {showInspector ? "Hide details" : "Show details"}
      </ActionButton>
    </div>
  )
}

function SceneBrowserPanel({
  isDark,
  browserView,
  onBrowserViewChange,
  search,
  onSearchChange,
  scenes,
  filteredScenes,
  selectedFolder,
  selectedSceneId,
  folderTree,
  collapsed,
  onToggleFolder,
  onSelectFolder,
  onCreateFolder,
  onDropScene,
  dropTargetFolder,
  onDropTargetChange,
  onSelectScene,
  onCreateScene,
}: {
  isDark: boolean
  browserView: BrowserView
  onBrowserViewChange: (value: BrowserView) => void
  search: string
  onSearchChange: (value: string) => void
  scenes: NovelScene[]
  filteredScenes: NovelScene[]
  selectedFolder: string | null
  selectedSceneId: string | null
  folderTree: FolderNode
  collapsed: Record<string, boolean>
  onToggleFolder: (path: string) => void
  onSelectFolder: (path: string | null) => void
  onCreateFolder: (path?: string | null) => void
  onDropScene: (sceneId: string, folderPath: string | null) => void
  dropTargetFolder: string | null
  onDropTargetChange: (path: string | null) => void
  onSelectScene: (scene: NovelScene) => void
  onCreateScene: () => void
}) {
  const folderPanelClass = browserView === "scenes" ? "hidden xl:block" : "block"
  const scenePanelClass = browserView === "folders" ? "hidden xl:block" : "block"

  return (
    <aside className={`h-full min-w-0 p-4 sm:p-5 ${isDark ? "bg-[#07101c]" : "bg-stone-50/70"}`}>
      <div className="space-y-4">
        <WorkspaceTabs isDark={isDark} value={browserView} onChange={onBrowserViewChange} />

        <div className="flex items-center gap-2">
          <label className={`flex min-w-0 flex-1 items-center gap-2 rounded-sm border px-3 py-2.5 text-sm ${isDark ? "border-white/10 bg-[#030b16] text-slate-100" : "border-stone-200 bg-white text-stone-900"}`}>
            <IconSearch />
            <span className="sr-only">Search scenes or folders</span>
            <input
              value={search}
              onChange={(event) => onSearchChange(event.target.value)}
              placeholder="Search scenes or folders"
              className={`min-w-0 flex-1 bg-transparent outline-none ${isDark ? "placeholder:text-slate-500" : "placeholder:text-stone-400"}`}
            />
          </label>
          <button
            type="button"
            aria-label="Scene browser filters"
            className={`inline-flex h-10 w-10 items-center justify-center rounded-sm border ${isDark ? "border-white/10 bg-[#030b16] text-slate-400" : "border-stone-200 bg-white text-stone-500"}`}
          >
            <IconFilter />
          </button>
        </div>

        <div className={folderPanelClass}>
          <PanelCard
            isDark={isDark}
            label="Folders"
            title="Scene folders"
            action={(
              <button
                type="button"
                onClick={() => onCreateFolder()}
                aria-label="Create new folder"
                className={`inline-flex h-8 w-8 items-center justify-center rounded-lg border transition ${isDark ? "border-white/10 text-slate-400 hover:border-white/15 hover:bg-white/[0.06] hover:text-white" : "border-stone-200 text-stone-500 hover:bg-stone-100 hover:text-stone-900"}`}
              >
                <IconPlus />
              </button>
            )}
          >
            <div className="space-y-2.5">
              <button
                type="button"
                onClick={() => onSelectFolder(null)}
                onDragOver={(event) => {
                  if (!parseSceneDragItem(event)) return
                  event.preventDefault()
                  onDropTargetChange("")
                }}
                onDragLeave={() => {
                  if (dropTargetFolder === "") onDropTargetChange(null)
                }}
                onDrop={(event) => {
                  const dragItem = parseSceneDragItem(event)
                  if (!dragItem) return
                  event.preventDefault()
                  onDropScene(dragItem.id, null)
                }}
                className={`flex w-full items-center justify-between rounded-md border px-3 py-2.5 text-left text-sm transition ${
                  !selectedFolder
                    ? isDark
                      ? "border-teal-400/30 bg-teal-400/12 text-teal-50"
                      : "border-teal-300 bg-teal-50 text-teal-800"
                    : isDark
                      ? "border-white/10 bg-white/[0.02] text-slate-300 hover:bg-white/[0.04]"
                      : "border-stone-200 bg-white text-stone-700 hover:bg-stone-50"
                } ${dropTargetFolder === "" ? (isDark ? "ring-1 ring-teal-300/50" : "ring-1 ring-teal-300") : ""}`}
              >
                <span className="flex items-center gap-2 font-medium"><IconFolder />All scenes</span>
                <span className={`text-xs ${isDark ? "text-slate-500" : "text-stone-400"}`}>{scenes.length}</span>
              </button>

              <div className="max-h-[18rem] overflow-auto pr-1">
                <SceneFolderTree
                  node={folderTree}
                  activePath={selectedFolder}
                  collapsed={collapsed}
                  onToggleFolder={onToggleFolder}
                  onSelect={onSelectFolder}
                  onCreateFolder={onCreateFolder}
                  onDropScene={(sceneId, folderPath) => void onDropScene(sceneId, folderPath)}
                  dropTargetPath={dropTargetFolder}
                  onDropTargetChange={onDropTargetChange}
                  isDark={isDark}
                />
              </div>

              <button type="button" onClick={() => onCreateFolder(selectedFolder)} className={`inline-flex items-center gap-2 text-sm font-medium ${isDark ? "text-teal-200 hover:text-white" : "text-teal-700 hover:text-teal-900"}`}>
                <IconPlus />
                New folder
              </button>
            </div>
          </PanelCard>
        </div>

        <div className={scenePanelClass}>
          <PanelCard
            isDark={isDark}
            label="Scenes"
            title="Scene list"
            action={<button type="button" aria-label="Create new scene" onClick={onCreateScene} className={`inline-flex h-8 w-8 items-center justify-center rounded-lg border transition ${isDark ? "border-white/10 text-slate-400 hover:border-white/15 hover:bg-white/[0.06] hover:text-white" : "border-stone-200 text-stone-500 hover:bg-stone-100 hover:text-stone-900"}`}><IconPlus /></button>}
          >
            {filteredScenes.length === 0 ? (
              <div className={`rounded-md border border-dashed px-4 py-8 text-center ${isDark ? "border-white/10 bg-white/[0.02]" : "border-stone-300 bg-stone-50/80"}`}>
                <div className={`mx-auto flex h-11 w-11 items-center justify-center rounded-full ${isDark ? "bg-white/[0.04] text-slate-400" : "bg-stone-100 text-stone-500"}`}>
                  <IconDocument />
                </div>
                <p className={`mt-4 text-sm font-medium ${isDark ? "text-slate-200" : "text-stone-800"}`}>No scenes match this view.</p>
                <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-400" : "text-stone-500"}`}>Create a new scene to get started.</p>
                <div className="mt-4">
                  <ActionButton type="button" isDark={isDark} onClick={onCreateScene}>New scene</ActionButton>
                </div>
              </div>
            ) : (
              <div className="max-h-[28rem] space-y-2 overflow-auto pr-1">
                {filteredScenes.map((scene) => (
                  <button
                    key={scene.id}
                    type="button"
                    draggable
                    onDragStart={(event) => {
                      const payload: SceneDragItem = { kind: "scene", id: scene.id }
                      event.dataTransfer.effectAllowed = "move"
                      event.dataTransfer.setData("application/lorevia-scene-item", JSON.stringify(payload))
                    }}
                    onClick={() => onSelectScene(scene)}
                    className={`block w-full rounded-md border px-3 py-3 text-left transition ${
                      selectedSceneId === scene.id
                        ? isDark
                          ? "border-teal-400/35 bg-teal-400/12 text-white"
                          : "border-teal-300 bg-teal-50 text-stone-950"
                        : isDark
                          ? "border-white/10 bg-white/[0.02] text-slate-300 hover:bg-white/[0.05]"
                          : "border-stone-200 bg-white text-stone-700 hover:bg-stone-50"
                    }`}
                  >
                    <span className="block truncate text-sm font-semibold">{scene.title}</span>
                    <span className={`mt-1 block truncate text-3xs ${isDark ? "text-slate-500" : "text-stone-400"}`}>{scene.path}</span>
                    {scene.description ? (
                      <span className={`mt-2 line-clamp-2 block text-xs leading-5 ${isDark ? "text-slate-400" : "text-stone-500"}`}>{scene.description}</span>
                    ) : null}
                  </button>
                ))}
              </div>
            )}
          </PanelCard>
        </div>
      </div>
    </aside>
  )
}

function SceneMetadataForm({
  isDark,
  title,
  description,
  chapterNumber,
  chapterOptions,
  sceneFolderDraft,
  sceneMetadata,
  selectedTagList,
  selectedMoodList,
  onTitleChange,
  onDescriptionChange,
  onChapterNumberChange,
  onSceneFolderDraftChange,
  onSceneMetadataChange,
}: {
  isDark: boolean
  title: string
  description: string
  chapterNumber: number | null
  chapterOptions: number[]
  sceneFolderDraft: string
  sceneMetadata: SceneMetadata
  selectedTagList: string[]
  selectedMoodList: string[]
  onTitleChange: (value: string) => void
  onDescriptionChange: (value: string) => void
  onChapterNumberChange: (value: number | null) => void
  onSceneFolderDraftChange: (value: string) => void
  onSceneMetadataChange: (updater: SceneMetadata | ((current: SceneMetadata) => SceneMetadata)) => void
}) {
  const setSceneMetadata = (updater: SceneMetadata | ((current: SceneMetadata) => SceneMetadata)) => {
    onSceneMetadataChange(typeof updater === "function" ? updater(sceneMetadata) : updater)
  }

  return (
    <section className={`rounded-md border px-4 py-6 sm:px-7 sm:py-8 ${isDark ? "border-white/10 bg-[#0b1421]" : "border-stone-200 bg-white"}`}>
      <div className="flex flex-col gap-2 border-b border-white/10 pb-7">
        <p className={sectionLabel(isDark)}>Scene metadata</p>
        <p className={`text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>Keep chapter assignment, folder path, POV, and planning notes aligned with the current draft.</p>
      </div>

      <div className="mt-8 grid gap-6 md:grid-cols-2">
        <Field label="Scene title" isDark={isDark}>
          <input value={title} onChange={(event) => onTitleChange(event.target.value)} className={inputClass(isDark)} placeholder="Scene title" />
        </Field>
        <Field label="Chapter" isDark={isDark}>
          <select value={chapterNumber ?? ""} onChange={(event) => onChapterNumberChange(event.target.value ? Number(event.target.value) : null)} className={inputClass(isDark)}>
            <option value="">Unassigned</option>
            {chapterOptions.map((chapterNumberOption) => (
              <option key={chapterNumberOption} value={chapterNumberOption}>Chapter {chapterNumberOption}</option>
            ))}
          </select>
        </Field>
      </div>

      <div className="mt-7 grid gap-6">
        <Field label="Folder path" isDark={isDark}>
          <input value={sceneFolderDraft} onChange={(event) => onSceneFolderDraftChange(event.target.value)} className={inputClass(isDark)} placeholder="scenes/act-1/opening" />
        </Field>

        <Field label="Description" isDark={isDark}>
          <textarea value={description} onChange={(event) => onDescriptionChange(event.target.value)} className={`${inputClass(isDark)} min-h-[9rem] resize-y`} placeholder="Optional scene summary" />
        </Field>
      </div>

      <div className="mt-7 grid gap-7 lg:grid-cols-2">
        <Field label="POV character" isDark={isDark}>
          <input value={sceneMetadata.pov ?? ""} onChange={(event) => setSceneMetadata((current) => ({ ...current, pov: event.target.value || null }))} className={inputClass(isDark)} placeholder="Whose eyes are we in?" />
        </Field>
        <Field label="Timeline / date" isDark={isDark}>
          <input value={sceneMetadata.timeline ?? ""} onChange={(event) => setSceneMetadata((current) => ({ ...current, timeline: event.target.value || null }))} className={inputClass(isDark)} placeholder="Day 3, Winter court, 8:12 PM" />
        </Field>
        <Field label="Location" isDark={isDark}>
          <input value={sceneMetadata.location ?? ""} onChange={(event) => setSceneMetadata((current) => ({ ...current, location: event.target.value || null }))} className={inputClass(isDark)} placeholder="Blackwater Station" />
        </Field>
        <Field label="Mood / tone" isDark={isDark}>
          <div className="space-y-2">
            {selectedMoodList.length > 0 ? <TokenList items={selectedMoodList} isDark={isDark} /> : null}
            <input value={(sceneMetadata.mood ?? []).join(", ")} onChange={(event) => setSceneMetadata((current) => ({ ...current, mood: metadataTextToList(event.target.value) }))} className={inputClass(isDark)} placeholder="tense, intimate, foreboding" />
          </div>
        </Field>
        <Field label="Tags" isDark={isDark}>
          <div className="space-y-2">
            {selectedTagList.length > 0 ? <TokenList items={selectedTagList} isDark={isDark} /> : null}
            <input value={(sceneMetadata.tags ?? []).join(", ")} onChange={(event) => setSceneMetadata((current) => ({ ...current, tags: metadataTextToList(event.target.value) }))} className={inputClass(isDark)} placeholder="betrayal, dagger, reveal" />
          </div>
        </Field>
        <Field label="Status note" isDark={isDark}>
          <input value={sceneMetadata.status_note ?? ""} onChange={(event) => setSceneMetadata((current) => ({ ...current, status_note: event.target.value || null }))} className={inputClass(isDark)} placeholder="Draft, revised, final, waiting on continuity pass" />
        </Field>
      </div>
    </section>
  )
}

function SceneEditorPanel({
  isDark,
  htmlBody,
  wordCount,
  readingTime,
  status,
  saving,
  canSave,
  hasSelectedScene,
  onHtmlChange,
  onDelete,
  onSave,
}: {
  isDark: boolean
  htmlBody: string
  wordCount: number
  readingTime: string
  status: string | null
  saving: boolean
  canSave: boolean
  hasSelectedScene: boolean
  onHtmlChange: (nextHtml: string, nextText: string) => void
  onDelete: () => void
  onSave: () => void
}) {
  return (
    <section className={`rounded-md border ${isDark ? "border-white/10 bg-[#09111c]" : "border-stone-200 bg-white"}`}>
      <div className="flex flex-col gap-2 border-b border-white/10 px-4 py-4 sm:px-5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <p className={sectionLabel(isDark)}>Scene text</p>
            <h2 className={`mt-1 text-base font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>Writing surface</h2>
          </div>
          <div className={`rounded-full border px-3 py-1 text-xs ${isDark ? "border-white/10 bg-white/[0.04] text-slate-400" : "border-stone-200 bg-stone-50 text-stone-500"}`}>
            {wordCount.toLocaleString()} words · {readingTime}
          </div>
        </div>
        <p className={`text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>Use the editor for drafting while keeping scene metadata and hierarchy visible beside it.</p>
      </div>

      <div className="overflow-hidden">
        <div className={isDark ? "bg-[#0d1726]" : "bg-stone-50/70"}>
          <EditorToolbar editorKey="scene-workspace-editor" isDark={isDark} compact />
        </div>
        <RichTextEditor
          editorKey="scene-workspace-editor"
          html={htmlBody}
          onChange={onHtmlChange}
          placeholder="Start writing your scene..."
          className={`min-h-[24rem] px-5 py-4 font-serif text-base leading-8 outline-none sm:min-h-[30rem] ${isDark ? "text-slate-100" : "text-stone-900"}`}
        />
      </div>

      <div className="flex flex-col gap-3 border-t border-white/10 px-4 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-5">
        <p className={`text-sm leading-6 ${isDark ? "text-slate-400" : "text-stone-500"}`}>
          {status ?? "Drag scene cards into folders to organize them."}
        </p>
        <div className="flex flex-wrap gap-2.5">
          {hasSelectedScene ? (
            <ActionButton type="button" variant="danger" isDark={isDark} onClick={onDelete}>Delete</ActionButton>
          ) : null}
          <ActionButton type="button" isDark={isDark} onClick={onSave} disabled={saving || !canSave}>
            {saving ? "Saving..." : "Save scene"}
          </ActionButton>
        </div>
      </div>
    </section>
  )
}

function MetadataPreviewPanel({
  isDark,
  metadataRows,
  sceneTitle,
  sceneDescription,
  chapterNumber,
  wordCount,
  readingTime,
  currentScenePath,
  selectedSceneId,
  structureTree,
}: {
  isDark: boolean
  metadataRows: Array<[string, unknown]>
  sceneTitle: string
  sceneDescription: string
  chapterNumber: number | null
  wordCount: number
  readingTime: string
  currentScenePath: string | null
  selectedSceneId: string | null
  structureTree: NonNullable<ManuscriptWorkspaceTree["structure_tree"]>
}) {
  const hierarchyPath = findWorkspaceStructurePath(structureTree, selectedSceneId, sceneTitle)
  const displayHierarchyPath: StructureNode[] = hierarchyPath.length
    ? hierarchyPath
    : chapterNumber
      ? [
          { id: `chapter-${chapterNumber}`, label: `Chapter ${chapterNumber}`, kind: "chapter", chapter_number: chapterNumber, children: [] },
          { id: selectedSceneId ?? "draft-scene", label: sceneTitle, kind: "scene", chapter_number: chapterNumber, scene_id: selectedSceneId, children: [] },
        ]
      : []
  const summaryFromMetadata = metadataRows.find(([key]) => key === "summary")?.[1]
  const summary = summaryFromMetadata ? formatMetadataValue(summaryFromMetadata) : sceneDescription
  const detailRows: Array<[string, string]> = [
    ["Chapter", chapterNumber ? `Chapter ${chapterNumber}` : "Unassigned"],
    ["Words", `${wordCount.toLocaleString()} words`],
    ["Read time", readingTime],
    ...metadataRows
      .filter(([key]) => key !== "summary")
      .slice(0, 5)
      .map(([key, value]) => [formatInspectorLabel(key), formatMetadataValue(value)] as [string, string]),
  ]

  return (
    <aside className={`h-full min-w-0 p-4 sm:p-5 ${isDark ? "bg-[#07101c]" : "bg-stone-50/70"}`}>
      <div className={`rounded-md border ${isDark ? "border-white/10 bg-[#0b1421]" : "border-stone-200 bg-white"}`}>
        <div className={`border-b px-4 py-4 ${isDark ? "border-white/10" : "border-stone-200"}`}>
          <p className={sectionLabel(isDark)}>Inspector</p>
          <h2 className={`mt-1 truncate text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{sceneTitle}</h2>
          <p className={`mt-2 text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>{chapterNumber ? `Chapter ${chapterNumber}` : "No chapter assigned"}</p>
        </div>

        <div className="space-y-5 px-4 py-4">
          <InspectorSection isDark={isDark} label="Summary">
            {summary ? (
              <p className={`max-h-36 overflow-hidden text-sm leading-6 ${isDark ? "text-slate-200" : "text-stone-700"}`}>{summary}</p>
            ) : (
              <p className={`rounded-md border border-dashed px-3 py-4 text-sm leading-6 ${isDark ? "border-white/10 text-slate-500" : "border-stone-300 text-stone-500"}`}>
                Add a description or summary to preview the scene here.
              </p>
            )}
          </InspectorSection>

          <InspectorSection isDark={isDark} label="Details">
            <dl className="space-y-2.5">
              {detailRows.map(([label, value]) => (
                <div key={label} className="grid grid-cols-[5.5rem_minmax(0,1fr)] gap-3">
                  <dt className={`text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>{label}</dt>
                  <dd className={`min-w-0 break-words text-right text-xs font-medium leading-5 ${isDark ? "text-slate-200" : "text-stone-800"}`}>{value}</dd>
                </div>
              ))}
            </dl>
          </InspectorSection>

          <InspectorSection isDark={isDark} label="File">
            <p className={`break-words rounded-sm border px-3 py-3 text-xs leading-5 ${isDark ? "border-white/10 bg-white/[0.03] text-slate-300" : "border-stone-200 bg-stone-50 text-stone-700"}`}>
              {currentScenePath ?? "Set a title to generate the scene filename."}
            </p>
          </InspectorSection>

          <InspectorSection isDark={isDark} label="Hierarchy">
            {displayHierarchyPath.length ? (
              <div className="space-y-2">
                {displayHierarchyPath.map((node, index) => (
                  <StructureTreePreview
                    key={`${node.id}-${index}`}
                    node={node}
                    isDark={isDark}
                    isCurrent={index === displayHierarchyPath.length - 1}
                  />
                ))}
              </div>
            ) : (
              <p className={`rounded-md border border-dashed px-3 py-4 text-sm leading-6 ${isDark ? "border-white/10 text-slate-500" : "border-stone-300 text-stone-500"}`}>
                No hierarchy is available for this scene yet.
              </p>
            )}
          </InspectorSection>

          <p className={`border-t pt-4 text-xs leading-5 ${isDark ? "border-white/10 text-slate-500" : "border-stone-200 text-stone-500"}`}>
            Folder paths stay attached when scenes move into the manuscript.
          </p>
        </div>
      </div>
    </aside>
  )
}

function WorkspaceTabs({
  isDark,
  value,
  onChange,
}: {
  isDark: boolean
  value: BrowserView
  onChange: (value: BrowserView) => void
}) {
  const tabs: Array<{ id: BrowserView; label: string }> = [
    { id: "folders", label: "Folders" },
    { id: "scenes", label: "Scenes" },
  ]

  return (
    <div className={`inline-flex rounded-md border p-1 ${isDark ? "border-white/10 bg-[#020814]" : "border-stone-200 bg-white"}`} role="tablist" aria-label="Scene browser sections">
      {tabs.map((tab) => {
        const active = tab.id === value
        return (
          <button
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={active}
            onClick={() => onChange(tab.id)}
            className={`rounded-sm px-4 py-2 text-xs font-semibold uppercase tracking-[0.22em] transition ${
              active
                ? isDark
                  ? "bg-teal-400/14 text-teal-100"
                  : "bg-teal-50 text-teal-800"
                : isDark
                  ? "text-slate-500 hover:text-slate-200"
                  : "text-stone-500 hover:text-stone-800"
            }`}
          >
            {tab.label}
          </button>
        )
      })}
    </div>
  )
}

function PanelCard({
  isDark,
  label,
  title,
  action,
  children,
}: {
  isDark: boolean
  label: string
  title: string
  action?: ReactNode
  children: ReactNode
}) {
  return (
    <section className={`rounded-md border px-4 py-4 ${isDark ? "border-white/10 bg-[#0b1421]" : "border-stone-200 bg-white"}`}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className={sectionLabel(isDark)}>{label}</p>
          <h2 className={`mt-1 text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{title}</h2>
        </div>
        {action}
      </div>
      <div className="mt-4">{children}</div>
    </section>
  )
}

function InspectorSection({
  isDark,
  label,
  children,
}: {
  isDark: boolean
  label: string
  children: ReactNode
}) {
  return (
    <section>
      <p className={`mb-2 text-3xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>{label}</p>
      {children}
    </section>
  )
}

function WorkspaceStateCard({
  isDark,
  title,
  body,
  action,
}: {
  isDark: boolean
  title: string
  body: string
  action?: ReactNode
}) {
  return (
    <div className="px-5 py-16 sm:px-8">
      <div className={`mx-auto max-w-2xl rounded-md border px-6 py-10 text-center ${isDark ? "border-white/10 bg-white/[0.03]" : "border-stone-200 bg-white"}`}>
        <p className={sectionLabel(isDark)}>Scene workspace</p>
        <h2 className={`mt-3 text-xl font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{title}</h2>
        <p className={`mt-3 text-sm leading-7 ${isDark ? "text-slate-400" : "text-stone-500"}`}>{body}</p>
        {action ? <div className="mt-5">{action}</div> : null}
      </div>
    </div>
  )
}

function Field({
  label,
  isDark,
  children,
}: {
  label: string
  isDark: boolean
  children: ReactNode
}) {
  return (
    <label className="block text-sm">
      <span className={labelClass(isDark)}>{label}</span>
      {children}
    </label>
  )
}

function TokenList({ items, isDark }: { items: string[]; isDark: boolean }) {
  return (
    <div className="flex flex-wrap gap-2">
      {items.map((item) => (
        <span
          key={item}
          className={`inline-flex items-center rounded-full border px-2.5 py-1 text-xs ${isDark ? "border-white/10 bg-white/[0.04] text-slate-300" : "border-stone-200 bg-stone-50 text-stone-700"}`}
        >
          {item}
        </span>
      ))}
    </div>
  )
}

function SceneFolderTree({
  node,
  activePath,
  collapsed,
  onToggleFolder,
  onSelect,
  onCreateFolder,
  onDropScene,
  dropTargetPath,
  onDropTargetChange,
  isDark,
  depth = 0,
}: {
  node: FolderNode
  activePath: string | null
  collapsed: Record<string, boolean>
  onToggleFolder: (path: string) => void
  onSelect: (path: string) => void
  onCreateFolder: (path: string) => void
  onDropScene: (sceneId: string, folderPath: string) => void
  dropTargetPath: string | null
  onDropTargetChange: (path: string | null) => void
  isDark: boolean
  depth?: number
}) {
  return (
    <div className="space-y-1.5">
      {[...node.folders.values()].map((child) => {
        const isCollapsed = Boolean(collapsed[child.path])
        const active = child.path === activePath
        return (
          <div key={child.path}>
            <div className="flex items-center gap-1.5">
              <button
                type="button"
                onClick={() => onToggleFolder(child.path)}
                aria-label={isCollapsed ? `Expand ${child.name}` : `Collapse ${child.name}`}
                className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg transition ${isDark ? "text-slate-500 hover:bg-white/[0.05] hover:text-slate-200" : "text-stone-400 hover:bg-stone-100 hover:text-stone-700"}`}
                style={{ marginLeft: `${depth * 12}px` }}
              >
                <IconChevron open={!isCollapsed} />
              </button>
              <button
                type="button"
                onClick={() => onSelect(child.path)}
                onDragOver={(event) => {
                  if (!parseSceneDragItem(event)) return
                  event.preventDefault()
                  onDropTargetChange(child.path)
                }}
                onDragLeave={() => onDropTargetChange(null)}
                onDrop={(event) => {
                  const dragItem = parseSceneDragItem(event)
                  if (!dragItem) return
                  event.preventDefault()
                  onDropScene(dragItem.id, child.path)
                }}
                className={`flex min-w-0 flex-1 items-center justify-between rounded-md border px-3 py-2 text-left text-sm transition ${
                  active
                    ? isDark
                      ? "border-teal-400/30 bg-teal-400/12 text-teal-50"
                      : "border-teal-300 bg-teal-50 text-teal-800"
                    : isDark
                      ? "border-white/10 bg-white/[0.02] text-slate-300 hover:bg-white/[0.04]"
                      : "border-stone-200 bg-white text-stone-700 hover:bg-stone-50"
                } ${dropTargetPath === child.path ? (isDark ? "ring-1 ring-teal-300/50" : "ring-1 ring-teal-300") : ""}`}
              >
                <span className="flex min-w-0 items-center gap-2">
                  <IconFolder />
                  <span className="truncate font-medium">{child.name}</span>
                </span>
                <span className={`text-xs ${active ? (isDark ? "text-teal-100/80" : "text-teal-700/80") : isDark ? "text-slate-500" : "text-stone-400"}`}>{child.itemCount}</span>
              </button>
              <button
                type="button"
                onClick={() => onCreateFolder(child.path)}
                aria-label={`Create a folder inside ${child.name}`}
                className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg transition ${isDark ? "text-slate-500 hover:bg-white/[0.05] hover:text-white" : "text-stone-400 hover:bg-stone-100 hover:text-stone-800"}`}
              >
                <IconPlus />
              </button>
            </div>
            {!isCollapsed ? (
              <div className="mt-1">
                <SceneFolderTree
                  node={child}
                  activePath={activePath}
                  collapsed={collapsed}
                  onToggleFolder={onToggleFolder}
                  onSelect={onSelect}
                  onCreateFolder={onCreateFolder}
                  onDropScene={onDropScene}
                  dropTargetPath={dropTargetPath}
                  onDropTargetChange={onDropTargetChange}
                  isDark={isDark}
                  depth={depth + 1}
                />
              </div>
            ) : null}
          </div>
        )
      })}
    </div>
  )
}

function ActionButton({
  isDark,
  variant = "primary",
  className = "",
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { isDark: boolean; variant?: "primary" | "secondary" | "ghost" | "danger" }) {
  const styles = {
    primary: isDark
      ? "border-teal-400/25 bg-[#1f615d] text-white"
      : "border-teal-500 bg-teal-700 text-white",
    secondary: isDark
      ? "border-white/10 bg-white/[0.05] text-slate-100 hover:bg-white/[0.08]"
      : "border-stone-200 bg-white text-stone-800 hover:bg-stone-50",
    ghost: isDark
      ? "border-white/10 bg-transparent text-slate-300 hover:bg-white/[0.05]"
      : "border-stone-200 bg-transparent text-stone-700 hover:bg-white",
    danger: isDark
      ? "border-rose-400/15 bg-rose-500/10 text-rose-100 hover:bg-rose-500/14"
      : "border-rose-200 bg-rose-50 text-rose-700 hover:bg-rose-100",
  }

  return (
    <button
      {...props}
      className={`inline-flex items-center justify-center gap-2 rounded-sm border px-4 py-2.5 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-50 ${styles[variant]} ${className}`}
    />
  )
}

function ActionLink({
  href,
  isDark,
  variant = "ghost",
  children,
  className,
}: {
  href: Route | string
  isDark: boolean
  variant?: "secondary" | "ghost"
  children: ReactNode
  className?: string
}) {
  const classes = variant === "secondary"
    ? isDark
      ? "border-white/10 bg-white/[0.05] text-slate-100 hover:bg-white/[0.08]"
      : "border-stone-200 bg-white text-stone-800 hover:bg-stone-50"
    : isDark
      ? "border-white/10 bg-transparent text-slate-200 hover:bg-white/[0.05]"
      : "border-stone-200 bg-white text-stone-700 hover:bg-stone-50"

  return (
    <Link href={href as Route} className={`inline-flex items-center justify-center gap-2 rounded-sm border px-4 py-2.5 text-sm font-semibold transition ${classes} ${className ?? ""}`}>
      {children}
    </Link>
  )
}

function formatMetadataValue(value: unknown) {
  if (Array.isArray(value)) return value.join(", ")
  return String(value ?? "")
}

function formatInspectorLabel(value: string) {
  return value
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase())
}

function sectionLabel(isDark: boolean) {
  return `text-3xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-500" : "text-stone-400"}`
}

function labelClass(isDark: boolean) {
  return `mb-2 block text-3xs font-semibold uppercase tracking-[0.2em] ${isDark ? "text-slate-400" : "text-stone-500"}`
}

function inputClass(isDark: boolean) {
  return `w-full rounded-md border px-4 py-4 text-sm outline-none transition focus-visible:ring-2 ${
    isDark
      ? "border-white/10 bg-[#040b15] text-slate-100 placeholder:text-slate-500 focus-visible:border-teal-300/30 focus-visible:ring-teal-300/20"
      : "border-stone-200 bg-white text-stone-900 placeholder:text-stone-400 focus-visible:border-teal-400 focus-visible:ring-teal-200"
  }`
}

function IconSearch() {
  return <svg className="h-4 w-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}><path strokeLinecap="round" strokeLinejoin="round" d="M11 18a7 7 0 100-14 7 7 0 000 14zM16 16l4 4" /></svg>
}

function IconChevron({ open }: { open: boolean }) {
  return <svg className={`h-4 w-4 transition ${open ? "rotate-90" : ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}><path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" /></svg>
}

function IconFolder() {
  return <svg className="h-4 w-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}><path strokeLinecap="round" strokeLinejoin="round" d="M4 7h6l2 2h8v9a2 2 0 01-2 2H6a2 2 0 01-2-2V7z" /></svg>
}

function IconPlus() {
  return <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.9}><path strokeLinecap="round" strokeLinejoin="round" d="M12 5v14M5 12h14" /></svg>
}

function WritingToolsPanel({
  isDark,
  visible,
  onOpen,
  bookId,
}: {
  isDark: boolean
  visible: boolean
  onOpen: () => void
  bookId: string
}) {
  if (!visible) {
    return (
      <section className={`rounded-md border px-4 py-4 sm:px-5 ${isDark ? "border-white/10 bg-[#0b1421]" : "border-stone-200 bg-white"}`}>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className={sectionLabel(isDark)}>Writing assistant</p>
            <p className={`mt-1 text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>Load the word finder only when you need it to keep the main editor lighter.</p>
          </div>
          <ActionButton type="button" variant="secondary" isDark={isDark} onClick={onOpen}>Open word finder</ActionButton>
        </div>
      </section>
    )
  }

  return (
    <div className="rounded-md border border-white/10 bg-black/10 p-4 sm:p-5">
      <div className="flex items-center justify-between gap-3">
        <p className={sectionLabel(isDark)}>Writing assistant</p>
        <span className={`text-xs ${isDark ? "text-slate-500" : "text-stone-400"}`}>Loaded on demand</span>
      </div>
      <WhatsTheWordPanel bookId={bookId} isDark={isDark} className="mt-3" />
    </div>
  )
}

function IconFilter() {
  return <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.9}><path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M7 12h10M10 18h4" /></svg>
}

function IconDocument() {
  return <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}><path strokeLinecap="round" strokeLinejoin="round" d="M8 3h6l5 5v13H8a2 2 0 01-2-2V5a2 2 0 012-2z" /><path strokeLinecap="round" strokeLinejoin="round" d="M14 3v5h5" /></svg>
}

function IconSparkPlus() {
  return <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.9}><path strokeLinecap="round" strokeLinejoin="round" d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8L12 3z" /><path strokeLinecap="round" strokeLinejoin="round" d="M19 18v4M17 20h4" /></svg>
}

function IconFolderPlus() {
  return <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.9}><path strokeLinecap="round" strokeLinejoin="round" d="M3.5 7.5h6l2 2h9v8.5a2 2 0 01-2 2h-13a2 2 0 01-2-2V7.5z" /><path strokeLinecap="round" strokeLinejoin="round" d="M16.5 13.5v4M14.5 15.5h4" /></svg>
}

function IconNote() {
  return <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.9}><path strokeLinecap="round" strokeLinejoin="round" d="M7 4h10a2 2 0 012 2v12l-4-2-4 2-4-2-4 2V6a2 2 0 012-2h2z" /></svg>
}

function IconMic() {
  return <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.9}><path strokeLinecap="round" strokeLinejoin="round" d="M12 15a3 3 0 003-3V7a3 3 0 10-6 0v5a3 3 0 003 3z" /><path strokeLinecap="round" strokeLinejoin="round" d="M19 11a7 7 0 01-14 0M12 18v3M8.5 21h7" /></svg>
}

function IconBook() {
  return <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.9}><path strokeLinecap="round" strokeLinejoin="round" d="M5 5.5A2.5 2.5 0 017.5 3H20v16H7.5A2.5 2.5 0 005 21.5v-16z" /><path strokeLinecap="round" strokeLinejoin="round" d="M5 5.5v16H4a1 1 0 01-1-1v-13a4 4 0 014-4h13" /></svg>
}

function StructureTreePreview({
  node,
  isDark,
  isCurrent,
}: {
  node: StructureNode
  isDark: boolean
  isCurrent: boolean
}) {
  return (
    <div className="flex min-w-0 items-start gap-2">
      <span className={`mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full ${isCurrent ? (isDark ? "bg-teal-300" : "bg-teal-600") : isDark ? "bg-slate-600" : "bg-stone-300"}`} />
      <div className="min-w-0">
        <p className={`truncate text-sm font-medium ${isCurrent ? (isDark ? "text-teal-50" : "text-teal-800") : isDark ? "text-slate-300" : "text-stone-700"}`}>{node.label}</p>
        <p className={`mt-0.5 text-3xs font-semibold uppercase tracking-[0.16em] ${isDark ? "text-slate-600" : "text-stone-400"}`}>{node.kind}</p>
      </div>
    </div>
  )
}
