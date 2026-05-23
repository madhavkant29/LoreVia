"use client"

import { useQuery } from "@tanstack/react-query"
import { useEffect, useMemo, useState, type DragEvent as ReactDragEvent } from "react"
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

type FolderNode = WorkspaceFolderNode
type SceneDragItem = { kind: "scene"; id: string }

const EditorToolbar = dynamic(
  () => import("@/components/editor/SharedRichTextEditor").then((module) => module.EditorToolbar),
  { ssr: false }
)

const AuthorToolsNav = dynamic(
  () => import("@/components/layout/AuthorToolsNav").then((module) => module.AuthorToolsNav),
  {
    ssr: false,
    loading: () => <div className="rounded-[1.8rem] border border-dashed p-8" />,
  }
)

const RichTextEditor = dynamic(
  () => import("@/components/editor/SharedRichTextEditor").then((module) => module.RichTextEditor),
  {
    ssr: false,
    loading: () => <div className="min-h-[32rem] animate-pulse bg-black/5" />,
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

  const { data: book = null } = useBookDetail(bookId)
  const {
    data: tree = null,
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

  const filteredScenes = useMemo(() => {
    const term = search.trim().toLowerCase()
    return scenes.filter((scene) => {
      const folderMatches = !selectedFolder || sceneFolder(scene.path) === selectedFolder || sceneFolder(scene.path).startsWith(`${selectedFolder}/`)
      if (!folderMatches) return false
      if (!term) return true
      return [scene.title, scene.description ?? "", scene.body, scene.path].some((value) => value.toLowerCase().includes(term))
    })
  }, [scenes, search, selectedFolder])

  const metadataRows = useMemo(() => {
    const metadata = selectedScene?.metadata ?? sceneMetadata ?? {}
    return Object.entries(metadata).filter(([, value]) => {
      if (Array.isArray(value)) return value.length > 0
      return value !== null && value !== undefined && String(value).trim() !== ""
    })
  }, [sceneMetadata, selectedScene])
  const sceneWordCount = useMemo(() => countWords(body), [body])
  const sceneReadingTime = useMemo(() => formatReadingTimeLabel(estimateReadingTimeMinutes(sceneWordCount)), [sceneWordCount])

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
    <div className={`min-h-screen ${isDark ? "bg-[linear-gradient(180deg,#020617_0%,#07111c_52%,#111827_100%)] text-slate-100" : "bg-[linear-gradient(180deg,#f7f0df_0%,#edf6ee_48%,#eef5f9_100%)] text-stone-950"}`}>
      <div className="mx-auto max-w-[108rem] px-4 pb-20 pt-6 sm:px-6 lg:px-8">
        <div className="grid gap-6 xl:grid-cols-[17rem_minmax(0,1fr)]">
          <AuthorToolsNav
            bookId={bookId}
            active="scenes"
            isDark={isDark}
            bookData={book}
            title="Scene workspace"
            description="Draft, organize, and prepare scene files before pulling them into the manuscript."
          />

          <main className="space-y-6">
            <section className={`overflow-hidden rounded-[2rem] border ${isDark ? "border-white/10 bg-white/[0.04]" : "border-white/70 bg-white/85"}`}>
              <div className={`border-b px-6 py-6 ${isDark ? "border-white/10" : "border-stone-200"}`}>
                <p className={`text-[11px] font-semibold uppercase tracking-[0.28em] ${isDark ? "text-emerald-300" : "text-emerald-700"}`}>Scene workspace</p>
                <div className="mt-3 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
                  <div>
                    <h1 className="font-serif text-4xl">{book?.title || "Manuscript"} scenes</h1>
                    <p className={`mt-2 max-w-3xl text-sm leading-7 ${isDark ? "text-slate-300" : "text-stone-600"}`}>
                      Organize scenes with nested folders, move them between planning buckets, and keep metadata attached when you import them into the manuscript.
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-3">
                    <button onClick={() => newScene()} className="rounded-full bg-[linear-gradient(135deg,#0f766e,#115e59)] px-4 py-2 text-sm font-semibold text-white">
                      New scene
                    </button>
                    <button onClick={() => createFolder()} className={`rounded-full px-4 py-2 text-sm font-semibold ${isDark ? "bg-white/10 text-slate-100" : "bg-stone-100 text-stone-800"}`}>
                      New folder
                    </button>
                    <Link href={`/${bookId}/notes`} className={`rounded-full px-4 py-2 text-sm font-semibold ${isDark ? "bg-white/10 text-slate-100" : "bg-white text-stone-800"}`}>
                      Open notes
                    </Link>
                    <Link href={`/${bookId}/voice` as Route} className={`rounded-full px-4 py-2 text-sm font-semibold ${isDark ? "bg-white/10 text-slate-100" : "bg-white text-stone-800"}`}>
                      Open voice workspace
                    </Link>
                    <Link href={`/${bookId}/manuscript`} className={`rounded-full px-4 py-2 text-sm font-semibold ${isDark ? "bg-white/10 text-slate-100" : "bg-stone-900 text-white"}`}>
                      Open manuscript
                    </Link>
                  </div>
                </div>
              </div>

              <div className="grid min-h-[46rem] lg:grid-cols-[23rem_minmax(0,1fr)_20rem]">
                <aside className={`border-r p-5 ${isDark ? "border-white/10 bg-black/20" : "border-stone-200 bg-stone-50/70"}`}>
                  <label className={`flex items-center gap-2 rounded-[1rem] border px-4 py-3 text-sm ${isDark ? "border-white/10 bg-black text-slate-100 placeholder:text-slate-500" : "border-stone-200 bg-white text-stone-900 placeholder:text-stone-400"}`}>
                    <IconSearch />
                    <input
                      value={search}
                      onChange={(event) => setSearch(event.target.value)}
                      placeholder="Search scenes or folders"
                      className="min-w-0 flex-1 bg-transparent outline-none"
                    />
                  </label>

                  <div className="mt-6 flex items-center justify-between">
                    <p className={`text-[11px] font-semibold uppercase tracking-[0.28em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Folders</p>
                    <button type="button" onClick={() => createFolder()} className={`rounded-full p-1.5 ${isDark ? "text-slate-400 hover:bg-white/[0.06] hover:text-white" : "text-stone-500 hover:bg-stone-100 hover:text-stone-900"}`} title="Create folder">
                      <IconPlus />
                    </button>
                  </div>

                  <div className="mt-3 max-h-[19rem] overflow-auto pr-1">
                    <button
                      type="button"
                      onClick={() => setSelectedFolder(null)}
                      onDragOver={(event) => {
                        if (!parseSceneDragItem(event)) return
                        event.preventDefault()
                        setDropTargetFolder("")
                      }}
                      onDragLeave={() => setDropTargetFolder((current) => (current === "" ? null : current))}
                      onDrop={(event) => {
                        const dragItem = parseSceneDragItem(event)
                        if (!dragItem) return
                        event.preventDefault()
                        void moveSceneToFolder(dragItem.id, null)
                      }}
                      className={`mb-2 flex w-full items-center justify-between rounded-xl px-3 py-2 text-left text-sm transition ${
                        !selectedFolder
                          ? isDark
                            ? "bg-emerald-500/12 text-emerald-100"
                            : "bg-emerald-50 text-emerald-800"
                          : isDark
                            ? "text-slate-300 hover:bg-white/[0.04]"
                            : "text-stone-700 hover:bg-stone-100"
                      } ${dropTargetFolder === "" ? (isDark ? "ring-1 ring-sky-400/60" : "ring-1 ring-sky-300") : ""}`}
                    >
                      <span className="font-medium">All scenes</span>
                      <span className={`text-xs ${isDark ? "text-slate-500" : "text-stone-400"}`}>{scenes.length}</span>
                    </button>
                    <SceneFolderTree
                      node={folderTree}
                      activePath={selectedFolder}
                      collapsed={collapsed}
                      onToggleFolder={(path) => setCollapsed((current) => ({ ...current, [path]: !current[path] }))}
                      onSelect={setSelectedFolder}
                      onCreateFolder={createFolder}
                      onDropScene={(sceneId, folderPath) => void moveSceneToFolder(sceneId, folderPath)}
                      dropTargetPath={dropTargetFolder}
                      onDropTargetChange={setDropTargetFolder}
                      isDark={isDark}
                    />
                  </div>

                  <div className="mt-6">
                    <div className="flex items-center justify-between gap-3">
                      <p className={`text-[11px] font-semibold uppercase tracking-[0.28em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Scenes</p>
                      <button type="button" onClick={() => newScene(selectedFolder)} className={`rounded-full px-3 py-1 text-xs font-semibold ${isDark ? "bg-white/10 text-slate-200" : "bg-white text-stone-700"}`}>
                        New
                      </button>
                    </div>
                    <div className="mt-3 max-h-[18rem] space-y-2 overflow-auto pr-1">
                      {filteredScenes.length === 0 ? (
                        <p className={`rounded-[1rem] border border-dashed px-4 py-8 text-center text-sm ${isDark ? "border-white/10 text-slate-500" : "border-stone-300 text-stone-500"}`}>No scenes match this view.</p>
                      ) : filteredScenes.map((scene) => (
                        <button
                          key={scene.id}
                          type="button"
                          draggable
                          onDragStart={(event) => {
                            const payload: SceneDragItem = { kind: "scene", id: scene.id }
                            event.dataTransfer.effectAllowed = "move"
                            event.dataTransfer.setData("application/lorevia-scene-item", JSON.stringify(payload))
                          }}
                          onClick={() => selectScene(scene)}
                          className={`block w-full rounded-[0.95rem] border px-3 py-3 text-left transition ${
                            selectedSceneId === scene.id
                              ? isDark
                                ? "border-emerald-300/40 bg-emerald-400/15 text-white"
                                : "border-emerald-300 bg-emerald-50 text-stone-950"
                              : isDark
                                ? "border-white/10 bg-black/20 text-slate-300 hover:bg-white/10"
                                : "border-stone-200 bg-white text-stone-700 hover:bg-stone-50"
                          }`}
                        >
                          <span className="block truncate text-sm font-semibold">{scene.title}</span>
                          <span className={`mt-1 block truncate text-[11px] ${isDark ? "text-slate-500" : "text-stone-400"}`}>{scene.path}</span>
                        </button>
                      ))}
                    </div>
                  </div>
                </aside>

                <section className="p-5">
                  <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_12rem]">
                    <label className="text-sm">
                      <span className={labelClass(isDark)}>Scene title</span>
                      <input value={title} onChange={(event) => setTitle(event.target.value)} className={inputClass(isDark)} placeholder="Scene title" />
                    </label>
                    <label className="text-sm">
                      <span className={labelClass(isDark)}>Chapter</span>
                      <select value={chapterNumber ?? ""} onChange={(event) => setChapterNumber(event.target.value ? Number(event.target.value) : null)} className={inputClass(isDark)}>
                        <option value="">Unassigned</option>
                        {chapterOptions.map((chapterNumberOption) => (
                          <option key={chapterNumberOption} value={chapterNumberOption}>Chapter {chapterNumberOption}</option>
                        ))}
                      </select>
                    </label>
                  </div>
                  <label className="mt-4 block text-sm">
                    <span className={labelClass(isDark)}>Folder path</span>
                    <input value={sceneFolderDraft} onChange={(event) => setSceneFolderDraft(event.target.value)} className={inputClass(isDark)} placeholder="scenes/act-1/opening" />
                  </label>
                  <label className="mt-4 block text-sm">
                    <span className={labelClass(isDark)}>Description</span>
                    <input value={description} onChange={(event) => setDescription(event.target.value)} className={inputClass(isDark)} placeholder="Optional scene summary" />
                  </label>
                  <div className="mt-4 grid gap-4 lg:grid-cols-2">
                    <label className="text-sm">
                      <span className={labelClass(isDark)}>POV character</span>
                      <input value={sceneMetadata.pov ?? ""} onChange={(event) => setSceneMetadata((current) => ({ ...current, pov: event.target.value || null }))} className={inputClass(isDark)} placeholder="Whose eyes are we in?" />
                    </label>
                    <label className="text-sm">
                      <span className={labelClass(isDark)}>Timeline / date</span>
                      <input value={sceneMetadata.timeline ?? ""} onChange={(event) => setSceneMetadata((current) => ({ ...current, timeline: event.target.value || null }))} className={inputClass(isDark)} placeholder="Day 3, Winter court, 8:12 PM" />
                    </label>
                    <label className="text-sm">
                      <span className={labelClass(isDark)}>Location</span>
                      <input value={sceneMetadata.location ?? ""} onChange={(event) => setSceneMetadata((current) => ({ ...current, location: event.target.value || null }))} className={inputClass(isDark)} placeholder="Blackwater Station" />
                    </label>
                    <label className="text-sm">
                      <span className={labelClass(isDark)}>Mood / tone</span>
                      <input value={(sceneMetadata.mood ?? []).join(", ")} onChange={(event) => setSceneMetadata((current) => ({ ...current, mood: metadataTextToList(event.target.value) }))} className={inputClass(isDark)} placeholder="tense, intimate, foreboding" />
                    </label>
                    <label className="text-sm">
                      <span className={labelClass(isDark)}>Tags</span>
                      <input value={(sceneMetadata.tags ?? []).join(", ")} onChange={(event) => setSceneMetadata((current) => ({ ...current, tags: metadataTextToList(event.target.value) }))} className={inputClass(isDark)} placeholder="betrayal, dagger, reveal" />
                    </label>
                    <label className="text-sm">
                      <span className={labelClass(isDark)}>Status note</span>
                      <input value={sceneMetadata.status_note ?? ""} onChange={(event) => setSceneMetadata((current) => ({ ...current, status_note: event.target.value || null }))} className={inputClass(isDark)} placeholder="Draft, revised, final, waiting on continuity pass" />
                    </label>
                  </div>
                  <WhatsTheWordPanel bookId={bookId} isDark={isDark} className="mt-4" />
                  <label className="mt-4 block text-sm">
                    <span className={labelClass(isDark)}>Scene text</span>
                    <div className={`overflow-hidden rounded-[1.2rem] border ${isDark ? "border-white/10 bg-black" : "border-stone-200 bg-white"}`}>
                      <EditorToolbar editorKey="scene-workspace-editor" isDark={isDark} compact />
                      <RichTextEditor
                        editorKey="scene-workspace-editor"
                        html={htmlBody}
                        onChange={(nextHtml, nextText) => {
                          setHtmlBody(nextHtml)
                          setBody(nextText)
                        }}
                        placeholder={"Rain hammered the platform while Elena counted the seconds until the train lights found her..."}
                        className={`min-h-[32rem] px-5 py-4 font-serif text-base leading-8 outline-none ${isDark ? "text-slate-100" : "text-stone-900"}`}
                      />
                    </div>
                  </label>
                  <div className="mt-5 flex flex-wrap items-center justify-between gap-3">
                    <p className={`text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>{status ?? `Drag scene cards onto folders to reorganize them. ${sceneWordCount.toLocaleString()} words, ${sceneReadingTime}.`}</p>
                    <div className="flex flex-wrap gap-3">
                      {selectedScene ? (
                        <button onClick={() => void deleteScene()} className={`rounded-full px-4 py-2 text-sm ${isDark ? "bg-rose-500/10 text-rose-200" : "bg-rose-50 text-rose-700"}`}>Delete</button>
                      ) : null}
                      <button onClick={() => void saveScene()} disabled={saving || !title.trim() || !body.trim()} className="rounded-full bg-[linear-gradient(135deg,#0f766e,#115e59)] px-5 py-2 text-sm font-semibold text-white disabled:opacity-50">
                        {saving ? "Saving..." : "Save scene"}
                      </button>
                    </div>
                  </div>
                </section>

                <aside className={`border-l p-5 ${isDark ? "border-white/10 bg-black/20" : "border-stone-200 bg-stone-50/70"}`}>
                  <p className={`text-[11px] font-semibold uppercase tracking-[0.2em] ${isDark ? "text-slate-400" : "text-stone-500"}`}>Metadata preview</p>
                  <div className="mt-4 space-y-3">
                    {metadataRows.length === 0 ? (
                      <p className={`rounded-[1rem] border border-dashed px-4 py-8 text-sm leading-6 ${isDark ? "border-white/10 text-slate-500" : "border-stone-300 text-stone-500"}`}>
                        Save labels such as POV, Location, Time, Characters, Goals, Conflict, Objects, Plot Threads, or Mood to populate this panel.
                      </p>
                    ) : metadataRows.map(([key, value]) => (
                      <div key={key} className={`rounded-[1rem] border px-4 py-3 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-stone-200 bg-white"}`}>
                        <p className={`text-[10px] font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>{key.replaceAll("_", " ")}</p>
                        <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-200" : "text-stone-700"}`}>{formatMetadataValue(value)}</p>
                      </div>
                    ))}
                  </div>
                  <div className={`mt-5 rounded-[1rem] border px-4 py-4 text-sm leading-6 ${isDark ? "border-emerald-300/20 bg-emerald-400/10 text-emerald-100" : "border-emerald-200 bg-emerald-50 text-emerald-800"}`}>
                    Scene files now follow folder paths directly, so you can keep planning by act, chapter, POV, or any other structure that fits your process.
                  </div>
                  <div className={`mt-4 rounded-[1rem] border px-4 py-4 text-sm leading-6 ${isDark ? "border-white/10 bg-white/[0.03] text-slate-300" : "border-stone-200 bg-white text-stone-700"}`}>
                    <p className="font-semibold">Current file</p>
                    <p className={`mt-2 break-all text-xs ${isDark ? "text-slate-400" : "text-stone-500"}`}>
                      {title.trim() ? buildScenePath(sceneFolderDraft, title.trim()) : "Set a title to generate the scene filename."}
                    </p>
                  </div>
                  {tree?.structure_tree?.length ? (
                    <div className={`mt-4 rounded-[1rem] border px-4 py-4 text-sm leading-6 ${isDark ? "border-white/10 bg-white/[0.03] text-slate-300" : "border-stone-200 bg-white text-stone-700"}`}>
                      <p className="font-semibold">Story hierarchy</p>
                      <div className="mt-3 space-y-2">
                        {tree.structure_tree.map((node) => (
                          <StructureTreePreview key={node.id} node={node} isDark={isDark} depth={0} />
                        ))}
                      </div>
                    </div>
                  ) : null}
                </aside>
              </div>
            </section>
          </main>
        </div>
      </div>
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
    <div className="space-y-1">
      {[...node.folders.values()].map((child) => {
        const isCollapsed = Boolean(collapsed[child.path])
        const active = child.path === activePath
        return (
          <div key={child.path}>
            <div className="flex items-center gap-1">
              <button
                type="button"
                onClick={() => onToggleFolder(child.path)}
                className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ${isDark ? "text-slate-500 hover:bg-white/[0.05] hover:text-slate-200" : "text-stone-400 hover:bg-stone-100 hover:text-stone-700"}`}
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
                className={`flex min-w-0 flex-1 items-center justify-between rounded-xl px-3 py-2 text-left text-sm transition ${
                  active
                    ? isDark
                      ? "bg-emerald-500/12 text-emerald-100"
                      : "bg-emerald-50 text-emerald-800"
                    : isDark
                      ? "text-slate-300 hover:bg-white/[0.04]"
                      : "text-stone-700 hover:bg-stone-100"
                } ${dropTargetPath === child.path ? (isDark ? "ring-1 ring-sky-400/60" : "ring-1 ring-sky-300") : ""}`}
              >
                <span className="flex min-w-0 items-center gap-2">
                  <IconFolder />
                  <span className="truncate font-medium">{child.name}</span>
                </span>
                <span className={`text-xs ${active ? (isDark ? "text-emerald-200/80" : "text-emerald-700/80") : isDark ? "text-slate-500" : "text-stone-400"}`}>{child.itemCount}</span>
              </button>
              <button
                type="button"
                onClick={() => onCreateFolder(child.path)}
                className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ${isDark ? "text-slate-500 hover:bg-white/[0.05] hover:text-white" : "text-stone-400 hover:bg-stone-100 hover:text-stone-800"}`}
                title={`Create a folder inside ${child.name}`}
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

function formatMetadataValue(value: unknown) {
  if (Array.isArray(value)) return value.join(", ")
  return String(value ?? "")
}

function labelClass(isDark: boolean) {
  return `mb-2 block text-xs font-semibold uppercase tracking-[0.16em] ${isDark ? "text-slate-400" : "text-stone-500"}`
}

function inputClass(isDark: boolean) {
  return `w-full rounded-[0.95rem] border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-black text-slate-100" : "border-stone-200 bg-white text-stone-900"}`
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

function StructureTreePreview({
  node,
  isDark,
  depth,
}: {
  node: NonNullable<ManuscriptWorkspaceTree["structure_tree"]>[number]
  isDark: boolean
  depth: number
}) {
  return (
    <div style={{ marginLeft: `${depth * 12}px` }}>
      <p className={`text-sm ${isDark ? "text-slate-200" : "text-stone-700"}`}>{node.label}</p>
      {node.children?.length ? (
        <div className="mt-1 space-y-1">
          {node.children.map((child) => (
            <StructureTreePreview key={child.id} node={child} isDark={isDark} depth={depth + 1} />
          ))}
        </div>
      ) : null}
    </div>
  )
}
