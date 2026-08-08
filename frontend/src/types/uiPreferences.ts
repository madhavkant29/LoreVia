export type ComplexityMode = "focused" | "standard" | "power"
export type BookPreset = "draft" | "review" | "story_bible" | "share" | "all"

export type ToolAccess =
  | "available"
  | "plan_locked"
  | "permission_denied"
  | "processing_blocked"

export type ToolVisibility =
  | "visible"
  | "preset_hidden"
  | "user_hidden"
  | "temporarily_revealed"

export type UiPreferenceOperation = {
  op: "set" | "unset"
  path: string
  value?: unknown
}

export interface UserUiPreference {
  schema_version: number
  revision: number
  complexity_mode: ComplexityMode
  dashboard_visibility: Record<string, ToolVisibility | boolean>
  dashboard_order: string[]
  public_tool_visibility: Record<string, ToolVisibility | boolean>
  density: "comfortable" | "compact" | "dense" | string
  reader_toolbar_density: "standard" | "compact" | string
  locked_tool_presentation: "compact" | "hidden" | string
  default_workspace_shell: "reader" | "author"
  mobile_actions: string[]
  guidance_dismissals: Record<string, unknown>
  recommendation_snoozes: Record<string, unknown>
  updated_at?: string | null
}

export interface UserBookUiPreference {
  book_id: string
  schema_version: number
  revision: number
  book_preset: BookPreset
  advanced_tool_override?: "show" | "hide" | null
  hidden_book_tools: string[]
  overview_cards: Record<string, ToolVisibility | boolean>
  reader_actions: string[]
  mobile_actions: string[]
  panel_state: Record<string, unknown>
  timeline_collapsed_sections: Record<string, boolean>
  updated_at?: string | null
}

export interface UserUiPreferenceExport {
  schema_version: number
  global_preferences: UserUiPreference
  book_preferences: UserBookUiPreference[]
}

export type UiPreferenceImportMode = "merge" | "replace"

export interface UiPreferenceImportResult {
  imported: boolean
  mode: UiPreferenceImportMode
  global_revision: number
  book_preferences_updated: number
}

export interface PreferenceConflictResponse<TPreference> {
  detail: string
  latest_revision: number
  latest: TPreference
}

export interface BookVisibilitySummaryItem {
  state: string
  label: string
  count?: number | null
  detail?: string | null
}

export interface BookVisibilitySummary {
  book_id: string
  access_class: "owner" | "author_collaborator" | "reader_collaborator"
  workspace_shell: "reader" | "author"
  badges: string[]
  private_status: BookVisibilitySummaryItem
  collaborators: BookVisibilitySummaryItem
  beta_readers: BookVisibilitySummaryItem
  public_publishing: BookVisibilitySummaryItem
  public_discussion: BookVisibilitySummaryItem
  rights: BookVisibilitySummaryItem
  moderation: BookVisibilitySummaryItem
  public_url?: string | null
}
