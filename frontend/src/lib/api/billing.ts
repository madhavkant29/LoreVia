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

export type BillingCheckoutPreview = {
  plan: PaidPlanCode
  display_name: string
  billing_interval: "monthly" | "annual"
  trial_status: "active" | "expired"
  trial_active: boolean
  trial_ends_at: string | null
  charge_today: string
  recurring_price: string
  confirmation_required: boolean
  confirmation_text: string | null
  checkout_button_label: string
  default_action_label: string | null
  quote_token: string | null
  billing_enabled: boolean
  message: string | null
}

export type BillingSubscription = {
  plan: string
  plan_tier: string
  status: string
  display_state: "free" | "trial" | "active" | "cancellation_scheduled" | "past_due" | "paused" | "canceled"
  price: { amount: number; currency: string; interval: "month" | "year" }
  current_period_start: string | null
  current_period_end: string | null
  cancel_at_period_end: boolean
  cancellation_scheduled_at: string | null
  next_charge_at: string | null
  auto_renew: boolean
  last_payment_status: string | null
  has_paddle_subscription: boolean
}

export const billingApi = {
  checkoutPreview: (plan: PaidPlanCode) =>
    apiClient.post<BillingCheckoutPreview>("/billing/checkout/preview", { plan }).then((r) => r.data),
  checkout: (plan: PaidPlanCode, confirmedImmediateCharge = false, quoteToken?: string | null) =>
    apiClient.post<{ checkout_url: string | null; billing_enabled: boolean; message?: string }>("/billing/checkout", {
      plan,
      confirmed_immediate_charge: confirmedImmediateCharge,
      quote_token: quoteToken ?? null,
    }).then((r) => r.data),
  abandonCheckout: (transactionId: string) =>
    apiClient.post<{ abandoned: boolean; transaction_id: string; status: string }>("/billing/checkout/abandon", {
      transaction_id: transactionId,
    }).then((r) => r.data),
  confirmation: (transactionId: string, confirmationToken?: string | null) =>
    apiClient.get<BillingConfirmation>("/billing/confirmation", {
      params: {
        transaction_id: transactionId,
        ...(confirmationToken ? { confirmation_token: confirmationToken } : {}),
      },
    }).then((r) => r.data),
  portal: () =>
    apiClient.post<{ portal_url: string | null; billing_enabled: boolean; message?: string }>("/billing/portal").then((r) => r.data),
  subscription: () =>
    apiClient.get<BillingSubscription>("/billing/subscription").then((r) => r.data),
}
