import type { Book } from "@/types/book"
import { getBookRouteSegment } from "@/lib/utils/bookRoutes"
import type {
  BookPreset,
  ComplexityMode,
  ToolAccess,
  ToolVisibility,
  UserBookUiPreference,
  UserUiPreference,
} from "@/types/uiPreferences"
import type { WorkspaceToolEntry } from "./toolRegistry"
import { complexityRank, routeForTool, toolComplexityRank } from "./toolRegistry"

export interface ToolResolverContext {
  mode: ComplexityMode
  activePath?: string | null
  book?: Book | null
  bookPreference?: UserBookUiPreference | null
  globalPreference?: UserUiPreference | null
  placement?: "dashboard" | "book" | "reader" | "public" | "command"
  hasAuthorAccess?: boolean
  paidUser?: boolean
  currentChapter?: number
}

export interface ResolvedWorkspaceTool {
  tool: WorkspaceToolEntry
  href: string
  access: ToolAccess
  visibility: ToolVisibility
  hidden: boolean
  reason?: string
}

function normalizedActivePath(path: string | null | undefined) {
  return String(path || "").replace(/\/+$/, "") || "/"
}

function bookRouteSegment(book: Book | null | undefined) {
  if (!book) return undefined
  return book.title ? getBookRouteSegment(book) : book.id
}

function routeMatchesActive(tool: WorkspaceToolEntry, href: string, activePath: string) {
  const normalizedHref = normalizedActivePath(href)
  if (tool.route.includes(":chapter")) {
    const prefix = normalizedHref.replace(/\/chapter\/\d+$/, "/chapter")
    return activePath.startsWith(prefix)
  }
  return activePath === normalizedHref
}

function toolRouteMatches(tool: WorkspaceToolEntry, context: ToolResolverContext) {
  const activePath = normalizedActivePath(context.activePath)
  if (!context.activePath) return false
  const chapter = context.currentChapter ?? 1
  const hrefs = new Set([
    routeForTool(tool, bookRouteSegment(context.book), chapter),
    routeForTool(tool, context.book?.id, chapter),
  ])
  return Array.from(hrefs).some((href) => routeMatchesActive(tool, href, activePath))
}

function toolAccess(tool: WorkspaceToolEntry, context: ToolResolverContext): ToolAccess {
  const book = context.book
  const permissions = book?.collaboration_permissions ?? null
  const isOwner = !book || !book.collaboration_role

  const permissionAccess: ToolAccess = (() => {
    switch (tool.permission) {
    case "owner":
      return isOwner ? "available" : "permission_denied"
    case "edit_manuscript":
      return isOwner || permissions?.can_edit_manuscript ? "available" : "permission_denied"
    case "story_bible":
      return isOwner || permissions?.can_view_story_bible ? "available" : "permission_denied"
    case "run_ai_scans":
      return isOwner || permissions?.can_run_ai_scans ? "available" : "permission_denied"
    case "export":
      return isOwner || permissions?.can_export ? "available" : "permission_denied"
    case "comment":
      return isOwner || permissions?.can_comment || permissions?.can_edit_manuscript
        ? "available"
        : "permission_denied"
    default:
      return "available"
    }
  })()
  if (permissionAccess !== "available") return permissionAccess
  if (tool.planGate === "author" && !context.hasAuthorAccess && isOwner) return "plan_locked"
  if (tool.requiresProcessing && book && book.status !== "ready") return "processing_blocked"
  return "available"
}

function normalizedVisibility(value: unknown): ToolVisibility | null {
  if (value === false || value === "user_hidden") return "user_hidden"
  if (value === true || value === "visible") return "visible"
  return null
}

function preferenceVisibility(tool: WorkspaceToolEntry, context: ToolResolverContext) {
  if (tool.id.startsWith("dashboard.public") || tool.placements.includes("public")) {
    return normalizedVisibility(context.globalPreference?.public_tool_visibility[tool.id])
  }
  if (tool.id.startsWith("dashboard.")) {
    return normalizedVisibility(context.globalPreference?.dashboard_visibility[tool.id])
  }
  if (tool.id.startsWith("book.")) {
    if (context.bookPreference?.hidden_book_tools.includes(tool.id)) return "user_hidden"
    return normalizedVisibility(context.bookPreference?.overview_cards[tool.id])
  }
  return null
}

function presetVisibility(tool: WorkspaceToolEntry, preset: BookPreset | undefined) {
  if (!preset || !tool.presets || tool.presets.includes(preset)) return "visible"
  return "preset_hidden"
}

export function resolveWorkspaceTool(
  tool: WorkspaceToolEntry,
  context: ToolResolverContext,
): ResolvedWorkspaceTool {
  const access = toolAccess(tool, context)
  const href = routeForTool(tool, bookRouteSegment(context.book), context.currentChapter ?? 1)
  const active = toolRouteMatches(tool, context)
  let resolved: ResolvedWorkspaceTool
  if (tool.nonHideable) {
    resolved = { tool, href, access, visibility: "visible", hidden: false }
  } else if (tool.id === "dashboard.pricing" && context.paidUser === false) {
    resolved = { tool, href, access, visibility: "visible", hidden: false }
  } else {
    const userVisibility = preferenceVisibility(tool, context)
    if (userVisibility) {
      resolved = {
      tool,
      href,
      access,
      visibility: userVisibility,
      hidden: userVisibility !== "visible",
      reason: userVisibility === "user_hidden" ? "hidden_by_user" : undefined,
      }
    } else if (tool.complexity === "advanced" && context.bookPreference?.advanced_tool_override) {
      resolved = context.bookPreference.advanced_tool_override === "show"
        ? { tool, href, access, visibility: "visible", hidden: false }
        : {
            tool,
            href,
            access,
            visibility: "preset_hidden",
            hidden: true,
            reason: "hidden_by_advanced_override",
          }
    } else {
      const byPreset = presetVisibility(tool, context.bookPreference?.book_preset)
      if (byPreset !== "visible" && context.mode !== "power") {
        resolved = { tool, href, access, visibility: byPreset, hidden: true, reason: "hidden_by_preset" }
      } else if (toolComplexityRank[tool.complexity] > complexityRank[context.mode]) {
        resolved = {
          tool,
          href,
          access,
          visibility: "preset_hidden",
          hidden: true,
          reason: "hidden_by_mode",
        }
      } else {
        resolved = { tool, href, access, visibility: "visible", hidden: false }
      }
    }
  }

  if (active && resolved.hidden) {
    return { ...resolved, visibility: "temporarily_revealed", hidden: false }
  }
  return resolved
}

export function resolveWorkspaceTools(
  tools: WorkspaceToolEntry[],
  context: ToolResolverContext,
) {
  return tools.map((tool) => resolveWorkspaceTool(tool, context))
}
