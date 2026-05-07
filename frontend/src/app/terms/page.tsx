import type { Metadata } from "next"

import { TrustPage } from "@/components/legal/TrustPage"
import { LEGAL_EMAIL, SUPPORT_EMAIL } from "@/lib/constants/contact"
import { TRUST_EFFECTIVE_DATE } from "@/lib/constants/trust"

export const metadata: Metadata = {
  title: "Terms of Service",
  description: "Read the LoreVia Terms of Service for the rules covering accounts, manuscript uploads, AI outputs, billing, and acceptable use.",
  alternates: {
    canonical: "/terms",
  },
}

const sections = [
  {
    title: "Acceptance and product scope",
    paragraphs: [
      "These Terms of Service govern access to and use of the LoreVia website, web application, and related services. By browsing the site, creating an account, uploading content, or using a LoreVia feature, you agree to these terms and to the related policies linked from the footer, including the Privacy Policy, Refund Policy, and End User License Agreement.",
      "LoreVia is a manuscript intelligence and reading workflow product. It is built to help users organize, inspect, and reason about long-form written material. The service is intended for lawful creative, editorial, study, and reference workflows. It is not sold as a source-of-truth archive, regulated records system, or guaranteed publishing authority.",
    ],
  },
  {
    title: "Eligibility and account responsibility",
    paragraphs: [
      "You are responsible for the accuracy of the account information you provide and for protecting access to your account. If you sign in through a supported OAuth provider, you are also responsible for the permissions and security of that external identity account.",
      "You may not share access in a way that bypasses plan limits, impersonate another person, or use the service under a false identity to evade moderation, billing, suspension, or legal obligations. If you become aware of unauthorized account access, you should notify LoreVia promptly so we can investigate the session and take reasonable protective steps.",
    ],
  },
  {
    title: "Your content and permitted uploads",
    paragraphs: [
      "You retain responsibility for the books, drafts, notes, and other materials you submit to LoreVia. Upload only content that you own, control, or are otherwise authorized to process. That requirement matters because LoreVia does not merely store files. It analyzes them, derives structured outputs, and may send relevant portions through model-backed workflows to produce the features you asked for.",
      "If your publishing agreement, employer policy, client contract, or governing law does not permit that level of processing, do not upload the material. LoreVia is not responsible for clearing rights on your behalf or determining whether a specific manuscript is safe for you to submit under your own legal obligations.",
    ],
  },
  {
    title: "Acceptable use and prohibited behavior",
    paragraphs: [
      "You may not use LoreVia to break the law, violate intellectual property rights, harass others, interfere with product operations, or probe the system for unauthorized access. The service also may not be used to build a data-extraction pipeline against other users, scrape private content, bypass feature limits, or reverse engineer internal behavior in a way that harms the platform or its users.",
      "We reserve the right to investigate misuse and to suspend, restrict, or terminate accounts when necessary to protect the service, comply with law, enforce plan limits, respond to complaints, or reduce security risk.",
    ],
    bullets: [
      "No uploading content you know you are not allowed to process.",
      "No deliberate attempts to break authentication, session handling, rate limits, or payment controls.",
      "No automated or bulk extraction of other users' private data or product behavior for a competing service.",
      "No use of LoreVia for unlawful, abusive, infringing, or clearly high-risk workloads that the product is not designed to support.",
    ],
  },
  {
    title: "AI-assisted outputs and product limitations",
    paragraphs: [
      "LoreVia uses AI-assisted and heuristic systems to generate summaries, character context, continuity cues, search aids, advisor responses, and related manuscript insights. Those outputs can be useful, but they can also be incomplete, stale, or wrong. A generated answer is not a guarantee that the manuscript has been perfectly interpreted.",
      "You remain responsible for verifying important editorial, legal, publishing, or narrative decisions. If an AI-generated response matters to rights clearance, contractual interpretation, factual publication claims, or safety-critical decisions, you must validate it independently.",
    ],
  },
  {
    title: "Subscriptions, pricing, and renewals",
    paragraphs: [
      "Some LoreVia features require a paid plan. If you purchase a subscription, billing, renewals, and customer payment mechanics are handled through the checkout and billing providers LoreVia uses at the time of purchase. Plan scope, feature availability, storage allowances, and product limits may change as the service evolves.",
      "Unless a separate offer says otherwise, paid subscriptions renew until cancelled. You are responsible for reviewing the plan details presented at checkout, including price, billing interval, and any taxes or processor-imposed conditions. Refunds and cancellations are handled according to the published Refund Policy and any mandatory consumer rights that apply by law.",
    ],
  },
  {
    title: "Availability, updates, and suspension",
    paragraphs: [
      "LoreVia works hard to stay available, but the service is provided on an as-available basis. We may change, refine, pause, or remove features, either temporarily or permanently, as part of product development, abuse prevention, maintenance, or legal risk management. Planned maintenance and unplanned incidents may be communicated through the public status page.",
      "We may suspend or limit access when we reasonably believe an account is violating these terms, threatening service stability, generating legal exposure, or placing other users at risk. When appropriate, we may attempt to notify the affected user, but immediate action can be taken when delay would materially increase risk.",
    ],
  },
  {
    title: "Ownership, feedback, and legal boundaries",
    paragraphs: [
      "LoreVia and its licensors retain all rights in the software, website, branding, and service design except where those rights are explicitly granted to users. Submitting feedback, product suggestions, or bug reports gives LoreVia permission to use that feedback to improve the product without owing compensation, unless a separate written agreement says otherwise.",
      "Nothing in these terms narrows any non-waivable rights that apply under mandatory law. If you have a formal legal question about these terms or need to send a rights-related notice, contact the legal address listed on this site.",
    ],
  },
] as const

export default function TermsPage() {
  return (
    <TrustPage
      currentPath="/terms"
      eyebrow="Terms"
      title="Ground rules for using LoreVia responsibly."
      description="These terms explain who may use LoreVia, what users are responsible for when they upload manuscripts, how paid features work, and where the product's limits begin."
      effectiveDate={TRUST_EFFECTIVE_DATE}
      intro={[
        "LoreVia is not a generic social app. It processes long-form text, account data, payment status, and model-backed features in ways that require clear responsibilities on both sides.",
        "These terms are written to match that reality. They focus on lawful uploads, acceptable use, plan enforcement, and the practical limits of AI-assisted editorial tooling.",
      ]}
      facts={[
        {
          label: "Primary use",
          value: "Reading, writing, editorial workflows",
          detail: "LoreVia is intended for lawful manuscript and narrative-analysis use, not unrestricted high-risk data handling.",
        },
        {
          label: "User obligation",
          value: "Upload only authorized content",
          detail: "If you do not have the right to process a work through LoreVia, you should not submit it.",
        },
        {
          label: "Paid access",
          value: "Subscriptions may renew until cancelled",
          detail: "Checkout terms, feature limits, and the Refund Policy work together to define paid usage.",
        },
        {
          label: "Questions",
          value: LEGAL_EMAIL,
          detail: `Use ${SUPPORT_EMAIL} for support and ${LEGAL_EMAIL} for formal legal or rights-related questions.`,
        },
      ]}
      sections={[...sections]}
      contacts={[
        {
          title: "General support",
          description: "Use support for account issues, billing access problems, and questions about how the product works in practice.",
          ctaLabel: SUPPORT_EMAIL,
          ctaHref: `mailto:${SUPPORT_EMAIL}`,
        },
        {
          title: "Legal and rights questions",
          description: "Use the legal inbox for formal notices, rights complaints, licensing questions, or contract-sensitive issues.",
          ctaLabel: LEGAL_EMAIL,
          ctaHref: `mailto:${LEGAL_EMAIL}`,
        },
      ]}
    />
  )
}
