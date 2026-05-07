export type WorkspaceFolderNode = {
  name: string
  path: string
  folders: Map<string, WorkspaceFolderNode>
  itemCount: number
}

export function normalizeWorkspaceFolderPath(value: string | null | undefined) {
  return (value ?? "").replace(/\\/g, "/").trim().replace(/^\/+|\/+$/g, "")
}

export function workspaceFolderName(path: string) {
  return normalizeWorkspaceFolderPath(path).split("/").filter(Boolean).pop() || "Folder"
}

export function workspaceFolderFromPath(path: string) {
  const normalized = path.replace(/\\/g, "/")
  return normalized.split("/").slice(0, -1).join("/")
}

export function workspaceFileTitle(path: string) {
  return path.split("/").pop()?.replace(/\.md$/i, "") || path
}

export function sanitizeWorkspaceTitle(value: string, fallback = "Untitled") {
  return value.replace(/[<>:"|?*]+/g, "").trim() || fallback
}

export function ensureWorkspaceFolderNode(root: WorkspaceFolderNode, folderPath: string) {
  const normalized = normalizeWorkspaceFolderPath(folderPath)
  const segments = normalized.split("/").filter(Boolean)
  let cursor = root
  for (const segment of segments) {
    const nextPath = cursor.path ? `${cursor.path}/${segment}` : segment
    if (!cursor.folders.has(segment)) {
      cursor.folders.set(segment, { name: segment, path: nextPath, folders: new Map(), itemCount: 0 })
    }
    cursor = cursor.folders.get(segment)!
  }
  return cursor
}

export function buildWorkspaceFolderTree(paths: string[], seededFolders: string[] = []) {
  const root: WorkspaceFolderNode = { name: "All items", path: "", folders: new Map(), itemCount: 0 }
  for (const folderPath of seededFolders) {
    ensureWorkspaceFolderNode(root, folderPath)
  }
  for (const fullPath of [...paths].sort()) {
    const segments = fullPath.split("/").slice(0, -1)
    let cursor = root
    for (const segment of segments) {
      const nextPath = cursor.path ? `${cursor.path}/${segment}` : segment
      if (!cursor.folders.has(segment)) {
        cursor.folders.set(segment, { name: segment, path: nextPath, folders: new Map(), itemCount: 0 })
      }
      cursor = cursor.folders.get(segment)!
      cursor.itemCount += 1
    }
  }
  return root
}

export function buildUniqueWorkspacePath(
  existingPaths: string[],
  folder: string | null,
  baseTitle: string,
  extension = ".md"
) {
  const cleanFolder = normalizeWorkspaceFolderPath(folder)
  const cleanBase = sanitizeWorkspaceTitle(baseTitle, "Untitled")
  const existing = new Set(existingPaths.map((path) => path.toLowerCase()))
  let attempt = 1
  while (attempt < 5000) {
    const titled = attempt === 1 ? cleanBase : `${cleanBase} ${attempt}`
    const filename = `${titled}${extension}`
    const path = cleanFolder ? `${cleanFolder}/${filename}` : filename
    if (!existing.has(path.toLowerCase())) return path
    attempt += 1
  }
  return `${Date.now()}${extension}`
}

export function buildUniqueWorkspacePathFromCandidate(
  existingPaths: string[],
  candidatePath: string,
  extension = ".md"
) {
  const normalized = candidatePath.replace(/\\/g, "/").trim().replace(/^\/+|\/+$/g, "")
  const folder = workspaceFolderFromPath(normalized)
  const title = workspaceFileTitle(normalized)
  return buildUniqueWorkspacePath(existingPaths, folder, title, extension)
}
