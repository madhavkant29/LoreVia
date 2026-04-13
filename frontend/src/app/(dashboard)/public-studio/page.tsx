"use client"

import { useState } from "react"
import { booksApi } from "@/lib/api/books"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import { GENRE_TAGS } from "@/lib/constants/genreTags"

const MAX_TAGS = 8

type DraftChapter = {
  title: string
  description: string
  text: string
}

export default function PublicStudioPage() {
  const { theme } = usePreferencesStore()
  const isDark = theme === "dark"
  const [title, setTitle] = useState("")
  const [author, setAuthor] = useState("")
  const [selectedTags, setSelectedTags] = useState<string[]>([])
  const [customTag, setCustomTag] = useState("")
  const [description, setDescription] = useState("")
  const [chapters, setChapters] = useState<DraftChapter[]>([{ title: "Chapter 1", description: "", text: "" }])
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const genre = selectedTags.join(", ")
  const suggestedTags = GENRE_TAGS.filter((tag) => !selectedTags.includes(tag)).slice(0, 20)

  const updateChapter = (index: number, patch: Partial<DraftChapter>) => {
    setChapters((current) => current.map((chapter, i) => (i === index ? { ...chapter, ...patch } : chapter)))
  }

  const addChapter = () => {
    setChapters((current) => [
      ...current,
      { title: `Chapter ${current.length + 1}`, description: "", text: "" },
    ])
  }

  const removeChapter = (index: number) => {
    setChapters((current) => current.filter((_, i) => i !== index))
  }

  const addTag = (rawTag: string) => {
    const tag = normalizeTag(rawTag)
    if (!tag) return
    setSelectedTags((current) => {
      if (current.includes(tag) || current.length >= MAX_TAGS) return current
      return [...current, tag]
    })
  }

  const removeTag = (tag: string) => {
    setSelectedTags((current) => current.filter((item) => item !== tag))
  }

  const addCustomTag = () => {
    addTag(customTag)
    setCustomTag("")
  }

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    setMessage(null)
    try {
      const payload = {
        title,
        author: author || undefined,
        genre: genre || undefined,
        description: description || undefined,
        chapters: chapters
          .filter((chapter) => chapter.text.trim())
          .map((chapter) => ({
            title: chapter.title,
            description: chapter.description || undefined,
            text: chapter.text,
          })),
      }
      const result = await booksApi.createPublicManual(payload)
      setMessage(`Public book created. Book id: ${result.book_id}`)
    } catch {
      setMessage("Could not create public book right now.")
    } finally {
      setSaving(false)
    }
  }

  const inputClass = isDark
    ? "border-white/10 bg-white/5 text-slate-100 placeholder:text-slate-500"
    : "border-slate-300 bg-white text-slate-950 placeholder:text-slate-400"

  return (
    <div className="mx-auto max-w-5xl space-y-8 px-4 py-10">
      <section className={`rounded-[2rem] border p-6 ${isDark ? "border-white/10 bg-slate-950" : "border-slate-200 bg-white"}`}>
        <p className={`text-xs font-semibold uppercase tracking-[0.28em] ${isDark ? "text-slate-400" : "text-slate-500"}`}>Public studio</p>
        <h1 className={`mt-3 font-serif text-4xl ${isDark ? "text-white" : "text-slate-950"}`}>Publish a public reading sample</h1>
        <p className={`mt-3 max-w-3xl text-sm leading-6 ${isDark ? "text-slate-300" : "text-slate-600"}`}>
          Create a public book chapter by chapter with your own titles and descriptions, or use the regular upload flow for a full PDF/EPUB public release.
        </p>
      </section>

      <form onSubmit={submit} className="space-y-6">
        <section className={`grid gap-4 rounded-[1.75rem] border p-6 md:grid-cols-2 ${isDark ? "border-white/10 bg-slate-950" : "border-slate-200 bg-white"}`}>
          <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Book title" required className={`rounded-xl border px-4 py-3 text-sm ${inputClass}`} />
          <input value={author} onChange={(e) => setAuthor(e.target.value)} placeholder="Author" className={`rounded-xl border px-4 py-3 text-sm ${inputClass}`} />
          <div className={`rounded-[1.25rem] border p-4 md:col-span-2 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-slate-300 bg-slate-50"}`}>
            <div className="flex items-center justify-between gap-3">
              <p className={`text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-400" : "text-slate-500"}`}>Genres and tags</p>
              <span className={`text-xs ${isDark ? "text-slate-500" : "text-slate-400"}`}>{selectedTags.length}/{MAX_TAGS}</span>
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              {selectedTags.length > 0 ? selectedTags.map((tag) => (
                <button
                  key={tag}
                  type="button"
                  onClick={() => removeTag(tag)}
                  className={`rounded-full px-3 py-1.5 text-xs font-medium transition ${isDark ? "bg-indigo-400/15 text-indigo-100 hover:bg-indigo-400/25" : "bg-indigo-100 text-indigo-800 hover:bg-indigo-200"}`}
                >
                  {tag} ×
                </button>
              )) : (
                <p className={`text-sm ${isDark ? "text-slate-500" : "text-slate-400"}`}>Pick suggested tags or add custom ones.</p>
              )}
            </div>
            <div className="mt-4 flex gap-2">
              <input value={customTag} list="genre-tags" onChange={(e) => setCustomTag(e.target.value)} placeholder="Add custom genre or tone" className={`flex-1 rounded-xl border px-4 py-3 text-sm ${inputClass}`} />
              <button type="button" onClick={addCustomTag} className={`rounded-xl px-4 py-3 text-sm font-semibold ${isDark ? "bg-white/10 text-white hover:bg-white/15" : "bg-slate-900 text-white hover:bg-slate-800"}`}>
                Add
              </button>
            </div>
            <div className="mt-4 flex flex-wrap gap-2">
              {suggestedTags.map((tag) => (
                <button
                  key={tag}
                  type="button"
                  onClick={() => addTag(tag)}
                  className={`rounded-full border px-3 py-1.5 text-xs font-medium transition ${isDark ? "border-white/10 text-slate-300 hover:bg-white/5" : "border-slate-300 text-slate-700 hover:bg-white"}`}
                >
                  + {tag}
                </button>
              ))}
            </div>
          </div>
          <textarea value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Public description" rows={3} className={`rounded-xl border px-4 py-3 text-sm md:col-span-2 ${inputClass}`} />
          <datalist id="genre-tags">
            {GENRE_TAGS.map((tag) => (
              <option key={tag} value={tag} />
            ))}
          </datalist>
        </section>

        <section className="space-y-4">
          {chapters.map((chapter, index) => (
            <div key={index} className={`rounded-[1.5rem] border p-5 ${isDark ? "border-white/10 bg-slate-950" : "border-slate-200 bg-white"}`}>
              <div className="mb-4 flex items-center justify-between gap-3">
                <h2 className={`text-lg font-semibold ${isDark ? "text-white" : "text-slate-950"}`}>Chapter {index + 1}</h2>
                {chapters.length > 1 ? (
                  <button type="button" onClick={() => removeChapter(index)} className={`text-sm ${isDark ? "text-rose-300" : "text-rose-600"}`}>
                    Remove
                  </button>
                ) : null}
              </div>
              <div className="grid gap-4">
                <input value={chapter.title} onChange={(e) => updateChapter(index, { title: e.target.value })} placeholder="Chapter title" className={`rounded-xl border px-4 py-3 text-sm ${inputClass}`} />
                <textarea value={chapter.description} onChange={(e) => updateChapter(index, { description: e.target.value })} placeholder="Chapter description" rows={2} className={`rounded-xl border px-4 py-3 text-sm ${inputClass}`} />
                <textarea value={chapter.text} onChange={(e) => updateChapter(index, { text: e.target.value })} placeholder="Chapter text" rows={12} className={`rounded-xl border px-4 py-3 text-sm ${inputClass}`} />
              </div>
            </div>
          ))}
        </section>

        <div className="flex flex-wrap gap-3">
          <button type="button" onClick={addChapter} className={`rounded-full px-5 py-3 text-sm font-semibold ${isDark ? "border border-white/10 text-white hover:bg-white/10" : "border border-slate-300 text-slate-800 hover:bg-white"}`}>
            Add chapter
          </button>
          <button type="submit" disabled={saving} className={`rounded-full px-5 py-3 text-sm font-semibold ${isDark ? "bg-white text-slate-950 hover:bg-slate-200" : "bg-slate-950 text-white hover:bg-slate-800"} disabled:opacity-60`}>
            {saving ? "Publishing..." : "Publish public book"}
          </button>
        </div>

        {message ? <p className={`text-sm ${isDark ? "text-slate-300" : "text-slate-600"}`}>{message}</p> : null}
      </form>
    </div>
  )
}

function normalizeTag(rawTag: string): string {
  return rawTag
    .trim()
    .toLowerCase()
    .replace(/\s+/g, " ")
}
