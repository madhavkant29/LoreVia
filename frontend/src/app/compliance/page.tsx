import type { Metadata } from "next"

import { TrustPage } from "@/components/legal/TrustPage"
import { LEGAL_EMAIL, SUPPORT_EMAIL } from "@/lib/constants/contact"
import { TRUST_EFFECTIVE_DATE } from "@/lib/constants/trust"

export const metadata: Metadata = {
  title: "Security & Compliance",
  description: "Read how LoreVia approaches security, responsible data handling, vendor usage, and workload suitability.",
  alternates: {
    canonical: "/compliance",
  },
}

const sections = [
  {
    title: "What this page is for",
    paragraphs: [
      "This page is LoreVia's plain-language trust overview for website visitors, authors, readers, and small teams evaluating whether the product is an appropriate place to process manuscripts. It is not a certification page and it should not be read as a claim that LoreVia satisfies every regulated framework by default.",
      "Instead, it explains the practical security posture of the product: what kinds of workflows the app is designed for, where third-party providers fit into the stack, what customer responsibilities still matter, and how to think about manuscript sensitivity before uploading anything.",
    ],
  },
  {
    title: "Security design priorities",
    paragraphs: [
      "LoreVia is built around the idea that manuscript tools need to balance utility with restraint. The application uses authenticated accounts, session handling, and plan-based access controls so that private workspaces are not exposed as public content by default. Billing is handled through a dedicated payment flow rather than storing raw payment card data directly in the main app experience.",
      "The product also keeps optional analytics separate from essential account functionality. Users can decline analytics cookies and still use the site, which helps keep product measurement from being confused with the controls needed to run the application itself.",
    ],
  },
  {
    title: "How manuscript data moves through the product",
    paragraphs: [
      "When you upload text into LoreVia, the product may store that material, derive structured metadata from it, and process relevant excerpts through model-backed workflows to generate summaries, insights, search aids, and other outputs you requested. That means your content may pass through storage, application processing, and model-assisted inference steps in the normal course of using the service.",
      "This is why LoreVia is explicit about intended use. The product is built for manuscript intelligence, continuity review, and creative reference workflows. It is not presented as an isolated offline editor or a no-processing archive.",
    ],
  },
  {
    title: "Current vendor roles in the stack",
    paragraphs: [
      "As reflected in the current codebase, LoreVia uses third-party providers to help deliver authentication, storage, model-backed features, billing, and optional analytics. At the time this page was published, those integrations include Supabase-related authentication flows, S3-compatible object storage, OpenAI-powered processing paths, Paddle billing infrastructure, and PostHog analytics.",
      "That does not mean every provider receives every category of data. Vendors are used for specific operational roles, and the product is structured so that payment processing, analytics, storage, and account access each happen through the parts of the stack that are relevant to that task.",
    ],
  },
  {
    title: "What LoreVia is appropriate for",
    paragraphs: [
      "LoreVia is appropriate for creative writing, editorial planning, reading workflows, and manuscript analysis where the people using the service have the right to submit the material. It can be a good fit for draft novels, beta-reading workflows, continuity checking, story research notes, and related creative production tasks.",
      "LoreVia is not advertised as a default fit for highly regulated or extremely sensitive datasets. Unless LoreVia has explicitly agreed otherwise in writing, you should not treat the product as approved for medical records, raw payment card storage, government-classified information, export-controlled content, or other workloads that require specialized contractual, regulatory, or infrastructure assurances.",
    ],
  },
  {
    title: "Shared responsibility still applies",
    paragraphs: [
      "Security is not only a vendor promise. Users still control what content gets uploaded, who receives account access, whether a manuscript contains embedded personal or contractual information, and whether an internal policy allows that material to be processed in a cloud application. The wrong upload decision can create risk even when the application itself is operating as designed.",
      "If you represent a company, editorial team, or client-facing workflow, you should evaluate whether your own confidentiality rules permit the use of a model-assisted manuscript platform before importing the material. LoreVia can explain how the product works, but it cannot decide your internal data classification rules for you.",
    ],
  },
  {
    title: "Reporting incidents and security concerns",
    paragraphs: [
      "If you believe you found a security issue, exposed data path, account compromise, or policy mismatch, contact LoreVia directly instead of posting exploit details publicly. The most useful initial report includes the affected route, steps to reproduce, whether user data may have been exposed, and whether you already verified the issue on a real account or only a test path.",
      "Operational service incidents are communicated through the public status page. Security-sensitive reports should go through direct email so we can investigate without turning an active issue into a wider risk event before it is contained.",
    ],
  },
  {
    title: "Procurement and trust questions",
    paragraphs: [
      "If you need to evaluate LoreVia for a team or business workflow, ask the concrete question rather than assuming a certification that is not listed. For example, you might ask whether a certain data type is appropriate, whether a specific workflow touches model providers, or whether your organization should avoid using the product for a particular manuscript class.",
      "That kind of narrow, factual conversation is usually more useful than boilerplate security theater. It keeps the trust conversation tied to the actual product, the real workflow, and the data you want to protect.",
    ],
  },
] as const

export default function CompliancePage() {
  return (
    <TrustPage
      currentPath="/compliance"
      eyebrow="Security"
      title="Security and compliance for LoreVia's real workload."
      description="LoreVia is a manuscript-processing web product, so trust has to be described in terms of accounts, uploads, vendor roles, and shared responsibility rather than vague certification language."
      effectiveDate={TRUST_EFFECTIVE_DATE}
      intro={[
        "This page is intentionally direct. It explains what LoreVia is built for, what it is not built for, and where third-party services are part of the delivery path.",
        "If you are evaluating the footer docs as part of a security review, this is the page that ties the product story together: manuscript uploads, AI-assisted processing, payment boundaries, status communications, and the places where customer judgment still matters.",
      ]}
      facts={[
        {
          label: "Best fit",
          value: "Creative and editorial workflows",
          detail: "LoreVia is positioned for manuscript analysis and story reference work, not every regulated data class.",
        },
        {
          label: "Payments",
          value: "Handled through Paddle",
          detail: "The app uses a dedicated billing provider instead of storing raw payment card details in its own interface.",
        },
        {
          label: "Live incidents",
          value: "Published on the status page",
          detail: "Operational uptime and maintenance updates belong on the public status host rather than hidden inside static docs.",
        },
        {
          label: "Security contact",
          value: LEGAL_EMAIL,
          detail: `Use ${LEGAL_EMAIL} or ${SUPPORT_EMAIL} for responsible disclosure and trust questions that need a direct response.`,
        },
      ]}
      sections={[...sections]}
      contacts={[
        {
          title: "Security reports",
          description: "Send vulnerability reports, suspected exposure issues, or trust questions that should be handled privately.",
          ctaLabel: LEGAL_EMAIL,
          ctaHref: `mailto:${LEGAL_EMAIL}`,
        },
        {
          title: "Operational support",
          description: "Use support when an account problem, billing issue, or product defect looks like a service issue rather than a vulnerability report.",
          ctaLabel: SUPPORT_EMAIL,
          ctaHref: `mailto:${SUPPORT_EMAIL}`,
        },
      ]}
    />
  )
}
