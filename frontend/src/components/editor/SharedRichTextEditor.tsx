"use client"

import { useEffect, useMemo, useRef, useState, type CSSProperties } from "react"
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

import type { Character } from "@/types/character"

type EditorLookup = Map<string, ReturnType<typeof useEditor>>

const editorRegistry: EditorLookup = new Map()

const FONT_OPTIONS = [
  { value: "Times New Roman", label: "Times" },
  { value: "Georgia", label: "Georgia" },
  { value: "Space Grotesk", label: "Space Grotesk" },
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

function colorValue(value: string) {
  return value.trim() || "#0f172a"
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
    ? `border-b px-3 py-2 ${isDark ? "border-white/10 bg-[#0f131a]/85 backdrop-blur" : "border-stone-200 bg-[#f6f1e8]/90 backdrop-blur"}`
    : ""
  const groupClass = "flex flex-wrap items-center gap-1.5"
  const buttonClass = `rounded-md px-2.5 py-2 text-[11px] font-medium transition ${isDark ? "text-slate-200 hover:bg-white/8" : "text-stone-700 hover:bg-white"}`
  const selectClass = `rounded-md border px-2 py-2 text-[11px] ${isDark ? "border-white/10 bg-black text-slate-200" : "border-stone-200 bg-white text-stone-700"}`
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
        <select className={selectClass} defaultValue="Times New Roman" onChange={(event) => run((instance) => instance.chain().focus().setFontFamily(event.target.value).run())}>
          {FONT_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
        </select>
        <select className={selectClass} defaultValue="12" onChange={(event) => run((instance) => instance.chain().focus().setFontSize(`${event.target.value}px`).run())}>
          {FONT_SIZE_OPTIONS.map((size) => <option key={size} value={size}>{size} pt</option>)}
        </select>
        <button type="button" title="Heading 2" onClick={() => run((instance) => instance.chain().focus().toggleHeading({ level: 2 }).run())} className={buttonClass}>H2</button>
        <button type="button" title="Heading 3" onClick={() => run((instance) => instance.chain().focus().toggleHeading({ level: 3 }).run())} className={buttonClass}>H3</button>
        <button type="button" title="Bold" onClick={() => run((instance) => instance.chain().focus().toggleBold().run())} className={buttonClass}>B</button>
        <button type="button" title="Italic" onClick={() => run((instance) => instance.chain().focus().toggleItalic().run())} className={`${buttonClass} italic`}>I</button>
        <button type="button" title="Underline" onClick={() => run((instance) => instance.chain().focus().toggleUnderline().run())} className={buttonClass}>U</button>
        <button type="button" title="Strikethrough" onClick={() => run((instance) => instance.chain().focus().toggleStrike().run())} className={`${buttonClass} line-through`}>S</button>
        <button type="button" title="Clear formatting" onClick={() => run((instance) => instance.chain().focus().unsetAllMarks().clearNodes().run())} className={buttonClass}>Clear</button>
        <span className={dividerClass} />
        <select className={selectClass} defaultValue={COLOR_OPTIONS[0]} onChange={(event) => run((instance) => instance.chain().focus().setColor(colorValue(event.target.value)).run())}>
          {COLOR_OPTIONS.map((color) => <option key={color} value={color}>{color}</option>)}
        </select>
        <select className={selectClass} defaultValue={HIGHLIGHT_OPTIONS[0]} onChange={(event) => run((instance) => instance.chain().focus().toggleHighlight({ color: colorValue(event.target.value) }).run())}>
          {HIGHLIGHT_OPTIONS.map((color) => <option key={color} value={color}>{color}</option>)}
        </select>
        <span className={dividerClass} />
        <button type="button" title="Bulleted list" onClick={() => run((instance) => instance.chain().focus().toggleBulletList().run())} className={buttonClass}>List</button>
        <button type="button" title="Numbered list" onClick={() => run((instance) => instance.chain().focus().toggleOrderedList().run())} className={buttonClass}>1.</button>
        <button type="button" title="Checklist" onClick={() => run((instance) => instance.chain().focus().toggleTaskList().run())} className={buttonClass}>[ ]</button>
        <button type="button" title="Quote" onClick={() => run((instance) => instance.chain().focus().toggleBlockquote().run())} className={buttonClass}>Quote</button>
        <button type="button" title="Divider" onClick={() => run((instance) => instance.chain().focus().setHorizontalRule().run())} className={buttonClass}>Rule</button>
        <button type="button" title="Scene break" onClick={() => run((instance) => instance.chain().focus().insertContent({ type: "sceneBreak" }).run())} className={buttonClass}>***</button>
        <button type="button" title="Page break" onClick={() => run((instance) => instance.chain().focus().insertContent({ type: "pageBreak" }).run())} className={buttonClass}>Page</button>
      </div>
      <div className={groupClass}>
        <select className={selectClass} defaultValue="1.8" onChange={(event) => run((instance) => (instance.chain() as any).focus().setLineHeight(event.target.value).run())}>
          {LINE_HEIGHT_OPTIONS.map((value) => <option key={value} value={value}>{value} lh</option>)}
        </select>
        <select className={selectClass} defaultValue="0.8rem" onChange={(event) => run((instance) => (instance.chain() as any).focus().setParagraphSpacing(event.target.value).run())}>
          {PARAGRAPH_SPACING_OPTIONS.map((value) => <option key={value} value={value}>{value} gap</option>)}
        </select>
        <button type="button" title="First-line indent" onClick={() => run((instance) => (instance.chain() as any).focus().setFirstLineIndent("1.5em").run())} className={buttonClass}>Indent</button>
        <button type="button" title="Align left" onClick={() => run((instance) => instance.chain().focus().setTextAlign("left").run())} className={buttonClass}>Left</button>
        <button type="button" title="Align center" onClick={() => run((instance) => instance.chain().focus().setTextAlign("center").run())} className={buttonClass}>Center</button>
        <button type="button" title="Align right" onClick={() => run((instance) => instance.chain().focus().setTextAlign("right").run())} className={buttonClass}>Right</button>
        <button type="button" title="Justify" onClick={() => run((instance) => instance.chain().focus().setTextAlign("justify").run())} className={buttonClass}>Justify</button>
        <span className={dividerClass} />
        <button type="button" title="Insert link" onClick={() => {
          const href = window.prompt("Enter a URL")
          if (!href) return
          run((instance) => instance.chain().focus().extendMarkRange("link").setLink({ href }).run())
        }} className={buttonClass}>Link</button>
        <button type="button" title="Insert image" onClick={() => fileInputRef.current?.click()} className={buttonClass}>Image</button>
        <div className="relative">
          <button type="button" title="Mention character" onClick={() => setShowMentionPicker((current) => !current)} className={buttonClass}>@</button>
          {showMentionPicker && mentionableCharacters.length > 0 ? (
            <div className={`absolute left-0 top-full z-20 mt-2 w-52 rounded-xl border p-1 shadow-[0_18px_50px_-24px_rgba(15,23,42,0.4)] ${isDark ? "border-white/10 bg-[#0f172a]" : "border-stone-200 bg-white"}`}>
              {mentionableCharacters.map((character) => (
                <button
                  key={character.id}
                  type="button"
                  onClick={() => {
                    run((instance) => instance.chain().focus().insertContent({ type: "mentionToken", attrs: { mention: character.name, label: character.name } }).insertContent(" ").run())
                    setShowMentionPicker(false)
                  }}
                  className={`block w-full rounded-lg px-3 py-2 text-left text-sm transition ${isDark ? "text-slate-200 hover:bg-white/8" : "text-stone-700 hover:bg-stone-100"}`}
                >
                  @{character.name}
                </button>
              ))}
            </div>
          ) : null}
        </div>
        {onAddComment ? <button type="button" title="Add comment" onClick={onAddComment} className={buttonClass}>Comment</button> : null}
        {onOpenNotes ? <button type="button" title="Open notes" onClick={onOpenNotes} className={buttonClass}>Notes</button> : null}
        <span className={dividerClass} />
        <button type="button" title="Undo" onClick={() => run((instance) => instance.chain().focus().undo().run())} className={buttonClass}>Undo</button>
        <button type="button" title="Redo" onClick={() => run((instance) => instance.chain().focus().redo().run())} className={buttonClass}>Redo</button>
      </div>
    </div>
  )
}

export function RichTextEditor({
  html,
  onChange,
  placeholder,
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
  placeholder?: string
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
        "data-placeholder": placeholder || "",
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
