import type { Metadata } from "next"

import { TrustPage } from "@/components/legal/TrustPage"
import { SUPPORT_EMAIL } from "@/lib/constants/contact"
import { TRUST_EFFECTIVE_DATE } from "@/lib/constants/trust"

export const metadata: Metadata = {
  title: "Refund Policy",
  description: "Understand LoreVia subscription cancellation, refund review criteria, renewal timing, and billing support.",
  alternates: {
    canonical: "/refund",
  },
}

const sections = [
  {
    title: "Subscriptions and renewals",
    paragraphs: [
      "LoreVia offers paid plans for users who need expanded access beyond the free tier. Paid plans may be billed on monthly or annual intervals depending on the option you select at checkout. Unless a specific offer states otherwise, subscriptions renew automatically until you cancel them.",
      "The price, billing cadence, and any taxes or processor-imposed terms are presented during checkout. Because billing is handled through a dedicated payment provider, some operational details of the charge lifecycle, receipt delivery, and refund mechanics depend on that provider's systems in addition to LoreVia's own policy decisions.",
    ],
  },
  {
    title: "How cancellation works",
    paragraphs: [
      "You can cancel a paid subscription through the LoreVia billing portal available from your account settings. That portal is the standard path for managing an active plan, reviewing the current subscription state, and ending future renewals without needing manual intervention from support.",
      "Cancellation stops the next renewal. It does not usually terminate access on the same day you click cancel. In most cases, you keep the paid tier until the current billing period ends, and then the account steps down to the free plan if one is available.",
    ],
  },
  {
    title: "What happens after cancellation",
    paragraphs: [
      "When a subscription ends, LoreVia may reduce access to features that exceed the free tier while preserving the account and its stored work according to the live product rules and retention practices. That means your books, notes, and workspace history are not automatically erased just because a paid plan ends.",
      "However, premium-only capabilities, higher limits, or plan-specific tools may no longer be available. If you are working against a deadline, cancel with that timing in mind instead of assuming premium features will remain permanently available after the billing term closes.",
    ],
  },
  {
    title: "When refund requests may be reviewed",
    paragraphs: [
      "LoreVia reviews refund requests on a case-by-case basis rather than promising an automatic no-questions-asked refund for every charge. The most common cases that warrant review are duplicate charges, clear billing mistakes, technical failures that blocked access to the paid service, or other circumstances where the charge did not align with what the customer reasonably purchased.",
      "If you believe a refund is justified, contact support within 14 days of the charge and include the account email, the charge date, the plan involved, and a short explanation of what went wrong. Requests with specific facts are much easier to evaluate fairly than one-line refund demands with no context.",
    ],
  },
  {
    title: "What does not automatically qualify",
    paragraphs: [
      "Cancelling a subscription does not automatically create a refund. It simply prevents future renewals. A refund request also may be denied when the account had meaningful access to the paid service and there is no billing error, fraud event, or material product failure to review.",
      "LoreVia may also deny requests that appear abusive, such as repeated signups followed by repeated refund demands after heavy use, or patterns that look like an attempt to use premium features temporarily without paying for the consumed service period.",
    ],
  },
  {
    title: "Approved refund timing and chargebacks",
    paragraphs: [
      "If a refund is approved, it is sent back to the original payment method through the billing provider. Posting times depend on the financial institutions involved and may take several business days before the credit is visible on your statement.",
      "If you are considering a chargeback because you believe a charge is fraudulent, unauthorized, or the product was materially unavailable, contact support first when possible. Most legitimate billing issues can be resolved faster through direct review, and unnecessary chargebacks can complicate account restoration and payment processing history.",
    ],
  },
  {
    title: "Trials, promos, and future plan changes",
    paragraphs: [
      "From time to time, LoreVia may offer promotional pricing, new plan structures, or limited trial programs. If that happens, the specific terms of the offer will control the billing behavior for that purchase. Trial language, intro pricing, or discounted annual offers should be read carefully because they may have different renewal timing than a standard full-price plan.",
      "This published policy applies unless a more specific offer, required consumer law, or separate written agreement overrides a particular point.",
    ],
  },
] as const

export default function RefundPage() {
  return (
    <TrustPage
      currentPath="/refund"
      eyebrow="Refunds"
      title="Refunds are reviewed carefully, not hidden behind vague copy."
      description="This page explains how LoreVia subscriptions renew, how cancellation works, and when a refund request may be reasonable to review."
      effectiveDate={TRUST_EFFECTIVE_DATE}
      intro={[
        "The goal of this policy is clarity. We do not want users guessing whether cancelling ends access immediately, whether a mistaken charge can be reviewed, or whether billing support lives inside the app or with a processor.",
        "LoreVia uses a dedicated billing flow and applies a case-by-case refund process. That is stricter than a blanket promise, but it is also more honest about how subscription products actually work.",
      ]}
      facts={[
        {
          label: "Cancellation",
          value: "Self-serve through the billing portal",
          detail: "The normal path is to manage or cancel your plan from the account billing area rather than by emailing first.",
        },
        {
          label: "Refund window",
          value: "Contact support within 14 days",
          detail: "That gives us the best chance to verify the charge while the billing context is still fresh.",
        },
        {
          label: "Automatic refund",
          value: "No",
          detail: "Cancellation stops renewal, but it does not automatically reverse the charge that already occurred.",
        },
        {
          label: "Billing help",
          value: SUPPORT_EMAIL,
          detail: "Include the account email, charge timing, and the reason you believe the charge should be reviewed.",
        },
      ]}
      sections={[...sections]}
      contacts={[
        {
          title: "Refund and billing review",
          description: "Use support for duplicate charges, cancellation questions, billing portal issues, and refund review requests.",
          ctaLabel: SUPPORT_EMAIL,
          ctaHref: `mailto:${SUPPORT_EMAIL}`,
        },
      ]}
    />
  )
}
