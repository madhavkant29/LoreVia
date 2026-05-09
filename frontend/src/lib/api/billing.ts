import { apiClient } from "./client"
import type { PaidPlanCode } from "@/lib/billing/plans"

export const billingApi = {
  checkout: (plan: PaidPlanCode) =>
    apiClient.post<{ checkout_url: string | null; billing_enabled: boolean; message?: string }>("/billing/checkout", { plan }).then((r) => r.data),
  portal: () =>
    apiClient.post<{ portal_url: string | null; billing_enabled: boolean; message?: string }>("/billing/portal").then((r) => r.data),
}
