import type { ShortcutDefinition } from "@/types/ux"

export const GLOBAL_SHORTCUTS: ShortcutDefinition[] = [
  {
    id: "command-palette",
    label: "Open command palette",
    keys: "Ctrl/⌘ K",
    description: "Jump to projects, tools, and common actions.",
  },
  {
    id: "search-focus",
    label: "Focus current search",
    keys: "/",
    description: "Focus the page search field when a screen provides one.",
  },
  {
    id: "escape-close",
    label: "Close overlay",
    keys: "Esc",
    description: "Dismiss dialogs, menus, and temporary panels.",
  },
]

export function formatShortcutList(shortcuts: ShortcutDefinition[]) {
  return shortcuts.map((shortcut) => `${shortcut.keys}: ${shortcut.label}`)
}
