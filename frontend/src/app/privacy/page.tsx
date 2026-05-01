import type { Metadata } from "next"
import Link from "next/link"
import { LEGAL_EMAIL, SUPPORT_EMAIL } from "@/lib/constants/contact"

export const metadata: Metadata = {
  title: "Privacy Policy",
  description: "Read the LoreVia privacy policy to understand how we handle account and manuscript data.",
}

export default function PrivacyPage() {
  return (
    <main className="min-h-screen bg-[linear-gradient(180deg,#020202_0%,#0a0a0a_45%,#111111_100%)] px-6 py-16 text-white">
      <div className="mx-auto max-w-4xl">
        <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400">LoreVia</p>
        <h1 className="mt-3 text-4xl font-semibold text-white">Privacy Policy</h1>
        <p className="mt-4 text-sm text-slate-500">Effective date: April 28, 2026</p>

        <div className="mt-8 space-y-6 text-sm leading-7 text-slate-300">
          <p>
            This policy explains how LoreVia handles account details, uploaded manuscripts, and service data. It is a
            plain-language summary of the main privacy practices for the product.
          </p>
          <p>
            We use account information to create and secure your profile, authenticate you, and provide the features
            you request. We use manuscript content to generate story analysis, summaries, and continuity insights.
          </p>
          <p>
            Your content is processed to deliver the service, but it remains your responsibility to ensure you have the
            right to upload and analyze the material.
          </p>
          <p>
            We may retain operational logs and product analytics to diagnose issues, improve reliability, and protect
            the service from abuse.
          </p>
          <p>
            If you need help with privacy questions, email{" "}
            <a className="font-medium text-white underline decoration-white/30 underline-offset-4" href={`mailto:${SUPPORT_EMAIL}`}>
              {SUPPORT_EMAIL}
            </a>{" "}
            or{" "}
            <a className="font-medium text-white underline decoration-white/30 underline-offset-4" href={`mailto:${LEGAL_EMAIL}`}>
              {LEGAL_EMAIL}
            </a>
            .
          </p>
          <p className="pt-2 text-slate-400">
            Back to{" "}
            <Link href="/" className="text-white underline decoration-white/30 underline-offset-4">
              landing page
            </Link>
            .
          </p>
        </div>
      </div>
    </main>
  )
}
