import type { Metadata } from "next"

import { LegalContactBlock, LegalPageShell, LegalRightRail } from "@/components/legal/LegalPageShell"
import { SUPPORT_EMAIL } from "@/lib/constants/contact"

export const metadata: Metadata = {
  title: "Refund Policy",
  description: "Understand LoreVia for authors subscription cancellation, refund review criteria, renewal timing, and billing support.",
  alternates: {
    canonical: "/refund",
  },
}

const effectiveDate = "May 8, 2026"

const sections = [
  {
    title: "Subscriptions and renewals",
    bullets: [
      "Plans renew automatically beyond the free tier. Paid plans may be billed monthly or on annual intervals depending on your selection.",
      "Unless a specific offer states otherwise, subscriptions renew automatically until you cancel.",
    ],
  },
  {
    title: "How cancellation works",
    bullets: [
      "Cancel anytime through the LoreVia billing portal available in your account settings.",
      "Cancellation stops the next renewal. It does not usually terminate access on the same day.",
      "Keep the paid tier until the current billing period ends, then the account steps down to the free plan if available.",
    ],
  },
  {
    title: "What happens after cancellation",
    bullets: [
      "You keep access to paid features until the end of the billing period.",
      "After that, access to paid features is removed and the account moves to the free tier with limited features.",
      "Exports, data, and manuscript content remain available according to our retention policy.",
    ],
  },
  {
    title: "When refund requests may be reviewed",
    bullets: [
      "Refunds are considered case-by-case within 14 days of the charge.",
      "Common reasons include accidental charges, duplicate billing, clear user error, or a product not working as described.",
      "Requests outside the window may be reviewed if there were technical issues on our side or an exceptional circumstance.",
    ],
  },
  {
    title: "What does not automatically qualify",
    bullets: [
      "Change of mind, unused time, or feature expectations not met.",
      "Requests after the 14-day window without a documented issue.",
      "Fraudulent activity, chargebacks without contacting support, or violation of our terms.",
    ],
  },
  {
    title: "Approved refund timing and chargebacks",
    bullets: [
      "If approved, refunds go back to the original payment method.",
      "Posting times depend on your bank or card issuer and may take several business days.",
      "Chargebacks are a last resort and can lead to account restrictions.",
    ],
  },
  {
    title: "Trials, promos, and future plan changes",
    bullets: [
      "Promotional pricing and trials follow their stated terms.",
      "If a promo ends or plan prices change, you'll be notified before the next charge.",
      "Future plan updates do not affect past charges.",
    ],
  },
] as const

export default function RefundPage() {
  return (
    <LegalPageShell
      eyebrow="Refund"
      title="Refunds are reviewed carefully and handled directly"
      description="We keep our refund process transparent and fair. Renewals are honest, cancellations are straightforward, and refund requests are reviewed by real people."
      effectiveDate={effectiveDate}
      notice="Refund requests are considered case-by-case within 14 days of the charge unless law or exceptional circumstances require a different review."
      sections={sections}
      rightRail={
        <LegalRightRail
          items={[
            {
              label: "Cancellation",
              value: "Self-serve",
              detail: "Cancel through the billing portal in account settings.",
            },
            {
              label: "Review window",
              value: "14 days",
              detail: "Contact support within 14 days of the charge for review.",
            },
            {
              label: "Billing help",
              value: SUPPORT_EMAIL,
              href: `mailto:${SUPPORT_EMAIL}`,
              detail: "Use support for refund review and billing questions.",
            },
          ]}
        />
      }
      contactBlock={
        <LegalContactBlock
          title="Need help with billing or a refund request?"
          description="Contact support with the account email, charge date, and a concise explanation of the issue."
        />
      }
    />
  )
}
