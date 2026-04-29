import type { Metadata } from "next"

export const metadata: Metadata = {
  title: "Refund Policy",
  description: "Read the LoreVia Refund Policy to understand our refund terms and process.",
}

export default function RefundPage() {
  return (
    <main className="min-h-screen bg-[linear-gradient(180deg,#020202_0%,#0a0a0a_45%,#111111_100%)] px-6 py-16 text-white">
      <div className="mx-auto max-w-4xl">
      <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400">LoreVia</p>
      <h1 className="mt-3 text-4xl font-semibold text-white">Refund Policy</h1>
      <div className="mt-8 space-y-6 text-sm leading-7 text-slate-300">
        <p>We want you to be satisfied with LoreVia. This policy explains our refund terms and how cancellations work through our billing system.</p>

        <div>
          <p className="font-semibold text-white">How to cancel your subscription</p>
          <p className="mt-2">You can cancel your subscription at any time through the LoreVia billing portal. To access the portal, go to your account settings and select "Manage billing." This opens a secure Paddle portal where you can view your subscription details and cancel active plans. Cancellations take effect at the end of your current billing period. After cancellation, your account is automatically downgraded to the free tier when the subscription ends.</p>
        </div>

        <div>
          <p className="font-semibold text-white">What happens when you cancel</p>
          <p className="mt-2">When your subscription is cancelled, our system automatically updates your account tier to free. You retain access to the free-tier features, including your uploaded books, reading progress, and basic workspace tools. Any paid features that exceed the free tier limits will be disabled. Your data remains stored in your account according to our standard data retention policies.</p>
        </div>

        <div>
          <p className="font-semibold text-white">Refund eligibility</p>
          <p className="mt-2">Refund requests are evaluated on a case-by-case basis. If you believe you are entitled to a refund (for example, if you were charged incorrectly or experienced a service issue), contact us at support@getlorevia.com within 14 days of the charge with your account email and the reason for your request. We review each request individually and respond within 5 business days. Refunds are not guaranteed and depend on the specific circumstances.</p>
        </div>

        <div>
          <p className="font-semibold text-white">Refund processing</p>
          <p className="mt-2">Approved refunds are processed back to your original payment method. The timing depends on your payment provider and may take 5-10 business days to appear in your account. Paddle, our payment processor, governs the actual refund mechanics and any processor-specific rules.</p>
        </div>

        <div>
          <p className="font-semibold text-white">No automatic refunds for cancellations</p>
          <p className="mt-2">Cancelling your subscription through the billing portal does not automatically generate a refund. You will continue to have access to paid features until the end of your current billing period. If you want a refund in addition to cancellation, you must contact support separately.</p>
        </div>

        <div>
          <p className="font-semibold text-white">Exceptions</p>
          <p className="mt-2">We reserve the right to deny refund requests that show signs of abuse, such as repeated subscription cycles followed by refund requests, or extensive use of paid features before requesting a refund.</p>
        </div>

        <p>Questions about this policy can be sent to support@getlorevia.com.</p>
      </div>
      </div>
    </main>
  )
}
