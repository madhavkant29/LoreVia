import type { Metadata } from "next"
import { redirect } from "next/navigation"

export const metadata: Metadata = {
  title: "Security & Compliance",
  description: "Read LoreVia's security, data-handling, and compliance information.",
}

export default function BookComplianceRedirect() {
  redirect("/compliance")
}
