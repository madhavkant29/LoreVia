const SAFE_TAGS = new Set([
  "p",
  "br",
  "strong",
  "b",
  "em",
  "i",
  "u",
  "s",
  "strike",
  "h1",
  "h2",
  "h3",
  "blockquote",
  "ul",
  "ol",
  "li",
  "div",
  "span",
  "a",
  "img",
])

const SAFE_ALIGNMENTS = new Set(["left", "center", "right", "justify"])

export function htmlToPlainText(html: string) {
  if (typeof window === "undefined") return html.replace(/<[^>]+>/g, " ")
  const container = document.createElement("div")
  container.innerHTML = html
  const blocks = Array.from(container.querySelectorAll("h1,h2,h3,p,blockquote,li,div"))
    .map((node) => node.textContent?.trim() ?? "")
    .filter(Boolean)
  return blocks.length ? blocks.join("\n\n") : (container.textContent ?? "").trim()
}

export function renderRichTextHtml(value: string, onCharacterClick?: (characterName: string) => void) {
  const normalized = /<[^>]+>/.test(value) ? value : plainTextToHtml(value)
  return sanitizeRichTextHtml(normalized, onCharacterClick)
}

export function sanitizeRichTextHtml(html: string, onCharacterClick?: (characterName: string) => void) {
  if (typeof window === "undefined") return html
  const container = document.createElement("div")
  container.innerHTML = html

  for (const node of Array.from(container.querySelectorAll("*"))) {
    const tag = node.tagName.toLowerCase()
    if (!SAFE_TAGS.has(tag)) {
      node.replaceWith(...Array.from(node.childNodes))
      continue
    }

    const element = node as HTMLElement
    const textAlign = element.style.textAlign
    const href = tag === "a" ? node.getAttribute("href") : null
    const src = tag === "img" ? node.getAttribute("src") : null
    const alt = tag === "img" ? node.getAttribute("alt") : null
    const mention = tag === "span" ? node.getAttribute("data-mention") : null
    const className = tag === "span" && element.classList.contains("mention-token") ? "mention-token" : null

    Array.from(node.attributes).forEach((attribute) => node.removeAttribute(attribute.name))

    if (textAlign && SAFE_ALIGNMENTS.has(textAlign)) {
      element.style.textAlign = textAlign
    }

    if (tag === "a" && href) {
      const safeHref = sanitizeHref(href)
      if (safeHref) {
        node.setAttribute("href", safeHref)
        node.setAttribute("target", "_blank")
        node.setAttribute("rel", "noreferrer noopener")
      } else {
        node.replaceWith(...Array.from(node.childNodes))
      }
    }

    if (tag === "img") {
      const safeSrc = sanitizeImageSrc(src)
      if (!safeSrc) {
        node.remove()
        continue
      }
      node.setAttribute("src", safeSrc)
      node.setAttribute("alt", alt?.slice(0, 160) || "Embedded image")
      node.setAttribute("loading", "lazy")
    }

    if (tag === "span" && mention && className) {
      node.setAttribute("data-mention", mention)
      node.setAttribute("class", className)
      if (onCharacterClick) {
        element.style.cursor = "pointer"
        element.onclick = () => onCharacterClick(mention)
      }
    }
  }

  const normalized = container.innerHTML.trim()
  return normalized || "<p></p>"
}

function plainTextToHtml(text: string) {
  const cleaned = text.trim()
  if (!cleaned) return "<p></p>"
  return cleaned
    .split(/\n{2,}/)
    .map((paragraph) => `<p>${escapeHtml(paragraph).replace(/\n/g, "<br>")}</p>`)
    .join("")
}

function sanitizeHref(value: string) {
  const trimmed = value.trim()
  if (/^(https?:|mailto:|tel:|\/|#)/i.test(trimmed)) return trimmed
  return null
}

function sanitizeImageSrc(value: string | null) {
  if (!value) return null
  const trimmed = value.trim()
  if (/^(https?:\/\/|data:image\/|\/)/i.test(trimmed)) return trimmed
  return null
}

function escapeHtml(value: string) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
}
