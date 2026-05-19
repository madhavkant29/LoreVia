import type { Metadata } from "next"
import { headers } from "next/headers"
import { Suspense } from "react"

import { PaddleCheckoutPage } from "@/components/billing/PaddleCheckoutPage"

export const metadata: Metadata = {
  title: "Secure Checkout",
  description: "LoreVia secure Paddle checkout page for hosted billing actions.",
  robots: {
    index: false,
    follow: false,
  },
}

export default async function CheckoutPage() {
  const nonce = (await headers()).get("x-nonce") ?? undefined

  return (
    <Suspense fallback={null}>
      <PaddleCheckoutPage nonce={nonce} />
    </Suspense>
  )
}
