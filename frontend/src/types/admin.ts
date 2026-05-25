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
