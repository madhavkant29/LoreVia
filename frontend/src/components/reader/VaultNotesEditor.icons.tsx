export function IconSearch() {
  return <svg className="h-4 w-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}><path strokeLinecap="round" strokeLinejoin="round" d="M11 18a7 7 0 100-14 7 7 0 000 14zM16 16l4 4" /></svg>
}

export function IconSliders() {
  return <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}><path strokeLinecap="round" strokeLinejoin="round" d="M4 6h8M16 6h4M10 6a2 2 0 11-4 0 2 2 0 014 0zM4 12h4M12 12h8M14 12a2 2 0 11-4 0 2 2 0 014 0zM4 18h10M18 18h2M16 18a2 2 0 11-4 0 2 2 0 014 0z" /></svg>
}

export function IconPlus() {
  return <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.9}><path strokeLinecap="round" strokeLinejoin="round" d="M12 5v14M5 12h14" /></svg>
}

export function IconCheck() {
  return <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M5 12.5l4 4L19 7.5" /></svg>
}

export function IconCopy() {
  return <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}><path strokeLinecap="round" strokeLinejoin="round" d="M9 9h10v11H9z" /><path strokeLinecap="round" strokeLinejoin="round" d="M5 15H4V5h10v1" /></svg>
}

export function IconUpload({ className = "" }: { className?: string }) {
  return <svg className={`h-4 w-4 ${className}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}><path strokeLinecap="round" strokeLinejoin="round" d="M12 16V4M7 9l5-5 5 5M5 20h14" /></svg>
}

export function IconDocument({ small = false }: { small?: boolean }) {
  return <svg className={small ? "h-4 w-4 shrink-0" : "h-5 w-5"} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}><path strokeLinecap="round" strokeLinejoin="round" d="M7 4h8l3 3v13H7V4z" /><path strokeLinecap="round" strokeLinejoin="round" d="M15 4v4h4M9 13h6M9 16h4" /></svg>
}

export function IconFolder() {
  return <svg className="h-4 w-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}><path strokeLinecap="round" strokeLinejoin="round" d="M4 7h6l2 2h8v9a2 2 0 01-2 2H6a2 2 0 01-2-2V7z" /></svg>
}

export function IconChevron({ open }: { open: boolean }) {
  return <svg className={`h-4 w-4 transition ${open ? "rotate-90" : ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}><path strokeLinecap="round" strokeLinejoin="round" d="M9 6l6 6-6 6" /></svg>
}

export function IconStar({ filled }: { filled: boolean }) {
  return filled
    ? <svg className="h-5 w-5" viewBox="0 0 24 24" fill="currentColor"><path d="M11.2 3.6a.85.85 0 011.6 0l2 4.78 5.17.44a.85.85 0 01.48 1.5l-3.93 3.4 1.19 5.04a.85.85 0 01-1.27.92L12 16.92l-4.44 2.76a.85.85 0 01-1.27-.92l1.19-5.04-3.93-3.4a.85.85 0 01.48-1.5l5.17-.44 2-4.78z" /></svg>
    : <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}><path strokeLinecap="round" strokeLinejoin="round" d="M11.2 3.6a.85.85 0 011.6 0l2 4.78 5.17.44a.85.85 0 01.48 1.5l-3.93 3.4 1.19 5.04a.85.85 0 01-1.27.92L12 16.92l-4.44 2.76a.85.85 0 01-1.27-.92l1.19-5.04-3.93-3.4a.85.85 0 01.48-1.5l5.17-.44 2-4.78z" /></svg>
}

export function IconExpand() {
  return <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}><path strokeLinecap="round" strokeLinejoin="round" d="M15 4h5v5M9 20H4v-5M20 9V4h-5M4 15v5h5" /></svg>
}

export function IconArrowUpRight() {
  return <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.9}><path strokeLinecap="round" strokeLinejoin="round" d="M7 17L17 7M9 7h8v8" /></svg>
}

export function IconArrowRight() {
  return <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.9}><path strokeLinecap="round" strokeLinejoin="round" d="M5 12h14M13 6l6 6-6 6" /></svg>
}

export function IconMore() {
  return <svg className="h-5 w-5" fill="currentColor" viewBox="0 0 24 24"><circle cx="5" cy="12" r="1.8" /><circle cx="12" cy="12" r="1.8" /><circle cx="19" cy="12" r="1.8" /></svg>
}

export function IconPencil() {
  return <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.9}><path strokeLinecap="round" strokeLinejoin="round" d="M4 20l4.5-1 9-9a2.2 2.2 0 10-3.1-3.1l-9 9L4 20z" /><path strokeLinecap="round" strokeLinejoin="round" d="M13 6l5 5" /></svg>
}
