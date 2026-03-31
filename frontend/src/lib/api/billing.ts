import { apiClient } from "./client"

export const billingApi = {
  checkout: (plan: "pro_monthly" | "pro_annual" | "power_monthly") =>
    apiClient.post<{ checkout_url: string | null; billing_enabled: boolean; message?: string }>("/billing/checkout", { plan }).then((r) => r.data),
  portal: () =>
    apiClient.post<{ portal_url: string | null; billing_enabled: boolean; message?: string }>("/billing/portal").then((r) => r.data),
}
