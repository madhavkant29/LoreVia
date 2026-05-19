import type { Metadata } from "next"
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

export default function CheckoutPage() {
  return (
    <Suspense fallback={null}>
      <PaddleCheckoutPage />
    </Suspense>
  )
}
