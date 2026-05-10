export type PointAction = "search" | "prediction" | "high_cost_authoring"
export type RewardedAdOutcome = "rewarded" | "dismissed" | "unsupported" | "error"

export interface PointsBalance {
  balance: number
}

export interface PointLedgerEntry {
  id: string
  entry_type: string
  source_type: string
  source_id?: string | null
  points_delta: number
  expires_at?: string | null
  metadata_json: Record<string, unknown>
  created_at: string
}

export interface PointSpendOffer {
  code: string
  action: PointAction
  title: string
  description: string
  points_cost: number
  units: number
  eligible: boolean
  reason?: string | null
}

export interface PointSpendOffersResponse {
  offers: PointSpendOffer[]
}

export interface SpendPointsResponse {
  balance: number
  purchased_units_today: number
  offer: PointSpendOffer
  confirmation_message: string
}

export interface RewardedAdStatus {
  enabled: boolean
  provider: string
  reward_points: number
  daily_cap: number
  claims_used_today: number
  claims_remaining_today: number
  session_ttl_seconds: number
  min_grant_seconds: number
  reason?: string | null
}

export interface StartRewardedAdSessionResponse {
  session_token: string
  provider: string
  reward_points: number
  ad_unit_path: string
  expires_at: string
  claims_remaining_today: number
}

export interface ResolveRewardedAdSessionResponse {
  status: string
  balance: number
  reward_points_granted: number
  claims_remaining_today: number
  confirmation_message: string
}

export interface ReferralReward {
  id: string
  referral_code: string
  status: string
  qualified_at?: string | null
  rewarded_at?: string | null
  created_at: string
}

export interface ReferralSummary {
  referral_code: string
  referral_url?: string | null
  points_balance: number
  rewards: ReferralReward[]
}
