"use client"

import type { RefObject } from "react"

import type { Book, BookSeries } from "@/types/book"
import type { UploadWizardController } from "./useUploadWizardState"

type Props = {
  wizard: UploadWizardController
  isDark: boolean
  isManagingExisting: boolean
  canUploadAuthorMode: boolean
  needsUsername: boolean
  settingUsername: boolean
  usernameError: string | null
  onSetUsername: () => Promise<void>
  existingAuthorBooks: Book[]
  selectedExistingBook: Book | null
  existingBookSelectLabel: string
  existingBookMenuRef: RefObject<HTMLDivElement | null>
  suggestedTags: string[]
  series: BookSeries[]
  uploadLimitCopy: string | null
  username: string | null | undefined
  addTag: (tag: string) => void
  removeTag: (tag: string) => void
  toggleSeries: (seriesId: string) => void
}

export function UploadProjectDetailsStep({
  wizard,
  isDark,
  isManagingExisting,
  canUploadAuthorMode,
  needsUsername,
  settingUsername,
  usernameError,
  onSetUsername,
  existingAuthorBooks,
  selectedExistingBook,
  existingBookSelectLabel,
  existingBookMenuRef,
  suggestedTags,
  series,
  uploadLimitCopy,
  username,
  addTag,
  removeTag,
  toggleSeries,
}: Props) {
  const {
    title, setTitle, author, setAuthor, setAuthorManuallyEdited, mode, setMode,
    startEmpty, setStartEmpty, selectedTags, customTag, setCustomTag, selectedSeriesIds,
    existingBookId, setExistingBookId, existingBookMenuOpen, setExistingBookMenuOpen,
    hoveredExistingBookId, setHoveredExistingBookId, workType, setWorkType, setWorkTypeDirty,
    usernameInput, setUsernameInput, files, setFiles, coverFile, autoExtractCover,
    setChapterNumberDirty,
  } = wizard
  const effectiveWorkType = isManagingExisting ? (selectedExistingBook?.work_type ?? workType) : workType
  const primaryFileIsPdf = Boolean(files[0]?.name.toLowerCase().endsWith(".pdf"))
  const willUseBlankCoverFallback = !coverFile && (!primaryFileIsPdf || !autoExtractCover)
  const shouldShowTagSuggestions = customTag.trim().length >= 2
  const existingBookOptionStyle = (selected: boolean, hovered: boolean) => ({
    backgroundColor: selected ? "#2563eb" : hovered ? "#f3f4f6" : "#ffffff",
    color: selected ? "#ffffff" : "#000000",
  })

  return (
    <>
          {!isManagingExisting ? (
            <div className="mb-1">
              <p className={`text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-400" : "text-slate-500"}`}>Optional metadata</p>
            </div>
          ) : null}

          {!isManagingExisting ? (
            <div className="grid gap-4 xl:grid-cols-2">
              <label className="grid gap-2">
                <span className={`text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-400" : "text-slate-500"}`}>Title</span>
                <input
                  type="text"
                  value={title}
                  onChange={e => setTitle(e.target.value)}
                  onInput={e => setTitle((e.target as HTMLInputElement).value)}
                  required
                  aria-label="Title"
                  className={`rounded-xl border px-3 py-2.5 text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500 ${
                    isDark
                      ? "border-white/10 bg-white/5 text-slate-100"
                      : "border-gray-300 bg-white text-slate-950"
                  }`}
                />
              </label>
              <div className="space-y-2">
              <label className="grid gap-2">
                <span className={`text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-400" : "text-slate-500"}`}>
                  {mode === "author" ? "Manuscript author or pen name" : willUseBlankCoverFallback ? "Author for blank cover" : "Author"}
                </span>
                <input
                  type="text"
                  value={author}
                  onChange={(e) => {
                    setAuthor(e.target.value)
                    setAuthorManuallyEdited(true)
                  }}
                  onInput={(e) => {
                    setAuthor((e.target as HTMLInputElement).value)
                    setAuthorManuallyEdited(true)
                  }}
                  aria-label={mode === "author" ? "Manuscript author or pen name" : willUseBlankCoverFallback ? "Author for blank cover" : "Author"}
                  className={`w-full rounded-xl border px-3 py-2.5 text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500 ${
                    isDark
                      ? "border-white/10 bg-white/5 text-slate-100"
                      : "border-gray-300 bg-white text-slate-950"
                  }`}
                />
              </label>
              {willUseBlankCoverFallback ? (
                <p className={`text-xs ${isDark ? "text-slate-400" : "text-slate-500"}`}>
                  If LoreVia cannot find a cover, it will generate a blank cover page using the title and author.
                </p>
              ) : null}
              {mode === "author" ? (
                <p className={`text-xs ${isDark ? "text-slate-400" : "text-slate-500"}`}>
                  This name appears on this manuscript only. It defaults to your username, but you can change it here if this book should use a different pen name or byline.
                </p>
              ) : null}
            </div>
            </div>
          ) : null}

          <div className={`rounded-xl border p-4 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-gray-200 bg-gray-50"}`}>
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className={`text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-400" : "text-slate-500"}`}>Manuscript type</p>
                {isManagingExisting ? (
                  <p className={`mt-1 text-sm ${isDark ? "text-slate-400" : "text-slate-500"}`}>
                    {selectedExistingBook
                      ? `This workspace is set to ${selectedExistingBook.work_type}.`
                      : "Choose how LoreVia should interpret this manuscript."}
                  </p>
                ) : null}
              </div>
            </div>
            <div className="mt-3 grid gap-2 sm:grid-cols-2">
              {([
                { value: "novel", label: "Novel" },
                { value: "screenplay", label: "Screenplay" },
              ] as const).map((option) => {
                const active = effectiveWorkType === option.value
                return (
                  <button
                    key={option.value}
                    type="button"
                    onClick={() => {
                      if (isManagingExisting && selectedExistingBook) return
                      setWorkType(option.value)
                      setWorkTypeDirty(true)
                    }}
                    disabled={isManagingExisting && !!selectedExistingBook}
                    className={`rounded-xl border px-4 py-3 text-left transition disabled:cursor-not-allowed disabled:opacity-80 ${
                      active
                        ? isDark
                          ? "border-indigo-400/50 bg-indigo-400/15 text-slate-100"
                          : "border-indigo-300 bg-indigo-50 text-stone-900"
                        : isDark
                          ? "border-white/10 bg-black/20 text-slate-300 hover:bg-white/5"
                          : "border-stone-200 bg-white text-stone-700 hover:bg-stone-50"
                    }`}
                  >
                    <p className="text-sm font-semibold">{option.label}</p>
                  </button>
                )
              })}
            </div>
          </div>

          <div className={`rounded-xl border p-3 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-gray-200 bg-gray-50"}`}>
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className={`text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-400" : "text-slate-500"}`}>Workspace mode</p>
                <p className={`mt-1 text-sm ${isDark ? "text-slate-400" : "text-slate-500"}`}>
                  {mode === "reader"
                    ? "Spoiler-aware workspace aligned to reading progress."
                    : "Full analysis with exports and writing-focused tools."}
                </p>
              </div>
            </div>
            <div className={`mt-3 inline-flex w-full rounded-full p-1 ${isDark ? "border border-white/10 bg-white/5" : "border border-stone-200 bg-stone-100"}`}>
              {(["reader", "author"] as const).map((value) => {
                const active = mode === value
                const locked = value === "author" && !canUploadAuthorMode
                return (
                  <button
                    key={value}
                    type="button"
                    onClick={() => {
                      if (locked) return
                      setMode(value)
                    }}
                    disabled={locked}
                    className={`flex-1 rounded-full px-4 py-2 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-50 ${
                      active
                        ? isDark ? "bg-white text-slate-950" : "bg-white text-stone-950"
                        : isDark ? "text-slate-300 hover:bg-white/10" : "text-stone-600 hover:bg-white/70"
                    }`}
                  >
                    {value === "reader" ? "Reading mode" : locked ? "Author mode locked" : "Author mode"}
                  </button>
                )
              })}
            </div>
            {!canUploadAuthorMode ? (
              <p className={`mt-3 text-xs leading-5 ${isDark ? "text-amber-200" : "text-amber-700"}`}>
                Author uploads require Author or Architect access. Collaboration-only access stays read-only.
              </p>
            ) : null}
            {uploadLimitCopy ? (
              <p className={`mt-3 text-xs leading-5 ${isDark ? "text-slate-400" : "text-slate-600"}`}>
                {uploadLimitCopy}
              </p>
            ) : null}
            {!isManagingExisting && mode === "author" && canUploadAuthorMode ? (
              <div className={`mt-4 inline-flex w-full rounded-full p-1 ${isDark ? "border border-white/10 bg-white/5" : "border border-stone-200 bg-stone-100"}`}>
                <button
                  type="button"
                  onClick={() => {
                    setStartEmpty(false)
                    setFiles([])
                  }}
                  className={`flex-1 rounded-full px-4 py-2 text-sm font-medium transition ${
                    !startEmpty
                      ? isDark ? "bg-white text-slate-950" : "bg-white text-stone-950"
                      : isDark ? "text-slate-300 hover:bg-white/10" : "text-stone-600 hover:bg-white/70"
                  }`}
                >
                  Upload manuscript
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setStartEmpty(true)
                    setFiles([])
                  }}
                  className={`flex-1 rounded-full px-4 py-2 text-sm font-medium transition ${
                    startEmpty
                      ? isDark ? "bg-white text-slate-950" : "bg-white text-stone-950"
                      : isDark ? "text-slate-300 hover:bg-white/10" : "text-stone-600 hover:bg-white/70"
                  }`}
                >
                  Start empty project
                </button>
              </div>
            ) : null}
            {mode === "author" && !username ? (
              <div className={`mt-4 rounded-xl border p-4 ${isDark ? "border-amber-500/30 bg-amber-500/10" : "border-amber-300 bg-amber-50"}`}>
                <p className={`text-sm font-medium mb-2 ${isDark ? "text-amber-200" : "text-amber-800"}`}>Select a username to use Author mode</p>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={usernameInput}
                    onChange={(e) => setUsernameInput(e.target.value)}
                    aria-label="Username"
                    className={`flex-1 rounded-lg border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-white/5 text-slate-100" : "border-gray-300 bg-white text-slate-950"}`}
                    minLength={3}
                    maxLength={32}
                  />
                  <button
                    type="button"
                    onClick={() => void onSetUsername()}
                    disabled={settingUsername || usernameInput.length < 3}
                    className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-indigo-700 disabled:opacity-50"
                  >
                    {settingUsername ? "Saving..." : "Set"}
                  </button>
                </div>
                {usernameError && <p className="mt-2 text-xs text-red-400">{usernameError}</p>}
                <p className={`mt-2 text-xs ${isDark ? "text-amber-300/70" : "text-amber-600"}`}>
                  Select the username you want to appear publicly on LoreVia. New author uploads default to this username, but each manuscript can still use a different author or pen name.
                </p>
              </div>
            ) : null}
            {mode === "author" && existingAuthorBooks.length > 0 ? (
              <div className="mt-4">
                <label className={`mb-2 block text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-400" : "text-slate-500"}`}>
                  Manage existing author upload
                </label>
                <div className="relative" ref={existingBookMenuRef}>
                  <button
                    type="button"
                    aria-haspopup="listbox"
                    aria-expanded={existingBookMenuOpen}
                    onClick={() => setExistingBookMenuOpen((open) => !open)}
                    className={`flex w-full items-center justify-between rounded-lg border px-3 py-2.5 text-left text-sm ${isDark ? "border-white/10" : "border-gray-300"}`}
                    style={{ backgroundColor: "#ffffff", color: "#000000" }}
                  >
                    <span className="truncate">{existingBookSelectLabel}</span>
                    <span aria-hidden="true" className="ml-3 text-base leading-none">v</span>
                  </button>
                  {existingBookMenuOpen ? (
                    <div
                      role="listbox"
                      className="absolute z-50 mt-1 max-h-64 w-full overflow-auto rounded-lg border border-gray-300 bg-white py-1"
                    >
                      <button
                        type="button"
                        role="option"
                        aria-selected={existingBookId === ""}
                        onClick={() => {
                          setExistingBookId("")
                          setChapterNumberDirty(false)
                          setExistingBookMenuOpen(false)
                        }}
                        onMouseEnter={() => setHoveredExistingBookId("")}
                        onMouseLeave={() => setHoveredExistingBookId((current) => (current === "" ? null : current))}
                        className="block w-full px-3 py-2 text-left text-sm"
                        style={existingBookOptionStyle(existingBookId === "", hoveredExistingBookId === "")}
                      >
                        Create a new upload
                      </button>
                      {existingAuthorBooks.map((book) => (
                        <button
                          key={book.id}
                          type="button"
                          role="option"
                          aria-selected={existingBookId === book.id}
                          onClick={() => {
                            setExistingBookId(book.id)
                            setChapterNumberDirty(false)
                            setExistingBookMenuOpen(false)
                          }}
                          onMouseEnter={() => setHoveredExistingBookId(book.id)}
                          onMouseLeave={() => setHoveredExistingBookId((current) => (current === book.id ? null : current))}
                          className="block w-full px-3 py-2 text-left text-sm"
                          style={existingBookOptionStyle(existingBookId === book.id, hoveredExistingBookId === book.id)}
                        >
                          {book.title}
                        </button>
                      ))}
                    </div>
                  ) : null}
                </div>
              </div>
            ) : null}
          </div>

          <div className="space-y-3">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className={`text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-400" : "text-slate-500"}`}>Genres and moods</p>
                <p className={`mt-1 text-sm ${isDark ? "text-slate-400" : "text-slate-500"}`}>Optional tags help organize tone, genre, and mood.</p>
              </div>
              <span className={`text-xs ${isDark ? "text-slate-500" : "text-slate-400"}`}>{selectedTags.length}/8</span>
            </div>
          <div className={`group relative rounded-xl border p-1 transition-all ${
            isDark ? "border-white/10 bg-white/5 focus-within:border-indigo-500/50" : "border-gray-300 bg-white"
          }`}>
            <div className="flex items-center gap-2 px-2 py-1">
              <input
                type="text"
                value={customTag}
                onChange={e => setCustomTag(e.target.value)}
                aria-label="Add genres or moods"
                className="flex-1 bg-transparent py-1.5 text-sm outline-none"
              />
              {customTag.trim().length > 0 && (
                <button
                  type="button"
                  onClick={() => {
                    addTag(customTag)
                    setCustomTag("")
                  }}
                  className="rounded-lg bg-indigo-600 px-3 py-1 text-xs font-medium text-white transition hover:bg-indigo-700"
                >
                  Add
                </button>
              )}
            </div>

            {/* Suggestions dropdown - Triggers at 2 characters */}
            {shouldShowTagSuggestions && suggestedTags.length > 0 && (
              <div className={`mt-1 border-t ${isDark ? "border-white/10" : "border-gray-100"}`}>
                <div className="px-3 pt-3">
                  <p className={`text-3xs font-bold uppercase tracking-wider ${isDark ? "text-slate-500" : "text-slate-500"}`}>
                    Suggestions
                  </p>
                </div>
                <div className="max-h-40 overflow-y-auto px-2 pb-2 pt-2">
                  {suggestedTags.map((tag) => (
                    <button
                      key={tag}
                      type="button"
                      onClick={() => {
                        addTag(tag)
                        setCustomTag("")
                      }}
                      className={`mb-1 flex w-full items-center justify-between rounded-lg border px-3 py-2 text-left text-xs font-medium transition ${
                        isDark
                          ? "border-white/10 text-slate-200 hover:bg-white/10"
                          : "border-slate-200 text-slate-700 hover:bg-slate-50"
                      }`}
                    >
                      <span>{tag}</span>
                      <span className={isDark ? "text-slate-400" : "text-slate-400"}>Add</span>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
          {selectedTags.length > 0 ? (
            <div className="flex flex-wrap gap-2">
              {selectedTags.map((tag) => (
                <button
                  key={tag}
                  type="button"
                  onClick={() => removeTag(tag)}
                  className={`rounded-full border px-3 py-1.5 text-xs font-medium transition ${
                    isDark
                      ? "border-white/10 bg-white/[0.04] text-slate-200 hover:bg-white/10"
                      : "border-slate-200 bg-slate-50 text-slate-700 hover:bg-slate-100"
                  }`}
                >
                  {tag} x
                </button>
              ))}
            </div>
          ) : null}
          </div>

          {series.length > 0 ? (
            <div className={`rounded-xl border p-4 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-gray-200 bg-gray-50"}`}>
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className={`text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-400" : "text-slate-500"}`}>Add to series</p>
                  <p className={`mt-1 text-sm ${isDark ? "text-slate-400" : "text-slate-500"}`}>
                    Optional. Attach this upload to one or more existing series now.
                  </p>
                </div>
                <span className={`text-xs ${isDark ? "text-slate-500" : "text-slate-400"}`}>
                  {selectedSeriesIds.length} selected
                </span>
              </div>
              <div className="mt-4 flex flex-wrap gap-2">
                {series.map((seriesItem) => {
                  const selected = selectedSeriesIds.includes(seriesItem.id)
                  return (
                    <button
                      key={seriesItem.id}
                      type="button"
                      onClick={() => toggleSeries(seriesItem.id)}
                      className={`rounded-full border px-3 py-2 text-xs font-medium transition ${
                        selected
                          ? isDark
                            ? "border-indigo-400/40 bg-indigo-400/20 text-indigo-100"
                            : "border-indigo-300 bg-indigo-100 text-indigo-800"
                          : isDark
                            ? "border-white/10 text-slate-300 hover:bg-white/5"
                            : "border-slate-300 text-slate-700 hover:bg-white"
                      }`}
                    >
                      {seriesItem.name}
                    </button>
                  )
                })}
              </div>
            </div>
          ) : null}

    </>
  )
}
