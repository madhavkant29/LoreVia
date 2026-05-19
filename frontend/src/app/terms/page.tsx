import type { Metadata } from "next"

import { LegalPageShell } from "@/components/legal/LegalPageShell"

export const metadata: Metadata = {
  title: "Terms & Conditions",
  description: "Read the LoreVia for authors Terms & Conditions for account responsibilities, permitted uploads, AI outputs, billing, and acceptable use.",
  alternates: {
    canonical: "/terms",
  },
}

const effectiveDate = "May 19, 2026"

const sections = [
  {
    title: "Acceptance and product scope",
    paragraphs: [
      "These Terms govern your access to and use of LoreVia's website, applications, and related services. By using the service, you agree to these Terms and our Privacy Policy.",
      "LoreVia is an AI-powered writing, manuscript intelligence, and creator publishing platform. It is not an unrestricted ebook mirror, public library, or upload-any-book service.",
    ],
  },
  {
    title: "Eligibility and account responsibility",
    paragraphs: [
      "You must be old enough to enter a binding agreement in your jurisdiction to use LoreVia. You are responsible for safeguarding your account and for activity that happens under it.",
      "You agree to provide accurate account information, keep your login credentials secure, and notify LoreVia if you suspect unauthorized access.",
    ],
  },
  {
    title: "Your content, ownership, and limited license",
    paragraphs: [
      "You retain ownership of the manuscripts, notes, and other content you submit to LoreVia. When you upload or publish content, you represent and warrant that you own it or have all rights, licenses, and permissions needed to upload, process, and publish it.",
      "You grant LoreVia a limited license to store, process, display public content, run AI analysis features, generate derived metadata such as embeddings, and otherwise operate and improve the product. This license is limited to operating LoreVia and does not transfer ownership to us.",
    ],
  },
  {
    title: "Public publishing rules",
    paragraphs: [
      "Public publishing on LoreVia is opt-in. Private manuscripts and workspaces are not public books unless you deliberately choose to publish them.",
      "You may publicly publish only original work you created, work you own, work you are licensed to publish, or material explicitly approved by LoreVia as public-domain demonstration content.",
    ],
    bullets: [
      "Do not publish pirated books, copied novels, scraped webnovels, EPUB dumps, fan translations you do not own, paid newsletter or membership content, or franchise works without permission.",
      "Do not use LoreVia to impersonate another creator or to repost third-party content without authorization.",
      "LoreVia may require explicit rights confirmation before a book becomes public.",
    ],
  },
  {
    title: "User responsibility and third-party claims",
    paragraphs: [
      "You are solely responsible for the content you upload or publish, including copyright infringement, licensing violations, plagiarism, unauthorized reposting, and claims brought by third parties.",
      "If a dispute arises over your content, LoreVia may request additional information, remove or restrict access to the content, or suspend related publishing activity while the issue is reviewed.",
    ],
  },
  {
    title: "LoreVia enforcement rights",
    paragraphs: [
      "LoreVia may remove, hide, restrict, or disable access to content at any time if we believe it violates these Terms, infringes rights, creates platform risk, or harms other users.",
      "LoreVia may investigate reports, contact uploaders, reject abusive reports, apply strikes, disable public publishing, suspend accounts, or terminate service for repeat infringers or serious abuse.",
    ],
  },
  {
    title: "AI-assisted outputs and service limits",
    paragraphs: [
      "LoreVia provides AI-generated assistance, summaries, and analysis tools. Outputs may be incomplete, inaccurate, or unsuitable without human review.",
      "You are responsible for reviewing and verifying AI-assisted output before relying on it for creative, legal, commercial, or publication decisions.",
    ],
  },
  {
    title: "Availability, billing, and changes",
    paragraphs: [
      "LoreVia may change features, pricing, limits, moderation workflows, and product functionality over time. We do not guarantee uninterrupted availability.",
      "Paid subscriptions renew according to their billing terms unless canceled. Fees are non-refundable except where required by law or stated otherwise.",
    ],
  },
  {
    title: "Ownership of the service and legal boundaries",
    paragraphs: [
      "LoreVia and its licensors retain all rights in the software, branding, design, and service itself. Feedback you provide may be used to improve the product without obligation to you.",
      "These Terms are governed by the laws applicable to LoreVia's operating entity, without regard to conflict-of-law rules.",
    ],
  },
] as const

export default function TermsPage() {
  return (
    <LegalPageShell
      eyebrow="Terms"
      title="Terms for a creator-first publishing and manuscript platform"
      description="These terms explain what you can publish on LoreVia, what stays private unless you choose otherwise, and how LoreVia handles abuse, reports, and repeat infringement."
      effectiveDate={effectiveDate}
      notice="By creating an account or using LoreVia, you agree to these Terms. Public books are optional and rights-sensitive. Private workspace content does not become public unless you deliberately publish it."
      sections={sections}
    />
  )
}
