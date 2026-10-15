"use client"

import Link from "next/link"
import { Suspense, useEffect, useState } from "react"
import { useSearchParams } from "next/navigation"

import { billingApi, type BillingConfirmation } from "@/lib/api/billing"

export default function CheckoutSuccessPage() {
  return (
    <Suspense fallback={null}>
      <CheckoutSuccessInner />
    </Suspense>
  )
}

function CheckoutSuccessInner() {
  const searchParams = useSearchParams()
  const transactionId = searchParams.get("txn")?.trim() ?? ""
  const confirmationToken = searchParams.get("confirmation_token")?.trim() ?? ""
  const [confirmation, setConfirmation] = useState<BillingConfirmation | null>(null)
  const [message, setMessage] = useState("Confirming your payment and loading your invoice details...")

  useEffect(() => {
    if (!transactionId) {
      setMessage("Missing transaction reference. Return to pricing or your account settings to continue.")
      return
    }

    let cancelled = false

    void billingApi
      .confirmation(transactionId, confirmationToken || null)
      .then((result) => {
        if (cancelled) return
        setConfirmation(result)
        setMessage("Payment confirmed. Your account update and invoice details are ready below.")
      })
      .catch(() => {
        if (cancelled) return
        setMessage("Payment may still be processing. Refresh this page in a few seconds to load your invoice details.")
      })

    return () => {
      cancelled = true
    }
  }, [confirmationToken, transactionId])

  return (
    <section className="mx-auto flex min-h-[calc(100dvh-80px)] w-full max-w-3xl flex-col justify-center px-6 py-16">
      <div className="border-y border-white/10 py-8 text-[#F2F4F7]">
        <p className="text-sm font-semibold text-[#C9A86A]">Payment confirmed</p>
        <h1 className="mt-3 text-3xl font-semibold tracking-[-0.03em]">
          Your subscription checkout is complete.
        </h1>
        <p className="mt-4 text-base leading-7 text-[#A8B0BA]">
          Paddle handles payment, tax, and the invoice record. LoreVia updates your access as soon as the webhook lands.
        </p>

        <div role="status" className="mt-6 border-l-2 border-[#C9A86A] px-4 py-2 text-sm leading-6 text-[#E7D3A8]">
          {message}
        </div>

        {confirmation ? (
          <div className="mt-8 grid gap-8 border-y border-white/10 py-6 md:grid-cols-2 md:divide-x md:divide-white/10">
            <div>
              <p className="text-sm font-semibold text-[#A8B0BA]">Plan</p>
              <p className="mt-3 text-2xl font-semibold text-[#F2F4F7]">
                {confirmation.display_name} {confirmation.billing_interval === "annual" ? "Annual" : "Monthly"}
              </p>
              <p className="mt-3 text-sm leading-6 text-[#A8B0BA]">
                Status: <span className="capitalize text-[#F2F4F7]">{confirmation.status}</span>
              </p>
              <p className="mt-2 text-sm leading-6 text-[#A8B0BA]">
                Total charged: <span className="text-[#F2F4F7]">{confirmation.total ?? "Processing"}</span>
              </p>
              <p className="mt-2 text-sm leading-6 text-[#A8B0BA]">
                Invoice number: <span className="text-[#F2F4F7]">{confirmation.invoice_number ?? "Will appear when Paddle finalizes the transaction"}</span>
              </p>
            </div>

            <div className="md:pl-8">
              <p className="text-sm font-semibold text-[#A8B0BA]">Account</p>
              <p className="mt-3 text-sm leading-6 text-[#A8B0BA]">
                Customer email: <span className="text-[#F2F4F7]">{confirmation.customer_email ?? "Unavailable"}</span>
              </p>
              <p className="mt-2 text-sm leading-6 text-[#A8B0BA]">
                Transaction ID: <span className="break-all text-[#F2F4F7]">{confirmation.transaction_id}</span>
              </p>
              <p className="mt-2 text-sm leading-6 text-[#A8B0BA]">
                Subscription ID: <span className="break-all text-[#F2F4F7]">{confirmation.subscription_id ?? "Will appear after Paddle completes provisioning"}</span>
              </p>
            </div>
          </div>
        ) : null}

        <div className="mt-8 flex flex-wrap gap-3">
          <Link
            href="/library"
            className="inline-flex items-center justify-center rounded-md bg-[#D2B47A] px-5 py-3 text-sm font-semibold text-[#05070A] transition hover:bg-[#E5CA91]"
          >
            Open your library
          </Link>
          {confirmation?.invoice_pdf_url ? (
            <a
              href={confirmation.invoice_pdf_url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center justify-center rounded-md border border-white/[0.12] px-5 py-3 text-sm font-semibold text-[#F2F4F7] transition hover:border-[#C9A86A]/45"
            >
              Open invoice PDF
            </a>
          ) : null}
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="inline-flex items-center justify-center px-2 py-3 text-sm font-semibold text-[#A8B0BA] transition hover:text-white"
          >
            Refresh status
          </button>
        </div>
      </div>
    </section>
  )
}
