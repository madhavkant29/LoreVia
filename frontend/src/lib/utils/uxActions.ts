import type { CommandAction, SmartEmptyStateAction } from "@/types/ux"

const RECENT_COMMANDS_KEY = "lorevia-command-recents:v1"
const RECENT_COMMAND_LIMIT = 8

function readStorage(key: string) {
  if (typeof window === "undefined") return null
  try {
    return window.localStorage.getItem(key)
  } catch {
    return null
  }
}

function writeStorage(key: string, value: string) {
  if (typeof window === "undefined") return
  try {
    window.localStorage.setItem(key, value)
  } catch {
    // localStorage can be unavailable in private browsing or tests.
  }
}

function commandHaystack(action: CommandAction) {
  return [action.label, action.description, action.group, action.shortcut, ...(action.keywords ?? [])]
    .filter(Boolean)
    .join(" ")
    .toLowerCase()
}

export function filterCommandActions(actions: CommandAction[], query: string) {
  const normalized = query.trim().toLowerCase()
  if (!normalized) return actions

  const terms = normalized.split(/\s+/).filter(Boolean)
  return actions.filter((action) => {
    const haystack = commandHaystack(action)
    return terms.every((term) => haystack.includes(term))
  })
}

export function loadRecentCommandActionIds() {
  const raw = readStorage(RECENT_COMMANDS_KEY)
  if (!raw) return [] as string[]
  try {
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed.filter((item): item is string => typeof item === "string") : []
  } catch {
    return []
  }
}

export function recordRecentCommandAction(id: string) {
  const next = [id, ...loadRecentCommandActionIds().filter((item) => item !== id)].slice(0, RECENT_COMMAND_LIMIT)
  writeStorage(RECENT_COMMANDS_KEY, JSON.stringify(next))
  return next
}

export function getRecentCommandActions(actions: CommandAction[]) {
  const actionMap = new Map(actions.map((action) => [action.id, action]))
  return loadRecentCommandActionIds()
    .map((id) => actionMap.get(id))
    .filter((action): action is CommandAction => Boolean(action))
}

export function choosePrimaryEmptyStateAction(actions: SmartEmptyStateAction[]) {
  return actions.find((action) => action.tone === "primary") ?? actions[0] ?? null
}
