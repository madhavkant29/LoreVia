"use client"
import { useQuery } from "@tanstack/react-query"
import { startTransition, useCallback, useDeferredValue, useEffect, useMemo, useRef, useState } from "react"
import { useParams } from "next/navigation"
import { booksApi } from "@/lib/api/books"
import { useBookDetail } from "@/lib/hooks/useBookDetail"
import { asQueryKey, bookCacheKey } from "@/lib/query/cacheKeys"
import { countWords, estimateReadingTimeMinutes, formatReadingTimeLabel } from "@/lib/utils/manuscriptEditor"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import { buildSceneChapterOptions, extractChapterNumberFromSceneFolder } from "@/lib/utils/sceneWorkspace"
import { buildUniqueWorkspacePathFromCandidate, buildWorkspaceFolderTree, normalizeWorkspaceFolderPath } from "@/lib/utils/workspacePaths"
import type { ManuscriptWorkspaceTree, SceneMetadata, WorkspaceScene } from "@/types/book"
import { AuthorToolsNav } from "@/components/layout/AuthorToolsNav"
import { usePromptDialog } from "@/components/ui/PromptDialog"
import { useConfirmDialog } from "@/components/ui/ConfirmDialog"
import { ErrorCard } from "@/components/ui/ErrorCard"
import { WorkspaceSidePanel } from "@/components/ui/WorkspaceSidePanel"
import {
  ActionButton,
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
  normalizeSceneMetadata,
  saveSceneFolders,
  sceneFolder,
} from "./scenesPage.helpers"
import { SceneSelectionActions, useSceneSelectionMenu } from "./scenesPage.selection"
import { useSceneNavigationGuard } from "./scenesPage.navigation"
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
  const [actionError, setActionError] = useState<string | null>(null)
  const baselineRef = useRef<string | null>(null)
  const newDraftRef = useRef(false)
  const savingRef = useRef(false)
  savingRef.current = saving
  const draftSignature = JSON.stringify({ title, description, body, htmlBody, chapterNumber, sceneMetadata, sceneFolderDraft })
  if (baselineRef.current === null) baselineRef.current = draftSignature
  const dirty = baselineRef.current !== null && baselineRef.current !== draftSignature
  const dirtyRef = useRef(dirty)
  dirtyRef.current = dirty
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({})
  const [browserView, setBrowserView] = useState<BrowserView>("folders")
  const [outlineOpen, setOutlineOpen] = useState(false)
  const [inspectorOpen, setInspectorOpen] = useState(false)
  const [showWritingTools, setShowWritingTools] = useState(false)
  const [firstLineIndent, setFirstLineIndent] = useState(false)
  const { selectionMenu, addCharacterOpen, addCharacterText, setAddCharacterOpen, openAddCharacterFromSelection, handleCharacterCreated } = useSceneSelectionMenu(setStatus)
  const selectedSceneIdRef = useRef(selectedSceneId)
  selectedSceneIdRef.current = selectedSceneId
  const prompt = usePromptDialog()
  const confirm = useConfirmDialog()
  useSceneNavigationGuard(dirtyRef, confirm)

  const { data: book = null } = useBookDetail(bookId)
  const {
    data: tree = null,
    isLoading: treeLoading,
    isError: treeError,
    refetch: refetchTree,
  } = useQuery<ManuscriptWorkspaceTree | null>({
    queryKey: asQueryKey(bookCacheKey(bookId, "workspace-tree")),
    queryFn: () => booksApi.getWorkspaceTree(bookId, { includeSceneBodies: true }),
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
      return [scene.title, scene.description ?? "", scene.body ?? "", scene.path].some((value) => value.toLowerCase().includes(term))
    })
  }, [deferredSearch, scenes, selectedFolder])

  const sceneWordCount = useMemo(() => countWords(body), [body])
  const sceneReadingTime = useMemo(() => formatReadingTimeLabel(estimateReadingTimeMinutes(sceneWordCount)), [sceneWordCount])
  const selectedTagList = (sceneMetadata.tags ?? []).filter(Boolean)
  const selectedMoodList = (sceneMetadata.mood ?? []).filter(Boolean)

  const rememberFolder = (folderPath: string | null | undefined) => {
    const normalized = normalizeWorkspaceFolderPath(folderPath)
    if (!normalized) return
    setCustomFolders((current) => [...new Set([...current, normalized])].sort())
  }

  const selectScene = useCallback((scene: WorkspaceScene) => {
    const inferredChapterNumber = scene.chapter_number ?? extractChapterNumberFromSceneFolder(scene.path)
    const folderPath = sceneFolder(scene.path) || defaultSceneFolder(inferredChapterNumber)
    const sceneBody = scene.body ?? ""
    const sceneHtml = scene.html_body ?? `<p>${sceneBody.replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replace(/\n/g, "<br>")}</p>`
    const metadata = { ...emptySceneMetadata(), ...(scene.metadata ?? {}) }
    baselineRef.current = JSON.stringify({ title: scene.title, description: scene.description ?? "", body: sceneBody, htmlBody: sceneHtml, chapterNumber: inferredChapterNumber, sceneMetadata: metadata, sceneFolderDraft: folderPath })
    newDraftRef.current = false
    setSelectedSceneId(scene.id)
    setSelectedFolder(sceneFolder(scene.path) || null)
    setTitle(scene.title)
    setDescription(scene.description ?? "")
    setBody(sceneBody)
    setHtmlBody(sceneHtml)
    setChapterNumber(inferredChapterNumber)
    setSceneMetadata(metadata)
    setSceneFolderDraft(folderPath)
    if (typeof window !== "undefined" && typeof window.matchMedia === "function" && !window.matchMedia("(min-width: 1280px)").matches) {
      setOutlineOpen(false)
    }
  }, [])

  const syncWorkspaceSelection = useCallback((treeData: ManuscriptWorkspaceTree | null, preferredSceneId?: string | null) => {
    const availableScenes = treeData?.scene_groups.flatMap((group) => group.scenes) ?? []
    const nextSceneId = preferredSceneId ?? selectedSceneIdRef.current
    const matchedScene = nextSceneId ? availableScenes.find((scene) => scene.id === nextSceneId) ?? null : null
    const fallbackScene = matchedScene ?? availableScenes[0] ?? null
    if (fallbackScene) {
      selectScene(fallbackScene)
      return
    }
    setSelectedSceneId(null)
  }, [selectScene])

  useEffect(() => {
    setCustomFolders(loadSceneFolders(bookId))
  }, [bookId])

  useEffect(() => saveSceneFolders(bookId, customFolders), [bookId, customFolders])

  useEffect(() => {
    if (!dirtyRef.current && !newDraftRef.current && !savingRef.current) syncWorkspaceSelection(tree)
  }, [syncWorkspaceSelection, tree])

  const confirmDraftChange = async () => !dirtyRef.current || await confirm({
    title: "Discard unsaved scene changes?",
    body: "Save this scene first to keep your edits, or discard them to continue.",
    confirmLabel: "Discard changes",
    cancelLabel: "Keep editing",
    tone: "danger",
  })

  const chooseScene = async (scene: WorkspaceScene) => {
    if (savingRef.current || scene.id === selectedSceneIdRef.current || !await confirmDraftChange()) return
    selectScene(scene)
    setStatus(null)
    setActionError(null)
  }

  function newScene(folderOverride?: string | null) {
    const destinationFolder = normalizeWorkspaceFolderPath(folderOverride ?? selectedFolder) || defaultSceneFolder(chapterNumber)
    const inferredChapterNumber = extractChapterNumberFromSceneFolder(destinationFolder)
    const nextChapter = inferredChapterNumber ?? chapterOptions[0] ?? null
    const metadata = emptySceneMetadata()
    baselineRef.current = JSON.stringify({ title: "", description: "", body: "", htmlBody: "<p></p>", chapterNumber: nextChapter, sceneMetadata: metadata, sceneFolderDraft: destinationFolder })
    newDraftRef.current = true
    rememberFolder(destinationFolder)
    setSelectedSceneId(null)
    setTitle("")
    setDescription("")
    setBody("")
    setHtmlBody("<p></p>")
    setChapterNumber(nextChapter)
    setSceneMetadata(metadata)
    setSceneFolderDraft(destinationFolder)
    setStatus(null)
    setActionError(null)
    if (typeof window !== "undefined" && typeof window.matchMedia === "function" && !window.matchMedia("(min-width: 1280px)").matches) {
      setOutlineOpen(false)
    }
  }

  const startNewScene = async () => {
    if (!savingRef.current && await confirmDraftChange()) newScene()
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
    setCollapsed((current) => ({ ...current, [cleanFolder]: false }))
    setStatus(`Created folder ${cleanFolder}`)
  }

  const saveScene = async () => {
    if (savingRef.current || !title.trim() || !body.trim()) return
    savingRef.current = true
    setSaving(true)
    setActionError(null)
    setStatus(null)
    try {
      const destinationFolder = normalizeWorkspaceFolderPath(sceneFolderDraft) || defaultSceneFolder(chapterNumber)
      rememberFolder(destinationFolder)
      const saved = await booksApi.saveScene(bookId, {
        id: selectedSceneId ?? undefined,
        title: title.trim(),
        description: description.trim() || null,
        body,
        html_body: htmlBody,
        metadata: normalizeSceneMetadata(sceneMetadata),
        path: buildScenePath(destinationFolder, title.trim()),
        chapter_number: chapterNumber,
        status: chapterNumber ? "assigned" : "unassigned",
        sort_order: selectedScene?.sort_order ?? 1,
      })
      setStatus("Scene saved. Metadata refreshed from the scene text.")
      baselineRef.current = draftSignature
      newDraftRef.current = false
      setSelectedSceneId(saved.id)
      selectedSceneIdRef.current = saved.id
      const { data: nextTree } = await refetchTree()
      const refreshedScene = nextTree?.scene_groups.flatMap((group) => group.scenes).find((scene) => scene.id === saved.id)
      if (refreshedScene) selectScene(refreshedScene)
    } catch {
      setActionError("Could not save this scene. Your edits are still here; try Save scene again.")
    } finally {
      savingRef.current = false
      setSaving(false)
    }
  }

  const moveSceneToFolder = async (sceneId: string, destinationFolder: string | null) => {
    if (savingRef.current || !await confirmDraftChange()) return
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

    savingRef.current = true
    setSaving(true)
    setActionError(null)
    try {
      rememberFolder(cleanFolder)
      await booksApi.saveScene(bookId, {
        id: scene.id,
        title: scene.title,
        description: scene.description,
        body: scene.body ?? "",
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
      setActionError("Could not move this scene. Its folder has not changed; try again.")
    } finally {
      savingRef.current = false
      setSaving(false)
      setDropTargetFolder(null)
    }
  }

  const deleteScene = async () => {
    if (!selectedScene || savingRef.current) return
    if (!await confirm({ title: "Delete this scene?", body: `Delete “${selectedScene.title}” and its text? This cannot be undone.`, confirmLabel: "Delete scene", tone: "danger" })) return
    savingRef.current = true
    setSaving(true)
    setActionError(null)
    try {
      await booksApi.deleteScene(bookId, selectedScene.id)
      newScene(selectedFolder)
      const { data: nextTree } = await refetchTree()
      syncWorkspaceSelection(nextTree ?? null)
      setStatus("Scene deleted.")
    } catch {
      setActionError("Could not delete this scene. Your scene is still available; try again.")
    } finally {
      savingRef.current = false
      setSaving(false)
    }
  }

  const workspaceColumns = outlineOpen && inspectorOpen
    ? "xl:grid-cols-[21rem_minmax(0,1fr)_22rem]"
    : outlineOpen
      ? "xl:grid-cols-[21rem_minmax(0,1fr)]"
      : inspectorOpen
        ? "xl:grid-cols-[minmax(0,1fr)_22rem]"
        : "xl:grid-cols-1"

  return (
    <div data-scene-workspace className={`min-h-screen ${isDark ? "bg-[#071211] text-slate-100" : "bg-stone-50 text-stone-950"}`}>
      <div className="w-full px-4 pb-12 pt-5 sm:px-5 lg:px-6">
        <main className="min-w-0 space-y-6">
            <AuthorToolsNav
              active="scenes"
              bookData={book}
              bookId={bookId}
              isDark={isDark}
              mode={book?.mode ?? "author"}
              title={book?.title || "Scene workspace"}
              variant="bar"
            />
            <WorkspaceHeader
              book={book}
              isDark={isDark}
              disabled={saving || !tree}
              onNewScene={() => void startNewScene()}
              onNewFolder={() => void createFolder()}
            />

            <MobilePanelToggles
              isDark={isDark}
              showBrowser={outlineOpen}
              showInspector={inspectorOpen}
              onToggleBrowser={() => setOutlineOpen((current) => !current)}
              onToggleInspector={() => setInspectorOpen((current) => !current)}
            />

            {actionError ? <p role="alert" className={`border-l-2 px-3 py-2 text-sm ${isDark ? "border-rose-400 text-rose-300" : "border-rose-600 text-rose-700"}`}>{actionError}</p> : null}
            {treeError && tree ? <ErrorCard variant="compact" isDark={isDark} message="Could not refresh the scene list. Your current edits are preserved." onRetry={() => void refetchTree()} /> : null}
            <section className={`border-y ${isDark ? "border-white/10" : "border-stone-200"}`}>
              {treeLoading && !tree ? (
                <WorkspaceStateCard
                  isDark={isDark}
                  title="Loading scene workspace"
                  body="Fetching scene files, folders, and structure for this manuscript."
                />
              ) : treeError && !tree ? (
                <WorkspaceStateCard
                  isDark={isDark}
                  title="Scene workspace unavailable"
                  body="We couldn't load the current scene workspace. Try again to refresh the folder tree and scene list."
                  action={<ActionButton type="button" variant="secondary" isDark={isDark} onClick={() => void refetchTree()}>Retry</ActionButton>}
                />
              ) : (
                <div className={`grid gap-0 xl:min-h-[44rem] ${workspaceColumns}`}>
                  {outlineOpen ? (
                    <WorkspaceSidePanel title="Scene outline" side="left" onClose={() => setOutlineOpen(false)}>
                    <div inert={saving}>
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
                      onSelectScene={(scene) => void chooseScene(scene)}
                      onCreateScene={() => void startNewScene()}
                    />
                      </div>
                    </WorkspaceSidePanel>
                  ) : null}

                  <div className="min-w-0 border-y xl:border-x xl:border-y-0" style={{ borderColor: isDark ? "rgba(255,255,255,0.08)" : "rgba(216, 216, 216, 0.9)" }}>
                    <div className="mx-auto min-w-0 max-w-[1040px] py-4 sm:px-3 sm:py-5 xl:px-5">
                      <div className="grid min-w-0 gap-5">
                        <SceneEditorPanel
                          isDark={isDark}
                          title={title}
                          chapterNumber={chapterNumber}
                          chapterOptions={chapterOptions}
                          htmlBody={htmlBody}
                          wordCount={sceneWordCount}
                          readingTime={sceneReadingTime}
                          status={status}
                          dirty={dirty}
                          saving={saving}
                          canSave={Boolean(title.trim() && body.trim())}
                          hasSelectedScene={Boolean(selectedScene)}
                          firstLineIndent={firstLineIndent}
                          onTitleChange={setTitle}
                          onChapterNumberChange={setChapterNumber}
                          onToggleFirstLineIndent={() => setFirstLineIndent((value) => !value)}
                          onHtmlChange={(nextHtml, nextText) => {
                            setHtmlBody(nextHtml)
                            setBody(nextText)
                          }}
                          onDelete={() => void deleteScene()}
                          onSave={() => void saveScene()}
                        />

                        <WritingToolsPanel
                          isDark={isDark}
                          visible={showWritingTools}
                          onOpen={() => startTransition(() => setShowWritingTools(true))}
                          bookId={bookId}
                        />
                      </div>
                    </div>
                  </div>

                  {inspectorOpen ? (
                    <WorkspaceSidePanel title="Scene details" side="right" onClose={() => setInspectorOpen(false)}>
                        <fieldset disabled={saving} className="min-w-0 p-4">
                          <SceneMetadataForm
                            isDark={isDark}
                            description={description}
                            sceneFolderDraft={sceneFolderDraft}
                            sceneMetadata={sceneMetadata}
                            selectedTagList={selectedTagList}
                            selectedMoodList={selectedMoodList}
                            onDescriptionChange={setDescription}
                            onSceneFolderDraftChange={setSceneFolderDraft}
                            onSceneMetadataChange={setSceneMetadata}
                          />
                        </fieldset>
                    </WorkspaceSidePanel>
                  ) : null}
                </div>
              )}
            </section>
        </main>

        <SceneSelectionActions
          bookId={bookId}
          chapterNumber={chapterNumber}
          isDark={isDark}
          menuPosition={selectionMenu}
          selectedText={addCharacterText}
          dialogOpen={addCharacterOpen}
          onOpenDialog={openAddCharacterFromSelection}
          onCloseDialog={() => setAddCharacterOpen(false)}
          onCreated={handleCharacterCreated}
        />
      </div>
    </div>
  )
}
