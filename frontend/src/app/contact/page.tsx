import type { Metadata } from "next"

import { TrustPage } from "@/components/legal/TrustPage"
import { LEGAL_EMAIL, SUPPORT_EMAIL } from "@/lib/constants/contact"
import { TRUST_EFFECTIVE_DATE } from "@/lib/constants/trust"

export const metadata: Metadata = {
  title: "Contact",
  description: "Find the right LoreVia contact path for support, billing, legal notices, copyright issues, and security concerns.",
  alternates: {
    canonical: "/contact",
  },
}

const sections = [
  {
    title: "How to reach LoreVia",
    paragraphs: [
      "LoreVia currently handles formal communication through email rather than through a large ticket portal or public forum. That keeps the contact surface small and makes it easier to route product support, legal notices, and security-sensitive issues to the right place.",
      "If you are unsure which inbox to use, support is usually the best starting point for account and product questions. Legal is the better path for rights complaints, licensing questions, formal notices, or security reports that should not be discussed in public.",
    ],
  },
  {
    title: "Use the support inbox for product and billing help",
    paragraphs: [
      `The support inbox at ${SUPPORT_EMAIL} is the main path for user help. Use it for account access problems, billing portal issues, refund review requests, bug reports, feature questions, manuscript workflow confusion, or anything else tied to how the product is behaving for you.`,
      "When you report a product issue, include enough context for a human to act on it. Helpful reports usually mention the account email, the page or feature involved, what you expected to happen, what actually happened, and whether the issue is repeatable.",
    ],
  },
  {
    title: "Use the legal inbox for formal matters",
    paragraphs: [
      `The legal inbox at ${LEGAL_EMAIL} should be used for copyright complaints, takedown requests, rights disputes, licensing questions, privacy requests that need formal handling, and other issues where a normal support conversation is not the right venue.`,
      "If you are sending a formal notice, include the identifying details that make the request actionable. For example, tell us which account, file, or published page is involved, what legal right or issue is being asserted, and what action you are asking LoreVia to take.",
    ],
  },
  {
    title: "Reporting a security issue responsibly",
    paragraphs: [
      "If you believe you found a vulnerability, exposed route, account takeover path, or other security defect, email LoreVia directly instead of posting the issue publicly. Early private reporting gives us a chance to verify, contain, and fix the problem before it becomes a wider risk.",
      "A strong initial report usually includes the affected URL or feature, the steps to reproduce, whether authentication was required, whether real user data may have been exposed, and whether you still have access to a safe test case that can help confirm the issue.",
    ],
  },
  {
    title: "What to include so we can help quickly",
    paragraphs: [
      "Clear reports move faster than emotional ones. If you need a response, send the shortest version of the facts that would let a teammate understand the problem without having to reconstruct the timeline from scratch.",
    ],
    bullets: [
      "The email address tied to the account, if you have one.",
      "The exact page, feature, or billing event involved.",
      "Screenshots, timestamps, and error text when relevant.",
      "Whether the issue is urgent because data, access, or billing may be affected right now.",
    ],
  },
  {
    title: "Response expectations",
    paragraphs: [
      "LoreVia aims to respond as quickly as practical, but response time can vary depending on the type of request, business hours, and whether the issue requires legal or technical investigation. Security reports, access problems, and billing errors generally need triage sooner than general feature suggestions.",
      "Sending the same request to both inboxes is not usually necessary unless the issue is truly both legal and operational. Duplicates can slow triage by creating parallel threads about the same incident.",
    ],
  },
] as const

export default function ContactPage() {
  return (
    <TrustPage
      currentPath="/contact"
      eyebrow="Contact"
      title="Reach the right LoreVia inbox the first time."
      description="Use this page to route support, billing, legal, copyright, privacy, and security questions without guessing which channel is appropriate."
      effectiveDate={TRUST_EFFECTIVE_DATE}
      intro={[
        "A lot of footer contact pages are decorative. This one is meant to be operational. It tells you where to send what, what context helps, and how to report something sensitive without turning it into a public problem first.",
        "LoreVia is a product for manuscript work, which means support requests can range from ordinary account issues to copyright or confidentiality concerns. Routing matters.",
      ]}
      facts={[
        {
          label: "Support",
          value: SUPPORT_EMAIL,
          detail: "Use for product help, billing questions, refunds, bugs, and account-access issues.",
        },
        {
          label: "Legal",
          value: LEGAL_EMAIL,
          detail: "Use for formal notices, rights disputes, licensing questions, privacy matters, and security reporting.",
        },
        {
          label: "Live operations",
          value: "status.getlorevia.com",
          detail: "Use the status page for active incidents and planned maintenance rather than waiting on manual email updates.",
        },
        {
          label: "Best reports",
          value: "Specific, reproducible, calm",
          detail: "Concise facts beat vague frustration when the goal is getting the issue fixed quickly.",
        },
      ]}
      sections={[...sections]}
      contacts={[
        {
          title: "Support and billing",
          description: "Product help, billing portal issues, refund reviews, account questions, and bug reports.",
          ctaLabel: SUPPORT_EMAIL,
          ctaHref: `mailto:${SUPPORT_EMAIL}`,
        },
        {
          title: "Legal, privacy, and security",
          description: "Formal notices, rights concerns, licensing questions, sensitive privacy matters, and vulnerability reports.",
          ctaLabel: LEGAL_EMAIL,
          ctaHref: `mailto:${LEGAL_EMAIL}`,
        },
        {
          title: "Service health",
          description: "Check the live public status host for maintenance windows and incident updates before assuming a local account problem.",
          ctaLabel: "status.getlorevia.com",
          ctaHref: "https://status.getlorevia.com",
        },
      ]}
    />
  )
}
