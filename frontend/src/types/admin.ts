export type AdminScope = "moderation_admin" | "billing_admin" | "super_admin"

export interface AdminSession {
  is_admin: boolean
  scopes: AdminScope[]
  is_owner: boolean
  requires_step_up: boolean
  session_expires_at?: string | null
}

export interface AdminBillingPlanStatus {
  code: string
  display_name: string
  billing_interval: "monthly" | "annual"
  price_usd: number
  configured: boolean
  price_id_present: boolean
}

export interface AdminBillingStatus {
  billing_enabled: boolean
  payments_ready: boolean
  paddle_api_key_present: boolean
  webhook_secret_present: boolean
  default_checkout_url_present: boolean
  recommended_default_checkout_url: string
  resend_api_key_present: boolean
  internal_job_secret_present: boolean
  fully_configured_plan_count: number
  missing_configuration: string[]
  plans: AdminBillingPlanStatus[]
  webhook_endpoint_path: string
  supported_webhook_events: string[]
  trial_email_job_endpoint_path: string
  trial_email_runner_script: string
  trial_email_automation_code_ready: boolean
  priority_processing_code_ready: boolean
  priority_queue_names: string[]
  external_action_items: string[]
}

export interface AdminPrincipal {
  id: string
  user_id: string
  status: "active" | "revoked" | string
  is_owner: boolean
  scopes: AdminScope[]
  grant_reason: string
  revoke_reason?: string | null
  granted_by_user_id?: string | null
  revoked_by_user_id?: string | null
  created_at: string
  updated_at: string
  revoked_at?: string | null
}

export interface AdminAuditEvent {
  id: string
  actor_user_id?: string | null
  target_user_id?: string | null
  target_book_id?: string | null
  target_report_id?: string | null
  target_refund_review_id?: string | null
  action_type: string
  reason?: string | null
  result: string
  request_id?: string | null
  ip_address?: string | null
  user_agent?: string | null
  scopes_snapshot: AdminScope[]
  metadata_json: Record<string, unknown>
  created_at: string
}

export interface AdminContentReport {
  id: string
  reported_book_id: string
  reported_author_user_id?: string | null
  reporter_user_id?: string | null
  reporter_email?: string | null
  report_type: string
  status: string
  reason: string
  details?: string | null
  created_at: string
}

export interface AdminPublicShare {
  book_id: string
  user_id: string
  author_username?: string | null
  title: string
  author?: string | null
  genre?: string | null
  isbn?: string | null
  copyright_warning: boolean
  public_description?: string | null
  requested_at?: string | null
  created_at: string
}

export interface AdminRefundReview {
  id: string
  user_id: string
  subscription_id?: string | null
  paddle_transaction_id: string
  paddle_adjustment_id?: string | null
  charge_at?: string | null
  plan_code: string
  billing_interval: string
  request_source: string
  support_reference?: string | null
  request_reason: string
  status: string
  auto_decision?: boolean | null
  decision_reason?: string | null
  eligibility_snapshot_json: Record<string, unknown>
  usage_snapshot_json: Record<string, unknown>
  provider_response_json: Record<string, unknown>
  requested_by_admin_user_id?: string | null
  resolved_by_admin_user_id?: string | null
  resolved_at?: string | null
  created_at: string
  updated_at: string
}

export interface AdminMetrics {
  users: number
  books: number
  characters: number
  chunks_indexed: number
  summaries_cached: number
  redis_memory_mb: number
  redis_key_count?: number
  redis_connected_clients?: number
  redis_key_prefix_counts?: Record<string, number>
  redis_key_prefix_samples?: Record<string, string[]>
  redis_key_scan_truncated?: boolean
}

export interface AdminQueueDepth {
  extraction: number
  analysis: number
  embedding: number
  intelligence: number
}

export interface AdminTaskExecution {
  id: string
  task_name: string
  feature: string
  status: string
  user_id?: string | null
  book_id?: string | null
  chapter_number?: number | null
  attempt_count: number
  max_attempts: number
  error_category?: string | null
  error_detail?: string | null
  created_at: string
}

export interface AdminOperationsMetrics {
  total_executions: number
  terminal_failures: number
  failure_rate: number
  oldest_job_age_seconds: number
  average_task_duration_seconds: number
  paused_runs: number
  queue_depth?: number
  running_executions?: number
  retry_count?: number
  by_task?: Array<{
    task_name: string
    count: number
    terminal_failures: number
    retries: number
    average_duration_seconds: number
  }>
}

export interface AdminAiQualityMetrics {
  label: string
  reviewed: number
  accepted: number
  acceptance_rate: number | null
  character_corrections_after_promotion?: number
  relationship_corrections?: number
  reprocessing_runs?: number
  support_incidents?: number
  support_incidents_per_processed_manuscript?: number | null
  breakdown: Array<{ entity_type: string; outcome: string; count: number }>
  by_model_version?: Array<{
    model?: string | null
    extractor_version?: string | null
    outcome: string
    count: number
  }>
}

export interface AdminContributionMargin {
  currency: string
  recognized_net_revenue: number
  llm_cost: number
  worker_cost: number
  storage_cost: number
  contribution_margin: number
  complete: boolean
  allocation_basis?: string
  by_feature: Array<{ feature: string; direct_cost: number; allocated_revenue: number }>
  by_user?: Array<{
    user_id: string
    tier?: string | null
    recognized_revenue: number
    direct_cost: number
    contribution_margin: number
  }>
  by_book?: Array<{
    book_id: string
    user_id?: string | null
    direct_cost: number
    allocated_revenue: number
  }>
}

export interface AdminSupportIncident {
  id: string
  user_id?: string | null
  book_id?: string | null
  category: string
  feature?: string | null
  severity: string
  status: string
  summary: string
  resolution?: string | null
  created_at: string
}

export interface AdminSubscriptionMetrics {
  cohort_start: string
  cohort_end: string
  trial_starts: number
  trial_to_paid_conversions: number
  trial_to_paid_rate: number | null
  cancellation_events: number
  resolved_cancellation_events: number
  unresolved_cancellation_events: number
  reactivated_after_cancellation: number
  churned_after_cancellation: number
  post_cancel_churn_rate: number | null
  reactivation_window_days: number
}

export interface AdminRateLimitOverride {
  search_per_hour: number | null
  summary_per_hour: number | null
  chat_per_day: number | null
  api_per_minute: number | null
}

export interface AdminRateLimitState {
  user_id: string
  email: string
  override: AdminRateLimitOverride
}

export interface AdminCreatorStrikeBody {
  book_id?: string | null
  report_id?: string | null
  strike_type: string
  severity: string
  reason: string
}

export interface AdminCreatorStrike {
  id: string
  user_id: string
  book_id: string | null
  report_id: string | null
  strike_type: string
  severity: string
  reason: string
  is_active: boolean
  created_at: string
}

export interface AdminPublicChapterIn {
  title: string
  text: string
  description?: string | null
}

export interface AdminPublicBookManualIn {
  title: string
  author?: string | null
  genre?: string | null
  description?: string | null
  chapters: AdminPublicChapterIn[]
}

export interface AdminPublicBookCreateOut {
  book_id: string
  status: string
  visibility: string
  public_kind: string
  approval_status: string
  public_slug?: string | null
  message?: string | null
}

export interface AdminPublicChapterAppendOut {
  book_id: string
  chapter_number: number
  saved: boolean
}
