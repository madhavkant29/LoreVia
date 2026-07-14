import { describe, expect, it, vi } from "vitest"
import { renderToStaticMarkup } from "react-dom/server"

import { WorldCorpusUploadCard } from "./WorldbuildingWorkspace.upload"

function file(name: string, size: number): File {
  return { name, size } as File
}

describe("Worldbuilding corpus upload card", () => {
  it("renders upload controls, selected files, and editor navigation", () => {
    const markup = renderToStaticMarkup(
      <WorldCorpusUploadCard
        bookId="book-1"
        focus="editor"
        isDark={false}
        uploadLimitNote="1,000/10,000 active words."
        uploadTitle="Atlas"
        uploadFiles={[
          file("atlas.md", 100),
          file("kingdoms.pdf", 200),
          file("laws.txt", 300),
          file("gods.md", 400),
          file("maps.pdf", 500),
        ]}
        replaceCorpusOnUpload={false}
        uploadingFiles={false}
        onUploadTitleChange={vi.fn()}
        onUploadFilesChange={vi.fn()}
        onReplaceCorpusOnUploadChange={vi.fn()}
        onUploadDocumentFiles={vi.fn()}
      />
    )

    expect(markup).toContain("Add or replace reference docs")
    expect(markup).toContain("Open World Gap Detection")
    expect(markup).toContain("1,000/10,000 active words.")
    expect(markup).toContain("5 files selected")
    expect(markup).toContain("atlas.md")
    expect(markup).toContain("+1 more")
    expect(markup).toContain("Add to corpus")
  })

  it("renders replace and uploading states", () => {
    const markup = renderToStaticMarkup(
      <WorldCorpusUploadCard
        bookId="book-1"
        focus="gap"
        isDark
        uploadLimitNote={null}
        uploadTitle=""
        uploadFiles={[file("atlas.md", 100)]}
        replaceCorpusOnUpload
        uploadingFiles
        onUploadTitleChange={vi.fn()}
        onUploadFilesChange={vi.fn()}
        onReplaceCorpusOnUploadChange={vi.fn()}
        onUploadDocumentFiles={vi.fn()}
      />
    )

    expect(markup).not.toContain("Open World Gap Detection")
    expect(markup).toContain("Replace active world corpus")
    expect(markup).toContain("Uploading...")
  })
})
