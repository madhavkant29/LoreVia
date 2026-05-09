"use client"

type FolderNode = {
  name: string
  path: string
  folders: Map<string, FolderNode>
  files: string[]
}

function buildTree(paths: string[]) {
  const root: FolderNode = { name: "All notes", path: "", folders: new Map(), files: [] }
  for (const fullPath of [...paths].sort()) {
    const segments = fullPath.split("/")
    let cursor = root
    for (const segment of segments.slice(0, -1)) {
      const nextPath = cursor.path ? `${cursor.path}/${segment}` : segment
      if (!cursor.folders.has(segment)) {
        cursor.folders.set(segment, { name: segment, path: nextPath, folders: new Map(), files: [] })
      }
      cursor = cursor.folders.get(segment)!
    }
    cursor.files.push(fullPath)
  }
  return root
}

function fileName(path: string) {
  return path.split("/").pop()?.replace(/\.md$/i, "") || path
}

export function FolderTree({
  paths,
  activePath,
  collapsed,
  onToggleFolder,
  onSelect,
  isDark,
}: {
  paths: string[]
  activePath: string | null
  collapsed: Record<string, boolean>
  onToggleFolder: (path: string) => void
  onSelect: (path: string) => void
  isDark: boolean
}) {
  const root = buildTree(paths)

  const renderNode = (node: FolderNode, depth = 0) => {
    const isCollapsed = depth > 0 && collapsed[node.path]
    return (
      <div key={node.path || "root"} className="space-y-1">
        {depth > 0 ? (
          <button
            type="button"
            onClick={() => onToggleFolder(node.path)}
            className={`flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left text-sm ${
              isDark ? "text-slate-300 hover:bg-white/5" : "text-stone-700 hover:bg-stone-100"
            }`}
            style={{ paddingLeft: `${depth * 14}px` }}
          >
            <span className="text-xs">{isCollapsed ? "+" : "-"}</span>
            <span className="font-medium">{node.name}</span>
          </button>
        ) : null}
        {!isCollapsed ? (
          <>
            {[...node.folders.values()].map((child) => renderNode(child, depth + 1))}
            {node.files.map((path) => {
              const active = path === activePath
              return (
                <button
                  key={path}
                  type="button"
                  onClick={() => onSelect(path)}
                  className={`flex w-full items-center rounded-lg px-2 py-2 text-left text-sm transition ${
                    active
                      ? isDark
                        ? "bg-emerald-500/15 text-emerald-100"
                        : "bg-emerald-50 text-emerald-800"
                      : isDark
                        ? "text-slate-300 hover:bg-white/5"
                        : "text-stone-700 hover:bg-stone-100"
                  }`}
                  style={{ paddingLeft: `${(depth + 1) * 14}px` }}
                >
                  {fileName(path)}
                </button>
              )
            })}
          </>
        ) : null}
      </div>
    )
  }

  return renderNode(root)
}
