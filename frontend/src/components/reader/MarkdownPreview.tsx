"use client"

import type { ObsidianVaultNote } from "@/types/book"
import { sanitizeRichTextHtml } from "@/lib/utils/richText"

function escapeHtml(value: string) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
}

type MarkdownRenderOptions = {
  notesByPath?: Map<string, ObsidianVaultNote>
  seen?: Set<string>
  depth?: number
}

function inlineMarkdownToHtml(value: string, options: MarkdownRenderOptions = {}) {
  let html = escapeHtml(value)
  html = html.replace(/`([^`]+)`/g, "<code>$1</code>")
  html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
  html = html.replace(/\*([^*]+)\*/g, "<em>$1</em>")
  html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2">$1</a>')
  html = html.replace(/!\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|([^\]]+))?\]\]/g, (_, target: string, alias?: string) => {
    const trimmedTarget = target.trim()
    const label = escapeHtml((alias || trimmedTarget).trim())
    const note = options.notesByPath ? findNote(options.notesByPath, trimmedTarget) : null
    if (!note) {
      return `<a href="#obsidian-note=${encodeURIComponent(trimmedTarget)}">${label}</a>`
    }

    const seen = options.seen ?? new Set<string>()
    const cycleKey = note.path.toLowerCase()
    if (seen.has(cycleKey) || (options.depth ?? 0) > 4) {
      return `<blockquote><p><strong>Embedded note:</strong> ${label} (already expanded)</p></blockquote>`
    }

    const nextSeen = new Set(seen)
    nextSeen.add(cycleKey)
    const embedded = markdownToHtml(note.content, {
      ...options,
      seen: nextSeen,
      depth: (options.depth ?? 0) + 1,
    })
    return `<blockquote><p><strong>Embedded note:</strong> <a href="#obsidian-note=${encodeURIComponent(note.path)}">${label}</a></p>${embedded}</blockquote>`
  })
  html = html.replace(/\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|([^\]]+))?\]\]/g, (_, target: string, alias?: string) => {
    const safeTarget = encodeURIComponent(target.trim())
    const label = escapeHtml((alias || target).trim())
    return `<a href="#obsidian-note=${safeTarget}">${label}</a>`
  })
  return html
}

function markdownToHtml(value: string, options: MarkdownRenderOptions = {}) {
  const normalized = value.replace(/\r\n/g, "\n")
  const lines = normalized.split("\n")
  const parts: string[] = []
  let inList = false
  let inCode = false
  let codeLines: string[] = []

  const closeList = () => {
    if (!inList) return
    parts.push("</ul>")
    inList = false
  }

  const closeCode = () => {
    if (!inCode) return
    parts.push(`<pre><code>${escapeHtml(codeLines.join("\n"))}</code></pre>`)
    inCode = false
    codeLines = []
  }

  for (const rawLine of lines) {
    const line = rawLine.trimEnd()
    if (line.startsWith("```")) {
      closeList()
      if (inCode) {
        closeCode()
      } else {
        inCode = true
      }
      continue
    }
    if (inCode) {
      codeLines.push(rawLine)
      continue
    }
    if (!line.trim()) {
      closeList()
      continue
    }
    const heading = line.match(/^(#{1,6})\s+(.*)$/)
    if (heading) {
      closeList()
      const level = heading[1].length
      parts.push(`<h${level}>${inlineMarkdownToHtml(heading[2], options)}</h${level}>`)
      continue
    }
    if (/^[-*]\s+/.test(line)) {
      if (!inList) {
        parts.push("<ul>")
        inList = true
      }
      parts.push(`<li>${inlineMarkdownToHtml(line.replace(/^[-*]\s+/, ""), options)}</li>`)
      continue
    }
    closeList()
    parts.push(`<p>${inlineMarkdownToHtml(line, options)}</p>`)
  }

  closeList()
  closeCode()
  return sanitizeRichTextHtml(parts.join(""))
}

export function MarkdownPreview({
  content,
  isDark,
  notes,
  currentPath,
  onOpenNote,
}: {
  content: string
  isDark: boolean
  notes?: ObsidianVaultNote[]
  currentPath?: string | null
  onOpenNote: (reference: string) => void
}) {
  const notesByPath = new Map((notes ?? []).map((note) => [note.path.toLowerCase(), note]))
  const html = markdownToHtml(content, {
    notesByPath,
    seen: currentPath ? new Set([currentPath.toLowerCase()]) : new Set<string>(),
    depth: 0,
  })

  return (
    <div
      className={`note-rich-content min-h-[24rem] rounded-[1.25rem] border px-5 py-4 text-sm leading-7 ${
        isDark ? "border-white/10 bg-[#07111f] text-slate-100" : "border-stone-200 bg-white text-stone-800"
      }`}
      onClick={(event) => {
        const anchor = (event.target as HTMLElement | null)?.closest("a")
        if (!anchor) return
        const href = anchor.getAttribute("href") || ""
        if (!href.startsWith("#obsidian-note=")) return
        event.preventDefault()
        onOpenNote(decodeURIComponent(href.replace("#obsidian-note=", "")))
      }}
      dangerouslySetInnerHTML={{ __html: html }}
    />
  )
}

function findNote(notesByPath: Map<string, ObsidianVaultNote>, reference: string) {
  const normalized = reference.replace(/\.md$/i, "").trim().toLowerCase()
  if (!normalized) return null
  for (const note of notesByPath.values()) {
    const notePath = note.path.toLowerCase()
    const noteTitle = note.path.split("/").pop()?.replace(/\.md$/i, "").trim().toLowerCase() ?? ""
    if (notePath === normalized || noteTitle === normalized) {
      return note
    }
  }
  return null
}
