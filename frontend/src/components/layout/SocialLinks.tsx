"use client"

import React from "react"

const SOCIAL_LINKS = [
  {
    href: "https://x.com/getLoreVia",
    label: "X",
    icon: (
      <svg aria-hidden="true" viewBox="0 0 24 24" className="h-4 w-4 fill-current">
        <path d="M18.9 2H22l-6.77 7.74L23.2 22h-6.25l-4.9-7.4L5.58 22H2.47l7.24-8.28L1.6 2h6.4l4.42 6.77L18.9 2Zm-1.1 18h1.73L7.07 3.9H5.2L17.8 20Z" />
      </svg>
    ),
  },
  {
    href: "https://www.instagram.com/getlorevia?igsh=MWk2YnFiMXI4bXc1Zg==",
    label: "Instagram",
    icon: (
      <svg aria-hidden="true" viewBox="0 0 24 24" className="h-4 w-4 fill-none stroke-current" strokeWidth="1.8">
        <rect x="3.25" y="3.25" width="17.5" height="17.5" rx="5.25" />
        <circle cx="12" cy="12" r="4.1" />
        <circle cx="17.35" cy="6.65" r="1" fill="currentColor" stroke="none" />
      </svg>
    ),
  },
]

interface SocialLinksProps {
  className?: string
  linkClassName?: string
}

export function SocialLinks({ className = "", linkClassName = "" }: SocialLinksProps) {
  return (
    <div className={className}>
      {SOCIAL_LINKS.map((link) => (
        <a
          key={link.label}
          href={link.href}
          target="_blank"
          rel="noreferrer"
          aria-label={link.label}
          className={linkClassName}
        >
          {link.icon}
        </a>
      ))}
    </div>
  )
}
