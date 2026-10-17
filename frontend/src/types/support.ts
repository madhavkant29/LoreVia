export type SupportWorkspace = "reader" | "author"

export type SupportUiContext = {
  route: string
  tool_id?: string | null
  workspace_shell?: SupportWorkspace | null
  account_tier?: string | null
  capability_flags?: string[]
  processing_state?: string | null
  save_state?: string | null
  error_code?: string | null
  request_id?: string | null
  app_version?: string | null
  device_class?: "desktop" | "tablet" | "mobile" | "unknown"
  book_id?: string | null
}

export type SupportSource = {
  slug: string
  title: string
  summary: string
  url: string
}

export type SupportAction = {
  label: string
  href: string
  external: boolean
}

export type SupportAnswer = {
  answer: string
  sources: SupportSource[]
  actions: SupportAction[]
  confidence: number
  escalation_available: boolean
  declined: boolean
}

export type SupportRecentMessage = {
  role: "user" | "assistant"
  content: string
}

export type SupportGuideSummary = {
  slug: string
  title: string
  summary: string
  routes: string[]
  workspace: string
}

export type SupportIncident = {
  id: string
  reference: string
  status: string
  category: string
  feature: string | null
  summary: string
  resolution: string | null
  created_at: string
}
