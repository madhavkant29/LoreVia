import { apiClient } from "./client"
import type { PaidPlanCode } from "@/lib/billing/plans"

export type BillingConfirmation = {
  transaction_id: string
  status: string
  plan: string
  billing_interval: "monthly" | "annual"
  display_name: string
  currency_code: string | null
  total: string | null
  invoice_number: string | null
  invoice_pdf_url: string | null
  subscription_id: string | null
  customer_email: string | null
}

export const billingApi = {
  checkout: (plan: PaidPlanCode) =>
    apiClient.post<{ checkout_url: string | null; billing_enabled: boolean; message?: string }>("/billing/checkout", { plan }).then((r) => r.data),
  confirmation: (transactionId: string, confirmationToken?: string | null) =>
    apiClient.get<BillingConfirmation>("/billing/confirmation", {
      params: {
        transaction_id: transactionId,
        ...(confirmationToken ? { confirmation_token: confirmationToken } : {}),
      },
    }).then((r) => r.data),
  portal: () =>
    apiClient.post<{ portal_url: string | null; billing_enabled: boolean; message?: string }>("/billing/portal").then((r) => r.data),
}
