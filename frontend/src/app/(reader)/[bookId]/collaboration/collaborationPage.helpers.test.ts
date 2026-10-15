import { describe, expect, it } from "vitest"
import type { BookCollaborator } from "@/types/book"
import { applyCollaboratorRole, collaborationDate, collaboratorDraft, collaboratorMatches, collaboratorPayload, permissionSummary, roleLabel, scopeSummary, validateCollaboratorDraft, ROLE_OPTIONS } from "./collaborationPage.helpers"

const valid = () => ({ ...collaboratorDraft(), email: " Reader@Example.com ", displayName: " Reader " })
const person = { id: "one", email: "reader@example.com", display_name: null, role: "commenter", invite_status: "revoked", permissions: valid().permissions, scope: valid().scope } as BookCollaborator

describe("collaborator access drafts", () => {
  it("clones existing revoked access and keeps empty defaults independent", () => {
    const draft = collaboratorDraft(person)
    expect(draft).toMatchObject({ id: "one", restoring: true, from: "1", through: "", displayName: "" })
    draft.permissions.can_comment = false
    expect(person.permissions.can_comment).toBe(true)
    expect(collaboratorDraft().permissions.can_comment).toBe(true)
  })
  it.each(ROLE_OPTIONS)("applies the $label preset without losing typed chapter boundaries", ({ value }) => {
    const draft = applyCollaboratorRole({ ...valid(), from: "3", through: "9" }, value)
    expect(draft.role).toBe(value)
    expect(draft.from).toBe("3")
    expect(draft.scope.character_bible).toBe(draft.permissions.can_view_story_bible)
    expect(draft.scope.continuity_report).toBe(draft.permissions.can_run_ai_scans)
    expect(roleLabel(value)).toBeTruthy()
  })
  it.each(["", "no-at-sign", "reader@", "a b@example.com", `${"a".repeat(320)}@x.com`])("rejects malformed email %s", email => {
    expect(validateCollaboratorDraft({ ...valid(), email }, [])).toContain("valid email")
  })
  it("validates names and blocks duplicate active or revoked emails without blocking edits", () => {
    expect(validateCollaboratorDraft({ ...valid(), displayName: "a".repeat(121) }, [])).toContain("120")
    expect(validateCollaboratorDraft(valid(), [person])).toContain("already listed")
    expect(validateCollaboratorDraft({ ...valid(), id: person.id }, [person])).toBeNull()
  })
  it.each(["0", "-1", "1.5", "oops", "1e2", "9007199254740992"])("rejects unsafe chapter boundary %s", from => {
    expect(validateCollaboratorDraft({ ...valid(), from }, [])).toContain("positive whole")
  })
  it("accepts open and inclusive ranges, rejects reversed ranges, and ignores unused bounds", () => {
    expect(validateCollaboratorDraft({ ...valid(), from: " ", through: "" }, [])).toBeNull()
    expect(validateCollaboratorDraft({ ...valid(), from: "3", through: "3" }, [])).toBeNull()
    expect(validateCollaboratorDraft({ ...valid(), from: "3", through: "2" }, [])).toContain("later")
    expect(validateCollaboratorDraft(applyCollaboratorRole({ ...valid(), from: "oops" }, "editor"), [])).toBeNull()
  })
  it("normalizes identity, open bounds, and prevents flags from granting disabled resources", () => {
    const draft = { ...valid(), from: " ", through: "", displayName: " ", scope: { ...valid().scope, character_bible: true, continuity_report: true, reader_confusion_report: true } }
    expect(collaboratorPayload(draft)).toMatchObject({ email: "reader@example.com", displayName: null, scope: { chapter_start: null, chapter_end: null, character_bible: false, continuity_report: false, reader_confusion_report: false } })
    expect(collaboratorPayload({ ...valid(), from: "2", through: "5" }).scope).toMatchObject({ chapter_start: 2, chapter_end: 5 })
    expect(collaboratorPayload(applyCollaboratorRole(valid(), "editor")).scope.chapter_start).toBeNull()
  })
  it("provides readable summaries and case-insensitive status, name and role searches", () => {
    expect(permissionSummary(valid().permissions)).toBe("Comments")
    expect(permissionSummary(applyCollaboratorRole(valid(), "viewer").permissions)).toBe("Read only")
    expect(scopeSummary(valid().scope, valid().permissions)).toBe("Chapters 1–end")
    expect(scopeSummary({ ...valid().scope, chapter_start: NaN }, valid().permissions)).toBe("Enter a valid chapter range")
    expect(scopeSummary(valid().scope, applyCollaboratorRole(valid(), "editor").permissions)).toBe("All chapters")
    expect(roleLabel("future_role")).toBe("future role")
    expect(collaboratorMatches(person, "READER", "revoked")).toBe(true)
    expect(collaboratorMatches(person, "commenter", "all")).toBe(true)
    expect(collaboratorMatches(person, "", "active")).toBe(false)
    expect(collaboratorMatches(person, "missing", "all")).toBe(false)
  })
  it("handles missing and invalid activity dates without throwing", () => {
    expect(collaborationDate(null)).toBe("Date unavailable")
    expect(collaborationDate("bad")).toBe("Date unavailable")
    expect(collaborationDate("2026-10-14T12:00:00Z")).not.toBe("Date unavailable")
  })
})
