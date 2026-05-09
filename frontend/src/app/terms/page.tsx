import type { Metadata } from "next"

import { LegalPageShell } from "@/components/legal/LegalPageShell"

export const metadata: Metadata = {
  title: "Terms & Conditions",
  description: "Read the LoreVia Terms & Conditions for account responsibilities, permitted uploads, AI outputs, billing, and acceptable use.",
  alternates: {
    canonical: "/terms",
  },
}

const effectiveDate = "May 8, 2026"

const sections = [
  {
    title: "Acceptance and product scope",
    body:
      "These Terms govern your access to and use of LoreVia's website, web applications, and related services. By using the Service, you accept and agree to be bound by these Terms and our Privacy Policy and AI Output License Agreement, which are incorporated by reference.",
  },
  {
    title: "Eligibility and account responsibility",
    body:
      "You must be at least the age of majority in your jurisdiction to use the Service. You are responsible for maintaining the confidentiality of your account credentials and for all activities under your account. You agree to provide accurate and current information and to notify us of any unauthorized use.",
  },
  {
    title: "Your content and permitted uploads",
    body:
      "You retain ownership of the content you submit to LoreVia. You grant LoreVia a limited license to process, store, and analyze your content solely to provide and improve the Service. You represent that you have the rights necessary to upload and use your content and that it does not infringe or violate the rights of others.",
  },
  {
    title: "Acceptable use and prohibited behavior",
    body:
      "You agree to use LoreVia only for lawful purposes and in accordance with these Terms. You will not upload or generate content that is illegal, harmful, infringing, or abusive. You will not attempt to reverse engineer, disrupt, or gain unauthorized access to any part of the Service or its systems.",
  },
  {
    title: "AI-assisted outputs and product limitations",
    body:
      "LoreVia provides AI-generated content and suggestions to support your creative process. Outputs may be incomplete, inaccurate, or require human review. You are responsible for evaluating and verifying all content. LoreVia does not guarantee any particular outcome or the factual accuracy of AI-generated material.",
  },
  {
    title: "Subscriptions, pricing, and renewals",
    body:
      "Some features require a paid subscription. Fees are billed in advance and are non-refundable except as required by law. Subscriptions renew automatically unless canceled before the end of the current billing period. Prices may change with notice. See our Refund Policy for details.",
  },
  {
    title: "Availability, updates, and suspension",
    body:
      "We strive to provide reliable access but do not guarantee uninterrupted service. We may update, modify, or suspend the Service, or any part of it, at any time with or without notice. We are not liable for any downtime or data loss, and we encourage regular backups of your content.",
  },
  {
    title: "Ownership, feedback, and legal boundaries",
    body:
      "LoreVia and its licensors retain all rights in the Service, including software, branding, and design. You may provide feedback and suggestions, which we may use without obligation. These Terms are governed by the laws of the jurisdiction in which LoreVia is established, without regard to conflict of law principles.",
  },
] as const

export default function TermsPage() {
  return (
    <LegalPageShell
      eyebrow="Terms"
      title="Terms & Conditions for using LoreVia"
      description="These terms explain how you may use LoreVia, what you are responsible for, and where the product's limits begin."
      effectiveDate={effectiveDate}
      notice="By creating an account or using LoreVia, you agree to these Terms. If you do not agree, please do not use the Service."
      sections={sections}
    />
  )
}
