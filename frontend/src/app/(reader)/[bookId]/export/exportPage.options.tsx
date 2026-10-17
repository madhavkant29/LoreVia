import type { NovelExportPreset, NovelImagePlacement } from "@/types/book"
import type { ReaderFontFamily } from "@/lib/utils/readerTypography"
import { READER_FONT_OPTIONS } from "@/lib/utils/readerTypography"
import { EPUB_FIELDS, FRONT_MATTER_FIELDS, type NovelSettings } from "./exportPage.helpers"

export type ExportOptions = {
  font: ReaderFontFamily; manuscript: "docx" | "pdf" | "epub" | "vault"; bible: "md" | "pdf" | "docx" | "vault_folder";
  novel: "pdf" | "docx" | "epub"; preset: NovelExportPreset; scenes: boolean; toc: boolean; sample: boolean;
  images: boolean; imagePlacement: NovelImagePlacement; captions: boolean;
}
export const DEFAULT_EXPORT_OPTIONS: ExportOptions = { font: "serif", manuscript: "docx", bible: "vault_folder", novel: "pdf", preset: "standard_novel", scenes: true, toc: false, sample: false, images: false, imagePlacement: "inline", captions: false }
export const MANUSCRIPT_FORMATS = ["docx", "pdf", "epub", "vault"] as const
export const NOVEL_FORMATS = ["pdf", "docx", "epub"] as const
export const BIBLE_FORMATS = ["vault_folder", "docx", "pdf", "md"] as const
const field = "export-field mt-2 min-h-11 w-full border border-[rgb(var(--border))] bg-[rgb(var(--background))] px-3 text-sm"
const muted = "text-[rgb(var(--muted-foreground))]"

export function FormatChoices<T extends string>({ values, value, onChange }: { values: readonly T[]; value: T; onChange: (value: T) => void }) {
  return <div role="group" aria-label="File format" className="mt-3 flex flex-wrap gap-2">{values.map((format) => <button type="button" key={format} aria-pressed={value === format} onClick={() => onChange(format)} className={`min-h-11 border px-4 py-2 text-sm font-medium ${value === format ? "border-[rgb(var(--accent))] bg-[rgb(var(--card))] underline underline-offset-4" : "border-[rgb(var(--border))]"}`}>{format.startsWith("vault") ? "Vault ZIP" : format === "md" ? "Markdown" : format.toUpperCase()}</button>)}</div>
}

export function ExportFont({ value, onChange }: { value: ReaderFontFamily; onChange: (value: ReaderFontFamily) => void }) {
  return <div className="max-w-xl border-b border-[rgb(var(--border))] pb-5"><label className="text-sm font-medium">Export font<select value={value} onChange={(event) => onChange(event.target.value as ReaderFontFamily)} className={field}>{READER_FONT_OPTIONS.map((font) => <option key={font.value} value={font.value}>{font.label}</option>)}</select></label><p className={`mt-2 text-sm leading-6 ${muted}`}>DOCX and EPUB request this font. PDF uses built-in alternatives; font files are not embedded.</p></div>
}

function Toggle({ checked, onChange, label, description }: { checked: boolean; onChange: (value: boolean) => void; label: string; description: string }) {
  return <label className="mt-4 flex items-start gap-3 text-sm leading-6"><input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} className="mt-1 h-4 w-4 shrink-0" /><span><span className="block font-medium">{label}</span><span className={`block ${muted}`}>{description}</span></span></label>
}

export function ManuscriptOptions({ options, update }: { options: ExportOptions; update: (patch: Partial<ExportOptions>) => void }) {
  return <><FormatChoices values={MANUSCRIPT_FORMATS} value={options.manuscript} onChange={(manuscript) => update({ manuscript })} /><Toggle checked={options.scenes} onChange={(scenes) => update({ scenes })} label="Include scene metadata" description="Turn off for clean prose with scene breaks shown as ***." /><Toggle checked={options.toc} onChange={(toc) => update({ toc })} label="Add table of contents" description="PDF includes generated page numbers. In Word, update the table field after opening." /></>
}

export function NovelOptions({ options, update }: { options: ExportOptions; update: (patch: Partial<ExportOptions>) => void }) {
  return <>
    <p className="text-sm font-medium">Novel export</p><p className={`mt-2 text-sm leading-6 ${muted}`}>Cover, contents, saved publishing details, chapters, and end marker.</p>
    <FormatChoices values={NOVEL_FORMATS} value={options.novel} onChange={(novel) => update({ novel })} />
    <label className="mt-4 block max-w-xl text-sm font-medium">Page template<select className={field} value={options.preset} onChange={(event) => update({ preset: event.target.value as NovelExportPreset })}><option value="standard_novel">Standard novel</option><option value="trade_novel">Trade paperback</option><option value="large_print">Large print</option><option value="ebook_optimized">eBook optimized</option></select></label>
    <p className={`mt-2 text-sm ${muted}`}>{({ standard_novel: "A5 pages and compact margins.", trade_novel: "6 × 9 inch trim and balanced margins.", large_print: "Letter pages and larger text.", ebook_optimized: "Compact layout for digital reading." })[options.preset]}</p>
    {options.novel === "docx" ? <p className={`mt-3 text-sm ${muted}`}>In Word, right-click the contents table and choose Update Field to refresh page numbers.</p> : null}
    <Toggle checked={options.sample} onChange={(sample) => update({ sample })} label="Export first 2 chapters only" description="Create a sample to check formatting, links, and images." />
    <Toggle checked={options.images} onChange={(images) => update({ images })} label="Include chapter images" description="Includes stored images where available; unreadable or missing images are skipped." />
    {options.images ? <div className="mt-4 max-w-xl"><label className="text-sm font-medium">Image placement<select className={field} value={options.imagePlacement} onChange={(event) => update({ imagePlacement: event.target.value as NovelImagePlacement })}><option value="inline">Inline markers</option><option value="end">Chapter end</option><option value="plates">Separate image plates</option></select></label><Toggle checked={options.captions} onChange={(captions) => update({ captions })} label="Include stored captions" description="Add available caption text below each image." /></div> : null}
  </>
}

export function PublishingDetails({ draft, onChange, dirty, busy, error, onSave, onDiscard }: { draft: NovelSettings; onChange: (draft: NovelSettings) => void; dirty: boolean; busy: boolean; error: string | null; onSave: () => void; onDiscard: () => void }) {
  return <details className="mt-6 border-y border-[rgb(var(--border))] py-4"><summary className="cursor-pointer text-sm font-semibold">Publishing details{dirty ? " · unsaved changes" : ""}</summary><fieldset disabled={busy} className="mt-4 min-w-0">
    <p className={`mb-4 text-sm leading-6 ${muted}`}>These details are saved with the book and used in reader editions. Save changes before exporting.</p>
    <label className="block text-sm font-medium">Preface<textarea aria-label="Preface" value={draft.preface} onChange={(event) => onChange({ ...draft, preface: event.target.value })} rows={4} className={`${field} py-3 leading-6`} /></label>
    <div className="mt-4 grid gap-4 md:grid-cols-2">{FRONT_MATTER_FIELDS.map(([key, label]) => <label key={key} className="block text-sm font-medium">{label}<textarea aria-label={label} value={draft.front_matter[key]} onChange={(event) => onChange({ ...draft, front_matter: { ...draft.front_matter, [key]: event.target.value } })} rows={3} className={`${field} py-3 leading-6`} /></label>)}</div>
    <div className="mt-4 grid gap-4 md:grid-cols-2">{EPUB_FIELDS.map(([key, label]) => <label key={key} className={`block text-sm font-medium ${key === "description" ? "md:col-span-2" : ""}`}>{label}{key === "description" ? <textarea aria-label={label} rows={4} value={draft.epub_metadata[key]} onChange={(event) => onChange({ ...draft, epub_metadata: { ...draft.epub_metadata, [key]: event.target.value } })} className={`${field} py-3 leading-6`} /> : <input aria-label={label} value={draft.epub_metadata[key]} onChange={(event) => onChange({ ...draft, epub_metadata: { ...draft.epub_metadata, [key]: event.target.value } })} className={field} />}</label>)}</div>
    {error ? <p role="alert" className="mt-3 text-sm text-rose-700 dark:text-rose-300">{error}</p> : null}
    <div className="mt-4 flex flex-wrap gap-3"><button type="button" className="app-button-primary" disabled={!dirty || !!error} onClick={onSave}>Save novel settings</button><button type="button" className="app-button-secondary" disabled={!dirty} onClick={onDiscard}>Discard publishing changes</button></div>
  </fieldset></details>
}
