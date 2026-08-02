import type { GlyphName } from "./LibraryClient.helpers"

export function SearchIcon({ className }: { className?: string }) {
  return (
    <svg className={`h-5 w-5 ${className ?? ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M11 18a7 7 0 100-14 7 7 0 000 14zM20 20l-4-4" />
    </svg>
  )
}

export function CalendarMetricIcon() {
  return (
    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M7 4v3M17 4v3M5 9h14" />
      <rect x="5" y="5.5" width="14" height="14" rx="2.5" />
    </svg>
  )
}

export function DraftMetricIcon() {
  return (
    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M5 19l4.2-1 9-9a2.1 2.1 0 00-3-3l-9 9L5 19z" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 7.5l3 3" />
    </svg>
  )
}

export function PulseMetricIcon() {
  return (
    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M4 12h3l2-5 4 10 2-5h5" />
    </svg>
  )
}

export function FilterIcon({ className }: { className?: string }) {
  return (
    <svg className={`h-5 w-5 ${className ?? ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16l-6 7v5l-4 2v-7L4 6z" />
    </svg>
  )
}

export function GridIcon() {
  return (
    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
      <rect x="4" y="4" width="6" height="6" rx="1.4" />
      <rect x="14" y="4" width="6" height="6" rx="1.4" />
      <rect x="4" y="14" width="6" height="6" rx="1.4" />
      <rect x="14" y="14" width="6" height="6" rx="1.4" />
    </svg>
  )
}

export function ListIcon() {
  return (
    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M8 6h12M8 12h12M8 18h12M4 6h.01M4 12h.01M4 18h.01" />
    </svg>
  )
}

export function PinIcon({ className }: { className?: string }) {
  return (
    <svg className={`h-4 w-4 ${className ?? ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M14 4l6 6-3 1-4 7-2-2 7-4 1-3-6-6 1-1zM8 14l-4 6" />
    </svg>
  )
}

export function FolderIcon({ className }: { className?: string }) {
  return (
    <svg className={`h-4 w-4 ${className ?? ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M3.5 7.5A2.5 2.5 0 016 5h4l2 2H18a2.5 2.5 0 012.5 2.5v7A2.5 2.5 0 0118 19H6a2.5 2.5 0 01-2.5-2.5v-9z" />
    </svg>
  )
}

export function PlusIcon() {
  return (
    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 5v14M5 12h14" />
    </svg>
  )
}

export function PlusLargeIcon() {
  return (
    <svg className="h-8 w-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.6}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 5v14M5 12h14" />
    </svg>
  )
}

export function DotsIcon() {
  return (
    <svg className="h-5 w-5" fill="currentColor" viewBox="0 0 20 20">
      <path d="M4 10a1.4 1.4 0 112.8 0A1.4 1.4 0 014 10zm4.6 0a1.4 1.4 0 112.8 0 1.4 1.4 0 01-2.8 0zm4.6 0a1.4 1.4 0 112.8 0 1.4 1.4 0 01-2.8 0z" />
    </svg>
  )
}

export function GroupIcon() {
  return (
    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.7}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 11a3 3 0 100-6 3 3 0 000 6zM4 19a5 5 0 0110 0M17 11a2.5 2.5 0 100-5M15.5 15.5A4.5 4.5 0 0120 20" />
    </svg>
  )
}

export function PageIcon() {
  return (
    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.7}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M7 4h8l3 3v13H7V4z" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M15 4v4h4M9 12h6M9 16h4" />
    </svg>
  )
}

export function AlertIcon() {
  return (
    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.7}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 4l8 14H4l8-14z" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v4M12 17h.01" />
    </svg>
  )
}

export function ProjectGlyph({ glyph }: { glyph: GlyphName }) {
  const className = "h-7 w-7"

  switch (glyph) {
    case "moon":
      return (
        <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M15.5 3.5a8.5 8.5 0 108 12.2A8 8 0 0115.5 3.5z" />
          <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 7.5l.7 1.6 1.6.7-1.6.7-.7 1.6-.7-1.6-1.6-.7 1.6-.7.7-1.6z" />
        </svg>
      )
    case "spark":
      return (
        <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 3v18M3 12h18M6.5 6.5l11 11M17.5 6.5l-11 11" />
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 6l1.3 4.7L18 12l-4.7 1.3L12 18l-1.3-4.7L6 12l4.7-1.3L12 6z" />
        </svg>
      )
    case "leaf":
      return (
        <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M18.5 5.5C11 5.5 6 10.2 6 16.4c0 1 .1 1.9.4 2.6 7.1-.4 12.1-5.1 12.1-11.4z" />
          <path strokeLinecap="round" strokeLinejoin="round" d="M7 17c2.8-2.5 5.7-4.6 9.5-6.2" />
        </svg>
      )
    case "crown":
      return (
        <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 18l1.8-9 5.7 4.2L17.7 9l1.8 9H4.5z" />
          <path strokeLinecap="round" strokeLinejoin="round" d="M8 18V7m8 11V7" />
        </svg>
      )
    case "wave":
      return (
        <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M4 8c2 0 2-1 4-1s2 1 4 1 2-1 4-1 2 1 4 1" />
          <path strokeLinecap="round" strokeLinejoin="round" d="M4 13c2 0 2-1 4-1s2 1 4 1 2-1 4-1 2 1 4 1" />
          <path strokeLinecap="round" strokeLinejoin="round" d="M4 18c2 0 2-1 4-1s2 1 4 1 2-1 4-1 2 1 4 1" />
        </svg>
      )
    case "diamond":
      return (
        <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 4l8 8-8 8-8-8 8-8z" />
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 8l4 4-4 4-4-4 4-4z" />
        </svg>
      )
    case "orbit":
      return (
        <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <circle cx="12" cy="12" r="2.2" />
          <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12c2.4-4.7 12.6-4.7 15 0-2.4 4.7-12.6 4.7-15 0z" />
          <path strokeLinecap="round" strokeLinejoin="round" d="M8 4.8c4.8-1.6 10.4 6.7 8.1 11.5-4.8 1.6-10.4-6.7-8.1-11.5z" />
        </svg>
      )
    case "star":
    default:
      return (
        <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 4l1.8 5.7L20 12l-6.2 2.3L12 20l-1.8-5.7L4 12l6.2-2.3L12 4z" />
        </svg>
      )
  }
}
