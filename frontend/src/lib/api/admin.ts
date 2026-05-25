import { apiClient } from "@/lib/api/client"
import type {
  AdminAuditEvent,
  AdminBillingStatus,
  AdminContentReport,
  AdminPrincipal,
  AdminPublicShare,
  AdminRefundReview,
  AdminScope,
  AdminSession,
} from "@/types/admin"

export const adminApi = {
  session: () => apiClient.get<AdminSession>("/admin/session").then((r) => r.data),
  billingStatus: () => apiClient.get<AdminBillingStatus>("/admin/billing/status").then((r) => r.data),
  stepUp: (password: string) => apiClient.post<{ ok: boolean }>("/admin/step-up", { password }).then((r) => r.data),
  access: () => apiClient.get<AdminPrincipal[]>("/admin/access?limit=50").then((r) => r.data),
  grantAccess: (payload: { user_id: string; scopes: AdminScope[]; is_owner: boolean; reason: string }) =>
    apiClient.post<AdminPrincipal>("/admin/access", payload).then((r) => r.data),
  revokeAccess: (principalId: string, reason: string) =>
    apiClient.post<AdminPrincipal>(`/admin/access/${principalId}/revoke`, { reason }).then((r) => r.data),
  audit: () => apiClient.get<AdminAuditEvent[]>("/admin/audit?limit=50").then((r) => r.data),
  publicShares: () => apiClient.get<AdminPublicShare[]>("/admin/public-shares/pending?limit=50").then((r) => r.data),
  reviewPublicShare: (bookId: string, payload: { approved: boolean; reason?: string | null }) =>
    apiClient.put(`/admin/public-shares/${bookId}`, payload).then((r) => r.data),
  reports: () => apiClient.get<AdminContentReport[]>("/admin/reports?limit=50").then((r) => r.data),
  refunds: () => apiClient.get<AdminRefundReview[]>("/admin/refunds/reviews?limit=50").then((r) => r.data),
  approveRefund: (reviewId: string, payload: { reason: string; provider_followup_only?: boolean }) =>
    apiClient.post<AdminRefundReview>(`/admin/refunds/reviews/${reviewId}/approve`, payload).then((r) => r.data),
  denyRefund: (reviewId: string, reason: string) =>
    apiClient.post<AdminRefundReview>(`/admin/refunds/reviews/${reviewId}/deny`, { reason }).then((r) => r.data),
  hideBook: (bookId: string, reason: string) =>
    apiClient.post(`/admin/books/${bookId}/hide`, { reason }).then((r) => r.data),
  removeBook: (bookId: string, reason: string) =>
    apiClient.post(`/admin/books/${bookId}/remove`, { reason }).then((r) => r.data),
  restoreBook: (bookId: string, reason: string) =>
    apiClient.post(`/admin/books/${bookId}/restore`, { reason }).then((r) => r.data),
  updateTier: (userId: string, tier: string) =>
    apiClient.put(`/admin/users/${userId}/tier`, { tier }).then((r) => r.data),
}
