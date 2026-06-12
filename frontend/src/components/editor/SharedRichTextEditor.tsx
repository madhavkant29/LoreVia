"use client"

import { useEffect, useMemo, useRef, useState, type CSSProperties, type ReactNode } from "react"
import { EditorContent, useEditor } from "@tiptap/react"
import { Extension, Mark, Node, mergeAttributes } from "@tiptap/core"
import StarterKit from "@tiptap/starter-kit"
import Underline from "@tiptap/extension-underline"
import TextAlign from "@tiptap/extension-text-align"
import Link from "@tiptap/extension-link"
import Image from "@tiptap/extension-image"
import Highlight from "@tiptap/extension-highlight"
import { TextStyle } from "@tiptap/extension-text-style"
import Color from "@tiptap/extension-color"
import TaskList from "@tiptap/extension-task-list"
import TaskItem from "@tiptap/extension-task-item"

import { Tooltip } from "@/components/ui/Tooltip"
import type { Character } from "@/types/character"

type EditorLookup = Map<string, ReturnType<typeof useEditor>>
type ActiveEditor = NonNullable<ReturnType<typeof useEditor>>
type RichTextCommandChain = ReturnType<ActiveEditor["chain"]> & {
  setLineHeight: (lineHeight: string | null) => RichTextCommandChain
  setParagraphSpacing: (marginBottom: string | null) => RichTextCommandChain
  setFirstLineIndent: (textIndent: string | null) => RichTextCommandChain
}

const editorRegistry: EditorLookup = new Map()

const FONT_OPTIONS = [
  { value: "Times New Roman", label: "Times" },
  { value: "Georgia", label: "Georgia" },
  { value: "Space Grotesk", label: "Space Grotesk" },
  {
    value: '"Iowan Old Style", "Palatino Linotype", "Book Antiqua", Palatino, Georgia, serif',
    label: "Old Style",
  },
  { value: '"EB Garamond", Garamond, "Times New Roman", Georgia, serif', label: "EB Garamond" },
]

const FONT_SIZE_OPTIONS = ["11", "12", "14", "16", "18"]
const LINE_HEIGHT_OPTIONS = ["1.5", "1.8", "2"]
const PARAGRAPH_SPACING_OPTIONS = ["0", "0.4rem", "0.8rem"]
const COLOR_OPTIONS = ["#0f172a", "#1d4ed8", "#0f766e", "#b45309", "#be123c"]
const HIGHLIGHT_OPTIONS = ["#fef08a", "#bfdbfe", "#bbf7d0", "#fecaca", "#fed7aa"]

const MentionToken = Node.create({
  name: "mentionToken",
  group: "inline",
  inline: true,
  atom: true,
  selectable: true,
  addAttributes() {
    return {
      mention: { default: "" },
      label: { default: "" },
    }
  },
  parseHTML() {
    return [{ tag: "span[data-mention]" }]
  },
  renderHTML({ HTMLAttributes }) {
    const label = String(HTMLAttributes.label || HTMLAttributes.mention || "")
    return ["span", mergeAttributes(HTMLAttributes, { class: "mention-token" }), label.startsWith("@") ? label : `@${label}`]
  },
})

const SceneBreak = Node.create({
  name: "sceneBreak",
  group: "block",
  atom: true,
  selectable: true,
  parseHTML() {
    return [{ tag: "div[data-scene-break]" }]
  },
  renderHTML() {
    return ["div", { "data-scene-break": "true", class: "scene-break-node" }, "***"]
  },
})

const PageBreak = Node.create({
  name: "pageBreak",
  group: "block",
  atom: true,
  selectable: true,
  parseHTML() {
    return [{ tag: "div[data-page-break]" }]
  },
  renderHTML() {
    return ["div", { "data-page-break": "true", class: "page-break-node" }, "Page break"]
  },
})

const FontFamily = Extension.create({
  name: "fontFamily",
  addGlobalAttributes() {
    return [{
      types: ["textStyle"],
      attributes: {
        fontFamily: {
          default: null,
          parseHTML: (element) => element.style.fontFamily || null,
          renderHTML: (attributes) => {
            if (!attributes.fontFamily) return {}
            return { style: `font-family:${attributes.fontFamily}` }
          },
        },
      },
    }]
  },
  addCommands() {
    return {
      setFontFamily: (fontFamily: string) => ({ chain }: { chain: any }) => chain().setMark("textStyle", { fontFamily }).run(),
      unsetFontFamily: () => ({ chain }: { chain: any }) => chain().setMark("textStyle", { fontFamily: null }).removeEmptyTextStyle().run(),
    }
  },
})

const FontSize = Extension.create({
  name: "fontSize",
  addGlobalAttributes() {
    return [{
      types: ["textStyle"],
      attributes: {
        fontSize: {
          default: null,
          parseHTML: (element) => element.style.fontSize || null,
          renderHTML: (attributes) => {
            if (!attributes.fontSize) return {}
            return { style: `font-size:${attributes.fontSize}` }
          },
        },
      },
    }]
  },
  addCommands() {
    return {
      setFontSize: (fontSize: string) => ({ chain }: { chain: any }) => chain().setMark("textStyle", { fontSize }).run(),
      unsetFontSize: () => ({ chain }: { chain: any }) => chain().setMark("textStyle", { fontSize: null }).removeEmptyTextStyle().run(),
    }
  },
})

const ParagraphStyle = Extension.create({
  name: "paragraphStyle",
  addGlobalAttributes() {
    return [{
      types: ["paragraph", "heading", "blockquote"],
      attributes: {
        lineHeight: {
          default: null,
          parseHTML: (element) => element.style.lineHeight || null,
          renderHTML: (attributes) => attributes.lineHeight ? { style: `line-height:${attributes.lineHeight}` } : {},
        },
        marginBottom: {
          default: null,
          parseHTML: (element) => element.style.marginBottom || null,
          renderHTML: (attributes) => attributes.marginBottom ? { style: `margin-bottom:${attributes.marginBottom}` } : {},
        },
        textIndent: {
          default: null,
          parseHTML: (element) => element.style.textIndent || null,
          renderHTML: (attributes) => attributes.textIndent ? { style: `text-indent:${attributes.textIndent}` } : {},
        },
      },
    }]
  },
  addCommands() {
    return {
      setLineHeight: (lineHeight: string | null) => ({ chain }: { chain: any }) => chain().updateAttributes("paragraph", { lineHeight }).updateAttributes("heading", { lineHeight }).updateAttributes("blockquote", { lineHeight }).run(),
      setParagraphSpacing: (marginBottom: string | null) => ({ chain }: { chain: any }) => chain().updateAttributes("paragraph", { marginBottom }).updateAttributes("heading", { marginBottom }).updateAttributes("blockquote", { marginBottom }).run(),
      setFirstLineIndent: (textIndent: string | null) => ({ chain }: { chain: any }) => chain().updateAttributes("paragraph", { textIndent }).run(),
    }
  },
})

const RemoveEmptyTextStyle = Extension.create({
  name: "removeEmptyTextStyle",
  addCommands() {
    return {
      removeEmptyTextStyle: () => ({ state, dispatch }) => {
        const { tr, doc } = state
        doc.descendants((node, pos) => {
          if (!node.isText) return
          const textStyle = node.marks.find((mark) => mark.type.name === "textStyle")
          if (!textStyle) return
          const attrs = textStyle.attrs ?? {}
          if (Object.values(attrs).some(Boolean)) return
          tr.removeMark(pos, pos + node.nodeSize, textStyle.type)
        })
        if (tr.docChanged && dispatch) dispatch(tr)
        return true
      },
    }
  },
})

function currentEditor(editorKey?: string | null) {
  if (!editorKey) return null
  return editorRegistry.get(editorKey) ?? null
}

function focusedRichTextChain(editor: ActiveEditor): RichTextCommandChain {
  return editor.chain().focus() as RichTextCommandChain
}

function colorValue(value: string) {
  return value.trim() || "#0f172a"
}

function ToolbarButton({
  title,
  className,
  onClick,
  children,
}: {
  title: string
  className: string
  onClick: () => void
  children: ReactNode
}) {
  return (
    <Tooltip content={title}>
      <button type="button" aria-label={title} title={title} onClick={onClick} className={className}>
        {children}
      </button>
    </Tooltip>
  )
}

function ToolbarButtonInDropdown({
  title,
  className,
  onClick,
  children,
}: {
  title: string
  className: string
  onClick: () => void
  children: ReactNode
}) {
  return (
    <Tooltip content={title} side="bottom">
      <button type="button" aria-label={title} title={title} onClick={onClick} className={className}>
        {children}
      </button>
    </Tooltip>
  )
}

export function EditorToolbar({
  isDark,
  compact = false,
  characters = [],
  editorKey,
  onAddComment,
  onOpenNotes,
}: {
  isDark: boolean
  compact?: boolean
  characters?: Character[]
  editorKey?: string
  onAddComment?: () => void
  onOpenNotes?: () => void
}) {
  const [showMentionPicker, setShowMentionPicker] = useState(false)
  const fileInputRef = useRef<HTMLInputElement | null>(null)
  const editor = currentEditor(editorKey)

  const shellClass = compact
    ? `rounded-sm border px-2 py-2 ${isDark ? "border-white/10 bg-[#0b1014]" : "border-stone-200 bg-white"}`
    : ""
  const groupClass = "flex flex-wrap items-center gap-1"
  const buttonClass = `rounded-sm px-2.5 py-2 text-3xs font-semibold transition focus:outline-none focus:ring-2 focus:ring-teal-300/40 ${isDark ? "text-slate-200 hover:bg-white/[0.07]" : "text-stone-700 hover:bg-stone-100"}`
  const selectClass = `rounded-sm border px-2 py-2 text-3xs focus:outline-none focus:ring-2 focus:ring-teal-300/40 ${isDark ? "border-white/10 bg-[#0f1418] text-slate-200" : "border-stone-200 bg-white text-stone-700"}`
  const dividerClass = isDark ? "h-5 w-px bg-white/10" : "h-5 w-px bg-stone-200"
  const mentionableCharacters = characters.slice(0, 8)

  const run = (fn: (instance: NonNullable<typeof editor>) => void) => {
    if (!editor) return
    fn(editor)
  }

  return (
    <div className={`flex flex-wrap items-center justify-between gap-3 ${shellClass}`}>
      <input
        ref={fileInputRef}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={(event) => {
          const file = event.target.files?.[0]
          if (!file) return
          const reader = new FileReader()
          reader.onload = () => {
            const result = typeof reader.result === "string" ? reader.result : ""
            if (!result) return
            run((instance) => instance.chain().focus().setImage({ src: result, alt: file.name || "Embedded image" }).run())
            event.target.value = ""
          }
          reader.readAsDataURL(file)
        }}
      />
      <div className={groupClass}>
        <select aria-label="Font family" className={selectClass} defaultValue="Times New Roman" onChange={(event) => run((instance) => instance.chain().focus().setFontFamily(event.target.value).run())}>
          {FONT_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
        </select>
        <select aria-label="Font size" className={selectClass} defaultValue="12" onChange={(event) => run((instance) => instance.chain().focus().setFontSize(`${event.target.value}px`).run())}>
          {FONT_SIZE_OPTIONS.map((size) => <option key={size} value={size}>{size} pt</option>)}
        </select>
        <ToolbarButton title="Heading 2" onClick={() => run((instance) => instance.chain().focus().toggleHeading({ level: 2 }).run())} className={buttonClass}>H2</ToolbarButton>
        <ToolbarButton title="Heading 3" onClick={() => run((instance) => instance.chain().focus().toggleHeading({ level: 3 }).run())} className={buttonClass}>H3</ToolbarButton>
        <ToolbarButton title="Bold" onClick={() => run((instance) => instance.chain().focus().toggleBold().run())} className={buttonClass}>B</ToolbarButton>
        <ToolbarButton title="Italic" onClick={() => run((instance) => instance.chain().focus().toggleItalic().run())} className={`${buttonClass} italic`}>I</ToolbarButton>
        <ToolbarButton title="Underline" onClick={() => run((instance) => instance.chain().focus().toggleUnderline().run())} className={buttonClass}>U</ToolbarButton>
        <ToolbarButton title="Strikethrough" onClick={() => run((instance) => instance.chain().focus().toggleStrike().run())} className={`${buttonClass} line-through`}>S</ToolbarButton>
        <span className={dividerClass} />
        <ToolbarButton title="Bulleted list" onClick={() => run((instance) => instance.chain().focus().toggleBulletList().run())} className={buttonClass}>•</ToolbarButton>
        <ToolbarButton title="Numbered list" onClick={() => run((instance) => instance.chain().focus().toggleOrderedList().run())} className={buttonClass}>1.</ToolbarButton>
        <ToolbarButton title="Align left" onClick={() => run((instance) => instance.chain().focus().setTextAlign("left").run())} className={buttonClass}>≡</ToolbarButton>
        <ToolbarButton title="Align center" onClick={() => run((instance) => instance.chain().focus().setTextAlign("center").run())} className={buttonClass}>≣</ToolbarButton>
        <ToolbarButton title="Align right" onClick={() => run((instance) => instance.chain().focus().setTextAlign("right").run())} className={buttonClass}>≡</ToolbarButton>
        <span className={dividerClass} />
        <ToolbarButton title="Insert link" onClick={() => {
          const href = window.prompt("Enter a URL")
          if (!href) return
          run((instance) => instance.chain().focus().extendMarkRange("link").setLink({ href }).run())
        }} className={buttonClass}>↗</ToolbarButton>
        <ToolbarButton title="Insert image" onClick={() => fileInputRef.current?.click()} className={buttonClass}>▧</ToolbarButton>
        <div className="relative">
          <ToolbarButton title="Mention character" onClick={() => setShowMentionPicker((current) => !current)} className={buttonClass}>@</ToolbarButton>
          {showMentionPicker && mentionableCharacters.length > 0 ? (
            <div className={`absolute left-0 top-full z-20 mt-2 w-52 rounded-md border p-1 ${isDark ? "border-white/10 bg-[#0f172a]" : "border-stone-200 bg-white"}`}>
              {mentionableCharacters.map((character) => (
                <button
                  key={character.id}
                  type="button"
                  onClick={() => {
                    run((instance) => instance.chain().focus().insertContent({ type: "mentionToken", attrs: { mention: character.name, label: character.name } }).insertContent(" ").run())
                    setShowMentionPicker(false)
                  }}
                  className={`block w-full rounded-sm px-3 py-2 text-left text-sm transition ${isDark ? "text-slate-200 hover:bg-white/[0.08]" : "text-stone-700 hover:bg-stone-100"}`}
                >
                  @{character.name}
                </button>
              ))}
            </div>
          ) : null}
        </div>
        {onAddComment ? <ToolbarButton title="Add comment" onClick={onAddComment} className={buttonClass}>Comment</ToolbarButton> : null}
        {onOpenNotes ? <ToolbarButton title="Open notes" onClick={onOpenNotes} className={buttonClass}>Notes</ToolbarButton> : null}
        <span className={dividerClass} />
        <ToolbarButton title="Undo" onClick={() => run((instance) => instance.chain().focus().undo().run())} className={buttonClass}>Undo</ToolbarButton>
        <ToolbarButton title="Redo" onClick={() => run((instance) => instance.chain().focus().redo().run())} className={buttonClass}>Redo</ToolbarButton>
        <details className="relative">
          <summary aria-label="More formatting controls" className={`${buttonClass} list-none cursor-pointer`}>More</summary>
          <div className={`absolute right-0 top-full z-30 mt-2 grid w-64 gap-2 rounded-md border p-3 ${isDark ? "border-white/10 bg-[#0d1117]" : "border-stone-200 bg-white"}`}>
            <div className="grid grid-cols-2 gap-2">
              <Tooltip content="Text color">
                <select aria-label="Text color" title="Text color" className={selectClass} defaultValue={COLOR_OPTIONS[0]} onChange={(event) => run((instance) => instance.chain().focus().setColor(colorValue(event.target.value)).run())}>
                  {COLOR_OPTIONS.map((color) => <option key={color} value={color}>{color}</option>)}
                </select>
              </Tooltip>
              <Tooltip content="Highlight color">
                <select aria-label="Highlight color" title="Highlight color" className={selectClass} defaultValue={HIGHLIGHT_OPTIONS[0]} onChange={(event) => run((instance) => instance.chain().focus().toggleHighlight({ color: colorValue(event.target.value) }).run())}>
                  {HIGHLIGHT_OPTIONS.map((color) => <option key={color} value={color}>{color}</option>)}
                </select>
              </Tooltip>
              <Tooltip content="Line height">
                <select aria-label="Line height" title="Line height" className={selectClass} defaultValue="1.8" onChange={(event) => run((instance) => focusedRichTextChain(instance).setLineHeight(event.target.value).run())}>
                  {LINE_HEIGHT_OPTIONS.map((value) => <option key={value} value={value}>{value} lh</option>)}
                </select>
              </Tooltip>
              <Tooltip content="Paragraph spacing">
                <select aria-label="Paragraph spacing" title="Paragraph spacing" className={selectClass} defaultValue="0.8rem" onChange={(event) => run((instance) => focusedRichTextChain(instance).setParagraphSpacing(event.target.value).run())}>
                  {PARAGRAPH_SPACING_OPTIONS.map((value) => <option key={value} value={value}>{value} gap</option>)}
                </select>
              </Tooltip>
            </div>
            <div className="flex flex-wrap gap-1">
              <ToolbarButtonInDropdown title="Clear formatting" onClick={() => run((instance) => instance.chain().focus().unsetAllMarks().clearNodes().run())} className={buttonClass}>Clear</ToolbarButtonInDropdown>
              <ToolbarButtonInDropdown title="Checklist" onClick={() => run((instance) => instance.chain().focus().toggleTaskList().run())} className={buttonClass}>[ ]</ToolbarButtonInDropdown>
              <ToolbarButtonInDropdown title="Quote" onClick={() => run((instance) => instance.chain().focus().toggleBlockquote().run())} className={buttonClass}>Quote</ToolbarButtonInDropdown>
              <ToolbarButtonInDropdown title="Justify" onClick={() => run((instance) => instance.chain().focus().setTextAlign("justify").run())} className={buttonClass}>Justify</ToolbarButtonInDropdown>
              <ToolbarButtonInDropdown title="Divider" onClick={() => run((instance) => instance.chain().focus().setHorizontalRule().run())} className={buttonClass}>Rule</ToolbarButtonInDropdown>
              <ToolbarButtonInDropdown title="Scene break" onClick={() => run((instance) => instance.chain().focus().insertContent({ type: "sceneBreak" }).run())} className={buttonClass}>***</ToolbarButtonInDropdown>
              <ToolbarButtonInDropdown title="Page break" onClick={() => run((instance) => instance.chain().focus().insertContent({ type: "pageBreak" }).run())} className={buttonClass}>Page</ToolbarButtonInDropdown>
              <ToolbarButtonInDropdown title="First-line indent" onClick={() => run((instance) => focusedRichTextChain(instance).setFirstLineIndent("1.5em").run())} className={buttonClass}>Indent</ToolbarButtonInDropdown>
            </div>
          </div>
        </details>
      </div>
    </div>
  )
}

export function RichTextEditor({
  html,
  onChange,
  className,
  style,
  contentClassName,
  editorKey,
  onFocus,
  onBlur,
  onCharacterClick,
  onShortcutSave,
  onShortcutComment,
  onShortcutNotes,
}: {
  html: string
  onChange: (html: string, text: string) => void
  className?: string
  style?: CSSProperties
  contentClassName?: string
  editorKey?: string
  onFocus?: () => void
  onBlur?: () => void
  onCharacterClick?: (characterName: string) => void
  onShortcutSave?: () => void
  onShortcutComment?: () => void
  onShortcutNotes?: () => void
}) {
  const wrapperClassName = useMemo(
    () => `${className ?? ""} ${contentClassName ?? ""} manuscript-editor`,
    [className, contentClassName]
  )
  const latestHtmlRef = useRef(html)

  const editor = useEditor({
    immediatelyRender: false,
    extensions: [
      StarterKit.configure({
        heading: { levels: [2, 3] },
      }),
      Underline,
      TextStyle,
      Color,
      Highlight.configure({ multicolor: true }),
      TextAlign.configure({ types: ["heading", "paragraph", "blockquote"] }),
      Link.configure({ openOnClick: false, autolink: true, defaultProtocol: "https" }),
      Image,
      TaskList,
      TaskItem.configure({ nested: true }),
      MentionToken,
      SceneBreak,
      PageBreak,
      FontFamily,
      FontSize,
      ParagraphStyle,
      RemoveEmptyTextStyle,
    ],
    content: html || "<p></p>",
    editorProps: {
      attributes: {
        class: wrapperClassName,
        "data-editor-key": editorKey || "",
      },
      handleClick(_view, _pos, event) {
        const target = event.target as HTMLElement | null
        const mention = target?.closest("[data-mention]")?.getAttribute("data-mention")
        if (mention && onCharacterClick) {
          onCharacterClick(mention)
          return true
        }
        return false
      },
      handleDOMEvents: {
        focus: () => {
          onFocus?.()
          return false
        },
        blur: () => {
          onBlur?.()
          return false
        },
      },
      handleKeyDown(_view, event) {
        const usesModifier = event.ctrlKey || event.metaKey
        if (!usesModifier) return false
        const key = event.key.toLowerCase()
        if (key === "s") {
          event.preventDefault()
          onShortcutSave?.()
          return true
        }
        if (event.shiftKey && key === "m") {
          event.preventDefault()
          onShortcutComment?.()
          return true
        }
        if (event.shiftKey && key === "n") {
          event.preventDefault()
          onShortcutNotes?.()
          return true
        }
        if (event.shiftKey && key === "8") {
          event.preventDefault()
          editor?.chain().focus().insertContent({ type: "sceneBreak" }).run()
          return true
        }
        if (event.altKey && key === "1") {
          event.preventDefault()
          editor?.chain().focus().toggleHeading({ level: 2 }).run()
          return true
        }
        if (event.altKey && key === "2") {
          event.preventDefault()
          editor?.chain().focus().toggleHeading({ level: 3 }).run()
          return true
        }
        return false
      },
    },
    onUpdate({ editor: instance }) {
      const nextHtml = instance.getHTML()
      latestHtmlRef.current = nextHtml
      onChange(nextHtml, instance.getText())
    },
  })

  useEffect(() => {
    if (!editor || !editorKey) return
    editorRegistry.set(editorKey, editor)
    return () => {
      editorRegistry.delete(editorKey)
    }
  }, [editor, editorKey])

  useEffect(() => {
    if (!editor) return
    if (html === latestHtmlRef.current) return
    latestHtmlRef.current = html
    editor.commands.setContent(html || "<p></p>")
  }, [editor, html])

  return (
    <div style={style}>
      <EditorContent editor={editor} />
    </div>
  )
}
