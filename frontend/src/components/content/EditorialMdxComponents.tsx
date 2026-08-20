import Image from "next/image"
import Link from "next/link"
import type { Route } from "next"
import type { ComponentPropsWithoutRef, ReactNode } from "react"

import { slugifyHeading } from "@/content/slug"

function nodeText(node: ReactNode): string {
  if (typeof node === "string" || typeof node === "number") return String(node)
  if (Array.isArray(node)) return node.map(nodeText).join("")
  if (node && typeof node === "object" && "props" in node) {
    return nodeText((node as { props: { children?: ReactNode } }).props.children)
  }
  return ""
}

function MdxLink({ href = "", children, ...props }: ComponentPropsWithoutRef<"a">) {
  const className = "font-medium text-[rgb(var(--accent))] underline decoration-[rgba(var(--accent),0.35)] underline-offset-4 transition hover:decoration-[rgb(var(--accent))]"
  if (href.startsWith("/")) {
    return <Link href={href as Route} className={className}>{children}</Link>
  }
  return (
    <a {...props} href={href} className={className} target="_blank" rel="noreferrer">
      {children}
    </a>
  )
}

function MdxHeadingTwo({ children }: { children?: ReactNode }) {
  const label = nodeText(children)
  return (
    <h2 id={slugifyHeading(label)} className="scroll-mt-28 font-display text-[2rem] font-semibold leading-[1.12] tracking-[-0.035em] text-foreground sm:text-[2.4rem]">
      {children}
    </h2>
  )
}

function MdxHeadingThree({ children }: { children?: ReactNode }) {
  const label = nodeText(children)
  return (
    <h3 id={slugifyHeading(label)} className="scroll-mt-28 text-[1.35rem] font-semibold leading-snug tracking-[-0.02em] text-foreground sm:text-[1.55rem]">
      {children}
    </h3>
  )
}

export function EditorialCallout({ title = "Editor’s note", children }: { title?: string; children?: ReactNode }) {
  return (
    <aside className="editorial-callout" aria-label={title}>
      <p className="editorial-callout__label">{title}</p>
      <div className="editorial-callout__body">{children}</div>
    </aside>
  )
}

export function EditorialPullQuote({ children }: { children?: ReactNode }) {
  return <blockquote className="editorial-pull-quote">{children}</blockquote>
}

export function EditorialFigure({
  src,
  alt,
  caption,
}: {
  src: string
  alt: string
  caption?: string
}) {
  return (
    <figure className="editorial-figure">
      <Image
        src={src}
        alt={alt}
        width={1400}
        height={788}
        sizes="(max-width: 768px) 100vw, 720px"
        className="h-auto w-full border border-[rgba(var(--border),0.72)] object-cover"
      />
      {caption ? <figcaption>{caption}</figcaption> : null}
    </figure>
  )
}

export const editorialMdxComponents = {
  a: MdxLink,
  h1: ({ children }: { children?: ReactNode }) => <h1 className="font-display text-4xl text-foreground">{children}</h1>,
  h2: MdxHeadingTwo,
  h3: MdxHeadingThree,
  p: ({ children }: { children?: ReactNode }) => <p>{children}</p>,
  ul: ({ children }: { children?: ReactNode }) => <ul>{children}</ul>,
  ol: ({ children }: { children?: ReactNode }) => <ol>{children}</ol>,
  li: ({ children }: { children?: ReactNode }) => <li>{children}</li>,
  blockquote: ({ children }: { children?: ReactNode }) => <blockquote>{children}</blockquote>,
  table: ({ children }: { children?: ReactNode }) => <div className="editorial-table-wrap"><table>{children}</table></div>,
  thead: ({ children }: { children?: ReactNode }) => <thead>{children}</thead>,
  tbody: ({ children }: { children?: ReactNode }) => <tbody>{children}</tbody>,
  tr: ({ children }: { children?: ReactNode }) => <tr>{children}</tr>,
  th: ({ children }: { children?: ReactNode }) => <th>{children}</th>,
  td: ({ children }: { children?: ReactNode }) => <td>{children}</td>,
  hr: () => <hr />,
  Callout: EditorialCallout,
  PullQuote: EditorialPullQuote,
  Figure: EditorialFigure,
}
