import type { IconName } from "./types"

export function Icon({ name, className = "h-4 w-4" }: { name: IconName; className?: string }) {
  const common = { className, fill: "none" as const, viewBox: "0 0 24 24", stroke: "currentColor", strokeWidth: 1.8 }

  switch (name) {
    case "analysis":
      return <svg {...common}><path strokeLinecap="round" strokeLinejoin="round" d="M5 19V9M10 19V5M15 19v-7M20 19V8M4 19h17" /></svg>
    case "bell":
      return <svg {...common}><path strokeLinecap="round" strokeLinejoin="round" d="M14.9 17H9.1m5.8 0H18l-1.3-1.3a2 2 0 01-.7-1.4V11a4 4 0 10-8 0v3.3a2 2 0 01-.7 1.4L6 17h3.1m5.8 0a3 3 0 11-5.8 0" /></svg>
    case "book":
      return <svg {...common}><path strokeLinecap="round" strokeLinejoin="round" d="M6 4h9a3 3 0 013 3v13H8a2 2 0 01-2-2V4zM8 18h10M9 8h5" /></svg>
    case "calendar":
      return <svg {...common}><path strokeLinecap="round" strokeLinejoin="round" d="M7 4v3M17 4v3M5 9h14M6 6h12a1 1 0 011 1v12H5V7a1 1 0 011-1z" /></svg>
    case "chat":
      return <svg {...common}><path strokeLinecap="round" strokeLinejoin="round" d="M5 6.5A3.5 3.5 0 018.5 3h7A3.5 3.5 0 0119 6.5v4A3.5 3.5 0 0115.5 14H11l-5 5v-5.5A3.5 3.5 0 015 10V6.5zM9 8h6M9 11h4" /></svg>
    case "chevron":
      return <svg {...common}><path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" /></svg>
    case "edit":
      return <svg {...common}><path strokeLinecap="round" strokeLinejoin="round" d="M4 20h4l11-11a2.6 2.6 0 10-4-4L4 16v4z" /></svg>
    case "file":
      return <svg {...common}><path strokeLinecap="round" strokeLinejoin="round" d="M7 4h8l3 3v13H7V4zM15 4v4h4M9 13h6M9 16h4" /></svg>
    case "flame":
      return <svg className={className} fill="currentColor" viewBox="0 0 24 24"><path d="M12.6 2.2c.5 2.8-.3 4.7-2.2 6.6-1.7 1.7-2.5 3.4-1.8 5.4.4 1.1 1.2 2 2.4 2.6-.3-1.4.2-2.8 1.4-4.1.9 1 1.8 2.2 1.8 4a3.6 3.6 0 01-3.8 3.6c-3.2 0-5.8-2.5-5.8-6.2 0-2.9 1.4-5.2 3.7-7.4 1.7-1.7 2.8-3.1 2.6-4.5h1.7zM14.8 4.8c2.9 2.5 4.6 5.3 4.6 8.7 0 4.7-3.2 8.3-8.1 8.3 3-.9 5.1-3.4 5.1-6.5 0-2.3-1.1-4.1-2.5-5.8.9-1.5 1.3-3 .9-4.7z" /></svg>
    case "gap":
      return <svg {...common}><path strokeLinecap="round" strokeLinejoin="round" d="M4 7h7M13 7h7M4 17h7M13 17h7M11 7l2 10" /></svg>
    case "gear":
      return <svg {...common}><path strokeLinecap="round" strokeLinejoin="round" d="M12 15.5a3.5 3.5 0 100-7 3.5 3.5 0 000 7z" /><path strokeLinecap="round" strokeLinejoin="round" d="M19 12a7 7 0 00-.1-1l2-1.5-2-3.4-2.4 1a7 7 0 00-1.7-1L14.5 3h-5l-.3 3.1a7 7 0 00-1.7 1l-2.4-1-2 3.4 2 1.5A7 7 0 005 12a7 7 0 00.1 1l-2 1.5 2 3.4 2.4-1a7 7 0 001.7 1l.3 3.1h5l.3-3.1a7 7 0 001.7-1l2.4 1 2-3.4-2-1.5c.1-.3.1-.7.1-1z" /></svg>
    case "graph":
      return <svg {...common}><path strokeLinecap="round" strokeLinejoin="round" d="M5 19V9M10 19V5M15 19v-7M20 19V8M4 19h17" /></svg>
    case "moon":
      return <svg {...common}><path strokeLinecap="round" strokeLinejoin="round" d="M20 15.5A8 8 0 018.5 4 8.5 8.5 0 1020 15.5z" /></svg>
    case "pen":
      return <svg {...common}><path strokeLinecap="round" strokeLinejoin="round" d="M4 20h4l11-11a2.6 2.6 0 10-4-4L4 16v4z" /></svg>
    case "plus":
      return <svg {...common}><path strokeLinecap="round" strokeLinejoin="round" d="M12 5v14M5 12h14" /></svg>
    case "search":
      return <svg {...common}><path strokeLinecap="round" strokeLinejoin="round" d="M11 18a7 7 0 100-14 7 7 0 000 14zM16 16l4 4" /></svg>
    case "spark":
      return <svg {...common}><path strokeLinecap="round" strokeLinejoin="round" d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8L12 3zM18 16l.8 2.2L21 19l-2.2.8L18 22l-.8-2.2L15 19l2.2-.8L18 16z" /></svg>
    case "sun":
      return <svg {...common}><path strokeLinecap="round" strokeLinejoin="round" d="M12 4V2M12 22v-2M4 12H2M22 12h-2M5 5l-1.4-1.4M20.4 20.4L19 19M19 5l1.4-1.4M3.6 20.4L5 19M12 16a4 4 0 100-8 4 4 0 000 8z" /></svg>
    case "timeline":
      return <svg {...common}><path strokeLinecap="round" strokeLinejoin="round" d="M7 4v16M17 4v16M7 8h10M7 16h10M10 12h4" /></svg>
    case "users":
      return <svg {...common}><path strokeLinecap="round" strokeLinejoin="round" d="M9 11a3 3 0 100-6 3 3 0 000 6zM4 19a5 5 0 0110 0M17 11a2.5 2.5 0 100-5M15.5 15.5A4.5 4.5 0 0120 20" /></svg>
    case "voice":
      return <svg {...common}><path strokeLinecap="round" strokeLinejoin="round" d="M4 13v-2M8 16V8M12 19V5M16 16V8M20 13v-2" /></svg>
    default:
      return null
  }
}
