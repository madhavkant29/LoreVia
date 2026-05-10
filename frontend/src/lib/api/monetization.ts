import { apiClient } from "./client"
import type {
  PointLedgerEntry,
  PointSpendOffersResponse,
  PointsBalance,
  ReferralSummary,
  ResolveRewardedAdSessionResponse,
  RewardedAdOutcome,
  RewardedAdStatus,
  StartRewardedAdSessionResponse,
  SpendPointsResponse,
} from "@/types/monetization"

export const monetizationApi = {
  getPointsBalance: () =>
    apiClient.get<PointsBalance>("/monetization/points").then((response) => response.data),
  getPointsLedger: () =>
    apiClient.get<PointLedgerEntry[]>("/monetization/points/ledger").then((response) => response.data),
  getReferralSummary: () =>
    apiClient.get<ReferralSummary>("/monetization/referrals").then((response) => response.data),
  getPointOffers: () =>
    apiClient.get<PointSpendOffersResponse>("/monetization/offers").then((response) => response.data),
  spendPoints: (offerCode: string) =>
    apiClient.post<SpendPointsResponse>("/monetization/points/spend", { offer_code: offerCode }).then((response) => response.data),
  getRewardedAdStatus: () =>
    apiClient.get<RewardedAdStatus>("/monetization/rewarded-ads/status").then((response) => response.data),
  startRewardedAdSession: (placement: string) =>
    apiClient.post<StartRewardedAdSessionResponse>("/monetization/rewarded-ads/session", { placement }).then((response) => response.data),
  resolveRewardedAdSession: (payload: {
    sessionToken: string
    outcome: RewardedAdOutcome
    rewardType?: string | null
    rewardAmount?: number | null
    errorMessage?: string | null
  }) =>
    apiClient
      .post<ResolveRewardedAdSessionResponse>("/monetization/rewarded-ads/resolve", {
        session_token: payload.sessionToken,
        outcome: payload.outcome,
        reward_type: payload.rewardType,
        reward_amount: payload.rewardAmount,
        error_message: payload.errorMessage,
      })
      .then((response) => response.data),
}
